import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { LocalEvidenceService } from '../local-evidence.service';
import { SimulatorStore } from '../simulator.store';
import { ProductShell } from './product-shell';
import { DebuggerStore } from '../debugger.store';
import { API_RUN, API_PROPOSALS } from '../local-evidence.test-fixtures';
import { parseLocalRun, parseProposals } from '../local-evidence.parsers';

describe('ProductShell', () => {
  it('brings the inspector tabs into view and focuses comparison on a narrow screen', () => {
    history.replaceState(null, '', '/?view=evidence');
    const fixture = TestBed.createComponent(ProductShell);
    TestBed.inject(LocalEvidenceService).state.set('connected');
    fixture.detectChanges();
    const tabs = fixture.nativeElement.querySelector('.inspector-tabs') as HTMLElement;
    const scrollIntoView = vi.fn();
    tabs.scrollIntoView = scrollIntoView;
    vi.stubGlobal('innerWidth', 412);
    let reveal: FrameRequestCallback | undefined;
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      reveal = callback;
      return 1;
    });
    const compare = tabs.querySelectorAll('button')[1];
    compare.click();
    fixture.detectChanges();
    reveal?.(0);
    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'start', behavior: 'instant' });
    expect(document.activeElement).toBe(compare);
    expect(compare.getAttribute('aria-pressed')).toBe('true');
  });

  it('opens a visible comparison immediately and keeps both records across supporting pages', () => {
    history.replaceState(null, '', '/?view=evidence&cell=cell_test');
    const fixture = TestBed.createComponent(ProductShell);
    const local = TestBed.inject(LocalEvidenceService);
    local.state.set('connected');
    local.cells.set([
      {
        cellId: 'cell_test',
        method: 'random',
        seed: 0,
        selectionOrder: 2,
        proposalCount: 32,
        pipelineValidCount: 32,
        supportAndPipelineValidCount: 32,
        qualifyingFailureCount: 0,
        validRatePercent: 100,
        finalFeasibleHypervolume: 0.3,
      },
    ]);
    local.selectedCellId.set('cell_test');
    const proposal = parseProposals(API_PROPOSALS)[0];
    local.proposals.set([
      { ...proposal, proposalNumber: 1, criticality: 0.5 },
      { ...proposal, proposalNumber: 2, criticality: 0.25 },
      { ...proposal, proposalNumber: 3, criticality: 0.2 },
    ]);
    local.selectedProposalNumber.set(1);
    fixture.detectChanges();
    const compare = () =>
      Array.from(
        fixture.nativeElement.querySelectorAll(
          'app-proposal-browser button.compare',
        ) as NodeListOf<HTMLButtonElement>,
      );
    compare()[0].click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.comparison-dock')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('app-proposal-browser .comparison-dock')).toBeNull();
    compare()[1].click();
    fixture.detectChanges();
    const table = () =>
      fixture.nativeElement.querySelector('.comparison-table') as HTMLTableElement;
    expect(table().textContent).toContain('1.00 m');
    expect(table().textContent).toContain('3.00 m');
    expect(compare()[2].disabled).toBe(true);
    for (const label of ['Models', 'Investigate']) {
      Array.from(
        fixture.nativeElement.querySelectorAll(
          '.product-header nav button',
        ) as NodeListOf<HTMLButtonElement>,
      )
        .find((b) => b.textContent?.trim() === label)!
        .click();
      fixture.detectChanges();
    }
    expect(table().textContent).toContain('1.00 m');
    expect(table().textContent).toContain('3.00 m');
  });

  it('removes unrelated health and model parameters when returning to Investigate', () => {
    history.replaceState(
      null,
      '',
      '/?view=health&health_source=live&section=health&issue=old&suite=lead_braking&job=old&study=prediction',
    );
    const fixture = TestBed.createComponent(ProductShell);
    fixture.detectChanges();
    Array.from(
      fixture.nativeElement.querySelectorAll(
        '.product-header nav button',
      ) as NodeListOf<HTMLButtonElement>,
    )
      .find((b) => b.textContent?.trim() === 'Investigate')!
      .click();
    fixture.detectChanges();
    const params = new URLSearchParams(location.search);
    expect(params.get('view')).toBe('evidence');
    for (const key of ['health_source', 'section', 'issue', 'suite', 'job', 'study'])
      expect(params.has(key)).toBe(false);
  });

  it('restores saved health context after visiting model evidence', () => {
    history.replaceState(
      null,
      '',
      '/?view=health&health_source=saved&section=triage&issue=PM-TRT-011&suite=lead_braking',
    );
    const fixture = TestBed.createComponent(ProductShell);
    TestBed.inject(LocalEvidenceService).state.set('connected');
    fixture.detectChanges();
    const clickNav = (label: string) => {
      Array.from(
        fixture.nativeElement.querySelectorAll(
          '.product-header nav button',
        ) as NodeListOf<HTMLButtonElement>,
      )
        .find((button) => button.textContent?.trim() === label)!
        .click();
      fixture.detectChanges();
    };
    clickNav('Models');
    expect(new URLSearchParams(location.search).has('health_source')).toBe(false);
    expect(new URLSearchParams(location.search).has('issue')).toBe(false);
    clickNav('Test health');
    const params = new URLSearchParams(location.search);
    expect(params.get('health_source')).toBe('saved');
    expect(params.get('section')).toBe('triage');
    expect(params.get('issue')).toBe('PM-TRT-011');
    expect(params.get('suite')).toBe('lead_braking');
    expect(fixture.nativeElement.querySelector('.context-inspector').textContent).toContain(
      'PM-TRT-011',
    );
    expect(fixture.nativeElement.querySelector('app-live-test-health')).toBeNull();
  });

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
    expect(text).toContain('Closest approach');
    expect(text).toContain('Change size');
    expect(text).not.toContain('Criticality 0.400');
    expect(text).toContain('Proposal trajectory is not retained');
    local.proposals.set([
      {
        ...local.proposals()[0],
        attemptStatus: 'mutation_rejected',
        objectiveAvailable: false,
        criticality: 0,
        minimality: 0,
        pipelinePasses: false,
        testedMutatedFailure: null,
        referenceMutatedSuccess: null,
      },
    ]);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No valid trajectory to replay');
    expect(fixture.nativeElement.textContent).toContain('Not scored');
    expect(fixture.nativeElement.textContent).not.toContain('100% of bounded range');
    expect(fixture.nativeElement.textContent).not.toContain('verified outcomes and metrics');
  });
});
