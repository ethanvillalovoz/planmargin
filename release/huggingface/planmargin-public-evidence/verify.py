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
    trajectory = json.loads((ROOT / "data/trajectory-model.json").read_text())
    trajectory_v2 = json.loads((ROOT / "data/trajectory-model-v2.json").read_text())
    active_risk = [
        json.loads((ROOT / f"data/active-risk-v{version}.json").read_text())
        for version in (1, 2)
    ]
    tensorrt = json.loads((ROOT / "data/tensorrt-qualification.json").read_text())
    cpp = json.loads((ROOT / "data/tensorrt-cpp-benchmark.json").read_text())
    tensorrt_v2 = json.loads(
        (ROOT / "data/tensorrt-qualification-v2.json").read_text()
    )
    cpp_v2 = json.loads((ROOT / "data/tensorrt-cpp-benchmark-v2.json").read_text())
    if trajectory.get("synthetic") is not False:
        raise SystemExit("Trajectory result must identify real training data")
    if (
        trajectory_v2.get("synthetic") is not False
        or trajectory_v2.get("scenario_count") != 1024
        or not all(trajectory_v2.get("gates", {}).values())
    ):
        raise SystemExit("Scaled trajectory result is incomplete")
    if any(
        result.get("status") != "qualification_no_go"
        or result.get("model_sha256") is not None
        for result in active_risk
    ):
        raise SystemExit("Active-risk no-go boundary is incomplete")
    if tensorrt.get("status") != "qualified" or not all(
        tensorrt.get("gates", {}).values()
    ):
        raise SystemExit("TensorRT qualification is incomplete")
    if cpp.get("measured_iterations") != 500:
        raise SystemExit("Unexpected C++ benchmark protocol")
    if (
        tensorrt_v2.get("status") != "no_go"
        or tensorrt_v2.get("gates", {}).get("fp16_max_error_under_7_5e_2_m")
        is not False
        or not all(
            passed
            for name, passed in tensorrt_v2.get("gates", {}).items()
            if name != "fp16_max_error_under_7_5e_2_m"
        )
    ):
        raise SystemExit("Scaled TensorRT no-go boundary is incomplete")
    if cpp_v2.get("schema_version") != "2.0.0" or cpp_v2.get(
        "measured_iterations"
    ) != 500:
        raise SystemExit("Unexpected scaled C++ benchmark protocol")
    restricted = json.dumps(
        (
            rows,
            trajectory,
            trajectory_v2,
            active_risk,
            tensorrt,
            cpp,
            tensorrt_v2,
            cpp_v2,
        ),
        sort_keys=True,
    )
    if any(
        key in restricted for key in ("scenario_ids", "source_shard", "record_index")
    ):
        raise SystemExit("Restricted provenance field found")
    print("PlanMargin public evidence verified: 14 aggregate research records")


if __name__ == "__main__":
    main()
