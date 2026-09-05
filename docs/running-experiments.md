# Run a new behavior test

The experiment runner changes a real recorded lead vehicle's braking timing
and speed, executes tested and reference Waymax IDM controller configurations, and saves
an exact replay. Two additional plans exercise command-loss protection and
deterministic recovery on unchanged recorded traffic. It is a local tool,
not a hosted simulation service.

You do **not** need Gemini, a sensor reconstruction, a GPU, or the complete
research campaign to use it. You do need an authorized Waymo Open Dataset
account, Python 3.11, `uv`, Node 24.15/npm 11, and a C++20 compiler.

## First-time setup

From the repository root:

```bash
uv sync --frozen
nvm install
nvm use
cd web/debugger
npm ci
cd ../..
```

`nvm` is optional if Node 24.15 is already installed. The locked Python install
includes the research dependencies; planning-only mode reduces data preparation,
not the package download size. macOS Apple silicon and Ubuntu x86-64 are tested.
Windows/WSL is not a verified target.

Review [Waymo's dataset terms](https://waymo.com/open/terms/) and complete its
official access process. Authenticate your authorized account locally:

```bash
gcloud auth login
gcloud auth application-default login
./scripts/verify_womd_access.sh
uv run --frozen planmargin-prepare-planning --accept-waymo-terms
uv run --frozen planmargin-workbench --planning-only
```

The terms flag confirms a decision **you** have made; it does not enroll you or
grant access. Nothing above creates a paid cloud resource. Without authorized
dataset access, stop at the access check—there is no synthetic substitution.

Preparation selects and validates ten real lead-braking scenarios from the
bounded WOMD training shard scan. It writes only
`artifacts/stage-0/scenario-selection.json`. An existing valid selection is reused,
not overwritten. A failed selection is not installed as the workspace input.
Source loading uses the dataset's configured GCS access and may require network
access on later runs; the selection manifest is not an offline copy of the data.

The launcher opens **New experiment**, with a short-lived local session. Keep
the terminal running. The UI is `http://127.0.0.1:4200`; the API binds only to
`127.0.0.1:8765`. Refreshing the browser does not cancel an experiment.

## First experiment

1. Keep **Scenario 1**, **+0.0 seconds**, and **0.90** speed.
2. Click **Run experiment**. Stage labels and elapsed times come from the worker.
3. Read the outcome and expand **Test gates and integrity**.
4. Click **Open this experiment replay**, then **Inspect minimum clearance**.
   Play or step through the trajectories. The original tested trajectory is the
   same tested controller **before** the change, not a third traffic participant.
   Vehicle footprints use the recorded dimensions and headings at each step,
   in the same world coordinates as the clearance metric. Older imported
   records without footprint geometry retain explicitly labeled schematic markers.
5. Return to experiments. Export result JSON or **Prepare linked rerun**.

Changing a control does not alter an existing record. Each submission creates a
new job. History survives a server restart. A lost HTTP response can be retried
without starting a duplicate job because submission IDs are idempotent.

## What is being compared?

The tested controller uses the repository's default Waymax IDM configuration
unless you choose custom settings; the reference always uses its fixed
conservative IDM configuration. They are not the Waymo
Driver. Controller parameters are defined in `controller_comparison.py` and
retained with each exact rollout collection. Supporting RL and neural-network
research models are **not** silently promoted into this runner.

## Try your own controller configuration

In **New experiment**, choose **Custom IDM settings** under **Tested planner
configuration**. Three parameters are supported:

| Setting | Allowed range | Default | Responsibility |
| --- | --- | --- | --- |
| Desired speed | 1–40 m/s | 30 m/s | Free-road target speed |
| Minimum spacing | 0.5–10 m | 2 m | Standstill gap term |
| Safe time headway | 0.5–5 s | 2 s | Speed-dependent following-gap term |

These are research input bounds, not recommendations for real driving. The
remaining IDM parameters and the conservative reference are unchanged.
This extension accepts numeric configuration, not executable code, model
uploads, shell commands, or browser-supplied file paths.

For a reproducible example, select scenario 8, +0.2 s onset, 0.879× speed,
then use 24 m/s desired speed, 3 m spacing, and 2.5 s headway.
The CLI equivalent, after stopping the workbench supervisor, is:

```bash
uv run --frozen planmargin-run-experiment \
  --selection-order 8 --onset 0.2 --speed 0.879 \
  --tested-controller-config examples/tested-idm.json
```

Copy [the example JSON](../examples/tested-idm.json) to a new file to vary
your own settings. Omitted fields in a custom JSON object use the defaults
above. Unknown fields, non-finite values, and out-of-range inputs are rejected.
Omitting the flag preserves the original default-controller request format.

The worker runs the selected tested policy on **both** the original and
changed scene. Each result seals the expanded custom configuration, a
content-addressed controller ID, full tested/reference specifications,
implementation hashes, and all finding gates. The replay collection retains
those specifications and repeated trajectory hashes. Default and custom jobs
remain separate from the frozen campaign; a new experiment cannot rewrite its
results or promotion decisions.

The result panel identifies its saved run and warns when the current draft
differs. **Prepare linked rerun** fills the form; only **Run experiment**
executes it. Draft edits survive navigation within the running app, but not a
full browser reload. Run-history selection and exact-replay identity are
restored from the URL and reverified locally.

The controls are bounded to ten selected scenarios, an onset shift of 0–0.5 s
in 0.1 s steps, and a speed multiplier of 0.75–1.00. The lead vehicle follows
the recorded route. The workflow validates the original case, validates the
mutation, executes each controller twice, and checks outcomes and identical
trajectory hashes. An accepted change produces eight 80-step planner rollouts
(original/changed × tested/reference × two repetitions), plus map-validity work.

## Command faults and recovery

Choose **Command loss · fallback protection** or **Command loss · recovery
handoff** in the test-plan selector. Both reuse the existing qualification
protocol, not a second approximate implementation:

- At 2.0 simulated seconds, the primary command stream is lost. The unprotected
  policy holds its last commanded pose; protection switches to conservative IDM.
- In recovery mode only, a deterministic test signal at 3.0 seconds resumes
  the protected policy's primary IDM. There is no human operator or LLM in this loop.
- The baseline, unprotected and protected policies each run twice: **six
  physical rollouts**, 80 steps each. The replay's two original roles share the
  single measured no-fault baseline; they are not extra executions.
- Results include the existing progress, validity, exact transition and
  repeatability gates. **Behavior checks passed** requires all named gates;
  completing the worker alone is insufficient.

Open the exact replay and click an **Observed behavior event** to seek to its
measured step. Labels distinguish **Unprotected**, **Protected**, **Primary
baseline**, and unchanged **Recorded lead**. The observed event times come from
the worker trace; a missing transition is not replaced by an expected event.

If the recorded lead leaves the observation timeline, its marker disappears and
separation/TTC become unavailable for those frames. The ego-policy traces continue;
the workbench neither freezes nor interpolates an unobserved traffic actor.

CLI equivalents (stop the workbench supervisor first):

```bash
uv run --frozen planmargin-run-experiment \
  --test-plan command_dropout --selection-order 1 --onset 0 --speed 1
uv run --frozen planmargin-run-experiment \
  --test-plan assistance_handoff --selection-order 1 --onset 0 --speed 1
```

Fault plans require unchanged traffic (`--onset 0 --speed 1`) and fixed
controllers. They do not use the lead-mutation empirical-support score and do
not claim to discover realistic traffic regressions.

## Live health, deadlines, and traceable reruns

**Test health → Live local runs** reads the authenticated supervisor's current
history. The separate **Saved campaign** view remains immutable.

Every new job declares a **10–900 second completion deadline** (default 120).
This measures local execution time, including loading and JAX compilation—not
simulated driving time. A late job is flagged and continues so its result can
be inspected. The independent 900-second hard limit still terminates the worker.
Older jobs with no declared deadline remain unmeasured; no objective is assigned
retroactively. The denominator excludes running and cancelled jobs.

Diagnostics distinguish failed execution, late completion, and failed behavior
checks. A lead-braking result of **not a qualifying regression** is not an
infrastructure failure. Select **Inspect run** for its stage and recovery action,
then **Prepare linked rerun**. This fills the original configuration without
executing it; click **Run experiment** to start the new job. You may declare a
different deadline, but the old miss stays visible. Changing the scenario or
policy creates a separate investigation, not a resolution of the old one.

A successful, on-time, same-configuration linked rerun resolves its ancestor
diagnostics. Failed behavior gates cannot resolve an incident. Original failed
records remain in history with the resolving run's ID. This is local test
operations, not a rolling production SLO, fleet dashboard, or reliability estimate.

| UI result | What it means | What to do |
| --- | --- | --- |
| Execution complete / not a qualifying regression | The computation completed, but the finding contract did not pass | Inspect the failed finding gate; do not label this a discovered failure |
| All finding gates passed | This exploratory case passes original-success, validity, determinism, recorded-support, reference-success, and tested-failure gates | Inspect the exact replay and reproduce independently; this is not a fleet-safety conclusion |
| Mutation rejected | The edit exceeded route/physical/map constraints | Read the reason; change the parameters or scenario |
| Execution failed | A worker, source, reproducibility, or integrity check failed | Read the last stage and recovery action; inspect the job's private `worker.log` |
| Cancelled / interrupted / timed out | No completed result is accepted | Rerun after addressing the stop condition |

For example, scenario 8 at +0.2 s and 0.90× was rejected because its changed
progress exceeded the recorded route. That is an invalid input, **not** a
planner failure. The tool deliberately preserves that attempt in history.

## Optional recorded-behavior support

Without a support model you can run simulations and inspect exact trajectories,
but **cannot qualify a regression**. The UI says so explicitly.

Prepare the existing empirical-support protocol when you want this gate:

```bash
uv run --frozen planmargin-build-empirical-support
```

This is a real-data scan of 16 specified WOMD training shards, with resumable
checkpoints. It costs local compute and download time, not a subscription. The
runner uses `artifacts/realism/lead-braking-support-v1/model.json` when present,
or the original workspace's `lead-braking-support-v1-00c3727/model.json` for
backward compatibility. Every worker validates the model and records its hash.
The support value is a calibrated conformity score under this bounded sample,
not a probability that driving is safe.

## Reproduce without the browser

Stop the workbench first—only one supervisor may own a workspace:

```bash
uv run --frozen planmargin-run-experiment \
  --selection-order 1 --onset 0 --speed 0.9
```

The CLI waits for its own worker and prints the resulting record. Interrupted,
failed, and timed-out executions return a nonzero exit status. A mutation
rejection is a valid test outcome, so it returns zero with status `rejected`.
Never infer a scientific finding from the process exit code alone.

## Retention, resources, and privacy

Jobs live under ignored `artifacts/local-experiments/<job-id>/`:

- `request.json`: immutable configuration and protocol.
- `state.json`: supervisor-owned status, timing, and result summary.
- `progress.json`: worker-reported execution stages.
- `worker.log`: private diagnostics; may include licensed source identifiers.
- `result.json`: hash-sealed decision, gates, metrics, and provenance.
- `collection.json`: complete trajectories for accepted, verified runs only.

One worker runs at a time. It has a 15-minute wall-time limit and is terminated
as a process group on cancellation. At 200 retained job directories, new runs
are refused; archive completed folders outside the workspace if needed. Never
move an active job. Closing the server marks its active job interrupted.

Results are not added to the frozen 3,200-proposal campaign, its denominators,
or the saved Test health report. **Live local runs** reflects this separate
lifecycle. Gemini's **campaign guide**
explains the saved public aggregates, not these new private experiment results.

API requests require the local session; state-changing browser requests also
require an allowed loopback origin and bounded JSON. Result and replay exports
are verified against their hashes. No script, command, path, or cloud resource
can be supplied through experiment configuration. No data leaves the machine
for Gemini or another hosted analysis service through this workflow.

Keep the private records and replay media local. The existing data license and
publication boundary still applies; exporting a file is not permission to
republish it. See [data handling](../data/README.md) and the
[full-workspace runbook](reproducing-the-workspace.md) for the separate sensor,
3DGS, learning, and campaign pipelines.
