# PlanMargin 2.1 release candidate

PlanMargin 2.1 is a local, unpublished release candidate. It does not create or
update a hosted application, GitHub Pages deployment, Hugging Face repository,
Git tag, or GitHub release.

## Product additions

- Ten campaign proposals now have exact, seal-verified replay packages instead
  of five. The other campaign proposals remain hash-and-metric evidence.
- Sensor Lab provides three independently generated Apple SHARP
  reconstructions from real WOD Perception FRONT frames 20, 60, and 99.
- The bounded evidence assistant now covers eight allowlisted topics, adding
  trajectory-model performance, NVIDIA inference qualification, and workbench
  provenance. Gemini still receives only public aggregate facts.
- The staged aggregate-only evidence bundle now contains sixteen records. No
  licensed scene, trajectory, camera, LiDAR, or Gaussian data is included.

## Research decisions

- A preregistered residual-only FP16 architecture passed the unchanged local
  Apple-MPS numerical proxy at 0.046 m maximum error and 0.0048 m RMSE. It has
  not been measured in TensorRT and is not promoted.
- A preregistered shielded DQN follow-up was deterministic and improved on the
  untrained policy, but its 2.686% synthetic collision rate missed the frozen
  1% gate. It remains a `synthetic_no_go` and did not advance to a real-WOMD
  campaign.

## Distribution boundary

The repository contains code, schemas, documentation, and aggregate decisions.
Exact replay packages, WOD Perception inputs, camera frames, LiDAR, and all
three 3DGS files remain ignored local evidence. Publishing remains a separate
operator decision.

## Local sign-off artifacts

- The authenticated browser audit covers desktop planning, all three 3DGS
  selectors, a live Gemini qualification answer with host-verified facts, and
  the 390 px workbench layout.
- A real 16-second aggregate-evidence screen recording was captured and
  inspected locally. Browser chrome was cropped from the retained copy so it
  contains no tabs, address bar, or ephemeral credential. It remains under the
  ignored `artifacts/demo/` boundary and is not a publication decision.
- The macOS accessibility tree exposes named navigation, evidence tabs,
  headings, status text, and primary actions. Keyboard Tab order and Return
  activation were exercised in Chrome. See
  [the accessibility audit](accessibility-audit-v2.1.md).
