import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { LocalEvidenceService } from '../local-evidence.service';
import { SimulatorStore } from '../simulator.store';
import { ProductShell } from './product-shell';

describe('ProductShell', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe(): void {}
        disconnect(): void {}
      },
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    TestBed.resetTestingModule();
  });

  it('opens on an honest local-workspace boundary with public evidence available', () => {
    const fixture = TestBed.createComponent(ProductShell);
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Workbench');
    expect(text).toContain('Replay sealed planner evidence locally');
    expect(text).toContain('Public proposals3,200');
    expect(text).not.toContain('No qualifying planner failure was found');
  });

  it('makes investigation first class without exposing local records while disconnected', () => {
    const fixture = TestBed.createComponent(ProductShell);
    fixture.detectChanges();
    const button = Array.from(
      fixture.nativeElement.querySelectorAll('nav button') as NodeListOf<HTMLButtonElement>,
    ).find((candidate) => candidate.textContent?.includes('Evidence'))!;
    button.click();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Review planner regressions');
    expect(fixture.nativeElement.textContent).toContain('Open local workspace');
  });

  it('maps task navigation to the correct planning and sensor workspaces', () => {
    const fixture = TestBed.createComponent(ProductShell);
    const simulator = TestBed.inject(SimulatorStore);
    fixture.detectChanges();
    const buttons = Array.from(
      fixture.nativeElement.querySelectorAll('nav button') as NodeListOf<HTMLButtonElement>,
    );

    buttons.find((candidate) => candidate.textContent?.includes('Sensors'))!.click();
    fixture.detectChanges();
    expect(simulator.sensorMode()).toBe('camera');

    buttons.find((candidate) => candidate.textContent?.includes('Workbench'))!.click();
    fixture.detectChanges();
    expect(simulator.sensorMode()).toBe('planning');
  });

  it('exposes the evidence assistant from the primary product header', () => {
    const fixture = TestBed.createComponent(ProductShell);
    const local = TestBed.inject(LocalEvidenceService);
    const simulator = TestBed.inject(SimulatorStore);
    local.state.set('connected');
    fixture.detectChanges();

    const button = Array.from(
      fixture.nativeElement.querySelectorAll(
        '.product-header button',
      ) as NodeListOf<HTMLButtonElement>,
    ).find((candidate) => candidate.textContent?.includes('Ask analysis'))!;
    expect(button.disabled).toBe(false);

    button.click();

    expect(simulator.assistantOpen()).toBe(true);
    expect(simulator.sensorMode()).toBe('planning');
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
        trajectoryAvailable: false,
        replayRunId: null,
      },
    ]);
    local.selectedProposalNumber.set(1);
    fixture.detectChanges();
    const button = Array.from(
      fixture.nativeElement.querySelectorAll('nav button') as NodeListOf<HTMLButtonElement>,
    ).find((candidate) => candidate.textContent?.includes('Evidence'))!;
    button.click();
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Tested planner still succeeds');
    expect(text).toContain('Reference planner');
    expect(text).toContain('Reproducible replay');
    expect(text).toContain('Safety result');
    expect(text).toContain('Change size');
    expect(text).not.toContain('Criticality 0.400');
    expect(text).toContain('Proposal trajectory is not retained');
  });
});
