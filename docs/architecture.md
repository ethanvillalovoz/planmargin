# Implemented version-one architecture

PlanMargin is a local counterfactual stress-testing workbench with two strict
boundaries: deterministic code owns scientific decisions, and restricted WOMD
records never enter the public repository. Version one is complete at this
boundary; this document describes the system that exists rather than a future
platform.

## System flow

```mermaid
flowchart TB
    subgraph P["Private local experiment boundary"]
        A["Authorized WOMD shards"] --> B["Scenario selection and empirical-support extraction"]
        B --> C["JAX / Waymax deterministic replay"]
        C --> G["Random or constrained Bayesian proposer"]
        G --> D["Bounded lead-braking mutation"]
        D --> E["Tested and reference controllers"]
        E --> F["Physical, map, behavior, failure, and rerun gates"]
        F -->|"method-neutral outcome"| G
        F --> H["Content-sealed cell records"]
        H --> I["Resumable campaign reconstruction"]
        I --> J["Private DuckDB and Parquet analytics"]
    end

    subgraph U["Public data-free boundary"]
        K["Versioned schemas and synthetic fixtures"]
        L["Aggregate-only campaign report"]
        M["Angular / Three.js evidence debugger"]
        N["Python and native parity tests"]
        K --> M
        L --> M
        K --> N
    end

    I -->|"permitted aggregates only"| L
```

## Component responsibilities

| Layer           | Implementation                   | Responsibility                                                                                                                                      |
| --------------- | -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Dataset adapter | Python, TensorFlow records, WOMD | Stream authorized shards, retain source identity privately, and normalize scenario inputs.                                                          |
| Simulation      | JAX, Waymax                      | Deterministic original and counterfactual closed-loop rollouts.                                                                                     |
| Mutation        | Python                           | Apply bounded braking-onset and speed changes while retaining the recorded spatial route.                                                           |
| Controllers     | Waymax IDM configurations        | Compare a tested technical controller with a conservative technical reference under the identical mutation.                                         |
| Validation      | Python plus C++20/pybind11       | Enforce initial, physical, map, empirical-support, failure, reference-success, and rerun gates; accelerate one profiled interaction-metrics kernel. |
| Search          | NumPy PCG64, PyTorch, BoTorch    | Produce stateless uniform-random proposals or constrained multi-objective qLogNEHVI proposals under matched budgets.                                |
| Coordination    | Python, JSON Schema              | Preserve every attempted proposal, account for physical rollout cost, seal checkpoints, and resume without changing decisions.                      |
| Analytics       | DuckDB, Parquet, SQL             | Normalize sealed campaign summaries privately and independently reconcile published aggregates.                                                     |
| Evidence UI     | Angular, TypeScript, Three.js    | Inspect a validated synthetic scenario and present only already-published aggregate campaign evidence.                                              |
| Automation      | uv, npm, GitHub Actions          | Reproduce data-free lint, tests, native builds, dependency audit, typechecking, and frontend production builds.                                     |

## Experiment execution

1. The selection stage identifies ten training scenarios and extracts a bounded
   empirical-support model from authorized WOMD training shards.
2. Each method receives the same scenario, seed, mutation bounds, controller
   parameters, proposal count, and validity contract.
3. The proposer selects a two-dimensional mutation. The method-neutral
   coordinator evaluates it through Waymax and retains accepted and rejected
   attempts in the audit trail.
4. A candidate is a qualifying finding only when the tested controller fails,
   the reference succeeds, every feasibility gate passes, and deterministic
   reruns agree.
5. Each cell is written atomically with content hashes. The campaign report is
   reconstructed from sealed cells rather than from a second in-memory result
   path.
6. The analytical builder validates those seals again, recreates method totals
   with SQL, reads back each Parquet table, and publishes only after all
   reconciliation checks agree.
7. Campaign-level aggregates cross the public boundary. Scenario identifiers,
   proposal records, trajectories, controller traces, feature vectors, support
   scores, and cell-level facts do not.

## Frozen scientific invariants

- Random and Bayesian search share proposal budgets, mutation bounds,
  controllers, physical-cost definitions, and validity gates.
- Rejected and invalid proposals remain part of the primary budget.
- The optimizer can propose a mutation but cannot certify a finding.
- No result is accepted without deterministic reconstruction from sealed
  records.
- Hypothesis rules are evaluated as frozen; budget-censored discovery values
  are not reported as observed costs.
- The held-out WOMD split remains unopened under the version-one `no_go`
  decision.

## Native geometry boundary

Profiling identified signed oriented-box separation as the bounded Python
hotspot inside continuous interaction metrics. C++20 owns the aligned
per-state geometry loop; Python retains schema validation and final rounding.
The original Python implementation remains the parity oracle.

On the development M4 Pro, the native path measured 585–619× faster than the
Python oracle for one deterministic 80-state synthetic trace. This is an
isolated-kernel result, not an end-to-end Waymax or campaign speedup. See the
[benchmark and parity contract](native-geometry.md).

## Analytical data boundary

The implemented analytical layer begins at sealed campaign and cell summaries.
It writes a private DuckDB database and Zstandard-compressed Parquet tables,
recomputes the published method metrics with SQL, and records reproducible
logical provenance. It intentionally does not duplicate raw dataset records,
proposal checkpoints, scenario identities, trajectories, or support vectors.
See the [analytics contract](analytics.md).

## Public and private artifacts

| Public and tracked                             | Private and ignored                       |
| ---------------------------------------------- | ----------------------------------------- |
| Source code and JSON Schemas                   | Raw or cached WOMD shards                 |
| Synthetic fixtures and parity cases            | Scenario and object identifiers           |
| Frozen protocols and decision records          | Original and mutated trajectories         |
| Campaign-level aggregate results               | Proposal and cell records                 |
| Screenshots of aggregate or synthetic evidence | Feature vectors and support scores        |
| Data-free CI configuration                     | DuckDB, Parquet, and checkpoint artifacts |

Repository policy tests and `.gitignore` enforce this separation. The debugger
ships no private data and does not upload local records.

## Deliberate omissions

- **Apache Beam:** the bounded local extraction did not justify a separate
  distributed pipeline responsibility.
- **FastAPI:** the final debugger can satisfy its public role with a synthetic
  fixture and static aggregate evidence; no private-record API is needed.
- **Hosted infrastructure:** local execution and GitHub Actions cover the
  reproducibility contract at zero cost.
- **AI explanation:** deterministic evidence is already concise, and an
  assistant would not own metric generation or safety decisions.
- **Gaussian splatting:** it does not help answer the version-one research
  question or inspect the frozen evidence.

These are scope decisions, not missing dependencies. New infrastructure belongs
in a future version only after a measured product or scaling requirement gives
it a concrete responsibility.
