import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { DebuggerStore } from '../debugger.store';
import { Point2d, TrajectoryKind } from '../debugger.types';

const TRAJECTORY_KINDS: readonly TrajectoryKind[] = ['recorded', 'reference', 'tested'];

interface FallbackScene {
  readonly viewBox: string;
  readonly roadCenterlines: readonly string[];
  readonly conflictRegion: string;
  readonly trajectories: readonly {
    readonly kind: TrajectoryKind;
    readonly points: string;
    readonly current: Point2d;
  }[];
  readonly leadTrajectory: string;
  readonly leadOriginalTrajectory: string;
  readonly leadCurrent: Point2d;
  readonly markerRadius: number;
  readonly scaleX: number;
  readonly scaleY: number;
}

@Component({
  selector: 'app-scene-viewport',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg
      class="fallback"
      [attr.viewBox]="fallbackScene().viewBox"
      role="img"
      aria-label="Real local trajectory scene"
      preserveAspectRatio="xMidYMid meet"
    >
      <g>
        @for (road of fallbackScene().roadCenterlines; track $index) {
          <polyline class="road" [attr.points]="road" />
        }
        @if (fallbackScene().conflictRegion) {
          <polygon class="conflict" [attr.points]="fallbackScene().conflictRegion" />
        }
        @for (trajectory of fallbackScene().trajectories; track trajectory.kind) {
          <polyline [attr.class]="trajectory.kind" [attr.points]="trajectory.points" />
          <rect
            [attr.class]="trajectory.kind"
            [attr.x]="trajectory.current.x - fallbackScene().markerRadius * 1.8"
            [attr.y]="-trajectory.current.y - fallbackScene().markerRadius"
            [attr.width]="fallbackScene().markerRadius * 3.6"
            [attr.height]="fallbackScene().markerRadius * 2"
            [attr.rx]="fallbackScene().markerRadius * 0.35"
          />
        }
        <polyline class="lead-original" [attr.points]="fallbackScene().leadOriginalTrajectory" />
        <polyline class="lead" [attr.points]="fallbackScene().leadTrajectory" />
        <rect
          class="lead"
          [attr.x]="fallbackScene().leadCurrent.x - fallbackScene().markerRadius * 1.8"
          [attr.y]="-fallbackScene().leadCurrent.y - fallbackScene().markerRadius"
          [attr.width]="fallbackScene().markerRadius * 3.6"
          [attr.height]="fallbackScene().markerRadius * 2"
          [attr.rx]="fallbackScene().markerRadius * 0.35"
        />
      </g>
      <g class="metric-scale" aria-hidden="true">
        <line
          [attr.x1]="fallbackScene().scaleX"
          [attr.x2]="fallbackScene().scaleX + 10"
          [attr.y1]="fallbackScene().scaleY"
          [attr.y2]="fallbackScene().scaleY"
        />
        <text [attr.x]="fallbackScene().scaleX" [attr.y]="fallbackScene().scaleY - 0.5">10 m</text>
      </g>
    </svg>
    <div class="scene-label">
      <strong>Scene</strong>
      <span>{{ store.selectedHypothesis().label }}</span>
    </div>
    <div class="orientation" aria-hidden="true"><span>Ego aligned</span><i></i></div>
    <div class="legend" aria-label="Trajectory legend">
      <span><i class="tested"></i>Tested</span>
      <span><i class="reference"></i>Reference</span>
      <span><i class="recorded"></i>Original tested</span>
      <span><i class="lead"></i>Mutated lead</span>
    </div>
    <div class="planning-guide">
      <strong>Planner rollout · {{ store.timeSeconds().toFixed(1) }} s</strong>
      <span>Green, yellow, and gray compare ego planners. Pink is the mutated lead vehicle.</span>
      <span>Markers are schematic; clearance uses recorded vehicle geometry.</span>
    </div>
  `,
  styles: `
    :host {
      position: absolute;
      inset: 0;
      display: block;
      min-width: 0;
      min-height: 0;
      overflow: hidden;
      --divider: #2a3239;
      --tested: #76d786;
      --reference: #e7dd55;
      --recorded: #a2a5a8;
      background: #080d11;
    }
    .fallback {
      position: absolute;
      top: 0;
      right: 0;
      bottom: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: #080d11;
    }
    .fallback :is(polyline, polygon, rect) {
      vector-effect: non-scaling-stroke;
    }
    .metric-scale line {
      stroke: #aab9c4;
      stroke-width: 1;
      vector-effect: non-scaling-stroke;
    }
    .metric-scale text {
      fill: #aab9c4;
      font-size: 0.9px;
    }
    .fallback polyline {
      fill: none;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .fallback .road {
      stroke: #35434c;
      stroke-width: 1;
    }
    .fallback .conflict {
      fill: rgb(255 121 0 / 10%);
      stroke: var(--tested);
      stroke-width: 1;
      stroke-dasharray: 4 4;
    }
    .fallback rect.tested {
      fill: var(--tested);
    }
    .fallback .tested {
      stroke: var(--tested);
      stroke-width: 2;
    }
    .fallback rect.reference {
      fill: var(--reference);
    }
    .fallback .reference {
      stroke: var(--reference);
      stroke-width: 2;
    }
    .fallback rect.recorded {
      fill: var(--recorded);
    }
    .fallback .recorded {
      stroke: var(--recorded);
      stroke-width: 1.5;
      stroke-dasharray: 4 4;
    }
    .fallback rect.lead {
      fill: #f09bb4;
    }
    .fallback .lead {
      stroke: #f09bb4;
      stroke-width: 2;
    }
    .fallback .lead-original {
      fill: none;
      stroke: #f09bb488;
      stroke-width: 1;
      stroke-dasharray: 2 5;
    }
    .scene-label {
      position: absolute;
      top: 5rem;
      left: 24px;
      display: flex;
      align-items: baseline;
      gap: 0.75rem;
      pointer-events: none;
    }
    .scene-label strong {
      color: #f4f8fa;
      font-size: 0.78rem;
    }
    .scene-label span {
      color: #aab9c4;
      font-size: 0.64rem;
    }
    .orientation {
      position: absolute;
      top: 5rem;
      right: 1rem;
      display: grid;
      justify-items: center;
      color: #aab9c4;
      font-size: 0.58rem;
    }
    .orientation i {
      width: 1px;
      height: 24px;
      margin-top: 2px;
      background: #aab9c4;
    }
    .legend {
      position: absolute;
      right: 1rem;
      bottom: 0.8rem;
      display: flex;
      gap: 0.9rem;
      padding: 0.4rem 0.55rem;
      border: 1px solid var(--divider);
      background: #080d11dd;
      color: #b8c5ce;
      font-size: 0.6rem;
    }
    .legend span {
      display: flex;
      align-items: center;
      gap: 0.3rem;
    }
    .legend i {
      width: 18px;
      height: 2px;
    }
    .legend .tested {
      background: var(--tested);
    }
    .legend .reference {
      background: var(--reference);
    }
    .legend .recorded {
      height: 1px;
      border-top: 1px dashed var(--recorded);
    }
    .legend .lead {
      background: #f09bb4;
    }
    .planning-guide {
      position: absolute;
      left: 50%;
      bottom: 0.8rem;
      display: grid;
      max-width: 390px;
      gap: 0.15rem;
      padding: 0.5rem 0.65rem;
      transform: translateX(-50%);
      border: 1px solid var(--divider);
      background: #080d11e8;
      color: #dce5e8;
      text-align: center;
      pointer-events: none;
    }
    .planning-guide strong {
      font-size: 0.66rem;
    }
    .planning-guide span {
      color: #91a2ad;
      font-size: 0.56rem;
    }
    @media (max-width: 760px) {
      .fallback {
        left: 0;
        width: 100%;
      }
      .scene-label {
        left: 1rem;
      }
      .legend {
        right: 0.65rem;
        bottom: 4.6rem;
        gap: 0.55rem;
      }
      .planning-guide {
        right: 0.65rem;
        bottom: 0.65rem;
        left: auto;
        width: min(330px, calc(100% - 1.3rem));
        transform: none;
        text-align: right;
      }
    }
    @media (max-width: 560px) {
      .scene-label,
      .orientation {
        top: 12.9rem;
      }
    }
  `,
})
export class SceneViewport {
  protected readonly store = inject(DebuggerStore);
  protected readonly fallbackScene = computed((): FallbackScene => {
    const run = this.store.run();
    const hypothesis = this.store.selectedHypothesis();
    const index = this.store.timestepIndex();
    const anchor = hypothesis.trajectories.tested[0];
    const destination = hypothesis.trajectories.tested.at(-1) ?? anchor;
    const rotation = -Math.atan2(destination.y - anchor.y, destination.x - anchor.x);
    const transform = (point: Point2d): Point2d => {
      const x = point.x - anchor.x;
      const y = point.y - anchor.y;
      return {
        x: x * Math.cos(rotation) - y * Math.sin(rotation),
        y: x * Math.sin(rotation) + y * Math.cos(rotation),
      };
    };
    const roadCenterlines = run.roadCenterlines.map((line) => line.map(transform));
    const trajectories = {
      tested: hypothesis.trajectories.tested.map(transform),
      reference: hypothesis.trajectories.reference.map(transform),
      recorded: hypothesis.trajectories.recorded.map(transform),
    };
    const leadOriginal = run.mutationTarget.original.map(transform);
    const leadTrajectory = run.mutationTarget.counterfactual.map(transform);
    const conflictRegion = run.conflictRegion.map(transform);
    const allPoints = [
      ...trajectories.tested,
      ...trajectories.reference,
      ...trajectories.recorded,
      ...leadOriginal,
      ...leadTrajectory,
      ...conflictRegion,
    ];
    const xs = allPoints.map((point) => point.x);
    const ys = allPoints.map((point) => point.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const width = Math.max(10, maxX - minX);
    const height = Math.max(10, maxY - minY);
    const padding = Math.max(3, width * 0.08, height * 0.08);
    const viewportAspect = 16 / 9;
    const currentTested = trajectories.tested[index];
    const currentLead = leadTrajectory[index];
    const viewWidth = Math.min(width + padding * 2, Math.max(72, width * 0.58));
    const viewHeight = Math.max(34, viewWidth / viewportAspect);
    const interactionCenterX = (currentTested.x + currentLead.x) / 2;
    const interactionCenterY = (currentTested.y + currentLead.y) / 2;
    const centerX = Math.min(maxX - viewWidth * 0.32, interactionCenterX + viewWidth * 0.08);
    const centerY = interactionCenterY;
    const points = (line: readonly Point2d[]): string =>
      line.map((point) => `${point.x},${-point.y}`).join(' ');
    const markerRadius = Math.max(width, height) * 0.0065;
    return {
      viewBox: `${centerX - viewWidth / 2} ${-(centerY + viewHeight / 2)} ${viewWidth} ${viewHeight}`,
      roadCenterlines: roadCenterlines.map(points),
      conflictRegion: conflictRegion.length >= 3 ? points(conflictRegion) : '',
      trajectories: TRAJECTORY_KINDS.map((kind) => {
        const current = trajectories[kind][index];
        return {
          kind,
          points: points(trajectories[kind]),
          current,
        };
      }),
      leadTrajectory: points(leadTrajectory),
      leadOriginalTrajectory: points(leadOriginal),
      leadCurrent: currentLead,
      markerRadius,
      scaleX: centerX - viewWidth / 2 + 2,
      scaleY: -centerY + viewHeight / 2 - 2,
    };
  });
}
