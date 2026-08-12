# WOMD empirical-support implementation

This component implements the first half of the frozen
[empirical-support and matched-search protocol](behavioral-realism-and-matched-search.md).
It builds a private split-conformal five-nearest-neighbor support model from
the exact 16 WOMD `1.3.1` training shards named in that protocol. It does not
read shard `00000`, the official validation split, controller outcomes, or
baseline-validation results.

## Shared feature contract

`planmargin.behavior_features.extract_behavior_features` is the single
float64 implementation used for both recorded WOMD events and mutated Waymax
trajectories. Callers state the current-timestep index explicitly: `0` for
WOMD current-plus-future arrays and `10` for complete Waymax log trajectories.
The function returns the eight-element model vector, the untransformed audit
metrics, or a versioned rejection reason. A missing, invalid, non-finite, or
wrong-shaped 61-state window never receives a score.

The Stage-0 lead-braking selector and its ranking formula are unchanged. The
reference scan first asks that selector for the one best qualifying lead and
then calls the shared feature extractor. Counterfactual mutation records call
the same extractor after the mutation has been installed in the Waymax log
trajectory.

## Private run layout

Run from the repository root after accepting the Waymo Open Dataset terms and
configuring access:

```bash
uv run planmargin-build-empirical-support
```

The default ignored output is:

```text
artifacts/realism/lead-braking-support-v1/
  run-manifest.json
  shards/shard-XXXXX.json
  model.json
  report.json
```

Each complete shard is streamed once and atomically checkpointed. TFRecord
payloads are never written. Re-running the command validates and skips sealed
shard checkpoints; a manifest, source, environment, shard, event-identity, or
content mismatch stops the run. `--max-new-shards N` provides a bounded,
durable stopping point. It does not change the frozen shard set.

After all 16 shards finish, the command fits the robust-scaled model, writes
the sealed model and aggregate report, then independently reconstructs both
from the shard checkpoints. An additional offline audit is available:

```bash
uv run planmargin-build-empirical-support --audit-only
```

Terminal output contains only shard indices, counts, final status, and the
aggregate gate decision. Scenario identifiers, event keys, vectors, support
scores, and model internals remain under the ignored artifact path.

## Frozen decision

The report says `support_gate_ready` only when all 16 shards are complete, at
least 160 unique finite events were included, the model reconstructs exactly,
and all privacy/provenance gates pass. A smaller fixed sample produces
`no_go`. That result must not trigger adaptive shards, threshold changes, or
an empirical-support claim.

The checked-in JSON Schemas cover the run manifest, shard checkpoint, model,
and aggregate report. Data-free tests cover feature formulas, natural/mutated
offset parity, robust scaling and the IQR floor, five-neighbor scoring,
tie-inclusive conformal p-values, strict finite JSON, schemas, privacy paths,
interruption/resume, tamper detection, independent reconstruction, and the
predeclared no-go.
