# PlanMargin design QA

## August 18 campaign-workbench audit

- Accepted visual reference: `docs/assets/debugger/desktop-concept.png`.
- Authenticated investigation: `/tmp/planmargin-authenticated-investigation.png`.
- Corrected Camera state: `/tmp/planmargin-camera-playback-fixed.png`.
- Corrected 3DGS state: `/tmp/planmargin-3dgs.png`.
- Mobile investigation: `/tmp/planmargin-mobile-investigation-fixed.png`.

The default product surface is now a dense investigation table rather than the
campaign-result presentation. It indexes all 3,200 sealed proposals, offers
three campaign-wide rankings, supports two-proposal comparison, and opens the
exact 32-proposal cell and proposal-specific analysis. The report is a separate
section. The palette, compact typography, dividers, cyan selection state, and
full-bleed sensor treatment remain faithful to the accepted visual system.

The rendered audit found and fixed two material responsive defects:

1. The embedded simulator hid its internal top bar but retained that grid row.
   The scene therefore occupied 70 px while the timeline incorrectly occupied
   498 px. Embedded Camera, Planning, 3DGS, and LiDAR now receive the full scene
   row and the timeline receives its intended 88 px.
2. `backdrop-filter` on the product header made the mobile fixed navigation
   position relative to the 64 px header, covering the brand and connection
   state. Mobile now uses an explicit two-row 112 px header.

Browser verification covered 1280 × 720 and 390 × 844 viewports with no
document-level horizontal overflow and no console warnings or errors. Camera
advanced 099 → 114 while native box count changed 35 → 34; Planning advanced
000 → 015; campaign comparison accepted two different method/cell proposals;
proposal analysis cited the selected sealed record; and source/left/right 3DGS
views rendered the real 1.18M-Gaussian reconstruction.

## Evidence

- Source visual truth path:
  `/Users/ethanvillalovoz/.codex/generated_images/019fe885-3e9f-7100-8bf7-babe11ab4b92/exec-457dbfc3-787c-474d-abd8-e746609d8b45.png`
- Latest implementation screenshot: `/tmp/planmargin-production-audit/03-3dgs.png`
- Latest Camera screenshot: `/tmp/planmargin-production-audit/01-camera.png`
- Latest Planning screenshot: `/tmp/planmargin-production-audit/02-planning.png`
- Latest LiDAR screenshot: `/tmp/planmargin-production-audit/04-lidar.png`
- Latest assistant screenshot: `/tmp/planmargin-production-audit/05-assistant.png`
- Latest compact screenshot: `/tmp/planmargin-production-audit/06-compact.png`
- Latest full comparison: `/tmp/planmargin-qa/source-vs-final-e2e.png`
- Latest focused left-controls comparison: `/tmp/planmargin-qa/compare-left-e2e.png`
- Latest focused assistant comparison: `/tmp/planmargin-qa/compare-right-e2e.png`
- Latest viewport: 1280 × 720 CSS pixels in the Codex in-app browser. Compact
  viewport: 760 × 900 CSS pixels.
- Source pixels: 1536 × 1024. Latest implementation pixels: 1280 × 720.
- Density normalization: the source was proportionally resized to 1280 × 853
  and center-cropped to 1280 × 720 before the latest side-by-side comparison;
  browser chrome and surrounding canvas were excluded.
- State: connected real-local evidence; Camera and Planning were exercised as
  independent timelines, with controls and assistant open.

## Findings

No actionable P0, P1, or P2 issue remains.

- [P3] The source mock uses slightly larger display copy and a taller assistant
  card than the implementation. The implementation retains the source hierarchy
  and improved the panel type scale in the final pass, while fitting longer,
  evidence-grounded copy without clipping.
- [P3] The real SHARP reconstruction is softer and more overexposed in the sky
  than the generated design image. This is genuine model output from the local
  source frame, not a replaceable decorative asset.

## Required fidelity surfaces

- Fonts and typography: the implementation uses the same compact grotesk
  hierarchy, weights, truncation, and uppercase micro-label treatment. Panel
  type was increased after the focused comparison; current copy is readable and
  does not overflow.
- Spacing and layout rhythm: the 70 px top bar, full-bleed scene, 240 px left
  controls, right analysis panel, floating sensor switcher, legend, and 88 px
  timeline preserve the source composition. Borders, restrained radii, and
  elevation remain consistent.
- Colors and tokens: near-black chrome, muted blue-gray secondary text, cyan
  selection/candidate, green observed, and coral counterfactual tokens match the
  source intent with sufficient visible contrast.
- Image quality and asset fidelity: the implementation replaces the generated
  concept scene with the requested real WOD frame and genuine Apple SHARP 3DGS.
  Camera and LiDAR modes use their real local assets. Phosphor icons replace no
  imagery and remain consistent in weight and alignment.
- Copy and content: source-like control labels were retained, while invented
  Gemini and outcome claims were replaced with the actual active provider,
  sealed Stage-0 measurements, and an explicit Perception-vs-Motion boundary.

## Intentional product deviations

- The source mock says “Ask Gemini.” This run has no `GEMINI_API_KEY`, so the UI
  truthfully shows “Ask analysis” and “Deterministic local provider.” When the
  backend is explicitly configured for Gemini, the same surface labels Gemini.
- The source mock draws planning overlays over its 3DGS view. The real visual
  Perception segment is not geometrically registered to the separate WOMD
  Motion evidence, so the implementation uses a dedicated Planning tab.
  Camera displays only native WOD camera boxes, and 3DGS/LiDAR display only
  source-frame geometry.
- Recorded Camera is the only temporal sensor stream. The real 3DGS and LiDAR
  artifacts are source-frame spatial assets, so their timelines are locked to
  frame 099 and playback is disabled instead of advancing an unchanged scene.

## States and interactions verified

- Authenticated local connection and memory-only token modal.
- Camera playback advanced from frame 099 to frame 109 in 0.85 seconds.
- Planning replay visibly advanced the sealed motion evidence from step 070 to
  078 in 0.85 seconds; the Camera frame remained independent.
- Camera, calibrated 1.18M-Gaussian SHARP 3DGS, and 50k-return LiDAR modes.
- Spatial modes replace the timeline with explicit single-asset provenance;
  source frame 099 remains locked and Camera overlays remain absent.
- 3D orbit-capable surface, 3DGS source/novel viewpoints, and LiDAR reset.
- Evidence modal auto-closed after authentication and reopened with consistent
  dark-theme status, campaign, select, proposal, and detail contrast.
- Static actor and mutation facts no longer masquerade as dropdown controls;
  nonfunctional overflow and timeline-setting controls were removed.
- Bounded method-comparison action and free-text evidence question.
- Compact 760 × 900 viewport without horizontal document overflow.
- Current clean-tab console: no warning or error entries after authentication,
  Camera playback, stress replay, 3DGS, LiDAR, modal, and assistant actions.

## Comparison history

1. Initial implementation comparison found a P1 3DGS camera mismatch: SHARP's
   OpenCV coordinates were treated as a generic Three.js world model, producing
   a white rear-view silhouette. Fixed with the documented 180° x-axis
   coordinate transform and embedded 1600 px / 1920 × 1280 camera calibration.
2. The next P1 comparison was blank because OrbitControls retargeted the camera
   to the untransformed positive-z center. Fixed by storing the calibrated
   negative-z reconstruction target for initialization and reset. Post-fix
   evidence: `/tmp/planmargin-qa/final-3dgs.png`.
3. The Camera comparison found P2 actor boxes displaced from the real sedan and
   pedestrian. Fixed their responsive percentages against frame 099. Post-fix
   evidence: `/tmp/planmargin-qa/final-camera.png`.
4. The first focused panel comparison found P2 type-density drift relative to
   the source. Increased control and assistant type scales without changing
   panel geometry. Post-fix evidence:
   `/tmp/planmargin-qa/compare-left-v2.png` and
   `/tmp/planmargin-qa/compare-right-v2.png`.
5. End-to-end interaction QA found a P1 playback-semantics failure: the common
   frame index advanced in 3DGS and LiDAR even though only one real spatial
   asset exists for each mode. Fixed by making Camera explicitly temporal,
   locking spatial modes to source frame 099, replacing the irrelevant timeline
   with spatial provenance, and adding source/left/right 3DGS viewpoints.
   Post-fix evidence:
   `/tmp/planmargin-qa/final-3dgs-source.png` and
   `/tmp/planmargin-qa/final-3dgs-novel.png`.
6. The connected evidence modal had a P1 contrast regression from retained
   light-theme status, select, run, and proposal-selection backgrounds. Fixed
   every explicit light surface with the app's dark tokens and verified the
   full records browser visually in the in-app browser.
7. End-to-end control inspection found P2 false affordances and an inert stress
   replay. Static mutation fields now read as sealed facts and unused controls
   were removed.
8. The latest normalized full-view and focused comparisons found no new P0,
   P1, or P2 visual mismatch. The implementation keeps the approved hierarchy
   while using truthful source-frame semantics and evidence-grounded copy.
9. Final rendered inspection found a P2 overlap between the spatial viewpoint
   controls and the global Camera/3DGS/LiDAR switcher. Moved the source/novel
   and reset controls below the switcher at desktop and compact breakpoints,
   then recaptured the final 3DGS state.
10. User playback review exposed a P0 truthfulness failure: Camera actor boxes,
    returns, and trajectory curves were hardcoded screen graphics and did not
    follow the recorded video. Removed every fabricated Camera overlay,
    downloaded this segment's official WOD `camera_box` component, exported
    8,364 native annotations across all 199 frames, and rendered them from their
    per-frame coordinates and stable track IDs. Browser proof advanced frame
    099 to 110 and the annotation signature changed with it; the visible
    crossing vehicle left the frame and its box disappeared. The planning
    controls now state that WOMD evidence is a separate, unregistered
    experiment. Post-fix screenshots were captured directly in the in-app
    browser at frames 099 and 110.
11. The same review exposed a second P0 truthfulness failure: Camera playback
    changed the independent planning timestep, “Show conflict frame” mapped a
    WOMD metric index onto an unrelated Perception image, and stress replay
    advanced that image as if it depicted the planning experiment. Planning is
    now a separate tab backed by the authenticated WOMD trajectory run and its
    own 81-step timeline. The Camera timeline no longer mutates planning state;
    “Show planning conflict” opens the actual minimum-margin planning step; and
    replay advanced planning step 070 to 078 without changing the Camera frame.
12. The overnight control audit found one-frame skip affordances that looked
    inert at normal playback scale, a stale spatial timeline, overlapping
    planning marker labels, and a disconnect transition that could leave the UI
    evaluating a removed run. The controls now jump a visible second, spatial
    views explain their single-asset semantics, marker callouts are separated,
    and disconnect returns safely to Camera before clearing planning state.
13. The final runtime audit removed the bundled synthetic parser, demo run,
    export path, and unused legacy debugger components. The production bundle
    now has no synthetic fallback; only API-shaped unit-test fixtures remain.
14. A clean route-order pass uncovered a P1 remount bug: entering 3DGS or LiDAR
    directly after Planning recreated the sensor component after its reactive
    mode effect had already sampled the current state, leaving an empty canvas.
    The post-render hook now explicitly loads the active connected view; both
    Planning → 3DGS and Planning → LiDAR were retested successfully.
15. Compact 760 × 900 QA exposed two weak responsive choices: the scene label
    crowded the status/action row, and the one-second controls disappeared.
    The compact top bar now keeps status and actions while dropping the
    redundant scene label, and −1s/+1s remain visible and functional.
16. A clean authenticated reload exposed a P1 initialization race: the
    post-render startup path and the sensor-mode effect could request scene
    metadata simultaneously, allowing one transient failure to leave a stale
    full-screen error over successfully loaded imagery. Scene initialization is
    now deduplicated, successful initialization clears stale errors, and a
    regression test covers the already-connected mount path.
17. The production-readiness pass found two P2 interaction gaps. Rapid camera
    playback could accumulate obsolete frame downloads, and the visually thin
    timeline also had a thin pointer target. New frame requests now abort the
    previous request, the slider keeps a 24 px interaction area around its 2 px
    visual track, and reduced-motion preferences disable nonessential motion.
18. Keyboard QA found a P2 modal-accessibility gap. The evidence dialog now
    receives initial focus, traps Tab/Shift+Tab, closes with Escape, and returns
    focus to the invoking control. The final clean browser pass exercised these
    behaviors at desktop and compact widths.

## Implementation checklist

- [x] Match the approved full-bleed simulator composition.
- [x] Replace concept imagery with authenticated real local sensor assets.
- [x] Preserve honest provenance and provider labeling.
- [x] Verify core interactions and responsive containment in the in-app browser.
- [x] Compare full view and focused regions after the last visual fix.

final result: passed
