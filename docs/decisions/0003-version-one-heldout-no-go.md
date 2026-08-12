# ADR 0003: Keep held-out validation unopened under version one

- **Status:** Accepted
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

The official WOMD validation split has not been opened. Running the unchanged
natural protocol on it would consume the holdout without a demonstrated
development signal for the primary comparison. Changing failure thresholds,
mutation bounds, the controller, or scenario selection after observing the
development result would violate the frozen protocol and weaken any later
claim.

## Decision

PlanMargin records a **version-one held-out `no_go`**. The validation split
will remain unopened under the current protocol. Version one closes with an
audited negative development result rather than a nominal held-out run that
cannot answer H1 or H2 reliably.

This decision changes the remaining version-one sequence in ADR 0002: the
project proceeds to the analytical data layer, measured systems optimization,
and recruiter-facing demonstration. It does not represent a failed validation
experiment, because no held-out scenario was loaded or evaluated.

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
   reporting before validation data is inspected.

The future protocol must define its development-signal threshold in advance;
this ADR deliberately does not choose one after seeing version-one outcomes.

## Consequences

### Positive

- The untouched validation split remains useful for a scientifically motivated
  future protocol.
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
