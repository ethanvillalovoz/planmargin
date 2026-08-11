"""Validate the lead-braking family on a fixed ten-scenario parameter grid."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import platform
import resource
import sys
import time
from pathlib import Path
from typing import Any

import jax
import numpy as np
import tensorflow as tf

from planmargin import controller_comparison
from planmargin import interaction_metrics
from planmargin import lead_braking
from planmargin import scenario_selection
from planmargin import speed_mutation

DEFAULT_MANIFEST = Path("artifacts/stage-0/scenario-selection.json")
DEFAULT_OUTPUT = Path("artifacts/family-validation/lead-braking-family.json")
ONSET_OFFSETS_S = (0.0, 0.2, 0.5)
SPEED_MULTIPLIERS = (0.75, 0.8, 1.0)
EXPECTED_SCENARIOS = 10
MIN_ELIGIBLE_SCENARIOS = 8
MIN_NONIDENTITY_VALID_RATE = 0.60
MIN_TESTED_RESPONSE_RATE = 0.80
MIN_VARYING_SCENARIOS = 5
MIN_SEPARATION_RANGE_M = 0.5
MIN_TTC_RANGE_S = 0.5


def parameter_grid() -> tuple[tuple[float, float], ...]:
    """Return the immutable onset-offset/speed-multiplier probe grid."""
    return tuple(itertools.product(ONSET_OFFSETS_S, SPEED_MULTIPLIERS))


def is_identity_point(onset_offset_s: float, speed_multiplier: float) -> bool:
    return onset_offset_s == 0.0 and speed_multiplier == 1.0


def load_manifest_candidates(manifest_path: Path) -> list[dict[str, Any]]:
    """Load and validate the ordered private lead-braking candidate set."""
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Local selection manifest not found: {manifest_path}. "
            "Run planmargin-select-scenarios first."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != EXPECTED_SCENARIOS:
        raise ValueError(
            f"Expected exactly {EXPECTED_SCENARIOS} selected scenarios."
        )
    if any(not isinstance(candidate, dict) for candidate in candidates):
        raise ValueError("Manifest candidates must be objects.")
    if any(
        candidate.get("family") != "lead_vehicle_braking"
        for candidate in candidates
    ):
        raise ValueError("Family validation requires only lead-vehicle-braking scenarios.")
    selection_orders = [
        candidate.get("selection_order") for candidate in candidates
    ]
    if any(
        not isinstance(selection_order, int)
        or isinstance(selection_order, bool)
        for selection_order in selection_orders
    ):
        raise ValueError("Manifest selection orders must be integers.")
    if sorted(selection_orders) != list(range(1, EXPECTED_SCENARIOS + 1)):
        raise ValueError(
            "Manifest selection orders must be unique and contiguous from 1 to "
            f"{EXPECTED_SCENARIOS}."
        )
    scenario_ids = [candidate.get("scenario_id") for candidate in candidates]
    if any(
        not isinstance(scenario_id, str) or not scenario_id
        for scenario_id in scenario_ids
    ):
        raise ValueError("Manifest scenario IDs must be non-empty strings.")
    if len(set(scenario_ids)) != EXPECTED_SCENARIOS:
        raise ValueError("Manifest scenario IDs must be unique.")
    return sorted(candidates, key=lambda candidate: candidate["selection_order"])


def _load_manifest_scenarios(
    manifest_path: Path,
) -> list[tuple[Any, dict[str, Any]]]:
    candidates = load_manifest_candidates(manifest_path)
    by_shard: dict[int, dict[int, dict[str, Any]]] = {}
    for candidate in candidates:
        shard_index = candidate.get("shard_index")
        record_index = candidate.get("record_index")
        if not isinstance(shard_index, int) or not isinstance(record_index, int):
            raise ValueError("Manifest candidate source location is incomplete.")
        shard_targets = by_shard.setdefault(shard_index, {})
        if record_index in shard_targets:
            raise ValueError("Manifest contains duplicate source records.")
        shard_targets[record_index] = candidate

    loaded: list[tuple[Any, dict[str, Any]]] = []
    for shard_index, targets in sorted(by_shard.items()):
        uri = scenario_selection._training_shard_uri(shard_index)
        dataset = tf.data.TFRecordDataset(
            [uri], buffer_size=8 * 1024 * 1024
        )
        for record_index, serialized in enumerate(dataset):
            candidate = targets.get(record_index)
            if candidate is None:
                if record_index > max(targets):
                    break
                continue
            record = serialized.numpy()
            arrays = scenario_selection._scenario_arrays(record)
            if arrays.scenario_id != candidate.get("scenario_id"):
                raise RuntimeError(
                    "Manifest scenario ID does not match source record."
                )
            loaded.append(
                (scenario_selection._waymax_scenario(record), candidate)
            )
            if len(loaded) == len(candidates):
                break
        missing = set(targets) - {
            candidate["record_index"]
            for _, candidate in loaded
            if candidate["shard_index"] == shard_index
        }
        if missing:
            raise RuntimeError("Manifest records were not found in source shard.")
    return sorted(loaded, key=lambda item: item[1]["selection_order"])


def _aligned_tracks(
    scenario: Any,
    object_index: int,
    rollout: dict[str, Any],
) -> tuple[dict[str, list[Any]], dict[str, list[Any]]]:
    trace = rollout["trajectory"]
    timesteps = np.asarray(trace["timestep"], dtype=int)
    trajectory = scenario.log_trajectory
    sdc_indices = np.flatnonzero(
        np.asarray(scenario.object_metadata.is_sdc, dtype=bool)
    )
    if sdc_indices.size != 1:
        raise ValueError(f"Expected one SDC, found {sdc_indices.size}.")
    sdc_index = int(sdc_indices[0])

    def values(field: str, index: int) -> list[Any]:
        return np.asarray(getattr(trajectory, field))[index, timesteps].tolist()

    sdc = {
        "x_m": trace["x_m"],
        "y_m": trace["y_m"],
        "yaw_rad": trace["yaw_rad"],
        "vel_x_mps": trace["vel_x_mps"],
        "vel_y_mps": trace["vel_y_mps"],
        "length_m": values("length", sdc_index),
        "width_m": values("width", sdc_index),
        "valid": trace["valid"],
    }
    lead = {
        "x_m": values("x", object_index),
        "y_m": values("y", object_index),
        "yaw_rad": values("yaw", object_index),
        "vel_x_mps": values("vel_x", object_index),
        "vel_y_mps": values("vel_y", object_index),
        "length_m": values("length", object_index),
        "width_m": values("width", object_index),
        "valid": [bool(value) for value in values("valid", object_index)],
    }
    return sdc, lead


def _controller_record(
    scenario: Any,
    object_index: int,
    rollout: dict[str, Any],
    original_hash: str | None,
) -> dict[str, Any]:
    sdc, lead = _aligned_tracks(scenario, object_index, rollout)
    return {
        "outputs_identical": rollout["outputs_identical"],
        "trajectory_sha256": rollout["trajectory_sha256"],
        "changed_from_original": (
            None
            if original_hash is None
            else rollout["trajectory_sha256"] != original_hash
        ),
        "outcome": rollout["outcome"],
        "interaction_metrics": interaction_metrics.interaction_metrics(
            sdc, lead
        ),
        "first_rollout_seconds": rollout["first_rollout_seconds"],
        "second_rollout_seconds": rollout["second_rollout_seconds"],
    }


def _original_record(
    scenario: Any,
    candidate: dict[str, Any],
    runners: dict[str, controller_comparison.ControllerRunner],
) -> dict[str, Any]:
    object_index = candidate["interacting_object_index"]
    controllers = {
        role: _controller_record(
            scenario,
            object_index,
            runner.run_twice(scenario),
            None,
        )
        for role, runner in runners.items()
    }
    return {
        "eligible": all(
            record["outcome"]["success"] for record in controllers.values()
        ),
        "controllers": controllers,
    }


def _attempt_record(
    scenario: Any,
    candidate: dict[str, Any],
    onset_offset_s: float,
    speed_multiplier: float,
    runners: dict[str, controller_comparison.ControllerRunner],
    mutation_validator: speed_mutation.MutationValidator,
    original: dict[str, Any],
) -> dict[str, Any]:
    started = time.perf_counter()
    config = lead_braking.LeadBrakingMutationConfig(
        braking_onset_offset_s=onset_offset_s,
        speed_multiplier=speed_multiplier,
    )
    object_index = candidate["interacting_object_index"]
    mutated_scenario, mutation = lead_braking.apply_lead_braking_mutation(
        scenario, object_index, config
    )
    record: dict[str, Any] = {
        "parameters": {
            "braking_onset_offset_s": onset_offset_s,
            "speed_multiplier": speed_multiplier,
        },
        "identity_control": is_identity_point(
            onset_offset_s, speed_multiplier
        ),
        "mutation": mutation.report(config),
        "status": "mutation_rejected",
        "scenario_validation": None,
        "controllers": None,
    }
    if mutated_scenario is None:
        record["elapsed_seconds"] = round(
            time.perf_counter() - started, 6
        )
        return record
    scenario_validation = mutation_validator.validate(
        mutated_scenario, object_index
    )
    record["scenario_validation"] = scenario_validation
    if not scenario_validation["accepted"]:
        record["status"] = "scenario_rejected"
        record["elapsed_seconds"] = round(
            time.perf_counter() - started, 6
        )
        return record
    controllers = {}
    for role, runner in runners.items():
        rollout = runner.run_twice(mutated_scenario)
        original_hash = original["controllers"][role][
            "trajectory_sha256"
        ]
        controllers[role] = _controller_record(
            mutated_scenario,
            object_index,
            rollout,
            original_hash,
        )
    record["controllers"] = controllers
    record["status"] = "accepted"
    record["elapsed_seconds"] = round(time.perf_counter() - started, 6)
    return record


def _safe_rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def evaluate_family(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate the predeclared family gates from private attempt records."""
    attempts = [
        attempt
        for scenario in scenarios
        for attempt in scenario["attempts"]
    ]
    eligible_count = sum(scenario["original"]["eligible"] for scenario in scenarios)
    nonidentity = [attempt for attempt in attempts if not attempt["identity_control"]]
    accepted_nonidentity = [
        attempt for attempt in nonidentity if attempt["status"] == "accepted"
    ]
    deterministic_accepted = [
        attempt
        for attempt in attempts
        if attempt["status"] == "accepted"
        and attempt["scenario_validation"]["outputs_identical"]
        and all(
            controller["outputs_identical"]
            for controller in attempt["controllers"].values()
        )
    ]
    tested_responses = sum(
        bool(attempt["controllers"]["tested"]["changed_from_original"])
        for attempt in accepted_nonidentity
    )
    varying_scenarios = 0
    for scenario in scenarios:
        accepted = [
            attempt
            for attempt in scenario["attempts"]
            if attempt["status"] == "accepted"
        ]
        separations = [
            attempt["controllers"]["tested"]["interaction_metrics"][
                "minimum_signed_separation_m"
            ]
            for attempt in accepted
        ]
        ttcs = [
            attempt["controllers"]["tested"]["interaction_metrics"][
                "minimum_longitudinal_ttc_s"
            ]
            for attempt in accepted
            if attempt["controllers"]["tested"]["interaction_metrics"][
                "minimum_longitudinal_ttc_s"
            ]
            is not None
        ]
        separation_range = max(separations) - min(separations) if separations else 0.0
        ttc_range = max(ttcs) - min(ttcs) if len(ttcs) >= 2 else 0.0
        scenario["severity_ranges"] = {
            "minimum_separation_range_m": round(separation_range, 6),
            "finite_ttc_range_s": round(ttc_range, 6),
        }
        if (
            scenario["original"]["eligible"]
            and (
                separation_range >= MIN_SEPARATION_RANGE_M
                or ttc_range >= MIN_TTC_RANGE_S
            )
        ):
            varying_scenarios += 1

    valid_rate = _safe_rate(len(accepted_nonidentity), len(nonidentity))
    deterministic_rate = _safe_rate(
        len(deterministic_accepted),
        sum(attempt["status"] == "accepted" for attempt in attempts),
    )
    tested_response_rate = _safe_rate(
        tested_responses, len(accepted_nonidentity)
    )
    gates = {
        "eligible_scenarios": eligible_count >= MIN_ELIGIBLE_SCENARIOS,
        "nonidentity_mutation_valid_rate": (
            valid_rate >= MIN_NONIDENTITY_VALID_RATE
        ),
        "accepted_attempt_determinism": deterministic_rate == 1.0,
        "tested_controller_response_rate": (
            tested_response_rate >= MIN_TESTED_RESPONSE_RATE
        ),
        "continuous_severity_variation": (
            varying_scenarios >= MIN_VARYING_SCENARIOS
        ),
    }
    policy_specific_failures = sum(
        scenario["original"]["eligible"]
        and attempt["status"] == "accepted"
        and not attempt["controllers"]["tested"]["outcome"]["success"]
        and attempt["controllers"]["reference"]["outcome"]["success"]
        for scenario in scenarios
        for attempt in scenario["attempts"]
    )
    return {
        "decision": "go" if all(gates.values()) else "no_go",
        "gates": gates,
        "metrics": {
            "scenario_count": len(scenarios),
            "eligible_scenario_count": eligible_count,
            "attempt_count": len(attempts),
            "nonidentity_attempt_count": len(nonidentity),
            "accepted_nonidentity_attempt_count": len(accepted_nonidentity),
            "nonidentity_mutation_valid_rate": valid_rate,
            "accepted_attempt_determinism_rate": deterministic_rate,
            "tested_controller_response_rate": tested_response_rate,
            "varying_scenario_count": varying_scenarios,
            "policy_specific_failure_count": policy_specific_failures,
        },
        "thresholds": {
            "minimum_eligible_scenarios": MIN_ELIGIBLE_SCENARIOS,
            "minimum_nonidentity_mutation_valid_rate": MIN_NONIDENTITY_VALID_RATE,
            "required_accepted_attempt_determinism_rate": 1.0,
            "minimum_tested_controller_response_rate": MIN_TESTED_RESPONSE_RATE,
            "minimum_varying_scenarios": MIN_VARYING_SCENARIOS,
            "minimum_separation_range_m": MIN_SEPARATION_RANGE_M,
            "minimum_finite_ttc_range_s": MIN_TTC_RANGE_S,
        },
    }


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def run(manifest_path: Path) -> dict[str, Any]:
    """Run the fixed family-validation grid and return its private report."""
    started = time.perf_counter()
    loaded = _load_manifest_scenarios(manifest_path)
    runners = {
        "tested": controller_comparison.ControllerRunner(
            controller_comparison.TESTED_CONTROLLER
        ),
        "reference": controller_comparison.ControllerRunner(
            controller_comparison.REFERENCE_CONTROLLER
        ),
    }
    mutation_validator = speed_mutation.MutationValidator(
        require_mutated_object_valid_all_steps=False
    )
    scenarios: list[dict[str, Any]] = []
    for scenario, candidate in loaded:
        original = _original_record(scenario, candidate, runners)
        attempts = [
            _attempt_record(
                scenario,
                candidate,
                onset_offset_s,
                speed_multiplier,
                runners,
                mutation_validator,
                original,
            )
            for onset_offset_s, speed_multiplier in parameter_grid()
        ]
        scenario_record = {
            "scenario_id": candidate["scenario_id"],
            "source_shard": candidate["source_shard"],
            "record_index": candidate["record_index"],
            "selection_order": candidate["selection_order"],
            "mutated_object_index": candidate[
                "interacting_object_index"
            ],
            "original": original,
            "attempts": attempts,
        }
        scenarios.append(scenario_record)
    evaluation = evaluate_family(scenarios)
    return {
        "schema_version": 1,
        "status": "completed",
        "experiment": "lead_braking_family_validation",
        "dataset": {
            "name": "Waymo Open Motion Dataset",
            "version": scenario_selection.DATASET_VERSION,
            "split": scenario_selection.SPLIT,
        },
        "grid": {
            "braking_onset_offsets_s": list(ONSET_OFFSETS_S),
            "speed_multipliers": list(SPEED_MULTIPLIERS),
            "points_per_scenario": len(parameter_grid()),
        },
        "controller_set": {
            "tested": controller_comparison.TESTED_CONTROLLER.report(),
            "reference": controller_comparison.REFERENCE_CONTROLLER.report(),
        },
        "evaluation": evaluation,
        "scenarios": scenarios,
        "environment": {
            **scenario_selection._git_provenance(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "jax": jax.__version__,
            "tensorflow": tf.__version__,
            "jax_backend": jax.default_backend(),
            "waymax_git_commit": scenario_selection.WAYMAX_GIT_COMMIT,
            "family_validation_source_sha256": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
            "seed": scenario_selection.SEED,
        },
        "total_seconds": round(time.perf_counter() - started, 6),
        "process_peak_rss_bytes": _peak_rss_bytes(),
        "limitations": [
            "The ordered ten-scenario training set is a feasibility sample, not a representative evaluation set.",
            "Both controllers share Waymax IDMRoutePolicy and differ only by configuration.",
            "Kinematic and map gates do not constitute a learned behavioral-likelihood model.",
            "A family go decision authorizes baseline implementation, not a planner-performance claim.",
            "This private report contains restricted scenario-derived data and must remain under artifacts/.",
        ],
    }


def public_summary(report: dict[str, Any], output: Path) -> dict[str, Any]:
    """Return the privacy-safe terminal summary for one completed run."""
    evaluation = report["evaluation"]
    return {
        "status": report["status"],
        "decision": evaluation["decision"],
        **evaluation["metrics"],
        "output": str(output),
    }


def validate_private_output_path(output: Path) -> None:
    """Reject report paths outside the repository's ignored artifacts tree."""
    artifacts_root = (Path.cwd() / "artifacts").resolve()
    if not output.resolve().is_relative_to(artifacts_root):
        raise ValueError(
            "Family-validation reports contain restricted scenario-derived data; "
            "--output must remain under artifacts/."
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    validate_private_output_path(args.output)
    report = run(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            public_summary(report, args.output),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
