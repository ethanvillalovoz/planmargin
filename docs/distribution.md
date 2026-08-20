# Evidence distribution

PlanMargin separates a public aggregate product from an authorized local evidence
product. This is a licensing and privacy boundary, not a demo-data fallback.

| Surface | Public clone / Hugging Face | Authorized local store |
| --- | --- | --- |
| Campaign decision and scale | Yes | Yes |
| Method and hypothesis aggregates | Yes | Yes |
| Per-cell and per-proposal records | No | Yes |
| Stage-0 planning replay | No | Yes |
| WOD camera, LiDAR, and 3DGS assets | No | Yes |
| Scenario IDs and source provenance | No | No UI exposure |

The staged dataset package is in
`release/huggingface/planmargin-public-evidence`. It contains six aggregate JSONL
records and an integrity verifier. It must not be expanded with ignored artifacts
or `data/raw` files.

Do not publish Waymo-derived scenario files unless the recipient-access and license
requirements in the current [Waymo Open Dataset terms](https://waymo.com/open/terms/)
have been independently satisfied. A Hugging Face gated repository is not, by
itself, proof that every recipient registered with Waymo and accepted those terms.

The local API binds only to loopback, requires an ephemeral token, validates all
source seals before serving, emits no-store headers, and exposes allowlisted,
privacy-reduced response models.
