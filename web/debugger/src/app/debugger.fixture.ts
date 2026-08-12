import {
  DebuggerHypothesis,
  DebuggerRun,
  MetricSample,
  Point2d,
  TrajectorySet,
} from './debugger.types';

const SAMPLE_COUNT = 81;
const STEP_SECONDS = 0.1;

function points(count: number, makePoint: (index: number) => Point2d): readonly Point2d[] {
  return Array.from({ length: count }, (_, index) => makePoint(index));
}

function trajectories(offset: number, braking: number): TrajectorySet {
  const build = (lateralOffset: number, deceleration: number) =>
    points(SAMPLE_COUNT, (index) => {
      const t = index * STEP_SECONDS;
      const progress = Math.max(0, 8.2 * t - deceleration * Math.max(0, t - 2.4) ** 2);
      return {
        x: -31 + progress,
        y: lateralOffset + 1.8 * Math.sin((progress - 10) / 18),
      };
    });

  return {
    tested: build(offset, braking),
    reference: build(0.9, 0.43),
    recorded: build(-0.75, 0.56),
  };
}

function metrics(failureBias: number): readonly MetricSample[] {
  return Array.from({ length: SAMPLE_COUNT }, (_, index) => {
    const timeSeconds = Number((index * STEP_SECONDS).toFixed(1));
    const conflict = Math.exp(-((timeSeconds - 4.8) ** 2) / 1.7);
    return {
      timeSeconds,
      signedSeparationMeters: 8.2 - 8.9 * conflict + failureBias,
      longitudinalTtcSeconds: Math.max(0.25, 6.2 - 5.4 * conflict + failureBias * 0.4),
    };
  });
}

function hypothesis(
  id: string,
  label: string,
  onsetSeconds: number,
  speedMetersPerSecond: number,
  failureBias: number,
  outcome: DebuggerHypothesis['controllerOutcome'],
): DebuggerHypothesis {
  return {
    id,
    label,
    onsetSeconds,
    speedMetersPerSecond,
    supported: true,
    deterministic: true,
    validationChecks: ['schema', 'finite-values', 'aligned-timeline'],
    controllerOutcome: outcome,
    trajectories: trajectories(failureBias * 0.35, 0.48 + failureBias * 0.02),
    metrics: metrics(failureBias),
  };
}

const RAW_SYNTHETIC_RUN: DebuggerRun = {
  schemaVersion: 'planmargin.debugger.v1',
  runId: 'synthetic-demo-v1',
  scenarioLabel: 'lead_braking_fixture',
  source: 'bundled-demo',
  synthetic: true,
  stepSeconds: STEP_SECONDS,
  roadCenterlines: [
    points(17, (index) => ({ x: -40 + index * 5, y: -4 + Math.sin(index / 3) * 1.3 })),
    points(17, (index) => ({ x: -40 + index * 5, y: 4 + Math.sin(index / 3) * 1.3 })),
    points(13, (index) => ({ x: -5 + Math.sin(index / 3), y: -30 + index * 5 })),
  ],
  conflictRegion: [
    { x: -6, y: -7 },
    { x: 8, y: -7 },
    { x: 8, y: 7 },
    { x: -6, y: 7 },
  ],
  hypotheses: [
    hypothesis('original', 'Original', 0, 8.2, 1.25, {
      tested: 'succeeds',
      reference: 'succeeds',
    }),
    hypothesis('proposal-01', 'Proposal 01', 2.8, 7.4, 0.45, {
      tested: 'succeeds',
      reference: 'succeeds',
    }),
    hypothesis('proposal-02', 'Proposal 02', 2.4, 6.8, -0.7, {
      tested: 'fails',
      reference: 'succeeds',
    }),
  ],
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function finiteNumber(value: unknown, path: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new Error(`${path} must be a finite number`);
  }
  return value;
}

function validatePoint(value: unknown, path: string): asserts value is Point2d {
  if (!isRecord(value)) {
    throw new Error(`${path} must be an object`);
  }
  finiteNumber(value['x'], `${path}.x`);
  finiteNumber(value['y'], `${path}.y`);
}

export function parseDebuggerRun(value: unknown): DebuggerRun {
  if (!isRecord(value)) {
    throw new Error('Run must be a JSON object');
  }
  if (value['schemaVersion'] !== 'planmargin.debugger.v1') {
    throw new Error('Unsupported debugger schema');
  }
  if (value['synthetic'] !== true) {
    throw new Error('This thin debugger accepts synthetic runs only');
  }
  if (value['source'] !== 'bundled-demo' && value['source'] !== 'local-file') {
    throw new Error('Run source must be bundled-demo or local-file');
  }
  if (
    typeof value['runId'] !== 'string' ||
    value['runId'].length === 0 ||
    typeof value['scenarioLabel'] !== 'string' ||
    value['scenarioLabel'].length === 0
  ) {
    throw new Error('Run identity fields must be non-empty strings');
  }
  const stepSeconds = finiteNumber(value['stepSeconds'], 'stepSeconds');
  if (stepSeconds <= 0) {
    throw new Error('stepSeconds must be positive');
  }
  const roadCenterlines = value['roadCenterlines'];
  const conflictRegion = value['conflictRegion'];
  const hypotheses = value['hypotheses'];
  if (
    !Array.isArray(roadCenterlines) ||
    !Array.isArray(conflictRegion) ||
    !Array.isArray(hypotheses)
  ) {
    throw new Error('Run geometry and hypotheses must be arrays');
  }
  if (roadCenterlines.length === 0) {
    throw new Error('Run must contain at least one road centerline');
  }
  roadCenterlines.forEach((line, lineIndex) => {
    if (!Array.isArray(line) || line.length < 2) {
      throw new Error(`roadCenterlines[${lineIndex}] must contain at least two points`);
    }
    line.forEach((point, pointIndex) =>
      validatePoint(point, `roadCenterlines[${lineIndex}][${pointIndex}]`),
    );
  });
  if (conflictRegion.length < 3) {
    throw new Error('conflictRegion must contain at least three points');
  }
  conflictRegion.forEach((point, index) => validatePoint(point, `conflictRegion[${index}]`));
  if (hypotheses.length === 0) {
    throw new Error('Run must contain at least one hypothesis');
  }

  let expectedSamples: number | undefined;
  const ids = new Set<string>();
  hypotheses.forEach((hypothesisValue, hypothesisIndex) => {
    const path = `hypotheses[${hypothesisIndex}]`;
    if (!isRecord(hypothesisValue)) {
      throw new Error(`${path} must be an object`);
    }
    const id = hypothesisValue['id'];
    if (typeof id !== 'string' || id.length === 0 || ids.has(id)) {
      throw new Error(`${path}.id must be a unique non-empty string`);
    }
    ids.add(id);
    if (typeof hypothesisValue['label'] !== 'string') {
      throw new Error(`${path}.label must be a string`);
    }
    const onsetSeconds = finiteNumber(hypothesisValue['onsetSeconds'], `${path}.onsetSeconds`);
    const speedMetersPerSecond = finiteNumber(
      hypothesisValue['speedMetersPerSecond'],
      `${path}.speedMetersPerSecond`,
    );
    if (onsetSeconds < 0 || speedMetersPerSecond < 0) {
      throw new Error(`${path} onset and speed must be non-negative`);
    }
    if (hypothesisValue['supported'] !== true || hypothesisValue['deterministic'] !== true) {
      throw new Error(`${path} must be supported and deterministic`);
    }
    const checks = hypothesisValue['validationChecks'];
    if (
      !Array.isArray(checks) ||
      checks.length === 0 ||
      !checks.every((check) => typeof check === 'string')
    ) {
      throw new Error(`${path}.validationChecks must contain strings`);
    }
    const outcome = hypothesisValue['controllerOutcome'];
    if (
      !isRecord(outcome) ||
      !['fails', 'succeeds'].includes(String(outcome['tested'])) ||
      !['fails', 'succeeds'].includes(String(outcome['reference']))
    ) {
      throw new Error(`${path}.controllerOutcome is invalid`);
    }
    const trajectoryValue = hypothesisValue['trajectories'];
    const metricValue = hypothesisValue['metrics'];
    if (!isRecord(trajectoryValue) || !Array.isArray(metricValue) || metricValue.length < 2) {
      throw new Error(`${path} must contain trajectories and metrics`);
    }
    for (const kind of ['tested', 'reference', 'recorded'] as const) {
      const trajectory = trajectoryValue[kind];
      if (!Array.isArray(trajectory) || trajectory.length !== metricValue.length) {
        throw new Error(`${path}.trajectories.${kind} must align with metrics`);
      }
      trajectory.forEach((point, index) =>
        validatePoint(point, `${path}.trajectories.${kind}[${index}]`),
      );
    }
    metricValue.forEach((sample, index) => {
      if (!isRecord(sample)) {
        throw new Error(`${path}.metrics[${index}] must be an object`);
      }
      const timeSeconds = finiteNumber(
        sample['timeSeconds'],
        `${path}.metrics[${index}].timeSeconds`,
      );
      if (Math.abs(timeSeconds - index * stepSeconds) > 1e-6) {
        throw new Error(`${path}.metrics must follow stepSeconds`);
      }
      finiteNumber(
        sample['signedSeparationMeters'],
        `${path}.metrics[${index}].signedSeparationMeters`,
      );
      finiteNumber(
        sample['longitudinalTtcSeconds'],
        `${path}.metrics[${index}].longitudinalTtcSeconds`,
      );
    });
    expectedSamples ??= metricValue.length;
    if (metricValue.length !== expectedSamples) {
      throw new Error('All hypotheses must use the same timeline length');
    }
  });

  return value as unknown as DebuggerRun;
}

export const SYNTHETIC_DEBUGGER_RUN = parseDebuggerRun(RAW_SYNTHETIC_RUN);
