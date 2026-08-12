"""Deterministic Waymax smoke test over one streamed WOMD scenario."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.metadata
import json
import os
import platform
import resource
import sys
import time
from pathlib import Path
from typing import Any

# Set TensorFlow logging before importing TensorFlow through Waymax.
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import jax
import numpy as np
import tensorflow as tf
from waymax import agents
from waymax import config
from waymax import dynamics
from waymax import env
from waymax.dataloader import womd_dataloader
from waymax.dataloader import womd_factories

DATASET_VERSION = "1.3.1"
DEFAULT_SHARD_URI = (
    "gs://waymo_open_dataset_motion_v_1_3_1/uncompressed/tf_example/"
    "training/training_tfexample.tfrecord-00000-of-01000"
)
WAYMAX_COMMIT = "a64dfec9be8576b60d9cecc94f406d9812d4a7d0"
MAX_NUM_OBJECTS = 128
SEED = 0


def _peak_rss_bytes() -> int:
    """Return process peak resident memory in bytes on macOS and Linux."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def _update_hash(digest: Any, state: Any) -> None:
    """Hash only simulated trajectories, using explicit shape and dtype tags."""
    for leaf in jax.tree_util.tree_leaves(state.sim_trajectory):
        array = np.ascontiguousarray(np.asarray(leaf))
        digest.update(str(array.dtype).encode())
        digest.update(str(array.shape).encode())
        digest.update(array.tobytes())


def _dataset_config(
    shard_uri: str, *, allow_validation_access: bool
) -> tuple[Any, str]:
    if "/training/training_tfexample." in shard_uri:
        return config.WOD_1_3_1_TRAINING, "training"
    if "/validation/validation_tfexample." in shard_uri:
        if not allow_validation_access:
            raise ValueError(
                "Validation access is never implicit; pass "
                "--allow-validation-access only under an authorized protocol."
            )
        return config.WOD_1_3_1_VALIDATION, "validation"
    raise ValueError("Shard URI must identify a WOMD v1.3.1 training or validation TFExample.")


def _load_first_scenario(
    shard_uri: str, *, allow_validation_access: bool = False
) -> tuple[Any, str, int, str]:
    """Stream and parse only the first TFExample from one fixed shard."""
    base_config, split = _dataset_config(
        shard_uri, allow_validation_access=allow_validation_access
    )
    dataset_config = dataclasses.replace(
        base_config,
        path=shard_uri,
        repeat=1,
        batch_dims=(),
        shuffle_seed=None,
        num_shards=1,
        deterministic=True,
        include_sdc_paths=False,
        num_paths=None,
        num_points_per_path=None,
        max_num_objects=MAX_NUM_OBJECTS,
    )
    options = tf.data.Options()
    options.deterministic = True
    records = tf.data.TFRecordDataset([shard_uri]).with_options(options).take(1)
    serialized = next(iter(records))
    serialized_bytes = serialized.numpy()

    example = tf.train.Example.FromString(serialized_bytes)
    scenario_id_values = example.features.feature[
        "scenario/id"
    ].bytes_list.value
    if not scenario_id_values:
        raise RuntimeError("The streamed TFExample has no scenario/id value.")
    scenario_id = scenario_id_values[0].decode("utf-8")

    parsed = womd_dataloader.preprocess_serialized_womd_data(
        serialized, dataset_config
    )
    scenario = womd_factories.simulator_state_from_womd_dict(
        parsed, include_sdc_paths=False
    )
    return scenario, scenario_id, len(serialized_bytes), split


def _rollout_once(
    scenario: Any,
    environment: Any,
    actor: Any,
    rollout_steps: int,
) -> tuple[Any, str]:
    """Run an unmodified expert-SDC rollout and return its final state/hash."""
    jit_step = jax.jit(environment.step)
    jit_select_action = jax.jit(actor.select_action)
    rng = jax.random.PRNGKey(SEED)
    state = environment.reset(scenario)
    digest = hashlib.sha256()
    _update_hash(digest, state)

    for _ in range(rollout_steps):
        actor_output = jit_select_action(None, state, None, rng)
        state = jit_step(state, actor_output.action)
        _update_hash(digest, state)

    jax.block_until_ready(state.timestep)
    return state, digest.hexdigest()


def _finite_summary(values: np.ndarray, valid: np.ndarray) -> dict[str, Any]:
    selected = np.asarray(values)[np.asarray(valid, dtype=bool)]
    selected = selected[np.isfinite(selected)]
    if selected.size == 0:
        return {"valid_count": 0, "mean": None, "max": None}
    return {
        "valid_count": int(selected.size),
        "mean": float(np.mean(selected)),
        "max": float(np.max(selected)),
    }


def _metric_summary(environment: Any, state: Any) -> dict[str, Any]:
    """Export small aggregates from Waymax's built-in final-state metrics."""
    is_sdc = np.asarray(state.object_metadata.is_sdc, dtype=bool)
    object_valid = np.squeeze(
        np.asarray(state.current_sim_trajectory.valid, dtype=bool), axis=-1
    )
    if object_valid.shape != is_sdc.shape:
        raise RuntimeError(
            "Object-valid and object-metadata masks have different shapes: "
            f"{object_valid.shape} != {is_sdc.shape}."
        )
    sdc_indices = np.flatnonzero(is_sdc)
    if sdc_indices.size != 1:
        raise RuntimeError(f"Expected exactly one SDC, found {sdc_indices.size}.")
    sdc_index = int(sdc_indices[0])

    summary: dict[str, Any] = {}
    for name, metric in environment.metrics(state).items():
        values = np.asarray(metric.value)
        # Some Waymax metrics, notably offroad, mark padded object slots as
        # metric-valid. Exclude slots without a valid simulated object before
        # computing research-facing aggregates.
        valid = np.asarray(metric.valid, dtype=bool) & object_valid
        item = _finite_summary(values, valid)
        item["sdc_valid"] = bool(valid[sdc_index])
        item["sdc_value"] = (
            float(values[sdc_index])
            if valid[sdc_index] and np.isfinite(values[sdc_index])
            else None
        )
        summary[name] = item
    return summary


def run(
    shard_uri: str,
    requested_steps: int,
    *,
    allow_validation_access: bool = False,
) -> dict[str, Any]:
    """Execute the complete Stage 0 smoke test and return its report."""
    started = time.perf_counter()
    load_started = time.perf_counter()
    scenario, scenario_id, record_bytes, split = _load_first_scenario(
        shard_uri, allow_validation_access=allow_validation_access
    )
    load_seconds = time.perf_counter() - load_started

    dynamics_model = dynamics.StateDynamics()
    environment = env.BaseEnvironment(
        dynamics_model=dynamics_model,
        config=dataclasses.replace(
            config.EnvironmentConfig(),
            max_num_objects=MAX_NUM_OBJECTS,
            controlled_object=config.ObjectType.SDC,
            compute_reward=False,
        ),
    )
    actor = agents.create_expert_actor(dynamics_model=dynamics_model)
    reset_state = environment.reset(scenario)
    remaining_steps = int(reset_state.remaining_timesteps)
    rollout_steps = min(requested_steps, remaining_steps)
    if rollout_steps < 1:
        raise RuntimeError("Scenario has no remaining rollout steps.")

    first_started = time.perf_counter()
    first_state, first_hash = _rollout_once(
        scenario, environment, actor, rollout_steps
    )
    first_seconds = time.perf_counter() - first_started

    second_started = time.perf_counter()
    second_state, second_hash = _rollout_once(
        scenario, environment, actor, rollout_steps
    )
    second_seconds = time.perf_counter() - second_started

    metrics_started = time.perf_counter()
    metrics = _metric_summary(environment, second_state)
    metrics_seconds = time.perf_counter() - metrics_started
    deterministic = first_hash == second_hash
    if not deterministic:
        raise RuntimeError("Repeated rollouts produced different trajectory hashes.")

    return {
        "schema_version": 1,
        "status": "passed",
        "dataset": {
            "name": "Waymo Open Motion Dataset",
            "version": DATASET_VERSION,
            "split": split,
            "shard": Path(shard_uri).name,
            "scenario_id": scenario_id,
            "streamed_record_bytes": record_bytes,
        },
        "simulation": {
            "simulator": "Waymax",
            "waymax_version": importlib.metadata.version("waymo-waymax"),
            "waymax_commit": WAYMAX_COMMIT,
            "policy": "expert log-playback for SDC; log playback for uncontrolled objects",
            "dynamics": "StateDynamics",
            "seed": SEED,
            "rollout_steps": rollout_steps,
            "first_trajectory_sha256": first_hash,
            "second_trajectory_sha256": second_hash,
            "outputs_identical": deterministic,
            "final_timestep": int(second_state.timestep),
        },
        "built_in_metrics_at_final_timestep": metrics,
        "performance": {
            "data_load_seconds": round(load_seconds, 6),
            "first_rollout_seconds_including_jit": round(first_seconds, 6),
            "second_rollout_seconds_warm": round(second_seconds, 6),
            "metric_seconds": round(metrics_seconds, 6),
            "total_seconds": round(time.perf_counter() - started, 6),
            "process_peak_rss_bytes": _peak_rss_bytes(),
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "jax": jax.__version__,
            "tensorflow": tf.__version__,
            "jax_backend": jax.default_backend(),
            "jax_devices": [str(device) for device in jax.devices()],
        },
        "publication_note": (
            "This report contains configuration, a permitted identifier, hashes, "
            "and aggregate metrics only; it does not contain raw WOMD records."
        ),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard-uri", default=DEFAULT_SHARD_URI)
    parser.add_argument(
        "--allow-validation-access",
        action="store_true",
        help="Explicitly authorize a validation URI under a separately frozen protocol.",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=80,
        help="Maximum future steps to simulate (default: full 8 seconds).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path. Parent directories are created.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.steps < 1:
        raise SystemExit("--steps must be at least 1")
    report = run(
        args.shard_uri,
        args.steps,
        allow_validation_access=args.allow_validation_access,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
