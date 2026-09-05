import { TestBed } from '@angular/core/testing';
import { DebuggerStore } from '../debugger.store';
import { parseLocalRun } from '../local-evidence.parsers';
import { API_RUN } from '../local-evidence.test-fixtures';
import { SceneViewport } from './scene-viewport';

describe('SceneViewport', () => {
  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('renders source-sized polygons instead of schematic markers when geometry is present', () => {
    const fixture = TestBed.createComponent(SceneViewport);
    const store = TestBed.inject(DebuggerStore);
    const corners = [
      { x: 2, y: 1 },
      { x: -2, y: 1 },
      { x: -2, y: -1 },
      { x: 2, y: -1 },
    ];
    const frames = [corners, corners.map((p) => ({ ...p, x: p.x + 1 }))];
    store.loadRun(
      parseLocalRun({
        ...API_RUN,
        hypothesis: {
          ...API_RUN.hypothesis,
          vehicle_footprints: { tested: frames, reference: frames, recorded: frames, lead: frames },
        },
      }),
    );
    store.seek(0);
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelectorAll('polygon.vehicle-footprint')).toHaveLength(4);
    expect(element.querySelectorAll('rect')).toHaveLength(0);
    expect(element.textContent).toContain('recorded dimensions and headings, to scale');
    const first = element.querySelector('polygon.tested')?.getAttribute('points');
    store.seek(1);
    fixture.detectChanges();
    expect(element.querySelector('polygon.tested')?.getAttribute('points')).not.toBe(first);
    // The API_RUN trace runs along +x, so this also tests world-to-SVG y inversion.
    expect(first).toBe('2,-1 -2,-1 -2,1 2,1');
  });

  it('advances actual trajectory markers and preserves a world-space ten-metre scale', () => {
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
    store.seek(0);
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    const firstMarkerX = element.querySelector('rect.tested')?.getAttribute('x');
    store.seek(1);
    fixture.detectChanges();
    const scene = (
      fixture.componentInstance as unknown as {
        fallbackScene(): {
          trajectories: readonly {
            current: { x: number };
          }[];
          leadTrajectory: string;
          leadCurrent: { x: number };
        };
      }
    ).fallbackScene();

    expect(scene.trajectories).toHaveLength(3);
    expect(scene.leadTrajectory).toContain('10');
    expect(scene.leadCurrent.x).toBeGreaterThan(0);
    expect(scene.trajectories.every((trajectory) => trajectory.current.x === 100)).toBe(true);
    expect(element.querySelector('rect.tested')?.getAttribute('x')).not.toBe(firstMarkerX);
    expect(element.querySelector('polyline.tested')?.getAttribute('points')).toBe('0,0 100,0');
    const scale = element.querySelector('.metric-scale line');
    expect(Number(scale?.getAttribute('x2')) - Number(scale?.getAttribute('x1'))).toBe(10);
    expect(element.querySelector('canvas')).toBeNull();
    expect(element.textContent).toContain('Markers are schematic');
  });
});
