# Reproducing the complete local workspace

PlanMargin has two reproducibility levels:

1. A clean clone can reproduce every data-free test and the aggregate product.
2. A registered WOD user can reproduce the private campaign and sensor
   workspace locally. Those artifacts remain ignored and are never silently
   uploaded.

Run `uv run --frozen planmargin-doctor` at any time. It reports the exact state
of the public bundle, sealed campaign, Stage-0 planning replay, exact campaign
proposal replay, Perception inputs, SHARP model output, prepared Sensor Lab,
Beam reconciliation, planning-linked Gaussian decision, and JAX controller
decision. `--require full` exits nonzero unless the complete local workbench
and research program are ready.

After installing the locked environment and authorizing WOD access, the entire
runbook below is available as one resumable command:

```bash
uv run --frozen planmargin-bootstrap-workbench --accept-waymo-terms
```

Pass `--plan` to inspect every phase without running it, or `--device mps`,
`--device cuda`, or `--device cpu` to require the reconstruction backend. The
command reuses capabilities that already pass the doctor and stops at the first
failed deterministic phase.

## 1. Install the locked environments

```bash
uv sync --frozen
cd web/debugger
npm ci
cd ../..
```

Use Python 3.11 and Node 24.15.0 (`.nvmrc`). A C++20 compiler is required for
the native interaction-metrics extension. On macOS, if Apple blocks the
compiler behind an unaccepted Xcode license, review and accept it with
`sudo xcodebuild -license` before running `uv sync`.

Current Apple-silicon macOS and x86-64 Ubuntu Linux are the tested platforms.
The locked environment excludes the unused Triton compiler backend; all torch
paths in this repository use eager execution, and CI tests that same lockfile
without uninstalling or replacing packages after synchronization.

## 2. Authorize WOD access

Review the current [Waymo Dataset License Agreement for Non-Commercial
Use](https://waymo.com/open/terms/), register through Waymo's official access
workflow, and authenticate the Google Cloud CLI outside the repository:

```bash
gcloud auth login
gcloud auth application-default login
./scripts/verify_womd_access.sh
```

No Google credential, token, or account identifier is written into PlanMargin.

## 3. Reproduce the planning evidence

These commands are resumable and keep every scenario-level record under the
ignored `artifacts/` tree. They intentionally take real compute time.

```bash
uv run --frozen planmargin-select-scenarios \
  --output artifacts/stage-0/scenario-selection.json

uv run --frozen planmargin-build-empirical-support

uv run --frozen planmargin-validate-lead-braking-family \
  --manifest artifacts/stage-0/scenario-selection.json \
  --output artifacts/family-validation/lead-braking-family.json

uv run --frozen planmargin-run-matched-campaign --readiness-only
uv run --frozen planmargin-run-matched-campaign --max-new-cells 1
uv run --frozen planmargin-run-matched-campaign --resume

uv run --frozen planmargin-build-analytics

uv run --frozen planmargin-build-beam-features \
  --source-mode sealed-support \
  --support-dir artifacts/realism/lead-braking-support-v1 \
  --output-dir artifacts/beam-features/lead-braking-v1
```

The campaign coordinator seals its environment and configuration. Do not copy
an incomplete campaign directory between revisions or weaken its resume checks.
The published aggregate result describes the recorded v1 run; a new execution
must be reported as a reproduction, not silently substituted for that record.

## 4. Reproduce the retained planning replay

The product only replays trajectories that were actually retained. Build the
Stage-0 controller comparison and export its verified rollout collection:

```bash
uv run --frozen planmargin-controller-comparison
uv run --frozen planmargin-export-rollout-records
```

The contracts are documented in [controller comparison](controller-comparison.md)
and [rollout records](rollout-record.md). The expected product path is:

```text
artifacts/stage-0/rollout-records.json
```

Campaign proposals retain trajectory hashes and measured outcomes, not full
trajectories. PlanMargin does not invent missing playback. Retain an accepted
proposal by its one-based campaign identity when exact inspection is needed:

```bash
uv run --frozen planmargin-retain-proposal-replay \
  --method random \
  --seed 1 \
  --selection-order 8 \
  --proposal-number 12
```

The exporter re-executes both planners twice, compares trajectory hashes,
outcomes, interaction metrics, scenario validation, and input immutability to
the sealed campaign record, then atomically installs the replay package. The
package remains under ignored `artifacts/proposal-replays/` and is not approved
for redistribution.

## 5. Reproduce the Sensor Lab

Train the real WOMD trajectory model first, then bootstrap the Sensor Lab. The
bootstrap downloads only the six pinned WOD v2 Perception Parquet components,
installs Apple SHARP at a pinned revision, predicts both source-frame 3DGS
assets using MPS/CUDA/CPU, and generates the camera, annotation, LiDAR, and
calibrated-trajectory manifests:

```bash
uv run --frozen planmargin-train-trajectory-model --epochs 64
uv run --frozen planmargin-bootstrap-sensor --accept-waymo-terms
```

Use `--device mps` to require Apple Metal, or `--device cpu` for the slowest but
most portable path. Use `--skip-download` only when the required authorized
Parquet files are already in the documented local directory.

## 6. Verify and launch

```bash
uv run --frozen planmargin-doctor --require full
.venv/bin/python scripts/launch_debugger.py
```

The doctor validates content seals, campaign-to-replay identity, database
hashes, all 199 frame hashes, native annotations, both PLY hashes, and the
expected product boundaries before declaring the complete workbench ready.

## What cannot be made one-click public

Raw WOD camera/LiDAR data and per-scenario records are not unrestricted public
assets. A public Hugging Face repository cannot prove that every downloader is
registered with Waymo. PlanMargin therefore provides code, aggregate evidence,
and a deterministic authorized bootstrap rather than mirroring restricted
files or replacing them with synthetic data.
