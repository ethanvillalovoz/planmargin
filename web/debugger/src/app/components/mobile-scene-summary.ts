import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { DebuggerStore } from '../debugger.store';

@Component({
  selector: 'app-mobile-scene-summary',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="transport">
      <button type="button" aria-label="Previous step" (click)="store.step(-1)">|‹</button>
      <button
        type="button"
        [attr.aria-label]="store.playing() ? 'Pause' : 'Play'"
        (click)="store.togglePlayback()"
      >
        {{ store.playing() ? 'Ⅱ' : '▶' }}
      </button>
      <button type="button" aria-label="Next step" (click)="store.step(1)">›|</button>
      <span>{{ store.timeSeconds().toFixed(1) }} s</span>
      <span>Real-time</span>
    </div>
    <div class="summary">
      <div>
        <strong>{{ store.selectedHypothesis().label }}</strong>
        <span>Qualifying (synthetic)</span>
      </div>
      <dl>
        <div>
          <dt>Onset</dt>
          <dd>{{ store.selectedHypothesis().onsetSeconds.toFixed(1) }} s</dd>
        </div>
        <div>
          <dt>Speed</dt>
          <dd>{{ store.selectedHypothesis().speedMetersPerSecond.toFixed(1) }} m/s</dd>
        </div>
      </dl>
    </div>
    <figure>
      <figcaption>
        <span>Signed separation</span>
        <strong>{{ store.metricSample().signedSeparationMeters.toFixed(2) }} m</strong>
      </figcaption>
      <svg
        viewBox="0 0 1000 96"
        preserveAspectRatio="none"
        role="img"
        aria-label="Signed separation plot"
      >
        <path class="grid" d="M0 20H1000 M0 52H1000 M0 84H1000"></path>
        <path class="threshold" d="M0 80H1000"></path>
        <polyline [attr.points]="plot()"></polyline>
        <line [attr.x1]="cursorX()" y1="0" [attr.x2]="cursorX()" y2="96"></line>
      </svg>
    </figure>
  `,
  styles: `
    :host {
      display: none;
      background: var(--rail);
    }
    .transport {
      display: grid;
      grid-template-columns: 40px 40px 40px 1fr auto;
      align-items: center;
      gap: 0.4rem;
      padding: 0.7rem 1rem;
      border-top: 1px solid var(--divider);
      border-bottom: 1px solid var(--divider);
      color: var(--secondary);
      font-size: 0.7rem;
    }
    button {
      min-height: 34px;
      border: 1px solid var(--divider);
      border-radius: 2px;
      background: transparent;
      color: var(--primary);
    }
    .transport span:nth-last-child(2) {
      justify-self: end;
      color: var(--primary);
      font-variant-numeric: tabular-nums;
    }
    .summary {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 1rem;
      padding: 0.8rem 1rem;
      border-bottom: 1px solid var(--divider);
    }
    .summary > div {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }
    .summary strong {
      font-size: 0.82rem;
    }
    .summary span {
      color: var(--reference);
      font-size: 0.62rem;
    }
    dl {
      display: flex;
      gap: 1rem;
      margin: 0;
    }
    dl div {
      display: grid;
      gap: 0.2rem;
    }
    dt {
      color: var(--secondary);
      font-size: 0.6rem;
    }
    dd {
      margin: 0;
      font-size: 0.72rem;
      font-variant-numeric: tabular-nums;
    }
    figure {
      margin: 0;
      padding: 0.75rem 1rem 1rem;
    }
    figcaption {
      display: flex;
      justify-content: space-between;
      color: var(--secondary);
      font-size: 0.68rem;
    }
    figcaption strong {
      color: var(--primary);
      font-weight: 500;
      font-variant-numeric: tabular-nums;
    }
    svg {
      width: 100%;
      height: 90px;
      margin-top: 0.3rem;
    }
    path,
    polyline,
    line {
      vector-effect: non-scaling-stroke;
    }
    .grid {
      fill: none;
      stroke: var(--grid);
    }
    .threshold {
      fill: none;
      stroke: var(--failure);
      stroke-dasharray: 4 5;
      opacity: 0.6;
    }
    polyline {
      fill: none;
      stroke: var(--tested);
      stroke-width: 1.5;
    }
    line {
      stroke: var(--primary);
      opacity: 0.65;
    }
    @media (max-width: 760px) {
      :host {
        display: block;
      }
    }
  `,
})
export class MobileSceneSummary {
  protected readonly store = inject(DebuggerStore);
  protected readonly cursorX = computed(
    () => (this.store.timestepIndex() / Math.max(1, this.store.sampleCount() - 1)) * 1000,
  );

  protected plot(): string {
    const samples = this.store.selectedHypothesis().metrics;
    return samples
      .map((sample, index) => {
        const x = (index / Math.max(1, samples.length - 1)) * 1000;
        const normalized = Math.max(0, Math.min(1, (sample.signedSeparationMeters + 2) / 12));
        return `${x.toFixed(1)},${(90 - normalized * 80).toFixed(1)}`;
      })
      .join(' ');
  }
}
