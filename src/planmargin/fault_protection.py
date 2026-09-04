"""Verify a bounded planner-command dropout and conservative fallback policy.

This is an independent research fault model on real WOMD training scenes. It
does not model or claim equivalence to Waymo Driver fault-protection behavior.
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
import jax.numpy as jnp
import numpy as np
from waymax import datatypes

from planmargin import controller_comparison, random_search, scenario_selection
from planmargin import speed_mutation

SCHEMA_VERSION = "1.0.0"
RECORD_TYPE = "planmargin.fault_protection_qualification"
PUBLIC_SCHEMA_URI = (
    "https://raw.githubusercontent.com/ethanvillalovoz/planmargin/main/"
    "schemas/fault-protection-public-v1.schema.json"
)
DEFAULT_MANIFEST = Path("artifacts/stage-0/scenario-selection.json")
DEFAULT_OUTPUT = Path("artifacts/fault-protection/command-dropout-v1/report.json")
DEFAULT_PUBLIC_OUTPUT = Path("experiments/fault-protection-command-dropout-v1.json")
FAULT_ONSET_STEP = 20


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


class FaultControllerRunner(controller_comparison.ControllerRunner):
    """Run a primary controller with either no protection or a fallback."""

    def __init__(
        self,
        *,
        protected: bool,
        fault_onset_step: int,
        recovery_step: int | None = None,
    ) -> None:
        super().__init__(controller_comparison.TESTED_CONTROLLER)
        if recovery_step is not None and recovery_step <= fault_onset_step:
            raise ValueError("Recovery must occur after fault onset")
        self.protected = protected
        self.fault_onset_step = fault_onset_step
        self.recovery_step = recovery_step
        fallback = controller_comparison.REFERENCE_CONTROLLER.build()
        self._fallback_select_action = jax.jit(fallback.select_action)

    def _fault_active(self, step_index: int) -> bool:
        return step_index >= self.fault_onset_step and (
            self.recovery_step is None or step_index < self.recovery_step
        )

    def _fault_action(
        self,
        *,
        primary: datatypes.Action,
        fallback: datatypes.Action,
        sdc_index: int,
        current_pose: jax.Array,
    ) -> datatypes.Action:
        if self.protected:
            return fallback
        data = primary.data.at[sdc_index, :].set(current_pose)
        return datatypes.Action(data=data, valid=primary.valid)

    def _run_once(self, scenario: Any) -> dict[str, Any]:
        sdc_indices = np.flatnonzero(
            np.asarray(scenario.object_metadata.is_sdc, dtype=bool)
        )
        if sdc_indices.size != 1:
            raise ValueError(f"Expected one SDC, found {sdc_indices.size}.")
        sdc_index = int(sdc_indices[0])
        state = self._environment.reset(scenario)
        rng = jax.random.PRNGKey(scenario_selection.SEED)
        trace = self._empty_trace()
        max_sdc_overlap = 0.0
        max_sdc_offroad = 0.0
        sdc_valid_all_steps = True
        first_failure_timestep: int | None = None
        first_failure_reasons: list[str] = []
        fault_activated_timestep: int | None = None
        primary_recovered_timestep: int | None = None

        for step_index in range(scenario_selection.NUM_TRAJECTORY_STEPS):
            overlap_values = np.asarray(self._overlap(state).value)
            offroad_values = np.asarray(self._offroad(state).value)
            current_overlap = float(overlap_values[sdc_index])
            current_offroad = float(offroad_values[sdc_index])
            max_sdc_overlap = max(max_sdc_overlap, current_overlap)
            max_sdc_offroad = max(max_sdc_offroad, current_offroad)
            current_valid = bool(
                np.asarray(state.current_sim_trajectory.valid)[sdc_index, 0]
            )
            sdc_valid_all_steps = sdc_valid_all_steps and current_valid
            reasons: list[str] = []
            if current_overlap > 0.0:
                reasons.append("sdc_overlap")
            if current_offroad > 0.0:
                reasons.append("sdc_offroad")
            if not current_valid:
                reasons.append("sdc_invalid")
            if reasons and first_failure_timestep is None:
                first_failure_timestep = int(state.timestep)
                first_failure_reasons = reasons
            self._append_state(trace, state, sdc_index)
            if step_index == scenario_selection.NUM_FUTURE_STEPS:
                break
            primary = self._select_action(None, state, None, rng).action
            if self._fault_active(step_index):
                fallback = self._fallback_select_action(None, state, None, rng).action
                current = state.current_sim_trajectory
                current_pose = jnp.stack(
                    (
                        current.x[sdc_index, 0],
                        current.y[sdc_index, 0],
                        current.yaw[sdc_index, 0],
                        jnp.asarray(0.0, dtype=current.vel_x.dtype),
                        jnp.asarray(0.0, dtype=current.vel_y.dtype),
                    )
                )
                action = self._fault_action(
                    primary=primary,
                    fallback=fallback,
                    sdc_index=sdc_index,
                    current_pose=current_pose,
                )
                if fault_activated_timestep is None:
                    fault_activated_timestep = int(state.timestep)
            else:
                action = primary
                if (
                    self.recovery_step is not None
                    and step_index >= self.recovery_step
                    and primary_recovered_timestep is None
                ):
                    primary_recovered_timestep = int(state.timestep)
            state = self._step(state, action)

        jax.block_until_ready(state.timestep)
        expected_final_timestep = (
            speed_mutation.CURRENT_TIMESTEP + scenario_selection.NUM_FUTURE_STEPS
        )
        final_timestep = int(state.timestep)
        if final_timestep != expected_final_timestep and first_failure_timestep is None:
            first_failure_timestep = final_timestep
            first_failure_reasons = ["rollout_incomplete"]
        return {
            "trajectory_sha256": controller_comparison._trace_hash(trace),
            "fault_activated_timestep": fault_activated_timestep,
            "primary_recovered_timestep": primary_recovered_timestep,
            "outcome": controller_comparison.evaluate_rollout(
                max_sdc_overlap=max_sdc_overlap,
                max_sdc_offroad=max_sdc_offroad,
                sdc_valid_all_steps=sdc_valid_all_steps,
                final_timestep=final_timestep,
                expected_final_timestep=expected_final_timestep,
                first_failure_timestep=first_failure_timestep,
                first_failure_reasons=first_failure_reasons,
            ),
            "trajectory": trace,
        }


def _qualify_scene(
    scenario: Any,
    *,
    baseline: controller_comparison.ControllerRunner,
    unprotected: FaultControllerRunner,
    protected: FaultControllerRunner,
) -> dict[str, Any]:
    baseline_result = baseline.run_twice(scenario)
    unprotected_result = unprotected.run_twice(scenario)
    protected_result = protected.run_twice(scenario)
    expected_fault_timestep = speed_mutation.CURRENT_TIMESTEP + FAULT_ONSET_STEP

    def post_fault_progress(result: dict[str, Any]) -> float:
        trace = result["trajectory"]
        start = FAULT_ONSET_STEP + 1
        points = np.column_stack((trace["x_m"][start:], trace["y_m"][start:]))
        if len(points) < 2:
            return 0.0
        return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())

    baseline_progress = post_fault_progress(baseline_result)
    unprotected_progress = post_fault_progress(unprotected_result)
    protected_progress = post_fault_progress(protected_result)
    gates = {
        "baseline_success": baseline_result["outcome"]["success"],
        "baseline_deterministic": baseline_result["outputs_identical"],
        "unprotected_fault_manifested": (
            unprotected_result["trajectory_sha256"]
            != baseline_result["trajectory_sha256"]
            and unprotected_progress <= 0.5
        ),
        "unprotected_deterministic": unprotected_result["outputs_identical"],
        "protected_fallback_success": protected_result["outcome"]["success"],
        "protected_progress_recovered": (
            protected_progress > unprotected_progress + 5.0
            and protected_progress >= baseline_progress * 0.5
        ),
        "protected_deterministic": protected_result["outputs_identical"],
        "fault_onset_exact": (
            unprotected_result["fault_activated_timestep"] == expected_fault_timestep
            and protected_result["fault_activated_timestep"] == expected_fault_timestep
        ),
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
            "failure_reasons": unprotected_result["outcome"]["failure_reasons"],
            "first_failure_timestep": unprotected_result["outcome"][
                "first_failure_timestep"
            ],
            "trajectory_sha256": unprotected_result["trajectory_sha256"],
        },
        "protected": {
            "success": protected_result["outcome"]["success"],
            "post_fault_progress_m": round(protected_progress, 6),
            "failure_reasons": protected_result["outcome"]["failure_reasons"],
            "first_failure_timestep": protected_result["outcome"][
                "first_failure_timestep"
            ],
            "trajectory_sha256": protected_result["trajectory_sha256"],
        },
    }


def run(manifest_path: Path, output_path: Path) -> dict[str, Any]:
    """Execute the frozen command-dropout protocol on all selected scenes."""

    if output_path.exists():
        raise FileExistsError(f"Output already exists: {output_path}")
    started = time.perf_counter()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidates = manifest.get("candidates", [])
    if manifest.get("status") != "passed" or len(candidates) != 10:
        raise ValueError("Fault qualification requires the ten passed Stage 0 scenes")
    baseline = controller_comparison.ControllerRunner(
        controller_comparison.TESTED_CONTROLLER
    )
    unprotected = FaultControllerRunner(
        protected=False, fault_onset_step=FAULT_ONSET_STEP
    )
    protected = FaultControllerRunner(
        protected=True, fault_onset_step=FAULT_ONSET_STEP
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
            protected=protected,
        )
        scene_results.append({"selection_order": order, **result})
        print(
            json.dumps(
                {
                    "selection_order": order,
                    "protected_success": result["protected"]["success"],
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
        "all_protected_fallbacks_pass": all(
            item["protected"]["success"] for item in scene_results
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
            "fault": "sustained_primary_command_dropout",
            "fault_onset_step": FAULT_ONSET_STEP,
            "fault_onset_seconds": FAULT_ONSET_STEP / 10.0,
            "unprotected_behavior": "zero_order_hold_at_last_commanded_pose",
            "protected_behavior": "switch_to_conservative_idm_fallback",
            "primary_controller": controller_comparison.TESTED_CONTROLLER.report(),
            "fallback_controller": controller_comparison.REFERENCE_CONTROLLER.report(),
            "physical_rollouts": len(scene_results) * 3 * 2,
            "waymax_steps": (
                len(scene_results)
                * 3
                * 2
                * scenario_selection.NUM_FUTURE_STEPS
            ),
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
            "protected_fallback_success_count": sum(
                item["protected"]["success"] for item in scene_results
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
            "Independent command-dropout and fallback verification on bounded real "
            "WOMD training scenes; not a model of Waymo Driver fault protection, a "
            "remote-assistance system, or a safety claim."
        ),
    }
    report = random_search._seal_record(report, "report_sha256")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    random_search._atomic_write_json(output_path, report)
    return report


def public_report(report: dict[str, Any]) -> dict[str, Any]:
    """Remove per-scene traces and identifiers from a qualified aggregate."""

    public = {
        "$schema": PUBLIC_SCHEMA_URI,
        "schema_version": report["schema_version"],
        "record_type": "planmargin.public_fault_protection_result",
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
