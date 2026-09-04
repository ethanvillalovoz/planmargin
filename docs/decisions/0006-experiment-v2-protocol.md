# ADR 0006: Freeze experiment v2 and its learned-controller gate

- **Status:** accepted; controller qualification `no_go`
- **Date:** 2026-08-12
- **Tracking:** #56

## Context

Experiment v1 compared two parameterizations of Waymax's same route-following
IDM algorithm. Its natural development campaign completed 3,200 proposals and
14,110 physical rollouts without a qualifying policy-specific failure. That is
a valid negative result, but it leaves H1 and H2 untestable and does not test an
algorithmically independent learned controller. Experiment v1 is immutable.

Experiment v2 changes exactly one scientific axis: the tested controller. It
keeps the frozen lead-vehicle-braking scenario family, two-dimensional mutation
space, empirical-support model, random and Bayesian search algorithms, budgets,
seeds, constraints, findings, and conservative IDM reference. This isolates
whether an independently learned longitudinal response creates an analyzable
testing problem without manufacturing signal by changing the scenario family
or search space at the same time.

Waymax supplies an acceleration-and-steering dynamics model and an RL-compatible
environment interface. The v2 controller uses JAX for a small Deep Q-Network
(DQN), but owns only longitudinal acceleration. Waymax's logged-route projection
remains the lateral scaffold. It is therefore a **learned longitudinal policy**,
not a full production planner or a model of the Waymo Driver.

Primary implementation references reviewed before freezing this protocol:

- the pinned [Waymax repository](https://github.com/waymo-research/waymax),
  including its planning-agent environment, Brax wrapper, and invertible bicycle
  dynamics;
- the original [DQN paper](https://doi.org/10.1038/nature14236); and
- the existing frozen PlanMargin v1 controller, mutation, support, coordinator,
  and campaign contracts.

## Decision

Experiment v2 has three sequential, irreversible gates:

1. train and qualify one fixed JAX DQN controller without official held-out data;
2. if qualification passes, freeze its model hash and run the complete v2
   development comparison on the existing ten training scenarios; and
3. open the official validation split only if the predeclared development-signal
   gate passes. Otherwise record `no_go` and stop.

No threshold below may be relaxed and no seed, controller checkpoint, scenario,
or mutation may be substituted after its corresponding result is observed.

## Phase 1: learned-controller qualification

### Training environment

The DQN trains only in a deterministic, vectorizable one-dimensional
car-following surrogate. It does not train on WOMD validation records or on v1
campaign outcomes.

- timestep: 0.1 seconds;
- horizon: 80 actions;
- state: ego speed, lead speed, bumper gap, relative speed, time headway, lead
  acceleration, and previous ego acceleration;
- initial ego and lead speeds: uniform `[5, 25] m/s`;
- initial bumper gap: uniform `[10, 60] m`;
- lead braking onset: uniform `[0, 4] s`;
- lead acceleration after onset: uniform `[-6, 0] m/s²`;
- nonnegative vehicle speeds and a collision termination at nonpositive gap;
- fixed vehicle lengths are absorbed into the initialized bumper gap.

The seven discrete ego accelerations are `[-6, -4, -2, -1, 0, 1, 2] m/s²`.
The normalized observation is clipped to the training support. A two-hidden-layer
MLP with 64 tanh units per layer outputs seven Q-values.

Per nonterminal step, the reward is:

```text
0.10 * ego_speed / 25
- 0.30 * max(0, 1.5 - time_headway)^2
- 0.002 * acceleration^2
- 0.001 * (acceleration - previous_acceleration)^2
```

A collision adds `-100` and terminates the episode. Reward is a controller
training device, never a PlanMargin finding or safety metric.

### Frozen DQN procedure

- implementation: JAX double DQN with a target network;
- optimizer: Adam, learning rate `3e-4`;
- discount: `0.99`;
- replay capacity: `100,000` transitions;
- environment collection: 32 parallel episodes;
- warm-up: `5,000` transitions;
- minibatch: `256`;
- training steps: `120,000`;
- optimizer ratio: four gradient updates after each 32-transition collection
  step once warm-up completes;
- target update interval: `1,000` optimizer steps;
- epsilon: linear from `1.0` to `0.05` over `80,000` environment steps;
- training seed: `2027`;
- initialization: deterministic variance-scaled JAX initialization;
- checkpoint selection: the final step only; no best-of-training selection;
- evaluation: greedy actions only;
- dependencies: existing JAX plus directly declared Optax; no paid compute.

The fixed synthetic evaluation contains 2,048 episodes generated with seed
`2028` from the same declared ranges. A deterministic emergency-braking
baseline applies `-6 m/s²` when time headway is below 1.5 seconds and otherwise
`+1 m/s²`, clipped at 25 m/s. The untrained baseline is the network at its fixed
initialization under greedy action selection.

### Waymax adapter

For each known same-route lead-braking scenario, the policy observes only the
current SDC and designated lead vehicle. It computes bumper gap from their
centers and lengths, uses current scalar speeds, estimates lead acceleration
from the two most recent simulated states, and applies the greedy DQN
acceleration. Waymax's `WaypointFollowingPolicy` projects the next state onto
the SDC's logged route. All non-SDC agents and both original/mutated inputs are
identical across tested/reference runs.

The qualification probe uses the existing ordered ten WOMD **training**
scenarios. Each original is run twice. Each controller also runs twice on the
single fixed mutation `(braking_onset_offset_s=0.2,
speed_multiplier=0.8)`. This probe is controller engineering evidence, not a
search comparison, and cannot authorize a finding.

### Qualification gates

Every gate must pass:

| Gate                    | Threshold                                                                                                                                                             |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Deterministic training  | Two clean seed-2027 trainings emit byte-identical checkpoints and identical logical fingerprints.                                                                     |
| Free local compute      | Each train/evaluate run completes on the M4 Pro in at most 15 minutes with peak RSS at most 8 GiB.                                                                    |
| Synthetic safety        | Fixed-evaluation collision rate is at most 1.0% and no worse than the emergency-braking baseline by more than 0.25 percentage points.                                 |
| Synthetic progress      | Mean ego distance is at least 80% of the emergency-braking baseline and mean return exceeds the fixed untrained network by at least 5.0.                              |
| Waymax originals        | The learned controller passes all 10 originals twice with no overlap, off-road state, invalid state, or incomplete rollout.                                           |
| Nontrivial progress     | Across originals, median learned final displacement is at least 80% of default-IDM displacement.                                                                      |
| Independent behavior    | Learned and default-IDM trajectory hashes differ on at least 8 of 10 originals.                                                                                       |
| Mutation response       | Learned original and fixed-mutation hashes differ on at least 8 of 10 scenarios.                                                                                      |
| Runtime contract        | Every action is finite, belongs to the frozen action set, and repeated greedy Waymax rollouts are byte-identical.                                                     |
| Privacy and reliability | Checkpoint/report remain ignored; tracked files contain no scenario identity; data-free tests cover training, serialization, inference, limits, and tamper rejection. |

Failure produces a controller `no_go`; the learned policy is not used in a v2
campaign, and no v2 validation access occurs.

## Phase 2: v2 development campaign

Phase 2 begins only with the single checkpoint produced by Phase 1. Its SHA-256
and logical fingerprint become part of every cell manifest.

### Frozen experimental factors

- scenarios: the same ordered ten WOMD v1 training scenarios;
- tested controller: qualified greedy DQN longitudinal policy with logged-route
  lateral scaffold;
- reference: unchanged `planmargin-conservative-idm-v1`;
- mutation: unchanged lead-braking onset `[0.0, 0.5] s` and speed multiplier
  `[0.75, 1.0]` with the v1 physical/map/determinism gates;
- behavioral support: unchanged sealed v1 WOMD k-nearest-neighbor model and
  `p >= 0.05` contract;
- search methods: unchanged stateless uniform random and constrained
  qLogNEHVI;
- seeds: `[0, 1, 2, 3, 4]`;
- budget: 32 proposals for each method × seed × scenario cell, including
  rejected and duplicate proposals;
- cost: all logical evaluations, doubled deterministic physical reruns, and
  Waymax steps counted under the existing coordinator contract;
- finding: learned passes original, learned fails an accepted supported
  mutation, conservative IDM passes original and the identical mutation, and
  all reproducibility and input-identity gates pass.

This again yields 100 paired cells and 3,200 proposals. Campaign execution is
pair-first by scenario and seed. A finding never ends a cell early.

### Hypotheses

- **V2-H1 efficiency:** Bayesian search has at least as many finding cells and
  lower restricted mean proposals **and** physical rollouts to first finding.
- **V2-H2 minimality:** among scenario/seed pairs where both methods find a
  failure, the median `Bayesian - random` minimum normalized mutation distance
  is negative.
- **V2-H3 validity:** Bayesian support-and-pipeline-valid rate is no more than
  5 percentage points below random.

No p-value or power claim is made from ten scenarios. Censored cells remain at
the full budget horizon.

### Development-signal gate

Held-out access requires all integrity gates plus all of:

1. at least 10 finding cells in total;
2. findings in at least 3 distinct scenarios;
3. at least 3 finding cells for each method;
4. at least 3 scenario/seed pairs where both methods find a failure, so V2-H2
   is defined;
5. exact rerun agreement for every completed controller evaluation; and
6. V2-H3 is supported.

H1 or H2 need not favor Bayesian to authorize held-out access—the gate requires
an analyzable comparison, not a preferred result. If any condition fails, v2
records a development `no_go`, preserves the negative result, and never reads
the official validation split.

## Phase 3: conditional held-out protocol

This section freezes selection without reading validation data. It becomes
executable only after the Phase-2 report itself evaluates the development gate
as `go`.

- source: WOMD v1.3.1 `validation` TFExamples only;
- shard order: SHA-256 rank of shard indices `0..149` under salt
  `planmargin-v2-heldout-2027`;
- within-shard order: physical TFRecord order;
- selection: the unchanged lead-braking candidate predicate and score from v1;
- sample: first 10 qualifying scenarios after deterministic global ordering;
- controllers, mutations, support, methods, seeds, budgets, findings, and
  aggregation: identical to Phase 2;
- access log: record only after authorization, remain ignored, and prove no
  earlier validation read;
- reporting: only aggregate method, hypothesis, cost, and gate values may enter
  Git; scenario IDs, shard locations, trajectories, proposals, and support
  values remain private.

The held-out run is confirmatory for this bounded simulator study only. It does
not evaluate the production Waymo Driver or establish real-world safety.

## Consequences

This design gives JAX and reinforcement learning a real, testable controller
responsibility and removes v1's same-algorithm controller limitation. It also
keeps the project scientifically legible: a failed RL qualification or sparse
development result remains useful evidence and cannot be bypassed to obtain a
more impressive held-out story.

## Result

The frozen training and synthetic evaluation ran twice on the M4 Pro. Both
trainings emitted byte-identical 21.66 KiB checkpoints and identical parameter
fingerprints. The first and second training runs took 6.66 and 5.99 seconds,
respectively; peak RSS was 292.2 MiB. The final controller was not selected from
intermediate checkpoints.

| Synthetic evaluation (2,048 episodes, seed 2028) | Collision rate | Mean distance | Mean return |
| ------------------------------------------------ | -------------: | ------------: | ----------: |
| Learned final DQN                                |     **3.125%** |       93.43 m |       -1.44 |
| Emergency-braking baseline                       |         1.953% |       92.50 m |       -1.40 |
| Fixed untrained network                          |        11.475% |       52.20 m |      -11.37 |

Determinism, free-compute, and progress gates passed. The synthetic-safety gate
failed because 3.125% exceeds both the absolute 1.0% maximum and the permitted
margin over the emergency baseline. The result is therefore
`synthetic_no_go`.

Per the predeclared sequence, PlanMargin did not deploy this checkpoint into
Waymax, did not run the 100-cell v2 development campaign, and performed no v2
validation read. Tuning the reward, training budget, action shield, architecture, or
threshold after this observation would constitute a new protocol version. The
implementation and aggregate result remain as evidence of genuine JAX/Optax
double-DQN engineering and of the project's refusal to promote an unqualified
controller.

The subsequent full-program audit also found that the legacy Stage 0 smoke test
had accessed one validation record before the v1 held-out decision. Thus the
Phase-3 requirement to prove no earlier validation read was already
unsatisfiable, independently of this controller `no_go`. No validation-backed
search comparison or v2 held-out campaign was performed.
