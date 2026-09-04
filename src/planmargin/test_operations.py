"""Build and validate the aggregate simulation-test operations report.

The report deliberately separates execution health from scientific outcomes. A
healthy campaign may reject every candidate; a promotion candidate may be
blocked even when the pipeline that measured it is healthy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb

from planmargin import random_search

SCHEMA_VERSION = "1.0.0"
SCHEMA_URI = (
    "https://raw.githubusercontent.com/ethanvillalovoz/planmargin/main/"
    "schemas/test-operations-report-v1.schema.json"
)
RECORD_TYPE = "planmargin.test_operations_report"
DEFAULT_CAMPAIGN = Path("artifacts/search-comparison/natural-development-v1")
DEFAULT_ANALYTICS = Path("artifacts/analytics/natural-development-v1")
DEFAULT_SELECTION = Path("artifacts/stage-0/scenario-selection.json")
DEFAULT_REPLAYS = Path("artifacts/proposal-replays/natural-development-v1")
DEFAULT_OUTPUT = Path("web/debugger/public/data/test-operations-v1.json")


def evaluate_test_health(
    *,
    completed_cells: int,
    planned_cells: int,
    integrity_passing: int,
    integrity_total: int,
    proposal_count: int,
    expected_proposals: int,
    method_proposals: dict[str, int],
    retained_replays: int,
    expected_replays: int,
    protected_scenes: int,
    expected_protected_scenes: int,
    assisted_scenes: int,
    expected_assisted_scenes: int,
) -> tuple[list[dict[str, str]], dict[str, Any], list[dict[str, Any]]]:
    """Evaluate campaign SLOs and emit actionable test-health alerts.

    This function is intentionally independent from artifact loading so CI can
    exercise both healthy and degraded states without fabricating experiment
    records or weakening evidence seals.
    """

    expected_each = expected_proposals // 2
    method_balanced = (
        set(method_proposals) == {"bayesian", "random"}
        and all(value == expected_each for value in method_proposals.values())
    )
    checks = [
        {
            "id": "cell_completion",
            "name": "Campaign cells complete",
            "target": f"{planned_cells} of {planned_cells}",
            "observed": f"{completed_cells} of {planned_cells}",
            "owner": "orchestration",
            "passed": completed_cells == planned_cells and planned_cells > 0,
            "severity": "high",
            "next_action": "Inspect the first incomplete cell and resume from its checkpoint.",
        },
        {
            "id": "integrity",
            "name": "Integrity checks pass",
            "target": "100%",
            "observed": f"{integrity_passing} of {integrity_total}",
            "owner": "evidence pipeline",
            "passed": integrity_passing == integrity_total and integrity_total > 0,
            "severity": "high",
            "next_action": "Quarantine the affected record and rerun seal reconciliation.",
        },
        {
            "id": "proposal_budget",
            "name": "Proposal budget exact",
            "target": f"{expected_proposals:,}",
            "observed": f"{proposal_count:,}",
            "owner": "search coordinator",
            "passed": proposal_count == expected_proposals,
            "severity": "medium",
            "next_action": "Resume the missing proposal work before comparing search methods.",
        },
        {
            "id": "method_balance",
            "name": "Matched method budgets",
            "target": f"{expected_each:,} each",
            "observed": " · ".join(
                f"{value:,} {method}" for method, value in sorted(method_proposals.items())
            ),
            "owner": "experiment design",
            "passed": method_balanced,
            "severity": "high",
            "next_action": "Reject the comparison until random and Bayesian budgets match.",
        },
        {
            "id": "retained_replays",
            "name": "Retained replays verified",
            "target": f"{expected_replays} retained",
            "observed": f"{retained_replays} of {expected_replays}",
            "owner": "replay evidence",
            "passed": retained_replays == expected_replays and expected_replays > 0,
            "severity": "medium",
            "next_action": "Rebuild the missing replay package from its sealed proposal record.",
        },
        {
            "id": "fault_fallback",
            "name": "Command-dropout fallback",
            "target": f"{expected_protected_scenes} of {expected_protected_scenes} scenes",
            "observed": f"{protected_scenes} of {expected_protected_scenes} scenes",
            "owner": "behavior V&V",
            "passed": (
                protected_scenes == expected_protected_scenes
                and expected_protected_scenes > 0
            ),
            "severity": "high",
            "next_action": "Block promotion and inspect the first failed protected rollout.",
        },
        {
            "id": "assistance_handoff",
            "name": "Assistance handoff recovery",
            "target": f"{expected_assisted_scenes} of {expected_assisted_scenes} scenes",
            "observed": f"{assisted_scenes} of {expected_assisted_scenes} scenes",
            "owner": "behavior V&V",
            "passed": (
                assisted_scenes == expected_assisted_scenes
                and expected_assisted_scenes > 0
            ),
            "severity": "high",
            "next_action": "Block promotion and inspect the first failed handoff transition.",
        },
    ]
    slos = [
        {
            "id": str(check["id"]),
            "name": str(check["name"]),
            "target": str(check["target"]),
            "observed": str(check["observed"]),
            "status": "pass" if check["passed"] else "fail",
            "owner": str(check["owner"]),
        }
        for check in checks
    ]
    alerts = [
        {
            "id": f"PM-HEALTH-{index:03d}",
            "severity": check["severity"],
            "state": "active",
            "component": check["owner"],
            "title": f"SLO failed: {check['name']}",
            "evidence": f"Observed {check['observed']}; target {check['target']}.",
            "failed_gates": [check["id"]],
            "next_action": check["next_action"],
            "source": "computed:test_operations",
        }
        for index, check in enumerate(checks, start=1)
        if not check["passed"]
    ]
    passing = sum(check["passed"] for check in checks)
    summary = {
        "status": "healthy" if passing == len(checks) else "degraded",
        "passing": passing,
        "total": len(checks),
    }
    return slos, summary, alerts


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sealed_json(path: Path, seal_field: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    random_search._validate_seal(value, seal_field, path=path)
    return value


def _plain_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _experiment(path: Path) -> dict[str, Any]:
    value = _plain_json(path)
    seal = value.get("report_sha256")
    if isinstance(seal, str):
        payload = dict(value)
        del payload["report_sha256"]
        accepted = {
            hashlib.sha256(_canonical_json(payload)).hexdigest(),
            random_search._content_sha256(payload),
        }
        if seal not in accepted:
            raise ValueError(f"Experiment report seal mismatch: {path}")
    if value.get("synthetic") is True:
        raise ValueError(f"Synthetic evidence is excluded from operations: {path}")
    return value


def _failed_gates(report: dict[str, Any]) -> list[str]:
    gates = report.get("gates", {})
    return sorted(name for name, passed in gates.items() if passed is False)


def build_report(root: Path) -> dict[str, Any]:
    """Reconstruct a privacy-safe operations view from verified local evidence."""

    root = root.resolve(strict=True)
    campaign_dir = root / DEFAULT_CAMPAIGN
    manifest = _sealed_json(campaign_dir / "run-manifest.json", "manifest_sha256")
    campaign = _sealed_json(campaign_dir / "report.json", "report_sha256")
    if campaign.get("decision") != "campaign_complete":
        raise ValueError("Test operations require a completed campaign")
    if campaign.get("campaign_id") != manifest.get("campaign_id"):
        raise ValueError("Campaign report and manifest identify different campaigns")

    analytics_dir = root / DEFAULT_ANALYTICS
    analytics_manifest = _sealed_json(analytics_dir / "manifest.json", "manifest_sha256")
    if analytics_manifest.get("campaign_report_sha256") != campaign["report_sha256"]:
        raise ValueError("Analytics do not identify the verified campaign report")
    database_path = analytics_dir / analytics_manifest["database"]["file"]
    if random_search._file_sha256(database_path) != analytics_manifest["database"]["sha256"]:
        raise ValueError("Analytics database hash does not match its manifest")

    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        cell_total, completed_cells = connection.execute(
            "SELECT count(*), count(*) FILTER (WHERE decision = 'cell_complete') FROM cells"
        ).fetchone()
        methods = connection.execute(
            "SELECT method, proposal_count, support_and_pipeline_valid_count, "
            "support_and_pipeline_valid_rate FROM methods ORDER BY method"
        ).fetchall()
        integrity_total, integrity_passing = connection.execute(
            "SELECT count(*), count(*) FILTER (WHERE passed) FROM integrity_gates"
        ).fetchone()
    finally:
        connection.close()

    selection = _plain_json(root / DEFAULT_SELECTION)
    if selection.get("status") != "passed":
        raise ValueError("Scenario selection did not pass")
    replay_count = len(list((root / DEFAULT_REPLAYS).glob("**/manifest.json")))
    if replay_count == 0:
        raise ValueError("No exact proposal replays were retained")

    tensorrt = _experiment(root / "experiments/tensorrt-qualification-v2.json")
    active_risk = _experiment(root / "experiments/active-risk-qualification-v2.json")
    residual = _experiment(root / "experiments/fp16-residual-candidate-v1.json")
    fault_protection = _experiment(
        root / "experiments/fault-protection-command-dropout-v1.json"
    )
    assistance_handoff = _experiment(
        root / "experiments/assistance-handoff-command-recovery-v1.json"
    )
    if tensorrt.get("status") != "no_go":
        raise ValueError("Expected the scaled TensorRT decision to remain a measured no-go")
    if active_risk.get("status") != "qualification_no_go":
        raise ValueError("Expected active-risk promotion to remain a measured no-go")
    if residual.get("status") != "tensorrt_required":
        raise ValueError("Expected the residual candidate to require TensorRT qualification")
    if fault_protection.get("status") != "qualified" or not all(
        fault_protection.get("gates", {}).values()
    ):
        raise ValueError("Fault-protection qualification did not pass")
    if assistance_handoff.get("status") != "qualified" or not all(
        assistance_handoff.get("gates", {}).values()
    ):
        raise ValueError("Assistance-handoff qualification did not pass")

    method_view = {
        method: {
            "proposal_count": proposal_count,
            "eligible_count": eligible_count,
            "eligible_rate": eligible_rate,
        }
        for method, proposal_count, eligible_count, eligible_rate in methods
    }
    proposal_budget = int(campaign["cost_total"]["core_mutation_attempts"])
    method_budget_balanced = (
        set(method_view) == {"bayesian", "random"}
        and method_view["bayesian"]["proposal_count"]
        == method_view["random"]["proposal_count"]
        == proposal_budget // 2
    )
    campaign_gates = campaign["integrity_gates"]
    slos, slo_summary, health_alerts = evaluate_test_health(
        completed_cells=completed_cells,
        planned_cells=cell_total,
        integrity_passing=integrity_passing,
        integrity_total=integrity_total,
        proposal_count=proposal_budget,
        expected_proposals=3200,
        method_proposals={
            method: int(values["proposal_count"])
            for method, values in method_view.items()
        },
        retained_replays=replay_count,
        expected_replays=10,
        protected_scenes=int(
            fault_protection["summary"]["protected_fallback_success_count"]
        ),
        expected_protected_scenes=int(fault_protection["dataset"]["scenario_count"]),
        assisted_scenes=int(
            assistance_handoff["summary"]["assisted_handoff_success_count"]
        ),
        expected_assisted_scenes=int(assistance_handoff["dataset"]["scenario_count"]),
    )
    if (
        slo_summary["status"] != "healthy"
        or not all(campaign_gates.values())
        or not method_budget_balanced
    ):
        raise ValueError("Campaign health invariants failed")

    fp16 = tensorrt["engines"]["fp16"]["pytorch_fp32_parity"]["256"]
    selected_family = selection["selection_protocol"]["selected_family"]
    scanned = int(selection["scan_summary"]["records_scanned"])
    selected = int(selection["scan_summary"]["selected_candidates"])
    report: dict[str, Any] = {
        "$schema": SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": RECORD_TYPE,
        "evidence_mode": "published_aggregate",
        "claim_boundary": (
            "Independent research evidence from bounded Waymo Open Dataset training "
            "scenes; not a Waymo Driver, fleet-health, or safety claim."
        ),
        "campaign": {
            "campaign_id": campaign["campaign_id"],
            "execution_health": "healthy",
            "behavior_outcome": "no_qualifying_regression",
            "completed_cells": completed_cells,
            "planned_cells": cell_total,
            "proposals": proposal_budget,
            "physical_rollouts": int(campaign["cost_total"]["total_physical_rollouts"]),
            "waymax_steps": int(campaign["cost_total"]["waymax_rollout_steps"]),
            "recorded_work_seconds": float(campaign["recorded_work_seconds"]),
            "real_data_only": True,
        },
        "slo_summary": slo_summary,
        "slos": slos,
        "pipeline_stages": [
            {
                "id": "selection",
                "name": "Scenario selection",
                "status": "healthy",
                "observed": f"{selected} selected from {scanned} scanned records",
                "detail": "Deterministic selection and baseline replay gates passed.",
            },
            {
                "id": "proposal",
                "name": "Counterfactual generation",
                "status": "healthy",
                "observed": f"{proposal_budget:,} proposals",
                "detail": "Matched random and Bayesian budgets completed.",
            },
            {
                "id": "simulation",
                "name": "Closed-loop validation",
                "status": "healthy",
                "observed": f"{campaign['cost_total']['total_physical_rollouts']:,} rollouts",
                "detail": "Reference and tested planners executed under identical mutations.",
            },
            {
                "id": "analytics",
                "name": "Coverage analytics",
                "status": "healthy",
                "observed": f"{integrity_passing} integrity checks",
                "detail": "DuckDB aggregates reconcile with sealed campaign records.",
            },
            {
                "id": "replay",
                "name": "Exact replay retention",
                "status": "healthy",
                "observed": f"{replay_count} priority replays",
                "detail": "Selective retention is explicit; full proposal paths remain private.",
            },
            {
                "id": "fault_v_and_v",
                "name": "Fault-injection V&V",
                "status": "healthy",
                "observed": "10/10 protected fallbacks pass",
                "detail": "Sustained command dropout triggered at 2.0 s in 60 deterministic rollouts.",
            },
            {
                "id": "assistance_v_and_v",
                "name": "Assistance handoff V&V",
                "status": "healthy",
                "observed": "10/10 handoffs pass",
                "detail": "Fault, request, fallback, resolution, and recovery verified in 60 repeated rollouts.",
            },
        ],
        "coverage": {
            "plan_version": "lead-braking-v1",
            "scenario_family": selected_family,
            "scenario_count": selected,
            "seeds": 5,
            "search_methods": 2,
            "cells": cell_total,
            "mutation_dimensions": ["lead speed multiplier", "braking onset offset"],
            "methods": method_view,
            "fault_protection": {
                "plan_version": "command-dropout-v1",
                "fault": "sustained planner-command dropout",
                "protected_behavior": "conservative IDM fallback",
                "scenario_count": fault_protection["dataset"]["scenario_count"],
                "physical_rollouts": fault_protection["protocol"]["physical_rollouts"],
                "scene_gate_passes": fault_protection["summary"]["scene_gate_passes"],
                "scene_gate_total": fault_protection["summary"]["scene_gate_total"],
                "status": "qualified",
            },
            "assistance_handoff": {
                "plan_version": "command-recovery-v1",
                "fault": "temporary planner-command dropout",
                "protected_behavior": "fallback until deterministic assistance resolution",
                "scenario_count": assistance_handoff["dataset"]["scenario_count"],
                "physical_rollouts": assistance_handoff["protocol"]["physical_rollouts"],
                "scene_gate_passes": assistance_handoff["summary"]["scene_gate_passes"],
                "scene_gate_total": assistance_handoff["summary"]["scene_gate_total"],
                "exact_transition_count": assistance_handoff["summary"][
                    "exact_transition_count"
                ],
                "status": "qualified",
            },
            "known_gaps": [
                {
                    "id": "simulator_diversity",
                    "label": "Cross-simulator agreement",
                    "status": "not_covered",
                    "next_test": "Repeat the frozen test contract in a second simulator.",
                },
            ],
        },
        "issues": health_alerts
        + [
            {
                "id": "PM-TRT-002",
                "severity": "high",
                "state": "blocked",
                "component": "TensorRT FP16 promotion",
                "title": "Scaled FP16 drift exceeds the promotion gate",
                "evidence": (
                    f"Batch 256 max drift {fp16['max_absolute_error_m']:.3f} m "
                    "exceeds the 0.075 m gate."
                ),
                "failed_gates": _failed_gates(tensorrt),
                "next_action": "Keep FP32; qualify the residual FP16 candidate independently.",
                "source": "experiments/tensorrt-qualification-v2.json",
            },
            {
                "id": "PM-RANK-006",
                "severity": "medium",
                "state": "stopped",
                "component": "Active-risk proposal ranking",
                "title": "Learned ranker did not generalize across scenarios",
                "evidence": f"{len(_failed_gates(active_risk))} promotion gates failed.",
                "failed_gates": _failed_gates(active_risk),
                "next_action": "Retain deterministic search; redesign only under a new protocol.",
                "source": "experiments/active-risk-qualification-v2.json",
            },
            {
                "id": "PM-TRT-011",
                "severity": "medium",
                "state": "pending_evidence",
                "component": "Residual FP16 candidate",
                "title": "Local numerical proxy passed; TensorRT evidence is still required",
                "evidence": "Four local proxy gates pass; no TensorRT promotion claim is made.",
                "failed_gates": [],
                "next_action": "Run the frozen candidate in a free T4 runtime before promotion.",
                "source": "experiments/fp16-residual-candidate-v1.json",
            },
        ],
        "source_seals": {
            "campaign_manifest_sha256": manifest["manifest_sha256"],
            "campaign_report_sha256": campaign["report_sha256"],
            "analytics_manifest_sha256": analytics_manifest["manifest_sha256"],
            "tensorrt_report_sha256": tensorrt["report_sha256"],
            "active_risk_report_sha256": active_risk["report_sha256"],
            "fault_protection_report_sha256": fault_protection["report_sha256"],
            "assistance_handoff_report_sha256": assistance_handoff["report_sha256"],
        },
    }
    report["report_sha256"] = hashlib.sha256(_canonical_json(report)).hexdigest()
    return report


def validate_report(report: dict[str, Any]) -> None:
    if report.get("record_type") != RECORD_TYPE or report.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported test-operations report")
    seal = report.get("report_sha256")
    if not isinstance(seal, str) or len(seal) != 64:
        raise ValueError("Test-operations report is missing its seal")
    payload = dict(report)
    del payload["report_sha256"]
    if hashlib.sha256(_canonical_json(payload)).hexdigest() != seal:
        raise ValueError("Test-operations report seal mismatch")
    if report.get("campaign", {}).get("real_data_only") is not True:
        raise ValueError("Operations report must exclude synthetic evidence")


def load_report(path: Path) -> dict[str, Any]:
    report = _plain_json(path)
    validate_report(report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_report(args.root)
    output = args.output if args.output.is_absolute() else args.root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_canonical_json(report))
    print(json.dumps({"output": str(output), "report_sha256": report["report_sha256"]}))


if __name__ == "__main__":
    main()
