import { TestBed } from '@angular/core/testing';
import { DebuggerStore } from './debugger.store';
import { parseLocalRun } from './local-evidence.parsers';
import { API_RUN } from './local-evidence.test-fixtures';
import { SimulatorStore } from './simulator.store';

describe('SimulatorStore', () => {
  let store: SimulatorStore;
  let debuggerStore: DebuggerStore;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({});
    store = TestBed.inject(SimulatorStore);
    debuggerStore = TestBed.inject(DebuggerStore);
    debuggerStore.loadRun(parseLocalRun(API_RUN));
  });

  afterEach(() => {
    vi.useRealTimers();
    TestBed.resetTestingModule();
  });

  it('configures and clamps the camera timeline without changing planning evidence', () => {
    store.configureScene(199, 10, 99);
    expect(store.frameIndex()).toBe(99);
    expect(debuggerStore.timestepIndex()).toBe(0);

    store.seekFrame(500);
    expect(store.frameIndex()).toBe(198);
    expect(debuggerStore.timestepIndex()).toBe(0);

    store.seekFrame(-10);
    expect(store.frameIndex()).toBe(0);
    expect(debuggerStore.timestepIndex()).toBe(0);
  });

  it('owns sensor and camera annotation state', () => {
    store.selectMode('reconstruction');
    store.toggleLayer('boxes');

    expect(store.sensorMode()).toBe('reconstruction');
    expect(store.layers().boxes).toBe(false);
  });

  it('locks single-frame spatial assets to their source frame and stops playback', () => {
    store.configureScene(199, 10, 99);
    store.seekFrame(40);
    store.togglePlayback();
    expect(store.playing()).toBe(true);

    store.selectMode('reconstruction');
    expect(store.playing()).toBe(false);
    expect(store.frameIndex()).toBe(99);
    expect(store.temporalPlaybackAvailable()).toBe(false);

    store.togglePlayback();
    store.step(1);
    store.seekFrame(12);
    vi.advanceTimersByTime(500);
    expect(store.frameIndex()).toBe(99);
  });

  it('plays recorded frames at the configured rate and stops at the boundary', () => {
    store.configureScene(3, 10, 0);
    store.togglePlayback();
    vi.advanceTimersByTime(210);

    expect(store.frameIndex()).toBe(2);
    vi.advanceTimersByTime(110);
    expect(store.playing()).toBe(false);
  });

  it('runs the bounded replay against planning evidence instead of the camera segment', () => {
    store.configureScene(199, 10, 12);
    store.runStressTest();

    expect(store.stressStatus()).toBe('running');
    expect(store.sensorMode()).toBe('planning');
    expect(store.playing()).toBe(true);
    vi.advanceTimersByTime(300);
    expect(store.stressStatus()).toBe('complete');
    expect(store.playing()).toBe(false);
    expect(store.frameIndex()).toBe(12);
    expect(debuggerStore.timestepIndex()).not.toBe(48);
  });

  it('plays and seeks the selected planning run on its own timeline', () => {
    store.selectMode('planning');
    store.seekFrame(1);
    expect(debuggerStore.timestepIndex()).toBe(1);
    expect(store.frameIndex()).toBe(99);

    store.togglePlayback();
    expect(store.playing()).toBe(true);
    vi.advanceTimersByTime(110);
    expect(debuggerStore.timestepIndex()).toBeGreaterThanOrEqual(0);
  });

  it('jumps camera and planning timelines by one visible second', () => {
    store.configureScene(199, 10, 99);
    store.jumpSeconds(1);
    expect(store.frameIndex()).toBe(109);
    store.jumpSeconds(-1);
    expect(store.frameIndex()).toBe(99);

    store.selectMode('planning');
    debuggerStore.seek(0);
    store.jumpSeconds(1);
    expect(debuggerStore.timestepIndex()).toBe(1);
  });

  it('closes analysis when leaving planning and keeps stress replay unobstructed', () => {
    store.assistantOpen.set(true);
    store.selectMode('camera');
    expect(store.assistantOpen()).toBe(false);

    store.assistantOpen.set(true);
    store.runStressTest();
    expect(store.sensorMode()).toBe('planning');
    expect(store.assistantOpen()).toBe(false);
  });
});
