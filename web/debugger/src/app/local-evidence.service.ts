import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { CAMPAIGN_EVIDENCE } from './campaign-evidence';
import { DebuggerRun } from './debugger.types';
import {
  parseCampaignInvestigation,
  parseCampaign,
  parseLocalRun,
  parseProposalAnalysis,
  parseProposals,
  parseRunSummaries,
  snapshot,
} from './local-evidence.parsers';
import {
  CampaignInvestigation,
  LocalCell,
  LocalConnectionState,
  LocalEvidenceSnapshot,
  LocalProposal,
  LocalRunSummary,
  ProposalAnalysis,
} from './local-evidence.types';
import {
  AssistantAnswer,
  AssistantQueryId,
  AssistantQuestion,
  AssistantStatus,
  CameraAnnotationBundle,
  GaussianFieldBundle,
  GaussianFieldSummary,
  SensorAssetBundle,
  SensorAssetName,
  SensorSceneSummary,
  SensorTrajectoryOverlay,
} from './product-evidence.types';

const API_HOST = window.location.hostname === 'localhost' ? 'localhost' : '127.0.0.1';
const API_ROOT = `http://${API_HOST}:8765/api/v1`;

@Injectable({ providedIn: 'root' })
export class LocalEvidenceService {
  private requestGeneration = 0;
  private selectionGeneration = 0;
  readonly state = signal<LocalConnectionState>('disconnected');
  readonly error = signal<string | undefined>(undefined);
  readonly campaign = signal(CAMPAIGN_EVIDENCE);
  readonly cells = signal<readonly LocalCell[]>([]);
  readonly runs = signal<readonly LocalRunSummary[]>([]);
  readonly proposals = signal<readonly LocalProposal[]>([]);
  readonly investigation = signal<CampaignInvestigation | undefined>(undefined);
  readonly selectedCellId = signal<string | undefined>(undefined);
  readonly selectedProposalNumber = signal<number | undefined>(undefined);
  readonly loadingProposals = signal(false);
  readonly connected = computed(() => this.state() === 'connected');
  readonly campaignAvailable = signal(true);
  readonly selectedCell = computed(() =>
    this.cells().find((cell) => cell.cellId === this.selectedCellId()),
  );
  readonly selectedProposal = computed(() =>
    this.proposals().find((proposal) => proposal.proposalNumber === this.selectedProposalNumber()),
  );

  constructor() {
    const onFocus = () => {
      if (this.connected()) void this.verifyConnection();
    };
    window.addEventListener('focus', onFocus);
    inject(DestroyRef).onDestroy(() => window.removeEventListener('focus', onFocus));
  }

  async verifyConnection(): Promise<void> {
    if (!this.connected()) return;
    const generation = this.requestGeneration;
    try {
      const health = this.record(await this.authorizedGet('/health'), 'health');
      if (health['status'] !== 'ready')
        throw new Error('Local evidence is not ready. Reconnect the workspace.');
    } catch (error: unknown) {
      if (generation === this.requestGeneration && this.state() !== 'disconnected') {
        this.state.set('error');
        this.error.set(this.safeMessage(error));
      }
    }
  }

  async connect(candidateToken: string): Promise<LocalEvidenceSnapshot> {
    const token = candidateToken.trim();
    if (token.length < 16) throw new Error('Token must contain at least 16 characters');
    const generation = ++this.requestGeneration;
    this.state.set('connecting');
    this.error.set(undefined);
    try {
      await this.startBrowserSession(token);
      return await this.loadSnapshot(generation);
    } catch (error: unknown) {
      if (generation === this.requestGeneration) {
        this.state.set('error');
        this.error.set(this.safeMessage(error));
      }
      throw error;
    }
  }

  async restoreBrowserSession(): Promise<LocalEvidenceSnapshot | undefined> {
    const generation = ++this.requestGeneration;
    this.state.set('connecting');
    this.error.set(undefined);
    try {
      return await this.loadSnapshot(generation);
    } catch (error: unknown) {
      if (generation !== this.requestGeneration) throw error;
      if (error instanceof Error && error.message === 'The local evidence token was rejected') {
        this.state.set('disconnected');
        this.error.set(undefined);
        return undefined;
      }
      this.state.set('error');
      this.error.set(this.safeMessage(error));
      throw error;
    }
  }

  async loadRun(runId: string): Promise<DebuggerRun> {
    this.error.set(undefined);
    try {
      return parseLocalRun(await this.authorizedGet(`/runs/${encodeURIComponent(runId)}`));
    } catch (error: unknown) {
      this.error.set(this.safeMessage(error));
      throw error;
    }
  }
  async loadExperimentRun(jobId: string): Promise<DebuggerRun> {
    if (!/^[0-9a-f]{32}$/.test(jobId)) throw new Error('Invalid experiment identity');
    return parseLocalRun(await this.authorizedGet(`/experiments/${jobId}/replay`));
  }

  async selectCell(cellId: string, proposalNumber?: number): Promise<void> {
    if (!this.cells().some((cell) => cell.cellId === cellId)) {
      throw new Error('Unknown local evidence cell');
    }
    const generation = ++this.selectionGeneration;
    const connectionGeneration = this.requestGeneration;
    this.error.set(undefined);
    this.loadingProposals.set(true);
    try {
      const proposals = parseProposals(
        await this.authorizedGet(`/cells/${encodeURIComponent(cellId)}/proposals`),
      );
      if (
        generation !== this.selectionGeneration ||
        connectionGeneration !== this.requestGeneration
      )
        return;
      const selected = proposalNumber ?? proposals[0].proposalNumber;
      if (!proposals.some((proposal) => proposal.proposalNumber === selected))
        throw new Error('Unknown local proposal');
      this.selectedCellId.set(cellId);
      this.proposals.set(proposals);
      this.selectedProposalNumber.set(selected);
      this.rememberProposal();
    } catch (error: unknown) {
      if (
        generation === this.selectionGeneration &&
        connectionGeneration === this.requestGeneration
      )
        this.error.set(this.safeMessage(error));
      throw error;
    } finally {
      if (generation === this.selectionGeneration) this.loadingProposals.set(false);
    }
  }

  selectProposal(proposalNumber: number): void {
    if (!this.proposals().some((proposal) => proposal.proposalNumber === proposalNumber)) {
      throw new Error('Unknown local proposal');
    }
    this.selectionGeneration++;
    this.loadingProposals.set(false);
    this.selectedProposalNumber.set(proposalNumber);
    this.rememberProposal();
  }

  private rememberProposal(): void {
    const cell = this.selectedCellId();
    const proposal = this.selectedProposalNumber();
    if (!cell || proposal === undefined) return;
    const url = new URL(window.location.href);
    url.searchParams.set('cell', cell);
    url.searchParams.set('proposal', String(proposal));
    window.history.replaceState(null, '', url.pathname + url.search);
  }

  async selectInvestigationProposal(cellId: string, proposalNumber: number): Promise<void> {
    await this.selectCell(cellId, proposalNumber);
  }

  async proposalAnalysis(cellId: string, proposalNumber: number): Promise<ProposalAnalysis> {
    return parseProposalAnalysis(
      await this.authorizedGet(
        `/cells/${encodeURIComponent(cellId)}/proposals/${proposalNumber}/analysis`,
      ),
    );
  }

  async assistantCatalog(): Promise<{
    readonly status: AssistantStatus;
    readonly questions: readonly AssistantQuestion[];
  }> {
    const [status, questions] = await Promise.all([
      this.authorizedGet('/assistant/status') as Promise<AssistantStatus>,
      this.authorizedGet('/assistant/questions') as Promise<readonly AssistantQuestion[]>,
    ]);
    return { status, questions };
  }

  async assistantStatus(): Promise<AssistantStatus> {
    return this.authorizedGet('/assistant/status') as Promise<AssistantStatus>;
  }

  async askAssistant(queryId: AssistantQueryId): Promise<AssistantAnswer> {
    return this.authorizedGet(
      `/assistant/${encodeURIComponent(queryId)}`,
    ) as Promise<AssistantAnswer>;
  }

  async gaussianField(): Promise<GaussianFieldBundle> {
    const [summary, bytes] = await Promise.all([
      this.authorizedGet('/gaussian-field') as Promise<GaussianFieldSummary>,
      this.authorizedBytes('/gaussian-field/field.ply'),
    ]);
    return { summary, bytes };
  }

  async sensorScene(): Promise<SensorSceneSummary> {
    return this.authorizedGet('/sensor-scene') as Promise<SensorSceneSummary>;
  }

  async sensorFrame(frameIndex: number, signal?: AbortSignal): Promise<Blob> {
    const response = await this.authorizedFetch(`/sensor-scene/front/${frameIndex}.jpg`, signal);
    return response.blob();
  }

  async sensorAnnotations(): Promise<CameraAnnotationBundle> {
    return this.authorizedGet(
      '/sensor-scene/front/annotations.json',
    ) as Promise<CameraAnnotationBundle>;
  }

  async sensorTrajectory(): Promise<SensorTrajectoryOverlay> {
    return this.authorizedGet('/sensor-scene/trajectory.json') as Promise<SensorTrajectoryOverlay>;
  }

  async sensorAsset(name: SensorAssetName): Promise<SensorAssetBundle> {
    const [summary, bytes] = await Promise.all([
      this.sensorScene(),
      this.authorizedBytes(`/sensor-scene/${name}.ply`),
    ]);
    return { summary, bytes };
  }

  async disconnect(): Promise<void> {
    this.requestGeneration++;
    this.selectionGeneration++;
    const logout = this.endBrowserSession();
    this.state.set('disconnected');
    this.error.set(undefined);
    this.campaign.set(CAMPAIGN_EVIDENCE);
    this.cells.set([]);
    this.runs.set([]);
    this.proposals.set([]);
    this.investigation.set(undefined);
    this.selectedCellId.set(undefined);
    this.selectedProposalNumber.set(undefined);
    this.loadingProposals.set(false);
    await logout;
  }

  private authorizedGet(path: string): Promise<unknown> {
    if (this.state() !== 'connected') {
      return Promise.reject(new Error('Local evidence is not connected'));
    }
    return this.get(path);
  }

  private async authorizedBytes(path: string): Promise<ArrayBuffer> {
    const response = await this.authorizedFetch(path);
    return response.arrayBuffer();
  }

  private async get(path: string, token?: string): Promise<unknown> {
    const response = await this.fetchWithToken(path, token);
    return response.json() as Promise<unknown>;
  }

  private authorizedFetch(path: string, signal?: AbortSignal): Promise<Response> {
    if (this.state() !== 'connected') {
      return Promise.reject(new Error('Local evidence is not connected'));
    }
    return this.fetchWithToken(path, undefined, signal);
  }

  private async fetchWithToken(
    path: string,
    token?: string,
    signal?: AbortSignal,
  ): Promise<Response> {
    const headers = token === undefined ? undefined : { 'X-PlanMargin-Token': token };
    let response: Response;
    const generation = this.requestGeneration;
    try {
      response = await fetch(`${API_ROOT}${path}`, {
        method: 'GET',
        headers,
        cache: 'no-store',
        credentials: 'include',
        mode: 'cors',
        referrerPolicy: 'no-referrer',
        signal,
      });
    } catch (error: unknown) {
      if (!signal?.aborted && this.connected() && generation === this.requestGeneration) {
        this.state.set('error');
        this.error.set(this.safeMessage(error));
      }
      throw error;
    }
    if (!response.ok) {
      if (response.status === 401) {
        if (this.connected() && generation === this.requestGeneration) {
          this.state.set('error');
          this.error.set('Your local session expired. Reconnect the workspace.');
        }
        throw new Error('The local evidence token was rejected');
      }
      throw new Error(`Local evidence request failed (${response.status})`);
    }
    return response;
  }

  private async startBrowserSession(token: string): Promise<void> {
    const response = await fetch(`${API_ROOT}/session`, {
      method: 'POST',
      headers: { 'X-PlanMargin-Token': token },
      cache: 'no-store',
      credentials: 'include',
      mode: 'cors',
      referrerPolicy: 'no-referrer',
    });
    if (!response.ok) {
      if (response.status === 401) throw new Error('The local evidence token was rejected');
      throw new Error(`Local evidence request failed (${response.status})`);
    }
  }

  private async endBrowserSession(): Promise<void> {
    try {
      await fetch(`${API_ROOT}/session/logout`, {
        method: 'POST',
        cache: 'no-store',
        credentials: 'include',
        mode: 'cors',
        referrerPolicy: 'no-referrer',
      });
    } catch {
      // Local state is still cleared immediately if the loopback API has stopped.
    }
  }

  private async loadSnapshot(generation: number): Promise<LocalEvidenceSnapshot> {
    const healthValue = await this.get('/health');
    const health = this.record(healthValue, 'health');
    if (health['status'] !== 'ready' || health['evidence_mode'] !== 'real_local_redacted') {
      throw new Error('Local API did not return the expected readiness contract');
    }
    if (health['campaign_ready'] === false) {
      if (generation !== this.requestGeneration) throw new Error('Connection was superseded');
      this.campaignAvailable.set(false);
      this.campaign.set(CAMPAIGN_EVIDENCE);
      this.cells.set([]);
      this.runs.set([]);
      this.proposals.set([]);
      this.investigation.set(undefined);
      this.selectedCellId.set(undefined);
      this.selectedProposalNumber.set(undefined);
      this.state.set('connected');
      return { campaign: CAMPAIGN_EVIDENCE, cells: [], runs: [] };
    }
    const campaignValue = await this.get('/campaign');
    const methodsValue = await this.get('/methods');
    const hypothesesValue = await this.get('/hypotheses');
    const cellsValue = await this.get('/cells');
    const runsValue = await this.get('/runs');
    const campaign = parseCampaign(campaignValue, methodsValue, hypothesesValue, cellsValue);
    const runs = parseRunSummaries(runsValue);
    const [initialRunValue, investigationValue] = await Promise.all([
      this.get(`/runs/${encodeURIComponent(runs[0].runId)}`),
      this.get('/investigation'),
    ]);
    const initialRun = parseLocalRun(initialRunValue);
    const investigation = parseCampaignInvestigation(investigationValue);
    const first = investigation.closestMargin[0];
    const requested = new URLSearchParams(window.location.search);
    const requestedCell = requested.get('cell');
    const firstCellId = requestedCell ?? first?.cellId ?? campaign.cells[0].cellId;
    if (!campaign.cells.some((cell) => cell.cellId === firstCellId))
      throw new Error('Investigation references an unknown cell');
    const proposals = parseProposals(
      await this.get(`/cells/${encodeURIComponent(firstCellId)}/proposals`),
    );
    const firstProposalNumber =
      requestedCell && requested.has('proposal')
        ? Number(requested.get('proposal'))
        : requestedCell
          ? proposals[0].proposalNumber
          : (first?.proposalNumber ?? proposals[0].proposalNumber);
    if (!proposals.some((proposal) => proposal.proposalNumber === firstProposalNumber))
      throw new Error('Investigation references an unknown proposal');
    if (generation !== this.requestGeneration) throw new Error('Connection was superseded');
    this.campaign.set(campaign.campaign);
    this.campaignAvailable.set(true);
    this.cells.set(campaign.cells);
    this.runs.set(runs);
    this.investigation.set(investigation);
    this.proposals.set(proposals);
    this.selectedCellId.set(firstCellId);
    this.selectedProposalNumber.set(firstProposalNumber);
    this.state.set('connected');
    return snapshot(campaign.campaign, campaign.cells, runs, initialRun);
  }

  private record(value: unknown, path: string): Record<string, unknown> {
    if (typeof value !== 'object' || value === null || Array.isArray(value)) {
      throw new Error(`${path} must be an object`);
    }
    return value as Record<string, unknown>;
  }

  private safeMessage(error: unknown): string {
    if (!(error instanceof Error)) return 'Unknown local evidence error';
    if (error.name === 'TypeError') {
      return 'Local API unavailable. Start it on 127.0.0.1:8765 and retry.';
    }
    return error.message.replaceAll(API_ROOT, 'local API');
  }
}
