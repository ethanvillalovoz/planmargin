import {
  afterNextRender,
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  effect,
  ElementRef,
  inject,
  output,
  signal,
  viewChild,
} from '@angular/core';
import type * as THREE from 'three';
import type { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { SplatMesh } from '@sparkjsdev/spark';
import { DebuggerStore } from '../debugger.store';
import { LocalEvidenceService } from '../local-evidence.service';
import { GaussianFieldSummary } from '../product-evidence.types';

@Component({
  selector: 'app-gaussian-field-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="gaussian-shell" aria-labelledby="gaussian-title">
      <header class="page-heading">
        <div>
          <h1 id="gaussian-title">Gaussian Field</h1>
          <p>Inspect the exact-scenario LiDAR field and the frozen gate that stopped it from becoming the default debugger view.</p>
        </div>
        @if (summary(); as result) {
          <span class="decision" [class.go]="result.decision === 'go'">{{ result.decision === 'go' ? 'GO' : 'NO-GO' }} · trajectory coverage</span>
        }
      </header>

      @if (!local.connected()) {
        <div class="connection-state">
          <div class="gaussian-mark" aria-hidden="true">⠿</div>
          <h2>Local field required</h2>
          <p>The 4.86 MiB PLY is private, ignored by Git, and served only through the authenticated loopback API.</p>
          <button type="button" class="primary" (click)="connectRequested.emit()">Connect local evidence</button>
        </div>
      } @else {
        <div class="gaussian-layout">
          <div class="viewer-card">
            <div #viewport class="viewer" aria-label="Interactive 3D Gaussian splat field"></div>
            @if (loading()) {
              <div class="viewer-state" role="status"><div class="loading-ring"></div><strong>Loading 75,000 Gaussians</strong><span>Decoding the authenticated local PLY in your browser.</span></div>
            }
            @if (error()) {
              <div class="viewer-state error" role="alert"><strong>Field unavailable</strong><span>{{ error() }}</span><button type="button" (click)="load()">Retry</button></div>
            }
            @if (ready()) {
              <div class="viewer-tools">
                <button type="button" (click)="resetCamera()">Reset view</button>
                <span>Drag to orbit · scroll to zoom</span>
              </div>
              <div class="viewer-legend"><span><i class="field"></i>LiDAR Gaussians</span><span><i class="trajectory"></i>Debugger trajectory</span></div>
            }
          </div>

          @if (summary(); as result) {
            <aside>
              <section class="gate-card">
                <div class="section-heading"><h2>Integration gate</h2><span>{{ percent(result.trajectory_linkage_fraction) }} / {{ percent(result.trajectory_linkage_gate) }}</span></div>
                <div class="gauge"><i [style.width.%]="result.trajectory_linkage_fraction * 100"></i><b [style.left.%]="result.trajectory_linkage_gate * 100"></b></div>
                <p><strong>Geometry passed.</strong> The 1.1-second sensor field covers too little of the full 8-second debugger trajectory, so this remains an experimental view.</p>
              </section>

              <section class="metrics-grid">
                <article><strong>{{ result.primitive_count.toLocaleString() }}</strong><span>Gaussian primitives</span></article>
                <article><strong>{{ mebibytes(result.field_bytes) }}</strong><span>Binary PLY</span></article>
                <article><strong>{{ result.runtime_seconds.toFixed(2) }} s</strong><span>Fit and score</span></article>
                <article><strong>{{ percent(result.geometry.coverage_within_0_50_m) }}</strong><span>Geometry within 0.50 m</span></article>
              </section>

              <section class="quality">
                <h2>Geometry quality</h2>
                <dl>
                  <div><dt>Median nearest mean</dt><dd>{{ result.geometry.median_nearest_mean_distance_m.toFixed(3) }} m</dd></div>
                  <div><dt>90th percentile</dt><dd>{{ result.geometry.p90_nearest_mean_distance_m.toFixed(3) }} m</dd></div>
                  @for (gate of gateEntries(result); track gate[0]) {
                    <div><dt>{{ gateLabel(gate[0]) }}</dt><dd [class.pass]="gate[1]" [class.fail]="!gate[1]">{{ gate[1] ? 'Pass' : 'Fail' }}</dd></div>
                  }
                </dl>
              </section>

              <div class="boundary"><strong>Research boundary</strong><p>Deterministic LiDAR Gaussian field—not photorealistic 3DGS, learned reconstruction, or planner-safety evidence. Export remains disabled.</p></div>
            </aside>
          }
        </div>
      }
    </section>
  `,
  styles: `
    :host { display: block; min-width: 0; min-height: 0; height: 100%; }
    .gaussian-shell { display: flex; height: 100%; min-height: 0; flex-direction: column; background: var(--surface); }
    .page-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; padding: 1.75rem 2rem 1.4rem; border-bottom: 1px solid var(--divider); }
    h1, h2, p { margin: 0; }
    h1 { font-size: clamp(1.35rem, 2vw, 1.8rem); letter-spacing: -.04em; }
    .page-heading p { max-width: 760px; margin-top: .45rem; color: var(--secondary); font-size: .86rem; line-height: 1.55; }
    .decision { padding: .5rem .7rem; border: 1px solid #ffc2b4; border-radius: 999px; background: #fff2ed; color: #b43b20; font-size: .7rem; font-weight: 800; }
    .decision.go { border-color: #b9dfb0; background: #f2fbef; color: #26721f; }
    .gaussian-layout { display: grid; grid-template-columns: minmax(0, 1fr) 360px; min-height: 0; flex: 1; padding: 1.25rem; gap: 1.25rem; background: var(--surface-subtle); }
    .viewer-card { position: relative; min-height: 520px; overflow: hidden; border: 1px solid var(--divider); border-radius: var(--radius); background: #07131e; box-shadow: var(--shadow-sm); }
    .viewer { position: absolute; inset: 0; }
    .viewer canvas { display: block; width: 100%; height: 100%; }
    .viewer-state { position: absolute; inset: 0; display: grid; align-content: center; justify-items: center; gap: .5rem; padding: 2rem; background: #07131e; color: #fff; text-align: center; }
    .viewer-state span { color: #9fb0bf; font-size: .78rem; }
    .viewer-state.error strong { color: #ff8f79; }
    .viewer-state button, .viewer-tools button { min-height: 34px; padding: 0 .75rem; border: 1px solid #51616f; border-radius: 8px; background: #142533; color: #fff; font: inherit; font-size: .72rem; }
    .loading-ring { width: 32px; height: 32px; border: 3px solid #273c4e; border-top-color: #42c8db; border-radius: 50%; animation: spin .8s linear infinite; }
    .viewer-tools { position: absolute; top: 1rem; right: 1rem; display: flex; align-items: center; gap: .7rem; color: #bac8d3; font-size: .66rem; }
    .viewer-legend { position: absolute; left: 1rem; bottom: 1rem; display: flex; gap: 1rem; padding: .55rem .7rem; border: 1px solid #344958; border-radius: 8px; background: rgb(6 18 28 / 86%); color: #dbe4ea; font-size: .68rem; }
    .viewer-legend span { display: flex; align-items: center; gap: .4rem; }
    .viewer-legend i { display: block; width: 18px; height: 3px; }
    .viewer-legend .field { background: #42c8db; box-shadow: 0 0 8px #42c8db; }
    .viewer-legend .trajectory { background: #ff775c; }
    aside { display: flex; min-height: 0; flex-direction: column; gap: .9rem; overflow: auto; }
    aside > section, .boundary { padding: 1rem; border: 1px solid var(--divider); border-radius: var(--radius-sm); background: #fff; }
    .section-heading { display: flex; align-items: center; justify-content: space-between; }
    aside h2 { font-size: .82rem; }
    .section-heading span { color: #b43b20; font-size: .78rem; font-weight: 800; }
    .gauge { position: relative; height: 9px; margin: 1rem 0 .8rem; overflow: visible; border-radius: 999px; background: #e9eef3; }
    .gauge i { display: block; height: 100%; border-radius: inherit; background: var(--accent-coral); }
    .gauge b { position: absolute; top: -4px; width: 2px; height: 17px; background: #1f2c38; }
    .gate-card p { color: var(--secondary); font-size: .75rem; line-height: 1.55; }
    .gate-card p strong { color: #26721f; }
    .metrics-grid { display: grid; grid-template-columns: 1fr 1fr; padding: 0; overflow: hidden; }
    .metrics-grid article { padding: .9rem; border-right: 1px solid var(--divider-soft); border-bottom: 1px solid var(--divider-soft); }
    .metrics-grid article:nth-child(even) { border-right: 0; }
    .metrics-grid article:nth-last-child(-n+2) { border-bottom: 0; }
    .metrics-grid strong, .metrics-grid span { display: block; }
    .metrics-grid strong { color: #1558d6; font-size: 1.05rem; font-variant-numeric: tabular-nums; }
    .metrics-grid span { margin-top: .2rem; color: var(--secondary); font-size: .65rem; }
    dl { margin: .7rem 0 0; }
    dl div { display: flex; justify-content: space-between; gap: .8rem; padding: .42rem 0; border-bottom: 1px solid var(--divider-soft); font-size: .72rem; }
    dl div:last-child { border-bottom: 0; }
    dt { color: var(--secondary); } dd { margin: 0; font-variant-numeric: tabular-nums; } dd.pass { color: #26721f; } dd.fail { color: #b43b20; font-weight: 800; }
    .boundary { border-left: 4px solid #7b65dc; }
    .boundary strong { color: #5843b5; font-size: .74rem; }
    .boundary p { margin-top: .3rem; color: var(--secondary); font-size: .72rem; line-height: 1.5; }
    .connection-state { display: grid; max-width: 540px; margin: auto; padding: 2rem; justify-items: center; text-align: center; }
    .connection-state h2 { margin-top: .8rem; font-size: 1.25rem; }
    .connection-state p { margin: .55rem 0 1.2rem; color: var(--secondary); line-height: 1.6; }
    .gaussian-mark { display: grid; width: 54px; height: 54px; place-items: center; border-radius: 18px; background: #e8f8fb; color: #14889b; font-size: 1.7rem; }
    button.primary { min-height: 38px; padding: 0 .9rem; border: 1px solid #1769e0; border-radius: 9px; background: #1769e0; color: #fff; font: inherit; font-size: .76rem; font-weight: 700; }
    @keyframes spin { to { transform: rotate(360deg); } }
    @media (max-width: 960px) { .gaussian-layout { grid-template-columns: 1fr; overflow: auto; } .viewer-card { min-height: 520px; } aside { overflow: visible; } }
    @media (max-width: 760px) { .page-heading { padding: 1.2rem; } .gaussian-layout { padding: .75rem; } .viewer-card { min-height: 430px; } .viewer-tools span { display: none; } }
  `,
})
export class GaussianFieldPanel {
  protected readonly local = inject(LocalEvidenceService);
  protected readonly connectRequested = output<void>();
  protected readonly summary = signal<GaussianFieldSummary | undefined>(undefined);
  protected readonly loading = signal(false);
  protected readonly ready = signal(false);
  protected readonly error = signal<string | undefined>(undefined);
  private readonly store = inject(DebuggerStore);
  private readonly destroyRef = inject(DestroyRef);
  private readonly viewport = viewChild.required<ElementRef<HTMLDivElement>>('viewport');
  private renderer: THREE.WebGLRenderer | undefined;
  private camera: THREE.PerspectiveCamera | undefined;
  private controls: OrbitControls | undefined;
  private splat: SplatMesh | undefined;
  private resizeObserver: ResizeObserver | undefined;
  private hostReady = false;

  constructor() {
    afterNextRender(() => {
      this.hostReady = true;
      if (this.local.connected()) void this.load();
    });
    effect(() => {
      if (this.local.connected() && this.hostReady && this.summary() === undefined && !this.loading()) {
        void this.load();
      }
    });
    this.destroyRef.onDestroy(() => this.dispose());
  }

  protected async load(): Promise<void> {
    if (!this.local.connected() || this.loading() || !this.hostReady) return;
    this.loading.set(true);
    this.ready.set(false);
    this.error.set(undefined);
    try {
      const bundle = await this.local.gaussianField();
      this.summary.set(bundle.summary);
      await this.render(bundle.bytes);
      this.ready.set(true);
    } catch (error: unknown) {
      this.error.set(error instanceof Error ? error.message : 'Unknown Gaussian viewer error');
    } finally {
      this.loading.set(false);
    }
  }

  private async render(bytes: ArrayBuffer): Promise<void> {
    this.dispose();
    const THREE = await import('three');
    const [{ OrbitControls }, { SparkRenderer, SplatMesh }] = await Promise.all([
      import('three/examples/jsm/controls/OrbitControls.js'),
      import('@sparkjsdev/spark'),
    ]);
    if (this.destroyRef.destroyed) return;
    const host = this.viewport().nativeElement;
    const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setClearColor(0x07131e, 1);
    renderer.domElement.setAttribute('aria-hidden', 'true');
    host.replaceChildren(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x07131e);
    const camera = new THREE.PerspectiveCamera(50, 1, 0.05, 500);
    camera.up.set(0, 0, 1);
    const spark = new SparkRenderer({ renderer });
    scene.add(spark);
    const splat = new SplatMesh({ fileBytes: bytes, fileName: 'field.ply' });
    await splat.initialized;
    if (this.destroyRef.destroyed) { splat.dispose(); renderer.dispose(); return; }
    scene.add(splat);
    const bounds = splat.getBoundingBox(true);
    const center = bounds.getCenter(new THREE.Vector3());
    const size = bounds.getSize(new THREE.Vector3());
    const distance = Math.max(30, size.length() * 0.72);
    camera.position.copy(center).add(new THREE.Vector3(distance, -distance, distance * 0.65));
    camera.lookAt(center);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.copy(center);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.update();

    const grid = new THREE.GridHelper(100, 20, 0x2f6073, 0x183342);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = bounds.min.z - 0.35;
    scene.add(grid);
    const trajectory = this.store.selectedHypothesis().trajectories.tested;
    const trajectoryGeometry = new THREE.BufferGeometry().setFromPoints(
      trajectory.map((point) => new THREE.Vector3(point.x, point.y, center.z)),
    );
    const trajectoryLine = new THREE.Line(
      trajectoryGeometry,
      new THREE.LineBasicMaterial({ color: 0xff775c, linewidth: 2 }),
    );
    scene.add(trajectoryLine);

    this.renderer = renderer;
    this.camera = camera;
    this.controls = controls;
    this.splat = splat;
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(host);
    this.resize();
    renderer.setAnimationLoop(() => {
      controls.update();
      renderer.render(scene, camera);
    });
  }

  protected resetCamera(): void {
    const bounds = this.splat?.getBoundingBox(true);
    if (bounds === undefined || this.camera === undefined || this.controls === undefined) return;
    const THREERef = this.camera.position.constructor as typeof THREE.Vector3;
    const center = bounds.getCenter(new THREERef());
    const size = bounds.getSize(new THREERef());
    const distance = Math.max(30, size.length() * 0.72);
    this.camera.position.copy(center).add(new THREERef(distance, -distance, distance * 0.65));
    this.controls.target.copy(center);
    this.controls.update();
  }

  private resize(): void {
    const host = this.viewport().nativeElement;
    if (this.renderer === undefined || this.camera === undefined || host.clientWidth === 0 || host.clientHeight === 0) return;
    this.renderer.setSize(host.clientWidth, host.clientHeight, false);
    this.camera.aspect = host.clientWidth / host.clientHeight;
    this.camera.updateProjectionMatrix();
  }

  private dispose(): void {
    this.resizeObserver?.disconnect();
    this.resizeObserver = undefined;
    this.renderer?.setAnimationLoop(null);
    this.controls?.dispose();
    this.splat?.dispose();
    this.renderer?.dispose();
    this.viewport()?.nativeElement.replaceChildren();
    this.renderer = undefined;
    this.camera = undefined;
    this.controls = undefined;
    this.splat = undefined;
  }

  protected percent(value: number): string { return `${(value * 100).toFixed(2)}%`; }
  protected mebibytes(bytes: number): string { return `${(bytes / 1024 ** 2).toFixed(2)} MiB`; }
  protected gateEntries(summary: GaussianFieldSummary): readonly [string, boolean][] { return Object.entries(summary.gates); }
  protected gateLabel(name: string): string { return name.replaceAll('_', ' ').replace(/^./, (value) => value.toUpperCase()); }
}
