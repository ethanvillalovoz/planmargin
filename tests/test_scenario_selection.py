"""Data-free tests for deterministic scenario-family mining."""

import dataclasses

import numpy as np

from planmargin import scenario_selection


def _base_arrays(num_objects: int = 3) -> scenario_selection.ScenarioArrays:
    steps = scenario_selection.NUM_TRAJECTORY_STEPS
    x = np.zeros((num_objects, steps), dtype=np.float32)
    y = np.zeros_like(x)
    yaw = np.zeros_like(x)
    valid = np.ones((num_objects, steps), dtype=bool)
    vel_x = np.ones_like(x) * 5.0
    vel_y = np.zeros_like(x)
    return scenario_selection.ScenarioArrays(
        scenario_id="synthetic",
        object_types=np.array([1, 1, 0], dtype=np.int32),
        is_sdc=np.array([True, False, False]),
        objects_of_interest=np.array([True, True, False]),
        x=x,
        y=y,
        yaw=yaw,
        valid=valid,
        vel_x=vel_x,
        vel_y=vel_y,
    )


def test_left_turn_candidate_requires_oncoming_path_conflict() -> None:
    arrays = _base_arrays()
    steps = scenario_selection.NUM_TRAJECTORY_STEPS
    angle = np.linspace(0.0, np.pi / 2, steps)
    radius = 30.0
    arrays.x[0] = radius * np.sin(angle)
    arrays.y[0] = radius * (1.0 - np.cos(angle))
    arrays.yaw[0] = angle
    arrays.vel_x[0] = 5.0 * np.cos(angle)
    arrays.vel_y[0] = 5.0 * np.sin(angle)
    arrays.x[1] = np.linspace(45.0, -5.0, steps)
    arrays.y[1] = 8.0
    arrays.yaw[1] = np.pi
    arrays.vel_x[1] = -5.0

    candidate = scenario_selection._left_turn_candidate(
        arrays, 0, 0, scenario_selection.SelectionThresholds()
    )

    assert candidate is not None
    assert candidate.family == "left_turn_oncoming"
    assert candidate.interacting_object_index == 1

    arrays.yaw[1] = 0.0
    assert (
        scenario_selection._left_turn_candidate(
            arrays, 0, 0, scenario_selection.SelectionThresholds()
        )
        is None
    )


def test_lead_braking_candidate_requires_same_recorded_route() -> None:
    arrays = _base_arrays()
    steps = scenario_selection.NUM_TRAJECTORY_STEPS
    arrays.x[0] = np.linspace(0.0, 80.0, steps)
    arrays.vel_x[0] = 10.0
    arrays.x[1] = np.linspace(15.0, 70.0, steps)
    arrays.vel_x[1, :31] = np.linspace(10.0, 5.0, 31)
    arrays.vel_x[1, 31:] = 5.0

    candidate = scenario_selection._lead_braking_candidate(
        arrays, 0, 0, scenario_selection.SelectionThresholds()
    )

    assert candidate is not None
    assert candidate.family == "lead_vehicle_braking"
    # This exact value pins the pre-empirical-support Stage-0 selector.
    assert candidate.score == 10.25
    assert candidate.interacting_object_index == 1
    assert candidate.features["max_total_speed_drop_mps"] == 5.0

    arrays.y[1] = 4.0
    assert (
        scenario_selection._lead_braking_candidate(
            arrays, 0, 0, scenario_selection.SelectionThresholds()
        )
        is None
    )


def test_wrap_angle_uses_smallest_signed_difference() -> None:
    wrapped = scenario_selection._wrap_angle_radians(3 * np.pi)
    assert np.isclose(abs(wrapped), np.pi)


def test_set_flag_rejects_negative_one_padding() -> None:
    result = scenario_selection._set_flag(np.array([1, 0, -1]))
    np.testing.assert_array_equal(result, np.array([True, False, False]))


def test_braking_features_require_a_complete_one_second_window() -> None:
    speed = np.full(scenario_selection.NUM_TRAJECTORY_STEPS, 5.0)
    speed[57:61] = [10.0, 9.3, 8.6, 8.0]
    speed[61:] = 8.0
    valid = np.ones_like(speed, dtype=bool)
    thresholds = dataclasses.replace(
        scenario_selection.SelectionThresholds(),
        max_abs_accel_mps2=100.0,
        max_abs_jerk_mps3=2_000.0,
        min_braking_nonincrease_fraction=0.0,
    )

    assert scenario_selection._braking_features(
        speed, valid, thresholds
    ) is None


def test_braking_features_reject_discontinuous_speed_spikes() -> None:
    speed = np.full(scenario_selection.NUM_TRAJECTORY_STEPS, 10.0)
    speed[20] = 25.0
    speed[21:] = 8.0
    valid = np.ones_like(speed, dtype=bool)

    assert scenario_selection._braking_features(
        speed, valid, scenario_selection.SelectionThresholds()
    ) is None


def test_braking_features_accept_clean_sustained_braking() -> None:
    speed = np.full(scenario_selection.NUM_TRAJECTORY_STEPS, 10.0)
    speed[20:41] = np.linspace(10.0, 7.0, 21)
    speed[41:] = 7.0
    valid = np.ones_like(speed, dtype=bool)

    features = scenario_selection._braking_features(
        speed, valid, scenario_selection.SelectionThresholds()
    )

    assert features is not None
    assert features["max_one_second_speed_drop_mps"] == 1.5
    assert features["braking_nonincrease_fraction"] == 1.0


def test_reported_thresholds_include_every_braking_window_rule() -> None:
    thresholds = dataclasses.asdict(
        scenario_selection.SelectionThresholds()
    )

    assert thresholds["braking_window_steps"] == 61
    assert thresholds["min_braking_valid_steps"] == 30
    assert thresholds["one_second_steps"] == 10
    assert thresholds["max_abs_accel_mps2"] == 12.0
    assert thresholds["max_abs_jerk_mps3"] == 100.0
    assert thresholds["max_braking_step_speed_increase_mps"] == 0.2
    assert thresholds["min_braking_nonincrease_fraction"] == 0.8
