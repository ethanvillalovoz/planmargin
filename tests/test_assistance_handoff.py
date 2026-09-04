"""Data-free contracts for the assistance-handoff qualification."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from planmargin import assistance_handoff
from planmargin import random_search

ROOT = Path(__file__).parents[1]


def test_post_fault_progress_measures_distance_after_detection() -> None:
    count = assistance_handoff.FAULT_ONSET_STEP + 4
    result = {
        "trajectory": {
            "x_m": [0.0] * (count - 3) + [0.0, 3.0, 3.0],
            "y_m": [0.0] * (count - 3) + [0.0, 0.0, 4.0],
        }
    }
    assert assistance_handoff._post_fault_progress(result) == 7.0


def test_public_report_removes_scene_records_and_identifiers() -> None:
    report = {
        "schema_version": "1.0.0",
        "status": "qualified",
        "protocol": {"fault": "temporary_primary_command_dropout"},
        "dataset": {"synthetic": False},
        "summary": {"assisted_handoff_success_count": 10},
        "gates": {"real_womd_only": True},
        "scenes": [{"selection_order": 1, "trajectory_sha256": "private"}],
        "report_sha256": "a" * 64,
        "claim_boundary": "bounded research claim",
    }
    public = assistance_handoff.public_report(report)
    assert "scenes" not in public
    assert "selection_order" not in str(public)
    assert public["record_type"] == assistance_handoff.PUBLIC_RECORD_TYPE
    assert public["dataset"]["synthetic"] is False


def test_tracked_assistance_report_is_sealed_schema_valid_and_private() -> None:
    report = json.loads(
        (ROOT / assistance_handoff.DEFAULT_PUBLIC_OUTPUT).read_text(encoding="utf-8")
    )
    schema = json.loads(
        (ROOT / "schemas/assistance-handoff-public-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.Draft202012Validator(schema).validate(report)
    payload = dict(report)
    seal = payload.pop("report_sha256")
    assert seal == random_search._content_sha256(payload)
    serialized = json.dumps(report).lower()
    for forbidden in ("scenario_id", "source_uri", "/users/", ".tfrecord"):
        assert forbidden not in serialized
