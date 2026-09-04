import { TestBed } from '@angular/core/testing';
import { OperationsWorkspace } from './operations-workspace';

describe('OperationsWorkspace', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('separates healthy execution, behavior outcome, coverage gaps, and promotion issues', () => {
    const fixture = TestBed.createComponent(OperationsWorkspace);
    fixture.detectChanges();
    let text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Execution healthy100/100');
    expect(text).toContain('Behavior outcome0qualifying regressions');
    expect(text).toContain('7/7 stages healthy');
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
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Local numerical proxy passed');
    expect(text).toContain('PM-TRT-011');
    expect(text).toContain('No gate is marked failed');
    expect(text).not.toContain('Scaled FP16 drift exceeds');
    expect(text).not.toContain('Learned ranker did not generalize');
  });
});
