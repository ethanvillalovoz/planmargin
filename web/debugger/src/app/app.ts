import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
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

  constructor() {
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
    const token = consumeLaunchToken(window.location, window.history);
    const recover =
      token === undefined
        ? () => this.local.restoreBrowserSession()
        : () => this.local.connect(token);
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const evidence = await recover();
        if (evidence === undefined) return;
        this.debuggerStore.loadRun(evidence.initialRun);
        return;
      } catch (error: unknown) {
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
