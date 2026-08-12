"""Run and aggregate the frozen natural matched-search development campaign."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import statistics
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from planmargin import empirical_support
from planmargin import family_validation
from planmargin import matched_coordinator
from planmargin import matched_search
from planmargin import matched_waymax
from planmargin import random_search
from planmargin import scenario_selection

SCHEMA_VERSION = "1.0.0"
SCHEMA_BASE_URI = (
    "https://raw.githubusercontent.com/ethanvillalovoz/planmargin/main/schemas"
)
MANIFEST_SCHEMA_URI = f"{SCHEMA_BASE_URI}/matched-campaign-run-manifest-v1.schema.json"
REPORT_SCHEMA_URI = f"{SCHEMA_BASE_URI}/matched-campaign-report-v1.schema.json"
MANIFEST_TYPE = "planmargin.matched_campaign_run_manifest"
REPORT_TYPE = "planmargin.matched_campaign_report"
CAMPAIGN_ID = "natural-development-v1"
TRACK = "natural"
EXPECTED_CELL_COUNT = (
    len(matched_search.METHODS)
    * len(matched_search.SEEDS)
    * family_validation.EXPECTED_SCENARIOS
)
EXPECTED_PROPOSAL_COUNT = EXPECTED_CELL_COUNT * matched_search.PROPOSAL_BUDGET
H3_NONINFERIORITY_MARGIN = 0.05
MINIMUM_FREE_DISK_BYTES = 2 * 1024**3

DEFAULT_MANIFEST = family_validation.DEFAULT_MANIFEST
DEFAULT_SUPPORT_MODEL = Path(
    "artifacts/realism/lead-braking-support-v1-00c3727/model.json"
)
DEFAULT_OUTPUT_DIR = Path(
    "artifacts/search-comparison/natural-development-v1"
)

CellRunner = Callable[
    [matched_coordinator.CellConfig, Path, bool],
    dict[str, Any],
]


def campaign_cells() -> tuple[matched_coordinator.CellConfig, ...]:
    """Return the frozen pair-first campaign order."""
    return tuple(
        matched_coordinator.CellConfig(method, TRACK, seed, selection_order)
        for selection_order in range(1, family_validation.EXPECTED_SCENARIOS + 1)
        for seed in matched_search.SEEDS
        for method in matched_search.METHODS
    )


def _identity(cell: matched_coordinator.CellConfig) -> dict[str, Any]:
    return {
        "method": cell.method,
        "track": cell.track,
        "seed": cell.seed,
        "selection_order": cell.selection_order,
        "proposal_index": None,
    }


def cell_output_dir(
    output_dir: Path, cell: matched_coordinator.CellConfig
) -> Path:
    """Return one stable private cell path without scenario identifiers."""
    return (
        output_dir
        / "cells"
        / cell.method
        / f"seed-{cell.seed}"
        / f"scenario-{cell.selection_order:02d}"
    )


def validate_private_output_dir(output_dir: Path) -> None:
    matched_coordinator.validate_private_output_dir(output_dir)


def _validate_campaign_shape() -> None:
    cells = campaign_cells()
    if len(cells) != EXPECTED_CELL_COUNT or len(set(cells)) != EXPECTED_CELL_COUNT:
        raise RuntimeError("Frozen campaign cell identities are incomplete")
    if any(cell.track != TRACK for cell in cells):
        raise RuntimeError("Frozen campaign contains a non-natural track")


def build_run_manifest(
    *,
    manifest_path: Path,
    support_model: dict[str, Any],
) -> dict[str, Any]:
    """Build the sealed identity for the complete natural campaign."""
    _validate_campaign_shape()
    empirical_support.validate_model(support_model)
    candidates = family_validation.load_manifest_candidates(manifest_path)
    selection_orders = [candidate["selection_order"] for candidate in candidates]
    expected_orders = list(range(1, family_validation.EXPECTED_SCENARIOS + 1))
    if selection_orders != expected_orders:
        raise ValueError("Campaign manifest must contain the ordered ten scenarios")
    source = scenario_selection._git_provenance()
    configuration = json.loads(
        random_search._canonical_json(
            {
                "campaign_id": CAMPAIGN_ID,
                "experiment": "matched_random_bayesian_lead_braking_v2",
                "track": TRACK,
                "methods": list(matched_search.METHODS),
                "seeds": list(matched_search.SEEDS),
                "selection_orders": expected_orders,
                "cell_order": [_identity(cell) for cell in campaign_cells()],
                "cell_count": EXPECTED_CELL_COUNT,
                "proposal_budget_per_cell": matched_search.PROPOSAL_BUDGET,
                "total_proposal_budget": EXPECTED_PROPOSAL_COUNT,
                "dataset": {
                    "name": "Waymo Open Motion Dataset",
                    "version": scenario_selection.DATASET_VERSION,
                    "split": scenario_selection.SPLIT,
                    "scenario_manifest_sha256": random_search._file_sha256(
                        manifest_path
                    ),
                    "held_out_opened": False,
                },
                "support": {
                    "model_fingerprint": support_model["model_fingerprint"],
                    "model_sha256": support_model["model_sha256"],
                },
                "reporting": {
                    "h1_censoring_proposal_horizon": matched_search.PROPOSAL_BUDGET,
                    "h1_requires_lower_proposal_and_physical_cost": True,
                    "h2_pair_key": ["selection_order", "seed"],
                    "h2_difference": "bayesian_minus_random",
                    "h3_noninferiority_margin": H3_NONINFERIORITY_MARGIN,
                },
                "source": {
                    **source,
                    "matched_campaign_source_sha256": random_search._file_sha256(
                        Path(__file__)
                    ),
                    "matched_coordinator_source_sha256": (
                        random_search._file_sha256(
                            Path(matched_coordinator.__file__)
                        )
                    ),
                },
            }
        )
    )
    record = {
        "$schema": MANIFEST_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": MANIFEST_TYPE,
        "campaign_id": CAMPAIGN_ID,
        "configuration_fingerprint": random_search._content_sha256(configuration),
        "configuration": configuration,
        "environment": matched_coordinator._environment(),
    }
    return random_search._seal_record(record, "manifest_sha256")


def _load_json(path: Path) -> dict[str, Any]:
    return random_search._read_json_object(path)


def _load_sealed_record(
    path: Path,
    *,
    record_type: str,
    schema_uri: str,
    seal_field: str,
) -> dict[str, Any]:
    record = _load_json(path)
    random_search._validate_seal(record, seal_field, path=path)
    if record.get("record_type") != record_type:
        raise ValueError(f"Unexpected campaign record type: {path}")
    if record.get("$schema") != schema_uri:
        raise ValueError(f"Unexpected campaign schema: {path}")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Unexpected campaign schema version: {path}")
    return record


def _initialize_or_resume(
    output_dir: Path,
    expected_manifest: dict[str, Any],
    *,
    resume: bool,
) -> dict[str, Any]:
    path = output_dir / "run-manifest.json"
    if path.exists():
        if not resume:
            raise FileExistsError("Campaign output exists; pass resume=True")
        record = _load_sealed_record(
            path,
            record_type=MANIFEST_TYPE,
            schema_uri=MANIFEST_SCHEMA_URI,
            seal_field="manifest_sha256",
        )
        if record != expected_manifest:
            raise ValueError("Campaign configuration or environment mismatch")
        return record
    if resume:
        raise FileNotFoundError("Campaign run manifest is missing")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("Campaign output is non-empty without a manifest")
    random_search._atomic_write_json(path, expected_manifest)
    return expected_manifest


def _validate_existing_tree(output_dir: Path) -> None:
    """Reject campaign files outside the frozen cell tree."""
    if not output_dir.exists():
        return
    allowed_top_level = {"run-manifest.json", "report.json", "cells"}
    unexpected_top_level = {
        path.name for path in output_dir.iterdir() if path.name not in allowed_top_level
    }
    if unexpected_top_level:
        raise ValueError("Campaign output contains unexpected top-level entries")
    cells_root = output_dir / "cells"
    if not cells_root.exists():
        return
    expected_cell_dirs = {
        cell_output_dir(output_dir, cell).resolve() for cell in campaign_cells()
    }
    for path in cells_root.rglob("*"):
        if path.is_file() and not any(
            path.resolve().is_relative_to(cell_dir)
            for cell_dir in expected_cell_dirs
        ):
            raise ValueError("Campaign output contains an unexpected cell path")


def _validate_cell_report(
    report: dict[str, Any],
    *,
    cell: matched_coordinator.CellConfig,
    support_model_fingerprint: str,
) -> None:
    payload = dict(report)
    seal = payload.pop("report_sha256", None)
    if not isinstance(seal, str) or random_search._content_sha256(payload) != seal:
        raise ValueError("Cell report content seal is invalid")
    if report.get("record_type") != matched_coordinator.REPORT_TYPE:
        raise ValueError("Campaign received a non-cell report")
    if report.get("$schema") != matched_coordinator.REPORT_SCHEMA_URI:
        raise ValueError("Campaign cell report schema mismatch")
    if report.get("schema_version") != matched_coordinator.SCHEMA_VERSION:
        raise ValueError("Campaign cell report schema version mismatch")
    if report.get("identity") != _identity(cell):
        raise ValueError("Campaign cell report identity mismatch")
    if report.get("support_model_fingerprint") != support_model_fingerprint:
        raise ValueError("Campaign cell support-model mismatch")
    if report.get("status") != "completed":
        raise ValueError("Campaign cell is not completed")


def _method_reports(
    reports: Sequence[dict[str, Any]], method: str
) -> list[dict[str, Any]]:
    return [report for report in reports if report["identity"]["method"] == method]


def _mean(values: Sequence[float | int]) -> float:
    if not values:
        raise ValueError("Cannot average an empty metric")
    return round(math.fsum(float(value) for value in values) / len(values), 6)


def _method_metrics(reports: Sequence[dict[str, Any]]) -> dict[str, Any]:
    finding_cells = [
        report
        for report in reports
        if report["metrics"]["qualifying_failure_count"] > 0
    ]
    return {
        "cell_count": len(reports),
        "proposal_count": sum(report["metrics"]["proposal_count"] for report in reports),
        "finding_cell_count": len(finding_cells),
        "qualifying_failure_count": sum(
            report["metrics"]["qualifying_failure_count"] for report in reports
        ),
        "restricted_mean_proposals_to_first_finding": _mean(
            [
                report["metrics"]["first_qualifying_failure_proposal_count"]
                or matched_search.PROPOSAL_BUDGET
                for report in reports
            ]
        ),
        "restricted_mean_physical_rollouts_to_first_finding": _mean(
            [
                report["metrics"][
                    "restricted_physical_rollouts_to_first_qualifying_failure"
                ]
                for report in reports
            ]
        ),
        "pipeline_valid_count": sum(
            report["metrics"]["pipeline_valid_count"] for report in reports
        ),
        "support_and_pipeline_valid_count": sum(
            report["metrics"]["support_and_pipeline_valid_count"]
            for report in reports
        ),
        "support_and_pipeline_valid_rate": round(
            sum(
                report["metrics"]["support_and_pipeline_valid_count"]
                for report in reports
            )
            / sum(report["metrics"]["proposal_count"] for report in reports),
            6,
        ),
        "mean_final_feasible_hypervolume": _mean(
            [report["metrics"]["final_feasible_hypervolume"] for report in reports]
        ),
        "mean_feasible_hypervolume_by_proposal": [
            _mean(
                [
                    report["metrics"]["feasible_hypervolume_by_proposal"][index]
                    for report in reports
                ]
            )
            for index in range(matched_search.PROPOSAL_BUDGET)
        ],
        "recorded_work_seconds": round(
            math.fsum(
                float(report["metrics"]["recorded_work_seconds"])
                for report in reports
            ),
            6,
        ),
    }


def _hypothesis_metrics(
    reports: Sequence[dict[str, Any]], methods: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    random_metrics = methods["random"]
    bayesian_metrics = methods["bayesian"]
    total_finding_cells = (
        random_metrics["finding_cell_count"]
        + bayesian_metrics["finding_cell_count"]
    )
    if total_finding_cells == 0:
        h1_status = "untestable"
    elif (
        bayesian_metrics["finding_cell_count"]
        >= random_metrics["finding_cell_count"]
        and bayesian_metrics["restricted_mean_proposals_to_first_finding"]
        < random_metrics["restricted_mean_proposals_to_first_finding"]
        and bayesian_metrics[
            "restricted_mean_physical_rollouts_to_first_finding"
        ]
        < random_metrics["restricted_mean_physical_rollouts_to_first_finding"]
    ):
        h1_status = "supported"
    else:
        h1_status = "unsupported"

    indexed = {
        (
            report["identity"]["selection_order"],
            report["identity"]["seed"],
            report["identity"]["method"],
        ): report
        for report in reports
    }
    paired_differences = []
    for selection_order in range(1, family_validation.EXPECTED_SCENARIOS + 1):
        for seed in matched_search.SEEDS:
            random_distance = indexed[(selection_order, seed, "random")]["metrics"][
                "minimum_failure_mutation_distance"
            ]
            bayesian_distance = indexed[(selection_order, seed, "bayesian")][
                "metrics"
            ]["minimum_failure_mutation_distance"]
            if random_distance is not None and bayesian_distance is not None:
                paired_differences.append(float(bayesian_distance) - float(random_distance))
    raw_paired_median = (
        float(statistics.median(paired_differences))
        if paired_differences
        else None
    )
    paired_median = (
        round(raw_paired_median, 6) if raw_paired_median is not None else None
    )
    h2_status = (
        "untestable"
        if raw_paired_median is None
        else "supported"
        if raw_paired_median < 0.0
        else "unsupported"
    )
    raw_h3_difference = (
        bayesian_metrics["support_and_pipeline_valid_rate"]
        - random_metrics["support_and_pipeline_valid_rate"]
    )
    h3_difference = round(raw_h3_difference, 6)
    return {
        "h1_efficiency": {
            "status": h1_status,
            "bayesian_finding_count_at_least_random": (
                bayesian_metrics["finding_cell_count"]
                >= random_metrics["finding_cell_count"]
            ),
            "bayesian_lower_restricted_mean_proposals": (
                bayesian_metrics["restricted_mean_proposals_to_first_finding"]
                < random_metrics["restricted_mean_proposals_to_first_finding"]
            ),
            "bayesian_lower_restricted_mean_physical_rollouts": (
                bayesian_metrics[
                    "restricted_mean_physical_rollouts_to_first_finding"
                ]
                < random_metrics[
                    "restricted_mean_physical_rollouts_to_first_finding"
                ]
            ),
        },
        "h2_minimality": {
            "status": h2_status,
            "paired_cell_count": len(paired_differences),
            "median_bayesian_minus_random_mutation_distance": paired_median,
        },
        "h3_validity": {
            "status": (
                "supported"
                if raw_h3_difference >= -H3_NONINFERIORITY_MARGIN
                else "unsupported"
            ),
            "bayesian_minus_random_valid_rate": h3_difference,
            "noninferiority_margin": H3_NONINFERIORITY_MARGIN,
        },
    }


def build_report(
    *,
    run_manifest: dict[str, Any],
    cell_reports: Sequence[dict[str, Any]],
    invocation_seconds: float,
    process_peak_rss_bytes: int,
) -> dict[str, Any]:
    """Derive the campaign report only from sealed completed cell reports."""
    if (
        isinstance(invocation_seconds, bool)
        or not math.isfinite(invocation_seconds)
        or invocation_seconds < 0.0
    ):
        raise ValueError("Campaign invocation time must be finite and non-negative")
    if (
        isinstance(process_peak_rss_bytes, bool)
        or not isinstance(process_peak_rss_bytes, int)
        or process_peak_rss_bytes < 0
    ):
        raise ValueError("Campaign peak memory must be a non-negative integer")
    expected_cells = campaign_cells()
    if len(cell_reports) != len(expected_cells):
        raise ValueError("Campaign report requires every frozen cell")
    support_fingerprint = run_manifest["configuration"]["support"][
        "model_fingerprint"
    ]
    for cell, report in zip(expected_cells, cell_reports, strict=True):
        _validate_cell_report(
            report,
            cell=cell,
            support_model_fingerprint=support_fingerprint,
        )

    method_metrics = {
        method: _method_metrics(_method_reports(cell_reports, method))
        for method in matched_search.METHODS
    }
    integrity_gates = {
        "exact_cell_count": len(cell_reports) == EXPECTED_CELL_COUNT,
        "unique_cell_identities": len(
            {
                random_search._canonical_json(report["identity"])
                for report in cell_reports
            }
        )
        == EXPECTED_CELL_COUNT,
        "exact_method_cell_counts": all(
            method_metrics[method]["cell_count"] == EXPECTED_CELL_COUNT // 2
            for method in matched_search.METHODS
        ),
        "exact_equal_proposal_budgets": all(
            method_metrics[method]["proposal_count"]
            == EXPECTED_PROPOSAL_COUNT // 2
            for method in matched_search.METHODS
        ),
        "all_cell_integrity_gates_pass": all(
            report["decision"] == "cell_complete"
            and all(report["integrity_gates"].values())
            for report in cell_reports
        ),
        "support_model_consistent": all(
            report["support_model_fingerprint"] == support_fingerprint
            for report in cell_reports
        ),
        "natural_track_only": all(
            report["identity"]["track"] == TRACK for report in cell_reports
        ),
    }
    cost_by_method = {
        method: random_search._sum_cost(
            [report["cost"]["total"] for report in _method_reports(cell_reports, method)]
        )
        for method in matched_search.METHODS
    }
    report = {
        "$schema": REPORT_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": REPORT_TYPE,
        "campaign_id": CAMPAIGN_ID,
        "configuration_fingerprint": run_manifest["configuration_fingerprint"],
        "support_model_fingerprint": support_fingerprint,
        "status": "completed",
        "decision": (
            "campaign_complete"
            if all(integrity_gates.values())
            else "invalid_campaign"
        ),
        "integrity_gates": integrity_gates,
        "metrics_by_method": method_metrics,
        "hypotheses": _hypothesis_metrics(cell_reports, method_metrics),
        "cost_by_method": cost_by_method,
        "cost_total": random_search._sum_cost(list(cost_by_method.values())),
        "recorded_work_seconds": round(
            math.fsum(
                method_metrics[method]["recorded_work_seconds"]
                for method in matched_search.METHODS
            ),
            6,
        ),
        "final_invocation_seconds": round(invocation_seconds, 6),
        "process_peak_rss_bytes": process_peak_rss_bytes,
        "limitations": [
            "This is a ten-scenario training-set development comparison.",
            "Five seeds support descriptive paired results, not broad generalization.",
            "A zero-finding natural result leaves H1 and H2 untestable.",
            "No result describes or evaluates the production Waymo Driver.",
            "This campaign did not read held-out WOMD validation data.",
        ],
    }
    return random_search._seal_record(report, "report_sha256")


def _public_progress(
    *, completed_cell_count: int, new_cell_count: int, output_dir: Path
) -> dict[str, Any]:
    return {
        "status": "in_progress",
        "decision": None,
        "campaign_id": CAMPAIGN_ID,
        "completed_cell_count": completed_cell_count,
        "expected_cell_count": EXPECTED_CELL_COUNT,
        "remaining_cell_count": EXPECTED_CELL_COUNT - completed_cell_count,
        "new_cell_count": new_cell_count,
        "output": str(output_dir),
    }


def public_summary(report: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Return only aggregate campaign fields suitable for a terminal."""
    if report.get("record_type") != REPORT_TYPE:
        return dict(report)
    return {
        "status": report["status"],
        "decision": report["decision"],
        "campaign_id": report["campaign_id"],
        "cell_count": sum(
            metrics["cell_count"]
            for metrics in report["metrics_by_method"].values()
        ),
        "proposal_count": sum(
            metrics["proposal_count"]
            for metrics in report["metrics_by_method"].values()
        ),
        "finding_cell_count_by_method": {
            method: report["metrics_by_method"][method]["finding_cell_count"]
            for method in matched_search.METHODS
        },
        "hypothesis_statuses": {
            name: result["status"]
            for name, result in report["hypotheses"].items()
        },
        "total_physical_rollouts": report["cost_total"]["total_physical_rollouts"],
        "output": str(output_dir),
    }


def readiness(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    support_model_path: Path = DEFAULT_SUPPORT_MODEL,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Validate private prerequisites without loading scenarios or writing output."""
    validate_private_output_dir(output_dir)
    candidates = family_validation.load_manifest_candidates(manifest_path)
    model = empirical_support.load_model(support_model_path)
    disk_probe = output_dir.parent
    while not disk_probe.exists() and disk_probe != disk_probe.parent:
        disk_probe = disk_probe.parent
    free_disk_bytes = shutil.disk_usage(disk_probe).free
    return {
        "status": "ready" if free_disk_bytes >= MINIMUM_FREE_DISK_BYTES else "no_go",
        "campaign_id": CAMPAIGN_ID,
        "scenario_count": len(candidates),
        "cell_count": EXPECTED_CELL_COUNT,
        "proposal_count": EXPECTED_PROPOSAL_COUNT,
        "maximum_physical_rollouts": (
            EXPECTED_CELL_COUNT * 4 + EXPECTED_PROPOSAL_COUNT * 6
        ),
        "support_model_valid": bool(model["model_fingerprint"]),
        "minimum_free_disk_bytes": MINIMUM_FREE_DISK_BYTES,
        "available_disk_bytes": free_disk_bytes,
        "disk_gate_passes": free_disk_bytes >= MINIMUM_FREE_DISK_BYTES,
        "output_exists": output_dir.exists(),
        "resume_required": (output_dir / "run-manifest.json").exists(),
        "held_out_opened": False,
    }


def run(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    support_model_path: Path = DEFAULT_SUPPORT_MODEL,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    resume: bool = False,
    max_new_cells: int | None = None,
    cell_runner: CellRunner | None = None,
) -> dict[str, Any]:
    """Execute or resume the complete natural development campaign."""
    started = time.perf_counter()
    validate_private_output_dir(output_dir)
    if max_new_cells is not None and (
        isinstance(max_new_cells, bool)
        or not isinstance(max_new_cells, int)
        or max_new_cells < 0
    ):
        raise ValueError("max_new_cells must be a non-negative integer")
    support_model = empirical_support.load_model(support_model_path)
    expected_manifest = build_run_manifest(
        manifest_path=manifest_path,
        support_model=support_model,
    )
    run_manifest = _initialize_or_resume(
        output_dir, expected_manifest, resume=resume
    )
    _validate_existing_tree(output_dir)
    adapter = matched_waymax.WaymaxEvaluatorAdapter()

    if cell_runner is None:

        def cell_runner(
            cell: matched_coordinator.CellConfig,
            cell_dir: Path,
            resume_cell: bool,
        ) -> dict[str, Any]:
            return matched_coordinator.run(
                manifest_path=manifest_path,
                support_model_path=support_model_path,
                output_dir=cell_dir,
                cell=cell,
                resume=resume_cell,
                original_evaluator=adapter.evaluate_original,
                attempt_evaluator=adapter.evaluate_attempt,
            )

    reports: list[dict[str, Any]] = []
    new_cell_count = 0
    for cell in campaign_cells():
        cell_dir = cell_output_dir(output_dir, cell)
        report_path = cell_dir / "report.json"
        if report_path.exists():
            result = cell_runner(cell, cell_dir, True)
            _validate_cell_report(
                result,
                cell=cell,
                support_model_fingerprint=support_model["model_fingerprint"],
            )
            reports.append(result)
            continue
        if max_new_cells is not None and new_cell_count >= max_new_cells:
            continue
        result = cell_runner(
            cell,
            cell_dir,
            (cell_dir / "run-manifest.json").exists(),
        )
        if result.get("record_type") != matched_coordinator.REPORT_TYPE:
            return _public_progress(
                completed_cell_count=len(reports),
                new_cell_count=new_cell_count,
                output_dir=output_dir,
            )
        _validate_cell_report(
            result,
            cell=cell,
            support_model_fingerprint=support_model["model_fingerprint"],
        )
        reports.append(result)
        new_cell_count += 1

    if len(reports) != EXPECTED_CELL_COUNT:
        if (output_dir / "report.json").exists():
            raise ValueError("Completed campaign report exists without every cell")
        return _public_progress(
            completed_cell_count=len(reports),
            new_cell_count=new_cell_count,
            output_dir=output_dir,
        )

    report_path = output_dir / "report.json"
    if report_path.exists():
        if not resume:
            raise FileExistsError("Completed campaign exists; pass resume=True")
        existing = _load_sealed_record(
            report_path,
            record_type=REPORT_TYPE,
            schema_uri=REPORT_SCHEMA_URI,
            seal_field="report_sha256",
        )
        expected = build_report(
            run_manifest=run_manifest,
            cell_reports=reports,
            invocation_seconds=float(existing["final_invocation_seconds"]),
            process_peak_rss_bytes=existing["process_peak_rss_bytes"],
        )
        if existing != expected:
            raise ValueError("Completed campaign report does not match cell reports")
        return existing

    report = build_report(
        run_manifest=run_manifest,
        cell_reports=reports,
        invocation_seconds=time.perf_counter() - started,
        process_peak_rss_bytes=family_validation._peak_rss_bytes(),
    )
    random_search._atomic_write_json(report_path, report)
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--support-model", type=Path, default=DEFAULT_SUPPORT_MODEL
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-new-cells", type=int)
    parser.add_argument("--readiness-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.readiness_only:
        result = readiness(
            manifest_path=args.manifest,
            support_model_path=args.support_model,
            output_dir=args.output_dir,
        )
    else:
        result = public_summary(
            run(
                manifest_path=args.manifest,
                support_model_path=args.support_model,
                output_dir=args.output_dir,
                resume=args.resume,
                max_new_cells=args.max_new_cells,
            ),
            args.output_dir,
        )
    print(json.dumps(result, allow_nan=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
