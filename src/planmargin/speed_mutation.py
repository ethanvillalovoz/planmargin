"""Apply and validate one bounded speed multiplier on a recorded WOMD route."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import platform
import resource
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np
import tensorflow as tf
from waymax import agents
from waymax import config as waymax_config
from waymax import dynamics
from waymax import env
from waymax.metrics import overlap
from waymax.metrics import roadgraph

from planmargin import scenario_selection

TIME_INTERVAL_S = 0.1
CURRENT_TIMESTEP = waymax_config.EnvironmentConfig().init_steps - 1
DEFAULT_MANIFEST = Path("artifacts/stage-0/scenario-selection.json")
DEFAULT_OUTPUT = Path("artifacts/stage-0/speed-mutation-smoke-test.json")


@dataclass(frozen=True)
class SpeedMutationConfig:
    """Parameters and acceptance bounds for the first non-ego mutation."""

    speed_multiplier: float = 0.9
    min_speed_multiplier: float = 0.75
    max_speed_multiplier: float = 1.0
    ramp_steps: int = 10
    max_speed_mps: float = 40.0
    max_abs_accel_mps2: float = 12.0
    max_abs_jerk_mps3: float = 100.0
    max_route_deviation_m: float = 0.05
    route_epsilon_m: float = 1e-4


@dataclass(frozen=True)
class MutationResult:
    """Mutation decision, audit metrics, and optional in-memory trajectory."""

    accepted: bool
    rejection_reasons: tuple[str, ...]
    metrics: dict[str, float | bool | int]
    x: np.ndarray | None = None
    y: np.ndarray | None = None
    yaw: np.ndarray | None = None
    vel_x: np.ndarray | None = None
    vel_y: np.ndarray | None = None

    def report(self, config: SpeedMutationConfig) -> dict[str, Any]:
        """Serialize the audit record without trajectory or dataset content."""
        return {
            "schema_version": 1,
            "mutation_type": "route_progress_speed_multiplier",
            "accepted": self.accepted,
            "parameters": dataclasses.asdict(config),
            "rejection_reasons": list(self.rejection_reasons),
            "metrics": self.metrics,
        }


def _rejected(
    *reasons: str,
    metrics: dict[str, float | bool | int] | None = None,
) -> MutationResult:
    return MutationResult(
        accepted=False,
        rejection_reasons=tuple(reasons),
        metrics={} if metrics is None else metrics,
    )


def _smoothstep(value: np.ndarray) -> np.ndarray:
    clipped = np.clip(value, 0.0, 1.0)
    return clipped * clipped * (3.0 - 2.0 * clipped)


def _point_to_polyline_distances(
    points: np.ndarray, polyline: np.ndarray
) -> np.ndarray:
    """Compute each point's distance to the closest polyline segment."""
    segment_starts = polyline[:-1]
    segment_vectors = np.diff(polyline, axis=0)
    squared_lengths = np.sum(segment_vectors * segment_vectors, axis=1)
    usable = squared_lengths > 1e-12
    if not np.any(usable):
        return np.linalg.norm(points - polyline[0], axis=1)
    segment_starts = segment_starts[usable]
    segment_vectors = segment_vectors[usable]
    squared_lengths = squared_lengths[usable]
    relative = points[:, None, :] - segment_starts[None, :, :]
    fraction = np.sum(
        relative * segment_vectors[None, :, :], axis=2
    ) / squared_lengths[None, :]
    fraction = np.clip(fraction, 0.0, 1.0)
    projections = (
        segment_starts[None, :, :]
        + fraction[..., None] * segment_vectors[None, :, :]
    )
    return np.min(
        np.linalg.norm(points[:, None, :] - projections, axis=2), axis=1
    )


def _interpolate_route(
    progress: np.ndarray,
    route_progress: np.ndarray,
    values: np.ndarray,
    epsilon: float,
) -> np.ndarray:
    """Interpolate values over route progress while tolerating stopped points."""
    keep = np.concatenate(
        ([True], np.diff(route_progress) > epsilon)
    )
    unique_progress = route_progress[keep]
    unique_values = values[keep]
    if len(unique_progress) < 2:
        raise ValueError("route_too_short")
    if values.ndim == 1:
        return np.interp(progress, unique_progress, unique_values)
    return np.column_stack(
        [
            np.interp(progress, unique_progress, unique_values[:, dimension])
            for dimension in range(values.shape[1])
        ]
    )


def mutate_route_speed(
    *,
    x: np.ndarray,
    y: np.ndarray,
    yaw: np.ndarray,
    vel_x: np.ndarray,
    vel_y: np.ndarray,
    valid: np.ndarray,
    current_timestep: int,
    config: SpeedMutationConfig,
) -> MutationResult:
    """Resample future progress along a recorded route by a smooth multiplier."""
    arrays = tuple(
        np.asarray(value)
        for value in (x, y, yaw, vel_x, vel_y, valid)
    )
    if any(value.ndim != 1 for value in arrays):
        return _rejected("trajectory_must_be_one_dimensional")
    lengths = {len(value) for value in arrays}
    if len(lengths) != 1:
        return _rejected("trajectory_field_lengths_differ")
    num_steps = lengths.pop()
    if current_timestep < 1 or current_timestep >= num_steps - 1:
        return _rejected("current_timestep_out_of_range")
    if not (
        config.min_speed_multiplier
        <= config.speed_multiplier
        <= config.max_speed_multiplier
    ):
        return _rejected("speed_multiplier_out_of_bounds")
    if config.ramp_steps < 1:
        return _rejected("ramp_steps_must_be_positive")
    if min(
        config.max_speed_mps,
        config.max_abs_accel_mps2,
        config.max_abs_jerk_mps3,
    ) <= 0.0:
        return _rejected("kinematic_bounds_must_be_positive")

    valid_bool = arrays[-1].astype(bool)
    if not valid_bool[current_timestep]:
        return _rejected("current_state_invalid")
    if not valid_bool[current_timestep:].all():
        return _rejected("future_route_not_contiguous")

    original_xy = np.column_stack((arrays[0], arrays[1])).astype(np.float64)
    route_xy = original_xy[current_timestep:]
    route_yaw = np.unwrap(arrays[2][current_timestep:].astype(np.float64))
    if not np.isfinite(route_xy).all() or not np.isfinite(route_yaw).all():
        return _rejected("future_route_not_finite")

    segment_lengths = np.linalg.norm(np.diff(route_xy, axis=0), axis=1)
    route_progress = np.concatenate(([0.0], np.cumsum(segment_lengths)))
    if route_progress[-1] <= config.route_epsilon_m:
        return _rejected("route_too_short")

    interval_numbers = np.arange(1, len(route_xy), dtype=np.float64)
    ramp_fraction = _smoothstep(interval_numbers / config.ramp_steps)
    interval_multipliers = 1.0 + (
        config.speed_multiplier - 1.0
    ) * ramp_fraction
    mutated_progress = np.concatenate(
        ([0.0], np.cumsum(segment_lengths * interval_multipliers))
    )
    if mutated_progress[-1] > route_progress[-1] + config.route_epsilon_m:
        return _rejected("mutated_progress_exceeds_recorded_route")

    output_x = arrays[0].astype(np.float64, copy=True)
    output_y = arrays[1].astype(np.float64, copy=True)
    output_yaw = arrays[2].astype(np.float64, copy=True)
    output_vel_x = arrays[3].astype(np.float64, copy=True)
    output_vel_y = arrays[4].astype(np.float64, copy=True)
    if config.speed_multiplier == 1.0:
        mutated_xy = route_xy.copy()
    else:
        try:
            mutated_xy = _interpolate_route(
                mutated_progress,
                route_progress,
                route_xy,
                config.route_epsilon_m,
            )
            mutated_yaw = _interpolate_route(
                mutated_progress,
                route_progress,
                route_yaw,
                config.route_epsilon_m,
            )
        except ValueError as error:
            return _rejected(str(error))

        output_x[current_timestep:] = mutated_xy[:, 0]
        output_y[current_timestep:] = mutated_xy[:, 1]
        output_yaw[current_timestep:] = mutated_yaw

        future_displacements = np.diff(mutated_xy, axis=0)
        future_velocity = future_displacements / TIME_INTERVAL_S
        output_vel_x[current_timestep + 1 :] = future_velocity[:, 0]
        output_vel_y[current_timestep + 1 :] = future_velocity[:, 1]
        moving = np.linalg.norm(future_displacements, axis=1) > 1e-6
        tangent_yaw = np.arctan2(
            future_displacements[:, 1], future_displacements[:, 0]
        )
        output_yaw[current_timestep + 1 :] = np.where(
            moving, tangent_yaw, mutated_yaw[1:]
        )

    history_unchanged = bool(
        np.array_equal(output_x[: current_timestep + 1], arrays[0][: current_timestep + 1])
        and np.array_equal(output_y[: current_timestep + 1], arrays[1][: current_timestep + 1])
        and np.array_equal(output_yaw[: current_timestep + 1], arrays[2][: current_timestep + 1])
        and np.array_equal(output_vel_x[: current_timestep + 1], arrays[3][: current_timestep + 1])
        and np.array_equal(output_vel_y[: current_timestep + 1], arrays[4][: current_timestep + 1])
    )
    mutated_velocity = np.column_stack(
        (
            output_vel_x[current_timestep:],
            output_vel_y[current_timestep:],
        )
    )
    boundary_velocity = np.column_stack(
        (
            output_vel_x[current_timestep - 1 :],
            output_vel_y[current_timestep - 1 :],
        )
    )
    acceleration = np.diff(boundary_velocity, axis=0) / TIME_INTERVAL_S
    jerk = np.diff(acceleration, axis=0) / TIME_INTERVAL_S
    mutated_speed = np.linalg.norm(mutated_velocity, axis=1)
    max_speed_mps = float(np.max(mutated_speed))
    max_abs_accel_mps2 = float(
        np.max(np.linalg.norm(acceleration, axis=1))
    )
    max_abs_jerk_mps3 = (
        float(np.max(np.linalg.norm(jerk, axis=1))) if len(jerk) else 0.0
    )
    route_deviation = _point_to_polyline_distances(mutated_xy, route_xy)
    max_route_deviation_m = float(np.max(route_deviation))
    first_future_displacement_m = float(
        np.linalg.norm(mutated_xy[1] - mutated_xy[0])
    )

    metrics: dict[str, float | bool | int] = {
        "history_unchanged": history_unchanged,
        "current_timestep": current_timestep,
        "mutated_future_steps": len(mutated_xy) - 1,
        "first_future_displacement_m": round(
            first_future_displacement_m, 6
        ),
        "max_speed_mps": round(max_speed_mps, 6),
        "max_abs_accel_mps2": round(max_abs_accel_mps2, 6),
        "max_abs_jerk_mps3": round(max_abs_jerk_mps3, 6),
        "max_route_deviation_m": round(max_route_deviation_m, 6),
        "recorded_route_length_m": round(float(route_progress[-1]), 6),
        "mutated_route_progress_m": round(float(mutated_progress[-1]), 6),
    }
    reasons: list[str] = []
    if not history_unchanged:
        reasons.append("history_changed")
    if max_speed_mps > config.max_speed_mps:
        reasons.append("speed_bound_exceeded")
    if max_abs_accel_mps2 > config.max_abs_accel_mps2:
        reasons.append("acceleration_bound_exceeded")
    if max_abs_jerk_mps3 > config.max_abs_jerk_mps3:
        reasons.append("jerk_bound_exceeded")
    if max_route_deviation_m > config.max_route_deviation_m:
        reasons.append("route_deviation_exceeded")
    if reasons:
        return _rejected(*reasons, metrics=metrics)

    return MutationResult(
        accepted=True,
        rejection_reasons=(),
        metrics=metrics,
        x=output_x.astype(arrays[0].dtype),
        y=output_y.astype(arrays[1].dtype),
        yaw=output_yaw.astype(arrays[2].dtype),
        vel_x=output_vel_x.astype(arrays[3].dtype),
        vel_y=output_vel_y.astype(arrays[4].dtype),
    )


def apply_speed_mutation(
    scenario: Any,
    object_index: int,
    config: SpeedMutationConfig,
) -> tuple[Any | None, MutationResult]:
    """Apply a route-speed mutation to one object's Waymax log trajectory."""
    trajectory = scenario.log_trajectory
    if object_index < 0 or object_index >= trajectory.num_objects:
        return None, _rejected("object_index_out_of_range")
    result = mutate_route_speed(
        x=np.asarray(trajectory.x)[object_index],
        y=np.asarray(trajectory.y)[object_index],
        yaw=np.asarray(trajectory.yaw)[object_index],
        vel_x=np.asarray(trajectory.vel_x)[object_index],
        vel_y=np.asarray(trajectory.vel_y)[object_index],
        valid=np.asarray(trajectory.valid)[object_index],
        current_timestep=CURRENT_TIMESTEP,
        config=config,
    )
    if not result.accepted:
        return None, result
    assert result.x is not None
    assert result.y is not None
    assert result.yaw is not None
    assert result.vel_x is not None
    assert result.vel_y is not None

    def replace_object(field: str, values: np.ndarray) -> jax.Array:
        source = getattr(trajectory, field)
        return source.at[object_index].set(jnp.asarray(values, dtype=source.dtype))

    mutated_trajectory = trajectory.replace(
        x=replace_object("x", result.x),
        y=replace_object("y", result.y),
        yaw=replace_object("yaw", result.yaw),
        vel_x=replace_object("vel_x", result.vel_x),
        vel_y=replace_object("vel_y", result.vel_y),
    )
    return scenario.replace(log_trajectory=mutated_trajectory), result


def _load_selected_scenario(
    manifest_path: Path, selection_order: int
) -> tuple[Any, dict[str, Any]]:
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Local selection manifest not found: {manifest_path}. "
            "Run planmargin-select-scenarios first."
        )
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    matches = [
        candidate
        for candidate in report["candidates"]
        if candidate["selection_order"] == selection_order
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one candidate at selection order {selection_order}."
        )
    candidate = matches[0]
    uri = scenario_selection._training_shard_uri(candidate["shard_index"])
    dataset = tf.data.TFRecordDataset([uri], buffer_size=8 * 1024 * 1024)
    for record_index, serialized in enumerate(dataset):
        if record_index != candidate["record_index"]:
            continue
        record = serialized.numpy()
        scenario = scenario_selection._waymax_scenario(record)
        scenario_id = scenario_selection._scenario_arrays(record).scenario_id
        if scenario_id != candidate["scenario_id"]:
            raise RuntimeError("Manifest scenario ID does not match source record.")
        return scenario, candidate
    raise RuntimeError("Manifest record index was not found in its source shard.")


def _update_hash(digest: Any, state: Any) -> None:
    for leaf in jax.tree_util.tree_leaves(state.sim_trajectory):
        array = np.ascontiguousarray(np.asarray(leaf))
        digest.update(str(array.dtype).encode())
        digest.update(str(array.shape).encode())
        digest.update(array.tobytes())


class MutationValidator:
    """Run the mutated scenario and audit initial, map, and replay gates."""

    def __init__(
        self, *, require_mutated_object_valid_all_steps: bool = True
    ) -> None:
        self._require_mutated_object_valid_all_steps = (
            require_mutated_object_valid_all_steps
        )
        dynamics_model = dynamics.StateDynamics()
        self._environment = env.BaseEnvironment(
            dynamics_model=dynamics_model,
            config=dataclasses.replace(
                waymax_config.EnvironmentConfig(),
                max_num_objects=scenario_selection.NUM_OBJECTS,
                controlled_object=waymax_config.ObjectType.SDC,
                compute_reward=False,
            ),
        )
        self._actor = agents.IDMRoutePolicy(
            is_controlled_func=lambda state: state.object_metadata.is_sdc
        )
        self._step = jax.jit(self._environment.step)
        self._select_action = jax.jit(self._actor.select_action)
        self._overlap = jax.jit(overlap.OverlapMetric().compute)
        self._offroad = jax.jit(roadgraph.OffroadMetric().compute)

    def _run_once(self, scenario: Any, mutated_object_index: int) -> dict[str, Any]:
        sdc_indices = np.flatnonzero(
            np.asarray(scenario.object_metadata.is_sdc, dtype=bool)
        )
        if sdc_indices.size != 1:
            raise ValueError(f"Expected one SDC, found {sdc_indices.size}.")
        sdc_index = int(sdc_indices[0])
        state = self._environment.reset(scenario)
        rng = jax.random.PRNGKey(scenario_selection.SEED)
        digest = hashlib.sha256()
        _update_hash(digest, state)
        max_sdc_overlap = 0.0
        max_sdc_offroad = 0.0
        max_mutated_object_offroad = 0.0
        mutated_object_valid_all_steps = True
        initial_sdc_overlap = 0.0
        initial_mutated_object_overlap = 0.0

        for step_index in range(scenario_selection.NUM_TRAJECTORY_STEPS):
            overlap_values = np.asarray(self._overlap(state).value)
            offroad_values = np.asarray(self._offroad(state).value)
            if step_index == 0:
                initial_sdc_overlap = float(overlap_values[sdc_index])
                initial_mutated_object_overlap = float(
                    overlap_values[mutated_object_index]
                )
            max_sdc_overlap = max(
                max_sdc_overlap, float(overlap_values[sdc_index])
            )
            max_sdc_offroad = max(
                max_sdc_offroad, float(offroad_values[sdc_index])
            )
            max_mutated_object_offroad = max(
                max_mutated_object_offroad,
                float(offroad_values[mutated_object_index]),
            )
            mutated_object_valid_all_steps = (
                mutated_object_valid_all_steps
                and bool(
                    np.asarray(state.current_sim_trajectory.valid)[
                        mutated_object_index, 0
                    ]
                )
            )
            if step_index == scenario_selection.NUM_FUTURE_STEPS:
                break
            action = self._select_action(None, state, None, rng).action
            state = self._step(state, action)
            _update_hash(digest, state)

        jax.block_until_ready(state.timestep)
        return {
            "trajectory_sha256": digest.hexdigest(),
            "final_timestep": int(state.timestep),
            "initial_sdc_overlap": initial_sdc_overlap,
            "initial_mutated_object_overlap": initial_mutated_object_overlap,
            "max_sdc_overlap": max_sdc_overlap,
            "max_sdc_offroad": max_sdc_offroad,
            "max_mutated_object_offroad": max_mutated_object_offroad,
            "mutated_object_valid_all_steps": mutated_object_valid_all_steps,
        }

    def validate(self, scenario: Any, mutated_object_index: int) -> dict[str, Any]:
        first = self._run_once(scenario, mutated_object_index)
        second = self._run_once(scenario, mutated_object_index)
        outputs_identical = (
            first["trajectory_sha256"] == second["trajectory_sha256"]
        )
        rejection_reasons: list[str] = []
        if first["initial_sdc_overlap"] > 0:
            rejection_reasons.append("initial_sdc_overlap")
        if first["initial_mutated_object_overlap"] > 0:
            rejection_reasons.append("initial_mutated_object_overlap")
        if first["max_mutated_object_offroad"] > 0:
            rejection_reasons.append("mutated_object_offroad")
        if (
            self._require_mutated_object_valid_all_steps
            and not first["mutated_object_valid_all_steps"]
        ):
            rejection_reasons.append("mutated_object_became_invalid")
        expected_final_timestep = (
            CURRENT_TIMESTEP + scenario_selection.NUM_FUTURE_STEPS
        )
        if (
            first["final_timestep"] != expected_final_timestep
            or second["final_timestep"] != expected_final_timestep
        ):
            rejection_reasons.append("rollout_incomplete")
        if not outputs_identical:
            rejection_reasons.append("rollout_not_deterministic")
        return {
            "accepted": not rejection_reasons,
            "rejection_reasons": rejection_reasons,
            "outputs_identical": outputs_identical,
            **first,
        }


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def run(
    manifest_path: Path,
    selection_order: int,
    config: SpeedMutationConfig,
) -> dict[str, Any]:
    """Apply one real mutation and return its private audit report."""
    started = time.perf_counter()
    scenario, candidate = _load_selected_scenario(
        manifest_path, selection_order
    )
    mutated_scenario, mutation = apply_speed_mutation(
        scenario, candidate["interacting_object_index"], config
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
            "mutated_object_index": candidate["interacting_object_index"],
        },
        "mutation": mutation.report(config),
        "environment": {
            **scenario_selection._git_provenance(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "jax": jax.__version__,
            "tensorflow": tf.__version__,
            "jax_backend": jax.default_backend(),
            "waymax_git_commit": scenario_selection.WAYMAX_GIT_COMMIT,
            "mutation_source_sha256": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
        },
        "limitations": [
            "This is a single feasibility mutation, not a planner comparison.",
            "The speed multiplier follows the recorded spatial route and does not model interactive actor intent.",
            "Acceleration and jerk bounds are Stage 0 data-quality gates, not final behavioral-realism certification.",
            "This per-scenario report belongs only in the ignored local artifacts directory.",
        ],
    }
    if mutated_scenario is None:
        report["total_seconds"] = round(time.perf_counter() - started, 6)
        report["process_peak_rss_bytes"] = _peak_rss_bytes()
        return report

    validation = MutationValidator().validate(
        mutated_scenario, candidate["interacting_object_index"]
    )
    report["validation"] = validation
    report["status"] = (
        "passed"
        if mutation.accepted and validation["accepted"]
        else "rejected"
    )
    report["total_seconds"] = round(time.perf_counter() - started, 6)
    report["process_peak_rss_bytes"] = _peak_rss_bytes()
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--selection-order", type=int, default=2)
    parser.add_argument("--speed-multiplier", type=float, default=0.9)
    parser.add_argument("--ramp-steps", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    config = SpeedMutationConfig(
        speed_multiplier=args.speed_multiplier,
        ramp_steps=args.ramp_steps,
    )
    report = run(args.manifest, args.selection_order, config)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
