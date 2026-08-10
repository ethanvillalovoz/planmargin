"""Data-free tests for the versioned rollout-record exporter."""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from planmargin import rollout_record


def _controller(role: str) -> dict[str, object]:
    return {
        "controller_id": f"{role}-controller-v1",
        "role": role,
        "implementation": "synthetic",
        "parameters": {"gain": 1.0},
    }


def _rollout(role: str, offset: float) -> dict[str, object]:
    trajectory = {
        "timestep": [10, 11],
        "x_m": [offset, offset + 1.0],
        "y_m": [0.0, 0.5],
        "yaw_rad": [0.0, 0.1],
        "speed_mps": [5.0, 5.1],
        "valid": [True, True],
    }
    return {
        "controller": _controller(role),
        "outputs_identical": True,
        "first_rollout_seconds": 1.0,
        "second_rollout_seconds": 0.5,
        "trajectory_sha256": rollout_record._content_sha256(trajectory),
        "non_sdc_input_sha256": f"input-{offset}",
        "input_unchanged_after_rollout": True,
        "outcome": {
            "success": True,
            "failure_reasons": [],
            "max_sdc_overlap": 0.0,
            "max_sdc_offroad": 0.0,
            "sdc_valid_all_steps": True,
            "final_timestep": 11,
            "expected_final_timestep": 11,
            "first_failure_timestep": None,
            "first_failure_reasons": [],
        },
        "trajectory": trajectory,
    }


def _actor_track(offset: float) -> dict[str, list[object]]:
    return {
        "timestep": [10, 11],
        "x_m": [offset, offset + 1.0],
        "y_m": [2.0, 2.5],
        "yaw_rad": [0.0, 0.1],
        "length_m": [4.5, 4.5],
        "width_m": [2.0, 2.0],
        "valid": [True, True],
    }


def _scene_context() -> dict[str, object]:
    return {
        "coordinate_frame": "Synthetic local Cartesian coordinates",
        "units": "meters",
        "bounds_m": {
            "min_x_m": -5.0,
            "max_x_m": 10.0,
            "min_y_m": -5.0,
            "max_y_m": 10.0,
        },
        "roadgraph_features": [
            {
                "feature_type": 2,
                "x_m": [-5.0, 10.0],
                "y_m": [0.0, 0.0],
            }
        ],
        "actors": {
            "sdc": {"object_type": 1, "length_m": 4.8, "width_m": 2.0},
            "mutation_target": {
                "object_type": 1,
                "original": _actor_track(0.0),
                "counterfactual": _actor_track(0.5),
            },
        },
    }


def _source(*, status: str = "passed") -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": status,
        "dataset": {
            "name": "Synthetic Motion Dataset",
            "version": "1.0",
            "split": "test",
            "scenario_id": "synthetic-scenario",
            "source_shard": "synthetic-shard",
            "record_index": 0,
            "mutated_object_index": 2,
        },
        "mutation": {
            "schema_version": 1,
            "mutation_type": "speed_multiplier",
            "accepted": status == "passed",
            "parameters": {"speed_multiplier": 0.9},
            "rejection_reasons": [],
            "metrics": {},
        },
        "controllers": {
            "tested": _controller("tested"),
            "reference": _controller("reference"),
        },
        "metric_definition": {"success_requires": ["complete rollout"]},
        "acceptance": {"all_rollouts_deterministic": True},
        "environment": {
            "git_commit": "deadbeef",
            "git_worktree_dirty": False,
            "waymax_git_commit": "waymax-revision",
            "comparison_source_sha256": "source-hash",
            "seed": 0,
            "python": "3.11",
            "jax": "1.0",
            "tensorflow": "2.0",
            "platform": "test-platform",
            "machine": "test-machine",
            "jax_backend": "cpu",
        },
        "limitations": ["Synthetic test only."],
        "finding": {"policy_specific_avoidable_failure": False},
        "scene_context": _scene_context(),
        "rollouts": {
            "original": {
                "tested": _rollout("tested", 0.0),
                "reference": _rollout("reference", 0.1),
            },
            "mutated": {
                "tested": _rollout("tested", 1.0),
                "reference": _rollout("reference", 1.1),
            },
        },
    }


def test_valid_export_contains_four_linked_rollout_records() -> None:
    collection = rollout_record.export_collection(_source())

    assert collection["schema_version"] == "1.1.0"
    assert collection["collection_status"] == "complete"
    assert len(collection["records"]) == 4
    assert collection["comparison_finding"] == {
        "policy_specific_avoidable_failure": False
    }
    assert {
        (record["variant"], record["controller_role"])
        for record in collection["records"]
    } == {
        ("original", "tested"),
        ("original", "reference"),
        ("counterfactual", "tested"),
        ("counterfactual", "reference"),
    }
    assert {
        record["comparison_key"] for record in collection["records"]
    } == {collection["comparison_key"]}
    assert rollout_record.validate_collection(collection) == []


def test_original_and_counterfactual_record_mutation_application() -> None:
    collection = rollout_record.export_collection(_source())
    by_variant = {
        record["variant"]: record for record in collection["records"]
    }

    assert by_variant["original"]["mutation"]["applied"] is False
    assert by_variant["counterfactual"]["mutation"]["applied"] is True


def test_export_is_deterministic() -> None:
    first = rollout_record.export_collection(_source())
    second = rollout_record.export_collection(_source())

    assert first == second
    assert len({record["record_id"] for record in first["records"]}) == 4


def test_record_id_changes_when_trajectory_changes() -> None:
    first = rollout_record.export_collection(_source())
    changed_source = _source()
    changed_rollout = changed_source["rollouts"]["original"]["tested"]
    changed_rollout["trajectory"]["x_m"][0] = 42.0
    changed_rollout["trajectory_sha256"] = rollout_record._content_sha256(
        changed_rollout["trajectory"]
    )
    second = rollout_record.export_collection(changed_source)

    first_record = next(
        record
        for record in first["records"]
        if record["variant"] == "original"
        and record["controller_role"] == "tested"
    )
    second_record = next(
        record
        for record in second["records"]
        if record["variant"] == "original"
        and record["controller_role"] == "tested"
    )

    assert first_record["comparison_key"] == second_record["comparison_key"]
    assert first_record["record_id"] != second_record["record_id"]


def test_comparison_key_changes_when_mutation_target_changes() -> None:
    first_source = _source()
    first_source["dataset"]["mutated_object_index"] = 2
    second_source = _source()
    second_source["dataset"]["mutated_object_index"] = 3

    first = rollout_record.export_collection(first_source)
    second = rollout_record.export_collection(second_source)

    assert first["comparison_key"] != second["comparison_key"]


def test_records_retain_required_reproducibility_context() -> None:
    record = rollout_record.export_collection(_source())["records"][0]

    assert record["controller_set"]["tested"]["controller_id"]
    assert record["controller_set"]["reference"]["controller_id"]
    assert record["metric_configuration"]
    assert record["acceptance_gate_results"]
    assert record["provenance"]["git_revision"] == "deadbeef"
    assert record["provenance"]["seed"] == 0
    assert record["provenance"]["hardware_class"]["jax_backend"] == "cpu"


def test_invalid_candidate_retains_rejection_reasons_without_trajectory() -> None:
    source = _source(status="rejected")
    source["mutation"]["rejection_reasons"] = [
        "acceleration_bound_exceeded"
    ]
    source.pop("rollouts")

    collection = rollout_record.export_collection(source)
    record = collection["records"][0]

    assert collection["collection_status"] == "invalid_candidate"
    assert record["status"] == "invalid"
    assert record["rejection_reasons"] == [
        "acceleration_bound_exceeded"
    ]
    assert record["trajectory"] is None
    assert record["outcome"] is None
    assert rollout_record.validate_collection(collection) == []


def test_invalid_candidate_without_specific_reason_gets_explicit_fallback() -> None:
    source = _source(status="rejected")
    source.pop("rollouts")

    collection = rollout_record.export_collection(source)

    assert collection["records"][0]["rejection_reasons"] == [
        "comparison_not_ready"
    ]


def test_early_invalid_candidate_can_omit_scene_context() -> None:
    source = _source(status="rejected")
    source.pop("rollouts")
    source.pop("scene_context")

    collection = rollout_record.export_collection(source)

    assert collection["scene_context"] is None
    assert collection["scene_context_sha256"] is None
    assert rollout_record.validate_collection(collection) == []


def test_validator_rejects_tampered_trajectory_content() -> None:
    collection = rollout_record.export_collection(_source())
    collection["records"][0]["trajectory"]["x_m"][0] = 999.0

    errors = rollout_record.validate_collection(collection)

    assert any("trajectory_sha256 does not match trajectory" in error for error in errors)


def test_validator_rejects_tampered_scene_context() -> None:
    collection = rollout_record.export_collection(_source())
    collection["scene_context"]["roadgraph_features"][0]["x_m"][0] = 999.0

    errors = rollout_record.validate_collection(collection)

    assert "scene_context_sha256 does not match scene context" in errors


def test_validator_rejects_unequal_trajectory_arrays() -> None:
    collection = rollout_record.export_collection(_source())
    collection["records"][0]["trajectory"]["valid"].pop()

    errors = rollout_record.validate_collection(collection)

    assert any("trajectory arrays must be non-empty and equal-length" in error for error in errors)


def test_validator_rejects_failure_without_first_failure_state() -> None:
    collection = rollout_record.export_collection(_source())
    outcome = collection["records"][0]["outcome"]
    outcome["success"] = False
    outcome["failure_reasons"] = ["sdc_overlap"]
    outcome["max_sdc_overlap"] = 1.0

    errors = rollout_record.validate_collection(collection)

    assert any("failed rollout requires a first failure timestep" in error for error in errors)
    assert any("failed rollout requires first failure reasons" in error for error in errors)


def test_validator_reports_malformed_arrays_without_raising() -> None:
    collection = rollout_record.export_collection(_source())
    trajectory = collection["records"][0]["trajectory"]
    trajectory["timestep"] = [10, "bad"]
    trajectory["valid"] = [False, False]
    track = collection["scene_context"]["actors"]["mutation_target"]["original"]
    track["length_m"] = ["bad", "bad"]
    outcome = collection["records"][0]["outcome"]
    outcome["success"] = False
    outcome["failure_reasons"] = [{"invalid": "reason"}]
    outcome["first_failure_timestep"] = 11
    outcome["first_failure_reasons"] = [{"invalid": "reason"}]

    errors = rollout_record.validate_collection(collection)

    assert any("timesteps must be strictly increasing integers" in error for error in errors)
    assert any("must contain at least one valid state" in error for error in errors)
    assert any("length_m must contain finite numbers" in error for error in errors)
    assert any("failure_reasons must contain strings" in error for error in errors)


def test_invalid_candidate_names_failed_acceptance_gates() -> None:
    source = _source(status="rejected")
    source["acceptance"] = {
        "mutation_core_accepted": True,
        "all_rollouts_deterministic": False,
        "identical_non_sdc_inputs_by_variant": {
            "original": True,
            "mutated": False,
        },
    }

    collection = rollout_record.export_collection(source)

    assert collection["records"][0]["rejection_reasons"] == [
        "acceptance_gate_failed:all_rollouts_deterministic",
        "acceptance_gate_failed:identical_non_sdc_inputs_by_variant.mutated",
    ]


def test_validator_detects_cross_collection_key_mismatch() -> None:
    collection = rollout_record.export_collection(_source())
    collection["records"][0]["comparison_key"] = "cmp_wrong"

    errors = rollout_record.validate_collection(collection)

    assert any("does not match collection" in error for error in errors)


def test_validator_rejects_malformed_collection_identifier() -> None:
    collection = rollout_record.export_collection(_source())
    collection["comparison_key"] = "cmp_not-a-sha256"

    errors = rollout_record.validate_collection(collection)

    assert "comparison_key is missing or invalid" in errors


def test_validator_rejects_well_formed_but_incorrect_identifiers() -> None:
    collection = rollout_record.export_collection(_source())
    forged_key = "cmp_" + "0" * 64
    forged_record_id = "rec_" + "0" * 64
    collection["comparison_key"] = forged_key
    for record in collection["records"]:
        record["comparison_key"] = forged_key
        record["record_id"] = forged_record_id

    errors = rollout_record.validate_collection(collection)

    assert any(
        "comparison_key does not match its identity" in error
        for error in errors
    )
    assert any(
        "record_id does not match its identity" in error
        for error in errors
    )


def test_validator_detects_variant_mutation_mismatch() -> None:
    collection = rollout_record.export_collection(_source())
    counterfactual = next(
        record
        for record in collection["records"]
        if record["variant"] == "counterfactual"
    )
    counterfactual["mutation"]["applied"] = False

    errors = rollout_record.validate_collection(collection)

    assert any("application is inconsistent" in error for error in errors)


def test_export_raises_when_required_controller_versions_are_missing() -> None:
    source = _source()
    source["controllers"]["reference"] = None

    with pytest.raises(rollout_record.RecordValidationError):
        rollout_record.export_collection(source)


def test_committed_json_schema_matches_exporter_constants() -> None:
    schema_path = (
        Path(__file__).parents[1]
        / "schemas"
        / "rollout-record-collection-v1.1.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["$id"] == rollout_record.SCHEMA_URI
    assert schema["properties"]["schema_version"]["const"] == (
        rollout_record.SCHEMA_VERSION
    )


@pytest.mark.parametrize("status", ["passed", "rejected"])
def test_committed_json_schema_accepts_exported_collections(
    status: str,
) -> None:
    schema_path = (
        Path(__file__).parents[1]
        / "schemas"
        / "rollout-record-collection-v1.1.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    source = _source(status=status)
    if status == "rejected":
        source["mutation"]["rejection_reasons"] = ["synthetic_rejection"]
        source.pop("rollouts")

    Draft202012Validator(schema).validate(
        rollout_record.export_collection(source)
    )


def test_committed_json_schema_rejects_inconsistent_mutation_state() -> None:
    schema_path = (
        Path(__file__).parents[1]
        / "schemas"
        / "rollout-record-collection-v1.1.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    collection = rollout_record.export_collection(_source())
    counterfactual = next(
        record
        for record in collection["records"]
        if record["variant"] == "counterfactual"
    )
    counterfactual["mutation"]["applied"] = False

    assert not Draft202012Validator(schema).is_valid(collection)


def test_export_does_not_mutate_source_report() -> None:
    source = _source()
    original = copy.deepcopy(source)

    rollout_record.export_collection(source)

    assert source == original
