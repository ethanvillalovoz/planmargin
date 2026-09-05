import { TestBed } from '@angular/core/testing';
import { ExperimentWorkspace } from './experiment-workspace';
import { ExperimentService, ExperimentJob } from '../experiment.service';
import { LocalEvidenceService } from '../local-evidence.service';

describe('experiment draft and saved-result separation', () => {
  afterEach(() => {
    TestBed.resetTestingModule();
    vi.unstubAllGlobals();
    window.history.replaceState(null, '', '/');
  });
  it('keeps edits on internal navigation and labels a different prior run without executing it', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise(() => {})),
    );
    const first = TestBed.createComponent(ExperimentWorkspace);
    TestBed.inject(LocalEvidenceService).state.set('connected');
    const experiments = TestBed.inject(ExperimentService);
    const job: ExperimentJob = {
      job_id: 'a'.repeat(32),
      config: { selection_order: 8, braking_onset_offset_s: 0.2, speed_multiplier: 0.879 },
      status: 'cancelled',
      stage: 'loading',
      stage_label: 'Cancelled',
      created_at: 1,
      elapsed_seconds: 5,
      events: [],
      result: null,
      error: null,
    };
    experiments.jobs.set([job]);
    experiments.selectedId.set(job.job_id);
    const start = vi.spyOn(experiments, 'start');
    first.detectChanges();
    expect(first.nativeElement.querySelector('.result-context').textContent).toContain(
      'does not match',
    );
    const input = first.nativeElement.querySelector('#experiment-speed') as HTMLInputElement;
    input.value = '0.85';
    input.dispatchEvent(new Event('input'));
    first.detectChanges();
    first.destroy();
    const second = TestBed.createComponent(ExperimentWorkspace);
    second.detectChanges();
    expect(second.nativeElement.querySelector('#experiment-speed').value).toBe('0.85');
    expect(start).not.toHaveBeenCalled();
    second.nativeElement.querySelector('.rerun').click();
    second.detectChanges();
    expect(second.nativeElement.querySelector('.result-context').textContent).toContain(
      'matches the configuration',
    );
    expect(second.nativeElement.querySelector('#experiment-speed').value).toBe('0.879');
    expect(start).not.toHaveBeenCalled();
  });
});
