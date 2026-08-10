# Data directory

Raw and derived Waymo Open Dataset files are intentionally excluded from Git.

Before using WOMD:

1. Review and accept the current [Waymo Open Dataset terms](https://waymo.com/open/terms/).
2. Obtain dataset access through the official Waymo Open Dataset workflow.
3. Keep credentials and authenticated configuration outside this repository.
4. Store local data under this directory or another ignored path.
5. Publish code, configuration, permitted identifiers, and aggregate results—not raw restricted data.

Future setup scripts will download or stream only the shards needed for a selected experiment. Tiny synthetic fixtures used by automated tests will live under `tests/fixtures` and will not contain Waymo data.

