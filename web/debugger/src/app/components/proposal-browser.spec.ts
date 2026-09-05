import { TestBed } from '@angular/core/testing';
import { LocalEvidenceService } from '../local-evidence.service';
import { API_PROPOSALS, API_INVESTIGATION } from '../local-evidence.test-fixtures';
import { parseProposals, parseCampaignInvestigation } from '../local-evidence.parsers';
import { LocalCell } from '../local-evidence.types';
import { ProposalBrowser, proposalGate } from './proposal-browser';

describe('ProposalBrowser', () => {
  afterEach(() => {
    history.replaceState(null, '', '/');
    TestBed.resetTestingModule();
  });
  function setup() {
    const fixture = TestBed.createComponent(ProposalBrowser);
    const local = TestBed.inject(LocalEvidenceService);
    const first: LocalCell = {
      cellId: 'cell_first',
      method: 'bayesian',
      seed: 0,
      selectionOrder: 1,
      proposalCount: 32,
      pipelineValidCount: 28,
      supportAndPipelineValidCount: 24,
      qualifyingFailureCount: 0,
      validRatePercent: 75,
      finalFeasibleHypervolume: 0.3,
    };
    local.cells.set([
      first,
      { ...first, cellId: 'cell_second', selectionOrder: 8 },
      { ...first, cellId: 'cell_other_method', selectionOrder: 8, method: 'random' },
      { ...first, cellId: 'cell_other_seed', selectionOrder: 8, seed: 1 },
    ]);
    local.selectedCellId.set('cell_second');
    local.proposals.set(parseProposals(API_PROPOSALS));
    local.selectedProposalNumber.set(1);
    local.investigation.set(parseCampaignInvestigation(API_INVESTIGATION));
    fixture.detectChanges();
    return { fixture, local };
  }
  it('shows the real selected scenario on initial rendering rather than the first option', () => {
    history.replaceState(null, '', '/?view=evidence&cell=cell_second');
    const { fixture } = setup();
    expect(
      fixture.nativeElement.querySelector('select[aria-label="Recorded scenario"]').value,
    ).toBe('8');
  });
  it('provides explicit scenario and method selection without a 100-entry picker', () => {
    history.replaceState(null, '', '/?cell=cell_second');
    const { fixture } = setup();
    const selected: string[] = [];
    fixture.componentInstance.cellRequested.subscribe((id) => selected.push(id));
    const method = fixture.nativeElement.querySelector(
      'select[aria-label="Search method"]',
    ) as HTMLSelectElement;
    method.value = 'random';
    method.dispatchEvent(new Event('change'));
    expect(selected).toEqual(['cell_other_method']);
    const repetition = fixture.nativeElement.querySelector(
      'select[aria-label="Search repetition"]',
    ) as HTMLSelectElement;
    repetition.value = '1';
    repetition.dispatchEvent(new Event('change'));
    expect(selected[1]).toBe('cell_other_seed');
  });
  it('makes comparison possible outside the campaign shortlist with full identity', () => {
    history.replaceState(null, '', '/?cell=cell_second');
    const { fixture } = setup();
    const items: unknown[] = [];
    fixture.componentInstance.compareRequested.subscribe((item) => items.push(item));
    fixture.nativeElement.querySelector('button.compare').click();
    expect(items[0]).toMatchObject({ cellId: 'cell_second', selectionOrder: 8, proposalNumber: 1 });
  });
  it('does not silently replace a third selection and permits removing existing choices', () => {
    history.replaceState(null, '', '/?cell=cell_second');
    const { fixture, local } = setup();
    const row = {
      ...local.proposals()[0],
      cellId: 'cell_second',
      selectionOrder: 8,
      method: 'bayesian' as const,
      seed: 0,
      decisiveGate: 'tested_controller_failure',
    };
    fixture.componentRef.setInput('compared', [
      row,
      { ...row, cellId: 'different', proposalNumber: 3 },
    ]);
    fixture.detectChanges();
    const buttons = fixture.nativeElement.querySelectorAll(
      'button.compare',
    ) as NodeListOf<HTMLButtonElement>;
    expect(buttons[0].disabled).toBe(false);
    expect(buttons[0].textContent).toContain('Remove A');
    for (const button of Array.from(buttons).slice(1)) expect(button.disabled).toBe(true);
  });
  it('explains a no-replay filter and lets the user recover without changing data', () => {
    history.replaceState(null, '', '/?cell=cell_second');
    const { fixture, local } = setup();
    const count = local.proposals().length;
    const checkbox = fixture.nativeElement.querySelector(
      'input[type="checkbox"]',
    ) as HTMLInputElement;
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No saved replays in this selection');
    const recover = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find((b) => b.textContent?.trim() === 'Show all proposals')!;
    recover.click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('button.inspect').length).toBe(count);
  });
  it('keeps unevaluated support separate from a tested planner success', () => {
    const proposal = parseProposals(API_PROPOSALS)[0];
    expect(proposalGate({ ...proposal, supportPasses: null })).toBe('empirical_support');
    expect(proposalGate({ ...proposal, attemptStatus: 'mutation_rejected' })).toBe(
      'mutation_geometry',
    );
  });
});
