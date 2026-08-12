import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { DebuggerStore } from '../debugger.store';
import { MetricSample } from '../debugger.types';

interface ChartDefinition {
  readonly title: string;
  readonly unit: string;
  readonly min: number;
  readonly max: number;
  readonly value: (sample: MetricSample) => number | null;
}

@Component({
  selector: 'app-metric-timeline',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="scrubber-row">
      <span>{{ store.timeSeconds().toFixed(1) }} s</span>
      <input
        aria-label="Timeline position"
        type="range"
        min="0"
        [max]="store.sampleCount() - 1"
        [value]="store.timestepIndex()"
        (input)="seek($event)"
      />
      <span>{{ duration().toFixed(1) }} s</span>
    </div>
    <div class="charts">
      @for (chart of charts; track chart.title) {
        <figure>
          <figcaption>
            <span>{{ chart.title }}</span>
            <strong>{{ displayValue(chart) }}</strong>
          </figcaption>
          <svg
            viewBox="0 0 1000 104"
            preserveAspectRatio="none"
            role="img"
            [attr.aria-label]="chart.title + ' plot'"
          >
            <path class="grid" d="M0 18H1000 M0 52H1000 M0 86H1000"></path>
            <path class="threshold" d="M0 86H1000"></path>
            @if (store.run().synthetic) {
              <path class="series recorded" [attr.d]="plot(chart, 0.78)"></path>
              <path class="series reference" [attr.d]="plot(chart, 0.3)"></path>
            }
            <path class="series tested" [attr.d]="plot(chart, 0)"></path>
            <line class="cursor" [attr.x1]="cursorX()" y1="0" [attr.x2]="cursorX()" y2="104"></line>
          </svg>
        </figure>
      }
    </div>
  `,
  styles: `
    :host {
      display: block;
      min-height: 0;
      padding: 0.65rem 1rem 0.8rem;
      border-top: 1px solid var(--divider);
      background: var(--rail);
    }
    .scrubber-row {
      display: grid;
      grid-template-columns: 38px 1fr 38px;
      align-items: center;
      gap: 0.65rem;
      color: var(--secondary);
      font-size: 0.62rem;
      font-variant-numeric: tabular-nums;
    }
    input {
      width: 100%;
      accent-color: var(--tested);
    }
    .charts {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.3rem;
      margin-top: 0.55rem;
    }
    figure {
      min-width: 0;
      margin: 0;
    }
    figcaption {
      display: flex;
      justify-content: space-between;
      margin-bottom: 0.2rem;
      color: var(--secondary);
      font-size: 0.64rem;
    }
    figcaption strong {
      color: var(--primary);
      font-weight: 500;
      font-variant-numeric: tabular-nums;
    }
    svg {
      width: 100%;
      height: 96px;
      overflow: visible;
    }
    path,
    polyline,
    line {
      vector-effect: non-scaling-stroke;
    }
    .grid {
      fill: none;
      stroke: var(--grid);
      stroke-width: 1;
    }
    .threshold {
      fill: none;
      stroke: var(--failure);
      stroke-width: 1;
      stroke-dasharray: 4 5;
      opacity: 0.6;
    }
    .series {
      fill: none;
      stroke-width: 1.5;
    }
    .tested {
      stroke: var(--tested);
    }
    .reference {
      stroke: var(--reference);
    }
    .recorded {
      stroke: var(--recorded);
      stroke-dasharray: 4 5;
    }
    .cursor {
      stroke: var(--primary);
      stroke-width: 1;
      opacity: 0.65;
    }
    @media (max-width: 760px) {
      :host {
        padding: 1rem;
        border-top: 0;
      }
      .charts {
        grid-template-columns: 1fr;
        gap: 1.2rem;
      }
      svg {
        height: 126px;
      }
    }
  `,
})
export class MetricTimeline {
  protected readonly store = inject(DebuggerStore);
  protected readonly charts: readonly ChartDefinition[] = [
    {
      title: 'Signed separation',
      unit: 'm',
      min: -2,
      max: 10,
      value: (sample) => sample.signedSeparationMeters,
    },
    {
      title: 'Longitudinal TTC',
      unit: 's',
      min: 0,
      max: 7,
      value: (sample) => sample.longitudinalTtcSeconds,
    },
  ];
  protected readonly cursorX = computed(
    () => (this.store.timestepIndex() / Math.max(1, this.store.sampleCount() - 1)) * 1000,
  );
  protected readonly duration = computed(
    () => this.store.selectedHypothesis().metrics.at(-1)?.timeSeconds ?? 0,
  );

  protected displayValue(chart: ChartDefinition): string {
    const value = chart.value(this.store.metricSample());
    return value === null ? 'Not closing' : `${value.toFixed(2)} ${chart.unit}`;
  }

  protected plot(chart: ChartDefinition, offset: number): string {
    const samples = this.store.selectedHypothesis().metrics;
    let drawing = false;
    return samples
      .map((sample, index) => {
        const value = chart.value(sample);
        if (value === null) {
          drawing = false;
          return '';
        }
        const x = (index / Math.max(1, samples.length - 1)) * 1000;
        const normalized = Math.max(
          0,
          Math.min(1, (value + offset - chart.min) / (chart.max - chart.min)),
        );
        const command = drawing ? 'L' : 'M';
        drawing = true;
        return `${command}${x.toFixed(1)} ${(98 - normalized * 88).toFixed(1)}`;
      })
      .filter((command) => command.length > 0)
      .join(' ');
  }

  protected seek(event: Event): void {
    this.store.seek(Number((event.target as HTMLInputElement).value));
  }
}
