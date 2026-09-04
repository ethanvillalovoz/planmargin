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
import { OperationsWorkspace } from './operations-workspace';

type ProductView = 'operations' | 'investigate' | 'replay' | 'sensor';
type EvidenceView = 'campaign' | 'deployment';
type ProposalSort = 'criticality' | 'minimality' | 'support' | 'sequence';
type ProposalFilter = 'all' | 'eligible' | 'support-rejected' | 'pipeline-rejected';
type InvestigationRank = 'closest' | 'minimal' | 'support';

function initialProductView(): ProductView {
  const requested = new URLSearchParams(window.location.search).get('view');
  if (requested === 'evidence') return 'investigate';
  if (requested === 'replay' || requested === 'sensors') {
    return requested === 'sensors' ? 'sensor' : requested;
  }
  return 'operations';
}

function initialEvidenceView(): EvidenceView {
  return new URLSearchParams(window.location.search).get('panel') === 'runtime'
    ? 'deployment'
    : 'campaign';
}

@Component({
  selector: 'app-product-shell',
  imports: [NgIcon, OperationsWorkspace, SimulatorWorkspace],
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
        <button class="brand" type="button" (click)="setView('operations')">
          <ng-icon name="phosphorStack" size="23" aria-hidden="true" />
          <span class="brand-lockup">
            <strong>PlanMargin</strong>
            <small>Behavior Test Studio</small>
          </span>
        </button>
        <nav aria-label="Product sections">
          <button
            type="button"
            [class.active]="view() === 'operations'"
            (click)="setView('operations')"
          >
            Campaign
          </button>
          <button type="button" [class.active]="view() === 'replay'" (click)="setView('replay')">
            Replay
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

      @if (view() === 'operations') {
        <app-operations-workspace (openScenarioLab)="setView('replay')" />
      } @else if (view() === 'investigate') {
        <main class="investigation-page">
          <header class="evidence-commandbar">
            <div class="evidence-context">
              <span>Evidence workspace</span>
              <strong>{{
                evidenceView() === 'campaign'
                  ? local.connected()
                    ? 'Counterfactual investigation'
                    : 'Published campaign evidence'
                  : 'Model qualification'
              }}</strong>
              <small>{{
                evidenceView() === 'campaign'
                  ? local.connected()
                    ? 'Rank, inspect, compare, replay, and export sealed proposals.'
                    : 'Inspect reproducible aggregates before opening licensed local records.'
                  : 'Trace prediction quality through runtime and promotion gates.'
              }}</small>
            </div>
            <nav class="evidence-sections" aria-label="Evidence sections">
              <button
                type="button"
                [class.active]="evidenceView() === 'campaign'"
                (click)="evidenceView.set('campaign')"
              >
                Campaign review
              </button>
              <button
                type="button"
                [class.active]="evidenceView() === 'deployment'"
                (click)="evidenceView.set('deployment')"
              >
                Model & runtime
              </button>
            </nav>
            <div class="page-status" [class.connected]="local.connected()">
              <i></i>{{ local.connected() ? 'Sealed records verified' : 'Local records required' }}
            </div>
          </header>

          @if (evidenceView() === 'deployment') {
            <section class="deployment-workbench" aria-labelledby="deployment-workbench-title">
              <header>
                <div>
                  <p>Measured deployment evidence</p>
                  <h2 id="deployment-workbench-title">Models, deployment, and promotion gates</h2>
                </div>
                <span class="qualification-status"><i></i>Promotion status explicit</span>
              </header>
              <section class="model-evidence" aria-labelledby="deployment-quality-title">
                <header>
                  <div>
                    <span>1,024-scenario scale study · byte-reproducible</span>
                    <h3 id="deployment-quality-title">Real-WOMD prediction quality</h3>
                  </div>
                  <b>real data · no synthetic training</b>
                </header>
                <div class="model-metrics">
                  <div>
                    <span>WOMD scenarios</span>
                    <strong>{{ local.campaign().scaleTrajectoryModel.scenarios }}</strong>
                    <small
                      >{{
                        local.campaign().scaleTrajectoryModel.windows.toLocaleString()
                      }}
                      windows</small
                    >
                  </div>
                  <div>
                    <span>Test ADE</span>
                    <strong
                      >{{ local.campaign().scaleTrajectoryModel.adeMeters.toFixed(3) }} m</strong
                    >
                    <small
                      >baseline
                      {{ local.campaign().scaleTrajectoryModel.baselineAdeMeters.toFixed(3) }}
                      m</small
                    >
                  </div>
                  <div>
                    <span>Test FDE</span>
                    <strong
                      >{{ local.campaign().scaleTrajectoryModel.fdeMeters.toFixed(3) }} m</strong
                    >
                    <small
                      >baseline
                      {{ local.campaign().scaleTrajectoryModel.baselineFdeMeters.toFixed(3) }}
                      m</small
                    >
                  </div>
                  <div>
                    <span>Test evidence</span>
                    <strong>{{
                      local.campaign().scaleTrajectoryModel.testWindows.toLocaleString()
                    }}</strong>
                    <small>complete-scenario windows</small>
                  </div>
                </div>
                <div class="deployment-divider">
                  <span
                    >Scaled 1,024-scenario model · {{ local.campaign().scaleInference.gpu }} · 500
                    measured</span
                  >
                  <b
                    >TensorRT {{ local.campaign().scaleInference.tensorrtVersion }} · measured
                    no-go</b
                  >
                </div>
                <div class="model-metrics" aria-label="Measured NVIDIA inference evidence">
                  <div>
                    <span>FP32 · batch 1 E2E</span>
                    <strong
                      >{{
                        local.campaign().scaleInference.fp32Batch1EndToEndP50Ms.toFixed(3)
                      }}
                      ms</strong
                    >
                    <small>p50 pinned-host latency</small>
                  </div>
                  <div>
                    <span>FP16 · batch 1 E2E</span>
                    <strong
                      >{{
                        local.campaign().scaleInference.fp16Batch1EndToEndP50Ms.toFixed(3)
                      }}
                      ms</strong
                    >
                    <small>p50 pinned-host latency</small>
                  </div>
                  <div>
                    <span>FP16 · batch 256</span>
                    <strong
                      >{{
                        (
                          local.campaign().scaleInference.fp16Batch256Throughput / 1_000_000
                        ).toFixed(2)
                      }}M/s</strong
                    >
                    <small>end-to-end throughput</small>
                  </div>
                  <div>
                    <span>C++17 · batch 1 E2E</span>
                    <strong
                      >{{
                        local.campaign().scaleInference.cppBatch1EndToEndP50Ms.toFixed(3)
                      }}
                      ms</strong
                    >
                    <small>independent pinned-host runner</small>
                  </div>
                </div>
              </section>
              <div class="deployment-notes">
                <article class="stopped-gate">
                  <span>Scale-model FP16 promotion gate · stopped</span>
                  <strong>One preregistered numerical-drift gate did not pass.</strong>
                  <p>
                    {{ (local.campaign().scaleInference.fp16RmseMeters * 100).toFixed(2) }} cm RMSE
                    passed;
                    {{ (local.campaign().scaleInference.fp16MaxDriftMeters * 100).toFixed(2) }} cm
                    maximum drift exceeded the frozen 7.50 cm limit at batch 256. FP32 parity and
                    GPU end-to-end latency passed.
                  </p>
                </article>
                <article>
                  <span>Protocol boundary</span>
                  <strong>Quality and deployment probes are kept separate.</strong>
                  <p>
                    ADE/FDE use the real WOMD scenario split. Deterministic physical probes are used
                    only for TensorRT timing and numerical parity.
                  </p>
                </article>
                <article>
                  <span>Reproducible artifact chain</span>
                  <strong>Weights, ONNX, reports, versions, and hashes are public.</strong>
                  <p>
                    TensorRT engines are rebuilt per GPU; the free-T4 notebook verifies each source
                    hash before engine creation and compiles the C++17 cross-check.
                  </p>
                </article>
                <article>
                  <span>Earlier model · qualified reference</span>
                  <strong>The 128-scenario model retains its independent T4 result.</strong>
                  <p>
                    FP32 {{ local.campaign().inference.fp32Batch1P50Ms.toFixed(3) }} ms · FP16
                    {{ local.campaign().inference.fp16Batch1P50Ms.toFixed(3) }} ms · C++17
                    {{ local.campaign().inference.cppBatch1P50Ms.toFixed(3) }} ms batch-1 device
                    p50. These numbers are not attributed to the scaled model.
                  </p>
                </article>
                <article class="stopped-gate">
                  <span>Active-risk promotion gate · stopped</span>
                  <strong>The learned ranker did not generalize across scenes.</strong>
                  <p>
                    {{ local.campaign().activeRisk.examples.toLocaleString() }} real proposal
                    targets · Spearman {{ local.campaign().activeRisk.meanSpearman.toFixed(3) }} ·
                    matched random at budget 8 in
                    {{ local.campaign().activeRisk.budgetEightWins }} of
                    {{ local.campaign().activeRisk.scenarios }} scenes. No selector was promoted.
                  </p>
                </article>
                <article class="stopped-gate">
                  <span>Neighbor-context ablation · stopped</span>
                  <strong>Nearest-actor pooling was worse than ego history alone.</strong>
                  <p>
                    ADE {{ local.campaign().interactionStudy.interactionAdeMeters.toFixed(3) }} m
                    with neighbors versus
                    {{ local.campaign().interactionStudy.egoOnlyAdeMeters.toFixed(3) }} m ego-only
                    on the same 102-scenario test split.
                  </p>
                </article>
                <article class="stopped-gate">
                  <span>Scale-model deployment decision · no-go</span>
                  <strong>The complete T4 protocol ran; FP16 was not promoted.</strong>
                  <p>
                    FP32 remains a measured deployment path. The failed FP16 max-drift gate is
                    preserved without relaxing its threshold after observation.
                  </p>
                </article>
              </div>
            </section>
          } @else if (!local.connected()) {
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
            @if (local.investigation(); as campaign) {
              <section class="campaign-index" aria-labelledby="campaign-index-title">
                <header>
                  <div>
                    <p>Verified campaign · {{ local.cells().length }} cells</p>
                    <h2 id="campaign-index-title">Priority review queue</h2>
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
                    <span role="columnheader">Rank</span><span role="columnheader">Case</span
                    ><span role="columnheader">Change</span
                    ><span role="columnheader">Safety result</span
                    ><span role="columnheader">Recorded precedent</span
                    ><span role="columnheader">Why it stopped</span
                    ><span role="columnheader">Actions</span>
                  </div>
                  @for (
                    proposal of campaignRanking();
                    track proposal.cellId + proposal.proposalNumber;
                    let index = $index
                  ) {
                    <div class="campaign-row" role="row">
                      <span role="cell">{{ index + 1 }}</span>
                      <span
                        role="cell"
                        class="method"
                        [class.bayesian]="proposal.method === 'bayesian'"
                      >
                        {{ proposal.method }} · S{{ proposal.selectionOrder }} · {{ proposal.seed }}
                      </span>
                      <span role="cell">{{ mutationNarrative(proposal) }}</span>
                      <span role="cell">{{ proximityLabel(proposal.criticality) }}</span>
                      <span role="cell">{{
                        supportLabel(proposal.empiricalSupportProbability, proposal.supportPasses)
                      }}</span>
                      <span role="cell">{{ formatGate(proposal.decisiveGate) }}</span>
                      <span role="cell" class="row-actions">
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
      grid-template-columns: auto minmax(0, 1fr) auto;
      align-items: center;
      min-height: 52px;
      padding: 0 0.8rem;
      border-bottom: 1px solid var(--divider);
      background: rgb(15 16 18 / 97%);
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
      gap: 0.5rem;
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
      font-size: 0.78rem;
      letter-spacing: -0.025em;
    }
    .product-header nav {
      display: flex;
      align-self: stretch;
      justify-content: flex-start;
      gap: 0;
      margin-left: 1rem;
      border-left: 1px solid var(--divider);
    }
    .product-header nav button {
      position: relative;
      border: 0;
      background: transparent;
      color: var(--secondary);
      padding: 0 0.9rem;
      border-right: 1px solid var(--divider);
      font-size: 0.62rem;
      font-weight: 650;
    }
    .product-header nav button.active {
      background: #1b1d1f;
      color: var(--primary);
    }
    .product-header nav button.active:after {
      position: absolute;
      right: 0;
      bottom: 0;
      left: 0;
      height: 2px;
      background: #e7dd55;
      content: '';
    }
    .connection,
    .assistant-launch {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.45rem;
      min-height: 30px;
      padding: 0 0.75rem;
      border: 1px solid var(--divider);
      border-radius: 2px;
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
    .proposal-detail header p {
      margin: 0 0 0.75rem;
      color: var(--reference);
      font-size: 0.61rem;
      font-weight: 750;
      letter-spacing: 0.12em;
      text-transform: uppercase;
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
      min-height: calc(100dvh - 52px);
      padding: 0;
    }
    .evidence-commandbar {
      position: sticky;
      z-index: 60;
      top: 52px;
      display: grid;
      grid-template-columns: minmax(260px, 1fr) auto minmax(190px, 1fr);
      align-items: center;
      gap: 1rem;
      min-height: 72px;
      padding: 0.65rem 1.5rem;
      border-bottom: 1px solid var(--divider);
      background: rgb(8 18 26 / 96%);
      backdrop-filter: blur(16px);
    }
    .evidence-context {
      display: grid;
      min-width: 0;
    }
    .evidence-context span {
      color: var(--reference);
      font-size: 0.53rem;
      font-weight: 750;
      letter-spacing: 0.11em;
      text-transform: uppercase;
    }
    .evidence-context strong {
      font-size: 0.83rem;
      font-weight: 650;
    }
    .evidence-context small {
      overflow: hidden;
      color: var(--secondary);
      font-size: 0.56rem;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .evidence-sections {
      display: flex;
      gap: 0.35rem;
      padding: 3px;
      border: 1px solid var(--divider);
      border-radius: 5px;
      background: var(--rail);
    }
    .evidence-sections button {
      min-height: 30px;
      padding: 0 0.8rem;
      border: 1px solid transparent;
      border-radius: 4px;
      background: transparent;
      color: var(--secondary);
      font-size: 0.62rem;
      font-weight: 650;
    }
    .evidence-sections button.active {
      border-color: transparent;
      background: #17313b;
      color: var(--primary);
    }
    .deployment-workbench {
      margin: 1rem 1.5rem 1.5rem;
      border: 1px solid var(--divider);
      background: var(--panel);
    }
    .deployment-workbench > header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      padding: 1.1rem 1.3rem;
      border-bottom: 1px solid var(--divider);
    }
    .deployment-workbench > header p,
    .deployment-notes span {
      margin: 0 0 0.28rem;
      color: var(--reference);
      font-size: 0.55rem;
      font-weight: 750;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }
    .deployment-workbench > header h2 {
      margin: 0;
      font-size: 1rem;
      font-weight: 600;
    }
    .qualification-status {
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      color: #176b43;
      font-size: 0.58rem;
      font-weight: 700;
      text-transform: uppercase;
    }
    .qualification-status i {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: currentcolor;
      box-shadow: 0 0 10px currentcolor;
    }
    .deployment-workbench .model-evidence {
      margin: 0;
      border: 0;
      border-bottom: 1px solid var(--divider);
    }
    .deployment-notes {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .deployment-notes article {
      padding: 1.2rem 1.3rem;
      border-right: 1px solid var(--divider);
    }
    .deployment-notes article:last-child {
      border-right: 0;
    }
    .deployment-notes article:nth-child(n + 4) {
      border-top: 1px solid var(--divider);
    }
    .deployment-notes article.stopped-gate {
      background: rgb(240 163 59 / 4%);
    }
    .deployment-notes article.stopped-gate span {
      color: #835600;
    }
    .deployment-notes strong {
      display: block;
      font-size: 0.72rem;
      line-height: 1.45;
    }
    .deployment-notes p {
      margin: 0.55rem 0 0;
      color: var(--secondary);
      font-size: 0.6rem;
      line-height: 1.6;
    }
    .page-status {
      display: flex;
      align-items: center;
      justify-self: end;
      gap: 0.45rem;
      color: var(--secondary);
      font-size: 0.62rem;
    }
    .public-workbench {
      margin: 1rem 1.5rem 1.5rem;
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
      color: #176b43;
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
      color: #176b43;
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
    .deployment-divider {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      margin: 1.35rem 0 0.65rem;
      padding-top: 1rem;
      border-top: 1px solid var(--divider);
    }
    .deployment-divider span {
      color: var(--reference);
      font-size: 0.56rem;
      font-weight: 750;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }
    .deployment-divider b {
      color: #176b43;
      font-size: 0.58rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .locked-workspace {
      display: grid;
      grid-template-columns: 210px minmax(0, 1fr) 280px;
      min-height: calc(100dvh - 52px);
      background: #090a0b;
    }
    .locked-rail,
    .locked-inspector {
      background: #101113;
    }
    .locked-rail {
      border-right: 1px solid var(--divider);
    }
    .locked-inspector {
      border-left: 1px solid var(--divider);
    }
    .locked-rail header,
    .locked-inspector header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 34px;
      padding: 0 0.7rem;
      border-bottom: 1px solid var(--divider);
      background: #151618;
      color: #85888b;
      font:
        600 0.55rem ui-monospace,
        monospace;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .locked-rail > button {
      width: 100%;
      padding: 0.8rem;
      border: 0;
      border-bottom: 1px solid var(--divider-soft);
      background: transparent;
      color: var(--primary);
      font-size: 0.65rem;
      text-align: left;
    }
    .locked-rail > button.selected {
      background: #1b1d1f;
      box-shadow: inset 2px 0 #e7dd55;
    }
    .locked-rail section {
      padding: 0.8rem;
      color: #7f8285;
      font-size: 0.56rem;
    }
    .locked-rail section span {
      font:
        600 0.5rem ui-monospace,
        monospace;
      text-transform: uppercase;
    }
    .locked-rail section p {
      margin: 0.65rem 0 0;
    }
    .locked-canvas {
      display: grid;
      min-width: 0;
      padding: 2rem;
      place-items: center;
    }
    .locked-canvas > div {
      max-width: 470px;
    }
    .locked-canvas span {
      color: #e7dd55;
      font:
        600 0.58rem ui-monospace,
        monospace;
      letter-spacing: 0.08em;
    }
    .locked-canvas h1 {
      margin: 0.8rem 0;
      font-size: 1.65rem;
      font-weight: 560;
      line-height: 1.2;
      letter-spacing: -0.03em;
    }
    .locked-canvas p {
      margin: 0 0 1.2rem;
      color: var(--secondary);
      font-size: 0.68rem;
      line-height: 1.6;
    }
    .locked-inspector dl {
      margin: 0;
    }
    .locked-inspector dl div {
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      padding: 0.72rem;
      border-bottom: 1px solid var(--divider-soft);
    }
    .locked-inspector dt,
    .locked-inspector dd {
      font-size: 0.56rem;
    }
    .locked-inspector dt {
      color: var(--secondary);
    }
    .locked-inspector dd {
      margin: 0;
      font-weight: 650;
      text-align: right;
    }
    .locked-inspector > button {
      width: calc(100% - 1.4rem);
      min-height: 32px;
      margin: 0.7rem;
      border: 1px solid var(--divider-strong);
      border-radius: 2px;
      background: #1a1c1e;
      color: var(--primary);
      font-size: 0.6rem;
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
      margin: 1rem 1.5rem 0;
      border: 1px solid var(--divider);
      border-bottom: 0;
      background: var(--surface);
    }
    .campaign-index > header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      min-height: 54px;
      padding: 0.65rem 0.9rem;
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
      padding: 0.55rem 0.75rem;
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
      max-height: 214px;
      overflow: auto;
    }
    .campaign-row {
      display: grid;
      grid-template-columns:
        42px 150px minmax(180px, 1.25fr) minmax(132px, 0.9fr)
        minmax(148px, 1fr) minmax(170px, 1.1fr) 130px;
      align-items: center;
      min-width: 920px;
      min-height: 39px;
      padding: 0.4rem 0.8rem;
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
      min-height: 660px;
      margin: 0 1.5rem 1.5rem;
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
      height: calc(100dvh - 52px);
    }

    /* Full-shell design language grounded in Waymo's public product surfaces. */
    :host {
      background: #f4f6f3;
      color: #141b2d;
    }
    .product-shell {
      background: #f4f6f3;
    }
    .product-header {
      grid-template-columns: auto minmax(0, 1fr) auto;
      min-height: 72px;
      padding: 0 22px;
      border-bottom: 1px solid #e3e7e3;
      background: rgb(255 255 255 / 96%);
      box-shadow: 0 2px 16px rgb(18 32 44 / 4%);
      backdrop-filter: blur(18px);
    }
    .brand {
      gap: 10px;
      color: #111a2d;
    }
    .brand ng-icon {
      display: grid;
      width: 36px;
      height: 36px;
      place-items: center;
      border-radius: 12px;
      background: #ddf8ee;
      color: #087d6a;
    }
    .brand-lockup {
      display: grid;
      gap: 1px;
      text-align: left;
    }
    .brand strong {
      font-size: 0.9rem;
      font-weight: 720;
      letter-spacing: -0.035em;
    }
    .brand small {
      color: #59636f;
      font-size: 0.55rem;
      font-weight: 650;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .product-header nav {
      align-self: center;
      justify-self: center;
      gap: 4px;
      margin-left: 0;
      padding: 4px;
      border: 0;
      border-radius: 999px;
      background: #f0f2ef;
    }
    .product-header nav button {
      min-height: 36px;
      padding: 0 15px;
      border: 0;
      border-radius: 999px;
      color: #626b76;
      font-size: 0.67rem;
      font-weight: 700;
    }
    .product-header nav button:hover {
      color: #174fae;
    }
    .product-header nav button.active {
      background: #ffffff;
      color: #164ca9;
      box-shadow: 0 2px 10px rgb(27 46 64 / 10%);
    }
    .product-header nav button.active:after {
      display: none;
    }
    .header-actions {
      gap: 8px;
    }
    .connection,
    .assistant-launch {
      min-height: 38px;
      padding: 0 14px;
      border: 0;
      border-radius: 999px;
      background: #edf0ed;
      color: #3f4855;
      font-size: 0.65rem;
      font-weight: 700;
    }
    .assistant-launch {
      background: #1769ff;
      color: #ffffff;
      box-shadow: 0 7px 20px rgb(23 105 255 / 18%);
    }
    .assistant-launch ng-icon {
      color: #ffffff;
    }
    .assistant-launch:hover,
    .assistant-launch.active {
      border-color: transparent;
      background: #0759e7;
    }
    .assistant-launch:disabled {
      background: #dfe4e2;
      color: #8b929b;
      box-shadow: none;
    }
    .connection.connected {
      background: #e1f4e8;
      color: #276e49;
    }
    .investigation-page {
      min-height: calc(100dvh - 72px);
      padding-bottom: 24px;
      background: #f4f6f3;
    }
    .evidence-commandbar {
      top: 72px;
      min-height: 108px;
      padding: 16px 24px 18px;
      border-bottom: 0;
      background: rgb(244 246 243 / 96%);
    }
    .evidence-context span {
      color: #0758c7;
      font-size: 0.58rem;
      letter-spacing: 0.08em;
    }
    .evidence-context strong {
      color: #121a2d;
      font-size: 1.45rem;
      font-weight: 510;
      letter-spacing: -0.045em;
    }
    .evidence-context small {
      margin-top: 3px;
      color: #56606c;
      font-size: 0.64rem;
    }
    .evidence-sections {
      gap: 4px;
      padding: 4px;
      border: 0;
      border-radius: 999px;
      background: #e9ede8;
    }
    .evidence-sections button {
      min-height: 36px;
      padding: 0 14px;
      border: 0;
      border-radius: 999px;
      color: #626b76;
    }
    .evidence-sections button.active {
      background: #ffffff;
      color: #164ca9;
      box-shadow: 0 2px 10px rgb(27 46 64 / 10%);
    }
    .page-status {
      min-height: 34px;
      padding: 0 12px;
      border-radius: 999px;
      background: #e8ece8;
      color: #56606c;
      font-weight: 650;
    }
    .page-status.connected {
      background: #e0f4e7;
      color: #286d49;
    }
    .deployment-workbench,
    .public-workbench,
    .campaign-index,
    .investigation-workspace {
      border: 1px solid #e0e5e1;
      border-radius: 22px;
      background: #ffffff;
      box-shadow: 0 8px 30px rgb(17 31 45 / 6%);
      overflow: hidden;
    }
    .deployment-workbench,
    .public-workbench {
      margin: 0 24px 24px;
    }
    .campaign-index,
    .investigation-workspace {
      margin-right: 24px;
      margin-left: 24px;
    }
    .deployment-workbench > header,
    .model-evidence,
    .public-kpis,
    .method-card,
    .campaign-funnel,
    .campaign-row,
    .cell-rail,
    .proposal-toolbar,
    .gate-funnel,
    .proposal-list,
    .parameter-strip,
    .controller-comparison,
    .proposal-detail > header,
    .comparison-dock,
    .comparison-dock > header,
    .comparison-dock article,
    .deployment-notes article {
      border-color: #e7eae7;
    }
    .deployment-workbench > header h2,
    .proposal-detail header h2,
    .rail-heading h2,
    .proposal-toolbar h2 {
      color: #121a2d;
      font-weight: 520;
      letter-spacing: -0.035em;
    }
    .qualification-status {
      min-height: 30px;
      padding: 0 11px;
      border-radius: 999px;
      background: #e0f4e7;
      color: #286d49;
    }
    .public-kpis div,
    .method-card,
    .decision-card,
    .proposal-detail,
    .cell-rail,
    .deployment-notes article {
      color: #20283a;
    }
    .public-kpis strong {
      color: #141b2d;
      font-size: 1.65rem;
      font-weight: 500;
    }
    .public-kpis span,
    .method-card small,
    .deployment-notes p,
    .rail-heading span,
    .proposal-toolbar p,
    .cell-summary dt,
    .proposal-list small,
    .proposal-list b,
    .parameter-strip span,
    .controller-comparison span,
    .gate-ladder span,
    .grounded-analysis p {
      color: #56606c;
    }
    .rank-tabs,
    .comparison-dock,
    .grounded-analysis {
      background: #f7f9f6;
    }
    .rank-tabs {
      padding: 4px;
      border-radius: 999px;
    }
    .rank-tabs button,
    .proposal-toolbar select,
    .row-actions button,
    .comparison-dock button,
    .detail-actions button,
    .replay-boundary button {
      border-color: #d7ddda;
      border-radius: 999px;
      background: #f0f2ef;
      color: #36404d;
    }
    .rank-tabs button.active {
      background: #0758c7;
      color: #ffffff;
    }
    .campaign-head {
      background: #f0f3ef;
      color: #56606c;
    }
    .campaign-row {
      color: #36404d;
    }
    .campaign-row .method.bayesian,
    .comparison-dock article > span,
    .proposal-detail header p,
    .grounded-analysis code {
      color: #0758c7;
    }
    .cell-grid button {
      border-radius: 7px;
      background: linear-gradient(to top, currentColor var(--validity), #e8ece8 var(--validity));
    }
    .proposal-list button {
      color: #20283a;
    }
    .proposal-list button:hover,
    .proposal-list button.active {
      background: #eef4ff;
      box-shadow: none;
    }
    .replay-boundary {
      border-radius: 0 14px 14px 0;
      background: #fff5e6;
      color: #3d4652;
    }
    .grounded-analysis {
      border-radius: 14px;
    }
    .public-boundary {
      border-color: #e7eae7;
      background: #f7f9f6;
      color: #141b2d;
    }
    .public-boundary strong {
      color: #141b2d;
    }
    .public-boundary p {
      color: #4d5764;
    }
    .locked-workspace {
      grid-template-columns: 230px minmax(0, 1fr) 300px;
      gap: 16px;
      min-height: calc(100dvh - 72px);
      padding: 18px;
      background: #f4f6f3;
    }
    .locked-rail,
    .locked-canvas,
    .locked-inspector {
      overflow: hidden;
      border: 1px solid #e0e5e1;
      border-radius: 20px;
      background: #ffffff;
      box-shadow: 0 8px 30px rgb(17 31 45 / 6%);
    }
    .locked-rail header,
    .locked-inspector header {
      min-height: 48px;
      padding: 0 14px;
      border-color: #e7eae7;
      background: #ffffff;
      color: #59636f;
      font-family: inherit;
      font-size: 0.56rem;
      font-weight: 750;
      letter-spacing: 0.08em;
    }
    .locked-rail header b {
      color: #9a5c00;
    }
    .locked-inspector header b {
      color: #56606c;
    }
    .locked-rail > button {
      min-height: 52px;
      padding: 0 14px;
      border-color: #e7eae7;
      color: #20283a;
      font-weight: 680;
    }
    .locked-rail > button.selected {
      background: #eef4ff;
      color: #164ca9;
      box-shadow: inset 3px 0 #1769ff;
    }
    .locked-rail section {
      padding: 18px 14px;
      color: #59636f;
      font-size: 0.62rem;
    }
    .locked-rail section span {
      color: #0758c7;
      font-family: inherit;
      font-size: 0.55rem;
      font-weight: 750;
      letter-spacing: 0.08em;
    }
    .locked-rail section p {
      margin-top: 0.8rem;
      color: #4d5764;
    }
    .locked-canvas {
      position: relative;
      padding: clamp(2rem, 6vw, 5rem);
      background:
        radial-gradient(circle at 76% 18%, rgb(23 105 255 / 9%), transparent 30%),
        linear-gradient(145deg, #ffffff 0%, #f7faf8 100%);
    }
    .locked-canvas::after {
      position: absolute;
      right: -90px;
      bottom: -130px;
      width: 330px;
      height: 330px;
      border: 64px solid rgb(100 211 138 / 12%);
      border-radius: 50%;
      content: '';
      pointer-events: none;
    }
    .locked-canvas > div {
      position: relative;
      z-index: 1;
      max-width: 560px;
    }
    .locked-canvas span {
      color: #0758c7;
      font-family: inherit;
      font-size: 0.59rem;
      font-weight: 760;
      letter-spacing: 0.09em;
    }
    .locked-canvas h1 {
      margin: 0.8rem 0 0.7rem;
      color: #121a2d;
      font-size: clamp(2rem, 4vw, 3.35rem);
      font-weight: 500;
      line-height: 1.02;
      letter-spacing: -0.055em;
    }
    .locked-canvas p {
      max-width: 500px;
      margin-bottom: 1.5rem;
      color: #4d5764;
      font-size: 0.76rem;
      line-height: 1.65;
    }
    .locked-canvas .primary {
      display: inline-flex;
      width: auto;
      min-height: 42px;
      border: 0;
      border-radius: 999px;
      background: #1769ff;
      color: #ffffff;
      box-shadow: 0 8px 22px rgb(23 105 255 / 20%);
    }
    .locked-canvas .primary:hover {
      background: #0759e7;
    }
    .locked-inspector dl div {
      padding: 14px;
      border-color: #e7eae7;
    }
    .locked-inspector dt {
      color: #59636f;
    }
    .locked-inspector dd {
      color: #141b2d;
    }
    .locked-inspector > button {
      width: calc(100% - 28px);
      min-height: 38px;
      margin: 14px;
      border: 0;
      border-radius: 999px;
      background: #eef4ff;
      color: #164ca9;
      font-weight: 680;
    }
    .locked-inspector > button:hover {
      background: #dfeaff;
    }
    .embedded-simulator {
      height: calc(100dvh - 72px);
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
      .evidence-commandbar {
        grid-template-columns: minmax(220px, 1fr) auto;
      }
      .evidence-commandbar .page-status {
        display: none;
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
      .locked-rail,
      .locked-inspector {
        display: none;
      }
      .deployment-notes {
        grid-template-columns: 1fr;
      }
      .deployment-notes article {
        border-right: 0;
        border-bottom: 1px solid var(--divider);
      }
      .deployment-notes article:last-child {
        border-bottom: 0;
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
        background: #f0f2ef;
      }
      .product-header nav button {
        flex: 1;
      }
      .header-actions {
        grid-row: 1;
        grid-column: 2;
      }
      .investigation-page {
        padding: 0 0 4.5rem;
      }
      .deployment-workbench {
        margin-right: 0.75rem;
        margin-left: 0.75rem;
      }
      .deployment-workbench > header {
        align-items: flex-start;
        flex-direction: column;
      }
      .evidence-commandbar {
        top: 112px;
        grid-template-columns: 1fr;
        gap: 0.55rem;
        min-height: 110px;
        padding: 0.65rem 0.75rem;
      }
      .evidence-context small {
        white-space: normal;
      }
      .evidence-sections {
        width: 100%;
      }
      .evidence-sections button {
        flex: 1;
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
        padding: 0.75rem;
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
      .campaign-index,
      .investigation-workspace {
        margin-right: 0.75rem;
        margin-left: 0.75rem;
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
  protected readonly view = signal<ProductView>(initialProductView());
  protected readonly evidenceView = signal<EvidenceView>(initialEvidenceView());
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
    // Entering a planning replay is an explicit request to inspect its evidence.
    // Re-open the panel even when the responsive layout collapsed it on startup.
    this.simulator.controlsOpen.set(true);
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
