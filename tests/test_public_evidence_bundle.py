"""Contract tests for the distributable aggregate-only evidence bundle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


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
