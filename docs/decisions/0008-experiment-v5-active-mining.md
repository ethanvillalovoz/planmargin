# ADR 0008: Freeze Experiment v5 active counterfactual mining

- **Status:** accepted; Stage A `qualification_no_go`
- **Date:** 2026-08-21
- **Product milestone:** PlanMargin 2.0

## Context

Experiments v1 through v4 are immutable:

- v1 executed the matched random/Bayesian lead-braking campaign and found no
  qualifying policy-specific failure;
- v2 qualified a JAX/Optax learned longitudinal controller and stopped at its
  predeclared synthetic-safety `no_go`;
- v3 trained the first bounded real-WOMD JAX trajectory model; and
- v4 trained and held out a real-WOMD PyTorch trajectory model, exported ONNX,
  and qualified independent Python and C++17 TensorRT runtimes on a free T4.

The remaining scientific gap is integration. The learned models do not select
which counterfactuals receive expensive closed-loop Waymax evaluation. The v1
campaign retained 3,200 sealed proposal records, including pre-controller
interaction features and measured deterministic planner outcomes. Experiment
v5 uses those immutable records as a retrospective qualification corpus before
allowing a learned selector into a new campaign.

## Decision

Experiment v5 asks:

> Can a calibrated learned risk ranker reduce the closed-loop evaluation budget
> needed to reach the lowest-clearance counterfactuals on unseen WOMD scenes?

The program has two irreversible stages. Stage A must pass before Stage B may
execute.

## Stage A: scenario-held-out risk-ranking qualification

### Evidence and claim boundary

The only source is the immutable `natural-development-v1` campaign over WOMD
v1.3.1 training scenarios. No synthetic scenario, official validation record,
sensor substitute, or production Waymo Driver output is used. The evaluation is
retrospective: every target was measured previously by Waymax. A passing result
qualifies a selector for prospective testing; it is not itself a new planner
failure-discovery claim.

Only accepted, deterministic proposals with a complete pre-controller feature
record, empirical-support score, and tested-controller separation are eligible.
Equivalent `(scenario, braking onset, speed multiplier)` proposals are reduced
to one example before fitting so repeated methods and seeds cannot overweight a
point.

### Inputs available before controller execution

The ranker receives exactly twelve finite values:

1. current longitudinal gap;
2. current closing speed;
3. current lead speed;
4. peak lead deceleration;
5. maximum cumulative speed drop;
6. maximum one-second speed drop;
7. braking nonincrease fraction;
8. log-transformed maximum absolute jerk;
9. braking-onset offset;
10. speed multiplier;
11. normalized mutation distance; and
12. empirical-support probability.

Method, seed, proposal index, scenario identifier, controller output, trajectory
hash, objective, and post-rollout metric are prohibited inputs. The regression
target is the tested controller's minimum signed longitudinal separation in
meters; lower predictions rank first.

### Split, model, uncertainty, and ranking

- evaluation: ten leave-one-scenario-out folds;
- calibration: the preceding scenario in the fixed selection order;
- training: the remaining eight scenarios;
- architecture: five independently initialized two-layer PyTorch MLP regressors
  with 64 hidden units and SiLU activations;
- loss: Smooth L1;
- preprocessing: training-fold mean and standard deviation only;
- uncertainty: ensemble standard deviation scaled on the calibration scenario
  to a 90% absolute-residual interval;
- ranking score: calibrated lower confidence bound `mean - scale * std`;
- candidate budget checkpoints: 1, 4, 8, 16, and 32;
- random baseline: 512 deterministic candidate permutations per held-out scene;
- physical heuristic: lower lead-speed multiplier, then later braking onset;
- oracle: observed separation order, reported only as an upper bound.

No candidate from the held-out or calibration scenario may affect weights or
normalization. The report contains aggregate metrics and selection-order labels,
never scenario identifiers or raw feature rows.

### Frozen Stage-A gates

All gates must pass:

| Gate | Threshold |
| --- | --- |
| Evidence scale | At least 500 unique accepted examples across exactly 10 scenarios. |
| Scenario isolation | Zero train/calibration/test overlap in every fold. |
| Ranking signal | Mean held-out Spearman correlation at least 0.25. |
| Budget efficiency | At budget 8, mean random-minus-learned best separation at least 0.25 m. |
| Scenario consistency | Learned budget-8 ranking matches or beats random median in at least 7 of 10 scenarios. |
| Calibration | Aggregate 90% held-out interval coverage in `[0.75, 0.98]`. |
| Determinism | Two clean runs have the same logical report fingerprint and byte-identical model bundle. |
| Privacy | Tracked/public output contains no scenario identifier, source location, or feature row. |

A failure is recorded as `qualification_no_go`. Thresholds, features, folds,
and labels may not be changed after observing Stage-A results under Experiment
v5.

## Stage B: prospective closed-loop campaign

Stage B is authorized only if Stage A passes. Its future protocol must be frozen
in a new ADR before any new controller outcome is observed. At minimum it must:

- select a new deterministic set of real WOMD training scenarios not used in
  v1 or Stage A fitting;
- compare random, constrained Bayesian, physical-heuristic, and learned ranking
  under equal proposal and physical-rollout budgets;
- retain full selected trajectories at execution time;
- report time to first qualifying failure when one exists and cumulative
  best-separation curves otherwise;
- profile preprocessing, TensorRT inference, ranking, and serialization as one
  batch-one C++17 path with p50, p95, p99, memory, and tool versions; and
- keep official WOMD validation data out of the program because its pristine
  access condition was invalidated by the legacy Stage-0 read.

Adding a CUDA kernel is permitted only when profiling identifies a measured
bottleneck. ROS, Isaac, Omniverse, DeepStream, and 3D perception are not Stage-B
requirements and must not be added as résumé-only dependencies.

## Consequences

This protocol makes PyTorch and accelerated inference responsible for the
project's core decision—what to simulate next—while preserving the negative
results that make the existing work trustworthy. It also creates a precise
stop condition: a model that predicts held-out margins but does not improve
budgeted discovery is not promoted into the workbench or a new campaign.

## Result

The immutable campaign contained 2,097 unique proposals with complete eligible
inputs and targets, exceeding the 500-example scale gate. However, selection
order 9 had zero accepted proposals with controller targets. Only nine of the
predeclared ten scenarios were therefore available. The exact-ten-scenario gate
failed before any model was trained, no cross-validation fold was executed, no
model or ONNX graph was exported, and Stage B was not authorized.

This is a data-coverage `no_go`, not a learned-ranking performance result. A
later experiment may define a grouped protocol over every eligible scenario
because no v5 model outcome was observed, but it must retain the v5 performance
thresholds and may not describe itself as the predeclared ten-scenario study.
