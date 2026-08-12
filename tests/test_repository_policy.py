"""Data-free checks for repository artifact boundaries."""

import subprocess
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
        REPOSITORY_ROOT
        / "experiments"
        / "stage-0"
        / "rollout-records.json",
        REPOSITORY_ROOT
        / "experiments"
        / "stage-0"
        / "trajectory-comparison.html",
        REPOSITORY_ROOT
        / "experiments"
        / "realism"
        / "lead-braking-support-v1"
        / "model.json",
        REPOSITORY_ROOT
        / "experiments"
        / "realism"
        / "lead-braking-support-v1"
        / "shards",
        REPOSITORY_ROOT
        / "artifacts"
        / "search-comparison",
    )

    tracked = subprocess.run(
        [
            "git",
            "ls-files",
            "--",
            *(str(path.relative_to(REPOSITORY_ROOT)) for path in prohibited_reports),
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    assert tracked == []
