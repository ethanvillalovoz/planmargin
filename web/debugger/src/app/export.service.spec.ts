import { SYNTHETIC_DEBUGGER_RUN } from './debugger.fixture';
import { serializeView } from './export.service';

describe('serializeView', () => {
  it('creates a stable view record without trajectory or provenance payloads', () => {
    const record = serializeView(
      SYNTHETIC_DEBUGGER_RUN,
      'proposal-02',
      48,
      '2026-08-11T00:00:00.000Z',
    );
    expect(record).toEqual({
      schemaVersion: 'planmargin.debugger-view.v1',
      exportedAt: '2026-08-11T00:00:00.000Z',
      runId: 'synthetic-demo-v1',
      scenarioLabel: 'lead_braking_fixture',
      synthetic: true,
      selectedHypothesisId: 'proposal-02',
      timestepIndex: 48,
      timeSeconds: 4.8,
    });
    expect(JSON.stringify(record)).not.toContain('trajectories');
  });

  it('refuses to serialize real local evidence', () => {
    expect(() =>
      serializeView(
        { ...SYNTHETIC_DEBUGGER_RUN, source: 'local-api', synthetic: false },
        'proposal-02',
        48,
        '2026-08-09T00:00:00.000Z',
      ),
    ).toThrowError('cannot be exported');
  });

  it('rejects an invalid timestep', () => {
    expect(() => serializeView(SYNTHETIC_DEBUGGER_RUN, 'proposal-02', 999, 'now')).toThrowError(
      'outside the run timeline',
    );
  });
});
