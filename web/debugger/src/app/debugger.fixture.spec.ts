import { parseDebuggerRun, SYNTHETIC_DEBUGGER_RUN } from './debugger.fixture';

describe('parseDebuggerRun', () => {
  it('accepts the bundled synthetic fixture', () => {
    expect(parseDebuggerRun(SYNTHETIC_DEBUGGER_RUN)).toBe(SYNTHETIC_DEBUGGER_RUN);
    expect(SYNTHETIC_DEBUGGER_RUN.hypotheses).toHaveLength(3);
  });

  it('rejects non-synthetic data before rendering', () => {
    const candidate = { ...SYNTHETIC_DEBUGGER_RUN, synthetic: false };
    expect(() => parseDebuggerRun(candidate)).toThrowError('accepts synthetic runs only');
  });

  it('rejects trajectories that do not align with the metric timeline', () => {
    const first = SYNTHETIC_DEBUGGER_RUN.hypotheses[0];
    const candidate = {
      ...SYNTHETIC_DEBUGGER_RUN,
      hypotheses: [
        {
          ...first,
          trajectories: { ...first.trajectories, tested: first.trajectories.tested.slice(1) },
        },
      ],
    };
    expect(() => parseDebuggerRun(candidate)).toThrowError('must align with metrics');
  });

  it('rejects a metric timeline that violates the declared step', () => {
    const first = SYNTHETIC_DEBUGGER_RUN.hypotheses[0];
    const metrics = [...first.metrics];
    metrics[1] = { ...metrics[1], timeSeconds: 0.15 };
    const candidate = {
      ...SYNTHETIC_DEBUGGER_RUN,
      hypotheses: [{ ...first, metrics }],
    };
    expect(() => parseDebuggerRun(candidate)).toThrowError('must follow stepSeconds');
  });

  it('rejects negative mutation parameters', () => {
    const first = SYNTHETIC_DEBUGGER_RUN.hypotheses[0];
    const candidate = {
      ...SYNTHETIC_DEBUGGER_RUN,
      hypotheses: [{ ...first, speedMetersPerSecond: -1 }],
    };
    expect(() => parseDebuggerRun(candidate)).toThrowError('must be non-negative');
  });
});
