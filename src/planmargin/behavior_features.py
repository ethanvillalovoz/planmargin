"""Shared empirical-support features for natural and mutated lead braking."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

FEATURE_SCHEMA_VERSION = "1.0.0"
TIME_INTERVAL_S = 0.1
WINDOW_STATES = 61
ONE_SECOND_STEPS = 10
NONINCREASE_TOLERANCE_MPS = 0.2
FEATURE_NAMES = (
    "current_longitudinal_gap_m",
    "current_closing_speed_mps",
    "current_lead_speed_mps",
    "peak_deceleration_mps2",
    "maximum_cumulative_speed_drop_mps",
    "maximum_one_second_speed_drop_mps",
    "braking_nonincrease_fraction",
    "log1p_maximum_absolute_jerk_mps3",
)


@dataclass(frozen=True)
class BehaviorFeatureResult:
    """Accepted feature vector or versioned, auditable rejection reasons."""

    accepted: bool
    rejection_reasons: tuple[str, ...]
    audit_metrics: dict[str, float]
    vector: tuple[float, ...] | None

    def report(self) -> dict[str, object]:
        return {
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "accepted": self.accepted,
            "rejection_reasons": list(self.rejection_reasons),
            "audit_metrics": self.audit_metrics,
            "feature_names": list(FEATURE_NAMES),
            "vector": None if self.vector is None else list(self.vector),
        }


def _reject(reason: str) -> BehaviorFeatureResult:
    return BehaviorFeatureResult(False, (reason,), {}, None)


def extract_behavior_features(
    *,
    sdc_x: np.ndarray,
    sdc_y: np.ndarray,
    sdc_yaw: np.ndarray,
    sdc_vel_x: np.ndarray,
    sdc_vel_y: np.ndarray,
    sdc_valid: np.ndarray,
    lead_x: np.ndarray,
    lead_y: np.ndarray,
    lead_vel_x: np.ndarray,
    lead_vel_y: np.ndarray,
    lead_valid: np.ndarray,
    current_timestep: int,
) -> BehaviorFeatureResult:
    """Return the frozen eight-feature vector using float64 arithmetic.

    ``current_timestep`` is zero for WOMD current+future arrays and ten for a
    complete Waymax log trajectory. Both natural and mutated callers use this
    function, which prevents the feature definitions from drifting apart.
    """
    values = (
        sdc_x,
        sdc_y,
        sdc_yaw,
        sdc_vel_x,
        sdc_vel_y,
        sdc_valid,
        lead_x,
        lead_y,
        lead_vel_x,
        lead_vel_y,
        lead_valid,
    )
    arrays = tuple(np.asarray(value) for value in values)
    if any(array.ndim != 1 for array in arrays):
        return _reject("trajectory_must_be_one_dimensional")
    lengths = {len(array) for array in arrays}
    if len(lengths) != 1:
        return _reject("trajectory_field_lengths_differ")
    num_states = lengths.pop()
    if current_timestep < 0:
        return _reject("current_timestep_out_of_range")
    stop = current_timestep + WINDOW_STATES
    if stop > num_states:
        return _reject("six_second_window_incomplete")

    sdc_valid_window = arrays[5][current_timestep:stop].astype(bool)
    lead_valid_window = arrays[10][current_timestep:stop].astype(bool)
    if not sdc_valid_window.all() or not lead_valid_window.all():
        return _reject("six_second_window_contains_invalid_state")

    numeric_indices = (0, 1, 2, 3, 4, 6, 7, 8, 9)
    if any(
        not np.isfinite(arrays[index][current_timestep:stop].astype(np.float64)).all()
        for index in numeric_indices
    ):
        return _reject("six_second_window_contains_nonfinite_value")

    (
        sdc_x64,
        sdc_y64,
        sdc_yaw64,
        sdc_vx64,
        sdc_vy64,
        _,
        lead_x64,
        lead_y64,
        lead_vx64,
        lead_vy64,
        _,
    ) = tuple(array.astype(np.float64, copy=False) for array in arrays)
    current = current_timestep
    forward = np.array(
        [np.cos(sdc_yaw64[current]), np.sin(sdc_yaw64[current])],
        dtype=np.float64,
    )
    relative_position = np.array(
        [
            lead_x64[current] - sdc_x64[current],
            lead_y64[current] - sdc_y64[current],
        ],
        dtype=np.float64,
    )
    longitudinal_gap = float(relative_position @ forward)
    sdc_speed = float(np.hypot(sdc_vx64[current], sdc_vy64[current]))
    lead_speed_window = np.hypot(lead_vx64[current:stop], lead_vy64[current:stop])
    current_lead_speed = float(lead_speed_window[0])
    closing_speed = sdc_speed - current_lead_speed

    speed_deltas = np.diff(lead_speed_window)
    acceleration = speed_deltas / TIME_INTERVAL_S
    jerk = np.diff(acceleration) / TIME_INTERVAL_S
    peak_deceleration = max(0.0, float(-np.min(acceleration)))
    cumulative_drop = float(
        np.max(np.maximum.accumulate(lead_speed_window) - lead_speed_window)
    )
    one_second_drop = max(
        0.0,
        float(
            np.max(
                lead_speed_window[:-ONE_SECOND_STEPS]
                - lead_speed_window[ONE_SECOND_STEPS:]
            )
        ),
    )
    nonincrease_fraction = float(np.mean(speed_deltas <= NONINCREASE_TOLERANCE_MPS))
    maximum_absolute_jerk = float(np.max(np.abs(jerk)))
    log_jerk = float(np.log1p(maximum_absolute_jerk))

    audit_metrics = {
        "current_longitudinal_gap_m": longitudinal_gap,
        "current_closing_speed_mps": closing_speed,
        "current_sdc_speed_mps": sdc_speed,
        "current_lead_speed_mps": current_lead_speed,
        "peak_deceleration_mps2": peak_deceleration,
        "maximum_cumulative_speed_drop_mps": cumulative_drop,
        "maximum_one_second_speed_drop_mps": one_second_drop,
        "braking_nonincrease_fraction": nonincrease_fraction,
        "maximum_absolute_jerk_mps3": maximum_absolute_jerk,
        "log1p_maximum_absolute_jerk_mps3": log_jerk,
    }
    vector = tuple(audit_metrics[name] for name in FEATURE_NAMES)
    if not np.isfinite(np.asarray(vector, dtype=np.float64)).all():
        return _reject("derived_feature_is_nonfinite")
    return BehaviorFeatureResult(True, (), audit_metrics, vector)


def extract_object_pair_features(
    *,
    x: np.ndarray,
    y: np.ndarray,
    yaw: np.ndarray,
    vel_x: np.ndarray,
    vel_y: np.ndarray,
    valid: np.ndarray,
    sdc_object_index: int,
    lead_object_index: int,
    current_timestep: int,
) -> BehaviorFeatureResult:
    """Apply the shared extractor to natural or counterfactual object arrays."""
    fields = tuple(np.asarray(value) for value in (x, y, yaw, vel_x, vel_y, valid))
    if any(field.ndim != 2 for field in fields):
        return _reject("object_trajectory_fields_must_be_two_dimensional")
    shapes = {field.shape for field in fields}
    if len(shapes) != 1:
        return _reject("object_trajectory_field_shapes_differ")
    num_objects = fields[0].shape[0]
    if not (
        0 <= sdc_object_index < num_objects and 0 <= lead_object_index < num_objects
    ):
        return _reject("object_index_out_of_range")
    if sdc_object_index == lead_object_index:
        return _reject("lead_matches_sdc")
    return extract_behavior_features(
        sdc_x=fields[0][sdc_object_index],
        sdc_y=fields[1][sdc_object_index],
        sdc_yaw=fields[2][sdc_object_index],
        sdc_vel_x=fields[3][sdc_object_index],
        sdc_vel_y=fields[4][sdc_object_index],
        sdc_valid=fields[5][sdc_object_index],
        lead_x=fields[0][lead_object_index],
        lead_y=fields[1][lead_object_index],
        lead_vel_x=fields[3][lead_object_index],
        lead_vel_y=fields[4][lead_object_index],
        lead_valid=fields[5][lead_object_index],
        current_timestep=current_timestep,
    )
