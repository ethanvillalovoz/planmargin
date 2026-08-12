import {
  afterNextRender,
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  effect,
  inject,
  viewChild,
} from '@angular/core';
import type * as THREE from 'three';
import { DebuggerStore } from '../debugger.store';
import { Point2d, TrajectoryKind } from '../debugger.types';

const COLORS: Record<TrajectoryKind, number> = {
  tested: 0xff7900,
  reference: 0x17b9d6,
  recorded: 0x858d93,
};

@Component({
  selector: 'app-scene-viewport',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div #viewport class="viewport" aria-label="Synthetic trajectory scene"></div>
    <div class="scene-label">
      <strong>Scene</strong>
      <span>{{ store.selectedHypothesis().label }}</span>
    </div>
    <div class="orientation" aria-hidden="true"><span>N</span><i></i></div>
    <div class="legend" aria-label="Trajectory legend">
      <span><i class="tested"></i>Tested</span>
      <span><i class="reference"></i>Reference</span>
      <span><i class="recorded"></i>Recorded</span>
    </div>
    <div class="scale" aria-hidden="true"><i></i><span>10 m</span></div>
  `,
  styles: `
    :host {
      position: relative;
      display: block;
      min-width: 0;
      min-height: 280px;
      overflow: hidden;
      background: var(--app-bg);
    }
    .viewport {
      position: absolute;
      inset: 0;
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
      color: var(--primary);
      font-size: 0.78rem;
    }
    .scene-label span {
      color: var(--secondary);
      font-size: 0.64rem;
    }
    .orientation {
      position: absolute;
      top: 0.85rem;
      right: 1rem;
      display: grid;
      justify-items: center;
      color: var(--secondary);
      font-size: 0.58rem;
    }
    .orientation i {
      width: 1px;
      height: 24px;
      margin-top: 2px;
      background: var(--secondary);
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
      color: var(--secondary);
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
      color: var(--secondary);
      font-size: 0.58rem;
    }
    .scale i {
      display: block;
      width: 58px;
      height: 5px;
      margin-bottom: 0.25rem;
      border-right: 1px solid var(--secondary);
      border-bottom: 1px solid var(--secondary);
      border-left: 1px solid var(--secondary);
    }
    @media (max-width: 760px) {
      :host {
        min-height: 440px;
      }
      .legend {
        right: 0.75rem;
        bottom: 0.75rem;
        gap: 0.55rem;
      }
    }
  `,
})
export class SceneViewport {
  protected readonly store = inject(DebuggerStore);
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
      const THREE = await import('three');
      if (this.destroyRef.destroyed) return;
      this.three = THREE;
      this.scene = new THREE.Scene();
      this.camera = new THREE.OrthographicCamera(-42, 42, 28, -28, 0.1, 100);
      this.camera.position.z = 20;
      this.scene.background = new THREE.Color(0x080d11);
      const host = this.viewport().nativeElement;
      this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
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
    const aspect = clientWidth / Math.max(1, clientHeight);
    const vertical = 32;
    camera.left = -vertical * aspect;
    camera.right = vertical * aspect;
    camera.top = vertical;
    camera.bottom = -vertical;
    camera.updateProjectionMatrix();
    this.renderScene();
  }

  private renderScene(): void {
    const renderer = this.renderer;
    const scene = this.scene;
    const camera = this.camera;
    if (renderer === undefined || scene === undefined || camera === undefined) return;
    this.clearScene();
    this.drawGrid();
    const run = this.store.run();
    run.roadCenterlines.forEach((line) => this.drawLine(line, 0x35434c, 0));
    this.drawConflictRegion(run.conflictRegion);
    const hypothesis = this.store.selectedHypothesis();
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

  private drawGrid(): void {
    const THREE = this.three;
    const scene = this.scene;
    if (THREE === undefined || scene === undefined) return;
    const vertices: number[] = [];
    for (let coordinate = -50; coordinate <= 50; coordinate += 5) {
      vertices.push(
        -60,
        coordinate,
        -2,
        60,
        coordinate,
        -2,
        coordinate,
        -60,
        -2,
        coordinate,
        60,
        -2,
      );
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    scene.add(new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: 0x162129 })));
  }

  private drawLine(points: readonly Point2d[], color: number, opacity: number): void {
    const THREE = this.three;
    const scene = this.scene;
    if (THREE === undefined || scene === undefined) return;
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
      color: 0xff7900,
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
