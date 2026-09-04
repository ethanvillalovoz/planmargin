"""Contract tests for the role-aligned test-operations report."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest
from fastapi.testclient import TestClient

from planmargin import evidence_api
from planmargin import test_operations

ROOT = Path(__file__).parents[1]
PUBLIC_REPORT = ROOT / test_operations.DEFAULT_OUTPUT
LOCAL_CAMPAIGN_AVAILABLE = (
    ROOT / test_operations.DEFAULT_CAMPAIGN / "run-manifest.json"
).is_file()


@pytest.mark.skipif(
    not LOCAL_CAMPAIGN_AVAILABLE,
    reason="requires the authorized local campaign and analytics workspace",
)
def test_repository_report_matches_verified_real_campaign() -> None:
    report = test_operations.build_report(ROOT)
    stored = test_operations.load_report(PUBLIC_REPORT)
    assert report == stored
    assert report["campaign"] == {
        "campaign_id": "natural-development-v1",
        "execution_health": "healthy",
        "behavior_outcome": "no_qualifying_regression",
        "completed_cells": 100,
        "planned_cells": 100,
        "proposals": 3200,
        "physical_rollouts": 14110,
        "waymax_steps": 1128800,
        "recorded_work_seconds": 30140.262755,
        "real_data_only": True,
    }
    assert report["slo_summary"] == {"status": "healthy", "passing": 7, "total": 7}
    assert len(report["pipeline_stages"]) == 7
    assert report["coverage"]["fault_protection"]["scene_gate_passes"] == 80
    assert report["coverage"]["fault_protection"]["status"] == "qualified"
    assert report["coverage"]["assistance_handoff"]["scene_gate_passes"] == 90
    assert report["coverage"]["assistance_handoff"]["status"] == "qualified"
    assert {issue["state"] for issue in report["issues"]} == {
        "blocked",
        "stopped",
        "pending_evidence",
    }


def test_report_validates_against_schema_and_contains_no_private_identifiers() -> None:
    report = test_operations.load_report(PUBLIC_REPORT)
    schema = json.loads((ROOT / "schemas/test-operations-report-v2.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(report)
    assert report["schema_version"] == "2.0.0"
    assert report["test_inventory"]["release_critical_cells"] == 120
    assert report["test_inventory"]["passing_release_critical_cells"] == 120
    assert len(report["test_inventory"]["suites"]) == 3
    assert len(report["coverage"]["versioned_plans"]) == 3
    assert {gap["id"] for gap in report["coverage"]["known_gaps"]} == {
        "simulator_diversity",
        "scheduled_completion_latency",
    }
    assert all("diagnostic" in issue for issue in report["issues"])
    serialized = json.dumps(report).lower()
    for forbidden in ("scenario_id", "source_uri", "/users/", ".tfrecord", "synthetic_no_go"):
        assert forbidden not in serialized


def test_report_tampering_is_rejected() -> None:
    report = copy.deepcopy(test_operations.load_report(PUBLIC_REPORT))
    report["campaign"]["proposals"] += 1
    with pytest.raises(ValueError, match="seal"):
        test_operations.validate_report(report)


def test_health_evaluator_identifies_root_cause_in_degraded_run() -> None:
    slos, summary, alerts = test_operations.evaluate_test_health(
        completed_cells=99,
        planned_cells=100,
        integrity_passing=806,
        integrity_total=807,
        proposal_count=3190,
        expected_proposals=3200,
        method_proposals={"random": 1600, "bayesian": 1590},
        retained_replays=9,
        expected_replays=10,
        protected_scenes=9,
        expected_protected_scenes=10,
        assisted_scenes=9,
        expected_assisted_scenes=10,
    )
    assert summary == {"status": "degraded", "passing": 0, "total": 7}
    assert {slo["status"] for slo in slos} == {"fail"}
    assert {alert["failed_gates"][0] for alert in alerts} == {
        "cell_completion",
        "integrity",
        "proposal_budget",
        "method_balance",
        "retained_replays",
        "fault_fallback",
        "assistance_handoff",
    }
    assert all(alert["next_action"] for alert in alerts)


def test_api_contract_accepts_degraded_health_evidence() -> None:
    report = copy.deepcopy(test_operations.load_report(PUBLIC_REPORT))
    report.pop("$schema")
    report["campaign"]["execution_health"] = "degraded"
    report["slo_summary"]["status"] = "degraded"
    report["slos"][0]["status"] = "fail"
    report["pipeline_stages"][0]["status"] = "degraded"
    report["issues"].insert(
        0,
        {
            "id": "PM-HEALTH-001",
            "severity": "high",
            "state": "active",
            "component": "orchestration",
            "title": "SLO failed: Campaign cells complete",
            "evidence": "Observed 99 of 100; target 100 of 100.",
            "failed_gates": ["cell_completion"],
            "next_action": "Resume from the first incomplete checkpoint.",
            "source": "computed:test_operations",
            "diagnostic": {
                "detected_by": "cell-completion SLO",
                "owner": "orchestration",
                "impact": "Release evidence is incomplete.",
                "root_cause_path": ["campaign", "cell scheduler", "completion gate"],
                "resolution": "Resume from the first incomplete checkpoint.",
                "prevention": "Alert before the completion budget is exhausted.",
            },
        },
    )

    parsed = evidence_api.TestOperationsEvidence.model_validate(report)
    assert parsed.campaign["execution_health"] == "degraded"
    assert parsed.slos[0].status == "fail"
    assert parsed.pipeline_stages[0].status == "degraded"
    assert parsed.issues[0].state == "active"


@pytest.mark.skipif(
    not LOCAL_CAMPAIGN_AVAILABLE,
    reason="requires the authorized local evidence API workspace",
)
def test_authenticated_api_serves_the_sealed_operations_contract() -> None:
    token = "test-operations-token-000000"
    app = evidence_api.create_app(root=ROOT, token=token)
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/test-operations", headers={"X-PlanMargin-Token": token}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["report_sha256"] == test_operations.load_report(PUBLIC_REPORT)[
        "report_sha256"
    ]
    assert body["slo_summary"] == {"status": "healthy", "passing": 7, "total": 7}
