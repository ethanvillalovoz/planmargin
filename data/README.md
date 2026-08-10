# Data directory

Raw and per-scenario derived Waymo Open Dataset files are intentionally
excluded from Git.

Before using WOMD:

1. Review and accept the current [Waymo Open Dataset terms](https://waymo.com/open/terms/).
2. Obtain dataset access through the official Waymo Open Dataset workflow.
3. Keep credentials and authenticated configuration outside this repository.
4. Store local data under this directory or another ignored path.
5. Publish code, configuration, and permitted aggregate results—not raw or
   per-scenario derived data.

Stage 0 workflows stream authorized records and write per-scenario reports only
under the ignored `artifacts/` directory. See
[the local setup guide](../docs/setup.md) and run
`scripts/verify_womd_access.sh` for a credential-safe metadata check.

If a later experiment requires a local cache, place authorized shards under
`data/raw/`; the repository ignores that path. Tiny synthetic fixtures used by
automated tests will live under `tests/fixtures` and will not contain Waymo
data.
