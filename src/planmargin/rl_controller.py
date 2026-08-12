"""Train and evaluate PlanMargin's frozen JAX longitudinal DQN controller."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import io
import json
import math
import os
import platform
import resource
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, NamedTuple

import jax
import jax.numpy as jnp
import numpy as np
import optax

SCHEMA_VERSION = "1.0.0"
REPORT_SCHEMA_URI = (
    "https://raw.githubusercontent.com/ethanvillalovoz/planmargin/main/"
    "schemas/rl-controller-training-report-v1.schema.json"
)
TRAINING_SEED = 2027
EVALUATION_SEED = 2028
ACTION_ACCELERATIONS = np.asarray(
    [-6.0, -4.0, -2.0, -1.0, 0.0, 1.0, 2.0], dtype=np.float32
)
OBSERVATION_SIZE = 7
HIDDEN_SIZE = 64
DEFAULT_OUTPUT_DIR = Path("artifacts/experiment-v2/controller-qualification")
MAX_CHECKPOINT_BYTES = 2 * 1024 * 1024


class RLControllerError(ValueError):
    """Raised when a controller artifact or frozen invariant is invalid."""


@dataclass(frozen=True)
class TrainingConfig:
    """DQN training constants; the default instance is the frozen protocol."""

    environment_steps: int = 120_000
    parallel_environments: int = 32
    replay_capacity: int = 100_000
    warmup_steps: int = 5_000
    batch_size: int = 256
    gradient_updates_per_collection: int = 4
    target_update_interval: int = 1_000
    epsilon_decay_steps: int = 80_000
    epsilon_start: float = 1.0
    epsilon_end: float = 0.05
    learning_rate: float = 3e-4
    discount: float = 0.99
    horizon: int = 80
    evaluation_episodes: int = 2_048


FROZEN_CONFIG = TrainingConfig()


class Parameters(NamedTuple):
    """Two-hidden-layer DQN parameters with stable serialization order."""

    w1: jax.Array
    b1: jax.Array
    w2: jax.Array
    b2: jax.Array
    w3: jax.Array
    b3: jax.Array


@dataclass
class SurrogateBatch:
    """Vectorized deterministic car-following simulator state."""

    ego_speed: np.ndarray
    lead_speed: np.ndarray
    gap: np.ndarray
    onset: np.ndarray
    lead_deceleration: np.ndarray
    step_index: np.ndarray
    previous_acceleration: np.ndarray
    episode_return: np.ndarray
    episode_distance: np.ndarray


class ReplayBuffer:
    """Bounded preallocated replay memory."""

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.observation = np.empty((capacity, OBSERVATION_SIZE), dtype=np.float32)
        self.action = np.empty(capacity, dtype=np.int32)
        self.reward = np.empty(capacity, dtype=np.float32)
        self.next_observation = np.empty((capacity, OBSERVATION_SIZE), dtype=np.float32)
        self.done = np.empty(capacity, dtype=np.float32)
        self.size = 0
        self.cursor = 0

    def add(
        self,
        observation: np.ndarray,
        action: np.ndarray,
        reward: np.ndarray,
        next_observation: np.ndarray,
        done: np.ndarray,
    ) -> None:
        count = len(observation)
        indices = (np.arange(count) + self.cursor) % self.capacity
        self.observation[indices] = observation
        self.action[indices] = action
        self.reward[indices] = reward
        self.next_observation[indices] = next_observation
        self.done[indices] = done
        self.cursor = (self.cursor + count) % self.capacity
        self.size = min(self.size + count, self.capacity)

    def sample(self, rng: np.random.Generator, size: int) -> tuple[np.ndarray, ...]:
        if self.size < size:
            raise RLControllerError("Replay buffer does not contain a full batch.")
        indices = rng.integers(0, self.size, size=size)
        return (
            self.observation[indices],
            self.action[indices],
            self.reward[indices],
            self.next_observation[indices],
            self.done[indices],
        )


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if os.uname().sysname == "Darwin" else peak * 1024)


def _validate_config(config: TrainingConfig) -> None:
    positive = (
        config.environment_steps,
        config.parallel_environments,
        config.replay_capacity,
        config.warmup_steps,
        config.batch_size,
        config.gradient_updates_per_collection,
        config.target_update_interval,
        config.epsilon_decay_steps,
        config.horizon,
        config.evaluation_episodes,
    )
    if any(value <= 0 for value in positive):
        raise RLControllerError("Every training count must be positive.")
    if config.environment_steps % config.parallel_environments:
        raise RLControllerError("Environment steps must divide parallel environments.")
    if config.replay_capacity < config.batch_size:
        raise RLControllerError("Replay capacity must fit one minibatch.")
    if not (0.0 <= config.epsilon_end <= config.epsilon_start <= 1.0):
        raise RLControllerError("Epsilon schedule is invalid.")
    if not (0.0 < config.learning_rate < 1.0 and 0.0 < config.discount <= 1.0):
        raise RLControllerError("Optimizer constants are invalid.")


def initialize_parameters(seed: int = TRAINING_SEED) -> Parameters:
    """Return deterministic variance-scaled parameters."""
    keys = jax.random.split(jax.random.PRNGKey(seed), 3)

    def weight(key: jax.Array, input_size: int, output_size: int) -> jax.Array:
        return jax.random.normal(
            key, (input_size, output_size), dtype=jnp.float32
        ) * math.sqrt(2.0 / input_size)

    return Parameters(
        weight(keys[0], OBSERVATION_SIZE, HIDDEN_SIZE),
        jnp.zeros(HIDDEN_SIZE, dtype=jnp.float32),
        weight(keys[1], HIDDEN_SIZE, HIDDEN_SIZE),
        jnp.zeros(HIDDEN_SIZE, dtype=jnp.float32),
        weight(keys[2], HIDDEN_SIZE, len(ACTION_ACCELERATIONS)),
        jnp.zeros(len(ACTION_ACCELERATIONS), dtype=jnp.float32),
    )


@jax.jit
def q_values(parameters: Parameters, observation: jax.Array) -> jax.Array:
    hidden = jnp.tanh(observation @ parameters.w1 + parameters.b1)
    hidden = jnp.tanh(hidden @ parameters.w2 + parameters.b2)
    return hidden @ parameters.w3 + parameters.b3


def normalize_observation(raw: np.ndarray | jax.Array) -> np.ndarray | jax.Array:
    """Normalize and clip the seven frozen car-following features."""
    module = jnp if isinstance(raw, jax.Array) else np
    value = module.asarray(raw, dtype=module.float32)
    scaled = module.stack(
        (
            value[..., 0] / 25.0,
            value[..., 1] / 25.0,
            value[..., 2] / 60.0,
            value[..., 3] / 30.0,
            value[..., 4] / 6.0,
            value[..., 5] / 6.0,
            value[..., 6] / 6.0,
        ),
        axis=-1,
    )
    lower = module.asarray([0.0, 0.0, 0.0, -1.0, 0.0, -1.0, -1.0])
    upper = module.asarray([1.2, 1.2, 1.2, 1.0, 1.0, 0.0, 1.0])
    return module.clip(scaled, lower, upper)


def greedy_action_indices(
    parameters: Parameters, observation: np.ndarray
) -> np.ndarray:
    values = np.asarray(q_values(parameters, jnp.asarray(observation)))
    if not np.all(np.isfinite(values)):
        raise RLControllerError("Controller produced non-finite Q-values.")
    return np.argmax(values, axis=-1).astype(np.int32)


def _reset_batch(rng: np.random.Generator, count: int) -> SurrogateBatch:
    return SurrogateBatch(
        ego_speed=rng.uniform(5.0, 25.0, count).astype(np.float32),
        lead_speed=rng.uniform(5.0, 25.0, count).astype(np.float32),
        gap=rng.uniform(10.0, 60.0, count).astype(np.float32),
        onset=rng.uniform(0.0, 4.0, count).astype(np.float32),
        lead_deceleration=rng.uniform(-6.0, 0.0, count).astype(np.float32),
        step_index=np.zeros(count, dtype=np.int32),
        previous_acceleration=np.zeros(count, dtype=np.float32),
        episode_return=np.zeros(count, dtype=np.float32),
        episode_distance=np.zeros(count, dtype=np.float32),
    )


def _raw_observation(batch: SurrogateBatch) -> np.ndarray:
    lead_acceleration = np.where(
        batch.step_index * 0.1 >= batch.onset,
        batch.lead_deceleration,
        0.0,
    )
    relative_speed = batch.lead_speed - batch.ego_speed
    time_headway = batch.gap / np.maximum(batch.ego_speed, 0.1)
    return np.column_stack(
        (
            batch.ego_speed,
            batch.lead_speed,
            batch.gap,
            relative_speed,
            time_headway,
            lead_acceleration,
            batch.previous_acceleration,
        )
    ).astype(np.float32)


def _replace_done(
    batch: SurrogateBatch, replacement: SurrogateBatch, done: np.ndarray
) -> None:
    for field in dataclasses.fields(batch):
        current = getattr(batch, field.name)
        current[done] = getattr(replacement, field.name)[done]


def _step_batch(
    batch: SurrogateBatch,
    action_indices: np.ndarray,
    horizon: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    observation = normalize_observation(_raw_observation(batch))
    acceleration = ACTION_ACCELERATIONS[action_indices]
    lead_acceleration = np.where(
        batch.step_index * 0.1 >= batch.onset,
        batch.lead_deceleration,
        0.0,
    )
    next_lead_speed = np.maximum(batch.lead_speed + lead_acceleration * 0.1, 0.0)
    next_ego_speed = np.clip(batch.ego_speed + acceleration * 0.1, 0.0, 30.0)
    next_gap = (
        batch.gap
        + (
            (batch.lead_speed + next_lead_speed) / 2.0
            - (batch.ego_speed + next_ego_speed) / 2.0
        )
        * 0.1
    )
    headway = batch.gap / np.maximum(batch.ego_speed, 0.1)
    reward = (
        0.10 * batch.ego_speed / 25.0
        - 0.30 * np.maximum(0.0, 1.5 - headway) ** 2
        - 0.002 * acceleration**2
        - 0.001 * (acceleration - batch.previous_acceleration) ** 2
    ).astype(np.float32)
    collision = next_gap <= 0.0
    reward[collision] -= 100.0
    batch.episode_return += reward
    batch.episode_distance += (batch.ego_speed + next_ego_speed) / 2.0 * 0.1
    batch.ego_speed[:] = next_ego_speed
    batch.lead_speed[:] = next_lead_speed
    batch.gap[:] = next_gap
    batch.previous_acceleration[:] = acceleration
    batch.step_index += 1
    done = collision | (batch.step_index >= horizon)
    next_observation = normalize_observation(_raw_observation(batch))
    return observation, reward, next_observation, done, collision


def _update_factory(config: TrainingConfig) -> Callable[..., tuple[Any, ...]]:
    optimizer = optax.adam(config.learning_rate)

    @jax.jit
    def update(
        parameters: Parameters,
        target: Parameters,
        optimizer_state: optax.OptState,
        observation: jax.Array,
        action: jax.Array,
        reward: jax.Array,
        next_observation: jax.Array,
        done: jax.Array,
    ) -> tuple[Parameters, optax.OptState, jax.Array]:
        next_action = jnp.argmax(q_values(parameters, next_observation), axis=-1)
        next_target = jnp.take_along_axis(
            q_values(target, next_observation), next_action[:, None], axis=-1
        )[:, 0]
        target_value = reward + config.discount * (1.0 - done) * next_target

        def loss_function(candidate: Parameters) -> jax.Array:
            predicted = jnp.take_along_axis(
                q_values(candidate, observation), action[:, None], axis=-1
            )[:, 0]
            return jnp.mean(optax.huber_loss(predicted, target_value, delta=1.0))

        loss, gradients = jax.value_and_grad(loss_function)(parameters)
        updates, optimizer_state = optimizer.update(
            gradients, optimizer_state, parameters
        )
        return optax.apply_updates(parameters, updates), optimizer_state, loss

    return update


def train(
    config: TrainingConfig = FROZEN_CONFIG,
    *,
    seed: int = TRAINING_SEED,
) -> tuple[Parameters, dict[str, Any]]:
    """Train the fixed DQN and return parameters plus aggregate diagnostics."""
    _validate_config(config)
    started = time.monotonic()
    rng = np.random.default_rng(seed)
    parameters = initialize_parameters(seed)
    initial_parameters = parameters
    target = parameters
    optimizer = optax.adam(config.learning_rate)
    optimizer_state = optimizer.init(parameters)
    update = _update_factory(config)
    replay = ReplayBuffer(config.replay_capacity)
    batch = _reset_batch(rng, config.parallel_environments)
    collections = config.environment_steps // config.parallel_environments
    optimizer_steps = 0
    completed_episodes = 0
    collision_episodes = 0
    recent_losses: list[float] = []
    for collection in range(collections):
        environment_step = collection * config.parallel_environments
        epsilon_progress = min(environment_step / config.epsilon_decay_steps, 1.0)
        epsilon = config.epsilon_start + epsilon_progress * (
            config.epsilon_end - config.epsilon_start
        )
        observation = normalize_observation(_raw_observation(batch))
        greedy = greedy_action_indices(parameters, observation)
        random_actions = rng.integers(
            0, len(ACTION_ACCELERATIONS), size=config.parallel_environments
        )
        explore = rng.random(config.parallel_environments) < epsilon
        action = np.where(explore, random_actions, greedy).astype(np.int32)
        current, reward, next_observation, done, collision = _step_batch(
            batch, action, config.horizon
        )
        replay.add(current, action, reward, next_observation, done)
        if np.any(done):
            completed_episodes += int(done.sum())
            collision_episodes += int(collision.sum())
            replacement = _reset_batch(rng, config.parallel_environments)
            _replace_done(batch, replacement, done)
        if replay.size >= max(config.warmup_steps, config.batch_size):
            for _ in range(config.gradient_updates_per_collection):
                sample = replay.sample(rng, config.batch_size)
                parameters, optimizer_state, loss = update(
                    parameters,
                    target,
                    optimizer_state,
                    *(jnp.asarray(value) for value in sample),
                )
                optimizer_steps += 1
                recent_losses.append(float(loss))
                if len(recent_losses) > 100:
                    del recent_losses[0]
                if optimizer_steps % config.target_update_interval == 0:
                    target = parameters
    jax.block_until_ready(parameters.w3)
    diagnostics = {
        "environment_steps": config.environment_steps,
        "optimizer_steps": optimizer_steps,
        "completed_training_episodes": completed_episodes,
        "training_collision_episodes": collision_episodes,
        "final_epsilon": config.epsilon_end,
        "mean_last_100_huber_loss": float(np.mean(recent_losses)),
        "runtime_seconds": time.monotonic() - started,
        "peak_rss_bytes": _peak_rss_bytes(),
        "initial_parameter_fingerprint": parameter_fingerprint(initial_parameters),
    }
    return parameters, diagnostics


def _evaluate_policy(
    policy: Callable[[np.ndarray], np.ndarray],
    *,
    episodes: int,
    seed: int,
    horizon: int,
) -> dict[str, float | int]:
    rng = np.random.default_rng(seed)
    batch = _reset_batch(rng, episodes)
    completed_return = np.zeros(episodes, dtype=np.float64)
    completed_distance = np.zeros(episodes, dtype=np.float64)
    collided = np.zeros(episodes, dtype=bool)
    active = np.ones(episodes, dtype=bool)
    for _ in range(horizon):
        if not np.any(active):
            break
        actions = policy(_raw_observation(batch))
        if (
            actions.shape != (episodes,)
            or np.any(actions < 0)
            or np.any(actions >= len(ACTION_ACCELERATIONS))
        ):
            raise RLControllerError(
                "Evaluation policy returned invalid action indices."
            )
        before = {
            field.name: getattr(batch, field.name).copy()
            for field in dataclasses.fields(batch)
        }
        _, _, _, done, collision = _step_batch(batch, actions, horizon)
        for name, value in before.items():
            getattr(batch, name)[~active] = value[~active]
        newly_done = done & active
        completed_return[newly_done] = batch.episode_return[newly_done]
        completed_distance[newly_done] = batch.episode_distance[newly_done]
        collided |= collision & active
        active &= ~done
    return {
        "episode_count": episodes,
        "collision_count": int(collided.sum()),
        "collision_rate": float(np.mean(collided)),
        "mean_return": float(np.mean(completed_return)),
        "mean_distance_m": float(np.mean(completed_distance)),
    }


def evaluate(
    parameters: Parameters,
    config: TrainingConfig = FROZEN_CONFIG,
) -> dict[str, Any]:
    """Compare the trained policy with both predeclared synthetic baselines."""

    def learned(raw: np.ndarray) -> np.ndarray:
        return greedy_action_indices(parameters, normalize_observation(raw))

    initial = initialize_parameters(TRAINING_SEED)

    def untrained(raw: np.ndarray) -> np.ndarray:
        return greedy_action_indices(initial, normalize_observation(raw))

    def emergency(raw: np.ndarray) -> np.ndarray:
        headway = raw[:, 4]
        closing_speed = np.maximum(-raw[:, 3], 0.0)
        time_to_collision = raw[:, 2] / np.maximum(closing_speed, 1e-3)
        acceleration = np.where((headway < 1.5) | (time_to_collision < 3.0), -6.0, 1.0)
        return np.searchsorted(ACTION_ACCELERATIONS, acceleration).astype(np.int32)

    arguments = {
        "episodes": config.evaluation_episodes,
        "seed": EVALUATION_SEED,
        "horizon": config.horizon,
    }
    return {
        "learned": _evaluate_policy(learned, **arguments),
        "untrained": _evaluate_policy(untrained, **arguments),
        "emergency_braking": _evaluate_policy(emergency, **arguments),
    }


def _arrays(parameters: Parameters) -> tuple[tuple[str, np.ndarray], ...]:
    return tuple(
        (name, np.asarray(getattr(parameters, name), dtype="<f4"))
        for name in Parameters._fields
    )


def parameter_fingerprint(parameters: Parameters) -> str:
    digest = hashlib.sha256()
    for name, value in _arrays(parameters):
        digest.update(name.encode("ascii") + b"\0")
        digest.update(np.asarray(value.shape, dtype="<i8").tobytes())
        digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def serialize_checkpoint(parameters: Parameters) -> bytes:
    """Serialize a checkpoint as a deterministic, timestamp-free ZIP."""
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "planmargin.jax_dqn_longitudinal_controller",
        "architecture": [
            OBSERVATION_SIZE,
            HIDDEN_SIZE,
            HIDDEN_SIZE,
            len(ACTION_ACCELERATIONS),
        ],
        "actions_mps2": ACTION_ACCELERATIONS.tolist(),
        "parameter_fingerprint": parameter_fingerprint(parameters),
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        entries: list[tuple[str, bytes]] = [
            ("metadata.json", _canonical_json(metadata))
        ]
        for name, value in _arrays(parameters):
            stream = io.BytesIO()
            np.save(stream, value, allow_pickle=False)
            entries.append((f"{name}.npy", stream.getvalue()))
        for name, value in entries:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o600 << 16
            archive.writestr(info, value)
    payload = output.getvalue()
    if len(payload) > MAX_CHECKPOINT_BYTES:
        raise RLControllerError("Controller checkpoint exceeds its frozen bound.")
    return payload


def load_checkpoint(payload: bytes) -> Parameters:
    """Load and fully validate a deterministic controller checkpoint."""
    if len(payload) > MAX_CHECKPOINT_BYTES:
        raise RLControllerError("Controller checkpoint exceeds its frozen bound.")
    expected_shapes = {
        "w1": (OBSERVATION_SIZE, HIDDEN_SIZE),
        "b1": (HIDDEN_SIZE,),
        "w2": (HIDDEN_SIZE, HIDDEN_SIZE),
        "b2": (HIDDEN_SIZE,),
        "w3": (HIDDEN_SIZE, len(ACTION_ACCELERATIONS)),
        "b3": (len(ACTION_ACCELERATIONS),),
    }
    try:
        with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
            expected_names = {"metadata.json"} | {
                f"{name}.npy" for name in expected_shapes
            }
            if set(archive.namelist()) != expected_names:
                raise RLControllerError("Checkpoint entries do not match the model.")
            metadata = json.loads(archive.read("metadata.json"))
            values = {
                name: np.load(
                    io.BytesIO(archive.read(f"{name}.npy")), allow_pickle=False
                )
                for name in expected_shapes
            }
    except (zipfile.BadZipFile, OSError, ValueError, json.JSONDecodeError) as error:
        if isinstance(error, RLControllerError):
            raise
        raise RLControllerError("Controller checkpoint is unreadable.") from error
    for name, shape in expected_shapes.items():
        value = values[name]
        if (
            value.shape != shape
            or value.dtype != np.dtype("float32")
            or not np.all(np.isfinite(value))
        ):
            raise RLControllerError(f"Controller parameter {name} is invalid.")
    parameters = Parameters(*(jnp.asarray(values[name]) for name in Parameters._fields))
    expected_metadata = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "planmargin.jax_dqn_longitudinal_controller",
        "architecture": [
            OBSERVATION_SIZE,
            HIDDEN_SIZE,
            HIDDEN_SIZE,
            len(ACTION_ACCELERATIONS),
        ],
        "actions_mps2": ACTION_ACCELERATIONS.tolist(),
        "parameter_fingerprint": parameter_fingerprint(parameters),
    }
    if metadata != expected_metadata:
        raise RLControllerError("Controller checkpoint metadata mismatch.")
    return parameters


def _output_dir(path: Path) -> Path:
    artifacts = (Path.cwd() / "artifacts").resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(artifacts):
        raise RLControllerError("Controller outputs must remain under artifacts/.")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _atomic_write(path: Path, payload: bytes) -> None:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def run_training(
    output_dir: Path = DEFAULT_OUTPUT_DIR, *, replace: bool = False
) -> dict[str, Any]:
    """Train twice, enforce determinism, and publish the private Phase-1 artifact."""
    output = _output_dir(output_dir)
    targets = (output / "controller.pmzip", output / "training-report.json")
    if not replace and any(path.exists() for path in targets):
        raise FileExistsError("Controller outputs exist; pass replace=True to rerun.")
    first, first_training = train()
    second, second_training = train()
    first_checkpoint = serialize_checkpoint(first)
    second_checkpoint = serialize_checkpoint(second)
    deterministic = first_checkpoint == second_checkpoint
    evaluation = evaluate(first)
    learned = evaluation["learned"]
    emergency = evaluation["emergency_braking"]
    untrained = evaluation["untrained"]
    gates = {
        "deterministic_training": deterministic,
        "free_local_compute": first_training["runtime_seconds"] <= 900.0
        and second_training["runtime_seconds"] <= 900.0
        and max(first_training["peak_rss_bytes"], second_training["peak_rss_bytes"])
        <= 8 * 1024**3,
        "synthetic_safety": learned["collision_rate"] <= 0.01
        and learned["collision_rate"] <= emergency["collision_rate"] + 0.0025,
        "synthetic_progress": learned["mean_distance_m"]
        >= 0.80 * emergency["mean_distance_m"]
        and learned["mean_return"] >= untrained["mean_return"] + 5.0,
    }
    report = {
        "$schema": REPORT_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": "planmargin.rl_controller_training_report",
        "status": "synthetic_go" if all(gates.values()) else "synthetic_no_go",
        "held_out_opened": False,
        "training_seed": TRAINING_SEED,
        "evaluation_seed": EVALUATION_SEED,
        "configuration": dataclasses.asdict(FROZEN_CONFIG),
        "provenance": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "jax": jax.__version__,
            "jax_backend": jax.default_backend(),
            "optax": optax.__version__,
            "controller_source_sha256": _file_sha256(Path(__file__)),
            "protocol_sha256": _file_sha256(
                Path("docs/decisions/0006-experiment-v2-protocol.md")
            ),
        },
        "checkpoint_sha256": _sha256(first_checkpoint),
        "parameter_fingerprint": parameter_fingerprint(first),
        "checkpoint_bytes": len(first_checkpoint),
        "first_training": first_training,
        "second_training": second_training,
        "evaluation": evaluation,
        "gates": gates,
    }
    report["report_sha256"] = _sha256(_canonical_json(report))
    _atomic_write(output / "controller.pmzip", first_checkpoint)
    _atomic_write(
        output / "training-report.json",
        json.dumps(report, allow_nan=False, indent=2, sort_keys=True).encode() + b"\n",
    )
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)
    report = run_training(args.output_dir, replace=args.replace)
    print(
        json.dumps(
            {"status": report["status"], "gates": report["gates"]}, sort_keys=True
        )
    )


if __name__ == "__main__":
    main()
