import { DestroyRef, Injectable, computed, effect, inject, signal } from '@angular/core';
import { LocalEvidenceService } from './local-evidence.service';
import { parseLocalRun } from './local-evidence.parsers';
import { DebuggerRun } from './debugger.types';

export interface ExperimentConfig {
  test_plan?: 'lead_braking' | 'command_dropout' | 'assistance_handoff';
  selection_order: number;
  braking_onset_offset_s: number;
  speed_multiplier: number;
  tested_controller?: TestedControllerConfig;
}
export interface TestedControllerConfig {
  desired_vel_mps: number;
  min_spacing_m: number;
  safe_time_headway_s: number;
}
export function validControllerConfig(value: unknown): value is TestedControllerConfig {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const config = value as Record<string, unknown>;
  const bounds = {
    desired_vel_mps: [1, 40],
    min_spacing_m: [0.5, 10],
    safe_time_headway_s: [0.5, 5],
  };
  return (
    Object.keys(config).length === 3 &&
    Object.entries(bounds).every(
      ([key, [min, max]]) =>
        typeof config[key] === 'number' &&
        Number.isFinite(config[key]) &&
        (config[key] as number) >= min &&
        (config[key] as number) <= max,
    )
  );
}
export function sameExperimentConfig(a: ExperimentConfig, b: ExperimentConfig): boolean {
  return (
    a.selection_order === b.selection_order &&
    (a.test_plan ?? 'lead_braking') === (b.test_plan ?? 'lead_braking') &&
    a.braking_onset_offset_s === b.braking_onset_offset_s &&
    a.speed_multiplier === b.speed_multiplier &&
    (a.tested_controller === undefined
      ? b.tested_controller === undefined
      : b.tested_controller !== undefined &&
        Object.entries(a.tested_controller).every(
          ([key, value]) => b.tested_controller![key as keyof TestedControllerConfig] === value,
        ))
  );
}
export interface ExperimentResult {
  decision: 'qualified' | 'not_qualified' | 'invalid_mutation' | 'checks_passed' | 'checks_failed';
  behavior_events?: { step: number; time_seconds: number; label: string }[];
  qualification?: Record<string, { post_fault_progress_m?: number }>;
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
  completion_deadline_seconds?: number;
  rerun_of?: string | null;
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

export interface ExperimentHealth {
  status: 'empty' | 'healthy' | 'running' | 'attention';
  total_jobs: number;
  active_incidents: number;
  resolved_incidents: number;
  deadline_measured_jobs: number;
  on_time_completed_jobs: number;
  unmeasured_jobs: number;
  incidents: {
    job_id: string;
    kind: string;
    selection_order: number;
    test_plan: string;
    component: string;
    stage_label: string;
    elapsed_seconds: number;
    deadline_seconds: number | null;
    recovery: string;
    resolved_by: string | null;
  }[];
}

export function parseExperimentHealth(value: unknown): ExperimentHealth {
  const health = value as ExperimentHealth | null;
  if (
    !health ||
    !['empty', 'healthy', 'running', 'attention'].includes(health.status) ||
    ![
      'total_jobs',
      'active_incidents',
      'resolved_incidents',
      'deadline_measured_jobs',
      'on_time_completed_jobs',
      'unmeasured_jobs',
    ].every(
      (key) =>
        Number.isInteger(health[key as keyof ExperimentHealth]) &&
        Number(health[key as keyof ExperimentHealth]) >= 0,
    ) ||
    !Array.isArray(health.incidents) ||
    health.incidents.some(
      (item) =>
        !item ||
        !/^[0-9a-f]{32}$/.test(item.job_id) ||
        typeof item.recovery !== 'string' ||
        typeof item.kind !== 'string' ||
        typeof item.stage_label !== 'string' ||
        (item.resolved_by !== null && !/^[0-9a-f]{32}$/.test(item.resolved_by)),
    )
  ) {
    throw new Error('Invalid live test-health response');
  }
  return health;
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
    !['lead_braking', 'command_dropout', 'assistance_handoff'].includes(
      item.config.test_plan ?? 'lead_braking',
    ) ||
    (item.rerun_of != null && !/^[0-9a-f]{32}$/.test(item.rerun_of)) ||
    (item.completion_deadline_seconds !== undefined &&
      (!Number.isInteger(item.completion_deadline_seconds) ||
        item.completion_deadline_seconds < 10 ||
        item.completion_deadline_seconds > 900)) ||
    !Number.isInteger(item.config.selection_order) ||
    item.config.selection_order < 1 ||
    item.config.selection_order > 10 ||
    !Number.isFinite(item.config.braking_onset_offset_s) ||
    ![0, 0.1, 0.2, 0.3, 0.4, 0.5].includes(item.config.braking_onset_offset_s) ||
    !Number.isFinite(item.config.speed_multiplier) ||
    item.config.speed_multiplier < 0.75 ||
    item.config.speed_multiplier > 1 ||
    (item.config.tested_controller !== undefined &&
      !validControllerConfig(item.config.tested_controller)) ||
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
      ![
        'qualified',
        'not_qualified',
        'invalid_mutation',
        'checks_passed',
        'checks_failed',
      ].includes(item.result.decision) ||
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
  readonly health = signal<ExperimentHealth | undefined>(undefined);
  readonly selectedId = signal<string | undefined>(
    new URLSearchParams(window.location.search).get('job') ??
      new URLSearchParams(window.location.search).get('experiment') ??
      undefined,
  );
  readonly draft = signal<ExperimentConfig>({
    selection_order: 1,
    braking_onset_offset_s: 0,
    speed_multiplier: 0.9,
  });
  readonly selected = computed(() => this.jobs().find((job) => job.job_id === this.selectedId()));
  readonly active = computed(() => this.jobs().find((job) => job.status === 'running'));
  readonly error = signal<string | undefined>(undefined);
  readonly busy = signal(false);
  private generation = 0;
  private refreshSequence = 0;
  private refreshFailure?: string;
  private timer?: ReturnType<typeof setTimeout>;
  private pending?: ExperimentConfig & {
    request_id: string;
    completion_deadline_seconds: number;
    rerun_of?: string;
  };

  selectJob(jobId: string): void {
    if (!this.jobs().some((job) => job.job_id === jobId)) return;
    this.selectedId.set(jobId);
    const url = new URL(window.location.href);
    url.searchParams.set('job', jobId);
    window.history.replaceState(null, '', url.pathname + url.search);
  }

  constructor() {
    effect(() => {
      const connected = this.local.connected();
      this.generation++;
      clearTimeout(this.timer);
      if (connected) void this.refresh();
      else {
        this.jobs.set([]);
        this.readiness.set(undefined);
        this.health.set(undefined);
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
      const [readiness, history, health] = await Promise.all([
        this.request('/readiness'),
        this.request(''),
        this.request('/health'),
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
      this.health.set(parseExperimentHealth(health));
      if (this.error() === this.refreshFailure) this.error.set(undefined);
      this.refreshFailure = undefined;
      if (!this.selectedId() || !this.jobs().some((job) => job.job_id === this.selectedId())) {
        this.selectedId.set(this.jobs()[0]?.job_id);
      }
    } catch (error) {
      if (generation !== this.generation || sequence !== this.refreshSequence) return;
      this.health.set(undefined);
      this.refreshFailure =
        error instanceof Error && error.name !== 'TypeError'
          ? error.message
          : 'Cannot reach the experiment runner. Reconnect or retry; saved jobs are retained.';
      this.error.set(this.refreshFailure);
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

  async start(config: ExperimentConfig, deadline = 120, rerunOf?: string): Promise<void> {
    if (this.busy() || !this.local.connected()) return;
    const generation = this.generation;
    this.busy.set(true);
    this.error.set(undefined);
    if (
      !this.pending ||
      !sameExperimentConfig(this.pending, config) ||
      this.pending.completion_deadline_seconds !== deadline ||
      this.pending.rerun_of !== rerunOf
    ) {
      this.pending = {
        ...config,
        request_id: crypto.randomUUID(),
        completion_deadline_seconds: deadline,
        ...(rerunOf ? { rerun_of: rerunOf } : {}),
      };
    }
    try {
      const job = parseExperimentJob(await this.request('', this.pending));
      if (generation !== this.generation) return;
      this.pending = undefined;
      this.jobs.update((jobs) => [
        job,
        ...jobs.filter((existing) => existing.job_id !== job.job_id),
      ]);
      this.selectJob(job.job_id);
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
    anchor.hidden = true;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
