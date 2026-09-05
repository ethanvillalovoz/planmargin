# Product completion contract

## The product, in one sentence

PlanMargin lets an engineer make a controlled change to a real driving scenario,
compare tested and reference controllers, inspect every finding gate, and
reproduce the exact result.

The supported loop is **configure → execute → compare → inspect → replay →
export/reproduce**. A collection of technology demonstrations or an attractive
dashboard without that loop does not satisfy this contract.

## Scope of this finish pass

| Requirement | Acceptance condition |
| --- | --- |
| Models is an evidence browser | Six studies have distinct comparisons, expandable gates, truthful promotion status, and actual source/reproduction links |
| Investigation context survives navigation | Campaign proposal, exact replay, model study, and triage selection can be revisited; refresh reverifies a requested record without substituting Stage 0 |
| Draft is not mistaken for execution | A different saved configuration is visibly labeled; reuse only fills the form; submission alone starts a new worker |
| One real extension point | Bounded custom tested-IDM speed, spacing, and headway reach Waymax and are sealed in result/replay provenance; the reference and frozen campaign remain unchanged |
| Supporting pages are usable | All primary routes plus coverage, triage, the assistant, and Models work at desktop and narrow widths; keyboard controls, unavailable states, and recovery are exercised |
| Reproduction is honest | A clean checkout runs the documented public setup; authorized users have a tested planning/configuration path; missing data is not replaced with synthetic evidence |

This contract is finite. Completion means the conditions above have evidence at
a named code revision, not that the repository is perfect or that all possible
research questions are resolved.

## Verification

Verified on **2026-09-04** against implementation revision
[`0ac6309`](https://github.com/ethanvillalovoz/planmargin/commit/0ac6309c0de93e0a378002d404146cbbefd3c07d).
The documentation commit containing this record does not change executable code.
See [PR #97](https://github.com/ethanvillalovoz/planmargin/pull/97) for the patch
and its exact-head CI status. This is a commit-scoped acceptance record, not a
guarantee about future dependencies or untested environments.
The [implementation CI run](https://github.com/ethanvillalovoz/planmargin/actions/runs/33939313675)
passed both data-free quality and scenario-debugger jobs.

| Check | Observed result |
| --- | --- |
| Python suite in the authorized full workspace | 337 passed; six upstream PyTorch/ONNX warnings |
| Python suite in a separate checkout and virtual environment | 335 passed, two explicitly skipped tests requiring the original full campaign/API workspace; six upstream warnings |
| Locked frontend installation in the separate checkout | `npm ci` succeeded; npm reported zero known vulnerabilities at verification time |
| Frontend formatting, typecheck, unit tests, and production build | Passed in both checkouts; 94 tests across 17 files |
| Data-free Chromium browser suite | 17 passed; one mobile-only test intentionally skipped in the desktop project |
| Live local workflow, without mocked API responses | Configuration reuse, result export, exact replay, moving footprints, navigation, and refresh passed |
| Live route and accessibility checks | 11 views at 1440×1080 and 412×915; no axe WCAG 2 A/AA or 2.1 AA violations, horizontal overflow, page errors, or console errors in the checked states |
| Live sensor verification | Camera annotations changed during playback; real LiDAR and SHARP assets loaded; source/viewpoint controls responded; overlay geometry passed at both widths |
| Live assistant verification | An actual `gemini_public_aggregate` response returned cited campaign facts; greeting made no model request and was labeled as local; both widths passed axe checks |

The 11 live views were the experiment result, exact replay, prediction study,
runtime study, investigation, saved health, coverage, triage, camera, LiDAR, and
3DGS. The assistant was checked separately. All six model studies and all three
saved test suites were exercised by the data-free browser tests, including
keyboard interaction, offline use, and source links. A human-visible screenshot
review caught sensor-control intersections that axe did not; these were fixed
and covered by the opt-in [`verify:sensors` check](using-the-workbench.md#verify-the-local-sensor-layout).
Native in-app-browser inspection confirmed the final Models selection, expanded
gates, and error-free console. Licensed sensor screenshots remain local.

### Real experiment reproduction

A separate checkout fetched from GitHub used its own virtual environment and
frontend install. Its selection and empirical-support artifacts were prepared
through the documented real-data commands, not copied from the original
workspace. It repeated the documented scenario-8, +0.2 s, 0.879× experiment:

| Tested configuration | Original minimum signed clearance | Changed minimum signed clearance | Outcome |
| --- | --- | --- | --- |
| Default IDM | 0.295291 m | 0.032252 m | Tested and reference succeed; not qualified |
| Custom IDM: 24 m/s, 3 m spacing, 2.5 s headway | 2.681218 m | 2.555910 m | Tested and reference succeed; not qualified |

Both repetitions matched **all four original/changed × tested/reference
trajectory hashes**, metrics, outcomes, and finding gates. The default repeated
the pre-extension result. Custom settings changed both tested trajectories and
left both reference trajectories unchanged; the reference retained 4.796619 m
minimum signed clearance in the changed scene. Each run also performed its
internal deterministic repeats. Whole result-file hashes differ because job
identity and timing are execution-specific.

This is independent-checkout reproduction on the **same Mac, toolchain, and
authorized dataset account**, not cross-hardware replication or an external
review. The execution implementation was unchanged after `d6ad17d`; later
finish-pass changes concerned UI, verification, and assistant wording. CI
separately exercises the data-free code on Ubuntu x86-64.

### Completion decision

The six acceptance conditions above are satisfied for this bounded local
research tool. The core workflow is usable without Gemini or sensor assets
after authorized planning-data preparation. A public clone can immediately
browse aggregate studies after the documented Node setup; it cannot run
licensed-data experiments without the documented access and preparation.

No remaining item below is disguised as an implemented capability. Broader
research, additional platforms, and general-purpose planner/agent support
would require a new contract rather than another claim that this one is
"almost done."

## Boundaries that do not disappear at completion

- The campaign still found zero qualifying regressions. This work does not
  retroactively alter it or manufacture a positive scientific result.
- Customization is a numeric IDM configuration, not arbitrary planner plugins.
  The initial data scope remains ten selected real lead-braking scenarios.
- Camera/3DGS/LiDAR use a separate Perception record. The three SHARP assets
  are independent single-image reconstructions, not one fused dynamic world.
- Gemini is optional, bounded to public aggregate explanations, and may fall
  back visibly. It is not an autonomous private-job agent.
- Some research models failed promotion; the residual FP16 candidate still
  needs independent NVIDIA evidence. None is silently deployed as a planner.
- Manual VoiceOver validation, other operating systems/browser engines,
  cross-simulator validation, new model architectures, and broader scene
  coverage need separately scoped verification. Keyboard and axe checks are
  not a claim of complete accessibility certification.
- No hosting, licensed-data upload, paid resource, or generated illustration
  is part of this finish pass.

New feature work begins with a new problem and acceptance criteria—not by
continually moving this milestone's finish line.
