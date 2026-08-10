"""Data-free unit tests for smoke-test reporting helpers."""

import hashlib

import jax.numpy as jnp
import numpy as np

from planmargin import smoke_test


class _TrajectoryState:
    def __init__(self, values: jnp.ndarray):
        self.sim_trajectory = {"x": values}


def test_trajectory_hash_is_stable_and_sensitive() -> None:
    first = hashlib.sha256()
    second = hashlib.sha256()
    changed = hashlib.sha256()

    smoke_test._update_hash(first, _TrajectoryState(jnp.array([1.0, 2.0])))
    smoke_test._update_hash(second, _TrajectoryState(jnp.array([1.0, 2.0])))
    smoke_test._update_hash(changed, _TrajectoryState(jnp.array([1.0, 3.0])))

    assert first.hexdigest() == second.hexdigest()
    assert first.hexdigest() != changed.hexdigest()


def test_finite_summary_excludes_invalid_and_non_finite_values() -> None:
    result = smoke_test._finite_summary(
        np.array([1.0, 100.0, np.inf, 3.0]),
        np.array([True, False, True, True]),
    )

    assert result == {"valid_count": 2, "mean": 2.0, "max": 3.0}
