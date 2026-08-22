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

    let text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Workbench');
    expect(text).toContain('Replay sealed planner evidence locally');
    expect(text).toContain('Public proposals3,200');
    const evidence = Array.from(
      fixture.nativeElement.querySelectorAll('nav button') as NodeListOf<HTMLButtonElement>,
    ).find((candidate) => candidate.textContent?.includes('Evidence'))!;
    evidence.click();
    fixture.detectChanges();
    const runtime = Array.from(
      fixture.nativeElement.querySelectorAll(
        '.evidence-sections button',
      ) as NodeListOf<HTMLButtonElement>,
    ).find((candidate) => candidate.textContent?.includes('Model & runtime'))!;
    runtime.click();
    fixture.detectChanges();
    text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Models, deployment, and promotion gates');
    expect(text).toContain('Test ADE0.418 m');
    expect(text).toContain('baseline 0.870 m');
    expect(text).toContain('Released 128-scenario model · Tesla T4 · 500 measured');
    expect(text).toContain('FP16 · batch 10.197 ms');
    expect(text).toContain('C++17 · batch 10.124 ms');
    expect(text).toContain('0.56 cm RMSE');
    expect(text).toContain('Active-risk promotion gate · stopped');
    expect(text).toContain('Neighbor-context ablation · stopped');
    expect(text).toContain('Scale-model deployment · pending');
    expect(text).toContain('does not inherit old runtime results');
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

    expect(fixture.nativeElement.textContent).toContain('Review candidate counterfactuals');
    expect(fixture.nativeElement.textContent).toContain('Open local workspace');
  });

  it('keeps measured model and runtime evidence reachable with local records connected', () => {
    const fixture = TestBed.createComponent(ProductShell);
    const local = TestBed.inject(LocalEvidenceService);
    local.state.set('connected');
    fixture.detectChanges();

    const navigation = Array.from(
      fixture.nativeElement.querySelectorAll(
        '.product-header nav button',
      ) as NodeListOf<HTMLButtonElement>,
    );
    navigation.find((candidate) => candidate.textContent?.includes('Evidence'))!.click();
    fixture.detectChanges();
    const runtime = Array.from(
      fixture.nativeElement.querySelectorAll(
        '.evidence-sections button',
      ) as NodeListOf<HTMLButtonElement>,
    ).find((candidate) => candidate.textContent?.includes('Model & runtime'))!;
    runtime.click();
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Models, deployment, and promotion gates');
    expect(text).toContain('real data · no synthetic training');
    expect(text).toContain('FP16 · batch 10.197 ms');
    expect(text).toContain('Quality and deployment probes are kept separate');
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
