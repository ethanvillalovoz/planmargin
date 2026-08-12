export const API_CAMPAIGN = {
  evidence_mode: 'real_local_redacted',
  campaign_label: 'natural-development-v1',
  total_physical_rollouts: 24,
  waymax_rollout_steps: 1_920,
  held_out_opened: false,
};

export const API_METHODS = [
  {
    method: 'random',
    proposal_count: 32,
    qualifying_failure_count: 0,
    support_and_pipeline_valid_rate: 0.5,
    mean_final_feasible_hypervolume: 0.2,
  },
  {
    method: 'bayesian',
    proposal_count: 32,
    qualifying_failure_count: 0,
    support_and_pipeline_valid_rate: 0.75,
    mean_final_feasible_hypervolume: 0.3,
  },
];

export const API_HYPOTHESES = [
  { hypothesis: 'h1_efficiency', status: 'untestable' },
  { hypothesis: 'h2_minimality', status: 'untestable' },
  { hypothesis: 'h3_validity', status: 'supported' },
];

export const API_CELLS = [
  {
    cell_id: 'cell_opaque',
    method: 'bayesian',
    seed: 0,
    selection_order: 1,
    proposal_count: 32,
    pipeline_valid_count: 28,
    support_and_pipeline_valid_count: 24,
    qualifying_failure_count: 0,
    support_and_pipeline_valid_rate: 0.75,
    final_feasible_hypervolume: 0.3,
  },
];

export const API_RUNS = [
  {
    run_id: 'run_opaque',
    label: 'Private local Stage 0 controller comparison',
    evidence_mode: 'real_local_redacted',
    record_count: 4,
    policy_specific_avoidable_failure: false,
  },
];

export const API_RUN = {
  schema_version: 'planmargin.local-evidence.v1',
  run_id: 'run_opaque',
  scenario_label: 'Private local comparison',
  evidence_mode: 'real_local_redacted',
  synthetic: false,
  step_seconds: 0.1,
  road_centerlines: [
    [
      { x: 0, y: 0 },
      { x: 20, y: 0 },
    ],
  ],
  mutation_target: {
    original: [
      { x: 10, y: 0 },
      { x: 10.8, y: 0 },
    ],
    counterfactual: [
      { x: 10, y: 0 },
      { x: 10.7, y: 0 },
    ],
  },
  hypothesis: {
    id: 'stage-0-counterfactual',
    label: 'Validated Stage 0 counterfactual',
    mutation_type: 'lead_braking',
    mutation_parameters: { braking_onset_offset_s: 0.2, speed_multiplier: 0.8 },
    onset_seconds: 0.2,
    target_initial_speed_meters_per_second: 8,
    supported: true,
    deterministic: true,
    validation_checks: ['schema', 'content_identity'],
    controller_outcome: { tested: 'fails', reference: 'succeeds' },
    trajectories: {
      tested: [
        { x: 0, y: 0 },
        { x: 1, y: 0 },
      ],
      reference: [
        { x: 0, y: 0.2 },
        { x: 1, y: 0.2 },
      ],
      recorded: [
        { x: 0, y: -0.2 },
        { x: 1, y: -0.2 },
      ],
    },
    metrics: [
      {
        time_seconds: 0,
        signed_separation_meters: 5,
        longitudinal_ttc_seconds: null,
      },
      {
        time_seconds: 0.1,
        signed_separation_meters: 4.8,
        longitudinal_ttc_seconds: 3.2,
      },
    ],
  },
  privacy: {
    scenario_identifier_exposed: false,
    source_shard_exposed: false,
    record_index_exposed: false,
    raw_provenance_exposed: false,
  },
};

export const API_PROPOSALS = [
  {
    proposal_number: 1,
    attempt_status: 'accepted',
    normalized_mutation_distance: 0.8,
    mutation_parameters: { braking_onset_offset_s: 0.2, speed_multiplier: 0.8 },
    empirical_support_probability: 0.6,
    support_passes: true,
    objective_available: true,
    policy_specific_avoidable_failure: false,
    tested_mutated_failure: false,
    reference_mutated_success: true,
    physical_rollouts: 6,
  },
];
