import { ChangeDetectionStrategy, Component, inject, output, signal } from '@angular/core';
import { NgIcon, provideIcons } from '@ng-icons/core';
import {
  phosphorDownloadSimple,
  phosphorPlay,
  phosphorSparkle,
  phosphorStack,
} from '@ng-icons/phosphor-icons/regular';
import { InvestigationReportService } from '../investigation-report.service';
import { DebuggerStore } from '../debugger.store';
import { LocalEvidenceService } from '../local-evidence.service';
import { InvestigationProposal, LocalProposal, ProposalAnalysis } from '../local-evidence.types';
import { SensorMode, SimulatorStore } from '../simulator.store';
import { SimulatorWorkspace } from './simulator-workspace';
import { OperationsWorkspace } from './operations-workspace';
import { ScenarioAssistant } from './scenario-assistant';
import { ExperimentWorkspace } from './experiment-workspace';
import { ModelsWorkspace } from './models-workspace';
import { ProposalBrowser } from './proposal-browser';
import { DebuggerRun } from '../debugger.types';

type ProductView = 'operations' | 'investigate' | 'replay' | 'sensor' | 'experiments';
type EvidenceView = 'campaign' | 'deployment';

function initialProductView(): ProductView {
  const requested = new URLSearchParams(window.location.search).get('view');
  if (requested === 'evidence') return 'investigate';
  if (requested === 'experiments') return 'experiments';
  if (requested === 'replay' || requested === 'sensors') {
    return requested === 'sensors' ? 'sensor' : requested;
  }
  if (requested === 'health' || requested === 'operations') return 'operations';
  return 'investigate';
}

function initialEvidenceView(): EvidenceView {
  return new URLSearchParams(window.location.search).get('panel') === 'runtime'
    ? 'deployment'
    : 'campaign';
}

@Component({
  selector: 'app-product-shell',
  imports: [
    NgIcon,
    OperationsWorkspace,
    SimulatorWorkspace,
    ScenarioAssistant,
    ExperimentWorkspace,
    ModelsWorkspace,
    ProposalBrowser,
  ],
  providers: [
    provideIcons({
      phosphorDownloadSimple,
      phosphorPlay,
      phosphorSparkle,
      phosphorStack,
    }),
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="product-shell" [class.sensor-active]="view() === 'sensor' || view() === 'replay'">
      <header class="product-header">
        <button class="brand" type="button" (click)="openInvestigation()">
          <ng-icon name="phosphorStack" size="23" aria-hidden="true" />
          <span class="brand-lockup">
            <strong>PlanMargin</strong>
            <small>Planner stress testing</small>
          </span>
        </button>
        <nav aria-label="Product sections">
          <button
            type="button"
            [class.active]="
              (view() === 'investigate' && evidenceView() === 'campaign') ||
              view() === 'experiments'
            "
            (click)="openInvestigation()"
          >
            Investigate
          </button>
          <button type="button" [class.active]="view() === 'replay'" (click)="setView('replay')">
            Replay
          </button>
          <button
            type="button"
            [class.active]="view() === 'operations'"
            (click)="setView('operations')"
          >
            Test health
          </button>
          <button type="button" [class.active]="view() === 'sensor'" (click)="setView('sensor')">
            Sensor lab
          </button>
          <button
            type="button"
            [class.active]="view() === 'investigate' && evidenceView() === 'deployment'"
            (click)="openModels()"
          >
            Models
          </button>
        </nav>
        <div class="header-actions">
          <button
            type="button"
            class="assistant-launch"
            [class.active]="simulator.assistantOpen()"
            [disabled]="!local.connected()"
            (click)="toggleAssistant()"
          >
            <ng-icon name="phosphorSparkle" size="15" />{{
              view() === 'experiments' ||
              (view() === 'replay' &&
                debuggerStore.hasRun() &&
                debuggerStore.run().runId.startsWith('experiment_'))
                ? 'Ask campaign guide'
                : 'Ask PlanMargin'
            }}
          </button>
          @if (publicHosted) {
            <a class="connection" [href]="repositoryUrl"><i></i>Clone for local workspace</a>
          } @else {
            <button
              type="button"
              class="connection"
              [class.connected]="local.connected()"
              [class.connecting]="local.state() === 'connecting'"
              (click)="connectRequested.emit()"
            >
              <i></i
              >{{
                local.connected()
                  ? 'Local workspace connected'
                  : local.state() === 'connecting'
                    ? 'Verifying local records…'
                    : local.state() === 'error'
                      ? 'Reconnect workspace'
                      : 'Open local workspace'
              }}
            </button>
          }
        </div>
      </header>

      @if (local.error()) {
        <div class="connection-error" role="alert">
          <span>{{ local.error() }}</span>
          <button type="button" (click)="connectRequested.emit()">Reconnect</button>
        </div>
      }
      @if (view() === 'experiments') {
        <app-experiment-workspace
          (campaignRequested)="openInvestigation()"
          (connectRequested)="connectRequested.emit()"
          (replayRequested)="openExperimentReplay($event)"
        />
      } @else if (view() === 'operations') {
        <app-operations-workspace
          (openScenarioLab)="openInvestigation()"
          (openExperiments)="setView('experiments')"
          (openModelStudy)="openModels($event)"
        />
      } @else if (view() === 'investigate') {
        <main class="investigation-page">
          <header class="evidence-commandbar">
            <div class="evidence-context">
              <span>{{
                evidenceView() === 'campaign'
                  ? 'Counterfactual investigation'
                  : 'Supporting research'
              }}</span>
              <h1>
                {{ evidenceView() === 'campaign' ? 'Lead-vehicle braking' : 'Models & runtime' }}
              </h1>
              <p>
                {{
                  evidenceView() === 'campaign'
                    ? 'Change when the lead vehicle brakes. Compare the tested planner with a conservative reference.'
                    : 'Prediction and deployment studies. These models are evaluated separately from the planning campaign.'
                }}
              </p>
            </div>
            @if (evidenceView() === 'campaign') {
              <button class="new-experiment-action" type="button" (click)="setView('experiments')">
                New experiment
              </button>
              <div class="campaign-outcome" aria-label="Campaign result">
                <strong
                  >{{
                    local.campaign().methods.random.qualifyingFindings +
                      local.campaign().methods.bayesian.qualifyingFindings
                  }}
                  qualifying regressions</strong
                >
                <span
                  >{{ local.campaign().proposals.toLocaleString() }} tested changes · 10 recorded
                  scenarios</span
                >
              </div>
            }
          </header>

          @if (evidenceView() === 'deployment') {
            <app-models-workspace
              [initialStudy]="modelStudy()"
              (studySelected)="modelStudy.set($event)"
            />
          } @else if (!local.connected() || !local.campaignAvailable()) {
            <section class="public-workbench">
              <header class="public-result">
                <div>
                  <span>Published aggregate evidence · verified campaign</span>
                  <h2>3,200 counterfactual proposals. Zero qualifying regressions.</h2>
                  <p>
                    Explore the real experiment summary below. Per-scenario WOMD records stay local,
                    so this public surface reports only sealed campaign aggregates—never substitute
                    or synthetic cases.
                  </p>
                </div>
                @if (publicHosted) {
                  <a class="primary" [href]="repositoryUrl">Clone for licensed local evidence</a>
                } @else {
                  <button class="primary" type="button" (click)="connectRequested.emit()">
                    Open licensed local evidence
                  </button>
                }
              </header>
              <div class="public-kpis" aria-label="Published campaign totals">
                <div>
                  <strong>{{ local.campaign().cells }}</strong
                  ><span>matched cells</span>
                </div>
                <div>
                  <strong>{{ local.campaign().proposals.toLocaleString() }}</strong
                  ><span>proposals</span>
                </div>
                <div>
                  <strong>{{ local.campaign().physicalRollouts.toLocaleString() }}</strong
                  ><span>physical rollouts</span>
                </div>
                <div>
                  <strong>{{ local.campaign().rolloutSteps.toLocaleString() }}</strong
                  ><span>Waymax steps</span>
                </div>
              </div>
              <div class="public-analysis">
                <section class="method-card" aria-labelledby="public-method-title">
                  <header>
                    <div>
                      <span>Method comparison</span>
                      <h3 id="public-method-title">Feasible proposal yield</h3>
                    </div>
                    <small>same 50 scenario × seed cells per method</small>
                  </header>
                  <div class="method-row random">
                    <div><strong>Random</strong><span>1,600 proposals</span></div>
                    <div class="bar">
                      <i [style.width.%]="local.campaign().methods.random.validRatePercent"></i>
                    </div>
                    <b>{{ local.campaign().methods.random.validRatePercent.toFixed(2) }}%</b>
                  </div>
                  <div class="method-row bayesian">
                    <div><strong>Constrained Bayesian</strong><span>1,600 proposals</span></div>
                    <div class="bar">
                      <i [style.width.%]="local.campaign().methods.bayesian.validRatePercent"></i>
                    </div>
                    <b>{{ local.campaign().methods.bayesian.validRatePercent.toFixed(2) }}%</b>
                  </div>
                  <p class="method-finding">
                    Bayesian search improved support-and-pipeline-valid yield by
                    <strong>{{ publicValidRateDelta().toFixed(2) }} percentage points</strong>. Both
                    methods found zero policy-specific avoidable failures, so efficiency and
                    minimality were not testable.
                  </p>
                </section>
                <section class="decision-card" aria-labelledby="public-decision-title">
                  <header>
                    <span>Frozen hypothesis decisions</span>
                    <h3 id="public-decision-title">What the evidence supports</h3>
                  </header>
                  <dl>
                    <div>
                      <dt>H1 · efficiency</dt>
                      <dd class="neutral">{{ local.campaign().hypotheses.efficiency }}</dd>
                    </div>
                    <div>
                      <dt>H2 · minimality</dt>
                      <dd class="neutral">{{ local.campaign().hypotheses.minimality }}</dd>
                    </div>
                    <div>
                      <dt>H3 · validity</dt>
                      <dd class="supported">{{ local.campaign().hypotheses.validity }}</dd>
                    </div>
                    <div>
                      <dt>Held-out comparison</dt>
                      <dd class="neutral">Not run</dd>
                    </div>
                  </dl>
                </section>
              </div>
              <footer class="public-boundary">
                <div>
                  <strong>Public and reproducible</strong>
                  <p>Campaign totals, method aggregates, decisions, hashes, and bundle verifier.</p>
                </div>
                <div>
                  <strong>Licensed local only</strong>
                  <p>Scenario paths, proposal records, camera imagery, LiDAR, and 3DGS assets.</p>
                </div>
              </footer>
            </section>
          } @else {
            <div class="investigation-layout">
              <app-proposal-browser
                [compared]="comparison()"
                (inspectRequested)="openCampaignProposal($event)"
                (compareRequested)="toggleCompare($event)"
                (comparisonRequested)="openComparison()"
                (cellRequested)="selectCell($event)"
              />
              <section class="investigation-workspace" aria-label="Proposal inspector">
                <nav class="inspector-tabs" aria-label="Inspection mode">
                  <button
                    type="button"
                    [attr.aria-pressed]="!showComparison()"
                    (click)="showComparison.set(false)"
                  >
                    Selected proposal
                  </button>
                  <button
                    type="button"
                    [attr.aria-pressed]="showComparison()"
                    (click)="openComparison()"
                  >
                    Compare ({{ comparison().length }}/2)
                  </button>
                </nav>
                @if (showComparison()) {
                  <section class="comparison-dock" aria-labelledby="comparison-title" tabindex="-1">
                    <header>
                      <div>
                        <p>2 · Compare measured outcomes</p>
                        <h2 id="comparison-title">Proposal comparison</h2>
                      </div>
                      <button type="button" (click)="comparison.set([])">Clear selection</button>
                    </header>
                    <p class="comparison-instruction" role="status">
                      {{
                        comparison().length < 2
                          ? 'Choose Compare on ' +
                            (comparison().length === 0 ? 'two proposals' : 'one more proposal') +
                            ' in the list. You can change scenarios without losing your selection.'
                          : 'A and B are selected. Compare their measurements below, or open either saved replay.'
                      }}
                    </p>
                    @if (
                      comparison().length === 2 &&
                      comparison()[0].selectionOrder !== comparison()[1].selectionOrder
                    ) {
                      <p class="comparison-boundary">
                        Different recorded scenarios: these are separate experiments, not two
                        planners in the same scene. A smaller gap alone does not mean a worse
                        planner.
                      </p>
                    }
                    @if (comparison().length > 0) {
                      <table
                        class="comparison-table"
                        aria-label="Proposal measurements side by side"
                      >
                        <thead>
                          <tr>
                            <th scope="col">Measurement</th>
                            @for (
                              proposal of comparison();
                              track proposal.cellId + ':' + proposal.proposalNumber;
                              let index = $index
                            ) {
                              <th scope="col">
                                <span class="comparison-slot">{{ index === 0 ? 'A' : 'B' }}</span
                                ><strong
                                  >Scenario {{ proposal.selectionOrder }}<br />Proposal
                                  {{ proposal.proposalNumber }}</strong
                                ><small>{{ proposal.method }} · seed {{ proposal.seed }}</small>
                              </th>
                            }
                          </tr>
                        </thead>
                        <tbody>
                          @for (measurement of comparisonMeasurements; track measurement.key) {
                            <tr>
                              <th scope="row">{{ measurement.label }}</th>
                              @for (
                                proposal of comparison();
                                track proposal.cellId + ':' + proposal.proposalNumber
                              ) {
                                <td>{{ comparisonValue(proposal, measurement.key) }}</td>
                              }
                            </tr>
                          }
                          <tr>
                            <th scope="row">Inspect evidence</th>
                            @for (
                              proposal of comparison();
                              track proposal.cellId + ':' + proposal.proposalNumber;
                              let index = $index
                            ) {
                              <td class="comparison-actions">
                                <button type="button" (click)="openCampaignProposal(proposal)">
                                  Inspect {{ index === 0 ? 'A' : 'B' }}
                                </button>
                                @if (proposal.trajectoryAvailable && proposal.replayRunId) {
                                  <button
                                    type="button"
                                    [disabled]="replayLoading()"
                                    (click)="openComparedReplay(proposal)"
                                  >
                                    Open replay {{ index === 0 ? 'A' : 'B' }}
                                  </button>
                                } @else {
                                  <span>Metrics only · trajectory not saved</span>
                                }
                                <button type="button" (click)="toggleCompare(proposal)">
                                  Remove {{ index === 0 ? 'A' : 'B' }}
                                </button>
                              </td>
                            }
                          </tr>
                        </tbody>
                      </table>
                      @if (comparison().length === 2) {
                        <p class="comparison-limit">
                          To compare another proposal, remove A or B first. Saved replays open
                          individually; this panel compares measurements.
                        </p>
                      }
                    }
                    @if (replayError()) {
                      <p role="alert">{{ replayError() }}</p>
                    }
                  </section>
                } @else {
                  <section class="proposal-region">
                    <div class="proposal-layout">
                      @if (local.loadingProposals()) {
                        <p class="loading-state" role="status">
                          Reading the selected scenario change…
                        </p>
                      } @else if (local.selectedProposal(); as proposal) {
                        <article class="proposal-detail">
                          <header>
                            <div>
                              <p>
                                Scenario {{ local.selectedCell()?.selectionOrder }} ·
                                {{ local.selectedCell()?.method }} · seed
                                {{ local.selectedCell()?.seed }} · proposal
                                {{ proposal.proposalNumber }}
                              </p>
                              <h2>{{ gateReason(proposal) }}</h2>
                            </div>
                            <button
                              type="button"
                              class="detail-help"
                              [attr.aria-expanded]="showGateDetails()"
                              (click)="showGateDetails.set(!showGateDetails())"
                            >
                              {{ showGateDetails() ? 'Hide gate details' : 'Explain decision' }}
                            </button>
                          </header>
                          <p class="decision-explanation">{{ decisionExplanation(proposal) }}</p>
                          <div class="parameter-strip">
                            <div>
                              <span>Braking onset shift</span
                              ><strong>{{
                                signedSeconds(proposal.brakingOnsetOffsetSeconds)
                              }}</strong>
                            </div>
                            <div>
                              <span>Lead speed scale</span
                              ><strong
                                >{{ (proposal.speedMultiplier * 100).toFixed(1) }}% of recorded
                                speed</strong
                              >
                            </div>
                            <div>
                              <span>Closest approach</span
                              ><strong>{{ proximityLabel(proposal.criticality) }}</strong>
                            </div>
                            <div>
                              <span>Change size</span
                              ><strong>{{
                                proposal.objectiveAvailable
                                  ? changeSizeLabel(proposal.minimality)
                                  : 'Not scored'
                              }}</strong>
                            </div>
                          </div>
                          <div class="controller-comparison" aria-label="Planner outcomes">
                            <div>
                              <span>Tested planner</span>
                              <strong [class.failure]="proposal.testedMutatedFailure === true">{{
                                proposal.testedMutatedFailure === true
                                  ? 'Failed'
                                  : proposal.testedMutatedFailure === false
                                    ? 'Succeeded'
                                    : 'Not evaluated'
                              }}</strong>
                            </div>
                            <div>
                              <span>Reference planner</span>
                              <strong [class.success]="proposal.referenceMutatedSuccess === true">{{
                                proposal.referenceMutatedSuccess === true
                                  ? 'Succeeded'
                                  : proposal.referenceMutatedSuccess === false
                                    ? 'Failed'
                                    : 'Not evaluated'
                              }}</strong>
                            </div>
                            <div>
                              <span>Finding contract</span>
                              <strong>{{
                                proposal.policySpecificAvoidableFailure === true
                                  ? 'Qualified'
                                  : 'Not qualified'
                              }}</strong>
                            </div>
                          </div>
                          @if (showGateDetails()) {
                            <ol class="gate-ladder">
                              @for (gate of proposalGates(proposal); track gate.label) {
                                <li [class.pass]="gate.pass" [class.stop]="gate.stop">
                                  <i>{{ gate.pass ? '✓' : gate.stop ? '×' : '—' }}</i>
                                  <div>
                                    <strong>{{ gate.label }}</strong
                                    ><span>{{ gate.detail }}</span>
                                  </div>
                                </li>
                              }
                            </ol>
                          }
                          <div class="replay-boundary">
                            @if (proposal.trajectoryAvailable && proposal.replayRunId) {
                              <strong>Exact proposal replay retained and verified.</strong>
                              <p>
                                Replay this exact change and inspect the moment of closest approach.
                              </p>
                              <button
                                type="button"
                                (click)="openProposalReplay(proposal.replayRunId)"
                                [disabled]="replayLoading()"
                              >
                                <ng-icon name="phosphorPlay" size="15" />{{
                                  replayLoading()
                                    ? 'Loading exact replay…'
                                    : 'Open exact proposal replay'
                                }}
                              </button>
                            } @else if (!proposal.objectiveAvailable) {
                              <strong>No valid trajectory to replay.</strong>
                              <p>
                                This proposal was rejected before a valid evaluation was completed.
                                You can inspect its rejection record, but it has no scored clearance
                                or saved replay.
                              </p>
                            } @else {
                              <strong>Proposal trajectory is not retained.</strong>
                              <p>
                                This change has verified outcomes and metrics. Its full trajectory
                                was not saved. Use “Saved replays only” in the scenario browser to
                                find a saved path. These planning scenarios are separate from the
                                Sensor lab's camera scenes.
                              </p>
                            }
                            @if (replayError()) {
                              <span class="replay-error" role="alert">{{ replayError() }}</span>
                            }
                          </div>
                          <div class="detail-actions">
                            <button
                              type="button"
                              (click)="groundAnalysis()"
                              [disabled]="analysisLoading()"
                            >
                              <ng-icon name="phosphorSparkle" size="15" />{{
                                analysisLoading()
                                  ? 'Reading sealed record…'
                                  : 'Analyze selected proposal'
                              }}
                            </button>
                            <button type="button" (click)="exportReport()">
                              <ng-icon name="phosphorDownloadSimple" size="15" />Export
                              investigation
                            </button>
                          </div>
                          @if (analysis(); as answer) {
                            <section class="grounded-analysis" aria-live="polite">
                              <strong>Proposal-specific evidence analysis</strong>
                              <p>{{ answer.explanation }}</p>
                              <dl>
                                @for (fact of answer.facts; track fact.label) {
                                  <div>
                                    <dt>{{ fact.label }}</dt>
                                    <dd>{{ fact.value }}</dd>
                                  </div>
                                }
                              </dl>
                              <div>
                                <code>sealed record · {{ answer.recordSha256.slice(0, 16) }}</code>
                              </div>
                            </section>
                          } @else if (analysisError()) {
                            <p class="analysis-error" role="alert">{{ analysisError() }}</p>
                          }
                        </article>
                      }
                    </div>
                  </section>
                }
              </section>
            </div>
          }
        </main>
      } @else if (!local.connected()) {
        <main class="locked-workspace">
          <aside class="locked-rail">
            <header><span>Workspace</span><b>OFFLINE</b></header>
            <button class="selected" type="button">
              {{ view() === 'sensor' ? 'Perception scene' : 'Planning replay' }}
            </button>
            <section>
              <span>Available after connection</span>
              <p>Camera frames</p>
              <p>LiDAR point cloud</p>
              <p>3DGS reconstruction</p>
              <p>Exact trajectories</p>
            </section>
          </aside>
          <section class="locked-canvas">
            <div>
              <span>LOCAL EVIDENCE REQUIRED</span>
              <h1>
                {{
                  view() === 'sensor' ? 'No perception scene loaded' : 'No retained replay loaded'
                }}
              </h1>
              <p>
                PlanMargin never substitutes generated or synthetic media for licensed Waymo Open
                Dataset records.
              </p>
              @if (publicHosted) {
                <a class="primary" [href]="repositoryUrl">Clone for local workspace</a>
              } @else {
                <button class="primary" type="button" (click)="connectRequested.emit()">
                  Connect sealed records
                </button>
              }
            </div>
          </section>
          <aside class="locked-inspector">
            <header><span>Data boundary</span><b>READ ONLY</b></header>
            <dl>
              <div>
                <dt>Campaign proposals</dt>
                <dd>{{ local.campaign().proposals.toLocaleString() }}</dd>
              </div>
              <div>
                <dt>Physical rollouts</dt>
                <dd>{{ local.campaign().physicalRollouts.toLocaleString() }}</dd>
              </div>
              <div>
                <dt>Local sensor record</dt>
                <dd>Not connected</dd>
              </div>
              <div>
                <dt>Synthetic substitutes</dt>
                <dd>None</dd>
              </div>
            </dl>
            <button type="button" (click)="setView('investigate')">
              Inspect aggregate evidence
            </button>
          </aside>
        </main>
      } @else if (view() === 'sensor' && !local.campaignAvailable()) {
        <main class="sensor-setup">
          <span>Optional workspace</span>
          <h1>Sensor lab is not loaded in planning-only mode</h1>
          <p>
            Your experiment runner is connected. Camera, LiDAR, and 3DGS use a separate licensed
            Perception segment and are not required for planning experiments.
          </p>
          <p>
            To add those capabilities, stop the launcher, prepare the full workspace, and relaunch
            without <code>--planning-only</code>.
          </p>
          <a
            href="https://github.com/ethanvillalovoz/planmargin/blob/main/docs/reproducing-the-workspace.md"
          >
            Read the full-workspace setup guide
          </a>
          <button type="button" (click)="setView('experiments')">Return to experiments</button>
        </main>
      } @else if (view() === 'replay' && !debuggerStore.hasRun()) {
        <main class="loading-state" role="status">
          {{
            local.campaignAvailable()
              ? 'Loading verified planning evidence…'
              : 'Run a local experiment to create an exact replay.'
          }}
          <button type="button" (click)="setView('experiments')">Open experiments</button>
        </main>
      } @else {
        <app-simulator-workspace
          class="embedded-simulator"
          [embedded]="true"
          (modeChanged)="onWorkspaceMode($event)"
          (connectRequested)="connectRequested.emit()"
          (evidenceRequested)="returnFromReplay()"
        />
      }
      @if (simulator.assistantOpen()) {
        <app-scenario-assistant class="global-assistant" (planningRequested)="setView('replay')" />
      }
    </div>
  `,
  styleUrl: './product-shell.css',
})
export class ProductShell {
  protected readonly local = inject(LocalEvidenceService);
  protected readonly simulator = inject(SimulatorStore);
  protected readonly debuggerStore = inject(DebuggerStore);
  private readonly reports = inject(InvestigationReportService);
  readonly connectRequested = output<void>();
  protected readonly repositoryUrl = 'https://github.com/ethanvillalovoz/planmargin';
  protected readonly publicHosted =
    window.location.protocol === 'https:' &&
    window.location.hostname !== 'localhost' &&
    window.location.hostname !== '127.0.0.1';
  protected readonly view = signal<ProductView>(initialProductView());
  constructor() {
    if (this.view() === 'replay') this.simulator.selectMode('planning');
    if (this.view() === 'sensor') this.simulator.selectMode('camera');
  }
  protected readonly evidenceView = signal<EvidenceView>(initialEvidenceView());
  protected readonly modelStudy = signal(
    new URLSearchParams(window.location.search).get('study') ?? 'prediction',
  );
  protected readonly comparison = signal<readonly InvestigationProposal[]>([]);
  protected readonly showComparison = signal(false);
  protected readonly comparisonMeasurements = [
    { key: 'gap', label: 'Minimum gap (m)' },
    { key: 'onset', label: 'Braking onset shift (s)' },
    { key: 'speed', label: 'Recorded lead speed (%)' },
    { key: 'tested', label: 'Tested planner' },
    { key: 'reference', label: 'Reference planner' },
    { key: 'support', label: 'Recorded-behavior support' },
    { key: 'regression', label: 'Qualifying regression' },
  ];
  protected comparisonValue(p: InvestigationProposal, key: string): string {
    if (key === 'gap')
      return p.objectiveAvailable ? this.clearanceValue(p.criticality) : 'Not evaluated';
    if (key === 'onset') return this.signedSeconds(p.brakingOnsetOffsetSeconds);
    if (key === 'speed') return (p.speedMultiplier * 100).toFixed(1) + '%';
    if (key === 'tested')
      return p.testedMutatedFailure === true
        ? 'Failed'
        : p.testedMutatedFailure === false
          ? 'Succeeded'
          : 'Not evaluated';
    if (key === 'reference')
      return p.referenceMutatedSuccess === true
        ? 'Succeeded'
        : p.referenceMutatedSuccess === false
          ? 'Failed'
          : 'Not evaluated';
    if (key === 'support') return this.supportLabel(p.empiricalSupportProbability, p.supportPasses);
    return p.policySpecificAvoidableFailure === true ? 'Yes' : 'No';
  }
  protected readonly analysis = signal<ProposalAnalysis | undefined>(undefined);
  protected readonly analysisLoading = signal(false);
  protected readonly analysisError = signal<string | undefined>(undefined);
  protected readonly replayLoading = signal(false);
  protected readonly replayError = signal<string | undefined>(undefined);
  protected readonly showGateDetails = signal(false);
  private analysisGeneration = 0;
  private readonly healthQueryKeys = ['health_source', 'section', 'issue', 'suite'];
  private healthContext: URLSearchParams | undefined;

  protected clearanceValue(value: number): string {
    return value > 0 ? Math.max(1 / value - 1, 0).toFixed(2) + ' m' : '—';
  }
  protected decisionExplanation(proposal: LocalProposal): string {
    if (proposal.policySpecificAvoidableFailure)
      return 'The edit passes the realism gates. The tested planner fails while the conservative reference succeeds under the same change.';
    if (!proposal.pipelinePasses)
      return 'This change did not pass simulation validity. Its result cannot establish a planner regression.';
    if (proposal.supportPasses !== true)
      return proposal.supportPasses === null
        ? 'Recorded-behavior support was not evaluated. This case cannot qualify without that realism check.'
        : 'The change falls outside the recorded behavior used by the realism gate. It is excluded from qualifying findings.';
    if (!proposal.referencePasses)
      return proposal.referenceMutatedSuccess === false
        ? 'The conservative reference failed. This case does not isolate an avoidable failure of the tested planner.'
        : 'The reference outcome is not established. This case cannot isolate an avoidable failure of the tested planner.';
    if (proposal.testedMutatedFailure !== false)
      return 'The complete planner-specific finding contract is not satisfied. Inspect the individual gates before drawing a conclusion.';
    return 'Both planners completed this change successfully. The minimum gap helps prioritize inspection, but this case is not a qualifying regression.';
  }
  protected openInvestigation(): void {
    this.evidenceView.set('campaign');
    this.setView('investigate');
  }
  protected openModels(study?: string): void {
    if (study) this.modelStudy.set(study);
    this.evidenceView.set('deployment');
    this.setView('investigate');
  }

  protected setView(view: ProductView): void {
    const url = new URL(window.location.href);
    if (this.view() === 'operations' && view !== 'operations') {
      // Keep the investigation in memory without leaking its route parameters
      // onto unrelated pages. No credential or private evidence is retained.
      this.healthContext = new URLSearchParams();
      for (const key of this.healthQueryKeys) {
        const value = url.searchParams.get(key);
        if (value !== null) this.healthContext.set(key, value);
      }
    } else if (view === 'operations' && this.healthContext) {
      for (const key of this.healthQueryKeys) {
        const value = this.healthContext.get(key);
        if (value === null) url.searchParams.delete(key);
        else url.searchParams.set(key, value);
      }
    }
    if (view === 'replay') this.simulator.selectMode('planning');
    if (view === 'sensor') this.simulator.selectMode('camera');
    this.view.set(view);
    window.scrollTo({ top: 0, behavior: 'instant' });
    if (view !== 'operations') {
      for (const key of this.healthQueryKeys) url.searchParams.delete(key);
    }
    if (view !== 'experiments' && view !== 'operations') url.searchParams.delete('job');
    if (!(view === 'investigate' && this.evidenceView() === 'deployment'))
      url.searchParams.delete('study');
    url.searchParams.set(
      'view',
      view === 'operations'
        ? 'health'
        : view === 'investigate'
          ? 'evidence'
          : view === 'experiments'
            ? 'experiments'
            : view === 'sensor'
              ? 'sensors'
              : 'replay',
    );
    if (view === 'investigate' && this.evidenceView() === 'deployment') {
      url.searchParams.set('panel', 'runtime');
      url.searchParams.set('study', this.modelStudy());
    } else url.searchParams.delete('panel');
    // Preserve the exact planning record across supporting pages and refresh.
    // These are opaque local record identifiers, never tokens or file paths.
    if (this.debuggerStore.hasRun()) {
      const runId = this.debuggerStore.run().runId;
      if (runId.startsWith('experiment_')) {
        url.searchParams.set('experiment', runId.slice('experiment_'.length));
        url.searchParams.delete('run');
      } else {
        url.searchParams.set('run', runId);
        url.searchParams.delete('experiment');
      }
    }
    window.history.replaceState(null, '', url.pathname + url.search);
  }
  protected openExperimentReplay(run: DebuggerRun): void {
    this.debuggerStore.loadRun(run);
    this.setView('replay');
    const url = new URL(window.location.href);
    url.searchParams.set('experiment', run.runId.replace('experiment_', ''));
    window.history.replaceState(null, '', url.pathname + url.search);
  }
  protected returnFromReplay(): void {
    this.setView(
      this.debuggerStore.hasRun() && this.debuggerStore.run().runId.startsWith('experiment_')
        ? 'experiments'
        : 'investigate',
    );
  }
  protected publicValidRateDelta(): number {
    return (
      this.local.campaign().methods.bayesian.validRatePercent -
      this.local.campaign().methods.random.validRatePercent
    );
  }
  protected onWorkspaceMode(mode: string): void {
    // setView('sensor') defaults to camera, so restore the explicit selection.
    this.setView(mode === 'planning' ? 'replay' : 'sensor');
    this.simulator.selectMode(mode as SensorMode);
  }
  protected toggleAssistant(): void {
    this.simulator.assistantOpen.update((value) => !value);
  }
  protected async openCampaignProposal(proposal: InvestigationProposal): Promise<void> {
    this.showComparison.set(false);
    this.analysis.set(undefined);
    this.analysisError.set(undefined);
    this.analysisGeneration++;
    this.showGateDetails.set(false);
    this.analysisLoading.set(false);
    try {
      await this.local.selectInvestigationProposal(proposal.cellId, proposal.proposalNumber);
      this.revealInspector();
    } catch {
      /* The connection banner exposes retry and the service error. */
    }
  }
  protected toggleCompare(proposal: InvestigationProposal): void {
    const current = [...this.comparison()];
    const index = current.findIndex(
      (candidate) =>
        candidate.cellId === proposal.cellId &&
        candidate.proposalNumber === proposal.proposalNumber,
    );
    if (index >= 0) current.splice(index, 1);
    else if (current.length < 2) current.push(proposal);
    this.comparison.set(current);
    this.openComparison();
  }
  protected openComparison(): void {
    this.showComparison.set(true);
    this.revealInspector();
  }
  private revealInspector(): void {
    requestAnimationFrame(() => {
      const tabs = document.querySelector<HTMLElement>('.inspector-tabs');
      tabs?.querySelector<HTMLButtonElement>('button[aria-pressed="true"]')?.focus({
        preventScroll: true,
      });
      if (window.innerWidth < 900) tabs?.scrollIntoView({ block: 'start', behavior: 'instant' });
    });
  }
  protected async openComparedReplay(proposal: InvestigationProposal): Promise<void> {
    if (!proposal.replayRunId) return;
    try {
      await this.local.selectInvestigationProposal(proposal.cellId, proposal.proposalNumber);
      await this.openProposalReplay(proposal.replayRunId);
    } catch {
      this.replayError.set('Could not load this proposal. Reconnect the workspace and try again.');
    }
  }
  protected formatGate(gate: string): string {
    return (
      {
        mutation_geometry: 'Scenario edit was invalid',
        scenario_validity: 'Replay became invalid',
        pipeline_reproducibility: 'Replay was not reproducible',
        empirical_support: 'Outside recorded behavior',
        reference_controller: 'Reference planner failed',
        tested_controller_failure: 'Tested planner still succeeds',
        finding_contract: 'Regression contract not met',
        qualifying_finding: 'Candidate regression',
      }[gate] ?? gate.replaceAll('_', ' ')
    );
  }
  protected mutationNarrative(proposal: {
    readonly brakingOnsetOffsetSeconds: number;
    readonly speedMultiplier: number;
  }): string {
    return `${this.signedSeconds(proposal.brakingOnsetOffsetSeconds)} onset · ${proposal.speedMultiplier.toFixed(2)}× speed`;
  }
  protected signedSeconds(value: number): string {
    return `${value >= 0 ? '+' : '−'}${Math.abs(value).toFixed(1)} s`;
  }
  protected proximityLabel(value: number): string {
    if (value <= 0) return 'Minimum clearance unavailable';
    const clearanceMeters = Math.max(1 / value - 1, 0);
    if (clearanceMeters < 0.005) return 'Contact boundary reached';
    return `${clearanceMeters.toFixed(2)} m minimum clearance`;
  }
  protected changeSizeLabel(value: number): string {
    const boundedEditPercent = Math.min(Math.max((1 - value) * 100, 0), 100);
    const size =
      boundedEditPercent <= 20 ? 'Small' : boundedEditPercent <= 50 ? 'Moderate' : 'Large';
    return `${size} edit · ${boundedEditPercent.toFixed(0)}% of bounded range`;
  }
  protected supportLabel(value: number | null, passes: boolean | null): string {
    if (value === null) return 'Not evaluated';
    return passes === true ? 'Seen in recorded behavior' : 'Outside recorded behavior';
  }
  protected async selectCell(cellId: string): Promise<void> {
    this.analysis.set(undefined);
    this.analysisError.set(undefined);
    this.analysisGeneration++;
    this.analysisLoading.set(false);
    try {
      await this.local.selectCell(cellId);
      // Select the closest evaluated proposal, which is also the default list order.
      // Keep a rejected proposal inspectable when the whole run was rejected.
      const first = [...this.local.proposals()].sort(
        (a, b) => b.criticality - a.criticality || a.proposalNumber - b.proposalNumber,
      )[0];
      if (first && this.local.selectedCellId() === cellId)
        this.local.selectProposal(first.proposalNumber);
    } catch {
      /* Service exposes the recoverable error. */
    }
  }
  protected gateReason(proposal: LocalProposal): string {
    if (proposal.attemptStatus === 'mutation_rejected') return 'Mutation gate rejected';
    if (proposal.attemptStatus === 'scenario_rejected') return 'Scenario gate rejected';
    if (!proposal.pipelinePasses) return 'Pipeline validity rejected';
    if (proposal.supportPasses !== true) return 'Empirical support rejected';
    if (!proposal.referencePasses) return 'Reference planner failed';
    if (proposal.testedMutatedFailure !== true) return 'Tested planner still succeeds';
    return proposal.policySpecificAvoidableFailure
      ? 'Qualifying finding'
      : 'Finding contract not met';
  }
  protected proposalGates(
    proposal: LocalProposal,
  ): readonly { label: string; detail: string; pass: boolean; stop: boolean }[] {
    const mutation = proposal.attemptStatus !== 'mutation_rejected';
    const scenario = mutation && proposal.attemptStatus !== 'scenario_rejected';
    const pipeline = scenario && proposal.pipelinePasses;
    const support = pipeline && proposal.supportPasses === true;
    const reference = support && proposal.referencePasses;
    const tested = reference && proposal.testedMutatedFailure === true;
    const gates = [
      {
        label: 'Mutation geometry',
        detail: mutation ? 'Bounded mutation accepted' : 'Core physical constraints rejected',
        pass: mutation,
      },
      {
        label: 'Scenario validity',
        detail: scenario
          ? 'Closed-loop scenario remained valid'
          : 'Scenario replay did not clear validity',
        pass: scenario,
      },
      {
        label: 'Reproducible replay',
        detail: pipeline
          ? 'Repeated execution produced the same sealed evidence'
          : 'Replay was not reproducible or was not evaluated',
        pass: pipeline,
      },
      {
        label: 'Empirical support',
        detail:
          proposal.empiricalSupportProbability === null
            ? 'Not evaluated'
            : proposal.supportPasses === true
              ? `Seen in recorded behavior · ${(proposal.empiricalSupportProbability * 100).toFixed(1)}% support`
              : `Outside recorded behavior · ${(proposal.empiricalSupportProbability * 100).toFixed(1)}% support`,
        pass: support,
      },
      {
        label: 'Reference planner',
        detail: reference
          ? 'Reference succeeded under the same mutation'
          : 'Not passed or not evaluated',
        pass: reference,
      },
      {
        label: 'Tested planner fails',
        detail: tested ? 'Tested planner failed' : 'Tested planner remained successful',
        pass: tested,
      },
    ];
    const firstFailure = gates.findIndex((gate) => !gate.pass);
    return gates.map((gate, index) => ({ ...gate, stop: index === firstFailure }));
  }
  protected openReplay(): void {
    this.simulator.selectMode('planning');
    // Entering a planning replay is an explicit request to inspect its evidence.
    // Re-open the panel even when the responsive layout collapsed it on startup.
    this.simulator.controlsOpen.set(true);
    this.setView('replay');
  }
  protected async openProposalReplay(runId: string): Promise<void> {
    this.replayLoading.set(true);
    this.replayError.set(undefined);
    try {
      this.debuggerStore.loadRun(await this.local.loadRun(runId));
      this.openReplay();
    } catch (error: unknown) {
      this.replayError.set(error instanceof Error ? error.message : 'Exact replay failed to load');
    } finally {
      this.replayLoading.set(false);
    }
  }
  protected async groundAnalysis(): Promise<void> {
    const generation = ++this.analysisGeneration;
    this.analysisLoading.set(true);
    this.analysisError.set(undefined);
    try {
      const cellId = this.local.selectedCellId();
      const proposalNumber = this.local.selectedProposalNumber();
      if (cellId === undefined || proposalNumber === undefined) {
        throw new Error('Select a proposal before running analysis');
      }
      const answer = await this.local.proposalAnalysis(cellId, proposalNumber);
      if (
        generation === this.analysisGeneration &&
        cellId === this.local.selectedCellId() &&
        proposalNumber === this.local.selectedProposalNumber()
      )
        this.analysis.set(answer);
    } catch (error: unknown) {
      if (generation === this.analysisGeneration)
        this.analysisError.set(error instanceof Error ? error.message : 'Analysis failed');
    } finally {
      if (generation === this.analysisGeneration) this.analysisLoading.set(false);
    }
  }
  protected async exportReport(): Promise<void> {
    const cell = this.local.selectedCell();
    const proposal = this.local.selectedProposal();
    try {
      if (cell && proposal)
        await this.reports.download({ campaign: this.local.campaign(), cell, proposal });
    } catch (error: unknown) {
      this.analysisError.set(error instanceof Error ? error.message : 'Export failed');
    }
  }
}
