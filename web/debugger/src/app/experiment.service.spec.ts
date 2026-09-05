import { TestBed } from '@angular/core/testing';
import { ExperimentService, parseExperimentJob } from './experiment.service';
import { LocalEvidenceService } from './local-evidence.service';

const JOB = {
  job_id: 'a'.repeat(32),
  config: { selection_order: 1, braking_onset_offset_s: 0, speed_multiplier: 0.9 },
  status: 'running',
  stage: 'starting',
  stage_label: 'Starting',
  created_at: 1,
  elapsed_seconds: 0,
  events: [],
  result: null,
  error: null,
};

describe('experiment response contract', () => {
  it('accepts a running job but rejects malformed metrics and configurations', () => {
    expect(parseExperimentJob(JOB).status).toBe('running');
    expect(() => parseExperimentJob({ ...JOB, job_id: '../../outside' })).toThrow();
    expect(() =>
      parseExperimentJob({ ...JOB, config: { ...JOB.config, speed_multiplier: 2 } }),
    ).toThrow();
    expect(() => parseExperimentJob({ ...JOB, events: [null] })).toThrow();
    expect(() => parseExperimentJob({ ...JOB, error: {} })).toThrow();
    expect(() =>
      parseExperimentJob({
        ...JOB,
        result: {
          decision: 'not_qualified',
          explanation: 'Bounded result',
          gates: {},
          result_sha256: 'b'.repeat(64),
          controllers: { tested: {} },
        },
      }),
    ).toThrow('controller');
  });
});

describe('ExperimentService lifecycle', () => {
  let local: LocalEvidenceService;
  let experiments: ExperimentService;
  let fetchMock: ReturnType<typeof vi.fn>;
  beforeEach(() => {
    fetchMock = vi.fn().mockImplementation((url: string) =>
      Promise.resolve(
        new Response(JSON.stringify(url.endsWith('/readiness') ? { ready: true } : []), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );
    vi.stubGlobal('fetch', fetchMock);
    TestBed.configureTestingModule({});
    local = TestBed.inject(LocalEvidenceService);
    experiments = TestBed.inject(ExperimentService);
    local.state.set('connected');
    TestBed.tick();
  });
  afterEach(() => {
    TestBed.resetTestingModule();
    vi.unstubAllGlobals();
  });

  it('does not restore private history from a request that finishes after disconnect', async () => {
    let resolveHistory!: (value: Response) => void;
    fetchMock.mockImplementation((url: string) =>
      url.endsWith('/readiness')
        ? Promise.resolve(new Response(JSON.stringify({ ready: true })))
        : new Promise((resolve) => {
            resolveHistory = resolve;
          }),
    );
    const refresh = experiments.refresh();
    local.state.set('disconnected');
    TestBed.tick();
    resolveHistory(new Response(JSON.stringify([JOB])));
    await refresh;
    expect(experiments.jobs()).toEqual([]);
    expect(experiments.readiness()).toBeUndefined();
  });

  it('reuses submission identity after a lost response', async () => {
    const requests: object[] = [];
    fetchMock.mockImplementation((url: string, options?: RequestInit) => {
      if (options?.method === 'POST') {
        requests.push(JSON.parse(options.body as string));
        return Promise.reject(new Error('Test-only lost response'));
      }
      return Promise.resolve(
        new Response(JSON.stringify(url.endsWith('/readiness') ? { ready: true } : [])),
      );
    });
    await experiments.start(JOB.config);
    await experiments.start(JOB.config);
    expect(requests).toHaveLength(2);
    expect(requests[0]).toEqual(requests[1]);
    expect(experiments.error()).toBe('Test-only lost response');
  });
});
