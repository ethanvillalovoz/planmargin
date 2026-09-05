import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { LocalEvidencePanel } from './components/local-evidence-panel';
import { ProductShell } from './components/product-shell';
import { DebuggerStore } from './debugger.store';
import { LocalEvidenceService } from './local-evidence.service';

export function consumeLaunchToken(location: Location, history: History): string | undefined {
  const parameters = new URLSearchParams(location.hash.slice(1));
  const token = parameters.get('token')?.trim();
  if (!token) return undefined;
  history.replaceState(null, '', `${location.pathname}${location.search}`);
  return token;
}

@Component({
  selector: 'app-root',
  imports: [LocalEvidencePanel, ProductShell],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-product-shell (connectRequested)="openLocalEvidence()" />
    @if (showLocalEvidence()) {
      <app-local-evidence-panel (close)="closeLocalEvidence()" />
    }
  `,
  styles: `
    :host {
      display: block;
      width: 100%;
      min-width: 320px;
      min-height: 100dvh;
    }
  `,
})
export class App {
  protected readonly showLocalEvidence = signal(false);
  private readonly local = inject(LocalEvidenceService);
  private readonly debuggerStore = inject(DebuggerStore);
  private returnFocus: HTMLElement | undefined;
  private sessionGeneration = 0;

  constructor() {
    const onLaunchLink = () => {
      if (new URLSearchParams(window.location.hash.slice(1)).get('token')) {
        void this.connectFromAvailableSession();
      }
    };
    window.addEventListener('hashchange', onLaunchLink);
    inject(DestroyRef).onDestroy(() => {
      this.sessionGeneration++;
      window.removeEventListener('hashchange', onLaunchLink);
    });
    void this.connectFromAvailableSession();
  }

  protected openLocalEvidence(): void {
    this.returnFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : undefined;
    this.showLocalEvidence.set(true);
  }

  protected closeLocalEvidence(): void {
    this.showLocalEvidence.set(false);
    queueMicrotask(() => this.returnFocus?.focus());
  }

  private async connectFromAvailableSession(): Promise<void> {
    const generation = ++this.sessionGeneration;
    const token = consumeLaunchToken(window.location, window.history);
    const recover =
      token === undefined
        ? () => this.local.restoreBrowserSession()
        : () => this.local.connect(token);
    for (let attempt = 0; attempt < 2; attempt++) {
      if (generation !== this.sessionGeneration) return;
      try {
        const evidence = await recover();
        if (generation !== this.sessionGeneration || evidence === undefined) return;
        const experiment = new URLSearchParams(window.location.search).get('experiment');
        if (experiment) {
          try {
            const run = await this.local.loadExperimentRun(experiment);
            if (generation !== this.sessionGeneration) return;
            this.debuggerStore.loadRun(run);
          } catch {
            if (generation !== this.sessionGeneration) return;
            this.local.error.set(
              'The requested experiment replay could not be verified. Return to experiments and inspect its status.',
            );
          }
        } else {
          const runId = new URLSearchParams(window.location.search).get('run');
          if (runId) {
            try {
              const run = await this.local.loadRun(runId);
              if (generation !== this.sessionGeneration) return;
              this.debuggerStore.loadRun(run);
            } catch {
              if (generation !== this.sessionGeneration) return;
              this.local.error.set(
                'The requested planning replay could not be verified. Select another retained replay from Investigate.',
              );
            }
          } else if (evidence.initialRun) this.debuggerStore.loadRun(evidence.initialRun);
        }
        this.showLocalEvidence.set(false);
        return;
      } catch (error: unknown) {
        if (generation !== this.sessionGeneration) return;
        if (!(error instanceof TypeError) || attempt === 1) {
          // A public clone is useful without the loopback API. Only surface the
          // connection panel automatically when an explicit launch token fails;
          // session recovery remains a quiet, best-effort enhancement.
          if (token !== undefined) this.showLocalEvidence.set(true);
          return;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 250));
      }
    }
  }
}
