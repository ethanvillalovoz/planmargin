"""Data-free tests for the NVIDIA qualification report helpers."""

import torch

import pytest

from planmargin import tensorrt_qualification


class _LegacyTensorRT:
    class NetworkDefinitionCreationFlag:
        EXPLICIT_BATCH = 3


class _TensorRT11:
    class NetworkDefinitionCreationFlag:
        pass


def test_latency_summary_reports_required_percentiles() -> None:
    result = tensorrt_qualification.latency_summary([1.0, 2.0, 3.0, 4.0])

    assert result == {"mean": 2.5, "p50": 2.5, "p95": 3.85, "p99": 3.97}


def test_network_flags_cover_legacy_and_tensorrt_11() -> None:
    assert tensorrt_qualification._network_creation_flags(_LegacyTensorRT) == 8
    assert tensorrt_qualification._network_creation_flags(_TensorRT11) == 0


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
