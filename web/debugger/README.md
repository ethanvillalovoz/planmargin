# PlanMargin campaign workbench

The hosted Space is the aggregate-only public application. It contains no WOD
frames, point clouds, scenario paths, proposal records, or local credentials.
Clone the [GitHub repository](https://github.com/ethanvillalovoz/planmargin) for
the authenticated local Workbench and Sensors surfaces.

This Angular, TypeScript, Three.js, and Spark application is PlanMargin's local
counterfactual-driving workbench. Its default workspace combines four visible
responsibilities:

- replay 199 recorded FRONT-camera frames with native per-frame tracked 2D
  boxes from the same local Waymo Open Dataset Perception segment;
- switch between 1,179,648-primitive Apple SHARP 3D Gaussian reconstructions
  of moving frame 20 and stopped frame 99, plus a 50,241-primitive LiDAR field;
- compare the calibrated recorded ego path, a real-WOMD-trained JAX prediction,
  and a constant-velocity baseline inside the moving-frame reconstruction;
- replay the sealed WOMD planning trajectories on their own timeline, separate
  from the 199-frame Camera timeline and source-frame 3DGS/LiDAR assets; and
- query the authenticated evidence assistant without exporting local records.

The visual sensor scene and the planning evidence are separate dataset
segments. The interface labels that boundary explicitly. The 3D reconstruction
is visual context and a rendering demonstration, not planner input or safety
evidence, and PlanMargin does not inspect the production Waymo Driver.

## Prepare the ignored local sensor scene

From the repository root, the authorized bootstrap downloads the six pinned
WOD components, installs the pinned SHARP tool, generates the source-frame
3DGS assets, and writes only ignored `data/` and `artifacts/` outputs. Generate
the real WOMD model before building the calibrated trajectory overlay:

```bash
uv run --frozen planmargin-train-trajectory-model --epochs 64
uv run --frozen planmargin-bootstrap-sensor --accept-waymo-terms
```

For already-downloaded inputs, pass `--skip-download`. The preparation extracts
199 camera JPEGs and tracked boxes, deterministically fits the same-frame LiDAR
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

The recommended launcher is `uv run --frozen planmargin-workbench`; it opens an
authenticated URL automatically and removes the launch token after exchanging
it for an HttpOnly browser-session cookie. Use the manual connection dialog
only to recover a separately opened local browser.

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
