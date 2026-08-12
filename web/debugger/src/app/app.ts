import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { parseDebuggerRun } from './debugger.fixture';
import { DebuggerStore } from './debugger.store';
import { ExportService } from './export.service';
import { CampaignSummary } from './components/campaign-summary';
import { EvidenceInspector } from './components/evidence-inspector';
import { MetricTimeline } from './components/metric-timeline';
import { MobileSceneSummary } from './components/mobile-scene-summary';
import { MobileViewNav } from './components/mobile-view-nav';
import { RunRail } from './components/run-rail';
import { SceneViewport } from './components/scene-viewport';

@Component({
  selector: 'app-root',
  imports: [
    CampaignSummary,
    EvidenceInspector,
    MetricTimeline,
    MobileSceneSummary,
    MobileViewNav,
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
          class="results"
          [attr.aria-expanded]="showCampaign()"
          (click)="showCampaign.set(true)"
        >
          Campaign results
        </button>
        <button type="button" (click)="runInput.click()">Open run</button>
        <button type="button" class="primary" (click)="exportView()">Export view</button>
      </div>
    </header>
    @if (showCampaign()) {
      <app-campaign-summary (close)="showCampaign.set(false)" />
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
    button.results {
      border-color: #4f626f;
      background: #101820;
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
        padding: 0 0.55rem;
        font-size: 0.62rem;
      }
      .actions button.results {
        max-width: 72px;
        line-height: 1.05;
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
  `,
})
export class App {
  protected readonly store = inject(DebuggerStore);
  private readonly exporter = inject(ExportService);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly notice = signal<string | undefined>(undefined);
  protected readonly showCampaign = signal(
    new URLSearchParams(window.location.search).has('evidence'),
  );
  private noticeTimer: ReturnType<typeof setTimeout> | undefined;

  constructor() {
    this.destroyRef.onDestroy(() => {
      if (this.noticeTimer !== undefined) clearTimeout(this.noticeTimer);
    });
  }

  protected exportView(): void {
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
