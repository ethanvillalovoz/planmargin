"""Data-free tests for independent controller outcome evaluation."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from planmargin import controller_comparison


def _outcome(success: bool) -> dict[str, bool]:
    return {"success": success}


def test_reference_configuration_is_distinct_and_more_conservative() -> None:
    tested = controller_comparison.TESTED_CONTROLLER
    reference = controller_comparison.REFERENCE_CONTROLLER

    assert tested.controller_id != reference.controller_id
    assert reference.desired_vel_mps < tested.desired_vel_mps
    assert reference.min_spacing_m > tested.min_spacing_m
    assert reference.safe_time_headway_s > tested.safe_time_headway_s
    assert reference.comfortable_decel_mps2 < (
        tested.comfortable_decel_mps2
    )
    assert reference.additional_lookahead_distance_m > (
        tested.additional_lookahead_distance_m
    )


def test_reference_has_larger_desired_gap_while_closing() -> None:
    tested_gap = controller_comparison.idm_desired_gap_m(
        controller_comparison.TESTED_CONTROLLER,
        current_speed_mps=15.0,
        lead_speed_mps=10.0,
    )
    reference_gap = controller_comparison.idm_desired_gap_m(
        controller_comparison.REFERENCE_CONTROLLER,
        current_speed_mps=15.0,
        lead_speed_mps=10.0,
    )

    assert reference_gap > tested_gap


def test_successful_rollout_has_no_failure_reasons() -> None:
    result = controller_comparison.evaluate_rollout(
        max_sdc_overlap=0.0,
        max_sdc_offroad=0.0,
        sdc_valid_all_steps=True,
        final_timestep=90,
        expected_final_timestep=90,
    )

    assert result["success"] is True
    assert result["failure_reasons"] == []


def test_failure_reasons_are_evaluated_independently() -> None:
    candidate = controller_comparison.evaluate_rollout(
        max_sdc_overlap=1.0,
        max_sdc_offroad=0.0,
        sdc_valid_all_steps=True,
        final_timestep=90,
        expected_final_timestep=90,
    )
    reference = controller_comparison.evaluate_rollout(
        max_sdc_overlap=0.0,
        max_sdc_offroad=1.0,
        sdc_valid_all_steps=False,
        final_timestep=89,
        expected_final_timestep=90,
    )

    assert candidate["failure_reasons"] == ["sdc_overlap"]
    assert reference["failure_reasons"] == [
        "sdc_offroad",
        "sdc_invalid",
        "rollout_incomplete",
    ]


def test_outcome_retains_first_failure_state() -> None:
    result = controller_comparison.evaluate_rollout(
        max_sdc_overlap=1.0,
        max_sdc_offroad=0.0,
        sdc_valid_all_steps=True,
        final_timestep=90,
        expected_final_timestep=90,
        first_failure_timestep=42,
        first_failure_reasons=["sdc_overlap"],
    )

    assert result["first_failure_timestep"] == 42
    assert result["first_failure_reasons"] == ["sdc_overlap"]


def test_policy_specific_finding_requires_all_four_outcomes() -> None:
    finding = controller_comparison.comparison_finding(
        tested_original=_outcome(True),
        tested_mutated=_outcome(False),
        reference_original=_outcome(True),
        reference_mutated=_outcome(True),
    )

    assert finding == {
        "tested_original_pass": True,
        "tested_mutated_failure": True,
        "reference_original_pass": True,
        "reference_mutated_success": True,
        "policy_specific_avoidable_failure": True,
    }


def test_reference_failure_does_not_count_as_avoidable() -> None:
    finding = controller_comparison.comparison_finding(
        tested_original=_outcome(True),
        tested_mutated=_outcome(False),
        reference_original=_outcome(True),
        reference_mutated=_outcome(False),
    )

    assert finding["tested_mutated_failure"] is True
    assert finding["reference_mutated_success"] is False
    assert finding["policy_specific_avoidable_failure"] is False


def test_controller_report_is_versioned_and_parameterized() -> None:
    report = controller_comparison.REFERENCE_CONTROLLER.report()

    assert report["controller_id"] == "planmargin-conservative-idm-v1"
    assert report["role"] == "reference"
    assert report["implementation"] == "Waymax IDMRoutePolicy"
    assert report["parameters"]["safe_time_headway_s"] == 3.0
    assert report["parameters"]["lookahead_from_current_position"] is True
    assert report["parameters"]["invalidate_on_end"] is False


def test_trace_hash_is_deterministic_and_content_sensitive() -> None:
    trace = {"timestep": [10, 11], "x_m": [1.0, 2.0]}

    first = controller_comparison._trace_hash(trace)
    second = controller_comparison._trace_hash(trace)
    changed = controller_comparison._trace_hash(
        {"timestep": [10, 11], "x_m": [1.0, 2.1]}
    )

    assert first == second
    assert first != changed


def test_trace_completeness_checks_every_field() -> None:
    complete = {"timestep": [10, 11], "x_m": [1.0, 2.0]}
    incomplete = {"timestep": [10, 11], "x_m": [1.0]}

    assert controller_comparison.trace_is_complete(complete, 2) is True
    assert controller_comparison.trace_is_complete(incomplete, 2) is False
    assert controller_comparison.trace_is_complete({}, 0) is False


def test_command_summary_does_not_echo_private_report_content() -> None:
    report = {
        "status": "passed",
        "dataset": {"scenario_id": "private-scenario-id"},
        "scene_context": {"roadgraph_features": [{"x_m": [1.0, 2.0]}]},
        "rollouts": {
            variant: {role: {"trajectory": {}} for role in ("tested", "reference")}
            for variant in ("original", "mutated")
        },
    }

    summary = controller_comparison._command_summary(
        report, Path("artifacts/stage-0/controller-comparison.json")
    )

    assert summary == {
        "status": "passed",
        "rollout_count": 4,
        "scene_context_exported": True,
        "output": "artifacts/stage-0/controller-comparison.json",
    }
    assert "private-scenario-id" not in str(summary)


def _synthetic_scenario(*, target_offset: float) -> SimpleNamespace:
    steps = 91
    x = np.zeros((2, steps), dtype=np.float32)
    y = np.zeros((2, steps), dtype=np.float32)
    x[0] = np.linspace(0.0, 20.0, steps)
    x[1] = np.linspace(4.0 + target_offset, 24.0 + target_offset, steps)
    y[1] = 2.0
    trajectory = SimpleNamespace(
        x=x,
        y=y,
        yaw=np.zeros((2, steps), dtype=np.float32),
        length=np.full((2, steps), 4.5, dtype=np.float32),
        width=np.full((2, steps), 2.0, dtype=np.float32),
        valid=np.ones((2, steps), dtype=bool),
    )
    roadgraph = SimpleNamespace(
        x=np.array([-5.0, 0.0, 5.0, 50.0, 10.0, 15.0]),
        y=np.zeros(6),
        ids=np.array([1, 1, 1, 1, 1, 1]),
        types=np.array([2, 2, 2, 2, 2, 2]),
        valid=np.ones(6, dtype=bool),
    )
    metadata = SimpleNamespace(
        is_sdc=np.array([True, False]),
        object_types=np.array([1, 1]),
    )
    return SimpleNamespace(
        log_trajectory=trajectory,
        roadgraph_points=roadgraph,
        object_metadata=metadata,
    )


def test_scene_context_aligns_roadgraph_and_mutation_target_tracks() -> None:
    original = _synthetic_scenario(target_offset=0.0)
    mutated = _synthetic_scenario(target_offset=1.0)
    trace = {
        "x_m": [0.0, 20.0],
        "y_m": [0.0, 0.0],
        "valid": [True, True],
    }
    rollouts = {
        variant: {
            role: {"trajectory": trace}
            for role in ("tested", "reference")
        }
        for variant in ("original", "mutated")
    }

    context = controller_comparison.build_scene_context(
        original, mutated, 1, rollouts
    )

    assert context["units"] == "meters"
    assert context["roadgraph_features"] == [
        {
            "feature_type": 2,
            "x_m": [-5.0, 0.0, 5.0],
            "y_m": [0.0, 0.0, 0.0],
        },
        {
            "feature_type": 2,
            "x_m": [10.0, 15.0],
            "y_m": [0.0, 0.0],
        },
    ]
    target = context["actors"]["mutation_target"]
    assert target["counterfactual"]["x_m"][0] == (
        target["original"]["x_m"][0] + 1.0
    )
    assert all(
        "feature_id" not in feature
        for feature in context["roadgraph_features"]
    )
