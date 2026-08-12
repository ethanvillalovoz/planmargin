import { CampaignEvidence } from './campaign-evidence';
import { DebuggerRun } from './debugger.types';

export type LocalConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error';

export interface LocalCell {
  readonly cellId: string;
  readonly method: 'random' | 'bayesian';
  readonly seed: number;
  readonly selectionOrder: number;
  readonly proposalCount: number;
  readonly pipelineValidCount: number;
  readonly supportAndPipelineValidCount: number;
  readonly qualifyingFailureCount: number;
  readonly validRatePercent: number;
  readonly finalFeasibleHypervolume: number;
}

export interface LocalProposal {
  readonly proposalNumber: number;
  readonly attemptStatus: string;
  readonly normalizedMutationDistance: number;
  readonly brakingOnsetOffsetSeconds: number;
  readonly speedMultiplier: number;
  readonly empiricalSupportProbability: number | null;
  readonly supportPasses: boolean | null;
  readonly objectiveAvailable: boolean;
  readonly policySpecificAvoidableFailure: boolean | null;
  readonly testedMutatedFailure: boolean | null;
  readonly referenceMutatedSuccess: boolean | null;
  readonly physicalRollouts: number;
}

export interface LocalRunSummary {
  readonly runId: string;
  readonly label: string;
  readonly recordCount: number;
  readonly policySpecificAvoidableFailure: boolean;
}

export interface LocalEvidenceSnapshot {
  readonly campaign: CampaignEvidence;
  readonly cells: readonly LocalCell[];
  readonly runs: readonly LocalRunSummary[];
  readonly initialRun: DebuggerRun;
}
