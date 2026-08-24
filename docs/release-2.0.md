# PlanMargin 2.0 evidence release

PlanMargin 2.0 strengthens the project through measured scope, not a longer
technology list. It scales the real-data prediction track, evaluates two new
learned hypotheses under frozen gates, makes deployment boundaries explicit in
the workbench, and adds an application-facing NVIDIA latency contract.

## Promoted

- **Real-WOMD scale study:** 1,024 complete scenarios and 126,992 windows.
- **Held-out quality:** 0.418 m ADE and 1.167 m FDE on 12,832 windows, versus
  0.870 m and 2.342 m for constant velocity.
- **Reproducibility:** a clean repeat produced byte-identical PyTorch and ONNX
  artifacts.
- **Model-only distribution:** source records and caches remain local; weights,
  ONNX, hashes, and aggregate metrics are independently releasable.

## Evaluated and stopped

- **Active-risk mining:** a five-member MLP ensemble used twelve pre-controller
  features and scenario-grouped evaluation over 2,097 real campaign targets.
  Mean Spearman was 0.137; learned selection beat matched random at budget eight
  in 3 of 9 scenes; interval coverage was 0.545. It was not exported or used to
  select a prospective campaign.
- **Nearest-actor prediction:** an eight-neighbor pooling model was compared
  with an ego-only ablation on the identical 102-scenario test split. Its 0.453
  m ADE was worse than the ego-only model's 0.434 m. It was not promoted.

These no-go decisions are first-class results. Promotion thresholds were not
relaxed after observation.

## Deployment contract

The free-T4 notebook now fetches the scaled, hash-pinned model release and
builds FP32 and typed-FP16 TensorRT engines. Both Python and C++17 paths report:

- CUDA-event `enqueueV3` latency at p50, p95, and p99;
- pinned-host end-to-end latency at p50, p95, and p99, including H2D, inference,
  D2H, and synchronization;
- numerical parity against PyTorch FP32;
- batch 1, 8, and 256 throughput, exact versions, GPU identity, and hashes.

The scaled model is **pending NVIDIA qualification** until this notebook is run
on a free T4. Published numbers from the earlier 128-scenario model are retained
but are never attributed to the new model.

## Product changes

- Evidence is now an operational investigation console: a compact sticky
  command bar, priority queue, campaign gates, matched-cell navigator, proposal
  ranking, and persistent candidate inspector replace the earlier oversized
  presentation-style heading and stacked report layout.
- Planning callouts turn inward near the viewport boundary, keeping tested,
  reference, and recorded labels legible at the final frame.
- The Model & runtime page leads with real-data quality and separates it from
  the earlier measured runtime result.
- Stopped active-risk and interaction studies appear beside the successful
  scale study, with plain-language reasons.
- The 3DGS workspace opens on the reconstructed source view; trajectory and
  conservative novel views remain explicit alternatives.
- Desktop and 390 px mobile surfaces have no horizontal overflow, browser
  warnings, or errors in the authenticated local flow.
- A deterministic desktop/mobile browser journey now covers ranking,
  comparison, proposal analysis, exact replay, Gemini's grounded response
  contract, and session recovery after refresh.

## Reproduce

See [the scale study](real-womd-scale-study.md),
[active-risk ADR 0008](decisions/0008-experiment-v5-active-mining.md),
[eligible-scenario ADR 0009](decisions/0009-experiment-v6-eligible-scenario-ranking.md),
[the interaction ablation](interaction-model-study.md), and
[the NVIDIA qualification contract](nvidia-inference.md).
