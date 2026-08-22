"""Data-free tests for the NVIDIA qualification report helpers."""

import pytest

from planmargin import tensorrt_qualification


def test_latency_summary_reports_required_percentiles() -> None:
    result = tensorrt_qualification.latency_summary([1.0, 2.0, 3.0, 4.0])

    assert result == {"mean": 2.5, "p50": 2.5, "p95": 3.85, "p99": 3.97}


@pytest.mark.parametrize("samples", [[], [1.0, float("nan")]])
def test_latency_summary_rejects_invalid_samples(samples: list[float]) -> None:
    with pytest.raises(ValueError, match="non-empty finite"):
        tensorrt_qualification.latency_summary(samples)
