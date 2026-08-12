import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  inject,
  output,
  signal,
} from '@angular/core';
import { DebuggerStore } from '../debugger.store';
import { LocalEvidenceService } from '../local-evidence.service';

@Component({
  selector: 'app-local-evidence-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="backdrop" (click)="closeFromBackdrop($event)">
      <section
        class="panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="local-evidence-title"
        aria-describedby="local-evidence-boundary"
      >
        <header>
          <div>
            <h1 id="local-evidence-title">Local evidence</h1>
            <p id="local-evidence-boundary">
              Verified records stay on this machine. The token is held in memory only.
            </p>
          </div>
          <button type="button" aria-label="Close local evidence" (click)="close.emit()">
            Close
          </button>
        </header>

        @if (!local.connected()) {
          <form (submit)="connect($event)">
            <label for="local-token">Ephemeral API token</label>
            <p>Start <code>planmargin-serve-evidence</code>, then paste its terminal token.</p>
            <input
              id="local-token"
              #tokenInput
              type="password"
              name="local-token"
              autocomplete="off"
              autocapitalize="none"
              spellcheck="false"
              minlength="16"
              required
              [disabled]="local.state() === 'connecting'"
            />
            @if (local.error()) {
              <p class="error" role="alert">{{ local.error() }}</p>
            }
            <div class="form-actions">
              <button type="button" (click)="close.emit()">Cancel</button>
              <button class="primary" type="submit" [disabled]="local.state() === 'connecting'">
                {{ local.state() === 'connecting' ? 'Verifying…' : 'Connect local evidence' }}
              </button>
            </div>
          </form>
        } @else {
          <div class="status">
            <span><i></i>Real local · verified</span>
            <button type="button" (click)="disconnect()">Disconnect</button>
          </div>

          @if (local.error()) {
            <p class="error connected-error" role="alert">{{ local.error() }}</p>
          }

          <div class="workspace">
            <section class="source-list" aria-labelledby="runs-title">
              <h2 id="runs-title">Replay evidence</h2>
              @for (run of local.runs(); track run.runId) {
                <button
                  type="button"
                  [class.active]="store.run().runId === run.runId"
                  (click)="loadRun(run.runId)"
                >
                  <strong>{{ run.label }}</strong>
                  <span>{{ run.recordCount }} sealed rollout records</span>
                </button>
              }
              <h2>Campaign cells</h2>
              <label class="cell-select">
                <span>Method · scenario order · seed</span>
                <select [value]="local.selectedCellId()" (change)="selectCell($event)">
                  @for (cell of local.cells(); track cell.cellId) {
                    <option [value]="cell.cellId">
                      {{ cell.method }} · {{ cell.selectionOrder }} · {{ cell.seed }}
                    </option>
                  }
                </select>
              </label>
              @if (local.selectedCell(); as cell) {
                <dl class="cell-metrics">
                  <div>
                    <dt>Eligible</dt>
                    <dd>{{ cell.supportAndPipelineValidCount }} / {{ cell.proposalCount }}</dd>
                  </div>
                  <div>
                    <dt>Valid rate</dt>
                    <dd>{{ cell.validRatePercent.toFixed(2) }}%</dd>
                  </div>
                  <div>
                    <dt>Findings</dt>
                    <dd>{{ cell.qualifyingFailureCount }}</dd>
                  </div>
                </dl>
              }
            </section>

            <section class="proposal-browser" aria-labelledby="proposals-title">
              <div class="browser-heading">
                <div>
                  <h2 id="proposals-title">Sealed proposals</h2>
                  <p>Redacted parameters, support, outcomes, and physical cost.</p>
                </div>
                <span>{{ local.proposals().length }} records</span>
              </div>
              @if (local.loadingProposals()) {
                <p class="loading" role="status">Verifying proposal seals…</p>
              } @else {
                <div class="proposal-layout">
                  <div class="proposal-list" aria-label="Proposal records">
                    @for (proposal of local.proposals(); track proposal.proposalNumber) {
                      <button
                        type="button"
                        [class.active]="local.selectedProposalNumber() === proposal.proposalNumber"
                        (click)="local.selectProposal(proposal.proposalNumber)"
                      >
                        <span>#{{ proposal.proposalNumber.toString().padStart(2, '0') }}</span>
                        <strong>{{ proposal.attemptStatus }}</strong>
                        <i [class.pass]="proposal.supportPasses === true"></i>
                      </button>
                    }
                  </div>
                  @if (local.selectedProposal(); as proposal) {
                    <article class="proposal-detail">
                      <div class="detail-title">
                        <span>PROPOSAL {{ proposal.proposalNumber }}</span>
                        <strong>{{ proposal.attemptStatus }}</strong>
                      </div>
                      <dl>
                        <div>
                          <dt>Onset offset</dt>
                          <dd>{{ proposal.brakingOnsetOffsetSeconds.toFixed(1) }} s</dd>
                        </div>
                        <div>
                          <dt>Speed multiplier</dt>
                          <dd>{{ proposal.speedMultiplier.toFixed(4) }}</dd>
                        </div>
                        <div>
                          <dt>Mutation distance</dt>
                          <dd>{{ proposal.normalizedMutationDistance.toFixed(4) }}</dd>
                        </div>
                        <div>
                          <dt>Support probability</dt>
                          <dd>{{ probability(proposal.empiricalSupportProbability) }}</dd>
                        </div>
                        <div>
                          <dt>Support gate</dt>
                          <dd [class.pass]="proposal.supportPasses === true">
                            {{ decision(proposal.supportPasses) }}
                          </dd>
                        </div>
                        <div>
                          <dt>Tested failed</dt>
                          <dd>{{ decision(proposal.testedMutatedFailure) }}</dd>
                        </div>
                        <div>
                          <dt>Reference succeeded</dt>
                          <dd>{{ decision(proposal.referenceMutatedSuccess) }}</dd>
                        </div>
                        <div>
                          <dt>Qualifying finding</dt>
                          <dd>{{ decision(proposal.policySpecificAvoidableFailure) }}</dd>
                        </div>
                        <div>
                          <dt>Physical rollouts</dt>
                          <dd>{{ proposal.physicalRollouts }}</dd>
                        </div>
                      </dl>
                    </article>
                  }
                </div>
              }
            </section>
          </div>
        }
      </section>
    </div>
  `,
  styles: `
    .error {
      padding: 0.6rem 0.7rem;
      border-left: 2px solid var(--failure);
      background: #211113;
      color: #ff9b95;
    }
    .connected-error {
      margin: 0.75rem 1.4rem 0;
    }
    .status {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 48px;
      padding: 0 1.4rem;
      border-bottom: 1px solid var(--divider);
      background: #0c1715;
      color: var(--success);
      font-size: 0.66rem;
    }
    .status span {
      display: flex;
      align-items: center;
      gap: 0.45rem;
    }
    .status i {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--success);
      box-shadow: 0 0 0 3px rgb(115 209 47 / 12%);
    }
    .workspace {
      display: grid;
      grid-template-columns: 270px minmax(0, 1fr);
      min-height: 570px;
    }
    .source-list {
      padding: 1.1rem;
      border-right: 1px solid var(--divider);
    }
    h2 {
      color: var(--secondary);
      font-size: 0.62rem;
      font-weight: 700;
      letter-spacing: 0.11em;
      text-transform: uppercase;
    }
    .source-list > button {
      display: grid;
      width: 100%;
      height: auto;
      gap: 0.25rem;
      margin: 0.65rem 0 1.4rem;
      padding: 0.7rem;
      text-align: left;
    }
    .source-list > button.active {
      border-color: var(--reference);
      background: #0d1a20;
    }
    .source-list > button strong {
      font-size: 0.7rem;
    }
    .source-list > button span,
    .cell-select > span {
      color: var(--secondary);
      font-size: 0.6rem;
    }
    .cell-select {
      display: grid;
      gap: 0.4rem;
      margin-top: 0.65rem;
    }
    select {
      width: 100%;
      padding: 0 0.5rem;
      background: #080d11;
    }
    .cell-metrics {
      margin: 0.8rem 0 0;
    }
    .cell-metrics div,
    .proposal-detail dl div {
      display: flex;
      justify-content: space-between;
      gap: 0.75rem;
      padding: 0.3rem 0;
      font-size: 0.66rem;
    }
    dt {
      color: var(--secondary);
    }
    dd {
      margin: 0;
      font-variant-numeric: tabular-nums;
    }
    .proposal-browser {
      min-width: 0;
      padding: 1.1rem 1.25rem;
    }
    .browser-heading {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 1rem;
      padding-bottom: 0.85rem;
      border-bottom: 1px solid var(--divider);
    }
    .browser-heading > span {
      color: var(--secondary);
      font-size: 0.62rem;
    }
    .browser-heading p {
      margin-top: 0.35rem;
      color: var(--secondary);
      font-size: 0.66rem;
      line-height: 1.5;
    }
    .proposal-layout {
      display: grid;
      grid-template-columns: 190px minmax(0, 1fr);
      min-height: 455px;
    }
    .proposal-list {
      max-height: 455px;
      overflow: auto;
      padding: 0.7rem 0.7rem 0.7rem 0;
      border-right: 1px solid var(--divider);
    }
    .proposal-list button {
      display: grid;
      grid-template-columns: 30px minmax(0, 1fr) 8px;
      align-items: center;
      width: 100%;
      gap: 0.45rem;
      padding: 0 0.5rem;
      border-color: transparent;
      text-align: left;
    }
    .proposal-list button.active {
      border-color: var(--divider);
      background: #111a20;
    }
    .proposal-list button span {
      color: var(--secondary);
      font-variant-numeric: tabular-nums;
    }
    .proposal-list button strong {
      overflow: hidden;
      font-size: 0.61rem;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .proposal-list i {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #46515a;
    }
    .proposal-list i.pass {
      background: var(--success);
    }
    .proposal-detail {
      padding: 1rem 0 1rem 1.2rem;
    }
    .detail-title {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 0.7rem;
    }
    .detail-title span {
      color: var(--tested);
      font-size: 0.58rem;
      font-weight: 700;
      letter-spacing: 0.12em;
    }
    .detail-title strong {
      font-size: 0.76rem;
    }
    .proposal-detail dl {
      margin: 0;
    }
    .proposal-detail dl div {
      padding: 0.46rem 0;
      border-bottom: 1px solid #1f2a31;
      font-size: 0.7rem;
    }
    dd.pass {
      color: var(--success);
    }
    .loading {
      padding: 2rem 0;
      color: var(--secondary);
      font-size: 0.7rem;
    }
    @media (max-width: 760px) {
      .workspace,
      .proposal-layout {
        grid-template-columns: 1fr;
      }
      .source-list,
      .proposal-list {
        border-right: 0;
        border-bottom: 1px solid var(--divider);
      }
      .proposal-list {
        display: flex;
        max-height: none;
        gap: 0.3rem;
        padding-right: 0;
        overflow: auto;
      }
      .proposal-list button {
        min-width: 142px;
      }
      .proposal-detail {
        padding-left: 0;
      }
    }
  `,
})
export class LocalEvidencePanel {
  protected readonly local = inject(LocalEvidenceService);
  protected readonly store = inject(DebuggerStore);
  readonly close = output<void>();
  protected readonly busy = signal(false);

  protected async connect(event: Event): Promise<void> {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement;
    const input = form.elements.namedItem('local-token') as HTMLInputElement;
    try {
      const evidence = await this.local.connect(input.value);
      input.value = '';
      this.store.loadRun(evidence.initialRun);
    } catch {
      input.value = '';
    }
  }

  protected async loadRun(runId: string): Promise<void> {
    if (this.busy()) return;
    this.busy.set(true);
    try {
      this.store.loadRun(await this.local.loadRun(runId));
    } catch {
      // The service exposes a redacted user-facing error in the panel.
    } finally {
      this.busy.set(false);
    }
  }

  protected async selectCell(event: Event): Promise<void> {
    try {
      await this.local.selectCell((event.target as HTMLSelectElement).value);
    } catch {
      // The service exposes a redacted user-facing error in the panel.
    }
  }

  protected disconnect(): void {
    this.local.disconnect();
    this.store.resetToSynthetic();
  }

  protected probability(value: number | null): string {
    return value === null ? 'Unavailable' : value.toFixed(4);
  }

  protected decision(value: boolean | null): string {
    return value === null ? 'Not evaluated' : value ? 'Yes' : 'No';
  }

  @HostListener('document:keydown.escape')
  protected closeFromEscape(): void {
    this.close.emit();
  }

  protected closeFromBackdrop(event: MouseEvent): void {
    if (event.target === event.currentTarget) this.close.emit();
  }
}
