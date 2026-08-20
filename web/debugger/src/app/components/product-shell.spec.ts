import { TestBed } from '@angular/core/testing';
import { LocalEvidenceService } from '../local-evidence.service';
import { ProductShell } from './product-shell';

describe('ProductShell', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('opens on the investigation tool with an honest public aggregate mode', () => {
    const fixture = TestBed.createComponent(ProductShell);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Trace why a proposal did');
    expect(text).toContain('Public aggregate mode');
    expect(text).toContain('data-access boundary');
  });

  it('makes investigation first class without exposing local records while disconnected', () => {
    const fixture = TestBed.createComponent(ProductShell);
    fixture.detectChanges();
    const button = Array.from(
      fixture.nativeElement.querySelectorAll('nav button') as NodeListOf<HTMLButtonElement>,
    ).find((candidate) => candidate.textContent?.includes('Investigate'))!;
    button.click();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Trace why a proposal did');
    expect(fixture.nativeElement.textContent).toContain('Connect local evidence');
  });

  it('renders measured proposal gates after local evidence is connected', () => {
    const fixture = TestBed.createComponent(ProductShell);
    const local = TestBed.inject(LocalEvidenceService);
    local.state.set('connected');
    local.cells.set([
      {
        cellId: 'cell_opaque',
        method: 'bayesian',
        seed: 0,
        selectionOrder: 1,
        proposalCount: 32,
        pipelineValidCount: 28,
        supportAndPipelineValidCount: 24,
        qualifyingFailureCount: 0,
        validRatePercent: 75,
        finalFeasibleHypervolume: 0.3,
      },
    ]);
    local.selectedCellId.set('cell_opaque');
    local.proposals.set([
      {
        proposalNumber: 1,
        attemptStatus: 'accepted',
        normalizedMutationDistance: 0.8,
        brakingOnsetOffsetSeconds: 0.2,
        speedMultiplier: 0.8,
        empiricalSupportProbability: 0.6,
        supportPasses: true,
        objectiveAvailable: true,
        criticality: 0.4,
        minimality: 0.7,
        pipelinePasses: true,
        referencePasses: true,
        policySpecificAvoidableFailure: false,
        testedMutatedFailure: false,
        referenceMutatedSuccess: true,
        physicalRollouts: 6,
      },
    ]);
    local.selectedProposalNumber.set(1);
    fixture.detectChanges();
    const button = Array.from(
      fixture.nativeElement.querySelectorAll('nav button') as NodeListOf<HTMLButtonElement>,
    ).find((candidate) => candidate.textContent?.includes('Investigate'))!;
    button.click();
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Tested controller did not fail');
    expect(text).toContain('Reference controller');
    expect(text).toContain('Proposal trajectory is not stored');
  });
});
