# Local real-record evidence API

The FastAPI service is the authenticated, read-only boundary between ignored
experiment artifacts and local engineering tools. It gives the debugger a
real-record path without copying restricted WOMD evidence into the Angular
bundle, Git, CI, browser storage, or a hosted service.

The campaign response contract is version `1.1.0`. It reports
`held_out_comparison_run: false`, replacing the ambiguous version-1.0
`held_out_opened` field after the historical access correction in
[ADR 0007](decisions/0007-correct-validation-access-boundary.md). The Angular
client rejects any other campaign-contract version instead of guessing at its
semantics.

## Source and response boundary

The service reads five fixed artifact families beneath the repository root:

| Source | Verification | Exposed projection |
| --- | --- | --- |
| `artifacts/analytics/natural-development-v1` | sealed manifest, DuckDB hash and size, exact table allowlist, row counts | campaign, method, hypothesis, and cell aggregates |
| `artifacts/search-comparison/natural-development-v1` | sealed campaign identity linked by the analytics manifest; sealed cell/proposal checkpoints on access | selected proposal parameters, outcomes, support decisions, findings, and cost |
| `artifacts/stage-0/rollout-records.json` | rollout collection schema, stable identities, trajectory and scene-context hashes | local road geometry, redacted trajectories, controller outcomes, and recomputed interaction timelines |
| `artifacts/gaussian-field/feasibility` | sealed manifest, exact gate allowlist, privacy declaration, PLY size and SHA-256 | geometry metrics, integration decision, and authenticated binary field |
| `artifacts/sensor-scene/waymo-front` | fixed manifest paths, frame indices, byte sizes, SHA-256 digests, source-frame alignment, and PLY vertex counts | recorded FRONT JPEGs, real SHARP reconstruction, and same-frame LiDAR Gaussian field |

The sensor-scene manifest is produced by
`uv run python scripts/prepare_perception_scene.py` from ignored local WOD
Perception inputs. It is a visual product surface, not campaign evidence.

Campaign proposal records contain hashes but not replayable trajectories. The
API therefore never represents proposal-level campaign evidence as trajectory
evidence. Its replay endpoint comes only from the separate validated Stage 0
rollout collection.

The response allowlist excludes scenario IDs, source-shard paths, TFRecord
indices, mutated object indices, controller configuration details, raw
provenance, feature vectors, and local filesystem paths. The proposal-analysis
endpoint returns only the selected proposal record's content SHA-256 as a
tamper-evident citation. Opaque run and cell IDs are derived from local
identities and reveal no source ID.

## Security contract

- Uvicorn binds only to `127.0.0.1`; the command offers no public-host flag.
- Every endpoint, including health, requires an `X-PlanMargin-Token` value of
  at least 16 characters.
- Browser access is restricted to the two explicit Angular development origins
  `http://127.0.0.1:4200` and `http://localhost:4200`.
- Trusted-host validation rejects DNS-rebinding hostnames.
- Responses carry `Cache-Control: no-store`, `Pragma: no-cache`,
  `X-Content-Type-Options: nosniff`, and `Referrer-Policy: no-referrer`.
- The API accepts no SQL, filesystem path, query expression, mutation, or
  write operation from a client. Every DuckDB query is source-controlled and
  each connection is opened read-only.
- Artifact and database symlinks are rejected. Core campaign/replay validation
  completes during startup; the optional Gaussian artifact is sealed and
  revalidated on every summary or binary request.
- The service performs no outbound network request.

These controls complement one another. CORS is a browser boundary, not
authentication; the random local token and trusted-host check also protect the
loopback service. The implementation follows FastAPI's documented
[lifespan](https://fastapi.tiangolo.com/advanced/events/) and explicit
[CORS origin](https://fastapi.tiangolo.com/tutorial/cors/) patterns.

## Start the service

Complete the private Stage 0 and campaign workflows first. From the repository
root, run:

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

Start the Angular debugger separately at `http://127.0.0.1:4200`, choose
**Connect local evidence**, paste the ephemeral token into **Local evidence**,
and connect. The client performs a sequential verified
handshake, then exposes the validated replay records and campaign cell/proposal
browser, bounded assistant, and the camera/3DGS/LiDAR workspace. It sends no writes and,
in the default offline-assistant mode, makes no outbound request beyond this
fixed loopback API.

The token is kept in a private in-memory field and the input is cleared after
connection. It is never persisted to local/session storage, a URL, a file, or
an export. Privacy-reduced proposal reports can be exported as self-contained
HTML, but never include the token, local paths, raw trajectories, or restricted
provenance. Disconnecting returns to
Camera, clears local planning evidence and sensor access, and leaves the
workspace explicitly empty; no demo or synthetic run is substituted.

## Fixed endpoints

| Endpoint | Responsibility |
| --- | --- |
| `GET /api/v1/health` | authenticated readiness and active evidence mode |
| `GET /api/v1/campaign` | immutable experiment-v1 status, cost, privacy, and whether a held-out comparison ran |
| `GET /api/v1/methods` | method-level aggregate comparison |
| `GET /api/v1/hypotheses` | frozen hypothesis decisions and available comparison values |
| `GET /api/v1/cells` | redacted cell aggregates with opaque IDs |
| `GET /api/v1/cells/{cell_id}/proposals` | sealed proposal evidence for an opaque cell |
| `GET /api/v1/investigation` | cached campaign-wide funnel and top proposal rankings across all 3,200 seals |
| `GET /api/v1/cells/{cell_id}/proposals/{proposal_number}/analysis` | deterministic proposal-specific gate explanation and sealed-record citation |
| `GET /api/v1/runs` | available validated replay evidence |
| `GET /api/v1/runs/{run_id}` | redacted scene, trajectories, outcomes, and interaction timeline |
| `GET /api/v1/assistant/status` | active explanation provider and input scope |
| `GET /api/v1/assistant/questions` | five natural-language questions mapped to a closed query allowlist |
| `GET /api/v1/assistant/{query_id}` | cited facts, bounded explanation, limitations, and privacy receipt |
| `GET /api/v1/gaussian-field` | privacy-reduced geometry metrics and frozen integration gates |
| `GET /api/v1/gaussian-field/field.ply` | sealed local Gaussian PLY for in-browser rendering |
| `GET /api/v1/sensor-scene` | fixed scene provenance, frame timing, hashes, and 3D asset metadata |
| `GET /api/v1/sensor-scene/front/{frame_index}.jpg` | one indexed recorded FRONT frame from the fixed manifest |
| `GET /api/v1/sensor-scene/reconstruction.ply` | real Apple SHARP 3DGS generated from the declared source frame |
| `GET /api/v1/sensor-scene/lidar.ply` | deterministic Gaussian field generated from same-frame LiDAR returns |
| `GET /api/v1/openapi.json` | authenticated OpenAPI 3 contract generated from closed response models |

The run timeline computes oriented-box separation with the same parity-tested
interaction-metrics implementation used by the experiment. Longitudinal TTC
is `null` when the target is not a closing lead; it is never replaced with a
made-up finite number for display convenience.

## Data-free verification

`tests/test_evidence_api.py` exercises token enforcement, explicit CORS,
trusted hosts, no-cache headers, redaction, opaque lookup behavior, database
hashes, manifest seals, exact table allowlists, path confinement, and rejected
tampering. It also covers assistant allowlisting/privacy, both Gaussian binary
paths, sensor-frame authentication, and missing-asset behavior. Synthetic
two-step traces exercise the real-response transformation without WOMD access.
Existing analytics and rollout-record tests remain the source-contract tests
below the API.
