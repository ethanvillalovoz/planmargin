# Implemented version-one architecture

PlanMargin is a local counterfactual stress-testing workbench with two strict
boundaries: deterministic code owns scientific decisions, and restricted WOMD
records never enter the public repository. Experiment v1 is complete at this
boundary. The broader program now adds platform layers without changing that
frozen scientific result.

## System flow

```mermaid
flowchart TB
    subgraph P["Private local experiment boundary"]
        A["Authorized WOMD shards"] --> B["Scenario selection and empirical-support extraction"]
        B --> C["JAX / Waymax deterministic replay"]
        B --> Q["Apache Beam bounded feature mining"]
        C --> G["Random or constrained Bayesian proposer"]
        G --> D["Bounded lead-braking mutation"]
        D --> E["Tested and reference controllers"]
        E --> F["Physical, map, behavior, failure, and rerun gates"]
        F -->|"method-neutral outcome"| G
        F --> H["Content-sealed cell records"]
        H --> I["Resumable campaign reconstruction"]
        I --> J["Private DuckDB and Parquet analytics"]
        Q --> R["Deterministic partitioned Parquet"]
        R --> J
        H --> O["Authenticated localhost FastAPI"]
        J --> O
    end

    subgraph U["Public data-free boundary"]
        K["Versioned schemas and synthetic fixtures"]
        L["Aggregate-only campaign report"]
        M["Angular / Three.js evidence debugger"]
        N["Python and native parity tests"]
        S["Deterministic aggregate evidence tools"]
        T["Offline / optional Gemini explanation"]
        K --> M
        L --> M
        K --> N
        L --> S
        S --> T
    end

    I -->|"permitted aggregates only"| L
    O -->|"authenticated loopback projections"| M
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
| Feature dataflow | Apache Beam, PyArrow, Parquet    | Mine or ingest bounded training shards, extract the shared behavior features, checkpoint by source, key/group into stable partitions, and reconcile in DuckDB. |
| Local API       | FastAPI, read-only DuckDB        | Verify ignored evidence at startup and expose token-authenticated, privacy-reduced projections on loopback only.                                     |
| Evidence UI     | Angular, TypeScript, Three.js    | Boot safely from a synthetic fixture; optionally inspect authenticated, redacted local trajectories and sealed proposal evidence without exporting it. |
| Evidence assistant | Python, optional Gemini SDK   | Route questions to one closed aggregate tool, cite sealed deterministic facts, and optionally explain public aggregates without sharing the raw question or private records. |
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

The implemented local API can expose redacted real evidence only to an
authenticated process on the same machine. It is not a public-data boundary:
coordinates and proposal facts remain restricted even after identifiers are
removed. See the [local evidence API contract](evidence-api.md).

## Reopened program responsibilities

Experiment v1 did not require the following layers, but ADR 0004 restores them
as separately gated program responsibilities rather than silently omitted
dependencies:

- **Apache Beam:** bounded scenario mining and empirical feature extraction to
  deterministic partitioned Parquet under DirectRunner; implemented with
  durable source checkpoints, keyed grouping, explicit partitions, and DuckDB
  reconciliation.
- **FastAPI:** implemented as a localhost-only, read-only boundary over ignored
  sealed records and verified DuckDB/Parquet evidence; the Angular client uses
  its fixed authenticated projections without persistence or export.
- **Evidence assistant:** implemented with five allowlisted aggregate-query
  tools, a deterministic offline default, sealed citations, and an optional
  public-only Gemini structured-output adapter; never metric generation,
  finding certification, or vehicle control.
- **3D Gaussian splatting:** the frozen exact-scenario LiDAR feasibility study
  completed `no_go` on trajectory coverage; its private field is not served and
  no renderer was added. Decoder/fitter code and aggregate audit results remain
  for reproducibility.
- **Learned or RL planner:** an experiment-v2 candidate that must earn a role
  through compute, determinism, and scientific-design gates.

Hosted infrastructure remains unnecessary: every core responsibility must
retain a free local or data-free execution path. See the
[original-program recovery decision](decisions/0004-recover-original-program.md).
