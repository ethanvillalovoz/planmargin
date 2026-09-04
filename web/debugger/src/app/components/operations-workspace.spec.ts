import { TestBed } from '@angular/core/testing';
import { DebuggerStore } from '../debugger.store';
import { LocalEvidenceService } from '../local-evidence.service';
import { parseLocalRun } from '../local-evidence.parsers';
import { API_RUN } from '../local-evidence.test-fixtures';
import { OperationsWorkspace } from './operations-workspace';

describe('OperationsWorkspace', () => {
  afterEach(() => {
    window.history.replaceState(null, '', '/');
    TestBed.resetTestingModule();
  });

  it('opens a requested review section for reproducible local inspection', () => {
    window.history.replaceState(null, '', '/?section=coverage');
    const fixture = TestBed.createComponent(OperationsWorkspace);
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Behavior coverage');
    expect(fixture.nativeElement.querySelector('.ops-tabs button.active').textContent).toContain(
      'Coverage',
    );
  });

  it('separates healthy execution, behavior outcome, coverage gaps, and promotion issues', () => {
    const fixture = TestBed.createComponent(OperationsWorkspace);
    fixture.detectChanges();
    let text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Executionhealthy100/100 cells complete');
    expect(text).toContain('Behavior outcome0 qualifying regressions');
    expect(text).toContain('Pipeline7/7');
    expect(text).toContain('Scaled FP16 drift exceeds the promotion gate');

    const coverage = Array.from(
      fixture.nativeElement.querySelectorAll('.ops-tabs button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent?.includes('Coverage'))!;
    coverage.click();
    fixture.detectChanges();
    text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Behavior coverage');
    expect(text).toContain('Off-nominal behavior V&V');
    expect(text).toContain('80/80 gates');
    expect(text).toContain('Assistance handoff recovery');
    expect(text).toContain('90/90 gates');
    expect(text).toContain('Cross-simulator agreement');
    expect(text).toContain('Not covered');
  });

  it('filters and opens measured issue details', () => {
    const fixture = TestBed.createComponent(OperationsWorkspace);
    fixture.detectChanges();
    const issues = Array.from(
      fixture.nativeElement.querySelectorAll('.ops-tabs button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent?.includes('Issues'))!;
    issues.click();
    fixture.detectChanges();
    const pending = Array.from(
      fixture.nativeElement.querySelectorAll('.filter-row button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent?.includes('Pending evidence'))!;
    pending.click();
    fixture.detectChanges();
    const text = fixture.nativeElement.querySelector('.issue-workspace').textContent as string;
    expect(text).toContain('Local numerical proxy passed');
    expect(text).toContain('PM-TRT-011');
    expect(text).toContain('No gate is marked failed');
    expect(text).not.toContain('Scaled FP16 drift exceeds');
    expect(text).not.toContain('Learned ranker did not generalize');
  });

  it('moves the real planning replay in one-second increments', () => {
    const fixture = TestBed.createComponent(OperationsWorkspace);
    const local = TestBed.inject(LocalEvidenceService);
    const store = TestBed.inject(DebuggerStore);
    local.state.set('connected');
    const run = parseLocalRun(API_RUN);
    store.loadRun(run);
    fixture.detectChanges();

    const forward = Array.from(
      fixture.nativeElement.querySelectorAll('.transport button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent?.includes('+1 s'))!;
    forward.click();
    fixture.detectChanges();

    const expectedIndex = Math.min(store.sampleCount() - 1, Math.round(1 / run.stepSeconds));
    expect(store.timestepIndex()).toBe(expectedIndex);
    expect(fixture.nativeElement.textContent).toContain(
      `${(expectedIndex * run.stepSeconds).toFixed(1)} s`,
    );
  });
});
