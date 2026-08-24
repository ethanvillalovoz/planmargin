"""Data-free tests for the NVIDIA qualification report helpers."""

import json
from pathlib import Path

import jsonschema
import torch

import pytest

from planmargin import tensorrt_qualification


class _LegacyTensorRT:
    class NetworkDefinitionCreationFlag:
        EXPLICIT_BATCH = 3


class _TensorRT11:
    class NetworkDefinitionCreationFlag:
        pass

    class BuilderFlag:
        pass


class _LegacyBuilder:
    platform_has_fast_fp16 = False


class _TensorRT11Builder:
    pass


class _Config:
    def __init__(self) -> None:
        self.flags: list[object] = []

    def set_flag(self, flag: object) -> None:
        self.flags.append(flag)


def test_latency_summary_reports_required_percentiles() -> None:
    result = tensorrt_qualification.latency_summary([1.0, 2.0, 3.0, 4.0])

    assert result == {"mean": 2.5, "p50": 2.5, "p95": 3.85, "p99": 3.97}


def test_network_flags_cover_legacy_and_tensorrt_11() -> None:
    assert tensorrt_qualification._network_creation_flags(_LegacyTensorRT) == 8
    assert tensorrt_qualification._network_creation_flags(_TensorRT11) == 0
    assert not tensorrt_qualification._supports_fast_fp16(_LegacyBuilder())
    assert tensorrt_qualification._supports_fast_fp16(_TensorRT11Builder())
    config = _Config()
    assert not tensorrt_qualification._enable_legacy_fp16(
        _TensorRT11, _TensorRT11Builder(), config
    )
    assert config.flags == []


@pytest.mark.parametrize("samples", [[], [1.0, float("nan")]])
def test_latency_summary_rejects_invalid_samples(samples: list[float]) -> None:
    with pytest.raises(ValueError, match="non-empty finite"):
        tensorrt_qualification.latency_summary(samples)


def test_deterministic_inference_probe_is_stable_and_physically_shaped() -> None:
    first_features, first_baseline = (
        tensorrt_qualification.deterministic_inference_probe(8)
    )
    second_features, second_baseline = (
        tensorrt_qualification.deterministic_inference_probe(8)
    )

    assert first_features.shape == (8, 66)
    assert first_baseline.shape == (8, 60)
    assert first_features.dtype == torch.float32
    assert first_baseline.dtype == torch.float32
    assert torch.equal(first_features, second_features)
    assert torch.equal(first_baseline, second_baseline)


def test_deterministic_inference_probe_rejects_empty_batch() -> None:
    with pytest.raises(ValueError, match="positive"):
        tensorrt_qualification.deterministic_inference_probe(0)


def test_end_to_end_qualification_schema_is_well_formed() -> None:
    schema_path = (
        Path(__file__).parents[1]
        / "schemas"
        / "tensorrt-qualification-public-v2.schema.json"
    )

    jsonschema.Draft202012Validator.check_schema(json.loads(schema_path.read_text()))


def test_scaled_t4_no_go_report_is_valid_and_sealed() -> None:
    root = Path(__file__).parents[1]
    schema = json.loads(
        (root / "schemas" / "tensorrt-qualification-public-v2.schema.json").read_text()
    )
    report = json.loads(
        (root / "experiments" / "tensorrt-qualification-v2.json").read_text()
    )

    jsonschema.validate(report, schema)
    sealed = dict(report)
    observed = sealed.pop("report_sha256")
    canonical = (
        json.dumps(sealed, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()

    import hashlib

    assert hashlib.sha256(canonical).hexdigest() == observed
    assert report["status"] == "no_go"
    assert not report["gates"]["fp16_max_error_under_7_5e_2_m"]
    assert all(
        passed
        for name, passed in report["gates"].items()
        if name != "fp16_max_error_under_7_5e_2_m"
    )
