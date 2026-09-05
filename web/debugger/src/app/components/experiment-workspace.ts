import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  output,
  signal,
} from '@angular/core';
import {
  ExperimentConfig,
  ExperimentJob,
  ExperimentService,
  sameExperimentConfig,
} from '../experiment.service';
import { LocalEvidenceService } from '../local-evidence.service';
import { DebuggerRun } from '../debugger.types';
import { LiveTestHealth } from './live-test-health';

@Component({
  selector: 'app-experiment-workspace',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LiveTestHealth],
  template: `
    <main class="experiment-page">
      <header class="page-heading">
        <div>
          <span class="eyebrow">Local experiment</span>
          <h1>Run a behavior test</h1>
          <p>
            Choose a real scenario, execute a bounded test plan, then inspect its events and exact
            replay.
          </p>
        </div>
        <button type="button" (click)="campaignRequested.emit()">View recorded campaign</button>
      </header>
      @if (!local.connected()) {
        <section class="card setup">
          <h2>Connect your local runner</h2>
          <p>
            Experiments use licensed Waymo data on your machine. No Gemini key, GPU, or sensor
            reconstruction is needed.
          </p>
          <code>uv run --frozen planmargin-workbench --planning-only</code>
          <button class="primary" type="button" (click)="connectRequested.emit()">
            Open local workspace
          </button>
        </section>
      } @else {
        @if (experiments.error()) {
          <div class="error" role="alert">
            <span>{{ experiments.error() }}</span>
            <button type="button" (click)="experiments.error.set(undefined); experiments.refresh()">
              Refresh status
            </button>
          </div>
        }
        <div class="experiment-grid">
          <section class="card configuration" aria-labelledby="configure-title">
            <span class="eyebrow">1 · Configure</span>
            <h2 id="configure-title">{{ planLabel(testPlan()) }}</h2>
            <p>
              {{
                testPlan() === 'lead_braking'
                  ? "Change the lead vehicle's timing and speed in one of ten real WOMD scenarios."
                  : 'Keep recorded traffic unchanged. Compare the primary baseline, command loss without protection, and a protected controller.'
              }}
            </p>
            @if (experiments.readiness(); as readiness) {
              @if (!readiness.ready) {
                <div class="notice">
                  <strong>Planning inputs are missing</strong>
                  <p>After authorizing Waymo access, run:</p>
                  <code>{{ readiness.setup_command }}</code>
                </div>
              } @else if (!readiness.empirical_support_ready && testPlan() === 'lead_braking') {
                <div class="notice">
                  Simulation is available. Empirical realism qualification is unavailable until the
                  support model is prepared.
                </div>
              }
            }
            <form (submit)="start($event)">
              <label for="experiment-plan">Test plan</label>
              <select
                id="experiment-plan"
                [value]="testPlan()"
                (change)="testPlan.set($any($event.target).value)"
              >
                <option value="lead_braking">Lead-vehicle braking</option>
                <option value="command_dropout">Command loss · fallback protection</option>
                <option value="assistance_handoff">Command loss · recovery handoff</option>
              </select>
              <label for="experiment-scenario">Recorded scenario</label>
              <select
                id="experiment-scenario"
                [value]="scenario()"
                (change)="scenario.set(+$any($event.target).value)"
              >
                @for (number of scenarios; track number) {
                  <option [value]="number">Scenario {{ number }}</option>
                }
              </select>
              @if (testPlan() === 'lead_braking') {
                <label for="experiment-onset">Braking onset shift</label>
                <select
                  id="experiment-onset"
                  [value]="onset()"
                  (change)="onset.set(+$any($event.target).value)"
                >
                  @for (offset of offsets; track offset) {
                    <option [value]="offset">+{{ offset.toFixed(1) }} seconds</option>
                  }
                </select>
                <label for="experiment-speed">Lead speed multiplier</label>
                <input
                  id="experiment-speed"
                  type="number"
                  min="0.75"
                  max="1"
                  step="0.001"
                  required
                  [value]="speed()"
                  (input)="speed.set(+$any($event.target).value)"
                  aria-describedby="speed-help"
                />
                <small id="speed-help"
                  >0.75–1.00 × recorded speed. For example, 0.90 means 90%.</small
                >
                <div class="controller-note">
                  <strong>Controller comparison</strong>
                  <label for="tested-controller-mode">Tested planner configuration</label>
                  <select
                    id="tested-controller-mode"
                    [value]="customController() ? 'custom' : 'default'"
                    (change)="customController.set($any($event.target).value === 'custom')"
                  >
                    <option value="default">Default Waymax IDM</option>
                    <option value="custom">Custom IDM settings</option>
                  </select>
                  @if (customController()) {
                    <label for="controller-speed">Desired speed (m/s)</label>
                    <input
                      id="controller-speed"
                      type="number"
                      min="1"
                      max="40"
                      step="0.1"
                      required
                      [value]="desiredSpeed()"
                      (input)="desiredSpeed.set(+$any($event.target).value)"
                    />
                    <label for="controller-spacing">Minimum spacing (m)</label>
                    <input
                      id="controller-spacing"
                      type="number"
                      min="0.5"
                      max="10"
                      step="0.1"
                      required
                      [value]="spacing()"
                      (input)="spacing.set(+$any($event.target).value)"
                    />
                    <label for="controller-headway">Safe time headway (s)</label>
                    <input
                      id="controller-headway"
                      type="number"
                      min="0.5"
                      max="5"
                      step="0.1"
                      required
                      [value]="headway()"
                      (input)="headway.set(+$any($event.target).value)"
                    />
                    <small
                      >Changes only the tested IDM policy in this new run. Not a custom model,
                      production controller, or change to the frozen campaign.</small
                    >
                  }
                  <span>Reference: conservative Waymax IDM · fixed</span>
                  <small>Original and changed cases each run twice per controller.</small>
                </div>
              } @else {
                <div class="controller-note">
                  <strong>Fixed, reproducible protocol</strong>
                  <span
                    >2.0 s · primary command lost; protection switches to conservative IDM.</span
                  >
                  @if (testPlan() === 'assistance_handoff') {
                    <span
                      >3.0 s · scripted recovery signal; protected controller resumes the primary
                      IDM.</span
                    >
                  } @else {
                    <span>The fallback remains active through the end of the rollout.</span>
                  }
                  <small
                    >Unprotected control holds its last commanded pose. Three policies × two
                    repetitions = six real Waymax rollouts. No live operator or AI-controlled
                    assistance.</small
                  >
                </div>
              }
              <label for="experiment-deadline">Completion deadline (seconds)</label>
              <input
                id="experiment-deadline"
                type="number"
                min="10"
                max="900"
                step="1"
                required
                [value]="deadline()"
                (input)="deadline.set(+$any($event.target).value)"
              />
              <small
                >A local latency objective, not simulated driving time. Late runs remain
                inspectable; the hard worker limit is 900 s.</small
              >
              @if (rerunOf() && draftMatchesRerun()) {
                <p class="notice">
                  Linked rerun of {{ rerunOf()!.slice(0, 8) }}. A successful rerun can resolve its
                  diagnostics without erasing the original.
                </p>
              }
              <button
                class="primary"
                type="submit"
                [disabled]="
                  !experiments.readiness()?.ready || !!experiments.active() || experiments.busy()
                "
              >
                {{
                  experiments.busy()
                    ? 'Submitting…'
                    : experiments.active()
                      ? 'An experiment is running'
                      : 'Run experiment'
                }}
              </button>
              <small>One local worker · 15-minute limit · no paid services</small>
            </form>
          </section>
          <section class="card execution" aria-labelledby="execution-title">
            <span class="eyebrow">2 · Execute and inspect</span>
            <h2 id="execution-title">Experiment result</h2>
            @if (experiments.selected(); as job) {
              <p class="result-context" [class.different]="!draftMatchesResult()" role="status">
                {{
                  draftMatchesResult()
                    ? 'Saved run · matches the configuration on the left'
                    : 'Previous run · does not match your current configuration'
                }}
                <span
                  >The result below belongs to run {{ job.job_id.slice(0, 8) }}. Editing the form
                  does not execute it.</span
                >
                @if (!draftMatchesResult()) {
                  <button type="button" (click)="reuse(job)">Load saved setup</button>
                }
              </p>
              <div class="job-heading">
                <div>
                  <strong>Scenario {{ job.config.selection_order }}</strong>
                  <span>{{ planLabel(job.config.test_plan ?? 'lead_braking') }}</span>
                  @if (!job.config.test_plan || job.config.test_plan === 'lead_braking') {
                    <span
                      >+{{ job.config.braking_onset_offset_s.toFixed(1) }} s onset ·
                      {{ job.config.speed_multiplier }}× speed</span
                    >
                    <small
                      >{{
                        job.config.tested_controller ? 'Custom tested IDM' : 'Default tested IDM'
                      }}
                      · fixed conservative reference</small
                    >
                  }
                  @if (job.rerun_of) {
                    <button type="button" (click)="experiments.selectJob(job.rerun_of)">
                      Inspect original run {{ job.rerun_of.slice(0, 8) }}
                    </button>
                  }
                </div>
                <span class="status" [class.bad]="!!job.error">{{ statusLabel(job) }}</span>
              </div>
              @if (job.completion_deadline_seconds) {
                <p
                  class="deadline"
                  [class.error]="
                    job.status !== 'cancelled' &&
                    job.elapsed_seconds > job.completion_deadline_seconds
                  "
                >
                  Declared deadline: {{ job.completion_deadline_seconds }} s ·
                  {{
                    job.status === 'cancelled'
                      ? 'cancelled — not scored'
                      : job.elapsed_seconds > job.completion_deadline_seconds
                        ? 'deadline missed'
                        : job.status === 'running'
                          ? 'within deadline so far'
                          : 'within deadline'
                  }}
                </p>
              }
              <div class="execution-status" role="status">
                <strong>{{ job.stage_label }}</strong>
                <span
                  >{{ duration(job.elapsed_seconds) }} elapsed · {{ job.job_id.slice(0, 8) }}</span
                >
              </div>
              @if (job.status === 'running') {
                <p>
                  Progress comes from the worker. The first planner run includes JAX compilation.
                  You can leave this page; the run continues locally.
                </p>
                <button
                  type="button"
                  (click)="experiments.cancel(job.job_id)"
                  [disabled]="experiments.busy()"
                >
                  Cancel experiment
                </button>
              }
              @if (job.error; as error) {
                <div class="error" role="alert">
                  <div>
                    <strong>Execution stopped at {{ job.stage_label }}</strong>
                    <p>{{ error.recovery }}</p>
                    <code>{{ error.code }}</code>
                  </div>
                </div>
                <p>
                  This is an execution outcome, not a planner failure. No completed result is being
                  substituted.
                </p>
              }
              @if (job.result; as result) {
                <div class="result">
                  <h3>
                    {{
                      result.decision === 'checks_passed'
                        ? 'Behavior checks passed'
                        : result.decision === 'checks_failed'
                          ? 'Behavior checks failed'
                          : result.decision === 'qualified'
                            ? 'All finding gates passed'
                            : result.decision === 'invalid_mutation'
                              ? 'Change rejected by validity checks'
                              : 'Not a qualifying regression'
                    }}
                  </h3>
                  <p>{{ result.explanation }}</p>
                  @if (result.behavior_events; as events) {
                    <h3>Observed behavior events</h3>
                    <ol class="stages">
                      @for (event of events; track event.step) {
                        <li>
                          <span>{{ event.label }}</span
                          ><strong>{{ event.time_seconds.toFixed(1) }} s</strong>
                        </li>
                      }
                    </ol>
                    @if (result.qualification; as qualification) {
                      <table class="comparison">
                        <caption>
                          Distance traveled after the fault
                        </caption>
                        <tbody>
                          @for (
                            role of ['baseline', 'unprotected', 'protected', 'assisted'];
                            track role
                          ) {
                            @if (qualification[role]; as measured) {
                              <tr>
                                <th scope="row">
                                  {{ role === 'assisted' ? 'Protected with recovery' : role }}
                                </th>
                                <td>{{ measured.post_fault_progress_m?.toFixed(2) }} m</td>
                              </tr>
                            }
                          }
                        </tbody>
                      </table>
                    }
                    <small
                      >The replay shares one measured baseline across its original roles. Six
                      physical rollouts, not eight. Open the replay to jump to each observed
                      event.</small
                    >
                  }
                  @if (result.rejection_reasons?.length) {
                    <p class="notice">{{ rejectionExplanation(result.rejection_reasons) }}</p>
                  }
                  @if (result.controllers; as controllers) {
                    @if (!result.behavior_events) {
                      @if (result.original_controllers; as original) {
                        <table
                          class="comparison"
                          aria-label="Original and changed minimum clearance"
                        >
                          <caption>
                            Minimum signed clearance to the lead vehicle
                          </caption>
                          <thead>
                            <tr>
                              <th scope="col">Planner</th>
                              <th scope="col">Original</th>
                              <th scope="col">Changed</th>
                            </tr>
                          </thead>
                          <tbody>
                            @for (role of ['tested', 'reference']; track role) {
                              <tr>
                                <th scope="row">
                                  {{ role === 'tested' ? 'Tested' : 'Reference' }}
                                </th>
                                <td>
                                  {{
                                    original[
                                      role
                                    ].interaction_metrics.minimum_signed_separation_m.toFixed(3)
                                  }}
                                  m
                                </td>
                                <td>
                                  {{
                                    controllers[
                                      role
                                    ].interaction_metrics.minimum_signed_separation_m.toFixed(3)
                                  }}
                                  m
                                </td>
                              </tr>
                            }
                          </tbody>
                        </table>
                        <small
                          >Positive means separated; negative means overlapping in this geometric
                          metric. Clearance alone does not decide the finding.</small
                        >
                      }
                    }
                    <dl class="outcomes">
                      <div>
                        <dt>
                          {{ result.behavior_events ? 'Unprotected validity' : 'Tested planner' }}
                        </dt>
                        <dd>
                          {{
                            controllers['tested'].outcome.success
                              ? result.behavior_events
                                ? 'Passed'
                                : 'Succeeded'
                              : 'Failed'
                          }}
                        </dd>
                      </div>
                      <div>
                        <dt>
                          {{ result.behavior_events ? 'Protected validity' : 'Reference planner' }}
                        </dt>
                        <dd>
                          {{
                            controllers['reference'].outcome.success
                              ? result.behavior_events
                                ? 'Passed'
                                : 'Succeeded'
                              : 'Failed'
                          }}
                        </dd>
                      </div>
                      <div>
                        <dt>Minimum signed clearance</dt>
                        <dd>
                          {{
                            controllers[
                              'tested'
                            ].interaction_metrics.minimum_signed_separation_m.toFixed(3)
                          }}
                          m
                        </dd>
                      </div>
                    </dl>
                    @if (result.behavior_events) {
                      <small
                        >A stopped vehicle can pass validity checks. The behavior gates above also
                        require progress recovery and exact transitions.</small
                      >
                    }
                  }
                  <div class="actions">
                    @if (result.collection_sha256) {
                      <button
                        class="primary"
                        type="button"
                        (click)="replay(job.job_id)"
                        [disabled]="loadingReplay()"
                      >
                        {{ loadingReplay() ? 'Verifying replay…' : 'Open this experiment replay' }}
                      </button>
                    }
                    <button type="button" (click)="exportResult(job.job_id)">
                      Export result JSON
                    </button>
                  </div>
                  <details>
                    <summary>Test gates and integrity</summary>
                    @if (job.config.tested_controller; as controller) {
                      <p>
                        Tested IDM: desired speed {{ controller.desired_vel_mps }} m/s · minimum
                        spacing {{ controller.min_spacing_m }} m · headway
                        {{ controller.safe_time_headway_s }} s.
                      </p>
                    }
                    <dl class="gates">
                      @for (gate of gateEntries(result.gates); track gate[0]) {
                        <div>
                          <dt>{{ gate[0].replaceAll('_', ' ') }}</dt>
                          <dd>{{ gate[1] ? 'Passed' : 'Not passed' }}</dd>
                        </div>
                      }
                    </dl>
                    <p class="digest">Result SHA-256: {{ result.result_sha256 }}</p>
                  </details>
                </div>
              }
              @if (actionError()) {
                <p class="error" role="alert">{{ actionError() }}</p>
              }
              @if (job.events.length) {
                <details [open]="job.status === 'running' || !!job.error">
                  <summary>Execution stages and timing</summary>
                  <ol class="stages">
                    @for (event of job.events; track event.stage) {
                      <li>
                        <span>{{ event.label }}</span
                        ><small>{{
                          event.duration_seconds === null
                            ? job.status === 'running'
                              ? 'Running'
                              : 'Stopped'
                            : duration(event.duration_seconds)
                        }}</small>
                      </li>
                    }
                  </ol>
                </details>
              }
              @if (job.status !== 'running') {
                <button type="button" class="rerun" (click)="reuse(job)">
                  Prepare linked rerun
                </button>
              }
            } @else {
              <div class="empty">
                <h3>Your next investigation starts here</h3>
                <p>
                  Choose a scenario and a bounded change, then run it. This panel will show real
                  execution stages, controller outcomes, and an exact replay when the test
                  completes.
                </p>
              </div>
            }
            <p class="boundary">
              These are exploratory local experiments. They never change the frozen campaign's
              results or count as a Waymo Driver safety claim.
            </p>
          </section>
        </div>
        <app-live-test-health (inspectRequested)="scrollToResult()" />
        <section class="card history" aria-labelledby="history-title">
          <header>
            <div>
              <span class="eyebrow">Persistent local records</span>
              <h2 id="history-title">Run history</h2>
            </div>
            <span
              >{{ experiments.jobs().length }}
              {{ experiments.jobs().length === 1 ? 'experiment' : 'experiments' }}</span
            >
          </header>
          @if (!experiments.jobs().length) {
            <p>
              No experiments yet. Completed, rejected, interrupted, and cancelled runs remain
              visible here.
            </p>
          }
          <div class="history-list">
            @for (job of experiments.jobs(); track job.job_id) {
              <button
                type="button"
                [class.selected]="experiments.selectedId() === job.job_id"
                (click)="experiments.selectJob(job.job_id)"
              >
                <strong>Scenario {{ job.config.selection_order }}</strong
                ><span>{{ planLabel(job.config.test_plan ?? 'lead_braking') }}</span>
                <span>{{ statusLabel(job) }}</span
                ><span>{{ duration(job.elapsed_seconds) }}</span
                ><small>{{ job.job_id.slice(0, 8) }}</small>
              </button>
            }
          </div>
        </section>
      }
    </main>
  `,
  styleUrl: './experiment-workspace.css',
})
export class ExperimentWorkspace {
  protected readonly experiments = inject(ExperimentService);
  protected readonly local = inject(LocalEvidenceService);
  readonly campaignRequested = output<void>();
  readonly connectRequested = output<void>();
  readonly replayRequested = output<DebuggerRun>();
  protected readonly scenarios = Array.from({ length: 10 }, (_, index) => index + 1);
  protected readonly offsets = [0, 0.1, 0.2, 0.3, 0.4, 0.5];
  protected readonly testPlan = signal<NonNullable<ExperimentConfig['test_plan']>>(
    this.experiments.draft().test_plan ?? 'lead_braking',
  );
  protected readonly deadline = signal(120);
  protected readonly rerunOf = signal<string | undefined>(undefined);
  protected readonly draftMatchesRerun = computed(() => {
    const parent = this.experiments.jobs().find((job) => job.job_id === this.rerunOf());
    return !!parent && sameExperimentConfig(parent.config, this.draftConfig());
  });
  protected readonly scenario = signal(this.experiments.draft().selection_order);
  protected readonly onset = signal(this.experiments.draft().braking_onset_offset_s);
  protected readonly speed = signal(this.experiments.draft().speed_multiplier);
  protected readonly customController = signal(!!this.experiments.draft().tested_controller);
  protected readonly desiredSpeed = signal(
    this.experiments.draft().tested_controller?.desired_vel_mps ?? 30,
  );
  protected readonly spacing = signal(
    this.experiments.draft().tested_controller?.min_spacing_m ?? 2,
  );
  protected readonly headway = signal(
    this.experiments.draft().tested_controller?.safe_time_headway_s ?? 2,
  );
  protected readonly draftConfig = computed<ExperimentConfig>(() => ({
    selection_order: this.scenario(),
    ...(this.testPlan() !== 'lead_braking' ? { test_plan: this.testPlan() } : {}),
    braking_onset_offset_s: this.testPlan() === 'lead_braking' ? this.onset() : 0,
    speed_multiplier: this.testPlan() === 'lead_braking' ? this.speed() : 1,
    ...(this.customController() && this.testPlan() === 'lead_braking'
      ? {
          tested_controller: {
            desired_vel_mps: this.desiredSpeed(),
            min_spacing_m: this.spacing(),
            safe_time_headway_s: this.headway(),
          },
        }
      : {}),
  }));
  protected readonly draftMatchesResult = computed(() => {
    const job = this.experiments.selected();
    return job !== undefined && sameExperimentConfig(this.draftConfig(), job.config);
  });
  constructor() {
    effect(() => this.experiments.draft.set(this.draftConfig()));
  }
  protected readonly loadingReplay = signal(false);
  protected readonly actionError = signal<string | undefined>(undefined);
  protected start(event: Event): void {
    event.preventDefault();
    this.actionError.set(undefined);
    void this.experiments.start(
      this.draftConfig(),
      this.deadline(),
      this.draftMatchesRerun() ? this.rerunOf() : undefined,
    );
  }
  protected reuse(job: ExperimentJob): void {
    this.testPlan.set(job.config.test_plan ?? 'lead_braking');
    this.rerunOf.set(job.job_id);
    this.deadline.set(job.completion_deadline_seconds ?? 120);
    this.scenario.set(job.config.selection_order);
    this.onset.set(job.config.braking_onset_offset_s);
    this.speed.set(job.config.speed_multiplier);
    this.customController.set(!!job.config.tested_controller);
    this.desiredSpeed.set(job.config.tested_controller?.desired_vel_mps ?? 30);
    this.spacing.set(job.config.tested_controller?.min_spacing_m ?? 2);
    this.headway.set(job.config.tested_controller?.safe_time_headway_s ?? 2);
    document.getElementById('experiment-scenario')?.focus();
  }
  protected async replay(jobId: string): Promise<void> {
    this.loadingReplay.set(true);
    this.actionError.set(undefined);
    try {
      this.replayRequested.emit(await this.experiments.replay(jobId));
    } catch (error) {
      this.actionError.set(error instanceof Error ? error.message : 'Replay unavailable');
    } finally {
      this.loadingReplay.set(false);
    }
  }
  protected planLabel(plan: string): string {
    return (
      (
        {
          lead_braking: 'Lead-vehicle braking',
          command_dropout: 'Command-loss protection',
          assistance_handoff: 'Recovery handoff',
        } as Record<string, string>
      )[plan] ?? plan
    );
  }
  protected scrollToResult(): void {
    document
      .getElementById('execution-title')
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  protected async exportResult(jobId: string): Promise<void> {
    try {
      await this.experiments.export(jobId);
    } catch (error) {
      this.actionError.set(error instanceof Error ? error.message : 'Export unavailable');
    }
  }
  protected gateEntries(gates: Record<string, boolean>): [string, boolean][] {
    return Object.entries(gates);
  }
  protected rejectionExplanation(reasons: string[]): string {
    return reasons
      .map((reason) =>
        reason === 'mutated_progress_exceeds_recorded_route'
          ? 'The shifted trajectory would extend beyond the recorded road path. Try a smaller onset shift or another recorded scenario.'
          : reason.replaceAll('_', ' '),
      )
      .join(' ');
  }
  protected duration(seconds: number): string {
    return seconds < 60
      ? `${seconds.toFixed(1)} s`
      : `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
  }
  protected statusLabel(job: ExperimentJob): string {
    return {
      running: 'Running',
      succeeded: 'Execution complete',
      rejected: 'Mutation rejected',
      failed: 'Execution failed',
      cancelled: 'Cancelled',
      interrupted: 'Interrupted',
      timed_out: 'Timed out',
    }[job.status];
  }
}
