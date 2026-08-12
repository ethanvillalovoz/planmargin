# ADR 0007: Correct the validation-access boundary

- **Status:** accepted
- **Date:** 2026-08-12
- **Tracking:** #57

## Context

The final full-program audit reconciled executable defaults, historical Stage-0
reports, public claims, API fields, debugger copy, and assistant responses. It
found a material inconsistency:

- the original `planmargin-waymax-smoke-test` default and access-check script
  pointed at validation shard `00000-of-00150`;
- the tracked Stage-0 report truthfully records that it streamed the first
  validation TFExample for a compatibility and deterministic-replay check; but
- later decisions and product copy said that the validation split had never
  been opened.

The later statement was false in the literal data-access sense. The early smoke
did not run either search method, tune a threshold, or produce a comparative
finding, but it did inspect one validation record. That distinction must be
explicit rather than hidden behind the phrase "held-out unopened."

## Decision

The public claim is corrected to:

> One validation record was accessed by the legacy Stage-0 compatibility smoke.
> No validation-backed random-versus-Bayesian or v2 comparative campaign ran.

Accordingly:

- ADR 0003 remains the decision not to execute a version-one validation
  comparison, but its pristine-holdout premise and absolute wording are
  corrected;
- the local evidence API replaces `held_out_opened: false` with the semantically
  precise `held_out_comparison_run: false` in API version 1.1;
- the Angular debugger and evidence assistant use the same comparative-campaign
  wording;
- the smoke test and credential check now default to training shard
  `00000-of-01000`;
- a validation URI is rejected unless the caller supplies the explicit
  `--allow-validation-access` flag under another authorized protocol; and
- the repository's final claim audit rejects a recurrence of the disproven
  absolute wording.

Historical Stage-0 documentation continues to say that its actual run used one
validation record. That record is not reclassified as training and the history
is not erased.

## Consequences

- PlanMargin cannot claim that WOMD validation was wholly untouched or pristine.
- It can accurately claim that no held-out comparative experiment was run.
- Experiment-v1 conclusions remain training-development conclusions; the
  validation compatibility record supplied no evidence for them.
- Experiment-v2 stopped before any v2 validation read for its independent
  synthetic-safety reason. Its proposed Phase-3 pristine-holdout proof was also
  impossible once this historical access was reconciled.
- Correcting the overstatement strengthens the repository's auditability even
  though the revised sentence is less impressive.
