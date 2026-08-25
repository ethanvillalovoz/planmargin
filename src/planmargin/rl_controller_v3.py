"""Evaluate the frozen Version 3 shielded JAX DQN controller."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from planmargin import rl_controller

PROTOCOL = Path("docs/decisions/0010-version-2-1-research-protocol.md")
DEFAULT_OUTPUT = Path("artifacts/experiment-v10/shielded-controller")
EVALUATION_SEED = 2029


def shielded_action_indices(
    parameters: rl_controller.Parameters, raw: np.ndarray
) -> np.ndarray:
    """Project learned accelerations into the frozen safety envelope."""
    learned = rl_controller.greedy_action_indices(
        parameters, rl_controller.normalize_observation(raw)
    )
    acceleration = rl_controller.ACTION_ACCELERATIONS[learned].copy()
    ego_speed = raw[:, 0]
    lead_speed = raw[:, 1]
    gap = raw[:, 2]
    closing_speed = np.maximum(-raw[:, 3], 0.0)
    headway = raw[:, 4]
    time_to_collision = gap / np.maximum(closing_speed, 1e-3)
    stopping_margin = gap - (ego_speed**2 / 12.0 - lead_speed**2 / 12.0 + 4.0)
    emergency = (time_to_collision < 4.0) | (headway < 1.8) | (stopping_margin <= 0.0)
    caution = (time_to_collision < 6.0) | (headway < 2.5)
    acceleration[caution] = np.minimum(acceleration[caution], -2.0)
    acceleration[emergency] = -6.0
    return np.searchsorted(rl_controller.ACTION_ACCELERATIONS, acceleration).astype(
        np.int32
    )


def evaluate(
    parameters: rl_controller.Parameters,
    config: rl_controller.TrainingConfig = rl_controller.FROZEN_CONFIG,
) -> dict[str, Any]:
    def shielded(raw: np.ndarray) -> np.ndarray:
        return shielded_action_indices(parameters, raw)

    initial = rl_controller.initialize_parameters(rl_controller.TRAINING_SEED)

    def untrained(raw: np.ndarray) -> np.ndarray:
        return rl_controller.greedy_action_indices(
            initial, rl_controller.normalize_observation(raw)
        )

    def emergency(raw: np.ndarray) -> np.ndarray:
        headway = raw[:, 4]
        closing_speed = np.maximum(-raw[:, 3], 0.0)
        time_to_collision = raw[:, 2] / np.maximum(closing_speed, 1e-3)
        acceleration = np.where((headway < 1.5) | (time_to_collision < 3.0), -6.0, 1.0)
        return np.searchsorted(rl_controller.ACTION_ACCELERATIONS, acceleration).astype(
            np.int32
        )

    arguments = {
        "episodes": config.evaluation_episodes,
        "seed": EVALUATION_SEED,
        "horizon": config.horizon,
    }
    return {
        "shielded_rl": rl_controller._evaluate_policy(shielded, **arguments),
        "untrained": rl_controller._evaluate_policy(untrained, **arguments),
        "emergency_braking": rl_controller._evaluate_policy(emergency, **arguments),
    }


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def run(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    first, first_training = rl_controller.train()
    second, second_training = rl_controller.train()
    deterministic = rl_controller.serialize_checkpoint(
        first
    ) == rl_controller.serialize_checkpoint(second)
    evaluation = evaluate(first)
    shielded = evaluation["shielded_rl"]
    emergency = evaluation["emergency_braking"]
    untrained = evaluation["untrained"]
    gates = {
        "deterministic_training": deterministic,
        "free_local_compute": max(
            first_training["runtime_seconds"], second_training["runtime_seconds"]
        )
        <= 900.0,
        "synthetic_collision_rate_at_most_1_percent": (
            shielded["collision_rate"] <= 0.01
        ),
        "not_worse_than_emergency_plus_0_25_points": (
            shielded["collision_rate"] <= emergency["collision_rate"] + 0.0025
        ),
        "progress_at_least_80_percent_of_emergency": (
            shielded["mean_distance_m"] >= 0.80 * emergency["mean_distance_m"]
        ),
        "return_at_least_5_above_untrained": (
            shielded["mean_return"] >= untrained["mean_return"] + 5.0
        ),
    }
    report: dict[str, Any] = {
        "record_type": "planmargin.shielded_rl_controller_qualification",
        "schema_version": "1.0.0",
        "experiment": "v10",
        "status": "synthetic_go" if all(gates.values()) else "synthetic_no_go",
        "real_waymax_campaign_run": False,
        "training_seed": rl_controller.TRAINING_SEED,
        "evaluation_seed": EVALUATION_SEED,
        "configuration": dataclasses.asdict(rl_controller.FROZEN_CONFIG),
        "shield": {
            "emergency_ttc_s": 4.0,
            "emergency_headway_s": 1.8,
            "caution_ttc_s": 6.0,
            "caution_headway_s": 2.5,
            "stopping_buffer_m": 4.0,
            "caution_acceleration_cap_mps2": -2.0,
            "emergency_acceleration_mps2": -6.0,
        },
        "evaluation": evaluation,
        "gates": gates,
        "claim_boundary": (
            "Synthetic car-following qualification only; not a Waymo Driver, "
            "real-WOMD, planner-safety, or deployment result."
        ),
        "protocol_sha256": _sha256(PROTOCOL.read_bytes()),
    }
    encoded = json.dumps(report, allow_nan=False, sort_keys=True, separators=(",", ":"))
    report["report_sha256"] = _sha256(encoded.encode())
    output.mkdir(parents=True, exist_ok=True)
    (output / "qualification-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(args.output)
    print(json.dumps({"status": report["status"], "gates": report["gates"]}))


if __name__ == "__main__":
    main()
