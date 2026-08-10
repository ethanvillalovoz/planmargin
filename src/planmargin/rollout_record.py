"""Export a versioned, auditable rollout and metric record collection."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
SCHEMA_URI = (
    "https://raw.githubusercontent.com/ethanvillalovoz/planmargin/main/"
    "schemas/rollout-record-collection-v1.schema.json"
)
COLLECTION_TYPE = "planmargin.rollout_record_collection"
RECORD_TYPE = "planmargin.rollout_record"
DEFAULT_INPUT = Path("artifacts/stage-0/controller-comparison.json")
DEFAULT_OUTPUT = Path("artifacts/stage-0/rollout-records.json")
ROLES = ("tested", "reference")
SOURCE_VARIANTS = ("original", "mutated")
EXPORTED_VARIANTS = {"original": "original", "mutated": "counterfactual"}

RECORD_REQUIRED_FIELDS = {
    "schema_version",
    "record_type",
    "record_id",
    "comparison_key",
    "record_kind",
    "status",
    "variant",
    "scenario",
    "controller_set",
    "controller_role",
    "controller",
    "mutation",
    "metric_configuration",
    "outcome",
    "acceptance_gate_results",
    "reproducibility",
    "trajectory",
    "provenance",
    "rejection_reasons",
    "limitations",
}


class RecordValidationError(ValueError):
    """Raised when an exported collection violates the v1 contract."""


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _stable_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(_canonical_json(value).encode()).hexdigest()
    return f"{prefix}_{digest}"


def _is_stable_id(value: Any, prefix: str) -> bool:
    if not isinstance(value, str) or not value.startswith(f"{prefix}_"):
        return False
    digest = value[len(prefix) + 1 :]
    return len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )


def _comparison_key(source: dict[str, Any]) -> str:
    dataset = source.get("dataset", {})
    mutation = source.get("mutation", {})
    identity = {
        "dataset": {
            "name": dataset.get("name"),
            "version": dataset.get("version"),
            "split": dataset.get("split"),
            "scenario_id": dataset.get("scenario_id"),
            "source_shard": dataset.get("source_shard"),
            "record_index": dataset.get("record_index"),
        },
        "mutation": {
            "mutation_type": mutation.get("mutation_type"),
            "parameters": mutation.get("parameters", {}),
        },
    }
    return _stable_id("cmp", identity)


def _controller_set(source: dict[str, Any]) -> dict[str, Any]:
    controllers = source.get("controllers", {})
    return {
        role: copy.deepcopy(controllers.get(role))
        for role in ROLES
    }


def _provenance(source: dict[str, Any]) -> dict[str, Any]:
    environment = source.get("environment", {})
    return {
        "git_revision": environment.get("git_commit"),
        "git_worktree_dirty": environment.get("git_worktree_dirty"),
        "waymax_revision": environment.get("waymax_git_commit"),
        "source_revision_sha256": environment.get(
            "comparison_source_sha256"
        ),
        "seed": environment.get("seed"),
        "runtime": {
            "python": environment.get("python"),
            "jax": environment.get("jax"),
            "tensorflow": environment.get("tensorflow"),
        },
        "hardware_class": {
            "platform": environment.get("platform"),
            "machine": environment.get("machine"),
            "jax_backend": environment.get("jax_backend"),
        },
    }


def _mutation_record(
    source: dict[str, Any], *, applied: bool
) -> dict[str, Any]:
    mutation = copy.deepcopy(source.get("mutation", {}))
    return {"applied": applied, **mutation}


def _completed_record(
    source: dict[str, Any],
    *,
    comparison_key: str,
    source_variant: str,
    role: str,
) -> dict[str, Any]:
    rollout = source["rollouts"][source_variant][role]
    variant = EXPORTED_VARIANTS[source_variant]
    record_identity = {
        "schema_version": SCHEMA_VERSION,
        "comparison_key": comparison_key,
        "variant": variant,
        "controller_role": role,
        "controller_id": rollout["controller"]["controller_id"],
        "git_revision": source.get("environment", {}).get("git_commit"),
        "trajectory_sha256": rollout["trajectory_sha256"],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": RECORD_TYPE,
        "record_id": _stable_id("rec", record_identity),
        "comparison_key": comparison_key,
        "record_kind": "rollout",
        "status": "completed",
        "variant": variant,
        "scenario": copy.deepcopy(source["dataset"]),
        "controller_set": _controller_set(source),
        "controller_role": role,
        "controller": copy.deepcopy(rollout["controller"]),
        "mutation": _mutation_record(
            source, applied=source_variant == "mutated"
        ),
        "metric_configuration": copy.deepcopy(
            source.get("metric_definition", {})
        ),
        "outcome": copy.deepcopy(rollout["outcome"]),
        "acceptance_gate_results": copy.deepcopy(
            source.get("acceptance", {})
        ),
        "reproducibility": {
            "outputs_identical": rollout["outputs_identical"],
            "trajectory_sha256": rollout["trajectory_sha256"],
            "non_sdc_input_sha256": rollout["non_sdc_input_sha256"],
            "input_unchanged_after_rollout": rollout[
                "input_unchanged_after_rollout"
            ],
            "first_rollout_seconds": rollout["first_rollout_seconds"],
            "second_rollout_seconds": rollout["second_rollout_seconds"],
        },
        "trajectory": copy.deepcopy(rollout["trajectory"]),
        "provenance": _provenance(source),
        "rejection_reasons": [],
        "limitations": copy.deepcopy(source.get("limitations", [])),
    }


def _invalid_rejection_reasons(source: dict[str, Any]) -> list[str]:
    reasons = list(
        source.get("mutation", {}).get("rejection_reasons", [])
    )
    reasons.extend(
        source.get("mutation_scenario_validation", {}).get(
            "rejection_reasons", []
        )
    )
    if not reasons:
        reasons.append("comparison_not_ready")
    return list(dict.fromkeys(reasons))


def _invalid_record(
    source: dict[str, Any], *, comparison_key: str
) -> dict[str, Any]:
    reasons = _invalid_rejection_reasons(source)
    record_identity = {
        "schema_version": SCHEMA_VERSION,
        "comparison_key": comparison_key,
        "record_kind": "invalid_candidate",
        "git_revision": source.get("environment", {}).get("git_commit"),
        "rejection_reasons": reasons,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": RECORD_TYPE,
        "record_id": _stable_id("rec", record_identity),
        "comparison_key": comparison_key,
        "record_kind": "invalid_candidate",
        "status": "invalid",
        "variant": "counterfactual",
        "scenario": copy.deepcopy(source.get("dataset", {})),
        "controller_set": _controller_set(source),
        "controller_role": None,
        "controller": None,
        "mutation": _mutation_record(source, applied=False),
        "metric_configuration": copy.deepcopy(
            source.get("metric_definition", {})
        ),
        "outcome": None,
        "acceptance_gate_results": copy.deepcopy(
            source.get("acceptance", {})
        ),
        "reproducibility": None,
        "trajectory": None,
        "provenance": _provenance(source),
        "rejection_reasons": reasons,
        "limitations": copy.deepcopy(source.get("limitations", [])),
    }


def export_collection(source: dict[str, Any]) -> dict[str, Any]:
    """Transform a controller-comparison report into v1 rollout records."""
    comparison_key = _comparison_key(source)
    has_rollouts = all(
        source.get("rollouts", {}).get(variant, {}).get(role) is not None
        for variant in SOURCE_VARIANTS
        for role in ROLES
    )
    if source.get("status") == "passed" and has_rollouts:
        records = [
            _completed_record(
                source,
                comparison_key=comparison_key,
                source_variant=variant,
                role=role,
            )
            for variant in SOURCE_VARIANTS
            for role in ROLES
        ]
        collection_status = "complete"
    else:
        records = [_invalid_record(source, comparison_key=comparison_key)]
        collection_status = "invalid_candidate"

    collection = {
        "$schema": SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": COLLECTION_TYPE,
        "collection_status": collection_status,
        "comparison_key": comparison_key,
        "comparison_finding": copy.deepcopy(source.get("finding", {})),
        "records": records,
    }
    errors = validate_collection(collection)
    if errors:
        raise RecordValidationError("; ".join(errors))
    return collection


def validate_collection(collection: dict[str, Any]) -> list[str]:
    """Return every structural error found in a v1 collection."""
    errors: list[str] = []
    if collection.get("$schema") != SCHEMA_URI:
        errors.append("collection schema URI is not the v1 URI")
    if collection.get("schema_version") != SCHEMA_VERSION:
        errors.append("collection schema_version is not 1.0.0")
    if collection.get("record_type") != COLLECTION_TYPE:
        errors.append("collection record_type is invalid")
    if not isinstance(collection.get("comparison_finding"), dict):
        errors.append("comparison_finding must be an object")
    comparison_key = collection.get("comparison_key")
    if not _is_stable_id(comparison_key, "cmp"):
        errors.append("comparison_key is missing or invalid")
    records = collection.get("records")
    if not isinstance(records, list) or not records:
        errors.append("records must be a non-empty list")
        return errors

    record_ids: list[str] = []
    completed_pairs: set[tuple[str, str]] = set()
    for index, record in enumerate(records):
        prefix = f"records[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = RECORD_REQUIRED_FIELDS - record.keys()
        if missing:
            errors.append(f"{prefix} missing fields: {sorted(missing)}")
        if record.get("schema_version") != SCHEMA_VERSION:
            errors.append(f"{prefix} schema_version is invalid")
        if record.get("record_type") != RECORD_TYPE:
            errors.append(f"{prefix} record_type is invalid")
        if record.get("comparison_key") != comparison_key:
            errors.append(f"{prefix} comparison_key does not match collection")
        record_id = record.get("record_id")
        if not _is_stable_id(record_id, "rec"):
            errors.append(f"{prefix} record_id is invalid")
        else:
            record_ids.append(record_id)

        scenario = record.get("scenario")
        if not isinstance(scenario, dict) or not scenario.get("version"):
            errors.append(f"{prefix} dataset version is missing")
        controller_set = record.get("controller_set")
        if not isinstance(controller_set, dict) or any(
            not isinstance(controller_set.get(role), dict)
            or not controller_set[role].get("controller_id")
            for role in ROLES
        ):
            errors.append(f"{prefix} controller_set is incomplete")
        mutation = record.get("mutation")
        if (
            not isinstance(mutation, dict)
            or not isinstance(mutation.get("applied"), bool)
            or not isinstance(mutation.get("parameters"), dict)
        ):
            errors.append(f"{prefix} mutation context is incomplete")
        if not isinstance(record.get("metric_configuration"), dict):
            errors.append(f"{prefix} metric configuration is missing")
        if not isinstance(record.get("acceptance_gate_results"), dict):
            errors.append(f"{prefix} acceptance-gate results are missing")
        provenance = record.get("provenance")
        if not isinstance(provenance, dict):
            errors.append(f"{prefix} provenance is missing")
        else:
            if not provenance.get("git_revision"):
                errors.append(f"{prefix} Git revision is missing")
            if provenance.get("seed") is None:
                errors.append(f"{prefix} seed is missing")
            if not isinstance(provenance.get("hardware_class"), dict):
                errors.append(f"{prefix} hardware class is missing")

        if record.get("status") == "completed":
            role = record.get("controller_role")
            variant = record.get("variant")
            if record.get("record_kind") != "rollout":
                errors.append(f"{prefix} completed record_kind is wrong")
            if role not in ROLES:
                errors.append(f"{prefix} completed controller_role is invalid")
            if variant not in EXPORTED_VARIANTS.values():
                errors.append(f"{prefix} completed variant is invalid")
            controller = record.get("controller")
            if not isinstance(controller, dict):
                errors.append(f"{prefix} completed controller is missing")
            elif (
                role in ROLES
                and isinstance(controller_set, dict)
                and isinstance(controller_set.get(role), dict)
                and controller.get("controller_id")
                != controller_set[role].get("controller_id")
            ):
                errors.append(f"{prefix} controller does not match its role")
            expected_applied = variant == "counterfactual"
            if (
                isinstance(mutation, dict)
                and mutation.get("applied") != expected_applied
            ):
                errors.append(f"{prefix} mutation application is inconsistent")
            if record.get("outcome") is None:
                errors.append(f"{prefix} completed outcome is missing")
            if record.get("trajectory") is None:
                errors.append(f"{prefix} completed trajectory is missing")
            if record.get("reproducibility") is None:
                errors.append(f"{prefix} reproducibility is missing")
            if record.get("rejection_reasons"):
                errors.append(f"{prefix} completed record has rejections")
            if role in ROLES and variant in EXPORTED_VARIANTS.values():
                completed_pairs.add((variant, role))
        elif record.get("status") == "invalid":
            if record.get("record_kind") != "invalid_candidate":
                errors.append(f"{prefix} invalid record_kind is wrong")
            if not record.get("rejection_reasons"):
                errors.append(f"{prefix} invalid record lost rejection reasons")
            if record.get("variant") != "counterfactual":
                errors.append(f"{prefix} invalid variant must be counterfactual")
            if (
                isinstance(mutation, dict)
                and mutation.get("applied") is not False
            ):
                errors.append(f"{prefix} invalid mutation cannot be applied")
            if record.get("trajectory") is not None:
                errors.append(f"{prefix} invalid record has a trajectory")
            if record.get("outcome") is not None:
                errors.append(f"{prefix} invalid record has an outcome")
        else:
            errors.append(f"{prefix} status is invalid")

    if len(record_ids) != len(set(record_ids)):
        errors.append("record_id values are not unique")
    if collection.get("collection_status") == "complete":
        expected_pairs = {
            (variant, role)
            for variant in EXPORTED_VARIANTS.values()
            for role in ROLES
        }
        if completed_pairs != expected_pairs:
            errors.append("complete collection does not contain all four rollouts")
        if len(records) != 4:
            errors.append("complete collection must contain exactly four records")
    elif collection.get("collection_status") == "invalid_candidate":
        if len(records) != 1 or records[0].get("status") != "invalid":
            errors.append("invalid_candidate collection must contain one invalid record")
    else:
        errors.append("collection_status is invalid")
    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8"))
    collection = export_collection(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(collection, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "passed",
                "schema_version": collection["schema_version"],
                "collection_status": collection["collection_status"],
                "record_count": len(collection["records"]),
                "output": str(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
