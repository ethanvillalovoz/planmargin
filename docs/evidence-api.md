# Local real-record evidence API

The FastAPI service is the authenticated boundary between ignored local
artifacts and engineering tools. Historical evidence remains read-only;
separate experiment routes start and cancel bounded local workers. It gives the debugger a
real-record path without copying restricted WOMD evidence into the Angular
bundle, Git, CI, browser storage, or a hosted service.

The campaign response contract is version `1.1.0`. It reports
`held_out_comparison_run: false`, replacing the ambiguous version-1.0
`held_out_opened` field after the historical access correction in
[ADR 0007](decisions/0007-correct-validation-access-boundary.md). The Angular
client rejects any other campaign-contract version instead of guessing at its
semantics.

## Source and response boundary

The historical-evidence service reads fixed artifact families beneath the repository root:

| Source                                               | Verification                                                                                                                                                        | Exposed projection                                                                                    |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `artifacts/analytics/natural-development-v1`         | sealed manifest, DuckDB hash and size, exact table allowlist, row counts                                                                                            | campaign, method, hypothesis, and cell aggregates                                                     |
| `artifacts/search-comparison/natural-development-v1` | sealed campaign identity linked by the analytics manifest; sealed cell/proposal checkpoints on access                                                               | selected proposal parameters, outcomes, support decisions, findings, and cost                         |
| `artifacts/stage-0/rollout-records.json`             | rollout collection schema, stable identities, trajectory and scene-context hashes                                                                                   | local road geometry, redacted trajectories, controller outcomes, and recomputed interaction timelines |
| `artifacts/proposal-replays/natural-development-v1`  | exact verification-key allowlist, proposal/original seals, scientific-evidence digest, collection hash, and semantic trajectory/outcome/mutation/scenario agreement | exact replay for each deliberately retained proposal                                                  |
| `artifacts/gaussian-field/feasibility`               | sealed manifest, exact gate allowlist, privacy declaration, PLY size and SHA-256                                                                                    | geometry metrics, integration decision, and authenticated binary field                                |
| `artifacts/sensor-scene/waymo-front`                 | fixed manifest paths, frame indices, byte sizes, SHA-256 digests, source-frame alignment, and PLY vertex counts                                                     | recorded FRONT JPEGs, real SHARP reconstruction, and same-frame LiDAR Gaussian field                  |

The sensor-scene manifest is produced by
`uv run python scripts/prepare_perception_scene.py` from ignored local WOD
Perception inputs. It is a visual product surface, not campaign evidence.

Campaign proposal records contain hashes but not replayable trajectories. The
API represents proposal evidence as a trajectory only when a separate replay
package reproduces the sealed hashes, outcomes, interaction metrics, and
scenario validation. The current workspace has ten such packages selected for
margin, edit-size, support, and method diversity. Stage-0 remains separate and
is never substituted for an unretained proposal.

At startup, the API requires the complete ten-check replay-verification set,
recomputes the scientific-evidence digest from the sealed original and proposal
records, and compares every retained record's scenario, mutation, trajectory
hash, outcome, change-from-original state, and acceptance gates with that
campaign evidence. A self-consistent rollout collection is not sufficient by
itself.

The response allowlist excludes scenario IDs, source-shard paths, TFRecord
indices, mutated object indices, controller configuration details, raw
provenance, feature vectors, and local filesystem paths. The proposal-analysis
endpoint returns only the selected proposal record's content SHA-256 as a
tamper-evident citation. Opaque run and cell IDs are derived from local
identities and reveal no source ID.

## Security contract

- Uvicorn binds only to `127.0.0.1`; the command offers no public-host flag.
- Every endpoint, including health, requires the valid ephemeral header token
  or its exchanged HttpOnly browser-session cookie.
- Browser access is restricted to the two explicit Angular development origins
  `http://127.0.0.1:4200` and `http://localhost:4200`.
- Trusted-host validation rejects DNS-rebinding hostnames.
- Responses carry `Cache-Control: no-store`, `Pragma: no-cache`,
  `X-Content-Type-Options: nosniff`, and `Referrer-Policy: no-referrer`.
- The API accepts no SQL, filesystem path, query expression, or arbitrary
  command. Every DuckDB query is source-controlled and opened read-only.
  Experiment configuration and cancellation use separate authenticated routes
  with trusted-origin checks and bounded, strictly validated JSON.
- Artifact and database symlinks are rejected. Core campaign/replay validation
  completes during startup; the optional Gaussian artifact is sealed and
  revalidated on every summary or binary request.
- Evidence reads do not fetch remote scenario records. Explicit new experiments
  run isolated workers that load their authorized WOMD source through configured
  GCS credentials. Optional Gemini explanations send only public aggregates.

These controls complement one another. CORS is a browser boundary, not
authentication; the random local token and trusted-host check also protect the
loopback service. The implementation follows FastAPI's documented
[lifespan](https://fastapi.tiangolo.com/advanced/events/) and explicit
[CORS origin](https://fastapi.tiangolo.com/tutorial/cors/) patterns.

## Start the service

For new experiments without the full campaign, use
`uv run --frozen planmargin-workbench --planning-only` after the
[planning setup](running-experiments.md). Campaign endpoints return an explicit
503 in this mode; health reports `campaign_ready: false`, while experiment
routes remain available. Optional sensors require the full workspace.

For the historical-evidence service, complete the private Stage 0 and campaign
workflows first. From the repository root, run:

```bash
uv run --frozen planmargin-serve-evidence
```

The command generates a fresh token, prints it only to the local terminal, and
listens at `http://127.0.0.1:8765`. To supply a stable token for one local
session without placing it in source code:

```bash
PLANMARGIN_API_TOKEN="$(openssl rand -base64 32)" \
  uv run --frozen planmargin-serve-evidence
```

Probe the service by copying the printed token into a local variable:

```bash
curl --fail \
  -H "X-PlanMargin-Token: $PLANMARGIN_API_TOKEN" \
  http://127.0.0.1:8765/api/v1/health
```

The generated token is intentionally ephemeral. Do not commit it, paste it in
an issue, or reuse it as a hosted credential.

## Connect the debugger

Run `uv run --frozen planmargin-workbench` to start both services. The launcher opens an ephemeral URL
whose fragment carries the ephemeral token. URL fragments are not sent to the
web server; the client reads the token into memory and immediately removes the
fragment from browser history before performing the verified handshake. The
manual **Local evidence** form remains only as a recovery path when the browser
was opened separately.

The handshake exposes the validated replay records and campaign cell/proposal
browser, bounded assistant, and camera/3DGS/LiDAR workspace. Merely browsing
evidence does not start a simulation. **Run experiment** explicitly submits a
new local job; it does not modify historical records.

The token is exchanged for an HttpOnly, `SameSite=Strict` browser-session
cookie after bootstrap so refreshes and fresh local tabs can reconnect. It is
removed by explicit disconnect or when the browser session closes. It is never
available to JavaScript or persisted to durable local storage, the
post-bootstrap address, a file, or an export. Privacy-reduced proposal reports
can be exported as self-contained
HTML, but never include the token, local paths, raw trajectories, or restricted
provenance. Disconnecting returns to
Camera, clears local planning evidence and sensor access, and leaves the
workspace explicitly empty; no demo or synthetic run is substituted.

Automatic bootstrap retries one transient loopback connection failure. A
temporary API interruption does not discard the browser session; an explicit
disconnect does.

## Fixed endpoints

| Endpoint                                                           | Responsibility                                                                       |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------ |
| `POST /api/v1/session`                                             | exchange the ephemeral header token for an HttpOnly browser-session cookie           |
| `POST /api/v1/session/logout`                                      | clear browser-session access                                                         |
| `GET /api/v1/health`                                               | authenticated readiness and active evidence mode                                     |
| `GET /api/v1/campaign`                                             | immutable experiment-v1 status, cost, privacy, and whether a held-out comparison ran |
| `GET /api/v1/methods`                                              | method-level aggregate comparison                                                    |
| `GET /api/v1/hypotheses`                                           | frozen hypothesis decisions and available comparison values                          |
| `GET /api/v1/cells`                                                | redacted cell aggregates with opaque IDs                                             |
| `GET /api/v1/cells/{cell_id}/proposals`                            | sealed proposal evidence for an opaque cell                                          |
| `GET /api/v1/investigation`                                        | cached campaign-wide funnel and top proposal rankings across all 3,200 seals         |
| `GET /api/v1/cells/{cell_id}/proposals/{proposal_number}/analysis` | deterministic proposal-specific gate explanation and sealed-record citation          |
| `GET /api/v1/runs`                                                 | Stage-0 plus every proposal-linked replay that passes startup validation             |
| `GET /api/v1/runs/{run_id}`                                        | redacted scene, trajectories, outcomes, and interaction timeline                     |
| `GET /api/v1/assistant/status`                                     | active explanation provider and input scope                                          |
| `GET /api/v1/assistant/questions`                                  | ten natural-language questions mapped to a closed query allowlist                    |
| `GET /api/v1/assistant/{query_id}`                                 | cited facts, bounded explanation, limitations, and privacy receipt                   |
| `GET /api/v1/gaussian-field`                                       | privacy-reduced geometry metrics and frozen integration gates                        |
| `GET /api/v1/gaussian-field/field.ply`                             | sealed local Gaussian PLY for in-browser rendering                                   |
| `GET /api/v1/sensor-scene`                                         | fixed scene provenance, frame timing, hashes, and 3D asset metadata                  |
| `GET /api/v1/sensor-scene/front/{frame_index}.jpg`                 | one indexed recorded FRONT frame from the fixed manifest                             |
| `GET /api/v1/sensor-scene/reconstruction.ply`                      | real Apple SHARP 3DGS generated from the declared source frame                       |
| `GET /api/v1/sensor-scene/lidar.ply`                               | deterministic Gaussian field generated from same-frame LiDAR returns                 |
| `GET /api/v1/openapi.json`                                         | authenticated OpenAPI 3 contract generated from closed response models               |

## Interactive experiment endpoints

| Endpoint | Responsibility |
| --- | --- |
| `GET /api/v1/experiments/readiness` | Local input availability and execution limits |
| `GET /api/v1/experiments` | Persistent job history, status, stages, and completed summaries |
| `POST /api/v1/experiments` | Start a strictly bounded scenario change with an idempotent request ID |
| `GET /api/v1/experiments/{job_id}` | Inspect a single job |
| `POST /api/v1/experiments/{job_id}/cancel` | Terminate that workspace's active job process group |
| `GET /api/v1/experiments/{job_id}/result` | Reverify and export a completed result |
| `GET /api/v1/experiments/{job_id}/replay` | Reverify the exact collection and project its trajectories |

Configuration permits only selection order 1–10, onset 0–0.5 s in 0.1 s steps,
speed 0.75–1.00, and a request UUID. POST configuration is capped at 4 KiB.
Duplicate request IDs return the existing job; changed parameters with the same
ID are rejected. A second active job returns 409. The supervisor permits one
worker, 15 minutes per run, and 200 retained jobs per workspace.

New results include source-code and input hashes but no raw source identifier
or filesystem path. Their trajectories remain licensed local data. Whole-result
hashes include job identity and timings; deterministic comparison uses
controller trajectory hashes and metrics. See the
[experiment contract](running-experiments.md) for lifecycle, privacy, and
scientific boundaries. These routes do not accept or expose arbitrary worker
logs, and no result is inferred from a failed, cancelled, or partial execution.

The run timeline computes oriented-box separation with the same parity-tested
interaction-metrics implementation used by the experiment. Longitudinal TTC
is `null` when the target is not a closing lead; it is never replaced with a
made-up finite number for display convenience.

## Data-free verification

`tests/test_evidence_api.py` exercises token enforcement, HttpOnly session
bootstrap/logout, explicit credentialed CORS, trusted hosts, no-cache headers,
redaction, opaque lookup behavior, database hashes, manifest seals, exact table
allowlists, path confinement, and rejected tampering. It also covers assistant
allowlisting/privacy, both Gaussian binary paths, sensor-frame authentication,
and missing-asset behavior. Synthetic
two-step traces exercise the real-response transformation without WOMD access.
Existing analytics and rollout-record tests remain the source-contract tests
below the API.
