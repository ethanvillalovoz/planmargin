# Stage 0 scenario-selection protocol

Issue #9 creates a ten-scenario feasibility set for the first mutation tests.
The protocol is deliberately deterministic and bounded; it does not claim that
the selected scenarios represent WOMD or real-world driving generally.

## Source and ordering

- WOMD Motion Dataset 1.3.1 training TFExamples
- shards visited in ascending numeric order, beginning with shard `00000`
- records visited in their stored TFRecord order
- at most one interacting vehicle retained per scenario
- raw records remain in memory only while mining and validation run

Training data is used because this is development and feasibility work. The
validation split remains held out for later experiment comparisons.

## Preferred family probe

The preferred family is an SDC left turn with an oncoming vehicle whose logged
path conflicts spatially with the SDC path. A candidate must satisfy all
thresholds recorded in the generated JSON report, including:

- SDC counter-clockwise yaw change between 40 and 140 degrees
- at least 10 m of SDC travel and 41 valid trajectory steps
- at least 125 degrees of initial heading opposition
- at least 8 m of oncoming-vehicle travel
- path-conflict distance no greater than 5 m
- conflict arrival-time gap no greater than 4 seconds
- synchronized separation no greater than 20 m

The probe is limited to one complete training shard. If it produces fewer than
ten candidates, the protocol selects the predeclared fallback family for the
entire feasibility set. Families are not mixed to reach the target count.

The heuristic identifies left-turn/oncoming interactions, not ground-truth
unprotected turns. The TFExample representation exposes trajectories, sampled
map features, and a limited set of observable traffic-light states, but no
definitive protection-status label. Any future claim that a scenario is
unprotected will require a separate map-and-signal validation stage.

## Lead-braking fallback

The fallback requires a vehicle ahead of the SDC that is aligned with the
SDC's heading and recorded future route. Among other recorded thresholds:

- initial longitudinal gap between 5 and 60 m
- initial heading difference no greater than 35 degrees
- current and median lead-to-SDC-route distances no greater than 2.5 m
- at least 40 jointly valid steps in the first five seconds
- minimum instantaneous acceleration at most -1.0 m/s²
- total speed drop of at least 2.0 m/s
- exactly one-second speed drop of at least 1.0 m/s
- at least 80% of steps in that window increase by no more than 0.2 m/s
- absolute acceleration no greater than 12 m/s²
- absolute jerk no greater than 100 m/s³
- at least 30 valid samples in the first 61 trajectory samples

The route-distance checks reject nearby vehicles in adjacent lanes. The exact
window, sustained-decrease, acceleration, and jerk screens reject partial
windows and obvious trajectory discontinuities. These are conservative Stage 0
data-quality screens, not final behavioral-realism certification.

## Baseline acceptance

Each retained scenario is replayed twice for all 80 future steps with Waymax's
`IDMRoutePolicy` controlling only the SDC through `StateDynamics`; other actors
follow their logs. A scenario passes only when:

1. both simulated-trajectory hashes are identical;
2. the SDC remains valid for every timestep;
3. the SDC has no overlap at any timestep;
4. the SDC is not offroad at any timestep; and
5. both runs finish at timestep 90.

This verifies the specific unmodified technical baseline needed for mutation.
It does not establish general planner quality or vehicle safety.

## Reproduce

WOMD access and the locked environment must be configured first. Then run:

```bash
./scripts/verify_womd_access.sh
uv sync --frozen
uv run --frozen planmargin-select-scenarios \
  --output artifacts/stage-0/scenario-selection.json
```

The ignored local output contains ten scenario IDs, source locations, derived
interaction features, baseline hashes and metrics, exact thresholds, scan
accounting, and limitations. It contains no raw trajectories, map samples, or
credentials and must not be committed. The public experiment note retains only
the methodology and permitted aggregate results.
