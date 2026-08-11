"""Data-free tests for the deterministic uniform-random baseline."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from planmargin import random_search

REPOSITORY_ROOT = Path(__file__).parents[1]


def _candidates() -> list[dict[str, Any]]:
    return [
        {
            "family": "lead_vehicle_braking",
            "selection_order": order,
            "scenario_id": f"private-scenario-{order}",
            "source_shard": f"private-shard-{order // 3}",
            "shard_index": order // 3,
            "record_index": order * 7,
            "interacting_object_index": order + 1,
        }
        for order in range(1, 11)
    ]


def _write_manifest(path: Path) -> None:
    path.write_text(
        json.dumps({"candidates": _candidates()}), encoding="utf-8"
    )


def _outcome(success: bool) -> dict[str, Any]:
    return {
        "success": success,
        "failure_reasons": [] if success else ["sdc_overlap"],
        "max_sdc_overlap": 0.0 if success else 1.0,
        "max_sdc_offroad": 0.0,
        "sdc_valid_all_steps": True,
        "final_timestep": 90,
        "expected_final_timestep": 90,
        "first_failure_timestep": None if success else 40,
        "first_failure_reasons": [] if success else ["sdc_overlap"],
    }


def _controller(
    role: str, *, success: bool = True, changed: bool | None = None
) -> dict[str, Any]:
    return {
        "outputs_identical": True,
        "trajectory_sha256": f"{role}-trajectory-{success}-{changed}",
        "changed_from_original": changed,
        "outcome": _outcome(success),
        "interaction_metrics": {
            "jointly_valid_states": 81,
            "minimum_signed_separation_m": 1.5,
            "minimum_longitudinal_ttc_s": 2.5,
        },
        "first_rollout_seconds": 0.2,
        "second_rollout_seconds": 0.1,
    }


def _fake_original(
    scenario: Any,
    candidate: dict[str, Any],
    runners: dict[str, Any],
) -> dict[str, Any]:
    del scenario, candidate, runners
    return {
        "eligible": True,
        "controllers": {
            "tested": _controller("tested", changed=None),
            "reference": _controller("reference", changed=None),
        },
    }


def _fake_attempt(
    scenario: Any,
    candidate: dict[str, Any],
    onset_offset_s: float,
    speed_multiplier: float,
    runners: dict[str, Any],
    mutation_validator: Any,
    original: dict[str, Any],
) -> dict[str, Any]:
    del scenario, candidate, runners, mutation_validator, original
    parameters = {
        "braking_onset_offset_s": onset_offset_s,
        "speed_multiplier": speed_multiplier,
    }
    mutation = {
        "schema_version": 1,
        "mutation_type": "lead_braking_onset_and_speed",
        "accepted": onset_offset_s != 0.5,
        "parameters": parameters,
        "rejection_reasons": (
            ["mutated_progress_exceeds_recorded_route"]
            if onset_offset_s == 0.5
            else []
        ),
        "metrics": {},
    }
    record: dict[str, Any] = {
        "parameters": parameters,
        "identity_control": False,
        "mutation": mutation,
        "status": "mutation_rejected",
        "scenario_validation": None,
        "controllers": None,
        "elapsed_seconds": round(0.01 + onset_offset_s, 6),
    }
    if onset_offset_s == 0.5:
        return record
    scenario_accepted = onset_offset_s != 0.4
    record["scenario_validation"] = {
        "accepted": scenario_accepted,
        "rejection_reasons": (
            [] if scenario_accepted else ["mutated_object_offroad"]
        ),
        "outputs_identical": True,
        "trajectory_sha256": "scenario-validation-hash",
    }
    if not scenario_accepted:
        record["status"] = "scenario_rejected"
        return record
    tested_success = speed_multiplier >= 0.77
    record["status"] = "accepted"
    record["controllers"] = {
        "tested": _controller(
            "tested", success=tested_success, changed=True
        ),
        "reference": _controller(
            "reference", success=True, changed=True
        ),
    }
    return record


@pytest.fixture
def fake_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        random_search.controller_comparison,
        "ControllerRunner",
        lambda spec: {"controller": spec.controller_id},
    )
    monkeypatch.setattr(
        random_search.speed_mutation,
        "MutationValidator",
        lambda **kwargs: {"validator": kwargs},
    )


def _loader(manifest_path: Path) -> list[tuple[Any, dict[str, Any]]]:
    del manifest_path
    return [(object(), candidate) for candidate in _candidates()]


def _run(
    manifest: Path,
    output_dir: Path,
    config: random_search.RandomSearchConfig,
    **kwargs: Any,
) -> dict[str, Any]:
    return random_search.run(
        manifest,
        output_dir,
        config,
        scenario_loader=_loader,
        original_evaluator=_fake_original,
        attempt_evaluator=_fake_attempt,
        **kwargs,
    )


def _without_invocation_observations(report: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(report)
    del result["report_sha256"]
    del result["metrics"]["final_invocation_seconds"]
    del result["metrics"]["process_peak_rss_bytes"]
    return result


def _validate_with_schema(record: dict[str, Any], schema_name: str) -> None:
    schema = json.loads(
        (REPOSITORY_ROOT / "schemas" / schema_name).read_text(encoding="utf-8")
    )
    Draft202012Validator(schema).validate(record)


def test_stateless_proposals_are_pinned_and_within_bounds() -> None:
    config = random_search.RandomSearchConfig()

    assert random_search.proposal_parameters(config, 1, 0) == {
        "braking_onset_offset_s": 0.3,
        "speed_multiplier": 0.8892845125515566,
    }
    assert random_search.proposal_parameters(config, 1, 1) == {
        "braking_onset_offset_s": 0.4,
        "speed_multiplier": 0.8135644568722702,
    }
    proposals = [
        random_search.proposal_parameters(config, order, index)
        for order in range(1, 11)
        for index in range(config.budget_per_scenario)
    ]

    assert len(proposals) == 320
    assert all(
        proposal["braking_onset_offset_s"]
        in random_search.ONSET_OFFSETS_S
        for proposal in proposals
    )
    assert all(
        0.75 <= proposal["speed_multiplier"] <= 1.0
        for proposal in proposals
    )


def test_invalid_seed_is_rejected_before_sampling() -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        random_search.RandomSearchConfig(seed=-1)


def test_proposals_do_not_depend_on_request_order() -> None:
    config = random_search.RandomSearchConfig()
    coordinates = [(1, 0), (10, 31), (2, 7), (1, 3)]
    forward = {
        coordinate: random_search.proposal_parameters(config, *coordinate)
        for coordinate in coordinates
    }
    reverse = {
        coordinate: random_search.proposal_parameters(config, *coordinate)
        for coordinate in reversed(coordinates)
    }

    assert forward == reverse


def test_normalized_mutation_distance_matches_frozen_definition() -> None:
    assert random_search.normalized_mutation_distance(
        {"braking_onset_offset_s": 0.0, "speed_multiplier": 1.0}
    ) == 0.0
    assert random_search.normalized_mutation_distance(
        {"braking_onset_offset_s": 0.5, "speed_multiplier": 0.75}
    ) == pytest.approx(2**0.5)


def test_cost_accounting_includes_rejections_and_physical_reruns() -> None:
    rejected = _fake_attempt(None, {}, 0.5, 0.8, {}, None, {})
    accepted = _fake_attempt(None, {}, 0.2, 0.8, {}, None, {})

    assert random_search.proposal_cost(rejected) == {
        "core_mutation_attempts": 1,
        "scenario_validation_logical_evaluations": 0,
        "scenario_validation_physical_rollouts": 0,
        "tested_controller_logical_evaluations": 0,
        "tested_controller_physical_rollouts": 0,
        "reference_controller_logical_evaluations": 0,
        "reference_controller_physical_rollouts": 0,
        "total_physical_rollouts": 0,
        "waymax_rollout_steps": 0,
    }
    assert random_search.proposal_cost(accepted)[
        "total_physical_rollouts"
    ] == 6
    assert random_search.proposal_cost(accepted)[
        "waymax_rollout_steps"
    ] == 480


def test_atomic_json_write_rejects_nonfinite_values(tmp_path: Path) -> None:
    target = tmp_path / "checkpoint.json"

    with pytest.raises(ValueError):
        random_search._atomic_write_json(target, {"value": float("nan")})

    assert not target.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_private_output_directory_is_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    random_search.validate_private_output_dir(
        Path("artifacts/random-search/allowed")
    )
    with pytest.raises(ValueError, match="must remain under artifacts"):
        random_search.validate_private_output_dir(Path("experiments/private"))


@pytest.mark.parametrize("selection_orders", [[1, 1], [11]])
def test_invalid_selection_orders_do_not_initialize_a_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_runtime: None,
    selection_orders: list[int],
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = tmp_path / "selection.json"
    _write_manifest(manifest)
    output_dir = Path("artifacts/random-search/invalid-selection")

    with pytest.raises(ValueError, match="selection_orders"):
        _run(
            manifest,
            output_dir,
            random_search.RandomSearchConfig(budget_per_scenario=1),
            selection_orders=selection_orders,
        )

    assert not output_dir.exists()


def test_interrupted_resume_matches_uninterrupted_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_runtime: None,
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = tmp_path / "selection.json"
    _write_manifest(manifest)
    config = random_search.RandomSearchConfig(budget_per_scenario=2)
    resumed_dir = Path("artifacts/random-search/resumed")
    full_dir = Path("artifacts/random-search/full")

    progress = _run(
        manifest,
        resumed_dir,
        config,
        selection_orders=[2, 1],
        max_new_proposals=3,
    )
    resumed = _run(manifest, resumed_dir, config, resume=True)
    full = _run(manifest, full_dir, config)

    assert progress["status"] == "in_progress"
    assert progress["completed_proposal_count"] == 3
    assert resumed["decision"] == "baseline_complete"
    assert resumed["metrics"]["proposal_count"] == 20
    assert resumed["metrics"]["scenario_count"] == 10
    assert all(resumed["integrity_gates"].values())
    assert _without_invocation_observations(
        resumed
    ) == _without_invocation_observations(full)
    for candidate in _candidates():
        order = candidate["selection_order"]
        assert json.loads(
            random_search._original_path(resumed_dir, order).read_text(
                encoding="utf-8"
            )
        ) == json.loads(
            random_search._original_path(full_dir, order).read_text(
                encoding="utf-8"
            )
        )
        for proposal_index in range(config.budget_per_scenario):
            assert json.loads(
                random_search._proposal_path(
                    resumed_dir, order, proposal_index
                ).read_text(encoding="utf-8")
            ) == json.loads(
                random_search._proposal_path(
                    full_dir, order, proposal_index
                ).read_text(encoding="utf-8")
            )


def test_completed_resume_performs_no_new_evaluations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_runtime: None,
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = tmp_path / "selection.json"
    _write_manifest(manifest)
    output_dir = Path("artifacts/random-search/complete")
    config = random_search.RandomSearchConfig(budget_per_scenario=1)
    completed = _run(manifest, output_dir, config)

    def fail_loader(path: Path) -> list[tuple[Any, dict[str, Any]]]:
        raise AssertionError(f"completed resume reloaded scenarios: {path}")

    resumed = random_search.run(
        manifest,
        output_dir,
        config,
        resume=True,
        scenario_loader=fail_loader,
        original_evaluator=_fake_original,
        attempt_evaluator=_fake_attempt,
    )

    assert resumed == completed


def test_completed_resume_revalidates_report_against_checkpoints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_runtime: None,
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = tmp_path / "selection.json"
    _write_manifest(manifest)
    output_dir = Path("artifacts/random-search/complete-tampered")
    config = random_search.RandomSearchConfig(budget_per_scenario=1)
    _run(manifest, output_dir, config)
    proposal_path = random_search._proposal_path(output_dir, 1, 0)
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    del proposal["record_sha256"]
    proposal["attempt"]["elapsed_seconds"] = 42.0
    proposal_path.write_text(
        json.dumps(random_search._seal_record(proposal, "record_sha256")),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError, match="Completed report does not match durable checkpoints"
    ):
        _run(manifest, output_dir, config, resume=True)


def test_completed_resume_requires_the_complete_checkpoint_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_runtime: None,
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = tmp_path / "selection.json"
    _write_manifest(manifest)
    output_dir = Path("artifacts/random-search/complete-missing")
    config = random_search.RandomSearchConfig(budget_per_scenario=1)
    _run(manifest, output_dir, config)
    random_search._proposal_path(output_dir, 1, 0).unlink()

    with pytest.raises(
        ValueError, match="without the complete checkpoint set"
    ):
        _run(manifest, output_dir, config, resume=True)


def test_completed_resume_rejects_resealed_report_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_runtime: None,
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = tmp_path / "selection.json"
    _write_manifest(manifest)
    output_dir = Path("artifacts/random-search/report-tampered")
    config = random_search.RandomSearchConfig(budget_per_scenario=1)
    _run(manifest, output_dir, config)
    report_path = output_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    del report["report_sha256"]
    report["metrics"]["proposal_count"] = 999
    report_path.write_text(
        json.dumps(random_search._seal_record(report, "report_sha256")),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError, match="Completed report does not match durable checkpoints"
    ):
        _run(manifest, output_dir, config, resume=True)


def test_resume_refuses_configuration_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_runtime: None,
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = tmp_path / "selection.json"
    _write_manifest(manifest)
    output_dir = Path("artifacts/random-search/mismatch")
    _run(
        manifest,
        output_dir,
        random_search.RandomSearchConfig(seed=0, budget_per_scenario=1),
        max_new_proposals=1,
    )

    with pytest.raises(ValueError, match="Run configuration mismatch"):
        _run(
            manifest,
            output_dir,
            random_search.RandomSearchConfig(seed=1, budget_per_scenario=1),
            resume=True,
        )


def test_resume_refuses_environment_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_runtime: None,
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = tmp_path / "selection.json"
    _write_manifest(manifest)
    output_dir = Path("artifacts/random-search/environment-mismatch")
    config = random_search.RandomSearchConfig(budget_per_scenario=1)
    _run(manifest, output_dir, config, max_new_proposals=1)
    monkeypatch.setattr(random_search.platform, "machine", lambda: "changed")

    with pytest.raises(ValueError, match="Run environment mismatch"):
        _run(manifest, output_dir, config, resume=True)


def test_resume_rejects_tampered_and_unexpected_checkpoints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_runtime: None,
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = tmp_path / "selection.json"
    _write_manifest(manifest)
    output_dir = Path("artifacts/random-search/tampered")
    config = random_search.RandomSearchConfig(budget_per_scenario=1)
    _run(manifest, output_dir, config, max_new_proposals=1)
    proposal_path = random_search._proposal_path(output_dir, 1, 0)
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    proposal["attempt"]["elapsed_seconds"] = 42.0
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")

    with pytest.raises(ValueError, match="content hash mismatch"):
        _run(manifest, output_dir, config, resume=True)

    proposal_path.write_text(
        json.dumps(
            random_search.build_proposal_record(
                random_search._read_json_object(output_dir / "run-manifest.json"),
                _candidates()[0],
                0,
                random_search.proposal_parameters(config, 1, 0),
                _fake_original(None, {}, {}),
                _fake_attempt(
                    None,
                    {},
                    random_search.proposal_parameters(config, 1, 0)[
                        "braking_onset_offset_s"
                    ],
                    random_search.proposal_parameters(config, 1, 0)[
                        "speed_multiplier"
                    ],
                    runners={},
                    mutation_validator=None,
                    original={},
                ),
            )
        ),
        encoding="utf-8",
    )
    unexpected = output_dir / "proposals" / "scenario-01" / "proposal-9999.json"
    unexpected.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Unexpected proposal"):
        _run(manifest, output_dir, config, resume=True)


def test_resume_rederives_cost_instead_of_trusting_resealed_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_runtime: None,
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = tmp_path / "selection.json"
    _write_manifest(manifest)
    output_dir = Path("artifacts/random-search/resealed")
    config = random_search.RandomSearchConfig(budget_per_scenario=1)
    _run(manifest, output_dir, config, max_new_proposals=1)
    proposal_path = random_search._proposal_path(output_dir, 1, 0)
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    del proposal["record_sha256"]
    proposal["cost"]["waymax_rollout_steps"] = 999
    resealed = random_search._seal_record(proposal, "record_sha256")
    proposal_path.write_text(json.dumps(resealed), encoding="utf-8")

    with pytest.raises(ValueError, match="cost accounting mismatch"):
        _run(manifest, output_dir, config, resume=True)


def test_resume_rejects_resealed_schema_identifier_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_runtime: None,
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = tmp_path / "selection.json"
    _write_manifest(manifest)
    output_dir = Path("artifacts/random-search/schema-mismatch")
    config = random_search.RandomSearchConfig(budget_per_scenario=1)
    _run(manifest, output_dir, config, max_new_proposals=1)
    proposal_path = random_search._proposal_path(output_dir, 1, 0)
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    del proposal["record_sha256"]
    proposal["$schema"] = "https://example.invalid/wrong-schema.json"
    proposal_path.write_text(
        json.dumps(random_search._seal_record(proposal, "record_sha256")),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="schema identifier mismatch"):
        _run(manifest, output_dir, config, resume=True)


def test_generated_private_records_match_versioned_schemas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_runtime: None,
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = tmp_path / "selection.json"
    _write_manifest(manifest)
    output_dir = Path("artifacts/random-search/schema")
    report = _run(
        manifest,
        output_dir,
        random_search.RandomSearchConfig(budget_per_scenario=1),
    )
    run_manifest = json.loads(
        (output_dir / "run-manifest.json").read_text(encoding="utf-8")
    )
    original = json.loads(
        random_search._original_path(output_dir, 1).read_text(encoding="utf-8")
    )
    proposal = json.loads(
        random_search._proposal_path(output_dir, 1, 0).read_text(
            encoding="utf-8"
        )
    )

    _validate_with_schema(
        run_manifest, "random-search-run-manifest-v1.schema.json"
    )
    _validate_with_schema(
        original, "random-search-original-v1.schema.json"
    )
    _validate_with_schema(
        proposal, "random-search-proposal-v1.schema.json"
    )
    _validate_with_schema(report, "random-search-report-v1.schema.json")


def test_finding_requires_both_original_controllers_to_pass(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "selection.json"
    _write_manifest(manifest_path)
    run_manifest = random_search.build_run_manifest(
        manifest_path,
        _candidates(),
        random_search.RandomSearchConfig(budget_per_scenario=1),
    )
    original = _fake_original(None, {}, {})
    original["eligible"] = False
    original["controllers"]["tested"]["outcome"] = _outcome(False)
    parameters = {"braking_onset_offset_s": 0.2, "speed_multiplier": 0.76}
    attempt = _fake_attempt(None, {}, 0.2, 0.76, {}, None, {})

    record = random_search.build_proposal_record(
        run_manifest,
        _candidates()[0],
        0,
        parameters,
        original,
        attempt,
    )

    assert record["finding"]["tested_mutated_failure"] is True
    assert record["finding"]["reference_mutated_success"] is True
    assert record["finding"]["policy_specific_avoidable_failure"] is False


def test_public_summary_excludes_private_scenario_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_runtime: None,
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = tmp_path / "selection.json"
    _write_manifest(manifest)
    output_dir = Path("artifacts/random-search/privacy")
    report = _run(
        manifest,
        output_dir,
        random_search.RandomSearchConfig(budget_per_scenario=1),
    )

    summary = random_search.public_summary(report, output_dir)

    assert "private-scenario" not in json.dumps(summary)
    assert "scenario_summaries" not in summary
    assert summary["proposal_count"] == 10
