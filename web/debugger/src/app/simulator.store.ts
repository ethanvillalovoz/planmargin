import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { DebuggerStore } from './debugger.store';

export type SensorMode = 'camera' | 'planning' | 'reconstruction' | 'lidar';
export type SceneLayer = 'boxes';
export type StressStatus = 'idle' | 'running' | 'complete';

@Injectable({ providedIn: 'root' })
export class SimulatorStore {
  private readonly debuggerStore = inject(DebuggerStore);
  private readonly destroyRef = inject(DestroyRef);
  private playbackTimer: ReturnType<typeof setInterval> | undefined;
  private stressTimer: ReturnType<typeof setTimeout> | undefined;

  readonly sensorMode = signal<SensorMode>('camera');
  readonly frameIndex = signal(99);
  readonly frameCount = signal(199);
  readonly frameRateHz = signal(10);
  readonly sourceFrameIndex = signal(99);
  private readonly cameraPlaying = signal(false);
  readonly playbackSpeed = signal<0.5 | 1 | 2>(1);
  readonly assistantOpen = signal(false);
  readonly controlsOpen = signal(true);
  readonly stressStatus = signal<StressStatus>('idle');
  readonly layers = signal<Readonly<Record<SceneLayer, boolean>>>(
    {
      boxes: true,
    },
    { equal: (left, right) => JSON.stringify(left) === JSON.stringify(right) },
  );

  readonly playing = computed(() =>
    this.sensorMode() === 'planning'
      ? this.debuggerStore.playing() || this.stressStatus() === 'running'
      : this.cameraPlaying(),
  );
  readonly timelineIndex = computed(() =>
    this.sensorMode() === 'planning' ? this.debuggerStore.timestepIndex() : this.frameIndex(),
  );
  readonly timelineCount = computed(() =>
    this.sensorMode() === 'planning' ? this.debuggerStore.sampleCount() : this.frameCount(),
  );
  readonly temporalPlaybackAvailable = computed(
    () => this.sensorMode() === 'camera' || this.sensorMode() === 'planning',
  );
  readonly temporalControlsEnabled = computed(
    () => this.temporalPlaybackAvailable() && this.stressStatus() !== 'running',
  );

  constructor() {
    this.destroyRef.onDestroy(() => {
      this.stop();
      if (this.stressTimer !== undefined) clearTimeout(this.stressTimer);
    });
  }

  configureScene(frameCount: number, frameRateHz: number, sourceFrameIndex: number): void {
    this.frameCount.set(frameCount);
    this.frameRateHz.set(frameRateHz);
    this.sourceFrameIndex.set(sourceFrameIndex);
    this.applyFrame(sourceFrameIndex);
  }

  setSpatialSourceFrame(sourceFrameIndex: number): void {
    this.sourceFrameIndex.set(sourceFrameIndex);
    this.applyFrame(sourceFrameIndex);
  }

  selectMode(mode: SensorMode): void {
    if (this.stressStatus() === 'running') this.cancelStressReplay();
    this.stop();
    if (mode !== 'planning') this.assistantOpen.set(false);
    if (mode === 'reconstruction' || mode === 'lidar') {
      this.applyFrame(this.sourceFrameIndex());
    }
    this.sensorMode.set(mode);
  }

  toggleLayer(layer: SceneLayer): void {
    this.layers.update((current) => ({ ...current, [layer]: !current[layer] }));
  }

  seekFrame(index: number): void {
    if (!this.temporalControlsEnabled()) return;
    if (this.sensorMode() === 'planning') this.debuggerStore.seek(index);
    else this.applyFrame(index);
  }

  private applyFrame(index: number): void {
    const bounded = Math.max(0, Math.min(Math.round(index), this.frameCount() - 1));
    this.frameIndex.set(bounded);
  }

  step(delta: number): void {
    if (!this.temporalControlsEnabled()) return;
    this.seekFrame(this.timelineIndex() + delta);
  }

  jumpSeconds(seconds: number): void {
    if (!this.temporalControlsEnabled()) return;
    const rate =
      this.sensorMode() === 'planning'
        ? Math.max(1, Math.round(1 / this.debuggerStore.run().stepSeconds))
        : this.frameRateHz();
    this.step(seconds * rate);
  }

  togglePlayback(): void {
    if (!this.temporalControlsEnabled()) return;
    if (this.sensorMode() === 'planning') this.debuggerStore.togglePlayback();
    else if (this.cameraPlaying()) this.stopCamera();
    else this.playCamera();
  }

  setPlaybackSpeed(speed: 0.5 | 1 | 2): void {
    this.playbackSpeed.set(speed);
    this.debuggerStore.setPlaybackSpeed(speed);
    if (this.cameraPlaying()) {
      this.stopCamera();
      this.playCamera();
    }
  }

  runStressTest(): void {
    if (this.stressStatus() === 'running') return;
    if (this.stressTimer !== undefined) clearInterval(this.stressTimer);
    this.stop();
    this.sensorMode.set('planning');
    this.stressStatus.set('running');
    this.assistantOpen.set(false);
    const metrics = this.debuggerStore.selectedHypothesis().metrics;
    const conflictIndex = metrics.reduce(
      (best, sample, index) =>
        sample.signedSeparationMeters < metrics[best].signedSeparationMeters ? index : best,
      0,
    );
    const firstFrame = Math.max(0, conflictIndex - 12);
    const lastFrame = Math.min(metrics.length - 1, conflictIndex + 12);
    this.debuggerStore.seek(firstFrame);
    this.stressTimer = setInterval(
      () => {
        if (this.debuggerStore.timestepIndex() >= lastFrame) {
          this.cancelStressReplay('complete');
          return;
        }
        this.debuggerStore.step(1);
      },
      Math.max(70, this.debuggerStore.run().stepSeconds * 1000),
    );
  }

  showPlanningFrame(index: number): void {
    this.stop();
    this.sensorMode.set('planning');
    this.debuggerStore.seek(index);
  }

  private cancelStressReplay(status: StressStatus = 'idle'): void {
    if (this.stressTimer !== undefined) {
      clearInterval(this.stressTimer);
      this.stressTimer = undefined;
    }
    this.debuggerStore.stop();
    this.stressStatus.set(status);
  }

  private playCamera(): void {
    if (this.frameIndex() >= this.frameCount() - 1) this.seekFrame(0);
    this.cameraPlaying.set(true);
    const interval = Math.max(70, 1000 / (this.frameRateHz() * this.playbackSpeed()));
    this.playbackTimer = setInterval(() => {
      if (this.frameIndex() >= this.frameCount() - 1) {
        this.stopCamera();
        return;
      }
      this.step(1);
    }, interval);
  }

  private stop(): void {
    this.stopCamera();
    this.debuggerStore.stop();
  }

  private stopCamera(): void {
    if (this.playbackTimer !== undefined) {
      clearInterval(this.playbackTimer);
      this.playbackTimer = undefined;
    }
    this.cameraPlaying.set(false);
  }
}
