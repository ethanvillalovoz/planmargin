# Private campaign analytics

The analytical layer converts the completed matched-search campaign summaries
into local DuckDB and Parquet tables. Its responsibility is narrow: make the
experiment queryable and independently recompute the sealed method aggregates
without copying proposal-level or raw dataset records into another system.

## Privacy boundary

The builder reads only the sealed campaign report and 100 sealed cell reports.
It does not read proposal checkpoints, selections, original trajectories,
scenario identifiers, object indices, empirical-support vectors, support
scores, or controller traces. Cell-level aggregate tables remain restricted
and are written only under the ignored `artifacts/analytics/` tree.

Terminal output contains table row counts and the aggregate verification
decision. Generated database paths, row contents, hashes, and source identities
are not printed.

## Tables

| Table | Responsibility |
| --- | --- |
| `campaign` | sealed campaign identity, status, total cost, and runtime |
| `methods` | published random and Bayesian aggregate metrics and costs |
| `hypotheses` | frozen H1, H2, and H3 decisions and comparison values |
| `cells` | private per-method, seed, and scenario-order aggregate facts |
| `hypervolume_trace` | private cell-level feasible hypervolume by proposal count |
| `status_counts` | private cell-level mutation-pipeline status counts |
| `integrity_gates` | campaign and cell reconstruction-gate outcomes |

Every table is stored in one local DuckDB database and exported to a
Zstandard-compressed Parquet file. The sealed analytics manifest records file
hashes, byte sizes, source report hashes, builder-source hash, DuckDB version,
and row counts.

## Verification contract

Before publishing the output directory atomically, the builder:

1. validates the campaign and every cell content seal;
2. reconstructs the campaign report from the ordered cell reports;
3. requires all source integrity gates to pass;
4. recomputes method counts, valid rates, hypervolume summaries, and rollout
   costs with SQL and requires agreement with the campaign report;
5. reads every Parquet file back through DuckDB and checks its row count; and
6. hashes the closed DuckDB and Parquet files into the manifest.

An existing output directory is never overwritten. This makes a partially
built or previously sealed analytical dataset distinguishable from a new run.

## Build and query

After the private natural campaign is complete:

```bash
uv run --frozen planmargin-build-analytics
```

The default output is
`artifacts/analytics/natural-development-v1/planmargin.duckdb`. For example:

```bash
uv run --frozen python - <<'PY'
import duckdb

with duckdb.connect(
    "artifacts/analytics/natural-development-v1/planmargin.duckdb",
    read_only=True,
) as connection:
    print(connection.sql("SELECT * FROM methods ORDER BY method"))
PY
```

These records are still development evidence. Queryability does not expand the
scientific claims in the [aggregate results](natural-development-results.md)
or authorize held-out access.
