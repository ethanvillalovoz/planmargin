# PlanMargin scenario simulator

This Angular, TypeScript, Three.js, and Spark application is PlanMargin's local
counterfactual-driving workbench. Its default workspace combines four visible
responsibilities:

- replay 199 recorded FRONT-camera frames with native per-frame tracked 2D
  boxes from the same local Waymo Open Dataset Perception segment;
- orbit a 1,179,648-primitive Apple SHARP 3D Gaussian reconstruction of frame
  99 and a 50,241-primitive same-frame LiDAR Gaussian field;
- replay the sealed WOMD planning trajectories on their own timeline, separate
  from the 199-frame Camera timeline and source-frame 3DGS/LiDAR assets; and
- query the authenticated evidence assistant without exporting local records.

The visual sensor scene and the planning evidence are separate dataset
segments. The interface labels that boundary explicitly. The 3D reconstruction
is visual context and a rendering demonstration, not planner input or safety
evidence, and PlanMargin does not inspect the production Waymo Driver.

## Prepare the ignored local sensor scene

The preparation step reads only already-downloaded local inputs and writes only
ignored `data/` and `artifacts/` outputs:

```bash
uv run python scripts/prepare_perception_scene.py
```

It expects the local Perception Parquet files—including `camera_box.parquet`—
and SHARP PLY described by the script's validation errors. It extracts the 199
camera JPEGs and tracked boxes, deterministically fits the same-frame LiDAR
Gaussian field, hashes every asset, and writes
`artifacts/sensor-scene/waymo-front/manifest.json`.

## Run locally

In one terminal at the repository root:

```bash
uv run --frozen planmargin-serve-evidence
```

In another terminal, using the Node version in `.nvmrc`:

```bash
cd web/debugger
npm ci
npm start
```

Open `http://127.0.0.1:4200`, choose **Connect local evidence**, and paste the
ephemeral token printed by the API. The token stays in memory only. It is not
placed in browser storage, URLs, logs, or exports.

The deterministic local assistant is the default and costs nothing. If the API
is deliberately started with the repository's optional Gemini provider, the
UI displays that provider by name. Gemini receives only the existing public
aggregate allowlist; raw frames, 3D assets, trajectories, and the raw question
remain local.

## Quality checks

```bash
npm run check
npm run format:check
npm audit --audit-level=moderate
```

`npm run check` performs strict application and test typechecking, Vitest, and
an optimized production build. Three.js, Spark, and the sensor renderer remain
lazy chunks. The accepted visual contract is documented in
[`../../docs/debugger-design.md`](../../docs/debugger-design.md).

## Local-data boundary

All sensor and evidence requests are fixed authenticated `GET` calls to
`http://127.0.0.1:8765/api/v1`, with `no-store`, omitted credentials, and no
referrer. The API accepts no client path, SQL, mutation, or write operation.
Disconnecting clears the token and removes access to every local sensor asset.

The production application contains no bundled demo run or synthetic fallback.
It starts disconnected, and its planning, camera, 3DGS, and LiDAR views render
only authenticated local evidence. Unit tests use small data-free API-shaped
fixtures; those fixtures are never imported into the application bundle.
