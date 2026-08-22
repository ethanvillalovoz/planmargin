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
  readonly mode: 'published-aggregate' | 'real-local-redacted';
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
  mode: 'published-aggregate',
};
