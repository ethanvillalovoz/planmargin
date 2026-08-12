# WOMD empirical-support and matched-search protocol

- **Status:** Frozen before implementation
- **Issue:** #22
- **Date:** 2026-08-11

## Purpose

This protocol closes the claim gap identified by the
[version-one product checkpoint](decisions/0002-version-one-product-checkpoint.md)
and freezes the development comparison before constrained Bayesian search is
implemented.

The current pipeline proves kinematic, route, map, and deterministic validity.
It does not prove that a counterfactual resembles behavior observed in WOMD.
Version one will therefore add a lightweight **WOMD empirical-support gate**.
That name is deliberate: the gate measures support under a bounded WOMD sample.
It is not a universal model of human driving, a probability of real-world
safety, or an independent validation of WOMD.

WOMD provides 91 trajectory states per training or validation example: one
second of history, the current state, and eight seconds of future at 10 Hz.
It also contains an unlabeled mixture of manually and autonomously driven data.
See the official [Motion Dataset format](https://waymo.com/open/data/motion/)
and [WOMD paper](https://waymo.com/research/large-scale-interactive-motion-forecasting-for-autonomous-driving--the-waymo-open-motion-dataset/).
A 2025 external validation study reports that WOMD may underrepresent abrupt
deceleration and short-headway behavior, so passing this gate cannot be
described as general naturalistic realism. See
[Zhang et al.](https://arxiv.org/abs/2509.03515).

## Existing-field audit

The repository already retains much of the required evidence:

| Source | Fields already available |
| --- | --- |
| Scenario selection | initial gap, lateral offset, heading difference, SDC and lead speed, peak deceleration, peak acceleration and jerk, total and one-second speed drop, and nonincrease fraction |
| Lead-braking mutation | recorded and shifted onset, peak speed, acceleration and jerk, route length, route progress, and route deviation |
| Scenario validator | overlap, offroad, validity, completion, and deterministic trajectory hash |
| Controller comparison | independent outcomes, signed separation, longitudinal TTC, response hash, and rerun determinism |
| Random-search record | proposal identity, rejection stage, normalized mutation distance, finding classification, and physical cost |

The mutation record does not yet retain total speed drop, one-second speed
drop, braking nonincrease fraction, current interaction context, or a support
score. Implementation must add one shared feature extractor and use it for
both recorded reference events and counterfactual trajectories. It must not
maintain separate formulas in the miner and mutation pipeline.

## Empirical reference sample

### Dataset partition

- dataset: WOMD Motion Dataset `1.3.1`, training split;
- development scenarios: training shard `00000`, already selected;
- empirical-reference shards: the following 16 complete training shards;
- future held-out evaluation: the official WOMD validation split, untouched by
  this milestone; and
- global shard-selection seed: `20260811` with the exact selected list pinned
  below, so NumPy-version changes cannot alter it.

```text
00057 00104 00159 00221 00278 00306 00311 00407
00539 00601 00638 00756 00784 00813 00870 00907
```

These shards were sampled without replacement from training shards `00001`
through `00999` using `SeedSequence([0, 20260811])` and `PCG64`. Shard `00000`
was excluded before sampling. The scan is fixed rather than expanded after
observing feature values.

Based on the completed shard-00000 scan, the bounded extraction is expected to
stream approximately 19.6 GB, finish in roughly 20 to 30 minutes on the M4 Pro,
and remain below 2 GiB peak RSS. These are feasibility estimates, not
performance claims. Source TFRecords are streamed and never copied into the
repository or output artifacts.

### Event inclusion

The extractor reuses the frozen lead-vehicle-braking candidate definition:

- vehicle lead on the SDC's recorded route;
- valid same-direction interaction geometry;
- sustained braking under the existing selection thresholds;
- one best-scoring lead per scenario; and
- no controller-outcome or baseline-validation filter.

Every included event is retained. Events are sorted by SHA-256 of the private
scenario identifier. The first 70% form the reference set and the remaining
30% form the calibration set. This split occurs only after the complete fixed
scan and is independent of feature values.

At least 160 included events are required. Fewer than 160 is a predeclared
no-go: do not add shards adaptively, do not tune the event filter, and do not
claim empirical behavioral support in version one. Instead, narrow the public
method name to kinematic/map-constrained search in a new decision record.

## Shared behavior features

Features are computed over 61 states from the current state through six
seconds of future data. Invalid or missing states inside that window reject the
feature vector. The SDC/lead context is measured at the current state, not at
the beginning of the one-second history.

The frozen vector is:

1. current center-to-center longitudinal gap in meters along the SDC heading;
2. current closing speed in meters per second: SDC speed minus lead speed;
3. current lead speed in meters per second;
4. peak deceleration magnitude in meters per second squared;
5. maximum cumulative speed drop in meters per second;
6. maximum one-second speed drop in meters per second;
7. braking nonincrease fraction using the existing `0.2 m/s` per-step
   tolerance; and
8. `log1p` of maximum absolute jerk in meters per second cubed.

All speed derivatives use `0.1 s` intervals and float64 arithmetic. The
extractor returns the untransformed audit metrics as well as the eight-element
model vector. It rejects non-finite values and records a versioned reason.

## Empirical-support model

The model is a deterministic split-conformal nearest-neighbor support score:

1. compute the reference-set median and interquartile range for every feature;
2. robust-scale each feature as `(x - median) / IQR`, with an IQR floor of
   `1e-9`;
3. define nonconformity as mean Euclidean distance to the five nearest
   reference vectors;
4. compute every calibration vector's nonconformity against the reference
   set; and
5. for candidate score `a`, compute

```text
p_support = (1 + count(calibration_score >= a)) / (n_calibration + 1)
```

The candidate passes when `p_support >= 0.05`. The signed outcome constraint
is `0.05 - p_support`, where values less than or equal to zero are feasible.
Exact-distance ties remain included in the count.

This is an empirical support test, not a density estimate. Its validity depends
on the reference/calibration exchangeability assumption and the bounded event
filter. The public report may publish feature names, sample counts, aggregate
quantiles, the calibration-score threshold, and pass rates. Per-event vectors,
scenario identifiers, hashes linked to private records, and counterfactual
support scores remain under ignored `artifacts/realism/` and
`artifacts/search-comparison/` paths.

The model artifact fingerprints the dataset version and split, exact shard
list, source code, feature configuration, event thresholds, ordered private
record keys, split membership, robust-scaling values, reference vectors,
calibration scores, and environment. Resume refuses any mismatch.

## Relationship to the completed random baseline

The completed seed-0 random baseline remains a valid engineering control for
proposal determinism, checkpointing, accounting, and the original kinematic/
map-constrained pipeline. It is not silently relabeled as the final
empirical-support comparator.

Its records lack several frozen behavior features, and the final comparison
requires five seeds and a method-neutral schema. Both search methods will
therefore run under a new version-two comparison contract. The old baseline is
preserved unchanged and cited as historical evidence.

## Matched development experiment

### Common contract

Random and Bayesian search receive identical:

- ordered ten-scenario training set;
- onset offsets `{0.0, 0.1, 0.2, 0.3, 0.4, 0.5}` seconds;
- continuous speed-multiplier bounds `[0.75, 1.00]`;
- 32 proposals per scenario;
- seeds `{0, 1, 2, 3, 4}`;
- mutation, scenario-validation, controller, empirical-support, finding, and
  repeated-run definitions;
- complete-budget behavior after a finding;
- invalid-attempt retention and proposal accounting; and
- proposal, simulator, controller-rollout, Waymax-step, time, and memory cost
  reporting.

Empirical support is computed before controller execution, but controller
rollouts still run for every core- and scenario-accepted proposal. This keeps
continuous objectives available for both feasible and support-rejected points
and prevents a cheap prefilter from giving one method a simulator-cost
advantage. Core and scenario rejections still skip unavailable downstream
work, exactly as in the existing accounting contract.

### Search outputs

For a core- and scenario-accepted tested-controller rollout, define two
dimensionless objectives to maximize:

```text
criticality(theta) = 1 / (1 + max(minimum_signed_separation_m, 0) / 1 m)
minimality(theta)  = 1 - normalized_mutation_distance(theta) / sqrt(2)
```

Both objectives lie in `[0, 1]`; the hypervolume reference point is `[0, 0]`.
Rejected proposals receive objective values `[0, 0]` and violated constraints,
so they contribute no feasible hypervolume but remain in every model update and
audit record. Longitudinal TTC is retained as an independent metric and is not
folded into the objective because zero TTC can coexist with positive oriented-
box separation.

The outcome constraints use BoTorch's convention that values less than or
equal to zero are feasible:

```text
pipeline_constraint  = -0.5 if core/scenario/determinism gates pass else +0.5
support_constraint   = 0.05 - p_support; missing support is +1.0
reference_constraint = -0.5 if the mutated reference succeeds else +0.5
```

Neither objective nor the acquisition function certifies a finding. The
existing four-outcome classification remains authoritative.

### Uniform-random control

The version-two random control keeps the existing stateless
`SeedSequence`/`PCG64` sampler keyed by `(seed, selection_order,
proposal_index)`. It changes only the shared evaluation record and adds four
predeclared seeds. No identity or favorable boundary point is injected.

### Constrained Bayesian method

The Bayesian method uses PyTorch/BoTorch in float64 on CPU. The GP problem is
small enough that MPS or paid CUDA is not required. The pinned implementation
version will be recorded by the downstream dependency issue.

For each scenario and seed:

1. proposals 0 through 7 use a scrambled two-dimensional Sobol sequence keyed
   by `(seed, selection_order)` and mapped into the same mixed search space;
2. proposals 8 through 31 are selected sequentially with constrained
   `qLogNoisyExpectedHypervolumeImprovement` (`q=1`);
3. independent exact `SingleTaskGP` outputs use outcome standardization and
   fixed observation variance `1e-6`;
4. the acquisition uses 128 Sobol QMC samples, 10 restarts, 256 raw samples,
   and at most 200 optimizer iterations; and
5. `optimize_acqf_mixed` enumerates the six exact onset offsets while
   optimizing only the continuous speed multiplier, avoiding optimize-then-
   round bias.

BoTorch distinguishes input constraints from modeled outcome constraints and
supports feasibility-weighted acquisition; see the official
[constraint documentation](https://botorch.org/docs/constraints). The two
objectives use its supported multi-objective Pareto-front workflow; see the
[multi-objective documentation](https://botorch.org/docs/multi_objective).

Every model is refit from all recorded proposals after each evaluation. If
fewer than two accepted objective observations exist, model fitting fails,
the acquisition is non-finite, or optimization raises, the next proposal is
the stateless Sobol fallback for that proposal index. The exception,
diagnostics, and fallback identity are retained. No manual retry changes the
candidate.

Exact duplicate parameter pairs consume budget and remain in the audit trail.
They are not resampled. Acquisition ties within absolute tolerance `1e-12` are
resolved by the lexicographically smallest SHA-256 digest of `(seed,
selection_order, proposal_index, onset, float64_speed_bytes)`, avoiding a
directional parameter preference.

## Natural and controlled-regression tracks

The unchanged natural-controller track is reported even if both methods find
zero qualifying failures. Bounds, thresholds, and controllers are not changed
in response.

A separate method-sensitivity track is frozen now rather than invented after a
negative result. It changes only the tested controller's safe time headway
from `2.0 s` to `1.0 s` and uses controller ID
`planmargin-idm-headway-regression-v1`. All other tested parameters and the
conservative reference remain unchanged. This is an intentionally injected
configuration regression, not a claim about the production Waymo Driver.

The regression track proceeds only if at least 8 of 10 originals pass both its
tested controller and the reference. Otherwise it records a no-go and no
replacement configuration is tried under this protocol version.

The completed [original-eligibility gate](regression-eligibility.md) returned
`no_go`: 4 of 10 originals were eligible. All integrity gates passed. The
controlled-regression track is therefore closed under protocol version one;
the natural track is unchanged.

## Interpretation rules

Each track reports all 50 scenario-seed pairs per method. With only five seeds,
results are descriptive rather than a claim of broad statistical
generalization.

- **H1, efficiency:** report finding count and restricted mean proposals and
  physical rollouts to first qualifying failure over the 32-proposal horizon,
  treating no finding as censored at the horizon. H1 is supported only if
  Bayesian search finds at least as many failures and has lower restricted
  mean cost.
- **H2, minimality:** among paired scenario-seed cells where both methods find
  a qualifying failure, report the median paired difference in smallest
  normalized mutation distance. H2 is supported only if the Bayesian median
  is lower. No paired cells leaves H2 untestable.
- **H3, validity:** compare empirical-support plus pipeline-valid proposal
  rates. A five-percentage-point noninferiority margin is frozen; H3 is
  supported only if Bayesian validity is no more than `0.05` below random.
- **Search learning:** report feasible Pareto hypervolume by proposal and
  physical rollout count as a continuous method diagnostic, not a safety
  claim.

Natural and controlled-regression results are never pooled. A natural-track
zero result leaves H1 and H2 untestable rather than unsupported. Regression-
track evidence demonstrates sensitivity to a known injected configuration
change and cannot substitute for held-out natural-controller evidence.

## Checkpoint, schema, and privacy contract

The downstream implementation must provide a shared method-neutral run
manifest, original record, proposal record, model-step record, and aggregate
report. Every record includes method and track identifiers, seed, proposal
index, support-model fingerprint, feature record, objective values,
constraints, finding, cost, source revision, environment, and a content seal.

Atomic replacement, completed-report reconstruction, full-record resume
validation, strict finite JSON, private path enforcement, and aggregate-only
terminal output remain mandatory. Resume must reproduce random proposals,
Sobol initialization, Bayesian candidates, model states or reconstructible
training data, fallback decisions, and non-timing aggregate results.

Raw WOMD records, scenario identifiers, object indices, per-event reference
features, counterfactual feature vectors, proposal records, model diagnostics,
and linked hashes remain ignored. CI uses synthetic fixtures only.

## Implementation gates

Before any private comparison run, data-free tests must prove:

- the exact 16-shard list and deterministic reference/calibration split;
- shared feature extraction on synthetic constant-speed and braking traces;
- robust scaling, five-neighbor nonconformity, conformal p-values, and ties;
- non-finite and incomplete-window rejection;
- all five 8-point Sobol initial designs across repeated processes;
- mixed acquisition returns only one of the six onset offsets;
- fallback, duplicate, and tie behavior;
- objective and constraint reference calculations;
- equal method budgets and physical accounting;
- interruption/resume equivalence; and
- privacy-safe paths, schemas, and terminal summaries.

Then run, in order:

1. the 16-shard empirical-reference extraction;
2. an independent aggregate and privacy audit;
3. a data-free synthetic closed-loop BoTorch test;
4. a one-scenario, two-proposal private integration smoke test;
5. the regression-track original-eligibility gate;
6. the complete natural development comparison; and
7. the complete controlled-regression comparison if its gate passes.

Held-out validation scenarios remain a separate, later protocol and are not
opened during these steps.
