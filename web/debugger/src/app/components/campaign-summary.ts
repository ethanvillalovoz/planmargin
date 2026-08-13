import {
  ChangeDetectionStrategy,
  Component,
  computed,
  HostListener,
  input,
  output,
} from '@angular/core';
import { CAMPAIGN_EVIDENCE, CampaignEvidence } from '../campaign-evidence';

@Component({
  selector: 'app-campaign-summary',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="backdrop" (click)="closeFromBackdrop($event)">
      <section
        class="sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="campaign-title"
        aria-describedby="campaign-scope"
      >
        <header>
          <div>
            <p>
              {{
                evidence().mode === 'real-local-redacted'
                  ? 'VERIFIED LOCAL CAMPAIGN'
                  : 'FROZEN DEVELOPMENT CAMPAIGN'
              }}
            </p>
            <h1 id="campaign-title">What the experiment established</h1>
          </div>
          <button
            type="button"
            aria-label="Close campaign results"
            autofocus
            (click)="close.emit()"
          >
            Close
          </button>
        </header>

        <div class="scale" aria-label="Campaign scale">
          <article>
            <strong>{{ evidence().cells }}</strong>
            <span>matched cells</span>
          </article>
          <article>
            <strong>{{ evidence().proposals.toLocaleString() }}</strong>
            <span>proposals</span>
          </article>
          <article>
            <strong>{{ evidence().physicalRollouts.toLocaleString() }}</strong>
            <span>physical rollouts</span>
          </article>
          <article>
            <strong>{{ evidence().rolloutSteps.toLocaleString() }}</strong>
            <span>Waymax steps</span>
          </article>
        </div>

        <div class="comparison">
          <div class="comparison-heading">
            <div>
              <p>ELIGIBLE PROPOSAL YIELD</p>
              <h2>Bayesian search preserved validity</h2>
            </div>
            <strong>+{{ validRateLiftPoints().toFixed(4) }} pp</strong>
          </div>
          <div class="method-row">
            <span>Random</span>
            <div class="track">
              <i class="random" [style.width.%]="evidence().methods.random.validRatePercent"></i>
            </div>
            <strong>{{ evidence().methods.random.validRatePercent.toFixed(4) }}%</strong>
          </div>
          <div class="method-row">
            <span>Bayesian</span>
            <div class="track">
              <i
                class="bayesian"
                [style.width.%]="evidence().methods.bayesian.validRatePercent"
              ></i>
            </div>
            <strong>{{ evidence().methods.bayesian.validRatePercent.toFixed(4) }}%</strong>
          </div>
          <p class="caption">
            Support-and-pipeline-valid proposals under equal 1,600-proposal method budgets.
          </p>
        </div>

        <div class="decisions">
          <article>
            <span>H1 · Efficiency</span>
            <strong class="neutral">{{ evidence().hypotheses.efficiency }}</strong>
            <p>No qualifying finding from either method.</p>
          </article>
          <article>
            <span>H2 · Minimality</span>
            <strong class="neutral">{{ evidence().hypotheses.minimality }}</strong>
            <p>No paired failure-inducing mutations.</p>
          </article>
          <article>
            <span>H3 · Validity</span>
            <strong class="positive">{{ evidence().hypotheses.validity }}</strong>
            <p>Passed the frozen noninferiority rule.</p>
          </article>
        </div>

        <div class="boundary" id="campaign-scope">
          <div>
            <p class="evidence-kicker">ENGINEERING EVIDENCE</p>
            <h2>Reconstructed, queryable, measured</h2>
            <ul>
              <li>Every cell replayed from sealed checkpoints</li>
              <li>DuckDB SQL reconciled the published aggregates</li>
              <li>
                C++20 geometry kernel measured at {{ evidence().nativeKernelSpeedupRange }} in
                isolation
              </li>
            </ul>
          </div>
          <div class="scope-note">
            <span>CLAIM BOUNDARY</span>
            <p>
              Ten training scenarios, five seeds, and no qualifying failures. No held-out
              comparative campaign ran. A legacy compatibility smoke accessed one validation record.
              This does not evaluate the production Waymo Driver.
            </p>
          </div>
        </div>
      </section>
    </div>
  `,
  styles: `
    :host {
      position: fixed;
      z-index: 100;
      inset: 0;
    }
    .backdrop {
      display: grid;
      min-height: 100%;
      place-items: center;
      padding: 1.5rem;
      overflow: auto;
      background: rgb(13 31 44 / 58%);
      backdrop-filter: blur(8px);
    }
    .sheet {
      width: min(960px, 100%);
      max-height: calc(100dvh - 3rem);
      overflow: auto;
      border: 1px solid var(--divider);
      border-radius: var(--radius);
      background: #fff;
      box-shadow: 0 30px 90px rgb(13 31 44 / 28%);
    }
    header {
      position: relative;
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 1.5rem;
      padding: 1.45rem 1.6rem 1.3rem;
      border-bottom: 1px solid var(--divider);
    }
    p,
    h1,
    h2 {
      margin: 0;
    }
    header p,
    .comparison-heading p,
    .evidence-kicker {
      margin-bottom: 0.42rem;
      color: var(--tested);
      font-size: 0.58rem;
      font-weight: 700;
      letter-spacing: 0.14em;
    }
    h1 {
      font-size: clamp(1.15rem, 2.5vw, 1.75rem);
      font-weight: 600;
      letter-spacing: -0.035em;
    }
    h2 {
      font-size: 0.92rem;
      font-weight: 600;
    }
    button {
      min-height: 34px;
      padding: 0 0.75rem;
      border: 1px solid var(--divider);
      border-radius: 2px;
      background: transparent;
      color: var(--primary);
      font: inherit;
      font-size: 0.66rem;
      font-weight: 650;
    }
    button:hover {
      border-color: var(--secondary);
    }
    .scale {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      border-bottom: 1px solid var(--divider);
    }
    .scale article {
      display: grid;
      gap: 0.25rem;
      padding: 1.25rem 1.5rem;
      border-right: 1px solid var(--divider);
    }
    .scale article:last-child {
      border-right: 0;
    }
    .scale strong {
      color: var(--primary);
      font-size: clamp(1.15rem, 2.4vw, 1.65rem);
      font-weight: 550;
      font-variant-numeric: tabular-nums;
      letter-spacing: -0.035em;
    }
    .scale span,
    .decisions span {
      color: var(--secondary);
      font-size: 0.62rem;
    }
    .comparison {
      overflow: hidden;
      padding: 1.4rem 1.6rem 1.2rem;
      border-bottom: 1px solid var(--divider);
    }
    .comparison-heading {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 1.15rem;
    }
    .comparison-heading > div {
      min-width: 0;
    }
    .comparison-heading > strong {
      color: var(--success);
      font-size: 1.15rem;
      font-weight: 550;
      font-variant-numeric: tabular-nums;
    }
    .method-row {
      display: grid;
      grid-template-columns: 72px minmax(0, 1fr) 88px;
      align-items: center;
      gap: 0.75rem;
      margin-top: 0.65rem;
      font-size: 0.7rem;
    }
    .method-row > span {
      color: var(--secondary);
    }
    .method-row > strong {
      text-align: right;
      font-weight: 550;
      font-variant-numeric: tabular-nums;
    }
    .track {
      height: 7px;
      background: #e8eef3;
    }
    .track i {
      display: block;
      height: 100%;
    }
    .track .random {
      background: var(--recorded);
    }
    .track .bayesian {
      background: var(--reference);
    }
    .caption {
      margin-top: 0.8rem;
      color: var(--secondary);
      font-size: 0.6rem;
    }
    .decisions {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      border-bottom: 1px solid var(--divider);
    }
    .decisions article {
      display: grid;
      gap: 0.35rem;
      padding: 1.15rem 1.5rem;
      border-right: 1px solid var(--divider);
    }
    .decisions article:last-child {
      border-right: 0;
    }
    .decisions strong {
      font-size: 0.78rem;
      font-weight: 600;
    }
    .decisions .neutral {
      color: #9a6b12;
    }
    .decisions .positive {
      color: var(--success);
    }
    .decisions p,
    .scope-note p,
    li {
      color: var(--secondary);
      font-size: 0.65rem;
      line-height: 1.55;
    }
    .boundary {
      display: grid;
      grid-template-columns: 1.35fr 1fr;
    }
    .boundary > div {
      padding: 1.35rem 1.6rem;
    }
    ul {
      display: grid;
      gap: 0.3rem;
      margin: 0.8rem 0 0;
      padding-left: 1.05rem;
    }
    .scope-note {
      border-left: 1px solid var(--divider);
      background: #fff5f1;
    }
    .scope-note span {
      color: var(--failure);
      font-size: 0.58rem;
      font-weight: 700;
      letter-spacing: 0.14em;
    }
    .scope-note p {
      margin: 0.65rem 0 0;
    }
    @media (max-width: 700px) {
      .backdrop {
        align-items: start;
        padding: 0;
      }
      .sheet {
        width: 100%;
        max-height: none;
        min-height: 100dvh;
        border: 0;
      }
      header,
      .comparison {
        padding-right: 1rem;
        padding-left: 1rem;
      }
      header {
        padding-right: 5rem;
      }
      header button {
        position: absolute;
        top: 1rem;
        right: 1rem;
      }
      .scale {
        grid-template-columns: 1fr 1fr;
      }
      .scale article:nth-child(2) {
        border-right: 0;
      }
      .scale article:nth-child(-n + 2) {
        border-bottom: 1px solid var(--divider);
      }
      .decisions,
      .boundary {
        grid-template-columns: 1fr;
      }
      .decisions article {
        border-right: 0;
        border-bottom: 1px solid var(--divider);
      }
      .decisions article:last-child {
        border-bottom: 0;
      }
      .scope-note {
        border-top: 1px solid var(--divider);
        border-left: 0;
      }
      .method-row {
        grid-template-columns: 62px minmax(0, 1fr) 78px;
      }
      .comparison-heading {
        align-items: flex-start;
        flex-direction: column;
        gap: 0.7rem;
      }
    }
  `,
})
export class CampaignSummary {
  readonly evidence = input<CampaignEvidence>(CAMPAIGN_EVIDENCE);
  protected readonly validRateLiftPoints = computed(
    () =>
      this.evidence().methods.bayesian.validRatePercent -
      this.evidence().methods.random.validRatePercent,
  );
  readonly close = output<void>();

  @HostListener('document:keydown.escape')
  protected closeFromEscape(): void {
    this.close.emit();
  }

  protected closeFromBackdrop(event: MouseEvent): void {
    if (event.target === event.currentTarget) this.close.emit();
  }
}
