import { TestBed } from '@angular/core/testing';
import { CAMPAIGN_EVIDENCE } from './campaign-evidence';
import { InvestigationReportService } from './investigation-report.service';
import type { InvestigationReportInput } from './investigation-report.service';

const REPORT_INPUT = {
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
} satisfies InvestigationReportInput;

describe('InvestigationReportService', () => {
  afterEach(() => vi.restoreAllMocks());

  it('builds a hashed report with the campaign claim boundary', async () => {
    const service = TestBed.inject(InvestigationReportService);
    const report = await service.html(REPORT_INPUT);
    expect(report).toContain('Tested planner still succeeds');
    expect(report).toContain('1.50 m minimum clearance');
    expect(report).toContain('Moderate edit · 30% of bounded range');
    expect(report).toContain('Seen in recorded behavior');
    expect(report).toContain('derived from the measured minimum signed separation');
    expect(report).toContain('3,200 proposals');
    expect(report).toMatch(/[a-f0-9]{64}/);
  });

  it('keeps the report URL valid until the browser accepts the download', async () => {
    const service = TestBed.inject(InvestigationReportService);
    const createObjectUrl = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:report');
    const revokeObjectUrl = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      expect(document.body.contains(this)).toBe(true);
      expect(revokeObjectUrl).not.toHaveBeenCalled();
    });

    await service.download(REPORT_INPUT);

    expect(createObjectUrl).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:report');
    expect(document.querySelector('a[download]')).toBeNull();
  });
});
