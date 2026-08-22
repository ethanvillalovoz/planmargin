# Local setup and WOMD access

This workflow streams one scenario from a fixed Waymo Open Motion Dataset
(WOMD) training shard. It does not download the complete dataset, commit raw
records, or place Google credentials in this repository.

## 1. Review the data terms

Before accessing WOMD, review the current
[Waymo Dataset License Agreement for Non-Commercial Use](https://waymo.com/open/terms/)
and the [Waymo Open Dataset FAQ](https://waymo.com/open/faq/). As reviewed for
Stage 0 on August 9, 2026, the published agreement is dated March 2025. Among
other conditions, it limits use to non-commercial purposes, requires specified
attribution for derivative IP, restricts redistribution, and incorporates the
Waymo website terms. The official terms—not this summary—govern all use.

Use the official [download and access page](https://waymo.com/open/download/)
to sign in and obtain access. Downloading or using the dataset constitutes
agreement to the published terms.

## 2. Configure credentials outside the repository

Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install), then
authenticate both the CLI and Application Default Credentials (ADC):

```bash
gcloud auth login
gcloud auth application-default login
```

The `gcloud` configuration and ADC file belong in their operating-system user
configuration locations. Do not copy either into this repository and never
commit an access token, service-account key, or credential JSON file.

Run the metadata-only access check:

```bash
./scripts/verify_womd_access.sh
```

The command uses ADC—not merely the active CLI identity—to read the shard's
metadata. It prints only the dataset version, split, shard name, object size,
and boolean authentication status. It intentionally suppresses account names
and tokens.

## 3. Create the pinned Python environment

Install [uv](https://docs.astral.sh/uv/) and a C++20 compiler. On macOS, the
compiler is provided by the free Xcode Command Line Tools:

```bash
xcode-select --install
```

Then run:

```bash
uv sync --frozen
```

The lockfile pins the complete transitive environment. Waymax itself is pinned
to commit `a64dfec9be8576b60d9cecc94f406d9812d4a7d0`. The project uses Python 3.11
because the system Python may be newer than TensorFlow supports. Environment
creation compiles the small C++20/pybind11 interaction-metrics extension
locally; it does not download a platform-specific project binary.

The tested platforms are current Apple-silicon macOS and x86-64 Ubuntu Linux.
The lock excludes PyTorch's optional Triton compiler backend because PlanMargin
uses eager execution only; this is part of the project configuration and Linux
CI runs the same unmodified `uv sync --frozen` environment.

## 4. Run the deterministic smoke test

```bash
uv run planmargin-waymax-smoke-test \
  --output artifacts/stage-0/waymax-smoke-test.json
```

The command streams only the first TFExample from training shard
`00000-of-01000`, preserves its `scenario/id`, completes the unmodified
eight-second rollout twice, and fails if the trajectory hashes differ. It
exports only a small report containing configuration, timing, peak process
memory, hashes, and aggregate Waymax metrics.

The default output path is ignored by Git. The checked-in Stage 0 report under
`experiments/stage-0/` is intentionally limited to metadata and aggregate
results. Raw WOMD data remains governed by its own license and must not be
committed.

## 5. Build the local Beam feature dataset

After the empirical-support workflow has completed, transform its sealed real
training evidence without another cloud read:

```bash
uv run --frozen planmargin-build-beam-features \
  --source-mode sealed-support \
  --support-dir artifacts/realism/lead-braking-support-v1 \
  --output-dir artifacts/beam-features/lead-braking-v1
```

Apache Beam 2.74.0 runs with local DirectRunner. The resulting source
checkpoints, partitioned Parquet, DuckDB file, and private manifest remain under
the ignored `artifacts/` tree. See [the Beam pipeline contract](beam-feature-pipeline.md)
before using `womd-direct`, which performs authorized dataset reads.

## Optional local cache

For later experiments, individual authorized shards may be copied under
`data/raw/`; everything below `data/` except its README is ignored. Prefer
streaming for this smoke test because only its first record is needed.

Validation access is never implicit. The CLI rejects a validation URI unless
`--allow-validation-access` is supplied under a separately authorized protocol.
That override is not part of the reproduction workflow.

## Build the local Perception Sensor Lab

The product bootstrap downloads only the six pinned WOD v2 Perception
components needed by the visual scene, installs Apple SHARP at a pinned
revision, generates both source-frame 3DGS assets on MPS/CUDA/CPU, and prepares
the camera, native annotation, LiDAR, and calibrated-trajectory manifests. The
trajectory model must be trained first from the authorized WOMD inputs:

```bash
uv run --frozen planmargin-train-trajectory-model --epochs 64
uv run --frozen planmargin-bootstrap-sensor --accept-waymo-terms
```

Run `uv run --frozen planmargin-doctor` before and after preparation for an
explicit capability report. See the
[complete workspace runbook](reproducing-the-workspace.md) for campaign and
planning-replay reproduction; the sensor bootstrap does not fabricate or
download those private experiment records.

## Optional Gemini explanation adapter

The evidence assistant is offline by default and needs no additional package:

```bash
uv run --frozen planmargin-ask-evidence \
  --question "What is the defensible claim?"
```

Only if you have independently verified that a Google AI Studio project is on
the current free tier, install the pinned optional SDK with
`uv sync --frozen --extra assistant`. Keep `GEMINI_API_KEY` in the environment and use
`--provider gemini --confirm-free-tier`. Hosted mode receives public aggregates
only and cannot be combined with local evidence. See the complete
[assistant privacy and provider contract](evidence-assistant.md) before use.
