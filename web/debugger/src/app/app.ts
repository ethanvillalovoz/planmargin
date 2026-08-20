import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { LocalEvidencePanel } from './components/local-evidence-panel';
import { ProductShell } from './components/product-shell';

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
  private returnFocus: HTMLElement | undefined;

  protected openLocalEvidence(): void {
    this.returnFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : undefined;
    this.showLocalEvidence.set(true);
  }

  protected closeLocalEvidence(): void {
    this.showLocalEvidence.set(false);
    queueMicrotask(() => this.returnFocus?.focus());
  }
}
