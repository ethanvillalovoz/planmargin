# PlanMargin workbench design

PlanMargin is a local counterfactual stress-testing workbench. Its primary user
question is: **what is the smallest behaviorally plausible scene change that
causes the tested planner to fail while a reference planner succeeds?** The
workspace makes the scene, mutation, evidence source, and claim boundary
visible in one synchronized engineering surface.

## Workspace contract

The simulator uses one full-bleed scene rather than separate product pages:

1. The **product bar** switches among Workbench, Sensors, and Evidence and
   shows the authenticated local-record state without a setup wizard.
2. **View-specific controls** expose only real actions or sealed facts: native
   tracked boxes in Camera, read-only mutation/outcome/metric evidence in
   Planning, and source-frame provenance in 3DGS/LiDAR.
3. The **sensor switcher** changes among the separate Planning replay,
   recorded Camera, real Apple SHARP 3D Gaussian reconstruction, and same-frame
   LiDAR Gaussian field.
4. **Evidence analysis** exposes the active provider, bounded explanations,
   source limitations, and direct questions over sealed aggregate evidence.
5. The **timeline** scrubs or plays all 199 recorded Camera frames or the
   81-step Planning run as independent clocks. 3DGS and LiDAR replace playback
   controls with a spatial-inspection footer because they are single-frame
   assets.

Every capability named in the workspace has a visible status, action, result,
evidence source, and limitation. Camera playback, 3D
orbit/source/novel/reset, layer toggles, one-second seeking, planning replay,
and assistant questions are
functional rather than decorative.

## Visual system

The visual system is an original dark engineering instrument inspired by
autonomous-vehicle simulation tools, not a copy of Waymo product chrome.
Near-black surfaces preserve focus on sensor imagery; cyan identifies selected
controls and candidate paths; green identifies observed paths; coral identifies
counterfactual paths or conflicts. Corners, borders, and shadows remain
restrained so dense evidence reads as an operational tool.

The PlanMargin mark is original repository artwork. No Waymo logo, proprietary
UI, map tile, or brand asset is copied. “Waymo Open Dataset” describes the
input source, not affiliation or production-driver access.

## Sensor and evidence boundary

- Camera and LiDAR come from one local Waymo Open Dataset v2 Perception
  segment. Camera boxes come from that segment's native `camera_box` component
  and preserve cross-frame track IDs. The SHARP 3DGS is generated from camera
  frame 99 of that segment.
- The planning overlay and counterfactual outcome come from a separate,
  privacy-reduced WOMD Motion/Stage-0 evidence path. They are not geometrically
  registered to the visual Perception segment and are labeled as separate.
- The SHARP result is a genuine learned 3D Gaussian reconstruction and supports
  nearby novel views. It is not planner input, production Waymo reconstruction,
  or safety evidence.
- The same-frame LiDAR view is a deterministic Gaussian field over genuine
  range returns. It is distinct from the earlier exact-planning-scenario
  feasibility field whose frozen 23.66% trajectory-linkage result remains
  `no_go`.
- The deterministic local assistant is fully functional. Optional Gemini is an
  explanation-only adapter over public aggregates and is shown as active only
  when the backend is explicitly configured for it.
- Real sensor assets remain ignored, localhost-only, authenticated, and
  non-exportable.

## Component ownership

- `SimulatorWorkspace`: the unified scene, top bar, controls, modes, timeline,
  and stress replay.
- `ProductShell`: task navigation and the candidate-evidence review surface.
- `SimulatorStore`: sensor mode, independent Camera and Planning clocks,
  source-frame spatial lock, scene layers, and replay state.
- `SensorViewport`: authenticated camera lifecycle, Spark/Three.js renderers,
  calibrated SHARP camera, LiDAR view, native Camera annotations, orbit, reset,
  and cleanup.
- `ScenarioAssistant`: provider status, bounded questions, public-claim limits,
  and privacy disclosure.
- `LocalEvidenceService`: fixed authenticated reads, HttpOnly browser-session
  handshake, `no-store` requests, and binary sensor loading.
- `DebuggerStore`: the existing validated planning evidence and metric samples.

## Verification contract

Before merge:

- strict TypeScript compilation, Vitest, Angular production build, Python API
  contract tests, Ruff, and the repository test suite pass;
- desktop browser testing covers local connection, recorded-frame seeking,
  stress replay, assistant questions, Camera playback, source-frame 3DGS/LiDAR
  switching, 3D source/novel/reset views,
  and a clean current console;
- a compact viewport has no horizontal document overflow and retains access to
  the core controls; and
- the selected design source and implementation screenshot are normalized to
  the same crop and dimensions for hierarchy, workspace composition, palette,
  control legibility, and evidence-boundary clarity.
