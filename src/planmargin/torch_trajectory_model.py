"""Train and export a TensorRT-friendly trajectory model on real WOMD tracks.

The training protocol is deliberately bounded enough for a laptop or a free
Colab runtime. It streams authorized WOMD TFExamples, caps each scenario's
contribution, holds out complete scenarios, and exports an ONNX graph whose
operators are intentionally simple for TensorRT.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

import numpy as np
import torch
from scipy.signal import savgol_filter
from torch import nn

from planmargin import scenario_selection
from planmargin import trajectory_model

DEFAULT_OUTPUT_DIR = Path("artifacts/experiment-v4/torch-trajectory-model")
DEFAULT_CACHE = Path("artifacts/experiment-v4/womd-window-cache.npz")
DEFAULT_SCENARIO_COUNT = 128
DEFAULT_SHARD_COUNT = 4
DEFAULT_MAX_WINDOWS_PER_SCENARIO = 256
MODEL_MEMBERS = {
    "configuration.json",
    "feature_mean.npy",
    "feature_scale.npy",
    "target_scale.npy",
    "smoothing_matrix.npy",
    "encoder.0.weight.npy",
    "encoder.0.bias.npy",
    "encoder.2.weight.npy",
    "encoder.2.bias.npy",
    "head.1.weight.npy",
    "head.1.bias.npy",
    "head.3.weight.npy",
    "head.3.bias.npy",
}


@dataclass(frozen=True)
class TorchTrainingConfig:
    scenario_count: int = DEFAULT_SCENARIO_COUNT
    shard_count: int = DEFAULT_SHARD_COUNT
    max_windows_per_scenario: int = DEFAULT_MAX_WINDOWS_PER_SCENARIO
    hidden_channels: int = 96
    head_width: int = 256
    epochs: int = 48
    batch_size: int = 512
    learning_rate: float = 8e-4
    weight_decay: float = 1e-5
    stride: int = 2
    seed: int = 17
    device: str = "cpu"


@dataclass(frozen=True)
class ScenarioWindows:
    scenario_id: str
    shard_index: int
    features: np.ndarray
    targets: np.ndarray
    baseline: np.ndarray


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _stable_seed(*values: object) -> int:
    digest = hashlib.sha256("|".join(map(str, values)).encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _smoothing_matrix() -> np.ndarray:
    return np.asarray(
        savgol_filter(
            np.eye(trajectory_model.FUTURE_STEPS, dtype=np.float32),
            11,
            2,
            axis=0,
            mode="interp",
        ),
        dtype=np.float32,
    )


def _scenario_windows(
    serialized: bytes,
    *,
    shard_index: int,
    stride: int,
    max_windows: int,
    seed: int,
) -> ScenarioWindows:
    arrays = scenario_selection._scenario_arrays(serialized)
    samples = trajectory_model.windows_from_tracks(
        scenario_id=arrays.scenario_id,
        x=arrays.x,
        y=arrays.y,
        yaw=arrays.yaw,
        vel_x=arrays.vel_x,
        vel_y=arrays.vel_y,
        valid=arrays.valid,
        object_types=arrays.object_types,
        stride=stride,
    )
    if len(samples.features) > max_windows:
        rng = np.random.default_rng(_stable_seed(seed, arrays.scenario_id))
        indices = np.sort(
            rng.choice(len(samples.features), size=max_windows, replace=False)
        )
    else:
        indices = np.arange(len(samples.features))
    return ScenarioWindows(
        scenario_id=arrays.scenario_id,
        shard_index=shard_index,
        features=samples.features[indices],
        targets=samples.targets[indices],
        baseline=samples.baseline[indices],
    )


def stream_womd_scenarios(config: TorchTrainingConfig) -> Iterator[ScenarioWindows]:
    """Stream a deterministic bounded set of authorized WOMD scenarios."""
    if config.scenario_count < 20:
        raise ValueError("At least 20 scenarios are required for the expanded protocol")
    if config.shard_count < 2 or config.shard_count > config.scenario_count:
        raise ValueError("shard_count must be between 2 and scenario_count")
    quotient, remainder = divmod(config.scenario_count, config.shard_count)
    for shard_index in range(config.shard_count):
        target = quotient + (1 if shard_index < remainder else 0)
        uri = scenario_selection._training_shard_uri(shard_index)
        dataset = scenario_selection.tf.data.TFRecordDataset(
            [uri], buffer_size=8 * 1024 * 1024
        )
        emitted = 0
        for serialized in dataset:
            windows = _scenario_windows(
                serialized.numpy(),
                shard_index=shard_index,
                stride=config.stride,
                max_windows=config.max_windows_per_scenario,
                seed=config.seed,
            )
            if len(windows.features) == 0:
                continue
            yield windows
            emitted += 1
            if emitted == target:
                break
        if emitted != target:
            raise RuntimeError(
                f"WOMD shard {shard_index} yielded only {emitted} scenarios"
            )


def _write_cache(path: Path, scenarios: Iterable[ScenarioWindows]) -> None:
    values = tuple(scenarios)
    if not values:
        raise ValueError("Cannot cache an empty scenario collection")
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        scenario_ids=np.asarray([item.scenario_id for item in values], dtype=str),
        shard_indices=np.asarray([item.shard_index for item in values], dtype=np.int16),
        window_counts=np.asarray(
            [len(item.features) for item in values], dtype=np.int32
        ),
        features=np.concatenate([item.features for item in values]),
        targets=np.concatenate([item.targets for item in values]),
        baseline=np.concatenate([item.baseline for item in values]),
    )


def _read_cache(path: Path) -> list[ScenarioWindows]:
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError(f"WOMD window cache is missing: {path}")
    with np.load(path, allow_pickle=False) as archive:
        scenario_ids = archive["scenario_ids"]
        shard_indices = archive["shard_indices"]
        counts = archive["window_counts"]
        features = archive["features"]
        targets = archive["targets"]
        baseline = archive["baseline"]
    if len(scenario_ids) != len(counts) or int(counts.sum()) != len(features):
        raise ValueError("WOMD cache accounting is inconsistent")
    result: list[ScenarioWindows] = []
    offset = 0
    for scenario_id, shard_index, count in zip(
        scenario_ids, shard_indices, counts, strict=True
    ):
        stop = offset + int(count)
        result.append(
            ScenarioWindows(
                scenario_id=str(scenario_id),
                shard_index=int(shard_index),
                features=np.asarray(features[offset:stop], dtype=np.float32),
                targets=np.asarray(targets[offset:stop], dtype=np.float32),
                baseline=np.asarray(baseline[offset:stop], dtype=np.float32),
            )
        )
        offset = stop
    return result


def prepare_cache(
    path: Path, config: TorchTrainingConfig, refresh: bool = False
) -> Path:
    if refresh or not path.is_file():
        _write_cache(path, stream_womd_scenarios(config))
    scenarios = _read_cache(path)
    if len(scenarios) != config.scenario_count:
        raise ValueError(
            f"Expected {config.scenario_count} cached scenarios, found {len(scenarios)}"
        )
    return path


def split_scenarios(
    scenarios: list[ScenarioWindows], seed: int
) -> dict[str, list[ScenarioWindows]]:
    if len(scenarios) < 20:
        raise ValueError("At least 20 scenarios are required")
    order = np.random.default_rng(seed).permutation(len(scenarios))
    test_count = max(2, round(len(order) * 0.1))
    validation_count = max(2, round(len(order) * 0.1))
    test_indices = order[:test_count]
    validation_indices = order[test_count : test_count + validation_count]
    train_indices = order[test_count + validation_count :]
    return {
        "train": [scenarios[int(index)] for index in train_indices],
        "validation": [scenarios[int(index)] for index in validation_indices],
        "test": [scenarios[int(index)] for index in test_indices],
    }


def combine_scenarios(values: Iterable[ScenarioWindows]) -> trajectory_model.Samples:
    scenarios = tuple(values)
    if not scenarios:
        raise ValueError("At least one scenario is required")
    return trajectory_model.Samples(
        features=np.concatenate([item.features for item in scenarios]),
        targets=np.concatenate([item.targets for item in scenarios]),
        baseline=np.concatenate([item.baseline for item in scenarios]),
        scenario_ids=np.concatenate(
            [np.repeat(item.scenario_id, len(item.features)) for item in scenarios]
        ),
    )


class TrajectoryConvNet(nn.Module):
    """A small TensorRT-friendly temporal convolutional residual predictor."""

    def __init__(
        self,
        *,
        feature_mean: np.ndarray,
        feature_scale: np.ndarray,
        target_scale: np.ndarray,
        hidden_channels: int,
        head_width: int,
    ) -> None:
        super().__init__()
        self.hidden_channels = hidden_channels
        self.head_width = head_width
        self.register_buffer("feature_mean", torch.as_tensor(feature_mean))
        self.register_buffer("feature_scale", torch.as_tensor(feature_scale))
        self.register_buffer("target_scale", torch.as_tensor(target_scale))
        self.register_buffer("smoothing_matrix", torch.from_numpy(_smoothing_matrix()))
        self.encoder = nn.Sequential(
            nn.Conv1d(6, hidden_channels, kernel_size=3, padding=1),
            nn.GELU(),
            nn.Conv1d(hidden_channels, hidden_channels, kernel_size=3, padding=1),
            nn.GELU(),
        )
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(hidden_channels * trajectory_model.HISTORY_STEPS, head_width),
            nn.GELU(),
            nn.Linear(head_width, trajectory_model.FUTURE_STEPS * 2),
        )

    def forward(self, features: torch.Tensor, baseline: torch.Tensor) -> torch.Tensor:
        normalized = (features - self.feature_mean) / self.feature_scale
        steps = trajectory_model.HISTORY_STEPS
        past_xy = normalized[:, : steps * 2].reshape(-1, steps, 2)
        past_velocity = normalized[:, steps * 2 : steps * 4].reshape(-1, steps, 2)
        sine = normalized[:, steps * 4 : steps * 5].reshape(-1, steps, 1)
        cosine = normalized[:, steps * 5 : steps * 6].reshape(-1, steps, 1)
        sequence = torch.cat((past_xy, past_velocity, sine, cosine), dim=2)
        encoded = self.encoder(sequence.transpose(1, 2))
        residual = self.head(encoded) * self.target_scale
        prediction = (baseline + residual).reshape(-1, trajectory_model.FUTURE_STEPS, 2)
        smoothed = torch.matmul(self.smoothing_matrix, prediction)
        return smoothed.reshape(-1, trajectory_model.FUTURE_STEPS * 2)


def _metrics(
    prediction: np.ndarray, target: np.ndarray, baseline: np.ndarray
) -> dict[str, float]:
    return trajectory_model._metrics(prediction, target, baseline)


def _evaluate(
    model: TrajectoryConvNet,
    samples: trajectory_model.Samples,
    device: torch.device,
    batch_size: int,
) -> tuple[np.ndarray, dict[str, float]]:
    predictions: list[np.ndarray] = []
    model.eval()
    with torch.inference_mode():
        for start in range(0, len(samples.features), batch_size):
            stop = start + batch_size
            output = model(
                torch.from_numpy(samples.features[start:stop]).to(device),
                torch.from_numpy(samples.baseline[start:stop]).to(device),
            )
            predictions.append(output.cpu().numpy())
    prediction = np.concatenate(predictions)
    return prediction, _metrics(prediction, samples.targets, samples.baseline)


def train(
    splits: dict[str, trajectory_model.Samples], config: TorchTrainingConfig
) -> tuple[TrajectoryConvNet, dict[str, Any]]:
    torch.manual_seed(config.seed)
    np.random.seed(config.seed)
    torch.set_num_threads(max(1, min(8, torch.get_num_threads())))
    # This model uses deterministic Conv1d/linear/reduction operators and an
    # explicit permutation seed. The global deterministic switch unnecessarily
    # imports Triton on CPU-only Linux runners and can segfault there.
    device = torch.device(config.device)
    train_samples = splits["train"]
    feature_mean = train_samples.features.mean(axis=0).astype(np.float32)
    feature_scale = np.maximum(train_samples.features.std(axis=0), 1e-4).astype(
        np.float32
    )
    residual = train_samples.targets - train_samples.baseline
    target_scale = np.maximum(residual.std(axis=0), 0.1).astype(np.float32)
    model = TrajectoryConvNet(
        feature_mean=feature_mean,
        feature_scale=feature_scale,
        target_scale=target_scale,
        hidden_channels=config.hidden_channels,
        head_width=config.head_width,
    ).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    horizon_weight = torch.linspace(
        1.0, 2.0, trajectory_model.FUTURE_STEPS, device=device
    ).reshape(1, -1, 1)
    rng = np.random.default_rng(config.seed)
    best_validation = math.inf
    best_state: dict[str, torch.Tensor] | None = None
    best_epoch = 0
    epoch_losses: list[float] = []
    validation_history: list[float] = []
    for epoch in range(config.epochs):
        model.train()
        order = rng.permutation(len(train_samples.features))
        losses: list[float] = []
        for start in range(0, len(order), config.batch_size):
            indices = order[start : start + config.batch_size]
            features = torch.from_numpy(train_samples.features[indices]).to(device)
            baseline = torch.from_numpy(train_samples.baseline[indices]).to(device)
            target = torch.from_numpy(train_samples.targets[indices]).to(device)
            prediction = model(features, baseline).reshape(
                -1, trajectory_model.FUTURE_STEPS, 2
            )
            target_xy = target.reshape(-1, trajectory_model.FUTURE_STEPS, 2)
            point_error = torch.nn.functional.smooth_l1_loss(
                prediction, target_xy, reduction="none", beta=0.5
            )
            loss = (point_error * horizon_weight).mean()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        epoch_losses.append(float(np.mean(losses)))
        _, validation_metrics = _evaluate(
            model, splits["validation"], device, config.batch_size
        )
        validation_history.append(validation_metrics["ade_m"])
        if validation_metrics["ade_m"] < best_validation:
            best_validation = validation_metrics["ade_m"]
            best_epoch = epoch + 1
            best_state = {
                key: value.detach().cpu().clone()
                for key, value in model.state_dict().items()
            }
    if best_state is None:
        raise RuntimeError("Training did not produce a finite validation checkpoint")
    model.load_state_dict(best_state)
    model.to(device)
    split_metrics: dict[str, dict[str, float | int]] = {}
    predictions: dict[str, np.ndarray] = {}
    for name, samples in splits.items():
        prediction, metrics = _evaluate(model, samples, device, config.batch_size)
        predictions[name] = prediction
        split_metrics[name] = {"window_count": len(samples.features), **metrics}
    test = split_metrics["test"]
    gates = {
        "real_womd_only": True,
        "scenario_level_holdout": True,
        "minimum_100_scenarios": config.scenario_count >= 100,
        "finite_training": bool(np.isfinite(epoch_losses).all()),
        "beats_constant_velocity_ade": test["ade_m"] < test["constant_velocity_ade_m"],
        "beats_constant_velocity_fde": test["fde_m"] < test["constant_velocity_fde_m"],
    }
    return model.cpu(), {
        "loss_first": round(epoch_losses[0], 8),
        "loss_final": round(epoch_losses[-1], 8),
        "best_epoch": best_epoch,
        "best_validation_ade_m": best_validation,
        "metrics": split_metrics,
        "gates": gates,
        "status": "deployment_candidate" if all(gates.values()) else "no_go",
        "test_prediction_sha256": _sha256(predictions["test"].tobytes()),
    }


def serialize_model(model: TrajectoryConvNet) -> bytes:
    output = io.BytesIO()
    configuration = {
        "hidden_channels": model.hidden_channels,
        "head_width": model.head_width,
        "history_steps": trajectory_model.HISTORY_STEPS,
        "future_steps": trajectory_model.FUTURE_STEPS,
    }
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        entries: dict[str, bytes] = {
            "configuration.json": _canonical_json(configuration)
        }
        for name, tensor in sorted(model.state_dict().items()):
            payload = io.BytesIO()
            np.save(payload, tensor.detach().cpu().numpy(), allow_pickle=False)
            entries[f"{name}.npy"] = payload.getvalue()
        if set(entries) != MODEL_MEMBERS:
            raise ValueError("Trajectory model member allowlist mismatch")
        for name in sorted(entries):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, entries[name])
    return output.getvalue()


def load_model(payload: bytes) -> TrajectoryConvNet:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = archive.namelist()
        if set(names) != MODEL_MEMBERS or any(
            Path(name).name != name for name in names
        ):
            raise ValueError("Trajectory model member allowlist mismatch")
        configuration = json.loads(archive.read("configuration.json"))
        arrays = {
            Path(name).stem: np.load(io.BytesIO(archive.read(name)), allow_pickle=False)
            for name in names
            if name.endswith(".npy")
        }
    model = TrajectoryConvNet(
        feature_mean=arrays.pop("feature_mean"),
        feature_scale=arrays.pop("feature_scale"),
        target_scale=arrays.pop("target_scale"),
        hidden_channels=int(configuration["hidden_channels"]),
        head_width=int(configuration["head_width"]),
    )
    state = model.state_dict()
    for name, value in arrays.items():
        if name == "smoothing_matrix":
            continue
        state[name].copy_(torch.from_numpy(value))
    model.load_state_dict(state)
    model.eval()
    return model


def export_onnx(
    model: TrajectoryConvNet,
    path: Path,
    *,
    dtype: torch.dtype = torch.float32,
) -> Path:
    try:
        import onnx
    except ImportError as error:
        raise RuntimeError("Install the 'nvidia' extra to export ONNX") from error
    path.parent.mkdir(parents=True, exist_ok=True)
    feature_width = trajectory_model.HISTORY_STEPS * 6
    target_width = trajectory_model.FUTURE_STEPS * 2
    batch = torch.export.Dim("batch")
    torch.onnx.export(
        model.eval(),
        args=(),
        kwargs={
            "features": torch.zeros((2, feature_width), dtype=dtype),
            "baseline": torch.zeros((2, target_width), dtype=dtype),
        },
        f=path,
        input_names=["features", "constant_velocity"],
        output_names=["trajectory"],
        dynamic_shapes={"features": {0: batch}, "baseline": {0: batch}},
        opset_version=18,
        dynamo=True,
        external_data=False,
    )
    onnx.checker.check_model(onnx.load(path))
    return path


def _split_fingerprint(values: list[ScenarioWindows]) -> str:
    return _sha256(_canonical_json(sorted(item.scenario_id for item in values)))


def run(
    *,
    cache: Path,
    output: Path,
    config: TorchTrainingConfig,
    refresh_cache: bool = False,
) -> Path:
    prepare_cache(cache, config, refresh=refresh_cache)
    scenario_splits = split_scenarios(_read_cache(cache), config.seed)
    splits = {
        name: combine_scenarios(values) for name, values in scenario_splits.items()
    }
    model, training = train(splits, config)
    payload = serialize_model(model)
    output.mkdir(parents=True, exist_ok=True)
    model_path = output / "trajectory-model.pmtorch"
    model_path.write_bytes(payload)
    onnx_path = export_onnx(model, output / "trajectory-model.onnx")
    report: dict[str, Any] = {
        "record_type": "planmargin.real_womd_torch_trajectory_model_report",
        "schema_version": "1.0.0",
        "source": "Waymo Open Motion Dataset v1.3.1 training TFExamples",
        "synthetic": False,
        "redistribution": "local_only",
        "task": "predict a smoothed 3 s local-frame vehicle path from 1 s of recorded motion",
        "architecture": "TensorRT-friendly two-layer temporal Conv1d residual network",
        "framework": {"torch": torch.__version__, "onnx_opset": 18},
        "configuration": asdict(config),
        "split": {
            name: {
                "scenario_count": len(values),
                "scenario_ids_sha256": _split_fingerprint(values),
                "source_shards": sorted({item.shard_index for item in values}),
            }
            for name, values in scenario_splits.items()
        },
        "claim_boundary": "Research prediction on bounded real WOMD training scenarios; not a Waymo Driver model or a safety claim.",
        **training,
        "model_bytes": len(payload),
        "model_sha256": _sha256(payload),
        "onnx_bytes": onnx_path.stat().st_size,
        "onnx_sha256": _sha256(onnx_path.read_bytes()),
        "source_sha256": _sha256(Path(__file__).read_bytes()),
    }
    report["report_sha256"] = _sha256(_canonical_json(report))
    report_path = output / "training-report.json"
    report_path.write_bytes(_canonical_json(report))
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--scenario-count", type=int, default=DEFAULT_SCENARIO_COUNT)
    parser.add_argument("--shard-count", type=int, default=DEFAULT_SHARD_COUNT)
    parser.add_argument(
        "--max-windows-per-scenario", type=int, default=DEFAULT_MAX_WINDOWS_PER_SCENARIO
    )
    parser.add_argument("--epochs", type=int, default=TorchTrainingConfig.epochs)
    parser.add_argument(
        "--batch-size", type=int, default=TorchTrainingConfig.batch_size
    )
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    parser.add_argument("--refresh-cache", action="store_true")
    args = parser.parse_args()
    report = run(
        cache=args.cache,
        output=args.output,
        config=TorchTrainingConfig(
            scenario_count=args.scenario_count,
            shard_count=args.shard_count,
            max_windows_per_scenario=args.max_windows_per_scenario,
            epochs=args.epochs,
            batch_size=args.batch_size,
            device=args.device,
        ),
        refresh_cache=args.refresh_cache,
    )
    print(report)


if __name__ == "__main__":
    main()
