"""Prepare just the licensed scenario selection, without running the research program."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from planmargin.experiment_jobs import MANIFEST, confined, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--accept-waymo-terms",
        action="store_true",
        help="Confirm you have reviewed Waymo's dataset terms and authorized access.",
    )
    args = parser.parse_args()
    if not args.accept_waymo_terms:
        parser.error(
            "Review https://waymo.com/open/terms/ and authorize WOD access before using --accept-waymo-terms."
        )
    from planmargin import family_validation, scenario_selection

    path = confined(Path.cwd().resolve(), MANIFEST)
    if path.exists():
        family_validation.load_manifest_candidates(path)
        print("Existing ten-scenario selection verified; no inputs overwritten.")
    else:
        print(
            "Selecting ten real lead-braking scenarios from authorized WOMD training data…",
            flush=True,
        )
        report = scenario_selection.select_scenarios(
            start_shard=0, max_shards=12, target_count=10, left_turn_probe_shards=1
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        # Incomplete selections must never become the reusable workspace input.
        with tempfile.TemporaryDirectory(
            prefix="planning-selection-", dir=path.parent
        ) as staging:
            staged = Path(staging) / "selection.json"
            write_json(staged, report)
            family_validation.load_manifest_candidates(staged)
            staged.replace(path)
        print(
            "Ten real scenarios selected. Raw source data remains licensed and local."
        )
    print("Next: uv run --frozen planmargin-workbench --planning-only")
    print(
        "Empirical support is optional for execution, but required to qualify a regression. See docs/running-experiments.md."
    )
