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
import {
  AssistantAnswer,
  AssistantQueryId,
  AssistantQuestion,
  AssistantStatus,
} from '../product-evidence.types';
import { SimulatorStore } from '../simulator.store';

export function classifyAssistantQuestion(value: string): AssistantQueryId | undefined {
  const question = value.trim().toLowerCase();
  if (!question) return undefined;
  if (/\b(tensorrt|fp16|fp32|inference|latency|throughput|t4)\b/.test(question)) {
    return 'inference_qualification';
  }
  if (/\b(trajectory model|predictor|ade|fde|constant velocity)\b/.test(question)) {
    return 'model_performance';
  }
  if (/\b(exact replay|reconstruction|3dgs|sensor scene|provenance)\b/.test(question)) {
    return 'workbench_provenance';
  }
  if (/\b(method|bayes|bayesian|random|hypervolume)\b/.test(question)) {
    return 'method_comparison';
  }
  if (/\b(hypothesis|hypotheses|h1|h2|h3)\b/.test(question)) {
    return 'hypothesis_decisions';
  }
  if (/\b(beam|pipeline|dataflow|partition|parquet|duckdb)\b/.test(question)) {
    return 'beam_pipeline';
  }
  if (/\b(limit|limitation|claim|safe|safety|production|held-out|generalize)\b/.test(question)) {
    return 'claim_boundary';
  }
  if (/\b(campaign|result|finding|cost|rollout|development|experiment)\b/.test(question)) {
    return 'campaign_overview';
  }
  return undefined;
}

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
                <span></span><span></span><span></span
                >{{
                  status()?.gemini_configured
                    ? 'Gemini is reading public evidence · up to 18 s'
                    : 'Reading sealed evidence'
                }}
              </div>
            } @else if (answer(); as response) {
              @if (usedFallback()) {
                <p class="fallback-note">
                  Gemini was unavailable, so this answer uses the verified deterministic explainer.
                </p>
              }
              <p>{{ response.explanation.summary }}</p>
              <p>{{ response.explanation.interpretation }}</p>
              <section class="verified-facts" aria-label="Verified facts used in this answer">
                <strong>Verified facts</strong>
                <dl>
                  @for (fact of response.tool_result.facts; track fact.fact_id) {
                    <div>
                      <dt>{{ fact.statement }}</dt>
                      <dd>
                        {{ fact.value === null ? 'not available' : fact.value
                        }}{{ fact.unit ? ' ' + fact.unit : '' }}
                      </dd>
                    </div>
                  }
                </dl>
              </section>
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
            @for (question of questions(); track question.query_id) {
              <button type="button" (click)="ask(question.query_id)">
                <ng-icon name="phosphorChartLine" size="15" />{{ question.question }}
              </button>
            }
          </div>
        }
      </div>

      <form (submit)="submit($event)">
        @if (notice()) {
          <p class="notice" role="status">{{ notice() }}</p>
        }
        @if (error()) {
          <p class="error" role="alert">{{ error() }}</p>
        }
        <input
          #question
          type="text"
          name="question"
          autocomplete="off"
          placeholder="Ask about campaign evidence…"
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
    .answer .fallback-note {
      margin: 0 0 0.7rem;
      padding: 0.55rem 0.6rem;
      border: 1px solid rgb(240 163 59 / 32%);
      border-radius: 5px;
      background: rgb(240 163 59 / 8%);
      color: #eac17f;
      font-size: 0.58rem;
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
    .verified-facts {
      margin-top: 0.8rem;
      padding-top: 0.7rem;
      border-top: 1px solid rgb(132 155 168 / 13%);
    }
    .verified-facts > strong {
      color: #9dafb8;
      font-size: 0.58rem;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .verified-facts dl {
      display: grid;
      gap: 0.45rem;
      margin: 0.55rem 0 0;
    }
    .verified-facts div {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: baseline;
      gap: 0.75rem;
    }
    .verified-facts dt {
      color: #9dafb8;
      font-size: 0.58rem;
      line-height: 1.4;
    }
    .verified-facts dd {
      margin: 0;
      color: #eef4f5;
      font-size: 0.64rem;
      font-weight: 700;
      text-align: right;
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
    form :is(.notice, .error) {
      grid-column: 1 / -1;
      margin: 0 0 0.25rem;
      padding: 0.55rem 0.65rem;
      border-radius: 6px;
      background: rgb(255 255 255 / 4%);
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
      color: #ff806c;
      font-size: 0.61rem;
    }
    .notice {
      color: #91a7b2;
      font-size: 0.61rem;
      line-height: 1.45;
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
  protected readonly questions = signal<readonly AssistantQuestion[]>([]);
  protected readonly answer = signal<AssistantAnswer | undefined>(undefined);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | undefined>(undefined);
  protected readonly notice = signal<string | undefined>(undefined);
  protected readonly usedFallback = computed(
    () =>
      this.status()?.gemini_configured === true &&
      this.answer()?.provider.id === 'offline_deterministic',
  );

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
        this.questions.set([]);
        this.answer.set(undefined);
      }
    });
  }

  private async loadCatalog(): Promise<void> {
    try {
      const catalog = await this.local.assistantCatalog();
      this.status.set(catalog.status);
      this.questions.set(catalog.questions);
      this.error.set(undefined);
    } catch (error: unknown) {
      this.error.set(this.message(error));
    }
  }

  protected async ask(queryId: AssistantQueryId): Promise<void> {
    if (!this.local.connected() || this.loading()) return;
    this.loading.set(true);
    this.error.set(undefined);
    this.notice.set(undefined);
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
    const value = input.value.trim();
    if (!value) return;
    const query = classifyAssistantQuestion(value);
    if (query === undefined) {
      this.notice.set(
        /\b(path|planning|replay|scenario|case)\b/i.test(value)
          ? 'Only trajectory packages that pass the replay-link verification can open. Close analysis and use Review candidate records to see availability.'
          : 'I could not route that question safely. Choose one of the verified evidence questions above.',
      );
      return;
    }
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
