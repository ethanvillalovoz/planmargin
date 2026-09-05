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
import type { SplatMesh } from '@sparkjsdev/spark';
import type * as THREE from 'three';
import type { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { LocalEvidenceService } from '../local-evidence.service';
import {
  CameraAnnotationBundle,
  CameraBoxAnnotation,
  SensorAssetName,
  SensorSceneSummary,
  SensorTrajectoryOverlay,
} from '../product-evidence.types';
import { SimulatorStore } from '../simulator.store';

@Component({
  selector: 'app-sensor-viewport',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="sensor-viewport" aria-label="Waymo Open Dataset sensor scene">
      <div #surface class="surface">
        @if (!local.connected()) {
          <div class="connection-state">
            <span class="connection-orbit" aria-hidden="true"></span>
            <strong>Connect the real local scene</strong>
            <p>
              Load 199 FRONT camera frames, the 1.18M-Gaussian SHARP reconstruction, same-frame
              LiDAR, and sealed counterfactual evidence.
            </p>
            <button type="button" (click)="connectRequested.emit()">Connect local evidence</button>
          </div>
        } @else {
          @if (simulator.sensorMode() === 'camera') {
            @if (frameUrl()) {
              <img
                [src]="frameUrl()"
                alt="Waymo Open Dataset FRONT camera frame"
                (load)="handleFrameLoad()"
              />
            }
          } @else {
            <div
              #splatViewport
              class="splat-viewport"
              role="img"
              [attr.aria-label]="splatLabel()"
            ></div>
          }
          <canvas
            #overlay
            class="overlay"
            aria-hidden="true"
            [attr.data-frame]="displayedFrame()"
            [attr.data-box-signature]="boxSignature()"
          ></canvas>

          @if (frameLoading() || splatLoading()) {
            <div class="loading-state" role="status">
              <span></span>
              <strong>{{
                simulator.sensorMode() === 'camera'
                  ? 'Loading recorded frame'
                  : 'Decoding local sensor field'
              }}</strong>
              @if (simulator.sensorMode() === 'reconstruction') {
                <small>1,179,648 real SHARP Gaussians · local only</small>
              }
            </div>
          }
          @if (error()) {
            <div class="error-state" role="alert">
              <strong>Scene unavailable</strong><span>{{ error() }}</span>
              <button type="button" (click)="retry()">Retry</button>
            </div>
          }

          <div class="source-badge">
            <span></span>
            @if (simulator.sensorMode() === 'camera') {
              Recorded · FRONT · {{ paddedFrame() }}
            } @else if (simulator.sensorMode() === 'reconstruction') {
              Reconstructed ·
              {{ compactCount(summary()?.reconstruction?.primitive_count) }} Gaussians
            } @else {
              Same-frame LiDAR · {{ compactCount(summary()?.lidar?.primitive_count) }} returns
            }
          </div>

          @if (simulator.sensorMode() !== 'camera' && splatReady()) {
            <div class="orbit-help">Spatial asset · drag to orbit · scroll to zoom</div>
            @if (simulator.sensorMode() === 'reconstruction') {
              <div class="reconstruction-scenes" aria-label="Reconstructed source frame">
                <button
                  type="button"
                  [class.active]="reconstructionAsset() === 'reconstruction'"
                  (click)="setReconstructionAsset('reconstruction')"
                >
                  020 · Moving
                </button>
                <button
                  type="button"
                  [class.active]="reconstructionAsset() === 'reconstruction_context'"
                  (click)="setReconstructionAsset('reconstruction_context')"
                >
                  060 · Approach
                </button>
                <button
                  type="button"
                  [class.active]="reconstructionAsset() === 'reconstruction_reference'"
                  (click)="setReconstructionAsset('reconstruction_reference')"
                >
                  099 · Stopped
                </button>
              </div>
              <div class="reconstruction-views" aria-label="Reconstruction viewpoint">
                <button
                  type="button"
                  [class.active]="reconstructionView() === 'path'"
                  (click)="setReconstructionView('path')"
                >
                  Path
                </button>
                <button
                  type="button"
                  [class.active]="reconstructionView() === 'source'"
                  (click)="setReconstructionView('source')"
                >
                  Source view
                </button>
                <button
                  type="button"
                  [class.active]="reconstructionView() === 'left'"
                  (click)="setReconstructionView('left')"
                >
                  Left
                </button>
                <button
                  type="button"
                  [class.active]="reconstructionView() === 'right'"
                  (click)="setReconstructionView('right')"
                >
                  Right
                </button>
              </div>
              <div class="spatial-details">
                <div class="reconstruction-explainer">
                  <strong>{{ reconstructionViewLabel() }}</strong>
                  <span>{{ reconstructionViewDescription() }}</span>
                </div>
                @if (reconstructionAsset() === 'reconstruction' && trajectory()) {
                  <div class="trajectory-evidence">
                    <strong>Calibrated 3 s ego paths</strong>
                    <span class="recorded"><i></i>Recorded WOD pose</span>
                    <span class="predicted"><i></i>JAX prediction</span>
                    <span class="baseline"><i></i>Constant velocity</span>
                    <small>
                      JAX {{ trajectory()!.metrics.jax_ade_m.toFixed(2) }} m ADE ·
                      {{ trajectory()!.metrics.jax_fde_m.toFixed(2) }} m FDE
                    </small>
                  </div>
                }
              </div>
            } @else {
              <button type="button" class="reset-view" (click)="resetCamera()">Reset view</button>
            }
          }

          @if (simulator.sensorMode() === 'camera') {
            <div class="overlay-provenance">
              {{ visibleBoxes().length }} native tracked boxes · WOD camera labels
            </div>
          }
        }
      </div>
    </section>
  `,
  styles: `
    :host {
      position: absolute;
      inset: 0;
      display: block;
      min-width: 0;
      min-height: 0;
    }
    .sensor-viewport,
    .surface {
      position: absolute;
      inset: 0;
      overflow: hidden;
      background: #071018;
    }
    img {
      position: absolute;
      inset: 0;
      display: block;
      width: 100%;
      height: 100%;
      object-fit: cover;
      object-position: center;
    }
    .splat-viewport {
      position: absolute;
      inset: 0;
    }
    .splat-viewport canvas {
      display: block;
      width: 100%;
      height: 100%;
    }
    .overlay {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
    }
    .connection-state,
    .loading-state,
    .error-state {
      position: absolute;
      z-index: 6;
      inset: 0;
      display: grid;
      align-content: center;
      justify-items: center;
      gap: 0.65rem;
      padding: 2rem;
      background: #071018;
      color: #f2f7f8;
      text-align: center;
    }
    .connection-state strong {
      font-size: 1.05rem;
      letter-spacing: -0.025em;
    }
    .connection-state p {
      max-width: 460px;
      margin: 0;
      color: #8fa0ab;
      font-size: 0.76rem;
      line-height: 1.6;
    }
    .connection-state button,
    .error-state button {
      min-height: 38px;
      padding: 0 0.9rem;
      border: 1px solid #35c5d3;
      border-radius: 8px;
      background: #35c5d3;
      color: #041115;
      font: inherit;
      font-size: 0.72rem;
      font-weight: 750;
    }
    .connection-orbit {
      width: 48px;
      height: 48px;
      border: 1px solid #2c8f9a;
      border-radius: 50%;
      box-shadow: inset 0 0 0 12px #0d2830;
    }
    .loading-state {
      background: rgb(7 16 24 / 88%);
      backdrop-filter: blur(6px);
    }
    .loading-state > span {
      width: 28px;
      height: 28px;
      border: 2px solid #25404d;
      border-top-color: #35c5d3;
      border-radius: 50%;
      animation: spin 0.75s linear infinite;
    }
    .loading-state strong {
      font-size: 0.76rem;
    }
    .loading-state small {
      color: #8fa0ab;
      font-size: 0.64rem;
    }
    .error-state {
      background: rgb(7 16 24 / 94%);
    }
    .error-state strong {
      color: #ff735f;
    }
    .error-state span {
      color: #aab7bf;
      font-size: 0.7rem;
    }
    .source-badge {
      position: absolute;
      z-index: 4;
      top: 1rem;
      left: 1rem;
      display: flex;
      align-items: center;
      gap: 0.45rem;
      min-height: 32px;
      padding: 0 0.7rem;
      border: 1px solid rgb(129 159 174 / 32%);
      border-radius: 8px;
      background: rgb(4 12 18 / 82%);
      color: #e5edef;
      backdrop-filter: blur(12px);
      font-size: 0.66rem;
      font-weight: 650;
    }
    .source-badge span {
      width: 7px;
      height: 7px;
      border: 1px solid #55d6e2;
      border-radius: 50%;
      box-shadow: 0 0 0 3px rgb(53 197 211 / 12%);
    }
    .orbit-help {
      position: absolute;
      z-index: 4;
      right: 1rem;
      bottom: 1rem;
      color: #91a2ad;
      font-size: 0.62rem;
    }
    .reset-view {
      position: absolute;
      z-index: 4;
      top: 4.65rem;
      right: 1rem;
      min-height: 31px;
      padding: 0 0.65rem;
      border: 1px solid rgb(129 159 174 / 34%);
      border-radius: 7px;
      background: rgb(4 12 18 / 78%);
      color: #e5edef;
      font: inherit;
      font-size: 0.64rem;
    }
    .reconstruction-views {
      position: absolute;
      z-index: 4;
      top: 8.3rem;
      right: 1rem;
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      padding: 3px;
      border: 1px solid rgb(129 159 174 / 34%);
      border-radius: 8px;
      background: rgb(4 12 18 / 84%);
      backdrop-filter: blur(10px);
    }
    .reconstruction-explainer {
      position: absolute;
      z-index: 4;
      right: 1rem;
      bottom: 2.8rem;
      display: grid;
      max-width: 280px;
      gap: 0.15rem;
      padding: 0.55rem 0.65rem;
      border: 1px solid rgb(129 159 174 / 28%);
      border-radius: 8px;
      background: rgb(4 12 18 / 82%);
      backdrop-filter: blur(10px);
    }
    .spatial-details {
      display: contents;
    }
    .reconstruction-explainer strong {
      color: #e5edef;
      font-size: 0.65rem;
    }
    .reconstruction-explainer span {
      color: #91a2ad;
      font-size: 0.57rem;
      line-height: 1.4;
    }
    .reconstruction-scenes {
      position: absolute;
      z-index: 4;
      top: 4.65rem;
      right: 1rem;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      width: min(330px, calc(100% - 2rem));
      padding: 3px;
      border: 1px solid rgb(129 159 174 / 34%);
      border-radius: 8px;
      background: rgb(4 12 18 / 84%);
      backdrop-filter: blur(10px);
    }
    .reconstruction-scenes button,
    .reconstruction-views button {
      min-height: 28px;
      padding: 0 0.65rem;
      border: 0;
      border-radius: 5px;
      background: transparent;
      color: #91a2ad;
      font: inherit;
      font-size: 0.62rem;
    }
    .reconstruction-scenes button.active,
    .reconstruction-views button.active {
      background: #123039;
      color: #55d6e2;
    }
    .trajectory-evidence {
      position: absolute;
      z-index: 4;
      left: 1rem;
      bottom: 1rem;
      display: grid;
      grid-template-columns: repeat(3, auto);
      gap: 0.35rem 0.7rem;
      padding: 0.6rem 0.7rem;
      border: 1px solid rgb(129 159 174 / 28%);
      border-radius: 8px;
      background: rgb(4 12 18 / 86%);
      backdrop-filter: blur(10px);
    }
    .trajectory-evidence strong,
    .trajectory-evidence small {
      grid-column: 1 / -1;
    }
    .trajectory-evidence strong {
      color: #e5edef;
      font-size: 0.65rem;
    }
    .trajectory-evidence span {
      display: flex;
      align-items: center;
      gap: 0.3rem;
      color: #a6b5bd;
      font-size: 0.56rem;
    }
    .trajectory-evidence i {
      width: 14px;
      height: 3px;
      border-radius: 2px;
      background: #56d98a;
    }
    .trajectory-evidence .predicted i {
      background: #55d6e2;
    }
    .trajectory-evidence .baseline i {
      background: #f0a33b;
    }
    .trajectory-evidence small {
      color: #788b96;
      font-size: 0.54rem;
    }
    .tracked-box {
      position: absolute;
      z-index: 3;
      border: 1px solid rgb(79 211 223 / 78%);
      box-shadow: inset 0 0 0 1px rgb(79 211 223 / 10%);
      pointer-events: none;
    }
    .tracked-box.pedestrian {
      border-color: rgb(84 214 138 / 78%);
    }
    .tracked-box.cyclist {
      border-color: rgb(255 184 92 / 82%);
    }
    .overlay-provenance {
      position: absolute;
      z-index: 4;
      bottom: 1rem;
      left: 1rem;
      padding: 0.35rem 0.5rem;
      border: 1px solid rgb(129 159 174 / 24%);
      border-radius: 6px;
      background: rgb(4 12 18 / 74%);
      color: #91a2ad;
      font-size: 0.56rem;
    }
    @keyframes spin {
      to {
        transform: rotate(360deg);
      }
    }
    @media (max-width: 860px) {
      .source-badge {
        top: 0.65rem;
        left: 0.65rem;
      }
      .reset-view,
      .reconstruction-scenes {
        top: 4rem;
        right: 0.65rem;
      }
      .reconstruction-scenes {
        width: min(330px, calc(100% - 1.3rem));
      }
      .reconstruction-views {
        top: 7.65rem;
        right: 0.65rem;
      }
      .reconstruction-explainer {
        right: 0.65rem;
        bottom: 2.4rem;
      }
      .overlay-provenance {
        display: none;
      }
    }
    @media (max-width: 560px) {
      .reset-view,
      .reconstruction-scenes {
        top: 6.5rem;
      }
      .reconstruction-views {
        top: 9.2rem;
      }
      .reconstruction-scenes,
      .reconstruction-views {
        left: 0.65rem;
        right: 0.65rem;
        width: auto;
      }
      .spatial-details {
        position: absolute;
        z-index: 4;
        right: 0.65rem;
        bottom: 0.65rem;
        left: 0.65rem;
        display: grid;
        gap: 0.45rem;
        pointer-events: none;
      }
      .spatial-details .reconstruction-explainer,
      .spatial-details .trajectory-evidence {
        position: static;
        max-width: none;
      }
      .trajectory-evidence {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .orbit-help {
        display: none;
      }
    }
  `,
})
export class SensorViewport {
  protected readonly local = inject(LocalEvidenceService);
  protected readonly simulator = inject(SimulatorStore);
  private readonly destroyRef = inject(DestroyRef);
  readonly connectRequested = output<void>();
  protected readonly summary = signal<SensorSceneSummary | undefined>(undefined);
  private readonly annotations = signal<CameraAnnotationBundle | undefined>(undefined);
  protected readonly trajectory = signal<SensorTrajectoryOverlay | undefined>(undefined);
  protected readonly frameUrl = signal<string | undefined>(undefined);
  protected readonly displayedFrame = signal<number | undefined>(undefined);
  protected readonly frameLoading = signal(false);
  protected readonly splatLoading = signal(false);
  protected readonly splatReady = signal(false);
  protected readonly reconstructionView = signal<'path' | 'source' | 'left' | 'right'>('source');
  protected readonly reconstructionAsset = signal<
    'reconstruction' | 'reconstruction_context' | 'reconstruction_reference'
  >('reconstruction');
  protected readonly error = signal<string | undefined>(undefined);
  protected readonly visibleBoxes = signal<readonly CameraBoxAnnotation[]>([]);
  private readonly surface = viewChild.required<ElementRef<HTMLDivElement>>('surface');
  private readonly overlay = viewChild<ElementRef<HTMLCanvasElement>>('overlay');
  private readonly splatViewport = viewChild<ElementRef<HTMLDivElement>>('splatViewport');
  private resizeObserver: ResizeObserver | undefined;
  private renderer: THREE.WebGLRenderer | undefined;
  private camera: THREE.PerspectiveCamera | undefined;
  private controls: OrbitControls | undefined;
  private splat: SplatMesh | undefined;
  private scene: THREE.Scene | undefined;
  private readonly sceneResources: Array<{ dispose(): void }> = [];
  private center: THREE.Vector3 | undefined;
  private distance = 10;
  private frameRequest = 0;
  private frameAbort: AbortController | undefined;
  private requestedFrame: number | undefined;
  private pendingFrame: number | undefined;
  private currentFrame: number | undefined;
  private assetRequest = 0;
  private requestedAsset: SensorAssetName | undefined;
  private currentAsset: SensorAssetName | undefined;
  private initialized = false;
  private sceneInitialization: Promise<void> | undefined;
  private assetBytes = new Map<SensorAssetName, ArrayBuffer>();

  constructor() {
    afterNextRender(() => {
      this.initialized = true;
      const host = this.surface().nativeElement;
      this.resizeObserver = new ResizeObserver(() => {
        this.resizeSplat();
        this.drawOverlay();
      });
      this.resizeObserver.observe(host);
      // The component is destroyed while Planning is active and recreated when
      // Camera/3DGS/LiDAR is selected. Signals may not change after that fresh
      // mount, so the effect below is not guaranteed to rerun. Kick the current
      // connected mode explicitly after view children exist.
      if (this.local.connected()) {
        void this.ensureSceneInitialized().then(() => this.loadCurrentView());
      }
    });
    effect(() => {
      const connected = this.local.connected();
      const mode = this.simulator.sensorMode();
      const frame = this.simulator.frameIndex();
      this.simulator.layers();
      if (!this.initialized) return;
      if (!connected) {
        this.disposeSplat();
        this.releaseFrame();
        return;
      }
      if (this.summary() === undefined) void this.ensureSceneInitialized();
      if (mode === 'camera') {
        this.disposeSplat();
        void this.loadFrame(frame);
      } else if (mode === 'reconstruction' || mode === 'lidar') {
        void this.loadSplat(mode === 'reconstruction' ? this.reconstructionAsset() : 'lidar');
      } else {
        this.disposeSplat();
      }
      queueMicrotask(() => this.drawOverlay());
    });
    this.destroyRef.onDestroy(() => {
      this.resizeObserver?.disconnect();
      this.disposeSplat();
      this.releaseFrame();
    });
  }

  private ensureSceneInitialized(): Promise<void> {
    if (this.summary() !== undefined) return Promise.resolve();
    if (this.sceneInitialization !== undefined) return this.sceneInitialization;
    this.sceneInitialization = this.initializeScene().finally(() => {
      this.sceneInitialization = undefined;
    });
    return this.sceneInitialization;
  }

  private loadCurrentView(): void {
    if (!this.initialized || !this.local.connected()) return;
    const mode = this.simulator.sensorMode();
    if (mode === 'camera') void this.loadFrame(this.simulator.frameIndex());
    else if (mode === 'reconstruction' || mode === 'lidar') {
      void this.loadSplat(mode === 'reconstruction' ? 'reconstruction' : 'lidar');
    }
  }

  private async initializeScene(): Promise<void> {
    try {
      const [summary, annotations, trajectory] = await Promise.all([
        this.local.sensorScene(),
        this.local.sensorAnnotations(),
        this.local.sensorTrajectory(),
      ]);
      this.summary.set(summary);
      this.annotations.set(annotations);
      this.trajectory.set(trajectory);
      this.simulator.configureScene(
        summary.frame_count,
        summary.frame_rate_hz,
        summary.reconstruction.source_frame_index,
      );
      this.error.set(undefined);
      if (this.displayedFrame() !== undefined) this.updateVisibleBoxes(this.displayedFrame()!);
    } catch (error: unknown) {
      this.error.set(this.message(error));
    }
  }

  private async loadFrame(index: number): Promise<void> {
    if (this.currentFrame === index && this.frameUrl() !== undefined) return;
    if (this.requestedFrame === index) return;
    const request = ++this.frameRequest;
    this.frameAbort?.abort();
    const controller = new AbortController();
    this.frameAbort = controller;
    this.requestedFrame = index;
    // Keep the previously decoded image and its matching boxes visible while
    // the next frame downloads. A full-screen loading state at 10 Hz creates
    // a strobe and makes ordinary playback unusable.
    this.frameLoading.set(this.frameUrl() === undefined);
    this.error.set(undefined);
    try {
      const blob = await this.local.sensorFrame(index, controller.signal);
      if (request !== this.frameRequest || this.destroyRef.destroyed) return;
      const next = URL.createObjectURL(blob);
      const previous = this.frameUrl();
      this.pendingFrame = index;
      this.frameUrl.set(next);
      this.currentFrame = index;
      if (previous !== undefined) URL.revokeObjectURL(previous);
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === 'AbortError') return;
      if (request === this.frameRequest) {
        this.requestedFrame = undefined;
        this.frameLoading.set(false);
        this.error.set(this.message(error));
      }
    } finally {
      if (request === this.frameRequest) this.requestedFrame = undefined;
    }
  }

  protected handleFrameLoad(): void {
    if (this.pendingFrame === undefined) return;
    this.displayedFrame.set(this.pendingFrame);
    this.updateVisibleBoxes(this.pendingFrame);
    this.pendingFrame = undefined;
    this.frameLoading.set(false);
  }

  private async loadSplat(name: SensorAssetName): Promise<void> {
    if (this.currentAsset === name && this.splatReady()) return;
    if (this.requestedAsset === name && this.splatLoading()) return;
    const request = ++this.assetRequest;
    this.requestedAsset = name;
    this.splatLoading.set(true);
    this.splatReady.set(false);
    this.error.set(undefined);
    try {
      let bytes = this.assetBytes.get(name);
      if (bytes === undefined) {
        const bundle = await this.local.sensorAsset(name);
        bytes = bundle.bytes;
        this.summary.set(bundle.summary);
        this.assetBytes.set(name, bytes);
      }
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
      if (request !== this.assetRequest || this.destroyRef.destroyed) return;
      await this.renderSplat(bytes, name);
      if (request !== this.assetRequest || this.destroyRef.destroyed) return;
      this.currentAsset = name;
      this.splatReady.set(true);
    } catch (error: unknown) {
      if (request === this.assetRequest) this.error.set(this.message(error));
    } finally {
      if (request === this.assetRequest) {
        this.requestedAsset = undefined;
        this.splatLoading.set(false);
      }
    }
  }

  private async renderSplat(bytes: ArrayBuffer, name: SensorAssetName): Promise<void> {
    this.disposeSplat(false);
    const host = this.splatViewport()?.nativeElement;
    if (host === undefined) return;
    const THREE = await import('three');
    const [{ OrbitControls }, { SparkRenderer, SplatMesh }] = await Promise.all([
      import('three/examples/jsm/controls/OrbitControls.js'),
      import('@sparkjsdev/spark'),
    ]);
    const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    const isReconstruction = name !== 'lidar';
    renderer.setClearColor(isReconstruction ? 0x071018 : 0x05090f, 1);
    renderer.domElement.setAttribute('aria-hidden', 'true');
    host.replaceChildren(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(isReconstruction ? 0x071018 : 0x05090f);
    const camera = new THREE.PerspectiveCamera(48, 1, 0.01, 1000);
    const spark = new SparkRenderer({ renderer });
    scene.add(spark);
    const splat = new SplatMesh({ fileBytes: bytes, fileName: `${name}.ply` });
    await splat.initialized;
    if (this.destroyRef.destroyed) {
      splat.dispose();
      renderer.dispose();
      return;
    }
    scene.add(splat);
    if (isReconstruction) {
      // SHARP exports OpenCV coordinates: +x right, +y down, +z forward.
      // Three.js cameras look down -z with +y up, so mirror y/z once at the
      // model boundary. The embedded SHARP camera is identity with 1600 px
      // focal length for a 1920 × 1280 image.
      splat.rotation.x = Math.PI;
      splat.updateMatrixWorld(true);
    }
    const bounds = splat.getBoundingBox(true);
    const center = bounds.getCenter(new THREE.Vector3());
    const size = bounds.getSize(new THREE.Vector3());
    const distance = Math.max(1.5, size.length() * 0.58);
    const reconstructionTarget = new THREE.Vector3(0, 0, -Math.max(1, Math.abs(center.z)));
    if (name === 'reconstruction') {
      camera.position.set(0, 0, 0);
      camera.up.set(0, 1, 0);
      camera.lookAt(0, 0, -1);
    } else {
      camera.up.set(0, 0, 1);
      camera.position
        .copy(center)
        .add(new THREE.Vector3(distance * 0.72, -distance, distance * 0.45));
      camera.lookAt(center);
    }
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.copy(isReconstruction ? reconstructionTarget : center);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.update();
    if (name === 'lidar') {
      const grid = new THREE.GridHelper(110, 22, 0x1e6874, 0x102c38);
      grid.rotation.x = Math.PI / 2;
      grid.position.z = bounds.min.z - 0.25;
      scene.add(grid);
      this.trackSceneObject(grid);
    }
    if (name === 'reconstruction') {
      const pathGrid = new THREE.GridHelper(12, 24, 0x2d808a, 0x173640);
      pathGrid.position.set(0, -2.11, -3);
      scene.add(pathGrid);
      this.trackSceneObject(pathGrid);
      this.addTrajectoryOverlay(scene, THREE);
    }
    this.renderer = renderer;
    this.camera = camera;
    this.controls = controls;
    this.splat = splat;
    this.scene = scene;
    this.center = isReconstruction ? reconstructionTarget : center;
    this.distance = distance;
    if (isReconstruction) this.applyReconstructionView(camera, controls, reconstructionTarget);
    this.resizeSplat();
    renderer.setAnimationLoop(() => {
      controls.update();
      renderer.render(scene, camera);
    });
  }

  protected resetCamera(): void {
    if (this.camera === undefined || this.controls === undefined || this.center === undefined)
      return;
    const mode = this.simulator.sensorMode();
    if (mode === 'reconstruction') {
      this.camera.position.set(0, 0, 0);
      this.camera.up.set(0, 1, 0);
      this.camera.lookAt(0, 0, -1);
      this.controls.target.set(0, 0, this.center.z);
    } else {
      this.camera.position
        .copy(this.center)
        .add({ x: this.distance * 0.72, y: -this.distance, z: this.distance * 0.45 });
      this.camera.lookAt(this.center);
      this.controls.target.copy(this.center);
    }
    this.controls.update();
  }

  protected setReconstructionView(view: 'path' | 'source' | 'left' | 'right'): void {
    this.reconstructionView.set(view);
    if (this.camera === undefined || this.controls === undefined || this.center === undefined)
      return;
    this.applyReconstructionView(this.camera, this.controls, this.center);
  }

  protected setReconstructionAsset(
    asset: 'reconstruction' | 'reconstruction_context' | 'reconstruction_reference',
  ): void {
    if (asset === this.reconstructionAsset()) return;
    this.reconstructionAsset.set(asset);
    this.reconstructionView.set('source');
    const source =
      asset === 'reconstruction'
        ? this.summary()?.reconstruction
        : asset === 'reconstruction_context'
          ? this.summary()?.reconstruction_context
          : this.summary()?.reconstruction_reference;
    if (source !== undefined) this.simulator.setSpatialSourceFrame(source.source_frame_index);
    void this.loadSplat(asset);
  }

  private addTrajectoryOverlay(scene: THREE.Scene, THREE: typeof import('three')): void {
    const overlay = this.trajectory();
    if (overlay === undefined) return;
    const paths: Array<{
      points: readonly { x: number; y: number; z: number }[];
      color: number;
      radius: number;
    }> = [
      { points: overlay.paths.constant_velocity, color: 0xf0a33b, radius: 0.025 },
      { points: overlay.paths.jax_prediction, color: 0x55d6e2, radius: 0.04 },
      { points: overlay.paths.recorded, color: 0x56d98a, radius: 0.055 },
    ];
    for (const path of paths) {
      const points = path.points
        .filter((point) => point.z > 0.25)
        .map((point) => new THREE.Vector3(point.x, -point.y + 0.14, -point.z));
      if (points.length < 2) continue;
      const curve = new THREE.CatmullRomCurve3(points);
      const geometry = new THREE.TubeGeometry(
        curve,
        Math.max(16, points.length * 2),
        path.radius,
        7,
        false,
      );
      const material = new THREE.MeshBasicMaterial({ color: path.color });
      const tube = new THREE.Mesh(geometry, material);
      scene.add(tube);
      this.trackSceneObject(tube);
      const endpoint = new THREE.Mesh(
        new THREE.SphereGeometry(0.09, 12, 8),
        new THREE.MeshBasicMaterial({ color: path.color }),
      );
      endpoint.position.copy(points.at(-1)!);
      scene.add(endpoint);
      this.trackSceneObject(endpoint);
    }
  }

  private trackSceneObject(object: {
    geometry: { dispose(): void };
    material: { dispose(): void } | { dispose(): void }[];
  }): void {
    this.sceneResources.push(object.geometry);
    this.sceneResources.push(
      ...(Array.isArray(object.material) ? object.material : [object.material]),
    );
  }

  private applyReconstructionView(
    camera: THREE.PerspectiveCamera,
    controls: OrbitControls,
    target: THREE.Vector3,
  ): void {
    camera.up.set(0, 1, 0);
    const view = this.reconstructionView();
    if (view === 'path') {
      camera.position.set(0, 0.8, 0.5);
      controls.target.set(0, -1.7, -5);
    } else if (view === 'source') {
      camera.position.set(0, 0, 0);
      controls.target.set(0, 0, target.z);
    } else {
      // Stay near the source-camera frustum. SHARP reconstructs a real 3D
      // field from one image, but large out-of-frustum moves expose areas the
      // source never observed and create misleading holes.
      const lateralOffset = Math.max(1.5, Math.min(2.8, this.distance * 0.075));
      camera.position.set(view === 'left' ? -lateralOffset : lateralOffset, -0.35, 0.35);
      controls.target.set(0, -0.15, Math.max(target.z, -15));
    }
    camera.lookAt(controls.target);
    controls.update();
  }

  protected reconstructionViewLabel(): string {
    return {
      path: 'Trajectory inspection view',
      source: 'Source camera match',
      left: 'Left novel viewpoint',
      right: 'Right novel viewpoint',
    }[this.reconstructionView()];
  }

  protected reconstructionViewDescription(): string {
    if (this.reconstructionView() === 'path') {
      return 'Camera pitched toward the calibrated 3 s paths on the reconstructed road';
    }
    return this.reconstructionView() === 'source'
      ? `Expected to resemble Camera at frame ${this.simulator.sourceFrameIndex().toString().padStart(3, '0')}`
      : 'A conservative camera move rendered from the same 1.18M reconstructed Gaussians';
  }

  protected retry(): void {
    this.error.set(undefined);
    void this.ensureSceneInitialized().then(() => this.loadCurrentView());
  }

  private resizeSplat(): void {
    const host = this.splatViewport()?.nativeElement;
    if (host === undefined || this.renderer === undefined || this.camera === undefined) return;
    this.renderer.setSize(Math.max(1, host.clientWidth), Math.max(1, host.clientHeight), false);
    this.camera.aspect = Math.max(1, host.clientWidth) / Math.max(1, host.clientHeight);
    if (
      this.currentAsset === 'reconstruction' ||
      this.currentAsset === 'reconstruction_context' ||
      this.currentAsset === 'reconstruction_reference' ||
      this.simulator.sensorMode() === 'reconstruction'
    ) {
      const sourceAspect = 1920 / 1280;
      const sourceVerticalFov = 2 * Math.atan(1280 / (2 * 1600));
      const fittedVerticalFov =
        this.camera.aspect >= sourceAspect
          ? 2 * Math.atan((Math.tan(sourceVerticalFov / 2) * sourceAspect) / this.camera.aspect)
          : sourceVerticalFov;
      this.camera.fov = (fittedVerticalFov * 180) / Math.PI;
    }
    this.camera.updateProjectionMatrix();
  }

  private drawOverlay(): void {
    const canvas = this.overlay()?.nativeElement;
    const host = this.surface()?.nativeElement;
    if (canvas === undefined || host === undefined) return;
    const ratio = Math.min(window.devicePixelRatio, 2);
    canvas.width = Math.max(1, Math.round(host.clientWidth * ratio));
    canvas.height = Math.max(1, Math.round(host.clientHeight * ratio));
    const context = canvas.getContext('2d');
    if (context === null) return;
    context.scale(ratio, ratio);
    context.clearRect(0, 0, host.clientWidth, host.clientHeight);
    if (this.simulator.sensorMode() !== 'camera' || !this.local.connected()) return;
    const width = host.clientWidth;
    const height = host.clientHeight;
    const sourceWidth = this.annotations()?.image_width ?? 1920;
    const sourceHeight = this.annotations()?.image_height ?? 1280;
    const scale = Math.max(width / sourceWidth, height / sourceHeight);
    const offsetX = (width - sourceWidth * scale) / 2;
    const offsetY = (height - sourceHeight * scale) / 2;
    context.lineWidth = 1;
    if (!this.simulator.layers().boxes) return;
    for (const box of this.visibleBoxes()) {
      const left = offsetX + (box.center_x - box.width / 2) * scale;
      const top = offsetY + (box.center_y - box.height / 2) * scale;
      const boxWidth = box.width * scale;
      const boxHeight = box.height * scale;
      if (left + boxWidth < 0 || left > width || top + boxHeight < 0 || top > height) continue;
      context.strokeStyle =
        box.category === 'pedestrian'
          ? 'rgba(84, 214, 138, .82)'
          : box.category === 'cyclist'
            ? 'rgba(255, 184, 92, .86)'
            : 'rgba(79, 211, 223, .78)';
      context.strokeRect(left, top, boxWidth, boxHeight);
    }
  }

  private updateVisibleBoxes(frameIndex: number): void {
    const frame = this.annotations()?.frames.find((candidate) => candidate.index === frameIndex);
    const boxes = frame?.boxes ?? [];
    this.visibleBoxes.set(
      boxes.filter((box) => box.width * box.height >= 850 && box.width >= 10 && box.height >= 10),
    );
    if (this.initialized) queueMicrotask(() => this.drawOverlay());
  }

  protected boxSignature(): string {
    if (!this.simulator.layers().boxes) return 'hidden';
    return this.visibleBoxes()
      .map((box) => `${box.track_id}:${box.center_x.toFixed(1)}:${box.center_y.toFixed(1)}`)
      .join('|');
  }

  private disposeSplat(invalidateRequest = true): void {
    if (invalidateRequest) this.assetRequest++;
    this.renderer?.setAnimationLoop(null);
    this.controls?.dispose();
    this.splat?.dispose();
    for (const resource of this.sceneResources.splice(0)) resource.dispose();
    this.renderer?.dispose();
    this.splatViewport()?.nativeElement.replaceChildren();
    this.renderer = undefined;
    this.camera = undefined;
    this.controls = undefined;
    this.splat = undefined;
    this.scene = undefined;
    this.center = undefined;
    this.currentAsset = undefined;
    if (invalidateRequest) this.requestedAsset = undefined;
    this.splatReady.set(false);
  }

  private releaseFrame(): void {
    this.frameRequest++;
    this.frameAbort?.abort();
    this.frameAbort = undefined;
    const current = this.frameUrl();
    if (current !== undefined) URL.revokeObjectURL(current);
    this.frameUrl.set(undefined);
    this.displayedFrame.set(undefined);
    this.visibleBoxes.set([]);
    this.currentFrame = undefined;
    this.requestedFrame = undefined;
    this.pendingFrame = undefined;
  }

  protected paddedFrame(): string {
    return this.simulator.frameIndex().toString().padStart(3, '0');
  }
  protected compactCount(value: number | undefined): string {
    if (value === undefined) return '—';
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
    if (value >= 1_000) return `${Math.round(value / 1_000)}k`;
    return value.toLocaleString();
  }
  protected splatLabel(): string {
    return this.simulator.sensorMode() === 'reconstruction'
      ? 'Interactive Apple SHARP 3D Gaussian reconstruction'
      : 'Interactive same-frame Waymo LiDAR Gaussian field';
  }
  private message(error: unknown): string {
    if (error instanceof TypeError) {
      return 'Local API unavailable. Restart planmargin-serve-evidence, then retry.';
    }
    return error instanceof Error ? error.message : 'Unknown local scene error';
  }
}
