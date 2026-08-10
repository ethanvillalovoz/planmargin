# Architecture

## Design principles

1. Establish the scientific experiment before building the platform around it.
2. Keep raw sensor and trajectory data outside relational databases and Git.
3. Separate deterministic metric computation from optional AI-generated explanation.
4. Make every expensive stage restartable from immutable inputs.
5. Add infrastructure only after a measured bottleneck or scaling requirement appears.

## Planned layers

### Dataset adapter

Loads selected Waymo Open Motion scenarios and converts them into an internal, versioned representation. Scenario identity and source-version metadata must remain attached to all derived records.

### Geometry and validation library

C++20 kernels will eventually own coordinate transforms, oriented-box overlap, route projection, conflict points, time-to-collision, mutation continuity, and kinematic bounds. Python bindings will be provided with pybind11.

Stage 0 may prototype these operations in Python, but each migrated kernel must have parity tests before the C++ version becomes authoritative.

### Scenario miner

An Apache Beam pipeline will classify and shard scenarios, compute reusable features, and write columnar Parquet outputs. Development uses the local Direct Runner. Cloud Dataflow is optional and never a core requirement.

### Analytical data layer

- Object storage or local files: source shards and large artifacts
- Parquet/Arrow: derived scenario, rollout, and metric tables
- DuckDB: analytical SQL, comparisons, slicing, and report generation

### Simulation and evaluation

Waymax runs closed-loop policies and produces trajectory states. PlanMargin adds custom failure, near-failure, realism, and reference-controller checks while preserving the individual metric components behind any composite score.

### Search coordinator

The coordinator presents identical mutation bounds and rollout budgets to random and Bayesian search, records every attempted mutation, and never discards invalid candidates from the audit trail.

### API and scenario debugger

A FastAPI service will expose experiment metadata and selected artifacts to an Angular/Three.js interface. The interface will compare original and counterfactual rollouts, policy and reference behavior, and metric timelines.

An optional Gemini assistant may summarize evidence already computed by deterministic tools. It cannot generate safety metrics or control a simulated vehicle.

## Reproducibility record

Every rollout result should be traceable to:

- scenario ID and dataset version
- source and derived-data checksums
- Git commit
- policy and reference-controller versions
- mutation parameters
- random seed
- metric configuration
- runtime environment
- hardware class
- start, completion, and failure status

The Stage 0 implementation serializes this contract as the versioned
[rollout-record collection](rollout-record.md). Restricted identifiers and
trajectories remain in ignored local artifacts; only the JSON Schema and
privacy-safe aggregate report are committed.

## Zero-cost execution

- Apple-silicon Mac: primary development, preprocessing, C++, DuckDB, Beam Direct Runner, frontend, and PyTorch MPS
- CPU JAX: deterministic smoke tests and reduced batches
- Colab Free: optional accelerated batches with resumable shards
- GitHub Actions: small fixture-based checks only; no restricted data
