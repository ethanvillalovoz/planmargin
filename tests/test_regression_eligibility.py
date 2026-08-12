"""Data-free tests for the controlled headway-regression eligibility gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from planmargin import controller_comparison
from planmargin import matched_coordinator
from planmargin import random_search
from planmargin import regression_eligibility

REPOSITORY_ROOT = Path(__file__).parents[1]


def _candidates() -> list[dict[str, Any]]:
    return [
        {
            "family": "lead_vehicle_braking",
            "selection_order": order,
            "scenario_id": f"private-scenario-{order}",
            "source_shard": "private-training-shard",
            "shard_index": 0,
            "record_index": order * 7,
            "interacting_object_index": order + 2,
        }
        for order in range(1, 11)
    ]


def _prepare(tmp_path: Path) -> Path:
    manifest = tmp_path / "selection.json"
    manifest.write_text(json.dumps({"candidates": _candidates()}))
    return manifest


def _loader(manifest_path: Path) -> list[tuple[Any, dict[str, Any]]]:
    del manifest_path
    return [(object(), candidate) for candidate in _candidates()]


def _controller(role: str, success: bool, deterministic: bool) -> dict[str, Any]:
    return {
        "outputs_identical": deterministic,
        "trajectory_sha256": f"{role}-{success}-{deterministic}",
        "changed_from_original": None,
        "outcome": {"success": success},
        "interaction_metrics": {"minimum_signed_separation_m": 1.0},
        "first_rollout_seconds": 0.1,
        "second_rollout_seconds": 0.1,
    }


def _evaluator(
    eligible_count: int,
    *,
    nondeterministic_order: int | None = None,
    calls: list[int] | None = None,
) -> regression_eligibility.OriginalEvaluator:
    def evaluate(
        scenario: Any,
        candidate: dict[str, Any],
        tested: controller_comparison.ControllerSpec,
        reference: controller_comparison.ControllerSpec,
    ) -> dict[str, Any]:
        del scenario
        order = candidate["selection_order"]
        if calls is not None:
            calls.append(order)
        natural = controller_comparison.TESTED_CONTROLLER
        assert tested == matched_coordinator.HEADWAY_REGRESSION_CONTROLLER
        assert reference == controller_comparison.REFERENCE_CONTROLLER
        differences = {
            field
            for field in natural.__dataclass_fields__
            if getattr(natural, field) != getattr(tested, field)
        }
        assert differences == {"controller_id", "safe_time_headway_s"}
        success = order <= eligible_count
        deterministic = order != nondeterministic_order
        controllers = {
            "tested": _controller("tested", success, deterministic),
            "reference": _controller("reference", True, True),
        }
        return {
            "eligible": all(
                controller["outcome"]["success"]
                for controller in controllers.values()
            ),
            "controllers": controllers,
        }

    return evaluate


def _run(
    *,
    manifest: Path,
    output: Path,
    evaluator: regression_eligibility.OriginalEvaluator,
    **kwargs: Any,
) -> dict[str, Any]:
    return regression_eligibility.run(
        manifest_path=manifest,
        output_dir=output,
        scenario_loader=_loader,
        original_evaluator=evaluator,
        **kwargs,
    )


def _schema(name: str) -> dict[str, Any]:
    return json.loads((REPOSITORY_ROOT / "schemas" / name).read_text())


def test_exact_threshold_produces_go_and_all_records_match_schemas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = _prepare(tmp_path)
    output = Path("artifacts/search-comparison/eligibility-go")
    result = _run(
        manifest=manifest,
        output=output,
        evaluator=_evaluator(8),
    )

    assert result["decision"] == "go"
    assert result["eligibility_gate"] == {
        "minimum_eligible_scenario_count": 8,
        "eligible_scenario_count": 8,
        "passes": True,
    }
    assert all(result["integrity_gates"].values())
    assert result["cost"]["total_physical_rollouts"] == 40
    assert result["cost"]["waymax_rollout_steps"] == 3200

    records = [
        (
            json.loads((output / "run-manifest.json").read_text()),
            "regression-eligibility-run-manifest-v1.schema.json",
        ),
        *[
            (
                json.loads(
                    regression_eligibility._original_path(output, order).read_text()
                ),
                "regression-eligibility-original-v1.schema.json",
            )
            for order in range(1, 11)
        ],
        (result, "regression-eligibility-report-v1.schema.json"),
    ]
    for record, schema_name in records:
        jsonschema.Draft202012Validator(_schema(schema_name)).validate(record)

    summary = regression_eligibility.public_summary(result, output)
    assert summary["eligible_scenario_count"] == 8
    assert "private-scenario" not in json.dumps(summary)
    assert "scenario" not in summary


@pytest.mark.parametrize(
    ("eligible_count", "nondeterministic_order", "decision"),
    [(7, None, "no_go"), (10, 3, "invalid_gate")],
)
def test_no_go_and_integrity_failure_remain_distinct(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    eligible_count: int,
    nondeterministic_order: int | None,
    decision: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = _prepare(tmp_path)
    result = _run(
        manifest=manifest,
        output=Path(f"artifacts/search-comparison/{decision}"),
        evaluator=_evaluator(
            eligible_count, nondeterministic_order=nondeterministic_order
        ),
    )

    assert result["decision"] == decision
    assert result["eligibility_gate"]["passes"] is (eligible_count >= 8)
    assert result["integrity_gates"][
        "all_original_rollouts_deterministic"
    ] is (nondeterministic_order is None)


def test_interrupted_resume_and_completed_resume_repeat_no_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = _prepare(tmp_path)
    output = Path("artifacts/search-comparison/resume")
    calls: list[int] = []
    evaluator = _evaluator(9, calls=calls)

    progress = _run(
        manifest=manifest,
        output=output,
        evaluator=evaluator,
        max_new_scenarios=4,
    )
    completed = _run(
        manifest=manifest,
        output=output,
        evaluator=evaluator,
        resume=True,
    )
    assert progress["completed_scenario_count"] == 4
    assert completed["decision"] == "go"
    assert calls == list(range(1, 11))

    def fail(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise AssertionError("completed resume performed private work")

    resumed = regression_eligibility.run(
        manifest_path=manifest,
        output_dir=output,
        resume=True,
        scenario_loader=fail,
        original_evaluator=fail,
    )
    assert resumed == completed


def test_resume_rejects_resealed_eligibility_and_unexpected_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = _prepare(tmp_path)
    output = Path("artifacts/search-comparison/tampered")
    _run(
        manifest=manifest,
        output=output,
        evaluator=_evaluator(8),
        max_new_scenarios=1,
    )
    path = regression_eligibility._original_path(output, 1)
    record = json.loads(path.read_text())
    del record["checkpoint_sha256"]
    record["eligible"] = False
    path.write_text(
        json.dumps(random_search._seal_record(record, "checkpoint_sha256"))
    )
    with pytest.raises(ValueError, match="checkpoint derivation"):
        _run(
            manifest=manifest,
            output=output,
            evaluator=_evaluator(8),
            resume=True,
        )

    clean_output = Path("artifacts/search-comparison/unexpected")
    _run(
        manifest=manifest,
        output=clean_output,
        evaluator=_evaluator(8),
        max_new_scenarios=1,
    )
    unexpected = clean_output / "originals" / "unexpected.txt"
    unexpected.write_text("private")
    with pytest.raises(ValueError, match="Unexpected eligibility checkpoint"):
        _run(
            manifest=manifest,
            output=clean_output,
            evaluator=_evaluator(8),
            resume=True,
        )


def test_completed_report_is_reconstructed_from_original_checkpoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = _prepare(tmp_path)
    output = Path("artifacts/search-comparison/report-tampered")
    _run(manifest=manifest, output=output, evaluator=_evaluator(8))
    path = output / "report.json"
    report = json.loads(path.read_text())
    del report["report_sha256"]
    report["eligibility_gate"]["eligible_scenario_count"] = 9
    path.write_text(json.dumps(random_search._seal_record(report, "report_sha256")))

    with pytest.raises(ValueError, match="does not match durable checkpoints"):
        _run(
            manifest=manifest,
            output=output,
            evaluator=_evaluator(8),
            resume=True,
        )


def test_private_output_path_and_maximum_new_scenarios_are_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = _prepare(tmp_path)
    with pytest.raises(ValueError, match="artifacts/search-comparison"):
        _run(
            manifest=manifest,
            output=Path("experiments/private"),
            evaluator=_evaluator(8),
        )
    with pytest.raises(ValueError, match="max_new_scenarios"):
        _run(
            manifest=manifest,
            output=Path("artifacts/search-comparison/invalid-limit"),
            evaluator=_evaluator(8),
            max_new_scenarios=True,
        )
