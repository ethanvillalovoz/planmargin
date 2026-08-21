"""Prepare the local, ignored Waymo sensor scene used by the debugger.

The command extracts all FRONT camera frames from one already-downloaded
Waymo Open Dataset v2 Perception segment, extracts its native tracked camera
boxes, and binds them to the real Apple SHARP 3D Gaussian reconstruction
produced from frame 99. It never downloads data and never writes outside
``data/`` or ``artifacts/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

from planmargin import trajectory_model

SEGMENT_ID = "10023947602400723454_1120_000_1140_000"
FRONT_CAMERA_NAME = 1
SOURCE_FRAME_INDEX = 99
MOVING_SOURCE_FRAME_INDEX = 20
EXPECTED_FRAME_COUNT = 199
EXPECTED_GAUSSIANS = 1_179_648
MAX_LIDAR_PRIMITIVES = 75_000
CAMERA_BOX_TYPES = {1: "vehicle", 2: "pedestrian", 4: "cyclist"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _vertex_count(path: Path) -> int:
    with path.open("rb") as source:
        header = source.read(16 * 1024).split(b"end_header\n", 1)[0]
    for line in header.decode("ascii").splitlines():
        if line.startswith("element vertex "):
            return int(line.rsplit(" ", 1)[1])
    raise ValueError(f"PLY vertex count is missing: {path}")


def _transform(points: np.ndarray, values: list[float]) -> np.ndarray:
    matrix = np.asarray(values, dtype=np.float64).reshape(4, 4)
    return points @ matrix[:3, :3].T + matrix[:3, 3]


def _range_image_points(
    values: list[float],
    shape: list[int],
    extrinsic: list[float],
    inclination_values: list[float] | None,
    inclination_min: float,
    inclination_max: float,
) -> tuple[np.ndarray, np.ndarray]:
    image = np.asarray(values, dtype=np.float64).reshape(shape)
    height, width, _ = image.shape
    ranges = image[:, :, 0]
    valid = np.isfinite(ranges) & (ranges > 0.0)
    if inclination_values:
        inclinations = np.asarray(inclination_values, dtype=np.float64)
    else:
        step = (inclination_max - inclination_min) / height
        inclinations = inclination_min + (np.arange(height) + 0.5) * step
    inclinations = inclinations[::-1]
    matrix = np.asarray(extrinsic, dtype=np.float64).reshape(4, 4)
    correction = math.atan2(matrix[1, 0], matrix[0, 0])
    ratios = (np.arange(width, 0, -1, dtype=np.float64) - 0.5) / width
    azimuth = (ratios * 2.0 - 1.0) * math.pi - correction
    cosine = np.cos(inclinations)[:, None]
    sensor = np.stack(
        (
            np.cos(azimuth)[None, :] * cosine * ranges,
            np.sin(azimuth)[None, :] * cosine * ranges,
            np.sin(inclinations)[:, None] * ranges,
        ),
        axis=-1,
    )
    return _transform(sensor[valid], extrinsic), image[:, :, 1][valid]


def _lidar_splat_payload(points: np.ndarray, intensity: np.ndarray) -> bytes:
    crop = (
        np.all(np.isfinite(points), axis=1)
        & np.isfinite(intensity)
        & (np.linalg.norm(points[:, :2], axis=1) <= 55.0)
        & (points[:, 2] >= -3.5)
        & (points[:, 2] <= 6.0)
    )
    points = points[crop]
    intensity = intensity[crop]
    keys = np.floor(points / 0.18).astype(np.int32)
    _, inverse = np.unique(keys, axis=0, return_inverse=True)
    counts = np.bincount(inverse)
    means = np.column_stack(
        [np.bincount(inverse, weights=points[:, axis]) / counts for axis in range(3)]
    )
    mean_intensity = np.bincount(inverse, weights=intensity) / counts
    if len(means) > MAX_LIDAR_PRIMITIVES:
        indices = np.linspace(0, len(means) - 1, MAX_LIDAR_PRIMITIVES, dtype=int)
        means = means[indices]
        mean_intensity = mean_intensity[indices]
    tree = cKDTree(means)
    _, neighbors = tree.query(means, k=min(12, len(means)), workers=-1)
    centered = means[neighbors] - means[:, None, :]
    covariance = np.einsum("nki,nkj->nij", centered, centered) / neighbors.shape[1]
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    scales = np.sqrt(np.maximum(eigenvalues, 0.0))
    scales[:, 0] = np.clip(scales[:, 0], 0.02, 0.12)
    scales[:, 1:] = np.clip(scales[:, 1:], 0.05, 0.32)
    eigenvectors[:, :, 2] *= np.where(np.linalg.det(eigenvectors) < 0.0, -1.0, 1.0)[
        :, None
    ]
    rotations = Rotation.from_matrix(eigenvectors).as_quat()[:, [3, 0, 1, 2]]
    low, high = np.percentile(mean_intensity, (2.0, 98.0))
    normalized = np.clip((mean_intensity - low) / max(float(high - low), 1e-6), 0, 1)
    stops = np.asarray([[0.10, 0.16, 0.34], [0.05, 0.78, 0.82], [0.74, 0.98, 0.76]])
    first = np.minimum(normalized * 2.0, 1.0)
    second = np.maximum(normalized * 2.0 - 1.0, 0.0)
    colors = (
        stops[0] * (1.0 - first[:, None])
        + stops[1] * (first - second)[:, None]
        + stops[2] * second[:, None]
    )
    names = [
        "x",
        "y",
        "z",
        "nx",
        "ny",
        "nz",
        "f_dc_0",
        "f_dc_1",
        "f_dc_2",
        "opacity",
        "scale_0",
        "scale_1",
        "scale_2",
        "rot_0",
        "rot_1",
        "rot_2",
        "rot_3",
    ]
    header = "\n".join(
        ["ply", "format binary_little_endian 1.0", f"element vertex {len(means)}"]
        + [f"property float {name}" for name in names]
        + ["end_header", ""]
    ).encode("ascii")
    c0 = 0.28209479177387814
    payload = np.column_stack(
        (
            means,
            np.zeros_like(means),
            (colors - 0.5) / c0,
            np.full((len(means), 1), math.log(0.88 / 0.12)),
            np.log(scales),
            rotations,
        )
    ).astype("<f4")
    return header + payload.tobytes(order="C")


def _prepare_lidar(data_directory: Path, timestamp_micros: int, output: Path) -> None:
    connection = duckdb.connect()
    try:
        calibration_rows = connection.execute(
            """
            SELECT "key.laser_name",
                   "[LiDARCalibrationComponent].extrinsic.transform",
                   "[LiDARCalibrationComponent].beam_inclination.values",
                   "[LiDARCalibrationComponent].beam_inclination.min",
                   "[LiDARCalibrationComponent].beam_inclination.max"
            FROM read_parquet(?) ORDER BY "key.laser_name"
            """,
            [str(data_directory / "lidar_calibration.parquet")],
        ).fetchall()
        calibrations = {int(row[0]): row[1:] for row in calibration_rows}
        laser_rows = connection.execute(
            """
            SELECT "key.laser_name",
                   "[LiDARComponent].range_image_return1.values",
                   "[LiDARComponent].range_image_return1.shape",
                   "[LiDARComponent].range_image_return2.values",
                   "[LiDARComponent].range_image_return2.shape"
            FROM read_parquet(?)
            WHERE "key.frame_timestamp_micros" = ?
            ORDER BY "key.laser_name"
            """,
            [str(data_directory / "lidar.parquet"), timestamp_micros],
        ).fetchall()
    finally:
        connection.close()
    chunks: list[np.ndarray] = []
    intensities: list[np.ndarray] = []
    for laser_name, first, first_shape, second, second_shape in laser_rows:
        extrinsic, inclination_values, inclination_min, inclination_max = calibrations[
            int(laser_name)
        ]
        for values, shape in ((first, first_shape), (second, second_shape)):
            xyz, strength = _range_image_points(
                values,
                shape,
                extrinsic,
                inclination_values,
                float(inclination_min),
                float(inclination_max),
            )
            chunks.append(xyz)
            intensities.append(strength)
    output.write_bytes(
        _lidar_splat_payload(np.concatenate(chunks), np.concatenate(intensities))
    )


def _prepare_camera_annotations(
    camera_box_parquet: Path, frame_timestamps: list[int], output: Path
) -> dict[str, Any]:
    connection = duckdb.connect()
    try:
        rows = connection.execute(
            """
            SELECT "key.frame_timestamp_micros",
                   "key.camera_object_id",
                   "[CameraBoxComponent].box.center.x",
                   "[CameraBoxComponent].box.center.y",
                   "[CameraBoxComponent].box.size.x",
                   "[CameraBoxComponent].box.size.y",
                   "[CameraBoxComponent].type"
            FROM read_parquet(?)
            WHERE "key.camera_name" = ?
            ORDER BY "key.frame_timestamp_micros", "key.camera_object_id"
            """,
            [str(camera_box_parquet), FRONT_CAMERA_NAME],
        ).fetchall()
    finally:
        connection.close()
    frame_index = {timestamp: index for index, timestamp in enumerate(frame_timestamps)}
    frames: list[list[dict[str, Any]]] = [[] for _ in frame_timestamps]
    for timestamp, object_id, center_x, center_y, size_x, size_y, label_type in rows:
        index = frame_index.get(int(timestamp))
        category = CAMERA_BOX_TYPES.get(int(label_type))
        if index is None or category is None:
            continue
        frames[index].append(
            {
                "track_id": str(object_id),
                "category": category,
                "center_x": round(float(center_x), 4),
                "center_y": round(float(center_y), 4),
                "width": round(float(size_x), 4),
                "height": round(float(size_y), 4),
            }
        )
    if any(not boxes for boxes in frames):
        raise ValueError("Every FRONT frame must have native camera-box annotations")
    payload = {
        "record_type": "planmargin.sensor_frame_annotations",
        "schema_version": "1.0.0",
        "source": "Waymo Open Dataset v2 Perception camera_box",
        "image_width": 1920,
        "image_height": 1280,
        "frames": [
            {
                "index": index,
                "timestamp_micros": timestamp,
                "boxes": boxes,
            }
            for index, (timestamp, boxes) in enumerate(
                zip(frame_timestamps, frames, strict=True)
            )
        ],
    }
    output.write_text(
        json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    return {"frame_count": len(frames), "box_count": sum(map(len, frames))}


def _yaw_from_pose(matrix: np.ndarray) -> float:
    return float(math.atan2(matrix[1, 0], matrix[0, 0]))


def _trajectory_window(
    poses: list[np.ndarray], source_index: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    positions = np.asarray([pose[:2, 3] for pose in poses], dtype=np.float32)
    yaw = np.asarray([_yaw_from_pose(pose) for pose in poses], dtype=np.float32)
    velocity = np.gradient(positions, 0.1, axis=0).astype(np.float32)
    start = source_index - trajectory_model.HISTORY_STEPS + 1
    stop = source_index + trajectory_model.FUTURE_STEPS + 1
    origin = positions[source_index]
    heading = float(yaw[source_index])
    past_xy = trajectory_model._local_xy(
        positions[start : source_index + 1], origin, heading
    )
    past_velocity = trajectory_model._local_xy(
        velocity[start : source_index + 1], np.zeros(2), heading
    )
    relative_yaw = trajectory_model._wrap_angle(yaw[start : source_index + 1] - heading)
    recorded = trajectory_model._local_xy(
        positions[source_index + 1 : stop], origin, heading
    ).astype(np.float32)
    times = (
        np.arange(1, trajectory_model.FUTURE_STEPS + 1, dtype=np.float32)[:, None]
        * trajectory_model.STEP_SECONDS
    )
    baseline = times * past_velocity[-1]
    features = np.concatenate(
        (
            past_xy.reshape(-1),
            past_velocity.reshape(-1),
            np.sin(relative_yaw),
            np.cos(relative_yaw),
        )
    ).astype(np.float32)[None, :]
    return features, baseline[None, :].reshape(1, -1), recorded


def _opencv_points(
    local_xy: np.ndarray, camera_extrinsic: np.ndarray
) -> list[dict[str, float]]:
    camera_from_vehicle = np.linalg.inv(camera_extrinsic)
    homogeneous = np.column_stack(
        (local_xy, np.zeros(len(local_xy)), np.ones(len(local_xy)))
    )
    camera_waymo = (camera_from_vehicle @ homogeneous.T).T[:, :3]
    opencv = np.column_stack(
        (-camera_waymo[:, 1], -camera_waymo[:, 2], camera_waymo[:, 0])
    )
    return [
        {
            "x": round(float(point[0]), 5),
            "y": round(float(point[1]), 5),
            "z": round(float(point[2]), 5),
        }
        for point in opencv
    ]


def _prepare_trajectory_overlay(
    root: Path, data_directory: Path, output: Path
) -> dict[str, Any]:
    model_directory = root / trajectory_model.DEFAULT_OUTPUT_DIR
    model_path = model_directory / "trajectory-model.pmzip"
    report_path = model_directory / "training-report.json"
    if not model_path.is_file() or not report_path.is_file():
        raise ValueError(
            "Run planmargin-train-trajectory-model before preparing the scene"
        )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("status") != "visualization_qualified":
        raise ValueError(
            "The real WOMD trajectory model is not visualization-qualified"
        )
    if _sha256(model_path) != report.get("model_sha256"):
        raise ValueError("Trajectory model hash does not match its report")
    connection = duckdb.connect()
    try:
        pose_rows = connection.execute(
            """
            SELECT "key.frame_timestamp_micros",
                   "[VehiclePoseComponent].world_from_vehicle.transform"
            FROM read_parquet(?) ORDER BY "key.frame_timestamp_micros"
            """,
            [str(data_directory / "vehicle_pose.parquet")],
        ).fetchall()
        camera_extrinsic = connection.execute(
            """
            SELECT "[CameraCalibrationComponent].extrinsic.transform"
            FROM read_parquet(?) WHERE "key.camera_name" = ?
            """,
            [str(data_directory / "camera_calibration.parquet"), FRONT_CAMERA_NAME],
        ).fetchone()[0]
    finally:
        connection.close()
    if len(pose_rows) != EXPECTED_FRAME_COUNT:
        raise ValueError("Vehicle-pose timeline is incomplete")
    poses = [np.asarray(row[1], dtype=np.float64).reshape(4, 4) for row in pose_rows]
    features, baseline, recorded = _trajectory_window(poses, MOVING_SOURCE_FRAME_INDEX)
    parameters = trajectory_model.load_model(model_path.read_bytes())
    predicted = trajectory_model.predict(parameters, features, baseline).reshape(-1, 2)
    baseline_xy = baseline.reshape(-1, 2)
    prediction_error = np.linalg.norm(predicted - recorded, axis=1)
    baseline_error = np.linalg.norm(baseline_xy - recorded, axis=1)
    extrinsic = np.asarray(camera_extrinsic, dtype=np.float64).reshape(4, 4)
    payload = {
        "record_type": "planmargin.calibrated_sensor_trajectory",
        "schema_version": "1.0.0",
        "source_frame_index": MOVING_SOURCE_FRAME_INDEX,
        "step_seconds": trajectory_model.STEP_SECONDS,
        "history_steps": trajectory_model.HISTORY_STEPS,
        "future_steps": trajectory_model.FUTURE_STEPS,
        "coordinate_system": "apple_sharp_source_camera_opencv",
        "paths": {
            "recorded": _opencv_points(recorded, extrinsic),
            "jax_prediction": _opencv_points(predicted, extrinsic),
            "constant_velocity": _opencv_points(baseline_xy, extrinsic),
        },
        "metrics": {
            "jax_ade_m": round(float(prediction_error.mean()), 6),
            "jax_fde_m": round(float(prediction_error[-1]), 6),
            "constant_velocity_ade_m": round(float(baseline_error.mean()), 6),
            "constant_velocity_fde_m": round(float(baseline_error[-1]), 6),
        },
        "model": {
            "framework": "JAX",
            "training_source": report["source"],
            "status": report["status"],
            "report_sha256": report["report_sha256"],
            "model_sha256": report["model_sha256"],
            "superiority_claim_supported": False,
        },
        "claim_boundary": "The overlay registers a research predictor and recorded ego poses into one WOD Perception frame; it is not a Waymo Driver trajectory or safety claim.",
    }
    output.write_text(
        json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    return payload


def prepare(
    root: Path,
    *,
    generate_sharp: bool = False,
    sharp_command: Path | None = None,
    sharp_checkpoint: Path | None = None,
    device: str = "default",
) -> Path:
    root = root.resolve(strict=True)
    data_directory = root / "data" / "raw" / "perception" / SEGMENT_ID
    camera_parquet = data_directory / "camera_image.parquet"
    camera_box_parquet = data_directory / "camera_box.parquet"
    gaussian_path = (
        root / "artifacts" / "real-3dgs" / "waymo-front" / "099-1552440205262596.ply"
    )
    moving_gaussian_path = (
        root
        / "artifacts"
        / "real-3dgs"
        / "waymo-front-moving"
        / "020-1552440197361693.ply"
    )
    for source in (
        camera_parquet,
        camera_box_parquet,
        data_directory / "lidar.parquet",
        data_directory / "lidar_calibration.parquet",
        data_directory / "vehicle_pose.parquet",
        data_directory / "camera_calibration.parquet",
    ):
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"Required local scene input is missing: {source}")
    frames_directory = data_directory / "front_frames"
    frames_directory.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    try:
        rows = connection.execute(
            """
            SELECT "key.frame_timestamp_micros", "[CameraImageComponent].image"
            FROM read_parquet(?)
            WHERE "key.camera_name" = ?
            ORDER BY "key.frame_timestamp_micros"
            """,
            [str(camera_parquet), FRONT_CAMERA_NAME],
        ).fetchall()
    finally:
        connection.close()
    if len(rows) != EXPECTED_FRAME_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_FRAME_COUNT} FRONT frames, observed {len(rows)}"
        )

    frames: list[dict[str, Any]] = []
    for index, (timestamp_micros, image) in enumerate(rows):
        filename = f"{index:03d}-{int(timestamp_micros)}.jpg"
        frame_path = frames_directory / filename
        payload = bytes(image)
        if not frame_path.exists() or frame_path.read_bytes() != payload:
            frame_path.write_bytes(payload)
        frames.append(
            {
                "index": index,
                "timestamp_micros": int(timestamp_micros),
                "file": filename,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )

    if not gaussian_path.is_file() and generate_sharp:
        if sharp_command is None or not sharp_command.is_file():
            raise ValueError("The Apple SHARP command is unavailable")
        gaussian_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                str(sharp_command),
                "predict",
                "--input-path",
                str(frames_directory / frames[SOURCE_FRAME_INDEX]["file"]),
                "--output-path",
                str(gaussian_path.parent),
                "--device",
                device,
                *(
                    ["--checkpoint-path", str(sharp_checkpoint)]
                    if sharp_checkpoint is not None
                    else []
                ),
            ],
            check=True,
        )
    if not moving_gaussian_path.is_file() and generate_sharp:
        if sharp_command is None or not sharp_command.is_file():
            raise ValueError("The Apple SHARP command is unavailable")
        moving_gaussian_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                str(sharp_command),
                "predict",
                "--input-path",
                str(frames_directory / frames[MOVING_SOURCE_FRAME_INDEX]["file"]),
                "--output-path",
                str(moving_gaussian_path.parent),
                "--device",
                device,
                "--no-render",
                *(
                    ["--checkpoint-path", str(sharp_checkpoint)]
                    if sharp_checkpoint is not None
                    else []
                ),
            ],
            check=True,
        )
    if gaussian_path.is_symlink() or not gaussian_path.is_file():
        raise ValueError(
            "Required SHARP reconstruction is missing; rerun with --generate-sharp"
        )
    if _vertex_count(gaussian_path) != EXPECTED_GAUSSIANS:
        raise ValueError(
            "The SHARP reconstruction does not have the expected Gaussian count"
        )
    if moving_gaussian_path.is_symlink() or not moving_gaussian_path.is_file():
        raise ValueError("Required moving-frame SHARP reconstruction is missing")
    if _vertex_count(moving_gaussian_path) != EXPECTED_GAUSSIANS:
        raise ValueError(
            "The moving-frame SHARP reconstruction has an unexpected count"
        )

    output_directory = root / "artifacts" / "sensor-scene" / "waymo-front"
    output_directory.mkdir(parents=True, exist_ok=True)
    lidar_path = output_directory / "099-lidar-field.ply"
    if not lidar_path.exists():
        _prepare_lidar(data_directory, int(rows[SOURCE_FRAME_INDEX][0]), lidar_path)
    annotations_path = output_directory / "front-camera-boxes.json"
    annotation_counts = _prepare_camera_annotations(
        camera_box_parquet, [int(row[0]) for row in rows], annotations_path
    )
    trajectory_path = output_directory / "020-calibrated-trajectory.json"
    trajectory = _prepare_trajectory_overlay(root, data_directory, trajectory_path)
    manifest = {
        "record_type": "planmargin.sensor_scene_manifest",
        "schema_version": "1.0.0",
        "source": "Waymo Open Dataset v2 Perception",
        "segment_id": SEGMENT_ID,
        "camera_name": "FRONT",
        "camera_enum": FRONT_CAMERA_NAME,
        "frame_count": len(frames),
        "frame_rate_hz": 10,
        "frames_directory": str(frames_directory.relative_to(root)),
        "frames": frames,
        "annotations": {
            "representation": "native_tracked_camera_boxes",
            "file": str(annotations_path.relative_to(root)),
            "bytes": annotations_path.stat().st_size,
            "sha256": _sha256(annotations_path),
            **annotation_counts,
        },
        "reconstruction": {
            "representation": "apple_sharp_3d_gaussian_splatting",
            "source_frame_index": MOVING_SOURCE_FRAME_INDEX,
            "primitive_count": EXPECTED_GAUSSIANS,
            "file": str(moving_gaussian_path.relative_to(root)),
            "bytes": moving_gaussian_path.stat().st_size,
            "sha256": _sha256(moving_gaussian_path),
        },
        "reconstruction_reference": {
            "representation": "apple_sharp_3d_gaussian_splatting",
            "source_frame_index": SOURCE_FRAME_INDEX,
            "primitive_count": EXPECTED_GAUSSIANS,
            "file": str(gaussian_path.relative_to(root)),
            "bytes": gaussian_path.stat().st_size,
            "sha256": _sha256(gaussian_path),
        },
        "lidar": {
            "representation": "same_frame_lidar_gaussian_field",
            "source_frame_index": SOURCE_FRAME_INDEX,
            "primitive_count": _vertex_count(lidar_path),
            "file": str(lidar_path.relative_to(root)),
            "bytes": lidar_path.stat().st_size,
            "sha256": _sha256(lidar_path),
        },
        "trajectory": {
            "representation": "calibrated_recorded_and_jax_predicted_ego_paths",
            "source_frame_index": MOVING_SOURCE_FRAME_INDEX,
            "file": str(trajectory_path.relative_to(root)),
            "bytes": trajectory_path.stat().st_size,
            "sha256": _sha256(trajectory_path),
            "future_steps": trajectory["future_steps"],
            "step_seconds": trajectory["step_seconds"],
            "model_status": trajectory["model"]["status"],
        },
    }
    encoded = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    manifest_path = output_directory / "manifest.json"
    manifest_path.write_text(encoded, encoding="utf-8")
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--generate-sharp", action="store_true")
    parser.add_argument("--sharp-command", type=Path)
    parser.add_argument("--sharp-checkpoint", type=Path)
    parser.add_argument(
        "--device", choices=("default", "cpu", "mps", "cuda"), default="default"
    )
    args = parser.parse_args()
    manifest = prepare(
        args.root,
        generate_sharp=args.generate_sharp,
        sharp_command=args.sharp_command,
        sharp_checkpoint=args.sharp_checkpoint,
        device=args.device,
    )
    print(manifest)


if __name__ == "__main__":
    main()
