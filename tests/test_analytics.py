"""Data-free checks for the private DuckDB and Parquet analytical layer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import jsonschema
import pytest

from planmargin import analytics
from planmargin import matched_campaign
from planmargin import matched_coordinator
from planmargin import random_search

REPOSITORY_ROOT = Path(__file__).parents[1]


def _cost(total_physical_rollouts: int) -> dict[str, int]:
    return {
        "core_mutation_attempts": 32,
        "reference_controller_logical_evaluations": 33,
        "reference_controller_physical_rollouts": 66,
        "scenario_validation_logical_evaluations": 32,
        "scenario_validation_physical_rollouts": 64,
        "tested_controller_logical_evaluations": 33,
        "tested_controller_physical_rollouts": 66,
        "total_physical_rollouts": total_physical_rollouts,
        "waymax_rollout_steps": total_physical_rollouts * 80,
    }


def _cell_report(
    cell: matched_coordinator.CellConfig, support_fingerprint: str
) -> dict[str, Any]:
    bayesian = cell.method == "bayesian"
    valid_count = 23 if bayesian else 20
    report = {
        "$schema": matched_coordinator.REPORT_SCHEMA_URI,
        "schema_version": matched_coordinator.SCHEMA_VERSION,
        "record_type": matched_coordinator.REPORT_TYPE,
        "identity": {
            "method": cell.method,
            "track": cell.track,
            "seed": cell.seed,
            "selection_order": cell.selection_order,
            "proposal_index": None,
        },
        "configuration_fingerprint": "b" * 64,
        "support_model_fingerprint": support_fingerprint,
        "status": "completed",
        "decision": "cell_complete",
        "integrity_gates": {"synthetic_complete": True},
        "metrics": {
            "proposal_budget": 32,
            "proposal_count": 32,
            "accepted_proposal_count": 30,
            "pipeline_valid_count": 25,
            "support_and_pipeline_valid_count": valid_count,
            "fully_feasible_count": valid_count,
            "qualifying_failure_count": 0,
            "first_qualifying_failure_proposal_count": None,
            "restricted_physical_rollouts_to_first_qualifying_failure": 196,
            "minimum_failure_mutation_distance": None,
            "pipeline_valid_rate": 0.78125,
            "support_and_pipeline_valid_rate": valid_count / 32,
            "duplicate_proposal_count": 0,
            "status_counts": {"accepted": 30, "mutation_rejected": 2},
            "final_feasible_hypervolume": 0.5 if bayesian else 0.4,
            "feasible_hypervolume_by_proposal": [
                round((index + 1) / (64 if bayesian else 80), 12)
                for index in range(32)
            ],
            "recorded_work_seconds": 10.0,
            "final_invocation_seconds": 10.0,
            "process_peak_rss_bytes": 1024,
        },
        "cost": {
            "original": _cost(4),
            "proposals": _cost(192),
            "total": _cost(196),
        },
        "limitations": ["synthetic test record"],
    }
    return random_search._seal_record(report, "report_sha256")


def _prepare_campaign(root: Path) -> Path:
    campaign_dir = root / "artifacts/search-comparison/natural-development-v1"
    support_fingerprint = "a" * 64
    run_manifest = random_search._seal_record(
        {
            "$schema": matched_campaign.MANIFEST_SCHEMA_URI,
            "schema_version": matched_campaign.SCHEMA_VERSION,
            "record_type": matched_campaign.MANIFEST_TYPE,
            "campaign_id": matched_campaign.CAMPAIGN_ID,
            "configuration_fingerprint": "c" * 64,
            "configuration": {
                "support": {"model_fingerprint": support_fingerprint}
            },
        },
        "manifest_sha256",
    )
    reports = []
    for cell in matched_campaign.campaign_cells():
        report = _cell_report(cell, support_fingerprint)
        reports.append(report)
        path = matched_campaign.cell_output_dir(campaign_dir, cell) / "report.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report), encoding="utf-8")
    campaign_report = matched_campaign.build_report(
        run_manifest=run_manifest,
        cell_reports=reports,
        invocation_seconds=1000.0,
        process_peak_rss_bytes=2048,
    )
    (campaign_dir / "run-manifest.json").write_text(
        json.dumps(run_manifest), encoding="utf-8"
    )
    (campaign_dir / "report.json").write_text(
        json.dumps(campaign_report), encoding="utf-8"
    )
    return campaign_dir


def test_builds_verified_duckdb_and_parquet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    campaign_dir = _prepare_campaign(tmp_path)
    output_dir = tmp_path / "artifacts/analytics/natural-development-v1"

    manifest = analytics.build_analytics(
        campaign_dir=campaign_dir, output_dir=output_dir
    )

    schema = json.loads(
        (REPOSITORY_ROOT / "schemas/analytics-manifest-v1.schema.json").read_text()
    )
    jsonschema.Draft202012Validator(schema).validate(manifest)
    random_search._validate_seal(
        manifest, "manifest_sha256", path=output_dir / "manifest.json"
    )
    assert manifest["table_row_counts"] == {
        "campaign": 1,
        "methods": 2,
        "hypotheses": 3,
        "cells": 100,
        "hypervolume_trace": 3200,
        "status_counts": 200,
        "integrity_gates": 107,
    }
    connection = duckdb.connect(str(output_dir / analytics.DATABASE_NAME))
    try:
        assert connection.execute(
            "SELECT sum(proposal_count) FROM methods"
        ).fetchone()[0] == 3200
        assert connection.execute(
            "SELECT count(*) FROM read_parquet(?)",
            [str(output_dir / "cells.parquet")],
        ).fetchone()[0] == 100
    finally:
        connection.close()
    summary = analytics.public_summary(manifest)
    assert summary["decision"] == "analytics_verified"
    assert "output" not in summary
    assert "scenario" not in json.dumps(summary)


def test_output_is_reproducible_and_cannot_be_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    campaign_dir = _prepare_campaign(tmp_path)
    first_dir = tmp_path / "artifacts/analytics/first"
    second_dir = tmp_path / "artifacts/analytics/second"

    first = analytics.build_analytics(
        campaign_dir=campaign_dir, output_dir=first_dir
    )
    second = analytics.build_analytics(
        campaign_dir=campaign_dir, output_dir=second_dir
    )

    assert first == second
    with pytest.raises(FileExistsError, match="already exists"):
        analytics.build_analytics(
            campaign_dir=campaign_dir, output_dir=first_dir
        )


def test_rejects_paths_and_tampered_cell_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    campaign_dir = _prepare_campaign(tmp_path)
    with pytest.raises(ValueError, match="campaign-dir"):
        analytics.build_analytics(
            campaign_dir=tmp_path / "elsewhere",
            output_dir=tmp_path / "artifacts/analytics/result",
        )
    with pytest.raises(ValueError, match="output-dir"):
        analytics.build_analytics(
            campaign_dir=campaign_dir, output_dir=tmp_path / "public/result"
        )

    report_path = next((campaign_dir / "cells").rglob("report.json"))
    report = json.loads(report_path.read_text())
    report["metrics"]["proposal_count"] = 31
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="content seal"):
        analytics.build_analytics(
            campaign_dir=campaign_dir,
            output_dir=tmp_path / "artifacts/analytics/tampered",
        )
