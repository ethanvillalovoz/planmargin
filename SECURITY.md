# Security policy

## Supported version

Security fixes are applied to the current `main` branch. PlanMargin is a local
research and engineering tool; it is not a hosted service.

## Report a vulnerability

Use GitHub's private vulnerability reporting for this repository. Do not open a
public issue containing tokens, local paths, Waymo Open Dataset records,
scenario identifiers, or other restricted evidence.

Include the affected commit, reproduction steps using data-free inputs where
possible, impact, and any proposed mitigation. Reports that require licensed
data should describe the failure without attaching that data.

## Security boundary

- The evidence API binds to loopback and rejects requests without a
  cryptographically random session token.
- The workbench exchanges the one-time header token for an HttpOnly,
  `SameSite=Strict` browser-session cookie scoped to `/api/v1`. JavaScript
  cannot read that credential, and the launch fragment is removed before
  evidence loads.
- Refreshes and additional tabs in the same browser session reconnect through
  that cookie. Explicit disconnect clears it; it is not written to durable
  browser storage, an export, or a repository file.
- API evidence projections are privacy-reduced with `no-store` and
  `nosniff`; raw paths, source URIs, scenario IDs, and record indexes are not
  exposed.
- The browser cannot submit SQL, filesystem paths, or arbitrary commands.
- Authenticated clients may start and cancel bounded local experiments.
  Browser writes require an allowed loopback origin; header-token clients
  may omit Origin. Configuration is strictly validated and size-limited.
- Workers run without a shell, one per workspace, with cancellation and a
  wall-time limit. New jobs never overwrite the frozen campaign.
- Optional proposal replay packages are revalidated against their sealed
  campaign record, fixed local path, collection hash, and rollout schema before
  the API exposes an opaque replay ID.
- Optional Gemini use is disabled by default and limited to allowlisted public
  aggregates.

These controls reduce accidental disclosure; they do not authorize publishing
or redistributing licensed dataset artifacts.
