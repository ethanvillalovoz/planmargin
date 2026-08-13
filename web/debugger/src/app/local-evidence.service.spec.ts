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
      if (url.endsWith('/assistant/status')) {
        return Promise.resolve(response({
          provider_id: 'offline_deterministic',
          model: null,
          source_mode: 'real_local_redacted',
          gemini_configured: false,
          explanation_only: true,
        }));
      }
      if (url.endsWith('/assistant/questions')) {
        return Promise.resolve(response([{ query_id: 'method_comparison', label: 'method comparison', question: 'How did the methods compare?' }]));
      }
      if (url.endsWith('/assistant/method_comparison')) {
        return Promise.resolve(response({ question: { query_id: 'method_comparison' }, privacy: { private_data_sent_to_provider: false } }));
      }
      if (url.endsWith('/gaussian-field/field.ply')) {
        return Promise.resolve(new Response(new Uint8Array([112, 108, 121])));
      }
      if (url.endsWith('/gaussian-field')) {
        return Promise.resolve(response({ primitive_count: 75000, decision: 'no_go' }));
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

  it('loads bounded assistant answers and Gaussian bytes through authenticated routes', async () => {
    await service.connect('0123456789abcdef');

    const catalog = await service.assistantCatalog();
    const answer = await service.askAssistant('method_comparison');
    const gaussian = await service.gaussianField();

    expect(catalog.status.provider_id).toBe('offline_deterministic');
    expect(catalog.questions[0].query_id).toBe('method_comparison');
    expect(answer.question.query_id).toBe('method_comparison');
    expect(gaussian.summary.primitive_count).toBe(75_000);
    expect(Array.from(new Uint8Array(gaussian.bytes))).toEqual([112, 108, 121]);
    for (const [url, options] of fetchMock.mock.calls.slice(-5) as [string, RequestInit][]) {
      expect(url).toMatch(/assistant|gaussian-field/);
      expect((options.headers as Record<string, string>)['X-PlanMargin-Token']).toBe(
        '0123456789abcdef',
      );
    }
  });
});
