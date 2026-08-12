"""Build and score the frozen WOMD empirical-support reference model."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable

import jax
import numpy as np
import tensorflow as tf

from planmargin import behavior_features
from planmargin import scenario_selection

SCHEMA_VERSION = "1.0.0"
SCHEMA_BASE_URI = (
    "https://raw.githubusercontent.com/ethanvillalovoz/planmargin/main/schemas"
)
MANIFEST_SCHEMA_URI = f"{SCHEMA_BASE_URI}/empirical-support-run-manifest-v1.schema.json"
SHARD_SCHEMA_URI = f"{SCHEMA_BASE_URI}/empirical-support-shard-v1.schema.json"
MODEL_SCHEMA_URI = f"{SCHEMA_BASE_URI}/empirical-support-model-v1.schema.json"
REPORT_SCHEMA_URI = f"{SCHEMA_BASE_URI}/empirical-support-report-v1.schema.json"
MANIFEST_TYPE = "planmargin.empirical_support_run_manifest"
SHARD_TYPE = "planmargin.empirical_support_shard_checkpoint"
MODEL_TYPE = "planmargin.empirical_support_model"
REPORT_TYPE = "planmargin.empirical_support_report"

REFERENCE_SHARDS = (
    57,
    104,
    159,
    221,
    278,
    306,
    311,
    407,
    539,
    601,
    638,
    756,
    784,
    813,
    870,
    907,
)
SHARD_SELECTION_SEED = 20260811
REFERENCE_FRACTION = 0.70
NEIGHBOR_COUNT = 5
IQR_FLOOR = 1e-9
SUPPORT_ALPHA = 0.05
MINIMUM_EVENT_COUNT = 160
DEFAULT_OUTPUT_DIR = Path("artifacts/realism/lead-braking-support-v1")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _content_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _seal_record(record: dict[str, Any], field: str) -> dict[str, Any]:
    sealed = dict(record)
    sealed[field] = _content_sha256(record)
    return sealed


def _validate_seal(record: dict[str, Any], field: str) -> None:
    expected = record.get(field)
    if not isinstance(expected, str):
        raise ValueError(f"Checkpoint is missing {field}")
    payload = dict(record)
    del payload[field]
    if _content_sha256(payload) != expected:
        raise ValueError("Checkpoint content hash mismatch")


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(value, allow_nan=False, indent=2, sort_keys=True))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Checkpoint is unreadable: {path}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Checkpoint root must be an object: {path}")
    return value


def validate_private_output_dir(output_dir: Path) -> None:
    artifacts_root = (Path.cwd() / "artifacts").resolve()
    if not output_dir.resolve().is_relative_to(artifacts_root):
        raise ValueError(
            "WOMD-derived records are restricted; --output-dir must remain "
            "under artifacts/."
        )


def _source_provenance() -> dict[str, Any]:
    try:
        git_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        git_worktree_dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        git_commit = None
        git_worktree_dirty = None
    source_files = (
        Path(__file__),
        Path(behavior_features.__file__),
        Path(scenario_selection.__file__),
    )
    return {
        "git_commit": git_commit,
        "git_worktree_dirty": git_worktree_dirty,
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source_files
        },
        "waymax_git_commit": scenario_selection.WAYMAX_GIT_COMMIT,
    }


def build_run_manifest() -> dict[str, Any]:
    """Build the immutable configuration for the fixed reference scan."""
    thresholds = dataclasses.asdict(scenario_selection.SelectionThresholds())
    configuration = {
        "experiment": "womd_lead_braking_empirical_support_v1",
        "dataset": {
            "name": "Waymo Open Motion Dataset",
            "version": scenario_selection.DATASET_VERSION,
            "split": scenario_selection.SPLIT,
            "excluded_development_shards": [0],
            "reference_shards": list(REFERENCE_SHARDS),
            "official_validation_used": False,
            "shard_selection_seed": SHARD_SELECTION_SEED,
        },
        "event_filter": {
            "family": "lead_vehicle_braking",
            "one_best_qualifying_lead_per_scenario": True,
            "controller_or_baseline_filter": False,
            "thresholds": thresholds,
        },
        "features": {
            "schema_version": behavior_features.FEATURE_SCHEMA_VERSION,
            "names": list(behavior_features.FEATURE_NAMES),
            "window_states": behavior_features.WINDOW_STATES,
            "time_interval_s": behavior_features.TIME_INTERVAL_S,
            "one_second_steps": behavior_features.ONE_SECOND_STEPS,
            "nonincrease_tolerance_mps": (behavior_features.NONINCREASE_TOLERANCE_MPS),
            "numeric_dtype": "float64",
        },
        "model": {
            "split_order": "sha256_private_scenario_id_ascending",
            "reference_fraction": REFERENCE_FRACTION,
            "quantile_method": "linear",
            "iqr_floor": IQR_FLOOR,
            "neighbor_count": NEIGHBOR_COUNT,
            "support_alpha": SUPPORT_ALPHA,
            "minimum_event_count": MINIMUM_EVENT_COUNT,
            "ties_included": True,
        },
        "source": _source_provenance(),
    }
    record = {
        "$schema": MANIFEST_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": MANIFEST_TYPE,
        "configuration_fingerprint": _content_sha256(configuration),
        "configuration": configuration,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "numpy": np.__version__,
            "jax": jax.__version__,
            "tensorflow": tf.__version__,
            "jax_backend": jax.default_backend(),
        },
    }
    return _seal_record(record, "manifest_sha256")


def validate_run_manifest(manifest: dict[str, Any]) -> None:
    """Validate the sealed manifest without requiring the original Git checkout."""
    _validate_seal(manifest, "manifest_sha256")
    if (
        manifest.get("$schema") != MANIFEST_SCHEMA_URI
        or manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("record_type") != MANIFEST_TYPE
    ):
        raise ValueError("Unexpected empirical-support run manifest contract")
    configuration = manifest.get("configuration")
    if not isinstance(configuration, dict) or manifest.get(
        "configuration_fingerprint"
    ) != _content_sha256(configuration):
        raise ValueError("Empirical-support configuration fingerprint mismatch")
    try:
        dataset = configuration["dataset"]
        features = configuration["features"]
        model = configuration["model"]
        event_filter = configuration["event_filter"]
    except (KeyError, TypeError) as error:
        raise ValueError(
            "Empirical-support manifest configuration is incomplete"
        ) from error
    if (
        dataset.get("version") != scenario_selection.DATASET_VERSION
        or dataset.get("split") != scenario_selection.SPLIT
        or dataset.get("excluded_development_shards") != [0]
        or dataset.get("reference_shards") != list(REFERENCE_SHARDS)
        or dataset.get("official_validation_used") is not False
        or event_filter.get("controller_or_baseline_filter") is not False
        or features.get("names") != list(behavior_features.FEATURE_NAMES)
        or features.get("numeric_dtype") != "float64"
        or model.get("minimum_event_count") != MINIMUM_EVENT_COUNT
        or model.get("neighbor_count") != NEIGHBOR_COUNT
        or model.get("support_alpha") != SUPPORT_ALPHA
    ):
        raise ValueError("Empirical-support manifest violates the frozen protocol")


def event_key(source: dict[str, Any]) -> str:
    """Return the stable private ordering key for one natural event."""
    scenario_id = source.get("scenario_id")
    if not isinstance(scenario_id, str) or not scenario_id:
        raise ValueError("Event source must contain a private scenario identifier")
    return hashlib.sha256(scenario_id.encode()).hexdigest()


def _mean_k_nearest_distance(
    candidate: np.ndarray,
    reference: np.ndarray,
    *,
    neighbor_count: int = NEIGHBOR_COUNT,
) -> float:
    if reference.ndim != 2 or candidate.shape != (reference.shape[1],):
        raise ValueError("Candidate and reference feature shapes are incompatible")
    if len(reference) < neighbor_count:
        raise ValueError("Reference set is smaller than neighbor_count")
    distances = np.linalg.norm(reference - candidate, axis=1)
    nearest = np.partition(distances, neighbor_count - 1)[:neighbor_count]
    return float(np.mean(nearest, dtype=np.float64))


def fit_model(
    events: Iterable[dict[str, Any]],
    *,
    configuration_fingerprint: str,
) -> dict[str, Any]:
    """Fit the frozen robust-scaled split-conformal 5-NN model."""
    ordered = sorted(events, key=lambda event: event["event_key"])
    if len({event["event_key"] for event in ordered}) != len(ordered):
        raise ValueError("Event keys must be unique")
    if len(ordered) < 8:
        raise ValueError("At least eight events are required to fit the model")
    vectors = np.asarray([event["vector"] for event in ordered], dtype=np.float64)
    if vectors.shape != (len(ordered), len(behavior_features.FEATURE_NAMES)):
        raise ValueError("Event vectors do not match the frozen feature dimension")
    if not np.isfinite(vectors).all():
        raise ValueError("Event vectors must be finite")

    reference_count = int(np.floor(len(ordered) * REFERENCE_FRACTION))
    if reference_count < NEIGHBOR_COUNT or reference_count == len(ordered):
        raise ValueError("Reference/calibration split is not viable")
    reference_vectors = vectors[:reference_count]
    calibration_vectors = vectors[reference_count:]
    median = np.median(reference_vectors, axis=0)
    first_quartile = np.quantile(reference_vectors, 0.25, axis=0, method="linear")
    third_quartile = np.quantile(reference_vectors, 0.75, axis=0, method="linear")
    iqr = third_quartile - first_quartile
    effective_iqr = np.maximum(iqr, IQR_FLOOR)
    scaled_reference = (reference_vectors - median) / effective_iqr
    scaled_calibration = (calibration_vectors - median) / effective_iqr
    calibration_scores = [
        _mean_k_nearest_distance(candidate, scaled_reference)
        for candidate in scaled_calibration
    ]
    model = {
        "feature_names": list(behavior_features.FEATURE_NAMES),
        "numeric_dtype": "float64",
        "split": {
            "ordering": "sha256_private_scenario_id_ascending",
            "reference_fraction": REFERENCE_FRACTION,
            "reference_event_keys": [
                event["event_key"] for event in ordered[:reference_count]
            ],
            "calibration_event_keys": [
                event["event_key"] for event in ordered[reference_count:]
            ],
        },
        "scaling": {
            "median": median.tolist(),
            "first_quartile": first_quartile.tolist(),
            "third_quartile": third_quartile.tolist(),
            "iqr": iqr.tolist(),
            "effective_iqr": effective_iqr.tolist(),
            "iqr_floor": IQR_FLOOR,
            "quantile_method": "linear",
        },
        "neighbor_count": NEIGHBOR_COUNT,
        "support_alpha": SUPPORT_ALPHA,
        "ties_included": True,
        "reference_vectors": reference_vectors.tolist(),
        "calibration_scores": calibration_scores,
    }
    record = {
        "$schema": MODEL_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": MODEL_TYPE,
        "configuration_fingerprint": configuration_fingerprint,
        "event_count": len(ordered),
        "model": model,
        "model_fingerprint": _content_sha256(model),
    }
    return _seal_record(record, "model_sha256")


def validate_model(model_record: dict[str, Any]) -> None:
    """Reject corrupt, non-finite, or internally inconsistent models."""
    _validate_seal(model_record, "model_sha256")
    if (
        model_record.get("$schema") != MODEL_SCHEMA_URI
        or model_record.get("schema_version") != SCHEMA_VERSION
        or model_record.get("record_type") != MODEL_TYPE
    ):
        raise ValueError("Unexpected empirical-support model record type")
    model = model_record.get("model")
    if not isinstance(model, dict) or _content_sha256(model) != model_record.get(
        "model_fingerprint"
    ):
        raise ValueError("Empirical-support model fingerprint mismatch")
    if model.get("feature_names") != list(behavior_features.FEATURE_NAMES):
        raise ValueError("Empirical-support feature names mismatch")
    if (
        model.get("numeric_dtype") != "float64"
        or model.get("neighbor_count") != NEIGHBOR_COUNT
        or model.get("support_alpha") != SUPPORT_ALPHA
        or model.get("ties_included") is not True
    ):
        raise ValueError("Empirical-support frozen model configuration mismatch")
    reference = np.asarray(model.get("reference_vectors"), dtype=np.float64)
    calibration = np.asarray(model.get("calibration_scores"), dtype=np.float64)
    scaling = model.get("scaling", {})
    scale_arrays = [
        np.asarray(scaling.get(name), dtype=np.float64)
        for name in ("median", "iqr", "effective_iqr")
    ]
    dimension = len(behavior_features.FEATURE_NAMES)
    if reference.ndim != 2 or reference.shape[1] != dimension:
        raise ValueError("Empirical-support reference matrix shape mismatch")
    if calibration.ndim != 1 or calibration.size < 1:
        raise ValueError("Empirical-support calibration scores are missing")
    if any(array.shape != (dimension,) for array in scale_arrays):
        raise ValueError("Empirical-support scaling shape mismatch")
    if not all(
        np.isfinite(array).all() for array in [reference, calibration, *scale_arrays]
    ):
        raise ValueError("Empirical-support model contains non-finite values")
    if np.any(scale_arrays[2] < IQR_FLOOR):
        raise ValueError("Empirical-support effective IQR violates the floor")
    split = model.get("split", {})
    if (
        split.get("ordering") != "sha256_private_scenario_id_ascending"
        or split.get("reference_fraction") != REFERENCE_FRACTION
        or scaling.get("iqr_floor") != IQR_FLOOR
        or scaling.get("quantile_method") != "linear"
    ):
        raise ValueError("Empirical-support split or scaling contract mismatch")
    if len(split.get("reference_event_keys", [])) != len(reference):
        raise ValueError("Empirical-support reference membership mismatch")
    if len(split.get("calibration_event_keys", [])) != len(calibration):
        raise ValueError("Empirical-support calibration membership mismatch")
    if model_record.get("event_count") != len(reference) + len(calibration):
        raise ValueError("Empirical-support event count mismatch")


def load_model(path: Path) -> dict[str, Any]:
    """Load and fully validate one private empirical-support model artifact."""
    model_record = _read_json_object(path)
    validate_model(model_record)
    return model_record


def score_vector(
    model_record: dict[str, Any], vector: Iterable[float]
) -> dict[str, Any]:
    """Score one candidate, including calibration ties in the conformal p-value."""
    validate_model(model_record)
    candidate = np.asarray(list(vector), dtype=np.float64)
    dimension = len(behavior_features.FEATURE_NAMES)
    if candidate.shape != (dimension,) or not np.isfinite(candidate).all():
        raise ValueError("Candidate vector must be finite and eight-dimensional")
    model = model_record["model"]
    scaling = model["scaling"]
    median = np.asarray(scaling["median"], dtype=np.float64)
    effective_iqr = np.asarray(scaling["effective_iqr"], dtype=np.float64)
    reference = np.asarray(model["reference_vectors"], dtype=np.float64)
    scaled_reference = (reference - median) / effective_iqr
    scaled_candidate = (candidate - median) / effective_iqr
    nonconformity = _mean_k_nearest_distance(scaled_candidate, scaled_reference)
    calibration = np.asarray(model["calibration_scores"], dtype=np.float64)
    tie_inclusive_count = int(np.count_nonzero(calibration >= nonconformity))
    p_support = (1.0 + tie_inclusive_count) / (len(calibration) + 1.0)
    return {
        "nonconformity": nonconformity,
        "p_support": p_support,
        "constraint": SUPPORT_ALPHA - p_support,
        "passes": bool(p_support >= SUPPORT_ALPHA),
        "tie_inclusive_calibration_count": tie_inclusive_count,
    }


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def _event_from_arrays(
    arrays: scenario_selection.ScenarioArrays,
    candidate: scenario_selection.Candidate,
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    sdc = candidate.sdc_object_index
    lead = candidate.interacting_object_index
    result = behavior_features.extract_object_pair_features(
        x=arrays.x,
        y=arrays.y,
        yaw=arrays.yaw,
        vel_x=arrays.vel_x,
        vel_y=arrays.vel_y,
        valid=arrays.valid,
        sdc_object_index=sdc,
        lead_object_index=lead,
        current_timestep=0,
    )
    if not result.accepted:
        return None, result.rejection_reasons
    assert result.vector is not None
    source = {
        "dataset_version": scenario_selection.DATASET_VERSION,
        "split": scenario_selection.SPLIT,
        "shard_index": candidate.shard_index,
        "record_index": candidate.record_index,
        "scenario_id": candidate.scenario_id,
        "sdc_object_index": sdc,
        "lead_object_index": lead,
    }
    return {
        "event_key": event_key(source),
        "source": source,
        "selection_score": candidate.score,
        "audit_metrics": result.audit_metrics,
        "vector": list(result.vector),
    }, ()


def scan_reference_shard(
    shard_index: int,
    thresholds: scenario_selection.SelectionThresholds,
) -> dict[str, Any]:
    """Stream one complete shard and retain no raw TFRecord payloads."""
    if shard_index not in REFERENCE_SHARDS:
        raise ValueError("Shard is outside the frozen empirical-reference set")
    started = time.perf_counter()
    events: list[dict[str, Any]] = []
    records_scanned = 0
    record_bytes_processed = 0
    parse_rejections = 0
    feature_rejections: Counter[str] = Counter()
    uri = scenario_selection._training_shard_uri(shard_index)
    dataset = tf.data.TFRecordDataset([uri], buffer_size=8 * 1024 * 1024)
    for record_index, serialized_tensor in enumerate(dataset):
        serialized = serialized_tensor.numpy()
        records_scanned += 1
        record_bytes_processed += len(serialized)
        try:
            arrays = scenario_selection._scenario_arrays(serialized)
        except ValueError:
            parse_rejections += 1
            continue
        candidate = scenario_selection._lead_braking_candidate(
            arrays, shard_index, record_index, thresholds
        )
        if candidate is not None:
            event, reasons = _event_from_arrays(arrays, candidate)
            if event is None:
                feature_rejections.update(reasons)
            else:
                events.append(event)
        if records_scanned % 100 == 0:
            print(
                f"shard={shard_index:05d} records={records_scanned} "
                f"events={len(events)}",
                file=sys.stderr,
                flush=True,
            )
    return {
        "records_scanned": records_scanned,
        "record_bytes_processed": record_bytes_processed,
        "parse_rejections": parse_rejections,
        "feature_rejection_counts": dict(sorted(feature_rejections.items())),
        "elapsed_seconds": time.perf_counter() - started,
        "process_peak_rss_bytes": _peak_rss_bytes(),
        "events": events,
    }


def build_shard_checkpoint(
    *,
    shard_index: int,
    configuration_fingerprint: str,
    observation: dict[str, Any],
) -> dict[str, Any]:
    events = observation["events"]
    if len({event["event_key"] for event in events}) != len(events):
        raise ValueError("Shard checkpoint event keys must be unique")
    record = {
        "$schema": SHARD_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": SHARD_TYPE,
        "configuration_fingerprint": configuration_fingerprint,
        "shard_index": shard_index,
        "source_uri": scenario_selection._training_shard_uri(shard_index),
        "status": "completed",
        "metrics": {
            key: observation[key]
            for key in (
                "records_scanned",
                "record_bytes_processed",
                "parse_rejections",
                "feature_rejection_counts",
                "elapsed_seconds",
                "process_peak_rss_bytes",
            )
        },
        "event_count": len(events),
        "events": events,
    }
    return _seal_record(record, "checkpoint_sha256")


def validate_shard_checkpoint(
    record: dict[str, Any], *, shard_index: int, fingerprint: str
) -> None:
    _validate_seal(record, "checkpoint_sha256")
    if (
        record.get("$schema") != SHARD_SCHEMA_URI
        or record.get("schema_version") != SCHEMA_VERSION
        or record.get("record_type") != SHARD_TYPE
        or record.get("status") != "completed"
    ):
        raise ValueError("Unexpected shard checkpoint record type")
    if record.get("configuration_fingerprint") != fingerprint:
        raise ValueError("Shard checkpoint configuration mismatch")
    if record.get("shard_index") != shard_index:
        raise ValueError("Shard checkpoint identity mismatch")
    if record.get("source_uri") != scenario_selection._training_shard_uri(shard_index):
        raise ValueError("Shard checkpoint source URI mismatch")
    events = record.get("events")
    if not isinstance(events, list) or record.get("event_count") != len(events):
        raise ValueError("Shard checkpoint event count mismatch")
    keys = [event.get("event_key") for event in events]
    if len(set(keys)) != len(keys):
        raise ValueError("Shard checkpoint contains duplicate event keys")
    if any(
        event.get("event_key") != event_key(event.get("source", {}))
        or event.get("source", {}).get("shard_index") != shard_index
        for event in events
    ):
        raise ValueError("Shard checkpoint event identity mismatch")
    vectors = np.asarray([event.get("vector") for event in events], dtype=np.float64)
    if len(events) and (
        vectors.shape != (len(events), len(behavior_features.FEATURE_NAMES))
        or not np.isfinite(vectors).all()
    ):
        raise ValueError("Shard checkpoint contains invalid feature vectors")
    for event, vector in zip(events, vectors):
        audit_metrics = event.get("audit_metrics", {})
        try:
            audit_vector = np.asarray(
                [audit_metrics[name] for name in behavior_features.FEATURE_NAMES],
                dtype=np.float64,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Shard checkpoint audit metrics are incomplete") from error
        try:
            selection_score = float(event.get("selection_score"))
        except (TypeError, ValueError) as error:
            raise ValueError("Shard checkpoint selection score is invalid") from error
        if not np.array_equal(vector, audit_vector) or not np.isfinite(selection_score):
            raise ValueError("Shard checkpoint audit metrics do not match its vector")


def _aggregate_quantiles(values: np.ndarray) -> dict[str, float]:
    return {
        name: float(value)
        for name, value in zip(
            ("minimum", "q25", "median", "q75", "maximum"),
            np.quantile(values, (0.0, 0.25, 0.5, 0.75, 1.0), method="linear"),
        )
    }


def build_report(
    manifest: dict[str, Any],
    checkpoints: list[dict[str, Any]],
    model_record: dict[str, Any] | None,
) -> dict[str, Any]:
    events = [event for checkpoint in checkpoints for event in checkpoint["events"]]
    event_count = len(events)
    enough_events = event_count >= MINIMUM_EVENT_COUNT
    all_shards_complete = [
        checkpoint["shard_index"] for checkpoint in checkpoints
    ] == list(REFERENCE_SHARDS)
    vectors_finite = all(
        np.isfinite(np.asarray(event["vector"], dtype=np.float64)).all()
        for event in events
    )
    unique_events = len({event["event_key"] for event in events}) == event_count
    model_valid = False
    if model_record is not None:
        try:
            validate_model(model_record)
            model_valid = (
                model_record["configuration_fingerprint"]
                == manifest["configuration_fingerprint"]
                and model_record["event_count"] == event_count
            )
        except ValueError:
            model_valid = False
    gates = {
        "fixed_shards_complete": all_shards_complete,
        "minimum_160_events": enough_events,
        "event_keys_unique": unique_events,
        "feature_vectors_finite": vectors_finite,
        "model_valid": model_valid,
        "official_validation_untouched": True,
        "no_controller_or_baseline_filter": True,
    }
    decision = "support_gate_ready" if all(gates.values()) else "no_go"
    feature_quantiles: dict[str, Any] = {}
    if events:
        vectors = np.asarray([event["vector"] for event in events], dtype=np.float64)
        feature_quantiles = {
            name: _aggregate_quantiles(vectors[:, index])
            for index, name in enumerate(behavior_features.FEATURE_NAMES)
        }
    calibration_quantiles = None
    calibration_pass_threshold = None
    if model_record is not None and model_valid:
        calibration_scores = np.asarray(
            model_record["model"]["calibration_scores"], dtype=np.float64
        )
        calibration_quantiles = _aggregate_quantiles(calibration_scores)
        required_tail_count = max(
            0,
            int(np.ceil(SUPPORT_ALPHA * (len(calibration_scores) + 1) - 1)),
        )
        if required_tail_count:
            calibration_pass_threshold = float(
                np.sort(calibration_scores)[::-1][required_tail_count - 1]
            )
    feature_rejection_counts: Counter[str] = Counter()
    for checkpoint in checkpoints:
        feature_rejection_counts.update(
            checkpoint["metrics"]["feature_rejection_counts"]
        )
    metrics = {
        "shard_count": len(checkpoints),
        "event_count": event_count,
        "reference_event_count": (
            len(model_record["model"]["split"]["reference_event_keys"])
            if model_valid and model_record is not None
            else 0
        ),
        "calibration_event_count": (
            len(model_record["model"]["split"]["calibration_event_keys"])
            if model_valid and model_record is not None
            else 0
        ),
        "records_scanned": sum(
            checkpoint["metrics"]["records_scanned"] for checkpoint in checkpoints
        ),
        "parse_rejections": sum(
            checkpoint["metrics"]["parse_rejections"] for checkpoint in checkpoints
        ),
        "feature_rejection_counts": dict(sorted(feature_rejection_counts.items())),
        "record_bytes_processed": sum(
            checkpoint["metrics"]["record_bytes_processed"]
            for checkpoint in checkpoints
        ),
        "recorded_work_seconds": sum(
            checkpoint["metrics"]["elapsed_seconds"] for checkpoint in checkpoints
        ),
        "maximum_process_peak_rss_bytes": max(
            (
                checkpoint["metrics"]["process_peak_rss_bytes"]
                for checkpoint in checkpoints
            ),
            default=0,
        ),
        "feature_quantiles": feature_quantiles,
        "calibration_score_quantiles": calibration_quantiles,
        "calibration_pass_nonconformity_threshold": calibration_pass_threshold,
    }
    record = {
        "$schema": REPORT_SCHEMA_URI,
        "schema_version": SCHEMA_VERSION,
        "record_type": REPORT_TYPE,
        "configuration_fingerprint": manifest["configuration_fingerprint"],
        "status": "completed",
        "decision": decision,
        "integrity_gates": gates,
        "metrics": metrics,
        "limitations": [
            "This is support under a bounded WOMD training sample, not a density estimate or safety probability.",
            "WOMD is an unlabeled mixture of manually and autonomously driven trajectories.",
            "No shards or event thresholds may be changed in response to this result.",
        ],
    }
    return _seal_record(record, "report_sha256")


ShardScanner = Callable[[int, scenario_selection.SelectionThresholds], dict[str, Any]]


def run(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    scanner: ShardScanner = scan_reference_shard,
    max_new_shards: int | None = None,
) -> dict[str, Any]:
    """Resume the exact scan, then atomically write and independently audit it."""
    validate_private_output_dir(output_dir)
    if max_new_shards is not None and max_new_shards < 0:
        raise ValueError("max_new_shards must be non-negative")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "run-manifest.json"
    current_manifest = build_run_manifest()
    if manifest_path.exists():
        manifest = _read_json_object(manifest_path)
        validate_run_manifest(manifest)
        if manifest != current_manifest:
            raise ValueError("Existing run manifest does not match this invocation")
    else:
        manifest = current_manifest
        _atomic_write_json(manifest_path, manifest)
    fingerprint = manifest["configuration_fingerprint"]
    thresholds = scenario_selection.SelectionThresholds()
    checkpoints: list[dict[str, Any]] = []
    new_shards = 0
    checkpoint_dir = output_dir / "shards"
    for shard_index in REFERENCE_SHARDS:
        checkpoint_path = checkpoint_dir / f"shard-{shard_index:05d}.json"
        if checkpoint_path.exists():
            checkpoint = _read_json_object(checkpoint_path)
            validate_shard_checkpoint(
                checkpoint, shard_index=shard_index, fingerprint=fingerprint
            )
            checkpoints.append(checkpoint)
            continue
        if max_new_shards is not None and new_shards >= max_new_shards:
            return {
                "status": "in_progress",
                "completed_shards": len(checkpoints),
                "remaining_shards": len(REFERENCE_SHARDS) - len(checkpoints),
                "event_count_so_far": sum(
                    checkpoint["event_count"] for checkpoint in checkpoints
                ),
            }
        print(
            f"Scanning frozen shard {shard_index:05d}...", file=sys.stderr, flush=True
        )
        observation = scanner(shard_index, thresholds)
        checkpoint = build_shard_checkpoint(
            shard_index=shard_index,
            configuration_fingerprint=fingerprint,
            observation=observation,
        )
        validate_shard_checkpoint(
            checkpoint, shard_index=shard_index, fingerprint=fingerprint
        )
        _atomic_write_json(checkpoint_path, checkpoint)
        checkpoints.append(checkpoint)
        new_shards += 1
        print(
            f"Completed shard {shard_index:05d}: {checkpoint['event_count']} events",
            file=sys.stderr,
            flush=True,
        )

    events = [event for checkpoint in checkpoints for event in checkpoint["events"]]
    if len(events) < 8:
        model_record = None
    else:
        model_record = fit_model(events, configuration_fingerprint=fingerprint)
        validate_model(model_record)
        _atomic_write_json(output_dir / "model.json", model_record)
    report = build_report(manifest, checkpoints, model_record)
    _atomic_write_json(output_dir / "report.json", report)
    audit_completed_run(output_dir)
    return report


def audit_completed_run(output_dir: Path) -> dict[str, Any]:
    """Rebuild every aggregate from sealed checkpoints and compare exactly."""
    validate_private_output_dir(output_dir)
    manifest = _read_json_object(output_dir / "run-manifest.json")
    validate_run_manifest(manifest)
    fingerprint = manifest["configuration_fingerprint"]
    checkpoints = []
    for shard_index in REFERENCE_SHARDS:
        checkpoint = _read_json_object(
            output_dir / "shards" / f"shard-{shard_index:05d}.json"
        )
        validate_shard_checkpoint(
            checkpoint, shard_index=shard_index, fingerprint=fingerprint
        )
        checkpoints.append(checkpoint)
    events = [event for checkpoint in checkpoints for event in checkpoint["events"]]
    model_path = output_dir / "model.json"
    model_record = load_model(model_path) if model_path.exists() else None
    if model_record is not None:
        expected_model = fit_model(events, configuration_fingerprint=fingerprint)
        if model_record != expected_model:
            raise ValueError("Completed model does not match durable checkpoints")
    report = _read_json_object(output_dir / "report.json")
    _validate_seal(report, "report_sha256")
    expected_report = build_report(manifest, checkpoints, model_record)
    if report != expected_report:
        raise ValueError("Completed report does not match durable checkpoints")
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the frozen WOMD empirical-support reference model."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--max-new-shards",
        type=int,
        default=None,
        help="Stop after this many new durable shard checkpoints.",
    )
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="Recompute and verify a completed run without reading WOMD.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    result = (
        audit_completed_run(args.output_dir)
        if args.audit_only
        else run(args.output_dir, max_new_shards=args.max_new_shards)
    )
    summary = {
        "status": result["status"],
        "decision": result.get("decision"),
        "completed_shards": result.get(
            "completed_shards", result.get("metrics", {}).get("shard_count")
        ),
        "event_count": result.get(
            "event_count_so_far", result.get("metrics", {}).get("event_count")
        ),
    }
    print(json.dumps(summary, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
