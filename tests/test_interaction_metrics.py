"""Data-free tests for continuous same-route interaction metrics."""

import numpy as np

from planmargin import interaction_metrics


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
