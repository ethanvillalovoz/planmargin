# Interaction-aware trajectory-model study

PlanMargin evaluated whether explicit nearby-actor context improves its
1,024-scenario real-WOMD trajectory track. This study was frozen around a
same-split ablation: the interaction model and ego-only model receive identical
SDC histories, targets, scenario partitions, training budgets, and optimizer
settings. Only the eight-nearest-actor encoder is disabled in the ablation.

## Evidence contract

- 1,024 real WOMD training scenarios from 16 shards;
- 820 train / 102 validation / 102 test scenarios;
- complete scenarios are held out;
- each SDC window contains eleven recorded 10 Hz steps;
- context contains the eight nearest valid actors' relative position, velocity,
  orientation, object type, and mask;
- the model predicts a three-second local-frame SDC path;
- no synthetic scene or official validation record is used.

## Result

| Test metric | Interaction model | Ego-only ablation | Constant velocity |
| ----------- | ----------------: | ----------------: | ----------------: |
| ADE         |           0.453 m |       **0.434 m** |           0.923 m |
| FDE         |           1.387 m |       **1.332 m** |           2.603 m |

Both learned models beat constant velocity, but the explicit neighbor encoder
failed both predeclared one-percent ablation gates. The study is therefore
`no_go`. Its model and ONNX files remain local research artifacts and are not
promoted into the application, NVIDIA qualification, or public model release.

The result narrows the next research problem: nearest-actor pooling at one
instant does not provide useful transferable scene context. A future model
would need temporal actor interaction, map context, or online scene adaptation,
and would require new independent evaluation evidence rather than tuning on the
observed test split.
