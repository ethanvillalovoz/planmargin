"""Verify a bounded assistance handoff after planner-command loss.

The experiment models a deterministic test signal, not a human operator or a
production remote-assistance system. It verifies the state transitions that a
behavior-test harness must observe: fault, request, fallback, resolution, and
primary recovery.
"""

from __future__ import annotations

import argparse
import json
import platform
import resource
import sys
import time
from pathlib import Path
from typing import Any

import jax
import numpy as np

from planmargin import controller_comparison, fault_protection, random_search
from planmargin import scenario_selection, speed_mutation

SCHEMA_VERSION = "1.0.0"
RECORD_TYPE = "planmargin.assistance_handoff_qualification"
PUBLIC_RECORD_TYPE = "planmargin.public_assistance_handoff_result"
PUBLIC_SCHEMA_URI = (
    "https://raw.githubusercontent.com/ethanvillalovoz/planmargin/main/"
    "schemas/assistance-handoff-public-v1.schema.json"
)
DEFAULT_MANIFEST = fault_protection.DEFAULT_MANIFEST
DEFAULT_OUTPUT = Path("artifacts/assistance-handoff/command-recovery-v1/report.json")
DEFAULT_PUBLIC_OUTPUT = Path("experiments/assistance-handoff-command-recovery-v1.json")
FAULT_ONSET_STEP = 20
ASSISTANCE_RESOLUTION_STEP = 30


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def _post_fault_progress(result: dict[str, Any]) -> float:
    trace = result["trajectory"]
    start = FAULT_ONSET_STEP + 1
    points = np.column_stack((trace["x_m"][start:], trace["y_m"][start:]))
    if len(points) < 2:
        return 0.0
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


def _qualify_scene(
    scenario: Any,
    *,
    baseline: controller_comparison.ControllerRunner,
    unprotected: fault_protection.FaultControllerRunner,
    assisted: fault_protection.FaultControllerRunner,
) -> dict[str, Any]:
    baseline_result = baseline.run_twice(scenario)
    unprotected_result = unprotected.run_twice(scenario)
    assisted_result = assisted.run_twice(scenario)
    expected_fault = speed_mutation.CURRENT_TIMESTEP + FAULT_ONSET_STEP
    expected_recovery = speed_mutation.CURRENT_TIMESTEP + ASSISTANCE_RESOLUTION_STEP
    baseline_progress = _post_fault_progress(baseline_result)
    unprotected_progress = _post_fault_progress(unprotected_result)
    assisted_progress = _post_fault_progress(assisted_result)
    gates = {
        "baseline_success": baseline_result["outcome"]["success"],
        "baseline_deterministic": baseline_result["outputs_identical"],
        "unprotected_fault_manifested": (
            unprotected_result["trajectory_sha256"]
            != baseline_result["trajectory_sha256"]
            and unprotected_progress <= 0.5
        ),
        "unprotected_deterministic": unprotected_result["outputs_identical"],
        "assistance_request_exact": (
            assisted_result["fault_activated_timestep"] == expected_fault
        ),
        "assistance_resolution_exact": (
            assisted_result["primary_recovered_timestep"] == expected_recovery
        ),
        "assisted_handoff_success": assisted_result["outcome"]["success"],
        "assisted_progress_recovered": (
            assisted_progress > unprotected_progress + 5.0
            and assisted_progress >= baseline_progress * 0.5
        ),
        "assisted_deterministic": assisted_result["outputs_identical"],
    }
    return {
        "gates": gates,
        "baseline": {
            "success": baseline_result["outcome"]["success"],
            "post_fault_progress_m": round(baseline_progress, 6),
            "trajectory_sha256": baseline_result["trajectory_sha256"],
        },
        "unprotected": {
            "success": unprotected_result["outcome"]["success"],
            "post_fault_progress_m": round(unprotected_progress, 6),
            "trajectory_sha256": unprotected_result["trajectory_sha256"],
        },
        "assisted": {
            "success": assisted_result["outcome"]["success"],
            "post_fault_progress_m": round(assisted_progress, 6),
            "fault_activated_timestep": assisted_result["fault_activated_timestep"],
            "primary_recovered_timestep": assisted_result[
                "primary_recovered_timestep"
            ],
            "trajectory_sha256": assisted_result["trajectory_sha256"],
        },
    }


def run(manifest_path: Path, output_path: Path) -> dict[str, Any]:
    """Execute the frozen assistance-handoff protocol on selected real scenes."""

    if output_path.exists():
        raise FileExistsError(f"Output already exists: {output_path}")
    started = time.perf_counter()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidates = manifest.get("candidates", [])
    if manifest.get("status") != "passed" or len(candidates) != 10:
        raise ValueError("Assistance qualification requires ten passed Stage 0 scenes")

    baseline = controller_comparison.ControllerRunner(
        controller_comparison.TESTED_CONTROLLER
    )
    unprotected = fault_protection.FaultControllerRunner(
        protected=False, fault_onset_step=FAULT_ONSET_STEP
    )
    assisted = fault_protection.FaultControllerRunner(
        protected=True,
        fault_onset_step=FAULT_ONSET_STEP,
        recovery_step=ASSISTANCE_RESOLUTION_STEP,
    )
    scene_results = []
    for candidate in candidates:
        order = int(candidate["selection_order"])
        scenario, loaded_candidate = speed_mutation._load_selected_scenario(
            manifest_path, order
        )
        if loaded_candidate != candidate:
            raise ValueError("Loaded scene does not match the selection manifest")
        result = _qualify_scene(
            scenario,
            baseline=baseline,
            unprotected=unprotected,
            assisted=assisted,
        )
        scene_results.append({"selection_order": order, **result})
        print(
            json.dumps(
                {
                    "selection_order": order,
                    "assisted_success": result["assisted"]["success"],
                    "all_gates_pass": all(result["gates"].values()),
                }
            ),
            flush=True,
        )

    scene_gate_total = sum(len(item["gates"]) for item in scene_results)
    scene_gate_passes = sum(
        sum(bool(value) for value in item["gates"].values()) for item in scene_results
    )
    summary_gates = {
        "all_baselines_pass": all(item["baseline"]["success"] for item in scene_results),
        "all_unprotected_faults_manifested": all(
            item["gates"]["unprotected_fault_manifested"] for item in scene_results
        ),
        "all_assisted_handoffs_pass": all(
            item["assisted"]["success"] for item in scene_results
        ),
        "all_state_transitions_exact": all(
            item["gates"]["assistance_request_exact"]
            and item["gates"]["assistance_resolution_exact"]
            for item in scene_results
        ),
        "all_scene_gates_pass": scene_gate_passes == scene_gate_total,
        "real_womd_only": True,
        "exactly_ten_scenes": len(scene_results) == 10,
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "record_type": RECORD_TYPE,
        "status": "qualified" if all(summary_gates.values()) else "no_go",
        "protocol": {
            "fault": "temporary_primary_command_dropout",
            "fault_onset_step": FAULT_ONSET_STEP,
            "fault_onset_seconds": FAULT_ONSET_STEP / 10.0,
            "assistance_request": "emitted_at_fault_detection",
            "assistance_resolution_step": ASSISTANCE_RESOLUTION_STEP,
            "assistance_resolution_seconds": ASSISTANCE_RESOLUTION_STEP / 10.0,
            "fallback_behavior": "conservative_idm_until_resolution",
            "recovery_behavior": "resume_primary_after_resolution",
            "physical_rollouts": len(scene_results) * 3 * 2,
            "waymax_steps": len(scene_results)
            * 3
            * 2
            * scenario_selection.NUM_FUTURE_STEPS,
        },
        "dataset": {
            "name": "Waymo Open Motion Dataset",
            "version": manifest["dataset"]["version"],
            "split": manifest["dataset"]["split"],
            "synthetic": False,
            "scenario_count": len(scene_results),
        },
        "summary": {
            "baseline_success_count": sum(
                item["baseline"]["success"] for item in scene_results
            ),
            "unprotected_fault_manifestation_count": sum(
                item["gates"]["unprotected_fault_manifested"]
                for item in scene_results
            ),
            "assisted_handoff_success_count": sum(
                item["assisted"]["success"] for item in scene_results
            ),
            "exact_transition_count": sum(
                item["gates"]["assistance_request_exact"]
                and item["gates"]["assistance_resolution_exact"]
                for item in scene_results
            ),
            "scene_gate_passes": scene_gate_passes,
            "scene_gate_total": scene_gate_total,
        },
        "gates": summary_gates,
        "scenes": scene_results,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "jax": jax.__version__,
            "jax_backend": jax.default_backend(),
            "process_peak_rss_bytes": _peak_rss_bytes(),
            "runtime_seconds": round(time.perf_counter() - started, 6),
        },
        "claim_boundary": (
            "Independent deterministic assistance-handoff test signal on bounded "
            "real WOMD training scenes; not a human-operated remote-assistance "
            "system, Waymo Driver behavior, or a safety claim."
        ),
    }
    report = random_search._seal_record(report, "report_sha256")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    random_search._atomic_write_json(output_path, report)
    return report


def public_report(report: dict[str, Any]) -> dict[str, Any]:
    """Return a schema-versioned aggregate with no scene records."""

    public = {
        "$schema": PUBLIC_SCHEMA_URI,
        "schema_version": report["schema_version"],
        "record_type": PUBLIC_RECORD_TYPE,
        "status": report["status"],
        "protocol": report["protocol"],
        "dataset": report["dataset"],
        "summary": report["summary"],
        "gates": report["gates"],
        "source_report_sha256": report["report_sha256"],
        "claim_boundary": report["claim_boundary"],
        "redistribution": "aggregate_only",
    }
    return random_search._seal_record(public, "report_sha256")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--public-output", type=Path, default=DEFAULT_PUBLIC_OUTPUT)
    args = parser.parse_args()
    report = run(args.manifest, args.output)
    public = public_report(report)
    args.public_output.parent.mkdir(parents=True, exist_ok=True)
    random_search._atomic_write_json(args.public_output, public)
    print(json.dumps({"status": report["status"], "summary": report["summary"]}))


if __name__ == "__main__":
    main()
