import { TestBed } from '@angular/core/testing';
import { DebuggerStore } from './debugger.store';

describe('DebuggerStore', () => {
  let store: DebuggerStore;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    store = TestBed.inject(DebuggerStore);
  });

  afterEach(() => TestBed.resetTestingModule());

  it('selects a hypothesis and clamps timeline seeks', () => {
    store.selectHypothesis('proposal-01');
    store.seek(999);
    expect(store.selectedHypothesis().label).toBe('Proposal 01');
    expect(store.timestepIndex()).toBe(store.sampleCount() - 1);

    store.seek(-10);
    expect(store.timestepIndex()).toBe(0);
  });

  it('rejects an unknown hypothesis without corrupting selection', () => {
    expect(() => store.selectHypothesis('missing')).toThrowError('Unknown hypothesis');
    expect(store.selectedHypothesisId()).toBe('proposal-02');
  });

  it('advances and stops playback deterministically', () => {
    vi.useFakeTimers();
    store.seek(0);
    store.togglePlayback();
    vi.advanceTimersByTime(310);
    expect(store.timestepIndex()).toBe(3);
    expect(store.playing()).toBe(true);

    store.stop();
    vi.advanceTimersByTime(500);
    expect(store.timestepIndex()).toBe(3);
    expect(store.playing()).toBe(false);
    vi.useRealTimers();
  });
});
