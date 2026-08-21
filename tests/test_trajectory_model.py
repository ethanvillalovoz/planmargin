"""Data-free tests for the real-data trajectory model machinery."""

from __future__ import annotations

import numpy as np

from planmargin import trajectory_model


def _straight_tracks() -> dict[str, np.ndarray]:
    steps = 91
    time = np.arange(steps, dtype=np.float32) * 0.1
    return {
        "x": time[None, :] * 5,
        "y": np.zeros((1, steps), dtype=np.float32),
        "yaw": np.zeros((1, steps), dtype=np.float32),
        "vel_x": np.full((1, steps), 5, dtype=np.float32),
        "vel_y": np.zeros((1, steps), dtype=np.float32),
        "valid": np.ones((1, steps), dtype=bool),
        "object_types": np.array([1], dtype=np.int32),
    }


def test_windows_use_recorded_tracks_and_local_frame() -> None:
    samples = trajectory_model.windows_from_tracks(
        scenario_id="real-scenario", **_straight_tracks()
    )
    assert len(samples.features) > 0
    assert set(samples.scenario_ids) == {"real-scenario"}
    np.testing.assert_allclose(samples.targets, samples.baseline, atol=1e-5)


def test_model_archive_is_deterministic_and_allowlisted() -> None:
    parameters = trajectory_model.initialize_parameters(
        trajectory_model.jax.random.PRNGKey(0), 66, 8, 60
    )
    frozen = {key: np.asarray(value) for key, value in parameters.items()}
    frozen.update(
        feature_mean=np.zeros(66, dtype=np.float32),
        feature_scale=np.ones(66, dtype=np.float32),
        target_scale=np.ones(60, dtype=np.float32),
    )
    first = trajectory_model.serialize_model(frozen)
    second = trajectory_model.serialize_model(frozen)
    assert first == second
    loaded = trajectory_model.load_model(first)
    assert set(loaded) == set(frozen)


def test_small_training_is_deterministic() -> None:
    samples = trajectory_model.windows_from_tracks(
        scenario_id="real-scenario", **_straight_tracks(), stride=5
    )
    config = trajectory_model.TrainingConfig(hidden_size=8, epochs=2, batch_size=8)
    first, first_report = trajectory_model.train(
        samples, {"test": samples}, config, seed=4
    )
    second, second_report = trajectory_model.train(
        samples, {"test": samples}, config, seed=4
    )
    assert trajectory_model.serialize_model(first) == trajectory_model.serialize_model(
        second
    )
    assert first_report == second_report
