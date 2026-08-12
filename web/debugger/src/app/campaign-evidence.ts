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
  readonly mode: 'published-aggregate' | 'real-local-redacted';
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
  mode: 'published-aggregate',
};
