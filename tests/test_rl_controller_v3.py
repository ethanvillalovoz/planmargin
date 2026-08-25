"""Contracts for the Version 2.1 shielded controller."""

import numpy as np

from planmargin import rl_controller, rl_controller_v3


def test_shield_applies_emergency_braking_to_imminent_collision() -> None:
    raw = np.asarray([[20.0, 5.0, 4.0, -15.0, 0.2, -6.0, 1.0]], dtype=np.float32)
    actions = rl_controller_v3.shielded_action_indices(
        rl_controller.initialize_parameters(), raw
    )
    assert rl_controller.ACTION_ACCELERATIONS[actions[0]] == -6.0


def test_shield_returns_valid_actions_for_nominal_batch() -> None:
    raw = np.asarray([[10.0, 12.0, 40.0, 2.0, 4.0, 0.0, 0.0]], dtype=np.float32)
    actions = rl_controller_v3.shielded_action_indices(
        rl_controller.initialize_parameters(), raw
    )
    assert actions.shape == (1,)
    assert 0 <= actions[0] < len(rl_controller.ACTION_ACCELERATIONS)
