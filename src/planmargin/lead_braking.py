"""Construct bounded two-dimensional lead-vehicle braking mutations."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np

from planmargin import speed_mutation

TIME_INTERVAL_S = speed_mutation.TIME_INTERVAL_S
CURRENT_TIMESTEP = speed_mutation.CURRENT_TIMESTEP


@dataclass(frozen=True)
class LeadBrakingMutationConfig:
    """Search parameters and fixed validity bounds for lead braking."""

    braking_onset_offset_s: float = 0.0
    speed_multiplier: float = 0.8
    min_braking_onset_offset_s: float = 0.0
    max_braking_onset_offset_s: float = 0.5
    min_speed_multiplier: float = 0.75
    max_speed_multiplier: float = 1.0
    multiplier_ramp_steps: int = 20
    onset_window_steps: int = 10
    min_onset_speed_drop_mps: float = 1.0
    min_onset_step_drop_mps: float = 0.05
    max_onset_step_increase_mps: float = 0.2
    min_onset_nonincrease_fraction: float = 0.8
    max_speed_mps: float = 40.0
    max_abs_accel_mps2: float = 12.0
    max_abs_jerk_mps3: float = 100.0
    max_route_deviation_m: float = 0.05
    route_epsilon_m: float = 1e-4


@dataclass(frozen=True)
class LeadBrakingMutationResult:
    """Mutation decision, audit metrics, and optional trajectory fields."""

    accepted: bool
    rejection_reasons: tuple[str, ...]
    metrics: dict[str, float | bool | int]
    x: np.ndarray | None = None
    y: np.ndarray | None = None
    yaw: np.ndarray | None = None
    vel_x: np.ndarray | None = None
    vel_y: np.ndarray | None = None

    def report(self, config: LeadBrakingMutationConfig) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "mutation_type": "lead_braking_onset_and_speed",
            "accepted": self.accepted,
            "parameters": dataclasses.asdict(config),
            "rejection_reasons": list(self.rejection_reasons),
            "metrics": self.metrics,
        }


def _rejected(
    *reasons: str,
    metrics: dict[str, float | bool | int] | None = None,
) -> LeadBrakingMutationResult:
    return LeadBrakingMutationResult(
        accepted=False,
        rejection_reasons=tuple(reasons),
        metrics={} if metrics is None else metrics,
    )


def _onset_offset_steps(
    config: LeadBrakingMutationConfig,
) -> int | None:
    raw_steps = config.braking_onset_offset_s / TIME_INTERVAL_S
    rounded_steps = round(raw_steps)
    if not np.isclose(raw_steps, rounded_steps, atol=1e-9):
        return None
    return int(rounded_steps)


def detect_recorded_braking_onset(
    interval_speeds_mps: np.ndarray,
    config: LeadBrakingMutationConfig,
) -> int | None:
    """Return the first sustained one-window speed-drop onset."""
    speeds = np.asarray(interval_speeds_mps, dtype=np.float64)
    window = config.onset_window_steps
    if speeds.ndim != 1 or window < 1 or len(speeds) <= window:
        return None
    for start in range(len(speeds) - window):
        sample = speeds[start : start + window + 1]
        drop = float(sample[0] - sample[-1])
        nonincrease_fraction = float(
            np.mean(np.diff(sample) <= config.max_onset_step_increase_mps)
        )
        if (
            drop >= config.min_onset_speed_drop_mps
            and nonincrease_fraction
            >= config.min_onset_nonincrease_fraction
        ):
            decline_indices = np.flatnonzero(
                np.diff(sample) <= -config.min_onset_step_drop_mps
            )
            if decline_indices.size:
                return start + int(decline_indices[0])
    return None


def _shift_braking_profile(
    recorded_speeds: np.ndarray,
    *,
    recorded_onset: int,
    shifted_onset: int,
) -> np.ndarray:
    output = np.empty_like(recorded_speeds, dtype=np.float64)
    onset_speed = float(recorded_speeds[recorded_onset])
    for index in range(len(output)):
        if index < shifted_onset:
            output[index] = (
                recorded_speeds[index]
                if index < recorded_onset
                else onset_speed
            )
            continue
        source_index = recorded_onset + index - shifted_onset
        output[index] = recorded_speeds[
            min(source_index, len(recorded_speeds) - 1)
        ]
    return output


def mutate_lead_braking(
    *,
    x: np.ndarray,
    y: np.ndarray,
    yaw: np.ndarray,
    vel_x: np.ndarray,
    vel_y: np.ndarray,
    valid: np.ndarray,
    current_timestep: int,
    config: LeadBrakingMutationConfig,
) -> LeadBrakingMutationResult:
    """Shift recorded braking onset and rescale post-onset route progress."""
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
        config.min_braking_onset_offset_s
        <= config.braking_onset_offset_s
        <= config.max_braking_onset_offset_s
    ):
        return _rejected("braking_onset_offset_out_of_bounds")
    offset_steps = _onset_offset_steps(config)
    if offset_steps is None:
        return _rejected("braking_onset_offset_not_timestep_aligned")
    if not (
        config.min_speed_multiplier
        <= config.speed_multiplier
        <= config.max_speed_multiplier
    ):
        return _rejected("speed_multiplier_out_of_bounds")
    if config.multiplier_ramp_steps < 1:
        return _rejected("multiplier_ramp_steps_must_be_positive")
    if config.onset_window_steps < 1:
        return _rejected("onset_window_steps_must_be_positive")
    if min(
        config.max_speed_mps,
        config.max_abs_accel_mps2,
        config.max_abs_jerk_mps3,
    ) <= 0.0:
        return _rejected("kinematic_bounds_must_be_positive")

    valid_bool = arrays[-1].astype(bool)
    if not valid_bool[current_timestep]:
        return _rejected("current_state_invalid")
    invalid_future_indices = np.flatnonzero(~valid_bool[current_timestep:])
    valid_future_states = (
        int(invalid_future_indices[0])
        if invalid_future_indices.size
        else num_steps - current_timestep
    )
    if valid_future_states < config.onset_window_steps + 2:
        return _rejected("future_route_too_short")
    route_stop = current_timestep + valid_future_states

    original_xy = np.column_stack((arrays[0], arrays[1])).astype(np.float64)
    route_xy = original_xy[current_timestep:route_stop]
    route_yaw = np.unwrap(
        arrays[2][current_timestep:route_stop].astype(np.float64)
    )
    if not np.isfinite(route_xy).all() or not np.isfinite(route_yaw).all():
        return _rejected("future_route_not_finite")
    segment_lengths = np.linalg.norm(np.diff(route_xy, axis=0), axis=1)
    route_progress = np.concatenate(([0.0], np.cumsum(segment_lengths)))
    if route_progress[-1] <= config.route_epsilon_m:
        return _rejected("route_too_short")
    interval_speeds = segment_lengths / TIME_INTERVAL_S
    recorded_onset = detect_recorded_braking_onset(interval_speeds, config)
    if recorded_onset is None:
        return _rejected("recorded_braking_onset_not_found")
    shifted_onset = recorded_onset + offset_steps
    if shifted_onset < 0 or shifted_onset >= len(interval_speeds):
        return _rejected("shifted_braking_onset_out_of_horizon")

    output_x = arrays[0].astype(np.float64, copy=True)
    output_y = arrays[1].astype(np.float64, copy=True)
    output_yaw = arrays[2].astype(np.float64, copy=True)
    output_vel_x = arrays[3].astype(np.float64, copy=True)
    output_vel_y = arrays[4].astype(np.float64, copy=True)
    is_identity = (
        offset_steps == 0 and config.speed_multiplier == 1.0
    )
    if is_identity:
        mutated_xy = route_xy.copy()
        mutated_progress = route_progress.copy()
    else:
        shifted_speeds = _shift_braking_profile(
            interval_speeds,
            recorded_onset=recorded_onset,
            shifted_onset=shifted_onset,
        )
        interval_numbers = np.arange(len(shifted_speeds))
        shift_transition_start = min(recorded_onset, shifted_onset)
        shift_fraction = speed_mutation._smoothstep(
            (interval_numbers - shift_transition_start + 1)
            / config.multiplier_ramp_steps
        )
        shifted_speeds = interval_speeds + (
            shifted_speeds - interval_speeds
        ) * shift_fraction
        ramp_fraction = speed_mutation._smoothstep(
            (interval_numbers - shifted_onset + 1)
            / config.multiplier_ramp_steps
        )
        interval_multipliers = np.where(
            interval_numbers >= shifted_onset,
            1.0 + (config.speed_multiplier - 1.0) * ramp_fraction,
            1.0,
        )
        mutated_interval_speeds = shifted_speeds * interval_multipliers
        mutated_progress = np.concatenate(
            ([0.0], np.cumsum(mutated_interval_speeds * TIME_INTERVAL_S))
        )
        if mutated_progress[-1] > route_progress[-1] + config.route_epsilon_m:
            return _rejected("mutated_progress_exceeds_recorded_route")
        try:
            mutated_xy = speed_mutation._interpolate_route(
                mutated_progress,
                route_progress,
                route_xy,
                config.route_epsilon_m,
            )
            mutated_yaw = speed_mutation._interpolate_route(
                mutated_progress,
                route_progress,
                route_yaw,
                config.route_epsilon_m,
            )
        except ValueError as error:
            return _rejected(str(error))
        output_x[current_timestep:route_stop] = mutated_xy[:, 0]
        output_y[current_timestep:route_stop] = mutated_xy[:, 1]
        output_yaw[current_timestep:route_stop] = mutated_yaw
        future_displacements = np.diff(mutated_xy, axis=0)
        future_velocity = future_displacements / TIME_INTERVAL_S
        output_vel_x[current_timestep + 1 : route_stop] = future_velocity[:, 0]
        output_vel_y[current_timestep + 1 : route_stop] = future_velocity[:, 1]
        moving = np.linalg.norm(future_displacements, axis=1) > 1e-6
        tangent_yaw = np.arctan2(
            future_displacements[:, 1], future_displacements[:, 0]
        )
        output_yaw[current_timestep + 1 : route_stop] = np.where(
            moving, tangent_yaw, mutated_yaw[1:]
        )

    history_slice = slice(None, current_timestep + 1)
    history_unchanged = bool(
        all(
            np.array_equal(output[history_slice], source[history_slice])
            for output, source in zip(
                (output_x, output_y, output_yaw, output_vel_x, output_vel_y),
                arrays[:5],
            )
        )
    )
    boundary_velocity = np.column_stack(
        (
            output_vel_x[current_timestep - 1 : route_stop],
            output_vel_y[current_timestep - 1 : route_stop],
        )
    )
    original_boundary_velocity = np.column_stack(
        (
            arrays[3][current_timestep - 1 : route_stop],
            arrays[4][current_timestep - 1 : route_stop],
        )
    ).astype(np.float64)
    acceleration = np.diff(boundary_velocity, axis=0) / TIME_INTERVAL_S
    jerk = np.diff(acceleration, axis=0) / TIME_INTERVAL_S
    original_acceleration = (
        np.diff(original_boundary_velocity, axis=0) / TIME_INTERVAL_S
    )
    original_jerk = np.diff(original_acceleration, axis=0) / TIME_INTERVAL_S
    mutated_velocity = boundary_velocity[1:]
    max_speed_mps = float(np.max(np.linalg.norm(mutated_velocity, axis=1)))
    max_abs_accel_mps2 = float(
        np.max(np.linalg.norm(acceleration, axis=1))
    )
    max_abs_jerk_mps3 = (
        float(np.max(np.linalg.norm(jerk, axis=1))) if len(jerk) else 0.0
    )
    original_max_speed_mps = float(
        np.max(np.linalg.norm(original_boundary_velocity[1:], axis=1))
    )
    original_max_abs_accel_mps2 = float(
        np.max(np.linalg.norm(original_acceleration, axis=1))
    )
    original_max_abs_jerk_mps3 = (
        float(np.max(np.linalg.norm(original_jerk, axis=1)))
        if len(original_jerk)
        else 0.0
    )
    route_deviation = speed_mutation._point_to_polyline_distances(
        mutated_xy, route_xy
    )
    max_route_deviation_m = float(np.max(route_deviation))
    trajectory_changed = bool(
        any(
            not np.array_equal(output[current_timestep + 1 :], source[current_timestep + 1 :])
            for output, source in zip(
                (output_x, output_y, output_yaw, output_vel_x, output_vel_y),
                arrays[:5],
            )
        )
    )
    metrics: dict[str, float | bool | int] = {
        "history_unchanged": history_unchanged,
        "trajectory_changed": trajectory_changed,
        "current_timestep": current_timestep,
        "recorded_braking_onset_step": recorded_onset,
        "shifted_braking_onset_step": shifted_onset,
        "recorded_braking_onset_s": round(
            recorded_onset * TIME_INTERVAL_S, 6
        ),
        "shifted_braking_onset_s": round(
            shifted_onset * TIME_INTERVAL_S, 6
        ),
        "max_speed_mps": round(max_speed_mps, 6),
        "max_abs_accel_mps2": round(max_abs_accel_mps2, 6),
        "max_abs_jerk_mps3": round(max_abs_jerk_mps3, 6),
        "original_max_speed_mps": round(original_max_speed_mps, 6),
        "original_max_abs_accel_mps2": round(
            original_max_abs_accel_mps2, 6
        ),
        "original_max_abs_jerk_mps3": round(
            original_max_abs_jerk_mps3, 6
        ),
        "max_route_deviation_m": round(max_route_deviation_m, 6),
        "recorded_route_length_m": round(float(route_progress[-1]), 6),
        "mutated_route_progress_m": round(float(mutated_progress[-1]), 6),
    }
    reasons: list[str] = []
    if not history_unchanged:
        reasons.append("history_changed")
    if not is_identity and not trajectory_changed:
        reasons.append("mutation_is_trivial")
    allowed_speed_mps = max(
        config.max_speed_mps, original_max_speed_mps + 1e-6
    )
    allowed_accel_mps2 = max(
        config.max_abs_accel_mps2,
        original_max_abs_accel_mps2 + 1e-6,
    )
    allowed_jerk_mps3 = max(
        config.max_abs_jerk_mps3,
        original_max_abs_jerk_mps3 + 1e-6,
    )
    if max_speed_mps > allowed_speed_mps:
        reasons.append("speed_bound_exceeded")
    if max_abs_accel_mps2 > allowed_accel_mps2:
        reasons.append("acceleration_bound_exceeded")
    if max_abs_jerk_mps3 > allowed_jerk_mps3:
        reasons.append("jerk_bound_exceeded")
    if max_route_deviation_m > config.max_route_deviation_m:
        reasons.append("route_deviation_exceeded")
    if reasons:
        return _rejected(*reasons, metrics=metrics)
    return LeadBrakingMutationResult(
        accepted=True,
        rejection_reasons=(),
        metrics=metrics,
        x=output_x.astype(arrays[0].dtype),
        y=output_y.astype(arrays[1].dtype),
        yaw=output_yaw.astype(arrays[2].dtype),
        vel_x=output_vel_x.astype(arrays[3].dtype),
        vel_y=output_vel_y.astype(arrays[4].dtype),
    )


def apply_lead_braking_mutation(
    scenario: Any,
    object_index: int,
    config: LeadBrakingMutationConfig,
) -> tuple[Any | None, LeadBrakingMutationResult]:
    """Apply one lead-braking mutation to a Waymax log trajectory."""
    trajectory = scenario.log_trajectory
    if object_index < 0 or object_index >= trajectory.num_objects:
        return None, _rejected("object_index_out_of_range")
    result = mutate_lead_braking(
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
        return source.at[object_index].set(
            jnp.asarray(values, dtype=source.dtype)
        )

    mutated_trajectory = trajectory.replace(
        x=replace_object("x", result.x),
        y=replace_object("y", result.y),
        yaw=replace_object("yaw", result.yaw),
        vel_x=replace_object("vel_x", result.vel_x),
        vel_y=replace_object("vel_y", result.vel_y),
    )
    return scenario.replace(log_trajectory=mutated_trajectory), result
