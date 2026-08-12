"""Data-free checks for the Beam-to-Parquet-to-DuckDB feature pipeline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb
import jsonschema
import numpy as np
import pytest

from planmargin import beam_features
from planmargin import random_search

REPOSITORY_ROOT = Path(__file__).parents[1]


def _fixture_record(
    scenario_id: str,
    *,
    shard_index: int,
    record_index: int,
    valid: bool = True,
) -> dict[str, Any]:
    states = 61
    time = np.arange(states, dtype=np.float64) * 0.1
    lead_speed = np.maximum(5.0, 10.0 - 0.08 * np.arange(states))
    lead_x = 25.0 + np.cumsum(lead_speed) * 0.1
    lead_valid = np.ones(states, dtype=bool)
    if not valid:
        lead_valid[20] = False
    return {
        "scenario_id": scenario_id,
        "shard_index": shard_index,
        "record_index": record_index,
        "selection_score": 0.75 + record_index * 0.01,
        "sdc_x": (12.0 * time).tolist(),
        "sdc_y": np.zeros(states).tolist(),
        "sdc_yaw": np.zeros(states).tolist(),
        "sdc_vel_x": np.full(states, 12.0).tolist(),
        "sdc_vel_y": np.zeros(states).tolist(),
        "sdc_valid": np.ones(states, dtype=bool).tolist(),
        "lead_x": lead_x.tolist(),
        "lead_y": np.zeros(states).tolist(),
        "lead_vel_x": lead_speed.tolist(),
        "lead_vel_y": np.zeros(states).tolist(),
        "lead_valid": lead_valid.tolist(),
    }


def _fixture_shards() -> dict[int, list[dict[str, Any]]]:
    return {
        3: [
            _fixture_record("private-fixture-scenario-a", shard_index=3, record_index=2)
        ],
        9: [
            _fixture_record(
                "private-fixture-scenario-b", shard_index=9, record_index=4
            ),
            _fixture_record(
                "private-fixture-rejected", shard_index=9, record_index=5, valid=False
            ),
        ],
    }


def test_restartable_fixture_pipeline_reconciles_parquet_and_duckdb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    output_dir = tmp_path / "artifacts/beam-features/fixture"
    partial = beam_features.run(
        output_dir,
        source_mode="fixture",
        support_dir=None,
        fixture_shards=_fixture_shards(),
        max_new_source_shards=1,
    )
    assert partial == {
        "status": "in_progress",
        "completed_source_shards": 1,
        "remaining_source_shards": 1,
        "accepted_event_count": 1,
    }
    assert (output_dir / "source-shards/shard=00003/checkpoint.json").is_file()

    manifest = beam_features.run(
        output_dir,
        source_mode="fixture",
        support_dir=None,
        fixture_shards=_fixture_shards(),
    )
    schema = json.loads(
        (REPOSITORY_ROOT / "schemas/beam-feature-manifest-v1.schema.json").read_text()
    )
    jsonschema.Draft202012Validator(schema).validate(manifest)
    random_search._validate_seal(
        manifest, "manifest_sha256", path=output_dir / "manifest.json"
    )
    assert manifest["source"] == {
        "mode": "fixture",
        "shard_count": 2,
        "checkpoint_seals": manifest["source"]["checkpoint_seals"],
        "records_scanned": 3,
        "accepted_event_count": 2,
        "feature_rejection_counts": {"six_second_window_contains_invalid_state": 1},
    }
    assert len(manifest["parquet"]) == beam_features.PARTITION_COUNT
    assert all(manifest["integrity_gates"].values())

    connection = duckdb.connect(
        str(output_dir / beam_features.DATABASE_NAME), read_only=True
    )
    try:
        assert connection.execute("SELECT count(*) FROM features").fetchone()[0] == 2
        assert connection.execute(
            "SELECT source_shard_index FROM features ORDER BY source_shard_index"
        ).fetchall() == [(3,), (9,)]
        assert "scenario_id" not in {
            row[1]
            for row in connection.execute("PRAGMA table_info('features')").fetchall()
        }
    finally:
        connection.close()
    assert beam_features.audit(output_dir) == manifest
    public = beam_features.public_summary(manifest)
    assert public["pipeline"]["partition_count"] == beam_features.PARTITION_COUNT
    rendered_public = json.dumps(public)
    assert "private-fixture-scenario-a" not in rendered_public
    assert "private-fixture-scenario-b" not in rendered_public
    assert (
        hashlib.sha256(b"private-fixture-scenario-a").hexdigest() not in rendered_public
    )
    assert "checkpoint_seals" not in rendered_public
    assert (
        beam_features.run(
            output_dir,
            source_mode="fixture",
            support_dir=None,
            fixture_shards=_fixture_shards(),
        )
        == manifest
    )


def test_fresh_runs_have_identical_logical_and_parquet_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifests = [
        beam_features.run(
            tmp_path / f"artifacts/beam-features/repeat-{index}",
            source_mode="fixture",
            support_dir=None,
            fixture_shards=_fixture_shards(),
        )
        for index in range(2)
    ]
    assert manifests[0]["logical_fingerprint"] == manifests[1]["logical_fingerprint"]
    assert [item["sha256"] for item in manifests[0]["parquet"]] == [
        item["sha256"] for item in manifests[1]["parquet"]
    ]
    assert manifests[0]["duckdb"]["metrics"] == manifests[1]["duckdb"]["metrics"]


def test_rejects_unsafe_paths_invalid_womd_shards_and_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="artifacts/beam-features"):
        beam_features.run(
            tmp_path / "public/beam",
            source_mode="fixture",
            support_dir=None,
            fixture_shards=_fixture_shards(),
        )
    with pytest.raises(ValueError, match="frozen reference set"):
        beam_features.run(
            tmp_path / "artifacts/beam-features/invalid",
            source_mode="womd-direct",
            support_dir=None,
            womd_shards=(999,),
        )

    output_dir = tmp_path / "artifacts/beam-features/tampered"
    manifest = beam_features.run(
        output_dir,
        source_mode="fixture",
        support_dir=None,
        fixture_shards={3: _fixture_shards()[3]},
    )
    parquet_path = output_dir / manifest["parquet"][0]["path"]
    with parquet_path.open("ab") as handle:
        handle.write(b"tampered")
    with pytest.raises(ValueError, match="Parquet artifact seal"):
        beam_features.audit(output_dir)
