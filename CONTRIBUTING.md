# Contributing to PlanMargin

PlanMargin treats scientific validity, data boundaries, and product behavior as
one review surface.

## Development setup

```bash
uv sync --frozen
cd web/debugger && npm ci && cd ../..
```

Use Python 3.11 and Node 24.15.0. Keep WOD credentials outside the repository
and every raw or scenario-level artifact under an ignored `data/` or
`artifacts/` path.

## Required checks

```bash
uv run --frozen ruff check .
uv run --frozen pytest
uv build
cd web/debugger && npm run check
```

Changes to a rendered workflow also require interaction testing at desktop and
compact widths. A passing build alone is not visual verification.

## Scientific changes

- Do not change a frozen threshold, budget, scenario family, or hypothesis in
  response to an observed result.
- Create a new protocol version for new experiments.
- Preserve negative and untestable results.
- Keep measured kernel improvements scoped to the benchmark actually run.
- Never describe PlanMargin as testing the production Waymo Driver.

## Data and security changes

- Do not commit WOD files, scenario IDs, trajectories, Parquet, DuckDB, PLY,
  checkpoints, tokens, or cloud credentials.
- Public API responses must remain allowlisted and privacy-reduced.
- The local evidence API stays loopback-only, read-only, token-authenticated,
  and `no-store`.
- Update schemas and tests together when a record contract changes.

## Pull requests

Explain the user-visible behavior, scientific claim impact, data-boundary
impact, and verification performed. Keep changes focused and do not reseal
historical evidence merely to make an old run accept new source code.
