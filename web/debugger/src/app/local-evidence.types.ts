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
  readonly criticality: number;
  readonly minimality: number;
  readonly pipelinePasses: boolean;
  readonly referencePasses: boolean;
  readonly policySpecificAvoidableFailure: boolean | null;
  readonly testedMutatedFailure: boolean | null;
  readonly referenceMutatedSuccess: boolean | null;
  readonly physicalRollouts: number;
}

export interface InvestigationProposal extends LocalProposal {
  readonly cellId: string;
  readonly method: 'random' | 'bayesian';
  readonly seed: number;
  readonly selectionOrder: number;
  readonly decisiveGate: string;
}

export interface InvestigationFunnel {
  readonly proposed: number;
  readonly mutationValid: number;
  readonly scenarioValid: number;
  readonly pipelineValid: number;
  readonly supportValid: number;
  readonly referencePasses: number;
  readonly testedFails: number;
  readonly qualifyingFindings: number;
}

export interface CampaignInvestigation {
  readonly cellCount: number;
  readonly proposalCount: number;
  readonly funnel: InvestigationFunnel;
  readonly closestMargin: readonly InvestigationProposal[];
  readonly smallestMutation: readonly InvestigationProposal[];
  readonly highestSupport: readonly InvestigationProposal[];
}

export interface ProposalAnalysis {
  readonly analysisMode: 'deterministic_proposal_specific';
  readonly cellId: string;
  readonly proposalNumber: number;
  readonly decision: string;
  readonly decisiveGate: string;
  readonly explanation: string;
  readonly facts: readonly { readonly label: string; readonly value: string }[];
  readonly recordSha256: string;
  readonly trajectoryAvailable: false;
}

export type ProposalGate =
  'mutation' | 'scenario' | 'support' | 'reference' | 'tested-controller' | 'finding';

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
