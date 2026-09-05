"""Execute one user-configured experiment in an isolated, cancellable process."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import os
import platform
import threading
import time
from pathlib import Path
from typing import Any

from planmargin.experiment_jobs import (
    JOBS,
    MANIFEST,
    PROTOCOL,
    STAGES,
    ExperimentConfig,
    confined,
    digest,
    read_json,
    support_path,
    write_json,
)


class Progress:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.started = time.monotonic()
        self.events: list[dict[str, Any]] = []

    def stage(self, name: str) -> None:
        elapsed = round(time.monotonic() - self.started, 3)
        if self.events:
            self.events[-1]["duration_seconds"] = round(
                elapsed - self.events[-1]["started_seconds"], 3
            )
            self.events[-1]["status"] = "completed"
        self.events.append(
            {
                "stage": name,
                "label": STAGES[name],
                "started_seconds": elapsed,
                "duration_seconds": 0.0 if name == "complete" else None,
                "status": "completed" if name == "complete" else "running",
            }
        )
        write_json(
            self.directory / "progress.json", {"stage": name, "events": self.events}
        )


def build_tested_controller(config: ExperimentConfig) -> Any:
    """Leave the frozen controller untouched; identify custom specs by content."""
    from planmargin.controller_comparison import TESTED_CONTROLLER

    if config.tested_controller is None:
        return TESTED_CONTROLLER
    parameters = config.tested_controller.model_dump()
    return dataclasses.replace(
        TESTED_CONTROLLER,
        controller_id=f"planmargin-custom-idm-{digest(parameters)[:16]}",
        **parameters,
    )


def execute(root: Path, job_id: str) -> None:
    directory = confined(root, JOBS / job_id)
    request = read_json(directory / "request.json")
    if request.get("job_id") != job_id or request.get("protocol") != PROTOCOL:
        raise ValueError("Invalid worker request identity")
    config = ExperimentConfig.model_validate(request["config"])
    progress = Progress(directory)
    progress.stage("inputs")
    # Heavy libraries initialize only inside the worker, never during API polling.
    import jax
    import tensorflow as tf

    from planmargin import (
        controller_comparison as controllers,
        experiment_jobs,
        empirical_support,
        family_validation,
        lead_braking,
        matched_coordinator,
        matched_waymax,
        random_search,
        rollout_record,
        scenario_selection,
        speed_mutation,
    )

    manifest_path = confined(root, MANIFEST)
    family_validation.load_manifest_candidates(manifest_path)
    support_file = support_path(root)
    support_model = (
        empirical_support.load_model(support_file) if support_file.exists() else None
    )
    input_hash = random_search._file_sha256(manifest_path)
    source_files = {
        module.__name__: Path(module.__file__)
        for module in (
            controllers,
            experiment_jobs,
            empirical_support,
            family_validation,
            lead_braking,
            matched_coordinator,
            matched_waymax,
            rollout_record,
            scenario_selection,
            speed_mutation,
        )
    }
    source_files["planmargin.experiment_worker"] = Path(__file__)
    source_hashes = {
        name: random_search._file_sha256(path) for name, path in source_files.items()
    }
    progress.stage("loading")
    # This loader scans only the selected source shard, not all ten scenarios.
    scenario, candidate = speed_mutation._load_selected_scenario(
        manifest_path, config.selection_order
    )
    object_index = candidate["interacting_object_index"]
    variant = "original"
    rollouts: dict[str, dict[str, Any]] = {"original": {}, "mutated": {}}

    class RecordingRunner:
        def __init__(self, spec: controllers.ControllerSpec) -> None:
            self.spec = spec
            self.runner = controllers.ControllerRunner(spec)

        def run_twice(self, state: Any) -> dict[str, Any]:
            progress.stage(f"{variant}_{self.spec.role}")
            before = controllers._non_sdc_log_hash(state)
            result = self.runner.run_twice(state)
            result["non_sdc_input_sha256"] = before
            result["input_unchanged_after_rollout"] = (
                before == controllers._non_sdc_log_hash(state)
            )
            rollouts[variant][self.spec.role] = result
            return result

    adapter = matched_waymax.WaymaxEvaluatorAdapter(
        runner_factory=RecordingRunner,
        support_scorer=lambda model, vector: empirical_support.score_vector(
            model, vector
        )
        if model
        else {},
    )
    tested, reference = (
        build_tested_controller(config),
        controllers.REFERENCE_CONTROLLER,
    )
    original = adapter.evaluate_original(scenario, candidate, tested, reference)
    variant = "mutated"
    progress.stage("mutation")
    parameters = config.model_dump(exclude={"selection_order", "tested_controller"})
    evaluation = adapter.evaluate_attempt(
        scenario,
        candidate,
        parameters,
        tested,
        reference,
        support_model or {},
        original,
    )
    attempt = evaluation["attempt"]
    progress.stage("validation")
    matched_coordinator._validate_feature_record(
        evaluation["feature"], attempt["status"]
    )
    support = (
        matched_coordinator._support_score(support_model, evaluation["feature"])
        if support_model
        else None
    )
    pipeline = matched_coordinator._pipeline_passes(attempt) and all(
        item["outputs_identical"] and item["input_unchanged_after_rollout"]
        for group in rollouts.values()
        for item in group.values()
    )
    finding = matched_coordinator._derive_finding(
        original=original, attempt=attempt, pipeline_passes=pipeline, support=support
    )
    result: dict[str, Any] = {
        "schema_version": "1.0.0",
        "job_id": job_id,
        "protocol": PROTOCOL,
        "config": config.record(),
        "controller_specs": {
            "tested": tested.report(),
            "reference": reference.report(),
        },
        "decision": "invalid_mutation",
        "explanation": "The scenario change failed the mutation or map-validity gate. No planner failure is claimed.",
        "finding": finding,
        "support_probability": support["p_support"] if support else None,
        "gates": {
            "original_planners_succeed": original["eligible"],
            "mutation_valid": attempt["status"] == "accepted",
            "reproducible": pipeline,
            "empirical_support": bool(support and support["passes"]),
            "reference_planner_succeeds": bool(
                attempt["controllers"]
                and attempt["controllers"]["reference"]["outcome"]["success"]
            ),
            "tested_planner_fails": bool(
                attempt["controllers"]
                and not attempt["controllers"]["tested"]["outcome"]["success"]
            ),
        },
        "controllers": attempt["controllers"],
        "original_controllers": original["controllers"],
        "rejection_reasons": attempt["mutation"].get("rejection_reasons", []),
        "collection_sha256": None,
        "provenance": {
            "selection_manifest_sha256": input_hash,
            "support_model_sha256": support_model["model_sha256"]
            if support_model
            else None,
            "worker_sha256": random_search._file_sha256(Path(__file__)),
            "source_sha256": source_hashes,
            "waymax_revision": scenario_selection.WAYMAX_GIT_COMMIT,
            "python": platform.python_version(),
            "jax": jax.__version__,
        },
        "boundary": "Exploratory single-case execution. Separate from the frozen campaign; not a Waymo Driver or fleet-safety claim. Licensed local evidence.",
    }
    if attempt["status"] == "accepted":
        if not pipeline:
            raise RuntimeError(
                "Simulation reproducibility or input immutability failed"
            )
        mutation_config = lead_braking.LeadBrakingMutationConfig(**parameters)
        mutated, mutation = lead_braking.apply_lead_braking_mutation(
            scenario, object_index, mutation_config
        )
        if mutated is None:
            raise RuntimeError("Mutation could not be reconstructed")
        decision = (
            "qualified"
            if finding and finding["policy_specific_avoidable_failure"]
            else "not_qualified"
        )
        reason = (
            "Every tested finding gate passed for this exploratory case. This does not alter the frozen campaign."
            if decision == "qualified"
            else "The tested planner succeeds under this change; this is not a planner regression."
            if attempt["controllers"]["tested"]["outcome"]["success"]
            else "The tested planner fails, but not every realism, original-pass, and reference-success gate passes. This is not a qualified regression."
        )
        if support_model is None:
            reason += " Empirical support is not prepared, so realism qualification is unavailable."
        result.update(decision=decision, explanation=reason)
        progress.stage("export")
        source = {
            "schema_version": 1,
            "status": "passed",
            "dataset": {
                "name": "Waymo Open Motion Dataset",
                "version": scenario_selection.DATASET_VERSION,
                "split": scenario_selection.SPLIT,
                "scenario_id": candidate["scenario_id"],
                "source_shard": candidate["source_shard"],
                "record_index": candidate["record_index"],
                "selection_order": config.selection_order,
                "mutated_object_index": object_index,
            },
            "mutation": attempt["mutation"],
            "controllers": {"tested": tested.report(), "reference": reference.report()},
            "metric_definition": {
                "success_requires": [
                    "zero SDC overlap",
                    "zero SDC offroad",
                    "valid SDC at every step",
                    "complete 80-step rollout",
                ]
            },
            "acceptance": result["gates"],
            "finding": finding,
            "rollouts": rollouts,
            "scene_context": controllers.build_scene_context(
                scenario, mutated, object_index, rollouts
            ),
            "environment": {
                **scenario_selection._git_provenance(),
                **result["provenance"],
                "tensorflow": tf.__version__,
                "platform": platform.platform(),
                "machine": platform.machine(),
                "jax_backend": jax.default_backend(),
                "waymax_git_commit": scenario_selection.WAYMAX_GIT_COMMIT,
                "comparison_source_sha256": result["provenance"]["worker_sha256"],
                "seed": scenario_selection.SEED,
            },
            "limitations": [
                result["boundary"],
                "Both controllers use Waymax IDM; this is a configuration comparison.",
            ],
        }
        collection = rollout_record.export_collection(source)
        collection_path = directory / "collection.json"
        write_json(collection_path, collection)
        result["collection_sha256"] = hashlib.sha256(
            collection_path.read_bytes()
        ).hexdigest()
    if random_search._file_sha256(manifest_path) != input_hash:
        raise RuntimeError("Selection inputs changed during execution")
    if any(
        random_search._file_sha256(path) != source_hashes[name]
        for name, path in source_files.items()
    ):
        raise RuntimeError(
            "Experiment source changed during execution; rerun on stable code"
        )
    result["result_sha256"] = digest(result)
    write_json(directory / "result.json", result)
    progress.stage("complete")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()
    import re

    if not re.fullmatch(r"[0-9a-f]{32}", args.job_id):
        raise ValueError("Invalid job ID")
    parent = os.getppid()

    def stop_if_orphaned() -> None:
        while True:
            time.sleep(1)
            if os.getppid() != parent:
                os._exit(2)

    threading.Thread(target=stop_if_orphaned, daemon=True).start()
    execute(args.root.resolve(), args.job_id)


if __name__ == "__main__":
    main()
