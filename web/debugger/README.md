# PlanMargin scenario debugger

This Angular and Three.js application is the thin, local visualization slice
for PlanMargin. It ships with one deterministic synthetic fixture; it does not
fetch WOMD, call a backend, upload files, or claim to inspect the production
Waymo Driver.

## Run locally

Use Node.js 24.15.0 (recorded in `.nvmrc`):

```bash
npm ci
npm start
```

Then open `http://127.0.0.1:4200`.

## Quality checks

```bash
npm run check
npm run format:check
npm audit --audit-level=moderate
```

`npm run check` performs strict application and test typechecking, ten unit
tests, and an optimized production build. Three.js is loaded as a lazy chunk,
keeping the initial application payload small.

## Data boundary

`Open run` accepts JSON only when it conforms to the
`planmargin.debugger.v1` synthetic contract and is no larger than 5 MB. The
parser rejects non-finite geometry, misaligned timelines, duplicate proposal
identifiers, and non-synthetic records before rendering. `Export view` writes
only the current synthetic run ID, proposal ID, timestep, and time; it does not
export trajectories or provenance payloads.

The accepted visual system and browser acceptance criteria live in
[`../../docs/debugger-design.md`](../../docs/debugger-design.md).
