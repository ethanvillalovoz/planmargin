import reportJson from '../../public/data/test-operations-v2.json';

export type OperationStatus =
  'healthy' | 'degraded' | 'pass' | 'fail' | 'active' | 'blocked' | 'stopped' | 'pending_evidence';

export interface TestOperationSlo {
  readonly id: string;
  readonly name: string;
  readonly indicator: string;
  readonly target: string;
  readonly observed: string;
  readonly objective: number;
  readonly observed_value: number;
  readonly error_budget_remaining_percent: number;
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
  readonly diagnostic: {
    readonly detected_by: string;
    readonly owner: string;
    readonly impact: string;
    readonly root_cause_path: readonly string[];
    readonly resolution: string;
    readonly prevention: string;
  };
}

export interface TestSuiteHealth {
  readonly id: string;
  readonly name: string;
  readonly plan_version: string;
  readonly platform: string;
  readonly owner: string;
  readonly status: 'healthy' | 'degraded';
  readonly scenario_count: number;
  readonly test_cell_count: number;
  readonly execution_count: number;
  readonly execution_unit: string;
  readonly gate_passes: number;
  readonly gate_total: number;
}

export interface VersionedCoveragePlan {
  readonly id: string;
  readonly plan_version: string;
  readonly scenario_family: string;
  readonly scenario_count: number;
  readonly test_cell_count: number;
  readonly gate_passes: number;
  readonly gate_total: number;
  readonly status: 'qualified' | 'no_go';
}

export interface TestOperationsReport {
  readonly schema_version: '2.0.0';
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
  readonly test_inventory: {
    readonly release_critical_cells: number;
    readonly passing_release_critical_cells: number;
    readonly tracked_suites: number;
    readonly active_health_alerts: number;
    readonly held_decisions: number;
    readonly suites: readonly TestSuiteHealth[];
  };
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
    readonly versioned_plans: readonly VersionedCoveragePlan[];
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
  if (candidate['schema_version'] !== '2.0.0') throw new Error('Unsupported operations schema');
  if (candidate['record_type'] !== 'planmargin.test_operations_report') {
    throw new Error('Unexpected operations record');
  }
  const campaign = record(candidate['campaign'], 'campaign');
  if (campaign['real_data_only'] !== true) {
    throw new Error('Operations report is not verified real-data evidence');
  }
  if (
    !Array.isArray(candidate['slos']) ||
    !Array.isArray(candidate['pipeline_stages']) ||
    !Array.isArray(record(candidate['test_inventory'], 'test inventory')['suites'])
  ) {
    throw new Error('Operations report is incomplete');
  }
  return value as TestOperationsReport;
}

export const TEST_OPERATIONS = parseTestOperations(reportJson);
