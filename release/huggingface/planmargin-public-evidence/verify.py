"""Verify the staged public PlanMargin aggregate evidence package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> None:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    for relative, expected in manifest["files"].items():
        path = ROOT / relative
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        if observed != expected:
            raise SystemExit(f"SHA-256 mismatch: {relative}")
    rows = [
        json.loads(line)
        for line in (ROOT / "data/campaign.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    if len(rows) != 6 or rows[0]["record_type"] != "campaign":
        raise SystemExit("Unexpected aggregate evidence schema")
    if any(
        key in json.dumps(rows)
        for key in ("scenario_id", "source_shard", "record_index")
    ):
        raise SystemExit("Restricted provenance field found")
    print("PlanMargin public evidence verified: 6 aggregate records")


if __name__ == "__main__":
    main()
