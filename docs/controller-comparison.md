# Stage 0 controller-comparison protocol

Issue #10 establishes the first auditable tested-versus-reference rollout
harness. The purpose is to distinguish a policy-specific response from an
obviously shared failure while keeping the non-ego scenario input identical.

## Controller specifications

Both controllers use the Waymax `IDMRoutePolicy` implementation pinned by the
repository. Their configurations are versioned separately:

| Parameter | Tested: `waymax-idm-default-v1` | Reference: `planmargin-conservative-idm-v1` |
| --- | ---: | ---: |
| Desired speed | `30.0 m/s` | `20.0 m/s` |
| Minimum spacing | `2.0 m` | `4.0 m` |
| Safe time headway | `2.0 s` | `3.0 s` |
| Maximum acceleration | `2.0 m/s²` | `1.5 m/s²` |
| Comfortable deceleration parameter | `4.0 m/s²` | `2.0 m/s²` |
| Lookahead from current simulated position | `true` | `true` |
| Additional lookahead points | `10` | `20` |
| Additional lookahead distance | `10.0 m` | `20.0 m` |
| Invalidate at route end | `false` | `false` |

The tested configuration matches Waymax defaults. The reference is intended to
be more conservative through lower desired speed and acceleration, larger
spacing and headway, less reliance on comfortable deceleration, and longer
lookahead. In Waymax's pinned IDM equation, the comfortable-deceleration value
appears in the desired-gap denominator; lowering it increases the desired gap
while closing on a slower lead vehicle. It is not a hard braking clamp.

## Four required outcomes

Each controller runs on both the original and mutated scenarios:

| Scenario | Tested policy | Reference policy |
| --- | --- | --- |
| Original | Must pass before a finding is eligible | Must pass before the reference is eligible |
| Mutated | Evaluated for candidate failure | Evaluated independently for reference success |

A rollout succeeds only if the SDC has zero overlap, zero off-road value,
remains valid, and completes all 80 future steps. A policy-specific avoidable
failure requires all four of the following:

1. the tested policy passes the original;
2. the tested policy fails the mutation;
3. the reference passes the original; and
4. the reference passes the identical mutation.

The evaluator retains each failure reason independently. A reference failure
cannot be hidden by, or combined with, a tested-policy failure.

## Identical input and reproducibility checks

Before each rollout, the harness hashes every non-SDC log-trajectory field. It
requires matching hashes between controllers for each scenario variant and
verifies that rollouts do not mutate their input scenario. The accepted
mutation is independently replayed through its initial-overlap, actor-validity,
off-road, full-horizon, and determinism checks. The comparison also requires:

- the original and mutated non-SDC hashes to differ;
- tested and reference output trajectories to differ on both variants;
- both controllers to respond to the mutation; and
- exact SDC trajectory-hash agreement across two runs of every
  controller/variant pair.

The local JSON exports 81 SDC states for each of the four first rollouts,
including position, yaw, velocity, speed, validity, independent outcomes,
controller parameters, hashes, timings, and provenance.

## Running locally

The ignored scenario-selection manifest must already exist:

```bash
uv sync --frozen
uv run --frozen planmargin-controller-comparison \
  --manifest artifacts/stage-0/scenario-selection.json \
  --output artifacts/stage-0/controller-comparison.json
```

The output contains restricted identifiers and per-scenario trajectories. It
must stay under `artifacts/` and must never be committed. The command writes
the full report only to that ignored file and prints a non-sensitive status
summary to the terminal.

## Reference limitations

The reference is a deterministic technical baseline—not a model of a human
driver, legal duty, responsibility, or the production Waymo Driver. Both
controllers share the same Waymax IDM algorithm and route-following
assumptions. A differential outcome therefore supports only a
configuration-specific avoidability claim. It does not establish algorithmic
independence, universal avoidability, or real-world safety.
