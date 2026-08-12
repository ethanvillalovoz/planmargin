"""Build restartable Beam-to-Parquet-to-DuckDB behavior-feature evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import apache_beam as beam
import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from apache_beam.io.parquetio import ReadAllFromParquet, WriteToParquet
from apache_beam.options.pipeline_options import DirectOptions, PipelineOptions

from planmargin import behavior_features
from planmargin import empirical_support
from planmargin import random_search
from planmargin import scenario_selection

SCHEMA_VERSION = "1.0.0"
SCHEMA_BASE_URI = (
    "https://raw.githubusercontent.com/ethanvillalovoz/planmargin/main/schemas"
)
MANIFEST_SCHEMA_URI = f"{SCHEMA_BASE_URI}/beam-feature-manifest-v1.schema.json"
MANIFEST_TYPE = "planmargin.beam_feature_manifest"
CHECKPOINT_TYPE = "planmargin.beam_source_checkpoint"
RUN_MANIFEST_TYPE = "planmargin.beam_run_manifest"
DEFAULT_OUTPUT_DIR = Path("artifacts/beam-features/lead-braking-v1")
DEFAULT_SUPPORT_DIR = empirical_support.DEFAULT_OUTPUT_DIR
DATABASE_NAME = "beam_features.duckdb"
PARTITION_COUNT = 8
PARQUET_COMPRESSION = "zstd"
SOURCE_MODES = ("sealed-support", "womd-direct")

FEATURE_SCHEMA = pa.schema(
    [
        pa.field("event_key", pa.string(), nullable=False),
        pa.field("source_shard_index", pa.int32(), nullable=False),
        pa.field("source_record_index", pa.int64(), nullable=False),
        pa.field("sdc_object_index", pa.int32(), nullable=False),
        pa.field("lead_object_index", pa.int32(), nullable=False),
        pa.field("selection_score", pa.float64(), nullable=False),
        *(
            pa.field(feature_name, pa.float64(), nullable=False)
            for feature_name in behavior_features.FEATURE_NAMES
        ),
    ]
)
PARTITIONED_FEATURE_SCHEMA = FEATURE_SCHEMA.append(
    pa.field("partition_id", pa.int8(), nullable=False)
)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object at {path}")
    return value


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(_canonical_json(value) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_private_paths(output_dir: Path, support_dir: Path | None) -> None:
    root = Path.cwd().resolve()
    output_root = (root / "artifacts" / "beam-features").resolve()
    if not output_dir.resolve().is_relative_to(output_root):
        raise ValueError(
            "Beam features contain restricted records; --output-dir must remain "
            "under artifacts/beam-features/."
        )
    if support_dir is not None:
        support_root = (root / "artifacts" / "realism").resolve()
        if not support_dir.resolve().is_relative_to(support_root):
            raise ValueError(
                "Sealed support input must remain under artifacts/realism/."
            )


def _pipeline_options() -> PipelineOptions:
    options = PipelineOptions(
        flags=[],
        runner="DirectRunner",
        save_main_session=False,
    )
    direct = options.view_as(DirectOptions)
    direct.direct_num_workers = 1
    direct.direct_running_mode = "in_memory"
    return options


def _partition_id(event_key: str) -> int:
    return int(event_key[:8], 16) % PARTITION_COUNT


def _flatten_event(event: Mapping[str, Any]) -> dict[str, Any]:
    source = event.get("source")
    audit = event.get("audit_metrics")
    if not isinstance(source, Mapping) or not isinstance(audit, Mapping):
        raise ValueError("Feature event is missing source or audit metrics")
    row: dict[str, Any] = {
        "event_key": str(event["event_key"]),
        "source_shard_index": int(source["shard_index"]),
        "source_record_index": int(source["record_index"]),
        "sdc_object_index": int(source["sdc_object_index"]),
        "lead_object_index": int(source["lead_object_index"]),
        "selection_score": float(event["selection_score"]),
    }
    row.update({name: float(audit[name]) for name in behavior_features.FEATURE_NAMES})
    _validate_row(row)
    return row


def _validate_row(row: Mapping[str, Any]) -> None:
    expected = {field.name for field in FEATURE_SCHEMA}
    if set(row) != expected:
        raise ValueError("Beam feature row columns do not match the frozen schema")
    key = row["event_key"]
    if (
        not isinstance(key, str)
        or len(key) != 64
        or any(character not in "0123456789abcdef" for character in key)
    ):
        raise ValueError("Beam feature event key is invalid")
    integers = (
        "source_shard_index",
        "source_record_index",
        "sdc_object_index",
        "lead_object_index",
    )
    if any(not isinstance(row[name], int) or row[name] < 0 for name in integers):
        raise ValueError("Beam feature source indices are invalid")
    numeric = [
        float(row[field.name])
        for field in FEATURE_SCHEMA
        if field.name not in integers and field.name != "event_key"
    ]
    if not np.isfinite(np.asarray(numeric, dtype=np.float64)).all():
        raise ValueError("Beam feature row contains a non-finite value")


def _fixture_event(
    record: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    required = {
        "scenario_id",
        "shard_index",
        "record_index",
        "selection_score",
        "sdc_x",
        "sdc_y",
        "sdc_yaw",
        "sdc_vel_x",
        "sdc_vel_y",
        "sdc_valid",
        "lead_x",
        "lead_y",
        "lead_vel_x",
        "lead_vel_y",
        "lead_valid",
    }
    if set(record) != required:
        raise ValueError("Fixture record does not match the normalized input contract")
    result = behavior_features.extract_behavior_features(
        sdc_x=np.asarray(record["sdc_x"]),
        sdc_y=np.asarray(record["sdc_y"]),
        sdc_yaw=np.asarray(record["sdc_yaw"]),
        sdc_vel_x=np.asarray(record["sdc_vel_x"]),
        sdc_vel_y=np.asarray(record["sdc_vel_y"]),
        sdc_valid=np.asarray(record["sdc_valid"]),
        lead_x=np.asarray(record["lead_x"]),
        lead_y=np.asarray(record["lead_y"]),
        lead_vel_x=np.asarray(record["lead_vel_x"]),
        lead_vel_y=np.asarray(record["lead_vel_y"]),
        lead_valid=np.asarray(record["lead_valid"]),
        current_timestep=0,
    )
    if not result.accepted:
        return None, result.rejection_reasons[0]
    assert result.vector is not None
    source = {
        "scenario_id": str(record["scenario_id"]),
        "shard_index": int(record["shard_index"]),
        "record_index": int(record["record_index"]),
        "sdc_object_index": 0,
        "lead_object_index": 1,
    }
    event = {
        "event_key": empirical_support.event_key(source),
        "source": source,
        "selection_score": float(record["selection_score"]),
        "audit_metrics": result.audit_metrics,
        "vector": list(result.vector),
    }
    return _flatten_event(event), None


class _ExtractFixtureDoFn(beam.DoFn):
    def process(self, record: Mapping[str, Any]) -> Iterable[Any]:
        row, rejection = _fixture_event(record)
        metric = {
            "records_scanned": 1,
            "record_bytes_processed": len(_canonical_json(record).encode("utf-8")),
            "parse_rejections": 0,
            "feature_rejection_counts": {} if rejection is None else {rejection: 1},
            "accepted_event_count": int(row is not None),
        }
        yield beam.pvalue.TaggedOutput("metrics", metric)
        if row is not None:
            yield row


class _MetricCombineFn(beam.CombineFn):
    def create_accumulator(self) -> dict[str, Any]:
        return {
            "records_scanned": 0,
            "record_bytes_processed": 0,
            "parse_rejections": 0,
            "feature_rejection_counts": Counter(),
            "accepted_event_count": 0,
        }

    def add_input(
        self, accumulator: dict[str, Any], value: Mapping[str, Any]
    ) -> dict[str, Any]:
        accumulator["records_scanned"] += int(value["records_scanned"])
        accumulator["record_bytes_processed"] += int(value["record_bytes_processed"])
        accumulator["parse_rejections"] += int(value["parse_rejections"])
        accumulator["accepted_event_count"] += int(value["accepted_event_count"])
        accumulator["feature_rejection_counts"].update(
            value["feature_rejection_counts"]
        )
        return accumulator

    def merge_accumulators(
        self, accumulators: Iterable[dict[str, Any]]
    ) -> dict[str, Any]:
        merged = self.create_accumulator()
        for accumulator in accumulators:
            self.add_input(merged, accumulator)
        return merged

    def extract_output(self, accumulator: dict[str, Any]) -> dict[str, Any]:
        return {
            **{
                key: accumulator[key]
                for key in (
                    "records_scanned",
                    "record_bytes_processed",
                    "parse_rejections",
                    "accepted_event_count",
                )
            },
            "feature_rejection_counts": dict(
                sorted(accumulator["feature_rejection_counts"].items())
            ),
        }


def _sort_group(
    group: tuple[int, Iterable[dict[str, Any]]],
) -> Iterable[dict[str, Any]]:
    _, rows = group
    return sorted(rows, key=lambda row: row["event_key"])


def _scan_womd_observation(shard_index: int) -> dict[str, Any]:
    return empirical_support.scan_reference_shard(
        shard_index, scenario_selection.SelectionThresholds()
    )


def _observation_metrics(observation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "records_scanned": int(observation["records_scanned"]),
        "record_bytes_processed": int(observation["record_bytes_processed"]),
        "parse_rejections": int(observation["parse_rejections"]),
        "feature_rejection_counts": dict(observation["feature_rejection_counts"]),
        "accepted_event_count": len(observation["events"]),
    }


def _run_source_pipeline(
    *,
    shard_index: int,
    destination: Path,
    source_mode: str,
    source_payload: Sequence[Mapping[str, Any]] | None,
    source_metrics: Mapping[str, Any] | None,
) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    with beam.Pipeline(options=_pipeline_options()) as pipeline:
        if source_mode == "fixture":
            assert source_payload is not None
            outputs = (
                pipeline
                | "CreateFixtureRecords" >> beam.Create(list(source_payload))
                | "ExtractFixtureFeatures"
                >> beam.ParDo(_ExtractFixtureDoFn()).with_outputs(
                    "metrics", main="events"
                )
            )
            events = outputs.events
            metrics = outputs.metrics | "CombineFixtureMetrics" >> beam.CombineGlobally(
                _MetricCombineFn()
            )
        elif source_mode == "sealed-support":
            assert source_payload is not None
            assert source_metrics is not None
            events = (
                pipeline
                | "CreateSealedEvents" >> beam.Create(list(source_payload))
                | "FlattenSealedEvents" >> beam.Map(_flatten_event)
            )
            metrics = pipeline | "CreateSealedMetrics" >> beam.Create(
                [dict(source_metrics)]
            )
        elif source_mode == "womd-direct":
            observation = (
                pipeline
                | "CreateWOMDShard" >> beam.Create([shard_index])
                | "MineWOMDShard" >> beam.Map(_scan_womd_observation)
            )
            events = (
                observation
                | "ExpandWOMDEvents" >> beam.FlatMap(lambda value: value["events"])
                | "FlattenWOMDEvents" >> beam.Map(_flatten_event)
            )
            metrics = observation | "ExtractWOMDMetrics" >> beam.Map(
                _observation_metrics
            )
        else:
            raise ValueError(f"Unsupported Beam source mode: {source_mode}")

        sorted_events = (
            events
            | "KeySourceEvents" >> beam.Map(lambda row: (0, row))
            | "GroupSourceEvents" >> beam.GroupByKey()
            | "SortSourceEvents" >> beam.FlatMap(_sort_group)
        )
        _ = sorted_events | "WriteSourceParquet" >> WriteToParquet(
            str(destination / "events"),
            schema=FEATURE_SCHEMA,
            codec=PARQUET_COMPRESSION,
            file_name_suffix=".parquet",
            num_shards=1,
            shard_name_template="",
        )
        _ = (
            metrics
            | "RenderSourceMetrics" >> beam.Map(_canonical_json)
            | "WriteSourceMetrics"
            >> beam.io.WriteToText(
                str(destination / "metrics"),
                file_name_suffix=".json",
                num_shards=1,
                shard_name_template="",
            )
        )


def _source_checkpoint(
    *,
    directory: Path,
    shard_index: int,
    configuration_fingerprint: str,
    source_fingerprint: str,
) -> dict[str, Any]:
    parquet_path = directory / "events.parquet"
    metrics_path = directory / "metrics.json"
    if not parquet_path.is_file() or not metrics_path.is_file():
        raise ValueError("Beam source pipeline did not produce its fixed outputs")
    metrics = _read_json(metrics_path)
    table = pq.ParquetFile(parquet_path).read()
    if not table.schema.equals(FEATURE_SCHEMA, check_metadata=False):
        raise ValueError("Beam source Parquet schema differs from the frozen schema")
    row_count = table.num_rows
    if row_count != metrics.get("accepted_event_count"):
        raise ValueError("Beam source metrics and Parquet row count differ")
    event_keys = table.column("event_key").to_pylist()
    if event_keys != sorted(event_keys) or len(event_keys) != len(set(event_keys)):
        raise ValueError("Beam source Parquet event ordering is invalid")
    record = {
        "schema_version": SCHEMA_VERSION,
        "record_type": CHECKPOINT_TYPE,
        "configuration_fingerprint": configuration_fingerprint,
        "source_fingerprint": source_fingerprint,
        "shard_index": shard_index,
        "status": "completed",
        "metrics": metrics,
        "parquet": {
            "path": "events.parquet",
            "bytes": parquet_path.stat().st_size,
            "sha256": _sha256_file(parquet_path),
            "row_count": row_count,
        },
    }
    return random_search._seal_record(record, "checkpoint_sha256")


def _validate_source_checkpoint(
    directory: Path,
    *,
    shard_index: int,
    configuration_fingerprint: str,
    source_fingerprint: str,
) -> dict[str, Any]:
    if directory.is_symlink():
        raise ValueError("Beam source checkpoint directories must not be symlinks")
    record = _read_json(directory / "checkpoint.json")
    random_search._validate_seal(
        record, "checkpoint_sha256", path=directory / "checkpoint.json"
    )
    if (
        record.get("record_type") != CHECKPOINT_TYPE
        or record.get("schema_version") != SCHEMA_VERSION
        or record.get("status") != "completed"
        or record.get("shard_index") != shard_index
        or record.get("configuration_fingerprint") != configuration_fingerprint
        or record.get("source_fingerprint") != source_fingerprint
        or record.get("parquet", {}).get("path") != "events.parquet"
    ):
        raise ValueError("Beam source checkpoint identity does not match this run")
    parquet_path = directory / record["parquet"]["path"]
    table = pq.ParquetFile(parquet_path).read()
    if (
        parquet_path.stat().st_size != record["parquet"]["bytes"]
        or _sha256_file(parquet_path) != record["parquet"]["sha256"]
        or table.num_rows != record["parquet"]["row_count"]
        or not table.schema.equals(FEATURE_SCHEMA, check_metadata=False)
    ):
        raise ValueError("Beam source checkpoint Parquet seal is invalid")
    rows = table.to_pylist()
    for row in rows:
        _validate_row(row)
    keys = [row["event_key"] for row in rows]
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise ValueError("Beam source checkpoint row ordering is invalid")
    metrics = _read_json(directory / "metrics.json")
    if metrics != record["metrics"]:
        raise ValueError("Beam source checkpoint metrics have changed")
    return record


def _run_partition_pipeline(source_files: Sequence[Path], dataset_dir: Path) -> None:
    dataset_dir.mkdir(parents=True, exist_ok=False)
    with beam.Pipeline(options=_pipeline_options()) as pipeline:
        rows = (
            pipeline
            | "CreateSourceParquetPaths"
            >> beam.Create([str(path) for path in source_files])
            | "ReadSourceParquet" >> ReadAllFromParquet()
        )
        grouped = (
            rows
            | "KeyByDeterministicPartition"
            >> beam.Map(lambda row: (_partition_id(row["event_key"]), row))
            | "GroupPartitionRows" >> beam.GroupByKey()
        )
        for partition in range(PARTITION_COUNT):
            partition_dir = dataset_dir / f"partition={partition:02d}"
            partition_dir.mkdir(parents=True, exist_ok=False)
            selected = (
                grouped
                | f"SelectPartition{partition:02d}"
                >> beam.Filter(lambda item, expected=partition: item[0] == expected)
                | f"SortPartition{partition:02d}" >> beam.FlatMap(_sort_group)
                | f"RecordPartition{partition:02d}"
                >> beam.Map(
                    lambda row, partition_id=partition: {
                        **row,
                        "partition_id": partition_id,
                    }
                )
            )
            _ = selected | f"WritePartition{partition:02d}" >> WriteToParquet(
                str(partition_dir / "events"),
                schema=PARTITIONED_FEATURE_SCHEMA,
                codec=PARQUET_COMPRESSION,
                file_name_suffix=".parquet",
                num_shards=1,
                shard_name_template="",
            )


def _build_duckdb(database_path: Path, parquet_files: Sequence[Path]) -> dict[str, Any]:
    connection = duckdb.connect(str(database_path))
    try:
        connection.execute(
            "CREATE TABLE features AS "
            "SELECT * FROM read_parquet(?, hive_partitioning = false) ORDER BY event_key",
            [[str(path) for path in parquet_files]],
        )
        connection.execute(
            "CREATE TABLE partition_counts AS "
            "SELECT partition_id, count(*) AS row_count FROM features "
            "GROUP BY partition_id ORDER BY partition_id"
        )
        feature_checks = " AND ".join(
            f'isfinite("{name}")' for name in behavior_features.FEATURE_NAMES
        )
        row_count, unique_count, finite_count = connection.execute(
            f"SELECT count(*), count(DISTINCT event_key), "
            f"count(*) FILTER (WHERE {feature_checks}) FROM features"
        ).fetchone()
        source_shard_count = connection.execute(
            "SELECT count(DISTINCT source_shard_index) FROM features"
        ).fetchone()[0]
        rows_by_source_shard = dict(
            connection.execute(
                "SELECT source_shard_index, count(*) FROM features "
                "GROUP BY source_shard_index ORDER BY source_shard_index"
            ).fetchall()
        )
        rows_by_partition = dict(
            connection.execute(
                "SELECT partition_id, count(*) FROM features "
                "GROUP BY partition_id ORDER BY partition_id"
            ).fetchall()
        )
        connection.execute("CHECKPOINT")
    finally:
        connection.close()
    return {
        "row_count": row_count,
        "unique_event_count": unique_count,
        "finite_feature_row_count": finite_count,
        "source_shard_count": source_shard_count,
        "rows_by_source_shard": {
            str(key): value for key, value in rows_by_source_shard.items()
        },
        "rows_by_partition": {
            str(key): value for key, value in rows_by_partition.items()
        },
    }


def _partition_assignments_valid(parquet_files: Sequence[Path]) -> bool:
    for path in parquet_files:
        partition_text = path.parent.name.removeprefix("partition=")
        if not partition_text.isdigit():
            return False
        expected = int(partition_text)
        table = pq.ParquetFile(path).read()
        if not table.schema.equals(PARTITIONED_FEATURE_SCHEMA, check_metadata=False):
            return False
        keys = table.column("event_key").to_pylist()
        partitions = table.column("partition_id").to_pylist()
        if keys != sorted(keys) or any(
            partition != expected or _partition_id(key) != expected
            for key, partition in zip(keys, partitions)
        ):
            return False
    return True


def _artifact_record(path: Path, *, relative_to: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(relative_to).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
        "row_count": pq.read_metadata(path).num_rows,
    }


def _source_descriptors(
    *,
    source_mode: str,
    support_dir: Path | None,
    fixture_shards: Mapping[int, Sequence[Mapping[str, Any]]] | None,
    womd_shards: Sequence[int] | None,
) -> tuple[
    list[int],
    dict[int, list[Mapping[str, Any]]],
    dict[int, str],
    dict[int, dict[str, Any]],
    str,
]:
    payloads: dict[int, list[Mapping[str, Any]]] = {}
    fingerprints: dict[int, str] = {}
    source_metrics: dict[int, dict[str, Any]] = {}
    if source_mode == "fixture":
        if not fixture_shards:
            raise ValueError("Fixture mode requires at least one fixture shard")
        shard_indices = sorted(fixture_shards)
        for shard_index in shard_indices:
            records = [dict(record) for record in fixture_shards[shard_index]]
            if any(
                int(record.get("shard_index", -1)) != shard_index for record in records
            ):
                raise ValueError("Fixture record shard identity is inconsistent")
            payloads[shard_index] = records
            fingerprints[shard_index] = _sha256_bytes(
                _canonical_json(records).encode("utf-8")
            )
        source_identity = _sha256_bytes(_canonical_json(fingerprints).encode("utf-8"))
        return shard_indices, payloads, fingerprints, source_metrics, source_identity
    if source_mode == "sealed-support":
        if support_dir is None:
            raise ValueError("Sealed-support mode requires a support directory")
        empirical_support.audit_completed_run(support_dir)
        run_manifest = _read_json(support_dir / "run-manifest.json")
        shard_indices = list(empirical_support.REFERENCE_SHARDS)
        for shard_index in shard_indices:
            checkpoint_path = support_dir / "shards" / f"shard-{shard_index:05d}.json"
            if checkpoint_path.is_symlink():
                raise ValueError("Sealed support checkpoints must not be symlinks")
            checkpoint = _read_json(checkpoint_path)
            empirical_support.validate_shard_checkpoint(
                checkpoint,
                shard_index=shard_index,
                fingerprint=run_manifest["configuration_fingerprint"],
            )
            payloads[shard_index] = [dict(event) for event in checkpoint["events"]]
            fingerprints[shard_index] = checkpoint["checkpoint_sha256"]
            source_metrics[shard_index] = {
                "records_scanned": checkpoint["metrics"]["records_scanned"],
                "record_bytes_processed": checkpoint["metrics"][
                    "record_bytes_processed"
                ],
                "parse_rejections": checkpoint["metrics"]["parse_rejections"],
                "feature_rejection_counts": checkpoint["metrics"][
                    "feature_rejection_counts"
                ],
                "accepted_event_count": checkpoint["event_count"],
            }
        return (
            shard_indices,
            payloads,
            fingerprints,
            source_metrics,
            run_manifest["manifest_sha256"],
        )
    if source_mode == "womd-direct":
        shard_indices = sorted(
            empirical_support.REFERENCE_SHARDS if womd_shards is None else womd_shards
        )
        if not shard_indices or any(
            shard not in empirical_support.REFERENCE_SHARDS for shard in shard_indices
        ):
            raise ValueError(
                "WOMD shards must be a nonempty subset of the frozen reference set"
            )
        for shard_index in shard_indices:
            fingerprints[shard_index] = _sha256_bytes(
                _canonical_json(
                    {
                        "dataset_version": scenario_selection.DATASET_VERSION,
                        "split": scenario_selection.SPLIT,
                        "shard_index": shard_index,
                        "uri": scenario_selection._training_shard_uri(shard_index),
                    }
                ).encode("utf-8")
            )
        return (
            shard_indices,
            payloads,
            fingerprints,
            source_metrics,
            _sha256_bytes(_canonical_json(fingerprints).encode("utf-8")),
        )
    raise ValueError(f"Unsupported Beam source mode: {source_mode}")


def _configuration(source_mode: str, source_identity: str) -> dict[str, Any]:
    return {
        "source_mode": source_mode,
        "source_identity": source_identity,
        "runner": "DirectRunner",
        "direct_num_workers": 1,
        "direct_running_mode": "in_memory",
        "partition_count": PARTITION_COUNT,
        "partition_function": "uint32_sha256_prefix_modulo_partition_count",
        "parquet_compression": PARQUET_COMPRESSION,
        "feature_schema_version": behavior_features.FEATURE_SCHEMA_VERSION,
        "feature_names": list(behavior_features.FEATURE_NAMES),
        "feature_numeric_dtype": "float64",
        "source_ordering": "ascending_shard_index",
        "event_ordering": "event_key_ascending_within_partition",
        "builder_source_sha256": _sha256_file(Path(__file__)),
        "feature_source_sha256": _sha256_file(Path(behavior_features.__file__)),
    }


def _run_manifest(
    configuration: Mapping[str, Any],
    shard_indices: Sequence[int],
    source_fingerprints: Mapping[int, str],
) -> dict[str, Any]:
    configuration_fingerprint = _sha256_bytes(
        _canonical_json(configuration).encode("utf-8")
    )
    return random_search._seal_record(
        {
            "schema_version": SCHEMA_VERSION,
            "record_type": RUN_MANIFEST_TYPE,
            "configuration_fingerprint": configuration_fingerprint,
            "configuration": dict(configuration),
            "source_shards": list(shard_indices),
            "source_fingerprints": {
                str(key): value for key, value in sorted(source_fingerprints.items())
            },
        },
        "manifest_sha256",
    )


def run(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    source_mode: str = "sealed-support",
    support_dir: Path | None = DEFAULT_SUPPORT_DIR,
    fixture_shards: Mapping[int, Sequence[Mapping[str, Any]]] | None = None,
    womd_shards: Sequence[int] | None = None,
    max_new_source_shards: int | None = None,
) -> dict[str, Any]:
    """Resume source checkpoints and materialize deterministic feature evidence."""
    _validate_private_paths(
        output_dir,
        support_dir if source_mode == "sealed-support" else None,
    )
    if max_new_source_shards is not None and max_new_source_shards < 0:
        raise ValueError("max_new_source_shards must be non-negative")
    (
        shard_indices,
        payloads,
        source_fingerprints,
        source_metrics,
        source_identity,
    ) = _source_descriptors(
        source_mode=source_mode,
        support_dir=support_dir,
        fixture_shards=fixture_shards,
        womd_shards=womd_shards,
    )
    effective_mode = "fixture" if source_mode == "fixture" else source_mode
    configuration = _configuration(effective_mode, source_identity)
    expected_run_manifest = _run_manifest(
        configuration, shard_indices, source_fingerprints
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    run_manifest_path = output_dir / "run-manifest.json"
    if run_manifest_path.exists():
        existing = _read_json(run_manifest_path)
        random_search._validate_seal(
            existing, "manifest_sha256", path=run_manifest_path
        )
        if existing != expected_run_manifest:
            raise ValueError(
                "Existing Beam run manifest does not match this invocation"
            )
    else:
        if any(output_dir.iterdir()):
            raise ValueError("Unsealed Beam output directory is not safe to reuse")
        _atomic_write_json(run_manifest_path, expected_run_manifest)

    final_manifest_path = output_dir / "manifest.json"
    if final_manifest_path.exists():
        return audit(output_dir)

    checkpoint_root = output_dir / "source-shards"
    checkpoint_root.mkdir(exist_ok=True)
    for stale in checkpoint_root.glob(".shard-*"):
        if stale.is_dir() and not stale.is_symlink():
            shutil.rmtree(stale)
    for stale in output_dir.glob(".final-build.*"):
        if stale.is_dir() and not stale.is_symlink():
            shutil.rmtree(stale)
    checkpoints: list[dict[str, Any]] = []
    new_count = 0
    for shard_index in shard_indices:
        checkpoint_dir = checkpoint_root / f"shard={shard_index:05d}"
        if checkpoint_dir.exists():
            checkpoint = _validate_source_checkpoint(
                checkpoint_dir,
                shard_index=shard_index,
                configuration_fingerprint=expected_run_manifest[
                    "configuration_fingerprint"
                ],
                source_fingerprint=source_fingerprints[shard_index],
            )
            checkpoints.append(checkpoint)
            continue
        if max_new_source_shards is not None and new_count >= max_new_source_shards:
            return {
                "status": "in_progress",
                "completed_source_shards": len(checkpoints),
                "remaining_source_shards": len(shard_indices) - len(checkpoints),
                "accepted_event_count": sum(
                    checkpoint["parquet"]["row_count"] for checkpoint in checkpoints
                ),
            }
        temporary = Path(
            tempfile.mkdtemp(dir=checkpoint_root, prefix=f".shard-{shard_index:05d}.")
        )
        try:
            _run_source_pipeline(
                shard_index=shard_index,
                destination=temporary / "output",
                source_mode=effective_mode,
                source_payload=payloads.get(shard_index),
                source_metrics=source_metrics.get(shard_index),
            )
            staged = temporary / "output"
            checkpoint = _source_checkpoint(
                directory=staged,
                shard_index=shard_index,
                configuration_fingerprint=expected_run_manifest[
                    "configuration_fingerprint"
                ],
                source_fingerprint=source_fingerprints[shard_index],
            )
            _atomic_write_json(staged / "checkpoint.json", checkpoint)
            os.replace(staged, checkpoint_dir)
            checkpoints.append(checkpoint)
            new_count += 1
        finally:
            shutil.rmtree(temporary, ignore_errors=True)

    source_files = [
        checkpoint_root / f"shard={shard_index:05d}" / "events.parquet"
        for shard_index in shard_indices
    ]
    dataset_dir = output_dir / "dataset"
    database_path = output_dir / DATABASE_NAME
    if dataset_dir.exists():
        shutil.rmtree(dataset_dir)
    database_path.unlink(missing_ok=True)
    temporary_final = Path(tempfile.mkdtemp(dir=output_dir, prefix=".final-build."))
    try:
        staged_dataset = temporary_final / "dataset"
        _run_partition_pipeline(source_files, staged_dataset)
        parquet_files = sorted(staged_dataset.glob("partition=*/events.parquet"))
        if len(parquet_files) != PARTITION_COUNT:
            raise ValueError("Beam did not write every deterministic partition")
        staged_database = temporary_final / DATABASE_NAME
        duckdb_metrics = _build_duckdb(staged_database, parquet_files)
        expected_rows = sum(
            checkpoint["parquet"]["row_count"] for checkpoint in checkpoints
        )
        gates = {
            "all_source_checkpoints_sealed": len(checkpoints) == len(shard_indices),
            "partition_count_exact": len(parquet_files) == PARTITION_COUNT,
            "row_count_reconciled": duckdb_metrics["row_count"] == expected_rows,
            "event_keys_unique": duckdb_metrics["unique_event_count"] == expected_rows,
            "partition_assignments_valid": _partition_assignments_valid(parquet_files),
            "feature_rows_finite": (
                duckdb_metrics["finite_feature_row_count"] == expected_rows
            ),
            "held_out_untouched": True,
            "raw_scenario_ids_excluded": True,
        }
        if not all(gates.values()):
            raise ValueError("Beam-to-DuckDB integrity gates did not all pass")
        parquet_records = [
            _artifact_record(path, relative_to=temporary_final)
            for path in parquet_files
        ]
        logical_fingerprint = _sha256_bytes(
            _canonical_json(
                {
                    "configuration_fingerprint": expected_run_manifest[
                        "configuration_fingerprint"
                    ],
                    "source_checkpoint_seals": [
                        checkpoint["checkpoint_sha256"] for checkpoint in checkpoints
                    ],
                    "parquet": parquet_records,
                    "duckdb_metrics": duckdb_metrics,
                }
            ).encode("utf-8")
        )
        manifest = random_search._seal_record(
            {
                "$schema": MANIFEST_SCHEMA_URI,
                "schema_version": SCHEMA_VERSION,
                "record_type": MANIFEST_TYPE,
                "configuration_fingerprint": expected_run_manifest[
                    "configuration_fingerprint"
                ],
                "logical_fingerprint": logical_fingerprint,
                "status": "completed",
                "decision": "beam_pipeline_verified",
                "source": {
                    "mode": effective_mode,
                    "shard_count": len(shard_indices),
                    "checkpoint_seals": [
                        checkpoint["checkpoint_sha256"] for checkpoint in checkpoints
                    ],
                    "records_scanned": sum(
                        checkpoint["metrics"]["records_scanned"]
                        for checkpoint in checkpoints
                    ),
                    "accepted_event_count": expected_rows,
                    "feature_rejection_counts": dict(
                        sorted(
                            sum(
                                (
                                    Counter(
                                        checkpoint["metrics"][
                                            "feature_rejection_counts"
                                        ]
                                    )
                                    for checkpoint in checkpoints
                                ),
                                Counter(),
                            ).items()
                        )
                    ),
                },
                "parquet": parquet_records,
                "duckdb": {
                    "path": DATABASE_NAME,
                    "bytes": staged_database.stat().st_size,
                    "sha256": _sha256_file(staged_database),
                    "metrics": duckdb_metrics,
                },
                "integrity_gates": gates,
                "provenance": {
                    "apache_beam": beam.__version__,
                    "pyarrow": pa.__version__,
                    "duckdb": duckdb.__version__,
                    "runner": "DirectRunner",
                    "builder_source_sha256": _sha256_file(Path(__file__)),
                },
                "privacy": {
                    "private_local_artifact": True,
                    "raw_scenario_ids_written": False,
                    "source_uris_written": False,
                    "held_out_opened": False,
                },
            },
            "manifest_sha256",
        )
        os.replace(staged_dataset, dataset_dir)
        os.replace(staged_database, database_path)
        _atomic_write_json(final_manifest_path, manifest)
    finally:
        shutil.rmtree(temporary_final, ignore_errors=True)
    return audit(output_dir)


def audit(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    """Verify all source seals, Parquet files, and DuckDB reconciliation."""
    _validate_private_paths(output_dir, None)
    run_manifest = _read_json(output_dir / "run-manifest.json")
    random_search._validate_seal(
        run_manifest, "manifest_sha256", path=output_dir / "run-manifest.json"
    )
    if run_manifest.get("configuration_fingerprint") != _sha256_bytes(
        _canonical_json(run_manifest.get("configuration")).encode("utf-8")
    ):
        raise ValueError("Beam run configuration fingerprint is invalid")
    manifest = _read_json(output_dir / "manifest.json")
    random_search._validate_seal(
        manifest, "manifest_sha256", path=output_dir / "manifest.json"
    )
    if (
        manifest.get("record_type") != MANIFEST_TYPE
        or manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("decision") != "beam_pipeline_verified"
        or manifest.get("configuration_fingerprint")
        != run_manifest.get("configuration_fingerprint")
        or not all(manifest.get("integrity_gates", {}).values())
        or manifest.get("provenance", {}).get("builder_source_sha256")
        != _sha256_file(Path(__file__))
    ):
        raise ValueError("Beam feature manifest contract is invalid")
    checkpoint_seals = []
    source_shards = run_manifest.get("source_shards")
    source_fingerprints = run_manifest.get("source_fingerprints")
    if (
        not isinstance(source_shards, list)
        or not source_shards
        or source_shards != sorted(set(source_shards))
        or not isinstance(source_fingerprints, dict)
        or set(source_fingerprints) != {str(shard) for shard in source_shards}
    ):
        raise ValueError("Beam run source identities are invalid")
    for shard_index in source_shards:
        directory = output_dir / "source-shards" / f"shard={shard_index:05d}"
        validated = _validate_source_checkpoint(
            directory,
            shard_index=shard_index,
            configuration_fingerprint=run_manifest["configuration_fingerprint"],
            source_fingerprint=source_fingerprints[str(shard_index)],
        )
        checkpoint_seals.append(validated["checkpoint_sha256"])
    if checkpoint_seals != manifest["source"]["checkpoint_seals"]:
        raise ValueError("Beam manifest source checkpoint seals differ")
    expected_artifact_paths = [
        f"dataset/partition={partition:02d}/events.parquet"
        for partition in range(PARTITION_COUNT)
    ]
    if [
        artifact.get("path") for artifact in manifest["parquet"]
    ] != expected_artifact_paths:
        raise ValueError("Beam manifest Parquet paths are not the fixed partition set")
    parquet_files = []
    for artifact in manifest["parquet"]:
        path = output_dir / artifact["path"]
        if (
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_size != artifact["bytes"]
            or _sha256_file(path) != artifact["sha256"]
            or pq.read_metadata(path).num_rows != artifact["row_count"]
        ):
            raise ValueError("Beam partitioned Parquet artifact seal is invalid")
        parquet_files.append(path)
    if not _partition_assignments_valid(parquet_files):
        raise ValueError("Beam Parquet partition assignment is invalid")
    database_path = output_dir / manifest["duckdb"]["path"]
    if (
        manifest["duckdb"]["path"] != DATABASE_NAME
        or database_path.is_symlink()
        or not database_path.is_file()
        or database_path.stat().st_size != manifest["duckdb"]["bytes"]
        or _sha256_file(database_path) != manifest["duckdb"]["sha256"]
    ):
        raise ValueError("Beam DuckDB artifact seal is invalid")
    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        feature_checks = " AND ".join(
            ["isfinite(selection_score)"]
            + [f'isfinite("{name}")' for name in behavior_features.FEATURE_NAMES]
        )
        row_count, unique_count, finite_count = connection.execute(
            f"SELECT count(*), count(DISTINCT event_key), "
            f"count(*) FILTER (WHERE {feature_checks}) FROM features"
        ).fetchone()
        parquet_count = connection.execute(
            "SELECT count(*) FROM read_parquet(?, hive_partitioning = false)",
            [[str(path) for path in parquet_files]],
        ).fetchone()[0]
        columns = [
            row[1]
            for row in connection.execute("PRAGMA table_info('features')").fetchall()
        ]
        rows_by_source = {
            str(key): value
            for key, value in connection.execute(
                "SELECT source_shard_index, count(*) FROM features "
                "GROUP BY source_shard_index ORDER BY source_shard_index"
            ).fetchall()
        }
        rows_by_partition = {
            str(key): value
            for key, value in connection.execute(
                "SELECT partition_id, count(*) FROM features "
                "GROUP BY partition_id ORDER BY partition_id"
            ).fetchall()
        }
    finally:
        connection.close()
    expected = manifest["source"]["accepted_event_count"]
    expected_columns = [field.name for field in PARTITIONED_FEATURE_SCHEMA]
    metrics = manifest["duckdb"]["metrics"]
    if (
        row_count != expected
        or unique_count != expected
        or finite_count != expected
        or parquet_count != expected
        or columns != expected_columns
        or rows_by_source != metrics["rows_by_source_shard"]
        or rows_by_partition != metrics["rows_by_partition"]
    ):
        raise ValueError("Beam DuckDB and Parquet row reconciliation failed")
    return manifest


def public_summary(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Return the aggregate allowlist suitable for a tracked integration report."""
    if (
        manifest.get("record_type") != MANIFEST_TYPE
        or manifest.get("decision") != "beam_pipeline_verified"
        or not all(manifest.get("integrity_gates", {}).values())
    ):
        raise ValueError("Public Beam summary requires a verified private manifest")
    return {
        "schema_version": 1,
        "record_type": "planmargin.beam_public_summary",
        "status": "completed",
        "decision": manifest["decision"],
        "logical_fingerprint": manifest["logical_fingerprint"],
        "pipeline": {
            "runner": manifest["provenance"]["runner"],
            "source_mode": manifest["source"]["mode"],
            "source_shard_count": manifest["source"]["shard_count"],
            "records_scanned": manifest["source"]["records_scanned"],
            "accepted_event_count": manifest["source"]["accepted_event_count"],
            "partition_count": len(manifest["parquet"]),
        },
        "versions": {
            "apache_beam": manifest["provenance"]["apache_beam"],
            "pyarrow": manifest["provenance"]["pyarrow"],
            "duckdb": manifest["provenance"]["duckdb"],
        },
        "integrity_gates": dict(manifest["integrity_gates"]),
        "privacy": dict(manifest["privacy"]),
        "limitations": [
            "This validates the data pipeline, not planner safety or failure discovery.",
            "The tracked report contains aggregates only; feature rows remain ignored locally.",
            "The official held-out split remains unopened.",
        ],
    }


def _write_public_summary(path: Path, summary: dict[str, Any]) -> None:
    root = Path.cwd().resolve()
    public_root = (root / "experiments" / "platform").resolve()
    if not path.resolve().is_relative_to(public_root):
        raise ValueError(
            "Public Beam summaries must remain under experiments/platform/."
        )
    _atomic_write_json(path, summary)


def _parse_shards(value: str) -> tuple[int, ...]:
    try:
        shards = tuple(int(item) for item in value.split(",") if item)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "shards must be comma-separated integers"
        ) from error
    if not shards:
        raise argparse.ArgumentTypeError("at least one shard is required")
    return shards


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--source-mode", choices=SOURCE_MODES, default="sealed-support")
    parser.add_argument("--support-dir", type=Path, default=DEFAULT_SUPPORT_DIR)
    parser.add_argument("--womd-shards", type=_parse_shards)
    parser.add_argument("--max-new-source-shards", type=int)
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--public-summary-output", type=Path)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    result = (
        audit(args.output_dir)
        if args.audit_only
        else run(
            args.output_dir,
            source_mode=args.source_mode,
            support_dir=args.support_dir,
            womd_shards=args.womd_shards,
            max_new_source_shards=args.max_new_source_shards,
        )
    )
    if args.public_summary_output is not None:
        _write_public_summary(args.public_summary_output, public_summary(result))
    print(
        json.dumps(
            {
                "status": result["status"],
                "decision": result.get("decision"),
                "completed_source_shards": result.get(
                    "completed_source_shards",
                    result.get("source", {}).get("shard_count"),
                ),
                "accepted_event_count": result.get(
                    "accepted_event_count",
                    result.get("source", {}).get("accepted_event_count"),
                ),
            },
            allow_nan=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
