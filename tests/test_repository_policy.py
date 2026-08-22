"""Data-free checks for repository artifact boundaries."""

import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).parents[1]


def test_per_scenario_womd_reports_are_not_committed() -> None:
    prohibited_reports = (
        REPOSITORY_ROOT / "experiments" / "stage-0" / "scenario-selection.json",
        REPOSITORY_ROOT / "experiments" / "stage-0" / "waymax-smoke-test.json",
        REPOSITORY_ROOT / "experiments" / "stage-0" / "speed-mutation-smoke-test.json",
        REPOSITORY_ROOT / "experiments" / "stage-0" / "controller-comparison.json",
        REPOSITORY_ROOT / "experiments" / "stage-0" / "rollout-records.json",
        REPOSITORY_ROOT / "experiments" / "stage-0" / "trajectory-comparison.html",
        REPOSITORY_ROOT
        / "experiments"
        / "realism"
        / "lead-braking-support-v1"
        / "model.json",
        REPOSITORY_ROOT
        / "experiments"
        / "realism"
        / "lead-braking-support-v1"
        / "shards",
        REPOSITORY_ROOT / "artifacts" / "search-comparison",
        REPOSITORY_ROOT / "artifacts" / "beam-features",
        REPOSITORY_ROOT / "artifacts" / "experiment-v2",
        REPOSITORY_ROOT / "artifacts" / "experiment-v4",
    )

    tracked = subprocess.run(
        [
            "git",
            "ls-files",
            "--",
            *(str(path.relative_to(REPOSITORY_ROOT)) for path in prohibited_reports),
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    assert tracked == []


def test_public_torch_result_is_aggregate_only_and_schema_valid() -> None:
    import json

    import jsonschema

    record = json.loads(
        (REPOSITORY_ROOT / "experiments" / "torch-trajectory-model-v1.json").read_text()
    )
    schema = json.loads(
        (
            REPOSITORY_ROOT / "schemas" / "torch-trajectory-model-public-v1.schema.json"
        ).read_text()
    )

    jsonschema.validate(record, schema)
    assert record["redistribution"] == "aggregate_only"
    assert "scenario_ids" not in json.dumps(record)


def test_public_scaled_torch_result_is_aggregate_only_and_schema_valid() -> None:
    import json

    import jsonschema

    record = json.loads(
        (REPOSITORY_ROOT / "experiments" / "torch-trajectory-model-v2.json").read_text()
    )
    schema = json.loads(
        (
            REPOSITORY_ROOT / "schemas" / "torch-trajectory-model-public-v1.schema.json"
        ).read_text()
    )

    jsonschema.validate(record, schema)
    assert record["scenario_count"] == 1024
    assert record["split"]["test_scenarios"] == 102
    assert record["gates"]["byte_identical_repeat"] is True
    assert "scenario_ids" not in json.dumps(record)


def test_public_active_risk_results_are_sealed_aggregate_only() -> None:
    import hashlib
    import json

    import jsonschema

    schema = json.loads(
        (
            REPOSITORY_ROOT
            / "schemas"
            / "active-risk-qualification-public-v1.schema.json"
        ).read_text()
    )
    for name in (
        "active-risk-qualification-v1.json",
        "active-risk-qualification-v2.json",
    ):
        record = json.loads((REPOSITORY_ROOT / "experiments" / name).read_text())
        jsonschema.validate(record, schema)
        expected = record.pop("report_sha256")
        canonical = (
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        assert hashlib.sha256(canonical).hexdigest() == expected
        assert record["redistribution"] == "aggregate_only"
        assert record["synthetic"] is False
        assert record["status"] == "qualification_no_go"
        assert record["model_sha256"] is None
        assert record["onnx_sha256"] is None


def test_cpp_tensorrt_runner_declares_end_to_end_measurement_boundary() -> None:
    source = (
        REPOSITORY_ROOT / "cpp" / "tensorrt" / "trajectory_runner.cpp"
    ).read_text()

    for required in (
        "cudaMallocHost",
        "cudaMemcpyHostToDevice",
        "cudaMemcpyDeviceToHost",
        "cudaStreamSynchronize(end-to-end)",
        "end_to_end_latency_ms",
        "pinned host input to pinned host output",
    ):
        assert required in source


def test_public_tensorrt_result_is_sealed_aggregate_only_and_schema_valid() -> None:
    import hashlib
    import json

    import jsonschema

    record = json.loads(
        (REPOSITORY_ROOT / "experiments" / "tensorrt-qualification-v1.json").read_text()
    )
    schema = json.loads(
        (
            REPOSITORY_ROOT / "schemas" / "tensorrt-qualification-public-v1.schema.json"
        ).read_text()
    )

    jsonschema.validate(record, schema)
    expected = record.pop("report_sha256")
    canonical = (
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    assert hashlib.sha256(canonical).hexdigest() == expected
    assert record["redistribution"] == "aggregate_only"
    assert record["source_model_training_data"]["synthetic"] is False
    serialized = json.dumps(record)
    assert "scenario_ids" not in serialized
    assert "features" not in serialized


def test_public_claims_do_not_repeat_disproven_pristine_holdout_language() -> None:
    prohibited = (
        "held-out split remains unopened",
        "validation split has not been opened",
        "official held-out womd evaluation remains unopened",
        "official womd validation split remains unopened",
        "held-out data remains unopened",
        "held-out remains unopened",
        "untouched validation split",
    )
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    searchable = {
        ".md",
        ".py",
        ".ts",
        ".json",
        ".html",
        ".sh",
    }
    violations: list[tuple[str, str]] = []
    for relative in tracked:
        path = REPOSITORY_ROOT / relative
        # A working tree can legitimately contain staged or unstaged deletions.
        # Repository-policy checks should evaluate files that still exist, not
        # fail before Git records the deletion in the index.
        if (
            not path.is_file()
            or path.suffix not in searchable
            or path.resolve() == Path(__file__).resolve()
        ):
            continue
        content = path.read_text(encoding="utf-8").lower()
        violations.extend(
            (relative, phrase) for phrase in prohibited if phrase in content
        )
    assert violations == []


def test_application_remains_unpublished_until_release_approval() -> None:
    assert not (
        REPOSITORY_ROOT / "deploy" / "huggingface-space" / "README.md"
    ).exists()
    assert not (
        REPOSITORY_ROOT / "scripts" / "publish_huggingface_space.sh"
    ).exists()
    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    assert "There is intentionally no hosted dashboard in this release" in readme
