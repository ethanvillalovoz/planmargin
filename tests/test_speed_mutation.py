"""Data-free tests for the bounded route-progress speed mutation."""

import dataclasses

import numpy as np

from planmargin import speed_mutation


def _straight_trajectory() -> dict[str, np.ndarray | int]:
    steps = 91
    speed_mps = 10.0
    x = np.arange(steps, dtype=np.float64) * speed_mps * 0.1
    return {
        "x": x,
        "y": np.zeros(steps, dtype=np.float64),
        "yaw": np.zeros(steps, dtype=np.float64),
        "vel_x": np.full(steps, speed_mps, dtype=np.float64),
        "vel_y": np.zeros(steps, dtype=np.float64),
        "valid": np.ones(steps, dtype=bool),
        "current_timestep": speed_mutation.CURRENT_TIMESTEP,
    }


def test_speed_multiplier_preserves_history_and_recorded_route() -> None:
    trajectory = _straight_trajectory()
    original_x = np.asarray(trajectory["x"]).copy()

    result = speed_mutation.mutate_route_speed(
        **trajectory,
        config=speed_mutation.SpeedMutationConfig(speed_multiplier=0.9),
    )

    assert result.accepted is True
    assert result.rejection_reasons == ()
    assert result.x is not None
    assert result.y is not None
    np.testing.assert_array_equal(
        result.x[: speed_mutation.CURRENT_TIMESTEP + 1],
        original_x[: speed_mutation.CURRENT_TIMESTEP + 1],
    )
    np.testing.assert_array_equal(result.y, np.zeros_like(result.y))
    assert result.x[-1] < original_x[-1]
    assert result.metrics["history_unchanged"] is True
    assert result.metrics["max_route_deviation_m"] == 0.0


def test_identity_multiplier_reproduces_route_positions() -> None:
    trajectory = _straight_trajectory()

    result = speed_mutation.mutate_route_speed(
        **trajectory,
        config=speed_mutation.SpeedMutationConfig(speed_multiplier=1.0),
    )

    assert result.accepted is True
    assert result.x is not None
    np.testing.assert_allclose(result.x, trajectory["x"], atol=1e-9)


def test_out_of_bounds_multiplier_retains_rejection_reason() -> None:
    result = speed_mutation.mutate_route_speed(
        **_straight_trajectory(),
        config=speed_mutation.SpeedMutationConfig(speed_multiplier=0.5),
    )

    assert result.accepted is False
    assert result.rejection_reasons == ("speed_multiplier_out_of_bounds",)
    assert result.report(speed_mutation.SpeedMutationConfig())["metrics"] == {}


def test_discontinuous_future_route_is_rejected() -> None:
    trajectory = _straight_trajectory()
    valid = np.asarray(trajectory["valid"]).copy()
    valid[30] = False
    trajectory["valid"] = valid

    result = speed_mutation.mutate_route_speed(
        **trajectory,
        config=speed_mutation.SpeedMutationConfig(),
    )

    assert result.accepted is False
    assert result.rejection_reasons == ("future_route_not_contiguous",)


def test_current_timestep_requires_one_boundary_history_step() -> None:
    trajectory = _straight_trajectory()
    trajectory["current_timestep"] = 0

    result = speed_mutation.mutate_route_speed(
        **trajectory,
        config=speed_mutation.SpeedMutationConfig(),
    )

    assert result.accepted is False
    assert result.rejection_reasons == ("current_timestep_out_of_range",)


def test_abrupt_multiplier_fails_kinematic_bounds() -> None:
    result = speed_mutation.mutate_route_speed(
        **_straight_trajectory(),
        config=speed_mutation.SpeedMutationConfig(
            speed_multiplier=0.75,
            ramp_steps=1,
        ),
    )

    assert result.accepted is False
    assert "acceleration_bound_exceeded" in result.rejection_reasons
    assert "jerk_bound_exceeded" in result.rejection_reasons


def test_invalid_boundary_acceleration_is_rejected() -> None:
    trajectory = _straight_trajectory()
    vel_x = np.asarray(trajectory["vel_x"]).copy()
    vel_x[speed_mutation.CURRENT_TIMESTEP - 1] = 0.0
    trajectory["vel_x"] = vel_x

    result = speed_mutation.mutate_route_speed(
        **trajectory,
        config=speed_mutation.SpeedMutationConfig(),
    )

    assert result.accepted is False
    assert "acceleration_bound_exceeded" in result.rejection_reasons


def test_progress_beyond_recorded_route_is_rejected() -> None:
    config = dataclasses.replace(
        speed_mutation.SpeedMutationConfig(),
        speed_multiplier=1.1,
        max_speed_multiplier=1.2,
    )

    result = speed_mutation.mutate_route_speed(
        **_straight_trajectory(), config=config
    )

    assert result.accepted is False
    assert result.rejection_reasons == (
        "mutated_progress_exceeds_recorded_route",
    )


def test_serialized_result_omits_trajectory_arrays() -> None:
    config = speed_mutation.SpeedMutationConfig()
    result = speed_mutation.mutate_route_speed(
        **_straight_trajectory(), config=config
    )

    report = result.report(config)

    assert report["schema_version"] == 1
    assert report["parameters"]["speed_multiplier"] == 0.9
    assert report["rejection_reasons"] == []
    assert not {"x", "y", "yaw", "vel_x", "vel_y"} & report.keys()
