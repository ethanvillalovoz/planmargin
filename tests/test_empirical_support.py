"""Data-free checks for the frozen empirical-support gate."""

import copy
import json
from pathlib import Path

import jsonschema
import numpy as np
import pytest

from planmargin import behavior_features
from planmargin import empirical_support


def _event(index: int, shard_index: int = 57) -> dict[str, object]:
    source = {
        "dataset_version": "1.3.1",
        "split": "training",
        "shard_index": shard_index,
        "record_index": index,
        "scenario_id": f"private-scenario-{shard_index}-{index}",
        "sdc_object_index": 0,
        "lead_object_index": 1,
    }
    base = index + shard_index / 1000.0
    vector = [
        10.0 + base / 100.0,
        1.0 + base / 200.0,
        8.0 + base / 300.0,
        2.0 + base / 400.0,
        3.0 + base / 500.0,
        1.0 + base / 600.0,
        0.9 + (index % 10) / 1000.0,
        2.0 + base / 700.0,
    ]
    audit = {
        name: float(vector[position])
        for position, name in enumerate(behavior_features.FEATURE_NAMES)
    }
    audit["current_sdc_speed_mps"] = 10.0
    audit["maximum_absolute_jerk_mps3"] = float(np.expm1(vector[-1]))
    return {
        "event_key": empirical_support.event_key(source),
        "source": source,
        "selection_score": float(index),
        "audit_metrics": audit,
        "vector": vector,
    }


def _scanner(events_per_shard: int = 10):
    def scan(shard_index, thresholds):
        del thresholds
        return {
            "records_scanned": 455,
            "record_bytes_processed": 1_000_000,
            "parse_rejections": 0,
            "feature_rejection_counts": {},
            "elapsed_seconds": 1.25,
            "process_peak_rss_bytes": 100_000,
            "events": [_event(index, shard_index) for index in range(events_per_shard)],
        }

    return scan


def _schema(name: str) -> dict[str, object]:
    root = Path(__file__).parents[1]
    return json.loads((root / "schemas" / name).read_text(encoding="utf-8"))


def test_model_split_scaling_scoring_and_ties_are_deterministic() -> None:
    events = [_event(index) for index in range(20)]
    first = empirical_support.fit_model(events, configuration_fingerprint="a" * 64)
    second = empirical_support.fit_model(
        list(reversed(events)), configuration_fingerprint="a" * 64
    )

    assert first == second
    empirical_support.validate_model(first)
    assert len(first["model"]["split"]["reference_event_keys"]) == 14
    assert len(first["model"]["split"]["calibration_event_keys"]) == 6
    assert min(first["model"]["scaling"]["effective_iqr"]) >= 1e-9

    calibration_key = first["model"]["split"]["calibration_event_keys"][0]
    calibration_event = next(
        event for event in events if event["event_key"] == calibration_key
    )
    score = empirical_support.score_vector(first, calibration_event["vector"])
    assert score["tie_inclusive_calibration_count"] >= 1
    assert score["p_support"] == (1 + score["tie_inclusive_calibration_count"]) / 7
    assert score["constraint"] == pytest.approx(0.05 - score["p_support"])


def test_event_order_key_hashes_only_the_private_scenario_identifier() -> None:
    first = _event(1, 57)
    changed_location = copy.deepcopy(first["source"])
    changed_location["shard_index"] = 907
    changed_location["record_index"] = 999

    assert empirical_support.event_key(first["source"]) == empirical_support.event_key(
        changed_location
    )


def test_iqr_floor_handles_constant_features() -> None:
    events = [_event(index) for index in range(20)]
    for event in events:
        event["vector"] = [1.0] * 8

    model = empirical_support.fit_model(events, configuration_fingerprint="b" * 64)

    assert model["model"]["scaling"]["iqr"] == [0.0] * 8
    assert model["model"]["scaling"]["effective_iqr"] == [1e-9] * 8
    score = empirical_support.score_vector(model, [1.0] * 8)
    assert score["nonconformity"] == 0.0
    assert score["p_support"] == 1.0


def test_model_rejects_nonfinite_duplicate_and_tampered_data() -> None:
    events = [_event(index) for index in range(20)]
    duplicate = copy.deepcopy(events)
    duplicate[-1]["event_key"] = duplicate[0]["event_key"]
    nonfinite = copy.deepcopy(events)
    nonfinite[0]["vector"][0] = np.nan

    with pytest.raises(ValueError, match="unique"):
        empirical_support.fit_model(duplicate, configuration_fingerprint="c" * 64)
    with pytest.raises(ValueError, match="finite"):
        empirical_support.fit_model(nonfinite, configuration_fingerprint="c" * 64)
    model = empirical_support.fit_model(events, configuration_fingerprint="c" * 64)
    model["model"]["reference_vectors"][0][0] += 1.0
    with pytest.raises(ValueError, match="hash mismatch"):
        empirical_support.validate_model(model)


def test_strict_json_refuses_nonfinite_checkpoints(tmp_path) -> None:
    path = tmp_path / "nonfinite.json"
    with pytest.raises(ValueError, match="Out of range float"):
        empirical_support._atomic_write_json(path, {"value": np.nan})
    assert not path.exists()


def test_output_must_remain_under_ignored_artifacts(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    empirical_support.validate_private_output_dir(Path("artifacts/realism/allowed"))
    with pytest.raises(ValueError, match="must remain under artifacts"):
        empirical_support.validate_private_output_dir(Path("experiments/leak"))


def test_interrupted_run_resumes_without_repeating_completed_shards(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    output_dir = Path("artifacts/realism/resume")
    calls: list[int] = []
    underlying = _scanner()

    def tracking_scanner(shard_index, thresholds):
        calls.append(shard_index)
        return underlying(shard_index, thresholds)

    progress = empirical_support.run(
        output_dir, scanner=tracking_scanner, max_new_shards=3
    )
    assert progress == {
        "status": "in_progress",
        "completed_shards": 3,
        "remaining_shards": 13,
        "event_count_so_far": 30,
    }
    report = empirical_support.run(output_dir, scanner=tracking_scanner)

    assert report["decision"] == "support_gate_ready"
    assert report["metrics"]["event_count"] == 160
    assert calls == list(empirical_support.REFERENCE_SHARDS)
    assert empirical_support.audit_completed_run(output_dir) == report
    terminal = capsys.readouterr()
    assert "private-scenario" not in terminal.out
    assert "private-scenario" not in terminal.err


def test_completed_run_records_validate_against_public_schemas(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    output_dir = Path("artifacts/realism/schema")
    report = empirical_support.run(output_dir, scanner=_scanner())

    manifest = json.loads((output_dir / "run-manifest.json").read_text())
    shard = json.loads((output_dir / "shards" / "shard-00057.json").read_text())
    model = json.loads((output_dir / "model.json").read_text())
    assert empirical_support.load_model(output_dir / "model.json") == model
    jsonschema.validate(
        manifest, _schema("empirical-support-run-manifest-v1.schema.json")
    )
    jsonschema.validate(shard, _schema("empirical-support-shard-v1.schema.json"))
    jsonschema.validate(model, _schema("empirical-support-model-v1.schema.json"))
    jsonschema.validate(report, _schema("empirical-support-report-v1.schema.json"))


def test_tampered_checkpoint_fails_resume_and_independent_audit(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    output_dir = Path("artifacts/realism/tamper")
    empirical_support.run(output_dir, scanner=_scanner())
    shard_path = output_dir / "shards" / "shard-00057.json"
    shard = json.loads(shard_path.read_text())
    shard["event_count"] += 1
    shard_path.write_text(json.dumps(shard), encoding="utf-8")

    with pytest.raises(ValueError, match="hash mismatch"):
        empirical_support.run(output_dir, scanner=_scanner())
    with pytest.raises(ValueError, match="hash mismatch"):
        empirical_support.audit_completed_run(output_dir)


def test_fixed_scan_below_160_is_predeclared_no_go(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    output_dir = Path("artifacts/realism/no-go")

    report = empirical_support.run(output_dir, scanner=_scanner(5))

    assert report["metrics"]["event_count"] == 80
    assert report["decision"] == "no_go"
    assert report["integrity_gates"]["minimum_160_events"] is False
    assert len(list((output_dir / "shards").glob("*.json"))) == 16
