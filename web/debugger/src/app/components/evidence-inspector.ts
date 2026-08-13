import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { DebuggerStore } from '../debugger.store';

@Component({
  selector: 'app-evidence-inspector',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header>
      <span>Evidence</span>
      <span class="qualifying">
        {{ store.run().synthetic ? 'Synthetic fixture' : 'Real local evidence' }}
      </span>
    </header>
    <section>
      <h2>Mutation</h2>
      <dl>
        <div>
          <dt>Type</dt>
          <dd>{{ mutationType() }}</dd>
        </div>
        @if (hasParameter('braking_onset_offset_s')) {
          <div>
            <dt>Onset offset</dt>
            <dd>{{ parameter('braking_onset_offset_s')!.toFixed(1) }} s</dd>
          </div>
        }
        @if (hasParameter('speed_multiplier')) {
          <div>
            <dt>Speed multiplier</dt>
            <dd>{{ parameter('speed_multiplier')!.toFixed(4) }}</dd>
          </div>
        }
        <div>
          <dt>{{ store.run().synthetic ? 'Speed' : 'Target initial speed' }}</dt>
          <dd>{{ store.selectedHypothesis().speedMetersPerSecond.toFixed(1) }} m/s</dd>
        </div>
      </dl>
    </section>
    <section>
      <h2>Validity</h2>
      <dl>
        <div>
          <dt>Supported{{ store.run().synthetic ? ' (fixture)' : '' }}</dt>
          <dd [class.pass]="store.selectedHypothesis().supported">
            {{ store.selectedHypothesis().supported ? 'Yes' : 'No' }}
          </dd>
        </div>
        <div>
          <dt>Deterministic</dt>
          <dd [class.pass]="store.selectedHypothesis().deterministic">
            {{ store.selectedHypothesis().deterministic ? 'Yes' : 'No' }}
          </dd>
        </div>
      </dl>
      <p class="checks">{{ store.selectedHypothesis().validationChecks.length }} checks verified</p>
    </section>
    <section>
      <h2>Controller outcomes</h2>
      <dl>
        <div>
          <dt>Tested</dt>
          <dd [class.fail]="store.selectedHypothesis().controllerOutcome.tested === 'fails'">
            {{ outcome(store.selectedHypothesis().controllerOutcome.tested) }}
          </dd>
        </div>
        <div>
          <dt>Reference</dt>
          <dd [class.fail]="store.selectedHypothesis().controllerOutcome.reference === 'fails'">
            {{ outcome(store.selectedHypothesis().controllerOutcome.reference) }}
          </dd>
        </div>
      </dl>
    </section>
    <section>
      <h2>Provenance</h2>
      <dl>
        <div>
          <dt>Source</dt>
          <dd>{{ sourceLabel() }}</dd>
        </div>
        <div>
          <dt>Run</dt>
          <dd>{{ store.run().runId }}</dd>
        </div>
      </dl>
    </section>
  `,
  styles: `
    :host {
      display: block;
      min-height: 0;
      overflow: auto;
      border-left: 1px solid var(--divider);
      background: var(--rail);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 48px;
      padding: 0 1rem;
      border-bottom: 1px solid var(--divider);
      color: var(--primary);
      font-size: 0.78rem;
      font-weight: 600;
    }
    .qualifying {
      color: var(--reference);
      font-size: 0.6rem;
      font-weight: 500;
    }
    section {
      padding: 1rem;
      border-bottom: 1px solid var(--divider);
    }
    h2 {
      margin: 0 0 0.75rem;
      color: var(--secondary);
      font-size: 0.64rem;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }
    dl {
      margin: 0;
    }
    dl div {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 0.75rem;
      padding: 0.32rem 0;
      font-size: 0.72rem;
    }
    dt {
      color: var(--secondary);
    }
    dd {
      margin: 0;
      color: var(--primary);
      text-align: right;
      font-variant-numeric: tabular-nums;
    }
    dd.pass {
      color: var(--success);
    }
    dd.fail {
      color: var(--failure);
    }
    .checks {
      margin: 0.7rem 0 0;
      padding: 0.45rem 0.55rem;
      border-left: 2px solid var(--success);
      background: #eff8ec;
      color: var(--success);
      font-size: 0.68rem;
    }
    @media (max-width: 760px) {
      :host {
        border-left: 0;
      }
      header {
        min-height: 52px;
      }
      section {
        padding: 1.15rem;
      }
      dl div {
        font-size: 0.82rem;
      }
    }
  `,
})
export class EvidenceInspector {
  protected readonly store = inject(DebuggerStore);

  protected outcome(value: 'fails' | 'succeeds'): string {
    return value === 'fails' ? 'Fails' : 'Succeeds';
  }

  protected sourceLabel(): string {
    return this.store.run().source === 'local-api'
      ? 'Authenticated local API'
      : this.store.run().source === 'local-file'
        ? 'Validated local file'
        : 'Bundled demo data';
  }

  protected parameter(name: string): number | undefined {
    return this.store.selectedHypothesis().mutationParameters[name];
  }

  protected hasParameter(name: string): boolean {
    return this.parameter(name) !== undefined;
  }

  protected mutationType(): string {
    return this.store.selectedHypothesis().mutationType.replaceAll('_', ' ');
  }
}
