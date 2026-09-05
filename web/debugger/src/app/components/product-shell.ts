import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  output,
  signal,
} from '@angular/core';
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
import { DebuggerRun } from '../debugger.types';

type ProductView = 'operations' | 'investigate' | 'replay' | 'sensor' | 'experiments';
type EvidenceView = 'campaign' | 'deployment';
type ProposalSort = 'criticality' | 'minimality' | 'support' | 'sequence';
type ProposalFilter = 'all' | 'eligible' | 'support-rejected' | 'pipeline-rejected';
type InvestigationRank = 'closest' | 'minimal' | 'support';

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
            <div class="investigation-layout" [class.browsing-cells]="browseCells()">
              @if (local.investigation(); as campaign) {
                <section class="campaign-index" aria-labelledby="campaign-index-title">
                  <header>
                    <div>
                      <p>
                        {{
                          browseCells()
                            ? 'Explore every search run'
                            : 'Start with the smallest margins'
                        }}
                      </p>
                      <h2 id="campaign-index-title">Scenario changes</h2>
                    </div>
                    <div class="rank-tabs" aria-label="Campaign ranking">
                      <button
                        type="button"
                        [class.active]="rank() === 'closest'"
                        (click)="rank.set('closest')"
                      >
                        Closest to failure
                      </button>
                      <button
                        type="button"
                        [class.active]="rank() === 'minimal'"
                        (click)="rank.set('minimal')"
                      >
                        Smallest change
                      </button>
                      <button
                        type="button"
                        [class.active]="rank() === 'support'"
                        (click)="rank.set('support')"
                      >
                        Strongest precedent
                      </button>
                    </div>
                  </header>
                  <div class="queue-controls">
                    <p>
                      {{
                        rank() === 'closest'
                          ? 'Closest approaches first. A small gap alone does not qualify as a planner failure.'
                          : rank() === 'minimal'
                            ? 'Smallest edits first, under the same realism and reproducibility gates.'
                            : 'Changes with the strongest support in recorded driving behavior.'
                      }}
                    </p>
                    <button
                      type="button"
                      [attr.aria-expanded]="browseCells()"
                      (click)="browseCells.set(!browseCells())"
                    >
                      {{ browseCells() ? 'Back to priority queue' : 'Browse all 100 search runs' }}
                    </button>
                  </div>
                  @if (!browseCells()) {
                    <div class="campaign-table" role="table" aria-label="Campaign-ranked proposals">
                      <div class="campaign-row campaign-head" role="row">
                        <span role="columnheader">Scenario / change</span>
                        <span role="columnheader">Minimum gap</span>
                        <span role="columnheader">Review</span>
                      </div>
                      @for (
                        proposal of campaignRanking();
                        track proposal.cellId + proposal.proposalNumber;
                        let index = $index
                      ) {
                        <div
                          class="campaign-row"
                          role="row"
                          [class.selected]="isSelected(proposal)"
                        >
                          <span role="cell" class="case-summary">
                            <strong
                              >Scenario {{ proposal.selectionOrder }}
                              <small
                                >{{ proposal.method }} · #{{ proposal.proposalNumber }}</small
                              ></strong
                            >
                            <span>{{ mutationNarrative(proposal) }}</span>
                            <small>{{ formatGate(proposal.decisiveGate) }}</small>
                          </span>
                          <span role="cell" class="gap-value"
                            >{{ clearanceValue(proposal.criticality)
                            }}<small>{{
                              proposal.trajectoryAvailable ? 'Replay available' : 'Metrics only'
                            }}</small></span
                          >
                          <span role="cell" class="row-actions">
                            <button
                              type="button"
                              [attr.aria-label]="
                                'Inspect ' +
                                proposal.method +
                                ' scenario ' +
                                proposal.selectionOrder +
                                ' seed ' +
                                proposal.seed +
                                ' proposal ' +
                                proposal.proposalNumber
                              "
                              (click)="openCampaignProposal(proposal)"
                            >
                              {{ isSelected(proposal) ? 'Selected' : 'Inspect' }}
                            </button>
                            <button
                              type="button"
                              [attr.aria-pressed]="isCompared(proposal)"
                              (click)="toggleCompare(proposal)"
                            >
                              {{ isCompared(proposal) ? 'Remove' : 'Compare' }}
                            </button>
                          </span>
                        </div>
                      }
                    </div>
                  }
                  @if (comparison().length > 0) {
                    <section class="comparison-dock" aria-label="Proposal comparison">
                      <header>
                        <strong>Comparison · {{ comparison().length }}/2</strong
                        ><button type="button" (click)="comparison.set([])">Clear</button>
                      </header>
                      <div>
                        @for (
                          proposal of comparison();
                          track proposal.cellId + proposal.proposalNumber
                        ) {
                          <article>
                            <span
                              >{{ proposal.method }} · S{{ proposal.selectionOrder }} · seed
                              {{ proposal.seed }}</span
                            >
                            <h3>Proposal {{ proposal.proposalNumber }}</h3>
                            <dl>
                              <div>
                                <dt>Safety result</dt>
                                <dd>{{ proximityLabel(proposal.criticality) }}</dd>
                              </div>
                              <div>
                                <dt>Change size</dt>
                                <dd>{{ changeSizeLabel(proposal.minimality) }}</dd>
                              </div>
                              <div>
                                <dt>Recorded precedent</dt>
                                <dd>
                                  {{
                                    supportLabel(
                                      proposal.empiricalSupportProbability,
                                      proposal.supportPasses
                                    )
                                  }}
                                </dd>
                              </div>
                              <div>
                                <dt>Why it stopped</dt>
                                <dd>{{ formatGate(proposal.decisiveGate) }}</dd>
                              </div>
                            </dl>
                            <button type="button" (click)="openCampaignProposal(proposal)">
                              Open evidence
                            </button>
                          </article>
                        }
                      </div>
                    </section>
                  }
                </section>
              }
              <section class="investigation-workspace">
                @if (browseCells()) {
                  <aside class="cell-rail" aria-labelledby="cell-matrix-title">
                    <div class="rail-heading">
                      <h2 id="cell-matrix-title">100 matched cells</h2>
                      <span>scenario × seed × method</span>
                    </div>
                    <label class="run-picker"
                      >Search run
                      <select [value]="local.selectedCellId()" (change)="changeCell($event)">
                        @for (cell of local.cells(); track cell.cellId) {
                          <option [value]="cell.cellId">
                            Scenario {{ cell.selectionOrder }} · {{ cell.method }} · seed
                            {{ cell.seed }}
                          </option>
                        }
                      </select>
                    </label>
                    <details class="run-matrix">
                      <summary>Show run matrix</summary>
                      <div class="cell-legend">
                        <span><i class="random"></i>Random</span
                        ><span><i class="bayesian"></i>Bayesian</span>
                      </div>
                      <div class="cell-grid">
                        @for (cell of local.cells(); track cell.cellId) {
                          <button
                            type="button"
                            [class.random]="cell.method === 'random'"
                            [class.bayesian]="cell.method === 'bayesian'"
                            [class.active]="local.selectedCellId() === cell.cellId"
                            [style.--validity]="cell.validRatePercent + '%'"
                            [attr.aria-label]="
                              cell.method +
                              ' scenario ' +
                              cell.selectionOrder +
                              ' seed ' +
                              cell.seed +
                              ', ' +
                              cell.validRatePercent.toFixed(1) +
                              ' percent eligible'
                            "
                            [attr.title]="
                              cell.method +
                              ' · scenario ' +
                              cell.selectionOrder +
                              ' · seed ' +
                              cell.seed
                            "
                            (click)="selectCell(cell.cellId)"
                          >
                            {{ cell.selectionOrder }}·{{ cell.seed }}
                          </button>
                        }
                      </div>
                    </details>
                    @if (local.selectedCell(); as cell) {
                      <dl class="cell-summary">
                        <div>
                          <dt>Selected</dt>
                          <dd>
                            {{ cell.method }} · S{{ cell.selectionOrder }} · seed {{ cell.seed }}
                          </dd>
                        </div>
                        <div>
                          <dt>Pipeline valid</dt>
                          <dd>{{ cell.pipelineValidCount }} / 32</dd>
                        </div>
                        <div>
                          <dt>Support + pipeline</dt>
                          <dd>{{ cell.supportAndPipelineValidCount }} / 32</dd>
                        </div>
                        <div>
                          <dt>Past realism gates</dt>
                          <dd>
                            {{ cell.supportAndPipelineValidCount }} / {{ cell.proposalCount }}
                          </dd>
                        </div>
                      </dl>
                    }
                  </aside>
                }
                <section class="proposal-region">
                  @if (browseCells()) {
                    <div class="proposal-toolbar">
                      <div>
                        <h2>Proposal evidence</h2>
                        <p>Rank the selected cell without changing its sealed sequence.</p>
                      </div>
                      <div class="toolbar-filters">
                        <label
                          >Show
                          <select [value]="filter()" (change)="changeFilter($event)">
                            <option value="all">All proposals</option>
                            <option value="eligible">All feasibility gates</option>
                            <option value="support-rejected">Support rejected</option>
                            <option value="pipeline-rejected">Pipeline rejected</option>
                          </select>
                        </label>
                        <label
                          >Rank by
                          <select [value]="sort()" (change)="changeSort($event)">
                            <option value="criticality">Closest safety margin</option>
                            <option value="minimality">Smallest mutation</option>
                            <option value="support">Highest support</option>
                            <option value="sequence">Original sequence</option>
                          </select>
                        </label>
                      </div>
                    </div>

                    <div class="gate-funnel" aria-label="Selected cell gate funnel">
                      @for (gate of funnel(); track gate.label) {
                        <div>
                          <strong>{{ gate.count }}</strong
                          ><span>{{ gate.label }}</span
                          ><i [style.width.%]="(gate.count / 32) * 100"></i>
                        </div>
                      }
                    </div>
                  }
                  <div class="proposal-layout" [class.with-list]="browseCells()">
                    @if (browseCells()) {
                      <div class="proposal-list" aria-label="Ranked proposal list">
                        @if (local.loadingProposals()) {
                          <p>Verifying 32 proposal seals…</p>
                        }
                        @for (proposal of rankedProposals(); track proposal.proposalNumber) {
                          <button
                            type="button"
                            [class.active]="
                              local.selectedProposalNumber() === proposal.proposalNumber
                            "
                            (click)="selectProposal(proposal.proposalNumber)"
                          >
                            <span>#{{ proposal.proposalNumber.toString().padStart(2, '0') }}</span>
                            <div>
                              <strong>{{ proposalTitle(proposal) }}</strong
                              ><small>{{ gateReason(proposal) }}</small>
                            </div>
                            <b>{{ rankValue(proposal) }}</b>
                          </button>
                        }
                      </div>
                    }
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
                            <span>Safety result</span
                            ><strong>{{ proximityLabel(proposal.criticality) }}</strong>
                          </div>
                          <div>
                            <span>Change size</span
                            ><strong>{{ changeSizeLabel(proposal.minimality) }}</strong>
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
                          } @else {
                            <strong>Proposal trajectory is not retained.</strong>
                            <p>
                              This change has verified outcomes and metrics. Its full trajectory was
                              not saved. Choose a row marked “Replay available” to inspect a saved
                              path.
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
                            <ng-icon name="phosphorDownloadSimple" size="15" />Export investigation
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
  protected readonly sort = signal<ProposalSort>('criticality');
  protected readonly filter = signal<ProposalFilter>('all');
  protected readonly rank = signal<InvestigationRank>('closest');
  protected readonly comparison = signal<readonly InvestigationProposal[]>([]);
  protected readonly analysis = signal<ProposalAnalysis | undefined>(undefined);
  protected readonly analysisLoading = signal(false);
  protected readonly analysisError = signal<string | undefined>(undefined);
  protected readonly replayLoading = signal(false);
  protected readonly replayError = signal<string | undefined>(undefined);
  protected readonly browseCells = signal(false);
  protected readonly showGateDetails = signal(false);
  private analysisGeneration = 0;

  protected isSelected(proposal: InvestigationProposal): boolean {
    return (
      this.local.selectedCellId() === proposal.cellId &&
      this.local.selectedProposalNumber() === proposal.proposalNumber
    );
  }
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

  protected readonly rankedProposals = computed(() => {
    const proposals = this.local.proposals().filter((proposal) => {
      if (this.filter() === 'eligible') {
        return (
          proposal.pipelinePasses && proposal.supportPasses === true && proposal.referencePasses
        );
      }
      if (this.filter() === 'support-rejected') {
        return proposal.pipelinePasses && proposal.supportPasses === false;
      }
      if (this.filter() === 'pipeline-rejected') return !proposal.pipelinePasses;
      return true;
    });
    return proposals.sort((a, b) => {
      if (this.sort() === 'sequence') return a.proposalNumber - b.proposalNumber;
      if (this.sort() === 'minimality')
        return b.minimality - a.minimality || b.criticality - a.criticality;
      if (this.sort() === 'support')
        return (
          (b.empiricalSupportProbability ?? -1) - (a.empiricalSupportProbability ?? -1) ||
          b.criticality - a.criticality
        );
      return b.criticality - a.criticality || b.minimality - a.minimality;
    });
  });
  protected readonly funnel = computed(() => {
    const proposals = this.local.proposals();
    return [
      { label: 'proposed', count: proposals.length },
      { label: 'pipeline valid', count: proposals.filter((p) => p.pipelinePasses).length },
      {
        label: 'support valid',
        count: proposals.filter((p) => p.pipelinePasses && p.supportPasses === true).length,
      },
      {
        label: 'reference passes',
        count: proposals.filter(
          (p) => p.pipelinePasses && p.supportPasses === true && p.referencePasses,
        ).length,
      },
      {
        label: 'tested fails',
        count: proposals.filter((p) => p.testedMutatedFailure === true).length,
      },
    ];
  });

  protected readonly campaignRanking = computed(() => {
    const investigation = this.local.investigation();
    if (investigation === undefined) return [];
    if (this.rank() === 'minimal') return investigation.smallestMutation;
    if (this.rank() === 'support') return investigation.highestSupport;
    return investigation.closestMargin;
  });

  protected setView(view: ProductView): void {
    if (view === 'replay') this.simulator.selectMode('planning');
    if (view === 'sensor') this.simulator.selectMode('camera');
    this.view.set(view);
    window.scrollTo({ top: 0, behavior: 'instant' });
    const url = new URL(window.location.href);
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
    this.analysis.set(undefined);
    this.analysisError.set(undefined);
    this.analysisGeneration++;
    this.showGateDetails.set(false);
    this.analysisLoading.set(false);
    try {
      await this.local.selectInvestigationProposal(proposal.cellId, proposal.proposalNumber);
      if (window.innerWidth < 900)
        document
          .querySelector('.proposal-region')
          ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
    else current.splice(0, 1, proposal);
    this.comparison.set(current);
  }
  protected isCompared(proposal: InvestigationProposal): boolean {
    return this.comparison().some(
      (candidate) =>
        candidate.cellId === proposal.cellId &&
        candidate.proposalNumber === proposal.proposalNumber,
    );
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
    } catch {
      /* Service exposes the recoverable error. */
    }
  }
  protected selectProposal(proposalNumber: number): void {
    this.analysisGeneration++;
    this.analysisLoading.set(false);
    this.analysis.set(undefined);
    this.analysisError.set(undefined);
    this.local.selectProposal(proposalNumber);
  }
  protected changeSort(event: Event): void {
    this.sort.set((event.target as HTMLSelectElement).value as ProposalSort);
  }
  protected changeCell(event: Event): void {
    void this.selectCell((event.target as HTMLSelectElement).value);
  }
  protected changeFilter(event: Event): void {
    this.filter.set((event.target as HTMLSelectElement).value as ProposalFilter);
  }
  protected proposalTitle(proposal: LocalProposal): string {
    return proposal.objectiveAvailable
      ? this.mutationNarrative(proposal)
      : proposal.attemptStatus.replaceAll('_', ' ');
  }
  protected rankValue(proposal: LocalProposal): string {
    if (this.sort() === 'sequence') return `#${proposal.proposalNumber}`;
    if (this.sort() === 'minimality') return this.changeSizeLabel(proposal.minimality);
    if (this.sort() === 'support') {
      return this.supportLabel(proposal.empiricalSupportProbability, proposal.supportPasses);
    }
    return this.proximityLabel(proposal.criticality);
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
