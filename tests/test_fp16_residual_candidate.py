"""Data-free contracts for the split residual deployment graph."""

import numpy as np
import torch

from planmargin import fp16_residual_candidate, torch_trajectory_model, trajectory_model


def _model() -> torch_trajectory_model.TrajectoryConvNet:
    width = trajectory_model.HISTORY_STEPS * 6
    return torch_trajectory_model.TrajectoryConvNet(
        feature_mean=np.zeros(width, dtype=np.float32),
        feature_scale=np.ones(width, dtype=np.float32),
        target_scale=np.ones(trajectory_model.FUTURE_STEPS * 2, dtype=np.float32),
        hidden_channels=4,
        head_width=8,
    ).eval()


def test_fp32_split_graph_matches_original_composition() -> None:
    model = _model()
    graph = fp16_residual_candidate.ResidualTrajectoryGraph(model).eval()
    features = torch.zeros((2, trajectory_model.HISTORY_STEPS * 6))
    baseline = torch.linspace(0.0, 8.0, trajectory_model.FUTURE_STEPS * 2).repeat(2, 1)
    with torch.inference_mode():
        expected = model(features, baseline)
        actual = fp16_residual_candidate.compose_host_fp32(
            graph(features), baseline, model.smoothing_matrix
        )
    torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-5)
