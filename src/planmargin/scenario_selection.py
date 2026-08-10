"""Mine and validate a deterministic ten-scenario WOMD feasibility set."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import os
import platform
import resource
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import jax
import numpy as np
import tensorflow as tf
from waymax import agents
from waymax import config as waymax_config
from waymax import dynamics
from waymax import env
from waymax.dataloader import womd_dataloader
from waymax.dataloader import womd_factories
from waymax.metrics import overlap
from waymax.metrics import roadgraph

DATASET_VERSION = "1.3.1"
SPLIT = "training"
NUM_OBJECTS = 128
NUM_FUTURE_STEPS = 80
NUM_TRAJECTORY_STEPS = NUM_FUTURE_STEPS + 1
TOTAL_TRAINING_SHARDS = 1_000
SEED = 0
WAYMAX_GIT_COMMIT = "a64dfec9be8576b60d9cecc94f406d9812d4a7d0"


@dataclass(frozen=True)
class SelectionThresholds:
    """Explicit geometric and behavioral thresholds for candidate mining."""

    # Preferred family: SDC left turn with a geometrically conflicting vehicle.
    min_left_turn_deg: float = 40.0
    max_left_turn_deg: float = 140.0
    min_sdc_turn_travel_m: float = 10.0
    min_turn_valid_steps: int = 41
    min_oncoming_heading_opposition_deg: float = 125.0
    min_oncoming_travel_m: float = 8.0
    min_interaction_valid_steps: int = 20
    max_path_conflict_distance_m: float = 5.0
    max_conflict_time_gap_s: float = 4.0
    max_synchronized_distance_m: float = 20.0

    # Fallback family: a same-route lead vehicle with sustained braking.
    min_sdc_speed_mps: float = 1.0
    min_initial_gap_m: float = 5.0
    max_initial_gap_m: float = 60.0
    max_initial_lateral_offset_m: float = 4.0
    max_heading_delta_deg: float = 35.0
    min_joint_valid_steps_first_5s: int = 40
    max_route_distance_m: float = 2.5
    min_lead_path_step_ahead: int = 3
    route_alignment_steps: int = 20
    min_braking_accel_mps2: float = -1.0
    min_total_speed_drop_mps: float = 2.0
    min_one_second_speed_drop_mps: float = 1.0
    braking_window_steps: int = 61
    min_braking_valid_steps: int = 30
    one_second_steps: int = 10
    max_abs_accel_mps2: float = 12.0
    max_abs_jerk_mps3: float = 100.0
    max_braking_step_speed_increase_mps: float = 0.2
    min_braking_nonincrease_fraction: float = 0.8


@dataclass(frozen=True)
class ScenarioArrays:
    """Small trajectory-only view extracted from one WOMD TFExample."""

    scenario_id: str
    object_types: np.ndarray
    is_sdc: np.ndarray
    objects_of_interest: np.ndarray
    x: np.ndarray
    y: np.ndarray
    yaw: np.ndarray
    valid: np.ndarray
    vel_x: np.ndarray
    vel_y: np.ndarray

    @property
    def speed(self) -> np.ndarray:
        return np.hypot(self.vel_x, self.vel_y)


@dataclass(frozen=True)
class Candidate:
    """One mined interaction candidate without raw WOMD content."""

    family: str
    scenario_id: str
    shard_index: int
    record_index: int
    sdc_object_index: int
    interacting_object_index: int
    score: float
    features: dict[str, float | bool | int]


@dataclass(frozen=True)
class MinedRecord:
    """In-memory candidate plus its serialized source record."""

    candidate: Candidate
    serialized: bytes


@dataclass(frozen=True)
class ShardScan:
    """Candidate pools and accounting from one source shard."""

    left_turns: tuple[MinedRecord, ...]
    lead_braking: tuple[MinedRecord, ...]
    records_scanned: int
    record_bytes_processed: int


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def _git_provenance() -> dict[str, str | bool | None]:
    """Return best-effort source provenance without making Git a runtime need."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        commit = None
        dirty = None
    return {"git_commit": commit, "git_worktree_dirty": dirty}


def _wrap_angle_radians(angle: float | np.ndarray) -> float | np.ndarray:
    return (angle + np.pi) % (2 * np.pi) - np.pi


def _feature_values(example: tf.train.Example, key: str) -> np.ndarray:
    feature = example.features.feature[key]
    kind = feature.WhichOneof("kind")
    if kind == "float_list":
        return np.asarray(feature.float_list.value, dtype=np.float32)
    if kind == "int64_list":
        return np.asarray(feature.int64_list.value, dtype=np.int64)
    raise ValueError(f"WOMD feature {key!r} has unsupported kind {kind!r}.")


def _set_flag(values: np.ndarray) -> np.ndarray:
    """Treat only WOMD's explicit value 1 as true; padding may be -1."""
    return np.asarray(values) == 1


def _trajectory_feature(example: tf.train.Example, name: str) -> np.ndarray:
    current = _feature_values(example, f"state/current/{name}").reshape(
        NUM_OBJECTS, 1
    )
    future = _feature_values(example, f"state/future/{name}").reshape(
        NUM_OBJECTS, NUM_FUTURE_STEPS
    )
    return np.concatenate([current, future], axis=1)


def _scenario_arrays(serialized: bytes) -> ScenarioArrays:
    example = tf.train.Example.FromString(serialized)
    scenario_ids = example.features.feature["scenario/id"].bytes_list.value
    if not scenario_ids:
        raise ValueError("WOMD record has no scenario/id.")
    arrays = ScenarioArrays(
        scenario_id=scenario_ids[0].decode("utf-8"),
        object_types=_feature_values(example, "state/type").astype(np.int32),
        is_sdc=_set_flag(_feature_values(example, "state/is_sdc")),
        objects_of_interest=_set_flag(
            _feature_values(example, "state/objects_of_interest")
        ),
        x=_trajectory_feature(example, "x"),
        y=_trajectory_feature(example, "y"),
        yaw=_trajectory_feature(example, "bbox_yaw"),
        valid=_set_flag(_trajectory_feature(example, "valid")),
        vel_x=_trajectory_feature(example, "velocity_x"),
        vel_y=_trajectory_feature(example, "velocity_y"),
    )
    if arrays.is_sdc.sum() != 1:
        raise ValueError(
            f"Expected one SDC in {arrays.scenario_id}, found {arrays.is_sdc.sum()}."
        )
    return arrays


def _path_travel_m(xy: np.ndarray) -> float:
    if len(xy) < 2:
        return 0.0
    return float(np.linalg.norm(np.diff(xy, axis=0), axis=1).sum())


def _braking_features(
    speed: np.ndarray,
    valid: np.ndarray,
    thresholds: SelectionThresholds,
) -> dict[str, float] | None:
    """Return bounded, sustained-braking features or reject the speed trace."""
    window_steps = thresholds.braking_window_steps
    if window_steps > len(speed) or window_steps > len(valid):
        return None

    window_valid = valid[:window_steps]
    braking_steps = np.flatnonzero(window_valid)
    if len(braking_steps) < thresholds.min_braking_valid_steps:
        return None

    window_speed = speed[:window_steps]
    valid_speed = window_speed[braking_steps]
    step_deltas = np.diff(braking_steps)
    step_seconds = 0.1 * step_deltas
    acceleration = np.diff(valid_speed) / step_seconds
    if len(acceleration) < 2:
        return None
    acceleration_seconds = 0.5 * (step_seconds[:-1] + step_seconds[1:])
    jerk = np.diff(acceleration) / acceleration_seconds

    min_accel_mps2 = float(np.min(acceleration))
    max_abs_accel_mps2 = float(np.max(np.abs(acceleration)))
    max_abs_jerk_mps3 = float(np.max(np.abs(jerk)))
    max_total_speed_drop_mps = float(
        np.max(np.maximum.accumulate(valid_speed) - valid_speed)
    )

    exact_windows: list[tuple[float, float, float]] = []
    window_width = thresholds.one_second_steps
    for start in range(window_steps - window_width):
        stop = start + window_width
        if not window_valid[start : stop + 1].all():
            continue
        speed_deltas = np.diff(window_speed[start : stop + 1])
        speed_drop = float(window_speed[start] - window_speed[stop])
        nonincrease_fraction = float(
            np.mean(
                speed_deltas
                <= thresholds.max_braking_step_speed_increase_mps
            )
        )
        max_speed_increase = float(np.max(speed_deltas))
        exact_windows.append(
            (speed_drop, nonincrease_fraction, max_speed_increase)
        )
    if not exact_windows:
        return None

    best_drop, nonincrease_fraction, max_speed_increase = max(
        exact_windows,
        key=lambda item: (item[0], item[1], -item[2]),
    )
    if (
        min_accel_mps2 > thresholds.min_braking_accel_mps2
        or max_total_speed_drop_mps < thresholds.min_total_speed_drop_mps
        or best_drop < thresholds.min_one_second_speed_drop_mps
        or max_abs_accel_mps2 > thresholds.max_abs_accel_mps2
        or max_abs_jerk_mps3 > thresholds.max_abs_jerk_mps3
        or nonincrease_fraction
        < thresholds.min_braking_nonincrease_fraction
    ):
        return None

    return {
        "min_lead_accel_mps2": round(min_accel_mps2, 6),
        "max_abs_lead_accel_mps2": round(max_abs_accel_mps2, 6),
        "max_abs_lead_jerk_mps3": round(max_abs_jerk_mps3, 6),
        "max_total_speed_drop_mps": round(max_total_speed_drop_mps, 6),
        "max_one_second_speed_drop_mps": round(best_drop, 6),
        "braking_nonincrease_fraction": round(nonincrease_fraction, 6),
        "max_braking_step_speed_increase_mps": round(
            max_speed_increase, 6
        ),
    }


def _left_turn_candidate(
    arrays: ScenarioArrays,
    shard_index: int,
    record_index: int,
    thresholds: SelectionThresholds,
) -> Candidate | None:
    sdc_index = int(np.flatnonzero(arrays.is_sdc)[0])
    sdc_valid_steps = np.flatnonzero(arrays.valid[sdc_index])
    if (
        len(sdc_valid_steps) < thresholds.min_turn_valid_steps
        or sdc_valid_steps[0] != 0
    ):
        return None

    sdc_yaw = np.unwrap(arrays.yaw[sdc_index, sdc_valid_steps])
    turn_deg = math.degrees(float(sdc_yaw[-1] - sdc_yaw[0]))
    sdc_xy = np.column_stack(
        (
            arrays.x[sdc_index, sdc_valid_steps],
            arrays.y[sdc_index, sdc_valid_steps],
        )
    )
    sdc_travel_m = _path_travel_m(sdc_xy)
    if not (
        thresholds.min_left_turn_deg
        <= turn_deg
        <= thresholds.max_left_turn_deg
        and sdc_travel_m >= thresholds.min_sdc_turn_travel_m
    ):
        return None

    best: Candidate | None = None
    for other_index in range(len(arrays.object_types)):
        if (
            other_index == sdc_index
            or arrays.object_types[other_index] != 1
            or not arrays.valid[other_index, 0]
        ):
            continue
        other_valid_steps = np.flatnonzero(arrays.valid[other_index])
        joint_valid = arrays.valid[sdc_index] & arrays.valid[other_index]
        if (
            len(other_valid_steps) < thresholds.min_interaction_valid_steps
            or int(joint_valid.sum()) < thresholds.min_interaction_valid_steps
        ):
            continue

        heading_opposition_deg = abs(
            math.degrees(
                float(
                    _wrap_angle_radians(
                        arrays.yaw[other_index, 0]
                        - arrays.yaw[sdc_index, 0]
                    )
                )
            )
        )
        if (
            heading_opposition_deg
            < thresholds.min_oncoming_heading_opposition_deg
        ):
            continue

        other_xy = np.column_stack(
            (
                arrays.x[other_index, other_valid_steps],
                arrays.y[other_index, other_valid_steps],
            )
        )
        other_travel_m = _path_travel_m(other_xy)
        if other_travel_m < thresholds.min_oncoming_travel_m:
            continue

        # A two-step stride is sufficient for the 5 m conflict threshold and
        # keeps the all-pairs path comparison inexpensive.
        sdc_sample = sdc_xy[::2]
        other_sample = other_xy[::2]
        pairwise = np.linalg.norm(
            sdc_sample[:, None, :] - other_sample[None, :, :], axis=2
        )
        sdc_path_index, other_path_index = np.unravel_index(
            int(np.argmin(pairwise)), pairwise.shape
        )
        path_conflict_distance_m = float(
            pairwise[sdc_path_index, other_path_index]
        )
        conflict_time_gap_s = (
            abs(
                int(sdc_valid_steps[::2][sdc_path_index])
                - int(other_valid_steps[::2][other_path_index])
            )
            * 0.1
        )
        synchronized_distance = np.hypot(
            arrays.x[sdc_index, joint_valid]
            - arrays.x[other_index, joint_valid],
            arrays.y[sdc_index, joint_valid]
            - arrays.y[other_index, joint_valid],
        )
        synchronized_min_distance_m = float(np.min(synchronized_distance))
        if (
            path_conflict_distance_m
            > thresholds.max_path_conflict_distance_m
            or conflict_time_gap_s > thresholds.max_conflict_time_gap_s
            or synchronized_min_distance_m
            > thresholds.max_synchronized_distance_m
        ):
            continue

        both_objects_of_interest = bool(
            arrays.objects_of_interest[sdc_index]
            and arrays.objects_of_interest[other_index]
        )
        score = (
            path_conflict_distance_m
            + 0.5 * conflict_time_gap_s
            + 0.05 * synchronized_min_distance_m
            - (2.0 if both_objects_of_interest else 0.0)
        )
        candidate = Candidate(
            family="left_turn_oncoming",
            scenario_id=arrays.scenario_id,
            shard_index=shard_index,
            record_index=record_index,
            sdc_object_index=sdc_index,
            interacting_object_index=other_index,
            score=round(score, 6),
            features={
                "sdc_turn_deg": round(turn_deg, 6),
                "sdc_travel_m": round(sdc_travel_m, 6),
                "heading_opposition_deg": round(
                    heading_opposition_deg, 6
                ),
                "path_conflict_distance_m": round(
                    path_conflict_distance_m, 6
                ),
                "conflict_time_gap_s": round(conflict_time_gap_s, 6),
                "synchronized_min_distance_m": round(
                    synchronized_min_distance_m, 6
                ),
                "sdc_is_womd_object_of_interest": bool(
                    arrays.objects_of_interest[sdc_index]
                ),
                "interacting_is_womd_object_of_interest": bool(
                    arrays.objects_of_interest[other_index]
                ),
            },
        )
        if best is None or (candidate.score, candidate.interacting_object_index) < (
            best.score,
            best.interacting_object_index,
        ):
            best = candidate
    return best


def _lead_braking_candidate(
    arrays: ScenarioArrays,
    shard_index: int,
    record_index: int,
    thresholds: SelectionThresholds,
) -> Candidate | None:
    sdc_index = int(np.flatnonzero(arrays.is_sdc)[0])
    speed = arrays.speed
    if (
        not arrays.valid[sdc_index, 0]
        or speed[sdc_index, 0] < thresholds.min_sdc_speed_mps
        or int(arrays.valid[sdc_index, :51].sum())
        < thresholds.min_joint_valid_steps_first_5s
    ):
        return None

    sdc_valid_steps = np.flatnonzero(arrays.valid[sdc_index])
    sdc_xy = np.column_stack(
        (
            arrays.x[sdc_index, sdc_valid_steps],
            arrays.y[sdc_index, sdc_valid_steps],
        )
    )
    sdc_heading = float(arrays.yaw[sdc_index, 0])
    forward = np.array([math.cos(sdc_heading), math.sin(sdc_heading)])
    left = np.array([-forward[1], forward[0]])

    best: Candidate | None = None
    for lead_index in range(len(arrays.object_types)):
        if (
            lead_index == sdc_index
            or arrays.object_types[lead_index] != 1
            or not arrays.valid[lead_index, 0]
        ):
            continue
        joint_first_5s = (
            arrays.valid[sdc_index, :51] & arrays.valid[lead_index, :51]
        )
        if (
            int(joint_first_5s.sum())
            < thresholds.min_joint_valid_steps_first_5s
        ):
            continue

        relative_xy = np.array(
            [
                arrays.x[lead_index, 0] - arrays.x[sdc_index, 0],
                arrays.y[lead_index, 0] - arrays.y[sdc_index, 0],
            ]
        )
        initial_gap_m = float(relative_xy @ forward)
        initial_lateral_offset_m = float(relative_xy @ left)
        heading_delta_deg = abs(
            math.degrees(
                float(
                    _wrap_angle_radians(
                        arrays.yaw[lead_index, 0]
                        - arrays.yaw[sdc_index, 0]
                    )
                )
            )
        )
        if not (
            thresholds.min_initial_gap_m
            <= initial_gap_m
            <= thresholds.max_initial_gap_m
            and abs(initial_lateral_offset_m)
            <= thresholds.max_initial_lateral_offset_m
            and heading_delta_deg <= thresholds.max_heading_delta_deg
        ):
            continue

        lead_valid_steps = np.flatnonzero(arrays.valid[lead_index])
        lead_xy = np.column_stack(
            (
                arrays.x[lead_index, lead_valid_steps],
                arrays.y[lead_index, lead_valid_steps],
            )
        )
        route_distances = np.linalg.norm(
            lead_xy[:, None, :] - sdc_xy[None, :, :], axis=2
        )
        nearest_route_distance = route_distances.min(axis=1)
        nearest_route_indices = route_distances.argmin(axis=1)
        route_steps = min(
            thresholds.route_alignment_steps, len(nearest_route_distance)
        )
        current_route_distance_m = float(nearest_route_distance[0])
        median_route_distance_m = float(
            np.median(nearest_route_distance[:route_steps])
        )
        lead_path_step_ahead = int(
            sdc_valid_steps[nearest_route_indices[0]]
        )
        if (
            current_route_distance_m > thresholds.max_route_distance_m
            or median_route_distance_m > thresholds.max_route_distance_m
            or lead_path_step_ahead < thresholds.min_lead_path_step_ahead
        ):
            continue

        braking_features = _braking_features(
            speed[lead_index], arrays.valid[lead_index], thresholds
        )
        if braking_features is None:
            continue

        score = (
            initial_gap_m
            + 2.0 * abs(initial_lateral_offset_m)
            + heading_delta_deg / 10.0
            + current_route_distance_m
            + median_route_distance_m
            - braking_features["max_total_speed_drop_mps"]
        )
        candidate = Candidate(
            family="lead_vehicle_braking",
            scenario_id=arrays.scenario_id,
            shard_index=shard_index,
            record_index=record_index,
            sdc_object_index=sdc_index,
            interacting_object_index=lead_index,
            score=round(score, 6),
            features={
                "initial_gap_m": round(initial_gap_m, 6),
                "initial_lateral_offset_m": round(
                    initial_lateral_offset_m, 6
                ),
                "heading_delta_deg": round(heading_delta_deg, 6),
                "current_route_distance_m": round(
                    current_route_distance_m, 6
                ),
                "median_route_distance_m": round(
                    median_route_distance_m, 6
                ),
                "lead_path_step_ahead": lead_path_step_ahead,
                "sdc_initial_speed_mps": round(
                    float(speed[sdc_index, 0]), 6
                ),
                "lead_initial_speed_mps": round(
                    float(speed[lead_index, 0]), 6
                ),
                **braking_features,
                "sdc_is_womd_object_of_interest": bool(
                    arrays.objects_of_interest[sdc_index]
                ),
                "interacting_is_womd_object_of_interest": bool(
                    arrays.objects_of_interest[lead_index]
                ),
            },
        )
        if best is None or (candidate.score, candidate.interacting_object_index) < (
            best.score,
            best.interacting_object_index,
        ):
            best = candidate
    return best


def _training_shard_uri(shard_index: int) -> str:
    return (
        "gs://waymo_open_dataset_motion_v_1_3_1/uncompressed/tf_example/"
        f"training/training_tfexample.tfrecord-{shard_index:05d}-of-01000"
    )


def _scan_shard(
    shard_index: int,
    thresholds: SelectionThresholds,
    families: Iterable[str],
) -> ShardScan:
    family_set = set(families)
    left_turns: list[MinedRecord] = []
    lead_braking: list[MinedRecord] = []
    record_count = 0
    record_bytes = 0
    uri = _training_shard_uri(shard_index)
    dataset = tf.data.TFRecordDataset([uri], buffer_size=8 * 1024 * 1024)
    for record_index, serialized_tensor in enumerate(dataset):
        serialized = serialized_tensor.numpy()
        record_count += 1
        record_bytes += len(serialized)
        try:
            arrays = _scenario_arrays(serialized)
        except ValueError as error:
            print(
                f"Skipping shard {shard_index} record {record_index}: {error}",
                file=sys.stderr,
                flush=True,
            )
            continue
        if "left_turn_oncoming" in family_set:
            candidate = _left_turn_candidate(
                arrays, shard_index, record_index, thresholds
            )
            if candidate is not None:
                left_turns.append(MinedRecord(candidate, serialized))
        if "lead_vehicle_braking" in family_set:
            candidate = _lead_braking_candidate(
                arrays, shard_index, record_index, thresholds
            )
            if candidate is not None:
                lead_braking.append(MinedRecord(candidate, serialized))
        if record_count % 100 == 0:
            print(
                f"shard={shard_index:05d} records={record_count} "
                f"left={len(left_turns)} lead={len(lead_braking)}",
                file=sys.stderr,
                flush=True,
            )
    return ShardScan(
        left_turns=tuple(left_turns),
        lead_braking=tuple(lead_braking),
        records_scanned=record_count,
        record_bytes_processed=record_bytes,
    )


def _waymax_scenario(serialized: bytes) -> Any:
    dataset_config = dataclasses.replace(
        waymax_config.WOD_1_3_1_TRAINING,
        repeat=1,
        batch_dims=(),
        shuffle_seed=None,
        num_shards=1,
        deterministic=True,
        include_sdc_paths=False,
        num_paths=None,
        num_points_per_path=None,
        max_num_objects=NUM_OBJECTS,
    )
    serialized_tensor = tf.convert_to_tensor(serialized, dtype=tf.string)
    parsed = womd_dataloader.preprocess_serialized_womd_data(
        serialized_tensor, dataset_config
    )
    return womd_factories.simulator_state_from_womd_dict(
        parsed, include_sdc_paths=False
    )


def _update_trajectory_hash(digest: Any, state: Any) -> None:
    for leaf in jax.tree_util.tree_leaves(state.sim_trajectory):
        array = np.ascontiguousarray(np.asarray(leaf))
        digest.update(str(array.dtype).encode())
        digest.update(str(array.shape).encode())
        digest.update(array.tobytes())


class BaselineValidator:
    """Validate the unmodified IDM baseline with reusable JIT functions."""

    def __init__(self) -> None:
        dynamics_model = dynamics.StateDynamics()
        self._environment = env.BaseEnvironment(
            dynamics_model=dynamics_model,
            config=dataclasses.replace(
                waymax_config.EnvironmentConfig(),
                max_num_objects=NUM_OBJECTS,
                controlled_object=waymax_config.ObjectType.SDC,
                compute_reward=False,
            ),
        )
        self._actor = agents.IDMRoutePolicy(
            is_controlled_func=lambda state: state.object_metadata.is_sdc
        )
        self._step = jax.jit(self._environment.step)
        self._select_action = jax.jit(self._actor.select_action)
        self._overlap = jax.jit(overlap.OverlapMetric().compute)
        self._offroad = jax.jit(roadgraph.OffroadMetric().compute)

    def _run_once(self, scenario: Any) -> dict[str, Any]:
        sdc_indices = np.flatnonzero(
            np.asarray(scenario.object_metadata.is_sdc, dtype=bool)
        )
        if sdc_indices.size != 1:
            raise ValueError(f"Expected one SDC, found {sdc_indices.size}.")
        sdc_index = int(sdc_indices[0])
        rng = jax.random.PRNGKey(SEED)
        state = self._environment.reset(scenario)
        digest = hashlib.sha256()
        _update_trajectory_hash(digest, state)
        max_overlap = 0.0
        max_offroad = 0.0
        sdc_valid_all_steps = True

        for step_index in range(NUM_TRAJECTORY_STEPS):
            overlap_result = self._overlap(state)
            offroad_result = self._offroad(state)
            max_overlap = max(
                max_overlap,
                float(np.asarray(overlap_result.value)[sdc_index]),
            )
            max_offroad = max(
                max_offroad,
                float(np.asarray(offroad_result.value)[sdc_index]),
            )
            sdc_valid_all_steps = sdc_valid_all_steps and bool(
                np.asarray(state.current_sim_trajectory.valid)[sdc_index, 0]
            )
            if step_index == NUM_FUTURE_STEPS:
                break
            actor_output = self._select_action(None, state, None, rng)
            state = self._step(state, actor_output.action)
            _update_trajectory_hash(digest, state)

        jax.block_until_ready(state.timestep)
        return {
            "trajectory_sha256": digest.hexdigest(),
            "max_sdc_overlap": max_overlap,
            "max_sdc_offroad": max_offroad,
            "sdc_valid_all_steps": sdc_valid_all_steps,
            "final_timestep": int(state.timestep),
        }

    def validate(self, serialized: bytes) -> tuple[bool, str, dict[str, Any]]:
        scenario = _waymax_scenario(serialized)
        first_started = time.perf_counter()
        first = self._run_once(scenario)
        first_seconds = time.perf_counter() - first_started
        second_started = time.perf_counter()
        second = self._run_once(scenario)
        second_seconds = time.perf_counter() - second_started
        deterministic = first["trajectory_sha256"] == second["trajectory_sha256"]
        completed = (
            first["final_timestep"] == 90 and second["final_timestep"] == 90
        )
        passed = bool(
            deterministic
            and completed
            and first["sdc_valid_all_steps"]
            and second["sdc_valid_all_steps"]
            and first["max_sdc_overlap"] == 0.0
            and second["max_sdc_overlap"] == 0.0
            and first["max_sdc_offroad"] == 0.0
            and second["max_sdc_offroad"] == 0.0
        )
        if not deterministic:
            reason = "trajectory hashes differ"
        elif not completed:
            reason = "rollout did not reach timestep 90"
        elif not first["sdc_valid_all_steps"] or not second["sdc_valid_all_steps"]:
            reason = "SDC became invalid"
        elif first["max_sdc_overlap"] > 0 or second["max_sdc_overlap"] > 0:
            reason = "SDC overlap occurred"
        elif first["max_sdc_offroad"] > 0 or second["max_sdc_offroad"] > 0:
            reason = "SDC offroad event occurred"
        else:
            reason = "passed"
        report = {
            "policy": "Waymax IDMRoutePolicy controlling SDC",
            "dynamics": "StateDynamics",
            "rollout_steps": NUM_FUTURE_STEPS,
            "seed": SEED,
            "outputs_identical": deterministic,
            "trajectory_sha256": first["trajectory_sha256"],
            "max_sdc_overlap": max(
                first["max_sdc_overlap"], second["max_sdc_overlap"]
            ),
            "max_sdc_offroad": max(
                first["max_sdc_offroad"], second["max_sdc_offroad"]
            ),
            "sdc_valid_all_steps": bool(
                first["sdc_valid_all_steps"]
                and second["sdc_valid_all_steps"]
            ),
            "final_timestep": min(
                first["final_timestep"], second["final_timestep"]
            ),
            "first_rollout_seconds": round(first_seconds, 6),
            "second_rollout_seconds": round(second_seconds, 6),
        }
        return passed, reason, report


def select_scenarios(
    start_shard: int,
    max_shards: int,
    target_count: int,
    left_turn_probe_shards: int,
) -> dict[str, Any]:
    """Run the bounded family probe, fallback decision, and validation."""
    if target_count < 1:
        raise ValueError("target_count must be positive.")
    if left_turn_probe_shards < 1 or left_turn_probe_shards > max_shards:
        raise ValueError("left_turn_probe_shards must be within max_shards.")
    if start_shard < 0 or start_shard + max_shards > TOTAL_TRAINING_SHARDS:
        raise ValueError("Requested shard range is outside the training split.")

    started = time.perf_counter()
    thresholds = SelectionThresholds()
    scans: list[ShardScan] = []
    left_pool: list[MinedRecord] = []
    lead_pool: list[MinedRecord] = []
    for shard_index in range(
        start_shard, start_shard + left_turn_probe_shards
    ):
        print(
            f"Probing preferred family in shard {shard_index:05d}...",
            file=sys.stderr,
            flush=True,
        )
        scan = _scan_shard(
            shard_index,
            thresholds,
            families=("left_turn_oncoming", "lead_vehicle_braking"),
        )
        scans.append(scan)
        left_pool.extend(scan.left_turns)
        lead_pool.extend(scan.lead_braking)

    use_left_turns = len(left_pool) >= target_count
    family = (
        "left_turn_oncoming" if use_left_turns else "lead_vehicle_braking"
    )
    fallback_reason = None
    if not use_left_turns:
        fallback_reason = (
            f"The bounded preferred-family probe found {len(left_pool)} "
            f"strict left-turn/oncoming candidates, fewer than the required "
            f"{target_count}; the predeclared lead-braking fallback was used."
        )

    validator = BaselineValidator()
    selected: list[dict[str, Any]] = []
    rejected_count = 0
    selected_family_candidates_mined = len(
        left_pool if use_left_turns else lead_pool
    )

    def validate_pool(pool: Iterable[MinedRecord]) -> None:
        nonlocal rejected_count
        for mined in pool:
            if len(selected) >= target_count:
                return
            candidate = mined.candidate
            print(
                f"Validating {candidate.family} candidate "
                f"{candidate.scenario_id}...",
                file=sys.stderr,
                flush=True,
            )
            passed, reason, baseline = validator.validate(mined.serialized)
            if not passed:
                rejected_count += 1
                print(
                    f"Rejected candidate: {reason}",
                    file=sys.stderr,
                    flush=True,
                )
                continue
            selected.append(
                {
                    "selection_order": len(selected) + 1,
                    **dataclasses.asdict(candidate),
                    "source_shard": Path(
                        _training_shard_uri(candidate.shard_index)
                    ).name,
                    "baseline_validation": baseline,
                    "protection_status": (
                        "unverified_from_tfexample"
                        if family == "left_turn_oncoming"
                        else "not_applicable"
                    ),
                }
            )

    validate_pool(left_pool if use_left_turns else lead_pool)

    next_shard = start_shard + left_turn_probe_shards
    while (
        len(selected) < target_count
        and next_shard < start_shard + max_shards
    ):
        print(
            f"Scanning {family} candidates in shard {next_shard:05d}...",
            file=sys.stderr,
            flush=True,
        )
        scan = _scan_shard(next_shard, thresholds, families=(family,))
        scans.append(scan)
        pool = scan.left_turns if use_left_turns else scan.lead_braking
        selected_family_candidates_mined += len(pool)
        validate_pool(pool)
        next_shard += 1

    if len(selected) != target_count:
        raise RuntimeError(
            f"Selected {len(selected)} of {target_count} required scenarios "
            f"after scanning {len(scans)} shards. Increase --max-shards."
        )

    return {
        "schema_version": 1,
        "status": "passed",
        "dataset": {
            "name": "Waymo Open Motion Dataset",
            "version": DATASET_VERSION,
            "split": SPLIT,
        },
        "selection_protocol": {
            "target_count": target_count,
            "start_shard": start_shard,
            "max_shards": max_shards,
            "left_turn_probe_shards": left_turn_probe_shards,
            "preferred_family": "left_turn_oncoming",
            "fallback_family": "lead_vehicle_braking",
            "selected_family": family,
            "fallback_reason": fallback_reason,
            "ordering": (
                "ascending shard index, then ascending TFRecord index; one "
                "best-scoring interacting vehicle per scenario"
            ),
            "thresholds": dataclasses.asdict(thresholds),
            "baseline_pass_definition": (
                "Two identical 80-step Waymax IDM SDC rollouts; SDC remains "
                "valid with zero overlap and zero offroad at every timestep."
            ),
        },
        "scan_summary": {
            "shards_scanned": len(scans),
            "records_scanned": sum(scan.records_scanned for scan in scans),
            "record_bytes_processed": sum(
                scan.record_bytes_processed for scan in scans
            ),
            "preferred_family_probe_records_scanned": sum(
                scan.records_scanned
                for scan in scans[:left_turn_probe_shards]
            ),
            "preferred_family_candidates_in_probe": len(left_pool),
            "selected_family_candidates_mined": selected_family_candidates_mined,
            "baseline_rejected_candidates": rejected_count,
            "selected_candidates": len(selected),
            "total_seconds": round(time.perf_counter() - started, 6),
            "process_peak_rss_bytes": _peak_rss_bytes(),
        },
        "candidates": selected,
        "environment": {
            **_git_provenance(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "jax": jax.__version__,
            "tensorflow": tf.__version__,
            "jax_backend": jax.default_backend(),
            "waymax_git_commit": WAYMAX_GIT_COMMIT,
            "selector_source_sha256": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
        },
        "limitations": [
            "This is a deterministic feasibility sample, not a representative or random sample.",
            "WOMD TFExample does not provide a definitive unprotected-turn label.",
            "The left-turn probe is intentionally bounded before using the predeclared fallback.",
            "IDM follows the recorded spatial route; passing does not imply general planner safety.",
            "Per-scenario identifiers and derived features belong only in ignored local artifacts; raw records are never written.",
        ],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-shard", type=int, default=0)
    parser.add_argument("--max-shards", type=int, default=12)
    parser.add_argument("--target-count", type=int, default=10)
    parser.add_argument("--left-turn-probe-shards", type=int, default=1)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = select_scenarios(
        start_shard=args.start_shard,
        max_shards=args.max_shards,
        target_count=args.target_count,
        left_turn_probe_shards=args.left_turn_probe_shards,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
