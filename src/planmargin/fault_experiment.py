"""Interactive execution of the existing deterministic fault/recovery protocols.

Three policies run twice: baseline, sustained command loss, and protection.
The four-role replay format shares the measured no-fault primary baseline;
it does NOT represent four independently executed policies or eight rollouts.
"""

from __future__ import annotations

import copy
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

from planmargin.experiment_jobs import (
    JOBS,
    MANIFEST,
    ExperimentConfig,
    confined,
    digest,
    protocol_for,
    read_json,
    write_json,
)


def fault_mutation(plan: str) -> dict[str, Any]:
    """Schema-complete command intervention, not a modification of traffic."""
    if plan not in {"command_dropout", "assistance_handoff"}:
        raise ValueError("Unsupported command-fault protocol")
    return {
        "schema_version": 1,
        "mutation_type": plan,
        "accepted": True,
        "rejection_reasons": [],
        "parameters": {
            "fault_onset_seconds": 2.0,
            **({"recovery_seconds": 3.0} if plan == "assistance_handoff" else {}),
        },
    }


def execute_fault(
    root: Path, job_id: str, config: ExperimentConfig, progress: Any
) -> None:
    import jax
    import tensorflow as tf
    from planmargin import (
        assistance_handoff,
        controller_comparison as controllers,
        fault_protection,
        family_validation,
        random_search,
        rollout_record,
        scenario_selection,
        speed_mutation,
    )

    directory = confined(root, JOBS / job_id)
    request = read_json(directory / "request.json")
    manifest = confined(root, MANIFEST)
    family_validation.load_manifest_candidates(manifest)
    manifest_hash = random_search._file_sha256(manifest)
    from planmargin import experiment_jobs, experiment_worker, interaction_metrics

    modules = (
        assistance_handoff,
        controllers,
        fault_protection,
        family_validation,
        rollout_record,
        scenario_selection,
        speed_mutation,
        experiment_jobs,
        experiment_worker,
        interaction_metrics,
    )
    paths = {module.__name__: Path(module.__file__) for module in modules}
    paths[__name__] = Path(__file__)
    schema_path = confined(
        root, Path("schemas/rollout-record-collection-v1.1.schema.json")
    )
    paths["collection_schema"] = schema_path
    hashes = {name: random_search._file_sha256(path) for name, path in paths.items()}
    progress.stage("loading")
    scenario, candidate = speed_mutation._load_selected_scenario(
        manifest, config.selection_order
    )
    target = candidate["interacting_object_index"]
    captured: dict[str, dict[str, Any]] = {}

    class Capture:
        def __init__(self, name: str, runner: Any) -> None:
            self.name, self.runner = name, runner

        def run_twice(self, state: Any) -> dict[str, Any]:
            progress.stage(self.name)
            before = controllers._non_sdc_log_hash(state)
            value = self.runner.run_twice(state)
            value["non_sdc_input_sha256"] = before
            value["input_unchanged_after_rollout"] = (
                before == controllers._non_sdc_log_hash(state)
            )
            captured[self.name] = value
            return value

    recovery = config.test_plan == "assistance_handoff"
    baseline = Capture(
        "baseline", controllers.ControllerRunner(controllers.TESTED_CONTROLLER)
    )
    unprotected = Capture(
        "unprotected",
        fault_protection.FaultControllerRunner(protected=False, fault_onset_step=20),
    )
    protected = Capture(
        "protected",
        fault_protection.FaultControllerRunner(
            protected=True, fault_onset_step=20, recovery_step=30 if recovery else None
        ),
    )
    if recovery:
        qualification = assistance_handoff._qualify_scene(
            scenario, baseline=baseline, unprotected=unprotected, assisted=protected
        )
    else:
        qualification = fault_protection._qualify_scene(
            scenario, baseline=baseline, unprotected=unprotected, protected=protected
        )
    progress.stage("behavior_validation")
    if not all(value["input_unchanged_after_rollout"] for value in captured.values()):
        raise RuntimeError("Simulation inputs changed during the test")
    passed = all(qualification["gates"].values())
    specs = {}
    for role, protection in (("tested", False), ("reference", True)):
        specs[role] = {
            "controller_id": f"{protocol_for(config)}-{'protected' if protection else 'unprotected'}",
            "role": role,
            "primary": controllers.TESTED_CONTROLLER.report(),
            "fallback": controllers.REFERENCE_CONTROLLER.report()
            if protection
            else None,
            "fault_onset_step": 20,
            "recovery_step": 30 if recovery and protection else None,
            "behavior": "conservative IDM fallback"
            if protection
            else "hold last commanded pose",
        }

    def with_policy(value: dict[str, Any], role: str) -> dict[str, Any]:
        result = copy.deepcopy(value)
        result["controller"] = specs[role]
        return result

    rollouts = {
        "original": {role: with_policy(captured["baseline"], role) for role in specs},
        "mutated": {
            "tested": with_policy(captured["unprotected"], "tested"),
            "reference": with_policy(captured["protected"], "reference"),
        },
    }
    events = []
    for key, label in (
        ("fault_activated_timestep", "Command lost · fallback activated"),
        ("primary_recovered_timestep", "Recovery signal · primary resumed"),
    ):
        timestep = captured["protected"].get(key)
        if timestep is not None:
            step = timestep - speed_mutation.CURRENT_TIMESTEP
            events.append({"step": step, "time_seconds": step / 10.0, "label": label})
    result = {
        "schema_version": "1.0.0",
        "job_id": job_id,
        "protocol": protocol_for(config),
        "config": config.record(),
        "controller_specs": specs,
        "execution": {
            key: request.get(key) for key in ("completion_deadline_seconds", "rerun_of")
        },
        "decision": "checks_passed" if passed else "checks_failed",
        "explanation": (
            "All deterministic fault/recovery checks passed."
            if passed
            else "One or more fault/recovery checks failed. Inspect the gates and trajectories."
        )
        + " The traffic recording is unchanged; the injected fault affects the primary controller's commands.",
        "gates": qualification["gates"],
        "qualification": qualification,
        "behavior_events": events,
        "physical_rollouts": 6,
        "replay_baseline": "One measured primary baseline is shared by both original replay roles. Three distinct policies, each executed twice.",
        "finding": {
            "behavior_checks_passed": passed,
            "policy_specific_avoidable_failure": False,
        },
        "support_probability": None,
        "rejection_reasons": [],
        "controllers": {
            role: family_validation._controller_record(
                scenario,
                target,
                rollouts["mutated"][role],
                captured["baseline"]["trajectory_sha256"],
            )
            for role in specs
        },
        "original_controllers": {
            role: family_validation._controller_record(
                scenario, target, captured["baseline"], None
            )
            for role in specs
        },
        "provenance": {
            "selection_manifest_sha256": manifest_hash,
            "source_sha256": hashes,
            "waymax_revision": scenario_selection.WAYMAX_GIT_COMMIT,
            "python": platform.python_version(),
            "jax": jax.__version__,
        },
        "boundary": "Local deterministic command-fault test on a real WOMD scenario. Recovery uses a scripted test signal, not Gemini or a human operator. Not a Waymo Driver, remote-assistance service, or fleet-safety claim.",
    }
    progress.stage("export")
    source = {
        "schema_version": 1,
        "status": "passed",
        "dataset": {
            "name": "Waymo Open Motion Dataset",
            "version": scenario_selection.DATASET_VERSION,
            "split": scenario_selection.SPLIT,
            **{
                key: candidate[key]
                for key in ("scenario_id", "source_shard", "record_index")
            },
            "selection_order": config.selection_order,
            "mutated_object_index": target,
        },
        "mutation": fault_mutation(config.test_plan),
        "controllers": specs,
        "acceptance": result["gates"],
        "finding": result["finding"],
        "metric_definition": {
            "success_requires": [
                "no overlap",
                "no offroad",
                "valid and complete rollout",
            ],
            "qualification": "All named behavior gates, including progress recovery and determinism",
        },
        "rollouts": rollouts,
        "scene_context": controllers.build_scene_context(
            scenario, scenario, target, rollouts
        ),
        "environment": {
            **scenario_selection._git_provenance(),
            **result["provenance"],
            "tensorflow": tf.__version__,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "jax_backend": jax.default_backend(),
            "waymax_git_commit": scenario_selection.WAYMAX_GIT_COMMIT,
            "comparison_source_sha256": hashes[__name__],
            "seed": scenario_selection.SEED,
        },
        "limitations": [result["boundary"], result["replay_baseline"]],
    }
    collection = rollout_record.export_collection(source)
    from jsonschema import Draft202012Validator

    Draft202012Validator(json.loads(schema_path.read_text())).validate(collection)
    collection_path = directory / "collection.json"
    write_json(collection_path, collection)
    result["collection_sha256"] = hashlib.sha256(
        collection_path.read_bytes()
    ).hexdigest()
    if random_search._file_sha256(manifest) != manifest_hash or any(
        random_search._file_sha256(path) != hashes[name] for name, path in paths.items()
    ):
        raise RuntimeError(
            "Inputs or source changed during execution; rerun on stable code"
        )
    result["result_sha256"] = digest(result)
    write_json(directory / "result.json", result)
    progress.stage("complete")
