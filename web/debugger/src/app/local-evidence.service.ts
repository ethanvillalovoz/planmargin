import { Injectable, computed, signal } from '@angular/core';
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
} from './product-evidence.types';

const API_ROOT = 'http://127.0.0.1:8765/api/v1';
const SESSION_TOKEN_KEY = 'planmargin.local-evidence-token.v1';

@Injectable({ providedIn: 'root' })
export class LocalEvidenceService {
  private token: string | undefined;
  private requestGeneration = 0;
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
  readonly selectedCell = computed(() =>
    this.cells().find((cell) => cell.cellId === this.selectedCellId()),
  );
  readonly selectedProposal = computed(() =>
    this.proposals().find((proposal) => proposal.proposalNumber === this.selectedProposalNumber()),
  );

  restoreSessionToken(): string | undefined {
    try {
      const token = window.sessionStorage.getItem(SESSION_TOKEN_KEY)?.trim();
      if (token && token.length >= 16) return token;
      window.sessionStorage.removeItem(SESSION_TOKEN_KEY);
    } catch {
      // The workbench remains usable through the manual connection dialog when
      // browser session storage is unavailable.
    }
    return undefined;
  }

  async connect(candidateToken: string): Promise<LocalEvidenceSnapshot> {
    const token = candidateToken.trim();
    if (token.length < 16) throw new Error('Token must contain at least 16 characters');
    const generation = ++this.requestGeneration;
    this.state.set('connecting');
    this.error.set(undefined);
    this.token = undefined;
    try {
      const healthValue = await this.get('/health', token);
      const health = this.record(healthValue, 'health');
      if (health['status'] !== 'ready' || health['evidence_mode'] !== 'real_local_redacted') {
        throw new Error('Local API did not return the expected readiness contract');
      }
      const campaignValue = await this.get('/campaign', token);
      const methodsValue = await this.get('/methods', token);
      const hypothesesValue = await this.get('/hypotheses', token);
      const cellsValue = await this.get('/cells', token);
      const runsValue = await this.get('/runs', token);
      const campaign = parseCampaign(campaignValue, methodsValue, hypothesesValue, cellsValue);
      const runs = parseRunSummaries(runsValue);
      const [initialRunValue, investigationValue] = await Promise.all([
        this.get(`/runs/${encodeURIComponent(runs[0].runId)}`, token),
        this.get('/investigation', token),
      ]);
      const initialRun = parseLocalRun(initialRunValue);
      const investigation = parseCampaignInvestigation(investigationValue);
      if (generation !== this.requestGeneration) throw new Error('Connection was superseded');
      this.token = token;
      this.campaign.set(campaign.campaign);
      this.cells.set(campaign.cells);
      this.runs.set(runs);
      this.investigation.set(investigation);
      this.state.set('connected');
      await this.selectCell(campaign.cells[0].cellId);
      this.rememberSessionToken(token);
      return snapshot(campaign.campaign, campaign.cells, runs, initialRun);
    } catch (error: unknown) {
      if (generation === this.requestGeneration) {
        this.token = undefined;
        if (error instanceof Error && error.message === 'The local evidence token was rejected') {
          this.forgetSessionToken();
        }
        this.state.set('error');
        this.error.set(this.safeMessage(error));
      }
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

  async selectCell(cellId: string): Promise<void> {
    if (!this.cells().some((cell) => cell.cellId === cellId)) {
      throw new Error('Unknown local evidence cell');
    }
    this.selectedCellId.set(cellId);
    this.error.set(undefined);
    this.selectedProposalNumber.set(undefined);
    this.proposals.set([]);
    this.loadingProposals.set(true);
    try {
      const proposals = parseProposals(
        await this.authorizedGet(`/cells/${encodeURIComponent(cellId)}/proposals`),
      );
      if (this.selectedCellId() !== cellId) return;
      this.proposals.set(proposals);
      this.selectedProposalNumber.set(proposals[0].proposalNumber);
    } catch (error: unknown) {
      this.error.set(this.safeMessage(error));
      throw error;
    } finally {
      if (this.selectedCellId() === cellId) this.loadingProposals.set(false);
    }
  }

  selectProposal(proposalNumber: number): void {
    if (!this.proposals().some((proposal) => proposal.proposalNumber === proposalNumber)) {
      throw new Error('Unknown local proposal');
    }
    this.selectedProposalNumber.set(proposalNumber);
  }

  async selectInvestigationProposal(cellId: string, proposalNumber: number): Promise<void> {
    await this.selectCell(cellId);
    this.selectProposal(proposalNumber);
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

  async sensorAsset(name: SensorAssetName): Promise<SensorAssetBundle> {
    const [summary, bytes] = await Promise.all([
      this.sensorScene(),
      this.authorizedBytes(`/sensor-scene/${name}.ply`),
    ]);
    return { summary, bytes };
  }

  disconnect(): void {
    this.requestGeneration++;
    this.token = undefined;
    this.forgetSessionToken();
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
  }

  private authorizedGet(path: string): Promise<unknown> {
    if (this.token === undefined || this.state() !== 'connected') {
      return Promise.reject(new Error('Local evidence is not connected'));
    }
    return this.get(path, this.token);
  }

  private async authorizedBytes(path: string): Promise<ArrayBuffer> {
    const response = await this.authorizedFetch(path);
    return response.arrayBuffer();
  }

  private async get(path: string, token: string): Promise<unknown> {
    const response = await this.fetchWithToken(path, token);
    return response.json() as Promise<unknown>;
  }

  private authorizedFetch(path: string, signal?: AbortSignal): Promise<Response> {
    if (this.token === undefined || this.state() !== 'connected') {
      return Promise.reject(new Error('Local evidence is not connected'));
    }
    return this.fetchWithToken(path, this.token, signal);
  }

  private async fetchWithToken(
    path: string,
    token: string,
    signal?: AbortSignal,
  ): Promise<Response> {
    const response = await fetch(`${API_ROOT}${path}`, {
      method: 'GET',
      headers: { 'X-PlanMargin-Token': token },
      cache: 'no-store',
      credentials: 'omit',
      mode: 'cors',
      referrerPolicy: 'no-referrer',
      signal,
    });
    if (!response.ok) {
      if (response.status === 401) throw new Error('The local evidence token was rejected');
      throw new Error(`Local evidence request failed (${response.status})`);
    }
    return response;
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

  private rememberSessionToken(token: string): void {
    try {
      window.sessionStorage.setItem(SESSION_TOKEN_KEY, token);
    } catch {
      // The verified in-memory connection remains valid even when the browser
      // refuses per-tab session storage.
    }
  }

  private forgetSessionToken(): void {
    try {
      window.sessionStorage.removeItem(SESSION_TOKEN_KEY);
    } catch {
      // There is nothing else to clear when session storage is unavailable.
    }
  }
}
