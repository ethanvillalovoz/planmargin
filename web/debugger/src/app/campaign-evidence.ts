export const CAMPAIGN_EVIDENCE = {
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
  heldOutOpened: false,
} as const;
