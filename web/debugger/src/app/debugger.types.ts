export type MobileView = 'scene' | 'evidence' | 'metrics';
export type TrajectoryKind = 'tested' | 'reference' | 'recorded';

export interface Point2d {
  readonly x: number;
  readonly y: number;
}

export interface MetricSample {
  readonly timeSeconds: number;
  readonly signedSeparationMeters: number;
  readonly longitudinalTtcSeconds: number;
}

export interface TrajectorySet {
  readonly tested: readonly Point2d[];
  readonly reference: readonly Point2d[];
  readonly recorded: readonly Point2d[];
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
  readonly source: 'bundled-demo' | 'local-file';
  readonly synthetic: true;
  readonly stepSeconds: number;
  readonly roadCenterlines: readonly (readonly Point2d[])[];
  readonly conflictRegion: readonly Point2d[];
  readonly hypotheses: readonly DebuggerHypothesis[];
}

export interface ExportedView {
  readonly schemaVersion: 'planmargin.debugger-view.v1';
  readonly exportedAt: string;
  readonly runId: string;
  readonly scenarioLabel: string;
  readonly synthetic: true;
  readonly selectedHypothesisId: string;
  readonly timestepIndex: number;
  readonly timeSeconds: number;
}
