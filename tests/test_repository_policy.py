"""Data-free checks for repository artifact boundaries."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).parents[1]


def test_per_scenario_womd_reports_are_not_committed() -> None:
    prohibited_reports = (
        REPOSITORY_ROOT
        / "experiments"
        / "stage-0"
        / "scenario-selection.json",
        REPOSITORY_ROOT
        / "experiments"
        / "stage-0"
        / "waymax-smoke-test.json",
        REPOSITORY_ROOT
        / "experiments"
        / "stage-0"
        / "speed-mutation-smoke-test.json",
        REPOSITORY_ROOT
        / "experiments"
        / "stage-0"
        / "controller-comparison.json",
    )

    assert all(not path.exists() for path in prohibited_reports)
