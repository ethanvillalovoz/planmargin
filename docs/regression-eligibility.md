# Controlled headway-regression eligibility

The controlled-regression track is a predeclared method-sensitivity check. It
changes only the tested IDM controller's identifier and safe time headway from
`2.0 s` to `1.0 s`; the conservative reference controller remains unchanged.
It is not a claim about the production Waymo Driver.

## Frozen gate

All ten fixed training scenarios are evaluated in their original, unmutated
form. Each tested and reference controller rollout is repeated twice. A
scenario is eligible only when both controllers succeed.

The regression track receives a `go` only when:

- at least 8 of 10 originals are eligible;
- all original rollouts are deterministic;
- exactly ten sequential checkpoints exist; and
- physical-cost accounting reconciles.

Fewer than eight eligible originals is a valid `no_go`. Failed integrity is an
`invalid_gate`, not an experimental outcome. A `no_go` authorizes no replacement
configuration under protocol version one.

## Durable private boundary

The runner writes one sealed manifest, ten sealed original checkpoints, and one
reconstructed aggregate report below
`artifacts/search-comparison/headway-regression-eligibility/`. Each completed
resume validates all records and the aggregate report before returning, without
loading WOMD or creating controller runners.

The terminal exposes only the track, aggregate counts, decision, deterministic
integrity, physical-rollout total, and ignored output path. Scenario identities,
source locations, trajectories, hashes, outcomes, and per-scenario eligibility
remain private.

Run or resume locally with:

```bash
uv run --frozen planmargin-check-regression-eligibility
uv run --frozen planmargin-check-regression-eligibility --resume
```

## Result

The frozen gate returned `no_go`: 4 of 10 originals were eligible, below the
required 8. All 40 physical rollouts were deterministic and every integrity
gate passed. The controlled-regression search track is therefore closed under
this protocol version. The natural track is unchanged.
