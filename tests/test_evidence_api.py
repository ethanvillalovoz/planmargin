"""Data-free security and response-contract tests for the local evidence API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import pytest
from fastapi.testclient import TestClient

from planmargin import analytics
from planmargin import evidence_api
from planmargin import random_search

TOKEN = "data-free-test-token-000000000"
CELL_ID = evidence_api._opaque_id("cell", "bayesian", 0, 1)


def _track(offset: float) -> dict[str, list[Any]]:
    return {
        "timestep": [10, 11],
        "x_m": [offset, offset + 1.0],
        "y_m": [0.0, 0.0],
        "z_m": [0.0, 0.0],
        "yaw_rad": [0.0, 0.0],
        "speed_mps": [10.0, 10.0],
        "vel_x_mps": [10.0, 10.0],
        "vel_y_mps": [0.0, 0.0],
        "valid": [True, True],
    }


def _record(variant: str, role: str, offset: float) -> dict[str, Any]:
    return {
        "variant": variant,
        "controller_role": role,
        "trajectory": _track(offset),
        "outcome": {"success": role == "reference"},
        "reproducibility": {"outputs_identical": True},
        "mutation": {
            "accepted": True,
            "mutation_type": "lead_braking",
            "parameters": {
                "braking_onset_offset_s": 0.2,
                "speed_multiplier": 0.8,
            },
        },
    }


def _collection() -> dict[str, Any]:
    lead = {
        "timestep": [10, 11],
        "x_m": [12.0, 12.8],
        "y_m": [0.0, 0.0],
        "yaw_rad": [0.0, 0.0],
        "length_m": [4.5, 4.5],
        "width_m": [2.0, 2.0],
        "valid": [True, True],
    }
    return {
        "collection_status": "complete",
        "comparison_key": "private-comparison-key",
        "scene_context_sha256": "private-scene-hash",
        "comparison_finding": {"policy_specific_avoidable_failure": False},
        "scene_context": {
            "actors": {
                "sdc": {"length_m": 4.8, "width_m": 2.0},
                "mutation_target": {
                    "original": lead,
                    "counterfactual": lead,
                },
            },
            "roadgraph_features": [{"x_m": [-5.0, 20.0], "y_m": [0.0, 0.0]}],
        },
        "records": [
            _record("original", "tested", 0.0),
            _record("original", "reference", 0.2),
            _record("counterfactual", "tested", 1.0),
            _record("counterfactual", "reference", 1.2),
        ],
    }


@pytest.fixture
def app_root(tmp_path: Path) -> Path:
    for relative in (
        evidence_api.DEFAULT_ANALYTICS,
        evidence_api.DEFAULT_CAMPAIGN,
        evidence_api.DEFAULT_ROLLOUTS.parent,
    ):
        (tmp_path / relative).mkdir(parents=True, exist_ok=True)
    (tmp_path / evidence_api.DEFAULT_ROLLOUTS).write_text("{}", encoding="utf-8")
    return tmp_path


def _seed_repository(repository: evidence_api.EvidenceRepository) -> None:
    repository.analytics_manifest = {
        "privacy_scope": "sealed_campaign_and_cell_aggregates_only"
    }
    repository.campaign_report = {"campaign_id": "development-v1"}
    repository.collection = _collection()
    repository._run_id = "run_opaque"
    repository._cell_by_id = {CELL_ID: ("bayesian", 0, 1)}


def _fake_query(sql: str) -> list[dict[str, Any]]:
    if "FROM campaign" in sql:
        return [
            {
                "status": "completed",
                "decision": "campaign_complete",
                "recorded_work_seconds": 12.5,
                "total_physical_rollouts": 24,
                "waymax_rollout_steps": 1920,
            }
        ]
    if "FROM methods" in sql:
        return [{"method": "bayesian", "proposal_count": 32}]
    if "FROM hypotheses" in sql:
        return [{"hypothesis": "H1", "status": "untestable"}]
    if "FROM cells" in sql:
        return [
            {
                "method": "bayesian",
                "track": "natural",
                "seed": 0,
                "selection_order": 1,
                "decision": "cell_complete",
                "proposal_count": 32,
                "pipeline_valid_count": 30,
                "support_and_pipeline_valid_count": 25,
                "qualifying_failure_count": 0,
                "minimum_failure_mutation_distance": None,
                "pipeline_valid_rate": 0.9375,
                "support_and_pipeline_valid_rate": 0.78125,
                "duplicate_proposal_count": 0,
                "final_feasible_hypervolume": 0.4,
                "total_physical_rollouts": 196,
                "waymax_rollout_steps": 15680,
            }
        ]
    raise AssertionError(f"Unexpected API query: {sql}")


def test_authenticated_routes_are_redacted_and_not_cached(
    app_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def open_repository(repository: evidence_api.EvidenceRepository) -> None:
        _seed_repository(repository)

    monkeypatch.setattr(evidence_api.EvidenceRepository, "open", open_repository)
    monkeypatch.setattr(
        evidence_api.EvidenceRepository, "_query", lambda _, sql: _fake_query(sql)
    )
    monkeypatch.setattr(
        evidence_api.EvidenceRepository,
        "proposals",
        lambda _, cell_id: [
            {
                "proposal_number": 1,
                "attempt_status": "mutation_rejected",
                "normalized_mutation_distance": 0.9,
                "mutation_parameters": {
                    "braking_onset_offset_s": 0.2,
                    "speed_multiplier": 0.8,
                },
                "duplicate_of_proposal_numbers": [],
                "empirical_support_probability": None,
                "support_passes": None,
                "objective_available": False,
                "objectives": [0.0, 0.0],
                "constraints": [0.5, 1.0, 0.5],
                "pipeline_reproducible": None,
                "policy_specific_avoidable_failure": None,
                "tested_mutated_failure": None,
                "reference_mutated_success": None,
                "physical_rollouts": 0,
            }
        ]
        if cell_id == CELL_ID
        else (_ for _ in ()).throw(KeyError(cell_id)),
    )
    app = evidence_api.create_app(root=app_root, token=TOKEN)

    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 401
        assert (
            client.get(
                "/api/v1/health", headers={"X-PlanMargin-Token": "incorrect"}
            ).status_code
            == 401
        )
        headers = {"X-PlanMargin-Token": TOKEN}
        campaign = client.get("/api/v1/campaign", headers=headers)
        cells = client.get("/api/v1/cells", headers=headers)
        proposals = client.get(f"/api/v1/cells/{CELL_ID}/proposals", headers=headers)
        runs = client.get("/api/v1/runs", headers=headers)
        run = client.get("/api/v1/runs/run_opaque", headers=headers)
        contract = client.get("/api/v1/openapi.json", headers=headers)

        for response in (campaign, cells, proposals, runs, run, contract):
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["x-content-type-options"] == "nosniff"
            serialized = response.text
            assert "private-comparison-key" not in serialized
            assert "private-scene-hash" not in serialized
            assert '"scenario_id":' not in serialized
            assert '"source_shard":' not in serialized
            assert '"record_index":' not in serialized

        assert campaign.json()["held_out_opened"] is False
        assert cells.json()[0]["cell_id"] == CELL_ID
        assert proposals.json()[0]["support_passes"] is None
        assert run.json()["synthetic"] is False
        assert len(run.json()["hypothesis"]["metrics"]) == 2
        assert "RunEvidence" in contract.json()["components"]["schemas"]
        security_schemes = contract.json()["components"]["securitySchemes"]
        assert next(iter(security_schemes.values())) == {
            "type": "apiKey",
            "in": "header",
            "name": "X-PlanMargin-Token",
        }
        assert client.get("/api/v1/openapi.json").status_code == 401
        assert client.get("/api/v1/runs/unknown", headers=headers).status_code == 404
        assert (
            client.get("/api/v1/cells?sql=select+*", headers=headers).status_code == 400
        )
        assert client.post("/api/v1/campaign", headers=headers).status_code == 405
        assert (
            client.get(
                "/api/v1/health",
                headers={**headers, "Host": "attacker.example"},
            ).status_code
            == 400
        )


def test_cors_allows_only_declared_debugger_origin(
    app_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        evidence_api.EvidenceRepository,
        "open",
        lambda repository: _seed_repository(repository),
    )
    app = evidence_api.create_app(root=app_root, token=TOKEN)
    headers = {
        "Origin": "http://127.0.0.1:4200",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "X-PlanMargin-Token",
    }
    with TestClient(app) as client:
        allowed = client.options("/api/v1/health", headers=headers)
        forbidden = client.options(
            "/api/v1/health",
            headers={**headers, "Origin": "https://attacker.example"},
        )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == headers["Origin"]
    assert forbidden.status_code == 400
    assert "access-control-allow-origin" not in forbidden.headers


def _analytics_fixture(root: Path) -> tuple[evidence_api.EvidenceRepository, Path]:
    analytics_dir = root / evidence_api.DEFAULT_ANALYTICS
    analytics_dir.mkdir(parents=True)
    database = analytics_dir / analytics.DATABASE_NAME
    connection = duckdb.connect(str(database))
    try:
        for table in analytics.TABLE_NAMES:
            connection.execute(f"CREATE TABLE {table} (fixture INTEGER)")
            connection.execute(
                f"COPY {table} TO ? (FORMAT PARQUET)",
                [str(analytics_dir / f"{table}.parquet")],
            )
        connection.execute("CHECKPOINT")
    finally:
        connection.close()
    manifest = random_search._seal_record(
        {
            "$schema": analytics.MANIFEST_SCHEMA_URI,
            "schema_version": analytics.SCHEMA_VERSION,
            "record_type": analytics.MANIFEST_TYPE,
            "sql_aggregate_verification": "passed",
            "database": {
                "file": analytics.DATABASE_NAME,
                "bytes": database.stat().st_size,
                "sha256": random_search._file_sha256(database),
            },
            "parquet": {
                table: {
                    "file": f"{table}.parquet",
                    "row_count": 0,
                    "bytes": (analytics_dir / f"{table}.parquet").stat().st_size,
                    "sha256": random_search._file_sha256(
                        analytics_dir / f"{table}.parquet"
                    ),
                }
                for table in analytics.TABLE_NAMES
            },
            "table_row_counts": {table: 0 for table in analytics.TABLE_NAMES},
        },
        "manifest_sha256",
    )
    (analytics_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    paths = evidence_api.EvidencePaths(
        root=root,
        analytics=analytics_dir,
        campaign=root / evidence_api.DEFAULT_CAMPAIGN,
        rollouts=root / evidence_api.DEFAULT_ROLLOUTS,
    )
    return evidence_api.EvidenceRepository(paths), database


def test_analytics_source_requires_matching_seal_hash_and_allowlisted_tables(
    tmp_path: Path,
) -> None:
    repository, database = _analytics_fixture(tmp_path)

    manifest = repository._verify_analytics()
    assert manifest["sql_aggregate_verification"] == "passed"

    with database.open("ab") as stream:
        stream.write(b"tamper")
    with pytest.raises(ValueError, match="size does not match"):
        repository._verify_analytics()


def test_rejects_short_tokens_and_paths_outside_artifacts(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least 16"):
        evidence_api.create_app(root=tmp_path, token="short")

    root = tmp_path / "repository"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    paths = evidence_api.EvidencePaths(
        root=root,
        analytics=outside,
        campaign=outside,
        rollouts=outside,
    )
    with pytest.raises(ValueError, match="escapes"):
        evidence_api.EvidenceRepository(paths).open()
