"""Train an interaction-aware trajectory model on real WOMD scenarios."""

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

from planmargin import scenario_selection, trajectory_model

DEFAULT_OUTPUT = Path("artifacts/experiment-v8/interaction-trajectory-model")
DEFAULT_CACHE = Path("artifacts/experiment-v8/interaction-window-cache.npz")
NEIGHBOR_COUNT = 8
NEIGHBOR_WIDTH = 8
EGO_WIDTH = trajectory_model.HISTORY_STEPS * 6
FEATURE_WIDTH = EGO_WIDTH + NEIGHBOR_COUNT * NEIGHBOR_WIDTH


@dataclass(frozen=True)
class InteractionConfig:
    scenario_count: int = 1024
    shard_count: int = 16
    max_windows_per_scenario: int = 16
    stride: int = 4
    neighbor_count: int = NEIGHBOR_COUNT
    hidden_channels: int = 64
    neighbor_hidden: int = 32
    head_width: int = 256
    epochs: int = 28
    batch_size: int = 512
    learning_rate: float = 8e-4
    weight_decay: float = 1e-5
    seed: int = 31
    device: str = "mps"


@dataclass(frozen=True)
class InteractionScenario:
    scenario_id: str
    shard_index: int
    features: np.ndarray
    targets: np.ndarray
    baseline: np.ndarray


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _rotate(vectors: np.ndarray, yaw: float) -> np.ndarray:
    cosine = np.cos(yaw)
    sine = np.sin(yaw)
    return np.column_stack(
        (
            cosine * vectors[:, 0] + sine * vectors[:, 1],
            -sine * vectors[:, 0] + cosine * vectors[:, 1],
        )
    )


def scenario_windows(
    serialized: bytes,
    *,
    shard_index: int,
    stride: int,
    max_windows: int,
    neighbor_count: int,
) -> InteractionScenario:
    arrays = scenario_selection._scenario_arrays(serialized)
    sdc_indices = np.flatnonzero(arrays.is_sdc)
    if len(sdc_indices) != 1:
        raise ValueError("Interaction model requires exactly one SDC")
    sdc = int(sdc_indices[0])
    features: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    baselines: list[np.ndarray] = []
    final_start = arrays.x.shape[1] - trajectory_model.FUTURE_STEPS
    for current in range(trajectory_model.HISTORY_STEPS - 1, final_start, stride):
        start = current - trajectory_model.HISTORY_STEPS + 1
        stop = current + trajectory_model.FUTURE_STEPS + 1
        if not arrays.valid[sdc, start:stop].all():
            continue
        origin = np.asarray([arrays.x[sdc, current], arrays.y[sdc, current]])
        heading = float(arrays.yaw[sdc, current])
        past_xy = trajectory_model._local_xy(
            np.column_stack(
                (arrays.x[sdc, start : current + 1], arrays.y[sdc, start : current + 1])
            ),
            origin,
            heading,
        )
        past_velocity = _rotate(
            np.column_stack(
                (
                    arrays.vel_x[sdc, start : current + 1],
                    arrays.vel_y[sdc, start : current + 1],
                )
            ),
            heading,
        )
        relative_yaw = trajectory_model._wrap_angle(
            arrays.yaw[sdc, start : current + 1] - heading
        )
        ego = np.concatenate(
            (
                past_xy.reshape(-1),
                past_velocity.reshape(-1),
                np.sin(relative_yaw),
                np.cos(relative_yaw),
            )
        ).astype(np.float32)

        valid_neighbors = np.flatnonzero(arrays.valid[:, current])
        valid_neighbors = valid_neighbors[valid_neighbors != sdc]
        world_positions = np.column_stack(
            (arrays.x[valid_neighbors, current], arrays.y[valid_neighbors, current])
        )
        relative_positions = trajectory_model._local_xy(
            world_positions, origin, heading
        )
        distances = np.linalg.norm(relative_positions, axis=1)
        order = np.argsort(distances, kind="stable")[:neighbor_count]
        neighbor_features = np.zeros((neighbor_count, NEIGHBOR_WIDTH), dtype=np.float32)
        for slot, local_index in enumerate(order):
            object_index = int(valid_neighbors[local_index])
            velocity = _rotate(
                np.asarray(
                    [
                        [
                            arrays.vel_x[object_index, current],
                            arrays.vel_y[object_index, current],
                        ]
                    ]
                ),
                heading,
            )[0]
            yaw = float(
                trajectory_model._wrap_angle(
                    arrays.yaw[object_index, current] - heading
                )
            )
            neighbor_features[slot] = (
                relative_positions[local_index, 0],
                relative_positions[local_index, 1],
                velocity[0],
                velocity[1],
                math.sin(yaw),
                math.cos(yaw),
                float(np.clip(arrays.object_types[object_index], 0, 3)) / 3.0,
                1.0,
            )

        future = trajectory_model._local_xy(
            np.column_stack(
                (arrays.x[sdc, current + 1 : stop], arrays.y[sdc, current + 1 : stop])
            ),
            origin,
            heading,
        ).astype(np.float32)
        times = (
            np.arange(1, trajectory_model.FUTURE_STEPS + 1, dtype=np.float32)[:, None]
            * trajectory_model.STEP_SECONDS
        )
        baseline = times * past_velocity[-1]
        features.append(np.concatenate((ego, neighbor_features.reshape(-1))))
        targets.append(future.reshape(-1))
        baselines.append(baseline.astype(np.float32).reshape(-1))
        if len(features) == max_windows:
            break
    return InteractionScenario(
        scenario_id=arrays.scenario_id,
        shard_index=shard_index,
        features=np.asarray(features, dtype=np.float32).reshape(-1, FEATURE_WIDTH),
        targets=np.asarray(targets, dtype=np.float32).reshape(
            -1, trajectory_model.FUTURE_STEPS * 2
        ),
        baseline=np.asarray(baselines, dtype=np.float32).reshape(
            -1, trajectory_model.FUTURE_STEPS * 2
        ),
    )


def stream_scenarios(config: InteractionConfig) -> Iterator[InteractionScenario]:
    if config.scenario_count < 100:
        raise ValueError("Interaction protocol requires at least 100 scenarios")
    if config.neighbor_count != NEIGHBOR_COUNT:
        raise ValueError(f"neighbor_count is frozen at {NEIGHBOR_COUNT}")
    quotient, remainder = divmod(config.scenario_count, config.shard_count)
    for shard_index in range(config.shard_count):
        target = quotient + (1 if shard_index < remainder else 0)
        dataset = scenario_selection.tf.data.TFRecordDataset(
            [scenario_selection._training_shard_uri(shard_index)],
            buffer_size=8 * 1024 * 1024,
        )
        emitted = 0
        for serialized in dataset:
            windows = scenario_windows(
                serialized.numpy(),
                shard_index=shard_index,
                stride=config.stride,
                max_windows=config.max_windows_per_scenario,
                neighbor_count=config.neighbor_count,
            )
            if len(windows.features) == 0:
                continue
            yield windows
            emitted += 1
            if emitted == target:
                break
        if emitted != target:
            raise RuntimeError(
                f"Shard {shard_index} yielded {emitted} of {target} scenarios"
            )


def write_cache(path: Path, scenarios: Iterable[InteractionScenario]) -> None:
    values = tuple(scenarios)
    if not values:
        raise ValueError("Cannot cache empty interaction evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        scenario_ids=np.asarray([value.scenario_id for value in values], dtype=str),
        shard_indices=np.asarray(
            [value.shard_index for value in values], dtype=np.int16
        ),
        window_counts=np.asarray(
            [len(value.features) for value in values], dtype=np.int16
        ),
        features=np.concatenate([value.features for value in values]),
        targets=np.concatenate([value.targets for value in values]),
        baseline=np.concatenate([value.baseline for value in values]),
    )


def read_cache(path: Path) -> list[InteractionScenario]:
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError(path)
    with np.load(path, allow_pickle=False) as values:
        ids = values["scenario_ids"]
        shards = values["shard_indices"]
        counts = values["window_counts"]
        features = values["features"]
        targets = values["targets"]
        baseline = values["baseline"]
    if int(counts.sum()) != len(features):
        raise ValueError("Interaction cache accounting is inconsistent")
    result = []
    offset = 0
    for scenario_id, shard, count in zip(ids, shards, counts, strict=True):
        stop = offset + int(count)
        result.append(
            InteractionScenario(
                scenario_id=str(scenario_id),
                shard_index=int(shard),
                features=np.asarray(features[offset:stop], dtype=np.float32),
                targets=np.asarray(targets[offset:stop], dtype=np.float32),
                baseline=np.asarray(baseline[offset:stop], dtype=np.float32),
            )
        )
        offset = stop
    return result


def split_scenarios(
    values: list[InteractionScenario], seed: int
) -> dict[str, list[InteractionScenario]]:
    order = np.random.default_rng(seed).permutation(len(values))
    test_count = max(10, round(len(order) * 0.1))
    validation_count = max(10, round(len(order) * 0.1))
    return {
        "test": [values[int(index)] for index in order[:test_count]],
        "validation": [
            values[int(index)]
            for index in order[test_count : test_count + validation_count]
        ],
        "train": [
            values[int(index)] for index in order[test_count + validation_count :]
        ],
    }


def combine(
    values: Iterable[InteractionScenario],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    scenarios = tuple(values)
    if not scenarios:
        raise ValueError("Interaction split is empty")
    return (
        np.concatenate([value.features for value in scenarios]),
        np.concatenate([value.targets for value in scenarios]),
        np.concatenate([value.baseline for value in scenarios]),
    )


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


class InteractionTrajectoryNet(nn.Module):
    def __init__(
        self,
        *,
        feature_mean: np.ndarray,
        feature_scale: np.ndarray,
        target_scale: np.ndarray,
        config: InteractionConfig,
        use_neighbors: bool,
    ) -> None:
        super().__init__()
        self.use_neighbors = use_neighbors
        self.config = config
        self.register_buffer("feature_mean", torch.as_tensor(feature_mean))
        self.register_buffer("feature_scale", torch.as_tensor(feature_scale))
        self.register_buffer("target_scale", torch.as_tensor(target_scale))
        self.register_buffer("smoothing_matrix", torch.from_numpy(_smoothing_matrix()))
        self.ego_encoder = nn.Sequential(
            nn.Conv1d(6, config.hidden_channels, 3, padding=1),
            nn.SiLU(),
            nn.Conv1d(config.hidden_channels, config.hidden_channels, 3, padding=1),
            nn.SiLU(),
        )
        self.neighbor_encoder = nn.Sequential(
            nn.Linear(NEIGHBOR_WIDTH - 1, config.neighbor_hidden),
            nn.SiLU(),
            nn.Linear(config.neighbor_hidden, config.neighbor_hidden),
            nn.SiLU(),
        )
        fusion_width = (
            config.hidden_channels * trajectory_model.HISTORY_STEPS
            + config.neighbor_hidden
        )
        self.head = nn.Sequential(
            nn.Linear(fusion_width, config.head_width),
            nn.SiLU(),
            nn.Linear(config.head_width, trajectory_model.FUTURE_STEPS * 2),
        )

    def forward(self, features: torch.Tensor, baseline: torch.Tensor) -> torch.Tensor:
        normalized = (features - self.feature_mean) / self.feature_scale
        steps = trajectory_model.HISTORY_STEPS
        past_xy = normalized[:, : steps * 2].reshape(-1, steps, 2)
        past_velocity = normalized[:, steps * 2 : steps * 4].reshape(-1, steps, 2)
        sine = normalized[:, steps * 4 : steps * 5].reshape(-1, steps, 1)
        cosine = normalized[:, steps * 5 : EGO_WIDTH].reshape(-1, steps, 1)
        ego = torch.cat((past_xy, past_velocity, sine, cosine), dim=2)
        ego_encoded = self.ego_encoder(ego.transpose(1, 2)).flatten(1)
        neighbors = normalized[:, EGO_WIDTH:].reshape(
            -1, NEIGHBOR_COUNT, NEIGHBOR_WIDTH
        )
        mask = (
            features[:, EGO_WIDTH:]
            .reshape(-1, NEIGHBOR_COUNT, NEIGHBOR_WIDTH)[:, :, -1:]
            .clamp(0, 1)
        )
        if self.use_neighbors:
            encoded = self.neighbor_encoder(neighbors[:, :, :-1]) * mask
            pooled = encoded.sum(dim=1) / mask.sum(dim=1).clamp_min(1.0)
        else:
            pooled = torch.zeros(
                (features.shape[0], self.config.neighbor_hidden),
                dtype=features.dtype,
                device=features.device,
            )
        residual = (
            self.head(torch.cat((ego_encoded, pooled), dim=1)) * self.target_scale
        )
        prediction = (baseline + residual).reshape(-1, trajectory_model.FUTURE_STEPS, 2)
        return torch.matmul(self.smoothing_matrix, prediction).reshape(
            -1, trajectory_model.FUTURE_STEPS * 2
        )


def _metrics(
    prediction: np.ndarray, target: np.ndarray, baseline: np.ndarray
) -> dict[str, float]:
    return trajectory_model._metrics(prediction, target, baseline)


def _evaluate(
    model: InteractionTrajectoryNet,
    values: tuple[np.ndarray, np.ndarray, np.ndarray],
    device: torch.device,
    batch_size: int,
) -> dict[str, float]:
    features, targets, baseline = values
    outputs = []
    model.eval()
    with torch.inference_mode():
        for start in range(0, len(features), batch_size):
            stop = start + batch_size
            outputs.append(
                model(
                    torch.from_numpy(features[start:stop]).to(device),
                    torch.from_numpy(baseline[start:stop]).to(device),
                )
                .cpu()
                .numpy()
            )
    return _metrics(np.concatenate(outputs), targets, baseline)


def train_model(
    splits: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
    config: InteractionConfig,
    *,
    use_neighbors: bool,
    seed_offset: int,
) -> tuple[InteractionTrajectoryNet, dict[str, Any]]:
    torch.manual_seed(config.seed + seed_offset)
    np.random.seed(config.seed + seed_offset)
    torch.use_deterministic_algorithms(True)
    device = torch.device(config.device)
    train_features, train_targets, train_baseline = splits["train"]
    feature_mean = train_features.mean(axis=0).astype(np.float32)
    feature_scale = np.maximum(train_features.std(axis=0), 1e-4).astype(np.float32)
    target_scale = np.maximum((train_targets - train_baseline).std(axis=0), 0.1).astype(
        np.float32
    )
    model = InteractionTrajectoryNet(
        feature_mean=feature_mean,
        feature_scale=feature_scale,
        target_scale=target_scale,
        config=config,
        use_neighbors=use_neighbors,
    ).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    rng = np.random.default_rng(config.seed + seed_offset)
    best_state: dict[str, torch.Tensor] | None = None
    best_ade = math.inf
    best_epoch = 0
    losses = []
    for epoch in range(config.epochs):
        model.train()
        order = rng.permutation(len(train_features))
        epoch_losses = []
        for start in range(0, len(order), config.batch_size):
            indices = order[start : start + config.batch_size]
            prediction = model(
                torch.from_numpy(train_features[indices]).to(device),
                torch.from_numpy(train_baseline[indices]).to(device),
            )
            target = torch.from_numpy(train_targets[indices]).to(device)
            loss = torch.nn.functional.smooth_l1_loss(prediction, target, beta=0.5)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            epoch_losses.append(float(loss.detach().cpu()))
        losses.append(float(np.mean(epoch_losses)))
        metrics = _evaluate(model, splits["validation"], device, config.batch_size)
        if metrics["ade_m"] < best_ade:
            best_ade = metrics["ade_m"]
            best_epoch = epoch + 1
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }
    if best_state is None:
        raise RuntimeError("No finite interaction checkpoint")
    model.load_state_dict(best_state)
    model.to(device)
    metrics = {
        name: {
            "window_count": len(values[0]),
            **_evaluate(model, values, device, config.batch_size),
        }
        for name, values in splits.items()
    }
    return model.cpu(), {
        "best_epoch": best_epoch,
        "best_validation_ade_m": best_ade,
        "loss_first": round(losses[0], 8),
        "loss_final": round(losses[-1], 8),
        "metrics": metrics,
    }


def serialize_model(model: InteractionTrajectoryNet) -> bytes:
    output = io.BytesIO()
    entries = {
        "configuration.json": _canonical_json(
            {
                "use_neighbors": model.use_neighbors,
                "configuration": asdict(model.config),
            }
        )
    }
    for name, tensor in sorted(model.state_dict().items()):
        payload = io.BytesIO()
        np.save(payload, tensor.detach().cpu().numpy(), allow_pickle=False)
        entries[f"{name}.npy"] = payload.getvalue()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, entries[name])
    return output.getvalue()


def export_onnx(model: InteractionTrajectoryNet, path: Path) -> Path:
    try:
        import onnx
    except ImportError as error:
        raise RuntimeError("Install the 'nvidia' extra to export ONNX") from error
    batch = torch.export.Dim("batch")
    torch.onnx.export(
        model.eval(),
        args=(),
        kwargs={
            "features": torch.zeros((2, FEATURE_WIDTH), dtype=torch.float32),
            "baseline": torch.zeros(
                (2, trajectory_model.FUTURE_STEPS * 2), dtype=torch.float32
            ),
        },
        f=path,
        input_names=["scene_features", "constant_velocity"],
        output_names=["sdc_trajectory"],
        dynamic_shapes={"features": {0: batch}, "baseline": {0: batch}},
        opset_version=18,
        dynamo=True,
        external_data=False,
    )
    onnx.checker.check_model(onnx.load(path))
    return path


def run(
    cache: Path, output: Path, config: InteractionConfig, *, refresh_cache: bool
) -> Path:
    if refresh_cache or not cache.is_file():
        write_cache(cache, stream_scenarios(config))
    scenarios = read_cache(cache)
    if len(scenarios) != config.scenario_count:
        raise ValueError(
            f"Expected {config.scenario_count} scenarios, found {len(scenarios)}"
        )
    grouped = split_scenarios(scenarios, config.seed)
    splits = {name: combine(values) for name, values in grouped.items()}
    interaction_model, interaction = train_model(
        splits, config, use_neighbors=True, seed_offset=0
    )
    ego_model, ego = train_model(splits, config, use_neighbors=False, seed_offset=1)
    test = interaction["metrics"]["test"]
    ego_test = ego["metrics"]["test"]
    gates = {
        "real_womd_only": True,
        "minimum_1000_scenarios": config.scenario_count >= 1000,
        "complete_scenario_holdout": True,
        "finite_training": math.isfinite(interaction["loss_final"]),
        "beats_constant_velocity_ade": test["ade_m"] < test["constant_velocity_ade_m"],
        "beats_constant_velocity_fde": test["fde_m"] < test["constant_velocity_fde_m"],
        "neighbors_improve_ade_by_1_percent": test["ade_m"] <= 0.99 * ego_test["ade_m"],
        "neighbors_improve_fde_by_1_percent": test["fde_m"] <= 0.99 * ego_test["fde_m"],
    }
    output.mkdir(parents=True, exist_ok=True)
    payload = serialize_model(interaction_model)
    (output / "interaction-trajectory-model.pmtorch").write_bytes(payload)
    onnx_path = export_onnx(
        interaction_model, output / "interaction-trajectory-model.onnx"
    )
    report = {
        "record_type": "planmargin.interaction_trajectory_model_report",
        "schema_version": "1.0.0",
        "experiment": "v8",
        "source": "Waymo Open Motion Dataset v1.3.1 training TFExamples",
        "synthetic": False,
        "configuration": asdict(config),
        "feature_contract": {
            "ego_history_steps": trajectory_model.HISTORY_STEPS,
            "nearest_actors": NEIGHBOR_COUNT,
            "neighbor_values": [
                "relative_x",
                "relative_y",
                "relative_vx",
                "relative_vy",
                "sin_yaw",
                "cos_yaw",
                "object_type",
                "valid",
            ],
        },
        "split": {
            name: {"scenario_count": len(values), "window_count": len(splits[name][0])}
            for name, values in grouped.items()
        },
        "interaction_model": interaction,
        "ego_only_ablation": ego,
        "gates": gates,
        "status": "deployment_candidate" if all(gates.values()) else "no_go",
        "claim_boundary": "SDC trajectory prediction on bounded real WOMD training scenarios; not a planner, Waymo Driver model, or safety claim.",
        "model_bytes": len(payload),
        "model_sha256": _sha256(payload),
        "onnx_bytes": onnx_path.stat().st_size,
        "onnx_sha256": _sha256(onnx_path.read_bytes()),
        "source_sha256": _sha256(Path(__file__).read_bytes()),
    }
    report["report_sha256"] = _sha256(_canonical_json(report))
    path = output / "training-report.json"
    path.write_bytes(_canonical_json(report))
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--scenario-count", type=int, default=InteractionConfig.scenario_count
    )
    parser.add_argument(
        "--shard-count", type=int, default=InteractionConfig.shard_count
    )
    parser.add_argument(
        "--max-windows-per-scenario",
        type=int,
        default=InteractionConfig.max_windows_per_scenario,
    )
    parser.add_argument("--epochs", type=int, default=InteractionConfig.epochs)
    parser.add_argument("--batch-size", type=int, default=InteractionConfig.batch_size)
    parser.add_argument(
        "--device", choices=("cpu", "mps", "cuda"), default=InteractionConfig.device
    )
    parser.add_argument("--refresh-cache", action="store_true")
    args = parser.parse_args()
    config = InteractionConfig(
        scenario_count=args.scenario_count,
        shard_count=args.shard_count,
        max_windows_per_scenario=args.max_windows_per_scenario,
        epochs=args.epochs,
        batch_size=args.batch_size,
        device=args.device,
    )
    print(run(args.cache, args.output, config, refresh_cache=args.refresh_cache))


if __name__ == "__main__":
    main()
