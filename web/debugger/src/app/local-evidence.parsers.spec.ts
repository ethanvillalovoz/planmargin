import {
  parseCampaignInvestigation,
  parseCampaign,
  parseLocalRun,
  parseProposalAnalysis,
  parseProposals,
  parseRunSummaries,
} from './local-evidence.parsers';
import {
  API_CAMPAIGN,
  API_CELLS,
  API_HYPOTHESES,
  API_INVESTIGATION,
  API_METHODS,
  API_PROPOSALS,
  API_RUN,
  API_RUNS,
} from './local-evidence.test-fixtures';

describe('local evidence response parsers', () => {
  it('keeps missing lead observations aligned without inventing measurements', () => {
    const payload = {
      ...API_RUN,
      mutation_target: {
        original: [API_RUN.mutation_target.original[0], null],
        counterfactual: [API_RUN.mutation_target.counterfactual[0], null],
      },
      hypothesis: {
        ...API_RUN.hypothesis,
        mutation_type: 'command_dropout',
        metrics: [
          API_RUN.hypothesis.metrics[0],
          {
            ...API_RUN.hypothesis.metrics[1],
            signed_separation_meters: null,
            longitudinal_ttc_seconds: null,
          },
        ],
      },
    };
    const run = parseLocalRun(payload);
    expect(run.mutationTarget.counterfactual).toHaveLength(2);
    expect(run.mutationTarget.counterfactual[1]).toBeNull();
    expect(run.hypotheses[0].metrics[1].signedSeparationMeters).toBeNull();
    expect(() =>
      parseLocalRun({
        ...payload,
        hypothesis: { ...payload.hypothesis, metrics: API_RUN.hypothesis.metrics },
      }),
    ).toThrowError('not aligned');
    expect(() =>
      parseLocalRun({
        ...payload,
        hypothesis: { ...payload.hypothesis, mutation_type: 'lead_braking' },
      }),
    ).toThrowError('observation gaps');
  });

  it('preserves optional recorded footprints and rejects partial or malformed geometry', () => {
    const corners = [
      { x: 2, y: 1 },
      { x: -2, y: 1 },
      { x: -2, y: -1 },
      { x: 2, y: -1 },
    ];
    const footprints = Object.fromEntries(
      ['tested', 'reference', 'recorded', 'lead'].map((kind) => [kind, [corners, corners]]),
    );
    const payload = {
      ...API_RUN,
      hypothesis: { ...API_RUN.hypothesis, vehicle_footprints: footprints },
    };
    expect(parseLocalRun(payload).hypotheses[0].vehicleFootprints?.tested[0]).toEqual(corners);
    expect(parseLocalRun(API_RUN).hypotheses[0].vehicleFootprints).toBeUndefined();
    for (const invalid of [
      [corners],
      [corners.slice(0, 3), corners],
      [corners.map((p) => ({ ...p, x: NaN })), corners],
    ]) {
      expect(() =>
        parseLocalRun({
          ...payload,
          hypothesis: {
            ...payload.hypothesis,
            vehicle_footprints: { ...footprints, tested: invalid },
          },
        }),
      ).toThrow();
    }
  });

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
    expect(run.mutationTarget.counterfactual).toEqual(API_RUN.mutation_target.counterfactual);
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

  it('rejects inconsistent proposal replay availability', () => {
    const proposals = structuredClone(API_PROPOSALS);
    proposals[0]!.trajectory_available = true;
    proposals[0]!.replay_run_id = null;

    expect(() => parseProposals(proposals)).toThrowError(/replay availability is inconsistent/);
  });

  it('maps the campaign-wide index and proposal-specific sealed analysis', () => {
    const investigation = parseCampaignInvestigation(API_INVESTIGATION);
    const analysis = parseProposalAnalysis({
      evidence_mode: 'real_local_redacted',
      analysis_mode: 'deterministic_proposal_specific',
      cell_id: 'cell_opaque',
      proposal_number: 1,
      decision: 'not_qualified',
      decisive_gate: 'tested_controller_failure',
      explanation: 'The tested controller remained successful.',
      facts: [{ label: 'method', value: 'bayesian' }],
      record_sha256: 'a'.repeat(64),
      trajectory_available: false,
      replay_run_id: null,
    });

    expect(investigation.proposalCount).toBe(1);
    expect(investigation.closestMargin[0].cellId).toBe('cell_opaque');
    expect(analysis.decisiveGate).toBe('tested_controller_failure');
    expect(analysis.trajectoryAvailable).toBe(false);
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
