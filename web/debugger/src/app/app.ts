import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { parseDebuggerRun } from './debugger.fixture';
import { DebuggerStore } from './debugger.store';
import { ExportService } from './export.service';
import { CampaignSummary } from './components/campaign-summary';
import { EvidenceInspector } from './components/evidence-inspector';
import { MetricTimeline } from './components/metric-timeline';
import { MobileSceneSummary } from './components/mobile-scene-summary';
import { MobileViewNav } from './components/mobile-view-nav';
import { LocalEvidencePanel } from './components/local-evidence-panel';
import { RunRail } from './components/run-rail';
import { SceneViewport } from './components/scene-viewport';
import { LocalEvidenceService } from './local-evidence.service';

@Component({
  selector: 'app-root',
  imports: [
    CampaignSummary,
    EvidenceInspector,
    MetricTimeline,
    MobileSceneSummary,
    MobileViewNav,
    LocalEvidencePanel,
    RunRail,
    SceneViewport,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header class="topbar">
      <div class="brand"><strong>PlanMargin</strong><span>Scenario debugger</span></div>
      <div class="actions">
        <input
          #runInput
          class="visually-hidden"
          type="file"
          accept="application/json,.json"
          tabindex="-1"
          aria-hidden="true"
          (change)="openRun($event)"
        />
        <button
          type="button"
          class="mode"
          [attr.aria-label]="local.connected() ? 'Real local evidence' : 'Synthetic demo'"
          [class.real]="local.connected()"
          [attr.aria-expanded]="showLocalEvidence()"
          (click)="showLocalEvidence.set(true)"
        >
          <i></i>
          <span class="desktop-label">{{
            local.connected() ? 'Real local' : 'Synthetic demo'
          }}</span>
          <span class="mobile-label">{{ local.connected() ? 'Local' : 'Demo' }}</span>
        </button>
        <button
          type="button"
          class="results"
          aria-label="Campaign results"
          [attr.aria-expanded]="showCampaign()"
          (click)="showCampaign.set(true)"
        >
          <span class="desktop-label">Campaign results</span>
          <span class="mobile-label">Results</span>
        </button>
        <button
          type="button"
          class="desktop-action"
          aria-label="Open run"
          (click)="runInput.click()"
        >
          <span class="desktop-label">Open run</span><span class="mobile-label">Open</span>
        </button>
        <button
          type="button"
          class="primary desktop-action"
          [attr.aria-label]="store.run().synthetic ? 'Export synthetic view' : 'Export blocked'"
          [disabled]="!store.run().synthetic"
          [attr.title]="
            store.run().synthetic
              ? 'Export synthetic view'
              : 'Real local evidence cannot be exported'
          "
          (click)="exportView()"
        >
          <span class="desktop-label">{{
            store.run().synthetic ? 'Export view' : 'Export blocked'
          }}</span>
          <span class="mobile-label">{{ store.run().synthetic ? 'Export' : 'Blocked' }}</span>
        </button>
        <details class="mobile-menu">
          <summary aria-label="More actions">⋮</summary>
          <div>
            <button type="button" (click)="runInput.click()">Open run</button>
            <button
              type="button"
              class="primary"
              [disabled]="!store.run().synthetic"
              (click)="exportView()"
            >
              {{ store.run().synthetic ? 'Export view' : 'Export blocked' }}
            </button>
          </div>
        </details>
      </div>
    </header>
    @if (showCampaign()) {
      <app-campaign-summary [evidence]="local.campaign()" (close)="showCampaign.set(false)" />
    }
    @if (showLocalEvidence()) {
      <app-local-evidence-panel (close)="showLocalEvidence.set(false)" />
    }
    <app-mobile-view-nav />
    @if (notice()) {
      <p class="notice" role="status">{{ notice() }}</p>
    }
    <main>
      <app-run-rail class="run-rail" />
      <app-scene-viewport class="scene" [class.mobile-hidden]="store.mobileView() !== 'scene'" />
      <app-mobile-scene-summary
        class="mobile-summary"
        [class.mobile-hidden]="store.mobileView() !== 'scene'"
      />
      <app-evidence-inspector
        class="evidence"
        [class.mobile-hidden]="store.mobileView() !== 'evidence'"
      />
      <app-metric-timeline
        class="metrics"
        [class.mobile-hidden]="store.mobileView() !== 'metrics'"
      />
    </main>
  `,
  styles: `
    :host {
      display: grid;
      grid-template-rows: 56px minmax(0, 1fr);
      width: 100%;
      min-height: 100dvh;
      background: var(--app-bg);
      color: var(--primary);
    }
    .topbar {
      z-index: 10;
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-width: 0;
      padding: 0 0.9rem 0 1rem;
      border-bottom: 1px solid var(--divider);
      background: #080d11;
    }
    .brand {
      display: flex;
      align-items: center;
      min-width: 0;
      gap: 1rem;
    }
    .brand strong {
      font-size: 0.9rem;
      letter-spacing: -0.02em;
    }
    .brand span {
      color: var(--secondary);
      font-size: 0.72rem;
    }
    .actions {
      display: flex;
      gap: 0.5rem;
    }
    .mobile-label {
      display: none;
    }
    .mobile-menu {
      display: none;
    }
    button {
      min-height: 32px;
      padding: 0 0.75rem;
      border: 1px solid var(--divider);
      border-radius: 2px;
      background: transparent;
      color: var(--primary);
      font: inherit;
      font-size: 0.68rem;
      font-weight: 600;
    }
    button:hover {
      border-color: var(--secondary);
    }
    button.primary {
      border-color: var(--tested);
      color: var(--tested);
    }
    button:disabled {
      cursor: not-allowed;
      opacity: 0.58;
    }
    button.results {
      border-color: #4f626f;
      background: #101820;
    }
    button.mode {
      display: flex;
      align-items: center;
      gap: 0.4rem;
      border-color: #4f626f;
    }
    button.mode i {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--recorded);
    }
    button.mode.real {
      border-color: #4f713e;
      color: var(--success);
    }
    button.mode.real i {
      background: var(--success);
    }
    main {
      display: grid;
      grid-template-columns: 210px minmax(0, 1fr) 300px;
      grid-template-rows: minmax(300px, 1fr) 210px;
      min-width: 0;
      min-height: 0;
    }
    .run-rail {
      grid-row: 1 / 3;
    }
    .scene {
      grid-column: 2;
      grid-row: 1;
    }
    .evidence {
      grid-column: 3;
      grid-row: 1 / 3;
    }
    .metrics {
      grid-column: 2;
      grid-row: 2;
    }
    .notice {
      position: fixed;
      z-index: 20;
      top: 64px;
      left: 50%;
      max-width: min(90vw, 560px);
      transform: translateX(-50%);
      margin: 0;
      padding: 0.55rem 0.8rem;
      border: 1px solid var(--divider);
      background: var(--rail);
      color: var(--primary);
      font-size: 0.72rem;
    }
    .visually-hidden {
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip: rect(0 0 0 0);
      white-space: nowrap;
      clip-path: inset(50%);
    }
    @media (max-width: 920px) {
      main {
        grid-template-columns: 184px minmax(0, 1fr) 250px;
      }
    }
    @media (max-width: 760px) {
      :host {
        grid-template-rows: 56px 45px minmax(0, 1fr);
      }
      .brand {
        gap: 0.55rem;
      }
      .brand span {
        display: none;
      }
      .actions button {
        padding: 0 0.48rem;
        font-size: 0.62rem;
      }
      .desktop-label {
        display: none;
      }
      .mobile-label {
        display: inline;
      }
      .desktop-action {
        display: none;
      }
      .mobile-menu {
        position: relative;
        display: block;
      }
      .mobile-menu summary {
        display: grid;
        width: 32px;
        min-height: 32px;
        cursor: pointer;
        list-style: none;
        place-items: center;
        border: 1px solid var(--divider);
        border-radius: 2px;
        color: var(--primary);
        font-size: 1.1rem;
      }
      .mobile-menu summary::-webkit-details-marker {
        display: none;
      }
      .mobile-menu div {
        position: absolute;
        z-index: 30;
        top: calc(100% + 0.4rem);
        right: 0;
        display: grid;
        width: 132px;
        gap: 0.35rem;
        padding: 0.5rem;
        border: 1px solid var(--divider);
        background: var(--rail);
        box-shadow: 0 12px 32px rgb(0 0 0 / 45%);
      }
      .mobile-menu button {
        width: 100%;
      }
      main {
        display: block;
        min-height: auto;
      }
      .run-rail {
        display: none;
      }
      .scene,
      .evidence,
      .metrics {
        display: block;
      }
      .scene {
        height: 470px;
        min-height: 470px;
      }
      .evidence,
      .metrics {
        min-height: calc(100dvh - 101px);
      }
      .mobile-hidden {
        display: none;
      }
    }
    @media (max-width: 420px) {
      .topbar {
        padding-right: 0.45rem;
        padding-left: 0.65rem;
      }
      .actions {
        gap: 0.28rem;
      }
      .actions button {
        min-height: 30px;
        padding: 0 0.38rem;
      }
    }
  `,
})
export class App {
  protected readonly store = inject(DebuggerStore);
  protected readonly local = inject(LocalEvidenceService);
  private readonly exporter = inject(ExportService);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly notice = signal<string | undefined>(undefined);
  protected readonly showCampaign = signal(
    new URLSearchParams(window.location.search).has('evidence'),
  );
  protected readonly showLocalEvidence = signal(false);
  private noticeTimer: ReturnType<typeof setTimeout> | undefined;

  constructor() {
    this.destroyRef.onDestroy(() => {
      if (this.noticeTimer !== undefined) clearTimeout(this.noticeTimer);
    });
  }

  protected exportView(): void {
    if (!this.store.run().synthetic) {
      this.showNotice('Real local evidence export is disabled');
      return;
    }
    this.exporter.download(
      this.store.run(),
      this.store.selectedHypothesisId(),
      this.store.timestepIndex(),
    );
    this.showNotice('Synthetic view exported');
  }

  protected async openRun(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file === undefined) return;
    try {
      if (file.size > 5_000_000) {
        throw new Error('Run file exceeds the 5 MB local limit');
      }
      const run = parseDebuggerRun(JSON.parse(await file.text()) as unknown);
      this.local.disconnect();
      this.store.loadRun(run);
      this.showNotice('Synthetic run opened');
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown file error';
      this.showNotice(`Run rejected: ${message}`);
    } finally {
      input.value = '';
    }
  }

  private showNotice(message: string): void {
    if (this.noticeTimer !== undefined) clearTimeout(this.noticeTimer);
    this.notice.set(message);
    this.noticeTimer = setTimeout(() => this.notice.set(undefined), 3200);
  }
}
