"""Data-free contracts for separately versioned campaign proposal replays."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from planmargin import proposal_replay
from planmargin import random_search

ROOT = Path(__file__).resolve().parents[1]


def test_replay_directory_is_stable_and_one_based() -> None:
    assert proposal_replay.replay_directory(
        Path("artifacts/proposal-replays/natural-development-v1"),
        method="bayesian",
        seed=4,
        selection_order=8,
        proposal_number=12,
    ) == Path(
        "artifacts/proposal-replays/natural-development-v1/"
        "bayesian/seed-4/scenario-08/proposal-0012"
    )


def test_scientific_controller_view_excludes_only_runtime_timings() -> None:
    record = {
        "outputs_identical": True,
        "trajectory_sha256": "a" * 64,
        "changed_from_original": True,
        "outcome": {"success": True},
        "interaction_metrics": {"minimum_signed_separation_m": 1.25},
        "first_rollout_seconds": 1.0,
        "second_rollout_seconds": 0.9,
    }
    view = proposal_replay._scientific_controller_view(record)
    assert set(view) == {
        "outputs_identical",
        "trajectory_sha256",
        "changed_from_original",
        "outcome",
        "interaction_metrics",
    }
    view["outcome"]["success"] = False
    assert record["outcome"]["success"] is True


def test_export_rejects_public_or_unconfined_output_before_loading_data(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="artifacts/proposal-replays"):
        proposal_replay.export(
            output_root=tmp_path / "public",
            method="random",
            seed=0,
            selection_order=1,
            proposal_number=1,
        )


def test_replay_manifest_schema_requires_restricted_export_boundary() -> None:
    schema = json.loads(
        (ROOT / "schemas/proposal-replay-manifest-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    payload = {
        "$schema": proposal_replay.MANIFEST_SCHEMA_URI,
        "schema_version": proposal_replay.SCHEMA_VERSION,
        "record_type": proposal_replay.MANIFEST_TYPE,
        "campaign_id": "natural-development-v1",
        "identity": {
            "method": "random",
            "track": "natural",
            "seed": 1,
            "selection_order": 8,
            "proposal_number": 12,
        },
        "proposal_record_sha256": "a" * 64,
        "cell_configuration_fingerprint": "b" * 64,
        "collection_file": "collection.json",
        "collection_sha256": "c" * 64,
        "verification": {"trajectory_hashes_match": True},
        "privacy": {
            "contains_restricted_scenario_derivatives": True,
            "unrestricted_export": False,
        },
    }
    manifest = random_search._seal_record(payload, "manifest_sha256")
    jsonschema.validate(manifest, schema)
    invalid = copy.deepcopy(manifest)
    invalid["privacy"]["unrestricted_export"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, schema)


def test_export_installs_complete_package_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        proposal_replay,
        "_load_campaign_records",
        lambda *args, **kwargs: (
            object(),
            {"configuration_fingerprint": "b" * 64},
            {},
            {"attempt": {"status": "accepted"}, "record_sha256": "a" * 64},
        ),
    )
    monkeypatch.setattr(
        proposal_replay,
        "_comparison_source",
        lambda **kwargs: ({"source": "fixture"}, {"reproduced": True}),
    )
    monkeypatch.setattr(
        proposal_replay.rollout_record,
        "export_collection",
        lambda source: {"collection_status": "complete", "source": source},
    )
    output_root = Path("artifacts/proposal-replays/test")

    manifest = proposal_replay.export(
        output_root=output_root,
        method="random",
        seed=1,
        selection_order=8,
        proposal_number=12,
    )

    directory = proposal_replay.replay_directory(
        output_root,
        method="random",
        seed=1,
        selection_order=8,
        proposal_number=12,
    )
    assert {path.name for path in directory.iterdir()} == {
        "collection.json",
        "manifest.json",
    }
    assert manifest["cell_configuration_fingerprint"] == "b" * 64
    assert json.loads((directory / "manifest.json").read_text()) == manifest


def test_export_does_not_leave_partial_package_when_manifest_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        proposal_replay,
        "_load_campaign_records",
        lambda *args, **kwargs: (
            object(),
            {"configuration_fingerprint": "b" * 64},
            {},
            {"attempt": {"status": "accepted"}, "record_sha256": "a" * 64},
        ),
    )
    monkeypatch.setattr(
        proposal_replay,
        "_comparison_source",
        lambda **kwargs: ({"source": "fixture"}, {"reproduced": True}),
    )
    monkeypatch.setattr(
        proposal_replay.rollout_record,
        "export_collection",
        lambda source: {"collection_status": "complete", "source": source},
    )
    write_json = random_search._atomic_write_json

    def fail_manifest(path: Path, value: dict[str, object]) -> None:
        if path.name == "manifest.json":
            raise OSError("simulated manifest failure")
        write_json(path, value)

    monkeypatch.setattr(random_search, "_atomic_write_json", fail_manifest)
    output_root = Path("artifacts/proposal-replays/test")
    directory = proposal_replay.replay_directory(
        output_root,
        method="random",
        seed=1,
        selection_order=8,
        proposal_number=12,
    )

    with pytest.raises(OSError, match="simulated manifest failure"):
        proposal_replay.export(
            output_root=output_root,
            method="random",
            seed=1,
            selection_order=8,
            proposal_number=12,
        )

    assert not directory.exists()
    assert not list(directory.parent.glob(f".{directory.name}.*"))
