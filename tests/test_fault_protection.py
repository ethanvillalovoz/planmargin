"""Data-free checks for fault-injection and fallback qualification."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import jax.numpy as jnp
from waymax import datatypes

from planmargin import fault_protection

ROOT = Path(__file__).parents[1]


def _action(valid: bool, value: float) -> datatypes.Action:
    return datatypes.Action(
        data=jnp.full((2, 5), value), valid=jnp.full((2, 1), valid)
    )


def test_unprotected_fault_holds_only_the_sdc_pose() -> None:
    runner = object.__new__(fault_protection.FaultControllerRunner)
    runner.protected = False
    action = runner._fault_action(
        primary=_action(True, 1.0),
        fallback=_action(True, 2.0),
        sdc_index=1,
        current_pose=jnp.asarray([3.0, 4.0, 0.5, 0.0, 0.0]),
    )
    assert action.valid[:, 0].tolist() == [True, True]
    assert action.data[0].tolist() == [1.0] * 5
    assert action.data[1].tolist() == [3.0, 4.0, 0.5, 0.0, 0.0]


def test_protected_fault_switches_to_the_fallback_action() -> None:
    runner = object.__new__(fault_protection.FaultControllerRunner)
    runner.protected = True
    fallback = _action(True, 2.0)
    action = runner._fault_action(
        primary=_action(True, 1.0),
        fallback=fallback,
        sdc_index=1,
        current_pose=jnp.zeros(5),
    )
    assert action is fallback


def test_fault_window_ends_on_the_frozen_recovery_step() -> None:
    runner = object.__new__(fault_protection.FaultControllerRunner)
    runner.fault_onset_step = 20
    runner.recovery_step = 30
    assert runner._fault_active(19) is False
    assert runner._fault_active(20) is True
    assert runner._fault_active(29) is True
    assert runner._fault_active(30) is False


def test_public_report_removes_scene_records() -> None:
    report = {
        "schema_version": "1.0.0",
        "status": "qualified",
        "protocol": {"fault": "dropout"},
        "dataset": {"synthetic": False},
        "summary": {"protected_fallback_success_count": 10},
        "gates": {"real_womd_only": True},
        "scenes": [{"selection_order": 1, "trajectory_sha256": "private"}],
        "report_sha256": "a" * 64,
        "claim_boundary": "bounded research claim",
    }
    public = fault_protection.public_report(report)
    assert "scenes" not in public
    assert "selection_order" not in str(public)
    assert public["dataset"]["synthetic"] is False


def test_tracked_public_report_is_sealed_schema_valid_and_private() -> None:
    report_path = ROOT / fault_protection.DEFAULT_PUBLIC_OUTPUT
    report = json.loads(report_path.read_text(encoding="utf-8"))
    schema = json.loads(
        (ROOT / "schemas/fault-protection-public-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.Draft202012Validator(schema).validate(report)
    payload = dict(report)
    seal = payload.pop("report_sha256")
    assert seal == fault_protection.random_search._content_sha256(payload)
    def keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value) | {key for item in value.values() for key in keys(item)}
        if isinstance(value, list):
            return {key for item in value for key in keys(item)}
        return set()

    assert {"scenes", "scenario_id", "source_uri"}.isdisjoint(keys(report))
    serialized = json.dumps(report).lower()
    for forbidden in ("/users/", ".tfrecord"):
        assert forbidden not in serialized
