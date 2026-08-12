"""Data-free checks for the complete matched-search campaign layer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from planmargin import empirical_support
from planmargin import matched_campaign
from planmargin import matched_coordinator
from planmargin import matched_search
from planmargin import random_search

REPOSITORY_ROOT = Path(__file__).parents[1]


def _candidates() -> list[dict[str, Any]]:
    return [
        {
            "family": "lead_vehicle_braking",
            "selection_order": order,
            "scenario_id": f"private-scenario-{order}",
            "source_shard": "private-training-shard",
            "shard_index": 0,
            "record_index": order * 11,
            "interacting_object_index": order + 1,
        }
        for order in range(1, 11)
    ]


def _vector(index: int) -> list[float]:
    offset = index / 100.0
    return [
        20.0 + offset,
        1.0 + offset,
        10.0 + offset,
        3.0 + offset,
        4.0 + offset,
        1.5 + offset,
        0.9 + offset / 10.0,
        2.0 + offset,
    ]


def _prepare(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    manifest = tmp_path / "selection.json"
    model_path = tmp_path / "support-model.json"
    manifest.write_text(json.dumps({"candidates": _candidates()}), encoding="utf-8")
    events = [
        {"event_key": f"{index:064x}", "vector": _vector(index)}
        for index in range(20)
    ]
    model = empirical_support.fit_model(events, configuration_fingerprint="a" * 64)
    model_path.write_text(json.dumps(model, sort_keys=True), encoding="utf-8")
    return manifest, model_path, model


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
    cell: matched_coordinator.CellConfig,
    *,
    support_fingerprint: str,
    finding: bool = True,
    valid_count: int | None = None,
) -> dict[str, Any]:
    bayesian = cell.method == "bayesian"
    count = valid_count if valid_count is not None else (23 if bayesian else 24)
    first = (5 if bayesian else 10) if finding else None
    distance = (0.4 if bayesian else 0.6) if finding else None
    physical_to_first = (34 if bayesian else 64) if finding else 196
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
            "accepted_proposal_count": 32,
            "pipeline_valid_count": 30,
            "support_and_pipeline_valid_count": count,
            "fully_feasible_count": count,
            "qualifying_failure_count": 1 if finding else 0,
            "first_qualifying_failure_proposal_count": first,
            "restricted_physical_rollouts_to_first_qualifying_failure": (
                physical_to_first
            ),
            "minimum_failure_mutation_distance": distance,
            "pipeline_valid_rate": 0.9375,
            "support_and_pipeline_valid_rate": count / 32,
            "duplicate_proposal_count": 0,
            "status_counts": {"accepted": 32},
            "final_feasible_hypervolume": 0.5 if bayesian else 0.4,
            "feasible_hypervolume_by_proposal": [
                round((index + 1) / 64, 12) for index in range(32)
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


def _campaign_manifest(support_fingerprint: str) -> dict[str, Any]:
    return {
        "configuration_fingerprint": "c" * 64,
        "configuration": {"support": {"model_fingerprint": support_fingerprint}},
    }


def _reports(
    support_fingerprint: str,
    *,
    finding: bool = True,
    valid_counts: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    return [
        _cell_report(
            cell,
            support_fingerprint=support_fingerprint,
            finding=finding,
            valid_count=(valid_counts or {}).get(cell.method),
        )
        for cell in matched_campaign.campaign_cells()
    ]


def test_campaign_grid_is_exact_and_pair_first() -> None:
    cells = matched_campaign.campaign_cells()

    assert len(cells) == 100
    assert len(set(cells)) == 100
    assert cells[:4] == (
        matched_coordinator.CellConfig("random", "natural", 0, 1),
        matched_coordinator.CellConfig("bayesian", "natural", 0, 1),
        matched_coordinator.CellConfig("random", "natural", 1, 1),
        matched_coordinator.CellConfig("bayesian", "natural", 1, 1),
    )
    assert {cell.track for cell in cells} == {"natural"}
    assert len(cells) * matched_search.PROPOSAL_BUDGET == 3200


def test_campaign_report_derives_supported_hypotheses() -> None:
    fingerprint = "d" * 64
    report = matched_campaign.build_report(
        run_manifest=_campaign_manifest(fingerprint),
        cell_reports=_reports(fingerprint),
        invocation_seconds=12.0,
        process_peak_rss_bytes=2048,
    )

    assert report["decision"] == "campaign_complete"
    assert report["metrics_by_method"]["random"]["proposal_count"] == 1600
    assert report["metrics_by_method"]["bayesian"]["proposal_count"] == 1600
    assert report["hypotheses"]["h1_efficiency"]["status"] == "supported"
    assert report["hypotheses"]["h2_minimality"] == {
        "status": "supported",
        "paired_cell_count": 50,
        "median_bayesian_minus_random_mutation_distance": -0.2,
    }
    assert report["hypotheses"]["h3_validity"]["status"] == "supported"
    assert report["cost_total"]["total_physical_rollouts"] == 19600
    jsonschema.Draft202012Validator(
        json.loads(
            (
                REPOSITORY_ROOT
                / "schemas"
                / "matched-campaign-report-v1.schema.json"
            ).read_text()
        )
    ).validate(report)


def test_zero_findings_leave_h1_and_h2_untestable() -> None:
    fingerprint = "e" * 64
    report = matched_campaign.build_report(
        run_manifest=_campaign_manifest(fingerprint),
        cell_reports=_reports(fingerprint, finding=False),
        invocation_seconds=1.0,
        process_peak_rss_bytes=1,
    )

    assert report["hypotheses"]["h1_efficiency"]["status"] == "untestable"
    assert report["hypotheses"]["h2_minimality"]["status"] == "untestable"


def test_h3_applies_the_frozen_noninferiority_margin() -> None:
    fingerprint = "f" * 64
    report = matched_campaign.build_report(
        run_manifest=_campaign_manifest(fingerprint),
        cell_reports=_reports(
            fingerprint,
            valid_counts={"random": 30, "bayesian": 20},
        ),
        invocation_seconds=1.0,
        process_peak_rss_bytes=1,
    )

    h3 = report["hypotheses"]["h3_validity"]
    assert h3["status"] == "unsupported"
    assert h3["noninferiority_margin"] == 0.05
    assert h3["bayesian_minus_random_valid_rate"] == -0.3125


def test_bounded_campaign_resume_and_tamper_detection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, model_path, model = _prepare(tmp_path)
    output = Path("artifacts/search-comparison/campaign")
    calls: list[tuple[matched_coordinator.CellConfig, bool]] = []

    def runner(
        cell: matched_coordinator.CellConfig,
        cell_dir: Path,
        resume: bool,
    ) -> dict[str, Any]:
        calls.append((cell, resume))
        path = cell_dir / "report.json"
        if path.exists():
            return json.loads(path.read_text())
        report = _cell_report(
            cell,
            support_fingerprint=model["model_fingerprint"],
        )
        random_search._atomic_write_json(path, report)
        return report

    progress = matched_campaign.run(
        manifest_path=manifest,
        support_model_path=model_path,
        output_dir=output,
        max_new_cells=2,
        cell_runner=runner,
    )
    assert progress["completed_cell_count"] == 2
    assert progress["new_cell_count"] == 2
    assert len(calls) == 2

    calls.clear()
    resumed = matched_campaign.run(
        manifest_path=manifest,
        support_model_path=model_path,
        output_dir=output,
        resume=True,
        max_new_cells=0,
        cell_runner=runner,
    )
    assert resumed["completed_cell_count"] == 2
    assert resumed["new_cell_count"] == 0
    assert calls == [
        (matched_campaign.campaign_cells()[0], True),
        (matched_campaign.campaign_cells()[1], True),
    ]

    first_report = matched_campaign.cell_output_dir(
        output, matched_campaign.campaign_cells()[0]
    ) / "report.json"
    tampered = json.loads(first_report.read_text())
    tampered["metrics"]["proposal_count"] = 31
    first_report.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="content seal"):
        matched_campaign.run(
            manifest_path=manifest,
            support_model_path=model_path,
            output_dir=output,
            resume=True,
            max_new_cells=0,
            cell_runner=runner,
        )


def test_complete_campaign_resume_reconstructs_without_new_cells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, model_path, model = _prepare(tmp_path)
    output = Path("artifacts/search-comparison/complete-campaign")
    created = 0

    def runner(
        cell: matched_coordinator.CellConfig,
        cell_dir: Path,
        resume: bool,
    ) -> dict[str, Any]:
        nonlocal created
        path = cell_dir / "report.json"
        if path.exists():
            assert resume
            return json.loads(path.read_text())
        created += 1
        report = _cell_report(
            cell,
            support_fingerprint=model["model_fingerprint"],
        )
        random_search._atomic_write_json(path, report)
        return report

    completed = matched_campaign.run(
        manifest_path=manifest,
        support_model_path=model_path,
        output_dir=output,
        cell_runner=runner,
    )
    assert completed["decision"] == "campaign_complete"
    assert created == 100

    resumed = matched_campaign.run(
        manifest_path=manifest,
        support_model_path=model_path,
        output_dir=output,
        resume=True,
        max_new_cells=0,
        cell_runner=runner,
    )
    assert resumed == completed
    assert created == 100


def test_manifest_schema_and_readiness_are_data_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest_path, model_path, model = _prepare(tmp_path)
    output = Path("artifacts/search-comparison/readiness")
    output.parent.mkdir(parents=True)
    manifest = matched_campaign.build_run_manifest(
        manifest_path=manifest_path,
        support_model=model,
    )
    schema = json.loads(
        (
            REPOSITORY_ROOT
            / "schemas"
            / "matched-campaign-run-manifest-v1.schema.json"
        ).read_text()
    )
    jsonschema.Draft202012Validator(schema).validate(manifest)

    result = matched_campaign.readiness(
        manifest_path=manifest_path,
        support_model_path=model_path,
        output_dir=output,
    )
    assert result["scenario_count"] == 10
    assert result["cell_count"] == 100
    assert result["proposal_count"] == 3200
    assert result["maximum_physical_rollouts"] == 19600
    assert result["held_out_opened"] is False
    assert "scenario_id" not in json.dumps(result)
