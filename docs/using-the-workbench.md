# Using the PlanMargin workbench

PlanMargin asks: **what realistic change could make this planner fail while a
conservative reference still succeeds?** Start with a scenario change, then
follow its decision to the exact evidence.

## Launch

To execute new experiments without preparing the entire historical workspace,
follow the [planning-only setup](running-experiments.md#first-time-setup), then run:

```bash
uv run --frozen planmargin-workbench --planning-only
```

This opens **New experiment**. Choose a scenario and braking change, run both
controllers, and open that job's exact replay. Progress, cancellation, gate
decisions, and history are live local job data—not saved campaign answers.

From an installed, authorized workspace:

```bash
uv run --frozen planmargin-doctor --require full
uv run --frozen planmargin-workbench
```

If required real-data artifacts are missing, review the dataset terms and use:

```bash
uv run --frozen planmargin-bootstrap-workbench --accept-waymo-terms
```

Bootstrap resumes verified phases. It does not fabricate missing records or
bypass dataset access. See [workspace reproduction](reproducing-the-workspace.md)
for prerequisites and stages.

The launcher starts the local API and web app, then opens an authenticated URL.
Its one-time token is exchanged for an HttpOnly browser-session cookie and
removed from the address bar. Keep the launcher terminal running. After a
restart, use its new URL rather than an old token.

A public clone without licensed data opens **aggregate evidence**. It cannot
show the private scenario queue, camera frames, or trajectories. This is an
explicit data boundary, not a broken download or a synthetic fallback.

## Investigate — start here

The default local view shows two panes: ranked changes and the selected
change's evidence. The nearest approach is selected initially.

1. Read the campaign outcome. The current campaign has **zero qualifying
   regressions**, even though some changes produce very small gaps.
2. Select **Inspect** on a row. The detail pane shows the scenario, method,
   seed, proposal, braking shift, speed scale, and both planner outcomes.
3. Read the decision explanation. Use **Explain decision** to reveal the
   individual gates when needed.
4. Choose **Open exact proposal replay** when available. For **Metrics only**
   rows, no full path is available. The UI does not substitute Stage 0.
5. Use **Analyze selected proposal** for a deterministic explanation of that
   specific sealed record. It does not call Gemini or send private data.
6. **Export investigation** downloads self-contained HTML plus a SHA-256
   digest over the privacy-reduced payload. This is an integrity digest, not
   an identity-authenticated digital signature. Treat exported local evidence
   according to the dataset terms.

The three rankings emphasize proximity, edit size, or empirical support.
**Compare** holds up to two rows. **Browse all 100 search runs** exposes the
scenario × seed × method matrix and each run's 32 attempts; these advanced
controls are intentionally hidden during the first investigation.

“Minimum gap” is recovered from criticality as
`max(1 / criticality - 1, 0)` metres. It saturates at zero at contact and is not
a penetration-depth measurement. “Change size” normalizes Euclidean distance
within the frozen two-dimensional mutation bounds; it is not a physical
percentage of speed or time. A small gap or small edit alone is not a finding.

## Replay — follow the selected evidence

- An exact-replay button loads that proposal's verified trajectory, not another
  visually similar path.
- Press Play, drag the timeline, or use **−1 s / +1 s**. Metrics and vehicles
  advance together.
- Tested, reference, and original-tested tracks compare outcomes for the
  **same ego vehicle**. Pink identifies the mutated lead vehicle. The third
  track is the tested controller's trajectory before the edit, not the logged
  recording. Markers are schematic; clearance uses recorded vehicle geometry.
- **Inspect minimum clearance** seeks the frame with the smallest tested gap.
- **Review candidate records** returns to Investigate and preserves the
  selected change.
- Opening Replay directly before selecting a retained proposal shows the
  separately identified Stage-0 comparison. It is not campaign evidence.
- A new experiment's replay URL includes its job ID. Refresh reverifies and
  restores that exact trajectory; it does not restore timeline position.
  **Return to experiments** preserves its selection in the live history.
- A historical campaign proposal's selection is not persisted on refresh.
  Reopen it from Investigate; Stage 0 remains separately identified.

The failure decision is made by the frozen gates—not by a single displayed
separation or time-to-collision value.

## Test health — inspect a completed run

This page displays a **saved, sealed report**, not live fleet telemetry or a
continuously refreshing incident feed.

- **Health:** execution and integrity checks; completion does not prove
  planner safety.
- **Coverage:** three versioned test plans, their gates and explicit gaps.
- **Triage:** measured blocked, stopped, or pending engineering decisions with
  diagnostic and resolution paths.

The inventory contains 100 search cells plus ten fault-dropout and ten handoff
cases. These reuse ten recorded scenarios; they are not 120 independent
scenes. The schema has SLI/objective fields, but no rolling time-window
availability or preregistered deadline was measured. Regenerate the report with
`planmargin-build-test-operations` after completing a new authorized campaign.

## Sensor lab — separate perception research

**Camera** plays 199 real FRONT frames with frame-specific native tracked
boxes. **3DGS** opens three pinned Apple SHARP source-frame reconstructions
(frames 20, 60, and 99); drag to orbit and scroll to zoom. **LiDAR** opens the
same-frame point field. Spatial assets do not pretend to be videos, so
playback is disabled for them.

These are real reconstructed assets, not image-generated illustrations.
They are separate single-image reconstructions, not a trained, fused dynamic
multi-view scene. The WOD Perception segment and WOMD planning experiment are
different records; no sensor-to-planning registration is claimed.

## Models — inspect promotion decisions

Prediction holdout metrics and NVIDIA runtime measurements are kept separate.
The scaled model's FP32 path was measured; FP16 did not pass the frozen
maximum-drift gate. Prior model timings are not relabeled as scaled-model
results. Active-risk and neighbor-context studies also preserve their no-go
decisions. These models are not silently promoted into the tested planner.

## Ask PlanMargin

The assistant opens alongside the current page without navigating away.
Greetings and help use a clearly labeled local guide. Evidence questions use:

1. Deterministic topic routing in the browser.
2. Retrieval of verified aggregate facts by the backend.
3. Optional Gemini synthesis from an allowlisted qualitative evidence packet.
4. Structured-response and citation validation; exact facts remain available
   under **Show verified facts**.

The raw question and private scene records are not sent to Gemini. This is a
bounded evidence explainer: it has ten supported topics, no chat memory, no
autonomous tool selection, and no ability to run experiments. Unmatched
questions receive an honest limitation rather than an invented answer.
Use **Analyze selected proposal** for private, proposal-specific questions.

To enable the optional Gemini provider, use your own free-tier project with
billing disabled and load its key securely in the launcher environment:

```bash
uv sync --frozen --extra assistant
uv run --frozen --extra assistant planmargin-workbench \
  --assistant-provider gemini \
  --confirm-gemini-free-tier
```

The header identifies Gemini synthesis when configured. A response can fall
back to the deterministic explainer; the panel labels this. The provider may
attempt up to three structured generations if generation or validation fails.
The flag records your free-tier confirmation; it cannot independently enforce
Google's project billing settings. The default offline provider costs nothing.

## Recovery

- If the API stops or the local session expires, the connection indicator and
  banner now report the failure. Relaunch the workbench, then use its new URL.
- Focus changes recheck a connected backend. Fetch failures do not silently
  leave the badge green or discard the last selected record.
- Refresh preserves the browser session, not all UI state. Navigation routes
  are retained; private evidence is always reverified.
- If a capability fails, run `uv run --frozen planmargin-doctor`. It reports
  exactly which inputs or derived artifacts need attention.
- Accepting an Xcode or dataset license remains a user action.
- Do not run `npm ci` while the same workspace's development server is running:
  stop it first, install dependencies, and relaunch.

Nothing in these steps publishes the app or its data.
