"""Data-free security and response-contract tests for the local evidence API."""

from __future__ import annotations

import hashlib

import json
from pathlib import Path
from typing import Any

import duckdb
import pytest
from fastapi.testclient import TestClient

from planmargin import analytics
from planmargin import evidence_assistant
from planmargin import evidence_api
from planmargin import random_search


def test_engineer_facing_metric_labels_preserve_direction() -> None:
    assert (
        evidence_api.EvidenceRepository._proximity_label(1.0)
        == "contact boundary reached"
    )
    assert (
        evidence_api.EvidenceRepository._proximity_label(0.5)
        == "1.00 m minimum clearance"
    )
    assert (
        evidence_api.EvidenceRepository._proximity_label(0.2)
        == "4.00 m minimum clearance"
    )
    assert evidence_api.EvidenceRepository._change_size_label(0.9) == (
        "small edit · 10% of bounded range"
    )
    assert evidence_api.EvidenceRepository._change_size_label(0.6) == (
        "moderate edit · 40% of bounded range"
    )
    assert evidence_api.EvidenceRepository._change_size_label(0.2) == (
        "large edit · 80% of bounded range"
    )


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


def _seed_gaussian(root: Path) -> bytes:
    directory = root / evidence_api.DEFAULT_GAUSSIAN
    directory.mkdir(parents=True, exist_ok=True)
    field = b"ply\nformat ascii 1.0\nelement vertex 0\nend_header\n"
    field_path = directory / "field.ply"
    field_path.write_bytes(field)
    manifest = random_search._seal_record(
        {
            "record_type": "planmargin.lidar_gaussian_field_manifest",
            "schema_version": "1.0.0",
            "decision": "no_go",
            "representation": "deterministic_lidar_gaussian_field",
            "field_sha256": random_search._file_sha256(field_path),
            "observed": {
                "primitive_count": 75_000,
                "field_bytes": len(field),
                "runtime_seconds": 3.7,
                "trajectory_linkage_fraction": 0.2366,
                "geometric_quality": {
                    "median_nearest_mean_distance_m": 0.105,
                    "p90_nearest_mean_distance_m": 0.172,
                    "coverage_within_0_50_m": 0.9844,
                },
            },
            "gates": {
                "authorized_exact_input": True,
                "determinism": True,
                "geometric_quality": True,
                "local_compute": True,
                "scale": True,
                "trajectory_linkage": False,
            },
            "privacy": {
                "contains_scenario_id": False,
                "contains_source_uri": False,
                "contains_raw_points": False,
                "unrestricted_export": False,
            },
            "claim_boundary": "not_photorealistic_not_learned_not_safety_evidence",
        },
        "manifest_sha256",
    )
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return field


def _seed_sensor_scene(
    root: Path,
) -> tuple[bytes, bytes, bytes, bytes, bytes, bytes, bytes]:
    frame = b"\xff\xd8real-waymo-frame\xff\xd9"
    reconstruction = b"ply\nformat ascii 1.0\nelement vertex 1\nend_header\n"
    reconstruction_reference = (
        b"ply\nformat ascii 1.0\nelement vertex 1\nend_header\nreference"
    )
    reconstruction_context = (
        b"ply\nformat ascii 1.0\nelement vertex 1\nend_header\ncontext"
    )
    lidar = b"ply\nformat ascii 1.0\nelement vertex 2\nend_header\n"
    trajectory = json.dumps(
        {
            "record_type": "planmargin.calibrated_sensor_trajectory",
            "schema_version": "1.0.0",
            "source_frame_index": 0,
            "paths": {"recorded": [], "jax_prediction": [], "constant_velocity": []},
        }
    ).encode()
    annotations = json.dumps(
        {
            "record_type": "planmargin.sensor_frame_annotations",
            "schema_version": "1.0.0",
            "source": "Waymo Open Dataset v2 Perception camera_box",
            "image_width": 1920,
            "image_height": 1280,
            "frames": [
                {
                    "index": 0,
                    "timestamp_micros": 1,
                    "boxes": [
                        {
                            "track_id": "track-1",
                            "category": "vehicle",
                            "center_x": 960.0,
                            "center_y": 640.0,
                            "width": 100.0,
                            "height": 50.0,
                        }
                    ],
                }
            ],
        }
    ).encode()
    frames_directory = root / "data" / "raw" / "perception" / "segment" / "front_frames"
    frames_directory.mkdir(parents=True)
    (frames_directory / "000-1.jpg").write_bytes(frame)
    reconstruction_path = root / "artifacts" / "real-3dgs" / "scene.ply"
    reconstruction_path.parent.mkdir(parents=True)
    reconstruction_path.write_bytes(reconstruction)
    reference_path = root / "artifacts" / "real-3dgs" / "scene-reference.ply"
    reference_path.write_bytes(reconstruction_reference)
    context_path = root / "artifacts" / "real-3dgs" / "scene-context.ply"
    context_path.write_bytes(reconstruction_context)
    sensor_directory = root / evidence_api.DEFAULT_SENSOR_SCENE
    sensor_directory.mkdir(parents=True)
    lidar_path = sensor_directory / "lidar.ply"
    lidar_path.write_bytes(lidar)
    annotations_path = sensor_directory / "front-camera-boxes.json"
    annotations_path.write_bytes(annotations)
    trajectory_path = sensor_directory / "trajectory.json"
    trajectory_path.write_bytes(trajectory)
    (sensor_directory / "manifest.json").write_text(
        json.dumps(
            {
                "record_type": "planmargin.sensor_scene_manifest",
                "schema_version": "1.0.0",
                "source": "Waymo Open Dataset v2 Perception",
                "segment_id": "segment",
                "camera_name": "FRONT",
                "camera_enum": 1,
                "frame_count": 1,
                "frame_rate_hz": 10,
                "frames_directory": "data/raw/perception/segment/front_frames",
                "frames": [
                    {
                        "index": 0,
                        "timestamp_micros": 1,
                        "file": "000-1.jpg",
                        "bytes": len(frame),
                        "sha256": hashlib.sha256(frame).hexdigest(),
                    }
                ],
                "annotations": {
                    "representation": "native_tracked_camera_boxes",
                    "frame_count": 1,
                    "box_count": 1,
                    "file": str(annotations_path.relative_to(root)),
                    "bytes": len(annotations),
                    "sha256": hashlib.sha256(annotations).hexdigest(),
                },
                "reconstruction": {
                    "representation": "apple_sharp_3d_gaussian_splatting",
                    "source_frame_index": 0,
                    "primitive_count": 1,
                    "file": "artifacts/real-3dgs/scene.ply",
                    "bytes": len(reconstruction),
                    "sha256": hashlib.sha256(reconstruction).hexdigest(),
                },
                "reconstruction_reference": {
                    "representation": "apple_sharp_3d_gaussian_splatting",
                    "source_frame_index": 0,
                    "primitive_count": 1,
                    "file": "artifacts/real-3dgs/scene-reference.ply",
                    "bytes": len(reconstruction_reference),
                    "sha256": hashlib.sha256(reconstruction_reference).hexdigest(),
                },
                "reconstruction_context": {
                    "representation": "apple_sharp_3d_gaussian_splatting",
                    "source_frame_index": 0,
                    "primitive_count": 1,
                    "file": "artifacts/real-3dgs/scene-context.ply",
                    "bytes": len(reconstruction_context),
                    "sha256": hashlib.sha256(reconstruction_context).hexdigest(),
                },
                "lidar": {
                    "representation": "same_frame_lidar_gaussian_field",
                    "source_frame_index": 0,
                    "primitive_count": 2,
                    "file": str(lidar_path.relative_to(root)),
                    "bytes": len(lidar),
                    "sha256": hashlib.sha256(lidar).hexdigest(),
                },
                "trajectory": {
                    "representation": "calibrated_recorded_and_jax_predicted_ego_paths",
                    "source_frame_index": 0,
                    "file": str(trajectory_path.relative_to(root)),
                    "bytes": len(trajectory),
                    "sha256": hashlib.sha256(trajectory).hexdigest(),
                    "future_steps": 30,
                    "step_seconds": 0.1,
                    "model_status": "visualization_qualified",
                },
            }
        ),
        encoding="utf-8",
    )
    return (
        frame,
        reconstruction,
        reconstruction_reference,
        reconstruction_context,
        lidar,
        annotations,
        trajectory,
    )


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
                "trajectory_available": False,
                "replay_run_id": None,
            }
        ]
        if cell_id == CELL_ID
        else (_ for _ in ()).throw(KeyError(cell_id)),
    )
    monkeypatch.setattr(
        evidence_api.EvidenceRepository,
        "investigation",
        lambda _: {
            "evidence_mode": "real_local_redacted",
            "integrity": "verified",
            "cell_count": 1,
            "proposal_count": 1,
            "funnel": {
                "proposed": 1,
                "mutation_valid": 0,
                "scenario_valid": 0,
                "pipeline_valid": 0,
                "support_valid": 0,
                "reference_passes": 0,
                "tested_fails": 0,
                "qualifying_findings": 0,
            },
            "closest_margin": [],
            "smallest_mutation": [],
            "highest_support": [],
        },
    )
    monkeypatch.setattr(
        evidence_api.EvidenceRepository,
        "proposal_analysis",
        lambda _, cell_id, proposal_number: {
            "evidence_mode": "real_local_redacted",
            "analysis_mode": "deterministic_proposal_specific",
            "cell_id": cell_id,
            "proposal_number": proposal_number,
            "decision": "not_qualified",
            "decisive_gate": "mutation_geometry",
            "explanation": "The bounded mutation geometry was rejected.",
            "facts": [{"label": "method", "value": "bayesian"}],
            "record_sha256": "a" * 64,
            "trajectory_available": False,
            "replay_run_id": None,
        },
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
        investigation = client.get("/api/v1/investigation", headers=headers)
        proposal_analysis = client.get(
            f"/api/v1/cells/{CELL_ID}/proposals/1/analysis", headers=headers
        )
        runs = client.get("/api/v1/runs", headers=headers)
        run = client.get("/api/v1/runs/run_opaque", headers=headers)
        contract = client.get("/api/v1/openapi.json", headers=headers)

        for response in (
            campaign,
            cells,
            proposals,
            investigation,
            proposal_analysis,
            runs,
            run,
            contract,
        ):
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["x-content-type-options"] == "nosniff"
            serialized = response.text
            assert "private-comparison-key" not in serialized
            assert "private-scene-hash" not in serialized
            assert '"scenario_id":' not in serialized
            assert '"source_shard":' not in serialized
            assert '"record_index":' not in serialized

        assert campaign.json()["api_version"] == "1.1.0"
        assert campaign.json()["held_out_comparison_run"] is False
        assert cells.json()[0]["cell_id"] == CELL_ID
        assert proposals.json()[0]["support_passes"] is None
        assert investigation.json()["proposal_count"] == 1
        assert investigation.json()["funnel"]["qualifying_findings"] == 0
        assert proposal_analysis.json()["trajectory_available"] is False
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


def test_assistant_and_gaussian_workspaces_are_authenticated(
    app_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    field = _seed_gaussian(app_root)

    def open_repository(repository: evidence_api.EvidenceRepository) -> None:
        _seed_repository(repository)

    monkeypatch.setattr(evidence_api.EvidenceRepository, "open", open_repository)
    monkeypatch.setattr(
        evidence_assistant.LocalEvidenceTools,
        "execute",
        lambda _self, query_id: evidence_assistant.PublicEvidenceTools().execute(
            query_id
        ),
    )
    app = evidence_api.create_app(root=app_root, token=TOKEN)

    with TestClient(app) as client:
        headers = {"X-PlanMargin-Token": TOKEN}
        status_response = client.get("/api/v1/assistant/status", headers=headers)
        questions = client.get("/api/v1/assistant/questions", headers=headers)
        answer = client.get("/api/v1/assistant/method_comparison", headers=headers)
        summary = client.get("/api/v1/gaussian-field", headers=headers)
        field_response = client.get("/api/v1/gaussian-field/field.ply", headers=headers)

        assert status_response.json() == {
            "provider_id": "offline_deterministic",
            "model": None,
            "source_mode": "real_local_redacted",
            "gemini_configured": False,
            "explanation_only": True,
        }
        assert len(questions.json()) == 8
        assert answer.status_code == 200
        assert answer.json()["question"]["query_id"] == "method_comparison"
        assert answer.json()["privacy"]["private_data_sent_to_provider"] is False
        assert summary.json()["primitive_count"] == 75_000
        assert summary.json()["gates"]["trajectory_linkage"] is False
        assert field_response.content == field
        assert field_response.headers["cache-control"] == "no-store"
        assert field_response.headers["content-type"].startswith(
            "application/octet-stream"
        )


def test_real_sensor_scene_is_authenticated_and_streamed(
    app_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (
        frame,
        reconstruction,
        reconstruction_reference,
        reconstruction_context,
        lidar,
        annotations,
        trajectory,
    ) = _seed_sensor_scene(app_root)

    def open_repository(repository: evidence_api.EvidenceRepository) -> None:
        _seed_repository(repository)

    monkeypatch.setattr(evidence_api.EvidenceRepository, "open", open_repository)
    app = evidence_api.create_app(root=app_root, token=TOKEN)

    with TestClient(app) as client:
        headers = {"X-PlanMargin-Token": TOKEN}
        summary = client.get("/api/v1/sensor-scene", headers=headers)
        front = client.get("/api/v1/sensor-scene/front/0.jpg", headers=headers)
        boxes = client.get(
            "/api/v1/sensor-scene/front/annotations.json", headers=headers
        )
        sharp = client.get("/api/v1/sensor-scene/reconstruction.ply", headers=headers)
        reference = client.get(
            "/api/v1/sensor-scene/reconstruction_reference.ply", headers=headers
        )
        context = client.get(
            "/api/v1/sensor-scene/reconstruction_context.ply", headers=headers
        )
        point_field = client.get("/api/v1/sensor-scene/lidar.ply", headers=headers)
        path_overlay = client.get(
            "/api/v1/sensor-scene/trajectory.json", headers=headers
        )

        assert summary.status_code == 200
        assert summary.json()["evidence_mode"] == "real_local_sensor"
        assert summary.json()["reconstruction"]["primitive_count"] == 1
        assert summary.json()["reconstruction_context"]["primitive_count"] == 1
        assert summary.json()["trajectory"]["model_status"] == "visualization_qualified"
        assert summary.json()["annotations"]["box_count"] == 1
        assert front.content == frame
        assert boxes.content == annotations
        assert sharp.content == reconstruction
        assert reference.content == reconstruction_reference
        assert context.content == reconstruction_context
        assert point_field.content == lidar
        assert path_overlay.content == trajectory
        assert client.get("/api/v1/sensor-scene").status_code == 401
        assert (
            client.get("/api/v1/sensor-scene/front/99.jpg", headers=headers).status_code
            == 404
        )

        assert client.get("/api/v1/assistant/status").status_code == 401
        assert client.get("/api/v1/gaussian-field").status_code == 401
        assert (
            client.get("/api/v1/assistant/not-allowlisted", headers=headers).status_code
            == 404
        )


def test_gemini_failure_returns_verified_offline_explanation(
    app_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailingGeminiProvider:
        provider_id = "gemini_public_aggregate"
        _model = evidence_assistant.DEFAULT_MODEL

        def explain(self, _: evidence_assistant.ToolResult) -> None:
            raise RuntimeError("hosted provider unavailable")

    monkeypatch.setattr(
        evidence_api.EvidenceRepository,
        "open",
        lambda repository: _seed_repository(repository),
    )
    monkeypatch.setattr(
        evidence_assistant,
        "GeminiProvider",
        lambda **_: FailingGeminiProvider(),
    )
    app = evidence_api.create_app(
        root=app_root,
        token=TOKEN,
        assistant_provider="gemini",
        confirm_gemini_free_tier=True,
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/assistant/campaign_overview",
            headers={"X-PlanMargin-Token": TOKEN},
        )

    assert response.status_code == 200
    assert response.json()["provider"] == {
        "id": "offline_deterministic",
        "model": None,
        "role": "explanation_only",
    }
    assert response.json()["privacy"]["provider_input_scope"] == "none"


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
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert "POST" in allowed.headers["access-control-allow-methods"]
    assert forbidden.status_code == 400
    assert "access-control-allow-origin" not in forbidden.headers


def test_browser_session_cookie_authenticates_fresh_requests_and_logout(
    app_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        evidence_api.EvidenceRepository,
        "open",
        lambda repository: _seed_repository(repository),
    )
    app = evidence_api.create_app(root=app_root, token=TOKEN)

    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 401

        session = client.post("/api/v1/session", headers={"X-PlanMargin-Token": TOKEN})
        assert session.status_code == 204
        cookie = session.headers["set-cookie"]
        assert f"{evidence_api.SESSION_COOKIE_NAME}=" in cookie
        assert "HttpOnly" in cookie
        assert "SameSite=strict" in cookie
        assert "Path=/api/v1" in cookie
        assert client.get("/api/v1/health").status_code == 200

        logout = client.post("/api/v1/session/logout")
        assert logout.status_code == 204
        assert client.get("/api/v1/health").status_code == 401

        rejected = client.post(
            "/api/v1/session", headers={"X-PlanMargin-Token": "incorrect"}
        )
        assert rejected.status_code == 401


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
