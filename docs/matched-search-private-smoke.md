# Private matched-search integration smoke test

The private smoke test is the bounded bridge between the data-free
[cell coordinator](matched-search-coordinator.md) and the existing Waymax
mutation and controller pipeline. It is an integration gate, not a search
experiment.

## Frozen scope

The command fixes the scientific coordinates in source:

```text
method = random
track = natural
seed = 0
scenario selection order = 1
new proposal count = 2
```

The proposal coordinates are therefore the first two outputs from the frozen
stateless PCG64 sequence. The runner accepts path overrides but exposes no CLI
option that can change the method, track, seed, scenario, or proposal count.
The coordinator's production cell budget remains 32.

## Evaluator boundary

`planmargin.matched_waymax.WaymaxEvaluatorAdapter` reuses the existing:

- lead-braking mutation and fixed bounds;
- repeated scenario validator;
- tested and conservative-reference controller specifications;
- repeated Waymax controller runner and controller evidence records; and
- shared eight-feature behavioral-realism extractor.

For every mutation- and scenario-accepted proposal, the adapter performs:

```text
mutation
  -> scenario validation
  -> feature extraction
  -> empirical-support scoring
  -> tested controller twice
  -> reference controller twice
```

Support scoring happens before either controller. Its result is deliberately
discarded by the adapter: only raw attempt and feature evidence cross the
boundary. The coordinator independently recomputes support, objectives,
constraints, findings, duplicate links, and cost. Both controllers still run
when the feature or support gate rejects an otherwise valid proposal.

## Run locally

The required selection manifest and support model are restricted local
artifacts. From the repository root:

```bash
uv run --frozen planmargin-run-matched-search-smoke
```

Private checkpoints are written below
`artifacts/search-comparison/private-integration-smoke/`. The command prints
only aggregate counts and limitations. It does not print scenario identifiers,
source records, feature vectors, support values, trajectory hashes, controller
outcomes, or per-proposal findings.

After two proposals, the runner resumes the same incomplete 32-proposal cell
with a zero-new-proposal limit and evaluator callbacks that fail if called.
This proves checkpoint validation and bounded resume without expanding the
smoke into a full cell.

## Interpretation

A pass establishes that the real private pipeline honors the coordinator
contract and evaluation order for the two predeclared proposals. It does not
measure search efficiency, establish an avoidable failure, evaluate Bayesian
search, support H1/H2/H3, or say anything about the production Waymo Driver.

The subsequent controlled headway-regression
[original-eligibility gate](regression-eligibility.md) returned `no_go`, so no
regression-track search cells are authorized. The natural track is unchanged.
