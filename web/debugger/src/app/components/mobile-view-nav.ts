import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { DebuggerStore } from '../debugger.store';
import { MobileView } from '../debugger.types';

@Component({
  selector: 'app-mobile-view-nav',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <nav aria-label="Debugger view">
      @for (view of views; track view) {
        <button
          type="button"
          [class.active]="store.mobileView() === view"
          [attr.aria-pressed]="store.mobileView() === view"
          (click)="store.mobileView.set(view)"
        >
          {{ labels[view] }}
        </button>
      }
    </nav>
  `,
  styles: `
    :host {
      display: none;
      border-bottom: 1px solid var(--divider);
      background: var(--rail);
    }
    nav {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
    }
    button {
      min-height: 44px;
      border: 0;
      border-bottom: 2px solid transparent;
      background: transparent;
      color: var(--secondary);
      font: inherit;
      font-size: 0.82rem;
      font-weight: 600;
    }
    button.active {
      border-bottom-color: var(--tested);
      color: var(--primary);
    }
    @media (max-width: 760px) {
      :host {
        display: block;
      }
    }
  `,
})
export class MobileViewNav {
  protected readonly store = inject(DebuggerStore);
  protected readonly views: readonly MobileView[] = ['scene', 'evidence', 'metrics'];
  protected readonly labels: Record<MobileView, string> = {
    scene: 'Scene',
    evidence: 'Evidence',
    metrics: 'Metrics',
  };
}
