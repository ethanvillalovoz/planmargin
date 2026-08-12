import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { DebuggerStore } from '../debugger.store';

@Component({
  selector: 'app-run-rail',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="rail-section" aria-labelledby="run-heading">
      <p class="eyebrow" id="run-heading">RUN</p>
      <strong>{{ store.run().runId }}</strong>
      <span>{{ store.run().scenarioLabel }}</span>
      <span>local_fixture</span>
      <span class="demo-flag">Demo fixture</span>
    </section>
    <section class="rail-section proposals" aria-labelledby="proposal-heading">
      <p class="eyebrow" id="proposal-heading">PROPOSALS</p>
      @for (hypothesis of store.run().hypotheses; track hypothesis.id) {
        <button
          type="button"
          [class.active]="store.selectedHypothesisId() === hypothesis.id"
          [attr.aria-pressed]="store.selectedHypothesisId() === hypothesis.id"
          (click)="store.selectHypothesis(hypothesis.id)"
        >
          <span class="marker"></span>
          {{ hypothesis.label }}
        </button>
      }
    </section>
    <section class="transport" aria-label="Playback controls">
      <div class="transport-buttons">
        <button type="button" aria-label="Previous step" (click)="store.step(-1)">|‹</button>
        <button
          type="button"
          [attr.aria-label]="store.playing() ? 'Pause' : 'Play'"
          (click)="store.togglePlayback()"
        >
          {{ store.playing() ? 'Ⅱ' : '▶' }}
        </button>
        <button type="button" aria-label="Next step" (click)="store.step(1)">›|</button>
      </div>
      <dl>
        <div>
          <dt>Time</dt>
          <dd>{{ store.timeSeconds().toFixed(1) }} s</dd>
        </div>
        <div>
          <dt>Step</dt>
          <dd>{{ store.timestepIndex() }} / {{ store.sampleCount() - 1 }}</dd>
        </div>
      </dl>
      <label>
        Speed
        <select [value]="store.playbackSpeed()" (change)="changeSpeed($event)">
          <option value="0.5">0.5×</option>
          <option value="1">Real-time</option>
          <option value="2">2×</option>
        </select>
      </label>
    </section>
  `,
  styles: `
    :host {
      display: flex;
      min-height: 0;
      flex-direction: column;
      background: var(--rail);
      border-right: 1px solid var(--divider);
    }
    .rail-section {
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
      padding: 1.1rem 1rem;
      border-bottom: 1px solid var(--divider);
      color: var(--secondary);
      font-size: 0.72rem;
    }
    .rail-section strong {
      color: var(--primary);
      font-size: 0.82rem;
    }
    .eyebrow {
      margin: 0 0 0.25rem;
      color: var(--secondary);
      font-size: 0.62rem;
      font-weight: 700;
      letter-spacing: 0.14em;
    }
    .demo-flag {
      width: max-content;
      margin-top: 0.35rem;
      padding: 0.2rem 0.35rem;
      border: 1px solid var(--divider);
      color: var(--reference);
    }
    .proposals {
      gap: 0.2rem;
    }
    .proposals button {
      display: flex;
      align-items: center;
      gap: 0.55rem;
      width: 100%;
      padding: 0.58rem 0.45rem;
      border: 1px solid transparent;
      border-radius: 2px;
      background: transparent;
      color: var(--secondary);
      text-align: left;
      font: inherit;
      font-weight: 600;
    }
    .proposals button:hover,
    .proposals button.active {
      border-color: var(--divider);
      background: #111a20;
      color: var(--primary);
    }
    .marker {
      width: 7px;
      height: 7px;
      border: 1px solid var(--recorded);
      border-radius: 50%;
    }
    .active .marker {
      border-color: var(--tested);
      background: var(--tested);
    }
    .transport {
      margin-top: auto;
      padding: 1rem;
      color: var(--secondary);
      font-size: 0.7rem;
    }
    .transport-buttons {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 0.35rem;
      margin-bottom: 0.8rem;
    }
    .transport-buttons button {
      min-height: 34px;
      border: 1px solid var(--divider);
      border-radius: 2px;
      background: transparent;
      color: var(--primary);
    }
    dl {
      margin: 0 0 0.7rem;
    }
    dl div {
      display: flex;
      justify-content: space-between;
      padding: 0.25rem 0;
    }
    dt {
      color: var(--secondary);
    }
    dd {
      margin: 0;
      color: var(--primary);
      font-variant-numeric: tabular-nums;
    }
    label {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    select {
      border: 1px solid var(--divider);
      border-radius: 2px;
      background: #080d11;
      color: var(--primary);
      padding: 0.3rem;
      font: inherit;
    }
  `,
})
export class RunRail {
  protected readonly store = inject(DebuggerStore);

  protected changeSpeed(event: Event): void {
    const speed = Number((event.target as HTMLSelectElement).value);
    if (speed === 0.5 || speed === 1 || speed === 2) {
      this.store.setPlaybackSpeed(speed);
    }
  }
}
