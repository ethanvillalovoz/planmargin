import { TestBed } from '@angular/core/testing';
import { CAMPAIGN_EVIDENCE } from './campaign-evidence';
import { InvestigationReportService } from './investigation-report.service';

describe('InvestigationReportService', () => {
  it('builds a hashed report with the campaign claim boundary', async () => {
    const service = TestBed.inject(InvestigationReportService);
    const report = await service.html({
      campaign: CAMPAIGN_EVIDENCE,
      cell: {
        cellId: 'cell_opaque',
        method: 'bayesian',
        seed: 0,
        selectionOrder: 1,
        proposalCount: 32,
        pipelineValidCount: 30,
        supportAndPipelineValidCount: 24,
        qualifyingFailureCount: 0,
        validRatePercent: 75,
        finalFeasibleHypervolume: 0.3,
      },
      proposal: {
        proposalNumber: 1,
        attemptStatus: 'accepted',
        normalizedMutationDistance: 0.8,
        brakingOnsetOffsetSeconds: 0.2,
        speedMultiplier: 0.8,
        empiricalSupportProbability: 0.6,
        supportPasses: true,
        objectiveAvailable: true,
        criticality: 0.4,
        minimality: 0.7,
        pipelinePasses: true,
        referencePasses: true,
        policySpecificAvoidableFailure: false,
        testedMutatedFailure: false,
        referenceMutatedSuccess: true,
        physicalRollouts: 6,
        trajectoryAvailable: false,
        replayRunId: null,
      },
    });
    expect(report).toContain('Tested planner still succeeds');
    expect(report).toContain('1.50 m minimum clearance');
    expect(report).toContain('Moderate edit · 30% of bounded range');
    expect(report).toContain('Seen in recorded behavior');
    expect(report).toContain('derived from the measured minimum signed separation');
    expect(report).toContain('3,200 proposals');
    expect(report).toMatch(/[a-f0-9]{64}/);
  });
});
