import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { LocalEvidenceService } from '../local-evidence.service';
import { SimulatorStore } from '../simulator.store';
import { ProductShell } from './product-shell';
import { DebuggerStore } from '../debugger.store';
import { API_RUN } from '../local-evidence.test-fixtures';
import { parseLocalRun } from '../local-evidence.parsers';

describe('ProductShell', () => {
  it('keeps an experiment replay selected while visiting models and returning', () => {
    const fixture = TestBed.createComponent(ProductShell);
    const runId = 'experiment_' + 'a'.repeat(32);
    TestBed.inject(DebuggerStore).loadRun({ ...parseLocalRun(API_RUN), runId });
    fixture.detectChanges();
    const nav = () =>
      Array.from(
        fixture.nativeElement.querySelectorAll(
          '.product-header nav button',
        ) as NodeListOf<HTMLButtonElement>,
      );
    nav()
      .find((button) => button.textContent?.trim() === 'Models')!
      .click();
    fixture.detectChanges();
    expect(new URLSearchParams(location.search).get('experiment')).toBe('a'.repeat(32));
    nav()
      .find((button) => button.textContent?.trim() === 'Replay')!
      .click();
    fixture.detectChanges();
    expect(TestBed.inject(DebuggerStore).run().runId).toBe(runId);
    expect(new URLSearchParams(location.search).get('experiment')).toBe('a'.repeat(32));
  });
  beforeEach(() => {
    vi.stubGlobal('scrollTo', vi.fn());
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe(): void {}
        disconnect(): void {}
      },
    );
    vi.stubGlobal('matchMedia', () => ({
      matches: false,
      addEventListener(): void {},
      removeEventListener(): void {},
    }));
  });

  afterEach(() => {
    window.history.replaceState(null, '', '/');
    vi.unstubAllGlobals();
    TestBed.resetTestingModule();
  });

  it('opens a requested evidence surface for reproducible local inspection', () => {
    window.history.replaceState(null, '', '/?view=evidence&panel=runtime');
    const fixture = TestBed.createComponent(ProductShell);
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Models & runtime');
    expect(fixture.nativeElement.textContent).toContain('Trajectory prediction');
  });

  it('waits for the initial replay instead of rendering an empty debugger store', () => {
    window.history.replaceState(null, '', '/?view=replay');
    const fixture = TestBed.createComponent(ProductShell);
    TestBed.inject(LocalEvidenceService).state.set('connected');
    expect(() => fixture.detectChanges()).not.toThrow();
    expect(fixture.nativeElement.textContent).toContain('Loading verified planning evidence');
    expect(fixture.nativeElement.querySelector('app-simulator-workspace')).toBeNull();
  });

  it('explains the optional sensor setup without a fictitious timeline in planning-only mode', () => {
    window.history.replaceState(null, '', '/?view=sensors');
    const fixture = TestBed.createComponent(ProductShell);
    const local = TestBed.inject(LocalEvidenceService);
    local.state.set('connected');
    local.campaignAvailable.set(false);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain(
      'Sensor lab is not loaded in planning-only mode',
    );
    expect(fixture.nativeElement.querySelector('app-simulator-workspace')).toBeNull();
    expect(fixture.nativeElement.querySelector('input[type=range]')).toBeNull();
  });

  it('opens on counterfactual investigation and keeps the local-workspace boundary explicit', () => {
    const fixture = TestBed.createComponent(ProductShell);
    fixture.detectChanges();

    let text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Campaign');
    expect(text).toContain('Counterfactual investigation');
    expect(text).toContain('0 qualifying regressions');
    expect(text).not.toContain('120/120test cells');
    expect(text).not.toContain('No retained replay loaded');
    const workbench = Array.from(
      fixture.nativeElement.querySelectorAll('nav button') as NodeListOf<HTMLButtonElement>,
    ).find((candidate) => candidate.textContent?.includes('Replay'))!;
    workbench.click();
    fixture.detectChanges();
    text = fixture.nativeElement.textContent as string;
    expect(text).toContain('No retained replay loaded');
    expect(text).toContain('Campaign proposals3,200');

    const evidence = Array.from(
      fixture.nativeElement.querySelectorAll('nav button') as NodeListOf<HTMLButtonElement>,
    ).find((candidate) => candidate.textContent?.includes('Investigate'))!;
    evidence.click();
    fixture.detectChanges();
    const runtime = Array.from(
      fixture.nativeElement.querySelectorAll(
        '.product-header nav button',
      ) as NodeListOf<HTMLButtonElement>,
    ).find((candidate) => candidate.textContent?.includes('Models'))!;
    runtime.click();
    fixture.detectChanges();
    text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Trajectory prediction');
    expect(text).toContain('0.418 m');
    expect(text).toContain('0.870 m');
    expect(text).toContain('Open source report');
    const runtimeStudy = Array.from(
      fixture.nativeElement.querySelectorAll(
        'app-models-workspace nav button',
      ) as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent?.includes('TensorRT deployment'))!;
    runtimeStudy.click();
    fixture.detectChanges();
    text = fixture.nativeElement.textContent as string;
    expect(text).toContain('0.393 ms');
    expect(text).toContain('0.101 m maximum drift');
    expect(text).toContain('Independent C++17 benchmark');
    expect(text).not.toContain('No qualifying planner failure was found');
  });

  it('makes investigation first class without exposing local records while disconnected', () => {
    const fixture = TestBed.createComponent(ProductShell);
    fixture.detectChanges();
    const button = Array.from(
      fixture.nativeElement.querySelectorAll('nav button') as NodeListOf<HTMLButtonElement>,
    ).find((candidate) => candidate.textContent?.includes('Investigate'))!;
    button.click();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Published aggregate evidence');
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
    navigation.find((candidate) => candidate.textContent?.includes('Investigate'))!.click();
    fixture.detectChanges();
    const runtime = Array.from(
      fixture.nativeElement.querySelectorAll(
        '.product-header nav button',
      ) as NodeListOf<HTMLButtonElement>,
    ).find((candidate) => candidate.textContent?.includes('Models'))!;
    runtime.click();
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Trajectory prediction');
    expect(text).toContain('1,024 real WOMD scenarios');
    expect(text).toContain('0.418 m');
    expect(text).toContain('These models do not drive the planning replay');
  });

  it('maps task navigation to the correct planning and sensor workspaces', () => {
    const fixture = TestBed.createComponent(ProductShell);
    const simulator = TestBed.inject(SimulatorStore);
    fixture.detectChanges();
    const buttons = Array.from(
      fixture.nativeElement.querySelectorAll('nav button') as NodeListOf<HTMLButtonElement>,
    );

    buttons.find((candidate) => candidate.textContent?.includes('Sensor lab'))!.click();
    fixture.detectChanges();
    expect(simulator.sensorMode()).toBe('camera');

    buttons.find((candidate) => candidate.textContent?.includes('Replay'))!.click();
    fixture.detectChanges();
    expect(simulator.sensorMode()).toBe('planning');
  });

  it('opens the assistant without navigating away or changing the sensor mode', () => {
    const fixture = TestBed.createComponent(ProductShell);
    const local = TestBed.inject(LocalEvidenceService);
    const simulator = TestBed.inject(SimulatorStore);
    local.state.set('connected');
    fixture.detectChanges();

    const button = Array.from(
      fixture.nativeElement.querySelectorAll(
        '.product-header button',
      ) as NodeListOf<HTMLButtonElement>,
    ).find((candidate) => candidate.textContent?.includes('Ask PlanMargin'))!;
    expect(button.disabled).toBe(false);

    const locationBefore = window.location.href;
    const modeBefore = simulator.sensorMode();
    button.click();

    expect(simulator.assistantOpen()).toBe(true);
    expect(simulator.sensorMode()).toBe(modeBefore);
    expect(window.location.href).toBe(locationBefore);
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
    ).find((candidate) => candidate.textContent?.includes('Investigate'))!;
    button.click();
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Tested planner still succeeds');
    expect(text).toContain('Reference planner');
    expect(text).not.toContain('Reproducible replay');
    const explain = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find((item) => item.textContent?.includes('Explain decision'))!;
    explain.click();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Reproducible replay');
    expect(text).toContain('Safety result');
    expect(text).toContain('Change size');
    expect(text).not.toContain('Criticality 0.400');
    expect(text).toContain('Proposal trajectory is not retained');
  });
});
