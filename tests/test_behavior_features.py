"""Data-free checks for the shared natural/counterfactual feature extractor."""

import numpy as np

from planmargin import behavior_features


def _trajectories(*, current_timestep: int = 0) -> dict[str, np.ndarray | int]:
    states = current_timestep + behavior_features.WINDOW_STATES
    lead_speed = np.full(states, 10.0, dtype=np.float64)
    lead_speed[current_timestep + 20 :] -= np.minimum(
        4.0,
        0.2 * np.arange(states - current_timestep - 20),
    )
    sdc_x = np.arange(states, dtype=np.float64)
    return {
        "sdc_x": sdc_x,
        "sdc_y": np.zeros(states),
        "sdc_yaw": np.zeros(states),
        "sdc_vel_x": np.full(states, 12.0),
        "sdc_vel_y": np.zeros(states),
        "sdc_valid": np.ones(states, dtype=bool),
        "lead_x": sdc_x + 20.0,
        "lead_y": np.zeros(states),
        "lead_vel_x": lead_speed,
        "lead_vel_y": np.zeros(states),
        "lead_valid": np.ones(states, dtype=bool),
        "current_timestep": current_timestep,
    }


def test_feature_math_matches_frozen_vector_and_float64() -> None:
    inputs = _trajectories()
    result = behavior_features.extract_behavior_features(**inputs)

    assert result.accepted is True
    assert result.vector is not None
    assert len(result.vector) == 8
    assert result.vector[0] == 20.0
    assert result.vector[1] == 2.0
    assert result.vector[2] == 10.0
    assert np.isclose(result.vector[3], 2.0)
    assert np.isclose(result.vector[4], 4.0)
    assert np.isclose(result.vector[5], 2.0)
    assert result.vector[6] == 1.0
    assert np.isfinite(np.asarray(result.vector, dtype=np.float64)).all()
    assert result.audit_metrics["maximum_absolute_jerk_mps3"] >= 0.0


def test_current_offset_produces_same_natural_and_waymax_features() -> None:
    natural = behavior_features.extract_behavior_features(**_trajectories())
    waymax = behavior_features.extract_behavior_features(
        **_trajectories(current_timestep=10)
    )

    assert natural.accepted and waymax.accepted
    np.testing.assert_allclose(natural.vector, waymax.vector, atol=1e-12)


def test_incomplete_invalid_and_nonfinite_windows_are_rejected() -> None:
    incomplete = _trajectories()
    for key, value in tuple(incomplete.items()):
        if isinstance(value, np.ndarray):
            incomplete[key] = value[:-1]
    invalid = _trajectories()
    invalid["lead_valid"][30] = False
    nonfinite = _trajectories()
    nonfinite["lead_vel_x"][30] = np.nan

    assert behavior_features.extract_behavior_features(
        **incomplete
    ).rejection_reasons == ("six_second_window_incomplete",)
    assert behavior_features.extract_behavior_features(**invalid).rejection_reasons == (
        "six_second_window_contains_invalid_state",
    )
    assert behavior_features.extract_behavior_features(
        **nonfinite
    ).rejection_reasons == ("six_second_window_contains_nonfinite_value",)


def test_length_and_shape_rejections_are_versioned() -> None:
    mismatched = _trajectories()
    mismatched["lead_x"] = mismatched["lead_x"][:-1]
    two_dimensional = _trajectories()
    two_dimensional["lead_x"] = two_dimensional["lead_x"][None, :]

    assert behavior_features.extract_behavior_features(
        **mismatched
    ).rejection_reasons == ("trajectory_field_lengths_differ",)
    assert behavior_features.extract_behavior_features(
        **two_dimensional
    ).rejection_reasons == ("trajectory_must_be_one_dimensional",)


def test_object_pair_wrapper_handles_mutated_arrays_and_geometry_errors() -> None:
    inputs = _trajectories(current_timestep=10)
    object_fields = {
        name: np.stack((inputs[f"sdc_{name}"], inputs[f"lead_{name}"]))
        for name in ("x", "y", "vel_x", "vel_y", "valid")
    }
    object_fields["yaw"] = np.stack(
        (inputs["sdc_yaw"], np.zeros_like(inputs["sdc_yaw"]))
    )

    result = behavior_features.extract_object_pair_features(
        **object_fields,
        sdc_object_index=0,
        lead_object_index=1,
        current_timestep=10,
    )
    invalid = behavior_features.extract_object_pair_features(
        **object_fields,
        sdc_object_index=0,
        lead_object_index=0,
        current_timestep=10,
    )

    assert result.accepted is True
    assert invalid.rejection_reasons == ("lead_matches_sdc",)
