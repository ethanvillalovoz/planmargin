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
    const token =
      consumeLaunchToken(window.location, window.history) ?? this.local.restoreSessionToken();
    if (token === undefined) return;
    try {
      const evidence = await this.local.connect(token);
      this.debuggerStore.loadRun(evidence.initialRun);
    } catch {
      this.showLocalEvidence.set(true);
    }
  }
}
