# Stage 0 rollout-record protocol

Issue #1 defines the smallest versioned record needed to reproduce and inspect
a controller rollout. The contract is implemented by
[`rollout-record-collection-v1.1.schema.json`](../schemas/rollout-record-collection-v1.1.schema.json)
and by a deterministic structural validator in `planmargin.rollout_record`.

## Collection model

A successful controller comparison exports one collection with four records:

| Variant | Controller role |
| --- | --- |
| Original | Tested |
| Original | Reference |
| Counterfactual | Tested |
| Counterfactual | Reference |

Every record has a unique deterministic record ID derived from its schema
version, comparison key, variant, controller, rollout Git revision, and
trajectory hash. All four share the same deterministic comparison key, which
is derived from private scenario identity, mutation-target object, mutation
schema, and mutation configuration. The key
links records—and remains stable across reruns—without exposing the source
identifier in filenames or public reports. The collection also retains the
comparison-level policy-specific finding computed from the four independent
outcomes.

The current v1.1 collection and record types are:

```text
schema_version: 1.1.0
collection type: planmargin.rollout_record_collection
record type: planmargin.rollout_record
```

## Required record content

Each completed rollout record retains:

- dataset name, version, split, and private scenario provenance;
- both tested and reference controller IDs, implementations, and parameters;
- the controller role used for this rollout;
- whether the mutation was applied, plus its type, bounds, parameters, metrics,
  and rejection list;
- metric definitions, independent outcome, and comparison acceptance gates;
- random seed, rollout Git revision, Waymax revision, runtime versions, and
  hardware class;
- non-SDC input and SDC trajectory hashes, repeatability result, input
  immutability result, and timings; and
- the per-step SDC trajectory and first-failure timestep; and
- one collection-level, bounded scene context containing aligned roadgraph
  geometry, SDC dimensions, and original/counterfactual mutation-target tracks.

Schema 1.0.0 remains committed as the immutable initial contract. Version
1.1.0 adds the minimum spatial context required to regenerate the Stage 0
comparison without reopening WOMD.

Original and counterfactual records retain the same accepted mutation
configuration; the explicit `mutation.applied` field distinguishes whether it
was active for that rollout.

## Invalid candidates

An invalid mutation does not produce fake controller outcomes or trajectories.
It produces one `invalid_candidate` record with:

- `status: invalid`;
- the same dataset, controller-set, mutation, metric, provenance, and gate
  context available at rejection time;
- `trajectory: null` and `outcome: null`; and
- a non-empty, deduplicated rejection-reason list.

If an upstream rejection lacks a specific reason, the exporter records
the names of any failed boolean acceptance gates. It uses
`comparison_not_ready` only when neither the mutation validators nor the
acceptance map provides a specific reason.

## Determinism and validation

The exporter uses canonical JSON hashing for comparison and record IDs and does
not add timestamps, so the same source report produces the same collection.
The validator requires:

- the v1.1 schema URI and semantic version;
- one shared comparison key and unique record IDs, recomputed from their
  documented identity fields;
- complete controller-set, dataset-version, Git-revision, seed, and hardware
  context;
- exactly four variant/role pairs for a complete collection; and
- ordered scene bounds, roadgraph features, SDC dimensions, and equal-length
  mutation-target tracks for a complete collection; and
- explicit rejection reasons with no trajectory or outcome for invalid
  candidates.

## Running locally

First produce the ignored controller-comparison artifact, then run:

```bash
uv run --frozen planmargin-export-rollout-records \
  --input artifacts/stage-0/controller-comparison.json \
  --output artifacts/stage-0/rollout-records.json
```

The exporter prints only schema status and record counts. The output includes
restricted identifiers, hashes, and derived trajectories, so it must remain
under `artifacts/` and must never be committed. The repository commits only the
schema, data-free synthetic tests, methodology, and privacy-safe aggregate
result.
