"""Build a deterministic, trajectory-linked LiDAR Gaussian field.

This module intentionally does not implement photometric 3DGS.  It converts the
exact scenario's WOMD-LiDAR range images into static anisotropic primitives and
scores held-aside sensor frames against the fitted means.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import resource
import tempfile
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import tensorflow as tf
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

from planmargin.womd_lidar_proto import DeltaEncodedData, Scenario

SCHEMA_VERSION = "1.0.0"
SCHEMA_URI = (
    "https://raw.githubusercontent.com/ethanvillalovoz/planmargin/main/"
    "schemas/gaussian-field-manifest-v1.schema.json"
)
DEFAULT_OUTPUT_DIR = Path("artifacts/gaussian-field/feasibility")
MAX_SOURCE_BYTES = 64 * 1024 * 1024
FRAME_COUNT = 11
TOP_LASER = 1
FIT_FRAMES = (0, 2, 4, 6, 8, 10)
EVAL_FRAMES = (1, 3, 5, 7, 9)
CROP_RADIUS_M = 40.0
CROP_Z_MIN_M = -3.0
CROP_Z_MAX_M = 5.0
BOX_EXPANSION_M = 0.5
FRAME_POINT_CAP = 75_000
VOXEL_SIZE_M = 0.25
NEIGHBOR_COUNT = 16
MIN_PRIMITIVES = 5_000
MAX_PRIMITIVES = 75_000
MAX_FIELD_BYTES = 32 * 1024 * 1024
MAX_RUNTIME_SECONDS = 15 * 60
MAX_PEAK_RSS_BYTES = 12 * 1024**3
MAX_MEDIAN_DISTANCE_M = 0.35
MAX_P90_DISTANCE_M = 0.75
MIN_COVERAGE_WITHIN_050 = 0.75
MIN_TRAJECTORY_LINKAGE = 0.90


class GaussianFieldError(ValueError):
    """Raised when private input or a frozen feasibility invariant is invalid."""


@dataclass(frozen=True)
class ActorBoxes:
    """Tracked actor boxes for the eleven past/current sensor timestamps."""

    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    length: np.ndarray
    width: np.ndarray
    height: np.ndarray
    yaw: np.ndarray
    valid: np.ndarray
    sdc_index: int


@dataclass(frozen=True)
class PointFrame:
    """One sensor frame represented in the global scenario coordinate frame."""

    xyz: np.ndarray
    intensity: np.ndarray
    elongation: np.ndarray
    pose: np.ndarray


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if os.uname().sysname == "Darwin" else peak * 1024)


def _private_file(path: Path, *, maximum_bytes: int = MAX_SOURCE_BYTES) -> Path:
    """Resolve a regular, non-symlink input confined to the ignored artifact tree."""
    artifacts = (Path.cwd() / "artifacts").resolve()
    if path.is_symlink():
        raise GaussianFieldError("Private Gaussian inputs may not be symlinks.")
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(artifacts):
        raise GaussianFieldError("Private Gaussian inputs must remain under artifacts/.")
    stat = resolved.stat()
    if not resolved.is_file() or stat.st_size > maximum_bytes:
        raise GaussianFieldError("Private Gaussian input is not a bounded regular file.")
    return resolved


def _output_dir(path: Path) -> Path:
    artifacts = (Path.cwd() / "artifacts").resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(artifacts):
        raise GaussianFieldError("Gaussian outputs must remain under artifacts/.")
    current = resolved
    while current != artifacts and not current.exists():
        current = current.parent
    if current.is_symlink():
        raise GaussianFieldError("Gaussian output ancestry may not be a symlink.")
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


def decompress_delta(payload: bytes) -> np.ndarray:
    """Decode Waymo's documented zlib/delta/RLE tensor representation."""
    if not payload:
        raise GaussianFieldError("Compressed tensor payload is empty.")
    decoded = DeltaEncodedData()
    try:
        decoded.ParseFromString(zlib.decompress(payload))
    except (zlib.error, ValueError) as error:
        raise GaussianFieldError("Compressed tensor payload is invalid.") from error
    shape = tuple(int(value) for value in decoded.metadata.shape)
    precision = np.asarray(decoded.metadata.quant_precision, dtype=np.float64)
    if len(shape) != 3 or any(value <= 0 for value in shape):
        raise GaussianFieldError("Compressed tensor has an invalid shape.")
    if precision.shape != (shape[2],) or np.any(~np.isfinite(precision)):
        raise GaussianFieldError("Compressed tensor precision metadata is invalid.")
    mask_runs = np.asarray(decoded.mask, dtype=np.int64)
    if mask_runs.size == 0 or np.any(mask_runs < 0):
        raise GaussianFieldError("Compressed tensor mask is invalid.")
    mask = np.repeat(np.arange(mask_runs.size) % 2 == 0, mask_runs)
    if mask.size != math.prod(shape):
        raise GaussianFieldError("Compressed tensor mask does not match its shape.")
    residual = np.asarray(decoded.residual, dtype=np.int64)
    if residual.size != int(mask.sum()):
        raise GaussianFieldError("Compressed tensor residual count is invalid.")
    values = np.zeros(mask.size, dtype=np.int64)
    values[mask] = np.cumsum(residual, dtype=np.int64)
    tensor = np.transpose(
        values.reshape((shape[2], shape[0], shape[1])), (1, 2, 0)
    ).astype(np.float64)
    return tensor * precision


def _matrix(values: Iterable[float], name: str) -> np.ndarray:
    array = np.asarray(tuple(values), dtype=np.float64)
    if array.shape != (16,) or np.any(~np.isfinite(array)):
        raise GaussianFieldError(f"{name} is not a finite 4x4 transform.")
    matrix = array.reshape(4, 4)
    if not np.allclose(matrix[3], [0.0, 0.0, 0.0, 1.0], atol=1e-5):
        raise GaussianFieldError(f"{name} is not an affine transform.")
    return matrix


def _transform_points(points: np.ndarray, transform: np.ndarray) -> np.ndarray:
    return points @ transform[:3, :3].T + transform[:3, 3]


def _range_image_points(
    range_image: np.ndarray,
    calibration: Any,
    frame_pose: np.ndarray,
    pixel_pose: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if range_image.ndim != 3 or range_image.shape[2] < 3:
        raise GaussianFieldError("Range image must contain range, intensity, elongation.")
    height, width, _ = range_image.shape
    ranges = range_image[:, :, 0]
    valid = np.isfinite(ranges) & (ranges > 0.0)
    if not np.any(valid):
        empty = np.empty((0,), dtype=np.float32)
        return np.empty((0, 3), dtype=np.float32), empty, empty

    inclinations = np.asarray(calibration.beam_inclinations, dtype=np.float64)
    if inclinations.size:
        if inclinations.shape != (height,):
            raise GaussianFieldError("Beam inclination count does not match image height.")
    else:
        step = (
            float(calibration.beam_inclination_max)
            - float(calibration.beam_inclination_min)
        ) / height
        inclinations = (
            float(calibration.beam_inclination_min)
            + (np.arange(height, dtype=np.float64) + 0.5) * step
        )
    inclinations = inclinations[::-1]
    extrinsic = _matrix(calibration.extrinsic.transform, "laser extrinsic")
    correction = math.atan2(extrinsic[1, 0], extrinsic[0, 0])
    ratios = (np.arange(width, 0, -1, dtype=np.float64) - 0.5) / width
    azimuth = (ratios * 2.0 - 1.0) * math.pi - correction
    cosine_inclination = np.cos(inclinations)[:, None]
    sensor = np.stack(
        (
            np.cos(azimuth)[None, :] * cosine_inclination * ranges,
            np.sin(azimuth)[None, :] * cosine_inclination * ranges,
            np.sin(inclinations)[:, None] * ranges,
        ),
        axis=-1,
    )
    vehicle = _transform_points(sensor[valid], extrinsic)
    if pixel_pose is not None:
        if pixel_pose.shape != (height, width, 6):
            raise GaussianFieldError("TOP pixel poses do not match range-image shape.")
        pixel_transforms = np.zeros((len(vehicle), 4, 4), dtype=np.float64)
        pixel_transforms[:, 3, 3] = 1.0
        poses = pixel_pose[valid]
        pixel_transforms[:, :3, :3] = Rotation.from_euler(
            "xyz", poses[:, :3]
        ).as_matrix()
        pixel_transforms[:, :3, 3] = poses[:, 3:]
        global_xyz = np.einsum(
            "nij,nj->ni", pixel_transforms[:, :3, :3], vehicle
        ) + pixel_transforms[:, :3, 3]
    else:
        global_xyz = _transform_points(vehicle, frame_pose)
    return (
        global_xyz.astype(np.float32),
        range_image[:, :, 1][valid].astype(np.float32),
        range_image[:, :, 2][valid].astype(np.float32),
    )


def load_sensor_frames(path: Path) -> list[PointFrame]:
    """Parse exactly one bounded WOMD-LiDAR scenario into global point frames."""
    source = _private_file(path)
    records = list(tf.data.TFRecordDataset([str(source)]).as_numpy_iterator())
    if len(records) != 1:
        raise GaussianFieldError("LiDAR input must contain exactly one scenario record.")
    scenario = Scenario()
    scenario.ParseFromString(records[0])
    frames = scenario.compressed_frame_laser_data
    if len(frames) != FRAME_COUNT:
        raise GaussianFieldError("LiDAR input must contain exactly eleven frames.")
    result: list[PointFrame] = []
    for frame_index, frame in enumerate(frames):
        frame_pose = _matrix(frame.pose.transform, f"frame {frame_index} pose")
        calibrations = {int(value.name): value for value in frame.laser_calibrations}
        lasers = {int(value.name): value for value in frame.lasers}
        if calibrations.keys() != lasers.keys() or len(lasers) != 5:
            raise GaussianFieldError("Every frame must contain five calibrated lasers.")
        top = lasers.get(TOP_LASER)
        if top is None:
            raise GaussianFieldError("Every frame must contain the TOP laser.")
        pixel_pose = decompress_delta(
            top.ri_return1.range_image_pose_delta_compressed
        )
        chunks: list[np.ndarray] = []
        intensities: list[np.ndarray] = []
        elongations: list[np.ndarray] = []
        for laser_name in sorted(lasers):
            laser = lasers[laser_name]
            calibration = calibrations[laser_name]
            for return_index, compressed in enumerate(
                (laser.ri_return1, laser.ri_return2)
            ):
                image = decompress_delta(compressed.range_image_delta_compressed)
                xyz, intensity, elongation = _range_image_points(
                    image,
                    calibration,
                    frame_pose,
                    pixel_pose if laser_name == TOP_LASER else None,
                )
                if return_index not in (0, 1):  # pragma: no cover - structural
                    raise AssertionError
                chunks.append(xyz)
                intensities.append(intensity)
                elongations.append(elongation)
        result.append(
            PointFrame(
                xyz=np.concatenate(chunks),
                intensity=np.concatenate(intensities),
                elongation=np.concatenate(elongations),
                pose=frame_pose,
            )
        )
    return result


def _feature(example: tf.train.Example, key: str, *, dtype: Any) -> np.ndarray:
    value = example.features.feature[key]
    kind = value.WhichOneof("kind")
    if kind == "float_list":
        return np.asarray(value.float_list.value, dtype=dtype)
    if kind == "int64_list":
        return np.asarray(value.int64_list.value, dtype=dtype)
    raise GaussianFieldError(f"Motion record is missing {key}.")


def _past_current(example: tf.train.Example, name: str) -> np.ndarray:
    past = _feature(example, f"state/past/{name}", dtype=np.float64).reshape(128, 10)
    current = _feature(
        example, f"state/current/{name}", dtype=np.float64
    ).reshape(128, 1)
    return np.concatenate((past, current), axis=1)


def load_actor_boxes(path: Path) -> tuple[ActorBoxes, str]:
    """Load one selected motion TFExample and its private scenario identifier."""
    source = _private_file(path)
    records = list(tf.data.TFRecordDataset([str(source)]).as_numpy_iterator())
    if len(records) != 1:
        raise GaussianFieldError("Motion input must contain exactly one record.")
    example = tf.train.Example.FromString(records[0])
    ids = example.features.feature["scenario/id"].bytes_list.value
    if len(ids) != 1:
        raise GaussianFieldError("Motion record has no unique scenario ID.")
    is_sdc = _feature(example, "state/is_sdc", dtype=np.int64) == 1
    if is_sdc.sum() != 1:
        raise GaussianFieldError("Motion record must contain exactly one SDC.")
    boxes = ActorBoxes(
        x=_past_current(example, "x"),
        y=_past_current(example, "y"),
        z=_past_current(example, "z"),
        length=_past_current(example, "length"),
        width=_past_current(example, "width"),
        height=_past_current(example, "height"),
        yaw=_past_current(example, "bbox_yaw"),
        valid=_past_current(example, "valid") == 1,
        sdc_index=int(np.flatnonzero(is_sdc)[0]),
    )
    return boxes, ids[0].decode("utf-8")


def _remove_actor_returns(points: np.ndarray, boxes: ActorBoxes, frame: int) -> np.ndarray:
    keep = np.ones(len(points), dtype=bool)
    for actor in np.flatnonzero(boxes.valid[:, frame]):
        delta = points - np.array(
            [boxes.x[actor, frame], boxes.y[actor, frame], boxes.z[actor, frame]]
        )
        cosine = math.cos(float(boxes.yaw[actor, frame]))
        sine = math.sin(float(boxes.yaw[actor, frame]))
        local_x = cosine * delta[:, 0] + sine * delta[:, 1]
        local_y = -sine * delta[:, 0] + cosine * delta[:, 1]
        inside = (
            (np.abs(local_x) <= boxes.length[actor, frame] / 2 + BOX_EXPANSION_M)
            & (np.abs(local_y) <= boxes.width[actor, frame] / 2 + BOX_EXPANSION_M)
            & (np.abs(delta[:, 2]) <= boxes.height[actor, frame] / 2 + BOX_EXPANSION_M)
        )
        keep &= ~inside
    return keep


def filter_frame(
    frame: PointFrame, boxes: ActorBoxes, frame_index: int, center: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    relative = frame.xyz - center
    keep = (
        (np.abs(relative[:, 0]) <= CROP_RADIUS_M)
        & (np.abs(relative[:, 1]) <= CROP_RADIUS_M)
        & (relative[:, 2] >= CROP_Z_MIN_M)
        & (relative[:, 2] <= CROP_Z_MAX_M)
        & np.all(np.isfinite(frame.xyz), axis=1)
        & np.isfinite(frame.intensity)
    )
    keep &= _remove_actor_returns(frame.xyz, boxes, frame_index)
    indices = np.flatnonzero(keep)
    if len(indices) > FRAME_POINT_CAP:
        indices = indices[np.linspace(0, len(indices) - 1, FRAME_POINT_CAP, dtype=int)]
    return frame.xyz[indices], frame.intensity[indices]


def fit_gaussians(
    points: np.ndarray, intensity: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Voxelize points and derive local anisotropic covariance primitives."""
    if len(points) < MIN_PRIMITIVES:
        raise GaussianFieldError("Too few retained fit points for the frozen gate.")
    keys = np.floor(points / VOXEL_SIZE_M).astype(np.int32)
    _, inverse = np.unique(keys, axis=0, return_inverse=True)
    counts = np.bincount(inverse)
    means = np.column_stack(
        [np.bincount(inverse, weights=points[:, axis]) / counts for axis in range(3)]
    )
    mean_intensity = np.bincount(inverse, weights=intensity) / counts
    if len(means) > MAX_PRIMITIVES:
        indices = np.linspace(0, len(means) - 1, MAX_PRIMITIVES, dtype=int)
        means = means[indices]
        mean_intensity = mean_intensity[indices]
    if len(means) < MIN_PRIMITIVES:
        raise GaussianFieldError("Voxel reduction produced too few Gaussian primitives.")
    tree = cKDTree(means)
    _, neighbors = tree.query(means, k=min(NEIGHBOR_COUNT, len(means)), workers=-1)
    centered = means[neighbors] - means[:, None, :]
    covariance = np.einsum("nki,nkj->nij", centered, centered) / neighbors.shape[1]
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    eigenvalues = np.maximum(eigenvalues, 0.0)
    scales = np.sqrt(eigenvalues)
    scales[:, 0] = np.clip(scales[:, 0], 0.03, 0.20)
    scales[:, 1:] = np.clip(scales[:, 1:], 0.08, 0.60)
    determinants = np.linalg.det(eigenvectors)
    eigenvectors[:, :, 2] *= np.where(determinants < 0.0, -1.0, 1.0)[:, None]
    quaternions_xyzw = Rotation.from_matrix(eigenvectors).as_quat()
    quaternions_wxyz = quaternions_xyzw[:, [3, 0, 1, 2]]
    low, high = np.percentile(mean_intensity, (2.0, 98.0))
    denominator = max(float(high - low), 1e-6)
    normalized = np.clip((mean_intensity - low) / denominator, 0.0, 1.0)
    # Fixed, high-contrast viridis-inspired ramp for geometry rather than RGB claims.
    stops = np.array(
        [[0.267, 0.005, 0.329], [0.128, 0.567, 0.551], [0.993, 0.906, 0.144]]
    )
    first = np.minimum(normalized * 2.0, 1.0)
    second = np.maximum(normalized * 2.0 - 1.0, 0.0)
    colors = (
        stops[0] * (1.0 - first[:, None])
        + stops[1] * (first - second)[:, None]
        + stops[2] * second[:, None]
    )
    return (
        means.astype(np.float32),
        scales.astype(np.float32),
        quaternions_wxyz.astype(np.float32),
        colors.astype(np.float32),
    )


def write_splat_ply(
    means: np.ndarray,
    scales: np.ndarray,
    rotations: np.ndarray,
    colors: np.ndarray,
) -> bytes:
    """Return a deterministic little-endian standard 3DGS PLY payload."""
    names = [
        "x", "y", "z", "nx", "ny", "nz", "f_dc_0", "f_dc_1", "f_dc_2",
        "opacity", "scale_0", "scale_1", "scale_2", "rot_0", "rot_1",
        "rot_2", "rot_3",
    ]
    header = "\n".join(
        ["ply", "format binary_little_endian 1.0", f"element vertex {len(means)}"]
        + [f"property float {name}" for name in names]
        + ["end_header", ""]
    ).encode("ascii")
    c0 = 0.28209479177387814
    values = np.column_stack(
        (
            means,
            np.zeros_like(means),
            (colors - 0.5) / c0,
            np.full((len(means), 1), math.log(0.82 / 0.18)),
            np.log(scales),
            rotations,
        )
    ).astype("<f4")
    return header + values.tobytes(order="C")


def _load_json(path: Path) -> dict[str, Any]:
    source = _private_file(path, maximum_bytes=32 * 1024 * 1024)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GaussianFieldError("Private JSON input is unreadable.") from error
    if not isinstance(value, dict):
        raise GaussianFieldError("Private JSON input must be an object.")
    return value


def _validate_identity(
    scenario_id: str, selection: dict[str, Any], rollouts: dict[str, Any]
) -> None:
    candidates = [
        value
        for value in selection.get("candidates", [])
        if value.get("selection_order") == 2
    ]
    if len(candidates) != 1 or candidates[0].get("scenario_id") != scenario_id:
        raise GaussianFieldError("Motion input does not match frozen selection order 2.")
    record_ids = {
        record.get("scenario", {}).get("scenario_id")
        for record in rollouts.get("records", [])
    }
    if record_ids != {scenario_id}:
        raise GaussianFieldError("Rollout collection does not match the motion input.")


def _trajectory_linkage(rollouts: dict[str, Any], center: np.ndarray) -> float:
    samples: list[tuple[float, float, float]] = []
    for record in rollouts.get("records", []):
        trace = record.get("trajectory", {})
        for x, y, z, valid in zip(
            trace.get("x_m", []), trace.get("y_m", []), trace.get("z_m", []),
            trace.get("valid", []), strict=True
        ):
            if valid:
                samples.append((float(x), float(y), float(z)))
    actors = rollouts.get("scene_context", {}).get("actors", {})
    target = actors.get("mutation_target", {})
    for variant in ("original", "counterfactual"):
        trace = target.get(variant, {})
        z_values = trace.get("z_m", [float(center[2])] * len(trace.get("x_m", [])))
        for x, y, z, valid in zip(
            trace.get("x_m", []), trace.get("y_m", []), z_values,
            trace.get("valid", []), strict=True
        ):
            if valid:
                samples.append((float(x), float(y), float(z)))
    if not samples:
        raise GaussianFieldError("Rollout collection has no valid trajectory samples.")
    relative = np.asarray(samples) - center
    inside = (
        (np.abs(relative[:, 0]) <= CROP_RADIUS_M + 2.0)
        & (np.abs(relative[:, 1]) <= CROP_RADIUS_M + 2.0)
        & (relative[:, 2] >= CROP_Z_MIN_M - 2.0)
        & (relative[:, 2] <= CROP_Z_MAX_M + 2.0)
    )
    return float(np.mean(inside))


def _coordinate_alignment(frames: list[PointFrame], boxes: ActorBoxes) -> dict[str, float]:
    translations = np.asarray([frame.pose[:3, 3] for frame in frames])
    sdc = np.column_stack(
        (boxes.x[boxes.sdc_index], boxes.y[boxes.sdc_index], boxes.z[boxes.sdc_index])
    )
    valid = boxes.valid[boxes.sdc_index]
    differences = translations[valid] - sdc[valid]
    xy_distances = np.linalg.norm(differences[:, :2], axis=1)
    if not len(xy_distances):
        raise GaussianFieldError("SDC has no valid sensor-alignment samples.")
    return {
        "median_xy_error_m": float(np.median(xy_distances)),
        "max_xy_error_m": float(np.max(xy_distances)),
        # The vehicle pose origin and tracked box center have different vertical
        # datums.  Constancy, rather than equality, is the coordinate-frame check.
        "median_z_offset_m": float(np.median(differences[:, 2])),
        "z_offset_spread_m": float(np.ptp(differences[:, 2])),
    }


def build_field(
    *,
    lidar_path: Path,
    motion_path: Path,
    selection_path: Path,
    rollouts_path: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Run the frozen private feasibility fit and atomically publish its outputs."""
    started = time.monotonic()
    output = _output_dir(output_dir)
    boxes, scenario_id = load_actor_boxes(motion_path)
    selection = _load_json(selection_path)
    rollouts = _load_json(rollouts_path)
    _validate_identity(scenario_id, selection, rollouts)
    frames = load_sensor_frames(lidar_path)
    alignment = _coordinate_alignment(frames, boxes)
    center = np.array(
        [
            boxes.x[boxes.sdc_index, -1],
            boxes.y[boxes.sdc_index, -1],
            boxes.z[boxes.sdc_index, -1],
        ],
        dtype=np.float64,
    )
    filtered = [filter_frame(frame, boxes, index, center) for index, frame in enumerate(frames)]
    fit_xyz = np.concatenate([filtered[index][0] for index in FIT_FRAMES])
    fit_intensity = np.concatenate([filtered[index][1] for index in FIT_FRAMES])
    means, scales, rotations, colors = fit_gaussians(fit_xyz, fit_intensity)
    tree = cKDTree(means)
    evaluation = np.concatenate([filtered[index][0] for index in EVAL_FRAMES])
    distances = tree.query(evaluation, k=1, workers=-1)[0]
    geometric = {
        "median_nearest_mean_distance_m": float(np.median(distances)),
        "p90_nearest_mean_distance_m": float(np.percentile(distances, 90.0)),
        "coverage_within_0_50_m": float(np.mean(distances <= 0.50)),
        "evaluation_point_count": int(len(evaluation)),
    }
    linkage = _trajectory_linkage(rollouts, center)
    ply = write_splat_ply(means, scales, rotations, colors)
    repeated = write_splat_ply(*fit_gaussians(fit_xyz, fit_intensity))
    deterministic = repeated == ply
    runtime = time.monotonic() - started
    observed = {
        "frame_count": len(frames),
        "fit_frame_indices": list(FIT_FRAMES),
        "evaluation_frame_indices": list(EVAL_FRAMES),
        "retained_points_by_frame": [int(len(value[0])) for value in filtered],
        "fit_point_count": int(len(fit_xyz)),
        "primitive_count": int(len(means)),
        "field_bytes": len(ply),
        "runtime_seconds": runtime,
        "peak_rss_bytes": _peak_rss_bytes(),
        "coordinate_alignment": alignment,
        "geometric_quality": geometric,
        "trajectory_linkage_fraction": linkage,
    }
    gates = {
        "authorized_exact_input": len(frames) == FRAME_COUNT,
        "determinism": deterministic,
        "scale": MIN_PRIMITIVES <= len(means) <= MAX_PRIMITIVES and len(ply) <= MAX_FIELD_BYTES,
        "local_compute": runtime <= MAX_RUNTIME_SECONDS and observed["peak_rss_bytes"] <= MAX_PEAK_RSS_BYTES,
        "geometric_quality": geometric["median_nearest_mean_distance_m"] <= MAX_MEDIAN_DISTANCE_M
        and geometric["p90_nearest_mean_distance_m"] <= MAX_P90_DISTANCE_M
        and geometric["coverage_within_0_50_m"] >= MIN_COVERAGE_WITHIN_050,
        "trajectory_linkage": linkage >= MIN_TRAJECTORY_LINKAGE
        and alignment["median_xy_error_m"] <= 0.50
        and alignment["max_xy_error_m"] <= 1.00
        and alignment["z_offset_spread_m"] <= 0.10,
    }
    field_path = output / "field.ply"
    _atomic_write(field_path, ply)
    field_sha256 = _sha256_bytes(ply)
    fingerprint_payload = {
        "configuration": {
            "fit_frames": list(FIT_FRAMES),
            "evaluation_frames": list(EVAL_FRAMES),
            "crop_radius_m": CROP_RADIUS_M,
            "crop_relative_z_m": [CROP_Z_MIN_M, CROP_Z_MAX_M],
            "voxel_size_m": VOXEL_SIZE_M,
            "neighbor_count": NEIGHBOR_COUNT,
            "fixed_opacity": 0.82,
        },
        "field_sha256": field_sha256,
        "gates": gates,
        "geometry": {
            "primitive_count": observed["primitive_count"],
            "field_bytes": observed["field_bytes"],
            "coordinate_alignment": alignment,
            "geometric_quality": geometric,
            "trajectory_linkage_fraction": linkage,
        },
    }
    manifest = {
        "$schema": SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": "planmargin.lidar_gaussian_field_manifest",
        "decision": "go" if all(gates.values()) else "no_go",
        "held_out_opened": False,
        "source_scope": "frozen_training_scenario_selection_order_2",
        "representation": "deterministic_lidar_gaussian_field",
        "claim_boundary": "not_photorealistic_not_learned_not_safety_evidence",
        "privacy": {
            "contains_scenario_id": False,
            "contains_source_uri": False,
            "contains_raw_points": False,
            "unrestricted_export": False,
        },
        "integration_gates": {
            "debugging_value": "not_run_after_trajectory_no_go",
            "browser_performance": "not_run_after_trajectory_no_go",
            "privacy": "not_run_after_trajectory_no_go",
            "data_free_reliability": "pass",
        },
        "configuration": fingerprint_payload["configuration"],
        "field_sha256": field_sha256,
        "observed": observed,
        "gates": gates,
        "logical_fingerprint": _sha256_bytes(_canonical_json(fingerprint_payload)),
    }
    manifest["manifest_sha256"] = _sha256_bytes(_canonical_json(manifest))
    _atomic_write(
        output / "manifest.json",
        json.dumps(manifest, allow_nan=False, indent=2, sort_keys=True).encode() + b"\n",
    )
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lidar", type=Path, required=True)
    parser.add_argument("--motion", type=Path, required=True)
    parser.add_argument("--selection", type=Path, default=Path("artifacts/stage-0/scenario-selection.json"))
    parser.add_argument("--rollouts", type=Path, default=Path("artifacts/stage-0/rollout-records.json"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    manifest = build_field(
        lidar_path=args.lidar,
        motion_path=args.motion,
        selection_path=args.selection,
        rollouts_path=args.rollouts,
        output_dir=args.output_dir,
    )
    print(json.dumps({"decision": manifest["decision"], "gates": manifest["gates"]}, sort_keys=True))


if __name__ == "__main__":
    main()
