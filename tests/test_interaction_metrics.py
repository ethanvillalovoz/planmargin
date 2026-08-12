"""Data-free tests for continuous same-route interaction metrics."""

import numpy as np
import pytest

from planmargin import interaction_metrics
from planmargin import geometry_benchmark


def _box(x_m: float) -> np.ndarray:
    return interaction_metrics.oriented_box_corners(
        x_m=x_m,
        y_m=0.0,
        yaw_rad=0.0,
        length_m=4.0,
        width_m=2.0,
    )


def test_signed_box_separation_is_positive_for_gap() -> None:
    assert interaction_metrics.signed_oriented_box_separation(
        _box(0.0), _box(5.0)
    ) == 1.0


def test_signed_box_separation_is_negative_for_overlap() -> None:
    assert interaction_metrics.signed_oriented_box_separation(
        _box(0.0), _box(3.0)
    ) == -1.0


def test_longitudinal_ttc_uses_bumper_gap_and_closing_speed() -> None:
    value = interaction_metrics.longitudinal_ttc_s(
        sdc_x_m=0.0,
        sdc_y_m=0.0,
        sdc_yaw_rad=0.0,
        sdc_vel_x_mps=10.0,
        sdc_vel_y_mps=0.0,
        sdc_length_m=4.0,
        lead_x_m=10.0,
        lead_y_m=0.0,
        lead_vel_x_mps=5.0,
        lead_vel_y_mps=0.0,
        lead_length_m=4.0,
    )

    assert value == 1.2


def test_non_closing_lead_has_no_finite_ttc() -> None:
    value = interaction_metrics.longitudinal_ttc_s(
        sdc_x_m=0.0,
        sdc_y_m=0.0,
        sdc_yaw_rad=0.0,
        sdc_vel_x_mps=5.0,
        sdc_vel_y_mps=0.0,
        sdc_length_m=4.0,
        lead_x_m=10.0,
        lead_y_m=0.0,
        lead_vel_x_mps=10.0,
        lead_vel_y_mps=0.0,
        lead_length_m=4.0,
    )

    assert value is None


def test_track_metrics_skip_invalid_states_and_report_minima() -> None:
    sdc = {
        "x_m": [0.0, 1.0, 2.0],
        "y_m": [0.0, 0.0, 0.0],
        "yaw_rad": [0.0, 0.0, 0.0],
        "vel_x_mps": [10.0, 10.0, 10.0],
        "vel_y_mps": [0.0, 0.0, 0.0],
        "length_m": [4.0, 4.0, 4.0],
        "width_m": [2.0, 2.0, 2.0],
        "valid": [True, False, True],
    }
    lead = {
        "x_m": [10.0, 9.0, 8.0],
        "y_m": [0.0, 0.0, 0.0],
        "yaw_rad": [0.0, 0.0, 0.0],
        "vel_x_mps": [5.0, 5.0, 5.0],
        "vel_y_mps": [0.0, 0.0, 0.0],
        "length_m": [4.0, 4.0, 4.0],
        "width_m": [2.0, 2.0, 2.0],
        "valid": [True, True, True],
    }

    result = interaction_metrics.interaction_metrics(sdc, lead)

    assert result == {
        "jointly_valid_states": 2,
        "minimum_signed_separation_m": 2.0,
        "minimum_longitudinal_ttc_s": 0.4,
    }


def test_valid_state_with_nonfinite_geometry_is_rejected() -> None:
    sdc = {
        "x_m": [float("nan")],
        "y_m": [0.0],
        "yaw_rad": [0.0],
        "vel_x_mps": [10.0],
        "vel_y_mps": [0.0],
        "length_m": [4.0],
        "width_m": [2.0],
        "valid": [True],
    }
    lead = {
        "x_m": [10.0],
        "y_m": [0.0],
        "yaw_rad": [0.0],
        "vel_x_mps": [5.0],
        "vel_y_mps": [0.0],
        "length_m": [4.0],
        "width_m": [2.0],
        "valid": [True],
    }

    with pytest.raises(ValueError, match="must be finite"):
        interaction_metrics.interaction_metrics(sdc, lead)


def test_native_trace_aggregation_matches_python_reference_randomized() -> None:
    generator = np.random.default_rng(20260812)
    for _ in range(100):
        states = 80
        sdc_x = np.cumsum(generator.uniform(0.5, 1.5, states))
        lead_x = sdc_x + generator.uniform(-3.0, 30.0, states)
        sdc = {
            "x_m": sdc_x,
            "y_m": generator.normal(0.0, 1.0, states),
            "yaw_rad": generator.uniform(-np.pi, np.pi, states),
            "vel_x_mps": generator.uniform(-2.0, 20.0, states),
            "vel_y_mps": generator.uniform(-2.0, 2.0, states),
            "length_m": generator.uniform(3.0, 6.0, states),
            "width_m": generator.uniform(1.5, 2.5, states),
            "valid": generator.random(states) > 0.1,
        }
        lead = {
            "x_m": lead_x,
            "y_m": generator.normal(0.0, 1.0, states),
            "yaw_rad": generator.uniform(-np.pi, np.pi, states),
            "vel_x_mps": generator.uniform(-2.0, 20.0, states),
            "vel_y_mps": generator.uniform(-2.0, 2.0, states),
            "length_m": generator.uniform(3.0, 6.0, states),
            "width_m": generator.uniform(1.5, 2.5, states),
            "valid": generator.random(states) > 0.1,
        }
        sdc["valid"][0] = True
        lead["valid"][0] = True

        assert interaction_metrics.interaction_metrics(
            sdc, lead
        ) == interaction_metrics._interaction_metrics_python(sdc, lead)


def test_native_kernel_preserves_invalid_state_and_shape_semantics() -> None:
    sdc, lead = geometry_benchmark.synthetic_tracks(states=3)
    sdc["x_m"][1] = np.nan
    sdc["valid"][1] = False
    assert interaction_metrics.interaction_metrics(
        sdc, lead
    ) == interaction_metrics._interaction_metrics_python(sdc, lead)

    sdc["valid"][:] = False
    with pytest.raises(ValueError, match="no jointly valid states"):
        interaction_metrics.interaction_metrics(sdc, lead)

    sdc, lead = geometry_benchmark.synthetic_tracks(states=3)
    sdc["x_m"] = sdc["x_m"][:, None]
    with pytest.raises(ValueError, match="one-dimensional"):
        interaction_metrics.interaction_metrics(sdc, lead)


def test_data_free_benchmark_checks_parity() -> None:
    report = geometry_benchmark.benchmark(iterations=3, states=20)

    assert report["decision"] == "parity_passed"
    assert report["fixture"] == "synthetic_20_state_lead_vehicle_trace"
    assert report["native_median_microseconds"] > 0.0
    assert report["python_median_microseconds"] > 0.0
    assert report["kernel_speedup"] > 0.0
