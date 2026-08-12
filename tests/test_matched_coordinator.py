"""Data-free checks for the method-neutral matched-search cell coordinator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from planmargin import behavior_features
from planmargin import empirical_support
from planmargin import matched_coordinator
from planmargin import matched_search
from planmargin import random_search

REPOSITORY_ROOT = Path(__file__).parents[1]


def _candidates() -> list[dict[str, Any]]:
    return [
        {
            "family": "lead_vehicle_braking",
            "selection_order": order,
            "scenario_id": f"private-scenario-{order}",
            "source_shard": "private-training-shard",
            "shard_index": 0,
            "record_index": order * 11,
            "interacting_object_index": order + 1,
        }
        for order in range(1, 11)
    ]


def _write_manifest(path: Path) -> None:
    path.write_text(json.dumps({"candidates": _candidates()}), encoding="utf-8")


def _vector(index: int) -> list[float]:
    offset = index / 100.0
    return [
        20.0 + offset,
        1.0 + offset,
        10.0 + offset,
        3.0 + offset,
        4.0 + offset,
        1.5 + offset,
        0.9 + offset / 10.0,
        2.0 + offset,
    ]


def _write_support_model(path: Path) -> dict[str, Any]:
    events = [
        {"event_key": f"{index:064x}", "vector": _vector(index)}
        for index in range(20)
    ]
    model = empirical_support.fit_model(events, configuration_fingerprint="a" * 64)
    path.write_text(json.dumps(model, sort_keys=True), encoding="utf-8")
    return model


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


def _controller(role: str, *, success: bool, separation: float) -> dict[str, Any]:
    return {
        "outputs_identical": True,
        "trajectory_sha256": f"{role}-{success}-{separation}",
        "changed_from_original": True,
        "outcome": _outcome(success),
        "interaction_metrics": {
            "jointly_valid_states": 81,
            "minimum_signed_separation_m": separation,
            "minimum_longitudinal_ttc_s": 2.0,
        },
        "first_rollout_seconds": 0.02,
        "second_rollout_seconds": 0.01,
    }


def _original(
    scenario: Any,
    candidate: dict[str, Any],
    tested: Any,
    reference: Any,
) -> dict[str, Any]:
    del scenario, candidate, tested, reference
    return {
        "eligible": True,
        "controllers": {
            "tested": _controller("tested-original", success=True, separation=2.0),
            "reference": _controller(
                "reference-original", success=True, separation=2.0
            ),
        },
    }


def _feature(index: int = 10) -> dict[str, Any]:
    vector = _vector(index)
    audit = {
        name: vector[position]
        for position, name in enumerate(behavior_features.FEATURE_NAMES)
    }
    audit["current_sdc_speed_mps"] = 12.0
    audit["maximum_absolute_jerk_mps3"] = 6.5
    return {
        "feature_schema_version": behavior_features.FEATURE_SCHEMA_VERSION,
        "accepted": True,
        "rejection_reasons": [],
        "audit_metrics": audit,
        "feature_names": list(behavior_features.FEATURE_NAMES),
        "vector": vector,
    }


def _attempt(
    scenario: Any,
    candidate: dict[str, Any],
    parameters: dict[str, float],
    tested: Any,
    reference: Any,
    support_model: dict[str, Any],
    original: dict[str, Any],
) -> dict[str, Any]:
    del scenario, candidate, tested, reference, support_model, original
    onset = parameters["braking_onset_offset_s"]
    multiplier = parameters["speed_multiplier"]
    tested_success = multiplier >= 0.79
    attempt = {
        "parameters": parameters,
        "identity_control": onset == 0.0 and multiplier == 1.0,
        "mutation": {
            "schema_version": 1,
            "mutation_type": "lead_braking_onset_and_speed",
            "accepted": True,
            "parameters": parameters,
            "rejection_reasons": [],
            "metrics": {},
        },
        "status": "accepted",
        "scenario_validation": {
            "accepted": True,
            "rejection_reasons": [],
            "outputs_identical": True,
            "trajectory_sha256": "scenario-validation-hash",
        },
        "controllers": {
            "tested": _controller(
                "tested", success=tested_success, separation=max(0.0, multiplier - 0.75)
            ),
            "reference": _controller("reference", success=True, separation=1.0),
        },
        "elapsed_seconds": 0.05,
    }
    feature = _feature()
    if onset == 0.5:
        feature = {
            "feature_schema_version": behavior_features.FEATURE_SCHEMA_VERSION,
            "accepted": False,
            "rejection_reasons": ["six_second_window_incomplete"],
            "audit_metrics": {},
            "feature_names": list(behavior_features.FEATURE_NAMES),
            "vector": None,
        }
    return {"attempt": attempt, "feature": feature}


def _attempt_with_rejections(
    scenario: Any,
    candidate: dict[str, Any],
    parameters: dict[str, float],
    tested: Any,
    reference: Any,
    support_model: dict[str, Any],
    original: dict[str, Any],
) -> dict[str, Any]:
    evaluation = _attempt(
        scenario,
        candidate,
        parameters,
        tested,
        reference,
        support_model,
        original,
    )
    if parameters["braking_onset_offset_s"] != 0.5:
        return evaluation
    attempt = evaluation["attempt"]
    attempt["mutation"]["accepted"] = False
    attempt["mutation"]["rejection_reasons"] = [
        "mutated_progress_exceeds_recorded_route"
    ]
    attempt["status"] = "mutation_rejected"
    attempt["scenario_validation"] = None
    attempt["controllers"] = None
    return {"attempt": attempt, "feature": None}


def _loader(
    manifest_path: Path, selection_order: int
) -> tuple[Any, dict[str, Any]]:
    del manifest_path
    return object(), _candidates()[selection_order - 1]


def _constant_optimizer(
    seed: int,
    selection_order: int,
    proposal_index: int,
    observations: list[matched_search.OutcomeRecord],
) -> tuple[tuple[float, float], dict[str, Any]]:
    del seed, selection_order, observations
    return (0.2, 0.78), {"synthetic_step": proposal_index}


def _run(
    *,
    manifest: Path,
    model: Path,
    output: Path,
    cell: matched_coordinator.CellConfig,
    **kwargs: Any,
) -> dict[str, Any]:
    return matched_coordinator.run(
        manifest_path=manifest,
        support_model_path=model,
        output_dir=output,
        cell=cell,
        scenario_loader=_loader,
        original_evaluator=_original,
        attempt_evaluator=_attempt,
        optimizer=_constant_optimizer,
        **kwargs,
    )


def _prepare(tmp_path: Path) -> tuple[Path, Path]:
    manifest = tmp_path / "selection.json"
    model = tmp_path / "support-model.json"
    _write_manifest(manifest)
    _write_support_model(model)
    return manifest, model


def _schema(name: str) -> dict[str, Any]:
    return json.loads((REPOSITORY_ROOT / "schemas" / name).read_text())


def test_track_controller_and_cell_identity_are_frozen() -> None:
    natural = matched_coordinator.tested_controller_for_track("natural")
    regression = matched_coordinator.tested_controller_for_track(
        "headway_regression"
    )

    assert natural.safe_time_headway_s == 2.0
    assert regression.safe_time_headway_s == 1.0
    assert regression.controller_id == "planmargin-idm-headway-regression-v1"
    assert dataclass_difference(natural, regression) == {
        "controller_id",
        "safe_time_headway_s",
    }
    with pytest.raises(ValueError, match="seed"):
        matched_coordinator.CellConfig("random", "natural", True, 1)
    with pytest.raises(ValueError, match="selection_order"):
        matched_coordinator.CellConfig("random", "natural", 0, 11)


def test_attempt_evaluator_receives_the_validated_support_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, model_path = _prepare(tmp_path)
    expected_model = empirical_support.load_model(model_path)
    observed_fingerprints: list[str] = []

    def evaluator(
        scenario: Any,
        candidate: dict[str, Any],
        parameters: dict[str, float],
        tested: Any,
        reference: Any,
        support_model: dict[str, Any],
        original: dict[str, Any],
    ) -> dict[str, Any]:
        assert support_model == expected_model
        observed_fingerprints.append(support_model["model_fingerprint"])
        return _attempt(
            scenario,
            candidate,
            parameters,
            tested,
            reference,
            support_model,
            original,
        )

    result = matched_coordinator.run(
        manifest_path=manifest,
        support_model_path=model_path,
        output_dir=Path("artifacts/search-comparison/support-model-seam"),
        cell=matched_coordinator.CellConfig("random", "natural", 0, 1),
        max_new_proposals=1,
        scenario_loader=_loader,
        original_evaluator=_original,
        attempt_evaluator=evaluator,
    )

    assert result["completed_proposal_count"] == 1
    assert observed_fingerprints == [expected_model["model_fingerprint"]]


def dataclass_difference(first: Any, second: Any) -> set[str]:
    return {
        field
        for field in first.__dataclass_fields__
        if getattr(first, field) != getattr(second, field)
    }


def test_both_methods_complete_equal_budgets_and_shared_accounting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, model = _prepare(tmp_path)
    reports = {}
    for method in matched_search.METHODS:
        cell = matched_coordinator.CellConfig(method, "natural", 0, 1)
        reports[method] = _run(
            manifest=manifest,
            model=model,
            output=Path(f"artifacts/search-comparison/{method}"),
            cell=cell,
        )

    assert all(report["decision"] == "cell_complete" for report in reports.values())
    assert {report["metrics"]["proposal_count"] for report in reports.values()} == {32}
    assert {
        report["cost"]["total"]["total_physical_rollouts"]
        for report in reports.values()
    } == {196}
    assert all(
        4
        <= report["metrics"][
            "restricted_physical_rollouts_to_first_qualifying_failure"
        ]
        <= 196
        for report in reports.values()
    )
    assert all(report["metrics"]["qualifying_failure_count"] > 0 for report in reports.values())
    assert reports["bayesian"]["metrics"]["duplicate_proposal_count"] == 23
    assert reports["bayesian"]["metrics"]["support_and_pipeline_valid_count"] < 32

    bayesian_dir = Path("artifacts/search-comparison/bayesian")
    unsupported = [
        json.loads(path.read_text())
        for path in sorted((bayesian_dir / "proposals").glob("*.json"))
        if json.loads(path.read_text())["support"] is None
    ]
    assert unsupported
    assert all(record["attempt"]["controllers"] is not None for record in unsupported)
    assert all(record["cost"]["total_physical_rollouts"] == 6 for record in unsupported)


def test_rejected_proposals_remain_in_the_complete_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, model = _prepare(tmp_path)
    output = Path("artifacts/search-comparison/rejections")
    cell = matched_coordinator.CellConfig("random", "natural", 0, 1)
    report = matched_coordinator.run(
        manifest_path=manifest,
        support_model_path=model,
        output_dir=output,
        cell=cell,
        scenario_loader=_loader,
        original_evaluator=_original,
        attempt_evaluator=_attempt_with_rejections,
    )
    proposals = [
        json.loads(path.read_text())
        for path in sorted((output / "proposals").glob("*.json"))
    ]
    rejected = [
        record
        for record in proposals
        if record["attempt"]["status"] == "mutation_rejected"
    ]

    assert report["metrics"]["proposal_count"] == 32
    assert rejected
    assert all(record["cost"]["core_mutation_attempts"] == 1 for record in rejected)
    assert all(record["cost"]["total_physical_rollouts"] == 0 for record in rejected)
    assert all(record["outcome"]["objectives"] == [0.0, 0.0] for record in rejected)


def test_no_finding_physical_cost_is_censored_at_the_complete_horizon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, model = _prepare(tmp_path)

    def no_finding_attempt(*args: Any, **kwargs: Any) -> dict[str, Any]:
        evaluation = _attempt(*args, **kwargs)
        tested = evaluation["attempt"]["controllers"]["tested"]
        tested["outcome"] = _outcome(True)
        return evaluation

    report = matched_coordinator.run(
        manifest_path=manifest,
        support_model_path=model,
        output_dir=Path("artifacts/search-comparison/no-findings"),
        cell=matched_coordinator.CellConfig("random", "natural", 0, 1),
        scenario_loader=_loader,
        original_evaluator=_original,
        attempt_evaluator=no_finding_attempt,
    )

    assert report["metrics"]["qualifying_failure_count"] == 0
    assert report["metrics"]["first_qualifying_failure_proposal_count"] is None
    assert report["metrics"][
        "restricted_physical_rollouts_to_first_qualifying_failure"
    ] == report["cost"]["total"]["total_physical_rollouts"]


def test_interrupted_resume_matches_uninterrupted_scientific_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, model = _prepare(tmp_path)
    cell = matched_coordinator.CellConfig("bayesian", "headway_regression", 4, 3)
    resumed_dir = Path("artifacts/search-comparison/resumed")
    full_dir = Path("artifacts/search-comparison/full")

    progress = _run(
        manifest=manifest,
        model=model,
        output=resumed_dir,
        cell=cell,
        max_new_proposals=11,
    )
    resumed = _run(
        manifest=manifest,
        model=model,
        output=resumed_dir,
        cell=cell,
        resume=True,
    )
    full = _run(
        manifest=manifest,
        model=model,
        output=full_dir,
        cell=cell,
    )

    assert progress["completed_proposal_count"] == 11
    assert resumed["decision"] == full["decision"] == "cell_complete"
    for index in range(32):
        resumed_selection = json.loads(
            matched_coordinator._selection_path(resumed_dir, index).read_text()
        )
        full_selection = json.loads(
            matched_coordinator._selection_path(full_dir, index).read_text()
        )
        assert resumed_selection["decision"] == full_selection["decision"]
        resumed_proposal = json.loads(
            matched_coordinator._proposal_path(resumed_dir, index).read_text()
        )
        full_proposal = json.loads(
            matched_coordinator._proposal_path(full_dir, index).read_text()
        )
        for field in (
            "proposal",
            "attempt",
            "feature",
            "support",
            "outcome",
            "finding",
            "cost",
        ):
            assert resumed_proposal[field] == full_proposal[field]


def test_completed_resume_performs_no_evaluator_or_scenario_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, model = _prepare(tmp_path)
    output = Path("artifacts/search-comparison/complete")
    cell = matched_coordinator.CellConfig("random", "natural", 1, 2)
    completed = _run(manifest=manifest, model=model, output=output, cell=cell)

    def fail(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise AssertionError("completed resume performed evaluator work")

    resumed = matched_coordinator.run(
        manifest_path=manifest,
        support_model_path=model,
        output_dir=output,
        cell=cell,
        resume=True,
        scenario_loader=fail,
        original_evaluator=fail,
        attempt_evaluator=fail,
    )

    assert resumed == completed


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("support", "support-score derivation"),
        ("outcome", "objective or constraint derivation"),
        ("finding", "finding derivation"),
        ("cost", "cost accounting"),
    ],
)
def test_resume_rejects_resealed_derived_proposal_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    message: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, model = _prepare(tmp_path)
    output = Path(f"artifacts/search-comparison/tampered-{field}")
    cell = matched_coordinator.CellConfig("random", "natural", 0, 1)
    _run(
        manifest=manifest,
        model=model,
        output=output,
        cell=cell,
        max_new_proposals=1,
    )
    path = matched_coordinator._proposal_path(output, 0)
    record = json.loads(path.read_text())
    del record["record_sha256"]
    if field == "support":
        record[field]["p_support"] = 0.123
    elif field == "outcome":
        record[field]["objectives"][0] = 0.123
    elif field == "finding":
        record[field]["policy_specific_avoidable_failure"] = not record[field][
            "policy_specific_avoidable_failure"
        ]
    else:
        record[field]["waymax_rollout_steps"] = 999
    path.write_text(
        json.dumps(random_search._seal_record(record, "record_sha256")),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        _run(
            manifest=manifest,
            model=model,
            output=output,
            cell=cell,
            resume=True,
        )


def test_resume_rejects_resealed_selection_history_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, model = _prepare(tmp_path)
    output = Path("artifacts/search-comparison/history-tampered")
    cell = matched_coordinator.CellConfig("bayesian", "natural", 0, 1)
    _run(
        manifest=manifest,
        model=model,
        output=output,
        cell=cell,
        max_new_proposals=2,
    )
    path = matched_coordinator._selection_path(output, 1)
    record = json.loads(path.read_text())
    del record["selection_sha256"]
    record["history"]["history_fingerprint"] = "b" * 64
    path.write_text(
        json.dumps(random_search._seal_record(record, "selection_sha256")),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="observation history"):
        _run(
            manifest=manifest,
            model=model,
            output=output,
            cell=cell,
            resume=True,
        )


def test_resume_rejects_resealed_parameter_and_selection_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, model = _prepare(tmp_path)
    cell = matched_coordinator.CellConfig("random", "natural", 0, 1)

    proposal_output = Path("artifacts/search-comparison/parameter-tampered")
    _run(
        manifest=manifest,
        model=model,
        output=proposal_output,
        cell=cell,
        max_new_proposals=1,
    )
    proposal_path = matched_coordinator._proposal_path(proposal_output, 0)
    proposal = json.loads(proposal_path.read_text())
    del proposal["record_sha256"]
    proposal["proposal"]["parameters"]["speed_multiplier"] = 0.75
    proposal_path.write_text(
        json.dumps(random_search._seal_record(proposal, "record_sha256")),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="parameters do not match selection"):
        _run(
            manifest=manifest,
            model=model,
            output=proposal_output,
            cell=cell,
            resume=True,
        )

    selection_output = Path("artifacts/search-comparison/selection-tampered")
    _run(
        manifest=manifest,
        model=model,
        output=selection_output,
        cell=cell,
        max_new_proposals=1,
    )
    selection_path = matched_coordinator._selection_path(selection_output, 0)
    selection = json.loads(selection_path.read_text())
    del selection["selection_sha256"]
    selection["decision"]["parameters"]["speed_multiplier"] = 0.75
    selection_path.write_text(
        json.dumps(random_search._seal_record(selection, "selection_sha256")),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="decision does not reproduce"):
        _run(
            manifest=manifest,
            model=model,
            output=selection_output,
            cell=cell,
            resume=True,
        )


def test_completed_report_is_reconstructed_from_checkpoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, model = _prepare(tmp_path)
    output = Path("artifacts/search-comparison/report-tampered")
    cell = matched_coordinator.CellConfig("random", "natural", 0, 1)
    _run(manifest=manifest, model=model, output=output, cell=cell)
    report_path = output / "report.json"
    report = json.loads(report_path.read_text())
    del report["report_sha256"]
    report["metrics"]["proposal_count"] = 31
    report_path.write_text(
        json.dumps(random_search._seal_record(report, "report_sha256")),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="does not match durable checkpoints"):
        _run(
            manifest=manifest,
            model=model,
            output=output,
            cell=cell,
            resume=True,
        )


def test_strict_finite_json_and_environment_resume_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "nonfinite.json"
    with pytest.raises(ValueError, match="Out of range float"):
        random_search._atomic_write_json(target, {"value": float("nan")})
    assert not target.exists()

    monkeypatch.chdir(tmp_path)
    manifest, model = _prepare(tmp_path)
    output = Path("artifacts/search-comparison/environment")
    cell = matched_coordinator.CellConfig("random", "natural", 0, 1)
    _run(
        manifest=manifest,
        model=model,
        output=output,
        cell=cell,
        max_new_proposals=1,
    )
    monkeypatch.setattr(matched_coordinator.platform, "machine", lambda: "changed")
    with pytest.raises(ValueError, match="Run environment mismatch"):
        _run(
            manifest=manifest,
            model=model,
            output=output,
            cell=cell,
            resume=True,
        )


def test_evaluator_boolean_aliases_are_rejected_before_checkpointing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, model = _prepare(tmp_path)
    output = Path("artifacts/search-comparison/boolean-alias")
    cell = matched_coordinator.CellConfig("random", "natural", 0, 1)

    def invalid_attempt(*args: Any, **kwargs: Any) -> dict[str, Any]:
        evaluation = _attempt(*args, **kwargs)
        evaluation["attempt"]["controllers"]["tested"][
            "outputs_identical"
        ] = 1
        return evaluation

    with pytest.raises(ValueError, match="must be booleans"):
        matched_coordinator.run(
            manifest_path=manifest,
            support_model_path=model,
            output_dir=output,
            cell=cell,
            scenario_loader=_loader,
            original_evaluator=_original,
            attempt_evaluator=invalid_attempt,
        )
    assert not matched_coordinator._proposal_path(output, 0).exists()


def test_all_generated_records_validate_against_public_schemas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, model = _prepare(tmp_path)
    output = Path("artifacts/search-comparison/schemas")
    cell = matched_coordinator.CellConfig("bayesian", "natural", 2, 4)
    report = _run(manifest=manifest, model=model, output=output, cell=cell)

    records = [
        (
            json.loads((output / "run-manifest.json").read_text()),
            "matched-cell-run-manifest-v1.schema.json",
        ),
        (
            json.loads((output / "original.json").read_text()),
            "matched-cell-original-v1.schema.json",
        ),
        (
            json.loads(matched_coordinator._selection_path(output, 8).read_text()),
            "matched-cell-selection-v1.schema.json",
        ),
        (
            json.loads(matched_coordinator._proposal_path(output, 8).read_text()),
            "matched-cell-proposal-v1.schema.json",
        ),
        (report, "matched-cell-report-v1.schema.json"),
    ]
    for record, schema_name in records:
        jsonschema.Draft202012Validator(_schema(schema_name)).validate(record)


def test_private_path_unexpected_files_and_public_summary_are_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest, model = _prepare(tmp_path)
    with pytest.raises(ValueError, match="artifacts/search-comparison"):
        _run(
            manifest=manifest,
            model=model,
            output=Path("experiments/private"),
            cell=matched_coordinator.CellConfig("random", "natural", 0, 1),
        )

    output = Path("artifacts/search-comparison/privacy")
    cell = matched_coordinator.CellConfig("random", "natural", 0, 1)
    report = _run(manifest=manifest, model=model, output=output, cell=cell)
    summary = matched_coordinator.public_summary(report, output)
    assert "private-scenario" not in json.dumps(summary)
    assert "scenario" not in summary

    unexpected = output / "proposals" / "unexpected.txt"
    unexpected.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Unexpected proposal"):
        _run(
            manifest=manifest,
            model=model,
            output=output,
            cell=cell,
            resume=True,
        )
