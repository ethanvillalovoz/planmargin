# Evidence distribution

PlanMargin separates a public aggregate product from an authorized local evidence
product. This is a licensing and privacy boundary, not a demo-data fallback.

| Surface                            | Public clone / Hugging Face | Authorized local store |
| ---------------------------------- | --------------------------- | ---------------------- |
| Campaign decision and scale        | Yes                         | Yes                    |
| Method and hypothesis aggregates   | Yes                         | Yes                    |
| Aggregate learned-model decisions  | Yes                         | Yes                    |
| Model-only PyTorch and ONNX files  | GitHub release              | Yes                    |
| Per-cell and per-proposal records  | No                          | Yes                    |
| Stage-0 planning replay            | No                          | Yes                    |
| WOD camera, LiDAR, and 3DGS assets | No                          | Yes                    |
| Scenario IDs and source provenance | No                          | No UI exposure         |

The staged dataset package is in
`release/huggingface/planmargin-public-evidence`. It contains six campaign
records, two trajectory-model results, two active-risk qualification decisions,
both TensorRT decisions, both C++ benchmarks, and an integrity verifier:
fourteen aggregate research records in total. Repository setup and verification
do not publish or update an external dataset.
This is a review supplement, not the data package for the complete workbench. It
must not be expanded with ignored artifacts or `data/raw` files.

The complete public repository instead ships an authorized bootstrap and an
executable readiness report. `planmargin-bootstrap-sensor` obtains WOD source
files directly from the official bucket after explicit terms acceptance and
creates the local Sensor Lab; `planmargin-doctor` reports which public and local
product surfaces are actually ready. Campaign records remain a long-running
local reproduction described in `docs/reproducing-the-workspace.md`.

Do not publish Waymo-derived scenario files unless the recipient-access and license
requirements in the current [Waymo Open Dataset terms](https://waymo.com/open/terms/)
have been independently satisfied. A Hugging Face gated repository is not, by
itself, proof that every recipient registered with Waymo and accepted those terms.

The local API binds only to loopback, requires an ephemeral token, validates all
source seals before serving, emits no-store headers, and exposes allowlisted,
privacy-reduced response models.
