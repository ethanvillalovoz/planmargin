"""Train a deterministic JAX trajectory predictor on real WOMD tracks.

The model is deliberately small enough to train on a laptop.  It predicts a
three-second local-frame path from one second of recorded motion and is
evaluated on scenarios that never contribute training windows.  The output is
an engineering qualification artifact, not a production driving policy.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import jax
import jax.numpy as jnp
import numpy as np
import optax
from scipy.signal import savgol_filter

DEFAULT_MANIFEST = Path("artifacts/stage-0/scenario-selection.json")
DEFAULT_OUTPUT_DIR = Path("artifacts/experiment-v3/trajectory-model")
HISTORY_STEPS = 11
FUTURE_STEPS = 30
STEP_SECONDS = 0.1
VEHICLE_TYPE = 1


@dataclass(frozen=True)
class TrainingConfig:
    hidden_size: int = 128
    epochs: int = 320
    batch_size: int = 128
    learning_rate: float = 8e-4
    weight_decay: float = 1e-5
    stride: int = 3


@dataclass(frozen=True)
class Samples:
    features: np.ndarray
    targets: np.ndarray
    baseline: np.ndarray
    scenario_ids: np.ndarray


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _wrap_angle(values: np.ndarray) -> np.ndarray:
    return (values + np.pi) % (2 * np.pi) - np.pi


def _local_xy(values: np.ndarray, origin: np.ndarray, yaw: float) -> np.ndarray:
    delta = values - origin
    cosine = np.cos(yaw)
    sine = np.sin(yaw)
    return np.column_stack(
        (
            cosine * delta[:, 0] + sine * delta[:, 1],
            -sine * delta[:, 0] + cosine * delta[:, 1],
        )
    )


def windows_from_tracks(
    *,
    scenario_id: str,
    x: np.ndarray,
    y: np.ndarray,
    yaw: np.ndarray,
    vel_x: np.ndarray,
    vel_y: np.ndarray,
    valid: np.ndarray,
    object_types: np.ndarray,
    stride: int = 3,
) -> Samples:
    """Create real, local-frame vehicle windows from one WOMD scenario."""
    features: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    baselines: list[np.ndarray] = []
    ids: list[str] = []
    final_start = x.shape[1] - FUTURE_STEPS
    for object_index in np.flatnonzero(np.asarray(object_types) == VEHICLE_TYPE):
        for current in range(HISTORY_STEPS - 1, final_start, stride):
            start = current - HISTORY_STEPS + 1
            stop = current + FUTURE_STEPS + 1
            if not np.asarray(valid[object_index, start:stop], dtype=bool).all():
                continue
            origin = np.array([x[object_index, current], y[object_index, current]])
            heading = float(yaw[object_index, current])
            past_xy = _local_xy(
                np.column_stack(
                    (
                        x[object_index, start : current + 1],
                        y[object_index, start : current + 1],
                    )
                ),
                origin,
                heading,
            )
            past_velocity = _local_xy(
                np.column_stack(
                    (
                        vel_x[object_index, start : current + 1],
                        vel_y[object_index, start : current + 1],
                    )
                ),
                np.zeros(2),
                heading,
            )
            relative_yaw = _wrap_angle(yaw[object_index, start : current + 1] - heading)
            future_xy = _local_xy(
                np.column_stack(
                    (
                        x[object_index, current + 1 : stop],
                        y[object_index, current + 1 : stop],
                    )
                ),
                origin,
                heading,
            )
            times = (
                np.arange(1, FUTURE_STEPS + 1, dtype=np.float32)[:, None] * STEP_SECONDS
            )
            baseline = times * past_velocity[-1]
            features.append(
                np.concatenate(
                    (
                        past_xy.reshape(-1),
                        past_velocity.reshape(-1),
                        np.sin(relative_yaw),
                        np.cos(relative_yaw),
                    )
                ).astype(np.float32)
            )
            targets.append(future_xy.astype(np.float32).reshape(-1))
            baselines.append(baseline.astype(np.float32).reshape(-1))
            ids.append(scenario_id)
    feature_width = HISTORY_STEPS * 6
    target_width = FUTURE_STEPS * 2
    return Samples(
        np.asarray(features, dtype=np.float32).reshape(-1, feature_width),
        np.asarray(targets, dtype=np.float32).reshape(-1, target_width),
        np.asarray(baselines, dtype=np.float32).reshape(-1, target_width),
        np.asarray(ids, dtype=str),
    )


def combine_samples(groups: Iterable[Samples]) -> Samples:
    values = tuple(groups)
    if not values:
        raise ValueError("At least one sample group is required")
    return Samples(
        *(
            np.concatenate([getattr(item, field) for item in values])
            for field in Samples.__dataclass_fields__
        )
    )


def initialize_parameters(
    key: jax.Array, input_size: int, hidden_size: int, output_size: int
) -> dict[str, jax.Array]:
    keys = jax.random.split(key, 3)
    widths = (
        (input_size, hidden_size),
        (hidden_size, hidden_size),
        (hidden_size, output_size),
    )
    parameters: dict[str, jax.Array] = {}
    for index, ((fan_in, fan_out), layer_key) in enumerate(
        zip(widths, keys, strict=True)
    ):
        parameters[f"w{index}"] = jax.random.normal(
            layer_key, (fan_in, fan_out)
        ) * np.sqrt(2.0 / fan_in)
        parameters[f"b{index}"] = jnp.zeros((fan_out,))
    return parameters


def _forward(parameters: dict[str, jax.Array], features: jax.Array) -> jax.Array:
    hidden = jax.nn.gelu(features @ parameters["w0"] + parameters["b0"])
    hidden = jax.nn.gelu(hidden @ parameters["w1"] + parameters["b1"])
    return hidden @ parameters["w2"] + parameters["b2"]


def _metrics(
    prediction: np.ndarray, target: np.ndarray, baseline: np.ndarray
) -> dict[str, float]:
    predicted_xy = prediction.reshape(-1, FUTURE_STEPS, 2)
    target_xy = target.reshape(-1, FUTURE_STEPS, 2)
    baseline_xy = baseline.reshape(-1, FUTURE_STEPS, 2)
    errors = np.linalg.norm(predicted_xy - target_xy, axis=2)
    baseline_errors = np.linalg.norm(baseline_xy - target_xy, axis=2)
    return {
        "ade_m": round(float(errors.mean()), 6),
        "fde_m": round(float(errors[:, -1].mean()), 6),
        "constant_velocity_ade_m": round(float(baseline_errors.mean()), 6),
        "constant_velocity_fde_m": round(float(baseline_errors[:, -1].mean()), 6),
    }


def train(
    train_samples: Samples,
    evaluation: dict[str, Samples],
    config: TrainingConfig,
    seed: int = 0,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    if len(train_samples.features) == 0:
        raise ValueError("Training split has no valid real-data windows")
    feature_mean = train_samples.features.mean(axis=0)
    feature_scale = np.maximum(train_samples.features.std(axis=0), 1e-4)
    residual = train_samples.targets - train_samples.baseline
    target_scale = np.maximum(residual.std(axis=0), 0.1)
    normalized_features = (train_samples.features - feature_mean) / feature_scale
    normalized_targets = residual / target_scale
    parameters = initialize_parameters(
        jax.random.PRNGKey(seed),
        normalized_features.shape[1],
        config.hidden_size,
        normalized_targets.shape[1],
    )
    optimizer = optax.adamw(config.learning_rate, weight_decay=config.weight_decay)
    optimizer_state = optimizer.init(parameters)

    @jax.jit
    def step(
        params: dict[str, jax.Array],
        state: optax.OptState,
        batch_x: jax.Array,
        batch_y: jax.Array,
    ) -> tuple[dict[str, jax.Array], optax.OptState, jax.Array]:
        def loss_fn(candidate: dict[str, jax.Array]) -> jax.Array:
            return jnp.mean((_forward(candidate, batch_x) - batch_y) ** 2)

        loss, gradients = jax.value_and_grad(loss_fn)(params)
        updates, next_state = optimizer.update(gradients, state, params)
        return optax.apply_updates(params, updates), next_state, loss

    rng = np.random.default_rng(seed)
    losses: list[float] = []
    for _ in range(config.epochs):
        order = rng.permutation(len(normalized_features))
        epoch_losses: list[float] = []
        for start in range(0, len(order), config.batch_size):
            indices = order[start : start + config.batch_size]
            parameters, optimizer_state, loss = step(
                parameters,
                optimizer_state,
                jnp.asarray(normalized_features[indices]),
                jnp.asarray(normalized_targets[indices]),
            )
            epoch_losses.append(float(loss))
        losses.append(float(np.mean(epoch_losses)))

    frozen = {key: np.asarray(value) for key, value in parameters.items()}
    frozen.update(
        feature_mean=feature_mean.astype(np.float32),
        feature_scale=feature_scale.astype(np.float32),
        target_scale=target_scale.astype(np.float32),
    )
    split_metrics: dict[str, dict[str, float | int]] = {}
    for name, samples in evaluation.items():
        prediction = predict(frozen, samples.features, samples.baseline)
        split_metrics[name] = {
            "window_count": len(samples.features),
            **_metrics(prediction, samples.targets, samples.baseline),
        }
    test = split_metrics["test"]
    baseline_comparison = {
        "model_beats_constant_velocity_ade": test["ade_m"]
        < test["constant_velocity_ade_m"],
        "model_beats_constant_velocity_fde": test["fde_m"]
        < test["constant_velocity_fde_m"],
        "superiority_claim_supported": False,
    }
    gates = {
        "real_womd_only": True,
        "scenario_level_holdout": True,
        "finite_training": bool(np.isfinite(losses).all()),
        "held_out_ade_below_0_50_m": test["ade_m"] < 0.50,
        "held_out_fde_below_1_00_m": test["fde_m"] < 1.00,
    }
    return frozen, {
        "loss_first": round(losses[0], 8),
        "loss_final": round(losses[-1], 8),
        "metrics": split_metrics,
        "baseline_comparison": baseline_comparison,
        "gates": gates,
        "status": "visualization_qualified" if all(gates.values()) else "no_go",
    }


def predict(
    parameters: dict[str, np.ndarray], features: np.ndarray, baseline: np.ndarray
) -> np.ndarray:
    normalized = (features - parameters["feature_mean"]) / parameters["feature_scale"]
    network = {
        key: jnp.asarray(value)
        for key, value in parameters.items()
        if key.startswith(("w", "b"))
    }
    residual = (
        np.asarray(_forward(network, jnp.asarray(normalized)))
        * parameters["target_scale"]
    )
    prediction = (np.asarray(baseline) + residual).reshape(-1, FUTURE_STEPS, 2)
    # Independent output heads can introduce high-frequency lateral jitter that
    # is physically meaningless at 10 Hz. This fixed non-learned filter is part
    # of the inference contract and is evaluated by the held-out gates.
    smoothed = savgol_filter(prediction, 11, 2, axis=1, mode="interp")
    return np.asarray(smoothed, dtype=np.float32).reshape(-1, FUTURE_STEPS * 2)


def serialize_model(parameters: dict[str, np.ndarray]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(parameters):
            payload = io.BytesIO()
            np.save(payload, np.asarray(parameters[name]), allow_pickle=False)
            entry = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, payload.getvalue())
    return output.getvalue()


def load_model(payload: bytes) -> dict[str, np.ndarray]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = archive.namelist()
        expected = {
            "w0.npy",
            "b0.npy",
            "w1.npy",
            "b1.npy",
            "w2.npy",
            "b2.npy",
            "feature_mean.npy",
            "feature_scale.npy",
            "target_scale.npy",
        }
        if set(names) != expected or any(Path(name).name != name for name in names):
            raise ValueError("Trajectory model member allowlist mismatch")
        return {
            Path(name).stem: np.load(io.BytesIO(archive.read(name)), allow_pickle=False)
            for name in names
        }


def _real_samples(manifest: Path, stride: int) -> list[tuple[Samples, dict[str, Any]]]:
    from planmargin.family_validation import _load_manifest_scenarios

    result: list[tuple[Samples, dict[str, Any]]] = []
    for scenario, candidate in _load_manifest_scenarios(manifest):
        trajectory = scenario.log_trajectory
        result.append(
            (
                windows_from_tracks(
                    scenario_id=candidate["scenario_id"],
                    x=np.asarray(trajectory.x),
                    y=np.asarray(trajectory.y),
                    yaw=np.asarray(trajectory.yaw),
                    vel_x=np.asarray(trajectory.vel_x),
                    vel_y=np.asarray(trajectory.vel_y),
                    valid=np.asarray(trajectory.valid),
                    object_types=np.asarray(scenario.object_metadata.object_types),
                    stride=stride,
                ),
                candidate,
            )
        )
    return result


def run(manifest: Path, output: Path, config: TrainingConfig, seed: int = 0) -> Path:
    groups = _real_samples(manifest, config.stride)
    if len(groups) != 10:
        raise ValueError("The frozen experiment requires exactly ten WOMD scenarios")
    train_groups = groups[:8]
    validation_group = groups[8]
    test_group = groups[9]
    splits = {
        "train": combine_samples(group for group, _ in train_groups),
        "validation": validation_group[0],
        "test": test_group[0],
    }
    parameters, training = train(splits["train"], splits, config, seed)
    payload = serialize_model(parameters)
    output.mkdir(parents=True, exist_ok=True)
    model_path = output / "trajectory-model.pmzip"
    model_path.write_bytes(payload)
    report: dict[str, Any] = {
        "record_type": "planmargin.real_womd_trajectory_model_report",
        "schema_version": "1.0.0",
        "source": "Waymo Open Motion Dataset v1.3.1 training TFExamples",
        "synthetic": False,
        "task": "predict and deterministically smooth 3 s of local-frame vehicle motion from 1 s of recorded history",
        "claim_boundary": "Research trajectory prediction on ten selected WOMD scenarios; not a Waymo Driver model and not a safety claim.",
        "split": {
            "train_scenario_ids_sha256": _sha256(
                _canonical_json(
                    [candidate["scenario_id"] for _, candidate in train_groups]
                )
            ),
            "validation_scenario_id_sha256": _sha256(
                validation_group[1]["scenario_id"].encode()
            ),
            "test_scenario_id_sha256": _sha256(test_group[1]["scenario_id"].encode()),
            "scenario_counts": {"train": 8, "validation": 1, "test": 1},
        },
        "configuration": config.__dict__,
        "source_sha256": _sha256(Path(__file__).read_bytes()),
        **training,
        "model_bytes": len(payload),
        "model_sha256": _sha256(payload),
    }
    report["report_sha256"] = _sha256(_canonical_json(report))
    (output / "training-report.json").write_bytes(_canonical_json(report))
    return output / "training-report.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--epochs", type=int, default=TrainingConfig.epochs)
    args = parser.parse_args()
    report = run(
        args.manifest, args.output, TrainingConfig(epochs=args.epochs), args.seed
    )
    print(report)


if __name__ == "__main__":
    main()
