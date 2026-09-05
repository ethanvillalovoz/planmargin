import { TestBed } from '@angular/core/testing';
import { OperationsWorkspace } from './operations-workspace';

describe('OperationsWorkspace', () => {
  it('deep-links triage to the corresponding model evidence and restores the selected issue', () => {
    window.history.replaceState(null, '', '/?view=health&section=triage&issue=PM-RANK-006');
    const fixture = TestBed.createComponent(OperationsWorkspace);
    let study = '';
    fixture.componentInstance.openModelStudy.subscribe((id) => (study = id));
    fixture.detectChanges();
    const button = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find((b) => b.textContent?.includes('Inspect model evidence'))!;
    button.click();
    expect(study).toBe('ranker');
    expect(fixture.nativeElement.querySelector('.context-inspector').textContent).toContain(
      'Learned ranker',
    );
  });
  afterEach(() => {
    window.history.replaceState(null, '', '/');
    TestBed.resetTestingModule();
  });

  it('opens a requested review section for reproducible local inspection', () => {
    window.history.replaceState(null, '', '/?section=coverage');
    const fixture = TestBed.createComponent(OperationsWorkspace);
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Versioned behavior coverage');
    expect(fixture.nativeElement.querySelector('.ops-tabs button.active').textContent).toContain(
      'Coverage',
    );
  });

  it('separates release health, versioned coverage, and measured decisions', () => {
    const fixture = TestBed.createComponent(OperationsWorkspace);
    fixture.detectChanges();
    let text = fixture.nativeElement.textContent as string;
    expect(text).toContain('The saved test run passed its checks.');
    expect(text).toContain('120/120test cells');
    expect(text).toContain('7/7checks passed');
    expect(text).toContain('Pipeline stages');
    expect(text).toContain('Scaled FP16 drift exceeds the promotion gate');

    const coverage = Array.from(
      fixture.nativeElement.querySelectorAll('.ops-tabs button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent?.includes('Coverage'))!;
    coverage.click();
    fixture.detectChanges();
    text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Coverage that can be regenerated and reviewed.');
    expect(text).toContain('Command-dropout fallback');
    expect(text).toContain('80/80');
    expect(text).toContain('Assistance handoff recovery');
    expect(text).toContain('90/90');
    expect(text).toContain('Cross-simulator agreement');
    expect(text).toContain('Not covered');
  });

  it('filters and opens measured issue details', () => {
    const fixture = TestBed.createComponent(OperationsWorkspace);
    fixture.detectChanges();
    const issues = Array.from(
      fixture.nativeElement.querySelectorAll('.ops-tabs button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent?.includes('Triage'))!;
    issues.click();
    fixture.detectChanges();
    const pending = Array.from(
      fixture.nativeElement.querySelectorAll('.filter-row button') as NodeListOf<HTMLButtonElement>,
    ).find((button) => button.textContent?.includes('Pending'))!;
    pending.click();
    fixture.detectChanges();
    const triageText = fixture.nativeElement.querySelector('.triage-workspace')
      .textContent as string;
    const inspectorText = fixture.nativeElement.querySelector('.context-inspector')
      .textContent as string;
    expect(triageText).toContain('Local numerical proxy passed');
    expect(triageText).toContain('PM-TRT-011');
    expect(inspectorText).toContain('deployment-evidence completeness gate');
    expect(triageText).not.toContain('Scaled FP16 drift exceeds');
    expect(triageText).not.toContain('Learned ranker did not generalize');
  });

  it('opens the retained planning replay from the operations command bar', () => {
    const fixture = TestBed.createComponent(OperationsWorkspace);
    fixture.detectChanges();
    let opened = false;
    fixture.componentInstance.openScenarioLab.subscribe(() => (opened = true));
    fixture.nativeElement.querySelector('.primary-action').click();
    expect(opened).toBe(true);
  });
});
