import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  output,
  signal,
} from '@angular/core';
import { TEST_OPERATIONS, TestOperationIssue, TestSuiteHealth } from '../test-operations';
import { LiveTestHealth } from './live-test-health';
import { LocalEvidenceService } from '../local-evidence.service';

type OperationsSection = 'health' | 'coverage' | 'triage';
type IssueFilter = 'all' | 'blocked' | 'stopped' | 'pending_evidence';

function initialOperationsSection(): OperationsSection {
  const requested = new URLSearchParams(window.location.search).get('section');
  if (requested === 'coverage') return 'coverage';
  if (requested === 'triage' || requested === 'issues') return 'triage';
  return 'health';
}

@Component({
  selector: 'app-operations-workspace',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LiveTestHealth],
  template: `
    <nav class="health-source" aria-label="Test-health source">
      <button type="button" [attr.aria-pressed]="liveSource()" (click)="liveSource.set(true)">
        Live local runs
      </button>
      <button type="button" [attr.aria-pressed]="!liveSource()" (click)="liveSource.set(false)">
        Saved campaign
      </button>
    </nav>
    @if (liveSource()) {
      <div class="live-source">
        <app-live-test-health (inspectRequested)="openExperiments.emit()" />
        <button type="button" class="primary-action" (click)="openExperiments.emit()">
          Configure a behavior test
        </button>
      </div>
    } @else {
      <main class="ops-workstation">
        <header class="runbar">
          <div class="run-context">
            <span>Saved verification report / {{ report.coverage.plan_version }}</span>
            <strong>Test health</strong>
            <small>Campaign {{ report.campaign.campaign_id }} · report {{ shortSeal() }}</small>
          </div>
          <p class="snapshot-note">
            Saved checks from a completed run.<br />Not live pipeline monitoring.
          </p>
          <button type="button" class="primary-action" (click)="openScenarioLab.emit()">
            Review scenario changes
          </button>
        </header>

        <div class="workstation-grid" [class.health-layout]="section() === 'health'">
          <aside class="suite-rail" aria-label="Test suite registry">
            <header class="rail-heading">
              <span>Test registry</span>
              <b>{{ report.test_inventory.tracked_suites }} suites</b>
            </header>
            <div class="registry-summary">
              <strong>Completed campaign</strong>
              <span>{{ report.campaign.campaign_id }}</span>
              <small>Real WOMD · sealed run</small>
            </div>
            <nav aria-label="Tracked test suites">
              @for (suite of report.test_inventory.suites; track suite.id) {
                <button
                  type="button"
                  [class.selected]="selectedSuite().id === suite.id"
                  (click)="selectSuite(suite)"
                >
                  <span class="suite-state"><i></i>{{ suite.status }}</span>
                  <strong>{{ suite.name }}</strong>
                  <small>{{ suite.plan_version }} · {{ suite.scenario_count }} scenarios</small>
                </button>
              }
            </nav>
            <footer>
              <span>Source boundary</span>
              <p>Research test evidence only. No fleet-health telemetry.</p>
            </footer>
          </aside>

          <section class="review-surface">
            <header class="review-toolbar">
              <div>
                <span>Simulation test operations</span>
                <strong>{{ sectionTitle() }}</strong>
              </div>
              <nav class="ops-tabs" aria-label="Campaign views">
                @for (item of sections; track item.id) {
                  <button
                    type="button"
                    [class.active]="section() === item.id"
                    (click)="section.set(item.id)"
                  >
                    {{ item.label }}
                    @if (item.id === 'triage') {
                      <span>{{ report.issues.length }}</span>
                    }
                  </button>
                }
              </nav>
            </header>

            @if (section() === 'health') {
              <div class="health-workspace">
                <section class="health-summary" aria-labelledby="health-title">
                  <div>
                    <span class="eyebrow">Execution verification</span>
                    <h1 id="health-title">The saved test run passed its checks.</h1>
                    <button type="button" class="secondary-action" (click)="openExperiments.emit()">
                      View live local experiments
                    </button>
                    <p>
                      The checks below validate execution and evidence integrity, not planner
                      safety. This report covers 100 search runs and 20 fault/handoff cases across
                      the same ten recorded scenarios.
                    </p>
                  </div>
                  <div class="health-kpis" aria-label="Release health summary">
                    <article>
                      <strong
                        >{{ report.test_inventory.passing_release_critical_cells }}/{{
                          report.test_inventory.release_critical_cells
                        }}</strong
                      >
                      <span>test cells</span>
                    </article>
                    <article>
                      <strong
                        >{{ report.slo_summary.passing }}/{{ report.slo_summary.total }}</strong
                      >
                      <span>checks passed</span>
                    </article>
                    <article>
                      <strong>{{ report.test_inventory.active_health_alerts }}</strong>
                      <span>run-health alerts</span>
                    </article>
                  </div>
                </section>

                <section class="stage-panel" aria-labelledby="pipeline-health-title">
                  <header>
                    <div>
                      <span class="eyebrow">Automated health checks</span>
                      <h2 id="pipeline-health-title">Pipeline stages</h2>
                    </div>
                    <b>{{ healthyStageCount() }}/{{ report.pipeline_stages.length }} healthy</b>
                  </header>
                  <div class="stage-table" role="table" aria-label="Pipeline stage health">
                    @for (stage of report.pipeline_stages; track stage.id; let index = $index) {
                      <div role="row">
                        <span role="cell" class="stage-order">{{ index + 1 }}</span>
                        <span role="cell" class="stage-name">
                          <strong>{{ stage.name }}</strong>
                          <small>{{ stage.detail }}</small>
                        </span>
                        <span role="cell" class="stage-observed">{{ stage.observed }}</span>
                        <span role="cell" class="healthy-label"><i></i>{{ stage.status }}</span>
                      </div>
                    }
                  </div>
                </section>

                <section class="attention-panel" aria-labelledby="attention-title">
                  <header>
                    <div>
                      <span class="eyebrow">Engineering attention</span>
                      <h2 id="attention-title">Held decisions</h2>
                    </div>
                    <button type="button" (click)="section.set('triage')">Open triage</button>
                  </header>
                  <div class="attention-list">
                    @for (issue of report.issues; track issue.id) {
                      <button type="button" (click)="openIssue(issue)">
                        <span class="severity" [class.high]="issue.severity === 'high'"></span>
                        <span>
                          <small>{{ issue.id }} · {{ issue.diagnostic.owner }}</small>
                          <strong>{{ issue.title }}</strong>
                        </span>
                        <b>{{ stateLabel(issue.state) }}</b>
                      </button>
                    }
                  </div>
                </section>
              </div>
            }

            @if (section() === 'coverage') {
              <div class="coverage-workspace">
                <header class="coverage-intro">
                  <div>
                    <span class="eyebrow">Versioned verification plans</span>
                    <h1>Coverage that can be regenerated and reviewed.</h1>
                  </div>
                  <p>
                    Every row is computed from sealed real-data artifacts and carries an explicit
                    plan version, scenario population, and gate result.
                  </p>
                </header>
                <section class="coverage-table" aria-label="Versioned behavior coverage">
                  <header>
                    <span>Test plan</span><span>Version</span><span>Scenarios</span
                    ><span>Gates</span><span>Status</span>
                  </header>
                  @for (plan of report.coverage.versioned_plans; track plan.id) {
                    <button type="button" (click)="selectPlan(plan.id)">
                      <span>
                        <strong>{{ suiteFor(plan.id).name }}</strong>
                        <small>{{ humanize(plan.scenario_family) }}</small>
                      </span>
                      <code>{{ plan.plan_version }}</code>
                      <span>{{ plan.scenario_count }}</span>
                      <span>{{ plan.gate_passes }}/{{ plan.gate_total }}</span>
                      <b><i></i>{{ plan.status }}</b>
                    </button>
                  }
                </section>
                <div class="coverage-gaps" aria-label="Known coverage gaps">
                  @for (gap of report.coverage.known_gaps; track gap.id) {
                    <section class="coverage-gap">
                      <span class="eyebrow">Known gap</span>
                      <div>
                        <strong>{{ gap.label }}</strong>
                        <p>{{ gap.next_test }}</p>
                      </div>
                      <b>Not covered</b>
                    </section>
                  }
                </div>
              </div>
            }

            @if (section() === 'triage') {
              <div class="triage-workspace">
                <header class="triage-header">
                  <div>
                    <span class="eyebrow">Measured decisions</span>
                    <h1>Investigate before changing the release path.</h1>
                  </div>
                  <div class="filter-row" aria-label="Issue filters">
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
                </header>
                <section class="issue-list" aria-label="Triage queue">
                  @for (issue of filteredIssues(); track issue.id) {
                    <button
                      type="button"
                      class="issue-row"
                      [class.selected]="selectedIssue().id === issue.id"
                      (click)="selectedIssue.set(issue)"
                    >
                      <span class="severity" [class.high]="issue.severity === 'high'"></span>
                      <span class="issue-copy">
                        <small>{{ issue.id }} · {{ issue.component }}</small>
                        <strong>{{ issue.title }}</strong>
                        <p>{{ issue.diagnostic.impact }}</p>
                      </span>
                      <span class="issue-owner">
                        <small>Owner</small>
                        <strong>{{ issue.diagnostic.owner }}</strong>
                      </span>
                      <b>{{ stateLabel(issue.state) }}</b>
                    </button>
                  }
                </section>
              </div>
            }
          </section>

          @if (section() !== 'health') {
            <aside class="context-inspector" aria-label="Release evidence inspector">
              @if (section() === 'coverage') {
                <header><span>Coverage inspector</span><b>VERSIONED</b></header>
                <section class="verdict">
                  <span class="status"><i></i>{{ selectedSuite().status }}</span>
                  <h2>{{ selectedSuite().name }}</h2>
                  <p>
                    {{ selectedSuite().scenario_count }} real-data scenarios on
                    {{ selectedSuite().platform }}.
                  </p>
                </section>
                <section class="inspector-block suite-inspector">
                  <span>Verification contract</span>
                  <dl>
                    <div>
                      <dt>Version</dt>
                      <dd>{{ selectedSuite().plan_version }}</dd>
                    </div>
                    <div>
                      <dt>Test cells</dt>
                      <dd>{{ selectedSuite().test_cell_count }}</dd>
                    </div>
                    <div>
                      <dt>Executions</dt>
                      <dd>{{ selectedSuite().execution_count.toLocaleString() }}</dd>
                    </div>
                    <div>
                      <dt>Unit</dt>
                      <dd>{{ selectedSuite().execution_unit }}</dd>
                    </div>
                    <div>
                      <dt>Gates</dt>
                      <dd>{{ selectedSuite().gate_passes }}/{{ selectedSuite().gate_total }}</dd>
                    </div>
                  </dl>
                </section>
              } @else {
                <header>
                  <span>Diagnostic</span><b>{{ selectedIssue().id }}</b>
                </header>
                <section class="verdict issue-verdict">
                  <span class="issue-state">{{ stateLabel(selectedIssue().state) }}</span>
                  <h2>{{ selectedIssue().title }}</h2>
                  <p>{{ selectedIssue().diagnostic.impact }}</p>
                </section>
                <section class="inspector-block">
                  <span>Detected by</span>
                  <strong>{{ selectedIssue().diagnostic.detected_by }}</strong>
                  <small>Owner · {{ selectedIssue().diagnostic.owner }}</small>
                </section>
                <section class="root-cause" aria-label="Root cause path">
                  <span>Isolation path</span>
                  <ol>
                    @for (
                      step of selectedIssue().diagnostic.root_cause_path;
                      track step;
                      let index = $index
                    ) {
                      <li>
                        <b>{{ index + 1 }}</b
                        ><span>{{ step }}</span>
                      </li>
                    }
                  </ol>
                </section>
                <section class="inspector-block action-block">
                  <span>Resolution</span>
                  <strong>{{ selectedIssue().diagnostic.resolution }}</strong>
                  <button
                    type="button"
                    class="secondary-action"
                    (click)="openModelStudy.emit(issueStudy())"
                  >
                    Inspect model evidence
                  </button>
                </section>
                <details class="release-contract prevention">
                  <summary>Prevention</summary>
                  <p>{{ selectedIssue().diagnostic.prevention }}</p>
                  <code>{{ selectedIssue().source }}</code>
                </details>
              }
              <footer>
                <strong>Evidence boundary</strong>
                <p>{{ report.claim_boundary }}</p>
              </footer>
            </aside>
          }
        </div>
      </main>
    }
  `,
  styles: `
    .health-source {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding: 18px 24px 0;
      background: #f4f6f3;
    }
    .health-source button {
      border: 1px solid #cbd8d1;
      border-radius: 999px;
      padding: 10px 18px;
      background: white;
      color: #31564a;
      cursor: pointer;
    }
    .health-source button[aria-pressed='true'] {
      background: #dff3e7;
      border-color: #83b99b;
      color: #124a34;
    }
    .health-source button:focus-visible {
      outline: 3px solid #1968fa;
      outline-offset: 3px;
    }
    .live-source {
      max-width: 1100px;
      padding: 24px;
      margin: auto;
      display: grid;
      gap: 20px;
    }
    :host {
      display: block;
      height: calc(100dvh - 72px);
      min-height: 720px;
      color: #141b2d;
      background: #f4f6f3;
      font-family:
        Inter,
        ui-sans-serif,
        -apple-system,
        BlinkMacSystemFont,
        'Segoe UI',
        sans-serif;
    }
    * {
      box-sizing: border-box;
    }
    button {
      font: inherit;
    }
    .secondary-action {
      margin-top: 12px;
      border: 1px solid #cddad3;
      border-radius: 7px;
      padding: 10px 14px;
      background: #fff;
      color: #174bb9;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
    }
    .secondary-action:hover {
      background: #eef3ff;
    }
    .secondary-action:focus-visible {
      outline: 3px solid #1b63ef;
      outline-offset: 3px;
    }
    .ops-workstation {
      display: grid;
      grid-template-rows: 94px minmax(0, 1fr);
      height: 100%;
    }
    .runbar {
      display: grid;
      grid-template-columns: minmax(280px, 1fr) auto auto;
      align-items: center;
      gap: 22px;
      padding: 14px 22px 16px;
    }
    .run-context {
      display: grid;
      gap: 2px;
      min-width: 0;
    }
    .run-context > span,
    .eyebrow,
    .rail-heading span,
    .review-toolbar > div span,
    .context-inspector > header span,
    .inspector-block > span,
    .root-cause > span {
      color: #576471;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .run-context > strong {
      font-size: 25px;
      font-weight: 540;
      letter-spacing: -0.045em;
      text-transform: capitalize;
    }
    .run-context > small {
      color: #576471;
      font-size: 12px;
    }
    .run-state {
      display: flex;
      gap: 8px;
    }
    .run-state span {
      display: inline-flex;
      align-items: center;
      min-height: 32px;
      gap: 7px;
      padding: 0 12px;
      border-radius: 999px;
      background: #e8eee8;
      color: #3f4d47;
      font-size: 12px;
      font-weight: 650;
    }
    .run-state i,
    .healthy-label i,
    .status i,
    .coverage-table b i,
    .release-contract i,
    .suite-state i {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #24aa6b;
    }
    .primary-action {
      min-height: 42px;
      padding: 0 18px;
      border: 0;
      border-radius: 999px;
      background: #1769ff;
      color: #fff;
      font-size: 11px;
      font-weight: 750;
      box-shadow: 0 8px 22px rgb(23 105 255 / 18%);
    }
    .primary-action:hover {
      background: #0759e7;
    }
    .workstation-grid {
      display: grid;
      grid-template-columns: 220px minmax(560px, 1fr) 290px;
      gap: 14px;
      min-height: 0;
      padding: 0 14px 14px;
    }
    .workstation-grid.health-layout {
      grid-template-columns: 220px minmax(0, 1fr);
      max-width: 1420px;
      margin: auto;
    }
    .snapshot-note {
      font-size: 12px;
      line-height: 1.6;
      color: #607168;
      margin: 0;
    }
    @media (max-width: 650px) {
      .workstation-grid.health-layout {
        grid-template-columns: 1fr;
      }
      .snapshot-note {
        grid-column: 1 / -1;
        order: 3;
      }
    }
    .suite-rail,
    .review-surface,
    .context-inspector {
      min-width: 0;
      border: 1px solid #e0e5e1;
      border-radius: 20px;
      background: #fff;
      box-shadow: 0 8px 28px rgb(17 31 45 / 6%);
      overflow: hidden;
    }
    .suite-rail {
      display: grid;
      grid-template-rows: auto auto 1fr auto;
    }
    .rail-heading,
    .context-inspector > header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 48px;
      padding: 0 14px;
      border-bottom: 1px solid #edf0ed;
    }
    .rail-heading b,
    .context-inspector > header b {
      color: #59636f;
      font-size: 11px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .registry-summary {
      display: grid;
      gap: 3px;
      margin: 10px;
      padding: 13px;
      border-radius: 13px;
      background: #eef4ff;
    }
    .registry-summary strong {
      color: #1549a4;
      font-size: 12px;
    }
    .registry-summary span {
      color: #263044;
      font-size: 12px;
    }
    .registry-summary small {
      color: #576471;
      font-size: 11px;
    }
    .suite-rail nav {
      display: grid;
      align-content: start;
      gap: 4px;
      padding: 0 10px;
    }
    .suite-rail nav button {
      display: grid;
      gap: 3px;
      width: 100%;
      padding: 11px;
      border: 0;
      border-radius: 12px;
      background: transparent;
      color: #1c2435;
      text-align: left;
    }
    .suite-rail nav button:hover,
    .suite-rail nav button.selected {
      background: #f1f4f1;
    }
    .suite-state {
      display: flex;
      align-items: center;
      gap: 5px;
      color: #2a794e;
      font-size: 10px;
      font-weight: 750;
      text-transform: uppercase;
    }
    .suite-rail nav strong {
      font-size: 12px;
    }
    .suite-rail nav small {
      overflow: hidden;
      color: #576471;
      font-size: 11px;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .suite-rail footer,
    .context-inspector > footer {
      padding: 14px;
      border-top: 1px solid #edf0ed;
    }
    .suite-rail footer span,
    .context-inspector footer strong {
      color: #576471;
      font-size: 11px;
      font-weight: 750;
      text-transform: uppercase;
    }
    .suite-rail footer p,
    .context-inspector footer p {
      margin: 5px 0 0;
      color: #576471;
      font-size: 11px;
      line-height: 1.45;
    }
    .review-surface {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
    }
    .review-toolbar {
      display: flex;
      min-height: 58px;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 0 10px 0 18px;
      border-bottom: 1px solid #e7ebe7;
    }
    .review-toolbar > div {
      display: grid;
      gap: 2px;
    }
    .review-toolbar > div strong {
      font-size: 12px;
    }
    .ops-tabs {
      display: flex;
      gap: 3px;
      padding: 3px;
      border-radius: 999px;
      background: #f0f2ef;
    }
    .ops-tabs button {
      min-width: 72px;
      min-height: 32px;
      border: 0;
      border-radius: 999px;
      background: transparent;
      color: #576471;
      font-size: 12px;
      font-weight: 700;
    }
    .ops-tabs button.active {
      background: #fff;
      color: #164ca9;
      box-shadow: 0 2px 8px rgb(24 43 61 / 10%);
    }
    .ops-tabs button span {
      margin-left: 3px;
      padding: 2px 5px;
      border-radius: 999px;
      background: #dde8ff;
      color: #164ca9;
      font-size: 10px;
    }
    .health-workspace,
    .coverage-workspace,
    .triage-workspace {
      min-height: 0;
      overflow: auto;
    }
    .health-workspace {
      display: grid;
      align-content: start;
      gap: 12px;
      padding: 12px;
    }
    .health-summary {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 24px;
      padding: 22px;
      border: 1px solid #e4e9e4;
      border-radius: 16px;
      background: #f8faf7;
    }
    h1 {
      margin: 7px 0 6px;
      font-size: 23px;
      font-weight: 550;
      letter-spacing: -0.035em;
      line-height: 1.1;
    }
    .health-summary p,
    .coverage-intro p {
      max-width: 590px;
      margin: 0;
      color: #576471;
      font-size: 12px;
      line-height: 1.55;
    }
    .health-kpis {
      display: grid;
      grid-template-columns: repeat(3, 92px);
      align-items: stretch;
    }
    .health-kpis article {
      display: grid;
      align-content: center;
      gap: 3px;
      padding: 0 13px;
      border-left: 1px solid #e2e7e2;
    }
    .health-kpis strong {
      font-size: 20px;
      font-weight: 600;
      letter-spacing: -0.03em;
    }
    .health-kpis span {
      color: #576471;
      font-size: 10px;
      text-transform: uppercase;
    }
    .stage-panel,
    .attention-panel {
      border: 1px solid #e4e8e4;
      border-radius: 16px;
      overflow: hidden;
    }
    .stage-panel > header,
    .attention-panel > header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 58px;
      padding: 0 14px;
      border-bottom: 1px solid #e8ece8;
    }
    .stage-panel h2,
    .attention-panel h2 {
      margin: 3px 0 0;
      font-size: 13px;
    }
    .stage-panel > header b {
      color: #2d7b4f;
      font-size: 11px;
      text-transform: uppercase;
    }
    .stage-table > div {
      display: grid;
      grid-template-columns: 28px minmax(190px, 1fr) 150px 66px;
      align-items: center;
      min-height: 52px;
      gap: 10px;
      padding: 7px 13px;
      border-bottom: 1px solid #edf0ed;
    }
    .stage-table > div:last-child {
      border-bottom: 0;
    }
    .stage-order {
      display: grid;
      width: 20px;
      height: 20px;
      place-items: center;
      border-radius: 50%;
      background: #f0f3f0;
      color: #576471;
      font-size: 10px;
    }
    .stage-name {
      display: grid;
      gap: 2px;
    }
    .stage-name strong {
      font-size: 12px;
    }
    .stage-name small,
    .stage-observed {
      color: #576471;
      font-size: 11px;
    }
    .stage-observed {
      text-align: right;
    }
    .healthy-label {
      display: flex;
      align-items: center;
      gap: 6px;
      color: #2c7c50;
      font-size: 10px;
      font-weight: 750;
      text-transform: uppercase;
    }
    .attention-panel > header button {
      border: 0;
      background: transparent;
      color: #1769ff;
      font-size: 11px;
      font-weight: 750;
    }
    .attention-list {
      display: grid;
    }
    .attention-list button {
      display: grid;
      grid-template-columns: 5px minmax(0, 1fr) auto;
      align-items: center;
      gap: 10px;
      min-height: 54px;
      padding: 8px 13px;
      border: 0;
      border-bottom: 1px solid #edf0ed;
      background: #fff;
      color: #1b2334;
      text-align: left;
    }
    .attention-list button:hover {
      background: #f6f8f5;
    }
    .attention-list button:last-child {
      border-bottom: 0;
    }
    .attention-list button > span:nth-child(2) {
      display: grid;
      gap: 2px;
    }
    .attention-list small,
    .issue-copy small {
      color: #576471;
      font-size: 10px;
      text-transform: uppercase;
    }
    .attention-list strong {
      font-size: 12px;
    }
    .attention-list b,
    .issue-row > b {
      color: #805414;
      font-size: 10px;
      text-transform: uppercase;
    }
    .severity {
      width: 4px;
      height: 28px;
      border-radius: 999px;
      background: #e3ad45;
    }
    .severity.high {
      background: #ff6f61;
    }
    .coverage-workspace {
      padding: 12px;
    }
    .coverage-intro {
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      align-items: end;
      gap: 24px;
      padding: 20px 10px 22px;
    }
    .coverage-intro h1 {
      margin-bottom: 0;
    }
    .coverage-table {
      border: 1px solid #e2e7e2;
      border-radius: 16px;
      overflow: hidden;
    }
    .coverage-table > header,
    .coverage-table > button {
      display: grid;
      grid-template-columns: minmax(190px, 1fr) 135px 70px 85px 72px;
      align-items: center;
      gap: 10px;
      padding: 0 14px;
    }
    .coverage-table > header {
      min-height: 38px;
      background: #f5f7f4;
      color: #576471;
      font-size: 10px;
      font-weight: 750;
      text-transform: uppercase;
    }
    .coverage-table > button {
      width: 100%;
      min-height: 66px;
      border: 0;
      border-top: 1px solid #e8ece8;
      background: #fff;
      color: #20283a;
      text-align: left;
    }
    .coverage-table > button:hover {
      background: #f1f5ff;
    }
    .coverage-table button > span:first-child {
      display: grid;
      gap: 3px;
    }
    .coverage-table strong {
      font-size: 12px;
    }
    .coverage-table small {
      color: #576471;
      font-size: 10px;
      text-transform: capitalize;
    }
    .coverage-table code {
      color: #375b92;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 10px;
    }
    .coverage-table button > span {
      font-size: 11px;
    }
    .coverage-table b {
      display: flex;
      align-items: center;
      gap: 6px;
      color: #2d7b4f;
      font-size: 10px;
      text-transform: uppercase;
    }
    .coverage-gaps {
      display: grid;
      gap: 8px;
      margin-top: 12px;
    }
    .coverage-gap {
      display: grid;
      grid-template-columns: 90px minmax(0, 1fr) auto;
      align-items: center;
      gap: 16px;
      padding: 16px;
      border: 1px solid #f0dfbc;
      border-radius: 14px;
      background: #fff9ee;
    }
    .coverage-gap strong {
      font-size: 12px;
    }
    .coverage-gap p {
      margin: 3px 0 0;
      color: #7e7159;
      font-size: 11px;
    }
    .coverage-gap > b {
      color: #805414;
      font-size: 10px;
      text-transform: uppercase;
    }
    .triage-workspace {
      padding: 12px;
    }
    .triage-header {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 18px;
      padding: 8px 8px 18px;
    }
    .triage-header h1 {
      margin-bottom: 0;
    }
    .filter-row {
      display: flex;
      gap: 4px;
      padding: 3px;
      border-radius: 999px;
      background: #f0f2ef;
    }
    .filter-row button {
      min-height: 28px;
      padding: 0 9px;
      border: 0;
      border-radius: 999px;
      background: transparent;
      color: #576471;
      font-size: 10px;
      font-weight: 700;
    }
    .filter-row button.active {
      background: #fff;
      color: #164ca9;
      box-shadow: 0 2px 7px rgb(24 43 61 / 9%);
    }
    .issue-list {
      border: 1px solid #e2e7e2;
      border-radius: 16px;
      overflow: hidden;
    }
    .issue-row {
      display: grid;
      grid-template-columns: 5px minmax(220px, 1fr) 130px 82px;
      align-items: center;
      gap: 12px;
      width: 100%;
      min-height: 82px;
      padding: 12px 14px;
      border: 0;
      border-bottom: 1px solid #e8ece8;
      background: #fff;
      color: #1c2435;
      text-align: left;
    }
    .issue-row:last-child {
      border-bottom: 0;
    }
    .issue-row:hover,
    .issue-row.selected {
      background: #f1f5ff;
    }
    .issue-copy {
      display: grid;
      gap: 4px;
    }
    .issue-copy strong {
      font-size: 11px;
    }
    .issue-copy p {
      margin: 0;
      color: #576471;
      font-size: 11px;
      line-height: 1.4;
    }
    .issue-owner {
      display: grid;
      gap: 3px;
    }
    .issue-owner small {
      color: #576471;
      font-size: 10px;
      text-transform: uppercase;
    }
    .issue-owner strong {
      color: #424c59;
      font-size: 11px;
    }
    .context-inspector {
      display: flex;
      flex-direction: column;
      overflow: auto;
    }
    .verdict,
    .inspector-block,
    .root-cause,
    .release-contract {
      margin: 0 14px;
      padding: 16px 0;
      border-bottom: 1px solid #edf0ed;
    }
    .status {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      min-height: 27px;
      padding: 0 10px;
      border-radius: 999px;
      background: #e2f5e9;
      color: #237447;
      font-size: 10px;
      font-weight: 750;
      text-transform: uppercase;
    }
    .verdict h2 {
      margin: 13px 0 7px;
      font-size: 22px;
      font-weight: 540;
      letter-spacing: -0.04em;
      line-height: 1.08;
    }
    .verdict p,
    .inspector-block p,
    .release-contract p {
      margin: 0;
      color: #576471;
      font-size: 12px;
      line-height: 1.5;
    }
    .suite-inspector > strong,
    .inspector-block > strong {
      display: block;
      margin-top: 7px;
      color: #20283a;
      font-size: 11px;
      line-height: 1.4;
    }
    .suite-inspector dl {
      margin: 10px 0 0;
    }
    .suite-inspector dl div {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 7px 0;
      border-top: 1px solid #edf0ed;
    }
    .suite-inspector dt {
      color: #576471;
      font-size: 10px;
      text-transform: uppercase;
    }
    .suite-inspector dd {
      margin: 0;
      color: #313a49;
      font-size: 11px;
      text-align: right;
    }
    .release-contract summary {
      display: flex;
      justify-content: space-between;
      color: #626c77;
      cursor: pointer;
      font-size: 11px;
      font-weight: 750;
      list-style: none;
      text-transform: uppercase;
    }
    .release-contract summary::-webkit-details-marker {
      display: none;
    }
    .release-contract > div {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      padding: 8px 0;
      border-top: 1px solid #edf0ed;
    }
    .release-contract > div:first-of-type {
      margin-top: 10px;
    }
    .release-contract > div span {
      display: flex;
      align-items: center;
      gap: 6px;
      color: #3d4754;
      font-size: 10px;
    }
    .release-contract > div small {
      color: #576471;
      font-size: 10px;
    }
    .issue-state {
      display: inline-flex;
      padding: 6px 9px;
      border-radius: 999px;
      background: #fff2dc;
      color: #94641c;
      font-size: 10px;
      font-weight: 750;
      text-transform: uppercase;
    }
    .inspector-block > small {
      display: block;
      margin-top: 6px;
      color: #576471;
      font-size: 11px;
    }
    .root-cause ol {
      display: grid;
      gap: 0;
      margin: 10px 0 0;
      padding: 0;
      list-style: none;
    }
    .root-cause li {
      display: grid;
      grid-template-columns: 22px 1fr;
      align-items: center;
      gap: 8px;
      min-height: 36px;
      position: relative;
    }
    .root-cause li:not(:last-child)::after {
      position: absolute;
      top: 26px;
      bottom: -10px;
      left: 9px;
      width: 1px;
      background: #dce2dd;
      content: '';
    }
    .root-cause li b {
      z-index: 1;
      display: grid;
      width: 19px;
      height: 19px;
      place-items: center;
      border-radius: 50%;
      background: #edf2ee;
      color: #5d6873;
      font-size: 10px;
    }
    .root-cause li span {
      color: #3d4754;
      font-size: 11px;
    }
    .action-block strong {
      color: #1549a4;
    }
    .prevention p {
      margin-top: 10px;
    }
    .prevention code {
      display: block;
      margin-top: 10px;
      overflow-wrap: anywhere;
      color: #576471;
      font-size: 10px;
    }
    .context-inspector > footer {
      margin-top: auto;
    }
    @media (max-width: 1180px) {
      .workstation-grid {
        grid-template-columns: 190px minmax(480px, 1fr) 250px;
      }
      .run-state span:last-child {
        display: none;
      }
      .health-kpis {
        grid-template-columns: repeat(3, 76px);
      }
      .stage-table > div {
        grid-template-columns: 28px minmax(170px, 1fr) 100px 60px;
      }
    }
    @media (max-width: 900px) {
      :host {
        height: auto;
      }
      .ops-workstation {
        min-height: calc(100dvh - 72px);
      }
      .runbar {
        grid-template-columns: 1fr auto;
      }
      .run-state {
        display: none;
      }
      .workstation-grid {
        grid-template-columns: 180px minmax(0, 1fr);
      }
      .context-inspector {
        grid-column: 1 / -1;
      }
      .review-surface {
        min-height: 610px;
      }
    }
    @media (max-width: 650px) {
      :host {
        min-height: 0;
      }
      .ops-workstation {
        grid-template-rows: auto auto;
      }
      .runbar {
        grid-template-columns: 1fr;
        padding: 12px;
      }
      .primary-action {
        display: none;
      }
      .workstation-grid {
        grid-template-columns: 1fr;
        padding: 0 8px 8px;
      }
      .suite-rail {
        display: none;
      }
      .review-toolbar {
        position: static;
        align-items: stretch;
        flex-direction: column;
        padding: 10px;
        background: #fff;
      }
      .ops-tabs {
        align-self: stretch;
      }
      .ops-tabs button {
        flex: 1;
      }
      .health-summary,
      .coverage-intro {
        grid-template-columns: 1fr;
      }
      .health-kpis {
        grid-template-columns: repeat(3, 1fr);
      }
      .health-kpis article:first-child {
        border-left: 0;
      }
      .stage-table > div {
        grid-template-columns: 24px minmax(0, 1fr) 58px;
      }
      .stage-observed {
        display: none;
      }
      .coverage-table {
        overflow-x: auto;
      }
      .coverage-table > header,
      .coverage-table > button {
        grid-template-columns: 190px 125px 60px 70px 70px;
        min-width: 560px;
      }
      .triage-header {
        align-items: stretch;
        flex-direction: column;
      }
      .filter-row {
        overflow-x: auto;
      }
      .issue-row {
        grid-template-columns: 5px minmax(0, 1fr) auto;
      }
      .issue-owner {
        display: none;
      }
      .context-inspector {
        max-height: none;
      }
    }
  `,
})
export class OperationsWorkspace {
  protected readonly liveSource = signal(
    new URLSearchParams(window.location.search).get('health_source') === 'live' ||
      (!new URLSearchParams(window.location.search).has('health_source') &&
        !new URLSearchParams(window.location.search).has('section') &&
        inject(LocalEvidenceService).connected()),
  );
  readonly openExperiments = output<void>();
  readonly openModelStudy = output<string>();
  protected issueStudy(): string {
    const id = this.selectedIssue().id;
    return id === 'PM-RANK-006' ? 'ranker' : id === 'PM-TRT-011' ? 'residual' : 'runtime';
  }
  readonly openScenarioLab = output<void>();
  protected readonly report = TEST_OPERATIONS;
  protected readonly section = signal<OperationsSection>(initialOperationsSection());
  protected readonly filter = signal<IssueFilter>('all');
  protected readonly selectedIssue = signal<TestOperationIssue>(
    TEST_OPERATIONS.issues.find(
      (issue) => issue.id === new URLSearchParams(window.location.search).get('issue'),
    ) ?? TEST_OPERATIONS.issues[0],
  );
  protected readonly selectedSuite = signal<TestSuiteHealth>(
    TEST_OPERATIONS.test_inventory.suites.find(
      (suite) => suite.id === new URLSearchParams(window.location.search).get('suite'),
    ) ?? TEST_OPERATIONS.test_inventory.suites[0],
  );
  constructor() {
    effect(() => {
      const url = new URL(window.location.href);
      url.searchParams.set('health_source', this.liveSource() ? 'live' : 'saved');
      url.searchParams.set('section', this.section());
      url.searchParams.set('issue', this.selectedIssue().id);
      url.searchParams.set('suite', this.selectedSuite().id);
      window.history.replaceState(null, '', url.pathname + url.search);
    });
  }
  protected readonly sections: readonly { id: OperationsSection; label: string }[] = [
    { id: 'health', label: 'Health' },
    { id: 'coverage', label: 'Coverage' },
    { id: 'triage', label: 'Triage' },
  ];
  protected readonly filters: readonly { id: IssueFilter; label: string }[] = [
    { id: 'all', label: 'All' },
    { id: 'blocked', label: 'Blocked' },
    { id: 'stopped', label: 'Stopped' },
    { id: 'pending_evidence', label: 'Pending' },
  ];
  protected readonly filteredIssues = computed(() =>
    this.filter() === 'all'
      ? this.report.issues
      : this.report.issues.filter((issue) => issue.state === this.filter()),
  );
  protected readonly healthyStageCount = computed(
    () => this.report.pipeline_stages.filter((stage) => stage.status === 'healthy').length,
  );

  protected openIssue(issue: TestOperationIssue): void {
    this.selectedIssue.set(issue);
    this.filter.set('all');
    this.section.set('triage');
  }

  protected setFilter(filter: IssueFilter): void {
    this.filter.set(filter);
    const firstVisible = this.filteredIssues()[0];
    if (firstVisible) this.selectedIssue.set(firstVisible);
  }

  protected selectSuite(suite: TestSuiteHealth): void {
    this.selectedSuite.set(suite);
    this.section.set('coverage');
  }

  protected selectPlan(id: string): void {
    this.selectedSuite.set(this.suiteFor(id));
  }

  protected suiteFor(id: string): TestSuiteHealth {
    return (
      this.report.test_inventory.suites.find((suite) => suite.id === id) ??
      this.report.test_inventory.suites[0]
    );
  }

  protected sectionTitle(): string {
    return {
      health: 'Saved run checks',
      coverage: 'Versioned behavior coverage',
      triage: 'Failure triage',
    }[this.section()];
  }

  protected shortSeal(): string {
    return `${this.report.report_sha256.slice(0, 8)}…${this.report.report_sha256.slice(-6)}`;
  }

  protected stateLabel(value: TestOperationIssue['state']): string {
    return value.replaceAll('_', ' ');
  }

  protected humanize(value: string): string {
    return value.replaceAll('_', ' ').replaceAll('v and v', 'V&V');
  }
}
