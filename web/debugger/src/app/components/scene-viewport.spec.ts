import { TestBed } from '@angular/core/testing';
import { DebuggerStore } from '../debugger.store';
import { parseLocalRun } from '../local-evidence.parsers';
import { API_RUN } from '../local-evidence.test-fixtures';
import { SceneViewport } from './scene-viewport';

describe('SceneViewport', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe(): void {}
        disconnect(): void {}
      },
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    TestBed.resetTestingModule();
  });

  it('flips trajectory callouts inward near the right edge', () => {
    const fixture = TestBed.createComponent(SceneViewport);
    const store = TestBed.inject(DebuggerStore);
    const longTrajectory = [
      { x: 0, y: 0 },
      { x: 100, y: 0 },
    ];
    store.loadRun(
      parseLocalRun({
        ...API_RUN,
        road_centerlines: [longTrajectory],
        hypothesis: {
          ...API_RUN.hypothesis,
          trajectories: {
            tested: longTrajectory,
            reference: longTrajectory.map((point) => ({ ...point, y: 1 })),
            recorded: longTrajectory.map((point) => ({ ...point, y: -1 })),
          },
        },
      }),
    );
    store.seek(1);
    fixture.detectChanges();

    const scene = (
      fixture.componentInstance as unknown as {
        fallbackScene(): {
          trajectories: readonly {
            current: { x: number };
            callout: { x: number };
            labelAnchor: string;
          }[];
          leadTrajectory: string;
          leadCurrent: { x: number };
        };
      }
    ).fallbackScene();

    expect(scene.trajectories).toHaveLength(3);
    expect(scene.leadTrajectory).toContain('10');
    expect(scene.leadCurrent.x).toBeGreaterThan(0);
    for (const trajectory of scene.trajectories) {
      expect(trajectory.callout.x).toBeLessThan(trajectory.current.x);
      expect(trajectory.labelAnchor).toBe('end');
    }
  });
});
