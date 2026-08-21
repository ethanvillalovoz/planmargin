import {
  afterNextRender,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  HostListener,
  inject,
  output,
  viewChild,
} from '@angular/core';
import { DebuggerStore } from '../debugger.store';
import { LocalEvidenceService } from '../local-evidence.service';
import { SimulatorStore } from '../simulator.store';

@Component({
  selector: 'app-local-evidence-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="backdrop" (click)="closeFromBackdrop($event)">
      <section
        #panel
        class="panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="local-evidence-title"
        aria-describedby="local-evidence-boundary"
      >
        <header>
          <div>
            <h1 id="local-evidence-title">Local evidence</h1>
            <p id="local-evidence-boundary">
              Verified records stay on this machine. Access is retained only for this browser tab.
            </p>
          </div>
          <button
            #dialogClose
            type="button"
            aria-label="Close local evidence"
            (click)="close.emit()"
          >
            Close
          </button>
        </header>

        @if (!local.connected()) {
          <form (submit)="connect($event)">
            <label for="local-token">Manual session recovery</label>
            <p>
              <code>uv run --frozen planmargin-workbench</code> normally connects automatically.
              Paste the launcher's ephemeral session token here only if this browser was opened
              separately.
            </p>
            <input
              id="local-token"
              #tokenInput
              type="password"
              name="local-token"
              autocomplete="off"
              autocapitalize="none"
              spellcheck="false"
              minlength="16"
              required
              [disabled]="local.state() === 'connecting'"
            />
            @if (local.error()) {
              <p class="error" role="alert">{{ local.error() }}</p>
            }
            <div class="form-actions">
              <button type="button" (click)="close.emit()">Cancel</button>
              <button class="primary" type="submit" [disabled]="local.state() === 'connecting'">
                {{ local.state() === 'connecting' ? 'Verifying…' : 'Connect local evidence' }}
              </button>
            </div>
          </form>
        } @else {
          <div class="status">
            <span><i></i>Real local · verified</span>
            <button type="button" (click)="disconnect()">Disconnect</button>
          </div>

          @if (local.error()) {
            <p class="error connected-error" role="alert">{{ local.error() }}</p>
          }

          <section class="session-summary" aria-labelledby="session-ready-title">
            <div>
              <p>Authenticated loopback session</p>
              <h2 id="session-ready-title">The engineering workspace is ready.</h2>
              <span>
                Use Workbench for the retained planning replay, Sensors for recorded perception, and
                Evidence for the sealed counterfactual campaign.
              </span>
            </div>
            <dl>
              <div>
                <dt>Campaign evidence</dt>
                <dd>{{ local.campaign().proposals }} proposals</dd>
              </div>
              <div>
                <dt>Matched experiment cells</dt>
                <dd>{{ local.cells().length }} verified</dd>
              </div>
              <div>
                <dt>Planning replay</dt>
                <dd>{{ local.runs().length }} available</dd>
              </div>
              <div>
                <dt>Data handling</dt>
                <dd>Local only · no uploads</dd>
              </div>
            </dl>
            <div class="session-actions">
              <button class="primary" type="button" (click)="close.emit()">
                Continue to workbench
              </button>
            </div>
          </section>
        }
      </section>
    </div>
  `,
  styles: `
    .error {
      padding: 0.6rem 0.7rem;
      border-left: 2px solid var(--failure);
      border: 1px solid rgb(255 107 85 / 30%);
      background: #281716;
      color: #ff9b8c;
    }
    .connected-error {
      margin: 0.75rem 1.4rem 0;
    }
    .status {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 48px;
      padding: 0 1.4rem;
      border-bottom: 1px solid var(--divider);
      background: #0b201f;
      color: #76dfa0;
      font-size: 0.66rem;
    }
    .status span {
      display: flex;
      align-items: center;
      gap: 0.45rem;
    }
    .status i {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--success);
      box-shadow: 0 0 0 3px rgb(115 209 47 / 12%);
    }
    .session-summary {
      display: grid;
      width: min(720px, 100%);
      gap: 1.5rem;
      margin: 0 auto;
      padding: 2.5rem 1.5rem;
    }
    .session-summary > div:first-child {
      display: grid;
      gap: 0.45rem;
    }
    .session-summary p {
      color: var(--reference);
      font-size: 0.58rem;
      font-weight: 750;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }
    .session-summary h2 {
      margin: 0;
      font-size: 1.35rem;
      letter-spacing: -0.03em;
    }
    .session-summary > div > span {
      color: var(--secondary);
      font-size: 0.7rem;
      line-height: 1.6;
    }
    .session-summary dl {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      margin: 0;
      border: 1px solid var(--divider);
    }
    .session-summary dl div {
      display: grid;
      gap: 0.25rem;
      padding: 1rem;
      border-right: 1px solid var(--divider);
      border-bottom: 1px solid var(--divider);
    }
    .session-summary dl div:nth-child(2n) {
      border-right: 0;
    }
    .session-summary dl div:nth-last-child(-n + 2) {
      border-bottom: 0;
    }
    .session-summary dt {
      color: var(--secondary);
      font-size: 0.6rem;
    }
    .session-summary dd {
      margin: 0;
      font-size: 0.76rem;
      font-weight: 650;
    }
    .session-actions {
      display: flex;
      justify-content: flex-end;
    }
    @media (max-width: 760px) {
      .session-summary dl {
        grid-template-columns: 1fr;
      }
      .session-summary dl div {
        border-right: 0;
      }
      .session-summary dl div:nth-last-child(2) {
        border-bottom: 1px solid var(--divider);
      }
    }
  `,
})
export class LocalEvidencePanel {
  protected readonly local = inject(LocalEvidenceService);
  protected readonly store = inject(DebuggerStore);
  protected readonly simulator = inject(SimulatorStore);
  readonly close = output<void>();
  private readonly panel = viewChild.required<ElementRef<HTMLElement>>('panel');
  private readonly tokenInput = viewChild<ElementRef<HTMLInputElement>>('tokenInput');
  private readonly dialogClose = viewChild.required<ElementRef<HTMLButtonElement>>('dialogClose');

  constructor() {
    afterNextRender(() => {
      (this.tokenInput()?.nativeElement ?? this.dialogClose().nativeElement).focus();
    });
  }

  protected async connect(event: Event): Promise<void> {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement;
    const input = form.elements.namedItem('local-token') as HTMLInputElement;
    try {
      const evidence = await this.local.connect(input.value);
      input.value = '';
      this.store.loadRun(evidence.initialRun);
      this.close.emit();
    } catch {
      input.value = '';
    }
  }

  protected disconnect(): void {
    // Return to the recorded camera before removing the planning run. This
    // prevents planning-only computed state from reading a run that no longer
    // exists during the same change-detection turn.
    this.simulator.selectMode('camera');
    this.local.disconnect();
    this.store.clearRun();
  }

  @HostListener('document:keydown', ['$event'])
  protected handleDialogKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      this.close.emit();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = Array.from(
      this.panel().nativeElement.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    ).filter((element) => element.getClientRects().length > 0);
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable.at(-1)!;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  protected closeFromBackdrop(event: MouseEvent): void {
    if (event.target === event.currentTarget) this.close.emit();
  }
}
