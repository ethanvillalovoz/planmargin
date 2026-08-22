export interface CampaignEvidence {
  readonly campaignId: string;
  readonly cells: number;
  readonly proposals: number;
  readonly physicalRollouts: number;
  readonly rolloutSteps: number;
  readonly methods: {
    readonly random: MethodEvidence;
    readonly bayesian: MethodEvidence;
  };
  readonly hypotheses: {
    readonly efficiency: string;
    readonly minimality: string;
    readonly validity: string;
  };
  readonly nativeKernelSpeedupRange: string;
  readonly heldOutComparisonRun: boolean;
  readonly trajectoryModel: TrajectoryModelEvidence;
  readonly scaleTrajectoryModel: TrajectoryModelEvidence;
  readonly inference: InferenceEvidence;
  readonly activeRisk: ActiveRiskEvidence;
  readonly interactionStudy: InteractionStudyEvidence;
  readonly mode: 'published-aggregate' | 'real-local-redacted';
}

export interface InferenceEvidence {
  readonly gpu: string;
  readonly tensorrtVersion: string;
  readonly fp32Batch1P50Ms: number;
  readonly fp16Batch1P50Ms: number;
  readonly fp16Batch256Throughput: number;
  readonly cppBatch1P50Ms: number;
  readonly fp16MaxDriftMeters: number;
  readonly fp16RmseMeters: number;
  readonly status: 'qualified';
}

export interface TrajectoryModelEvidence {
  readonly scenarios: number;
  readonly windows: number;
  readonly testWindows: number;
  readonly adeMeters: number;
  readonly fdeMeters: number;
  readonly baselineAdeMeters: number;
  readonly baselineFdeMeters: number;
  readonly status: 'deployment candidate';
}

export interface ActiveRiskEvidence {
  readonly examples: number;
  readonly scenarios: number;
  readonly meanSpearman: number;
  readonly budgetEightAdvantageMeters: number;
  readonly budgetEightWins: number;
  readonly status: 'no-go';
}

export interface InteractionStudyEvidence {
  readonly scenarios: number;
  readonly interactionAdeMeters: number;
  readonly egoOnlyAdeMeters: number;
  readonly interactionFdeMeters: number;
  readonly egoOnlyFdeMeters: number;
  readonly status: 'no-go';
}

export interface MethodEvidence {
  readonly proposals: number;
  readonly qualifyingFindings: number;
  readonly validRatePercent: number;
  readonly finalHypervolume: number;
}

export const CAMPAIGN_EVIDENCE: CampaignEvidence = {
  campaignId: 'natural-development-v1',
  cells: 100,
  proposals: 3_200,
  physicalRollouts: 14_110,
  rolloutSteps: 1_128_800,
  methods: {
    random: {
      proposals: 1_600,
      qualifyingFindings: 0,
      validRatePercent: 54.5625,
      finalHypervolume: 0.227223,
    },
    bayesian: {
      proposals: 1_600,
      qualifyingFindings: 0,
      validRatePercent: 69.375,
      finalHypervolume: 0.25825,
    },
  },
  hypotheses: {
    efficiency: 'Untestable',
    minimality: 'Untestable',
    validity: 'Supported',
  },
  nativeKernelSpeedupRange: '585–619×',
  heldOutComparisonRun: false,
  trajectoryModel: {
    scenarios: 128,
    windows: 29_288,
    testWindows: 3_157,
    adeMeters: 0.322497,
    fdeMeters: 0.888763,
    baselineAdeMeters: 0.620216,
    baselineFdeMeters: 1.666729,
    status: 'deployment candidate',
  },
  scaleTrajectoryModel: {
    scenarios: 1_024,
    windows: 126_992,
    testWindows: 12_832,
    adeMeters: 0.418364,
    fdeMeters: 1.166769,
    baselineAdeMeters: 0.870479,
    baselineFdeMeters: 2.341937,
    status: 'deployment candidate',
  },
  inference: {
    gpu: 'Tesla T4',
    tensorrtVersion: '11.2.1.2',
    fp32Batch1P50Ms: 0.246592,
    fp16Batch1P50Ms: 0.196688,
    fp16Batch256Throughput: 1_008_815.312,
    cppBatch1P50Ms: 0.124288,
    fp16MaxDriftMeters: 0.05508423,
    fp16RmseMeters: 0.00563178,
    status: 'qualified',
  },
  activeRisk: {
    examples: 2_097,
    scenarios: 9,
    meanSpearman: 0.137194,
    budgetEightAdvantageMeters: -0.475234,
    budgetEightWins: 3,
    status: 'no-go',
  },
  interactionStudy: {
    scenarios: 1_024,
    interactionAdeMeters: 0.452594,
    egoOnlyAdeMeters: 0.434009,
    interactionFdeMeters: 1.386596,
    egoOnlyFdeMeters: 1.332229,
    status: 'no-go',
  },
  mode: 'published-aggregate',
};
