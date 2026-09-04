export type TrajectoryKind = 'tested' | 'reference' | 'recorded';

export interface Point2d {
  readonly x: number;
  readonly y: number;
}

export interface MetricSample {
  readonly timeSeconds: number;
  readonly signedSeparationMeters: number;
  readonly longitudinalTtcSeconds: number | null;
}

export interface TrajectorySet {
  readonly tested: readonly Point2d[];
  readonly reference: readonly Point2d[];
  readonly recorded: readonly Point2d[];
}

export interface MutationTarget {
  readonly original: readonly Point2d[];
  readonly counterfactual: readonly Point2d[];
}

export interface ControllerOutcome {
  readonly tested: 'fails' | 'succeeds';
  readonly reference: 'fails' | 'succeeds';
}

export interface DebuggerHypothesis {
  readonly id: string;
  readonly label: string;
  readonly onsetSeconds: number;
  readonly speedMetersPerSecond: number;
  readonly mutationType: string;
  readonly mutationParameters: Readonly<Record<string, number>>;
  readonly supported: boolean;
  readonly deterministic: boolean;
  readonly validationChecks: readonly string[];
  readonly controllerOutcome: ControllerOutcome;
  readonly trajectories: TrajectorySet;
  readonly metrics: readonly MetricSample[];
}

export interface DebuggerRun {
  readonly schemaVersion: 'planmargin.debugger.v1';
  readonly runId: string;
  readonly scenarioLabel: string;
  readonly source: 'bundled-demo' | 'local-file' | 'local-api';
  readonly synthetic: boolean;
  readonly stepSeconds: number;
  readonly roadCenterlines: readonly (readonly Point2d[])[];
  readonly mutationTarget: MutationTarget;
  readonly conflictRegion: readonly Point2d[];
  readonly hypotheses: readonly DebuggerHypothesis[];
}
