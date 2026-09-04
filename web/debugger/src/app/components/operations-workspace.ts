import { ChangeDetectionStrategy, Component, computed, output, signal } from '@angular/core';
import { TEST_OPERATIONS, TestOperationIssue } from '../test-operations';

type OperationsSection = 'overview' | 'coverage' | 'issues';
type IssueFilter = 'all' | 'active' | 'blocked' | 'pending_evidence';

@Component({
  selector: 'app-operations-workspace',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="ops-shell">
      <header class="ops-commandbar">
        <div>
          <span class="eyebrow">Simulation test operations</span>
          <h1>Campaign health and release evidence</h1>
          <p>
            Monitor execution, inspect coverage, and triage promotion gates from one sealed run.
          </p>
        </div>
        <div class="ops-actions">
          <span class="data-boundary"><i></i>Real WOMD · aggregate view</span>
          <button type="button" (click)="openScenarioLab.emit()">Open scenario lab</button>
        </div>
      </header>

      <nav class="ops-tabs" aria-label="Operations views">
        @for (item of sections; track item.id) {
          <button
            type="button"
            [class.active]="section() === item.id"
            (click)="section.set(item.id)"
          >
            {{ item.label }}
            @if (item.id === 'issues') {
              <span>{{ report.issues.length }}</span>
            }
          </button>
        }
        <small>Report {{ shortSeal() }}</small>
      </nav>

      @if (section() === 'overview') {
        <section class="status-strip" aria-label="Campaign status summary">
          <div class="primary-status">
            <span
              class="status-label"
              [class.degraded]="report.campaign.execution_health === 'degraded'"
              ><i></i>Execution {{ report.campaign.execution_health }}</span
            >
            <strong
              >{{ report.campaign.completed_cells }}/{{ report.campaign.planned_cells }}</strong
            >
            <small>campaign cells completed</small>
          </div>
          <div>
            <span>SLOs passing</span>
            <strong>{{ report.slo_summary.passing }}/{{ report.slo_summary.total }}</strong>
            <small>no pipeline alert active</small>
          </div>
          <div>
            <span>Closed-loop work</span>
            <strong>{{ compact(report.campaign.physical_rollouts) }}</strong>
            <small>{{ compact(report.campaign.waymax_steps) }} Waymax steps</small>
          </div>
          <div>
            <span>Behavior outcome</span>
            <strong class="neutral">0</strong>
            <small>qualifying regressions</small>
          </div>
          <div class="attention-status">
            <span>Promotion queue</span>
            <strong>{{ report.issues.length }}</strong>
            <small>measured decisions need review</small>
          </div>
        </section>

        <div class="ops-grid">
          <section class="panel pipeline-panel" aria-labelledby="pipeline-title">
            <header class="panel-heading">
              <div>
                <span>Current run</span>
                <h2 id="pipeline-title">Pipeline stages</h2>
              </div>
              <b
                ><i></i>{{ healthyStageCount() }}/{{ report.pipeline_stages.length }} stages
                healthy</b
              >
            </header>
            <ol class="stage-list">
              @for (stage of report.pipeline_stages; track stage.id; let index = $index) {
                <li>
                  <div class="stage-index">0{{ index + 1 }}</div>
                  <div class="stage-copy">
                    <strong>{{ stage.name }}</strong
                    ><span>{{ stage.detail }}</span>
                  </div>
                  <div class="stage-measure">
                    <b>{{ stage.observed }}</b
                    ><span [class.degraded]="stage.status === 'degraded'"
                      ><i></i>{{ stage.status === 'healthy' ? 'Healthy' : 'Degraded' }}</span
                    >
                  </div>
                </li>
              }
            </ol>
          </section>

          <section class="panel slo-panel" aria-labelledby="slo-title">
            <header class="panel-heading">
              <div>
                <span>Release contract</span>
                <h2 id="slo-title">Service-level objectives</h2>
              </div>
              <button type="button" (click)="section.set('coverage')">Coverage →</button>
            </header>
            <div class="slo-table" role="table" aria-label="Service-level objectives">
              <div class="slo-row head" role="row">
                <span>Objective</span><span>Target</span><span>Observed</span><span>State</span>
              </div>
              @for (slo of report.slos; track slo.id) {
                <div class="slo-row" role="row">
                  <span
                    ><strong>{{ slo.name }}</strong
                    ><small>{{ slo.owner }}</small></span
                  >
                  <span>{{ slo.target }}</span
                  ><span>{{ slo.observed }}</span
                  ><span
                    [class.pass]="slo.status === 'pass'"
                    [class.fail]="slo.status === 'fail'"
                    >{{ slo.status === 'pass' ? 'Pass' : 'Fail' }}</span
                  >
                </div>
              }
            </div>
          </section>

          <section class="panel issue-preview" aria-labelledby="attention-title">
            <header class="panel-heading">
              <div>
                <span>Engineering decisions</span>
                <h2 id="attention-title">Attention queue</h2>
              </div>
              <button type="button" (click)="section.set('issues')">View all →</button>
            </header>
            @for (issue of report.issues; track issue.id) {
              <button class="issue-row" type="button" (click)="openIssue(issue)">
                <span class="severity" [class.high]="issue.severity === 'high'"></span>
                <span
                  ><small>{{ issue.id }} · {{ stateLabel(issue.state) }}</small
                  ><strong>{{ issue.title }}</strong></span
                >
                <b>{{ issue.component }}</b
                ><i>→</i>
              </button>
            }
          </section>
        </div>
      }

      @if (section() === 'coverage') {
        <section class="coverage-layout">
          <div class="panel coverage-map">
            <header class="panel-heading">
              <div>
                <span>Versioned test plan</span>
                <h2>Behavior coverage</h2>
              </div>
              <b>{{ report.coverage.plan_version }}</b>
            </header>
            <div class="coverage-facts">
              <div>
                <span>Scenario family</span><strong>Lead-vehicle braking</strong
                ><small>real WOMD training scenes</small>
              </div>
              <div>
                <span>Scenarios</span><strong>{{ report.coverage.scenario_count }}</strong
                ><small>deterministically selected</small>
              </div>
              <div>
                <span>Seeds</span><strong>{{ report.coverage.seeds }}</strong
                ><small>per scenario and method</small>
              </div>
              <div>
                <span>Test cells</span><strong>{{ report.coverage.cells }}</strong
                ><small>complete and sealed</small>
              </div>
            </div>
            <div class="coverage-contract">
              <span>Mutation contract</span>
              @for (dimension of report.coverage.mutation_dimensions; track dimension) {
                <b>{{ dimension }}</b>
              }
            </div>
            <section class="fault-verification" aria-labelledby="fault-verification-title">
              <header>
                <div>
                  <span>Off-nominal behavior V&amp;V</span>
                  <h3 id="fault-verification-title">Protection and assistance protocols</h3>
                </div>
                <b>2 protocols qualified</b>
              </header>
              <div class="protocol-heading">
                <strong>01 · Sustained command dropout</strong>
                <b>
                  {{ report.coverage.fault_protection.scene_gate_passes }}/{{
                    report.coverage.fault_protection.scene_gate_total
                  }}
                  gates
                </b>
              </div>
              <div class="protocol-facts">
                <p>
                  <span>Injected fault</span
                  ><strong>{{ report.coverage.fault_protection.fault }}</strong
                  ><small>triggered at 2.0 seconds</small>
                </p>
                <p>
                  <span>Protected response</span
                  ><strong>{{ report.coverage.fault_protection.protected_behavior }}</strong
                  ><small
                    >{{ report.coverage.fault_protection.scenario_count }}/{{
                      report.coverage.fault_protection.scenario_count
                    }}
                    real scenes passed</small
                  >
                </p>
                <p>
                  <span>Verification work</span
                  ><strong
                    >{{ report.coverage.fault_protection.physical_rollouts }} physical
                    rollouts</strong
                  ><small>baseline, unprotected, and protected · repeated</small>
                </p>
              </div>
              <div class="protocol-heading secondary">
                <strong>02 · Assistance handoff recovery</strong>
                <b>
                  {{ report.coverage.assistance_handoff.scene_gate_passes }}/{{
                    report.coverage.assistance_handoff.scene_gate_total
                  }}
                  gates
                </b>
              </div>
              <div class="protocol-facts">
                <p>
                  <span>State sequence</span><strong>Fault → request → fallback</strong
                  ><small>deterministic resolution at 3.0 seconds</small>
                </p>
                <p>
                  <span>Recovery</span><strong>Primary resumes after resolution</strong
                  ><small>
                    {{ report.coverage.assistance_handoff.exact_transition_count }}/{{
                      report.coverage.assistance_handoff.scenario_count
                    }}
                    exact transition traces
                  </small>
                </p>
                <p>
                  <span>Verification work</span
                  ><strong>
                    {{ report.coverage.assistance_handoff.physical_rollouts }} physical rollouts
                  </strong>
                  <small>10 real scenes · 90/90 gates passed</small>
                </p>
              </div>
            </section>
            <div class="method-comparison">
              @for (method of methods(); track method.name) {
                <div>
                  <span>{{ method.name }}</span
                  ><strong
                    >{{ method.value.eligible_count.toLocaleString() }} /
                    {{ method.value.proposal_count.toLocaleString() }}</strong
                  >
                  <div><i [style.width.%]="method.value.eligible_rate * 100"></i></div>
                  <small
                    >{{ (method.value.eligible_rate * 100).toFixed(2) }}% empirically supported +
                    pipeline valid</small
                  >
                </div>
              }
            </div>
          </div>
          <aside class="panel gap-panel">
            <header class="panel-heading">
              <div>
                <span>Known unknowns</span>
                <h2>Coverage gaps</h2>
              </div>
              <b>{{ report.coverage.known_gaps.length }} open</b>
            </header>
            <p>These are explicit omissions, not claims hidden behind a green campaign status.</p>
            @for (gap of report.coverage.known_gaps; track gap.id) {
              <article>
                <span>Not covered</span>
                <h3>{{ gap.label }}</h3>
                <p>{{ gap.next_test }}</p>
              </article>
            }
          </aside>
        </section>
      }

      @if (section() === 'issues') {
        <section class="issues-layout">
          <div class="panel issues-list">
            <header class="panel-heading">
              <div>
                <span>Measured evidence only</span>
                <h2>Promotion and test-health queue</h2>
              </div>
            </header>
            <div class="filter-row">
              @for (filterItem of filters; track filterItem.id) {
                <button
                  type="button"
                  [class.active]="filter() === filterItem.id"
                  (click)="setFilter(filterItem.id)"
                >
                  {{ filterItem.label }}
                </button>
              }
            </div>
            @for (issue of filteredIssues(); track issue.id) {
              <button
                class="issue-card"
                type="button"
                [class.selected]="selectedIssue().id === issue.id"
                (click)="selectedIssue.set(issue)"
              >
                <span class="severity" [class.high]="issue.severity === 'high'"></span>
                <span
                  ><small>{{ issue.id }} · {{ issue.component }}</small
                  ><strong>{{ issue.title }}</strong>
                  <p>{{ issue.evidence }}</p></span
                >
                <b>{{ stateLabel(issue.state) }}</b>
              </button>
            }
          </div>
          <aside class="panel issue-detail">
            <header>
              <span>{{ selectedIssue().id }}</span
              ><b>{{ stateLabel(selectedIssue().state) }}</b>
            </header>
            <h2>{{ selectedIssue().title }}</h2>
            <dl>
              <div>
                <dt>Component</dt>
                <dd>{{ selectedIssue().component }}</dd>
              </div>
              <div>
                <dt>Measured evidence</dt>
                <dd>{{ selectedIssue().evidence }}</dd>
              </div>
              <div>
                <dt>Next action</dt>
                <dd>{{ selectedIssue().next_action }}</dd>
              </div>
              <div>
                <dt>Source record</dt>
                <dd>
                  <code>{{ selectedIssue().source }}</code>
                </dd>
              </div>
            </dl>
            @if (selectedIssue().failed_gates.length > 0) {
              <div class="failed-gates">
                <span>Failed gates</span>
                @for (gate of selectedIssue().failed_gates; track gate) {
                  <code>{{ humanize(gate) }}</code>
                }
              </div>
            } @else {
              <div class="pending-note">
                No gate is marked failed. Promotion waits on external TensorRT evidence.
              </div>
            }
          </aside>
        </section>
      }

      <footer class="claim-boundary">
        <strong>Evidence boundary</strong><span>{{ report.claim_boundary }}</span>
      </footer>
    </main>
  `,
  styles: `
    :host {
      display: block;
      min-height: calc(100dvh - 64px);
      background: #07131b;
      color: #e7f1f4;
      font-family:
        Inter,
        ui-sans-serif,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        'Segoe UI',
        sans-serif;
    }
    .ops-shell {
      max-width: 1600px;
      margin: 0 auto;
      padding: 28px 32px 22px;
    }
    .ops-commandbar {
      display: flex;
      justify-content: space-between;
      gap: 32px;
      align-items: flex-end;
      padding: 4px 2px 24px;
    }
    .eyebrow,
    .panel-heading span,
    .coverage-contract > span {
      color: #64dbe7;
      font:
        600 11px/1.2 ui-monospace,
        SFMono-Regular,
        Menlo,
        monospace;
      letter-spacing: 0.09em;
      text-transform: uppercase;
    }
    .ops-commandbar h1 {
      font-size: 28px;
      line-height: 1.15;
      margin: 7px 0 8px;
      letter-spacing: -0.025em;
    }
    .ops-commandbar p {
      margin: 0;
      color: #91a8b2;
      font-size: 14px;
    }
    .ops-actions {
      display: flex;
      gap: 12px;
      align-items: center;
    }
    .ops-actions button,
    .panel-heading button {
      border: 1px solid #287985;
      background: #0b2730;
      color: #d9f9fb;
      border-radius: 6px;
      padding: 10px 14px;
      font-weight: 650;
      cursor: pointer;
    }
    .data-boundary {
      border: 1px solid #193541;
      background: #091b24;
      color: #9db3bb;
      border-radius: 6px;
      padding: 9px 12px;
      font-size: 12px;
    }
    .data-boundary i,
    .status-label i,
    .panel-heading b i,
    .stage-measure span i {
      display: inline-block;
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #46d9a0;
      margin-right: 7px;
      box-shadow: 0 0 0 3px #123a35;
    }
    .ops-tabs {
      height: 43px;
      border: 1px solid #18333e;
      background: #091922;
      display: flex;
      align-items: stretch;
      border-radius: 7px 7px 0 0;
    }
    .ops-tabs button {
      color: #8299a3;
      background: transparent;
      border: 0;
      border-right: 1px solid #18333e;
      padding: 0 19px;
      font-weight: 650;
      cursor: pointer;
    }
    .ops-tabs button.active {
      color: #eaf9fa;
      background: #0d2630;
      box-shadow: inset 0 -2px #43cddd;
    }
    .ops-tabs button span {
      margin-left: 7px;
      background: #213944;
      padding: 2px 6px;
      border-radius: 9px;
      font:
        600 10px/1 ui-monospace,
        monospace;
    }
    .ops-tabs small {
      margin-left: auto;
      align-self: center;
      margin-right: 15px;
      color: #58717b;
      font:
        11px ui-monospace,
        monospace;
    }
    .status-strip {
      display: grid;
      grid-template-columns: 1.25fr repeat(4, 1fr);
      border: 1px solid #18333e;
      border-top: 0;
      background: #091922;
    }
    .status-strip > div {
      padding: 20px;
      border-right: 1px solid #18333e;
    }
    .status-strip > div:last-child {
      border: 0;
    }
    .status-strip span {
      display: block;
      color: #738d98;
      font-size: 11px;
    }
    .status-strip strong {
      display: block;
      font-size: 26px;
      margin: 7px 0 2px;
      letter-spacing: -0.035em;
    }
    .status-strip small {
      color: #718995;
      font-size: 11px;
    }
    .status-strip .status-label {
      color: #6ce0ad;
      text-transform: uppercase;
      font:
        650 10px ui-monospace,
        monospace;
    }
    .status-strip .status-label.degraded,
    .stage-measure span.degraded,
    .slo-row .fail {
      color: #ff776c;
    }
    .status-strip .neutral {
      color: #aabcc3;
    }
    .attention-status strong {
      color: #ffc66e;
    }
    .ops-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.4fr) minmax(420px, 1fr);
      gap: 14px;
      margin-top: 14px;
    }
    .panel {
      background: #091922;
      border: 1px solid #18333e;
      border-radius: 7px;
      overflow: hidden;
    }
    .panel-heading {
      min-height: 63px;
      padding: 0 17px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid #18333e;
    }
    .panel-heading h2 {
      font-size: 15px;
      margin: 4px 0 0;
    }
    .panel-heading b {
      font-size: 11px;
      color: #8eb2b7;
      font-weight: 600;
    }
    .stage-list {
      list-style: none;
      margin: 0;
      padding: 0;
    }
    .stage-list li {
      display: grid;
      grid-template-columns: 42px minmax(0, 1fr) 190px;
      gap: 12px;
      align-items: center;
      padding: 14px 17px;
      border-bottom: 1px solid #132d37;
    }
    .stage-list li:last-child {
      border: 0;
    }
    .stage-index {
      color: #506a75;
      font:
        12px ui-monospace,
        monospace;
    }
    .stage-copy strong,
    .stage-copy span,
    .stage-measure b,
    .stage-measure span {
      display: block;
    }
    .stage-copy strong {
      font-size: 13px;
      margin-bottom: 4px;
    }
    .stage-copy span {
      color: #718995;
      font-size: 11px;
    }
    .stage-measure {
      text-align: right;
    }
    .stage-measure b {
      font-size: 11px;
      color: #b9cbd1;
    }
    .stage-measure span {
      color: #5fdca8;
      font:
        600 10px ui-monospace,
        monospace;
      margin-top: 5px;
      text-transform: uppercase;
    }
    .slo-table {
      font-size: 11px;
    }
    .slo-row {
      display: grid;
      grid-template-columns: minmax(150px, 1.4fr) 0.7fr 0.9fr 48px;
      align-items: center;
      gap: 12px;
      padding: 10px 14px;
      border-bottom: 1px solid #132d37;
      color: #afc0c6;
    }
    .slo-row:last-child {
      border: 0;
    }
    .slo-row.head {
      color: #57717c;
      text-transform: uppercase;
      font:
        10px ui-monospace,
        monospace;
    }
    .slo-row strong,
    .slo-row small {
      display: block;
    }
    .slo-row strong {
      font-size: 11px;
      color: #d8e5e8;
    }
    .slo-row small {
      color: #59717b;
      margin-top: 3px;
    }
    .slo-row .pass {
      color: #5ee0a8;
      font:
        650 10px ui-monospace,
        monospace;
      text-transform: uppercase;
    }
    .slo-row .fail {
      font:
        650 10px ui-monospace,
        monospace;
      text-transform: uppercase;
    }
    .issue-preview {
      grid-column: 1/-1;
    }
    .issue-row {
      width: 100%;
      display: grid;
      grid-template-columns: 8px minmax(0, 1fr) 230px 18px;
      gap: 12px;
      align-items: center;
      text-align: left;
      background: transparent;
      border: 0;
      border-bottom: 1px solid #132d37;
      color: #dce8eb;
      padding: 13px 16px;
      cursor: pointer;
    }
    .issue-row:hover,
    .issue-card:hover {
      background: #0c222c;
    }
    .issue-row > span strong,
    .issue-row > span small {
      display: block;
    }
    .issue-row small {
      font:
        10px ui-monospace,
        monospace;
      color: #718995;
      margin-bottom: 4px;
    }
    .issue-row strong {
      font-size: 12px;
    }
    .issue-row b {
      font-size: 11px;
      color: #869da6;
      font-weight: 500;
    }
    .severity {
      width: 6px;
      height: 22px;
      border-radius: 3px;
      background: #e6ae57;
    }
    .severity.high {
      background: #f06f62;
    }
    .coverage-layout,
    .issues-layout {
      display: grid;
      grid-template-columns: minmax(0, 1.55fr) minmax(340px, 0.7fr);
      gap: 14px;
      margin-top: 14px;
    }
    .coverage-facts {
      display: grid;
      grid-template-columns: 2fr repeat(3, 1fr);
      border-bottom: 1px solid #18333e;
    }
    .coverage-facts > div {
      padding: 20px;
      border-right: 1px solid #18333e;
    }
    .coverage-facts span,
    .coverage-facts strong,
    .coverage-facts small {
      display: block;
    }
    .coverage-facts span {
      font-size: 10px;
      text-transform: uppercase;
      color: #64808a;
    }
    .coverage-facts strong {
      font-size: 18px;
      margin: 8px 0 4px;
    }
    .coverage-facts small {
      font-size: 10px;
      color: #6d858f;
    }
    .coverage-contract {
      display: flex;
      gap: 8px;
      align-items: center;
      padding: 13px 18px;
      border-bottom: 1px solid #18333e;
    }
    .coverage-contract > span {
      margin-right: auto;
    }
    .coverage-contract b {
      font:
        500 11px ui-monospace,
        monospace;
      color: #9bb0b7;
      border: 1px solid #21404b;
      border-radius: 4px;
      padding: 6px 8px;
    }
    .fault-verification {
      border-bottom: 1px solid #18333e;
      background: #0a1e27;
      padding: 17px 18px;
    }
    .fault-verification header,
    .protocol-heading,
    .protocol-facts {
      display: flex;
      justify-content: space-between;
      gap: 18px;
    }
    .fault-verification header span {
      color: #64dbe7;
      font:
        600 10px ui-monospace,
        monospace;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .fault-verification h3 {
      margin: 4px 0 0;
      font-size: 14px;
    }
    .fault-verification header b {
      color: #5ee0a8;
      font:
        650 10px ui-monospace,
        monospace;
      text-transform: uppercase;
    }
    .protocol-heading {
      align-items: center;
      margin-top: 17px;
      padding-top: 2px;
    }
    .protocol-heading.secondary {
      border-top: 1px solid #18333e;
      margin-top: 18px;
      padding-top: 16px;
    }
    .protocol-heading strong {
      color: #a9c0c7;
      font:
        600 11px ui-monospace,
        monospace;
      text-transform: uppercase;
    }
    .protocol-heading b {
      color: #5ee0a8;
      font:
        650 10px ui-monospace,
        monospace;
    }
    .protocol-facts {
      margin-top: 10px;
    }
    .protocol-facts p {
      flex: 1;
      margin: 0;
    }
    .protocol-facts p span,
    .protocol-facts p strong,
    .protocol-facts p small {
      display: block;
    }
    .protocol-facts p span {
      color: #607b86;
      font-size: 10px;
      text-transform: uppercase;
    }
    .protocol-facts p strong {
      margin: 6px 0 4px;
      color: #dce8eb;
      font-size: 12px;
    }
    .protocol-facts p small {
      color: #708993;
      font-size: 10px;
    }
    .method-comparison {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 28px;
      padding: 23px;
    }
    .method-comparison span,
    .method-comparison strong,
    .method-comparison small {
      display: block;
    }
    .method-comparison span {
      color: #6b8791;
      font:
        600 10px ui-monospace,
        monospace;
      text-transform: uppercase;
    }
    .method-comparison strong {
      font-size: 18px;
      margin: 6px 0 10px;
    }
    .method-comparison > div > div {
      height: 4px;
      background: #142f39;
      border-radius: 4px;
      overflow: hidden;
    }
    .method-comparison i {
      display: block;
      height: 100%;
      background: #43cedc;
    }
    .method-comparison small {
      color: #78909a;
      margin-top: 7px;
      font-size: 10px;
    }
    .gap-panel > p {
      color: #8097a0;
      font-size: 12px;
      line-height: 1.55;
      margin: 16px;
    }
    .gap-panel article {
      padding: 16px;
      border-top: 1px solid #18333e;
    }
    .gap-panel article span {
      color: #f0b863;
      font:
        650 10px ui-monospace,
        monospace;
      text-transform: uppercase;
    }
    .gap-panel h3 {
      font-size: 13px;
      margin: 6px 0;
    }
    .gap-panel article p {
      color: #8299a2;
      font-size: 11px;
      line-height: 1.5;
      margin: 0;
    }
    .issues-list .filter-row {
      display: flex;
      gap: 7px;
      padding: 11px 14px;
      border-bottom: 1px solid #18333e;
    }
    .filter-row button {
      border: 1px solid #1d3a46;
      background: #0a1c25;
      color: #78919b;
      border-radius: 5px;
      padding: 6px 10px;
      font-size: 10px;
      cursor: pointer;
    }
    .filter-row button.active {
      border-color: #3bc6d4;
      color: #d9fbfd;
      background: #0c2b34;
    }
    .issue-card {
      width: 100%;
      display: grid;
      grid-template-columns: 7px minmax(0, 1fr) 110px;
      gap: 14px;
      text-align: left;
      padding: 15px;
      background: transparent;
      border: 0;
      border-bottom: 1px solid #18333e;
      color: #dce7ea;
      cursor: pointer;
    }
    .issue-card.selected {
      background: #0d2731;
      box-shadow: inset 2px 0 #41ccda;
    }
    .issue-card small,
    .issue-card strong {
      display: block;
    }
    .issue-card small {
      color: #6b848f;
      font:
        10px ui-monospace,
        monospace;
      margin-bottom: 5px;
    }
    .issue-card strong {
      font-size: 12px;
    }
    .issue-card p {
      color: #7d949d;
      font-size: 11px;
      margin: 6px 0 0;
    }
    .issue-card > b {
      color: #dbb469;
      font:
        650 9px ui-monospace,
        monospace;
      text-transform: uppercase;
      text-align: right;
    }
    .issue-detail {
      padding: 20px;
      align-self: start;
    }
    .issue-detail header {
      display: flex;
      justify-content: space-between;
      color: #6d8791;
      font:
        10px ui-monospace,
        monospace;
      text-transform: uppercase;
    }
    .issue-detail header b {
      color: #e5b768;
    }
    .issue-detail h2 {
      font-size: 19px;
      line-height: 1.3;
      margin: 18px 0 22px;
    }
    .issue-detail dl {
      margin: 0;
    }
    .issue-detail dl div {
      border-top: 1px solid #19343e;
      padding: 13px 0;
    }
    .issue-detail dt {
      color: #607b86;
      font-size: 10px;
      text-transform: uppercase;
      margin-bottom: 5px;
    }
    .issue-detail dd {
      margin: 0;
      color: #aebfc5;
      font-size: 12px;
      line-height: 1.5;
    }
    .issue-detail code,
    .failed-gates code {
      font:
        10px ui-monospace,
        monospace;
      color: #8edbe1;
    }
    .failed-gates {
      border-top: 1px solid #19343e;
      padding-top: 14px;
    }
    .failed-gates span {
      display: block;
      color: #607b86;
      font-size: 10px;
      text-transform: uppercase;
      margin-bottom: 8px;
    }
    .failed-gates code {
      display: block;
      background: #0d232c;
      border: 1px solid #1c3b46;
      border-radius: 4px;
      padding: 7px;
      margin: 5px 0;
    }
    .pending-note {
      background: #1c211c;
      border: 1px solid #4a4932;
      color: #c8bd83;
      border-radius: 5px;
      padding: 12px;
      font-size: 11px;
      line-height: 1.5;
    }
    .claim-boundary {
      display: flex;
      gap: 16px;
      margin-top: 14px;
      padding: 12px 15px;
      border: 1px solid #16313c;
      border-radius: 6px;
      color: #617b86;
      font-size: 10px;
    }
    .claim-boundary strong {
      color: #8aa0a8;
      white-space: nowrap;
      text-transform: uppercase;
    }
    @media (max-width: 1000px) {
      .ops-grid,
      .coverage-layout,
      .issues-layout {
        grid-template-columns: 1fr;
      }
      .status-strip {
        grid-template-columns: repeat(2, 1fr);
      }
      .status-strip > div {
        border-bottom: 1px solid #18333e;
      }
      .coverage-facts {
        grid-template-columns: repeat(2, 1fr);
      }
    }
    @media (max-width: 680px) {
      .ops-shell {
        padding: 16px 12px;
      }
      .ops-commandbar {
        align-items: flex-start;
        flex-direction: column;
      }
      .ops-actions {
        width: 100%;
        flex-wrap: wrap;
      }
      .ops-tabs small {
        display: none;
      }
      .status-strip {
        grid-template-columns: 1fr;
      }
      .stage-list li {
        grid-template-columns: 32px minmax(0, 1fr);
      }
      .stage-measure {
        grid-column: 2;
        text-align: left;
      }
      .slo-row {
        grid-template-columns: 1.5fr 0.8fr 50px;
      }
      .slo-row > *:nth-child(2) {
        display: none;
      }
      .coverage-facts,
      .method-comparison {
        grid-template-columns: 1fr;
      }
      .coverage-contract {
        align-items: flex-start;
        flex-direction: column;
      }
      .fault-verification header,
      .protocol-heading,
      .protocol-facts {
        align-items: flex-start;
        flex-direction: column;
      }
      .issue-row {
        grid-template-columns: 7px minmax(0, 1fr) 18px;
      }
      .issue-row > b {
        display: none;
      }
      .claim-boundary {
        flex-direction: column;
        gap: 6px;
      }
    }
  `,
})
export class OperationsWorkspace {
  readonly openScenarioLab = output<void>();
  protected readonly report = TEST_OPERATIONS;
  protected readonly section = signal<OperationsSection>('overview');
  protected readonly filter = signal<IssueFilter>('all');
  protected readonly selectedIssue = signal<TestOperationIssue>(TEST_OPERATIONS.issues[0]);
  protected readonly sections: readonly { id: OperationsSection; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'coverage', label: 'Coverage' },
    { id: 'issues', label: 'Issues' },
  ];
  protected readonly filters: readonly { id: IssueFilter; label: string }[] = [
    { id: 'all', label: 'All decisions' },
    { id: 'active', label: 'Active alerts' },
    { id: 'blocked', label: 'Blocked' },
    { id: 'pending_evidence', label: 'Pending evidence' },
  ];
  protected readonly filteredIssues = computed(() =>
    this.filter() === 'all'
      ? this.report.issues
      : this.report.issues.filter((issue) => issue.state === this.filter()),
  );
  protected readonly methods = computed(() =>
    Object.entries(this.report.coverage.methods).map(([name, value]) => ({ name, value })),
  );
  protected readonly healthyStageCount = computed(
    () => this.report.pipeline_stages.filter((stage) => stage.status === 'healthy').length,
  );
  protected openIssue(issue: TestOperationIssue): void {
    this.selectedIssue.set(issue);
    this.filter.set('all');
    this.section.set('issues');
  }
  protected setFilter(filter: IssueFilter): void {
    this.filter.set(filter);
    const firstVisible = this.filteredIssues()[0];
    if (firstVisible) this.selectedIssue.set(firstVisible);
  }
  protected shortSeal(): string {
    return `${this.report.report_sha256.slice(0, 8)}…${this.report.report_sha256.slice(-6)}`;
  }
  protected compact(value: number): string {
    return Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 2 }).format(value);
  }
  protected stateLabel(value: TestOperationIssue['state']): string {
    return value.replaceAll('_', ' ');
  }
  protected humanize(value: string): string {
    return (
      {
        fp16_max_error_under_7_5e_2_m: 'FP16 max drift under 0.075 m',
        budget_8_advantage_at_least_0_25_m: 'Budget-8 advantage at least 0.25 m',
        budget_8_wins_at_least_7_scenarios: 'Budget-8 wins in at least 7 scenarios',
        coverage_between_0_75_and_0_98: 'Calibration coverage between 0.75 and 0.98',
        mean_spearman_at_least_0_25: 'Mean Spearman correlation at least 0.25',
      }[value] ?? value.replaceAll('_', ' ')
    );
  }
}
