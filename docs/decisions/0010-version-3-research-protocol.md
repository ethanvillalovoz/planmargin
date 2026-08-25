# ADR 0010: Version 3 bounded research follow-ups

## Status

Accepted before the Version 3 follow-up runs on August 24, 2026.

## Context

Version 2 preserved two honest no-go results: the first JAX DQN missed its
synthetic safety gate, and the scaled TensorRT FP16 graph exceeded its frozen
maximum-drift gate. Version 3 may attempt new designs, but it must not move
the old gates or rewrite either result.

## Decision

### Shielded RL controller

Evaluate a new controller made from the trained JAX DQN plus a deterministic
longitudinal safety envelope. The envelope applies maximum braking when either
time-to-collision is below 4 seconds, headway is below 1.8 seconds, or the
kinematic stopping-distance margin is exhausted. It caps the learned action at
-2 m/s² when time-to-collision is below 6 seconds or headway is below 2.5
seconds. These constants are frozen before the new evaluation seed is opened.

The synthetic gate requires all of the following:

- byte-identical repeated training;
- collision rate no greater than 1%;
- collision rate no worse than the emergency baseline plus 0.25 percentage
  points;
- mean distance at least 80% of the emergency baseline; and
- mean return at least five points above the untrained network.

Passing this gate would qualify only a synthetic controller study. It would not
authorize a real-WOMD campaign, describe the controller as safe, or replace the
planner under test.

### Split residual FP16 candidate

Evaluate a deployment architecture that keeps baseline smoothing and residual
addition in host FP32 while the accelerator graph predicts only the smoothed
trajectory residual. The physical-probe distribution and 0.075 m maximum-error
and 0.01 m RMSE gates remain unchanged.

Apple MPS may provide a local FP16 proxy. Only a TensorRT run on NVIDIA hardware
can promote the candidate. A local pass therefore has status
`tensorrt_required`, never `qualified`.

## Consequences

Every result is additive. The Version 2 DQN and FP16 no-go records remain
immutable and visible. New aggregate reports may be committed, while models,
engines, licensed records, and exact trajectories remain ignored local
artifacts.
