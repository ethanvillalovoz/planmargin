"""Contract tests for the distributable aggregate-only evidence bundle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from planmargin.public_evidence_bundle import build_archive


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "release" / "huggingface" / "planmargin-public-evidence"


def test_public_bundle_hashes_and_scope() -> None:
    manifest = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["distribution_scope"] == "aggregate_only_no_waymo_dataset_files"
    for relative, expected in manifest["files"].items():
        assert hashlib.sha256((BUNDLE / relative).read_bytes()).hexdigest() == expected

    rows = [
        json.loads(line)
        for line in (BUNDLE / "data" / "campaign.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(rows) == 6
    assert sum(row["record_type"] == "method" for row in rows) == 2
    assert sum(row["record_type"] == "hypothesis" for row in rows) == 3
    serialized = json.dumps(rows, sort_keys=True)
    for forbidden in (
        "scenario_id",
        "source_shard",
        "record_index",
        "trajectory",
        "camera",
        "lidar",
        "gaussian",
    ):
        assert forbidden not in serialized

    expected_sources = {
        "trajectory-model.json": ROOT
        / "experiments"
        / "torch-trajectory-model-v1.json",
        "tensorrt-qualification.json": ROOT
        / "experiments"
        / "tensorrt-qualification-v1.json",
        "tensorrt-cpp-benchmark.json": ROOT
        / "experiments"
        / "tensorrt-cpp-benchmark-v1.json",
        "tensorrt-qualification-v2.json": ROOT
        / "experiments"
        / "tensorrt-qualification-v2.json",
        "tensorrt-cpp-benchmark-v2.json": ROOT
        / "experiments"
        / "tensorrt-cpp-benchmark-v2.json",
        "trajectory-model-v2.json": ROOT
        / "experiments"
        / "torch-trajectory-model-v2.json",
        "active-risk-v1.json": ROOT
        / "experiments"
        / "active-risk-qualification-v1.json",
        "active-risk-v2.json": ROOT
        / "experiments"
        / "active-risk-qualification-v2.json",
    }
    for name, source in expected_sources.items():
        public = json.loads((BUNDLE / "data" / name).read_text(encoding="utf-8"))
        canonical = json.loads(source.read_text(encoding="utf-8"))
        assert public == canonical
        assert "scenario_ids" not in json.dumps(public, sort_keys=True)


def test_public_bundle_archive_is_byte_for_byte_deterministic(tmp_path: Path) -> None:
    first = build_archive(BUNDLE, tmp_path / "first.zip")
    second = build_archive(BUNDLE, tmp_path / "second.zip")

    assert first.read_bytes() == second.read_bytes()
