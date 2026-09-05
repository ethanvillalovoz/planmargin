import { TestBed } from '@angular/core/testing';
import { ModelsWorkspace } from './models-workspace';
import { MODEL_STUDIES } from '../model-studies';

describe('model evidence browser', () => {
  afterEach(() => {
    TestBed.resetTestingModule();
    window.history.replaceState(null, '', '/');
    vi.restoreAllMocks();
  });
  it('shows a baseline comparison and links to actual reports instead of a metric billboard', () => {
    const fixture = TestBed.createComponent(ModelsWorkspace);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('table').textContent).toContain('0.870 m');
    expect(fixture.nativeElement.querySelector('a').href).toContain(
      'experiments/torch-trajectory-model-v2.json',
    );
    expect(fixture.nativeElement.querySelector('details').open).toBe(false);
    expect(fixture.nativeElement.querySelectorAll('nav button')).toHaveLength(6);
  });
  it('switches study, exposes failed gates, and retains source boundaries', () => {
    const fixture = TestBed.createComponent(ModelsWorkspace);
    fixture.componentRef.setInput('initialStudy', 'runtime');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('0.000046 m');
    expect(fixture.nativeElement.textContent).toContain('0.101 m maximum drift');
    fixture.nativeElement.querySelectorAll('nav button')[5].click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('#study-title').textContent).toBe(
      'Residual FP16 candidate',
    );
    expect(fixture.nativeElement.textContent).toContain('TensorRT has not been measured');
    expect(window.location.search).toContain('study=residual');
  });
  it('handles clipboard success and refusal without claiming a copy succeeded', async () => {
    const fixture = TestBed.createComponent(ModelsWorkspace);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
    fixture.detectChanges();
    const button = fixture.nativeElement.querySelector('.reproduction button') as HTMLButtonElement;
    button.click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role=status]').textContent).toBe('Copied');
    writeText.mockRejectedValueOnce(new Error('denied'));
    button.click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role=status]').textContent).toContain(
      'Clipboard unavailable',
    );
  });
  it('keeps each study distinct and supplies actionable provenance', () => {
    expect(new Set(MODEL_STUDIES.map((s) => s.id)).size).toBe(MODEL_STUDIES.length);
    for (const study of MODEL_STUDIES) {
      expect(study.report).toBeTruthy();
      expect(study.guide).toBeTruthy();
      expect(study.gates.length).toBeGreaterThan(0);
      for (const row of study.rows) expect(row.values.length + 1).toBe(study.columns.length);
    }
    expect(
      MODEL_STUDIES.find((s) => s.id === 'runtime')?.gates.filter((g) => !g.passed),
    ).toHaveLength(1);
  });
});
