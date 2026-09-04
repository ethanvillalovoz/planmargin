import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  output,
  signal,
} from '@angular/core';
import { DebuggerStore } from '../debugger.store';
import { LocalEvidenceService } from '../local-evidence.service';
import { TEST_OPERATIONS, TestOperationIssue } from '../test-operations';
import { SceneViewport } from './scene-viewport';

type OperationsSection = 'overview' | 'coverage' | 'issues';
type IssueFilter = 'all' | 'active' | 'blocked' | 'pending_evidence';

@Component({
  selector: 'app-operations-workspace',
  imports: [SceneViewport],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="ops-workstation">
      <header class="runbar">
        <div class="run-context">
          <span class="run-kicker">Behavior test / {{ report.coverage.plan_version }}</span>
          <strong>{{ report.coverage.scenario_family }}</strong>
          <small>Campaign {{ report.campaign.campaign_id }} · report {{ shortSeal() }}</small>
        </div>
        <div class="run-facts" aria-label="Current campaign state">
          <span
            ><i class="ok"></i>{{ report.campaign.completed_cells }}/{{
              report.campaign.planned_cells
            }}
            cells</span
          >
          <span>{{ compact(report.campaign.physical_rollouts) }} rollouts</span>
          <span>{{ compact(report.campaign.waymax_steps) }} Waymax steps</span>
          <span class="decision"><i></i>0 qualifying regressions</span>
        </div>
        <button type="button" class="primary-action" (click)="openScenarioLab.emit()">
          Open retained replay
        </button>
      </header>

      <div class="workstation-grid">
        <aside class="campaign-rail" aria-label="Campaign explorer">
          <section class="rail-section campaign-summary">
            <header><span>Campaign</span><b>ACTIVE</b></header>
            <button type="button" class="campaign-row selected">
              <span><i class="ok"></i>{{ report.campaign.campaign_id }}</span>
              <small>Real WOMD · matched search</small>
            </button>
          </section>
          <section class="rail-section">
            <header>
              <span>Review queue</span><b>{{ report.issues.length }}</b>
            </header>
            @for (issue of report.issues; track issue.id) {
              <button
                type="button"
                class="rail-issue"
                [class.selected]="selectedIssue().id === issue.id"
                (click)="openIssue(issue)"
              >
                <i [class.high]="issue.severity === 'high'"></i>
                <span
                  ><strong>{{ issue.id }}</strong
                  ><small>{{ issue.title }}</small></span
                >
              </button>
            }
          </section>
          <section class="rail-section pipeline">
            <header>
              <span>Pipeline</span
              ><b>{{ healthyStageCount() }}/{{ report.pipeline_stages.length }}</b>
            </header>
            <ol>
              @for (stage of report.pipeline_stages; track stage.id; let index = $index) {
                <li>
                  <span>{{ index + 1 }}</span>
                  <div>
                    <strong>{{ stage.name }}</strong
                    ><small>{{ stage.observed }}</small>
                  </div>
                  <i [class.degraded]="stage.status === 'degraded'"></i>
                </li>
              }
            </ol>
          </section>
        </aside>

        <section class="review-surface">
          <header class="review-toolbar">
            <div>
              <span>Selected evidence</span
              ><strong>{{
                debuggerStore.hasRun()
                  ? debuggerStore.run().scenarioLabel
                  : 'No retained scene loaded'
              }}</strong>
            </div>
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
            </nav>
          </header>

          @if (section() === 'overview') {
            <div class="scene-frame">
              @if (local.connected() && debuggerStore.hasRun()) {
                <app-scene-viewport />
              } @else {
                <div class="scene-unavailable">
                  <span>LOCAL REPLAY OFFLINE</span>
                  <h1>Connect sealed records to inspect the synchronized scene.</h1>
                  <p>
                    Aggregate campaign health remains available. Camera frames, LiDAR, 3DGS, and
                    exact trajectories stay on the engineer's machine.
                  </p>
                  <button type="button" (click)="openScenarioLab.emit()">
                    Open replay workspace
                  </button>
                </div>
              }
            </div>
            <div class="time-readout" aria-label="Replay status">
              @if (local.connected() && debuggerStore.hasRun()) {
                <div class="transport">
                  <button type="button" (click)="togglePlayback()">
                    {{ debuggerStore.playing() ? 'Pause' : 'Play' }}
                  </button>
                  <button type="button" title="Back one second" (click)="jumpSeconds(-1)">
                    −1 s
                  </button>
                  <button type="button" title="Forward one second" (click)="jumpSeconds(1)">
                    +1 s
                  </button>
                </div>
              }
              <span class="timecode">{{ currentTime() }}</span>
              <div>
                <strong>{{
                  debuggerStore.hasRun() ? 'Retained planning replay' : 'Aggregate campaign only'
                }}</strong
                ><small>{{
                  local.connected() ? 'Local evidence verified' : 'Local evidence not connected'
                }}</small>
              </div>
              @if (local.connected() && debuggerStore.hasRun()) {
                <input
                  type="range"
                  min="0"
                  [max]="debuggerStore.sampleCount() - 1"
                  step="1"
                  [value]="debuggerStore.timestepIndex()"
                  (input)="seek($event)"
                  aria-label="Planning replay timeline"
                />
              }
              <span class="source">WOMD Motion · sealed evidence</span>
            </div>
            <section class="evidence-strip" aria-label="Campaign evidence summary">
              <div>
                <span>Execution</span><strong>healthy</strong
                ><small
                  >{{ report.campaign.completed_cells }}/{{ report.campaign.planned_cells }} cells
                  complete</small
                >
              </div>
              <div>
                <span>SLO state</span
                ><strong
                  >{{ report.slo_summary.passing }}/{{ report.slo_summary.total }} pass</strong
                ><small>no pipeline alert active</small>
              </div>
              <div>
                <span>Search yield</span><strong>{{ bayesianYield() }}</strong
                ><small>Bayesian valid proposals</small>
              </div>
              <div>
                <span>Behavior outcome</span><strong>0 qualifying regressions</strong
                ><small>tested planner succeeds</small>
              </div>
            </section>
          }

          @if (section() === 'coverage') {
            <div class="coverage-workspace">
              <section>
                <header>
                  <span>Versioned test plan</span><strong>Behavior coverage</strong
                  ><b>{{ report.coverage.plan_version }}</b>
                </header>
                <dl class="coverage-facts">
                  <div>
                    <dt>Scenario family</dt>
                    <dd>{{ report.coverage.scenario_family }}</dd>
                  </div>
                  <div>
                    <dt>Scenarios</dt>
                    <dd>{{ report.coverage.scenario_count }} deterministically selected</dd>
                  </div>
                  <div>
                    <dt>Seeds</dt>
                    <dd>{{ report.coverage.seeds }} per scenario and method</dd>
                  </div>
                  <div>
                    <dt>Test cells</dt>
                    <dd>{{ report.coverage.cells }} complete and sealed</dd>
                  </div>
                </dl>
                <div class="protocol">
                  <span>01</span>
                  <div>
                    <strong>Off-nominal behavior V&amp;V</strong
                    ><small
                      >Sustained command dropout ·
                      {{ report.coverage.fault_protection.physical_rollouts }} physical
                      rollouts</small
                    >
                  </div>
                  <b>80/80 gates</b>
                </div>
                <div class="protocol">
                  <span>02</span>
                  <div>
                    <strong>Assistance handoff recovery</strong
                    ><small
                      >Fault → request → fallback ·
                      {{ report.coverage.assistance_handoff.physical_rollouts }} physical
                      rollouts</small
                    >
                  </div>
                  <b>90/90 gates</b>
                </div>
                <div class="protocol">
                  <span>03</span>
                  <div>
                    <strong>Mutation contract frozen</strong
                    ><small
                      >Reference and tested planners share the same recorded intervention</small
                    >
                  </div>
                  <b>verified</b>
                </div>
              </section>
              <aside>
                <header><span>Known unknowns</span><strong>Not covered</strong></header>
                @for (gap of report.coverage.known_gaps; track gap.id) {
                  <article>
                    <b>{{ gap.label }}</b>
                    <p>{{ gap.next_test }}</p>
                  </article>
                }
              </aside>
            </div>
          }

          @if (section() === 'issues') {
            <div class="issue-workspace">
              <section class="issue-list">
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
                    type="button"
                    class="issue-card"
                    [class.selected]="selectedIssue().id === issue.id"
                    (click)="selectedIssue.set(issue)"
                  >
                    <i [class.high]="issue.severity === 'high'"></i
                    ><span
                      ><small>{{ issue.id }} · {{ issue.component }}</small
                      ><strong>{{ issue.title }}</strong>
                      <p>{{ issue.evidence }}</p></span
                    ><b>{{ stateLabel(issue.state) }}</b>
                  </button>
                }
              </section>
              <aside class="issue-detail">
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
            </div>
          }
        </section>

        <aside class="decision-inspector" aria-label="Release evidence inspector">
          <header><span>Release inspector</span><b>REVIEW</b></header>
          <section class="verdict">
            <span class="status"><i></i>TESTED PLANNER HOLDS MARGIN</span>
            <h2>No qualifying regression found.</h2>
            <p>
              The campaign is reproducible and complete. Three measured promotion decisions remain
              intentionally stopped or pending.
            </p>
          </section>
          <section class="inspector-block">
            <header>
              <span>Selected decision</span><small>{{ selectedIssue().id }}</small>
            </header>
            <strong>{{ selectedIssue().title }}</strong>
            <p>{{ selectedIssue().evidence }}</p>
            <button type="button" (click)="openIssue(selectedIssue())">Inspect evidence</button>
          </section>
          <section class="inspector-block slos">
            <header>
              <span>Release contract</span
              ><small>{{ report.slo_summary.passing }}/{{ report.slo_summary.total }}</small>
            </header>
            @for (slo of report.slos; track slo.id) {
              <div>
                <span>{{ slo.name }}</span
                ><b [class.fail]="slo.status === 'fail'">{{ slo.status }}</b>
              </div>
            }
          </section>
          <footer>
            <strong>Evidence boundary</strong>
            <p>{{ report.claim_boundary }}</p>
          </footer>
        </aside>
      </div>
    </main>
  `,
  styles: `
    :host {
      display: block;
      height: calc(100dvh - 52px);
      min-height: 640px;
      background: #0b0c0d;
      color: #e9e9e7;
      font-family:
        Inter,
        ui-sans-serif,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        'Segoe UI',
        sans-serif;
    }
    button {
      font-family: inherit;
      cursor: pointer;
    }
    .ops-workstation {
      height: 100%;
      display: grid;
      grid-template-rows: 52px minmax(0, 1fr);
      overflow: hidden;
    }
    .runbar {
      display: grid;
      grid-template-columns: minmax(270px, 1fr) auto auto;
      align-items: center;
      gap: 18px;
      padding: 0 14px;
      border-bottom: 1px solid #2a2c2e;
      background: #111214;
    }
    .run-context {
      display: grid;
      min-width: 0;
    }
    .run-kicker,
    .run-context small,
    .review-toolbar span,
    .campaign-rail header span,
    .decision-inspector > header span,
    .coverage-workspace header span {
      color: #85888b;
      font:
        600 10px/1.25 ui-monospace,
        SFMono-Regular,
        Menlo,
        monospace;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .run-context strong {
      font-size: 13px;
      font-weight: 620;
    }
    .run-context small {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 9px;
      letter-spacing: 0;
      text-transform: none;
    }
    .run-facts {
      display: flex;
      gap: 18px;
      align-items: center;
      color: #a9abad;
      font-size: 10px;
    }
    .run-facts span {
      white-space: nowrap;
    }
    .run-facts i,
    .campaign-row i,
    .status i {
      display: inline-block;
      width: 6px;
      height: 6px;
      margin-right: 6px;
      border-radius: 50%;
      background: #73db73;
    }
    .run-facts .decision {
      color: #d7d7d4;
    }
    .run-facts .decision i {
      background: #e7dd55;
    }
    .primary-action {
      min-height: 30px;
      padding: 0 11px;
      border: 1px solid #686b6e;
      border-radius: 3px;
      background: #e9e9e7;
      color: #111214;
      font-size: 10px;
      font-weight: 700;
    }
    .workstation-grid {
      display: grid;
      grid-template-columns: 220px minmax(520px, 1fr) 286px;
      min-height: 0;
    }
    .campaign-rail,
    .decision-inspector {
      min-height: 0;
      overflow: auto;
      background: #101113;
    }
    .campaign-rail {
      border-right: 1px solid #2a2c2e;
    }
    .rail-section {
      border-bottom: 1px solid #2a2c2e;
    }
    .rail-section > header,
    .decision-inspector > header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 34px;
      padding: 0 10px;
      background: #151618;
    }
    .rail-section header b,
    .decision-inspector > header b {
      color: #b9bbbd;
      font:
        600 9px ui-monospace,
        monospace;
    }
    .campaign-row,
    .rail-issue {
      width: 100%;
      border: 0;
      background: transparent;
      color: #d9d9d7;
      text-align: left;
    }
    .campaign-row {
      display: grid;
      gap: 4px;
      padding: 11px 10px;
    }
    .campaign-row.selected {
      background: #1b1d1f;
      box-shadow: inset 2px 0 #e7dd55;
    }
    .campaign-row span {
      font:
        600 10px ui-monospace,
        monospace;
    }
    .campaign-row small {
      color: #7e8184;
      font-size: 9px;
    }
    .rail-issue {
      display: grid;
      grid-template-columns: 4px minmax(0, 1fr);
      gap: 9px;
      padding: 9px 10px;
      border-top: 1px solid #222426;
    }
    .rail-issue > i,
    .issue-card > i {
      width: 3px;
      height: 26px;
      border-radius: 1px;
      background: #d9a84c;
    }
    .rail-issue > i.high,
    .issue-card > i.high {
      background: #ef705f;
    }
    .rail-issue span {
      display: grid;
      gap: 3px;
    }
    .rail-issue strong {
      font:
        600 9px ui-monospace,
        monospace;
    }
    .rail-issue small {
      overflow: hidden;
      color: #9b9d9f;
      font-size: 9px;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .rail-issue.selected {
      background: #191b1d;
    }
    .pipeline ol {
      list-style: none;
      margin: 0;
      padding: 3px 0;
    }
    .pipeline li {
      display: grid;
      grid-template-columns: 18px minmax(0, 1fr) 7px;
      gap: 6px;
      align-items: center;
      padding: 7px 10px;
    }
    .pipeline li > span {
      color: #66696c;
      font:
        9px ui-monospace,
        monospace;
    }
    .pipeline li div {
      display: grid;
    }
    .pipeline li strong {
      font-size: 9px;
      font-weight: 600;
    }
    .pipeline li small {
      color: #727578;
      font-size: 8px;
    }
    .pipeline li > i {
      width: 5px;
      height: 5px;
      border-radius: 50%;
      background: #69d38a;
    }
    .pipeline li > i.degraded {
      background: #ef705f;
    }
    .review-surface {
      display: grid;
      grid-template-rows: 43px minmax(0, 1fr) auto auto;
      min-width: 0;
      min-height: 0;
      background: #090a0b;
    }
    .review-toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 12px;
      border-bottom: 1px solid #2a2c2e;
      background: #121315;
    }
    .review-toolbar > div {
      display: grid;
    }
    .review-toolbar strong {
      font-size: 11px;
      font-weight: 620;
    }
    .ops-tabs {
      align-self: stretch;
      display: flex;
    }
    .ops-tabs button {
      min-width: 72px;
      border: 0;
      border-left: 1px solid #292b2d;
      background: transparent;
      color: #8d9093;
      font-size: 10px;
      font-weight: 620;
    }
    .ops-tabs button.active {
      background: #1b1d1f;
      color: #f1f1ef;
      box-shadow: inset 0 -2px #e7dd55;
    }
    .ops-tabs button span {
      margin-left: 4px;
      padding: 1px 4px;
      border-radius: 8px;
      background: #2d3032;
      color: #d4d4d2;
      font-size: 8px;
    }
    .scene-frame {
      position: relative;
      min-height: 0;
      overflow: hidden;
      background: #050606;
    }
    .scene-frame app-scene-viewport {
      position: absolute;
      inset: 0;
    }
    .scene-unavailable {
      display: grid;
      align-content: center;
      justify-items: start;
      max-width: 480px;
      height: 100%;
      margin: auto;
      padding: 34px;
    }
    .scene-unavailable span {
      color: #e7dd55;
      font:
        600 10px ui-monospace,
        monospace;
      letter-spacing: 0.08em;
    }
    .scene-unavailable h1 {
      margin: 12px 0 8px;
      font-size: 22px;
      line-height: 1.2;
    }
    .scene-unavailable p {
      margin: 0 0 18px;
      color: #929598;
      font-size: 12px;
      line-height: 1.55;
    }
    .scene-unavailable button,
    .inspector-block button {
      min-height: 30px;
      border: 1px solid #4b4e51;
      border-radius: 2px;
      background: #1a1c1e;
      color: #ececea;
      font-size: 10px;
    }
    .time-readout {
      display: grid;
      grid-template-columns: auto 1fr auto;
      align-items: center;
      gap: 12px;
      min-height: 44px;
      padding: 0 12px;
      border-top: 1px solid #2a2c2e;
      background: #111214;
    }
    .time-readout:has(.transport) {
      grid-template-columns: auto auto minmax(130px, auto) minmax(120px, 1fr) auto;
    }
    .timecode {
      color: #e7dd55;
      font:
        600 12px ui-monospace,
        monospace;
    }
    .time-readout > div {
      display: grid;
    }
    .time-readout .transport {
      display: flex;
      gap: 4px;
    }
    .transport button {
      min-height: 26px;
      padding: 0 7px;
      border: 1px solid #3d4043;
      border-radius: 2px;
      background: #191b1d;
      color: #d9d9d7;
      font-size: 9px;
    }
    .time-readout input {
      width: 100%;
      accent-color: #e7dd55;
    }
    .time-readout strong {
      font-size: 10px;
    }
    .time-readout small,
    .time-readout .source {
      color: #777a7d;
      font-size: 9px;
    }
    .evidence-strip {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      border-top: 1px solid #2a2c2e;
      background: #131416;
    }
    .evidence-strip > div {
      display: grid;
      gap: 3px;
      padding: 9px 11px;
      border-right: 1px solid #2a2c2e;
    }
    .evidence-strip > div:last-child {
      border: 0;
    }
    .evidence-strip span {
      color: #777a7d;
      font:
        9px ui-monospace,
        monospace;
      text-transform: uppercase;
    }
    .evidence-strip strong {
      font-size: 11px;
      font-weight: 620;
    }
    .evidence-strip small {
      color: #808386;
      font-size: 8px;
    }
    .decision-inspector {
      border-left: 1px solid #2a2c2e;
    }
    .verdict,
    .inspector-block,
    .decision-inspector > footer {
      padding: 13px;
      border-bottom: 1px solid #2a2c2e;
    }
    .status {
      color: #e7dd55;
      font:
        600 9px ui-monospace,
        monospace;
    }
    .status i {
      background: #e7dd55;
    }
    .verdict h2 {
      margin: 10px 0 7px;
      font-size: 17px;
      line-height: 1.25;
    }
    .verdict p,
    .inspector-block p,
    .decision-inspector footer p {
      margin: 0;
      color: #929598;
      font-size: 10px;
      line-height: 1.5;
    }
    .inspector-block > header {
      display: flex;
      justify-content: space-between;
      margin-bottom: 10px;
      color: #7f8285;
      font:
        600 9px ui-monospace,
        monospace;
      text-transform: uppercase;
    }
    .inspector-block > strong {
      display: block;
      margin-bottom: 6px;
      font-size: 11px;
      line-height: 1.35;
    }
    .inspector-block button {
      width: 100%;
      margin-top: 11px;
    }
    .slos > div {
      display: flex;
      justify-content: space-between;
      padding: 7px 0;
      border-top: 1px solid #242628;
      font-size: 9px;
    }
    .slos b {
      color: #6ed28e;
      text-transform: uppercase;
    }
    .slos b.fail {
      color: #ef705f;
    }
    .decision-inspector footer strong {
      font:
        600 9px ui-monospace,
        monospace;
      text-transform: uppercase;
    }
    .coverage-workspace,
    .issue-workspace {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 300px;
      min-height: 0;
      overflow: auto;
    }
    .coverage-workspace > section,
    .coverage-workspace > aside,
    .issue-list,
    .issue-detail {
      min-width: 0;
      background: #101113;
    }
    .coverage-workspace > aside,
    .issue-detail {
      border-left: 1px solid #2a2c2e;
    }
    .coverage-workspace header {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 3px;
      padding: 13px;
      border-bottom: 1px solid #2a2c2e;
    }
    .coverage-workspace header span {
      grid-column: 1/-1;
    }
    .coverage-workspace header strong {
      font-size: 13px;
    }
    .coverage-workspace header b {
      font:
        600 9px ui-monospace,
        monospace;
    }
    .coverage-facts {
      margin: 0;
    }
    .coverage-facts div {
      display: grid;
      grid-template-columns: 145px 1fr;
      padding: 10px 13px;
      border-bottom: 1px solid #242628;
    }
    .coverage-facts dt {
      color: #7d8083;
      font-size: 9px;
    }
    .coverage-facts dd {
      margin: 0;
      font-size: 10px;
    }
    .protocol {
      display: grid;
      grid-template-columns: 28px minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
      padding: 12px 13px;
      border-bottom: 1px solid #242628;
    }
    .protocol > span {
      color: #66696c;
      font:
        10px ui-monospace,
        monospace;
    }
    .protocol > div {
      display: grid;
    }
    .protocol strong {
      font-size: 10px;
    }
    .protocol small {
      color: #7e8184;
      font-size: 9px;
    }
    .protocol > b {
      color: #6ed28e;
      font:
        600 9px ui-monospace,
        monospace;
      text-transform: uppercase;
    }
    .coverage-workspace article {
      padding: 13px;
      border-bottom: 1px solid #242628;
    }
    .coverage-workspace article b {
      font-size: 10px;
    }
    .coverage-workspace article p {
      margin: 5px 0 0;
      color: #85888b;
      font-size: 9px;
      line-height: 1.45;
    }
    .issue-workspace {
      grid-template-columns: minmax(0, 1.3fr) minmax(260px, 0.7fr);
    }
    .filter-row {
      display: flex;
      gap: 5px;
      padding: 8px;
      border-bottom: 1px solid #2a2c2e;
    }
    .filter-row button {
      padding: 5px 8px;
      border: 1px solid #343638;
      border-radius: 2px;
      background: #161719;
      color: #8f9295;
      font-size: 9px;
    }
    .filter-row button.active {
      border-color: #777a7d;
      background: #27292b;
      color: #f0f0ee;
    }
    .issue-card {
      display: grid;
      grid-template-columns: 4px minmax(0, 1fr) auto;
      gap: 10px;
      width: 100%;
      padding: 11px 12px;
      border: 0;
      border-bottom: 1px solid #242628;
      background: transparent;
      color: #dededc;
      text-align: left;
    }
    .issue-card.selected {
      background: #1b1d1f;
    }
    .issue-card span {
      display: grid;
      gap: 3px;
    }
    .issue-card small {
      color: #7f8285;
      font:
        9px ui-monospace,
        monospace;
    }
    .issue-card strong {
      font-size: 10px;
    }
    .issue-card p {
      margin: 0;
      color: #898c8f;
      font-size: 9px;
    }
    .issue-card > b {
      color: #d8ad5a;
      font:
        600 8px ui-monospace,
        monospace;
      text-transform: uppercase;
    }
    .issue-detail {
      padding: 14px;
    }
    .issue-detail > header {
      display: flex;
      justify-content: space-between;
      color: #85888b;
      font:
        600 9px ui-monospace,
        monospace;
      text-transform: uppercase;
    }
    .issue-detail h2 {
      margin: 14px 0;
      font-size: 16px;
      line-height: 1.3;
    }
    .issue-detail dl {
      margin: 0;
    }
    .issue-detail dl div {
      padding: 9px 0;
      border-top: 1px solid #2a2c2e;
    }
    .issue-detail dt {
      color: #777a7d;
      font-size: 8px;
      text-transform: uppercase;
    }
    .issue-detail dd {
      margin: 4px 0 0;
      color: #b4b6b8;
      font-size: 9px;
      line-height: 1.5;
    }
    .issue-detail code,
    .failed-gates code {
      font:
        8px ui-monospace,
        monospace;
      color: #d4cf75;
    }
    .failed-gates {
      margin-top: 10px;
    }
    .failed-gates span {
      display: block;
      color: #777a7d;
      font-size: 8px;
      text-transform: uppercase;
    }
    .failed-gates code {
      display: block;
      margin-top: 5px;
      padding: 6px;
      background: #18191b;
    }
    .pending-note {
      margin-top: 10px;
      padding: 8px;
      border-left: 2px solid #d9a84c;
      background: #1b1914;
      color: #c9b47e;
      font-size: 9px;
      line-height: 1.4;
    }
    @media (max-width: 1180px) {
      .workstation-grid {
        grid-template-columns: 190px minmax(440px, 1fr) 250px;
      }
      .run-facts span:nth-child(2),
      .run-facts span:nth-child(3) {
        display: none;
      }
    }
    @media (max-width: 900px) {
      :host {
        height: auto;
      }
      .ops-workstation {
        height: auto;
        min-height: calc(100dvh - 52px);
      }
      .runbar {
        grid-template-columns: 1fr auto;
      }
      .run-facts {
        display: none;
      }
      .workstation-grid {
        grid-template-columns: 180px minmax(0, 1fr);
      }
      .decision-inspector {
        grid-column: 1/-1;
        border-top: 1px solid #2a2c2e;
        border-left: 0;
      }
      .review-surface {
        min-height: 620px;
      }
      .coverage-workspace,
      .issue-workspace {
        grid-template-columns: 1fr;
      }
    }
    @media (max-width: 650px) {
      .runbar {
        grid-template-columns: 1fr;
        padding: 7px 10px;
      }
      .primary-action {
        display: none;
      }
      .workstation-grid {
        grid-template-columns: 1fr;
      }
      .campaign-rail {
        display: none;
      }
      .review-toolbar {
        align-items: stretch;
        flex-direction: column;
        height: auto;
        padding: 8px;
      }
      .review-surface {
        grid-template-rows: auto minmax(0, 1fr) auto auto;
      }
      .ops-tabs {
        min-height: 34px;
      }
      .evidence-strip {
        grid-template-columns: repeat(2, 1fr);
      }
      .source {
        display: none;
      }
    }
  `,
})
export class OperationsWorkspace {
  readonly openScenarioLab = output<void>();
  protected readonly debuggerStore = inject(DebuggerStore);
  protected readonly local = inject(LocalEvidenceService);
  protected readonly report = TEST_OPERATIONS;
  protected readonly section = signal<OperationsSection>('overview');
  protected readonly filter = signal<IssueFilter>('all');
  protected readonly selectedIssue = signal<TestOperationIssue>(TEST_OPERATIONS.issues[0]);
  protected readonly sections: readonly { id: OperationsSection; label: string }[] = [
    { id: 'overview', label: 'Replay' },
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
  protected currentTime(): string {
    return this.debuggerStore.hasRun() ? `${this.debuggerStore.timeSeconds().toFixed(1)} s` : '—';
  }
  protected togglePlayback(): void {
    this.debuggerStore.togglePlayback();
  }
  protected jumpSeconds(deltaSeconds: number): void {
    const steps = Math.max(
      1,
      Math.round(Math.abs(deltaSeconds) / this.debuggerStore.run().stepSeconds),
    );
    this.debuggerStore.step(Math.sign(deltaSeconds) * steps);
  }
  protected seek(event: Event): void {
    this.debuggerStore.seek(Number((event.target as HTMLInputElement).value));
  }
  protected bayesianYield(): string {
    return `${(this.report.coverage.methods['bayesian'].eligible_rate * 100).toFixed(2)}%`;
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
