# Version 3 accessibility audit

**Audit date:** August 24, 2026

**Scope:** public aggregate Evidence workspace and authenticated responsive
Workbench

## Result

The primary public workflow is keyboard-operable and exposes useful native
semantics to macOS accessibility clients. The authenticated workbench also
retains accessible names for its navigation, sensor tabs, playback controls,
control-panel disclosure, status, and assistant entry point.

This audit does not claim formal WCAG certification. CI remains responsible for
the repository's automated Chromium and axe A/AA checks. Spoken VoiceOver
phrasing still requires a human listener because the autonomous audit can
inspect the macOS accessibility tree but cannot hear or judge synthesized
speech.

## Manual keyboard evidence

Chrome exposed and reached the public controls in this order:

1. PlanMargin home
2. Workbench
3. Sensors
4. Evidence
5. Open local workspace
6. Campaign review
7. Model & runtime
8. Open licensed local evidence

`Return` activated **Model & runtime** and changed the evidence surface from
the campaign review to model qualification without a mouse. Focus remained on
the activated control. The page used native button roles instead of clickable
generic containers.

## macOS accessibility-tree evidence

The public surface exposed:

- a named `Product sections` navigation container;
- named buttons for every primary destination and evidence section;
- real heading levels for `Published campaign evidence`, `Model qualification`,
  and their result sections;
- explicit status text for local-record requirements and promotion decisions;
- metric labels adjacent to their values rather than unexplained numbers; and
- no keyboard trap in the audited primary focus sequence.

At 390 px, the authenticated planning control panel starts collapsed so it no
longer covers the sensor tabs. The mode tabs, collapsed panel, scene label,
legend, planning explanation, playback, one-second jumps, scrubber, and speed
control remain visible without horizontal overflow.

## Remaining human-only check

Before claiming full screen-reader certification, a human should run one final
VoiceOver speech pass in Safari or Chrome and judge verbosity, pronunciation,
and announcement timing for dynamic Gemini and playback updates. That check is
not a code or repository blocker for the Version 3 release candidate; it is a
separate perceptual sign-off that this environment cannot honestly simulate.
