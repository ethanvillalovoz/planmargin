import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { NgIcon, provideIcons } from '@ng-icons/core';
import {
  phosphorChartLine,
  phosphorPaperPlaneTilt,
  phosphorPlayCircle,
  phosphorSparkle,
  phosphorX,
} from '@ng-icons/phosphor-icons/regular';
import { DebuggerStore } from '../debugger.store';
import { LocalEvidenceService } from '../local-evidence.service';
import { AssistantAnswer, AssistantQueryId, AssistantStatus } from '../product-evidence.types';
import { SimulatorStore } from '../simulator.store';

@Component({
  selector: 'app-scenario-assistant',
  imports: [NgIcon],
  providers: [
    provideIcons({
      phosphorChartLine,
      phosphorPaperPlaneTilt,
      phosphorPlayCircle,
      phosphorSparkle,
      phosphorX,
    }),
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <aside class="assistant" aria-labelledby="assistant-title">
      <header>
        <div>
          <ng-icon name="phosphorSparkle" size="17" aria-hidden="true" />
          <div>
            <strong id="assistant-title">{{ title() }}</strong
            ><span>{{ providerLabel() }}</span>
          </div>
        </div>
        <button
          type="button"
          aria-label="Close analysis"
          (click)="simulator.assistantOpen.set(false)"
        >
          <ng-icon name="phosphorX" size="16" />
        </button>
      </header>

      <div class="assistant-body">
        @if (!local.connected()) {
          <div class="assistant-empty">
            <strong>Evidence is disconnected</strong>
            <p>Connect the local API to ground every answer in sealed run data.</p>
          </div>
        } @else {
          <article class="answer">
            @if (loading()) {
              <div class="thinking">
                <span></span><span></span><span></span>Reading sealed evidence
              </div>
            } @else if (answer(); as response) {
              <p>{{ response.explanation.summary }}</p>
              <p>{{ response.explanation.interpretation }}</p>
              <small>{{ response.explanation.limitation }}</small>
            } @else {
              <p>{{ scenarioInsight() }}</p>
              <p>{{ scenarioComparison() }}</p>
              <small
                >Trajectory evidence is privacy-reduced WOMD Motion; the visual sensor scene is a
                separate WOD Perception segment.</small
              >
            }
          </article>

          <div class="assistant-actions">
            <button type="button" (click)="showConflictFrame()">
              <ng-icon name="phosphorPlayCircle" size="15" />Show planning conflict
            </button>
            <button type="button" (click)="ask('method_comparison')">
              <ng-icon name="phosphorChartLine" size="15" />Compare search methods
            </button>
          </div>

          @if (error()) {
            <p class="error" role="alert">{{ error() }}</p>
          }
        }
      </div>

      <form (submit)="submit($event)">
        <input
          #question
          type="text"
          name="question"
          autocomplete="off"
          placeholder="Ask about this evidence…"
          [disabled]="!local.connected() || loading()"
        />
        <button
          type="submit"
          aria-label="Ask evidence assistant"
          [disabled]="!local.connected() || loading()"
        >
          <ng-icon name="phosphorPaperPlaneTilt" size="17" />
        </button>
      </form>
    </aside>
  `,
  styles: `
    :host {
      display: block;
    }
    .assistant {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      width: 100%;
      max-height: min(64vh, 580px);
      overflow: hidden;
      border: 1px solid rgb(132 155 168 / 28%);
      border-radius: 12px;
      background: rgb(5 13 20 / 94%);
      color: #eef4f5;
      box-shadow: 0 18px 50px rgb(0 0 0 / 30%);
      backdrop-filter: blur(18px);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 58px;
      padding: 0 1rem;
      border-bottom: 1px solid rgb(132 155 168 / 18%);
    }
    header > div {
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }
    header strong,
    header span {
      display: block;
    }
    header strong {
      font-size: 0.82rem;
    }
    header span {
      margin-top: 0.12rem;
      color: #78909e;
      font-size: 0.58rem;
    }
    header ng-icon {
      color: #e6edf0;
    }
    header button {
      display: grid;
      width: 30px;
      height: 30px;
      place-items: center;
      border: 0;
      border-radius: 6px;
      background: transparent;
      color: #92a3ad;
    }
    header button:hover {
      background: rgb(255 255 255 / 7%);
      color: #fff;
    }
    .assistant-body {
      min-height: 0;
      padding: 0.8rem;
      overflow: auto;
    }
    .answer {
      padding: 0.85rem;
      border: 1px solid rgb(132 155 168 / 14%);
      border-radius: 9px;
      background: rgb(255 255 255 / 3.5%);
    }
    .answer p {
      margin: 0;
      color: #dce5e8;
      font-size: 0.76rem;
      line-height: 1.55;
    }
    .answer p + p {
      margin-top: 0.65rem;
    }
    .answer small {
      display: block;
      margin-top: 0.8rem;
      padding-top: 0.65rem;
      border-top: 1px solid rgb(132 155 168 / 13%);
      color: #7f929d;
      font-size: 0.6rem;
      line-height: 1.5;
    }
    .assistant-actions {
      display: grid;
      gap: 0.45rem;
      margin-top: 0.65rem;
    }
    .assistant-actions button {
      display: flex;
      align-items: center;
      min-height: 39px;
      gap: 0.55rem;
      padding: 0 0.75rem;
      border: 1px solid rgb(132 155 168 / 25%);
      border-radius: 7px;
      background: transparent;
      color: #dce5e8;
      font: inherit;
      font-size: 0.69rem;
      text-align: left;
    }
    .assistant-actions button:hover {
      border-color: #35c5d3;
      color: #fff;
    }
    form {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 38px;
      gap: 0.4rem;
      padding: 0.75rem;
      border-top: 1px solid rgb(132 155 168 / 18%);
    }
    input {
      min-width: 0;
      min-height: 38px;
      padding: 0 0.7rem;
      border: 1px solid rgb(132 155 168 / 26%);
      border-radius: 7px;
      outline: 0;
      background: rgb(255 255 255 / 3%);
      color: #eef4f5;
      font: inherit;
      font-size: 0.69rem;
    }
    input:focus {
      border-color: #35c5d3;
    }
    form button {
      display: grid;
      place-items: center;
      border: 1px solid rgb(132 155 168 / 26%);
      border-radius: 7px;
      background: rgb(255 255 255 / 3%);
      color: #35c5d3;
    }
    :is(input, button):disabled {
      cursor: not-allowed;
      opacity: 0.48;
    }
    .assistant-empty {
      padding: 1rem;
      text-align: center;
    }
    .assistant-empty strong {
      font-size: 0.72rem;
    }
    .assistant-empty p {
      color: #8496a1;
      font-size: 0.63rem;
      line-height: 1.5;
    }
    .error {
      margin: 0.6rem 0 0;
      color: #ff806c;
      font-size: 0.61rem;
    }
    .thinking {
      display: flex;
      align-items: center;
      gap: 0.3rem;
      color: #93a4ae;
      font-size: 0.63rem;
    }
    .thinking span {
      width: 4px;
      height: 4px;
      border-radius: 50%;
      background: #35c5d3;
      animation: pulse 1s infinite alternate;
    }
    .thinking span:nth-child(2) {
      animation-delay: 0.15s;
    }
    .thinking span:nth-child(3) {
      animation-delay: 0.3s;
      margin-right: 0.2rem;
    }
    @keyframes pulse {
      to {
        opacity: 0.25;
        transform: translateY(-2px);
      }
    }
  `,
})
export class ScenarioAssistant {
  protected readonly local = inject(LocalEvidenceService);
  protected readonly simulator = inject(SimulatorStore);
  private readonly store = inject(DebuggerStore);
  protected readonly status = signal<AssistantStatus | undefined>(undefined);
  protected readonly answer = signal<AssistantAnswer | undefined>(undefined);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | undefined>(undefined);

  protected readonly title = computed(() =>
    this.status()?.gemini_configured ? 'Gemini analysis' : 'Evidence analysis',
  );
  protected readonly providerLabel = computed(() => {
    const status = this.status();
    if (status === undefined)
      return this.local.connected() ? 'Loading provider' : 'Local evidence required';
    return status.gemini_configured
      ? `${status.model ?? 'Gemini'} · public aggregate only`
      : 'Deterministic local provider';
  });
  protected readonly scenarioInsight = computed(() => {
    const hypothesis = this.store.selectedHypothesis();
    const minimum = hypothesis.metrics.reduce((best, value) =>
      value.signedSeparationMeters < best.signedSeparationMeters ? value : best,
    );
    return `${hypothesis.label} reaches ${minimum.signedSeparationMeters.toFixed(2)} m signed separation at ${minimum.timeSeconds.toFixed(1)} s. The tested controller ${hypothesis.controllerOutcome.tested}; the reference controller ${hypothesis.controllerOutcome.reference}.`;
  });
  protected readonly scenarioComparison = computed(() => {
    const hypothesis = this.store.selectedHypothesis();
    const parameters = Object.entries(hypothesis.mutationParameters)
      .filter(([key]) => !key.startsWith('max_') && !key.endsWith('_epsilon_m'))
      .map(([key, value]) => `${key.replaceAll('_', ' ')} ${value}`)
      .slice(0, 4)
      .join(', ');
    return `The sealed ${hypothesis.mutationType.replaceAll('_', ' ')} mutation records ${parameters || 'no numeric parameters'}. Open the planning conflict to inspect its smallest margin.`;
  });

  constructor() {
    effect(() => {
      if (this.local.connected() && this.status() === undefined) void this.loadCatalog();
      if (!this.local.connected()) {
        this.status.set(undefined);
        this.answer.set(undefined);
      }
    });
  }

  private async loadCatalog(): Promise<void> {
    try {
      this.status.set(await this.local.assistantStatus());
      this.error.set(undefined);
    } catch (error: unknown) {
      this.error.set(this.message(error));
    }
  }

  protected async ask(queryId: AssistantQueryId): Promise<void> {
    if (!this.local.connected() || this.loading()) return;
    this.loading.set(true);
    this.error.set(undefined);
    try {
      this.answer.set(await this.local.askAssistant(queryId));
    } catch (error: unknown) {
      this.error.set(this.message(error));
    } finally {
      this.loading.set(false);
    }
  }

  protected submit(event: Event): void {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement;
    const input = form.elements.namedItem('question') as HTMLInputElement;
    const value = input.value.trim().toLowerCase();
    if (!value) return;
    const query: AssistantQueryId =
      value.includes('method') || value.includes('bayes')
        ? 'method_comparison'
        : value.includes('hypoth')
          ? 'hypothesis_decisions'
          : value.includes('beam') || value.includes('pipeline')
            ? 'beam_pipeline'
            : value.includes('limit') || value.includes('claim') || value.includes('safe')
              ? 'claim_boundary'
              : 'campaign_overview';
    input.value = '';
    void this.ask(query);
  }

  protected showConflictFrame(): void {
    const metrics = this.store.selectedHypothesis().metrics;
    const minimumIndex = metrics.reduce(
      (best, value, index) =>
        value.signedSeparationMeters < metrics[best].signedSeparationMeters ? index : best,
      0,
    );
    this.simulator.showPlanningFrame(minimumIndex);
  }

  private message(error: unknown): string {
    return error instanceof Error ? error.message : 'Unknown assistant error';
  }
}
