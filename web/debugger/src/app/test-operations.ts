import reportJson from '../../public/data/test-operations-v1.json';

export type OperationStatus =
  'healthy' | 'degraded' | 'pass' | 'fail' | 'active' | 'blocked' | 'stopped' | 'pending_evidence';

export interface TestOperationSlo {
  readonly id: string;
  readonly name: string;
  readonly target: string;
  readonly observed: string;
  readonly status: 'pass' | 'fail';
  readonly owner: string;
}

export interface TestOperationStage {
  readonly id: string;
  readonly name: string;
  readonly status: 'healthy' | 'degraded';
  readonly observed: string;
  readonly detail: string;
}

export interface CoverageGap {
  readonly id: string;
  readonly label: string;
  readonly status: 'not_covered';
  readonly next_test: string;
}

export interface TestOperationIssue {
  readonly id: string;
  readonly severity: 'high' | 'medium' | 'low';
  readonly state: 'active' | 'blocked' | 'stopped' | 'pending_evidence';
  readonly component: string;
  readonly title: string;
  readonly evidence: string;
  readonly failed_gates: readonly string[];
  readonly next_action: string;
  readonly source: string;
}

export interface TestOperationsReport {
  readonly schema_version: '1.0.0';
  readonly record_type: 'planmargin.test_operations_report';
  readonly evidence_mode: 'published_aggregate';
  readonly claim_boundary: string;
  readonly campaign: {
    readonly campaign_id: string;
    readonly execution_health: 'healthy' | 'degraded';
    readonly behavior_outcome: 'no_qualifying_regression';
    readonly completed_cells: number;
    readonly planned_cells: number;
    readonly proposals: number;
    readonly physical_rollouts: number;
    readonly waymax_steps: number;
    readonly recorded_work_seconds: number;
    readonly real_data_only: true;
  };
  readonly slo_summary: {
    readonly status: 'healthy' | 'degraded';
    readonly passing: number;
    readonly total: number;
  };
  readonly slos: readonly TestOperationSlo[];
  readonly pipeline_stages: readonly TestOperationStage[];
  readonly coverage: {
    readonly plan_version: string;
    readonly scenario_family: string;
    readonly scenario_count: number;
    readonly seeds: number;
    readonly search_methods: number;
    readonly cells: number;
    readonly mutation_dimensions: readonly string[];
    readonly methods: Readonly<
      Record<
        string,
        {
          readonly proposal_count: number;
          readonly eligible_count: number;
          readonly eligible_rate: number;
        }
      >
    >;
    readonly fault_protection: {
      readonly plan_version: string;
      readonly fault: string;
      readonly protected_behavior: string;
      readonly scenario_count: number;
      readonly physical_rollouts: number;
      readonly scene_gate_passes: number;
      readonly scene_gate_total: number;
      readonly status: 'qualified';
    };
    readonly assistance_handoff: {
      readonly plan_version: string;
      readonly fault: string;
      readonly protected_behavior: string;
      readonly scenario_count: number;
      readonly physical_rollouts: number;
      readonly scene_gate_passes: number;
      readonly scene_gate_total: number;
      readonly exact_transition_count: number;
      readonly status: 'qualified';
    };
    readonly known_gaps: readonly CoverageGap[];
  };
  readonly issues: readonly TestOperationIssue[];
  readonly report_sha256: string;
}

function record(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
  return value as Record<string, unknown>;
}

export function parseTestOperations(value: unknown): TestOperationsReport {
  const candidate = record(value, 'test operations report');
  if (candidate['schema_version'] !== '1.0.0') throw new Error('Unsupported operations schema');
  if (candidate['record_type'] !== 'planmargin.test_operations_report') {
    throw new Error('Unexpected operations record');
  }
  const campaign = record(candidate['campaign'], 'campaign');
  if (campaign['real_data_only'] !== true) {
    throw new Error('Operations report is not verified real-data evidence');
  }
  if (!Array.isArray(candidate['slos']) || !Array.isArray(candidate['pipeline_stages'])) {
    throw new Error('Operations report is incomplete');
  }
  return value as TestOperationsReport;
}

export const TEST_OPERATIONS = parseTestOperations(reportJson);
