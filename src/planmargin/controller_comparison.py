"""Compare tested and reference controllers on identical scenario variants."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import platform
import resource
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jax
import numpy as np
import tensorflow as tf
from waymax import agents
from waymax import config as waymax_config
from waymax import dynamics
from waymax import env
from waymax.metrics import overlap
from waymax.metrics import roadgraph

from planmargin import scenario_selection
from planmargin import speed_mutation

DEFAULT_OUTPUT = Path("artifacts/stage-0/controller-comparison.json")
TRAJECTORY_FIELDS = (
    "x",
    "y",
    "z",
    "length",
    "width",
    "height",
    "yaw",
    "vel_x",
    "vel_y",
    "valid",
)
ROADGRAPH_TYPES_FOR_VISUALIZATION = frozenset(
    {1, 2, 3, 6, 7, 8, 9, 10, 11, 12, 13, 15, 16, 17, 18, 19}
)
SCENE_PADDING_M = 12.0


@dataclass(frozen=True)
class ControllerSpec:
    """Auditable parameters for one route-following controller."""

    controller_id: str
    role: str
    desired_vel_mps: float
    min_spacing_m: float
    safe_time_headway_s: float
    max_accel_mps2: float
    comfortable_decel_mps2: float
    delta: float
    max_lookahead: int
    lookahead_from_current_position: bool
    additional_lookahead_points: int
    additional_lookahead_distance_m: float
    invalidate_on_end: bool

    def build(self) -> agents.IDMRoutePolicy:
        """Build the pinned Waymax IDM implementation for this specification."""
        return agents.IDMRoutePolicy(
            is_controlled_func=lambda state: state.object_metadata.is_sdc,
            desired_vel=self.desired_vel_mps,
            min_spacing=self.min_spacing_m,
            safe_time_headway=self.safe_time_headway_s,
            max_accel=self.max_accel_mps2,
            max_decel=self.comfortable_decel_mps2,
            delta=self.delta,
            max_lookahead=self.max_lookahead,
            lookahead_from_current_position=(
                self.lookahead_from_current_position
            ),
            additional_lookahead_points=self.additional_lookahead_points,
            additional_lookahead_distance=(
                self.additional_lookahead_distance_m
            ),
            invalidate_on_end=self.invalidate_on_end,
        )

    def report(self) -> dict[str, Any]:
        """Return a stable, JSON-safe controller record."""
        return {
            "controller_id": self.controller_id,
            "role": self.role,
            "implementation": "Waymax IDMRoutePolicy",
            "parameters": {
                key: value
                for key, value in dataclasses.asdict(self).items()
                if key not in {"controller_id", "role"}
            },
        }


TESTED_CONTROLLER = ControllerSpec(
    controller_id="waymax-idm-default-v1",
    role="tested",
    desired_vel_mps=30.0,
    min_spacing_m=2.0,
    safe_time_headway_s=2.0,
    max_accel_mps2=2.0,
    comfortable_decel_mps2=4.0,
    delta=4.0,
    max_lookahead=10,
    lookahead_from_current_position=True,
    additional_lookahead_points=10,
    additional_lookahead_distance_m=10.0,
    invalidate_on_end=False,
)

REFERENCE_CONTROLLER = ControllerSpec(
    controller_id="planmargin-conservative-idm-v1",
    role="reference",
    desired_vel_mps=20.0,
    min_spacing_m=4.0,
    safe_time_headway_s=3.0,
    max_accel_mps2=1.5,
    comfortable_decel_mps2=2.0,
    delta=4.0,
    max_lookahead=10,
    lookahead_from_current_position=True,
    additional_lookahead_points=20,
    additional_lookahead_distance_m=20.0,
    invalidate_on_end=False,
)


def idm_desired_gap_m(
    spec: ControllerSpec,
    *,
    current_speed_mps: float,
    lead_speed_mps: float,
) -> float:
    """Compute the pinned IDM desired gap for an auditable closing example."""
    closing_term = (
        current_speed_mps * (current_speed_mps - lead_speed_mps)
    ) / (
        2.0
        * math.sqrt(
            spec.max_accel_mps2 * spec.comfortable_decel_mps2
        )
    )
    return spec.min_spacing_m + max(
        0.0,
        current_speed_mps * spec.safe_time_headway_s + closing_term,
    )


def evaluate_rollout(
    *,
    max_sdc_overlap: float,
    max_sdc_offroad: float,
    sdc_valid_all_steps: bool,
    final_timestep: int,
    expected_final_timestep: int,
    first_failure_timestep: int | None = None,
    first_failure_reasons: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluate one policy outcome without coupling it to the other policy."""
    failure_reasons: list[str] = []
    if max_sdc_overlap > 0.0:
        failure_reasons.append("sdc_overlap")
    if max_sdc_offroad > 0.0:
        failure_reasons.append("sdc_offroad")
    if not sdc_valid_all_steps:
        failure_reasons.append("sdc_invalid")
    if final_timestep != expected_final_timestep:
        failure_reasons.append("rollout_incomplete")
    return {
        "success": not failure_reasons,
        "failure_reasons": failure_reasons,
        "max_sdc_overlap": max_sdc_overlap,
        "max_sdc_offroad": max_sdc_offroad,
        "sdc_valid_all_steps": sdc_valid_all_steps,
        "final_timestep": final_timestep,
        "expected_final_timestep": expected_final_timestep,
        "first_failure_timestep": first_failure_timestep,
        "first_failure_reasons": first_failure_reasons or [],
    }


def comparison_finding(
    *,
    tested_original: dict[str, Any],
    tested_mutated: dict[str, Any],
    reference_original: dict[str, Any],
    reference_mutated: dict[str, Any],
) -> dict[str, bool]:
    """Classify controller outcomes while retaining each independent result."""
    tested_original_pass = bool(tested_original["success"])
    tested_mutated_failure = not bool(tested_mutated["success"])
    reference_original_pass = bool(reference_original["success"])
    reference_mutated_success = bool(reference_mutated["success"])
    return {
        "tested_original_pass": tested_original_pass,
        "tested_mutated_failure": tested_mutated_failure,
        "reference_original_pass": reference_original_pass,
        "reference_mutated_success": reference_mutated_success,
        "policy_specific_avoidable_failure": bool(
            tested_original_pass
            and tested_mutated_failure
            and reference_original_pass
            and reference_mutated_success
        ),
    }


def _hash_arrays(arrays: list[np.ndarray]) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.dtype).encode())
        digest.update(str(contiguous.shape).encode())
        digest.update(contiguous.tobytes())
    return digest.hexdigest()


def _non_sdc_log_hash(scenario: Any) -> str:
    non_sdc = ~np.asarray(scenario.object_metadata.is_sdc, dtype=bool)
    trajectory = scenario.log_trajectory
    return _hash_arrays(
        [np.asarray(getattr(trajectory, field))[non_sdc] for field in TRAJECTORY_FIELDS]
    )


def _trace_hash(trace: dict[str, list[Any]]) -> str:
    encoded = json.dumps(
        trace,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def trace_is_complete(
    trace: dict[str, list[Any]], expected_states: int
) -> bool:
    """Return whether every exported trace field has the expected length."""
    return bool(trace) and all(
        len(values) == expected_states for values in trace.values()
    )


def _actor_track(scenario: Any, object_index: int) -> dict[str, list[Any]]:
    trajectory = scenario.log_trajectory
    start = speed_mutation.CURRENT_TIMESTEP
    stop = start + scenario_selection.NUM_FUTURE_STEPS + 1
    indices = np.arange(start, stop)
    return {
        "timestep": indices.astype(int).tolist(),
        "x_m": np.asarray(trajectory.x)[object_index, indices]
        .astype(float)
        .round(6)
        .tolist(),
        "y_m": np.asarray(trajectory.y)[object_index, indices]
        .astype(float)
        .round(6)
        .tolist(),
        "yaw_rad": np.asarray(trajectory.yaw)[object_index, indices]
        .astype(float)
        .round(6)
        .tolist(),
        "length_m": np.asarray(trajectory.length)[object_index, indices]
        .astype(float)
        .round(6)
        .tolist(),
        "width_m": np.asarray(trajectory.width)[object_index, indices]
        .astype(float)
        .round(6)
        .tolist(),
        "valid": np.asarray(trajectory.valid)[object_index, indices]
        .astype(bool)
        .tolist(),
    }


def _actor_dimensions(scenario: Any, object_index: int) -> dict[str, float]:
    trajectory = scenario.log_trajectory
    valid = np.asarray(trajectory.valid)[object_index]

    def median_positive(field: str) -> float:
        values = np.asarray(getattr(trajectory, field))[object_index]
        selected = values[valid & np.isfinite(values) & (values > 0.0)]
        if selected.size == 0:
            raise ValueError(f"No valid {field} for actor {object_index}.")
        return round(float(np.median(selected)), 6)

    return {
        "length_m": median_positive("length"),
        "width_m": median_positive("width"),
    }


def _scene_bounds(
    rollouts: dict[str, dict[str, Any]],
    target_tracks: dict[str, dict[str, list[Any]]],
) -> dict[str, float]:
    xs: list[float] = []
    ys: list[float] = []
    for variant in ("original", "mutated"):
        for role in ("tested", "reference"):
            trace = rollouts[variant][role]["trajectory"]
            xs.extend(
                float(value)
                for value, valid in zip(trace["x_m"], trace["valid"])
                if valid and math.isfinite(value)
            )
            ys.extend(
                float(value)
                for value, valid in zip(trace["y_m"], trace["valid"])
                if valid and math.isfinite(value)
            )
    for track in target_tracks.values():
        xs.extend(
            float(value)
            for value, valid in zip(track["x_m"], track["valid"])
            if valid and math.isfinite(value)
        )
        ys.extend(
            float(value)
            for value, valid in zip(track["y_m"], track["valid"])
            if valid and math.isfinite(value)
        )
    if not xs or not ys:
        raise ValueError("Scene context has no valid actor positions.")
    return {
        "min_x_m": round(min(xs) - SCENE_PADDING_M, 6),
        "max_x_m": round(max(xs) + SCENE_PADDING_M, 6),
        "min_y_m": round(min(ys) - SCENE_PADDING_M, 6),
        "max_y_m": round(max(ys) + SCENE_PADDING_M, 6),
    }


def _roadgraph_features(
    scenario: Any, bounds: dict[str, float]
) -> list[dict[str, Any]]:
    points = scenario.roadgraph_points
    x_values = np.asarray(points.x)
    y_values = np.asarray(points.y)
    ids = np.asarray(points.ids)
    types = np.asarray(points.types)
    valid = np.asarray(points.valid, dtype=bool)
    visible = (
        valid
        & np.isin(types, list(ROADGRAPH_TYPES_FOR_VISUALIZATION))
        & (x_values >= bounds["min_x_m"])
        & (x_values <= bounds["max_x_m"])
        & (y_values >= bounds["min_y_m"])
        & (y_values <= bounds["max_y_m"])
    )
    grouped: dict[tuple[int, int], dict[str, Any]] = {}
    for x_m, y_m, feature_id, feature_type in zip(
        x_values[visible], y_values[visible], ids[visible], types[visible]
    ):
        key = (int(feature_id), int(feature_type))
        feature = grouped.setdefault(
            key,
            {
                "feature_type": int(feature_type),
                "x_m": [],
                "y_m": [],
            },
        )
        feature["x_m"].append(round(float(x_m), 4))
        feature["y_m"].append(round(float(y_m), 4))
    return [
        feature
        for feature in grouped.values()
        if len(feature["x_m"]) >= 2
    ]


def build_scene_context(
    original_scenario: Any,
    mutated_scenario: Any,
    mutated_object_index: int,
    rollouts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build the bounded spatial context needed by record-only visualization."""
    sdc_indices = np.flatnonzero(
        np.asarray(original_scenario.object_metadata.is_sdc, dtype=bool)
    )
    if sdc_indices.size != 1:
        raise ValueError(f"Expected one SDC, found {sdc_indices.size}.")
    sdc_index = int(sdc_indices[0])
    target_tracks = {
        "original": _actor_track(original_scenario, mutated_object_index),
        "counterfactual": _actor_track(
            mutated_scenario, mutated_object_index
        ),
    }
    bounds = _scene_bounds(rollouts, target_tracks)
    object_types = np.asarray(
        original_scenario.object_metadata.object_types
    )
    return {
        "coordinate_frame": "WOMD scenario-local Cartesian coordinates",
        "units": "meters",
        "bounds_m": bounds,
        "roadgraph_features": _roadgraph_features(
            original_scenario, bounds
        ),
        "actors": {
            "sdc": {
                "object_type": int(object_types[sdc_index]),
                **_actor_dimensions(original_scenario, sdc_index),
            },
            "mutation_target": {
                "object_type": int(object_types[mutated_object_index]),
                "original": target_tracks["original"],
                "counterfactual": target_tracks["counterfactual"],
            },
        },
    }


class ControllerRunner:
    """Run one controller twice and export its first deterministic SDC trace."""

    def __init__(self, spec: ControllerSpec) -> None:
        self.spec = spec
        self._environment = env.BaseEnvironment(
            dynamics_model=dynamics.StateDynamics(),
            config=dataclasses.replace(
                waymax_config.EnvironmentConfig(),
                max_num_objects=scenario_selection.NUM_OBJECTS,
                controlled_object=waymax_config.ObjectType.SDC,
                compute_reward=False,
            ),
        )
        self._actor = spec.build()
        self._step = jax.jit(self._environment.step)
        self._select_action = jax.jit(self._actor.select_action)
        self._overlap = jax.jit(overlap.OverlapMetric().compute)
        self._offroad = jax.jit(roadgraph.OffroadMetric().compute)

    @staticmethod
    def _empty_trace() -> dict[str, list[Any]]:
        return {
            "timestep": [],
            "x_m": [],
            "y_m": [],
            "z_m": [],
            "yaw_rad": [],
            "vel_x_mps": [],
            "vel_y_mps": [],
            "speed_mps": [],
            "valid": [],
        }

    @staticmethod
    def _append_state(
        trace: dict[str, list[Any]], state: Any, sdc_index: int
    ) -> None:
        current = state.current_sim_trajectory
        trace["timestep"].append(int(state.timestep))
        trace["x_m"].append(float(np.asarray(current.x)[sdc_index, 0]))
        trace["y_m"].append(float(np.asarray(current.y)[sdc_index, 0]))
        trace["z_m"].append(float(np.asarray(current.z)[sdc_index, 0]))
        trace["yaw_rad"].append(float(np.asarray(current.yaw)[sdc_index, 0]))
        trace["vel_x_mps"].append(
            float(np.asarray(current.vel_x)[sdc_index, 0])
        )
        trace["vel_y_mps"].append(
            float(np.asarray(current.vel_y)[sdc_index, 0])
        )
        trace["speed_mps"].append(
            float(np.asarray(current.speed)[sdc_index, 0])
        )
        trace["valid"].append(
            bool(np.asarray(current.valid)[sdc_index, 0])
        )

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

        for step_index in range(scenario_selection.NUM_TRAJECTORY_STEPS):
            overlap_values = np.asarray(self._overlap(state).value)
            offroad_values = np.asarray(self._offroad(state).value)
            current_overlap = float(overlap_values[sdc_index])
            current_offroad = float(offroad_values[sdc_index])
            max_sdc_overlap = max(
                max_sdc_overlap, current_overlap
            )
            max_sdc_offroad = max(
                max_sdc_offroad, current_offroad
            )
            current_valid = bool(
                np.asarray(state.current_sim_trajectory.valid)[sdc_index, 0]
            )
            sdc_valid_all_steps = sdc_valid_all_steps and current_valid
            step_failure_reasons: list[str] = []
            if current_overlap > 0.0:
                step_failure_reasons.append("sdc_overlap")
            if current_offroad > 0.0:
                step_failure_reasons.append("sdc_offroad")
            if not current_valid:
                step_failure_reasons.append("sdc_invalid")
            if step_failure_reasons and first_failure_timestep is None:
                first_failure_timestep = int(state.timestep)
                first_failure_reasons = step_failure_reasons
            self._append_state(trace, state, sdc_index)
            if step_index == scenario_selection.NUM_FUTURE_STEPS:
                break
            action = self._select_action(None, state, None, rng).action
            state = self._step(state, action)

        jax.block_until_ready(state.timestep)
        expected_final_timestep = (
            speed_mutation.CURRENT_TIMESTEP
            + scenario_selection.NUM_FUTURE_STEPS
        )
        final_timestep = int(state.timestep)
        if (
            final_timestep != expected_final_timestep
            and first_failure_timestep is None
        ):
            first_failure_timestep = final_timestep
            first_failure_reasons = ["rollout_incomplete"]
        return {
            "trajectory_sha256": _trace_hash(trace),
            "outcome": evaluate_rollout(
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

    def run_twice(self, scenario: Any) -> dict[str, Any]:
        """Run twice, retain the first trace, and report exact repeatability."""
        first_started = time.perf_counter()
        first = self._run_once(scenario)
        first_seconds = time.perf_counter() - first_started
        second_started = time.perf_counter()
        second = self._run_once(scenario)
        second_seconds = time.perf_counter() - second_started
        outputs_identical = (
            first["trajectory_sha256"] == second["trajectory_sha256"]
        )
        return {
            "controller": self.spec.report(),
            "outputs_identical": outputs_identical,
            "first_rollout_seconds": round(first_seconds, 6),
            "second_rollout_seconds": round(second_seconds, 6),
            **first,
        }


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def run(
    manifest_path: Path,
    selection_order: int,
    mutation_config: speed_mutation.SpeedMutationConfig,
) -> dict[str, Any]:
    """Compare both controllers on the original and identical mutation."""
    started = time.perf_counter()
    scenario, candidate = speed_mutation._load_selected_scenario(
        manifest_path, selection_order
    )
    object_index = candidate["interacting_object_index"]
    if bool(np.asarray(scenario.object_metadata.is_sdc)[object_index]):
        raise ValueError("The selected mutation target must be non-SDC.")
    mutated_scenario, mutation = speed_mutation.apply_speed_mutation(
        scenario, object_index, mutation_config
    )

    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "rejected",
        "dataset": {
            "name": "Waymo Open Motion Dataset",
            "version": scenario_selection.DATASET_VERSION,
            "split": scenario_selection.SPLIT,
            "scenario_id": candidate["scenario_id"],
            "source_shard": candidate["source_shard"],
            "record_index": candidate["record_index"],
            "selection_order": candidate["selection_order"],
            "mutated_object_index": object_index,
        },
        "mutation": mutation.report(mutation_config),
        "controllers": {
            "tested": TESTED_CONTROLLER.report(),
            "reference": REFERENCE_CONTROLLER.report(),
        },
        "metric_definition": {
            "success_requires": [
                "zero SDC overlap",
                "zero SDC offroad",
                "valid SDC at every step",
                "complete 80-step rollout",
            ],
            "policy_specific_avoidable_failure_requires": [
                "tested policy passes original",
                "tested policy fails mutation",
                "reference policy passes original",
                "reference policy passes identical mutation",
            ],
        },
        "environment": {
            **scenario_selection._git_provenance(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "jax": jax.__version__,
            "tensorflow": tf.__version__,
            "jax_backend": jax.default_backend(),
            "waymax_git_commit": scenario_selection.WAYMAX_GIT_COMMIT,
            "comparison_source_sha256": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
            "seed": scenario_selection.SEED,
        },
        "limitations": [
            "The reference is a conservative technical baseline, not a human-driver, legal, or responsibility model.",
            "Both controllers use Waymax IDMRoutePolicy; the comparison tests configuration-specific behavior, not independent planning algorithms.",
            "A passing reference cannot establish that a maneuver is universally avoidable or safe.",
            "This single feasibility comparison is not a planner-performance evaluation.",
            "This per-scenario report and its trajectories belong only in the ignored local artifacts directory.",
        ],
    }
    if mutated_scenario is None:
        report["total_seconds"] = round(time.perf_counter() - started, 6)
        report["process_peak_rss_bytes"] = _peak_rss_bytes()
        return report

    mutation_validation = speed_mutation.MutationValidator().validate(
        mutated_scenario, object_index
    )

    runners = {
        "tested": ControllerRunner(TESTED_CONTROLLER),
        "reference": ControllerRunner(REFERENCE_CONTROLLER),
    }
    variants = {"original": scenario, "mutated": mutated_scenario}
    rollouts: dict[str, dict[str, Any]] = {}
    identical_inputs: dict[str, bool] = {}
    scenario_unchanged: dict[str, bool] = {}
    for variant_name, variant_scenario in variants.items():
        rollouts[variant_name] = {}
        input_hashes: list[str] = []
        unchanged_values: list[bool] = []
        for role, runner in runners.items():
            before_hash = _non_sdc_log_hash(variant_scenario)
            rollout = runner.run_twice(variant_scenario)
            after_hash = _non_sdc_log_hash(variant_scenario)
            rollout["non_sdc_input_sha256"] = before_hash
            rollout["input_unchanged_after_rollout"] = (
                before_hash == after_hash
            )
            input_hashes.append(before_hash)
            unchanged_values.append(before_hash == after_hash)
            rollouts[variant_name][role] = rollout
        identical_inputs[variant_name] = len(set(input_hashes)) == 1
        scenario_unchanged[variant_name] = all(unchanged_values)

    finding = comparison_finding(
        tested_original=rollouts["original"]["tested"]["outcome"],
        tested_mutated=rollouts["mutated"]["tested"]["outcome"],
        reference_original=rollouts["original"]["reference"]["outcome"],
        reference_mutated=rollouts["mutated"]["reference"]["outcome"],
    )
    mutation_nontrivial = (
        rollouts["original"]["tested"]["non_sdc_input_sha256"]
        != rollouts["mutated"]["tested"]["non_sdc_input_sha256"]
    )
    deterministic = all(
        rollouts[variant][role]["outputs_identical"]
        for variant in variants
        for role in runners
    )
    controller_outputs_distinct = {
        variant: (
            rollouts[variant]["tested"]["trajectory_sha256"]
            != rollouts[variant]["reference"]["trajectory_sha256"]
        )
        for variant in variants
    }
    controllers_respond_to_mutation = {
        role: (
            rollouts["original"][role]["trajectory_sha256"]
            != rollouts["mutated"][role]["trajectory_sha256"]
        )
        for role in runners
    }
    expected_trace_states = scenario_selection.NUM_TRAJECTORY_STEPS
    trajectories_exported = all(
        trace_is_complete(
            rollouts[variant][role]["trajectory"], expected_trace_states
        )
        for variant in variants
        for role in runners
    )
    acceptance = {
        "mutation_core_accepted": mutation.accepted,
        "mutation_scenario_validation_accepted": mutation_validation[
            "accepted"
        ],
        "mutation_nontrivial": mutation_nontrivial,
        "tested_policy_passes_original": finding["tested_original_pass"],
        "reference_policy_passes_original": finding[
            "reference_original_pass"
        ],
        "identical_non_sdc_inputs_by_variant": identical_inputs,
        "input_scenarios_unchanged_by_rollouts": scenario_unchanged,
        "all_rollouts_deterministic": deterministic,
        "controller_outputs_distinct_by_variant": (
            controller_outputs_distinct
        ),
        "controllers_respond_to_mutation": controllers_respond_to_mutation,
        "candidate_and_reference_trajectories_exported": (
            trajectories_exported
        ),
        "outcomes_evaluated_independently": True,
    }
    comparison_ready = bool(
        all(
            (
                acceptance["mutation_core_accepted"],
                acceptance["mutation_scenario_validation_accepted"],
                acceptance["mutation_nontrivial"],
                acceptance["tested_policy_passes_original"],
                acceptance["reference_policy_passes_original"],
                all(identical_inputs.values()),
                all(scenario_unchanged.values()),
                acceptance["all_rollouts_deterministic"],
                all(controller_outputs_distinct.values()),
                all(controllers_respond_to_mutation.values()),
                acceptance[
                    "candidate_and_reference_trajectories_exported"
                ],
            )
        )
    )
    report["acceptance"] = acceptance
    report["mutation_scenario_validation"] = mutation_validation
    report["finding"] = finding
    report["rollouts"] = rollouts
    report["scene_context"] = build_scene_context(
        scenario,
        mutated_scenario,
        object_index,
        rollouts,
    )
    report["status"] = "passed" if comparison_ready else "rejected"
    report["total_seconds"] = round(time.perf_counter() - started, 6)
    report["process_peak_rss_bytes"] = _peak_rss_bytes()
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=speed_mutation.DEFAULT_MANIFEST,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--selection-order", type=int, default=2)
    parser.add_argument("--speed-multiplier", type=float, default=0.9)
    parser.add_argument("--ramp-steps", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run(
        args.manifest,
        args.selection_order,
        speed_mutation.SpeedMutationConfig(
            speed_multiplier=args.speed_multiplier,
            ramp_steps=args.ramp_steps,
        ),
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
