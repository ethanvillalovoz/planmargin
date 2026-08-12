"""Run the frozen one-scenario, two-proposal private integration smoke test."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, NoReturn

from planmargin import empirical_support
from planmargin import family_validation
from planmargin import matched_coordinator
from planmargin import matched_search
from planmargin import matched_waymax
from planmargin import random_search

DEFAULT_MANIFEST = family_validation.DEFAULT_MANIFEST
DEFAULT_SUPPORT_MODEL = Path(
    "artifacts/realism/lead-braking-support-v1-00c3727/model.json"
)
DEFAULT_OUTPUT_DIR = Path("artifacts/search-comparison/private-integration-smoke")
SMOKE_CELL = matched_coordinator.CellConfig("random", "natural", 0, 1)
SMOKE_PROPOSAL_COUNT = 2
EXPECTED_ATTEMPT_STAGES = (
    "mutation",
    "scenario_validation",
    "feature_extraction",
    "support_scoring",
    "tested_controller",
    "reference_controller",
)


def _fail_evaluator(*args: Any, **kwargs: Any) -> NoReturn:
    del args, kwargs
    raise AssertionError("bounded resume repeated evaluator work")


def _load_proposals(output_dir: Path) -> list[dict[str, Any]]:
    proposals = []
    for index in range(SMOKE_PROPOSAL_COUNT):
        path = matched_coordinator._proposal_path(output_dir, index)
        proposals.append(random_search._read_json_object(path))
    return proposals


def _verify_records(
    output_dir: Path,
    proposals: list[dict[str, Any]],
) -> None:
    if len(proposals) != SMOKE_PROPOSAL_COUNT:
        raise RuntimeError("Smoke test did not produce exactly two proposals")
    for index, proposal in enumerate(proposals):
        expected = matched_search.random_parameters(
            seed=SMOKE_CELL.seed,
            selection_order=SMOKE_CELL.selection_order,
            proposal_index=index,
        )
        if proposal["identity"]["proposal_index"] != index:
            raise RuntimeError("Smoke proposal indices are not sequential")
        if proposal["proposal"]["parameters"] != {
            "braking_onset_offset_s": expected[0],
            "speed_multiplier": expected[1],
        }:
            raise RuntimeError("Smoke proposal does not match the frozen sequence")
        if proposal["attempt"]["status"] == "accepted" and (
            proposal["attempt"]["controllers"] is None
        ):
            raise RuntimeError("Accepted smoke proposal lacks controller evidence")
        selection = random_search._read_json_object(
            matched_coordinator._selection_path(output_dir, index)
        )
        if proposal["selection_sha256"] != selection["selection_sha256"]:
            raise RuntimeError("Smoke proposal selection link is invalid")


def _verify_order(events: tuple[dict[str, int | str], ...]) -> None:
    by_attempt: dict[int, list[str]] = {}
    for event in events:
        attempt_index = event["attempt_index"]
        stage = event["stage"]
        if not isinstance(attempt_index, int) or not isinstance(stage, str):
            raise RuntimeError("Adapter emitted an invalid ordering event")
        by_attempt.setdefault(attempt_index, []).append(stage)
    if set(by_attempt) != set(range(SMOKE_PROPOSAL_COUNT)):
        raise RuntimeError("Adapter did not observe exactly two attempts")
    for stages in by_attempt.values():
        if tuple(stages) != EXPECTED_ATTEMPT_STAGES:
            raise RuntimeError("Private evaluator stage order violated the contract")


def run(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    support_model_path: Path = DEFAULT_SUPPORT_MODEL,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Execute two real proposals, then prove bounded resume repeats no evaluation."""
    matched_coordinator.validate_private_output_dir(output_dir)
    empirical_support.load_model(support_model_path)
    adapter = matched_waymax.WaymaxEvaluatorAdapter()
    first = matched_coordinator.run(
        manifest_path=manifest_path,
        support_model_path=support_model_path,
        output_dir=output_dir,
        cell=SMOKE_CELL,
        max_new_proposals=SMOKE_PROPOSAL_COUNT,
        original_evaluator=adapter.evaluate_original,
        attempt_evaluator=adapter.evaluate_attempt,
    )
    if (
        first.get("status") != "in_progress"
        or first.get("completed_proposal_count") != SMOKE_PROPOSAL_COUNT
        or first.get("new_proposal_count") != SMOKE_PROPOSAL_COUNT
    ):
        raise RuntimeError("Coordinator exceeded or missed the bounded smoke budget")
    proposals = _load_proposals(output_dir)
    _verify_records(output_dir, proposals)
    _verify_order(adapter.events)

    resumed = matched_coordinator.run(
        manifest_path=manifest_path,
        support_model_path=support_model_path,
        output_dir=output_dir,
        cell=SMOKE_CELL,
        resume=True,
        max_new_proposals=0,
        original_evaluator=_fail_evaluator,
        attempt_evaluator=_fail_evaluator,
    )
    if (
        resumed.get("completed_proposal_count") != SMOKE_PROPOSAL_COUNT
        or resumed.get("new_proposal_count") != 0
    ):
        raise RuntimeError("Bounded resume did not preserve the smoke checkpoints")

    statuses = Counter(proposal["attempt"]["status"] for proposal in proposals)
    accepted = [
        proposal for proposal in proposals if proposal["attempt"]["status"] == "accepted"
    ]
    return {
        "status": "passed",
        "scope": "one_scenario_two_proposals",
        "method": SMOKE_CELL.method,
        "track": SMOKE_CELL.track,
        "seed": SMOKE_CELL.seed,
        "selection_order": SMOKE_CELL.selection_order,
        "proposal_count": len(proposals),
        "status_counts": dict(sorted(statuses.items())),
        "feature_accepted_count": sum(
            bool(proposal["feature"] and proposal["feature"]["accepted"])
            for proposal in proposals
        ),
        "support_pass_count": sum(
            bool(proposal["support"] and proposal["support"]["passes"])
            for proposal in proposals
        ),
        "controller_evaluated_proposal_count": sum(
            proposal["attempt"]["controllers"] is not None for proposal in proposals
        ),
        "ordering_verified_attempt_count": SMOKE_PROPOSAL_COUNT,
        "resume_repeated_evaluation_count": 0,
        "total_physical_rollouts": sum(
            proposal["cost"]["total_physical_rollouts"] for proposal in proposals
        ),
        "output": str(output_dir),
        "limitations": [
            "Integration evidence only; the production cell budget remains 32.",
            "No search-performance, planner-performance, H1, H2, or H3 claim follows.",
        ],
        "accepted_proposal_count": len(accepted),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--support-model", type=Path, default=DEFAULT_SUPPORT_MODEL
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = run(
        manifest_path=args.manifest,
        support_model_path=args.support_model,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
