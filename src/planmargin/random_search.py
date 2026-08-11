"""Run the deterministic uniform-random lead-braking search baseline."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import os
import platform
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import jax
import numpy as np
import tensorflow as tf

from planmargin import controller_comparison
from planmargin import family_validation
from planmargin import lead_braking
from planmargin import scenario_selection
from planmargin import speed_mutation

SCHEMA_VERSION = "1.0.0"
SCHEMA_BASE_URI = (
    "https://raw.githubusercontent.com/ethanvillalovoz/planmargin/main/schemas"
)
RUN_MANIFEST_SCHEMA_URI = f"{SCHEMA_BASE_URI}/random-search-run-manifest-v1.schema.json"
ORIGINAL_SCHEMA_URI = f"{SCHEMA_BASE_URI}/random-search-original-v1.schema.json"
PROPOSAL_SCHEMA_URI = f"{SCHEMA_BASE_URI}/random-search-proposal-v1.schema.json"
REPORT_SCHEMA_URI = f"{SCHEMA_BASE_URI}/random-search-report-v1.schema.json"
RUN_MANIFEST_TYPE = "planmargin.random_search_run_manifest"
ORIGINAL_TYPE = "planmargin.random_search_original_checkpoint"
PROPOSAL_TYPE = "planmargin.random_search_proposal"
REPORT_TYPE = "planmargin.random_search_report"

DEFAULT_MANIFEST = family_validation.DEFAULT_MANIFEST
DEFAULT_OUTPUT_DIR = Path("artifacts/random-search/lead-braking-baseline")
DEFAULT_SEED = 0
DEFAULT_BUDGET = 32
ONSET_OFFSETS_S = tuple(round(index * 0.1, 1) for index in range(6))
MIN_SPEED_MULTIPLIER = 0.75
MAX_SPEED_MULTIPLIER = 1.0
ROLES = ("tested", "reference")

CostRecord = dict[str, int]
OriginalEvaluator = Callable[[Any, dict[str, Any], dict[str, Any]], dict[str, Any]]
AttemptEvaluator = Callable[
    [
        Any,
        dict[str, Any],
        float,
        float,
        dict[str, Any],
        Any,
        dict[str, Any],
    ],
    dict[str, Any],
]


@dataclass(frozen=True)
class RandomSearchConfig:
    """Frozen proposal-sequence configuration for one baseline run."""

    seed: int = DEFAULT_SEED
    budget_per_scenario: int = DEFAULT_BUDGET

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed must be an integer")
        if (
            isinstance(self.budget_per_scenario, bool)
            or not isinstance(self.budget_per_scenario, int)
            or self.budget_per_scenario < 1
        ):
            raise ValueError("budget_per_scenario must be a positive integer")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _content_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _seal_record(record: dict[str, Any], hash_field: str) -> dict[str, Any]:
    sealed = dict(record)
    sealed[hash_field] = _content_sha256(record)
    return sealed


def _validate_seal(
    record: dict[str, Any], hash_field: str, *, path: Path
) -> None:
    expected = record.get(hash_field)
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError(f"Checkpoint is missing {hash_field}: {path}")
    payload = dict(record)
    del payload[hash_field]
    if _content_sha256(payload) != expected:
        raise ValueError(f"Checkpoint content hash mismatch: {path}")


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    """Durably replace one strict-JSON checkpoint in its target directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    value,
                    allow_nan=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Checkpoint is unreadable: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Checkpoint root must be an object: {path}")
    return value


def validate_private_output_dir(output_dir: Path) -> None:
    """Reject restricted checkpoint paths outside the ignored artifacts tree."""
    artifacts_root = (Path.cwd() / "artifacts").resolve()
    if not output_dir.resolve().is_relative_to(artifacts_root):
        raise ValueError(
            "Random-search records contain restricted scenario-derived data; "
            "--output-dir must remain under artifacts/."
        )


def proposal_parameters(
    config: RandomSearchConfig,
    selection_order: int,
    proposal_index: int,
) -> dict[str, float]:
    """Return one stateless PCG64 proposal keyed only by stable indices."""
    if selection_order < 1:
        raise ValueError("selection_order must be positive")
    if proposal_index < 0:
        raise ValueError("proposal_index must be non-negative")
    seed_sequence = np.random.SeedSequence(
        [config.seed, selection_order, proposal_index]
    )
    generator = np.random.Generator(np.random.PCG64(seed_sequence))
    onset_index = int(generator.integers(0, len(ONSET_OFFSETS_S)))
    speed_multiplier = MIN_SPEED_MULTIPLIER + (
        MAX_SPEED_MULTIPLIER - MIN_SPEED_MULTIPLIER
    ) * float(generator.random())
    return {
        "braking_onset_offset_s": ONSET_OFFSETS_S[onset_index],
        "speed_multiplier": speed_multiplier,
    }


def normalized_mutation_distance(parameters: dict[str, float]) -> float:
    """Return the predeclared normalized Euclidean distance from identity."""
    onset = float(parameters["braking_onset_offset_s"])
    multiplier = float(parameters["speed_multiplier"])
    return math.sqrt(
        (onset / 0.5) ** 2
        + ((1.0 - multiplier) / 0.25) ** 2
    )


def _scenario_descriptor(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "scenario_id": candidate["scenario_id"],
        "source_shard": candidate["source_shard"],
        "shard_index": candidate["shard_index"],
        "record_index": candidate["record_index"],
        "selection_order": candidate["selection_order"],
        "mutated_object_index": candidate["interacting_object_index"],
    }


def _fixed_mutation_configuration() -> dict[str, Any]:
    values = dataclasses.asdict(lead_braking.LeadBrakingMutationConfig())
    del values["braking_onset_offset_s"]
    del values["speed_multiplier"]
    return values


def build_run_manifest(
    manifest_path: Path,
    candidates: list[dict[str, Any]],
    config: RandomSearchConfig,
) -> dict[str, Any]:
    """Build the immutable private configuration and provenance manifest."""
    provenance = scenario_selection._git_provenance()
    source_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    configuration = {
        "experiment": "deterministic_uniform_random_lead_braking_baseline",
        "dataset": {
            "name": "Waymo Open Motion Dataset",
            "version": scenario_selection.DATASET_VERSION,
            "split": scenario_selection.SPLIT,
            "scenario_manifest_sha256": _file_sha256(manifest_path),
            "scenarios": [_scenario_descriptor(candidate) for candidate in candidates],
        },
        "search": {
            "method": "stateless_uniform_random_pcg64",
            "seed": config.seed,
            "budget_per_scenario": config.budget_per_scenario,
            "total_proposal_budget": len(candidates) * config.budget_per_scenario,
            "braking_onset_offsets_s": list(ONSET_OFFSETS_S),
            "minimum_speed_multiplier": MIN_SPEED_MULTIPLIER,
            "maximum_speed_multiplier": MAX_SPEED_MULTIPLIER,
            "proposal_key": ["seed", "selection_order", "proposal_index"],
            "exhaust_budget_after_finding": True,
        },
        "mutation": {
            "type": "lead_braking_onset_and_speed",
            "fixed_configuration": _fixed_mutation_configuration(),
        },
        "controllers": {
            "tested": controller_comparison.TESTED_CONTROLLER.report(),
            "reference": controller_comparison.REFERENCE_CONTROLLER.report(),
        },
        "accounting": {
            "primary_budget_unit": "proposed_parameter_pair",
            "rejected_proposals_consume_budget": True,
            "deterministic_physical_rollouts_per_logical_evaluation": 2,
            "waymax_steps_per_physical_rollout": (
                scenario_selection.NUM_FUTURE_STEPS
            ),
            "original_controller_evaluations_consume_proposal_budget": False,
        },
        "source": {
            **provenance,
            "random_search_source_sha256": source_sha256,
            "waymax_git_commit": scenario_selection.WAYMAX_GIT_COMMIT,
        },
    }
    record = {
        "$schema": RUN_MANIFEST_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": RUN_MANIFEST_TYPE,
        "configuration_fingerprint": _content_sha256(configuration),
        "configuration": configuration,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "numpy": np.__version__,
            "jax": jax.__version__,
            "tensorflow": tf.__version__,
            "jax_backend": jax.default_backend(),
        },
    }
    return _seal_record(record, "manifest_sha256")


def _original_cost() -> CostRecord:
    physical_rollouts = 4
    return {
        "core_mutation_attempts": 0,
        "scenario_validation_logical_evaluations": 0,
        "scenario_validation_physical_rollouts": 0,
        "tested_controller_logical_evaluations": 1,
        "tested_controller_physical_rollouts": 2,
        "reference_controller_logical_evaluations": 1,
        "reference_controller_physical_rollouts": 2,
        "total_physical_rollouts": physical_rollouts,
        "waymax_rollout_steps": (
            physical_rollouts * scenario_selection.NUM_FUTURE_STEPS
        ),
    }


def proposal_cost(attempt: dict[str, Any]) -> CostRecord:
    """Derive exact logical and physical simulator accounting for one attempt."""
    scenario_evaluated = attempt.get("scenario_validation") is not None
    controllers_evaluated = attempt.get("status") == "accepted"
    scenario_physical = 2 if scenario_evaluated else 0
    tested_physical = 2 if controllers_evaluated else 0
    reference_physical = 2 if controllers_evaluated else 0
    total_physical = scenario_physical + tested_physical + reference_physical
    return {
        "core_mutation_attempts": 1,
        "scenario_validation_logical_evaluations": int(scenario_evaluated),
        "scenario_validation_physical_rollouts": scenario_physical,
        "tested_controller_logical_evaluations": int(controllers_evaluated),
        "tested_controller_physical_rollouts": tested_physical,
        "reference_controller_logical_evaluations": int(controllers_evaluated),
        "reference_controller_physical_rollouts": reference_physical,
        "total_physical_rollouts": total_physical,
        "waymax_rollout_steps": (
            total_physical * scenario_selection.NUM_FUTURE_STEPS
        ),
    }


def _finding(
    original: dict[str, Any], attempt: dict[str, Any]
) -> dict[str, bool] | None:
    if attempt.get("status") != "accepted":
        return None
    return controller_comparison.comparison_finding(
        tested_original=original["controllers"]["tested"]["outcome"],
        tested_mutated=attempt["controllers"]["tested"]["outcome"],
        reference_original=original["controllers"]["reference"]["outcome"],
        reference_mutated=attempt["controllers"]["reference"]["outcome"],
    )


def build_original_checkpoint(
    run_manifest: dict[str, Any],
    candidate: dict[str, Any],
    original: dict[str, Any],
) -> dict[str, Any]:
    record = {
        "$schema": ORIGINAL_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": ORIGINAL_TYPE,
        "configuration_fingerprint": run_manifest[
            "configuration_fingerprint"
        ],
        "scenario": _scenario_descriptor(candidate),
        "original": original,
        "cost": _original_cost(),
    }
    return _seal_record(record, "checkpoint_sha256")


def build_proposal_record(
    run_manifest: dict[str, Any],
    candidate: dict[str, Any],
    proposal_index: int,
    parameters: dict[str, float],
    original: dict[str, Any],
    attempt: dict[str, Any],
) -> dict[str, Any]:
    proposal_identity = {
        "configuration_fingerprint": run_manifest[
            "configuration_fingerprint"
        ],
        "selection_order": candidate["selection_order"],
        "proposal_index": proposal_index,
        "parameters": parameters,
    }
    record = {
        "$schema": PROPOSAL_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": PROPOSAL_TYPE,
        "record_id": f"proposal_{_content_sha256(proposal_identity)}",
        "configuration_fingerprint": run_manifest[
            "configuration_fingerprint"
        ],
        "scenario": _scenario_descriptor(candidate),
        "proposal": {
            "proposal_index": proposal_index,
            "parameters": parameters,
            "normalized_mutation_distance": round(
                normalized_mutation_distance(parameters), 12
            ),
        },
        "attempt": attempt,
        "finding": _finding(original, attempt),
        "cost": proposal_cost(attempt),
    }
    return _seal_record(record, "record_sha256")


def _load_sealed_record(
    path: Path,
    *,
    record_type: str,
    hash_field: str,
    configuration_fingerprint: str,
) -> dict[str, Any]:
    record = _read_json_object(path)
    if record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Checkpoint schema version mismatch: {path}")
    if record.get("record_type") != record_type:
        raise ValueError(f"Checkpoint record type mismatch: {path}")
    if record.get("configuration_fingerprint") != configuration_fingerprint:
        raise ValueError(f"Checkpoint configuration mismatch: {path}")
    _validate_seal(record, hash_field, path=path)
    return record


def _original_path(output_dir: Path, selection_order: int) -> Path:
    return output_dir / "originals" / f"scenario-{selection_order:02d}.json"


def _proposal_path(
    output_dir: Path, selection_order: int, proposal_index: int
) -> Path:
    return (
        output_dir
        / "proposals"
        / f"scenario-{selection_order:02d}"
        / f"proposal-{proposal_index:04d}.json"
    )


def _sum_cost(records: list[CostRecord]) -> CostRecord:
    if not records:
        return {key: 0 for key in _original_cost()}
    keys = set(_original_cost())
    if any(set(record) != keys for record in records):
        raise ValueError("Cost records do not share the accounting schema")
    return {key: sum(record[key] for record in records) for key in sorted(keys)}


def _rejection_reasons(record: dict[str, Any]) -> list[str]:
    attempt = record["attempt"]
    if attempt["status"] == "mutation_rejected":
        return list(attempt["mutation"]["rejection_reasons"])
    if attempt["status"] == "scenario_rejected":
        return list(attempt["scenario_validation"]["rejection_reasons"])
    return []


def _recorded_original_seconds(original: dict[str, Any]) -> float:
    return sum(
        float(controller["first_rollout_seconds"])
        + float(controller["second_rollout_seconds"])
        for controller in original["controllers"].values()
    )


def build_aggregate_report(
    run_manifest: dict[str, Any],
    originals: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    *,
    invocation_seconds: float,
    process_peak_rss_bytes: int,
) -> dict[str, Any]:
    """Derive the completed private report only from durable checkpoints."""
    configuration = run_manifest["configuration"]
    budget = int(configuration["search"]["budget_per_scenario"])
    scenario_count = len(configuration["dataset"]["scenarios"])
    expected_proposals = scenario_count * budget
    ordered_originals = sorted(
        originals, key=lambda record: record["scenario"]["selection_order"]
    )
    ordered_proposals = sorted(
        proposals,
        key=lambda record: (
            record["scenario"]["selection_order"],
            record["proposal"]["proposal_index"],
        ),
    )
    accepted = [
        record
        for record in ordered_proposals
        if record["attempt"]["status"] == "accepted"
    ]
    failures = [
        record
        for record in accepted
        if record["finding"]["policy_specific_avoidable_failure"]
    ]
    deterministic = [
        record
        for record in accepted
        if record["attempt"]["scenario_validation"]["outputs_identical"]
        and all(
            controller["outputs_identical"]
            for controller in record["attempt"]["controllers"].values()
        )
    ]
    tested_responses = sum(
        bool(
            record["attempt"]["controllers"]["tested"][
                "changed_from_original"
            ]
        )
        for record in accepted
    )
    status_counts = Counter(
        record["attempt"]["status"] for record in ordered_proposals
    )
    rejection_counts = Counter(
        reason
        for record in ordered_proposals
        for reason in _rejection_reasons(record)
    )
    original_cost = _sum_cost([record["cost"] for record in ordered_originals])
    proposal_total_cost = _sum_cost(
        [record["cost"] for record in ordered_proposals]
    )
    total_cost = _sum_cost([original_cost, proposal_total_cost])
    scenario_summaries = []
    for original_checkpoint in ordered_originals:
        order = original_checkpoint["scenario"]["selection_order"]
        scenario_proposals = [
            record
            for record in ordered_proposals
            if record["scenario"]["selection_order"] == order
        ]
        scenario_failures = [
            record
            for record in scenario_proposals
            if record.get("finding")
            and record["finding"]["policy_specific_avoidable_failure"]
        ]
        first_failure = None
        if scenario_failures:
            first = scenario_failures[0]
            through_first = [
                record
                for record in scenario_proposals
                if record["proposal"]["proposal_index"]
                <= first["proposal"]["proposal_index"]
            ]
            first_failure = {
                "proposal_index": first["proposal"]["proposal_index"],
                "proposal_count_including_failure": len(through_first),
                "cumulative_cost_including_original": _sum_cost(
                    [
                        original_checkpoint["cost"],
                        _sum_cost([record["cost"] for record in through_first]),
                    ]
                ),
            }
        scenario_summaries.append(
            {
                "scenario": original_checkpoint["scenario"],
                "original_eligible": original_checkpoint["original"]["eligible"],
                "proposal_count": len(scenario_proposals),
                "status_counts": dict(
                    sorted(
                        Counter(
                            record["attempt"]["status"]
                            for record in scenario_proposals
                        ).items()
                    )
                ),
                "qualifying_failure_count": len(scenario_failures),
                "first_qualifying_failure": first_failure,
            }
        )
    minimum_separation = min(
        (
            record["attempt"]["controllers"]["tested"][
                "interaction_metrics"
            ]["minimum_signed_separation_m"]
            for record in accepted
        ),
        default=None,
    )
    finite_ttcs = [
        record["attempt"]["controllers"]["tested"]["interaction_metrics"][
            "minimum_longitudinal_ttc_s"
        ]
        for record in accepted
        if record["attempt"]["controllers"]["tested"][
            "interaction_metrics"
        ]["minimum_longitudinal_ttc_s"]
        is not None
    ]
    recorded_work_seconds = sum(
        _recorded_original_seconds(record["original"])
        for record in ordered_originals
    ) + sum(
        float(record["attempt"]["elapsed_seconds"])
        for record in ordered_proposals
    )
    integrity_gates = {
        "exact_original_count": len(ordered_originals) == scenario_count,
        "exact_proposal_budget": len(ordered_proposals) == expected_proposals,
        "unique_proposal_coordinates": len(
            {
                (
                    record["scenario"]["selection_order"],
                    record["proposal"]["proposal_index"],
                )
                for record in ordered_proposals
            }
        )
        == expected_proposals,
        "original_rollout_determinism": all(
            controller["outputs_identical"]
            for record in ordered_originals
            for controller in record["original"]["controllers"].values()
        ),
        "accepted_attempt_determinism": len(deterministic) == len(accepted),
        "cost_accounting_reconciles": total_cost
        == _sum_cost(
            [
                *[record["cost"] for record in ordered_originals],
                *[record["cost"] for record in ordered_proposals],
            ]
        ),
    }
    valid_rate = len(accepted) / len(ordered_proposals) if ordered_proposals else 0.0
    deterministic_rate = len(deterministic) / len(accepted) if accepted else 0.0
    response_rate = tested_responses / len(accepted) if accepted else 0.0
    metrics = {
        "scenario_count": scenario_count,
        "eligible_original_scenario_count": sum(
            record["original"]["eligible"] for record in ordered_originals
        ),
        "proposal_budget_per_scenario": budget,
        "proposal_count": len(ordered_proposals),
        "accepted_proposal_count": len(accepted),
        "valid_mutation_rate": round(valid_rate, 6),
        "accepted_attempt_determinism_rate": round(deterministic_rate, 6),
        "tested_controller_response_rate": round(response_rate, 6),
        "qualifying_failure_count": len(failures),
        "minimum_tested_signed_separation_m": (
            round(float(minimum_separation), 6)
            if minimum_separation is not None
            else None
        ),
        "minimum_tested_longitudinal_ttc_s": (
            round(float(min(finite_ttcs)), 6) if finite_ttcs else None
        ),
        "minimum_failure_mutation_distance": (
            round(
                min(
                    record["proposal"]["normalized_mutation_distance"]
                    for record in failures
                ),
                12,
            )
            if failures
            else None
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "rejection_reason_counts": dict(sorted(rejection_counts.items())),
        "recorded_work_seconds": round(recorded_work_seconds, 6),
        "final_invocation_seconds": round(invocation_seconds, 6),
        "proposals_per_recorded_work_second": (
            round(len(ordered_proposals) / recorded_work_seconds, 6)
            if recorded_work_seconds
            else None
        ),
        "process_peak_rss_bytes": process_peak_rss_bytes,
    }
    report = {
        "$schema": REPORT_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": REPORT_TYPE,
        "configuration_fingerprint": run_manifest[
            "configuration_fingerprint"
        ],
        "status": "completed",
        "decision": (
            "baseline_complete"
            if all(integrity_gates.values())
            else "invalid_run"
        ),
        "integrity_gates": integrity_gates,
        "metrics": metrics,
        "cost": {
            "originals": original_cost,
            "proposals": proposal_total_cost,
            "total": total_cost,
        },
        "scenario_summaries": scenario_summaries,
        "limitations": [
            "This is a training-set development baseline, not a held-out evaluation.",
            "Both controllers share Waymax IDMRoutePolicy and differ only by configuration.",
            "A qualifying failure is configuration-specific and makes no claim about the production Waymo Driver.",
            "The fixed proposal budget is an experimental control, not evidence that search is exhaustive.",
            "Restricted scenario and proposal records remain only under ignored artifacts paths.",
        ],
    }
    return _seal_record(report, "report_sha256")


def _validate_existing_checkpoint_identity(
    record: dict[str, Any],
    *,
    candidate: dict[str, Any],
    proposal_index: int | None = None,
    parameters: dict[str, float] | None = None,
) -> None:
    if record.get("scenario") != _scenario_descriptor(candidate):
        raise ValueError("Checkpoint scenario identity mismatch")
    if proposal_index is not None:
        proposal = record.get("proposal", {})
        if proposal.get("proposal_index") != proposal_index:
            raise ValueError("Checkpoint proposal index mismatch")
        if proposal.get("parameters") != parameters:
            raise ValueError("Checkpoint proposal parameters mismatch")


def _validate_original_checkpoint(
    record: dict[str, Any], *, candidate: dict[str, Any]
) -> None:
    _validate_existing_checkpoint_identity(record, candidate=candidate)
    if record.get("cost") != _original_cost():
        raise ValueError("Original checkpoint cost accounting mismatch")
    try:
        controllers = record["original"]["controllers"]
        eligible = all(
            controllers[role]["outcome"]["success"] for role in ROLES
        )
    except (KeyError, TypeError) as error:
        raise ValueError("Original checkpoint controller record is incomplete") from error
    if record["original"].get("eligible") is not bool(eligible):
        raise ValueError("Original checkpoint eligibility mismatch")


def _validate_proposal_derivations(
    record: dict[str, Any],
    *,
    candidate: dict[str, Any],
    proposal_index: int,
    parameters: dict[str, float],
    original: dict[str, Any],
    fingerprint: str,
) -> None:
    proposal_identity = {
        "configuration_fingerprint": fingerprint,
        "selection_order": candidate["selection_order"],
        "proposal_index": proposal_index,
        "parameters": parameters,
    }
    if record.get("record_id") != f"proposal_{_content_sha256(proposal_identity)}":
        raise ValueError("Checkpoint proposal record ID mismatch")
    proposal = record["proposal"]
    expected_distance = round(normalized_mutation_distance(parameters), 12)
    if proposal.get("normalized_mutation_distance") != expected_distance:
        raise ValueError("Checkpoint mutation distance mismatch")
    attempt = record.get("attempt")
    if not isinstance(attempt, dict):
        raise ValueError("Checkpoint attempt record is incomplete")
    if attempt.get("parameters") != parameters:
        raise ValueError("Checkpoint attempt parameters mismatch")
    expected_identity = family_validation.is_identity_point(
        parameters["braking_onset_offset_s"], parameters["speed_multiplier"]
    )
    if attempt.get("identity_control") is not expected_identity:
        raise ValueError("Checkpoint identity classification mismatch")
    if record.get("cost") != proposal_cost(attempt):
        raise ValueError("Checkpoint proposal cost accounting mismatch")
    if record.get("finding") != _finding(original, attempt):
        raise ValueError("Checkpoint policy-specific finding mismatch")


def _initialize_or_resume(
    output_dir: Path,
    expected_manifest: dict[str, Any],
    *,
    resume: bool,
) -> dict[str, Any]:
    manifest_path = output_dir / "run-manifest.json"
    if manifest_path.exists():
        if not resume:
            raise FileExistsError(
                "A random-search run already exists; pass --resume to continue it."
            )
        existing = _read_json_object(manifest_path)
        if existing.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Run manifest schema version mismatch")
        if existing.get("record_type") != RUN_MANIFEST_TYPE:
            raise ValueError("Run manifest record type mismatch")
        _validate_seal(existing, "manifest_sha256", path=manifest_path)
        if _content_sha256(existing.get("configuration")) != existing.get(
            "configuration_fingerprint"
        ):
            raise ValueError("Run manifest configuration fingerprint mismatch")
        if (
            existing.get("configuration_fingerprint")
            != expected_manifest["configuration_fingerprint"]
        ):
            raise ValueError(
                "Run configuration mismatch; seed, budget, source, controllers, "
                "or scenario manifest changed."
            )
        return existing
    if resume:
        raise FileNotFoundError("Cannot resume because run-manifest.json is missing")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(
            "Output directory is non-empty but has no valid run manifest"
        )
    _atomic_write_json(manifest_path, expected_manifest)
    return expected_manifest


def _load_completed_records(
    output_dir: Path,
    candidates: list[dict[str, Any]],
    config: RandomSearchConfig,
    fingerprint: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    originals: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    expected_original_paths = {
        _original_path(output_dir, candidate["selection_order"])
        for candidate in candidates
    }
    expected_proposal_paths = {
        _proposal_path(
            output_dir,
            candidate["selection_order"],
            proposal_index,
        )
        for candidate in candidates
        for proposal_index in range(config.budget_per_scenario)
    }
    actual_original_paths = set((output_dir / "originals").rglob("*.json"))
    actual_proposal_paths = set((output_dir / "proposals").rglob("*.json"))
    if actual_original_paths - expected_original_paths:
        raise ValueError("Unexpected original checkpoint file")
    if actual_proposal_paths - expected_proposal_paths:
        raise ValueError("Unexpected proposal checkpoint file")
    for candidate in candidates:
        order = candidate["selection_order"]
        original_path = _original_path(output_dir, order)
        if original_path.exists():
            record = _load_sealed_record(
                original_path,
                record_type=ORIGINAL_TYPE,
                hash_field="checkpoint_sha256",
                configuration_fingerprint=fingerprint,
            )
            _validate_original_checkpoint(record, candidate=candidate)
            originals.append(record)
        original = originals[-1]["original"] if original_path.exists() else None
        for proposal_index in range(config.budget_per_scenario):
            path = _proposal_path(output_dir, order, proposal_index)
            if not path.exists():
                continue
            parameters = proposal_parameters(config, order, proposal_index)
            record = _load_sealed_record(
                path,
                record_type=PROPOSAL_TYPE,
                hash_field="record_sha256",
                configuration_fingerprint=fingerprint,
            )
            _validate_existing_checkpoint_identity(
                record,
                candidate=candidate,
                proposal_index=proposal_index,
                parameters=parameters,
            )
            if original is None:
                raise ValueError(
                    "Proposal checkpoint exists without its original checkpoint"
                )
            _validate_proposal_derivations(
                record,
                candidate=candidate,
                proposal_index=proposal_index,
                parameters=parameters,
                original=original,
                fingerprint=fingerprint,
            )
            proposals.append(record)
    return originals, proposals


def run(
    manifest_path: Path,
    output_dir: Path,
    config: RandomSearchConfig,
    *,
    resume: bool = False,
    selection_orders: list[int] | None = None,
    max_new_proposals: int | None = None,
    scenario_loader: Callable[
        [Path], list[tuple[Any, dict[str, Any]]]
    ] = family_validation._load_manifest_scenarios,
    original_evaluator: OriginalEvaluator = family_validation._original_record,
    attempt_evaluator: AttemptEvaluator = family_validation._attempt_record,
) -> dict[str, Any]:
    """Execute or resume the private baseline and return a safe or full result."""
    invocation_started = time.perf_counter()
    validate_private_output_dir(output_dir)
    if max_new_proposals is not None and max_new_proposals < 0:
        raise ValueError("max_new_proposals must be non-negative")
    candidates = family_validation.load_manifest_candidates(manifest_path)
    expected_manifest = build_run_manifest(manifest_path, candidates, config)
    run_manifest = _initialize_or_resume(
        output_dir, expected_manifest, resume=resume
    )
    fingerprint = run_manifest["configuration_fingerprint"]
    report_path = output_dir / "report.json"
    if report_path.exists():
        if not resume:
            raise FileExistsError("Completed report already exists")
        return _load_sealed_record(
            report_path,
            record_type=REPORT_TYPE,
            hash_field="report_sha256",
            configuration_fingerprint=fingerprint,
        )
    expected_orders = [candidate["selection_order"] for candidate in candidates]
    requested_orders = expected_orders if selection_orders is None else selection_orders
    if len(set(requested_orders)) != len(requested_orders):
        raise ValueError("selection_orders must not contain duplicates")
    if any(order not in expected_orders for order in requested_orders):
        raise ValueError("selection_orders must belong to the run manifest")

    loaded = scenario_loader(manifest_path)
    by_order = {
        candidate["selection_order"]: (scenario, candidate)
        for scenario, candidate in loaded
    }
    if set(by_order) != set(expected_orders):
        raise ValueError("Loaded scenarios do not match the run manifest")
    runners = {
        "tested": controller_comparison.ControllerRunner(
            controller_comparison.TESTED_CONTROLLER
        ),
        "reference": controller_comparison.ControllerRunner(
            controller_comparison.REFERENCE_CONTROLLER
        ),
    }
    mutation_validator = speed_mutation.MutationValidator(
        require_mutated_object_valid_all_steps=False
    )
    new_proposals = 0
    stop_requested = False
    for order in requested_orders:
        scenario, candidate = by_order[order]
        original_path = _original_path(output_dir, order)
        if original_path.exists():
            original_checkpoint = _load_sealed_record(
                original_path,
                record_type=ORIGINAL_TYPE,
                hash_field="checkpoint_sha256",
                configuration_fingerprint=fingerprint,
            )
            _validate_original_checkpoint(
                original_checkpoint, candidate=candidate
            )
        else:
            original = original_evaluator(scenario, candidate, runners)
            original_checkpoint = build_original_checkpoint(
                run_manifest, candidate, original
            )
            _atomic_write_json(original_path, original_checkpoint)
        original = original_checkpoint["original"]
        for proposal_index in range(config.budget_per_scenario):
            proposal_path = _proposal_path(
                output_dir, order, proposal_index
            )
            parameters = proposal_parameters(config, order, proposal_index)
            if proposal_path.exists():
                existing = _load_sealed_record(
                    proposal_path,
                    record_type=PROPOSAL_TYPE,
                    hash_field="record_sha256",
                    configuration_fingerprint=fingerprint,
                )
                _validate_existing_checkpoint_identity(
                    existing,
                    candidate=candidate,
                    proposal_index=proposal_index,
                    parameters=parameters,
                )
                _validate_proposal_derivations(
                    existing,
                    candidate=candidate,
                    proposal_index=proposal_index,
                    parameters=parameters,
                    original=original,
                    fingerprint=fingerprint,
                )
                continue
            if (
                max_new_proposals is not None
                and new_proposals >= max_new_proposals
            ):
                stop_requested = True
                break
            attempt = attempt_evaluator(
                scenario,
                candidate,
                parameters["braking_onset_offset_s"],
                parameters["speed_multiplier"],
                runners,
                mutation_validator,
                original,
            )
            record = build_proposal_record(
                run_manifest,
                candidate,
                proposal_index,
                parameters,
                original,
                attempt,
            )
            _atomic_write_json(proposal_path, record)
            new_proposals += 1
        if stop_requested:
            break

    originals, proposals = _load_completed_records(
        output_dir, candidates, config, fingerprint
    )
    expected_proposal_count = len(candidates) * config.budget_per_scenario
    if (
        len(originals) == len(candidates)
        and len(proposals) == expected_proposal_count
    ):
        report = build_aggregate_report(
            run_manifest,
            originals,
            proposals,
            invocation_seconds=time.perf_counter() - invocation_started,
            process_peak_rss_bytes=family_validation._peak_rss_bytes(),
        )
        _atomic_write_json(report_path, report)
        return report
    return {
        "status": "in_progress",
        "decision": None,
        "completed_original_count": len(originals),
        "expected_original_count": len(candidates),
        "completed_proposal_count": len(proposals),
        "expected_proposal_count": expected_proposal_count,
        "remaining_proposal_count": expected_proposal_count - len(proposals),
        "new_proposal_count": new_proposals,
        "output": str(output_dir),
    }


def public_summary(result: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Return aggregate-only terminal output for progress or completion."""
    if result.get("record_type") != REPORT_TYPE:
        return {
            key: value
            for key, value in result.items()
            if key
            in {
                "status",
                "decision",
                "completed_original_count",
                "expected_original_count",
                "completed_proposal_count",
                "expected_proposal_count",
                "remaining_proposal_count",
                "new_proposal_count",
                "output",
            }
        }
    metrics = result["metrics"]
    return {
        "status": result["status"],
        "decision": result["decision"],
        "scenario_count": metrics["scenario_count"],
        "proposal_count": metrics["proposal_count"],
        "accepted_proposal_count": metrics["accepted_proposal_count"],
        "valid_mutation_rate": metrics["valid_mutation_rate"],
        "accepted_attempt_determinism_rate": metrics[
            "accepted_attempt_determinism_rate"
        ],
        "tested_controller_response_rate": metrics[
            "tested_controller_response_rate"
        ],
        "qualifying_failure_count": metrics["qualifying_failure_count"],
        "output": str(output_dir / "report.json"),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--selection-order", type=int, action="append", dest="selection_orders"
    )
    parser.add_argument("--max-new-proposals", type=int)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    output_dir = args.output_dir
    result = run(
        args.manifest,
        output_dir,
        RandomSearchConfig(
            seed=args.seed,
            budget_per_scenario=args.budget,
        ),
        resume=args.resume,
        selection_orders=args.selection_orders,
        max_new_proposals=args.max_new_proposals,
    )
    print(
        json.dumps(
            public_summary(result, output_dir),
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
