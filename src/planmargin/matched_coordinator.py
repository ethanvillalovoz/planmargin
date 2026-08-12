"""Method-neutral, resumable coordination for one matched-search cell."""

from __future__ import annotations

import dataclasses
import json
import math
import platform
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

import jax
import numpy as np
import tensorflow as tf

from planmargin import behavior_features
from planmargin import controller_comparison
from planmargin import empirical_support
from planmargin import family_validation
from planmargin import matched_search
from planmargin import random_search
from planmargin import scenario_selection

SCHEMA_VERSION = "1.0.0"
SCHEMA_BASE_URI = (
    "https://raw.githubusercontent.com/ethanvillalovoz/planmargin/main/schemas"
)
MANIFEST_SCHEMA_URI = f"{SCHEMA_BASE_URI}/matched-cell-run-manifest-v1.schema.json"
ORIGINAL_SCHEMA_URI = f"{SCHEMA_BASE_URI}/matched-cell-original-v1.schema.json"
SELECTION_SCHEMA_URI = f"{SCHEMA_BASE_URI}/matched-cell-selection-v1.schema.json"
PROPOSAL_SCHEMA_URI = f"{SCHEMA_BASE_URI}/matched-cell-proposal-v1.schema.json"
REPORT_SCHEMA_URI = f"{SCHEMA_BASE_URI}/matched-cell-report-v1.schema.json"
MANIFEST_TYPE = "planmargin.matched_cell_run_manifest"
ORIGINAL_TYPE = "planmargin.matched_cell_original_checkpoint"
SELECTION_TYPE = "planmargin.matched_cell_selection_step"
PROPOSAL_TYPE = "planmargin.matched_cell_proposal"
REPORT_TYPE = "planmargin.matched_cell_report"
RECORD_SCHEMA_BY_TYPE = {
    MANIFEST_TYPE: MANIFEST_SCHEMA_URI,
    ORIGINAL_TYPE: ORIGINAL_SCHEMA_URI,
    SELECTION_TYPE: SELECTION_SCHEMA_URI,
    PROPOSAL_TYPE: PROPOSAL_SCHEMA_URI,
    REPORT_TYPE: REPORT_SCHEMA_URI,
}

Method = Literal["random", "bayesian"]
Track = Literal["natural", "headway_regression"]
CostRecord = dict[str, int]
ScenarioLoader = Callable[[Path, int], tuple[Any, dict[str, Any]]]
OriginalEvaluator = Callable[
    [Any, dict[str, Any], controller_comparison.ControllerSpec,
     controller_comparison.ControllerSpec],
    dict[str, Any],
]
AttemptEvaluator = Callable[
    [
        Any,
        dict[str, Any],
        dict[str, float],
        controller_comparison.ControllerSpec,
        controller_comparison.ControllerSpec,
        dict[str, Any],
        dict[str, Any],
    ],
    dict[str, Any],
]


@dataclass(frozen=True)
class CellConfig:
    """Stable identity for one complete 32-proposal comparison cell."""

    method: Method
    track: Track
    seed: int
    selection_order: int

    def __post_init__(self) -> None:
        if self.method not in matched_search.METHODS:
            raise ValueError("method is outside the frozen set")
        if self.track not in matched_search.TRACKS:
            raise ValueError("track is outside the frozen set")
        if isinstance(self.seed, bool) or self.seed not in matched_search.SEEDS:
            raise ValueError("seed is outside the frozen set")
        if (
            isinstance(self.selection_order, bool)
            or not isinstance(self.selection_order, int)
            or not 1 <= self.selection_order <= family_validation.EXPECTED_SCENARIOS
        ):
            raise ValueError("selection_order is outside the frozen scenario set")


HEADWAY_REGRESSION_CONTROLLER = dataclasses.replace(
    controller_comparison.TESTED_CONTROLLER,
    controller_id="planmargin-idm-headway-regression-v1",
    safe_time_headway_s=1.0,
)


def tested_controller_for_track(
    track: Track,
) -> controller_comparison.ControllerSpec:
    """Return the only tested-controller configuration allowed for a track."""
    if track == "natural":
        return controller_comparison.TESTED_CONTROLLER
    if track == "headway_regression":
        return HEADWAY_REGRESSION_CONTROLLER
    raise ValueError("track is outside the frozen set")


def validate_private_output_dir(output_dir: Path) -> None:
    """Keep all scenario-derived cell records in the ignored artifact tree."""
    allowed_root = (Path.cwd() / "artifacts" / "search-comparison").resolve()
    if not output_dir.resolve().is_relative_to(allowed_root):
        raise ValueError(
            "Matched-search records are restricted; --output-dir must remain "
            "under artifacts/search-comparison/."
        )


def _identity(cell: CellConfig, proposal_index: int | None = None) -> dict[str, Any]:
    return {
        "method": cell.method,
        "track": cell.track,
        "seed": cell.seed,
        "selection_order": cell.selection_order,
        "proposal_index": proposal_index,
    }


def _scenario_descriptor(candidate: dict[str, Any]) -> dict[str, Any]:
    return random_search._scenario_descriptor(candidate)


def _parameters_dict(parameters: tuple[float, float]) -> dict[str, float]:
    return {
        "braking_onset_offset_s": parameters[0],
        "speed_multiplier": parameters[1],
    }


def _parameters_tuple(parameters: dict[str, Any]) -> tuple[float, float]:
    try:
        pair = (
            parameters["braking_onset_offset_s"],
            parameters["speed_multiplier"],
        )
    except (KeyError, TypeError) as error:
        raise ValueError("Proposal parameters are incomplete") from error
    matched_search._validate_parameters(pair)
    return pair


def _load_cell_scenario(
    manifest_path: Path, selection_order: int
) -> tuple[Any, dict[str, Any]]:
    loaded = family_validation._load_manifest_scenarios(manifest_path)
    matches = [
        pair for pair in loaded if pair[1]["selection_order"] == selection_order
    ]
    if len(matches) != 1:
        raise ValueError("Loaded scenario does not match the cell identity")
    return matches[0]


def _environment() -> dict[str, Any]:
    return json.loads(random_search._canonical_json({
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "numpy": np.__version__,
        "jax": jax.__version__,
        "tensorflow": tf.__version__,
        "jax_backend": jax.default_backend(),
        "matched_search": matched_search.dependency_report(),
    }))


def build_run_manifest(
    *,
    manifest_path: Path,
    candidate: dict[str, Any],
    support_model: dict[str, Any],
    cell: CellConfig,
) -> dict[str, Any]:
    """Build the sealed scientific identity for one comparison cell."""
    empirical_support.validate_model(support_model)
    tested = tested_controller_for_track(cell.track)
    source = scenario_selection._git_provenance()
    configuration = json.loads(random_search._canonical_json({
        "experiment": "matched_random_bayesian_lead_braking_v2",
        "cell": _identity(cell),
        "dataset": {
            "name": "Waymo Open Motion Dataset",
            "version": scenario_selection.DATASET_VERSION,
            "split": scenario_selection.SPLIT,
            "scenario_manifest_sha256": random_search._file_sha256(manifest_path),
            "scenario": _scenario_descriptor(candidate),
        },
        "search": asdict(matched_search.MatchedSearchConfig()),
        "support": {
            "model_fingerprint": support_model["model_fingerprint"],
            "model_sha256": support_model["model_sha256"],
            "feature_schema_version": behavior_features.FEATURE_SCHEMA_VERSION,
        },
        "mutation": {
            "type": "lead_braking_onset_and_speed",
            "fixed_configuration": random_search._fixed_mutation_configuration(),
        },
        "controllers": {
            "tested": tested.report(),
            "reference": controller_comparison.REFERENCE_CONTROLLER.report(),
        },
        "accounting": {
            "primary_budget_unit": "proposed_parameter_pair",
            "budget_per_cell": matched_search.PROPOSAL_BUDGET,
            "rejected_and_duplicate_proposals_consume_budget": True,
            "exhaust_budget_after_finding": True,
            "deterministic_physical_rollouts_per_logical_evaluation": 2,
            "waymax_steps_per_physical_rollout": (
                scenario_selection.NUM_FUTURE_STEPS
            ),
        },
        "source": {
            **source,
            "matched_coordinator_source_sha256": random_search._file_sha256(
                Path(__file__)
            ),
            "matched_search_source_sha256": random_search._file_sha256(
                Path(matched_search.__file__)
            ),
            "waymax_git_commit": scenario_selection.WAYMAX_GIT_COMMIT,
        },
    }))
    record = {
        "$schema": MANIFEST_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": MANIFEST_TYPE,
        "identity": _identity(cell),
        "configuration_fingerprint": random_search._content_sha256(configuration),
        "configuration": configuration,
        "environment": _environment(),
    }
    return random_search._seal_record(record, "manifest_sha256")


def _validate_identity(
    record: dict[str, Any], cell: CellConfig, proposal_index: int | None
) -> None:
    if record.get("identity") != _identity(cell, proposal_index):
        raise ValueError("Checkpoint cell identity mismatch")


def _load_sealed_record(
    path: Path,
    *,
    record_type: str,
    seal_field: str,
    fingerprint: str,
    cell: CellConfig,
    proposal_index: int | None,
) -> dict[str, Any]:
    record = random_search._read_json_object(path)
    if record.get("$schema") != RECORD_SCHEMA_BY_TYPE[record_type]:
        raise ValueError(f"Checkpoint schema identifier mismatch: {path}")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Checkpoint schema version mismatch: {path}")
    if record.get("record_type") != record_type:
        raise ValueError(f"Checkpoint record type mismatch: {path}")
    if record.get("configuration_fingerprint") != fingerprint:
        raise ValueError(f"Checkpoint configuration mismatch: {path}")
    _validate_identity(record, cell, proposal_index)
    random_search._validate_seal(record, seal_field, path=path)
    return record


def build_original_checkpoint(
    *,
    run_manifest: dict[str, Any],
    candidate: dict[str, Any],
    cell: CellConfig,
    original: dict[str, Any],
) -> dict[str, Any]:
    record = {
        "$schema": ORIGINAL_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": ORIGINAL_TYPE,
        "identity": _identity(cell),
        "configuration_fingerprint": run_manifest["configuration_fingerprint"],
        "scenario": _scenario_descriptor(candidate),
        "support_model_fingerprint": run_manifest["configuration"]["support"][
            "model_fingerprint"
        ],
        "original": original,
        "cost": random_search._original_cost(),
    }
    return random_search._seal_record(record, "checkpoint_sha256")


def _validate_original(
    record: dict[str, Any],
    *,
    candidate: dict[str, Any],
    support_model_fingerprint: str,
) -> None:
    if record.get("scenario") != _scenario_descriptor(candidate):
        raise ValueError("Original checkpoint scenario mismatch")
    if record.get("cost") != random_search._original_cost():
        raise ValueError("Original checkpoint cost mismatch")
    if record.get("support_model_fingerprint") != support_model_fingerprint:
        raise ValueError("Original checkpoint support-model mismatch")
    try:
        controllers = record["original"]["controllers"]
        if set(controllers) != set(random_search.ROLES):
            raise ValueError("Original controller roles mismatch")
        for role in random_search.ROLES:
            controller = controllers[role]
            if not isinstance(controller["outputs_identical"], bool) or not isinstance(
                controller["outcome"]["success"], bool
            ):
                raise ValueError("Original controller booleans are invalid")
            for field in ("first_rollout_seconds", "second_rollout_seconds"):
                value = controller[field]
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or value < 0.0
                ):
                    raise ValueError("Original controller timing is invalid")
        eligible = all(
            controllers[role]["outcome"]["success"]
            for role in random_search.ROLES
        )
    except (KeyError, TypeError) as error:
        raise ValueError("Original controller evidence is incomplete") from error
    if record["original"].get("eligible") is not bool(eligible):
        raise ValueError("Original eligibility derivation mismatch")


def _history_fingerprint(proposals: Sequence[dict[str, Any]]) -> str:
    return random_search._content_sha256(
        [record["record_sha256"] for record in proposals]
    )


def _outcome_from_record(record: dict[str, Any]) -> matched_search.OutcomeRecord:
    outcome = record["outcome"]
    return matched_search.OutcomeRecord(
        parameters=_parameters_tuple(record["proposal"]["parameters"]),
        objectives=tuple(outcome["objectives"]),
        constraints=tuple(outcome["constraints"]),
        objective_available=outcome["objective_available"],
    )


def _select_proposal(
    *,
    cell: CellConfig,
    proposal_index: int,
    proposals: Sequence[dict[str, Any]],
    optimizer: matched_search.BayesianOptimizer | None,
) -> matched_search.ProposalDecision:
    if cell.method == "random":
        return matched_search.ProposalDecision(
            proposal_index=proposal_index,
            parameters=matched_search.random_parameters(
                seed=cell.seed,
                selection_order=cell.selection_order,
                proposal_index=proposal_index,
            ),
            source="stateless_uniform_random_pcg64",
        )
    return matched_search.bayesian_proposal(
        seed=cell.seed,
        selection_order=cell.selection_order,
        proposal_index=proposal_index,
        observations=[_outcome_from_record(record) for record in proposals],
        optimizer=optimizer,
    )


def build_selection_record(
    *,
    run_manifest: dict[str, Any],
    candidate: dict[str, Any],
    cell: CellConfig,
    proposal_index: int,
    prior_proposals: Sequence[dict[str, Any]],
    decision: matched_search.ProposalDecision,
    selection_seconds: float,
) -> dict[str, Any]:
    if decision.proposal_index != proposal_index:
        raise ValueError("Proposal decision index mismatch")
    record = {
        "$schema": SELECTION_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": SELECTION_TYPE,
        "identity": _identity(cell, proposal_index),
        "configuration_fingerprint": run_manifest["configuration_fingerprint"],
        "scenario": _scenario_descriptor(candidate),
        "support_model_fingerprint": run_manifest["configuration"]["support"][
            "model_fingerprint"
        ],
        "history": {
            "observation_count": len(prior_proposals),
            "proposal_record_sha256": [
                record["record_sha256"] for record in prior_proposals
            ],
            "history_fingerprint": _history_fingerprint(prior_proposals),
        },
        "decision": decision.report(),
        "selection_seconds": round(selection_seconds, 6),
    }
    return random_search._seal_record(record, "selection_sha256")


def _validate_selection_derivations(
    record: dict[str, Any],
    *,
    candidate: dict[str, Any],
    cell: CellConfig,
    proposal_index: int,
    prior_proposals: Sequence[dict[str, Any]],
    expected_decision: matched_search.ProposalDecision,
    support_model_fingerprint: str,
) -> None:
    if record.get("scenario") != _scenario_descriptor(candidate):
        raise ValueError("Selection scenario mismatch")
    if record.get("support_model_fingerprint") != support_model_fingerprint:
        raise ValueError("Selection support-model mismatch")
    expected_history = {
        "observation_count": len(prior_proposals),
        "proposal_record_sha256": [
            proposal["record_sha256"] for proposal in prior_proposals
        ],
        "history_fingerprint": _history_fingerprint(prior_proposals),
    }
    if record.get("history") != expected_history:
        raise ValueError("Selection observation history mismatch")
    decision = record.get("decision")
    if not isinstance(decision, dict):
        raise ValueError("Selection decision is incomplete")
    if decision != expected_decision.report():
        raise ValueError("Selection decision does not reproduce")
    seconds = record.get("selection_seconds")
    if (
        isinstance(seconds, bool)
        or not isinstance(seconds, (int, float))
        or not math.isfinite(seconds)
        or seconds < 0.0
    ):
        raise ValueError("Selection timing is invalid")


def _validate_feature_record(feature: dict[str, Any] | None, status: str) -> None:
    if status != "accepted":
        if feature is not None:
            raise ValueError("Rejected attempts must not contain behavior features")
        return
    if not isinstance(feature, dict):
        raise ValueError("Accepted attempts require a behavior-feature record")
    if feature.get("feature_schema_version") != behavior_features.FEATURE_SCHEMA_VERSION:
        raise ValueError("Behavior-feature schema version mismatch")
    if feature.get("feature_names") != list(behavior_features.FEATURE_NAMES):
        raise ValueError("Behavior-feature names mismatch")
    accepted = feature.get("accepted")
    if not isinstance(accepted, bool):
        raise ValueError("Behavior-feature acceptance must be boolean")
    vector = feature.get("vector")
    reasons = feature.get("rejection_reasons")
    audit = feature.get("audit_metrics")
    if not isinstance(reasons, list) or not isinstance(audit, dict):
        raise ValueError("Behavior-feature audit record is incomplete")
    if accepted:
        array = np.asarray(vector, dtype=np.float64)
        expected_audit_names = {
            *behavior_features.FEATURE_NAMES,
            "current_sdc_speed_mps",
            "maximum_absolute_jerk_mps3",
        }
        if (
            array.shape != (len(behavior_features.FEATURE_NAMES),)
            or not np.isfinite(array).all()
            or reasons
            or set(audit) != expected_audit_names
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                for value in audit.values()
            )
            or list(array) != [audit[name] for name in behavior_features.FEATURE_NAMES]
        ):
            raise ValueError("Accepted behavior-feature vector is invalid")
    elif vector is not None or not reasons or audit:
        raise ValueError("Rejected behavior-feature record is invalid")


def _validate_attempt(
    attempt: dict[str, Any], parameters: dict[str, float]
) -> None:
    if not isinstance(attempt, dict) or attempt.get("parameters") != parameters:
        raise ValueError("Attempt parameters do not match the selection")
    status = attempt.get("status")
    if status not in {"mutation_rejected", "scenario_rejected", "accepted"}:
        raise ValueError("Attempt status is invalid")
    expected_identity = family_validation.is_identity_point(
        parameters["braking_onset_offset_s"], parameters["speed_multiplier"]
    )
    if attempt.get("identity_control") is not expected_identity:
        raise ValueError("Attempt identity classification mismatch")
    mutation = attempt.get("mutation")
    if not isinstance(mutation, dict) or mutation.get("parameters") != parameters:
        raise ValueError("Attempt mutation evidence is incomplete")
    if status == "mutation_rejected":
        if mutation.get("accepted") is not False:
            raise ValueError("Mutation rejection acceptance flag mismatch")
        if attempt.get("scenario_validation") is not None or attempt.get(
            "controllers"
        ) is not None:
            raise ValueError("Mutation rejection contains downstream evidence")
    elif status == "scenario_rejected":
        scenario_validation = attempt.get("scenario_validation")
        if (
            mutation.get("accepted") is not True
            or not isinstance(scenario_validation, dict)
            or scenario_validation.get("accepted") is not False
            or attempt.get("controllers") is not None
        ):
            raise ValueError("Scenario rejection evidence is inconsistent")
    else:
        try:
            controllers = attempt["controllers"]
            if (
                mutation.get("accepted") is not True
                or attempt["scenario_validation"].get("accepted") is not True
                or set(controllers) != set(random_search.ROLES)
            ):
                raise ValueError("Accepted attempt controller roles mismatch")
            if not isinstance(
                attempt["scenario_validation"]["outputs_identical"], bool
            ):
                raise ValueError("Scenario determinism flag must be boolean")
            for role in random_search.ROLES:
                controller = controllers[role]
                if not isinstance(
                    controller["outputs_identical"], bool
                ) or not isinstance(controller["outcome"]["success"], bool):
                    raise ValueError("Controller outcome flags must be booleans")
                separation = controller["interaction_metrics"][
                    "minimum_signed_separation_m"
                ]
                if (
                    isinstance(separation, bool)
                    or not isinstance(separation, (int, float))
                    or not math.isfinite(separation)
                ):
                    raise ValueError("Controller separation metric is invalid")
        except (KeyError, TypeError) as error:
            raise ValueError("Accepted attempt evidence is incomplete") from error
    elapsed = attempt.get("elapsed_seconds")
    if (
        isinstance(elapsed, bool)
        or not isinstance(elapsed, (int, float))
        or not math.isfinite(elapsed)
        or elapsed < 0.0
    ):
        raise ValueError("Attempt timing is invalid")


def _pipeline_passes(attempt: dict[str, Any]) -> bool:
    if attempt["status"] != "accepted":
        return False
    return bool(
        attempt["scenario_validation"]["outputs_identical"]
        and all(
            attempt["controllers"][role]["outputs_identical"]
            for role in random_search.ROLES
        )
    )


def _support_score(
    support_model: dict[str, Any], feature: dict[str, Any] | None
) -> dict[str, Any] | None:
    if feature is None or not feature["accepted"]:
        return None
    return empirical_support.score_vector(support_model, feature["vector"])


def _derive_finding(
    *,
    original: dict[str, Any],
    attempt: dict[str, Any],
    pipeline_passes: bool,
    support: dict[str, Any] | None,
) -> dict[str, bool] | None:
    if attempt["status"] != "accepted":
        return None
    classification = controller_comparison.comparison_finding(
        tested_original=original["controllers"]["tested"]["outcome"],
        tested_mutated=attempt["controllers"]["tested"]["outcome"],
        reference_original=original["controllers"]["reference"]["outcome"],
        reference_mutated=attempt["controllers"]["reference"]["outcome"],
    )
    controller_specific = classification["policy_specific_avoidable_failure"]
    classification["pipeline_reproducible"] = pipeline_passes
    classification["empirical_support_pass"] = bool(
        support is not None and support["passes"]
    )
    classification["policy_specific_avoidable_failure"] = bool(
        controller_specific
        and classification["pipeline_reproducible"]
        and classification["empirical_support_pass"]
    )
    return classification


def _derive_outcome(
    *,
    parameters: tuple[float, float],
    attempt: dict[str, Any],
    support: dict[str, Any] | None,
) -> matched_search.OutcomeRecord:
    pipeline_passes = _pipeline_passes(attempt)
    separation = None
    reference_succeeds = False
    if attempt["status"] == "accepted":
        separation = attempt["controllers"]["tested"]["interaction_metrics"][
            "minimum_signed_separation_m"
        ]
        reference_succeeds = bool(
            attempt["controllers"]["reference"]["outcome"]["success"]
        )
    return matched_search.evaluate_outcomes(
        parameters=parameters,
        minimum_signed_separation_m=separation,
        pipeline_passes=pipeline_passes,
        p_support=None if support is None else support["p_support"],
        reference_succeeds=reference_succeeds,
    )


def build_proposal_record(
    *,
    run_manifest: dict[str, Any],
    candidate: dict[str, Any],
    cell: CellConfig,
    proposal_index: int,
    selection: dict[str, Any],
    prior_proposals: Sequence[dict[str, Any]],
    original: dict[str, Any],
    evaluation: dict[str, Any],
    support_model: dict[str, Any],
) -> dict[str, Any]:
    parameters = selection["decision"]["parameters"]
    parameter_pair = (
        parameters["braking_onset_offset_s"],
        parameters["speed_multiplier"],
    )
    matched_search._validate_parameters(parameter_pair)
    if not isinstance(evaluation, dict) or set(evaluation) != {
        "attempt",
        "feature",
    }:
        raise ValueError("Evaluator output must contain only attempt and feature")
    attempt = evaluation["attempt"]
    feature = evaluation["feature"]
    _validate_attempt(attempt, parameters)
    _validate_feature_record(feature, attempt["status"])
    support = _support_score(support_model, feature)
    pipeline_passes = _pipeline_passes(attempt)
    outcome = _derive_outcome(
        parameters=parameter_pair,
        attempt=attempt,
        support=support,
    )
    finding = _derive_finding(
        original=original,
        attempt=attempt,
        pipeline_passes=pipeline_passes,
        support=support,
    )
    identity = _identity(cell, proposal_index)
    record_identity = {
        "configuration_fingerprint": run_manifest["configuration_fingerprint"],
        "identity": identity,
    }
    record = {
        "$schema": PROPOSAL_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": PROPOSAL_TYPE,
        "record_id": (
            f"matched_proposal_{random_search._content_sha256(record_identity)}"
        ),
        "identity": identity,
        "configuration_fingerprint": run_manifest["configuration_fingerprint"],
        "scenario": _scenario_descriptor(candidate),
        "support_model_fingerprint": support_model["model_fingerprint"],
        "selection_sha256": selection["selection_sha256"],
        "proposal": {
            "parameters": parameters,
            "normalized_mutation_distance": round(
                matched_search.normalized_mutation_distance(parameter_pair), 12
            ),
            "duplicate_of_proposal_indices": [
                index
                for index, prior in enumerate(prior_proposals)
                if prior["proposal"]["parameters"] == parameters
            ],
        },
        "attempt": attempt,
        "feature": feature,
        "support": support,
        "outcome": {
            "objectives": list(outcome.objectives),
            "constraints": list(outcome.constraints),
            "objective_available": outcome.objective_available,
        },
        "finding": finding,
        "cost": random_search.proposal_cost(attempt),
    }
    return random_search._seal_record(record, "record_sha256")


def _validate_proposal_derivations(
    record: dict[str, Any],
    *,
    candidate: dict[str, Any],
    cell: CellConfig,
    proposal_index: int,
    selection: dict[str, Any],
    prior_proposals: Sequence[dict[str, Any]],
    original: dict[str, Any],
    support_model: dict[str, Any],
) -> None:
    if record.get("scenario") != _scenario_descriptor(candidate):
        raise ValueError("Proposal scenario mismatch")
    if record.get("support_model_fingerprint") != support_model["model_fingerprint"]:
        raise ValueError("Proposal support-model mismatch")
    if record.get("selection_sha256") != selection["selection_sha256"]:
        raise ValueError("Proposal selection link mismatch")
    identity = _identity(cell, proposal_index)
    record_identity = {
        "configuration_fingerprint": record["configuration_fingerprint"],
        "identity": identity,
    }
    if record.get("record_id") != (
        f"matched_proposal_{random_search._content_sha256(record_identity)}"
    ):
        raise ValueError("Proposal record ID mismatch")
    parameters = record.get("proposal", {}).get("parameters")
    if parameters != selection["decision"]["parameters"]:
        raise ValueError("Proposal parameters do not match selection")
    parameter_pair = _parameters_tuple(parameters)
    expected_distance = round(
        matched_search.normalized_mutation_distance(parameter_pair), 12
    )
    if record["proposal"].get("normalized_mutation_distance") != expected_distance:
        raise ValueError("Proposal mutation distance mismatch")
    expected_duplicates = [
        index
        for index, prior in enumerate(prior_proposals)
        if prior["proposal"]["parameters"] == parameters
    ]
    if record["proposal"].get("duplicate_of_proposal_indices") != expected_duplicates:
        raise ValueError("Proposal duplicate derivation mismatch")
    attempt = record.get("attempt")
    feature = record.get("feature")
    _validate_attempt(attempt, parameters)
    _validate_feature_record(feature, attempt["status"])
    expected_support = _support_score(support_model, feature)
    if record.get("support") != expected_support:
        raise ValueError("Proposal support-score derivation mismatch")
    expected_outcome = _derive_outcome(
        parameters=parameter_pair,
        attempt=attempt,
        support=expected_support,
    )
    if record.get("outcome") != {
        "objectives": list(expected_outcome.objectives),
        "constraints": list(expected_outcome.constraints),
        "objective_available": expected_outcome.objective_available,
    }:
        raise ValueError("Proposal objective or constraint derivation mismatch")
    expected_finding = _derive_finding(
        original=original,
        attempt=attempt,
        pipeline_passes=_pipeline_passes(attempt),
        support=expected_support,
    )
    if record.get("finding") != expected_finding:
        raise ValueError("Proposal finding derivation mismatch")
    if record.get("cost") != random_search.proposal_cost(attempt):
        raise ValueError("Proposal cost accounting mismatch")


def _selection_path(output_dir: Path, proposal_index: int) -> Path:
    return output_dir / "selections" / f"step-{proposal_index:04d}.json"


def _proposal_path(output_dir: Path, proposal_index: int) -> Path:
    return output_dir / "proposals" / f"proposal-{proposal_index:04d}.json"


def _validate_expected_files(output_dir: Path) -> None:
    expected_root = {output_dir / "run-manifest.json", output_dir / "original.json"}
    report_path = output_dir / "report.json"
    if report_path.exists():
        expected_root.add(report_path)
    actual_root = {path for path in output_dir.iterdir() if path.is_file()}
    if actual_root - expected_root:
        raise ValueError("Unexpected matched-cell root checkpoint file")
    expected_selections = {
        _selection_path(output_dir, index)
        for index in range(matched_search.PROPOSAL_BUDGET)
    }
    expected_proposals = {
        _proposal_path(output_dir, index)
        for index in range(matched_search.PROPOSAL_BUDGET)
    }
    actual_selections = {
        path for path in (output_dir / "selections").rglob("*") if path.is_file()
    }
    actual_proposals = {
        path for path in (output_dir / "proposals").rglob("*") if path.is_file()
    }
    if actual_selections - expected_selections:
        raise ValueError("Unexpected selection checkpoint file")
    if actual_proposals - expected_proposals:
        raise ValueError("Unexpected proposal checkpoint file")


def _initialize_or_resume(
    output_dir: Path,
    expected_manifest: dict[str, Any],
    *,
    cell: CellConfig,
    resume: bool,
) -> dict[str, Any]:
    path = output_dir / "run-manifest.json"
    if path.exists():
        if not resume:
            raise FileExistsError(
                "A matched-search cell already exists; pass resume=True to continue"
            )
        record = _load_sealed_record(
            path,
            record_type=MANIFEST_TYPE,
            seal_field="manifest_sha256",
            fingerprint=expected_manifest["configuration_fingerprint"],
            cell=cell,
            proposal_index=None,
        )
        if record.get("configuration") != expected_manifest["configuration"]:
            raise ValueError("Run configuration mismatch")
        if record.get("environment") != expected_manifest["environment"]:
            raise ValueError("Run environment mismatch")
        return record
    if resume:
        raise FileNotFoundError("Cannot resume because run-manifest.json is missing")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("Output directory is non-empty without a run manifest")
    random_search._atomic_write_json(path, expected_manifest)
    return expected_manifest


def _load_records(
    *,
    output_dir: Path,
    run_manifest: dict[str, Any],
    candidate: dict[str, Any],
    cell: CellConfig,
    support_model: dict[str, Any],
    optimizer: matched_search.BayesianOptimizer | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
    _validate_expected_files(output_dir)
    fingerprint = run_manifest["configuration_fingerprint"]
    original_path = output_dir / "original.json"
    original_record = None
    if original_path.exists():
        original_record = _load_sealed_record(
            original_path,
            record_type=ORIGINAL_TYPE,
            seal_field="checkpoint_sha256",
            fingerprint=fingerprint,
            cell=cell,
            proposal_index=None,
        )
        _validate_original(
            original_record,
            candidate=candidate,
            support_model_fingerprint=support_model["model_fingerprint"],
        )
    selections: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    for proposal_index in range(matched_search.PROPOSAL_BUDGET):
        selection_path = _selection_path(output_dir, proposal_index)
        proposal_path = _proposal_path(output_dir, proposal_index)
        if proposal_path.exists() and not selection_path.exists():
            raise ValueError("Proposal checkpoint exists without its selection step")
        if selection_path.exists():
            expected_decision = _select_proposal(
                cell=cell,
                proposal_index=proposal_index,
                proposals=proposals,
                optimizer=optimizer,
            )
            selection = _load_sealed_record(
                selection_path,
                record_type=SELECTION_TYPE,
                seal_field="selection_sha256",
                fingerprint=fingerprint,
                cell=cell,
                proposal_index=proposal_index,
            )
            _validate_selection_derivations(
                selection,
                candidate=candidate,
                cell=cell,
                proposal_index=proposal_index,
                prior_proposals=proposals,
                expected_decision=expected_decision,
                support_model_fingerprint=support_model["model_fingerprint"],
            )
            selections.append(selection)
        if proposal_path.exists():
            if original_record is None:
                raise ValueError("Proposal checkpoint exists without original evidence")
            proposal = _load_sealed_record(
                proposal_path,
                record_type=PROPOSAL_TYPE,
                seal_field="record_sha256",
                fingerprint=fingerprint,
                cell=cell,
                proposal_index=proposal_index,
            )
            _validate_proposal_derivations(
                proposal,
                candidate=candidate,
                cell=cell,
                proposal_index=proposal_index,
                selection=selections[-1],
                prior_proposals=proposals,
                original=original_record["original"],
                support_model=support_model,
            )
            proposals.append(proposal)
        elif selection_path.exists():
            if any(
                _selection_path(output_dir, later).exists()
                or _proposal_path(output_dir, later).exists()
                for later in range(
                    proposal_index + 1, matched_search.PROPOSAL_BUDGET
                )
            ):
                raise ValueError("Matched-cell checkpoints contain an index gap")
            break
        elif any(
            _selection_path(output_dir, later).exists()
            or _proposal_path(output_dir, later).exists()
            for later in range(proposal_index + 1, matched_search.PROPOSAL_BUDGET)
        ):
            raise ValueError("Matched-cell checkpoints contain an index gap")
        else:
            break
    return original_record, selections, proposals


def _sum_cost(records: Sequence[CostRecord]) -> CostRecord:
    return random_search._sum_cost(list(records))


def _two_objective_hypervolume(records: Sequence[dict[str, Any]]) -> float:
    feasible = [
        tuple(record["outcome"]["objectives"])
        for record in records
        if all(value <= 0.0 for value in record["outcome"]["constraints"])
    ]
    if not feasible:
        return 0.0
    nondominated = [
        point
        for point in feasible
        if not any(
            other != point
            and other[0] >= point[0]
            and other[1] >= point[1]
            for other in feasible
        )
    ]
    area = 0.0
    previous_x = 0.0
    for x_value, y_value in sorted(nondominated):
        area += max(x_value - previous_x, 0.0) * y_value
        previous_x = max(previous_x, x_value)
    return area


def build_report(
    *,
    run_manifest: dict[str, Any],
    original: dict[str, Any],
    selections: Sequence[dict[str, Any]],
    proposals: Sequence[dict[str, Any]],
    invocation_seconds: float,
    process_peak_rss_bytes: int,
) -> dict[str, Any]:
    accepted = [record for record in proposals if record["attempt"]["status"] == "accepted"]
    pipeline_valid = [record for record in proposals if record["outcome"]["constraints"][0] <= 0.0]
    support_pipeline_valid = [
        record
        for record in proposals
        if record["outcome"]["constraints"][0] <= 0.0
        and record["outcome"]["constraints"][1] <= 0.0
    ]
    feasible = [
        record
        for record in proposals
        if all(value <= 0.0 for value in record["outcome"]["constraints"])
    ]
    findings = [
        record
        for record in proposals
        if record.get("finding")
        and record["finding"]["policy_specific_avoidable_failure"]
    ]
    status_counts = Counter(record["attempt"]["status"] for record in proposals)
    duplicate_count = sum(
        bool(record["proposal"]["duplicate_of_proposal_indices"])
        for record in proposals
    )
    proposal_cost = _sum_cost([record["cost"] for record in proposals])
    original_cost = original["cost"]
    total_cost = _sum_cost([original_cost, proposal_cost])
    hypervolume_trace = [
        round(_two_objective_hypervolume(proposals[: index + 1]), 12)
        for index in range(len(proposals))
    ]
    integrity_gates = {
        "exact_selection_budget": len(selections) == matched_search.PROPOSAL_BUDGET,
        "exact_proposal_budget": len(proposals) == matched_search.PROPOSAL_BUDGET,
        "sequential_indices": [
            record["identity"]["proposal_index"] for record in proposals
        ]
        == list(range(matched_search.PROPOSAL_BUDGET)),
        "history_chain_complete": all(
            selection["history"]["observation_count"] == index
            for index, selection in enumerate(selections)
        ),
        "selection_links_complete": all(
            proposal["selection_sha256"] == selection["selection_sha256"]
            for proposal, selection in zip(proposals, selections, strict=True)
        ),
        "original_rollout_determinism": all(
            controller["outputs_identical"]
            for controller in original["original"]["controllers"].values()
        ),
        "accepted_attempt_determinism": all(
            _pipeline_passes(record["attempt"]) for record in accepted
        ),
        "cost_accounting_reconciles": total_cost
        == _sum_cost([original["cost"], *[record["cost"] for record in proposals]]),
    }
    proposal_count = len(proposals)
    recorded_work_seconds = sum(
        float(controller["first_rollout_seconds"])
        + float(controller["second_rollout_seconds"])
        for controller in original["original"]["controllers"].values()
    ) + sum(
        float(selection["selection_seconds"])
        + float(proposal["attempt"]["elapsed_seconds"])
        for selection, proposal in zip(selections, proposals, strict=True)
    )
    metrics = {
        "proposal_budget": matched_search.PROPOSAL_BUDGET,
        "proposal_count": proposal_count,
        "accepted_proposal_count": len(accepted),
        "pipeline_valid_count": len(pipeline_valid),
        "support_and_pipeline_valid_count": len(support_pipeline_valid),
        "fully_feasible_count": len(feasible),
        "qualifying_failure_count": len(findings),
        "first_qualifying_failure_proposal_count": (
            findings[0]["identity"]["proposal_index"] + 1 if findings else None
        ),
        "minimum_failure_mutation_distance": (
            min(record["proposal"]["normalized_mutation_distance"] for record in findings)
            if findings
            else None
        ),
        "pipeline_valid_rate": (
            round(len(pipeline_valid) / proposal_count, 6) if proposal_count else 0.0
        ),
        "support_and_pipeline_valid_rate": (
            round(len(support_pipeline_valid) / proposal_count, 6)
            if proposal_count
            else 0.0
        ),
        "duplicate_proposal_count": duplicate_count,
        "status_counts": dict(sorted(status_counts.items())),
        "final_feasible_hypervolume": (
            hypervolume_trace[-1] if hypervolume_trace else 0.0
        ),
        "feasible_hypervolume_by_proposal": hypervolume_trace,
        "recorded_work_seconds": round(recorded_work_seconds, 6),
        "final_invocation_seconds": round(invocation_seconds, 6),
        "process_peak_rss_bytes": process_peak_rss_bytes,
    }
    report = {
        "$schema": REPORT_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": REPORT_TYPE,
        "identity": run_manifest["identity"],
        "configuration_fingerprint": run_manifest["configuration_fingerprint"],
        "support_model_fingerprint": run_manifest["configuration"]["support"][
            "model_fingerprint"
        ],
        "status": "completed",
        "decision": (
            "cell_complete" if all(integrity_gates.values()) else "invalid_cell"
        ),
        "integrity_gates": integrity_gates,
        "metrics": metrics,
        "cost": {
            "original": original_cost,
            "proposals": proposal_cost,
            "total": total_cost,
        },
        "limitations": [
            "This is one training-set development cell, not a campaign comparison.",
            "A technical controller comparison makes no claim about the production Waymo Driver.",
            "Cell completion alone does not support H1, H2, or H3.",
            "Restricted scenario, feature, support, and proposal records remain under artifacts.",
        ],
    }
    return random_search._seal_record(report, "report_sha256")


def _validate_completed_report(
    report: dict[str, Any],
    *,
    run_manifest: dict[str, Any],
    original: dict[str, Any],
    selections: Sequence[dict[str, Any]],
    proposals: Sequence[dict[str, Any]],
) -> None:
    try:
        invocation_seconds = float(report["metrics"]["final_invocation_seconds"])
        peak = report["metrics"]["process_peak_rss_bytes"]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Completed report observations are incomplete") from error
    if isinstance(peak, bool) or not isinstance(peak, int) or peak < 0:
        raise ValueError("Completed report peak memory is invalid")
    expected = build_report(
        run_manifest=run_manifest,
        original=original,
        selections=selections,
        proposals=proposals,
        invocation_seconds=invocation_seconds,
        process_peak_rss_bytes=peak,
    )
    if report != expected:
        raise ValueError("Completed report does not match durable checkpoints")


def run(
    *,
    manifest_path: Path,
    support_model_path: Path,
    output_dir: Path,
    cell: CellConfig,
    resume: bool = False,
    max_new_proposals: int | None = None,
    scenario_loader: ScenarioLoader = _load_cell_scenario,
    original_evaluator: OriginalEvaluator,
    attempt_evaluator: AttemptEvaluator,
    optimizer: matched_search.BayesianOptimizer | None = None,
) -> dict[str, Any]:
    """Execute or resume one complete method-neutral matched-search cell."""
    started = time.perf_counter()
    validate_private_output_dir(output_dir)
    if (
        max_new_proposals is not None
        and (
            isinstance(max_new_proposals, bool)
            or not isinstance(max_new_proposals, int)
            or max_new_proposals < 0
        )
    ):
        raise ValueError("max_new_proposals must be a non-negative integer")
    candidates = family_validation.load_manifest_candidates(manifest_path)
    candidate = next(
        candidate
        for candidate in candidates
        if candidate["selection_order"] == cell.selection_order
    )
    support_model = empirical_support.load_model(support_model_path)
    expected_manifest = build_run_manifest(
        manifest_path=manifest_path,
        candidate=candidate,
        support_model=support_model,
        cell=cell,
    )
    run_manifest = _initialize_or_resume(
        output_dir, expected_manifest, cell=cell, resume=resume
    )
    original_record, selections, proposals = _load_records(
        output_dir=output_dir,
        run_manifest=run_manifest,
        candidate=candidate,
        cell=cell,
        support_model=support_model,
        optimizer=optimizer,
    )
    report_path = output_dir / "report.json"
    if report_path.exists():
        if not resume:
            raise FileExistsError("Completed cell report already exists")
        if (
            original_record is None
            or len(selections) != matched_search.PROPOSAL_BUDGET
            or len(proposals) != matched_search.PROPOSAL_BUDGET
        ):
            raise ValueError("Completed report exists without complete checkpoints")
        report = _load_sealed_record(
            report_path,
            record_type=REPORT_TYPE,
            seal_field="report_sha256",
            fingerprint=run_manifest["configuration_fingerprint"],
            cell=cell,
            proposal_index=None,
        )
        _validate_completed_report(
            report,
            run_manifest=run_manifest,
            original=original_record,
            selections=selections,
            proposals=proposals,
        )
        return report

    scenario, loaded_candidate = scenario_loader(manifest_path, cell.selection_order)
    if loaded_candidate != candidate:
        raise ValueError("Scenario loader candidate does not match the manifest")
    tested = tested_controller_for_track(cell.track)
    reference = controller_comparison.REFERENCE_CONTROLLER
    if original_record is None:
        original = original_evaluator(
            scenario, candidate, tested, reference
        )
        original_record = build_original_checkpoint(
            run_manifest=run_manifest,
            candidate=candidate,
            cell=cell,
            original=original,
        )
        _validate_original(
            original_record,
            candidate=candidate,
            support_model_fingerprint=support_model["model_fingerprint"],
        )
        random_search._atomic_write_json(output_dir / "original.json", original_record)
    original = original_record["original"]
    new_proposals = 0
    while len(proposals) < matched_search.PROPOSAL_BUDGET:
        proposal_index = len(proposals)
        if max_new_proposals is not None and new_proposals >= max_new_proposals:
            break
        selection_path = _selection_path(output_dir, proposal_index)
        if len(selections) > proposal_index:
            selection = selections[proposal_index]
        else:
            selection_started = time.perf_counter()
            decision = _select_proposal(
                cell=cell,
                proposal_index=proposal_index,
                proposals=proposals,
                optimizer=optimizer,
            )
            selection = build_selection_record(
                run_manifest=run_manifest,
                candidate=candidate,
                cell=cell,
                proposal_index=proposal_index,
                prior_proposals=proposals,
                decision=decision,
                selection_seconds=time.perf_counter() - selection_started,
            )
            random_search._atomic_write_json(selection_path, selection)
            selections.append(selection)
        parameters = selection["decision"]["parameters"]
        evaluation = attempt_evaluator(
            scenario,
            candidate,
            parameters,
            tested,
            reference,
            support_model,
            original,
        )
        proposal = build_proposal_record(
            run_manifest=run_manifest,
            candidate=candidate,
            cell=cell,
            proposal_index=proposal_index,
            selection=selection,
            prior_proposals=proposals,
            original=original,
            evaluation=evaluation,
            support_model=support_model,
        )
        _validate_proposal_derivations(
            proposal,
            candidate=candidate,
            cell=cell,
            proposal_index=proposal_index,
            selection=selection,
            prior_proposals=proposals,
            original=original,
            support_model=support_model,
        )
        random_search._atomic_write_json(
            _proposal_path(output_dir, proposal_index), proposal
        )
        proposals.append(proposal)
        new_proposals += 1

    if len(proposals) == matched_search.PROPOSAL_BUDGET:
        report = build_report(
            run_manifest=run_manifest,
            original=original_record,
            selections=selections,
            proposals=proposals,
            invocation_seconds=time.perf_counter() - started,
            process_peak_rss_bytes=family_validation._peak_rss_bytes(),
        )
        random_search._atomic_write_json(report_path, report)
        return report
    return {
        "status": "in_progress",
        "decision": None,
        "identity": _identity(cell),
        "completed_proposal_count": len(proposals),
        "expected_proposal_count": matched_search.PROPOSAL_BUDGET,
        "remaining_proposal_count": matched_search.PROPOSAL_BUDGET - len(proposals),
        "new_proposal_count": new_proposals,
        "output": str(output_dir),
    }


def public_summary(result: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Return aggregate-only progress suitable for a terminal."""
    if result.get("record_type") != REPORT_TYPE:
        allowed = {
            "status",
            "decision",
            "identity",
            "completed_proposal_count",
            "expected_proposal_count",
            "remaining_proposal_count",
            "new_proposal_count",
        }
        return {key: value for key, value in result.items() if key in allowed}
    return {
        "status": result["status"],
        "decision": result["decision"],
        "identity": result["identity"],
        "proposal_count": result["metrics"]["proposal_count"],
        "support_and_pipeline_valid_rate": result["metrics"][
            "support_and_pipeline_valid_rate"
        ],
        "qualifying_failure_count": result["metrics"][
            "qualifying_failure_count"
        ],
        "total_physical_rollouts": result["cost"]["total"][
            "total_physical_rollouts"
        ],
        "output": str(output_dir),
    }
