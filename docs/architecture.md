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

The first measured native kernel aggregates oriented-box separation and
longitudinal TTC across aligned controller traces. C++20 owns the per-state
geometry loop through pybind11; Python retains schema validation and final
rounding. The original Python algorithm remains a parity oracle, with edge-case
and randomized equivalence tests required before the native result is
authoritative. Other geometry stays in Python until profiling gives it a real
native responsibility. See the [native geometry benchmark](native-geometry.md).

### Scenario miner

An Apache Beam pipeline will classify and shard scenarios, compute reusable features, and write columnar Parquet outputs. Development uses the local Direct Runner. Cloud Dataflow is optional and never a core requirement.

### Analytical data layer

- Object storage or local files: source shards and large artifacts
- Parquet/Arrow: derived scenario, rollout, and metric tables
- DuckDB: analytical SQL, comparisons, slicing, and report generation

The version-one implementation deliberately begins at the aggregate boundary.
It normalizes sealed campaign and cell reports into a private DuckDB database
and Zstandard-compressed Parquet tables, then uses SQL to reproduce the sealed
method totals before accepting the export. It does not duplicate proposal
records, scenario identifiers, trajectories, or support vectors. See the
[analytics contract](analytics.md).

### Simulation and evaluation

Waymax runs closed-loop policies and produces trajectory states. PlanMargin adds custom failure, near-failure, realism, and reference-controller checks while preserving the individual metric components behind any composite score.

Version one defines realism narrowly as a deterministic WOMD empirical-support
gate over interpretable lead-braking and interaction features. A bounded
training-shard extractor fits a robust split-conformal nearest-neighbor model;
per-event features remain private, while only aggregate calibration evidence is
public. The gate does not claim universal human-driving realism.

### Search coordinator

The coordinator presents identical mutation bounds and rollout budgets to random and Bayesian search, records every attempted mutation, and never discards invalid candidates from the audit trail.

The first implementation was the
[deterministic uniform-random baseline](random-search.md). Stateless PCG64
proposals make execution order and resume boundaries irrelevant. Atomic,
content-hashed checkpoints retain every original and proposal evaluation, and
the completed aggregate is rebuilt from those checkpoints rather than a
second in-memory result path. The implemented method-neutral coordinator now
preserves the same proposal budget, mutation/controller treatment, empirical
support, and cost definitions for random and Bayesian search. The final
comparison uses that shared contract for both methods; it does not compare the
new Bayesian pipeline directly with the historical random report.

The frozen
[matched-search protocol](behavioral-realism-and-matched-search.md) replaces a
weighted scalar score with constrained multi-objective search over criticality
and mutation minimality. Uniform random and qLogNEHVI methods emit one
method-neutral checkpoint contract so the analytical layer and debugger do not
depend on optimizer-specific files.

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

The first consumer is the deterministic
[trajectory-visualization protocol](trajectory-visualization.md): a static,
responsive SVG comparison that exercises the record boundary before the API
and Angular debugger exist.

The first multi-scenario consumer is the
[lead-braking family-validation protocol](family-validation.md). It runs a
fixed two-dimensional mutation grid, preserves every rejection, and adds
continuous oriented-box separation and longitudinal TTC metrics before any
search method is allowed to optimize the space.

## Zero-cost execution

- Apple-silicon Mac: primary development, preprocessing, C++, DuckDB, Beam Direct Runner, frontend, and PyTorch MPS
- CPU JAX: deterministic smoke tests and reduced batches
- Colab Free: optional accelerated batches with resumable shards
- GitHub Actions: small fixture-based checks only; no restricted data
