import { TestBed } from '@angular/core/testing';
import {
  API_CAMPAIGN,
  API_CELLS,
  API_HYPOTHESES,
  API_INVESTIGATION,
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
    fetchMock = vi.fn((input: string | URL | Request, options?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/session/logout') && options?.method === 'POST') {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.endsWith('/session') && options?.method === 'POST') {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.endsWith('/health')) {
        return Promise.resolve(response({ status: 'ready', evidence_mode: 'real_local_redacted' }));
      }
      if (url.endsWith('/campaign')) return Promise.resolve(response(API_CAMPAIGN));
      if (url.endsWith('/methods')) return Promise.resolve(response(API_METHODS));
      if (url.endsWith('/hypotheses')) return Promise.resolve(response(API_HYPOTHESES));
      if (url.endsWith('/cells')) return Promise.resolve(response(API_CELLS));
      if (url.endsWith('/runs')) return Promise.resolve(response(API_RUNS));
      if (url.endsWith('/runs/run_opaque')) return Promise.resolve(response(API_RUN));
      if (url.endsWith('/investigation')) return Promise.resolve(response(API_INVESTIGATION));
      if (url.endsWith('/cells/cell_opaque/proposals')) {
        return Promise.resolve(response(API_PROPOSALS));
      }
      if (url.endsWith('/cells/cell_opaque/proposals/1/analysis')) {
        return Promise.resolve(
          response({
            evidence_mode: 'real_local_redacted',
            analysis_mode: 'deterministic_proposal_specific',
            cell_id: 'cell_opaque',
            proposal_number: 1,
            decision: 'not_qualified',
            decisive_gate: 'tested_controller_failure',
            explanation: 'The tested controller remained successful.',
            facts: [{ label: 'method', value: 'bayesian' }],
            record_sha256: 'a'.repeat(64),
            trajectory_available: false,
            replay_run_id: null,
          }),
        );
      }
      if (url.endsWith('/assistant/status')) {
        return Promise.resolve(
          response({
            provider_id: 'offline_deterministic',
            model: null,
            source_mode: 'real_local_redacted',
            gemini_configured: false,
            explanation_only: true,
          }),
        );
      }
      if (url.endsWith('/assistant/questions')) {
        return Promise.resolve(
          response([
            {
              query_id: 'method_comparison',
              label: 'method comparison',
              question: 'How did the methods compare?',
            },
          ]),
        );
      }
      if (url.endsWith('/assistant/method_comparison')) {
        return Promise.resolve(
          response({
            question: { query_id: 'method_comparison' },
            privacy: { private_data_sent_to_provider: false },
          }),
        );
      }
      if (url.endsWith('/gaussian-field/field.ply')) {
        return Promise.resolve(new Response(new Uint8Array([112, 108, 121])));
      }
      if (url.endsWith('/gaussian-field')) {
        return Promise.resolve(response({ primitive_count: 75000, decision: 'no_go' }));
      }
      if (url.endsWith('/sensor-scene/front/99.jpg')) {
        return Promise.resolve(new Response(new Uint8Array([255, 216, 255, 217])));
      }
      if (url.endsWith('/sensor-scene/front/annotations.json')) {
        return Promise.resolve(
          response({
            record_type: 'planmargin.sensor_frame_annotations',
            schema_version: '1.0.0',
            source: 'Waymo Open Dataset v2 Perception camera_box',
            image_width: 1920,
            image_height: 1280,
            frames: [
              {
                index: 99,
                timestamp_micros: 1,
                boxes: [
                  {
                    track_id: 'track-1',
                    category: 'vehicle',
                    center_x: 960,
                    center_y: 640,
                    width: 100,
                    height: 50,
                  },
                ],
              },
            ],
          }),
        );
      }
      if (url.endsWith('/sensor-scene/reconstruction.ply')) {
        return Promise.resolve(new Response(new Uint8Array([112, 108, 121, 51])));
      }
      if (url.endsWith('/sensor-scene/reconstruction_context.ply')) {
        return Promise.resolve(new Response(new Uint8Array([112, 108, 121, 67])));
      }
      if (url.endsWith('/sensor-scene/lidar.ply')) {
        return Promise.resolve(new Response(new Uint8Array([112, 108, 121, 76])));
      }
      if (url.endsWith('/sensor-scene')) {
        return Promise.resolve(
          response({
            frame_count: 199,
            frame_rate_hz: 10,
            annotations: {
              representation: 'native_tracked_camera_boxes',
              frame_count: 199,
              box_count: 8364,
              bytes: 1_247_497,
            },
            reconstruction: { primitive_count: 1_179_648, source_frame_index: 99 },
            reconstruction_context: { primitive_count: 1_179_648, source_frame_index: 60 },
            lidar: { primitive_count: 50_241, source_frame_index: 99 },
          }),
        );
      }
      return Promise.resolve(response({ detail: 'not found' }, 404));
    });
    vi.stubGlobal('fetch', fetchMock);
    TestBed.configureTestingModule({});
    service = TestBed.inject(LocalEvidenceService);
  });

  afterEach(async () => {
    await service.disconnect();
    vi.unstubAllGlobals();
    TestBed.resetTestingModule();
  });

  it('connects through fixed no-store loopback requests and loads sealed proposals', async () => {
    const evidence = await service.connect('0123456789abcdef');

    expect(service.state()).toBe('connected');
    expect(evidence.initialRun.synthetic).toBe(false);
    expect(service.proposals()[0].proposalNumber).toBe(1);
    expect((await service.proposalAnalysis('cell_opaque', 1)).decisiveGate).toBe(
      'tested_controller_failure',
    );
    expect(fetchMock).toHaveBeenCalledTimes(11);
    const [sessionUrl, sessionOptions] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(sessionUrl).toMatch(/^http:\/\/(127\.0\.0\.1|localhost):8765\/api\/v1\/session$/);
    expect(sessionOptions.method).toBe('POST');
    expect((sessionOptions.headers as Record<string, string>)['X-PlanMargin-Token']).toBe(
      '0123456789abcdef',
    );
    for (const [url, options] of fetchMock.mock.calls.slice(1) as [string, RequestInit][]) {
      expect(url).toMatch(/^http:\/\/(127\.0\.0\.1|localhost):8765\/api\/v1\//);
      expect(options.cache).toBe('no-store');
      expect(options.credentials).toBe('include');
      expect(options.referrerPolicy).toBe('no-referrer');
      expect(options.headers).toBeUndefined();
    }

    await service.disconnect();
    expect(service.state()).toBe('disconnected');
    expect(service.cells()).toEqual([]);
    expect(service.campaign().mode).toBe('published-aggregate');
  });

  it('does not issue a request for a short token', async () => {
    await expect(service.connect('short')).rejects.toThrow('at least 16');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('redacts transient connection failures', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('network failed with sensitive details'));

    await expect(service.connect('0123456789abcdef')).rejects.toThrow();
    expect(service.state()).toBe('error');
    expect(service.error()).toContain('127.0.0.1:8765');
    await expect(service.loadRun('run_opaque')).rejects.toThrow('not connected');
  });

  it('rejects an invalid session bootstrap token', async () => {
    fetchMock.mockResolvedValueOnce(response({ detail: 'unauthorized' }, 401));

    await expect(service.connect('fedcba9876543210')).rejects.toThrow('token was rejected');
    expect(service.state()).toBe('error');
  });

  it('restores a browser session without exposing a token to JavaScript', async () => {
    const evidence = await service.restoreBrowserSession();

    expect(evidence?.initialRun.runId).toBe('run_opaque');
    expect(service.state()).toBe('connected');
    expect(fetchMock).toHaveBeenCalledTimes(9);
    for (const [, options] of fetchMock.mock.calls as [string, RequestInit][]) {
      expect(options.credentials).toBe('include');
      expect(options.headers).toBeUndefined();
    }
  });

  it('quietly remains disconnected when no browser session exists', async () => {
    fetchMock.mockResolvedValueOnce(response({ detail: 'unauthorized' }, 401));

    await expect(service.restoreBrowserSession()).resolves.toBeUndefined();
    expect(service.state()).toBe('disconnected');
    expect(service.error()).toBeUndefined();
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
      expect(options.credentials).toBe('include');
      expect(options.headers).toBeUndefined();
    }
  });

  it('loads the real sensor timeline and both authenticated 3D assets', async () => {
    await service.connect('0123456789abcdef');

    const scene = await service.sensorScene();
    const frame = await service.sensorFrame(99);
    const annotations = await service.sensorAnnotations();
    const reconstruction = await service.sensorAsset('reconstruction');
    const context = await service.sensorAsset('reconstruction_context');
    const lidar = await service.sensorAsset('lidar');

    expect(scene.frame_count).toBe(199);
    expect(Array.from(new Uint8Array(await frame.arrayBuffer()))).toEqual([255, 216, 255, 217]);
    expect(annotations.frames[0].boxes[0].track_id).toBe('track-1');
    expect(reconstruction.summary.reconstruction.primitive_count).toBe(1_179_648);
    expect(Array.from(new Uint8Array(reconstruction.bytes))).toEqual([112, 108, 121, 51]);
    expect(Array.from(new Uint8Array(context.bytes))).toEqual([112, 108, 121, 67]);
    expect(lidar.summary.lidar.primitive_count).toBe(50_241);
    expect(Array.from(new Uint8Array(lidar.bytes))).toEqual([112, 108, 121, 76]);
  });

  it('passes an abort signal to camera-frame requests', async () => {
    await service.connect('0123456789abcdef');
    const controller = new AbortController();

    await service.sensorFrame(99, controller.signal);

    const [, options] = fetchMock.mock.calls.at(-1) as [string, RequestInit];
    expect(options.signal).toBe(controller.signal);
  });
});
