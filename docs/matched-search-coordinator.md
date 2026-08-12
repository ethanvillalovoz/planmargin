# Matched-search cell coordinator

The cell coordinator implements the durable, method-neutral boundary between
the [proposal core](matched-search-proposal-core.md) and the future private
Waymax evaluator. It remains data-free in CI and does not provide a public
command that can accidentally open WOMD.

## Cell identity

One cell is exactly one tuple:

```text
(method, track, seed, scenario selection order)
```

It always consumes all 32 proposal indices. A cell is small enough to resume,
audit, or schedule independently, while a later campaign layer can compose the
fixed 200 natural-track and controlled-regression cells without changing their
scientific identities.

The two tracks differ only in the tested controller. `natural` uses
`waymax-idm-default-v1` with its `2.0 s` safe time headway.
`headway_regression` uses `planmargin-idm-headway-regression-v1` with a
`1.0 s` headway. The conservative reference is unchanged.

## Trusted boundary

An evaluator callback supplies only raw evidence:

- the original tested/reference controller records;
- the mutation, scenario-validation, and tested/reference attempt records; and
- the shared behavior-feature result.

The attempt callback receives the already validated support model so its
private adapter can extract and score the feature before starting either
controller. It returns no score and must run both controllers after that step,
including when the score fails. The next integration test will instrument this
call order.

The coordinator does not accept evaluator-provided support scores, objectives,
constraints, findings, or cost. It derives those values using the existing
empirical-support model, `matched_search.evaluate_outcomes`,
`controller_comparison.comparison_finding`, and the historical physical-cost
accounting function. Support is scored before controller evidence is consumed,
but an accepted mutation must still contain both controller results even when
support fails.

A qualifying version-two finding requires the four controller outcomes,
pipeline reproducibility, and empirical-support acceptance. The raw controller
classification is retained inside that extended finding record.

## Private layout

Every future private cell must remain below
`artifacts/search-comparison/`:

```text
cell-directory/
  run-manifest.json
  original.json
  selections/step-0000.json ... step-0031.json
  proposals/proposal-0000.json ... proposal-0031.json
  report.json
```

The checked-in Draft 2020-12 schemas cover all five record types. Records carry
the method, track, seed, scenario order, nullable or exact proposal index,
configuration fingerprint, empirical-support model fingerprint, and a content
seal. The configuration fingerprint links source revision, dependency
environment, mutation settings, controller definitions, dataset provenance,
and physical-accounting rules.

Each selection step stores the exact ordered list of prior proposal-record
hashes and its history fingerprint. Resume reconstructs the five model outputs
from those proposal records and reproduces the random, Sobol, qLogNEHVI, or
fallback decision before trusting the stored selection. A proposal then links
the selection seal and retains duplicate predecessors instead of resampling.

Writes use atomic replacement and strict finite JSON. Resume rejects schema,
identity, configuration, environment, support-model, history, candidate,
derived-value, seal, index-gap, and unexpected-file mismatches. A completed
resume performs no scenario or evaluator work, but still validates every
selection and proposal and reconstructs the aggregate report.

Selection and evaluation wall times are observations, so independent clean
runs may have different timing fields and seals. Scientific fields and
proposal decisions must match. The cell report includes status counts, pipeline
and support validity, complete physical cost, duplicate and finding counts, and
the feasible two-objective hypervolume trace. It does not evaluate H1, H2, or
H3; those require the later complete campaign.

## Next gate

The next milestone is a bounded private adapter and one-scenario, two-proposal
integration smoke test. That adapter must extract the shared counterfactual
feature vector before controller execution and then return both controller
records regardless of the support result. It must not change this coordinator,
the frozen proposal rule, thresholds, controller configurations, or record
derivations in response to the smoke-test outcome.
