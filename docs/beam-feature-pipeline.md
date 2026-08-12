# Beam feature pipeline

Apache Beam owns PlanMargin's bounded, restartable scenario-feature dataflow.
It executes locally with DirectRunner, writes deterministic partitioned Parquet,
and materializes a DuckDB table that independently reconciles every row. This
is a platform layer over the frozen experiment-v1 evidence; it does not alter
the support model, campaign, hypothesis decisions, or held-out gate.

## Responsibility

```mermaid
flowchart LR
    A["Bounded source shards"] --> B["Beam source transform"]
    B --> C["Shared eight-feature extractor"]
    C --> D["Sealed per-shard Parquet checkpoint"]
    D --> E["Key by SHA-256 partition"]
    E --> F["Group and deterministic sort"]
    F --> G["Eight partitioned Parquet files"]
    G --> H["DuckDB materialization"]
    H --> I["Seal and reconciliation gates"]
```

The implementation uses three source modes:

| Mode | Responsibility |
| --- | --- |
| `womd-direct` | Run the existing bounded WOMD shard miner and shared behavior-feature extractor inside a Beam transform. |
| `sealed-support` | Validate and ingest the already-completed private v1 WOMD feature checkpoints without repeating cloud reads. |
| `fixture` | Exercise feature extraction, rejection accounting, restart, sharding, and tamper behavior in data-free tests. |

`fixture` is programmatic only. Public CLI runs accept the two private source
modes. The direct adapter accepts only a nonempty subset of the 16 frozen
empirical-reference training shards.

## Determinism and restart contract

Each source shard is an independently durable unit:

1. Beam emits accepted flat feature rows and deterministic scan/rejection
   metrics.
2. `GroupByKey` removes any dependence on runner element order; rows are sorted
   by the private SHA-256 event key.
3. one Zstandard Parquet file and one metrics file are written to a temporary
   directory;
4. byte hashes, row counts, configuration identity, and input identity are
   sealed in `checkpoint.json`; and
5. the directory is atomically promoted.

A rerun validates and skips completed checkpoints. `--max-new-source-shards`
can stop after a bounded number of new units; repeating the identical command
resumes. A changed input, feature implementation, pipeline implementation, or
configuration changes the frozen run identity and is rejected rather than
silently mixed with old work.

After all source checkpoints exist, a second Beam graph reads their Parquet
files, assigns `uint32(SHA-256 prefix) mod 8`, performs keyed grouping and
sorting, and writes one file under every `partition=00` through `partition=07`
directory. Each output row includes `partition_id`; the auditor recomputes the
partition from `event_key` and rejects any misplaced row.

Apache Beam documents DirectRunner as a local correctness and development
runner that checks Beam-model assumptions such as arbitrary element order and
serializable transforms. It is not used to claim distributed throughput. The
fixed one-file-per-partition layout deliberately favors byte-repeatable
evidence over runner-chosen sharding. See the official
[DirectRunner contract](https://beam.apache.org/documentation/runners/direct/)
and [ParquetIO API](https://beam.apache.org/releases/pydoc/current/apache_beam.io.parquetio.html).

## DuckDB contract

DuckDB reads the eight explicit file paths with Hive auto-detection disabled,
orders the materialized `features` table by event key, and stores a
`partition_counts` reconciliation table. Completion requires:

- every source checkpoint seal to validate;
- exactly eight Parquet partitions;
- source, Parquet, and DuckDB row counts to agree;
- every event key to be unique;
- all eight feature values to be finite;
- every partition assignment to match the frozen hash function;
- raw scenario IDs and source URIs to be absent; and
- the official held-out split to remain unopened.

DuckDB's Parquet reader supports explicit multi-file scans, projections, and
filter pushdown; PlanMargin passes a fixed file list rather than a client or
shell glob. See the official
[DuckDB Parquet documentation](https://duckdb.org/docs/stable/data/parquet/overview).

## Run locally

Reuse and independently transform the sealed private v1 WOMD feature evidence:

```bash
uv run --frozen planmargin-build-beam-features \
  --source-mode sealed-support \
  --support-dir artifacts/realism/lead-braking-support-v1 \
  --output-dir artifacts/beam-features/lead-braking-v1
```

Audit without running Beam or reading WOMD:

```bash
uv run --frozen planmargin-build-beam-features \
  --audit-only \
  --output-dir artifacts/beam-features/lead-braking-v1
```

An authorized direct scan uses the identical shard list on every resume:

```bash
uv run --frozen planmargin-build-beam-features \
  --source-mode womd-direct \
  --womd-shards 57,104,159 \
  --max-new-source-shards 1 \
  --output-dir artifacts/beam-features/direct-gate
```

The output tree remains ignored:

```text
artifacts/beam-features/lead-braking-v1/
├── run-manifest.json
├── source-shards/shard=.../{events.parquet,metrics.json,checkpoint.json}
├── dataset/partition=00..07/events.parquet
├── beam_features.duckdb
└── manifest.json
```

## Verified private integration

The August 12, 2026 integration reused all 16 sealed v1 training-shard
checkpoints and completed in local DirectRunner without a new cloud read. Beam
consumed evidence derived from 7,796 WOMD records, retained 265 accepted events,
wrote eight nonempty partitions, and passed exact DuckDB row, uniqueness,
finite-feature, partition, privacy, and held-out gates. The aggregate-only
tracked record is
[`experiments/platform/beam-feature-integration.json`](../experiments/platform/beam-feature-integration.json).

This proves the pipeline and real-record compatibility, not planner safety or
failure discovery. A fresh `womd-direct` scan remains available when a new
feature contract actually requires rereading authorized shards. Avoiding a
redundant scan preserves the project's free-only and bounded-compute rules.

## Flume claim boundary

Flume is a proprietary Google system and is not claimed here. Beam provides a
public dataflow model with map, keyed group/combine, sharded output, runner
semantics, and restart evidence that can be inspected and reproduced locally.
