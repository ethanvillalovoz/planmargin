# Experiments

Each experiment will receive a versioned configuration and a short report containing:

- objective and hypothesis
- scenario selection criteria
- policy and reference-controller versions
- mutation bounds
- rollout budget
- random seeds
- metric definitions
- environment and hardware
- results and uncertainty
- limitations and follow-up decision

Large outputs, checkpoints, raw data, identifiers, and per-scenario derived
records are ignored. Public experiment notes are limited to methodology and
permitted aggregate results. Complete local manifests belong under the ignored
`artifacts/` directory.

The completed access, deterministic-baseline, scenario-selection, and first
mutation evidence is recorded under [`stage-0/`](stage-0/), including the
[ten-scenario selection report](stage-0/scenario-selection.md) and the
[bounded speed-mutation report](stage-0/speed-mutation.md). The
[controller-comparison report](stage-0/controller-comparison.md) records the
first tested-versus-reference harness run and its negative finding. The
[rollout-record report](stage-0/rollout-record.md) validates the versioned
private export that will feed visualization and later analysis. The
[trajectory-visualization report](stage-0/trajectory-visualization.md) records
the first responsive spatial comparison generated only from that export.
The [lead-braking family-validation report](lead-braking-family-validation.md)
records the first fixed multi-scenario mutation grid and its predeclared go
decision before search implementation.
The [deterministic random-search baseline report](random-search-baseline.md)
records the complete fixed-budget training run, including all invalid-attempt
and physical-rollout accounting, before the Bayesian core was implemented.
The [data-free matched-search proposal-core report](matched-search-proposal-core.md)
records the released CPU dependency stack and synthetic evidence for the
frozen random/Bayesian proposal boundary used by the coordinator.
The [data-free matched-search cell-coordinator report](matched-search-cell-coordinator.md)
records method-neutral schema, derivation, accounting, checkpoint, resume, and
privacy evidence before the bounded private integration smoke test.
The [bounded private matched-search smoke report](matched-search-private-smoke.md)
records the aggregate evidence that real mutation, feature, support, and
controller components compose through that coordinator for exactly two
predeclared proposals.
The [controlled headway-regression eligibility report](regression-eligibility.md)
records the valid `no_go` that closes the injected-regression track without
changing its frozen configuration or the natural experiment.
The [experiment-v2 protocol and result](../docs/decisions/0006-experiment-v2-protocol.md)
records deterministic JAX double-DQN training and the synthetic-safety `no_go`
that prevented Waymax deployment and a v2 development or held-out campaign.

The [command-dropout fault-protection result](fault-protection-command-dropout-v1.json)
records a qualified off-nominal verification study over ten real WOMD training
scenes: 60 deterministic physical rollouts and 80/80 passing scene gates. Its
protocol, first failed fault representation, and corrected qualification are
documented in [ADR 0011](../docs/decisions/0011-command-dropout-fault-protection.md).
Only the schema-validated aggregate is tracked; scene traces remain private.

The [assistance-handoff result](assistance-handoff-command-recovery-v1.json)
extends that fault test with explicit request, fallback, deterministic
resolution, and primary-recovery states. All 90 frozen gates passed across 60
additional repeated real-WOMD rollouts. [ADR 0012](../docs/decisions/0012-assistance-handoff-v-and-v.md)
defines the boundary: it tests assistance behavior, not a human-operated or
production remote-assistance service.
