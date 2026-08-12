# Natural matched-search development campaign

The campaign layer composes the frozen method-neutral cells into the complete
training-set development comparison. It adds orchestration and aggregate
reporting; it does not change proposal selection, mutation bounds, controller
definitions, empirical-support scoring, finding classification, or physical
cost accounting.

## Frozen scope

Only the `natural` track is authorized. The headway-regression track is absent
because its original-eligibility gate returned `no_go`.

```text
methods             = random, bayesian
seeds               = 0, 1, 2, 3, 4
scenario orders     = 1 through 10
cells               = 100
proposals per cell  = 32
total proposals     = 3,200
```

Execution is pair-first: for each `(scenario order, seed)` pair, the random
cell runs before the Bayesian cell. This ordering preserves paired progress if
an invocation is interrupted. It has no effect on either method's inputs or
proposal decisions.

## Private layout and resume

All records remain under the ignored private artifact tree:

```text
artifacts/search-comparison/natural-development-v1/
  run-manifest.json
  cells/{method}/seed-{seed}/scenario-{order}/
    run-manifest.json
    original.json
    selections/
    proposals/
    report.json
  report.json
```

The campaign manifest seals the exact cell order, support-model fingerprint,
source revision, dependency environment, training-manifest hash, proposal
budget, and reporting rules. Every completed cell is independently resumed
through the existing coordinator, which reconstructs proposal decisions and
validates all sealed records before the campaign trusts its report.

The top-level report is reconstructed only from the 100 validated cell
reports. Resume refuses environment, configuration, support-model, identity,
content-seal, budget, or aggregate mismatches. Timing and peak-memory fields
are observations; scientific fields must match exactly.

## Aggregate definitions

For each method, the report includes the number of cells with at least one
qualifying failure, total qualifying failures, support-plus-pipeline validity,
restricted mean proposals and physical rollouts to first finding, and mean
feasible hypervolume by proposal.

- **H1 — efficiency:** untestable when both methods find zero cells. Otherwise
  supported only when Bayesian search finds at least as many cells and has
  strictly lower restricted mean proposal and physical-rollout costs.
- **H2 — minimality:** uses only `(scenario order, seed)` pairs where both
  methods find a qualifying failure. It reports the median of
  `Bayesian minimum distance - random minimum distance`; no paired cells is
  untestable, and support requires a negative median.
- **H3 — validity:** reports the aggregate Bayesian-minus-random
  support-plus-pipeline-valid rate. The frozen noninferiority margin is `0.05`,
  so support requires a difference of at least `-0.05`.

These are descriptive results across ten training scenarios and five seeds.
They are not broad statistical generalization or evidence about the production
Waymo Driver.

## Commands

The readiness command validates the ten-scenario manifest, empirical-support
model, private output path, exact budgets, and a conservative free-disk gate.
It does not load a scenario or write campaign output.

```bash
uv run --frozen planmargin-run-matched-campaign --readiness-only
```

A bounded operational checkpoint completes at most one new 32-proposal cell:

```bash
uv run --frozen planmargin-run-matched-campaign --max-new-cells 1
```

After that checkpoint, resume the same sealed campaign:

```bash
uv run --frozen planmargin-run-matched-campaign --resume
```

Every command prints only aggregate-safe progress or completed campaign
metrics. Scenario identifiers, object indices, feature vectors, support
scores, controller outcomes, proposal records, and linked private hashes stay
inside ignored artifacts. This campaign does not read the WOMD validation split.
