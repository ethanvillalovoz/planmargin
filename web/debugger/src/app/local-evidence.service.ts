import { Injectable, computed, signal } from '@angular/core';
import { CAMPAIGN_EVIDENCE } from './campaign-evidence';
import { DebuggerRun } from './debugger.types';
import {
  parseCampaign,
  parseLocalRun,
  parseProposals,
  parseRunSummaries,
  snapshot,
} from './local-evidence.parsers';
import {
  LocalCell,
  LocalConnectionState,
  LocalEvidenceSnapshot,
  LocalProposal,
  LocalRunSummary,
} from './local-evidence.types';

const API_ROOT = 'http://127.0.0.1:8765/api/v1';

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
      const initialRun = parseLocalRun(
        await this.get(`/runs/${encodeURIComponent(runs[0].runId)}`, token),
      );
      if (generation !== this.requestGeneration) throw new Error('Connection was superseded');
      this.token = token;
      this.campaign.set(campaign.campaign);
      this.cells.set(campaign.cells);
      this.runs.set(runs);
      this.state.set('connected');
      await this.selectCell(campaign.cells[0].cellId);
      return snapshot(campaign.campaign, campaign.cells, runs, initialRun);
    } catch (error: unknown) {
      if (generation === this.requestGeneration) {
        this.token = undefined;
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

  disconnect(): void {
    this.requestGeneration++;
    this.token = undefined;
    this.state.set('disconnected');
    this.error.set(undefined);
    this.campaign.set(CAMPAIGN_EVIDENCE);
    this.cells.set([]);
    this.runs.set([]);
    this.proposals.set([]);
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

  private async get(path: string, token: string): Promise<unknown> {
    const response = await fetch(`${API_ROOT}${path}`, {
      method: 'GET',
      headers: { 'X-PlanMargin-Token': token },
      cache: 'no-store',
      credentials: 'omit',
      mode: 'cors',
      referrerPolicy: 'no-referrer',
    });
    if (!response.ok) {
      if (response.status === 401) throw new Error('The local evidence token was rejected');
      throw new Error(`Local evidence request failed (${response.status})`);
    }
    return response.json() as Promise<unknown>;
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
