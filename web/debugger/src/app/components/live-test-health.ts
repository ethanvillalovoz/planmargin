import { ChangeDetectionStrategy, Component, inject, output } from '@angular/core';
import { ExperimentService } from '../experiment.service';
import { LocalEvidenceService } from '../local-evidence.service';

@Component({
  selector: 'app-live-test-health',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="health" aria-labelledby="live-health-title">
      <header>
        <div>
          <span class="eyebrow">Live · this workspace</span>
          <h2 id="live-health-title">Local test health</h2>
        </div>
        <button type="button" (click)="experiments.refresh()" [disabled]="!local.connected()">
          Refresh health
        </button>
      </header>
      @if (!local.connected()) {
        <p>
          Connect a local runner to inspect current jobs. The saved campaign below is historical
          evidence, not a live service.
        </p>
      } @else if (experiments.health(); as health) {
        <p role="status">
          {{
            health.active_incidents
              ? health.active_incidents + ' unresolved diagnostics'
              : health.total_jobs
                ? 'No unresolved execution or behavior diagnostics'
                : 'No local experiments yet'
          }}. A negative regression finding is not an execution failure.
        </p>
        <dl>
          <div>
            <dt>Retained jobs</dt>
            <dd>{{ health.total_jobs }}</dd>
          </div>
          <div>
            <dt>On-time completions</dt>
            <dd>{{ health.on_time_completed_jobs }} / {{ health.deadline_measured_jobs }}</dd>
          </div>
          <div>
            <dt>Resolved diagnostics</dt>
            <dd>{{ health.resolved_incidents }}</dd>
          </div>
        </dl>
        <small
          >Deadlines are declared before execution. {{ health.unmeasured_jobs }} older jobs have no
          deadline measurement. Cancelled and running jobs are excluded from the completion
          denominator.</small
        >
        @if (experiments.active(); as job) {
          <button class="active-job" type="button" (click)="inspect(job.job_id)">
            Running · {{ job.stage_label }} · {{ job.elapsed_seconds.toFixed(1) }} s — inspect
            progress
          </button>
        }
        @if (health.incidents.length) {
          <details [open]="health.active_incidents > 0">
            <summary>Execution and behavior diagnostics</summary>
            <ul>
              @for (incident of health.incidents; track incident.job_id + incident.kind) {
                <li [class.resolved]="!!incident.resolved_by">
                  <div>
                    <strong>{{ incident.kind.replaceAll('_', ' ') }}</strong>
                    <span
                      >Scenario {{ incident.selection_order }} ·
                      {{ incident.test_plan.replaceAll('_', ' ') }} ·
                      {{ incident.stage_label }}</span
                    >
                    <p>{{ incident.recovery }}</p>
                    @if (incident.kind === 'completion_deadline_missed') {
                      <small
                        >{{ incident.elapsed_seconds.toFixed(1) }} s elapsed /
                        {{ incident.deadline_seconds }} s declared deadline</small
                      >
                    }
                    @if (incident.resolved_by) {
                      <small
                        >Resolved by linked rerun {{ incident.resolved_by.slice(0, 8) }}. Original
                        evidence retained.</small
                      >
                    }
                  </div>
                  <div class="incident-actions">
                    <button type="button" (click)="inspect(incident.job_id)">Inspect run</button>
                    @if (incident.resolved_by) {
                      <button type="button" (click)="inspect(incident.resolved_by)">
                        Inspect resolution
                      </button>
                    }
                  </div>
                </li>
              }
            </ul>
          </details>
        }
      } @else {
        <p role="status">Loading authenticated local health…</p>
      }
      @if (experiments.error()) {
        <p role="alert">{{ experiments.error() }}</p>
      }
    </section>
  `,
  styles: `
    :host {
      display: block;
    }
    .health {
      background: white;
      border: 1px solid #dbe4e0;
      border-radius: 18px;
      padding: 24px;
      color: #172239;
    }
    header,
    li {
      display: flex;
      justify-content: space-between;
      align-items: start;
      gap: 20px;
    }
    h2 {
      margin: 6px 0 12px;
      font-size: 22px;
    }
    .eyebrow,
    dt {
      color: #526371;
      font-size: 12px;
    }
    p,
    small {
      color: #526371;
      line-height: 1.6;
    }
    small,
    li span {
      display: block;
    }
    dl {
      display: flex;
      gap: 36px;
      flex-wrap: wrap;
    }
    dd {
      margin: 4px 0;
      font-size: 24px;
      font-weight: 650;
    }
    button {
      border: 1px solid #b8cbc3;
      background: #f3f8f5;
      border-radius: 10px;
      padding: 10px 14px;
      color: #145840;
      cursor: pointer;
      flex-shrink: 0;
    }
    button:focus-visible,
    summary:focus-visible {
      outline: 3px solid #1968fa;
      outline-offset: 3px;
    }
    button:disabled {
      opacity: 0.5;
      cursor: default;
    }
    ul {
      margin: 0;
      padding: 0;
      list-style: none;
    }
    li {
      padding: 18px 0;
      border-top: 1px solid #e1e8e5;
    }
    li strong {
      text-transform: capitalize;
    }
    li p {
      margin: 6px 0;
    }
    li.resolved strong {
      color: #168052;
    }
    summary {
      cursor: pointer;
      margin: 20px 0;
    }
    .active-job {
      margin-top: 16px;
    }
    .incident-actions {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    @media (max-width: 680px) {
      header,
      li {
        flex-direction: column;
      }
      .health {
        padding: 18px;
      }
      dl {
        gap: 18px;
      }
    }
  `,
})
export class LiveTestHealth {
  protected readonly experiments = inject(ExperimentService);
  protected readonly local = inject(LocalEvidenceService);
  readonly inspectRequested = output<void>();
  protected inspect(jobId: string): void {
    this.experiments.selectJob(jobId);
    this.inspectRequested.emit();
  }
}
