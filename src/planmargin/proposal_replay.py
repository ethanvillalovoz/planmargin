"""Re-execute one sealed campaign proposal and retain its exact trajectories."""

from __future__ import annotations

import argparse
import copy
import json
import platform
import tempfile
import time
from pathlib import Path
from typing import Any

import jax
import tensorflow as tf

from planmargin import controller_comparison
from planmargin import family_validation
from planmargin import lead_braking
from planmargin import matched_campaign
from planmargin import matched_coordinator
from planmargin import random_search
from planmargin import rollout_record
from planmargin import scenario_selection
from planmargin import speed_mutation

SCHEMA_VERSION = "1.0.0"
SCHEMA_BASE_URI = (
    "https://raw.githubusercontent.com/ethanvillalovoz/planmargin/main/schemas"
)
MANIFEST_SCHEMA_URI = f"{SCHEMA_BASE_URI}/proposal-replay-manifest-v1.schema.json"
MANIFEST_TYPE = "planmargin.proposal_replay_manifest"
DEFAULT_CAMPAIGN = Path("artifacts/search-comparison/natural-development-v1")
DEFAULT_OUTPUT_ROOT = Path("artifacts/proposal-replays/natural-development-v1")
VERIFICATION_KEYS = frozenset(
    {
        "proposal_record_seal_verified",
        "source_scenario_identity_verified",
        "mutation_parameters_match",
        "scenario_validation_matches",
        "original_tested_matches_v1",
        "original_reference_matches_v1",
        "counterfactual_tested_matches_v1",
        "counterfactual_reference_matches_v1",
        "all_replays_deterministic",
        "inputs_unchanged_by_replay",
    }
)


def replay_directory(
    output_root: Path,
    *,
    method: str,
    seed: int,
    selection_order: int,
    proposal_number: int,
) -> Path:
    """Return the stable ignored location for one retained replay."""
    return (
        output_root
        / method
        / f"seed-{seed}"
        / f"scenario-{selection_order:02d}"
        / f"proposal-{proposal_number:04d}"
    )


def _load_campaign_records(
    campaign_root: Path,
    *,
    method: str,
    seed: int,
    selection_order: int,
    proposal_number: int,
) -> tuple[
    matched_coordinator.CellConfig,
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    if not 1 <= proposal_number <= 32:
        raise ValueError("proposal_number must be between 1 and 32")
    cell = matched_coordinator.CellConfig(method, "natural", seed, selection_order)
    directory = matched_campaign.cell_output_dir(campaign_root, cell)
    run_manifest_raw = random_search._read_json_object(directory / "run-manifest.json")
    fingerprint = run_manifest_raw.get("configuration_fingerprint")
    run_manifest = matched_coordinator._load_sealed_record(
        directory / "run-manifest.json",
        record_type=matched_coordinator.MANIFEST_TYPE,
        seal_field="manifest_sha256",
        fingerprint=fingerprint,
        cell=cell,
        proposal_index=None,
    )
    original = matched_coordinator._load_sealed_record(
        directory / "original.json",
        record_type=matched_coordinator.ORIGINAL_TYPE,
        seal_field="checkpoint_sha256",
        fingerprint=fingerprint,
        cell=cell,
        proposal_index=None,
    )
    proposal = matched_coordinator._load_sealed_record(
        directory / "proposals" / f"proposal-{proposal_number - 1:04d}.json",
        record_type=matched_coordinator.PROPOSAL_TYPE,
        seal_field="record_sha256",
        fingerprint=fingerprint,
        cell=cell,
        proposal_index=proposal_number - 1,
    )
    return cell, run_manifest, original, proposal


def _scientific_controller_view(record: dict[str, Any]) -> dict[str, Any]:
    """Drop runtime-only timings before comparing a fresh run to v1."""
    return {
        key: copy.deepcopy(record[key])
        for key in (
            "outputs_identical",
            "trajectory_sha256",
            "changed_from_original",
            "outcome",
            "interaction_metrics",
        )
    }


def _scientific_evidence(
    original_checkpoint: dict[str, Any], proposal: dict[str, Any]
) -> dict[str, Any]:
    """Return the sealed campaign facts an exact replay must reproduce."""
    return {
        "scenario": copy.deepcopy(proposal["scenario"]),
        "mutation": copy.deepcopy(proposal["attempt"]["mutation"]),
        "scenario_validation": copy.deepcopy(
            proposal["attempt"]["scenario_validation"]
        ),
        "controllers": {
            "original": {
                role: _scientific_controller_view(record)
                for role, record in original_checkpoint["original"][
                    "controllers"
                ].items()
            },
            "counterfactual": {
                role: _scientific_controller_view(record)
                for role, record in proposal["attempt"]["controllers"].items()
            },
        },
        "finding": copy.deepcopy(proposal.get("finding") or {}),
    }


def _scientific_evidence_sha256(
    original_checkpoint: dict[str, Any], proposal: dict[str, Any]
) -> str:
    return random_search._content_sha256(
        _scientific_evidence(original_checkpoint, proposal)
    )


def validate_retained_collection(
    *,
    manifest: dict[str, Any],
    collection: dict[str, Any],
    original_checkpoint: dict[str, Any],
    proposal: dict[str, Any],
) -> None:
    """Prove that one retained collection is the linked sealed proposal replay."""
    verification = manifest.get("verification")
    if (
        not isinstance(verification, dict)
        or set(verification) != VERIFICATION_KEYS
        or any(value is not True for value in verification.values())
    ):
        raise ValueError("Proposal replay verification contract is incomplete")
    expected_evidence = _scientific_evidence(original_checkpoint, proposal)
    if manifest.get("scientific_evidence_sha256") != random_search._content_sha256(
        expected_evidence
    ):
        raise ValueError("Proposal replay scientific evidence does not match campaign")

    raw_records = collection.get("records")
    if (
        not isinstance(raw_records, list)
        or len(raw_records) != 4
        or any(not isinstance(record, dict) for record in raw_records)
    ):
        raise ValueError("Proposal replay must contain exactly four controller records")
    records = {
        (record.get("variant"), record.get("controller_role")): record
        for record in raw_records
    }
    expected_keys = {
        (variant, role)
        for variant in ("original", "counterfactual")
        for role in ("tested", "reference")
    }
    if set(records) != expected_keys:
        raise ValueError("Proposal replay must contain exactly four controller records")
    if collection.get("comparison_finding") != expected_evidence["finding"]:
        raise ValueError("Proposal replay finding does not match campaign")

    expected_scenario = expected_evidence["scenario"]
    scenario_fields = (
        "scenario_id",
        "source_shard",
        "record_index",
        "selection_order",
        "mutated_object_index",
    )
    expected_mutation = expected_evidence["mutation"]
    for (variant, role), record in records.items():
        scenario = record.get("scenario")
        if not isinstance(scenario, dict) or any(
            scenario.get(field) != expected_scenario.get(field)
            for field in scenario_fields
        ):
            raise ValueError("Proposal replay scenario does not match campaign")
        mutation = record.get("mutation")
        if not isinstance(mutation, dict) or any(
            mutation.get(field) != value for field, value in expected_mutation.items()
        ):
            raise ValueError("Proposal replay mutation does not match campaign")
        if mutation.get("applied") is not (variant == "counterfactual"):
            raise ValueError("Proposal replay mutation application is inconsistent")
        if record.get("acceptance_gate_results") != verification:
            raise ValueError(
                "Proposal replay record verification gates are inconsistent"
            )

        expected_controller = expected_evidence["controllers"][variant][role]
        reproducibility = record.get("reproducibility")
        if not isinstance(reproducibility, dict) or any(
            reproducibility.get(field) != expected_controller[field]
            for field in ("outputs_identical", "trajectory_sha256")
        ):
            raise ValueError("Proposal replay trajectory does not match campaign")
        if record.get("outcome") != expected_controller["outcome"]:
            raise ValueError("Proposal replay outcome does not match campaign")

        original_hash = expected_evidence["controllers"]["original"][role][
            "trajectory_sha256"
        ]
        changed_from_original = (
            None
            if variant == "original"
            else reproducibility["trajectory_sha256"] != original_hash
        )
        if changed_from_original != expected_controller["changed_from_original"]:
            raise ValueError(
                "Proposal replay trajectory change does not match campaign"
            )


def _run_variant(
    scenario: Any,
    *,
    object_index: int,
    runners: dict[str, controller_comparison.ControllerRunner],
    original_hashes: dict[str, str | None],
) -> tuple[dict[str, Any], dict[str, Any]]:
    rollouts: dict[str, Any] = {}
    scientific: dict[str, Any] = {}
    for role, runner in runners.items():
        before_hash = controller_comparison._non_sdc_log_hash(scenario)
        rollout = runner.run_twice(scenario)
        after_hash = controller_comparison._non_sdc_log_hash(scenario)
        rollout["non_sdc_input_sha256"] = before_hash
        rollout["input_unchanged_after_rollout"] = before_hash == after_hash
        rollouts[role] = rollout
        scientific[role] = family_validation._controller_record(
            scenario,
            object_index,
            rollout,
            original_hashes[role],
        )
    return rollouts, scientific


def _comparison_source(
    *,
    manifest_path: Path,
    cell: matched_coordinator.CellConfig,
    original_checkpoint: dict[str, Any],
    proposal: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    scenario, candidate = matched_coordinator._load_cell_scenario(
        manifest_path, cell.selection_order
    )
    object_index = candidate["interacting_object_index"]
    parameters = proposal["proposal"]["parameters"]
    mutation_config = lead_braking.LeadBrakingMutationConfig(
        braking_onset_offset_s=parameters["braking_onset_offset_s"],
        speed_multiplier=parameters["speed_multiplier"],
    )
    mutated_scenario, mutation = lead_braking.apply_lead_braking_mutation(
        scenario, object_index, mutation_config
    )
    if mutated_scenario is None or not mutation.accepted:
        raise ValueError("The sealed proposal cannot produce a replayable mutation")
    validation = speed_mutation.MutationValidator(
        require_mutated_object_valid_all_steps=False
    ).validate(mutated_scenario, object_index)
    if not validation["accepted"]:
        raise ValueError("The sealed proposal does not pass scenario validation")

    tested = matched_coordinator.tested_controller_for_track(cell.track)
    controller_specs = {
        "tested": tested,
        "reference": controller_comparison.REFERENCE_CONTROLLER,
    }
    runners = {
        role: controller_comparison.ControllerRunner(spec)
        for role, spec in controller_specs.items()
    }
    empty_hashes: dict[str, str | None] = {"tested": None, "reference": None}
    original_rollouts, original_scientific = _run_variant(
        scenario,
        object_index=object_index,
        runners=runners,
        original_hashes=empty_hashes,
    )
    original_hashes = {
        role: record["trajectory_sha256"]
        for role, record in original_scientific.items()
    }
    mutated_rollouts, mutated_scientific = _run_variant(
        mutated_scenario,
        object_index=object_index,
        runners=runners,
        original_hashes=original_hashes,
    )

    expected_original = original_checkpoint["original"]["controllers"]
    expected_mutated = proposal["attempt"]["controllers"]
    mutation_record = mutation.report(mutation_config)
    mutation_record["parameters"] = dict(parameters)
    checks = {
        "proposal_record_seal_verified": True,
        "source_scenario_identity_verified": (
            candidate["selection_order"] == cell.selection_order
            and proposal["scenario"] == random_search._scenario_descriptor(candidate)
        ),
        "mutation_parameters_match": mutation_record["parameters"] == parameters,
        "scenario_validation_matches": validation
        == proposal["attempt"]["scenario_validation"],
        "original_tested_matches_v1": _scientific_controller_view(
            original_scientific["tested"]
        )
        == _scientific_controller_view(expected_original["tested"]),
        "original_reference_matches_v1": _scientific_controller_view(
            original_scientific["reference"]
        )
        == _scientific_controller_view(expected_original["reference"]),
        "counterfactual_tested_matches_v1": _scientific_controller_view(
            mutated_scientific["tested"]
        )
        == _scientific_controller_view(expected_mutated["tested"]),
        "counterfactual_reference_matches_v1": _scientific_controller_view(
            mutated_scientific["reference"]
        )
        == _scientific_controller_view(expected_mutated["reference"]),
        "all_replays_deterministic": all(
            rollout["outputs_identical"]
            for variant in (original_rollouts, mutated_rollouts)
            for rollout in variant.values()
        ),
        "inputs_unchanged_by_replay": all(
            rollout["input_unchanged_after_rollout"]
            for variant in (original_rollouts, mutated_rollouts)
            for rollout in variant.values()
        ),
    }
    if not all(checks.values()):
        failed = ", ".join(name for name, passed in checks.items() if not passed)
        raise RuntimeError(
            f"Proposal replay did not reproduce sealed v1 evidence: {failed}"
        )

    finding = copy.deepcopy(proposal["finding"] or {})
    source = {
        "schema_version": 1,
        "status": "passed",
        "dataset": {
            "name": "Waymo Open Motion Dataset",
            "version": scenario_selection.DATASET_VERSION,
            "split": scenario_selection.SPLIT,
            "scenario_id": candidate["scenario_id"],
            "source_shard": candidate["source_shard"],
            "record_index": candidate["record_index"],
            "selection_order": candidate["selection_order"],
            "mutated_object_index": object_index,
        },
        "mutation": mutation_record,
        "controllers": {role: spec.report() for role, spec in controller_specs.items()},
        "metric_definition": {
            "success_requires": [
                "zero SDC overlap",
                "zero SDC offroad",
                "valid SDC at every step",
                "complete 80-step rollout",
            ],
            "reproduction_requires": [
                "trajectory hashes match the sealed campaign proposal",
                "outcomes and interaction metrics match the sealed campaign proposal",
                "both physical executions are identical",
            ],
        },
        "acceptance": checks,
        "finding": finding,
        "rollouts": {
            "original": original_rollouts,
            "mutated": mutated_rollouts,
        },
        "scene_context": controller_comparison.build_scene_context(
            scenario,
            mutated_scenario,
            object_index,
            {"original": original_rollouts, "mutated": mutated_rollouts},
        ),
        "environment": {
            **scenario_selection._git_provenance(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "jax": jax.__version__,
            "tensorflow": tf.__version__,
            "jax_backend": jax.default_backend(),
            "waymax_git_commit": scenario_selection.WAYMAX_GIT_COMMIT,
            "comparison_source_sha256": random_search._file_sha256(Path(__file__)),
            "seed": scenario_selection.SEED,
        },
        "limitations": [
            "This replay reproduces one selected development proposal; it does not alter the frozen v1 campaign.",
            "The reference is a technical baseline, not a production Waymo Driver or human-driver model.",
            "The replay remains a licensed local artifact and is not approved for redistribution.",
        ],
        "total_seconds": round(time.perf_counter() - started, 6),
    }
    return source, checks


def export(
    *,
    manifest_path: Path = family_validation.DEFAULT_MANIFEST,
    campaign_root: Path = DEFAULT_CAMPAIGN,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    method: str,
    seed: int,
    selection_order: int,
    proposal_number: int,
) -> dict[str, Any]:
    """Re-execute and atomically retain one proposal-linked replay package."""
    allowed_root = (Path.cwd() / "artifacts" / "proposal-replays").resolve()
    if not output_root.resolve().is_relative_to(allowed_root):
        raise ValueError(
            "proposal replay output must remain under artifacts/proposal-replays"
        )
    directory = replay_directory(
        output_root,
        method=method,
        seed=seed,
        selection_order=selection_order,
        proposal_number=proposal_number,
    )
    if directory.exists():
        raise FileExistsError(
            "Proposal replay already exists; remove it deliberately before re-exporting"
        )
    cell, run_manifest, original, proposal = _load_campaign_records(
        campaign_root,
        method=method,
        seed=seed,
        selection_order=selection_order,
        proposal_number=proposal_number,
    )
    if proposal["attempt"]["status"] != "accepted":
        raise ValueError("Only an accepted proposal can be retained as an exact replay")
    source, checks = _comparison_source(
        manifest_path=manifest_path,
        cell=cell,
        original_checkpoint=original,
        proposal=proposal,
    )
    collection = rollout_record.export_collection(source)
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{directory.name}.", dir=directory.parent
    ) as temporary_name:
        temporary = Path(temporary_name)
        collection_path = temporary / "collection.json"
        random_search._atomic_write_json(collection_path, collection)
        manifest = random_search._seal_record(
            {
                "$schema": MANIFEST_SCHEMA_URI,
                "schema_version": SCHEMA_VERSION,
                "record_type": MANIFEST_TYPE,
                "campaign_id": matched_campaign.CAMPAIGN_ID,
                "identity": {
                    "method": method,
                    "track": "natural",
                    "seed": seed,
                    "selection_order": selection_order,
                    "proposal_number": proposal_number,
                },
                "proposal_record_sha256": proposal["record_sha256"],
                "cell_configuration_fingerprint": run_manifest[
                    "configuration_fingerprint"
                ],
                "scientific_evidence_sha256": _scientific_evidence_sha256(
                    original, proposal
                ),
                "collection_file": "collection.json",
                "collection_sha256": random_search._file_sha256(collection_path),
                "verification": checks,
                "privacy": {
                    "contains_restricted_scenario_derivatives": True,
                    "unrestricted_export": False,
                },
            },
            "manifest_sha256",
        )
        random_search._atomic_write_json(temporary / "manifest.json", manifest)
        temporary.replace(directory)
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=family_validation.DEFAULT_MANIFEST
    )
    parser.add_argument("--campaign-root", type=Path, default=DEFAULT_CAMPAIGN)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--method", choices=("random", "bayesian"), required=True)
    parser.add_argument("--seed", type=int, choices=range(5), required=True)
    parser.add_argument(
        "--selection-order", type=int, choices=range(1, 11), required=True
    )
    parser.add_argument(
        "--proposal-number", type=int, choices=range(1, 33), required=True
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = export(
        manifest_path=args.manifest,
        campaign_root=args.campaign_root,
        output_root=args.output_root,
        method=args.method,
        seed=args.seed,
        selection_order=args.selection_order,
        proposal_number=args.proposal_number,
    )
    print(
        json.dumps(
            {
                "status": "verified",
                "identity": manifest["identity"],
                "proposal_record_sha256": manifest["proposal_record_sha256"],
                "manifest_sha256": manifest["manifest_sha256"],
                "unrestricted_export": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
