import { ChangeDetectionStrategy, Component, inject, output, signal } from '@angular/core';
import { ExperimentJob, ExperimentService } from '../experiment.service';
import { LocalEvidenceService } from '../local-evidence.service';
import { DebuggerRun } from '../debugger.types';

@Component({
  selector: 'app-experiment-workspace',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="experiment-page">
      <header class="page-heading">
        <div>
          <span class="eyebrow">Local experiment</span>
          <h1>Test a scenario change</h1>
          <p>
            Run both planners on the original and changed scene. Inspect the outcome—not just a
            saved answer.
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
            <h2 id="configure-title">Lead-vehicle braking</h2>
            <p>
              Choose one of ten selected real WOMD training scenarios. Only the lead vehicle's
              timing and speed change.
            </p>
            @if (experiments.readiness(); as readiness) {
              @if (!readiness.ready) {
                <div class="notice">
                  <strong>Planning inputs are missing</strong>
                  <p>After authorizing Waymo access, run:</p>
                  <code>{{ readiness.setup_command }}</code>
                </div>
              } @else if (!readiness.empirical_support_ready) {
                <div class="notice">
                  Simulation is available. Empirical realism qualification is unavailable until the
                  support model is prepared.
                </div>
              }
            }
            <form (submit)="start($event)">
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
                <strong>Two fixed controller configurations</strong>
                <span>Tested: default Waymax IDM</span
                ><span>Reference: conservative Waymax IDM</span>
                <small>Original and changed cases each run twice per controller.</small>
              </div>
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
              <div class="job-heading">
                <div>
                  <strong>Scenario {{ job.config.selection_order }}</strong>
                  <span
                    >+{{ job.config.braking_onset_offset_s.toFixed(1) }} s onset ·
                    {{ job.config.speed_multiplier }}× speed</span
                  >
                </div>
                <span class="status" [class.bad]="!!job.error">{{ statusLabel(job) }}</span>
              </div>
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
                      result.decision === 'qualified'
                        ? 'All finding gates passed'
                        : result.decision === 'invalid_mutation'
                          ? 'Change rejected by validity checks'
                          : 'Not a qualifying regression'
                    }}
                  </h3>
                  <p>{{ result.explanation }}</p>
                  @if (result.rejection_reasons?.length) {
                    <p class="notice">{{ rejectionExplanation(result.rejection_reasons) }}</p>
                  }
                  @if (result.controllers; as controllers) {
                    @if (result.original_controllers; as original) {
                      <table class="comparison" aria-label="Original and changed minimum clearance">
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
                              <th scope="row">{{ role === 'tested' ? 'Tested' : 'Reference' }}</th>
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
                    <dl class="outcomes">
                      <div>
                        <dt>Tested planner</dt>
                        <dd>
                          {{ controllers['tested'].outcome.success ? 'Succeeded' : 'Failed' }}
                        </dd>
                      </div>
                      <div>
                        <dt>Reference planner</dt>
                        <dd>
                          {{ controllers['reference'].outcome.success ? 'Succeeded' : 'Failed' }}
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
                    <summary>Finding gates and integrity</summary>
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
                  Use this configuration again
                </button>
              }
            } @else {
              <div class="empty">
                <h3>Your next investigation starts here</h3>
                <p>
                  Choose a scenario and a bounded change, then run it. This panel will show real
                  execution stages, both planner outcomes, and an exact replay when the mutation is
                  valid.
                </p>
              </div>
            }
            <p class="boundary">
              These are exploratory local experiments. They never change the frozen campaign's
              results or count as a Waymo Driver safety claim.
            </p>
          </section>
        </div>
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
                (click)="experiments.selectedId.set(job.job_id)"
              >
                <strong>Scenario {{ job.config.selection_order }}</strong
                ><span
                  >+{{ job.config.braking_onset_offset_s.toFixed(1) }} s ·
                  {{ job.config.speed_multiplier }}×</span
                >
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
  protected readonly scenario = signal(1);
  protected readonly onset = signal(0);
  protected readonly speed = signal(0.9);
  protected readonly loadingReplay = signal(false);
  protected readonly actionError = signal<string | undefined>(undefined);
  protected start(event: Event): void {
    event.preventDefault();
    this.actionError.set(undefined);
    void this.experiments.start({
      selection_order: this.scenario(),
      braking_onset_offset_s: this.onset(),
      speed_multiplier: this.speed(),
    });
  }
  protected reuse(job: ExperimentJob): void {
    this.scenario.set(job.config.selection_order);
    this.onset.set(job.config.braking_onset_offset_s);
    this.speed.set(job.config.speed_multiplier);
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
