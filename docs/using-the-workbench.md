# Using the PlanMargin workbench

PlanMargin has three task surfaces. They intentionally preserve different
evidence scopes instead of pretending every artifact is synchronized.

## Launch

From an installed authorized workspace:

```bash
uv run --frozen planmargin-doctor --require full
uv run --frozen planmargin-workbench
```

The launcher starts the local API and web application, then opens a one-time
authenticated URL. The token is consumed into memory and removed from the
address bar. Use the manual connection dialog only when the browser was opened
separately.

## Workbench: inspect the retained planning replay

The default surface is the planning workbench.

1. Read the decision banner first. It says whether the tested planner failed,
   the reference planner failed, or the tested planner retained margin.
2. Press play or drag the timeline. The tested, reference, and recorded paths
   advance on the same retained WOMD run.
3. Use **−1 s** and **+1 s** to move by a visible interval; the step counter and
   metrics update with the scene.
4. Read signed separation and time-to-collision together. A raw value is never
   the decision by itself; the frozen gates define the decision.

This replay is the retained Stage-0 controller comparison. It is not silently
substituted for a campaign proposal whose full trajectory was not stored.

## Sensors: inspect recorded perception evidence

Choose **Sensors** to open the WOD Perception track.

- **Camera** plays 199 recorded FRONT frames. Native boxes change with each
  frame rather than remaining fixed on the video.
- **3DGS** loads the pinned Apple SHARP reconstruction for one source frame.
  Drag to orbit and scroll to zoom. It is a spatial asset, so video playback is
  correctly disabled.
- **LiDAR** loads the same-frame point field as the reconstruction. It is also a
  spatial asset rather than a disguised camera frame.

The Perception segment and the WOMD planning replay are separate authorized
records. PlanMargin labels that boundary and does not claim sensor-to-planning
registration.

## Evidence: review candidate counterfactuals

Choose **Evidence** to inspect the immutable search campaign.

1. Select a queue: **Closest to failure**, **Smallest change**, or **Strongest
   precedent**.
2. Read **Why it stopped**. This is the first failed gate, expressed in planner
   language rather than only as a score.
3. Open a candidate to see the complete gate ladder. Later gates are marked as
   not evaluated after the first stop.
4. Compare two candidates when deciding which case deserves deeper replay
   instrumentation.
5. Use **Analyze selected proposal** for a deterministic, proposal-specific
   explanation tied to the sealed record hash.
6. Export the privacy-reduced HTML report when the decision must travel outside
   the running application.

### Metric translations

The UI keeps raw values available for audit but leads with their meaning:

| UI label                 | Raw quantity                                    | Direction                                              |
| ------------------------ | ----------------------------------------------- | ------------------------------------------------------ |
| Safety result            | `criticality`                                   | higher means closer to contact                         |
| Change size              | `minimality`                                    | higher means a smaller edit from the recorded scenario |
| Recorded precedent       | empirical support probability                   | passes at the frozen 0.05 threshold                    |
| Normalized edit distance | Euclidean distance in the frozen mutation space | zero is the unchanged scenario                         |

## Evidence assistant

**Ask analysis** opens bounded questions backed by deterministic local tools.
The default path is offline. The optional Gemini adapter receives only
allowlisted public aggregates after the user explicitly confirms provider use;
restricted scenario records are never sent.

## Troubleshooting

- Run `uv run --frozen planmargin-doctor` for a capability-by-capability status
  report.
- If the browser shows no evidence, relaunch with
  `uv run --frozen planmargin-workbench`; do not reuse a token from an earlier
  process.
- If the native toolchain is unavailable on macOS, review the doctor output.
  Accepting the Xcode license is a user action; PlanMargin will not attempt it.
- If Camera works but 3DGS or LiDAR does not, rerun the resumable sensor
  bootstrap and then the doctor. Existing complete artifacts are reused.

No step requires paid compute or a hosted database.
