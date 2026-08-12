# PlanMargin scenario debugger

This Angular and Three.js application is PlanMargin's local evidence debugger.
It always boots into a deterministic synthetic fixture and can optionally read
privacy-reduced real experiment evidence from the authenticated loopback-only
FastAPI service. It never uploads records or claims to inspect the production
Waymo Driver.

## Run locally

Use Node.js 24.15.0 (recorded in `.nvmrc`):

```bash
npm ci
npm start
```

Then open `http://127.0.0.1:4200`.

To inspect ignored local evidence, first run `uv run --frozen
planmargin-serve-evidence` from the repository root. Select **Synthetic demo**
in the debugger, paste the ephemeral token printed by the service, and choose
**Connect local evidence**. The token stays only in service memory; it is not
placed in browser storage, URLs, logs, or exports.

## Quality checks

```bash
npm run check
npm run format:check
npm audit --audit-level=moderate
```

`npm run check` performs strict application and test typechecking, unit tests,
and an optimized production build. Three.js is loaded as a lazy chunk, keeping
the initial application payload small.

## Data boundary

`Open run` accepts JSON only when it conforms to the
`planmargin.debugger.v1` synthetic contract and is no larger than 5 MB. The
parser rejects non-finite geometry, misaligned timelines, duplicate proposal
identifiers, and non-synthetic records before rendering. `Export view` writes
only the current synthetic run ID, proposal ID, timestep, and time; it does not
export trajectories or provenance payloads.

The real-evidence mode calls only fixed `http://127.0.0.1:8765/api/v1`
endpoints with `GET`, `no-store`, omitted credentials, no referrer, and the
ephemeral token header. It maps closed API response models into debugger state,
renders nullable TTC values as “Not closing,” exposes sealed campaign proposal
evidence in a separate panel, and hard-disables export. Disconnecting clears
the token and restores the bundled synthetic fixture.

The accepted visual system and browser acceptance criteria live in
[`../../docs/debugger-design.md`](../../docs/debugger-design.md).
