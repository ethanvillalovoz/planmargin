# ADR 0003: Do not run a held-out comparison under version one

- **Status:** Accepted; historical access claim corrected by ADR 0007
- **Date:** 2026-08-12
- **Checkpoint revision:** `4736ebf`

## Context

ADR 0002 required PlanMargin to establish development signal before freezing
and running a held-out evaluation. It also predeclared one method-sensitivity
alternative for a natural-track zero result: an intentionally injected
headway-regression controller, gated on at least 8 of 10 original scenarios
passing both tested and reference controllers.

The complete frozen natural development campaign evaluated 100 cells and
3,200 proposals. Neither random nor constrained Bayesian search produced a
qualifying finding. H1 efficiency and H2 minimality are consequently
untestable; H3 validity is supported under its predeclared noninferiority rule.
The separate headway-regression eligibility gate returned `no_go` because only
4 of 10 originals were eligible. No replacement controller configuration was
authorized under protocol version one.

The legacy Stage-0 compatibility smoke had already loaded the first record of a
validation shard. It did not run either search method and supplied no
comparative result, but validation was not a pristine statistical holdout.
Running the unchanged natural protocol on additional validation data would
still consume the reserved comparison set without a demonstrated development
signal. Changing failure thresholds, mutation bounds, the controller, or
scenario selection after observing the development result would violate the
frozen protocol and weaken any later claim.

## Decision

PlanMargin records a **version-one held-out-comparison `no_go`**. No validation
search campaign will run under the current protocol. Version one closes with an
audited negative development result rather than a nominal held-out run that
cannot answer H1 or H2 reliably.

This decision changes the remaining version-one sequence in ADR 0002: the
project proceeds to the analytical data layer, measured systems optimization,
and recruiter-facing demonstration. It does not represent a failed validation
comparison: the legacy record was used only for compatibility, and neither
search method was evaluated on it.

A future versioned experiment may authorize held-out access only after all of
the following occur:

1. a new scientific rationale is documented independently of a desire to
   reverse the observed zero-finding result;
2. its scenario family, controller identities, mutation space, eligibility
   gate, behavioral-support contract, budgets, and metrics are frozen before
   the new development run;
3. a predeclared development-signal gate passes on training data;
4. the data-free, privacy, reconstruction, and zero-cost readiness gates pass;
   and
5. a separate held-out protocol freezes scenario selection and aggregate
   reporting before any additional validation data is inspected.

The future protocol must define its development-signal threshold in advance;
this ADR deliberately does not choose one after seeing version-one outcomes.

## Consequences

### Positive

- The unused remainder of validation can support a transparently caveated
  future protocol, but not a claim that the entire split was pristine.
- The project reports the zero-finding result without tuning it away.
- Engineering effort moves to product and systems responsibilities that have
  independent value and do not require additional private-data exposure.
- Version-one public claims remain narrow and auditable.

### Negative

- Version one cannot make a held-out claim about comparative discovery
  efficiency or minimality.
- The original version-one product definition is narrowed from a training and
  held-out comparison to a complete, reproducible development comparison.
- A future held-out study requires a separately versioned design and another
  development campaign.

## Rejected alternatives

- **Run the unchanged protocol on validation anyway:** this would spend the
  holdout despite the absent development signal required by ADR 0002.
- **Relax gates or widen mutation bounds now:** this would be post-result
  tuning and would make the existing and revised experiments incomparable.
- **Try additional controller regressions until one is eligible:** the frozen
  version-one protocol authorized exactly one regression configuration and
  explicitly prohibited replacements after `no_go`.
- **Describe the development result as evidence of equal failure-discovery
  performance:** zero findings leave the primary comparison untestable, not
  equivalent.

The supporting aggregate evidence is published in the
[natural development results](../natural-development-results.md).
