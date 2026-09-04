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
    tensorrt_v2 = json.loads((ROOT / "data/tensorrt-qualification-v2.json").read_text())
    cpp_v2 = json.loads((ROOT / "data/tensorrt-cpp-benchmark-v2.json").read_text())
    residual_fp16 = json.loads((ROOT / "data/fp16-residual-candidate.json").read_text())
    shielded_rl = json.loads((ROOT / "data/shielded-rl-controller.json").read_text())
    fault_protection = json.loads(
        (ROOT / "data/fault-protection-command-dropout.json").read_text()
    )
    assistance_handoff = json.loads(
        (ROOT / "data/assistance-handoff-command-recovery.json").read_text()
    )
    test_operations = json.loads((ROOT / "data/test-operations.json").read_text())
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
    if (
        cpp_v2.get("schema_version") != "2.0.0"
        or cpp_v2.get("measured_iterations") != 500
    ):
        raise SystemExit("Unexpected scaled C++ benchmark protocol")
    if (
        residual_fp16.get("status") != "tensorrt_required"
        or residual_fp16.get("tensorrt_measured") is not False
        or not all(residual_fp16.get("gates", {}).values())
    ):
        raise SystemExit("Residual FP16 proxy boundary is incomplete")
    if (
        shielded_rl.get("status") != "synthetic_no_go"
        or shielded_rl.get("real_waymax_campaign_run") is not False
        or shielded_rl.get("gates", {}).get(
            "synthetic_collision_rate_at_most_1_percent"
        )
        is not False
    ):
        raise SystemExit("Shielded-controller no-go boundary is incomplete")
    if (
        fault_protection.get("status") != "qualified"
        or fault_protection.get("summary", {}).get(
            "protected_fallback_success_count"
        )
        != 10
        or not all(fault_protection.get("gates", {}).values())
    ):
        raise SystemExit("Fault-protection qualification is incomplete")
    if (
        assistance_handoff.get("status") != "qualified"
        or assistance_handoff.get("summary", {}).get(
            "assisted_handoff_success_count"
        )
        != 10
        or not all(assistance_handoff.get("gates", {}).values())
    ):
        raise SystemExit("Assistance-handoff qualification is incomplete")
    if (
        test_operations.get("slo_summary")
        != {"status": "healthy", "passing": 7, "total": 7}
        or test_operations.get("campaign", {}).get("real_data_only") is not True
    ):
        raise SystemExit("Test-operations contract is incomplete")
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
            residual_fp16,
            shielded_rl,
            fault_protection,
            assistance_handoff,
            test_operations,
        ),
        sort_keys=True,
    )
    if any(
        key in restricted for key in ("scenario_ids", "source_shard", "record_index")
    ):
        raise SystemExit("Restricted provenance field found")
    print("PlanMargin public evidence verified: 19 aggregate research records")


if __name__ == "__main__":
    main()
