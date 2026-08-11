# Deterministic uniform-random baseline protocol

Issue #19 implements the fixed experimental control for the later constrained
Bayesian search. This baseline changes only proposal generation. It reuses the
lead-braking mutation, scenario-validation, controller-comparison, continuous
metric, reproducibility, and privacy contracts established in Stage 0.

The first run uses the ordered ten-scenario training feasibility set. It is not
a held-out evaluation and cannot support a planner-performance claim.

## Frozen search space and budget

For each scenario, the baseline evaluates exactly 32 indexed proposals:

```text
theta = [braking_onset_offset_s, speed_multiplier]
```

- braking-onset offset is sampled uniformly from the simulator-aligned set
  `{0.0, 0.1, 0.2, 0.3, 0.4, 0.5}` seconds;
- speed multiplier is sampled from the continuous uniform interval
  `[0.75, 1.00]` using float64 arithmetic;
- the global seed is `0`; and
- the ten-scenario development run contains 320 total proposals.

The sampler is stateless. NumPy `SeedSequence` and `PCG64` are initialized from
`[seed, selection_order, proposal_index]` for every proposal. Proposal values
therefore do not depend on execution order, sharding, prior failures, or
resume boundaries. No identity point or favorable boundary is injected.
Duplicates remain in the audit trail and consume budget.

The run always exhausts the complete budget, even if it finds a qualifying
failure early. Original controller evaluations are cached separately and do
not consume proposal budget.

## Evaluation and cost accounting

Every proposed pair consumes one primary budget unit, including pairs rejected
before controller execution. The pipeline is:

1. apply the existing lead-braking mutation;
2. retain core rejections;
3. run the repeated scenario validator for core-accepted mutations;
4. retain scenario rejections;
5. run tested and reference controllers twice on every accepted mutation;
6. compute signed oriented-box separation and longitudinal TTC; and
7. classify the four-outcome policy-specific finding.

A policy-specific avoidable failure requires both controllers to pass the
original, the tested controller to fail the mutation, and the reference to
succeed on that identical mutation.

In addition to proposal count, every checkpoint records logical evaluations,
physical deterministic rollouts, and Waymax rollout steps for scenario
validation and each controller role. The later Bayesian method must use the
same proposal budget, bounds, controller budget, and accounting definitions.

## Search metrics

The aggregate report derives directly from durable proposal checkpoints and
retains:

- status and rejection-reason counts;
- valid-mutation, deterministic-reproduction, and controller-response rates;
- qualifying-failure count and first-failure cost by scenario;
- minimum tested-controller signed separation and longitudinal TTC;
- minimum normalized mutation distance among qualifying failures; and
- runtime, throughput, rollout-cost, and memory observations.

Normalized mutation distance is frozen as:

```text
d(theta) = sqrt(
  (braking_onset_offset_s / 0.5)^2
  + ((1.0 - speed_multiplier) / 0.25)^2
)
```

The baseline does not use or tune a composite severity objective.

## Checkpoint and resume behavior

Restricted run state lives under
`artifacts/random-search/lead-braking-baseline/`:

```text
run-manifest.json
originals/scenario-XX.json
proposals/scenario-XX/proposal-XXXX.json
report.json
```

The immutable run manifest fingerprints the source scenario manifest,
scenario order, dataset, mutation configuration, controllers, bounds, seed,
budget, accounting rules, Git revision and dirty flag, and coordinator source
hash. Each original and proposal checkpoint is strict JSON with its own
content hash and configuration fingerprint.

Writes use a flushed and synchronized temporary file followed by atomic
replacement. Resume validates the run fingerprint, record type, schema
version, content hash, scenario identity, proposal index, and deterministically
regenerated parameters before skipping work. Missing records are evaluated;
corrupt, unexpected, or mismatched records stop the run rather than being
silently replaced.

The completed report is reconstructed from checkpoints on disk. Reordered,
interrupted, and resumed fixture runs must match uninterrupted results except
for invocation timing and process-memory observations.

## Versioned private schemas

- [`random-search-run-manifest-v1.schema.json`](../schemas/random-search-run-manifest-v1.schema.json)
- [`random-search-original-v1.schema.json`](../schemas/random-search-original-v1.schema.json)
- [`random-search-proposal-v1.schema.json`](../schemas/random-search-proposal-v1.schema.json)
- [`random-search-report-v1.schema.json`](../schemas/random-search-report-v1.schema.json)

These schemas describe private records and do not authorize committing record
instances.

## Running locally

Start the frozen baseline from the repository root:

```bash
uv run --frozen planmargin-run-random-baseline \
  --manifest artifacts/stage-0/scenario-selection.json \
  --output-dir artifacts/random-search/lead-braking-baseline
```

Resume the identical configuration:

```bash
uv run --frozen planmargin-run-random-baseline \
  --manifest artifacts/stage-0/scenario-selection.json \
  --output-dir artifacts/random-search/lead-braking-baseline \
  --resume
```

Repeated `--selection-order` arguments allow deterministic sequential shards.
`--max-new-proposals` provides a controlled interruption boundary for testing
resume behavior. `--seed` and `--budget` are fingerprinted configuration
arguments; the definitive development run uses their defaults of `0` and
`32`.

The command rejects output paths outside `artifacts/`. Terminal output contains
only aggregate progress or completed metrics. Scenario identifiers, source
locations, object indices, per-proposal parameters and outcomes, and linked
hashes remain private and ignored.

## Interpretation boundary

Completing the baseline establishes a reproducible experimental control. It
does not establish that random search is effective, that a discovered event is
representative, or that the production Waymo Driver would behave like either
technical controller. Bayesian optimization and held-out evaluation remain
separate future milestones.
