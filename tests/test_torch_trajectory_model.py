"""Data-free tests for the TensorRT-friendly real-data model pipeline."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import onnx
import torch

from planmargin import torch_trajectory_model
from planmargin import trajectory_model


def _samples(
    scenario_id: str, offset: float = 0.0
) -> torch_trajectory_model.ScenarioWindows:
    steps = 81
    time = np.arange(steps, dtype=np.float32) * 0.1
    x = (time * 5 + offset)[None, :]
    zeros = np.zeros((1, steps), dtype=np.float32)
    values = trajectory_model.windows_from_tracks(
        scenario_id=scenario_id,
        x=x,
        y=zeros,
        yaw=zeros,
        vel_x=np.full((1, steps), 5, dtype=np.float32),
        vel_y=zeros,
        valid=np.ones((1, steps), dtype=bool),
        object_types=np.array([1], dtype=np.int32),
        stride=5,
    )
    return torch_trajectory_model.ScenarioWindows(
        scenario_id=scenario_id,
        shard_index=0,
        features=values.features,
        targets=values.targets,
        baseline=values.baseline,
    )


def _model() -> torch_trajectory_model.TrajectoryConvNet:
    return torch_trajectory_model.TrajectoryConvNet(
        feature_mean=np.zeros(66, dtype=np.float32),
        feature_scale=np.ones(66, dtype=np.float32),
        target_scale=np.ones(60, dtype=np.float32),
        hidden_channels=8,
        head_width=16,
    ).eval()


def test_scenario_split_has_no_leakage() -> None:
    scenarios = [_samples(f"scenario-{index}") for index in range(20)]
    splits = torch_trajectory_model.split_scenarios(scenarios, seed=3)
    ids = [{item.scenario_id for item in values} for values in splits.values()]
    assert len(ids[0] & ids[1]) == 0
    assert len(ids[0] & ids[2]) == 0
    assert len(ids[1] & ids[2]) == 0
    assert sum(map(len, ids)) == 20


def test_model_archive_is_deterministic_and_allowlisted() -> None:
    torch.manual_seed(4)
    model = _model()
    first = torch_trajectory_model.serialize_model(model)
    second = torch_trajectory_model.serialize_model(model)
    assert first == second
    loaded = torch_trajectory_model.load_model(first)
    features = torch.zeros((2, 66))
    baseline = torch.zeros((2, 60))
    torch.testing.assert_close(model(features, baseline), loaded(features, baseline))


def test_onnx_export_is_valid_and_has_dynamic_batch(tmp_path: Path) -> None:
    path = torch_trajectory_model.export_onnx(_model(), tmp_path / "model.onnx")
    graph = onnx.load(path)
    onnx.checker.check_model(graph)
    assert graph.graph.input[0].type.tensor_type.shape.dim[0].dim_param == "batch"
    assert {item.name for item in graph.graph.input} == {
        "features",
        "constant_velocity",
    }


def test_fp16_onnx_export_has_typed_inputs(tmp_path: Path) -> None:
    path = torch_trajectory_model.export_onnx(
        _model().half(), tmp_path / "model-fp16.onnx", dtype=torch.float16
    )
    graph = onnx.load(path)
    onnx.checker.check_model(graph)
    assert all(
        value.type.tensor_type.elem_type == onnx.TensorProto.FLOAT16
        for value in graph.graph.input
    )


def test_small_training_is_deterministic() -> None:
    scenarios = [_samples(f"scenario-{index}", offset=index) for index in range(20)]
    grouped = torch_trajectory_model.split_scenarios(scenarios, seed=7)
    splits = {
        name: torch_trajectory_model.combine_scenarios(values)
        for name, values in grouped.items()
    }
    config = torch_trajectory_model.TorchTrainingConfig(
        scenario_count=20,
        shard_count=2,
        hidden_channels=8,
        head_width=16,
        epochs=2,
        batch_size=32,
        seed=7,
    )
    first, first_report = torch_trajectory_model.train(splits, config)
    second, second_report = torch_trajectory_model.train(splits, config)
    assert torch_trajectory_model.serialize_model(
        first
    ) == torch_trajectory_model.serialize_model(second)
    assert first_report == second_report
