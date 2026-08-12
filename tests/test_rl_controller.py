"""Data-free tests for the experiment-v2 JAX DQN controller."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from planmargin import rl_controller


def test_observation_normalization_is_bounded() -> None:
    raw = np.array([[50.0, -1.0, 100.0, -100.0, 10.0, -12.0, 8.0]])
    value = rl_controller.normalize_observation(raw)
    np.testing.assert_allclose(value, [[1.2, 0.0, 1.2, -1.0, 1.0, -1.0, 1.0]])


def test_checkpoint_is_deterministic_and_tamper_evident() -> None:
    parameters = rl_controller.initialize_parameters()
    first = rl_controller.serialize_checkpoint(parameters)
    second = rl_controller.serialize_checkpoint(parameters)
    assert first == second
    loaded = rl_controller.load_checkpoint(first)
    assert rl_controller.parameter_fingerprint(
        loaded
    ) == rl_controller.parameter_fingerprint(parameters)
    damaged = bytearray(first)
    damaged[-20] ^= 0x01
    with pytest.raises(rl_controller.RLControllerError):
        rl_controller.load_checkpoint(bytes(damaged))


def test_small_training_run_updates_parameters_and_is_repeatable() -> None:
    config = rl_controller.TrainingConfig(
        environment_steps=512,
        parallel_environments=16,
        replay_capacity=512,
        warmup_steps=128,
        batch_size=64,
        gradient_updates_per_collection=2,
        target_update_interval=20,
        epsilon_decay_steps=400,
        horizon=20,
        evaluation_episodes=64,
    )
    first, first_report = rl_controller.train(config, seed=7)
    second, second_report = rl_controller.train(config, seed=7)
    assert rl_controller.serialize_checkpoint(
        first
    ) == rl_controller.serialize_checkpoint(second)
    assert first_report["optimizer_steps"] > 0
    assert (
        first_report["mean_last_100_huber_loss"]
        == second_report["mean_last_100_huber_loss"]
    )
    assert rl_controller.parameter_fingerprint(
        first
    ) != rl_controller.parameter_fingerprint(rl_controller.initialize_parameters(7))
    evaluation = rl_controller.evaluate(first, config)
    assert evaluation["learned"]["episode_count"] == 64


def test_replay_buffer_and_output_path_enforce_bounds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    replay = rl_controller.ReplayBuffer(4)
    observation = np.zeros((4, rl_controller.OBSERVATION_SIZE), dtype=np.float32)
    replay.add(
        observation, np.zeros(4, dtype=int), np.zeros(4), observation, np.zeros(4)
    )
    sample = replay.sample(np.random.default_rng(0), 4)
    assert all(len(value) == 4 for value in sample)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(rl_controller.RLControllerError, match="under artifacts"):
        rl_controller._output_dir(tmp_path / "outside")
