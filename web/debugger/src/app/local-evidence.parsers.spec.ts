import {
  parseCampaign,
  parseLocalRun,
  parseProposals,
  parseRunSummaries,
} from './local-evidence.parsers';
import {
  API_CAMPAIGN,
  API_CELLS,
  API_HYPOTHESES,
  API_METHODS,
  API_PROPOSALS,
  API_RUN,
  API_RUNS,
} from './local-evidence.test-fixtures';

describe('local evidence response parsers', () => {
  it('maps real aggregate evidence without widening the claim boundary', () => {
    const result = parseCampaign(API_CAMPAIGN, API_METHODS, API_HYPOTHESES, API_CELLS);

    expect(result.campaign.mode).toBe('real-local-redacted');
    expect(result.campaign.heldOutComparisonRun).toBe(false);
    expect(result.campaign.methods.bayesian.validRatePercent).toBe(75);
    expect(result.campaign.hypotheses.efficiency).toBe('Untestable');
    expect(result.cells[0].cellId).toBe('cell_opaque');
  });

  it('maps a real replay while preserving a missing TTC value', () => {
    const run = parseLocalRun(API_RUN);

    expect(run.source).toBe('local-api');
    expect(run.synthetic).toBe(false);
    expect(run.hypotheses[0].metrics[0].longitudinalTtcSeconds).toBeNull();
    expect(run.conflictRegion).toEqual([]);
    expect(run.hypotheses[0].controllerOutcome.tested).toBe('fails');
  });

  it('maps run and proposal provenance through opaque identifiers', () => {
    expect(parseRunSummaries(API_RUNS)[0].runId).toBe('run_opaque');
    expect(parseProposals(API_PROPOSALS)[0]).toMatchObject({
      proposalNumber: 1,
      supportPasses: true,
      physicalRollouts: 6,
    });
  });

  it('rejects an opened held-out claim and misaligned replay timeline', () => {
    expect(() =>
      parseCampaign(
        { ...API_CAMPAIGN, api_version: '1.0.0' },
        API_METHODS,
        API_HYPOTHESES,
        API_CELLS,
      ),
    ).toThrowError('api_version is not supported');
    expect(() =>
      parseCampaign(
        { ...API_CAMPAIGN, held_out_comparison_run: true },
        API_METHODS,
        API_HYPOTHESES,
        API_CELLS,
      ),
    ).toThrowError('held-out comparison ran');
    const changed = structuredClone(API_RUN);
    changed.hypothesis.metrics[1].time_seconds = 0.3;
    expect(() => parseLocalRun(changed)).toThrowError('fixed step');
  });
});
