import { ChangeDetectionStrategy, Component, inject, output } from '@angular/core';
import { DebuggerStore } from '../debugger.store';

export type OverviewDestination = 'scenario' | 'assistant' | 'gaussian';

@Component({
  selector: 'app-project-overview',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="overview" aria-labelledby="overview-title">
      <div class="overview-hero">
        <div class="eyebrow"><i></i>Planner evaluation workbench</div>
        <h1 id="overview-title">Find the smallest realistic change that flips the outcome.</h1>
        <p>
          PlanMargin searches for behaviorally plausible scene mutations where the tested planner fails
          and a reference planner succeeds—then preserves the evidence boundary around that result.
        </p>
        <div class="hero-actions">
          <button type="button" class="primary" (click)="workspaceRequested.emit('scenario')">Open Scenario Lab <span>→</span></button>
          <button type="button" (click)="workspaceRequested.emit('assistant')">Ask the evidence <span>✦</span></button>
        </div>
      </div>

      <div class="outcome-card">
        <div class="outcome-head"><span>Selected evidence case</span><strong>{{ store.selectedHypothesis().label }}</strong></div>
        <div class="outcome-compare">
          <article class="tested"><span>Tested planner</span><strong>{{ outcomeLabel('tested') }}</strong><p>{{ outcomeDetail('tested') }}</p></article>
          <div aria-hidden="true">≠</div>
          <article class="reference"><span>Reference planner</span><strong>{{ outcomeLabel('reference') }}</strong><p>{{ outcomeDetail('reference') }}</p></article>
        </div>
        <footer><span><i></i>Support + pipeline valid</span><span>Deterministic replay</span></footer>
      </div>

      <section class="workflow" aria-labelledby="workflow-title">
        <div class="section-heading">
          <div><span>How to read this tool</span><h2 id="workflow-title">One evidence path, four workspaces</h2></div>
          <small>Every claim remains traceable to sealed artifacts.</small>
        </div>
        <div class="workflow-grid">
          <button type="button" (click)="workspaceRequested.emit('scenario')">
            <span class="step">01</span><i class="scenario-icon">⌁</i><h3>Reproduce</h3><p>Replay the tested, reference, and recorded trajectories at the same timestep.</p><strong>Scenario Lab →</strong>
          </button>
          <button type="button" (click)="campaignRequested.emit()">
            <span class="step">02</span><i class="search-icon">◎</i><h3>Compare search</h3><p>Audit Bayesian and random search using matched physical-rollout budgets.</p><strong>Campaign evidence →</strong>
          </button>
          <button type="button" (click)="workspaceRequested.emit('assistant')">
            <span class="step">03</span><i class="assistant-icon">✦</i><h3>Interrogate</h3><p>Ask five bounded questions over verified facts and source seals.</p><strong>Evidence Assistant →</strong>
          </button>
          <button type="button" (click)="workspaceRequested.emit('gaussian')">
            <span class="step">04</span><i class="gaussian-icon">⠿</i><h3>Inspect geometry</h3><p>Explore the local LiDAR Gaussian field and see why its integration gate failed.</p><strong>Gaussian Field →</strong>
          </button>
        </div>
      </section>

      <section class="pipeline" aria-label="Evidence pipeline">
        <div><span>01</span><strong>Waymo scenario</strong><small>Privacy-reduced input</small></div><i>→</i>
        <div><span>02</span><strong>Beam features</strong><small>Reproducible pipeline</small></div><i>→</i>
        <div><span>03</span><strong>Matched search</strong><small>Budget-aware comparison</small></div><i>→</i>
        <div><span>04</span><strong>Sealed evidence</strong><small>SHA-256 provenance</small></div>
      </section>
    </section>
  `,
  styles: `
    :host { display: block; min-height: 100%; }
    button { color: inherit; font: inherit; }
    .overview { min-height: 100%; padding: clamp(1.5rem,4vw,3.5rem); background: linear-gradient(145deg,#fff 0%,#fff 58%,#f5f8fb 100%); }
    .overview-hero { max-width: 820px; }
    .eyebrow { display: flex; align-items: center; gap: .5rem; color: #1558ba; font-size: .7rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
    .eyebrow i { width: 24px; height: 2px; background: var(--reference); }
    h1 { max-width: 820px; margin: .75rem 0 0; font-size: clamp(2rem,4.8vw,4rem); line-height: 1.02; letter-spacing: -.06em; }
    .overview-hero > p { max-width: 760px; margin: 1.2rem 0 0; color: var(--secondary); font-size: clamp(.9rem,1.6vw,1.08rem); line-height: 1.65; }
    .hero-actions { display: flex; gap: .7rem; margin-top: 1.5rem; }
    .hero-actions button { min-height: 40px; padding: 0 1rem; border: 1px solid var(--divider-strong); border-radius: 9px; background: #fff; font-size: .73rem; font-weight: 750; }
    .hero-actions button span { margin-left: .4rem; }
    .hero-actions .primary { border-color: #12324a; background: #12324a; color: #fff; }
    .outcome-card { max-width: 980px; margin-top: 2.6rem; overflow: hidden; border: 1px solid var(--divider); border-radius: var(--radius); background: #fff; box-shadow: var(--shadow-sm); }
    .outcome-head, .outcome-card footer { display: flex; align-items: center; justify-content: space-between; padding: .75rem 1rem; }
    .outcome-head { border-bottom: 1px solid var(--divider); font-size: .68rem; }
    .outcome-head span { color: var(--secondary); } .outcome-head strong { color: #a33a1f; }
    .outcome-compare { display: grid; grid-template-columns: 1fr 40px 1fr; align-items: center; padding: 1.25rem; }
    .outcome-compare > div { color: var(--tertiary); text-align: center; }
    .outcome-compare article { padding: .9rem 1rem; border-radius: var(--radius-sm); }
    .outcome-compare .tested { background: #fff3ef; } .outcome-compare .reference { background: #eaf8fb; }
    .outcome-compare span, .outcome-compare strong, .outcome-compare p { display: block; margin: 0; }
    .outcome-compare span { color: var(--secondary); font-size: .65rem; font-weight: 700; }
    .outcome-compare strong { margin-top: .25rem; font-size: 1.25rem; }
    .tested strong { color: #ba4328; } .reference strong { color: #087b8c; }
    .outcome-compare p { margin-top: .3rem; color: var(--secondary); font-size: .67rem; }
    .outcome-card footer { border-top: 1px solid var(--divider); background: var(--surface-subtle); color: var(--secondary); font-size: .64rem; }
    .outcome-card footer span:first-child { display: flex; align-items: center; gap: .4rem; color: #26721f; }
    .outcome-card footer i { width: 6px; height: 6px; border-radius: 50%; background: var(--accent-green); }
    .workflow { max-width: 1180px; margin-top: 3rem; }
    .section-heading { display: flex; align-items: end; justify-content: space-between; gap: 1rem; }
    .section-heading span { color: #1558ba; font-size: .65rem; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; }
    .section-heading h2 { margin: .3rem 0 0; font-size: 1.35rem; letter-spacing: -.035em; }
    .section-heading small { color: var(--secondary); font-size: .68rem; }
    .workflow-grid { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: .8rem; margin-top: 1rem; }
    .workflow-grid button { position: relative; min-height: 220px; padding: 1rem; border: 1px solid var(--divider); border-radius: var(--radius-sm); background: #fff; text-align: left; transition: transform .16s ease, box-shadow .16s ease; }
    .workflow-grid button:hover { transform: translateY(-2px); box-shadow: var(--shadow); }
    .workflow-grid .step { position: absolute; top: 1rem; right: 1rem; color: var(--tertiary); font-size: .62rem; font-weight: 800; }
    .workflow-grid button > i { display: grid; width: 38px; height: 38px; place-items: center; border-radius: 11px; font-size: 1.2rem; font-style: normal; }
    .scenario-icon { background: #fff0eb; color: #c3482d; } .search-icon { background: #e9f8fb; color: #087b8c; } .assistant-icon { background: #f0edff; color: #6855c0; } .gaussian-icon { background: #eef7dc; color: #5f7f18; }
    .workflow-grid h3 { margin: 1rem 0 0; font-size: .88rem; }
    .workflow-grid p { min-height: 60px; margin: .45rem 0 .9rem; color: var(--secondary); font-size: .7rem; line-height: 1.55; }
    .workflow-grid button > strong { color: #1558ba; font-size: .66rem; }
    .pipeline { display: grid; grid-template-columns: 1fr auto 1fr auto 1fr auto 1fr; align-items: center; max-width: 1180px; margin-top: 2rem; padding: 1rem; border: 1px solid var(--divider); border-radius: var(--radius-sm); background: #f8fafc; }
    .pipeline > div { display: grid; grid-template-columns: 28px 1fr; column-gap: .55rem; }
    .pipeline > div span { grid-row: 1/3; display: grid; width: 26px; height: 26px; place-items: center; border-radius: 50%; background: #e8eef4; color: #466071; font-size: .55rem; font-weight: 800; }
    .pipeline strong { font-size: .68rem; } .pipeline small { color: var(--secondary); font-size: .59rem; }
    .pipeline > i { color: var(--tertiary); font-style: normal; }
    @media (max-width: 1080px) { .workflow-grid { grid-template-columns: repeat(2,minmax(0,1fr)); } }
    @media (max-width: 760px) {
      .overview { padding: 1.35rem 1rem 2rem; } h1 { font-size: 2.25rem; }
      .hero-actions { flex-direction: column; }
      .outcome-compare { grid-template-columns: 1fr; gap: .5rem; } .outcome-compare > div { display: none; }
      .workflow-grid { grid-template-columns: 1fr; } .workflow-grid button { min-height: 190px; }
      .pipeline { grid-template-columns: 1fr; gap: .65rem; } .pipeline > i { display: none; }
    }
  `,
})
export class ProjectOverview {
  protected readonly store = inject(DebuggerStore);
  readonly workspaceRequested = output<OverviewDestination>();
  readonly campaignRequested = output<void>();

  protected outcomeLabel(role: 'tested' | 'reference'): string {
    return this.store.selectedHypothesis().controllerOutcome[role] === 'fails' ? 'Fails' : 'Succeeds';
  }

  protected outcomeDetail(role: 'tested' | 'reference'): string {
    return this.store.selectedHypothesis().controllerOutcome[role] === 'fails'
      ? 'Crosses the planner-defined failure boundary.'
      : 'Remains within the planner-defined success boundary.';
  }
}
