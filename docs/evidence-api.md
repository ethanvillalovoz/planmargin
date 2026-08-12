# Local real-record evidence API

The FastAPI service is the authenticated, read-only boundary between ignored
experiment artifacts and local engineering tools. It gives the debugger a
real-record path without copying restricted WOMD evidence into the Angular
bundle, Git, CI, browser storage, or a hosted service.

## Source and response boundary

The service reads three fixed artifact families beneath the repository root:

| Source | Verification | Exposed projection |
| --- | --- | --- |
| `artifacts/analytics/natural-development-v1` | sealed manifest, DuckDB hash and size, exact table allowlist, row counts | campaign, method, hypothesis, and cell aggregates |
| `artifacts/search-comparison/natural-development-v1` | sealed campaign identity linked by the analytics manifest; sealed cell/proposal checkpoints on access | selected proposal parameters, outcomes, support decisions, findings, and cost |
| `artifacts/stage-0/rollout-records.json` | rollout collection schema, stable identities, trajectory and scene-context hashes | local road geometry, redacted trajectories, controller outcomes, and recomputed interaction timelines |

Campaign proposal records contain hashes but not replayable trajectories. The
API therefore never represents proposal-level campaign evidence as trajectory
evidence. Its replay endpoint comes only from the separate validated Stage 0
rollout collection.

The response allowlist excludes scenario IDs, source-shard paths, TFRecord
indices, mutated object indices, controller configuration details, raw
provenance, feature vectors, record hashes, and local filesystem paths. Opaque
run and cell IDs are derived from local identities and reveal no source ID.

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
- Artifact and database symlinks are rejected. Required content validation
  completes during application startup before a request is served.
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

## Fixed endpoints

| Endpoint | Responsibility |
| --- | --- |
| `GET /api/v1/health` | authenticated readiness and active evidence mode |
| `GET /api/v1/campaign` | immutable experiment-v1 status, cost, privacy, and held-out boundary |
| `GET /api/v1/methods` | method-level aggregate comparison |
| `GET /api/v1/hypotheses` | frozen hypothesis decisions and available comparison values |
| `GET /api/v1/cells` | redacted cell aggregates with opaque IDs |
| `GET /api/v1/cells/{cell_id}/proposals` | sealed proposal evidence for an opaque cell |
| `GET /api/v1/runs` | available validated replay evidence |
| `GET /api/v1/runs/{run_id}` | redacted scene, trajectories, outcomes, and interaction timeline |
| `GET /api/v1/openapi.json` | authenticated OpenAPI 3 contract generated from closed response models |

The run timeline computes oriented-box separation with the same parity-tested
interaction-metrics implementation used by the experiment. Longitudinal TTC
is `null` when the target is not a closing lead; it is never replaced with a
made-up finite number for display convenience.

## Data-free verification

`tests/test_evidence_api.py` exercises token enforcement, explicit CORS,
trusted hosts, no-cache headers, redaction, opaque lookup behavior, database
hashes, manifest seals, exact table allowlists, path confinement, and rejected
tampering. Synthetic two-step traces exercise the real-response transformation
without WOMD access. Existing analytics and rollout-record tests remain the
source-contract tests below the API.
