import {
  ChangeDetectionStrategy,
  afterNextRender,
  Component,
  computed,
  effect,
  inject,
  output,
  signal,
  viewChild,
  ElementRef,
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

interface LocalAssistantReply {
  readonly heading: string;
  readonly body: string;
}

export function classifyAssistantQuestion(value: string): AssistantQueryId | undefined {
  const question = value.trim().toLowerCase();
  if (!question) return undefined;
  if (/\b(test health|pipeline health|release health|healthy|slo|alert|on time)\b/.test(question)) {
    return 'test_health';
  }
  if (
    /\b(behavior coverage|test coverage|fault protection|command dropout|remote assistance|assistance handoff|off[- ]nominal)\b/.test(
      question,
    )
  ) {
    return 'behavior_coverage';
  }
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
  host: { '(keydown.escape)': 'close()' },
  template: `
    <aside class="assistant" aria-labelledby="assistant-title">
      <header>
        <div>
          <ng-icon name="phosphorSparkle" size="17" aria-hidden="true" />
          <div>
            <strong id="assistant-title">PlanMargin assistant</strong
            ><span>{{ providerLabel() }}</span>
          </div>
        </div>
        <button type="button" aria-label="Close analysis" (click)="close()">
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
            } @else if (localReply(); as reply) {
              <div class="local-reply-label"><i></i>Local guide</div>
              <h2>{{ reply.heading }}</h2>
              <p>{{ reply.body }}</p>
              <small>
                Evidence questions use deterministic routing and verified tool results. Gemini only
                synthesizes the returned public aggregate packet.
              </small>
            } @else if (answer(); as response) {
              @if (usedFallback()) {
                <p class="fallback-note">
                  Gemini was unavailable, so this answer uses the verified deterministic explainer.
                </p>
              }
              <p>{{ response.explanation.summary }}</p>
              <p>{{ response.explanation.interpretation }}</p>
              <details class="verified-facts">
                <summary>Show verified facts ({{ response.tool_result.facts.length }})</summary>
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
              </details>
              <small>{{ response.explanation.limitation }}</small>
            } @else {
              <div class="local-reply-label"><i></i>Connected</div>
              <h2>What should we inspect?</h2>
              <p>
                Ask about test health, behavior coverage, held engineering decisions, campaign
                evidence, or model qualification.
              </p>
              <small
                >Campaign answers use verified aggregate records. For a specific change, use
                “Analyze selected proposal” in Investigate.</small
              >
            }
          </article>

          <div class="assistant-actions">
            <span>Suggested investigations</span>
            @for (question of suggestedQuestions(); track question.query_id) {
              <button type="button" (click)="ask(question.query_id)">
                <ng-icon name="phosphorChartLine" size="15" />{{ question.question }}
              </button>
            }
          </div>
          @if (remainingQuestions().length > 0) {
            <details class="more-actions">
              <summary>
                More evidence topics <b>{{ remainingQuestions().length }}</b>
              </summary>
              <div>
                @for (question of remainingQuestions(); track question.query_id) {
                  <button type="button" (click)="ask(question.query_id)">
                    {{ question.question }}
                  </button>
                }
              </div>
            </details>
          }
          @if (store.hasRun()) {
            <button type="button" class="context-action" (click)="showConflictFrame()">
              <ng-icon name="phosphorPlayCircle" size="15" />Jump to smallest margin in the loaded
              replay
            </button>
          }
        }
      </div>

      <form (submit)="submit($event)">
        @if (error()) {
          <p class="error" role="alert">{{ error() }}</p>
        }
        <input
          #question
          type="text"
          name="question"
          aria-label="Ask about campaign evidence…"
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
      height: min(720px, calc(100dvh - 160px));
      overflow: hidden;
      border: 1px solid #d6e1db;
      border-radius: 16px;
      background: #fff;
      color: #172b22;
      box-shadow: 0 12px 40px #12281e20;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 18px;
      border-bottom: 1px solid #e1e9e4;
    }
    header > div {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    header strong,
    header span {
      display: block;
    }
    header strong {
      font-size: 15px;
    }
    header span {
      margin-top: 5px;
      color: #65726c;
      font-size: 10px;
      line-height: 1.4;
    }
    header ng-icon {
      color: #0c846b;
    }
    button,
    input {
      font: inherit;
    }
    button {
      cursor: pointer;
    }
    header button {
      display: grid;
      place-items: center;
      width: 32px;
      height: 32px;
      border: 0;
      border-radius: 50%;
      color: #60716b;
      background: #f0f4f1;
    }
    .assistant-body {
      overflow: auto;
      min-height: 0;
      padding: 20px;
    }
    .answer h2 {
      font-size: 20px;
      line-height: 1.3;
      margin: 10px 0;
      letter-spacing: -0.5px;
    }
    .answer p {
      font-size: 14px;
      line-height: 1.7;
      margin: 0 0 14px;
      color: #43594d;
    }
    .answer small {
      display: block;
      font-size: 11px;
      color: #65766b;
      line-height: 1.6;
    }
    .local-reply-label {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      color: #20724e;
      font-weight: 650;
    }
    .fallback-note,
    .error {
      padding: 12px;
      background: #fff2e4;
      color: #8a4b0b;
      border-radius: 8px;
    }
    .verified-facts {
      margin: 18px 0;
      border-block: 1px solid #e1e9e4;
      padding: 14px 0;
    }
    .verified-facts summary {
      cursor: pointer;
      font-size: 12px;
      font-weight: 650;
      color: #286846;
    }
    .verified-facts dl {
      margin: 5px 0 0;
    }
    .verified-facts dl > div {
      display: grid;
      gap: 6px;
      padding: 12px 0;
      border-bottom: 1px solid #edf1ee;
    }
    .verified-facts dt {
      font-size: 12px;
      color: #627167;
      line-height: 1.5;
    }
    .verified-facts dd {
      margin: 0;
      font-size: 13px;
      font-weight: 600;
    }
    .assistant-actions {
      margin: 28px 0 14px;
      display: grid;
      gap: 8px;
    }
    .assistant-actions > span {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      color: #65726b;
      margin-bottom: 4px;
    }
    .assistant-actions button,
    .more-actions button {
      display: flex;
      align-items: center;
      gap: 9px;
      text-align: left;
      color: #25493b;
      font-size: 12px;
      line-height: 1.5;
      padding: 12px;
      border: 1px solid #dce6df;
      border-radius: 8px;
      background: #f7faf8;
    }
    .assistant-actions button:hover,
    .more-actions button:hover {
      border-color: #86baa1;
      background: #eaf5ef;
    }
    .more-actions summary {
      cursor: pointer;
      font-size: 12px;
      color: #567061;
      padding: 8px 0;
    }
    .more-actions > div {
      display: grid;
      gap: 6px;
      padding-top: 8px;
    }
    .context-action {
      display: flex;
      align-items: center;
      gap: 7px;
      border: 0;
      border-top: 1px solid #e4eae6;
      background: transparent;
      color: #0c5ec6;
      font-size: 12px;
      padding: 18px 0 0;
      margin-top: 20px;
      text-align: left;
    }
    form {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 42px;
      gap: 8px;
      padding: 16px;
      border-top: 1px solid #e1e9e4;
    }
    input {
      min-width: 0;
      padding: 12px;
      border: 1px solid #becfc4;
      border-radius: 8px;
      background: #fff;
      color: #172b22;
      font-size: 13px;
    }
    form button {
      display: grid;
      place-items: center;
      background: #1769ff;
      color: #fff;
      border: 0;
      border-radius: 8px;
    }
    button:focus-visible,
    input:focus-visible,
    summary:focus-visible {
      outline: 3px solid #1769ff;
      outline-offset: 3px;
    }
    :is(input, button):disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .error {
      grid-column: 1 / -1;
      font-size: 12px;
      line-height: 1.5;
      margin: 0;
    }
    .assistant-empty {
      font-size: 14px;
      line-height: 1.6;
    }
    .thinking {
      font-size: 13px;
      color: #49785f;
      padding: 16px 0;
    }
    .thinking span {
      display: inline-block;
      width: 4px;
      height: 4px;
      margin-right: 5px;
      background: #00977a;
      border-radius: 50%;
      animation: pulse 1s infinite alternate;
    }
    @keyframes pulse {
      to {
        opacity: 0.3;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .thinking span {
        animation: none;
      }
    }
  `,
})
export class ScenarioAssistant {
  readonly planningRequested = output<void>();
  private readonly questionInput = viewChild<ElementRef<HTMLInputElement>>('question');
  protected readonly local = inject(LocalEvidenceService);
  protected readonly simulator = inject(SimulatorStore);
  protected readonly store = inject(DebuggerStore);
  protected readonly status = signal<AssistantStatus | undefined>(undefined);
  protected readonly questions = signal<readonly AssistantQuestion[]>([]);
  protected readonly answer = signal<AssistantAnswer | undefined>(undefined);
  protected readonly localReply = signal<LocalAssistantReply | undefined>(undefined);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | undefined>(undefined);
  protected readonly usedFallback = computed(
    () =>
      this.status()?.gemini_configured === true &&
      this.answer()?.provider.id === 'offline_deterministic',
  );

  protected readonly providerLabel = computed(() => {
    const status = this.status();
    if (status === undefined)
      return this.local.connected() ? 'Loading provider' : 'Local evidence required';
    return status.gemini_configured
      ? `Gemini synthesis · verified aggregates · ${status.model ?? 'configured model'}`
      : 'Verified local evidence · deterministic synthesis';
  });
  protected readonly suggestedQuestions = computed(() => this.questions().slice(0, 3));
  protected readonly remainingQuestions = computed(() => this.questions().slice(3));
  protected readonly scenarioInsight = computed(() => {
    if (!this.store.hasRun())
      return 'Open a retained replay to inspect its exact path and smallest margin.';
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
    afterNextRender(() => this.questionInput()?.nativeElement.focus());
    effect(() => {
      if (this.local.connected() && this.status() === undefined) void this.loadCatalog();
      if (!this.local.connected()) {
        this.status.set(undefined);
        this.questions.set([]);
        this.answer.set(undefined);
        this.localReply.set(undefined);
      }
    });
  }

  protected close(): void {
    this.simulator.assistantOpen.set(false);
    queueMicrotask(() => document.querySelector<HTMLButtonElement>('.assistant-launch')?.focus());
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
    this.localReply.set(undefined);
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
    input.value = '';
    this.error.set(undefined);
    if (/^(hi|hello|hey|good (morning|afternoon|evening))[!. ]*$/i.test(value)) {
      this.answer.set(undefined);
      this.localReply.set({
        heading: 'Hi. I’m ready to inspect the run.',
        body: 'I can explain release health, versioned behavior coverage, campaign results, model and TensorRT qualification, or the evidence boundary. Ask naturally or choose a suggested investigation.',
      });
      return;
    }
    if (/\b(what can you do|help|capabilit(?:y|ies)|how do i use)\b/i.test(value)) {
      this.answer.set(undefined);
      this.localReply.set({
        heading: 'I explain verified PlanMargin evidence.',
        body: 'Natural-language questions are routed to a sealed evidence query. The backend retrieves cited facts, then Gemini—when configured—writes a bounded explanation without receiving your raw question or private scene data.',
      });
      return;
    }
    const query = classifyAssistantQuestion(value);
    if (query === undefined) {
      this.answer.set(undefined);
      this.localReply.set({
        heading: /\b(path|planning|replay|scenario|case)\b/i.test(value)
          ? 'That requires an exact retained replay.'
          : 'That question is outside the verified evidence boundary.',
        body: /\b(path|planning|replay|scenario|case)\b/i.test(value)
          ? 'Only proposals with a verified replay link can open a trajectory. Use Investigate to select an available record, or ask me about the current campaign’s replay provenance.'
          : 'I will not invent an answer. Try asking about test health, behavior coverage, campaign results, model qualification, or claim limitations.',
      });
      return;
    }
    void this.ask(query);
  }

  protected showConflictFrame(): void {
    if (!this.store.hasRun()) return;
    const metrics = this.store.selectedHypothesis().metrics;
    const minimumIndex = metrics.reduce(
      (best, value, index) =>
        value.signedSeparationMeters < metrics[best].signedSeparationMeters ? index : best,
      0,
    );
    this.simulator.showPlanningFrame(minimumIndex);
    this.planningRequested.emit();
  }

  private message(error: unknown): string {
    return error instanceof Error ? error.message : 'Unknown assistant error';
  }
}
