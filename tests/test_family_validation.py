"""Data-free tests for the lead-braking family evaluation contract."""

from pathlib import Path

from planmargin import family_validation


def _controller(
    *, changed: bool = True, separation: float = 1.0, ttc: float = 2.0
) -> dict[str, object]:
    return {
        "outputs_identical": True,
        "changed_from_original": changed,
        "outcome": {"success": True},
        "interaction_metrics": {
            "minimum_signed_separation_m": separation,
            "minimum_longitudinal_ttc_s": ttc,
        },
    }


def _attempt(
    *,
    identity: bool,
    separation: float,
    changed: bool = True,
    status: str = "accepted",
) -> dict[str, object]:
    return {
        "identity_control": identity,
        "status": status,
        "scenario_validation": {"outputs_identical": True},
        "controllers": {
            "tested": _controller(
                changed=changed, separation=separation
            ),
            "reference": _controller(
                changed=changed, separation=separation + 1.0
            ),
        },
    }


def _passing_input() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    scenarios = []
    attempts = []
    for _ in range(10):
        scenario_attempts = [
            _attempt(identity=True, separation=2.0, changed=False),
            _attempt(identity=False, separation=1.0),
        ]
        scenarios.append(
            {
                "original": {"eligible": True},
                "attempts": scenario_attempts,
            }
        )
        attempts.extend(scenario_attempts)
    return scenarios, attempts


def test_parameter_grid_is_fixed_and_contains_identity() -> None:
    grid = family_validation.parameter_grid()

    assert len(grid) == 9
    assert grid[0] == (0.0, 0.75)
    assert grid[-1] == (0.5, 1.0)
    assert (0.0, 1.0) in grid


def test_passing_family_evaluation_returns_go() -> None:
    scenarios, attempts = _passing_input()

    result = family_validation.evaluate_family(scenarios, attempts)

    assert result["decision"] == "go"
    assert all(result["gates"].values())
    assert result["metrics"]["eligible_scenario_count"] == 10
    assert result["metrics"]["varying_scenario_count"] == 10


def test_family_gate_failure_returns_no_go_without_hiding_metrics() -> None:
    scenarios, attempts = _passing_input()
    for scenario in scenarios[:3]:
        scenario["original"]["eligible"] = False
    for attempt in attempts:
        if not attempt["identity_control"]:
            attempt["controllers"]["tested"]["changed_from_original"] = False

    result = family_validation.evaluate_family(scenarios, attempts)

    assert result["decision"] == "no_go"
    assert result["gates"]["eligible_scenarios"] is False
    assert result["gates"]["tested_controller_response_rate"] is False
    assert result["metrics"]["eligible_scenario_count"] == 7


def test_public_summary_excludes_private_scenario_records() -> None:
    report = {
        "status": "completed",
        "evaluation": {
            "decision": "go",
            "metrics": {
                "scenario_count": 10,
                "attempt_count": 90,
            },
        },
        "scenarios": [{"scenario_id": "private-id"}],
    }

    summary = family_validation.public_summary(
        report, Path("artifacts/family-validation/report.json")
    )

    assert summary == {
        "status": "completed",
        "decision": "go",
        "scenario_count": 10,
        "attempt_count": 90,
        "output": "artifacts/family-validation/report.json",
    }
    assert "private-id" not in str(summary)
