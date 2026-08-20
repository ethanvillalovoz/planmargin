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
- The workbench keeps the token in memory, sends it only in the local API
  header, and removes the ephemeral launch fragment before loading evidence.
- API responses are closed, privacy-reduced models with `no-store` and
  `nosniff`; raw paths, source URIs, scenario IDs, and record indexes are not
  exposed.
- The browser cannot submit SQL, filesystem paths, or write requests.
- Optional Gemini use is disabled by default and limited to allowlisted public
  aggregates.

These controls reduce accidental disclosure; they do not authorize publishing
or redistributing licensed dataset artifacts.
