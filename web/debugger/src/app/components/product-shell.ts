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
import { SimulatorStore } from '../simulator.store';
import { SimulatorWorkspace } from './simulator-workspace';

type ProductView = 'investigate' | 'replay' | 'sensor';
type ProposalSort = 'criticality' | 'minimality' | 'support' | 'sequence';
type ProposalFilter = 'all' | 'eligible' | 'support-rejected' | 'pipeline-rejected';
type InvestigationRank = 'closest' | 'minimal' | 'support';

@Component({
  selector: 'app-product-shell',
  imports: [NgIcon, SimulatorWorkspace],
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
        <button class="brand" type="button" (click)="setView('replay')">
          <ng-icon name="phosphorStack" size="23" aria-hidden="true" />
          <strong>PlanMargin</strong>
        </button>
        <nav aria-label="Product sections">
          <button type="button" [class.active]="view() === 'replay'" (click)="setView('replay')">
            Workbench
          </button>
          <button type="button" [class.active]="view() === 'sensor'" (click)="setView('sensor')">
            Sensors
          </button>
          <button
            type="button"
            [class.active]="view() === 'investigate'"
            (click)="setView('investigate')"
          >
            Evidence
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
            <ng-icon name="phosphorSparkle" size="15" />Ask analysis
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
                  ? 'Local records verified'
                  : local.state() === 'connecting'
                    ? 'Verifying local records…'
                    : 'Open local workspace'
              }}
            </button>
          }
        </div>
      </header>

      @if (view() === 'investigate') {
        <main class="investigation-page">
          <header class="page-heading">
            <div>
              <p>Candidate review</p>
              <h1>Review planner regressions by the reason they stopped.</h1>
            </div>
            <div class="page-status" [class.connected]="local.connected()">
              <i></i
              >{{ local.connected() ? 'Sealed local records verified' : 'Local records required' }}
            </div>
          </header>

          @if (!local.connected()) {
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
              <section class="model-evidence" aria-labelledby="model-evidence-title">
                <header>
                  <div>
                    <span>Real WOMD trajectory model</span>
                    <h3 id="model-evidence-title">
                      A deployable predictor that beats its baseline.
                    </h3>
                  </div>
                  <b>{{ local.campaign().trajectoryModel.status }}</b>
                </header>
                <div class="model-metrics">
                  <div>
                    <span>Sealed corpus</span>
                    <strong>{{ local.campaign().trajectoryModel.scenarios }}</strong>
                    <small
                      >{{
                        local.campaign().trajectoryModel.windows.toLocaleString()
                      }}
                      windows</small
                    >
                  </div>
                  <div>
                    <span>Test ADE</span>
                    <strong>{{ local.campaign().trajectoryModel.adeMeters.toFixed(3) }} m</strong>
                    <small
                      >baseline
                      {{ local.campaign().trajectoryModel.baselineAdeMeters.toFixed(3) }} m</small
                    >
                  </div>
                  <div>
                    <span>Test FDE</span>
                    <strong>{{ local.campaign().trajectoryModel.fdeMeters.toFixed(3) }} m</strong>
                    <small
                      >baseline
                      {{ local.campaign().trajectoryModel.baselineFdeMeters.toFixed(3) }} m</small
                    >
                  </div>
                  <div>
                    <span>Held-out evidence</span>
                    <strong>{{
                      local.campaign().trajectoryModel.testWindows.toLocaleString()
                    }}</strong>
                    <small>complete-scenario test windows</small>
                  </div>
                </div>
                <p>
                  Two-layer temporal Conv1d residual network · PyTorch → ONNX → TensorRT · aggregate
                  metrics only
                </p>
              </section>
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
            @if (local.investigation(); as campaign) {
              <section class="campaign-index" aria-labelledby="campaign-index-title">
                <header>
                  <div>
                    <p>Verified campaign index</p>
                    <h2 id="campaign-index-title">Review queue</h2>
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
                <div class="campaign-funnel" aria-label="Campaign-wide gate funnel">
                  <div>
                    <strong>{{ campaign.funnel.proposed }}</strong
                    ><span>proposed</span>
                  </div>
                  <div>
                    <strong>{{ campaign.funnel.scenarioValid }}</strong
                    ><span>scenario valid</span>
                  </div>
                  <div>
                    <strong>{{ campaign.funnel.pipelineValid }}</strong
                    ><span>deterministic</span>
                  </div>
                  <div>
                    <strong>{{ campaign.funnel.supportValid }}</strong
                    ><span>supported</span>
                  </div>
                  <div>
                    <strong>{{ campaign.funnel.referencePasses }}</strong
                    ><span>reference pass</span>
                  </div>
                  <div>
                    <strong>{{ campaign.funnel.testedFails }}</strong
                    ><span>tested fail</span>
                  </div>
                  <div class="terminal">
                    <strong>{{ campaign.funnel.qualifyingFindings }}</strong
                    ><span>findings</span>
                  </div>
                </div>
                <div class="campaign-table" role="table" aria-label="Campaign-ranked proposals">
                  <div class="campaign-row campaign-head" role="row">
                    <span>Rank</span><span>Case</span><span>Change</span><span>Safety result</span
                    ><span>Recorded precedent</span><span>Why it stopped</span><span></span>
                  </div>
                  @for (
                    proposal of campaignRanking();
                    track proposal.cellId + proposal.proposalNumber;
                    let index = $index
                  ) {
                    <div class="campaign-row" role="row">
                      <span>{{ index + 1 }}</span>
                      <span class="method" [class.bayesian]="proposal.method === 'bayesian'">
                        {{ proposal.method }} · S{{ proposal.selectionOrder }} · {{ proposal.seed }}
                      </span>
                      <span>{{ mutationNarrative(proposal) }}</span>
                      <span>{{ proximityLabel(proposal.criticality) }}</span>
                      <span>{{
                        supportLabel(proposal.empiricalSupportProbability, proposal.supportPasses)
                      }}</span>
                      <span>{{ formatGate(proposal.decisiveGate) }}</span>
                      <span class="row-actions">
                        <button type="button" (click)="openCampaignProposal(proposal)">
                          Inspect
                        </button>
                        <button type="button" (click)="toggleCompare(proposal)">
                          {{ isCompared(proposal) ? 'Remove' : 'Compare' }}
                        </button>
                      </span>
                    </div>
                  }
                </div>
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
              <aside class="cell-rail" aria-labelledby="cell-matrix-title">
                <div class="rail-heading">
                  <h2 id="cell-matrix-title">100 matched cells</h2>
                  <span>scenario × seed × method</span>
                </div>
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
                      (click)="selectCell(cell.cellId)"
                    ></button>
                  }
                </div>
                @if (local.selectedCell(); as cell) {
                  <dl class="cell-summary">
                    <div>
                      <dt>Selected</dt>
                      <dd>{{ cell.method }} · S{{ cell.selectionOrder }} · seed {{ cell.seed }}</dd>
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
                      <dd>{{ cell.supportAndPipelineValidCount }} / {{ cell.proposalCount }}</dd>
                    </div>
                  </dl>
                }
              </aside>

              <section class="proposal-region">
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

                <div class="proposal-layout">
                  <div class="proposal-list" aria-label="Ranked proposal list">
                    @if (local.loadingProposals()) {
                      <p>Verifying 32 proposal seals…</p>
                    }
                    @for (proposal of rankedProposals(); track proposal.proposalNumber) {
                      <button
                        type="button"
                        [class.active]="local.selectedProposalNumber() === proposal.proposalNumber"
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

                  @if (local.selectedProposal(); as proposal) {
                    <article class="proposal-detail">
                      <header>
                        <div>
                          <p>Proposal {{ proposal.proposalNumber }}</p>
                          <h2>{{ gateReason(proposal) }}</h2>
                        </div>
                        <span [class.finding]="proposal.policySpecificAvoidableFailure">{{
                          proposal.attemptStatus.replaceAll('_', ' ')
                        }}</span>
                      </header>
                      <div class="parameter-strip">
                        <div>
                          <span>Braking onset shift</span
                          ><strong>{{ signedSeconds(proposal.brakingOnsetOffsetSeconds) }}</strong>
                        </div>
                        <div>
                          <span>Lead speed scale</span
                          ><strong>{{ proposal.speedMultiplier.toFixed(4) }}</strong>
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
                      <div class="replay-boundary">
                        @if (proposal.trajectoryAvailable && proposal.replayRunId) {
                          <strong>Exact proposal replay retained and verified.</strong>
                          <p>
                            This proposal was re-executed from its authorized WOMD source. Fresh
                            tested and reference trajectories match the sealed v1 trajectory hashes.
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
                            The frozen campaign kept trajectory hashes, outcomes, objectives, and
                            cost. It did not keep every full path. The available Stage-0 replay is
                            separate evidence and is labeled as such.
                          </p>
                          <button type="button" (click)="openReplay()">
                            <ng-icon name="phosphorPlay" size="15" />Open separate Stage-0 replay
                          </button>
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
                          <ng-icon name="phosphorDownloadSimple" size="15" />Export signed HTML
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
          }
        </main>
      } @else if (!local.connected()) {
        <main class="locked-workspace">
          <div>
            <span>{{
              view() === 'sensor' ? 'Recorded sensor lab' : 'Planning replay workbench'
            }}</span>
            <h1>
              {{
                view() === 'sensor'
                  ? 'Inspect real camera, LiDAR, and 3DGS locally.'
                  : 'Replay sealed planner evidence locally.'
              }}
            </h1>
            <p>
              This surface requires the licensed records on the engineer's machine. The public
              campaign analysis remains available without them.
            </p>
            <div>
              @if (publicHosted) {
                <a class="primary" [href]="repositoryUrl">Clone for local workspace</a>
              } @else {
                <button class="primary" type="button" (click)="connectRequested.emit()">
                  Open local workspace
                </button>
              }
              <button type="button" (click)="setView('investigate')">Review public evidence</button>
            </div>
          </div>
          <dl>
            <div>
              <dt>Public proposals</dt>
              <dd>{{ local.campaign().proposals.toLocaleString() }}</dd>
            </div>
            <div>
              <dt>Physical rollouts</dt>
              <dd>{{ local.campaign().physicalRollouts.toLocaleString() }}</dd>
            </div>
            <div>
              <dt>Synthetic substitutes</dt>
              <dd>None</dd>
            </div>
          </dl>
        </main>
      } @else {
        <app-simulator-workspace
          class="embedded-simulator"
          [embedded]="true"
          (connectRequested)="connectRequested.emit()"
          (evidenceRequested)="setView('investigate')"
        />
      }
    </div>
  `,
  styles: `
    :host {
      display: block;
      min-height: 100dvh;
      background: var(--app-bg);
      color: var(--primary);
    }
    button,
    select {
      font-family: inherit;
    }
    .product-shell {
      min-height: 100dvh;
    }
    .product-header {
      position: sticky;
      z-index: 80;
      top: 0;
      display: grid;
      grid-template-columns: 220px minmax(0, 1fr) 220px;
      align-items: center;
      min-height: 64px;
      padding: 0 1.4rem;
      border-bottom: 1px solid var(--divider);
      background: rgb(7 16 24 / 94%);
      backdrop-filter: blur(16px);
    }
    .header-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 0.5rem;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 0.65rem;
      width: max-content;
      padding: 0;
      border: 0;
      background: transparent;
      color: var(--primary);
    }
    .brand ng-icon {
      color: var(--reference);
    }
    .brand strong {
      font-size: 0.92rem;
      letter-spacing: -0.025em;
    }
    .product-header nav {
      display: flex;
      align-self: stretch;
      justify-content: center;
      gap: 1.7rem;
    }
    .product-header nav button {
      position: relative;
      border: 0;
      background: transparent;
      color: var(--secondary);
      font-size: 0.69rem;
      font-weight: 650;
    }
    .product-header nav button.active {
      color: var(--primary);
    }
    .product-header nav button.active:after {
      position: absolute;
      right: 0;
      bottom: 0;
      left: 0;
      height: 2px;
      background: var(--reference);
      content: '';
    }
    .connection,
    .assistant-launch {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.45rem;
      min-height: 34px;
      padding: 0 0.75rem;
      border: 1px solid var(--divider);
      border-radius: 4px;
      background: var(--surface-subtle);
      color: var(--secondary);
      font-size: 0.63rem;
      text-decoration: none;
    }
    .assistant-launch {
      color: var(--primary);
      white-space: nowrap;
    }
    .assistant-launch ng-icon {
      color: var(--reference);
    }
    .assistant-launch:hover,
    .assistant-launch.active {
      border-color: var(--reference);
      background: rgb(53 197 211 / 10%);
    }
    .assistant-launch:disabled {
      cursor: not-allowed;
      opacity: 0.45;
    }
    .connection i,
    .page-status i {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--tested);
    }
    .connection.connected {
      color: #9be4b8;
    }
    .connection.connected i,
    .page-status.connected i {
      background: var(--success);
    }
    .connection.connecting i {
      background: #f0a33b;
      animation: connection-pulse 1s ease-in-out infinite alternate;
    }
    @keyframes connection-pulse {
      to {
        opacity: 0.35;
      }
    }
    .page-heading p,
    .proposal-detail header p {
      margin: 0 0 0.75rem;
      color: var(--reference);
      font-size: 0.61rem;
      font-weight: 750;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    .page-heading h1 {
      max-width: 760px;
      margin: 0;
      font-size: clamp(2.35rem, 5vw, 4.8rem);
      font-weight: 520;
      line-height: 0.98;
      letter-spacing: -0.06em;
    }
    .primary,
    .detail-actions button,
    .replay-boundary button {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.45rem;
      min-height: 42px;
      padding: 0 1rem;
      border: 1px solid var(--divider-strong);
      border-radius: 5px;
      background: transparent;
      color: var(--primary);
      font-size: 0.69rem;
      font-weight: 650;
    }
    .primary {
      border-color: var(--tested);
      background: var(--tested);
      color: #071218;
    }
    .investigation-page {
      min-height: calc(100dvh - 64px);
      padding: 1.7rem;
    }
    .page-heading {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 2rem;
      padding: 0 0 1.5rem;
    }
    .page-heading p {
      margin-bottom: 0.45rem;
    }
    .page-heading h1 {
      font-size: clamp(1.65rem, 3vw, 2.5rem);
      line-height: 1.05;
    }
    .page-status {
      display: flex;
      align-items: center;
      gap: 0.45rem;
      color: var(--secondary);
      font-size: 0.62rem;
    }
    .public-workbench {
      border: 1px solid var(--divider);
      background: var(--surface);
    }
    .public-kpis {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      border-bottom: 1px solid var(--divider);
    }
    .public-kpis div {
      display: grid;
      gap: 0.28rem;
      padding: 1.2rem 1.5rem;
      border-right: 1px solid var(--divider);
    }
    .public-kpis div:last-child {
      border-right: 0;
    }
    .public-kpis strong {
      font-size: 1.3rem;
      font-weight: 560;
      letter-spacing: -0.035em;
    }
    .public-kpis span,
    .method-card small {
      color: var(--secondary);
      font-size: 0.58rem;
    }
    .public-analysis {
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(310px, 0.8fr);
    }
    .method-card,
    .decision-card {
      padding: 1.5rem;
    }
    .method-card {
      border-right: 1px solid var(--divider);
    }
    .method-card > header,
    .decision-card > header {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 1.2rem;
    }
    .method-card header span,
    .decision-card header span {
      color: var(--reference);
      font-size: 0.56rem;
      font-weight: 750;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }
    .method-card h3,
    .decision-card h3 {
      margin: 0.3rem 0 0;
      font-size: 1rem;
      font-weight: 600;
    }
    .method-row {
      display: grid;
      grid-template-columns: 145px minmax(100px, 1fr) 62px;
      align-items: center;
      gap: 0.8rem;
      min-height: 56px;
      border-top: 1px solid var(--divider);
    }
    .method-row > div:first-child {
      display: grid;
      gap: 0.18rem;
    }
    .method-row strong,
    .method-row b {
      font-size: 0.68rem;
    }
    .method-row span {
      color: var(--secondary);
      font-size: 0.55rem;
    }
    .method-row b {
      text-align: right;
    }
    .method-row .bar {
      height: 8px;
      overflow: hidden;
      border-radius: 1px;
      background: #14232d;
    }
    .method-row .bar i {
      display: block;
      height: 100%;
      background: #7b8c96;
    }
    .method-row.bayesian .bar i {
      background: var(--reference);
    }
    .method-finding {
      margin: 0.9rem 0 0;
      padding: 0.8rem;
      border-left: 2px solid var(--reference);
      background: rgb(53 197 211 / 6%);
      color: var(--secondary);
      font-size: 0.63rem;
      line-height: 1.55;
    }
    .method-finding strong {
      color: var(--primary);
    }
    .decision-card dl {
      margin: 0;
      border: 1px solid var(--divider);
    }
    .decision-card dl div {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 48px;
      padding: 0 0.8rem;
      border-bottom: 1px solid var(--divider);
    }
    .decision-card dl div:last-child {
      border-bottom: 0;
    }
    .decision-card dt,
    .decision-card dd {
      font-size: 0.62rem;
    }
    .decision-card dd {
      margin: 0;
      padding: 0.22rem 0.45rem;
      border-radius: 3px;
    }
    .decision-card dd.neutral {
      background: #202a31;
      color: #aab6bd;
    }
    .decision-card dd.supported {
      background: rgb(86 217 138 / 12%);
      color: #7be5a6;
    }
    .model-evidence {
      padding: 1.5rem;
      border-top: 1px solid var(--divider);
      background: linear-gradient(100deg, rgb(53 197 211 / 5%), transparent 55%);
    }
    .model-evidence > header {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 1rem;
    }
    .model-evidence header span {
      color: var(--reference);
      font-size: 0.56rem;
      font-weight: 750;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }
    .model-evidence h3 {
      margin: 0.3rem 0 0;
      font-size: 1rem;
      font-weight: 600;
    }
    .model-evidence header b {
      color: #7be5a6;
      font-size: 0.58rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .model-metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      border: 1px solid var(--divider);
    }
    .model-metrics div {
      display: grid;
      gap: 0.28rem;
      padding: 1rem;
      border-right: 1px solid var(--divider);
    }
    .model-metrics div:last-child {
      border-right: 0;
    }
    .model-metrics span,
    .model-metrics small,
    .model-evidence > p {
      color: var(--secondary);
      font-size: 0.56rem;
    }
    .model-metrics strong {
      font-size: 1.05rem;
      font-weight: 600;
    }
    .model-evidence > p {
      margin: 0.8rem 0 0;
    }
    .public-boundary {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      border-top: 1px solid var(--divider);
    }
    .public-boundary div {
      padding: 1rem 1.5rem;
    }
    .public-boundary div:first-child {
      border-right: 1px solid var(--divider);
    }
    .locked-workspace {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 300px;
      align-items: center;
      min-height: calc(100dvh - 64px);
      gap: 4rem;
      padding: clamp(2rem, 8vw, 8rem);
      background:
        linear-gradient(120deg, rgb(7 16 24 / 96%), rgb(7 16 24 / 82%)),
        radial-gradient(circle at 75% 40%, rgb(53 197 211 / 16%), transparent 36%);
    }
    .locked-workspace > div > span {
      color: var(--reference);
      font-size: 0.6rem;
      font-weight: 750;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }
    .locked-workspace h1 {
      max-width: 760px;
      margin: 0.7rem 0;
      font-size: clamp(2rem, 5vw, 4.4rem);
      font-weight: 520;
      line-height: 0.98;
      letter-spacing: -0.055em;
    }
    .locked-workspace p {
      max-width: 620px;
      color: var(--secondary);
      font-size: 0.72rem;
      line-height: 1.7;
    }
    .locked-workspace > div > div {
      display: flex;
      gap: 0.6rem;
      margin-top: 1.4rem;
    }
    .locked-workspace > div > div > button:not(.primary) {
      min-height: 42px;
      padding: 0 1rem;
      border: 1px solid var(--divider-strong);
      border-radius: 5px;
      background: transparent;
      color: var(--primary);
      font-size: 0.69rem;
    }
    .locked-workspace > dl {
      margin: 0;
      border: 1px solid var(--divider);
      background: rgb(9 20 29 / 80%);
    }
    .locked-workspace > dl div {
      display: flex;
      justify-content: space-between;
      padding: 1rem;
      border-bottom: 1px solid var(--divider);
    }
    .locked-workspace > dl div:last-child {
      border-bottom: 0;
    }
    .locked-workspace dt,
    .locked-workspace dd {
      font-size: 0.65rem;
    }
    .locked-workspace dt {
      color: var(--secondary);
    }
    .locked-workspace dd {
      margin: 0;
      font-weight: 650;
    }
    .public-result {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 2rem;
      padding: clamp(1.5rem, 4vw, 3rem);
      border-bottom: 1px solid var(--divider);
    }
    .public-result span,
    .campaign-index > header p {
      color: var(--reference);
      font-size: 0.58rem;
      font-weight: 750;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }
    .public-result h2 {
      margin: 0.5rem 0;
      font-size: clamp(1.3rem, 2.5vw, 2rem);
      font-weight: 560;
      letter-spacing: -0.035em;
    }
    .public-result p,
    .public-boundary p {
      max-width: 700px;
      margin: 0;
      color: var(--secondary);
      font-size: 0.7rem;
      line-height: 1.6;
    }
    .public-boundary {
      display: grid;
      grid-template-columns: 170px 1fr;
      gap: 1rem;
      padding: 1rem 1.4rem;
      border: 1px solid var(--divider);
      border-width: 1px 0 0;
      background: #0c1820;
      font-size: 0.65rem;
    }
    .campaign-index {
      margin-bottom: 1rem;
      border: 1px solid var(--divider);
      background: var(--surface);
    }
    .campaign-index > header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      padding: 1rem 1.2rem;
      border-bottom: 1px solid var(--divider);
    }
    .campaign-index > header p {
      margin: 0 0 0.3rem;
    }
    .campaign-index > header h2 {
      margin: 0;
      font-size: 1rem;
    }
    .rank-tabs {
      display: flex;
      border: 1px solid var(--divider);
    }
    .rank-tabs button {
      min-height: 32px;
      padding: 0 0.75rem;
      border: 0;
      border-right: 1px solid var(--divider);
      background: transparent;
      color: var(--secondary);
      font-size: 0.58rem;
    }
    .rank-tabs button:last-child {
      border-right: 0;
    }
    .rank-tabs button.active {
      background: var(--reference);
      color: #031014;
    }
    .campaign-funnel {
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
      border-bottom: 1px solid var(--divider);
    }
    .campaign-funnel div {
      display: grid;
      gap: 0.15rem;
      padding: 0.75rem 1rem;
      border-right: 1px solid var(--divider);
    }
    .campaign-funnel div:last-child {
      border-right: 0;
    }
    .campaign-funnel strong {
      font-size: 0.82rem;
    }
    .campaign-funnel span {
      color: var(--tertiary);
      font-size: 0.52rem;
      text-transform: uppercase;
    }
    .campaign-funnel .terminal strong {
      color: var(--tested);
    }
    .campaign-table {
      max-height: 386px;
      overflow: auto;
    }
    .campaign-row {
      display: grid;
      grid-template-columns:
        42px 150px minmax(180px, 1.25fr) minmax(132px, 0.9fr)
        minmax(148px, 1fr) minmax(170px, 1.1fr) 130px;
      align-items: center;
      min-width: 920px;
      padding: 0.55rem 0.8rem;
      border-bottom: 1px solid var(--divider);
      color: #bac7cd;
      font-size: 0.58rem;
    }
    .campaign-row:last-child {
      border-bottom: 0;
    }
    .campaign-head {
      position: sticky;
      z-index: 2;
      top: 0;
      background: #101c24;
      color: var(--tertiary);
      font-weight: 700;
      text-transform: uppercase;
    }
    .campaign-row .method {
      color: #aab5bb;
      text-transform: capitalize;
    }
    .campaign-row .method.bayesian {
      color: var(--reference);
    }
    .row-actions {
      display: flex;
      justify-content: flex-end;
      gap: 0.35rem;
    }
    .row-actions button,
    .comparison-dock button {
      min-height: 27px;
      padding: 0 0.5rem;
      border: 1px solid var(--divider-strong);
      background: transparent;
      color: var(--primary);
      font-size: 0.54rem;
    }
    .comparison-dock {
      border-top: 1px solid var(--divider);
      background: #0b161e;
    }
    .comparison-dock > header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.6rem 1rem;
      border-bottom: 1px solid var(--divider);
      font-size: 0.62rem;
    }
    .comparison-dock > div {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .comparison-dock article {
      padding: 1rem;
      border-right: 1px solid var(--divider);
    }
    .comparison-dock article:last-child {
      border-right: 0;
    }
    .comparison-dock article > span {
      color: var(--reference);
      font-size: 0.55rem;
      text-transform: capitalize;
    }
    .comparison-dock h3 {
      margin: 0.25rem 0 0.75rem;
      font-size: 0.8rem;
    }
    .comparison-dock dl {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      margin: 0 0 0.75rem;
    }
    .comparison-dock dl div {
      display: grid;
      gap: 0.2rem;
    }
    .comparison-dock dt {
      color: var(--tertiary);
      font-size: 0.5rem;
    }
    .comparison-dock dd {
      margin: 0;
      font-size: 0.6rem;
    }
    .investigation-workspace {
      display: grid;
      grid-template-columns: 250px minmax(0, 1fr);
      min-height: 680px;
      border: 1px solid var(--divider);
      background: var(--surface);
    }
    .cell-rail {
      padding: 1rem;
      border-right: 1px solid var(--divider);
      background: var(--rail);
    }
    .rail-heading h2,
    .proposal-toolbar h2 {
      margin: 0;
      font-size: 0.74rem;
    }
    .rail-heading span,
    .proposal-toolbar p {
      color: var(--tertiary);
      font-size: 0.59rem;
    }
    .cell-legend {
      display: flex;
      gap: 1rem;
      margin: 1rem 0 0.75rem;
      color: var(--secondary);
      font-size: 0.57rem;
    }
    .cell-legend span {
      display: flex;
      align-items: center;
      gap: 0.35rem;
    }
    .cell-legend i {
      width: 6px;
      height: 6px;
      border-radius: 50%;
    }
    .cell-legend i.random {
      background: #748690;
    }
    .cell-legend i.bayesian {
      background: var(--reference);
    }
    .cell-grid {
      display: grid;
      grid-template-columns: repeat(10, 1fr);
      gap: 5px;
    }
    .cell-grid button {
      position: relative;
      aspect-ratio: 1;
      border: 1px solid var(--divider);
      border-radius: 2px;
      background: linear-gradient(to top, currentColor var(--validity), #14222b var(--validity));
      color: #6d7e87;
    }
    .cell-grid button.bayesian {
      color: #278b96;
    }
    .cell-grid button:hover,
    .cell-grid button.active {
      z-index: 1;
      outline: 2px solid var(--primary);
      outline-offset: 1px;
    }
    .cell-summary {
      margin: 1.1rem 0 0;
    }
    .cell-summary div {
      display: flex;
      justify-content: space-between;
      gap: 0.5rem;
      padding: 0.48rem 0;
      border-bottom: 1px solid var(--divider-soft);
      font-size: 0.59rem;
    }
    .cell-summary dt {
      color: var(--tertiary);
    }
    .cell-summary dd {
      margin: 0;
      text-align: right;
      font-variant-numeric: tabular-nums;
    }
    .proposal-region {
      min-width: 0;
    }
    .proposal-toolbar {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 1rem;
      padding: 1rem 1.2rem;
      border-bottom: 1px solid var(--divider);
    }
    .proposal-toolbar p {
      margin: 0.25rem 0 0;
    }
    .toolbar-filters {
      display: flex;
      align-items: center;
      gap: 0.7rem;
    }
    .proposal-toolbar label {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      color: var(--secondary);
      font-size: 0.59rem;
    }
    .proposal-toolbar select {
      min-height: 32px;
      padding: 0 0.5rem;
      border: 1px solid var(--divider);
      border-radius: 3px;
      background: #09141c;
      color: var(--primary);
      font-size: 0.62rem;
    }
    .gate-funnel {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      border-bottom: 1px solid var(--divider);
    }
    .gate-funnel div {
      position: relative;
      display: grid;
      gap: 0.2rem;
      padding: 0.8rem 1rem;
      border-right: 1px solid var(--divider-soft);
      overflow: hidden;
    }
    .gate-funnel strong {
      font-size: 0.9rem;
      font-variant-numeric: tabular-nums;
    }
    .gate-funnel span {
      color: var(--secondary);
      font-size: 0.55rem;
    }
    .gate-funnel i {
      position: absolute;
      bottom: 0;
      left: 0;
      height: 2px;
      background: var(--reference);
    }
    .proposal-layout {
      display: grid;
      grid-template-columns: 285px minmax(0, 1fr);
      min-height: 535px;
    }
    .proposal-list {
      max-height: 590px;
      overflow: auto;
      border-right: 1px solid var(--divider);
    }
    .proposal-list > p {
      padding: 1rem;
      color: var(--secondary);
      font-size: 0.65rem;
    }
    .proposal-list button {
      display: grid;
      grid-template-columns: 30px minmax(0, 1fr) 52px;
      align-items: center;
      width: 100%;
      min-height: 56px;
      gap: 0.55rem;
      padding: 0 0.8rem;
      border: 0;
      border-bottom: 1px solid var(--divider-soft);
      background: transparent;
      color: var(--primary);
      text-align: left;
    }
    .proposal-list button:hover {
      background: #0f1e27;
    }
    .proposal-list button.active {
      background: #102831;
      box-shadow: inset 2px 0 var(--reference);
    }
    .proposal-list button > span {
      color: var(--tertiary);
      font-size: 0.58rem;
    }
    .proposal-list button div {
      min-width: 0;
    }
    .proposal-list strong,
    .proposal-list small {
      display: block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .proposal-list strong {
      font-size: 0.64rem;
    }
    .proposal-list small {
      margin-top: 0.2rem;
      color: var(--tertiary);
      font-size: 0.55rem;
    }
    .proposal-list b {
      text-align: right;
      color: var(--secondary);
      font-size: 0.58rem;
      font-weight: 550;
      font-variant-numeric: tabular-nums;
    }
    .proposal-detail {
      min-width: 0;
      padding: 1.2rem 1.4rem;
    }
    .proposal-detail > header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 1rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid var(--divider);
    }
    .proposal-detail header p {
      margin-bottom: 0.35rem;
    }
    .proposal-detail header h2 {
      margin: 0;
      font-size: 1.15rem;
      font-weight: 560;
      letter-spacing: -0.025em;
    }
    .proposal-detail header > span {
      padding: 0.35rem 0.5rem;
      border: 1px solid var(--divider);
      border-radius: 3px;
      color: var(--secondary);
      font-size: 0.55rem;
      text-transform: uppercase;
    }
    .parameter-strip {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      border-bottom: 1px solid var(--divider);
    }
    .parameter-strip div {
      display: grid;
      gap: 0.25rem;
      padding: 0.8rem 0;
    }
    .parameter-strip span {
      color: var(--tertiary);
      font-size: 0.55rem;
    }
    .parameter-strip strong {
      font-size: 0.7rem;
      font-variant-numeric: tabular-nums;
    }
    .controller-comparison {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      border-bottom: 1px solid var(--divider);
    }
    .controller-comparison div {
      display: grid;
      gap: 0.25rem;
      padding: 0.75rem 0;
    }
    .controller-comparison span {
      color: var(--tertiary);
      font-size: 0.55rem;
    }
    .controller-comparison strong {
      font-size: 0.67rem;
    }
    .controller-comparison strong.success {
      color: var(--success);
    }
    .controller-comparison strong.failure {
      color: var(--failure);
    }
    .gate-ladder {
      display: grid;
      gap: 0;
      margin: 1rem 0;
      padding: 0;
      list-style: none;
    }
    .gate-ladder li {
      display: grid;
      grid-template-columns: 28px 1fr;
      align-items: center;
      gap: 0.5rem;
      min-height: 45px;
      border-bottom: 1px solid var(--divider-soft);
      opacity: 0.45;
    }
    .gate-ladder li.pass,
    .gate-ladder li.stop {
      opacity: 1;
    }
    .gate-ladder li > i {
      display: grid;
      width: 20px;
      height: 20px;
      place-items: center;
      border: 1px solid var(--divider);
      border-radius: 50%;
      color: var(--tertiary);
      font-size: 0.65rem;
      font-style: normal;
    }
    .gate-ladder li.pass > i {
      border-color: var(--success);
      color: var(--success);
    }
    .gate-ladder li.stop > i {
      border-color: var(--tested);
      color: var(--tested);
    }
    .gate-ladder strong,
    .gate-ladder span {
      display: block;
    }
    .gate-ladder strong {
      font-size: 0.64rem;
    }
    .gate-ladder span {
      margin-top: 0.12rem;
      color: var(--tertiary);
      font-size: 0.55rem;
    }
    .replay-boundary {
      padding: 0.85rem 1rem;
      border-left: 2px solid #bd8b36;
      background: #161c20;
    }
    .replay-boundary strong {
      font-size: 0.66rem;
    }
    .replay-boundary p {
      margin: 0.3rem 0 0.7rem;
      color: var(--secondary);
      font-size: 0.59rem;
      line-height: 1.5;
    }
    .replay-boundary button {
      min-height: 34px;
      padding: 0 0.7rem;
    }
    .replay-error {
      display: block;
      margin-top: 0.6rem;
      color: #ff9b8c;
      font-size: 0.61rem;
    }
    .detail-actions {
      display: flex;
      gap: 0.5rem;
      margin-top: 0.8rem;
    }
    .detail-actions button {
      min-height: 36px;
    }
    .detail-actions button:disabled {
      opacity: 0.5;
    }
    .grounded-analysis {
      margin-top: 0.8rem;
      padding: 1rem;
      border: 1px solid var(--divider);
      background: #0c1820;
    }
    .grounded-analysis p {
      margin: 0;
      color: #b3c0c6;
      font-size: 0.63rem;
      line-height: 1.55;
    }
    .grounded-analysis p + p {
      margin-top: 0.55rem;
    }
    .grounded-analysis > strong {
      font-size: 0.64rem;
    }
    .grounded-analysis dl {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 0.45rem;
      margin: 0.75rem 0 0;
    }
    .grounded-analysis dl div {
      display: grid;
      gap: 0.15rem;
      margin: 0;
    }
    .grounded-analysis dt {
      color: var(--tertiary);
      font-size: 0.5rem;
      text-transform: uppercase;
    }
    .grounded-analysis dd {
      margin: 0;
      color: var(--primary);
      font-size: 0.59rem;
    }
    .grounded-analysis div {
      display: grid;
      gap: 0.25rem;
      margin-top: 0.75rem;
    }
    .grounded-analysis code {
      color: var(--reference);
      font-size: 0.52rem;
    }
    .analysis-error {
      margin: 0.8rem 0 0;
      color: #ff9b8c;
      font-size: 0.61rem;
    }
    .embedded-simulator {
      display: block;
      height: calc(100dvh - 64px);
    }
    @media (max-width: 900px) {
      .product-header {
        grid-template-columns: auto 1fr auto;
      }
      .connection {
        font-size: 0;
        width: 38px;
        padding: 0;
      }
      .connection i {
        width: 7px;
        height: 7px;
      }
      .assistant-launch {
        width: 38px;
        padding: 0;
        font-size: 0;
      }
      .investigation-workspace {
        grid-template-columns: 1fr;
      }
      .campaign-index > header {
        align-items: flex-start;
        flex-direction: column;
      }
      .campaign-funnel {
        grid-template-columns: repeat(4, 1fr);
      }
      .cell-rail {
        border-right: 0;
        border-bottom: 1px solid var(--divider);
      }
      .cell-grid {
        grid-template-columns: repeat(20, 1fr);
      }
      .proposal-layout {
        grid-template-columns: 240px minmax(0, 1fr);
      }
      .public-kpis {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .public-kpis div:nth-child(2) {
        border-right: 0;
      }
      .public-kpis div:nth-child(-n + 2) {
        border-bottom: 1px solid var(--divider);
      }
      .public-analysis,
      .locked-workspace {
        grid-template-columns: 1fr;
      }
      .model-metrics {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .model-metrics div:nth-child(2) {
        border-right: 0;
      }
      .model-metrics div:nth-child(-n + 2) {
        border-bottom: 1px solid var(--divider);
      }
      .method-card {
        border-right: 0;
        border-bottom: 1px solid var(--divider);
      }
    }
    @media (max-width: 680px) {
      .product-header {
        grid-template-columns: 1fr auto;
        grid-template-rows: 58px 54px;
        min-height: 112px;
        padding: 0 0.8rem;
      }
      .product-header nav {
        position: static;
        grid-row: 2;
        grid-column: 1 / -1;
        height: 54px;
        border-top: 1px solid var(--divider);
        background: #071018;
      }
      .product-header nav button {
        flex: 1;
      }
      .header-actions {
        grid-row: 1;
        grid-column: 2;
      }
      .investigation-page {
        padding: 1.25rem 1rem 4.5rem;
      }
      .page-heading {
        align-items: flex-start;
        flex-direction: column;
        gap: 0.6rem;
      }
      .public-result {
        align-items: flex-start;
        flex-direction: column;
      }
      .comparison-dock > div {
        grid-template-columns: 1fr;
      }
      .comparison-dock article {
        border-right: 0;
        border-bottom: 1px solid var(--divider);
      }
      .public-boundary {
        grid-template-columns: 1fr;
      }
      .model-evidence > header {
        align-items: flex-start;
        flex-direction: column;
      }
      .public-boundary div:first-child {
        border-right: 0;
        border-bottom: 1px solid var(--divider);
      }
      .method-row {
        grid-template-columns: 120px minmax(80px, 1fr) 55px;
      }
      .locked-workspace {
        min-height: calc(100dvh - 112px);
        gap: 2rem;
        padding: 2rem 1rem;
      }
      .rank-tabs {
        width: 100%;
        overflow-x: auto;
      }
      .rank-tabs button {
        flex: 1 0 auto;
      }
      .campaign-funnel {
        grid-template-columns: 1fr 1fr;
      }
      .page-heading {
        align-items: flex-start;
        flex-direction: column;
      }
      .page-status {
        display: none;
      }
      .cell-grid {
        grid-template-columns: repeat(10, 1fr);
      }
      .gate-funnel {
        grid-template-columns: repeat(5, minmax(70px, 1fr));
        overflow: auto;
      }
      .proposal-layout {
        grid-template-columns: 1fr;
      }
      .proposal-list {
        max-height: 250px;
        border-right: 0;
        border-bottom: 1px solid var(--divider);
      }
      .parameter-strip {
        grid-template-columns: 1fr 1fr;
      }
      .controller-comparison {
        grid-template-columns: 1fr;
      }
      .toolbar-filters {
        align-items: stretch;
        flex-direction: column;
      }
      .detail-actions {
        align-items: stretch;
        flex-direction: column;
      }
      .embedded-simulator {
        height: calc(100dvh - 112px);
      }
    }
  `,
})
export class ProductShell {
  protected readonly local = inject(LocalEvidenceService);
  protected readonly simulator = inject(SimulatorStore);
  private readonly debuggerStore = inject(DebuggerStore);
  private readonly reports = inject(InvestigationReportService);
  readonly connectRequested = output<void>();
  protected readonly repositoryUrl = 'https://github.com/ethanvillalovoz/planmargin';
  protected readonly publicHosted =
    window.location.protocol === 'https:' &&
    window.location.hostname !== 'localhost' &&
    window.location.hostname !== '127.0.0.1';
  protected readonly view = signal<ProductView>('replay');
  protected readonly sort = signal<ProposalSort>('criticality');
  protected readonly filter = signal<ProposalFilter>('all');
  protected readonly rank = signal<InvestigationRank>('closest');
  protected readonly comparison = signal<readonly InvestigationProposal[]>([]);
  protected readonly analysis = signal<ProposalAnalysis | undefined>(undefined);
  protected readonly analysisLoading = signal(false);
  protected readonly analysisError = signal<string | undefined>(undefined);
  protected readonly replayLoading = signal(false);
  protected readonly replayError = signal<string | undefined>(undefined);

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
  }
  protected publicValidRateDelta(): number {
    return (
      this.local.campaign().methods.bayesian.validRatePercent -
      this.local.campaign().methods.random.validRatePercent
    );
  }
  protected toggleAssistant(): void {
    const opening = this.view() !== 'replay' || !this.simulator.assistantOpen();
    this.setView('replay');
    this.simulator.assistantOpen.set(opening);
  }
  protected async openCampaignProposal(proposal: InvestigationProposal): Promise<void> {
    this.analysis.set(undefined);
    this.analysisError.set(undefined);
    await this.local.selectInvestigationProposal(proposal.cellId, proposal.proposalNumber);
    document.querySelector('.investigation-workspace')?.scrollIntoView({ behavior: 'smooth' });
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
    await this.local.selectCell(cellId);
  }
  protected selectProposal(proposalNumber: number): void {
    this.analysis.set(undefined);
    this.analysisError.set(undefined);
    this.local.selectProposal(proposalNumber);
  }
  protected changeSort(event: Event): void {
    this.sort.set((event.target as HTMLSelectElement).value as ProposalSort);
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
    this.view.set('replay');
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
    this.analysisLoading.set(true);
    this.analysisError.set(undefined);
    try {
      const cellId = this.local.selectedCellId();
      const proposalNumber = this.local.selectedProposalNumber();
      if (cellId === undefined || proposalNumber === undefined) {
        throw new Error('Select a proposal before running analysis');
      }
      this.analysis.set(await this.local.proposalAnalysis(cellId, proposalNumber));
    } catch (error: unknown) {
      this.analysisError.set(error instanceof Error ? error.message : 'Analysis failed');
    } finally {
      this.analysisLoading.set(false);
    }
  }
  protected async exportReport(): Promise<void> {
    const cell = this.local.selectedCell();
    const proposal = this.local.selectedProposal();
    if (cell && proposal)
      await this.reports.download({ campaign: this.local.campaign(), cell, proposal });
  }
}
