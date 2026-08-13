# PlanMargin engineering workbench design

PlanMargin is a local counterfactual stress-testing workbench. Its primary user
question is: **what is the smallest behaviorally plausible scene change that
causes the tested planner to fail while a reference planner succeeds?** The UI
must make that question, the evidence path, and the claim boundary visible
before it exposes implementation detail.

## Information architecture

The persistent navigation owns five surfaces:

1. **Overview** explains the product, selected planner outcomes, four-step
   workflow, and Waymo-scenario → Beam-features → matched-search → sealed-evidence
   pipeline.
2. **Scenario Lab** synchronizes scene replay, run/case selection, controller
   evidence, and interaction metrics.
3. **Search Campaign** compares Bayesian and random search under matched
   physical-rollout budgets and displays the frozen H1/H2/H3 decisions.
4. **Evidence Assistant** answers five allowlisted questions over measured facts
   and shows citations, source seals, limitations, provider scope, and privacy.
5. **Gaussian Field** renders the authenticated local PLY and explains the
   exact no-go gate that keeps it experimental.

The interface never presents a terminal-only capability as a product feature.
If a capability is named in the workbench, it must have a visible status,
action, result, evidence source, and limitation.

## Visual system

The workbench uses a bright engineering-instrument palette rather than copying
Waymo branding or product chrome. White and cool gray surfaces keep dense
evidence readable. Deep blue-gray is the primary ink; coral identifies the
tested planner or a no-go boundary; cyan identifies the reference planner;
green identifies passed validation; violet identifies explanation; and lime
identifies experimental geometry. Corners are restrained and shadows are used
only for hierarchy.

The PlanMargin mark is original repository artwork. No Waymo logo, proprietary
UI, map tile, or brand asset is copied. “Waymo scenario” describes the input
dataset family, not an affiliation or production-driver claim.

## Evidence and safety boundary

- Synthetic fixture mode is always data-free and exportable.
- Real local evidence requires the authenticated loopback API. Its token remains
  memory-only and all real-record export is disabled.
- The assistant receives a closed tool result, never SQL. Offline explanation is
  fully functional. Optional Gemini explanation receives only public aggregates,
  requires explicit free-tier confirmation, and never receives raw questions or
  private records.
- Gaussian rendering is deterministic LiDAR Gaussian geometry, not
  photorealistic 3DGS, learned reconstruction, planner input, or safety evidence.
  Its 23.66% trajectory linkage fails the frozen 90% integration gate.
- Results describe the frozen development campaign and validated local artifacts;
  they do not establish production Waymo Driver behavior or real-world safety.

## Component ownership

- `ProjectOverview`: purpose, selected outcomes, workflow, evidence pipeline.
- `DebuggerStore`: selected case, timestep, playback, and responsive view state.
- `RunRail`, `SceneViewport`, `EvidenceInspector`, `MetricTimeline`: synchronized
  Scenario Lab.
- `CampaignSummary`: frozen aggregate comparison and claim boundary.
- `EvidenceAssistantPanel`: question catalog, provider status, facts, citations,
  limitations, and privacy receipt.
- `GaussianFieldPanel`: authenticated PLY lifecycle, Spark/Three.js viewer,
  geometric metrics, and integration gates.
- `LocalEvidenceService`: fixed authenticated reads, memory-only token, no-store
  requests, and binary field loading.
- `LocalEvidencePanel`: connection, campaign cell, and sealed proposal inspection.

## Verification contract

Before merge:

- strict TypeScript compilation, Vitest, Angular production build, Python API
  contract tests, Ruff, and the repository test suite must pass;
- the production build must retain the 8 kB hard per-component style limit;
- desktop browser testing must cover overview comprehension, local connection,
  scenario playback, campaign opening, all five assistant questions, Gaussian
  loading/orbit/reset, and an error-console review;
- mobile testing at 390 × 844 must verify navigation, Scenario/Evidence/Metrics
  switching, readable assistant output, and a usable Gaussian fallback layout;
- screenshots of the generated visual concept and implementation must be
  compared for hierarchy, navigation, palette, workspace composition, and
  evidence-boundary clarity.
