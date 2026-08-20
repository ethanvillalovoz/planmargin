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
  phosphorArrowRight,
  phosphorCheck,
  phosphorDownloadSimple,
  phosphorFlask,
  phosphorPlay,
  phosphorSparkle,
  phosphorStack,
} from '@ng-icons/phosphor-icons/regular';
import { InvestigationReportService } from '../investigation-report.service';
import { LocalEvidenceService } from '../local-evidence.service';
import { InvestigationProposal, LocalProposal, ProposalAnalysis } from '../local-evidence.types';
import { SimulatorStore } from '../simulator.store';
import { SimulatorWorkspace } from './simulator-workspace';

type ProductView = 'result' | 'investigate' | 'replay' | 'sensor';
type ProposalSort = 'criticality' | 'minimality' | 'support' | 'sequence';
type ProposalFilter = 'all' | 'eligible' | 'support-rejected' | 'pipeline-rejected';
type InvestigationRank = 'closest' | 'minimal' | 'support';

@Component({
  selector: 'app-product-shell',
  imports: [NgIcon, SimulatorWorkspace],
  providers: [
    provideIcons({
      phosphorArrowRight,
      phosphorCheck,
      phosphorDownloadSimple,
      phosphorFlask,
      phosphorPlay,
      phosphorSparkle,
      phosphorStack,
    }),
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="product-shell" [class.sensor-active]="view() === 'sensor' || view() === 'replay'">
      <header class="product-header">
        <button class="brand" type="button" (click)="setView('investigate')">
          <ng-icon name="phosphorStack" size="23" aria-hidden="true" />
          <strong>PlanMargin</strong>
        </button>
        <nav aria-label="Product sections">
          <button
            type="button"
            [class.active]="view() === 'investigate'"
            (click)="setView('investigate')"
          >
            Investigate
          </button>
          <button type="button" [class.active]="view() === 'replay'" (click)="setView('replay')">
            Replay
          </button>
          <button type="button" [class.active]="view() === 'sensor'" (click)="setView('sensor')">
            Sensor Lab
          </button>
          <button type="button" [class.active]="view() === 'result'" (click)="setView('result')">
            Report
          </button>
        </nav>
        <button
          type="button"
          class="connection"
          [class.connected]="local.connected()"
          (click)="connectRequested.emit()"
        >
          <i></i>{{ local.connected() ? 'Local evidence verified' : 'Connect real evidence' }}
        </button>
      </header>

      @if (view() === 'result') {
        <main class="result-page">
          <section class="result-hero" aria-labelledby="result-title">
            <div>
              <p class="result-context">Immutable v1 development campaign</p>
              <h1 id="result-title">No qualifying planner failure was found.</h1>
              <p class="result-summary">
                That is the result—not an empty state. Bayesian search produced more realistic,
                reproducible proposals, but the frozen experiment cannot claim better failure
                discovery or mutation minimality.
              </p>
              <div class="hero-actions">
                <button class="primary" type="button" (click)="setView('investigate')">
                  Investigate the evidence <ng-icon name="phosphorArrowRight" size="16" />
                </button>
                <button type="button" (click)="setView('sensor')">Open Sensor Lab</button>
              </div>
            </div>
            <div class="result-mark" aria-label="Campaign conclusion">
              <span>0</span>
              <strong>qualifying findings</strong>
              <small>from 3,200 tested proposals</small>
            </div>
          </section>

          <section class="scale-rail" aria-label="Campaign scale">
            <div><strong>100</strong><span>matched cells</span></div>
            <div><strong>14,110</strong><span>physical rollouts</span></div>
            <div><strong>1,128,800</strong><span>Waymax steps</span></div>
            <div><strong>+14.8125 pp</strong><span>Bayesian valid-yield lift</span></div>
          </section>

          <section class="result-analysis">
            <div class="method-story">
              <div class="section-heading">
                <div>
                  <p>Method comparison</p>
                  <h2>Bayesian search preserved validity.</h2>
                </div>
                <strong>H3 supported</strong>
              </div>
              <div class="method-row">
                <span>Random</span>
                <div><i style="width:54.5625%"></i></div>
                <strong>54.5625%</strong>
              </div>
              <div class="method-row bayesian">
                <span>Bayesian</span>
                <div><i style="width:69.375%"></i></div>
                <strong>69.3750%</strong>
              </div>
              <p>Support-and-pipeline-valid proposals under equal 1,600-proposal budgets.</p>
            </div>

            <div class="decision-story">
              <div>
                <span>H1 · Efficiency</span><strong>Untestable</strong>
                <p>No finding from either method.</p>
              </div>
              <div>
                <span>H2 · Minimality</span><strong>Untestable</strong>
                <p>No paired failure mutations.</p>
              </div>
              <div>
                <span>H3 · Validity</span><strong class="positive">Supported</strong>
                <p>Frozen noninferiority rule passed.</p>
              </div>
            </div>
          </section>

          <section class="program-boundary">
            <div>
              <p>What the system established</p>
              <h2>A complete negative result with a preserved audit trail.</h2>
              <ul>
                <li>
                  <ng-icon name="phosphorCheck" size="16" />All 100 cells reconciled from sealed
                  records
                </li>
                <li>
                  <ng-icon name="phosphorCheck" size="16" />Random and Bayesian budgets remained
                  matched
                </li>
                <li>
                  <ng-icon name="phosphorCheck" size="16" />No validation comparison was opened
                  after the no-go
                </li>
              </ul>
            </div>
            <div class="research-status">
              <article>
                <span>v1 campaign</span><strong>Complete</strong
                ><small>Development no-go preserved</small>
              </article>
              <article>
                <span>v2 learned controller</span><strong>No-go</strong
                ><small>3.125% synthetic collision rate</small>
              </article>
              <article>
                <span>Planning-scene Gaussian</span><strong>No-go</strong
                ><small>23.66% trajectory linkage</small>
              </article>
              <article>
                <span>Perception Sensor Lab</span><strong>Available</strong
                ><small>Real WOD camera, 3DGS, and LiDAR</small>
              </article>
            </div>
          </section>

          <aside class="claim-boundary">
            <strong>Claim boundary</strong>
            <p>
              Ten training scenarios, five seeds, and no qualifying failures. This bounded simulator
              study does not evaluate the production Waymo Driver. The visual WOD Perception segment
              is not geometrically registered to the WOMD planning evidence.
            </p>
          </aside>
        </main>
      } @else if (view() === 'investigate') {
        <main class="investigation-page">
          <header class="page-heading">
            <div>
              <p>Campaign investigation</p>
              <h1>Trace why a proposal did—or did not—qualify.</h1>
            </div>
            <div class="page-status">
              <i></i
              >{{
                local.connected() ? '3,200 sealed proposals available' : 'Local records required'
              }}
            </div>
          </header>

          @if (!local.connected()) {
            <section class="public-workbench">
              <div class="public-result">
                <div>
                  <span>Public aggregate mode</span>
                  <h2>Completed campaign · 0 qualifying findings</h2>
                  <p>
                    The aggregate result works from a clean clone. Connect the authorized local
                    evidence store to inspect all 3,200 proposal records, exact gates, and replays.
                  </p>
                </div>
                <button class="primary" type="button" (click)="connectRequested.emit()">
                  Connect local evidence
                </button>
              </div>
              <div class="public-methods">
                <article>
                  <span>Random search</span><strong>54.5625%</strong
                  ><small>support + pipeline valid</small>
                  <i><b style="width:54.5625%"></b></i>
                </article>
                <article>
                  <span>Bayesian search</span><strong>69.3750%</strong
                  ><small>support + pipeline valid</small>
                  <i><b style="width:69.375%"></b></i>
                </article>
                <article>
                  <span>Experiment scale</span><strong>3,200</strong
                  ><small>sealed proposals · 100 cells</small>
                </article>
                <article>
                  <span>Hypothesis decision</span><strong>H3 supported</strong
                  ><small>H1 and H2 untestable</small>
                </article>
              </div>
              <div class="public-boundary">
                <strong>Why proposal rows are locked</strong>
                <p>
                  Waymo-derived per-scenario records remain local under the dataset terms. This is a
                  data-access boundary, not synthetic sample data or an unfinished screen.
                </p>
              </div>
            </section>
          } @else {
            @if (local.investigation(); as campaign) {
              <section class="campaign-index" aria-labelledby="campaign-index-title">
                <header>
                  <div>
                    <p>Verified campaign index</p>
                    <h2 id="campaign-index-title">
                      Rank all {{ campaign.proposalCount }} proposals
                    </h2>
                  </div>
                  <div class="rank-tabs" aria-label="Campaign ranking">
                    <button
                      type="button"
                      [class.active]="rank() === 'closest'"
                      (click)="rank.set('closest')"
                    >
                      Closest margin
                    </button>
                    <button
                      type="button"
                      [class.active]="rank() === 'minimal'"
                      (click)="rank.set('minimal')"
                    >
                      Smallest mutation
                    </button>
                    <button
                      type="button"
                      [class.active]="rank() === 'support'"
                      (click)="rank.set('support')"
                    >
                      Highest support
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
                    <span>Rank</span><span>Cell</span><span>Proposal</span><span>Criticality</span
                    ><span>Minimality</span><span>Support</span><span>Decisive gate</span
                    ><span></span>
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
                      <span>#{{ proposal.proposalNumber.toString().padStart(2, '0') }}</span>
                      <span>{{ proposal.criticality.toFixed(4) }}</span>
                      <span>{{ proposal.minimality.toFixed(4) }}</span>
                      <span>{{ proposal.empiricalSupportProbability?.toFixed(4) ?? '—' }}</span>
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
                              <dt>Criticality</dt>
                              <dd>{{ proposal.criticality.toFixed(4) }}</dd>
                            </div>
                            <div>
                              <dt>Minimality</dt>
                              <dd>{{ proposal.minimality.toFixed(4) }}</dd>
                            </div>
                            <div>
                              <dt>Support</dt>
                              <dd>{{ proposal.empiricalSupportProbability?.toFixed(4) ?? '—' }}</dd>
                            </div>
                            <div>
                              <dt>Gate</dt>
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
                      <dt>Hypervolume</dt>
                      <dd>{{ cell.finalFeasibleHypervolume.toFixed(4) }}</dd>
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
                          <span>Onset offset</span
                          ><strong>{{ proposal.brakingOnsetOffsetSeconds.toFixed(1) }} s</strong>
                        </div>
                        <div>
                          <span>Speed multiplier</span
                          ><strong>{{ proposal.speedMultiplier.toFixed(4) }}</strong>
                        </div>
                        <div>
                          <span>Criticality</span
                          ><strong>{{ proposal.criticality.toFixed(4) }}</strong>
                        </div>
                        <div>
                          <span>Minimality</span
                          ><strong>{{ proposal.minimality.toFixed(4) }}</strong>
                        </div>
                      </div>
                      <div class="controller-comparison" aria-label="Controller outcomes">
                        <div>
                          <span>Tested controller</span>
                          <strong [class.failure]="proposal.testedMutatedFailure === true">{{
                            proposal.testedMutatedFailure === true
                              ? 'Failed'
                              : proposal.testedMutatedFailure === false
                                ? 'Succeeded'
                                : 'Not evaluated'
                          }}</strong>
                        </div>
                        <div>
                          <span>Reference controller</span>
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
                        <strong>Proposal trajectory is not stored.</strong>
                        <p>
                          The campaign retained validated trajectory hashes, outcomes, objectives,
                          and cost—not a replay package for every proposal. The available Stage-0
                          replay is separate evidence.
                        </p>
                        <button type="button" (click)="openReplay()">
                          <ng-icon name="phosphorPlay" size="15" />Open available sealed replay
                        </button>
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
      } @else {
        <app-simulator-workspace
          class="embedded-simulator"
          [embedded]="true"
          (connectRequested)="connectRequested.emit()"
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
    .connection {
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
    .page-status i {
      background: var(--success);
    }
    .result-page {
      width: min(1240px, 100%);
      margin: 0 auto;
      padding: clamp(2rem, 5vw, 4.75rem) clamp(1.2rem, 4vw, 3rem) 4rem;
    }
    .result-hero {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 310px;
      align-items: center;
      gap: clamp(2rem, 7vw, 7rem);
      min-height: 320px;
    }
    .result-context,
    .section-heading p,
    .program-boundary > div > p,
    .page-heading p,
    .proposal-detail header p {
      margin: 0 0 0.75rem;
      color: var(--reference);
      font-size: 0.61rem;
      font-weight: 750;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    .result-hero h1,
    .page-heading h1 {
      max-width: 760px;
      margin: 0;
      font-size: clamp(2.35rem, 5vw, 4.8rem);
      font-weight: 520;
      line-height: 0.98;
      letter-spacing: -0.06em;
    }
    .result-summary {
      max-width: 690px;
      margin: 1.4rem 0 0;
      color: #a8b7bf;
      font-size: clamp(0.87rem, 1.3vw, 1.02rem);
      line-height: 1.65;
    }
    .hero-actions {
      display: flex;
      gap: 0.65rem;
      margin-top: 1.8rem;
    }
    .hero-actions button,
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
    .hero-actions button.primary,
    .primary {
      border-color: var(--tested);
      background: var(--tested);
      color: #fff;
    }
    .result-mark {
      display: grid;
      place-items: center;
      min-height: 250px;
      border: 1px solid var(--divider);
      border-radius: 50%;
      background: radial-gradient(circle, #102831 0, #08141d 68%);
      text-align: center;
    }
    .result-mark span {
      margin-top: 1.5rem;
      color: var(--tested);
      font-size: 6.6rem;
      font-weight: 500;
      line-height: 0.7;
      letter-spacing: -0.08em;
    }
    .result-mark strong {
      font-size: 0.83rem;
    }
    .result-mark small {
      margin-top: -1.3rem;
      color: var(--tertiary);
      font-size: 0.63rem;
    }
    .scale-rail {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      margin-top: 3rem;
      border-top: 1px solid var(--divider);
      border-bottom: 1px solid var(--divider);
    }
    .scale-rail div {
      display: grid;
      gap: 0.3rem;
      padding: 1.35rem 1.1rem;
      border-right: 1px solid var(--divider);
    }
    .scale-rail div:last-child {
      border: 0;
    }
    .scale-rail strong {
      font-size: 1.35rem;
      font-weight: 560;
      font-variant-numeric: tabular-nums;
    }
    .scale-rail span {
      color: var(--secondary);
      font-size: 0.62rem;
    }
    .result-analysis {
      display: grid;
      grid-template-columns: 1.4fr 1fr;
      gap: 4rem;
      padding: 4rem 0;
      border-bottom: 1px solid var(--divider);
    }
    .section-heading {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 1rem;
    }
    .section-heading h2,
    .program-boundary h2 {
      margin: 0;
      font-size: clamp(1.35rem, 2.4vw, 2.1rem);
      font-weight: 540;
      letter-spacing: -0.04em;
    }
    .section-heading > strong {
      color: var(--success);
      font-size: 0.72rem;
    }
    .method-row {
      display: grid;
      grid-template-columns: 74px minmax(0, 1fr) 84px;
      align-items: center;
      gap: 0.8rem;
      margin-top: 1.3rem;
      color: var(--secondary);
      font-size: 0.68rem;
    }
    .method-row > div {
      height: 7px;
      background: var(--divider-soft);
    }
    .method-row i {
      display: block;
      height: 100%;
      background: var(--tertiary);
    }
    .method-row.bayesian i {
      background: var(--reference);
    }
    .method-row strong {
      text-align: right;
      color: var(--primary);
      font-variant-numeric: tabular-nums;
    }
    .method-story > p {
      margin: 1rem 0 0;
      color: var(--tertiary);
      font-size: 0.61rem;
    }
    .decision-story {
      border-left: 1px solid var(--divider);
    }
    .decision-story div {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 0.35rem 1rem;
      padding: 1rem 0 1rem 1.5rem;
      border-bottom: 1px solid var(--divider-soft);
    }
    .decision-story span {
      color: var(--secondary);
      font-size: 0.64rem;
    }
    .decision-story strong {
      font-size: 0.7rem;
    }
    .decision-story strong.positive {
      color: var(--success);
    }
    .decision-story p {
      grid-column: 1/-1;
      margin: 0;
      color: var(--tertiary);
      font-size: 0.62rem;
    }
    .program-boundary {
      display: grid;
      grid-template-columns: 1fr 1.15fr;
      gap: 5rem;
      padding: 4rem 0;
    }
    .program-boundary ul {
      display: grid;
      gap: 0.7rem;
      margin: 1.7rem 0 0;
      padding: 0;
      list-style: none;
    }
    .program-boundary li {
      display: flex;
      align-items: center;
      gap: 0.55rem;
      color: #b9c6cc;
      font-size: 0.72rem;
    }
    .program-boundary li ng-icon {
      color: var(--success);
    }
    .research-status {
      border-top: 1px solid var(--divider);
    }
    .research-status article {
      display: grid;
      grid-template-columns: 1.2fr 0.6fr 1.6fr;
      align-items: center;
      gap: 1rem;
      padding: 1rem 0;
      border-bottom: 1px solid var(--divider);
      font-size: 0.66rem;
    }
    .research-status span,
    .research-status small {
      color: var(--secondary);
    }
    .research-status strong {
      font-size: 0.68rem;
    }
    .claim-boundary {
      display: grid;
      grid-template-columns: 180px 1fr;
      gap: 1rem;
      padding: 1.2rem 1.4rem;
      border-left: 3px solid var(--tested);
      background: #111d25;
    }
    .claim-boundary strong {
      font-size: 0.72rem;
    }
    .claim-boundary p {
      margin: 0;
      color: #9babb4;
      font-size: 0.68rem;
      line-height: 1.6;
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
    .public-methods {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
    }
    .public-methods article {
      display: grid;
      gap: 0.45rem;
      padding: 1.4rem;
      border-right: 1px solid var(--divider);
    }
    .public-methods article:last-child {
      border-right: 0;
    }
    .public-methods span,
    .public-methods small {
      color: var(--secondary);
      font-size: 0.58rem;
    }
    .public-methods strong {
      font-size: 1.15rem;
    }
    .public-methods i {
      display: block;
      height: 3px;
      overflow: hidden;
      background: var(--divider);
    }
    .public-methods b {
      display: block;
      height: 100%;
      background: var(--reference);
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
        42px 150px 70px repeat(3, minmax(86px, 0.75fr)) minmax(150px, 1fr)
        130px;
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
      .result-hero {
        grid-template-columns: 1fr;
      }
      .result-mark {
        display: none;
      }
      .result-analysis,
      .program-boundary {
        grid-template-columns: 1fr;
        gap: 2rem;
      }
      .investigation-workspace {
        grid-template-columns: 1fr;
      }
      .public-methods {
        grid-template-columns: 1fr 1fr;
      }
      .public-methods article:nth-child(2) {
        border-right: 0;
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
      .connection {
        grid-row: 1;
        grid-column: 2;
      }
      .result-page,
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
      .public-methods,
      .comparison-dock > div {
        grid-template-columns: 1fr;
      }
      .public-methods article,
      .public-methods article:nth-child(2),
      .comparison-dock article {
        border-right: 0;
        border-bottom: 1px solid var(--divider);
      }
      .public-boundary {
        grid-template-columns: 1fr;
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
      .result-hero {
        min-height: auto;
      }
      .result-hero h1 {
        font-size: 2.45rem;
      }
      .hero-actions {
        align-items: stretch;
        flex-direction: column;
      }
      .scale-rail {
        grid-template-columns: 1fr 1fr;
      }
      .scale-rail div:nth-child(2) {
        border-right: 0;
      }
      .scale-rail div:nth-child(-n + 2) {
        border-bottom: 1px solid var(--divider);
      }
      .decision-story {
        border-left: 0;
      }
      .research-status article {
        grid-template-columns: 1fr auto;
      }
      .research-status small {
        grid-column: 1/-1;
      }
      .claim-boundary {
        grid-template-columns: 1fr;
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
  private readonly simulator = inject(SimulatorStore);
  private readonly reports = inject(InvestigationReportService);
  readonly connectRequested = output<void>();
  protected readonly view = signal<ProductView>('investigate');
  protected readonly sort = signal<ProposalSort>('criticality');
  protected readonly filter = signal<ProposalFilter>('all');
  protected readonly rank = signal<InvestigationRank>('closest');
  protected readonly comparison = signal<readonly InvestigationProposal[]>([]);
  protected readonly analysis = signal<ProposalAnalysis | undefined>(undefined);
  protected readonly analysisLoading = signal(false);
  protected readonly analysisError = signal<string | undefined>(undefined);

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
    this.view.set(view);
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
    return gate.replaceAll('_', ' ');
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
      ? `Criticality ${proposal.criticality.toFixed(3)}`
      : proposal.attemptStatus.replaceAll('_', ' ');
  }
  protected rankValue(proposal: LocalProposal): string {
    if (this.sort() === 'sequence') return `#${proposal.proposalNumber}`;
    if (this.sort() === 'minimality') return proposal.minimality.toFixed(3);
    if (this.sort() === 'support') return proposal.empiricalSupportProbability?.toFixed(3) ?? '—';
    return proposal.criticality.toFixed(3);
  }
  protected gateReason(proposal: LocalProposal): string {
    if (proposal.attemptStatus === 'mutation_rejected') return 'Mutation gate rejected';
    if (proposal.attemptStatus === 'scenario_rejected') return 'Scenario gate rejected';
    if (!proposal.pipelinePasses) return 'Pipeline validity rejected';
    if (proposal.supportPasses !== true) return 'Empirical support rejected';
    if (!proposal.referencePasses) return 'Reference controller failed';
    if (proposal.testedMutatedFailure !== true) return 'Tested controller did not fail';
    return proposal.policySpecificAvoidableFailure
      ? 'Qualifying finding'
      : 'Finding contract not met';
  }
  protected proposalGates(
    proposal: LocalProposal,
  ): readonly { label: string; detail: string; pass: boolean; stop: boolean }[] {
    const mutation = proposal.attemptStatus !== 'mutation_rejected';
    const scenario = mutation && proposal.attemptStatus !== 'scenario_rejected';
    const support = scenario && proposal.supportPasses === true;
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
        label: 'Empirical support',
        detail:
          proposal.empiricalSupportProbability === null
            ? 'Not evaluated'
            : `p = ${proposal.empiricalSupportProbability.toFixed(4)} · threshold 0.05`,
        pass: support,
      },
      {
        label: 'Reference controller',
        detail: reference
          ? 'Reference succeeded under the same mutation'
          : 'Not passed or not evaluated',
        pass: reference,
      },
      {
        label: 'Tested-controller failure',
        detail: tested ? 'Tested controller failed' : 'Tested controller remained successful',
        pass: tested,
      },
    ];
    const firstFailure = gates.findIndex((gate) => !gate.pass);
    return gates.map((gate, index) => ({ ...gate, stop: index === firstFailure }));
  }
  protected contextualSummary(proposal: LocalProposal): string {
    return `For proposal ${proposal.proposalNumber}, the decisive gate was: ${this.gateReason(proposal).toLowerCase()}. Criticality ${proposal.criticality.toFixed(4)}, minimality ${proposal.minimality.toFixed(4)}, and support ${proposal.empiricalSupportProbability?.toFixed(4) ?? 'not evaluated'} are measured local evidence.`;
  }
  protected openReplay(): void {
    this.simulator.selectMode('planning');
    this.view.set('replay');
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
