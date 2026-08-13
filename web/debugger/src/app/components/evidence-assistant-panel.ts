import { ChangeDetectionStrategy, Component, effect, inject, output, signal } from '@angular/core';
import { LocalEvidenceService } from '../local-evidence.service';
import {
  AssistantAnswer,
  AssistantQueryId,
  AssistantQuestion,
  AssistantStatus,
} from '../product-evidence.types';

@Component({
  selector: 'app-evidence-assistant-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="assistant-shell" aria-labelledby="assistant-title">
      <header class="page-heading">
        <div>
          <h1 id="assistant-title">Evidence Assistant</h1>
          <p>Ask bounded questions over sealed experiment evidence—without giving a model SQL or private records.</p>
        </div>
        @if (status(); as current) {
          <span class="provider" [class.gemini]="current.gemini_configured">
            <i></i>{{ providerLabel(current) }}
          </span>
        }
      </header>

      @if (!local.connected()) {
        <div class="connection-state">
          <div class="assistant-mark" aria-hidden="true">✦</div>
          <h2>Connect verified evidence first</h2>
          <p>The assistant reads only the authenticated local evidence boundary. No question or record leaves this machine in offline mode.</p>
          <button type="button" class="primary" (click)="connectRequested.emit()">Connect local evidence</button>
        </div>
      } @else if (loadingCatalog()) {
        <div class="connection-state" role="status">
          <div class="loading-ring"></div>
          <h2>Verifying assistant tools</h2>
          <p>Checking the five-query allowlist and source seals.</p>
        </div>
      } @else if (error()) {
        <div class="connection-state error" role="alert">
          <h2>Assistant unavailable</h2>
          <p>{{ error() }}</p>
          <button type="button" (click)="loadCatalog()">Retry</button>
        </div>
      } @else {
        <div class="assistant-layout">
          <nav class="question-list" aria-label="Evidence questions">
            <p>Suggested questions</p>
            @for (question of questions(); track question.query_id; let index = $index) {
              <button
                type="button"
                [class.active]="selectedQuery() === question.query_id"
                [attr.aria-pressed]="selectedQuery() === question.query_id"
                (click)="ask(question)"
              >
                <span>{{ index + 1 }}</span>
                <strong>{{ question.question }}</strong>
              </button>
            }
            <div class="provider-note">
              <strong>{{ status()?.gemini_configured ? 'Gemini explanation enabled' : 'Gemini adapter ready' }}</strong>
              <p>
                {{ status()?.gemini_configured
                  ? 'Gemini receives public aggregate facts only.'
                  : 'Start the API with the free-tier Gemini flags to use hosted explanation. Offline answers remain fully functional.' }}
              </p>
            </div>
          </nav>

          <article class="answer" aria-live="polite">
            @if (asking()) {
              <div class="answer-loading" role="status"><div class="loading-ring"></div>Tracing facts and citations…</div>
            } @else if (answer(); as result) {
              <div class="answer-heading">
                <span>{{ result.question.query_label }}</span>
                <small>{{ result.tool_result.source_mode === 'real_local_redacted' ? 'Local sealed evidence' : 'Public aggregate evidence' }}</small>
              </div>
              <h2>{{ result.explanation.summary }}</h2>
              <p class="interpretation">{{ result.explanation.interpretation }}</p>

              <section aria-labelledby="facts-title">
                <div class="section-heading"><h3 id="facts-title">Verified facts</h3><span>{{ result.tool_result.facts.length }} facts</span></div>
                <ul class="facts">
                  @for (fact of result.tool_result.facts; track fact.fact_id) {
                    <li>
                      <i></i>
                      <div><p>{{ fact.statement }}</p><small>{{ fact.fact_id }}</small></div>
                      @if (fact.value !== null) { <strong>{{ displayValue(fact.value, fact.unit) }}</strong> }
                    </li>
                  }
                </ul>
              </section>

              <div class="limitation">
                <strong>Claim boundary</strong>
                <p>{{ result.explanation.limitation }}</p>
              </div>

              <section aria-labelledby="citations-title">
                <div class="section-heading"><h3 id="citations-title">Source seals</h3><span>Repository-local</span></div>
                <ul class="citations">
                  @for (citation of result.tool_result.citations; track citation.citation_id) {
                    <li><div><strong>{{ citation.title }}</strong><span>{{ citation.repository_path }}</span></div><code>{{ citation.sha256.slice(0, 12) }}…</code></li>
                  }
                </ul>
              </section>

              <footer>
                <span><i></i>No private data sent to provider</span>
                <span>Question stored as SHA-256 only</span>
              </footer>
            }
          </article>
        </div>
      }
    </section>
  `,
  styles: `
    :host { display: block; min-width: 0; min-height: 0; height: 100%; }
    .assistant-shell { display: flex; height: 100%; min-height: 0; flex-direction: column; background: var(--surface); }
    .page-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; padding: 1.75rem 2rem 1.4rem; border-bottom: 1px solid var(--divider); }
    h1, h2, h3, p { margin: 0; }
    h1 { font-size: clamp(1.35rem, 2vw, 1.8rem); letter-spacing: -0.04em; }
    .page-heading p { max-width: 720px; margin-top: .45rem; color: var(--secondary); font-size: .86rem; line-height: 1.55; }
    .provider { display: flex; align-items: center; gap: .45rem; flex: 0 0 auto; padding: .48rem .7rem; border: 1px solid #b9dfb0; border-radius: 999px; background: #f2fbef; color: #26721f; font-size: .72rem; font-weight: 700; }
    .provider i { width: 7px; height: 7px; border-radius: 50%; background: #45a83c; }
    .provider.gemini { border-color: #c9c5fa; background: #f5f3ff; color: #5641bd; }
    .provider.gemini i { background: #7057e8; }
    .assistant-layout { display: grid; grid-template-columns: minmax(250px, 30%) minmax(0, 1fr); min-height: 0; flex: 1; }
    .question-list { padding: 1.25rem; overflow: auto; border-right: 1px solid var(--divider); background: var(--surface-subtle); }
    .question-list > p { margin: 0 0 .7rem .25rem; color: var(--secondary); font-size: .72rem; font-weight: 700; }
    .question-list > button { display: grid; grid-template-columns: 26px minmax(0,1fr); align-items: start; width: 100%; gap: .65rem; margin-bottom: .55rem; padding: .85rem; border: 1px solid transparent; border-radius: var(--radius-sm); background: transparent; color: var(--primary); text-align: left; }
    .question-list > button:hover, .question-list > button.active { border-color: #c8d5f5; background: #fff; box-shadow: var(--shadow-sm); }
    .question-list > button span { display: grid; width: 24px; height: 24px; place-items: center; border-radius: 50%; background: #e8f0ff; color: #1558d6; font-size: .7rem; font-weight: 800; }
    .question-list > button strong { font-size: .78rem; line-height: 1.4; }
    .provider-note { margin-top: 1.25rem; padding: 1rem; border: 1px solid var(--divider); border-radius: var(--radius-sm); background: #fff; }
    .provider-note strong { font-size: .78rem; }
    .provider-note p { margin-top: .35rem; color: var(--secondary); font-size: .72rem; line-height: 1.5; }
    .answer { min-width: 0; padding: clamp(1.4rem, 3vw, 2.5rem); overflow: auto; }
    .answer-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.2rem; color: #1558d6; font-size: .72rem; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; }
    .answer-heading small { color: var(--secondary); font-weight: 600; letter-spacing: 0; text-transform: none; }
    .answer h2 { max-width: 830px; font-size: clamp(1.35rem, 2.5vw, 2rem); line-height: 1.18; letter-spacing: -.035em; }
    .interpretation { max-width: 840px; margin-top: .8rem; color: var(--secondary); font-size: .92rem; line-height: 1.65; }
    .answer section { margin-top: 1.8rem; }
    .section-heading { display: flex; align-items: center; justify-content: space-between; padding-bottom: .65rem; border-bottom: 1px solid var(--divider); }
    .section-heading h3 { font-size: .82rem; }
    .section-heading span { color: var(--secondary); font-size: .7rem; }
    ul { margin: 0; padding: 0; list-style: none; }
    .facts li { display: grid; grid-template-columns: 9px minmax(0,1fr) auto; align-items: start; gap: .7rem; padding: .85rem 0; border-bottom: 1px solid var(--divider-soft); }
    .facts li > i { width: 7px; height: 7px; margin-top: .4rem; border-radius: 50%; background: var(--accent-green); }
    .facts p { font-size: .82rem; line-height: 1.48; }
    .facts small { display: block; margin-top: .2rem; color: var(--tertiary); font-size: .62rem; }
    .facts li > strong { color: #1558d6; font-size: .78rem; font-variant-numeric: tabular-nums; }
    .limitation { margin-top: 1.5rem; padding: 1rem 1.1rem; border-left: 4px solid var(--accent-coral); border-radius: 0 var(--radius-sm) var(--radius-sm) 0; background: #fff5f1; }
    .limitation strong { color: #a33a1f; font-size: .74rem; }
    .limitation p { margin-top: .3rem; color: #733525; font-size: .78rem; line-height: 1.5; }
    .citations li { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: .75rem 0; border-bottom: 1px solid var(--divider-soft); }
    .citations strong, .citations span { display: block; }
    .citations strong { font-size: .76rem; }
    .citations span { margin-top: .2rem; color: var(--secondary); font-size: .66rem; }
    code { color: #6752bd; font-size: .66rem; }
    footer { display: flex; justify-content: space-between; gap: 1rem; margin-top: 1.5rem; padding: .75rem .85rem; border-radius: var(--radius-sm); background: var(--surface-subtle); color: var(--secondary); font-size: .68rem; }
    footer span:first-child { display: flex; align-items: center; gap: .4rem; color: #26721f; }
    footer i { width: 7px; height: 7px; border-radius: 50%; background: var(--accent-green); }
    .connection-state { display: grid; max-width: 540px; margin: auto; padding: 2rem; justify-items: center; text-align: center; }
    .connection-state h2 { margin-top: .8rem; font-size: 1.25rem; }
    .connection-state p { margin: .55rem 0 1.2rem; color: var(--secondary); line-height: 1.6; }
    .assistant-mark { display: grid; width: 54px; height: 54px; place-items: center; border-radius: 18px; background: #f0edff; color: #6954d8; font-size: 1.6rem; }
    .loading-ring { width: 30px; height: 30px; border: 3px solid #dfe6ef; border-top-color: #1558d6; border-radius: 50%; animation: spin .8s linear infinite; }
    .answer-loading { display: flex; align-items: center; gap: .8rem; color: var(--secondary); }
    button { min-height: 38px; padding: 0 .9rem; border: 1px solid var(--divider-strong); border-radius: 9px; background: #fff; color: var(--primary); font: inherit; font-size: .76rem; font-weight: 700; }
    button.primary { border-color: #1769e0; background: #1769e0; color: #fff; }
    @keyframes spin { to { transform: rotate(360deg); } }
    @media (max-width: 760px) { .page-heading { padding: 1.2rem; } .assistant-layout { grid-template-columns: 1fr; overflow: auto; } .question-list { overflow: visible; border-right: 0; border-bottom: 1px solid var(--divider); } .answer { overflow: visible; padding: 1.2rem; } footer { flex-direction: column; } }
  `,
})
export class EvidenceAssistantPanel {
  protected readonly local = inject(LocalEvidenceService);
  protected readonly connectRequested = output<void>();
  protected readonly status = signal<AssistantStatus | undefined>(undefined);
  protected readonly questions = signal<readonly AssistantQuestion[]>([]);
  protected readonly answer = signal<AssistantAnswer | undefined>(undefined);
  protected readonly selectedQuery = signal<AssistantQueryId | undefined>(undefined);
  protected readonly loadingCatalog = signal(false);
  protected readonly asking = signal(false);
  protected readonly error = signal<string | undefined>(undefined);

  constructor() {
    effect(() => {
      if (this.local.connected() && this.questions().length === 0 && !this.loadingCatalog()) {
        void this.loadCatalog();
      }
    });
  }

  protected async loadCatalog(): Promise<void> {
    if (!this.local.connected() || this.loadingCatalog()) return;
    this.loadingCatalog.set(true);
    this.error.set(undefined);
    try {
      const catalog = await this.local.assistantCatalog();
      this.status.set(catalog.status);
      this.questions.set(catalog.questions);
      if (catalog.questions.length > 0) await this.ask(catalog.questions[1] ?? catalog.questions[0]);
    } catch (error: unknown) {
      this.error.set(error instanceof Error ? error.message : 'Unknown assistant error');
    } finally {
      this.loadingCatalog.set(false);
    }
  }

  protected async ask(question: AssistantQuestion): Promise<void> {
    this.selectedQuery.set(question.query_id);
    this.asking.set(true);
    this.error.set(undefined);
    try {
      this.answer.set(await this.local.askAssistant(question.query_id));
    } catch (error: unknown) {
      this.error.set(error instanceof Error ? error.message : 'Unknown assistant error');
    } finally {
      this.asking.set(false);
    }
  }

  protected providerLabel(status: AssistantStatus): string {
    return status.gemini_configured ? `Gemini · ${status.model ?? 'configured'}` : 'Offline verified';
  }

  protected displayValue(value: string | number | boolean, unit: string | null): string {
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    if (typeof value === 'number') {
      if (unit === 'proportion') return `${(value * 100).toFixed(4)}%`;
      if (unit === 'percent') return `${value.toFixed(4)}%`;
      if (unit === 'percentage points') return `${value.toFixed(4)} pp`;
      const rendered = value.toLocaleString(undefined, { maximumFractionDigits: 4 });
      return unit === null ? rendered : `${rendered} ${unit}`;
    }
    return unit === null ? value : `${value} ${unit}`;
  }
}
