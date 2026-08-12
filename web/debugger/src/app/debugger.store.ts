import { computed, DestroyRef, inject, Injectable, signal } from '@angular/core';
import { SYNTHETIC_DEBUGGER_RUN } from './debugger.fixture';
import { DebuggerRun, MobileView } from './debugger.types';

@Injectable({ providedIn: 'root' })
export class DebuggerStore {
  private readonly destroyRef = inject(DestroyRef);
  private playbackTimer: ReturnType<typeof setInterval> | undefined;

  readonly run = signal<DebuggerRun>(SYNTHETIC_DEBUGGER_RUN);
  readonly selectedHypothesisId = signal('proposal-02');
  readonly timestepIndex = signal(48);
  readonly playing = signal(false);
  readonly playbackSpeed = signal<0.5 | 1 | 2>(1);
  readonly mobileView = signal<MobileView>('scene');

  readonly selectedHypothesis = computed(() => {
    const hypotheses = this.run().hypotheses;
    return (
      hypotheses.find((candidate) => candidate.id === this.selectedHypothesisId()) ?? hypotheses[0]
    );
  });
  readonly sampleCount = computed(() => this.selectedHypothesis().metrics.length);
  readonly metricSample = computed(() => this.selectedHypothesis().metrics[this.timestepIndex()]);
  readonly timeSeconds = computed(() => this.metricSample().timeSeconds);

  constructor() {
    this.destroyRef.onDestroy(() => this.stop());
  }

  loadRun(run: DebuggerRun): void {
    this.stop();
    this.run.set(run);
    this.selectedHypothesisId.set(run.hypotheses[0].id);
    this.timestepIndex.set(0);
  }

  selectHypothesis(id: string): void {
    if (!this.run().hypotheses.some((hypothesis) => hypothesis.id === id)) {
      throw new Error(`Unknown hypothesis: ${id}`);
    }
    this.selectedHypothesisId.set(id);
  }

  seek(index: number): void {
    const bounded = Math.max(0, Math.min(Math.round(index), this.sampleCount() - 1));
    this.timestepIndex.set(bounded);
  }

  step(delta: number): void {
    this.seek(this.timestepIndex() + delta);
  }

  setPlaybackSpeed(speed: 0.5 | 1 | 2): void {
    this.playbackSpeed.set(speed);
    if (this.playing()) {
      this.stop();
      this.play();
    }
  }

  togglePlayback(): void {
    if (this.playing()) {
      this.stop();
    } else {
      this.play();
    }
  }

  stop(): void {
    if (this.playbackTimer !== undefined) {
      clearInterval(this.playbackTimer);
      this.playbackTimer = undefined;
    }
    this.playing.set(false);
  }

  private play(): void {
    if (this.timestepIndex() >= this.sampleCount() - 1) {
      this.seek(0);
    }
    this.playing.set(true);
    const intervalMilliseconds = Math.max(
      30,
      (this.run().stepSeconds * 1000) / this.playbackSpeed(),
    );
    this.playbackTimer = setInterval(() => {
      if (this.timestepIndex() >= this.sampleCount() - 1) {
        this.stop();
        return;
      }
      this.step(1);
    }, intervalMilliseconds);
  }
}
