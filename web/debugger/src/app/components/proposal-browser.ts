import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { LocalEvidenceService } from '../local-evidence.service';
import { InvestigationProposal, LocalProposal } from '../local-evidence.types';

export function proposalGate(proposal: LocalProposal): string {
  if (proposal.attemptStatus === 'mutation_rejected') return 'mutation_geometry';
  if (proposal.attemptStatus === 'scenario_rejected') return 'scenario_validity';
  if (!proposal.pipelinePasses) return 'pipeline_reproducibility';
  if (proposal.supportPasses !== true) return 'empirical_support';
  if (!proposal.referencePasses) return 'reference_controller';
  if (proposal.testedMutatedFailure !== true) return 'tested_controller_failure';
  return proposal.policySpecificAvoidableFailure ? 'qualifying_finding' : 'finding_contract';
}

@Component({
  selector: 'app-proposal-browser',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section aria-labelledby="proposal-browser-title">
      <header>
        <span class="eyebrow">1 · Choose a scenario and proposal</span>
        <h2 id="proposal-browser-title">Browse recorded tests</h2>
        <p>A proposal is one tested change to the lead vehicle's timing and speed.</p>
        <label
          >Recorded scenario
          <select
            aria-label="Recorded scenario"
            (change)="changeScenario($event)"
            [disabled]="local.loadingProposals()"
          >
            <option value="priority" [selected]="priority()">
              Priority proposals · all scenarios
            </option>
            @for (scenario of scenarios(); track scenario) {
              <option
                [value]="scenario"
                [selected]="!priority() && local.selectedCell()?.selectionOrder === scenario"
              >
                Scenario {{ scenario }}
              </option>
            }
          </select>
        </label>
        @if (!priority()) {
          <div class="run-filters">
            <label
              >Search method
              <select
                aria-label="Search method"
                (change)="changeRun('method', $event)"
                [disabled]="local.loadingProposals()"
              >
                <option value="bayesian" [selected]="local.selectedCell()?.method === 'bayesian'">
                  Bayesian search
                </option>
                <option value="random" [selected]="local.selectedCell()?.method === 'random'">
                  Random search
                </option>
              </select>
            </label>
            <label
              >Search repetition
              <select
                aria-label="Search repetition"
                (change)="changeRun('seed', $event)"
                [disabled]="local.loadingProposals()"
              >
                @for (seed of seeds(); track seed) {
                  <option [value]="seed" [selected]="local.selectedCell()?.seed === seed">
                    {{ seed + 1 }} (seed {{ seed }})
                  </option>
                }
              </select>
            </label>
          </div>
        }
        <div class="list-filters">
          <label
            >Sort proposals
            <select aria-label="Sort proposals" [value]="sort()" (change)="changeSort($event)">
              <option value="closest">Smallest gap</option>
              <option value="minimal">Smallest change</option>
              <option value="support">Strongest recorded support</option>
              @if (!priority()) {
                <option value="sequence">Proposal number</option>
              }
            </select>
          </label>
          <label class="check"
            ><input
              type="checkbox"
              [checked]="replaysOnly()"
              (change)="replaysOnly.set($any($event.target).checked)"
            />Saved replays only</label
          >
        </div>
        <details class="outcome-filters">
          <summary>Filter outcomes</summary>
          <label
            >Show outcomes
            <select
              aria-label="Show outcomes"
              [value]="outcome()"
              (change)="outcome.set($any($event.target).value)"
            >
              <option value="all">All outcomes</option>
              <option value="eligible">Passed realism and reference checks</option>
              <option value="support-rejected">Outside recorded behavior</option>
              <option value="pipeline-rejected">Validity rejected</option>
            </select>
          </label>
        </details>
        <p class="list-status" role="status">
          {{
            local.loadingProposals()
              ? 'Loading the selected scenario…'
              : rows().length + ' proposals shown'
          }}
          @if (priority()) {
            · ranked shortlist. Choose a scenario to browse every proposal.
          }
        </p>
        <div class="compare-hint">
          <span>{{ compared().length }}/2 selected for comparison</span>
          <button
            type="button"
            [disabled]="compared().length === 0"
            (click)="comparisonRequested.emit()"
          >
            View comparison
          </button>
        </div>
      </header>
      <div
        class="proposal-rows"
        aria-label="Scenario proposals"
        [attr.aria-busy]="local.loadingProposals()"
      >
        @if (!local.loadingProposals()) {
          @for (proposal of rows(); track proposal.cellId + ':' + proposal.proposalNumber) {
            <article [class.selected]="selected(proposal)">
              <button
                class="inspect"
                type="button"
                [attr.aria-pressed]="selected(proposal)"
                [attr.aria-label]="'Inspect ' + identity(proposal)"
                (click)="inspectRequested.emit(proposal)"
              >
                <span class="row-title"
                  >Scenario {{ proposal.selectionOrder }} · Proposal
                  {{ proposal.proposalNumber }}</span
                >
                <span
                  >{{ proposal.method === 'bayesian' ? 'Bayesian' : 'Random' }} · repetition
                  {{ proposal.seed + 1 }} (seed {{ proposal.seed }})</span
                >
                <span class="mutation">{{
                  proposal.objectiveAvailable
                    ? '+' +
                      proposal.brakingOnsetOffsetSeconds.toFixed(1) +
                      ' s onset · ' +
                      (proposal.speedMultiplier * 100).toFixed(1) +
                      '% speed'
                    : 'Change rejected before evaluation'
                }}</span>
                <span class="row-result"
                  ><strong>{{ clearance(proposal) }}</strong
                  ><span [class.replay]="proposal.trajectoryAvailable">{{
                    proposal.trajectoryAvailable ? 'Saved replay' : 'Metrics only'
                  }}</span></span
                >
              </button>
              <button
                class="compare"
                type="button"
                [attr.aria-label]="(slot(proposal) ? 'Remove ' : 'Compare ') + identity(proposal)"
                [attr.aria-pressed]="!!slot(proposal)"
                [disabled]="!slot(proposal) && compared().length === 2"
                (click)="compareRequested.emit(proposal)"
              >
                {{ slot(proposal) ? 'Remove ' + slot(proposal) : 'Compare' }}
              </button>
            </article>
          } @empty {
            <div class="empty">
              <strong>{{
                replaysOnly()
                  ? 'No saved replays in this selection.'
                  : 'No proposals match this outcome filter.'
              }}</strong>
              <p>
                {{
                  replaysOnly()
                    ? 'The campaign kept metrics for every proposal, but only selected trajectories. Show all proposals to inspect the measured results.'
                    : 'This search run has no proposals with the selected outcome. Show all proposals or choose another search run.'
                }}
              </p>
              <button type="button" (click)="replaysOnly.set(false); outcome.set('all')">
                Show all proposals
              </button>
            </div>
          }
        }
      </div>
    </section>
  `,
  styleUrl: './proposal-browser.css',
})
export class ProposalBrowser {
  protected readonly local = inject(LocalEvidenceService);
  readonly compared = input<readonly InvestigationProposal[]>([]);
  readonly inspectRequested = output<InvestigationProposal>();
  readonly compareRequested = output<InvestigationProposal>();
  readonly comparisonRequested = output<void>();
  readonly cellRequested = output<string>();
  protected readonly priority = signal(!new URLSearchParams(location.search).has('cell'));
  protected readonly sort = signal('closest');
  protected readonly replaysOnly = signal(false);
  protected readonly outcome = signal('all');
  protected readonly scenarios = computed(() =>
    [...new Set(this.local.cells().map((c) => c.selectionOrder))].sort((a, b) => a - b),
  );
  protected readonly seeds = computed(() =>
    [
      ...new Set(
        this.local
          .cells()
          .filter((c) => c.selectionOrder === this.local.selectedCell()?.selectionOrder)
          .map((c) => c.seed),
      ),
    ].sort((a, b) => a - b),
  );
  protected readonly rows = computed(() => {
    let proposals: readonly InvestigationProposal[];
    if (this.priority()) {
      const investigation = this.local.investigation();
      proposals =
        (this.sort() === 'minimal'
          ? investigation?.smallestMutation
          : this.sort() === 'support'
            ? investigation?.highestSupport
            : investigation?.closestMargin) ?? [];
    } else {
      const cell = this.local.selectedCell();
      proposals = cell
        ? this.local.proposals().map((p) => ({
            ...p,
            cellId: cell.cellId,
            method: cell.method,
            seed: cell.seed,
            selectionOrder: cell.selectionOrder,
            decisiveGate: proposalGate(p),
          }))
        : [];
    }
    return proposals
      .filter((p) => {
        if (this.replaysOnly() && !p.trajectoryAvailable) return false;
        if (this.outcome() === 'eligible')
          return p.pipelinePasses && p.supportPasses === true && p.referencePasses;
        if (this.outcome() === 'support-rejected')
          return p.pipelinePasses && p.supportPasses === false;
        if (this.outcome() === 'pipeline-rejected') return !p.pipelinePasses;
        return true;
      })
      .sort((a, b) => {
        if (this.sort() === 'sequence') return a.proposalNumber - b.proposalNumber;
        if (this.sort() === 'minimal')
          return b.minimality - a.minimality || b.criticality - a.criticality;
        if (this.sort() === 'support')
          return (
            (b.empiricalSupportProbability ?? -1) - (a.empiricalSupportProbability ?? -1) ||
            b.criticality - a.criticality
          );
        return b.criticality - a.criticality || a.proposalNumber - b.proposalNumber;
      });
  });
  protected identity(p: InvestigationProposal): string {
    return `scenario ${p.selectionOrder} ${p.method} seed ${p.seed} proposal ${p.proposalNumber}`;
  }
  protected selected(p: InvestigationProposal): boolean {
    return (
      this.local.selectedCellId() === p.cellId &&
      this.local.selectedProposalNumber() === p.proposalNumber
    );
  }
  protected slot(p: InvestigationProposal): string {
    const index = this.compared().findIndex(
      (c) => c.cellId === p.cellId && c.proposalNumber === p.proposalNumber,
    );
    return index < 0 ? '' : index === 0 ? 'A' : 'B';
  }
  protected clearance(p: InvestigationProposal): string {
    return p.objectiveAvailable && p.criticality > 0
      ? Math.max(1 / p.criticality - 1, 0).toFixed(2) + ' m gap'
      : 'Gap not evaluated';
  }
  protected changeSort(event: Event): void {
    this.sort.set((event.target as HTMLSelectElement).value);
  }
  protected changeScenario(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.priority.set(value === 'priority');
    if (value === 'priority') {
      if (this.sort() === 'sequence') this.sort.set('closest');
      return;
    }
    const selected = this.local.selectedCell();
    const candidates = this.local.cells().filter((c) => c.selectionOrder === Number(value));
    const cell =
      candidates.find((c) => c.method === selected?.method && c.seed === selected?.seed) ??
      candidates[0];
    if (cell) this.cellRequested.emit(cell.cellId);
  }
  protected changeRun(field: 'method' | 'seed', event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    const selected = this.local.selectedCell();
    const cell = this.local
      .cells()
      .find(
        (c) =>
          c.selectionOrder === selected?.selectionOrder &&
          c.method === (field === 'method' ? value : selected?.method) &&
          c.seed === (field === 'seed' ? Number(value) : selected?.seed),
      );
    if (cell) this.cellRequested.emit(cell.cellId);
  }
}
