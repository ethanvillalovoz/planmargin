import { CAMPAIGN_EVIDENCE } from './campaign-evidence';

describe('CAMPAIGN_EVIDENCE', () => {
  it('matches the published aggregate-only campaign result', () => {
    expect(CAMPAIGN_EVIDENCE.cells).toBe(100);
    expect(CAMPAIGN_EVIDENCE.proposals).toBe(3_200);
    expect(CAMPAIGN_EVIDENCE.physicalRollouts).toBe(14_110);
    expect(CAMPAIGN_EVIDENCE.rolloutSteps).toBe(1_128_800);
    expect(CAMPAIGN_EVIDENCE.methods.random.proposals).toBe(1_600);
    expect(CAMPAIGN_EVIDENCE.methods.bayesian.proposals).toBe(1_600);
    expect(CAMPAIGN_EVIDENCE.methods.random.validRatePercent).toBe(54.5625);
    expect(CAMPAIGN_EVIDENCE.methods.bayesian.validRatePercent).toBe(69.375);
  });

  it('does not overstate the zero-finding result or held-out status', () => {
    expect(CAMPAIGN_EVIDENCE.methods.random.qualifyingFindings).toBe(0);
    expect(CAMPAIGN_EVIDENCE.methods.bayesian.qualifyingFindings).toBe(0);
    expect(CAMPAIGN_EVIDENCE.hypotheses.efficiency).toBe('Untestable');
    expect(CAMPAIGN_EVIDENCE.hypotheses.minimality).toBe('Untestable');
    expect(CAMPAIGN_EVIDENCE.hypotheses.validity).toBe('Supported');
    expect(CAMPAIGN_EVIDENCE.heldOutComparisonRun).toBe(false);
    expect(CAMPAIGN_EVIDENCE.scaleTrajectoryModel.scenarios).toBe(1_024);
    expect(CAMPAIGN_EVIDENCE.scaleTrajectoryModel.testWindows).toBe(12_832);
    expect(CAMPAIGN_EVIDENCE.scaleTrajectoryModel.adeMeters).toBeLessThan(
      CAMPAIGN_EVIDENCE.scaleTrajectoryModel.baselineAdeMeters,
    );
    expect(CAMPAIGN_EVIDENCE.activeRisk.status).toBe('no-go');
    expect(CAMPAIGN_EVIDENCE.interactionStudy.status).toBe('no-go');
  });
});
