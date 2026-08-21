# Real-data JAX trajectory model

PlanMargin v1.1 adds a small trajectory predictor whose purpose is to make the
JAX part of the project real, measurable, and useful inside the Sensor Lab. It
does not replace the Waymax controllers and makes no claim about the production
Waymo Driver.

## Frozen task

- Source: real vehicle tracks from the ten selected WOMD v1.3.1 scenarios.
- Input: one second (11 samples) of local-frame position, velocity, and heading.
- Output: three seconds (30 samples) of local-frame position.
- Split: eight training scenarios, one validation scenario, and one untouched
  test scenario. Windows from one scenario never cross splits.
- Model: a deterministic two-hidden-layer JAX/Optax residual MLP trained against
  a constant-velocity path, followed by a fixed Savitzky–Golay filter whose
  output is included in the held-out evaluation.

Run it with:

```bash
uv run --frozen planmargin-train-trajectory-model --epochs 64
```

The ignored output directory contains a deterministic `trajectory-model.pmzip`
checkpoint and a sealed `training-report.json`.

## Qualification and negative result

The frozen test split contains 871 windows. The model records 0.261 m average
displacement error and 0.761 m final displacement error at three seconds, which
passes the visualization gates of 0.50 m ADE and 1.00 m FDE. Constant velocity
is better on that split (0.181 m ADE and 0.457 m FDE). Consequently:

- the model is qualified only for the explicitly labeled research overlay;
- no baseline-superiority, planning-quality, or safety claim is supported; and
- the baseline remains visible beside the model in the UI.

## Perception-scene registration

The Sensor Lab applies the frozen model to the recorded ego history at WOD
Perception frame 20. Vehicle poses and the FRONT camera extrinsic transform all
three paths—recorded, JAX, and constant velocity—into the Apple SHARP source-
camera coordinate system. The generated JSON stores the transformation contract,
model/report hashes, exact metrics, and claim boundary. It is local licensed
evidence and is not redistributed in the public repository.
