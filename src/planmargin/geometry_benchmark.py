"""Benchmark the Python and C++20 interaction-metrics implementations."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections.abc import Callable

import numpy as np

from planmargin import interaction_metrics


def synthetic_tracks(states: int = 80) -> tuple[dict[str, np.ndarray], ...]:
    """Return deterministic, data-free vehicle traces."""
    if states < 2:
        raise ValueError("benchmark requires at least two states")
    timeline = np.arange(states, dtype=np.float64) * 0.1
    sdc = {
        "x_m": 10.0 * timeline,
        "y_m": 0.2 * np.sin(timeline),
        "yaw_rad": 0.02 * np.sin(timeline),
        "vel_x_mps": np.full(states, 10.0),
        "vel_y_mps": np.zeros(states),
        "length_m": np.full(states, 4.8),
        "width_m": np.full(states, 2.0),
        "valid": np.ones(states, dtype=bool),
    }
    lead = {
        "x_m": 15.0 + 8.0 * timeline,
        "y_m": 0.1 * np.sin(timeline),
        "yaw_rad": 0.01 * np.sin(timeline),
        "vel_x_mps": np.full(states, 8.0),
        "vel_y_mps": np.zeros(states),
        "length_m": np.full(states, 4.6),
        "width_m": np.full(states, 1.9),
        "valid": np.ones(states, dtype=bool),
    }
    return sdc, lead


def _median_microseconds(function: Callable[[], object], iterations: int) -> float:
    samples = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        function()
        samples.append((time.perf_counter_ns() - started) / 1_000.0)
    return float(statistics.median(samples))


def benchmark(*, iterations: int = 200, states: int = 80) -> dict[str, object]:
    """Return deterministic-input latency observations and exact parity."""
    if iterations < 1:
        raise ValueError("benchmark iterations must be positive")
    sdc, lead = synthetic_tracks(states)

    def native() -> dict[str, float | int | None]:
        return interaction_metrics.interaction_metrics(sdc, lead)

    def python() -> dict[str, float | int | None]:
        return interaction_metrics._interaction_metrics_python(sdc, lead)

    expected = python()
    actual = native()
    if actual != expected:
        raise RuntimeError("native interaction metrics differ from Python reference")
    for _ in range(5):
        native()
        python()
    native_us = _median_microseconds(native, iterations)
    python_us = _median_microseconds(python, iterations)
    return {
        "status": "completed",
        "decision": "parity_passed",
        "fixture": f"synthetic_{states}_state_lead_vehicle_trace",
        "states": states,
        "iterations": iterations,
        "python_median_microseconds": round(python_us, 3),
        "native_median_microseconds": round(native_us, 3),
        "kernel_speedup": round(python_us / native_us, 3),
        "limitations": [
            "This benchmark isolates one data-free geometry kernel.",
            "It does not estimate end-to-end Waymax campaign speedup.",
        ],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--states", type=int, default=80)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    print(
        json.dumps(
            benchmark(iterations=args.iterations, states=args.states),
            indent=2,
            sort_keys=True,
        )
    )
