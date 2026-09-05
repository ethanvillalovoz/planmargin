import { DestroyRef, Injectable, computed, effect, inject, signal } from '@angular/core';
import { LocalEvidenceService } from './local-evidence.service';
import { parseLocalRun } from './local-evidence.parsers';
import { DebuggerRun } from './debugger.types';

export interface ExperimentConfig {
  selection_order: number;
  braking_onset_offset_s: number;
  speed_multiplier: number;
}
export interface ExperimentResult {
  decision: 'qualified' | 'not_qualified' | 'invalid_mutation';
  explanation: string;
  gates: Record<string, boolean>;
  support_probability: number | null;
  collection_sha256: string | null;
  result_sha256: string;
  boundary: string;
  rejection_reasons: string[];
  controllers: Record<
    string,
    {
      outcome: { success: boolean; failure_reasons: string[] };
      interaction_metrics: { minimum_signed_separation_m: number };
    }
  > | null;
  original_controllers?: ExperimentResult['controllers'];
}
export interface ExperimentJob {
  job_id: string;
  config: ExperimentConfig;
  status:
    'running' | 'succeeded' | 'rejected' | 'failed' | 'cancelled' | 'interrupted' | 'timed_out';
  stage: string;
  stage_label: string;
  created_at: number;
  elapsed_seconds: number;
  events: { stage: string; label: string; duration_seconds: number | null; status: string }[];
  error: { code: string; component: string; recovery: string } | null;
  result: ExperimentResult | null;
}
export interface ExperimentReadiness {
  ready: boolean;
  missing: string[];
  empirical_support_ready: boolean;
  setup_command: string;
  boundary: string;
}

export function parseExperimentJob(value: unknown): ExperimentJob {
  if (typeof value !== 'object' || value === null) throw new Error('Invalid experiment response');
  const item = value as ExperimentJob;
  if (
    !/^[0-9a-f]{32}$/.test(item.job_id) ||
    ![
      'running',
      'succeeded',
      'rejected',
      'failed',
      'cancelled',
      'interrupted',
      'timed_out',
    ].includes(item.status) ||
    !item.config ||
    !Number.isInteger(item.config.selection_order) ||
    item.config.selection_order < 1 ||
    item.config.selection_order > 10 ||
    !Number.isFinite(item.config.braking_onset_offset_s) ||
    ![0, 0.1, 0.2, 0.3, 0.4, 0.5].includes(item.config.braking_onset_offset_s) ||
    !Number.isFinite(item.config.speed_multiplier) ||
    item.config.speed_multiplier < 0.75 ||
    item.config.speed_multiplier > 1 ||
    !Number.isFinite(item.elapsed_seconds) ||
    !Number.isFinite(item.created_at) ||
    typeof item.stage_label !== 'string' ||
    !Array.isArray(item.events) ||
    item.events.some(
      (event) =>
        !event ||
        typeof event.label !== 'string' ||
        typeof event.status !== 'string' ||
        (event.duration_seconds !== null && !Number.isFinite(event.duration_seconds)),
    ) ||
    (item.error !== null &&
      (!item.error ||
        typeof item.error.code !== 'string' ||
        typeof item.error.recovery !== 'string'))
  ) {
    throw new Error('Invalid experiment response');
  }
  if (
    item.result !== null &&
    (!item.result ||
      typeof item.result.explanation !== 'string' ||
      !['qualified', 'not_qualified', 'invalid_mutation'].includes(item.result.decision) ||
      !item.result.gates ||
      Object.values(item.result.gates).some((value) => typeof value !== 'boolean') ||
      !/^[0-9a-f]{64}$/.test(item.result.result_sha256))
  ) {
    throw new Error('Invalid experiment result');
  }
  for (const group of [item.result?.controllers, item.result?.original_controllers]) {
    if (!group) continue;
    for (const role of ['tested', 'reference']) {
      const controller = group[role];
      if (
        !controller ||
        typeof controller.outcome?.success !== 'boolean' ||
        !Number.isFinite(controller.interaction_metrics?.minimum_signed_separation_m)
      ) {
        throw new Error('Invalid experiment controller metrics');
      }
    }
  }
  return item;
}

@Injectable({ providedIn: 'root' })
export class ExperimentService {
  private readonly local = inject(LocalEvidenceService);
  private readonly root = `http://${window.location.hostname === 'localhost' ? 'localhost' : '127.0.0.1'}:8765/api/v1/experiments`;
  readonly jobs = signal<readonly ExperimentJob[]>([]);
  readonly readiness = signal<ExperimentReadiness | undefined>(undefined);
  readonly selectedId = signal<string | undefined>(undefined);
  readonly selected = computed(() => this.jobs().find((job) => job.job_id === this.selectedId()));
  readonly active = computed(() => this.jobs().find((job) => job.status === 'running'));
  readonly error = signal<string | undefined>(undefined);
  readonly busy = signal(false);
  private generation = 0;
  private refreshSequence = 0;
  private timer?: ReturnType<typeof setTimeout>;
  private pending?: ExperimentConfig & { request_id: string };

  constructor() {
    effect(() => {
      const connected = this.local.connected();
      this.generation++;
      clearTimeout(this.timer);
      if (connected) void this.refresh();
      else {
        this.jobs.set([]);
        this.readiness.set(undefined);
        this.error.set(undefined);
      }
    });
    inject(DestroyRef).onDestroy(() => {
      this.generation++;
      clearTimeout(this.timer);
    });
  }

  private async request(path: string, body?: object): Promise<unknown> {
    const response = await fetch(`${this.root}${path}`, {
      method: body ? 'POST' : 'GET',
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      credentials: 'include',
      cache: 'no-store',
      referrerPolicy: 'no-referrer',
      signal: AbortSignal.timeout(15_000),
    });
    if (response.status === 401) {
      await this.local.verifyConnection();
      throw new Error('Your local session expired. Reconnect the workspace.');
    }
    const value: unknown = await response.json();
    if (!response.ok) {
      const detail =
        value && typeof value === 'object' && 'detail' in value ? value.detail : undefined;
      throw new Error(
        typeof detail === 'string' ? detail : `Experiment request failed (${response.status})`,
      );
    }
    return value;
  }

  async refresh(): Promise<void> {
    if (!this.local.connected()) return;
    const generation = this.generation;
    const sequence = ++this.refreshSequence;
    clearTimeout(this.timer);
    try {
      const [readiness, history] = await Promise.all([
        this.request('/readiness'),
        this.request(''),
      ]);
      if (generation !== this.generation || sequence !== this.refreshSequence) return;
      if (
        !readiness ||
        typeof readiness !== 'object' ||
        !('ready' in readiness) ||
        typeof readiness.ready !== 'boolean' ||
        !Array.isArray(history)
      ) {
        throw new Error('Invalid experiment workspace response');
      }
      this.readiness.set(readiness as ExperimentReadiness);
      this.jobs.set(history.map(parseExperimentJob));
      if (!this.selectedId() || !this.jobs().some((job) => job.job_id === this.selectedId())) {
        this.selectedId.set(this.jobs()[0]?.job_id);
      }
    } catch (error) {
      if (generation !== this.generation || sequence !== this.refreshSequence) return;
      this.error.set(
        error instanceof Error && error.name !== 'TypeError'
          ? error.message
          : 'Cannot reach the experiment runner. Reconnect or retry; saved jobs are retained.',
      );
    } finally {
      if (
        generation === this.generation &&
        sequence === this.refreshSequence &&
        this.local.connected()
      ) {
        this.timer = setTimeout(() => void this.refresh(), this.active() ? 1000 : 5000);
      }
    }
  }

  async start(config: ExperimentConfig): Promise<void> {
    if (this.busy() || !this.local.connected()) return;
    const generation = this.generation;
    this.busy.set(true);
    this.error.set(undefined);
    if (
      !this.pending ||
      Object.entries(config).some(
        ([key, value]) => this.pending?.[key as keyof ExperimentConfig] !== value,
      )
    ) {
      this.pending = { ...config, request_id: crypto.randomUUID() };
    }
    try {
      const job = parseExperimentJob(await this.request('', this.pending));
      if (generation !== this.generation) return;
      this.pending = undefined;
      this.selectedId.set(job.job_id);
      await this.refresh();
    } catch (error) {
      if (generation !== this.generation) return;
      this.error.set(error instanceof Error ? error.message : 'Unable to start the experiment');
    } finally {
      this.busy.set(false);
    }
  }

  async cancel(jobId: string): Promise<void> {
    if (this.busy() || !this.local.connected()) return;
    const generation = this.generation;
    this.busy.set(true);
    this.error.set(undefined);
    try {
      await this.request(`/${jobId}/cancel`, {});
      if (generation !== this.generation) return;
      await this.refresh();
    } catch (error) {
      if (generation !== this.generation) return;
      this.error.set(error instanceof Error ? error.message : 'Unable to cancel the experiment');
    } finally {
      this.busy.set(false);
    }
  }

  async replay(jobId: string): Promise<DebuggerRun> {
    return parseLocalRun(await this.request(`/${jobId}/replay`));
  }

  async export(jobId: string): Promise<void> {
    const result = await this.request(`/${jobId}/result`);
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }),
    );
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `planmargin-experiment-${jobId.slice(0, 8)}.json`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
