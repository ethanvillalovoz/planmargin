"""Evaluate the frozen headway-regression original-eligibility gate."""

from __future__ import annotations

import argparse
import json
import math
import platform
import time
from pathlib import Path
from typing import Any, Callable

import jax
import numpy as np
import tensorflow as tf

from planmargin import controller_comparison
from planmargin import family_validation
from planmargin import matched_coordinator
from planmargin import matched_waymax
from planmargin import random_search
from planmargin import scenario_selection

SCHEMA_VERSION = "1.0.0"
SCHEMA_BASE_URI = (
    "https://raw.githubusercontent.com/ethanvillalovoz/planmargin/main/schemas"
)
MANIFEST_SCHEMA_URI = (
    f"{SCHEMA_BASE_URI}/regression-eligibility-run-manifest-v1.schema.json"
)
ORIGINAL_SCHEMA_URI = (
    f"{SCHEMA_BASE_URI}/regression-eligibility-original-v1.schema.json"
)
REPORT_SCHEMA_URI = f"{SCHEMA_BASE_URI}/regression-eligibility-report-v1.schema.json"
MANIFEST_TYPE = "planmargin.regression_eligibility_run_manifest"
ORIGINAL_TYPE = "planmargin.regression_eligibility_original_checkpoint"
REPORT_TYPE = "planmargin.regression_eligibility_report"
DEFAULT_MANIFEST = family_validation.DEFAULT_MANIFEST
DEFAULT_OUTPUT_DIR = Path(
    "artifacts/search-comparison/headway-regression-eligibility"
)
TRACK = "headway_regression"
EXPECTED_SCENARIOS = 10
MIN_ELIGIBLE_SCENARIOS = 8

ScenarioLoader = Callable[[Path], list[tuple[Any, dict[str, Any]]]]
OriginalEvaluator = Callable[
    [
        Any,
        dict[str, Any],
        controller_comparison.ControllerSpec,
        controller_comparison.ControllerSpec,
    ],
    dict[str, Any],
]


def _identity(selection_order: int | None = None) -> dict[str, Any]:
    return {"track": TRACK, "selection_order": selection_order}


def _environment() -> dict[str, Any]:
    return json.loads(
        random_search._canonical_json(
            {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "machine": platform.machine(),
                "numpy": np.__version__,
                "jax": jax.__version__,
                "tensorflow": tf.__version__,
                "jax_backend": jax.default_backend(),
            }
        )
    )


def build_run_manifest(
    manifest_path: Path, candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    """Build the sealed scientific identity of the regression eligibility gate."""
    tested = matched_coordinator.tested_controller_for_track(TRACK)
    reference = controller_comparison.REFERENCE_CONTROLLER
    configuration = json.loads(
        random_search._canonical_json(
            {
                "experiment": "headway_regression_original_eligibility_v1",
                "identity": _identity(),
                "dataset": {
                    "name": "Waymo Open Motion Dataset",
                    "version": scenario_selection.DATASET_VERSION,
                    "split": scenario_selection.SPLIT,
                    "scenario_manifest_sha256": random_search._file_sha256(
                        manifest_path
                    ),
                    "selection_orders": [
                        candidate["selection_order"] for candidate in candidates
                    ],
                },
                "controllers": {
                    "tested": tested.report(),
                    "reference": reference.report(),
                },
                "gate": {
                    "expected_scenario_count": EXPECTED_SCENARIOS,
                    "minimum_eligible_scenario_count": MIN_ELIGIBLE_SCENARIOS,
                    "eligible_definition": (
                        "tested_original_success_and_reference_original_success"
                    ),
                    "all_original_rollouts_must_be_deterministic": True,
                    "replacement_configuration_on_no_go": False,
                },
                "accounting": {
                    "deterministic_physical_rollouts_per_controller": 2,
                    "controllers_per_scenario": 2,
                    "waymax_steps_per_physical_rollout": (
                        scenario_selection.NUM_FUTURE_STEPS
                    ),
                },
                "source": {
                    **scenario_selection._git_provenance(),
                    "regression_eligibility_source_sha256": (
                        random_search._file_sha256(Path(__file__))
                    ),
                    "matched_waymax_source_sha256": random_search._file_sha256(
                        Path(matched_waymax.__file__)
                    ),
                    "waymax_git_commit": scenario_selection.WAYMAX_GIT_COMMIT,
                },
            }
        )
    )
    record = {
        "$schema": MANIFEST_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": MANIFEST_TYPE,
        "identity": _identity(),
        "configuration_fingerprint": random_search._content_sha256(configuration),
        "configuration": configuration,
        "environment": _environment(),
    }
    return random_search._seal_record(record, "manifest_sha256")


def _original_path(output_dir: Path, selection_order: int) -> Path:
    return output_dir / "originals" / f"scenario-{selection_order:02d}.json"


def _load_sealed_record(
    path: Path,
    *,
    record_type: str,
    schema_uri: str,
    seal_field: str,
    fingerprint: str,
    selection_order: int | None,
) -> dict[str, Any]:
    record = random_search._read_json_object(path)
    if record.get("$schema") != schema_uri:
        raise ValueError(f"Eligibility checkpoint schema mismatch: {path}")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Eligibility checkpoint version mismatch: {path}")
    if record.get("record_type") != record_type:
        raise ValueError(f"Eligibility checkpoint type mismatch: {path}")
    if record.get("configuration_fingerprint") != fingerprint:
        raise ValueError(f"Eligibility checkpoint configuration mismatch: {path}")
    if record.get("identity") != _identity(selection_order):
        raise ValueError(f"Eligibility checkpoint identity mismatch: {path}")
    random_search._validate_seal(record, seal_field, path=path)
    return record


def _validate_original_evidence(original: dict[str, Any]) -> bool:
    try:
        controllers = original["controllers"]
        if set(controllers) != set(random_search.ROLES):
            raise ValueError("Eligibility original controller roles mismatch")
        for role in random_search.ROLES:
            controller = controllers[role]
            if not isinstance(controller["outputs_identical"], bool):
                raise ValueError("Eligibility original determinism flag is invalid")
            if not isinstance(controller["outcome"]["success"], bool):
                raise ValueError("Eligibility original outcome flag is invalid")
            for field in ("first_rollout_seconds", "second_rollout_seconds"):
                value = controller[field]
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or value < 0.0
                ):
                    raise ValueError("Eligibility original timing is invalid")
        eligible = all(
            controllers[role]["outcome"]["success"] for role in random_search.ROLES
        )
    except (KeyError, TypeError) as error:
        raise ValueError("Eligibility original evidence is incomplete") from error
    if original.get("eligible") is not bool(eligible):
        raise ValueError("Eligibility original evaluator derivation mismatch")
    return eligible


def build_original_checkpoint(
    *,
    run_manifest: dict[str, Any],
    candidate: dict[str, Any],
    original: dict[str, Any],
) -> dict[str, Any]:
    """Seal one original evaluation after deriving its eligibility."""
    eligible = _validate_original_evidence(original)
    record = {
        "$schema": ORIGINAL_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": ORIGINAL_TYPE,
        "identity": _identity(candidate["selection_order"]),
        "configuration_fingerprint": run_manifest["configuration_fingerprint"],
        "scenario": random_search._scenario_descriptor(candidate),
        "original": original,
        "eligible": eligible,
        "cost": random_search._original_cost(),
    }
    return random_search._seal_record(record, "checkpoint_sha256")


def _validate_original_checkpoint(
    record: dict[str, Any], candidate: dict[str, Any]
) -> None:
    if record.get("scenario") != random_search._scenario_descriptor(candidate):
        raise ValueError("Eligibility original scenario mismatch")
    eligible = _validate_original_evidence(record.get("original"))
    if record.get("eligible") is not bool(eligible):
        raise ValueError("Eligibility checkpoint derivation mismatch")
    if record.get("cost") != random_search._original_cost():
        raise ValueError("Eligibility original cost mismatch")


def _validate_expected_files(output_dir: Path) -> None:
    expected = {
        output_dir / "run-manifest.json",
        *{
            _original_path(output_dir, order)
            for order in range(1, EXPECTED_SCENARIOS + 1)
        },
    }
    report_path = output_dir / "report.json"
    if report_path.exists():
        expected.add(report_path)
    actual = {path for path in output_dir.rglob("*") if path.is_file()}
    if actual - expected:
        raise ValueError("Unexpected eligibility checkpoint file")


def _initialize_or_resume(
    output_dir: Path,
    expected_manifest: dict[str, Any],
    *,
    resume: bool,
) -> dict[str, Any]:
    path = output_dir / "run-manifest.json"
    if path.exists():
        if not resume:
            raise FileExistsError("Eligibility output exists; pass resume=True")
        record = _load_sealed_record(
            path,
            record_type=MANIFEST_TYPE,
            schema_uri=MANIFEST_SCHEMA_URI,
            seal_field="manifest_sha256",
            fingerprint=expected_manifest["configuration_fingerprint"],
            selection_order=None,
        )
        if record.get("configuration") != expected_manifest["configuration"]:
            raise ValueError("Eligibility run configuration mismatch")
        if record.get("environment") != expected_manifest["environment"]:
            raise ValueError("Eligibility run environment mismatch")
        return record
    if resume:
        raise FileNotFoundError("Eligibility run manifest is missing")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("Eligibility output is non-empty without a manifest")
    random_search._atomic_write_json(path, expected_manifest)
    return expected_manifest


def _load_originals(
    *,
    output_dir: Path,
    run_manifest: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    _validate_expected_files(output_dir)
    originals = []
    fingerprint = run_manifest["configuration_fingerprint"]
    for candidate in candidates:
        order = candidate["selection_order"]
        path = _original_path(output_dir, order)
        if not path.exists():
            if any(
                _original_path(output_dir, later).exists()
                for later in range(order + 1, EXPECTED_SCENARIOS + 1)
            ):
                raise ValueError("Eligibility checkpoints contain an index gap")
            break
        record = _load_sealed_record(
            path,
            record_type=ORIGINAL_TYPE,
            schema_uri=ORIGINAL_SCHEMA_URI,
            seal_field="checkpoint_sha256",
            fingerprint=fingerprint,
            selection_order=order,
        )
        _validate_original_checkpoint(record, candidate)
        originals.append(record)
    return originals


def build_report(
    *,
    run_manifest: dict[str, Any],
    originals: list[dict[str, Any]],
    invocation_seconds: float,
    process_peak_rss_bytes: int,
) -> dict[str, Any]:
    """Derive the completed eligibility decision from sealed originals."""
    eligible_count = sum(record["eligible"] for record in originals)
    deterministic_count = sum(
        all(
            controller["outputs_identical"]
            for controller in record["original"]["controllers"].values()
        )
        for record in originals
    )
    exact_count = len(originals) == EXPECTED_SCENARIOS
    sequential = [record["identity"]["selection_order"] for record in originals] == list(
        range(1, EXPECTED_SCENARIOS + 1)
    )
    deterministic = deterministic_count == EXPECTED_SCENARIOS
    threshold_passes = eligible_count >= MIN_ELIGIBLE_SCENARIOS
    integrity_gates = {
        "exact_scenario_count": exact_count,
        "sequential_selection_orders": sequential,
        "all_original_rollouts_deterministic": deterministic,
        "cost_accounting_reconciles": all(
            record["cost"] == random_search._original_cost() for record in originals
        ),
    }
    if not all(integrity_gates.values()):
        decision = "invalid_gate"
    elif threshold_passes:
        decision = "go"
    else:
        decision = "no_go"
    cost = random_search._sum_cost([record["cost"] for record in originals])
    report = {
        "$schema": REPORT_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": REPORT_TYPE,
        "identity": _identity(),
        "configuration_fingerprint": run_manifest["configuration_fingerprint"],
        "status": "completed",
        "decision": decision,
        "integrity_gates": integrity_gates,
        "eligibility_gate": {
            "minimum_eligible_scenario_count": MIN_ELIGIBLE_SCENARIOS,
            "eligible_scenario_count": eligible_count,
            "passes": threshold_passes,
        },
        "metrics": {
            "scenario_count": len(originals),
            "eligible_scenario_count": eligible_count,
            "ineligible_scenario_count": len(originals) - eligible_count,
            "deterministic_scenario_count": deterministic_count,
            "recorded_work_seconds": round(
                sum(
                    float(controller["first_rollout_seconds"])
                    + float(controller["second_rollout_seconds"])
                    for record in originals
                    for controller in record["original"]["controllers"].values()
                ),
                6,
            ),
            "final_invocation_seconds": round(invocation_seconds, 6),
            "process_peak_rss_bytes": process_peak_rss_bytes,
        },
        "cost": cost,
        "limitations": [
            "This gate tests an intentionally injected controller regression.",
            "No mutation, search, planner-performance, H1, H2, or H3 claim follows.",
            "A no-go authorizes no replacement configuration in protocol version one.",
        ],
    }
    return random_search._seal_record(report, "report_sha256")


def _validate_completed_report(
    report: dict[str, Any],
    *,
    run_manifest: dict[str, Any],
    originals: list[dict[str, Any]],
) -> None:
    try:
        seconds = report["metrics"]["final_invocation_seconds"]
        peak = report["metrics"]["process_peak_rss_bytes"]
    except (KeyError, TypeError) as error:
        raise ValueError("Eligibility report observations are incomplete") from error
    if (
        isinstance(seconds, bool)
        or not isinstance(seconds, (int, float))
        or not math.isfinite(seconds)
        or seconds < 0.0
        or isinstance(peak, bool)
        or not isinstance(peak, int)
        or peak < 0
    ):
        raise ValueError("Eligibility report observations are invalid")
    expected = build_report(
        run_manifest=run_manifest,
        originals=originals,
        invocation_seconds=seconds,
        process_peak_rss_bytes=peak,
    )
    if report != expected:
        raise ValueError("Eligibility report does not match durable checkpoints")


def run(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    resume: bool = False,
    max_new_scenarios: int | None = None,
    scenario_loader: ScenarioLoader = family_validation._load_manifest_scenarios,
    original_evaluator: OriginalEvaluator | None = None,
) -> dict[str, Any]:
    """Execute or resume the ten-scenario private eligibility gate."""
    started = time.perf_counter()
    matched_coordinator.validate_private_output_dir(output_dir)
    if (
        max_new_scenarios is not None
        and (
            isinstance(max_new_scenarios, bool)
            or not isinstance(max_new_scenarios, int)
            or max_new_scenarios < 0
        )
    ):
        raise ValueError("max_new_scenarios must be a non-negative integer")
    candidates = family_validation.load_manifest_candidates(manifest_path)
    expected_manifest = build_run_manifest(manifest_path, candidates)
    run_manifest = _initialize_or_resume(
        output_dir, expected_manifest, resume=resume
    )
    originals = _load_originals(
        output_dir=output_dir,
        run_manifest=run_manifest,
        candidates=candidates,
    )
    report_path = output_dir / "report.json"
    if report_path.exists():
        if not resume:
            raise FileExistsError("Completed eligibility report already exists")
        if len(originals) != EXPECTED_SCENARIOS:
            raise ValueError("Eligibility report exists without ten originals")
        report = _load_sealed_record(
            report_path,
            record_type=REPORT_TYPE,
            schema_uri=REPORT_SCHEMA_URI,
            seal_field="report_sha256",
            fingerprint=run_manifest["configuration_fingerprint"],
            selection_order=None,
        )
        _validate_completed_report(
            report, run_manifest=run_manifest, originals=originals
        )
        return report

    loaded = scenario_loader(manifest_path)
    by_order = {
        candidate["selection_order"]: (scenario, candidate)
        for scenario, candidate in loaded
    }
    if set(by_order) != set(range(1, EXPECTED_SCENARIOS + 1)):
        raise ValueError("Loaded eligibility scenarios do not match the manifest")
    if original_evaluator is None:
        adapter = matched_waymax.WaymaxEvaluatorAdapter()
        evaluator = adapter.evaluate_original
    else:
        evaluator = original_evaluator
    tested = matched_coordinator.tested_controller_for_track(TRACK)
    reference = controller_comparison.REFERENCE_CONTROLLER
    new_scenarios = 0
    for candidate in candidates[len(originals) :]:
        if max_new_scenarios is not None and new_scenarios >= max_new_scenarios:
            break
        scenario, loaded_candidate = by_order[candidate["selection_order"]]
        if loaded_candidate != candidate:
            raise ValueError("Eligibility scenario candidate mismatch")
        original = evaluator(scenario, candidate, tested, reference)
        checkpoint = build_original_checkpoint(
            run_manifest=run_manifest,
            candidate=candidate,
            original=original,
        )
        _validate_original_checkpoint(checkpoint, candidate)
        random_search._atomic_write_json(
            _original_path(output_dir, candidate["selection_order"]), checkpoint
        )
        originals.append(checkpoint)
        new_scenarios += 1

    if len(originals) == EXPECTED_SCENARIOS:
        report = build_report(
            run_manifest=run_manifest,
            originals=originals,
            invocation_seconds=time.perf_counter() - started,
            process_peak_rss_bytes=family_validation._peak_rss_bytes(),
        )
        random_search._atomic_write_json(report_path, report)
        return report
    return {
        "status": "in_progress",
        "decision": None,
        "track": TRACK,
        "completed_scenario_count": len(originals),
        "expected_scenario_count": EXPECTED_SCENARIOS,
        "remaining_scenario_count": EXPECTED_SCENARIOS - len(originals),
        "new_scenario_count": new_scenarios,
        "output": str(output_dir),
    }


def public_summary(result: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Return aggregate-only gate output suitable for the terminal."""
    if result.get("record_type") != REPORT_TYPE:
        allowed = {
            "status",
            "decision",
            "track",
            "completed_scenario_count",
            "expected_scenario_count",
            "remaining_scenario_count",
            "new_scenario_count",
        }
        summary = {key: value for key, value in result.items() if key in allowed}
        summary["output"] = str(output_dir)
        return summary
    return {
        "status": result["status"],
        "decision": result["decision"],
        "track": TRACK,
        "scenario_count": result["metrics"]["scenario_count"],
        "eligible_scenario_count": result["metrics"]["eligible_scenario_count"],
        "minimum_eligible_scenario_count": result["eligibility_gate"][
            "minimum_eligible_scenario_count"
        ],
        "all_original_rollouts_deterministic": result["integrity_gates"][
            "all_original_rollouts_deterministic"
        ],
        "total_physical_rollouts": result["cost"]["total_physical_rollouts"],
        "output": str(output_dir / "report.json"),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-new-scenarios", type=int)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = run(
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        resume=args.resume,
        max_new_scenarios=args.max_new_scenarios,
    )
    print(json.dumps(public_summary(result, args.output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
