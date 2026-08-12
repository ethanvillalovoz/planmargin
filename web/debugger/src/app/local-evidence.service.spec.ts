import { TestBed } from '@angular/core/testing';
import {
  API_CAMPAIGN,
  API_CELLS,
  API_HYPOTHESES,
  API_METHODS,
  API_PROPOSALS,
  API_RUN,
  API_RUNS,
} from './local-evidence.test-fixtures';
import { LocalEvidenceService } from './local-evidence.service';

function response(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('LocalEvidenceService', () => {
  let service: LocalEvidenceService;
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith('/health')) {
        return Promise.resolve(response({ status: 'ready', evidence_mode: 'real_local_redacted' }));
      }
      if (url.endsWith('/campaign')) return Promise.resolve(response(API_CAMPAIGN));
      if (url.endsWith('/methods')) return Promise.resolve(response(API_METHODS));
      if (url.endsWith('/hypotheses')) return Promise.resolve(response(API_HYPOTHESES));
      if (url.endsWith('/cells')) return Promise.resolve(response(API_CELLS));
      if (url.endsWith('/runs')) return Promise.resolve(response(API_RUNS));
      if (url.endsWith('/runs/run_opaque')) return Promise.resolve(response(API_RUN));
      if (url.endsWith('/cells/cell_opaque/proposals')) {
        return Promise.resolve(response(API_PROPOSALS));
      }
      return Promise.resolve(response({ detail: 'not found' }, 404));
    });
    vi.stubGlobal('fetch', fetchMock);
    TestBed.configureTestingModule({});
    service = TestBed.inject(LocalEvidenceService);
  });

  afterEach(() => {
    service.disconnect();
    vi.unstubAllGlobals();
    TestBed.resetTestingModule();
  });

  it('connects through fixed no-store loopback requests and loads sealed proposals', async () => {
    const evidence = await service.connect('0123456789abcdef');

    expect(service.state()).toBe('connected');
    expect(evidence.initialRun.synthetic).toBe(false);
    expect(service.proposals()[0].proposalNumber).toBe(1);
    expect(fetchMock).toHaveBeenCalledTimes(8);
    for (const [url, options] of fetchMock.mock.calls as [string, RequestInit][]) {
      expect(url).toMatch(/^http:\/\/127\.0\.0\.1:8765\/api\/v1\//);
      expect(options.cache).toBe('no-store');
      expect(options.credentials).toBe('omit');
      expect(options.referrerPolicy).toBe('no-referrer');
      expect((options.headers as Record<string, string>)['X-PlanMargin-Token']).toBe(
        '0123456789abcdef',
      );
    }

    service.disconnect();
    expect(service.state()).toBe('disconnected');
    expect(service.cells()).toEqual([]);
    expect(service.campaign().mode).toBe('published-aggregate');
  });

  it('does not issue a request for a short token', async () => {
    await expect(service.connect('short')).rejects.toThrow('at least 16');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('redacts connection failures and clears authorization state', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('network failed with sensitive details'));

    await expect(service.connect('0123456789abcdef')).rejects.toThrow();
    expect(service.state()).toBe('error');
    expect(service.error()).toContain('127.0.0.1:8765');
    await expect(service.loadRun('run_opaque')).rejects.toThrow('not connected');
  });
});
