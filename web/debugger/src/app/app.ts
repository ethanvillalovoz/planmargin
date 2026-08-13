import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { CampaignSummary } from './components/campaign-summary';
import { EvidenceAssistantPanel } from './components/evidence-assistant-panel';
import { EvidenceInspector } from './components/evidence-inspector';
import { GaussianFieldPanel } from './components/gaussian-field-panel';
import { LocalEvidencePanel } from './components/local-evidence-panel';
import { MetricTimeline } from './components/metric-timeline';
import { MobileSceneSummary } from './components/mobile-scene-summary';
import { MobileViewNav } from './components/mobile-view-nav';
import { ProjectOverview } from './components/project-overview';
import { RunRail } from './components/run-rail';
import { SceneViewport } from './components/scene-viewport';
import { parseDebuggerRun } from './debugger.fixture';
import { DebuggerStore } from './debugger.store';
import { ExportService } from './export.service';
import { LocalEvidenceService } from './local-evidence.service';

type Workspace = 'overview' | 'scenario' | 'assistant' | 'gaussian';

@Component({
  selector: 'app-root',
  imports: [
    CampaignSummary,
    EvidenceAssistantPanel,
    EvidenceInspector,
    GaussianFieldPanel,
    LocalEvidencePanel,
    MetricTimeline,
    MobileSceneSummary,
    MobileViewNav,
    ProjectOverview,
    RunRail,
    SceneViewport,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header class="topbar">
      <button type="button" class="brand" aria-label="Open PlanMargin overview" (click)="workspace.set('overview')">
        <span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span>
        <span><strong>PlanMargin</strong><small>Counterfactual stress testing</small></span>
      </button>
      <div class="topbar-context">
        <span>Natural development campaign</span><i></i><strong>v1 · immutable</strong>
      </div>
      <div class="topbar-actions">
        <button
          type="button"
          class="evidence-mode"
          [class.connected]="local.connected()"
          [attr.aria-expanded]="showLocalEvidence()"
          (click)="showLocalEvidence.set(true)"
        >
          <i></i>{{ local.connected() ? 'Verified local evidence' : 'Connect local evidence' }}
        </button>
      </div>
    </header>

    <div class="product-shell">
      <nav class="workspace-nav" aria-label="PlanMargin workspaces">
        <div class="nav-group">
          <p>Workspace</p>
          <button type="button" aria-label="Overview" [class.active]="workspace() === 'overview'" (click)="workspace.set('overview')">
            <span aria-hidden="true">⌂</span><strong>Overview</strong>
          </button>
          <button type="button" aria-label="Scenario Lab" [class.active]="workspace() === 'scenario'" (click)="workspace.set('scenario')">
            <span aria-hidden="true">⌁</span><strong>Scenario Lab</strong>
          </button>
          <button type="button" aria-label="Search Campaign" (click)="showCampaign.set(true)">
            <span aria-hidden="true">◎</span><strong>Search Campaign</strong>
          </button>
          <button type="button" aria-label="Evidence Assistant" [class.active]="workspace() === 'assistant'" (click)="workspace.set('assistant')">
            <span aria-hidden="true">✦</span><strong>Evidence Assistant</strong>
          </button>
          <button type="button" aria-label="Gaussian Field" [class.active]="workspace() === 'gaussian'" (click)="workspace.set('gaussian')">
            <span aria-hidden="true">⠿</span><strong>Gaussian Field</strong><em>EXP</em>
          </button>
        </div>

        <div class="nav-boundary">
          <span><i></i>Research prototype</span>
          <p>Find behaviorally plausible failures. Do not infer real-world safety.</p>
        </div>
      </nav>

      <main class="workspace">
        @switch (workspace()) {
          @case ('overview') {
            <app-project-overview
              (workspaceRequested)="workspace.set($event)"
              (campaignRequested)="showCampaign.set(true)"
            />
          }
          @case ('scenario') {
            <section class="scenario-workspace" aria-labelledby="scenario-title">
              <header class="scenario-heading">
                <div><span>Scenario Lab</span><h1 id="scenario-title">Replay a counterfactual comparison</h1><p>Compare three trajectories against the same scene mutation and inspect the exact planner margin.</p></div>
                <div class="scenario-actions">
                  <input #runInput class="visually-hidden" type="file" accept="application/json,.json" (change)="openRun($event)" />
                  <button type="button" (click)="runInput.click()">Open run</button>
                  <button type="button" [disabled]="!store.run().synthetic" (click)="exportView()">{{ store.run().synthetic ? 'Export demo view' : 'Export blocked' }}</button>
                </div>
              </header>
              <app-mobile-view-nav />
              <div class="scenario-grid">
                <app-run-rail class="run-rail" />
                <app-scene-viewport class="scene" [class.mobile-hidden]="store.mobileView() !== 'scene'" />
                <app-mobile-scene-summary class="mobile-summary" [class.mobile-hidden]="store.mobileView() !== 'scene'" />
                <app-evidence-inspector class="evidence" [class.mobile-hidden]="store.mobileView() !== 'evidence'" />
                <app-metric-timeline class="metrics" [class.mobile-hidden]="store.mobileView() !== 'metrics'" />
              </div>
            </section>
          }
          @case ('assistant') {
            <app-evidence-assistant-panel (connectRequested)="showLocalEvidence.set(true)" />
          }
          @case ('gaussian') {
            <app-gaussian-field-panel (connectRequested)="showLocalEvidence.set(true)" />
          }
        }
      </main>
    </div>

    @if (showCampaign()) {
      <app-campaign-summary [evidence]="local.campaign()" (close)="showCampaign.set(false)" />
    }
    @if (showLocalEvidence()) {
      <app-local-evidence-panel (close)="showLocalEvidence.set(false)" />
    }
    @if (notice()) { <p class="notice" role="status">{{ notice() }}</p> }
  `,
  styles: `
    :host { display: grid; grid-template-rows: 64px minmax(0,1fr); width: 100%; min-height: 100dvh; background: var(--app-bg); color: var(--primary); }
    button { color: inherit; font: inherit; }
    .topbar { z-index: 50; display: grid; grid-template-columns: 240px minmax(0,1fr) auto; align-items: center; padding: 0 1.1rem; border-bottom: 1px solid var(--divider); background: rgb(255 255 255 / 94%); backdrop-filter: blur(14px); }
    .brand { display: flex; align-items: center; gap: .7rem; padding: 0; border: 0; background: transparent; text-align: left; }
    .brand-mark { position: relative; display: block; width: 32px; height: 32px; border-radius: 10px; background: #102b3b; overflow: hidden; }
    .brand-mark i { position: absolute; display: block; width: 17px; height: 4px; border-radius: 999px; transform: rotate(-24deg); }
    .brand-mark i:nth-child(1) { top: 8px; left: 7px; background: #5bd1df; }
    .brand-mark i:nth-child(2) { top: 14px; left: 9px; background: #ff765e; }
    .brand-mark i:nth-child(3) { top: 20px; left: 7px; background: #b7e154; }
    .brand strong, .brand small { display: block; }
    .brand strong { font-size: .92rem; letter-spacing: -.035em; }
    .brand small { margin-top: .12rem; color: var(--secondary); font-size: .61rem; }
    .topbar-context { display: flex; align-items: center; justify-content: center; gap: .55rem; color: var(--secondary); font-size: .68rem; }
    .topbar-context i { width: 3px; height: 3px; border-radius: 50%; background: var(--tertiary); }
    .topbar-context strong { color: var(--primary); font-weight: 700; }
    .evidence-mode { display: flex; align-items: center; gap: .45rem; min-height: 34px; padding: 0 .75rem; border: 1px solid var(--divider-strong); border-radius: 999px; background: #fff; font-size: .68rem; font-weight: 700; }
    .evidence-mode i { width: 7px; height: 7px; border-radius: 50%; background: var(--recorded); }
    .evidence-mode.connected { border-color: #b9dfb0; background: #f4fbf2; color: #26721f; }
    .evidence-mode.connected i { background: var(--accent-green); }
    .product-shell { display: grid; grid-template-columns: 210px minmax(0,1fr); min-width: 0; min-height: 0; }
    .workspace-nav { display: flex; min-height: 0; flex-direction: column; justify-content: space-between; padding: 1.1rem .75rem; border-right: 1px solid var(--divider); background: #fbfcfd; }
    .nav-group > p { margin: .25rem .65rem .65rem; color: var(--tertiary); font-size: .6rem; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; }
    .nav-group button { position: relative; display: grid; grid-template-columns: 25px minmax(0,1fr) auto; align-items: center; width: 100%; min-height: 40px; gap: .45rem; padding: 0 .65rem; border: 0; border-radius: 9px; background: transparent; color: var(--secondary); text-align: left; }
    .nav-group button:hover { background: #f0f4f7; color: var(--primary); }
    .nav-group button.active { background: #eaf2ff; color: #1558ba; }
    .nav-group button.active::before { position: absolute; left: -12px; width: 3px; height: 21px; border-radius: 0 3px 3px 0; background: #1769e0; content: ''; }
    .nav-group button > span { display: grid; width: 24px; place-items: center; font-size: 1rem; }
    .nav-group button strong { font-size: .72rem; font-weight: 680; }
    .nav-group button em { padding: .2rem .3rem; border-radius: 4px; background: #eff0fb; color: #6855c0; font-size: .48rem; font-style: normal; font-weight: 900; }
    .nav-boundary { margin: 1rem .5rem .2rem; padding: .8rem; border: 1px solid var(--divider); border-radius: 9px; background: #fff; }
    .nav-boundary span { display: flex; align-items: center; gap: .4rem; color: var(--primary); font-size: .64rem; font-weight: 800; }
    .nav-boundary span i { width: 6px; height: 6px; border-radius: 50%; background: var(--accent-coral); }
    .nav-boundary p { margin: .35rem 0 0; color: var(--secondary); font-size: .6rem; line-height: 1.45; }
    .workspace { min-width: 0; min-height: 0; overflow: auto; background: var(--surface); }
    .scenario-workspace { display: grid; grid-template-rows: auto auto minmax(0,1fr); height: 100%; min-height: 0; }
    .scenario-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem; padding: 1.1rem 1.25rem; border-bottom: 1px solid var(--divider); background: #fff; }
    .scenario-heading span { color: #1558ba; font-size: .62rem; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; }
    .scenario-heading h1 { margin: .2rem 0 0; font-size: 1.2rem; letter-spacing: -.035em; }
    .scenario-heading p { margin: .3rem 0 0; color: var(--secondary); font-size: .7rem; }
    .scenario-actions { display: flex; gap: .5rem; }
    .scenario-actions button { min-height: 34px; padding: 0 .75rem; border: 1px solid var(--divider-strong); border-radius: 9px; background: #fff; font-size: .7rem; font-weight: 700; }
    .scenario-actions button:disabled { cursor: not-allowed; opacity: .5; }
    .scenario-grid { display: grid; grid-template-columns: 190px minmax(0,1fr) 310px; grid-template-rows: minmax(300px,1fr) 205px; min-width: 0; min-height: 0; }
    .run-rail { grid-row: 1/3; } .scene { grid-column: 2; grid-row: 1; } .evidence { grid-column: 3; grid-row: 1/3; } .metrics { grid-column: 2; grid-row: 2; }
    app-evidence-assistant-panel, app-gaussian-field-panel { display: block; height: 100%; min-height: 0; }
    .notice { position: fixed; z-index: 200; top: 74px; left: 50%; max-width: min(90vw,560px); transform: translateX(-50%); margin: 0; padding: .65rem .85rem; border: 1px solid var(--divider); border-radius: 9px; background: #102b3b; color: #fff; box-shadow: var(--shadow); font-size: .72rem; }
    .visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; clip-path: inset(50%); }
    @media (min-width: 761px) { app-mobile-view-nav, .mobile-summary { display: none; } }
    @media (max-width: 1080px) {
      .product-shell { grid-template-columns: 68px minmax(0,1fr); }
      .workspace-nav { padding-inline: .55rem; }
      .nav-group > p, .nav-group button strong, .nav-group button em, .nav-boundary p { display: none; }
      .nav-group button { grid-template-columns: 1fr; justify-items: center; padding: 0; }
      .nav-group button.active::before { left: -9px; }
      .nav-boundary { display: grid; padding: .65rem .2rem; justify-items: center; }
      .nav-boundary span { font-size: 0; } .nav-boundary span i { width: 8px; height: 8px; }
      .scenario-grid { grid-template-columns: 165px minmax(0,1fr) 280px; }
    }
    @media (max-width: 760px) {
      :host { grid-template-rows: 58px minmax(0,1fr); }
      .topbar { grid-template-columns: 1fr auto; padding: 0 .7rem; }
      .brand small, .topbar-context { display: none; }
      .evidence-mode { width: 34px; padding: 0; justify-content: center; font-size: 0; }
      .product-shell { display: block; height: 100%; min-height: 0; }
      .workspace-nav { position: fixed; z-index: 80; right: 0; bottom: 0; left: 0; display: block; padding: .35rem; border-top: 1px solid var(--divider); border-right: 0; }
      .nav-group { display: grid; grid-template-columns: repeat(5,1fr); }
      .nav-group > p, .nav-boundary { display: none; }
      .nav-group button { min-height: 44px; }
      .nav-group button.active::before { top: -6px; left: 50%; width: 20px; height: 3px; transform: translateX(-50%); border-radius: 0 0 3px 3px; }
      .workspace { height: 100%; padding-bottom: 51px; }
      .scenario-workspace { display: block; height: auto; }
      .scenario-heading { align-items: flex-start; flex-direction: column; }
      .scenario-grid { display: block; }
      .run-rail { display: none; }
      .scene { display: block; height: 460px; min-height: 460px; }
      .evidence, .metrics { display: block; min-height: calc(100dvh - 148px); }
      .mobile-hidden { display: none; }
    }
  `,
})
export class App {
  protected readonly store = inject(DebuggerStore);
  protected readonly local = inject(LocalEvidenceService);
  private readonly exporter = inject(ExportService);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly workspace = signal<Workspace>('overview');
  protected readonly notice = signal<string | undefined>(undefined);
  protected readonly showCampaign = signal(new URLSearchParams(window.location.search).has('evidence'));
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
    this.exporter.download(this.store.run(), this.store.selectedHypothesisId(), this.store.timestepIndex());
    this.showNotice('Synthetic view exported');
  }

  protected async openRun(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file === undefined) return;
    try {
      if (file.size > 5_000_000) throw new Error('Run file exceeds the 5 MB local limit');
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
