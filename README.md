# PlanMargin

**Change a driving scenario. Test two planners. Inspect exactly what happened.**

<!-- prettier-ignore -->
[![CI](https://github.com/ethanvillalovoz/planmargin/actions/workflows/ci.yml/badge.svg)](https://github.com/ethanvillalovoz/planmargin/actions/workflows/ci.yml) ![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB) ![Node 24](https://img.shields.io/badge/Node-24-5FA04E) [![License](https://img.shields.io/badge/Code-Apache--2.0-blue.svg)](LICENSE)

PlanMargin is a local **counterfactual planner-testing workbench**. It takes a
recorded Waymo Open Motion Dataset scenario, changes the lead vehicle's braking
timing and speed, then compares a tested controller with a conservative reference.

The question is specific: **can a small, realistic change make the tested
planner fail while the reference still succeeds?** You get the result,
the decision gates, and the exact trajectories—not just a dashboard of scores.

[Run an experiment](docs/running-experiments.md) ·
[Follow a real case study](docs/case-study-close-clearance.md) ·
[Workbench guide](docs/using-the-workbench.md) ·
[Contribute](CONTRIBUTING.md)

## The workflow

1. **Configure** a lead-vehicle change on one of ten selected real scenarios.
2. **Run** both controllers on the original and changed scene, twice each.
   Follow actual execution stages, cancel a run, or return to its saved history.
3. **Understand the decision.** Compare before-and-after clearance, planner
   outcomes, physical validity, repeatability, and recorded-behavior support.
4. **Inspect the exact replay.** Jump to minimum clearance, play or step through
   the trajectory, refresh the same run, and export its verified result.

For example, [one reproduced change](docs/case-study-close-clearance.md) narrowed
the tested controller's minimum signed clearance from **0.295 m to 0.032 m**;
the reference retained **4.797 m**. Both controllers still succeeded, so
PlanMargin explicitly reports **not a qualifying regression**. The case study
includes the configuration, metrics, provenance, and reproduction commands.

The runner currently supports one lead-braking mutation family and two fixed
Waymax IDM controller configurations. It is not a general-purpose planner
plugin platform, the Waymo Driver, or a vehicle-safety certification system.

## Quick start

Choose the amount of setup you need:

| Goal | Data required | Start here |
| --- | --- | --- |
| Browse the measured research results | None; aggregate records are included | Public application below |
| Execute a new planning experiment | Authorized WOMD access and ten validated scenarios | Planning-only setup below |
| Reproduce the full campaign, sensors, and model studies | Larger licensed local workspace | [Full reproduction runbook](docs/reproducing-the-workspace.md) |

### Public application — no dataset account needed

Requires Node 24.15/npm 11. With `nvm` installed:

```bash
git clone https://github.com/ethanvillalovoz/planmargin.git
cd planmargin
nvm install
nvm use
cd web/debugger
npm ci
npm start
```

Open [localhost:4200](http://127.0.0.1:4200). Aggregate evidence works immediately.
The app identifies unavailable private capabilities; it does not invent camera
frames or substitute synthetic scenarios.
There is intentionally no hosted dashboard in this release.

### Planning-only — execute real experiments

Also requires Python 3.11, [uv](https://docs.astral.sh/uv/), a C++20 compiler,
the Google Cloud CLI, and an account authorized for the Waymo Open Dataset.
From the repository root, after the frontend installation above:

```bash
uv sync --frozen
gcloud auth login
gcloud auth application-default login
./scripts/verify_womd_access.sh
uv run --frozen planmargin-prepare-planning --accept-waymo-terms
uv run --frozen planmargin-workbench --planning-only
```

Review [the dataset terms](https://waymo.com/open/terms/) and obtain access
**before** accepting the terms flag. Stop the frontend-only `npm start` process
before launching the workbench; both use port 4200.

The launcher opens an authenticated local session. Choose **Scenario 1**, keep
**+0.0 s / 0.90×**, and click **Run experiment**. No GPU, Gemini key, paid cloud
resource, or sensor reconstruction is needed. The Python lock includes research
dependencies; planning-only mode reduces data preparation, not installation size.

An empirical-support model is optional for execution, but required to qualify
a regression. Prepare it with:

```bash
uv run --frozen planmargin-build-empirical-support
```

This scans 16 specified real WOMD shards and resumes interrupted preparation.
Without it, the support gate is explicitly unavailable. See the
[experiment guide](docs/running-experiments.md) for setup, CLI execution,
resource limits, rejected changes, and recovery.

## What else is in the workbench?

| Surface | Engineering task | Boundary |
| --- | --- | --- |
| Investigate | Rank recorded changes, inspect gates, compare attempts, open retained replays | Frozen campaign and new local experiments remain separate |
| Test health | Inspect execution integrity, versioned coverage, and diagnostic paths | Saved test report; links to the live local job history |
| Sensor lab | Inspect synchronized camera boxes, LiDAR, and three SHARP 3DGS reconstructions | Separate WOD Perception segment, not the planning scene |
| Models | Review prediction and NVIDIA inference studies and promotion decisions | Research models are not silently used as planners |
| Ask PlanMargin | Retrieve verified campaign facts; optionally explain them with Gemini | Bounded evidence guide, not an autonomous agent or access to new private jobs |

The [workbench guide](docs/using-the-workbench.md) explains each surface. The
[research overview](docs/research-evidence.md) preserves the complete measured
results, model comparisons, architecture, and explicit no-go decisions.

The original campaign evaluated **3,200 proposals across ten recorded scenes**
and found **zero qualifying regressions**. Search validity improved under the
tested Bayesian method; failure-discovery superiority was not demonstrated.
Interactive runs do not retroactively change that experiment.

## How it works

```text
Real WOMD scenario + bounded change
  → isolated, cancellable Waymax worker
  → original and changed × tested and reference × repeated execution
  → C++ interaction metrics + independent finding gates
  → hash-sealed local result and exact trajectory collection
  → authenticated FastAPI → Angular investigation and replay
```

The wider research pipeline includes Beam/Parquet/DuckDB analytics, JAX and
PyTorch prediction models, and separately measured ONNX/TensorRT inference.
See [architecture and implementation responsibilities](docs/research-evidence.md#system-architecture).

## Data, privacy, and limitations

- **Real data stays local.** Public code and aggregate results are included;
  licensed scenarios, trajectories, camera frames, and reconstructions are not.
  Preparation requires your own authorized access and may need network access
  again when a source scenario is loaded.
- **Bounded execution.** One worker per workspace, a 15-minute per-run limit,
  200 retained jobs, strict parameter validation, and explicit failure/cancel
  states. Results survive server restarts. This is a single-user local tool.
- **Verified does not mean safe.** Hashes verify integrity, not authorship or
  correctness by themselves. Physical, support, determinism, and planner
  outcome gates are shown separately.
- **Gemini is optional.** It requires your key and explicit free-tier
  confirmation. Only public aggregate facts are sent; hosted output is
  validated and fallback is labeled. It does not inspect new private jobs.
  See [assistant setup and scope](docs/evidence-assistant.md).
- **Research boundaries remain visible.** Some model and RL hypotheses failed
  qualification. Historical synthetic RL qualification is labeled as such;
  no synthetic scenario substitutes for the interactive real-data workflow.

No setup command hosts the application or publishes licensed data. See
[data handling](data/README.md), [security](SECURITY.md), and
[known dependency exceptions](docs/dependency-security.md).

## Development and verification

macOS Apple silicon is exercised locally; Ubuntu x86-64 is covered by CI.
Windows/WSL and other browser engines are not verified targets.

```bash
uv run --frozen ruff check .
uv run --frozen pytest
uv build
cd web/debugger
npm run check
npm run e2e
```

Tests cover numerical parity, evidence contracts, auth, worker lifecycle,
idempotency, cancellation, replay integrity, and desktop/mobile interactions.
Browser contract tests use fixtures; the [case study](docs/case-study-close-clearance.md)
documents the separately executed real-data path. Stop the development server
before `npm ci`; replacing dependencies underneath it can break the running app.

| Directory | Responsibility |
| --- | --- |
| [src/planmargin](src/planmargin) | Simulation, search, jobs, evidence API, setup, and analysis |
| [cpp](cpp) | C++20 metrics and the separate C++17 TensorRT runner |
| [web/debugger](web/debugger) | Angular workbench and browser tests |
| [schemas](schemas) / [tests](tests) | Versioned contracts and verification |
| [docs](docs) | Reproduction guides, protocols, decisions, and measured results |

## License and affiliation

PlanMargin is independent and is **not affiliated with, endorsed by, or
representative of Waymo LLC**. It does not evaluate the production Waymo Driver.

This software was made using the Waymo Open Dataset, provided by Waymo LLC
under the [Waymo Dataset License Agreement for Non-Commercial Use](https://waymo.com/open/terms/).
WOD source data and restricted per-scenario derivatives are not included.

Original code is licensed under [Apache License 2.0](LICENSE). Dataset, model,
and third-party terms remain separate; see [NOTICE](NOTICE).
