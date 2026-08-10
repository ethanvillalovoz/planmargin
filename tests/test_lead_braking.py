"""Data-free tests for two-dimensional lead-braking mutations."""

import numpy as np

from planmargin import lead_braking


def _braking_trajectory() -> dict[str, np.ndarray | int]:
    steps = 91
    intervals = steps - 1
    speeds = np.full(intervals, 10.0, dtype=np.float64)
    braking_start = lead_braking.CURRENT_TIMESTEP + 20
    speeds[braking_start:] = np.maximum(
        4.0,
        10.0 - 0.2 * np.arange(1, intervals - braking_start + 1),
    )
    x = np.concatenate(([0.0], np.cumsum(speeds * 0.1)))
    state_speeds = np.concatenate(([speeds[0]], speeds))
    return {
        "x": x,
        "y": np.zeros(steps, dtype=np.float64),
        "yaw": np.zeros(steps, dtype=np.float64),
        "vel_x": state_speeds,
        "vel_y": np.zeros(steps, dtype=np.float64),
        "valid": np.ones(steps, dtype=bool),
        "current_timestep": lead_braking.CURRENT_TIMESTEP,
    }


def test_identity_control_reproduces_every_field_exactly() -> None:
    trajectory = _braking_trajectory()
    config = lead_braking.LeadBrakingMutationConfig(
        braking_onset_offset_s=0.0,
        speed_multiplier=1.0,
    )

    result = lead_braking.mutate_lead_braking(
        **trajectory, config=config
    )

    assert result.accepted is True
    assert result.metrics["trajectory_changed"] is False
    for field in ("x", "y", "yaw", "vel_x", "vel_y"):
        output = getattr(result, field)
        assert output is not None
        np.testing.assert_array_equal(output, trajectory[field])


def test_onset_offset_and_multiplier_preserve_history_and_route() -> None:
    trajectory = _braking_trajectory()
    original_x = np.asarray(trajectory["x"]).copy()
    config = lead_braking.LeadBrakingMutationConfig(
        braking_onset_offset_s=0.2,
        speed_multiplier=0.8,
    )

    result = lead_braking.mutate_lead_braking(
        **trajectory, config=config
    )

    assert result.accepted is True
    assert result.x is not None
    np.testing.assert_array_equal(
        result.x[: lead_braking.CURRENT_TIMESTEP + 1],
        original_x[: lead_braking.CURRENT_TIMESTEP + 1],
    )
    assert result.x[-1] < original_x[-1]
    assert result.metrics["history_unchanged"] is True
    assert result.metrics["trajectory_changed"] is True
    assert result.metrics["shifted_braking_onset_step"] == (
        result.metrics["recorded_braking_onset_step"] + 2
    )
    assert result.metrics["max_route_deviation_m"] == 0.0


def test_detected_onset_is_deterministic() -> None:
    trajectory = _braking_trajectory()
    route_x = np.asarray(trajectory["x"])[lead_braking.CURRENT_TIMESTEP :]
    speeds = np.diff(route_x) / lead_braking.TIME_INTERVAL_S
    config = lead_braking.LeadBrakingMutationConfig()

    first = lead_braking.detect_recorded_braking_onset(speeds, config)
    second = lead_braking.detect_recorded_braking_onset(speeds, config)

    assert first is not None
    assert first == second


def test_non_aligned_and_out_of_bounds_parameters_are_rejected() -> None:
    trajectory = _braking_trajectory()

    non_aligned = lead_braking.mutate_lead_braking(
        **trajectory,
        config=lead_braking.LeadBrakingMutationConfig(
            braking_onset_offset_s=0.15
        ),
    )
    out_of_bounds = lead_braking.mutate_lead_braking(
        **trajectory,
        config=lead_braking.LeadBrakingMutationConfig(
            speed_multiplier=0.5
        ),
    )

    assert non_aligned.rejection_reasons == (
        "braking_onset_offset_not_timestep_aligned",
    )
    assert out_of_bounds.rejection_reasons == (
        "speed_multiplier_out_of_bounds",
    )


def test_track_without_sustained_braking_is_rejected() -> None:
    trajectory = _braking_trajectory()
    x = np.arange(91, dtype=np.float64)
    trajectory["x"] = x
    trajectory["vel_x"] = np.full(91, 10.0)

    result = lead_braking.mutate_lead_braking(
        **trajectory, config=lead_braking.LeadBrakingMutationConfig()
    )

    assert result.rejection_reasons == (
        "recorded_braking_onset_not_found",
    )


def test_identity_preserves_recorded_invalid_tail() -> None:
    trajectory = _braking_trajectory()
    valid = np.asarray(trajectory["valid"]).copy()
    valid[70:] = False
    trajectory["valid"] = valid
    config = lead_braking.LeadBrakingMutationConfig(
        braking_onset_offset_s=0.0,
        speed_multiplier=1.0,
    )

    result = lead_braking.mutate_lead_braking(
        **trajectory, config=config
    )

    assert result.accepted is True
    assert result.metrics["trajectory_changed"] is False
    np.testing.assert_array_equal(result.x, trajectory["x"])


def test_report_omits_trajectory_arrays() -> None:
    config = lead_braking.LeadBrakingMutationConfig()
    result = lead_braking.mutate_lead_braking(
        **_braking_trajectory(), config=config
    )

    report = result.report(config)

    assert report["mutation_type"] == "lead_braking_onset_and_speed"
    assert not {"x", "y", "yaw", "vel_x", "vel_y"} & report.keys()
