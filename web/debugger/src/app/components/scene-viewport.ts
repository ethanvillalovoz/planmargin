import {
  afterNextRender,
  ChangeDetectionStrategy,
  Component,
  computed,
  DestroyRef,
  ElementRef,
  effect,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import type * as THREE from 'three';
import { DebuggerStore } from '../debugger.store';
import { Point2d, TrajectoryKind } from '../debugger.types';

const COLORS: Record<TrajectoryKind, number> = {
  tested: 0xf16347,
  reference: 0x0ba8bd,
  recorded: 0x83919c,
};

interface FallbackScene {
  readonly viewBox: string;
  readonly roadCenterlines: readonly string[];
  readonly conflictRegion: string;
  readonly trajectories: readonly {
    readonly kind: TrajectoryKind;
    readonly points: string;
    readonly current: Point2d;
    readonly callout: Point2d;
  }[];
  readonly markerRadius: number;
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
          <line
            class="marker-callout"
            [attr.x1]="trajectory.current.x + fallbackScene().markerRadius * 1.8"
            [attr.y1]="-trajectory.current.y"
            [attr.x2]="trajectory.callout.x"
            [attr.y2]="trajectory.callout.y"
          />
          <text
            class="marker-label"
            [attr.x]="trajectory.callout.x + fallbackScene().markerRadius * 0.45"
            [attr.y]="trajectory.callout.y + fallbackScene().markerRadius * 0.35"
            [attr.font-size]="fallbackScene().markerRadius * 1.35"
          >
            {{ trajectory.kind }}
          </text>
        }
      </g>
    </svg>
    <div #viewport hidden></div>
    <div class="scene-label">
      <strong>Scene</strong>
      <span>{{ store.selectedHypothesis().label }}</span>
    </div>
    <div class="orientation" aria-hidden="true"><span>Ego aligned</span><i></i></div>
    <div class="legend" aria-label="Trajectory legend">
      <span><i class="tested"></i>Tested</span>
      <span><i class="reference"></i>Reference</span>
      <span><i class="recorded"></i>Recorded</span>
    </div>
    <div class="planning-guide">
      <strong>Planner rollout · {{ store.timeSeconds().toFixed(1) }} s</strong>
      <span>Three planner outcomes for the same ego vehicle—not three traffic actors.</span>
    </div>
    <div class="scale" aria-hidden="true"><i></i><span>10 m</span></div>
  `,
  styles: `
    :host {
      position: absolute;
      inset: 0;
      display: block;
      min-width: 0;
      min-height: 0;
      overflow: hidden;
      background: var(--app-bg);
    }
    .viewport {
      position: absolute;
      inset: 0;
    }
    .fallback {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      background: var(--app-bg);
    }
    .fallback :is(polyline, polygon, rect) {
      vector-effect: non-scaling-stroke;
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
    .fallback .tested {
      fill: var(--tested);
      stroke: var(--tested);
      stroke-width: 2;
    }
    .fallback .reference {
      fill: var(--reference);
      stroke: var(--reference);
      stroke-width: 2;
    }
    .fallback .recorded {
      fill: var(--recorded);
      stroke: var(--recorded);
      stroke-width: 1.5;
      stroke-dasharray: 4 4;
    }
    .fallback .marker-label {
      fill: #dce5e8;
      paint-order: stroke;
      stroke: #080d11;
      stroke-width: 0.35px;
      text-transform: capitalize;
    }
    .fallback .marker-callout {
      stroke: #8496a1;
      stroke-width: 0.65;
      vector-effect: non-scaling-stroke;
    }
    .viewport canvas {
      display: block;
      width: 100%;
      height: 100%;
    }
    .scene-label {
      position: absolute;
      top: 0.85rem;
      left: 1rem;
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
      top: 0.85rem;
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
    .scale {
      position: absolute;
      left: 1rem;
      bottom: 0.8rem;
      color: #aab9c4;
      font-size: 0.58rem;
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
    .scale i {
      display: block;
      width: 58px;
      height: 5px;
      margin-bottom: 0.25rem;
      border-right: 1px solid #aab9c4;
      border-bottom: 1px solid #aab9c4;
      border-left: 1px solid #aab9c4;
    }
    @media (max-width: 760px) {
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
      .scale {
        bottom: 4.6rem;
      }
    }
  `,
})
export class SceneViewport {
  protected readonly store = inject(DebuggerStore);
  protected readonly rendererUnavailable = signal(true);
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
    const conflictRegion = run.conflictRegion.map(transform);
    const allPoints = [
      ...trajectories.tested,
      ...trajectories.reference,
      ...trajectories.recorded,
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
    let viewWidth = width + padding * 2;
    let viewHeight = height + padding * 2;
    if (viewWidth / viewHeight < viewportAspect) viewWidth = viewHeight * viewportAspect;
    else viewHeight = viewWidth / viewportAspect;
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    const points = (line: readonly Point2d[]): string =>
      line.map((point) => `${point.x},${-point.y}`).join(' ');
    const markerRadius = Math.max(width, height) * 0.009;
    const calloutOffsets: Record<TrajectoryKind, number> = {
      tested: -2.8,
      reference: 0,
      recorded: 2.8,
    };
    return {
      viewBox: `${centerX - viewWidth / 2} ${-(centerY + viewHeight / 2)} ${viewWidth} ${viewHeight}`,
      roadCenterlines: roadCenterlines.map(points),
      conflictRegion: conflictRegion.length >= 3 ? points(conflictRegion) : '',
      trajectories: (Object.keys(COLORS) as TrajectoryKind[]).map((kind) => {
        const current = trajectories[kind][index];
        return {
          kind,
          points: points(trajectories[kind]),
          current,
          callout: {
            x: current.x + markerRadius * 4.2,
            y: -current.y + markerRadius * calloutOffsets[kind],
          },
        };
      }),
      markerRadius,
    };
  });
  private readonly destroyRef = inject(DestroyRef);
  private readonly viewport = viewChild.required<ElementRef<HTMLDivElement>>('viewport');
  private renderer: THREE.WebGLRenderer | undefined;
  private scene: THREE.Scene | undefined;
  private camera: THREE.OrthographicCamera | undefined;
  private three: typeof import('three') | undefined;
  private resizeObserver: ResizeObserver | undefined;

  constructor() {
    effect(() => {
      this.store.run();
      this.store.selectedHypothesis();
      this.store.timestepIndex();
      this.renderScene();
    });

    afterNextRender(async () => {
      const canvas = document.createElement('canvas');
      const context = canvas.getContext('webgl2');
      if (context === null) {
        this.rendererUnavailable.set(true);
        return;
      }
      const THREE = await import('three');
      if (this.destroyRef.destroyed) return;
      this.three = THREE;
      this.scene = new THREE.Scene();
      this.camera = new THREE.OrthographicCamera(-42, 42, 28, -28, 0.1, 100);
      this.camera.position.z = 20;
      this.scene.background = new THREE.Color(0x080d11);
      const host = this.viewport().nativeElement;
      this.renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: false,
        canvas,
        context,
      });
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      this.renderer.domElement.setAttribute('aria-hidden', 'true');
      host.append(this.renderer.domElement);
      this.resizeObserver = new ResizeObserver(() => this.resize());
      this.resizeObserver.observe(host);
      this.resize();
      this.destroyRef.onDestroy(() => {
        this.resizeObserver?.disconnect();
        this.clearScene();
        this.renderer?.dispose();
      });
    });
  }

  private resize(): void {
    const renderer = this.renderer;
    const camera = this.camera;
    if (renderer === undefined || camera === undefined) return;
    const { clientWidth, clientHeight } = this.viewport().nativeElement;
    renderer.setSize(Math.max(1, clientWidth), Math.max(1, clientHeight), false);
    this.renderScene();
  }

  private renderScene(): void {
    const renderer = this.renderer;
    const scene = this.scene;
    const camera = this.camera;
    if (renderer === undefined || scene === undefined || camera === undefined) return;
    this.clearScene();
    const run = this.store.run();
    const hypothesis = this.store.selectedHypothesis();
    const allPoints = [
      ...run.roadCenterlines.flat(),
      ...hypothesis.trajectories.tested,
      ...hypothesis.trajectories.reference,
      ...hypothesis.trajectories.recorded,
    ];
    const bounds = this.fitCamera(allPoints);
    this.drawGrid(bounds);
    run.roadCenterlines.forEach((line) => this.drawLine(line, 0x435766, 0));
    if (run.conflictRegion.length >= 3) this.drawConflictRegion(run.conflictRegion);
    (Object.keys(COLORS) as TrajectoryKind[]).forEach((kind) => {
      this.drawLine(hypothesis.trajectories[kind], COLORS[kind], kind === 'recorded' ? 0.25 : 0.55);
      const point = hypothesis.trajectories[kind][this.store.timestepIndex()];
      this.drawVehicle(point, COLORS[kind], kind === 'tested' ? 1 : 0.65);
    });
    renderer.render(scene, camera);
  }

  private clearScene(): void {
    const THREE = this.three;
    const scene = this.scene;
    if (THREE === undefined || scene === undefined) return;
    for (const child of [...scene.children]) {
      child.traverse((object) => {
        if (
          object instanceof THREE.Mesh ||
          object instanceof THREE.LineSegments ||
          object instanceof THREE.Line
        ) {
          object.geometry.dispose();
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          materials.forEach((material) => material.dispose());
        }
      });
      scene.remove(child);
    }
  }

  private fitCamera(points: readonly Point2d[]): {
    readonly minX: number;
    readonly maxX: number;
    readonly minY: number;
    readonly maxY: number;
  } {
    const camera = this.camera;
    if (camera === undefined || points.length === 0) {
      return { minX: -32, maxX: 32, minY: -32, maxY: 32 };
    }
    const xs = points.map((point) => point.x);
    const ys = points.map((point) => point.y);
    const source = {
      minX: Math.min(...xs),
      maxX: Math.max(...xs),
      minY: Math.min(...ys),
      maxY: Math.max(...ys),
    };
    const centerX = (source.minX + source.maxX) / 2;
    const centerY = (source.minY + source.maxY) / 2;
    const { clientWidth, clientHeight } = this.viewport().nativeElement;
    const aspect = clientWidth / Math.max(1, clientHeight);
    const halfHeight = Math.max(
      8,
      (source.maxY - source.minY) * 0.6,
      ((source.maxX - source.minX) * 0.6) / Math.max(0.25, aspect),
    );
    const halfWidth = halfHeight * aspect;
    camera.left = centerX - halfWidth;
    camera.right = centerX + halfWidth;
    camera.top = centerY + halfHeight;
    camera.bottom = centerY - halfHeight;
    camera.position.set(0, 0, 20);
    camera.updateProjectionMatrix();
    return {
      minX: camera.left,
      maxX: camera.right,
      minY: camera.bottom,
      maxY: camera.top,
    };
  }

  private drawGrid(bounds: {
    readonly minX: number;
    readonly maxX: number;
    readonly minY: number;
    readonly maxY: number;
  }): void {
    const THREE = this.three;
    const scene = this.scene;
    if (THREE === undefined || scene === undefined) return;
    const vertices: number[] = [];
    const startX = Math.floor(bounds.minX / 5) * 5;
    const startY = Math.floor(bounds.minY / 5) * 5;
    for (let x = startX; x <= bounds.maxX; x += 5) {
      vertices.push(x, bounds.minY, -2, x, bounds.maxY, -2);
    }
    for (let y = startY; y <= bounds.maxY; y += 5) {
      vertices.push(bounds.minX, y, -2, bounds.maxX, y, -2);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    scene.add(new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: 0x182731 })));
  }

  private drawLine(points: readonly Point2d[], color: number, opacity: number): void {
    const THREE = this.three;
    const scene = this.scene;
    if (THREE === undefined || scene === undefined || points.length < 2) return;
    const geometry = new THREE.BufferGeometry().setFromPoints(
      points.map((point) => new THREE.Vector3(point.x, point.y, 0)),
    );
    const material = new THREE.LineBasicMaterial({
      color,
      transparent: opacity < 1,
      opacity: opacity || 1,
    });
    scene.add(new THREE.Line(geometry, material));
  }

  private drawConflictRegion(points: readonly Point2d[]): void {
    const THREE = this.three;
    const scene = this.scene;
    if (THREE === undefined || scene === undefined) return;
    const shape = new THREE.Shape();
    points.forEach((point, index) =>
      index === 0 ? shape.moveTo(point.x, point.y) : shape.lineTo(point.x, point.y),
    );
    shape.closePath();
    const material = new THREE.MeshBasicMaterial({
      color: 0xf16347,
      transparent: true,
      opacity: 0.08,
      side: THREE.DoubleSide,
    });
    scene.add(new THREE.Mesh(new THREE.ShapeGeometry(shape), material));
  }

  private drawVehicle(point: Point2d, color: number, opacity: number): void {
    const THREE = this.three;
    const scene = this.scene;
    if (THREE === undefined || scene === undefined) return;
    const geometry = new THREE.PlaneGeometry(4.4, 2.1);
    const material = new THREE.MeshBasicMaterial({ color, transparent: opacity < 1, opacity });
    const vehicle = new THREE.Mesh(geometry, material);
    vehicle.position.set(point.x, point.y, 1);
    scene.add(vehicle);
  }
}
