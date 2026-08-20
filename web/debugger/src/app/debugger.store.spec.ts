import { TestBed } from '@angular/core/testing';
import { DebuggerStore } from './debugger.store';
import { parseLocalRun } from './local-evidence.parsers';
import { API_RUN } from './local-evidence.test-fixtures';

describe('DebuggerStore', () => {
  let store: DebuggerStore;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    store = TestBed.inject(DebuggerStore);
    store.loadRun(parseLocalRun(API_RUN));
  });

  afterEach(() => TestBed.resetTestingModule());

  it('selects a hypothesis and clamps timeline seeks', () => {
    store.selectHypothesis('stage-0-counterfactual');
    store.seek(999);
    expect(store.selectedHypothesis().label).toBe('Validated Stage 0 counterfactual');
    expect(store.timestepIndex()).toBe(store.sampleCount() - 1);

    store.seek(-10);
    expect(store.timestepIndex()).toBe(0);
  });

  it('rejects an unknown hypothesis without corrupting selection', () => {
    expect(() => store.selectHypothesis('missing')).toThrowError('Unknown hypothesis');
    expect(store.selectedHypothesisId()).toBe('stage-0-counterfactual');
  });

  it('advances and stops playback deterministically', () => {
    vi.useFakeTimers();
    store.seek(0);
    store.togglePlayback();
    vi.advanceTimersByTime(110);
    expect(store.timestepIndex()).toBe(1);
    expect(store.playing()).toBe(true);

    store.stop();
    vi.advanceTimersByTime(500);
    expect(store.timestepIndex()).toBe(1);
    expect(store.playing()).toBe(false);
    vi.useRealTimers();
  });

  it('clears planning evidence after local evidence disconnects', () => {
    store.loadRun({
      ...store.run(),
      runId: 'temporary-local',
      source: 'local-api',
      synthetic: false,
    });
    store.clearRun();

    expect(store.hasRun()).toBe(false);
    expect(store.selectedHypothesisId()).toBe('');
    expect(store.timestepIndex()).toBe(0);
    expect(() => store.run()).toThrowError('Real local planning evidence is not connected');
  });
});
