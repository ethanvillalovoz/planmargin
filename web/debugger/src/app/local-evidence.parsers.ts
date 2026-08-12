import { CampaignEvidence } from './campaign-evidence';
import { DebuggerHypothesis, DebuggerRun, MetricSample, Point2d } from './debugger.types';
import {
  LocalCell,
  LocalEvidenceSnapshot,
  LocalProposal,
  LocalRunSummary,
} from './local-evidence.types';

function object(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error(`${path} must be an object`);
  }
  return value as Record<string, unknown>;
}

function array(value: unknown, path: string): readonly unknown[] {
  if (!Array.isArray(value)) throw new Error(`${path} must be an array`);
  return value;
}

function text(value: unknown, path: string): string {
  if (typeof value !== 'string' || value.length === 0) {
    throw new Error(`${path} must be a non-empty string`);
  }
  return value;
}

function number(value: unknown, path: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new Error(`${path} must be a finite number`);
  }
  return value;
}

function integer(value: unknown, path: string): number {
  const result = number(value, path);
  if (!Number.isInteger(result)) throw new Error(`${path} must be an integer`);
  return result;
}

function boolean(value: unknown, path: string): boolean {
  if (typeof value !== 'boolean') throw new Error(`${path} must be a boolean`);
  return value;
}

function nullableBoolean(value: unknown, path: string): boolean | null {
  return value === null ? null : boolean(value, path);
}

function nullableNumber(value: unknown, path: string): number | null {
  return value === null ? null : number(value, path);
}

function point(value: unknown, path: string): Point2d {
  const candidate = object(value, path);
  return { x: number(candidate['x'], `${path}.x`), y: number(candidate['y'], `${path}.y`) };
}

function points(value: unknown, path: string): readonly Point2d[] {
  const result = array(value, path).map((candidate, index) =>
    point(candidate, `${path}[${index}]`),
  );
  if (result.length < 2) throw new Error(`${path} must contain at least two points`);
  return result;
}

function numberRecord(value: unknown, path: string): Readonly<Record<string, number>> {
  const candidate = object(value, path);
  return Object.fromEntries(
    Object.entries(candidate).map(([name, item]) => [name, number(item, `${path}.${name}`)]),
  );
}

function title(value: string): string {
  return value.length === 0 ? value : `${value[0].toUpperCase()}${value.slice(1)}`;
}

export function parseCampaign(
  campaignValue: unknown,
  methodsValue: unknown,
  hypothesesValue: unknown,
  cellsValue: unknown,
): { readonly campaign: CampaignEvidence; readonly cells: readonly LocalCell[] } {
  const campaign = object(campaignValue, 'campaign');
  if (campaign['evidence_mode'] !== 'real_local_redacted') {
    throw new Error('campaign.evidence_mode is not local redacted evidence');
  }
  if (campaign['held_out_opened'] !== false) {
    throw new Error('Local evidence claims that the held-out split was opened');
  }
  const methods = new Map(
    array(methodsValue, 'methods').map((value, index) => {
      const item = object(value, `methods[${index}]`);
      const method = text(item['method'], `methods[${index}].method`);
      if (method !== 'random' && method !== 'bayesian') {
        throw new Error(`methods[${index}].method is unsupported`);
      }
      return [method, item] as const;
    }),
  );
  const random = methods.get('random');
  const bayesian = methods.get('bayesian');
  if (random === undefined || bayesian === undefined || methods.size !== 2) {
    throw new Error('methods must contain exactly random and bayesian');
  }
  const hypotheses = new Map(
    array(hypothesesValue, 'hypotheses').map((value, index) => {
      const item = object(value, `hypotheses[${index}]`);
      return [text(item['hypothesis'], `hypotheses[${index}].hypothesis`), item] as const;
    }),
  );
  const hypothesisStatus = (name: string): string => {
    const item = hypotheses.get(name);
    if (item === undefined) throw new Error(`Missing hypothesis ${name}`);
    return title(text(item['status'], `hypotheses.${name}.status`));
  };
  const cells = array(cellsValue, 'cells').map((value, index): LocalCell => {
    const item = object(value, `cells[${index}]`);
    const method = text(item['method'], `cells[${index}].method`);
    if (method !== 'random' && method !== 'bayesian') {
      throw new Error(`cells[${index}].method is unsupported`);
    }
    return {
      cellId: text(item['cell_id'], `cells[${index}].cell_id`),
      method,
      seed: integer(item['seed'], `cells[${index}].seed`),
      selectionOrder: integer(item['selection_order'], `cells[${index}].selection_order`),
      proposalCount: integer(item['proposal_count'], `cells[${index}].proposal_count`),
      pipelineValidCount: integer(
        item['pipeline_valid_count'],
        `cells[${index}].pipeline_valid_count`,
      ),
      supportAndPipelineValidCount: integer(
        item['support_and_pipeline_valid_count'],
        `cells[${index}].support_and_pipeline_valid_count`,
      ),
      qualifyingFailureCount: integer(
        item['qualifying_failure_count'],
        `cells[${index}].qualifying_failure_count`,
      ),
      validRatePercent:
        number(
          item['support_and_pipeline_valid_rate'],
          `cells[${index}].support_and_pipeline_valid_rate`,
        ) * 100,
      finalFeasibleHypervolume: number(
        item['final_feasible_hypervolume'],
        `cells[${index}].final_feasible_hypervolume`,
      ),
    };
  });
  if (cells.length === 0) throw new Error('cells must not be empty');
  const methodView = (item: Record<string, unknown>) => ({
    proposals: integer(item['proposal_count'], 'method.proposal_count'),
    qualifyingFindings: integer(
      item['qualifying_failure_count'],
      'method.qualifying_failure_count',
    ),
    validRatePercent: number(item['support_and_pipeline_valid_rate'], 'method.valid_rate') * 100,
    finalHypervolume: number(
      item['mean_final_feasible_hypervolume'],
      'method.mean_final_feasible_hypervolume',
    ),
  });
  return {
    campaign: {
      campaignId: text(campaign['campaign_label'], 'campaign.campaign_label'),
      cells: cells.length,
      proposals: cells.reduce((sum, cell) => sum + cell.proposalCount, 0),
      physicalRollouts: integer(
        campaign['total_physical_rollouts'],
        'campaign.total_physical_rollouts',
      ),
      rolloutSteps: integer(campaign['waymax_rollout_steps'], 'campaign.waymax_rollout_steps'),
      methods: { random: methodView(random), bayesian: methodView(bayesian) },
      hypotheses: {
        efficiency: hypothesisStatus('h1_efficiency'),
        minimality: hypothesisStatus('h2_minimality'),
        validity: hypothesisStatus('h3_validity'),
      },
      nativeKernelSpeedupRange: '585–619×',
      heldOutOpened: false,
      mode: 'real-local-redacted',
    },
    cells,
  };
}

export function parseRunSummaries(value: unknown): readonly LocalRunSummary[] {
  const runs = array(value, 'runs').map((candidate, index): LocalRunSummary => {
    const item = object(candidate, `runs[${index}]`);
    if (item['evidence_mode'] !== 'real_local_redacted') {
      throw new Error(`runs[${index}] is not local redacted evidence`);
    }
    return {
      runId: text(item['run_id'], `runs[${index}].run_id`),
      label: text(item['label'], `runs[${index}].label`),
      recordCount: integer(item['record_count'], `runs[${index}].record_count`),
      policySpecificAvoidableFailure: boolean(
        item['policy_specific_avoidable_failure'],
        `runs[${index}].policy_specific_avoidable_failure`,
      ),
    };
  });
  if (runs.length === 0) throw new Error('runs must not be empty');
  return runs;
}

export function parseLocalRun(value: unknown): DebuggerRun {
  const run = object(value, 'run');
  if (
    run['schema_version'] !== 'planmargin.local-evidence.v1' ||
    run['evidence_mode'] !== 'real_local_redacted' ||
    run['synthetic'] !== false
  ) {
    throw new Error('Run is not a supported real local evidence record');
  }
  const hypothesisValue = object(run['hypothesis'], 'run.hypothesis');
  const trajectoriesValue = object(hypothesisValue['trajectories'], 'run.hypothesis.trajectories');
  const outcomeValue = object(
    hypothesisValue['controller_outcome'],
    'run.hypothesis.controller_outcome',
  );
  const outcome = (key: string): 'fails' | 'succeeds' => {
    const result = outcomeValue[key];
    if (result !== 'fails' && result !== 'succeeds') {
      throw new Error(`run.hypothesis.controller_outcome.${key} is invalid`);
    }
    return result;
  };
  const metrics = array(hypothesisValue['metrics'], 'run.hypothesis.metrics').map(
    (candidate, index): MetricSample => {
      const item = object(candidate, `run.hypothesis.metrics[${index}]`);
      return {
        timeSeconds: number(item['time_seconds'], `metrics[${index}].time_seconds`),
        signedSeparationMeters: number(
          item['signed_separation_meters'],
          `metrics[${index}].signed_separation_meters`,
        ),
        longitudinalTtcSeconds: nullableNumber(
          item['longitudinal_ttc_seconds'],
          `metrics[${index}].longitudinal_ttc_seconds`,
        ),
      };
    },
  );
  const stepSeconds = number(run['step_seconds'], 'run.step_seconds');
  if (stepSeconds <= 0 || metrics.length < 2) throw new Error('Run timeline is incomplete');
  metrics.forEach((sample, index) => {
    if (Math.abs(sample.timeSeconds - index * stepSeconds) > 1e-6) {
      throw new Error('Run timeline does not follow its fixed step');
    }
  });
  const hypothesis: DebuggerHypothesis = {
    id: text(hypothesisValue['id'], 'run.hypothesis.id'),
    label: text(hypothesisValue['label'], 'run.hypothesis.label'),
    onsetSeconds: number(hypothesisValue['onset_seconds'], 'run.hypothesis.onset_seconds'),
    speedMetersPerSecond: number(
      hypothesisValue['target_initial_speed_meters_per_second'],
      'run.hypothesis.target_initial_speed_meters_per_second',
    ),
    mutationType: text(hypothesisValue['mutation_type'], 'run.hypothesis.mutation_type'),
    mutationParameters: numberRecord(
      hypothesisValue['mutation_parameters'],
      'run.hypothesis.mutation_parameters',
    ),
    supported: boolean(hypothesisValue['supported'], 'run.hypothesis.supported'),
    deterministic: boolean(hypothesisValue['deterministic'], 'run.hypothesis.deterministic'),
    validationChecks: array(
      hypothesisValue['validation_checks'],
      'run.hypothesis.validation_checks',
    ).map((item, index) => text(item, `validation_checks[${index}]`)),
    controllerOutcome: { tested: outcome('tested'), reference: outcome('reference') },
    trajectories: {
      tested: points(trajectoriesValue['tested'], 'trajectories.tested'),
      reference: points(trajectoriesValue['reference'], 'trajectories.reference'),
      recorded: points(trajectoriesValue['recorded'], 'trajectories.recorded'),
    },
    metrics,
  };
  for (const trajectory of Object.values(hypothesis.trajectories)) {
    if (trajectory.length !== metrics.length) throw new Error('Run trajectories are not aligned');
  }
  return {
    schemaVersion: 'planmargin.debugger.v1',
    runId: text(run['run_id'], 'run.run_id'),
    scenarioLabel: text(run['scenario_label'], 'run.scenario_label'),
    source: 'local-api',
    synthetic: false,
    stepSeconds,
    roadCenterlines: array(run['road_centerlines'], 'run.road_centerlines').map((line, index) =>
      points(line, `run.road_centerlines[${index}]`),
    ),
    conflictRegion: [],
    hypotheses: [hypothesis],
  };
}

export function parseProposals(value: unknown): readonly LocalProposal[] {
  const proposals = array(value, 'proposals').map((candidate, index): LocalProposal => {
    const item = object(candidate, `proposals[${index}]`);
    const parameters = object(
      item['mutation_parameters'],
      `proposals[${index}].mutation_parameters`,
    );
    return {
      proposalNumber: integer(item['proposal_number'], `proposals[${index}].proposal_number`),
      attemptStatus: text(item['attempt_status'], `proposals[${index}].attempt_status`),
      normalizedMutationDistance: number(
        item['normalized_mutation_distance'],
        `proposals[${index}].normalized_mutation_distance`,
      ),
      brakingOnsetOffsetSeconds: number(
        parameters['braking_onset_offset_s'],
        `proposals[${index}].braking_onset_offset_s`,
      ),
      speedMultiplier: number(
        parameters['speed_multiplier'],
        `proposals[${index}].speed_multiplier`,
      ),
      empiricalSupportProbability: nullableNumber(
        item['empirical_support_probability'],
        `proposals[${index}].empirical_support_probability`,
      ),
      supportPasses: nullableBoolean(item['support_passes'], `proposals[${index}].support_passes`),
      objectiveAvailable: boolean(
        item['objective_available'],
        `proposals[${index}].objective_available`,
      ),
      policySpecificAvoidableFailure: nullableBoolean(
        item['policy_specific_avoidable_failure'],
        `proposals[${index}].policy_specific_avoidable_failure`,
      ),
      testedMutatedFailure: nullableBoolean(
        item['tested_mutated_failure'],
        `proposals[${index}].tested_mutated_failure`,
      ),
      referenceMutatedSuccess: nullableBoolean(
        item['reference_mutated_success'],
        `proposals[${index}].reference_mutated_success`,
      ),
      physicalRollouts: integer(item['physical_rollouts'], `proposals[${index}].physical_rollouts`),
    };
  });
  if (proposals.length === 0) throw new Error('proposals must not be empty');
  return proposals;
}

export function snapshot(
  campaign: CampaignEvidence,
  cells: readonly LocalCell[],
  runs: readonly LocalRunSummary[],
  initialRun: DebuggerRun,
): LocalEvidenceSnapshot {
  return { campaign, cells, runs, initialRun };
}
