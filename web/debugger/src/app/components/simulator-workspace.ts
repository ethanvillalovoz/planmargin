import {
  afterNextRender,
  ChangeDetectionStrategy,
  Component,
  inject,
  input,
  output,
} from '@angular/core';
import { NgIcon, provideIcons } from '@ng-icons/core';
import {
  phosphorCaretDown,
  phosphorCaretUp,
  phosphorCornersOut,
  phosphorCube,
  phosphorDotsNine,
  phosphorEye,
  phosphorPause,
  phosphorPath,
  phosphorPlay,
  phosphorSkipBack,
  phosphorSkipForward,
  phosphorSparkle,
  phosphorStack,
  phosphorUserFocus,
} from '@ng-icons/phosphor-icons/regular';
import { DebuggerStore } from '../debugger.store';
import { LocalEvidenceService } from '../local-evidence.service';
import { SensorMode, SimulatorStore } from '../simulator.store';
import { ScenarioAssistant } from './scenario-assistant';
import { SceneViewport } from './scene-viewport';
import { SensorViewport } from './sensor-viewport';

@Component({
  selector: 'app-simulator-workspace',
  imports: [NgIcon, ScenarioAssistant, SceneViewport, SensorViewport],
  providers: [
    provideIcons({
      phosphorCaretDown,
      phosphorCaretUp,
      phosphorCornersOut,
      phosphorCube,
      phosphorDotsNine,
      phosphorEye,
      phosphorPause,
      phosphorPath,
      phosphorPlay,
      phosphorSkipBack,
      phosphorSkipForward,
      phosphorSparkle,
      phosphorStack,
      phosphorUserFocus,
    }),
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="simulator-shell" [class.embedded]="embedded()">
      <header class="topbar">
        <div class="brand-lockup">
          <ng-icon name="phosphorStack" size="24" aria-hidden="true" />
          <strong>PlanMargin</strong>
        </div>

        <div class="scene-selector" aria-label="Current dataset scene">
          <span>{{
            !local.connected()
              ? local.state() === 'connecting'
                ? 'Verifying local evidence…'
                : 'No scene loaded'
              : simulator.sensorMode() === 'planning'
                ? debuggerStore.run().scenarioLabel
                : 'SF · segment 100239…'
          }}</span>
        </div>

        <div class="dataset-source">
          {{
            !local.connected()
              ? 'Authenticated local runtime'
              : simulator.sensorMode() === 'planning'
                ? 'WOMD Motion · sealed planning evidence'
                : 'WOD Perception · recorded sensor evidence'
          }}
        </div>

        <button
          type="button"
          class="sync-status"
          [class.connected]="local.connected()"
          [class.connecting]="local.state() === 'connecting'"
          (click)="connectRequested.emit()"
        >
          <i></i
          ><span>{{
            local.connected()
              ? simulator.sensorMode() === 'planning'
                ? 'Planning step ' + paddedTimelineIndex() + ' · local evidence'
                : 'Camera frame ' + paddedFrame() + ' · 10 Hz'
              : local.state() === 'connecting'
                ? 'Verifying local evidence…'
                : 'Open local workspace'
          }}</span>
        </button>

        <div class="topbar-actions">
          <button
            type="button"
            class="assistant-button"
            [class.active]="simulator.assistantOpen()"
            (click)="toggleAssistant()"
          >
            <ng-icon name="phosphorSparkle" size="15" />Ask analysis
          </button>
          <button
            type="button"
            class="run-button"
            [disabled]="simulator.stressStatus() === 'running'"
            (click)="runStressTest()"
          >
            @if (simulator.stressStatus() === 'running') {
              <span class="button-spinner"></span>Replaying closest case…
            } @else if (simulator.stressStatus() === 'complete') {
              <ng-icon name="phosphorPlay" size="15" />Replay again
            } @else {
              <ng-icon name="phosphorPlay" size="15" />Replay closest-margin case
            }
          </button>
        </div>
      </header>

      <main
        class="scene-stage"
        [class.sensor-stage]="simulator.sensorMode() !== 'planning'"
        [class.spatial-stage]="
          simulator.sensorMode() === 'reconstruction' || simulator.sensorMode() === 'lidar'
        "
      >
        @if (embedded() && local.connected() && simulator.sensorMode() === 'planning') {
          <section class="case-banner" aria-live="polite">
            <i [class.regression]="isCandidateRegression()"></i>
            <div>
              <strong>{{ workbenchDecisionTitle() }}</strong>
              <span>{{ workbenchDecisionSummary() }}</span>
            </div>
          </section>
        }
        @if (local.connected()) {
          @if (simulator.sensorMode() === 'planning') {
            <app-scene-viewport />
          } @else {
            <app-sensor-viewport (connectRequested)="connectRequested.emit()" />
          }
        } @else {
          <div class="empty-stage" aria-hidden="true"></div>
        }

        @if (
          local.connected() &&
          (simulator.sensorMode() === 'planning' || simulator.sensorMode() === 'camera')
        ) {
          <section
            class="scenario-controls"
            [class.collapsed]="!simulator.controlsOpen()"
            aria-labelledby="scenario-controls-title"
          >
            <header>
              <strong id="scenario-controls-title">{{ controlPanelTitle() }}</strong>
              <button
                type="button"
                [attr.aria-label]="
                  simulator.controlsOpen() ? 'Collapse controls' : 'Expand controls'
                "
                (click)="simulator.controlsOpen.update((value) => !value)"
              >
                <ng-icon
                  [name]="simulator.controlsOpen() ? 'phosphorCaretUp' : 'phosphorCaretDown'"
                  size="14"
                />
              </button>
            </header>
            @if (simulator.controlsOpen()) {
              @if (simulator.sensorMode() === 'planning') {
                <p class="evidence-boundary">
                  WOMD Motion experiment · independent of the Perception scene
                </p>
                <label class="field-label">Replay coverage</label>
                <div class="select-control">
                  <span>{{
                    debuggerStore.selectedHypothesis().label.replace('Validated ', '')
                  }}</span
                  ><small>1 replay</small>
                </div>
                <p class="replay-boundary">
                  @if (debuggerStore.selectedHypothesis().id === 'proposal-linked-counterfactual') {
                    Exact campaign link verified: this fresh re-execution matches the selected
                    proposal's sealed trajectory hashes, outcomes, and interaction metrics.
                  } @else if (
                    debuggerStore.selectedHypothesis().id === 'interactive-counterfactual'
                  ) {
                    Exact trajectories from your new local experiment. This run is separate from the
                    frozen campaign.
                  } @else {
                    This Stage-0 replay is separate from campaign proposals. Most proposal records
                    retain sealed hashes, outcomes, and metrics without their full paths.
                  }
                </p>
                <button type="button" class="review-records" (click)="evidenceRequested.emit()">
                  {{
                    debuggerStore.selectedHypothesis().id === 'interactive-counterfactual'
                      ? 'Return to experiments'
                      : 'Review candidate records'
                  }}
                </button>
                <button type="button" class="review-records" (click)="jumpToMinimum()">
                  Inspect minimum clearance
                </button>
                @if (debuggerStore.selectedHypothesis().behaviorEvents; as events) {
                  <p class="field-label">Observed behavior events</p>
                  @for (event of events; track event.step) {
                    <button
                      type="button"
                      class="review-records"
                      (click)="debuggerStore.seek(event.step)"
                    >
                      {{ event.timeSeconds.toFixed(1) }} s · {{ event.label }}
                    </button>
                  }
                }
                <label class="field-label">Recorded mutation</label>
                <div class="select-control">
                  <span>{{ mutationLabel() }}</span
                  ><small>read-only evidence</small>
                </div>
                <div class="delay-heading">
                  <span>Recorded onset</span
                  ><strong
                    >{{ debuggerStore.selectedHypothesis().onsetSeconds.toFixed(1) }} s</strong
                  >
                </div>
                <p class="evidence-boundary">
                  {{
                    debuggerStore.selectedHypothesis().behaviorBoundary ??
                      'Tested and reference show the changed scenario. Original tested shows the same tested planner before the change.'
                  }}
                </p>
                <dl class="live-metrics" aria-label="Current planning metrics">
                  <div>
                    <dt>Time</dt>
                    <dd>{{ debuggerStore.timeSeconds().toFixed(1) }} s</dd>
                  </div>
                  <div>
                    <dt>Separation</dt>
                    <dd
                      [class.risk]="(debuggerStore.metricSample().signedSeparationMeters ?? 1) <= 0"
                    >
                      {{
                        debuggerStore.metricSample().signedSeparationMeters === null
                          ? '—'
                          : debuggerStore.metricSample().signedSeparationMeters?.toFixed(2) + ' m'
                      }}
                    </dd>
                  </div>
                  <div>
                    <dt>TTC</dt>
                    <dd>{{ currentTtc() }}</dd>
                  </div>
                </dl>
                @if (debuggerStore.metricSample().signedSeparationMeters === null) {
                  <p class="evidence-boundary">
                    Recorded lead not observed at this frame. No separation or TTC measurement is
                    available.
                  </p>
                }
                @if (debuggerStore.selectedHypothesis().behaviorDecision) {
                  <p class="evidence-boundary">
                    Validity alone does not require progress. Inspect the behavior gates and
                    recovered distance in the experiment result.
                  </p>
                } @else {
                  <div class="controller-outcome">
                    <span
                      >{{ debuggerStore.selectedHypothesis().trajectoryLabels?.tested ?? 'Tested' }}
                      {{ debuggerStore.selectedHypothesis().controllerOutcome.tested }}</span
                    >
                    <span
                      >{{
                        debuggerStore.selectedHypothesis().trajectoryLabels?.reference ??
                          'Reference'
                      }}
                      {{ debuggerStore.selectedHypothesis().controllerOutcome.reference }}</span
                    >
                  </div>
                }
              } @else if (simulator.sensorMode() === 'camera') {
                <p class="evidence-boundary">
                  WOD Perception segment · native frame-specific labels
                </p>
                <div class="layer-heading">
                  <span>Camera annotation</span><small>WOD Perception</small>
                </div>
                <div class="layer-list">
                  <button
                    type="button"
                    [class.enabled]="simulator.layers().boxes"
                    (click)="simulator.toggleLayer('boxes')"
                  >
                    <span><i></i>Tracked 2D boxes</span
                    ><ng-icon name="phosphorUserFocus" size="15" />
                  </button>
                </div>
              }
            }
          </section>
        }

        <div class="view-controls">
          <div class="mode-switcher" role="tablist" aria-label="Sensor representation">
            <button
              type="button"
              role="tab"
              [class.active]="simulator.sensorMode() === 'planning'"
              [attr.aria-selected]="simulator.sensorMode() === 'planning'"
              [disabled]="!local.connected()"
              (click)="selectMode('planning')"
            >
              Planning
            </button>
            <button
              type="button"
              role="tab"
              [class.active]="simulator.sensorMode() === 'camera'"
              [attr.aria-selected]="simulator.sensorMode() === 'camera'"
              [disabled]="!local.connected() || !local.campaignAvailable()"
              [title]="local.campaignAvailable() ? 'Camera' : 'Requires the full sensor workspace'"
              (click)="selectMode('camera')"
            >
              Camera
            </button>
            <button
              type="button"
              role="tab"
              [class.active]="simulator.sensorMode() === 'reconstruction'"
              [attr.aria-selected]="simulator.sensorMode() === 'reconstruction'"
              [disabled]="!local.connected() || !local.campaignAvailable()"
              [title]="local.campaignAvailable() ? '3DGS' : 'Requires the full sensor workspace'"
              (click)="selectMode('reconstruction')"
            >
              3DGS
            </button>
            <button
              type="button"
              role="tab"
              [class.active]="simulator.sensorMode() === 'lidar'"
              [attr.aria-selected]="simulator.sensorMode() === 'lidar'"
              [disabled]="!local.connected() || !local.campaignAvailable()"
              [title]="local.campaignAvailable() ? 'LiDAR' : 'Requires the full sensor workspace'"
              (click)="selectMode('lidar')"
            >
              LiDAR
            </button>
          </div>
          <button
            type="button"
            class="fullscreen-button"
            aria-label="Enter fullscreen"
            (click)="toggleFullscreen()"
          >
            <ng-icon name="phosphorCornersOut" size="17" />
          </button>
        </div>

        @if (!embedded() && simulator.assistantOpen()) {
          <app-scenario-assistant class="assistant-panel" />
        }
      </main>

      <footer
        class="timeline"
        [class.spatial]="!local.connected() || !simulator.temporalPlaybackAvailable()"
      >
        @if (!local.connected()) {
          <div class="spatial-summary">
            <strong>{{
              local.state() === 'connecting'
                ? 'Verifying local evidence…'
                : 'No local evidence loaded'
            }}</strong>
            <span>{{
              local.state() === 'connecting'
                ? 'Checking seals and preparing the workbench.'
                : 'Launch the local workspace to inspect recorded data.'
            }}</span>
          </div>
          <div class="spatial-fact"><span>Runtime source</span><strong>Disconnected</strong></div>
          <p>PlanMargin does not substitute demo or synthetic data.</p>
        } @else if (simulator.temporalPlaybackAvailable()) {
          <div class="playback-controls">
            <button
              type="button"
              [disabled]="!simulator.temporalControlsEnabled()"
              [attr.aria-label]="
                simulator.temporalPlaybackAvailable()
                  ? simulator.playing()
                    ? 'Pause current evidence'
                    : 'Play current evidence'
                  : 'Playback is unavailable for this spatial asset'
              "
              [attr.title]="
                simulator.temporalPlaybackAvailable() ? null : 'Single-frame spatial asset'
              "
              (click)="simulator.togglePlayback()"
            >
              <ng-icon [name]="simulator.playing() ? 'phosphorPause' : 'phosphorPlay'" size="17" />
            </button>
            <button
              type="button"
              [attr.aria-label]="
                simulator.sensorMode() === 'planning'
                  ? 'Back one second in planning evidence'
                  : 'Back one second in camera video'
              "
              title="Back 1 second"
              [disabled]="!simulator.temporalControlsEnabled()"
              (click)="simulator.jumpSeconds(-1)"
            >
              <span class="jump-label">−1s</span>
            </button>
            <button
              type="button"
              [attr.aria-label]="
                simulator.sensorMode() === 'planning'
                  ? 'Forward one second in planning evidence'
                  : 'Forward one second in camera video'
              "
              title="Forward 1 second"
              [disabled]="!simulator.temporalControlsEnabled()"
              (click)="simulator.jumpSeconds(1)"
            >
              <span class="jump-label">+1s</span>
            </button>
          </div>
          @if (simulator.sensorMode() === 'planning') {
            <strong
              >Step {{ paddedTimelineIndex() }}
              <span
                >/ {{ simulator.timelineCount() }} ·
                {{ debuggerStore.timeSeconds().toFixed(1) }} s</span
              ></strong
            >
          } @else {
            <strong
              >Frame {{ paddedFrame() }} <span>/ {{ simulator.frameCount() }}</span></strong
            >
          }
          <div class="scrubber">
            <input
              type="range"
              min="0"
              [max]="simulator.timelineCount() - 1"
              step="1"
              [value]="simulator.timelineIndex()"
              [disabled]="!simulator.temporalControlsEnabled()"
              (input)="seekFrame($event)"
              aria-label="Evidence timeline"
            />
            <div class="scrubber-labels">
              <span>000</span><span>{{ midpointLabel() }}</span
              ><span>{{ finalTimelineLabel() }}</span>
            </div>
          </div>
          <button
            type="button"
            class="speed-button"
            [disabled]="!simulator.temporalControlsEnabled()"
            (click)="cycleSpeed()"
          >
            {{ simulator.playbackSpeed().toFixed(1) }}×
            <ng-icon name="phosphorCaretDown" size="12" />
          </button>
        } @else {
          <div class="spatial-summary">
            <strong>{{ spatialTitle() }}</strong>
            <span>Source frame {{ paddedFrame() }} · drag to orbit · scroll to zoom</span>
          </div>
          <div class="spatial-fact">
            <span>Temporal playback</span><strong>Not applicable</strong>
          </div>
          <p>This view is one real spatial asset—not a video frame disguised as 3D.</p>
        }
      </footer>
    </div>
  `,
  styles: `
    :host {
      display: block;
      width: 100%;
      min-width: 320px;
      height: 100dvh;
      min-height: 620px;
      overflow: hidden;
      background: #071018;
      color: #edf3f4;
    }
    button,
    input {
      font: inherit;
    }
    button {
      color: inherit;
    }
    .simulator-shell {
      display: grid;
      grid-template-rows: 70px minmax(0, 1fr) 88px;
      width: 100%;
      height: 100%;
    }
    .simulator-shell.embedded {
      grid-template-rows: minmax(0, 1fr) 88px;
      min-height: 100%;
      height: 100%;
    }
    .simulator-shell.embedded .topbar {
      display: none;
    }
    .topbar {
      position: relative;
      z-index: 30;
      display: grid;
      grid-template-columns: auto minmax(190px, auto) minmax(190px, 1fr) auto auto;
      align-items: center;
      min-width: 0;
      padding: 0 1rem;
      border-bottom: 1px solid #1a2a34;
      background: #071018;
    }
    .brand-lockup {
      display: flex;
      align-items: center;
      gap: 0.55rem;
      padding-right: 1.2rem;
      border-right: 1px solid #22313a;
    }
    .brand-lockup ng-icon {
      color: #35c5d3;
      transform: rotate(-8deg);
    }
    .brand-lockup strong {
      font-size: 1.03rem;
      letter-spacing: -0.035em;
    }
    .scene-selector {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-width: 0;
      gap: 0.7rem;
      padding: 0 1rem;
      color: #dce5e8;
      font-size: 0.69rem;
    }
    .scene-selector span {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .dataset-source {
      min-width: 0;
      color: #788a95;
      font-size: 0.62rem;
      text-align: center;
    }
    .sync-status {
      display: flex;
      align-items: center;
      gap: 0.45rem;
      padding: 0 0.8rem;
      border: 0;
      background: transparent;
      color: #8496a1;
      font-size: 0.62rem;
    }
    .sync-status i {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #ff725f;
    }
    .sync-status.connected i {
      background: #35c5d3;
      box-shadow: 0 0 0 3px rgb(53 197 211 / 10%);
    }
    .sync-status.connecting i {
      background: #f0a33b;
    }
    .topbar-actions {
      display: flex;
      align-items: center;
      gap: 0.55rem;
    }
    .topbar-actions button {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 38px;
      gap: 0.45rem;
      border-radius: 8px;
      font-size: 0.65rem;
      font-weight: 700;
    }
    .assistant-button {
      padding: 0 0.75rem;
      border: 1px solid #293944;
      background: #0b151d;
    }
    .assistant-button:hover {
      border-color: #536874;
    }
    .assistant-button.active {
      border-color: #35c5d3;
      background: #102831;
      color: #55d6e2;
    }
    .run-button {
      min-width: 138px;
      padding: 0 0.85rem;
      border: 1px solid #35c5d3;
      background: #35c5d3;
      color: #031015;
    }
    .run-button:disabled {
      cursor: wait;
      opacity: 0.7;
    }
    .button-spinner {
      width: 13px;
      height: 13px;
      border: 2px solid rgb(3 16 21 / 24%);
      border-top-color: #031015;
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
    }
    .scene-stage {
      position: relative;
      min-width: 0;
      min-height: 0;
      overflow: hidden;
    }
    .empty-stage {
      position: absolute;
      inset: 0;
      background:
        linear-gradient(rgb(10 24 33 / 88%), rgb(5 13 20 / 96%)),
        radial-gradient(circle at 32% 42%, rgb(53 197 211 / 12%), transparent 34%);
    }
    .case-banner {
      position: absolute;
      z-index: 13;
      top: 1rem;
      left: 50%;
      display: grid;
      grid-template-columns: 8px minmax(0, 1fr);
      align-items: start;
      width: min(520px, calc(100% - 590px));
      gap: 0.65rem;
      padding: 0.7rem 0.8rem;
      border: 1px solid rgb(132 155 168 / 27%);
      border-radius: 7px;
      background: rgb(5 13 20 / 94%);
      box-shadow: 0 12px 34px rgb(0 0 0 / 24%);
      backdrop-filter: blur(18px);
      transform: translateX(-50%);
    }
    .case-banner > i {
      width: 8px;
      height: 8px;
      margin-top: 0.23rem;
      border-radius: 50%;
      background: #f0a33b;
    }
    .case-banner > i.regression {
      background: #ff6b55;
    }
    .case-banner div {
      display: grid;
      gap: 0.2rem;
    }
    .case-banner strong {
      font-size: 0.72rem;
      letter-spacing: -0.015em;
    }
    .case-banner span {
      color: #8fa0aa;
      font-size: 0.59rem;
      line-height: 1.45;
    }
    .scenario-controls {
      position: absolute;
      z-index: 12;
      top: 1rem;
      left: 1rem;
      width: 240px;
      overflow: hidden;
      border: 1px solid rgb(132 155 168 / 27%);
      border-radius: 11px;
      background: rgb(5 13 20 / 93%);
      box-shadow: 0 16px 45px rgb(0 0 0 / 24%);
      backdrop-filter: blur(18px);
    }
    .scenario-controls.collapsed {
      width: 190px;
    }
    .sensor-stage .scenario-controls {
      top: 4rem;
    }
    .scenario-controls > header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 49px;
      padding: 0 0.85rem;
      border-bottom: 1px solid rgb(132 155 168 / 16%);
    }
    .scenario-controls header strong {
      font-size: 0.8rem;
    }
    .scenario-controls header button {
      display: grid;
      width: 28px;
      height: 28px;
      place-items: center;
      border: 0;
      background: transparent;
      color: #8fa0aa;
    }
    .evidence-boundary {
      margin: 0;
      padding: 0.65rem 0.8rem;
      border-bottom: 1px solid rgb(132 155 168 / 15%);
      color: #7f929d;
      font-size: 0.58rem;
      line-height: 1.45;
    }
    .replay-boundary {
      margin: 0.55rem 0.8rem 0;
      color: #8496a1;
      font-size: 0.57rem;
      line-height: 1.45;
    }
    .review-records {
      width: calc(100% - 1.6rem);
      min-height: 34px;
      margin: 0.55rem 0.8rem 0;
      border: 1px solid rgb(53 197 211 / 42%);
      border-radius: 6px;
      background: rgb(53 197 211 / 8%);
      color: #8be8ef;
      font-size: 0.59rem;
      font-weight: 700;
    }
    .review-records:hover {
      border-color: #35c5d3;
      background: rgb(53 197 211 / 14%);
    }
    .field-label {
      display: block;
      margin: 0.8rem 0.8rem 0.38rem;
      color: #8fa0aa;
      font-size: 0.64rem;
    }
    .select-control {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: calc(100% - 1.6rem);
      min-height: 36px;
      margin: 0 0.8rem;
      padding: 0 0.65rem;
      border: 1px solid rgb(132 155 168 / 24%);
      border-radius: 7px;
      background: rgb(255 255 255 / 2%);
      color: #dce5e8;
      font-size: 0.7rem;
    }
    .select-control small {
      flex: 0 0 auto;
      color: #71838e;
      font-size: 0.54rem;
      text-transform: uppercase;
      letter-spacing: 0.07em;
    }
    .select-control > span {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .delay-heading {
      display: flex;
      justify-content: space-between;
      gap: 0.6rem;
      margin: 0.9rem 0.8rem 0.35rem;
      color: #9bacb6;
      font-size: 0.65rem;
    }
    .delay-heading strong {
      color: #e6edef;
      font-weight: 700;
    }
    .live-metrics {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 1px;
      margin: 0;
      border-top: 1px solid rgb(132 155 168 / 15%);
      background: rgb(132 155 168 / 15%);
    }
    .live-metrics div {
      display: grid;
      gap: 0.22rem;
      padding: 0.65rem 0.5rem;
      background: rgb(5 13 20 / 96%);
      text-align: center;
    }
    .live-metrics dt {
      color: #71838e;
      font-size: 0.5rem;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }
    .live-metrics dd {
      margin: 0;
      color: #e4ecef;
      font-size: 0.64rem;
      font-variant-numeric: tabular-nums;
    }
    .live-metrics dd.risk {
      color: #ff806d;
    }
    .controller-outcome {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.35rem;
      padding: 0.65rem 0.8rem 0.75rem;
    }
    .controller-outcome span {
      padding: 0.35rem 0.25rem;
      border: 1px solid rgb(132 155 168 / 18%);
      border-radius: 5px;
      color: #9aabb5;
      font-size: 0.53rem;
      text-align: center;
      text-transform: capitalize;
    }
    .layer-heading {
      display: flex;
      justify-content: space-between;
      padding: 0.75rem 0.8rem 0.45rem;
      border-top: 1px solid rgb(132 155 168 / 15%);
      color: #899ba5;
      font-size: 0.64rem;
    }
    .layer-heading small {
      color: #94a7b2;
      font-size: 0.52rem;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .layer-list {
      padding: 0 0.45rem 0.5rem;
    }
    .layer-list button {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 100%;
      min-height: 36px;
      padding: 0 0.4rem;
      border: 0;
      border-radius: 6px;
      background: transparent;
      color: #60737f;
      font-size: 0.68rem;
    }
    .layer-list button:hover {
      background: rgb(255 255 255 / 4%);
    }
    .layer-list button.enabled {
      color: #dce5e8;
    }
    .layer-list button:disabled {
      cursor: not-allowed;
      opacity: 0.35;
    }
    .layer-list button span {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .layer-list button span i {
      display: block;
      width: 14px;
      height: 14px;
      border: 1px solid #3b4d58;
      border-radius: 3px;
    }
    .layer-list button.enabled span i {
      border-color: #35c5d3;
      background: #35c5d3;
      box-shadow: inset 0 0 0 3px #071018;
    }
    .view-controls {
      position: absolute;
      z-index: 13;
      top: 1rem;
      right: 1rem;
      display: flex;
      gap: 0.45rem;
    }
    .mode-switcher {
      display: grid;
      grid-template-columns: repeat(4, 62px);
      padding: 4px;
      border: 1px solid rgb(132 155 168 / 27%);
      border-radius: 9px;
      background: rgb(5 13 20 / 91%);
      backdrop-filter: blur(14px);
    }
    .mode-switcher button {
      min-height: 32px;
      border: 0;
      border-radius: 6px;
      background: transparent;
      color: #b4c0c6;
      font-size: 0.62rem;
    }
    .mode-switcher button.active {
      background: #123039;
      color: #44ced9;
    }
    .mode-switcher button:disabled {
      cursor: not-allowed;
      opacity: 0.4;
    }
    .fullscreen-button {
      display: grid;
      width: 41px;
      place-items: center;
      border: 1px solid rgb(132 155 168 / 27%);
      border-radius: 9px;
      background: rgb(5 13 20 / 91%);
      color: #bdc8cd;
    }
    .assistant-panel {
      position: absolute;
      z-index: 14;
      top: 5rem;
      right: 1rem;
      width: min(390px, calc(100% - 2rem));
      max-height: calc(100% - 6rem);
    }
    .timeline {
      position: relative;
      z-index: 25;
      display: grid;
      grid-template-columns: auto auto minmax(140px, 1fr) auto;
      align-items: center;
      gap: 1rem;
      padding: 0 1rem;
      border-top: 1px solid #1a2a34;
      background: #071018;
    }
    .timeline.spatial {
      grid-template-columns: minmax(260px, 1fr) auto minmax(260px, 1fr);
    }
    .spatial-summary {
      display: grid;
      gap: 0.25rem;
    }
    .spatial-summary strong {
      font-size: 0.72rem;
    }
    .spatial-summary span,
    .timeline.spatial > p,
    .spatial-fact span {
      color: #7c8e98;
      font-size: 0.58rem;
    }
    .spatial-fact {
      display: grid;
      min-width: 130px;
      gap: 0.2rem;
      padding-left: 1rem;
      border-left: 1px solid #263741;
    }
    .spatial-fact strong {
      color: #b7c4ca;
      font-size: 0.63rem;
    }
    .timeline.spatial > p {
      justify-self: end;
      margin: 0;
      max-width: 300px;
      line-height: 1.45;
      text-align: right;
    }
    .playback-controls {
      display: flex;
      gap: 0.45rem;
    }
    .playback-controls button {
      display: grid;
      width: 40px;
      height: 40px;
      place-items: center;
      border: 1px solid #263741;
      border-radius: 8px;
      background: transparent;
      color: #dce5e8;
    }
    .jump-label {
      font-size: 0.62rem;
      font-weight: 750;
      letter-spacing: -0.02em;
    }
    .playback-controls button:disabled,
    .speed-button:disabled,
    .scrubber input:disabled {
      cursor: not-allowed;
      opacity: 0.38;
    }
    .spatial-label {
      color: #dce5e8;
    }
    .timeline > strong {
      font-size: 0.66rem;
      white-space: nowrap;
    }
    .timeline > strong span {
      color: #7c8e98;
      font-weight: 500;
    }
    .scrubber {
      position: relative;
      min-width: 0;
      padding-top: 0.45rem;
    }
    .scrubber input {
      width: 100%;
      height: 24px;
      margin: 0;
      appearance: none;
      outline: 0;
      background: transparent;
      cursor: pointer;
    }
    .scrubber input::-webkit-slider-runnable-track {
      height: 2px;
      border-radius: 999px;
      background: #465660;
    }
    .scrubber input::-webkit-slider-thumb {
      position: relative;
      z-index: 4;
      width: 14px;
      height: 14px;
      appearance: none;
      border: 3px solid #35c5d3;
      border-radius: 50%;
      background: #071018;
      box-shadow: 0 0 0 4px rgb(53 197 211 / 15%);
    }
    .scrubber input::-moz-range-track {
      height: 2px;
      border: 0;
      border-radius: 999px;
      background: #465660;
    }
    .scrubber input::-moz-range-thumb {
      width: 14px;
      height: 14px;
      border: 3px solid #35c5d3;
      border-radius: 50%;
      background: #071018;
      box-shadow: 0 0 0 4px rgb(53 197 211 / 15%);
    }
    .scrubber-labels {
      display: flex;
      justify-content: space-between;
      margin-top: 0.45rem;
      color: #94a7b2;
      font-size: 0.625rem;
    }
    .speed-button {
      display: flex;
      align-items: center;
      justify-content: center;
      min-width: 82px;
      min-height: 40px;
      gap: 0.45rem;
      border: 1px solid #263741;
      border-radius: 8px;
      background: transparent;
      color: #dce5e8;
      font-size: 0.64rem;
    }
    @keyframes spin {
      to {
        transform: rotate(360deg);
      }
    }
    @media (max-width: 1180px) {
      .topbar {
        grid-template-columns: auto minmax(180px, 1fr) auto auto;
      }
      .dataset-source {
        display: none;
      }
      .assistant-panel {
        width: min(360px, calc(100% - 2rem));
      }
    }
    @media (max-width: 860px) {
      :host {
        min-height: 560px;
      }
      .simulator-shell {
        grid-template-rows: 58px minmax(0, 1fr) 76px;
      }
      .simulator-shell.embedded {
        grid-template-rows: minmax(0, 1fr) 76px;
      }
      .topbar {
        grid-template-columns: auto minmax(0, 1fr) auto;
        padding: 0 0.7rem;
      }
      .brand-lockup {
        padding-right: 0.7rem;
      }
      .brand-lockup strong,
      .sync-status,
      .assistant-button,
      .scene-selector {
        padding: 0 0.7rem;
      }
      .scene-selector {
        display: none;
      }
      .run-button {
        min-width: 40px;
        width: 40px;
        padding: 0;
        font-size: 0 !important;
      }
      .run-button ng-icon {
        display: block;
      }
      .scenario-controls {
        top: 4.65rem;
        left: 0.65rem;
        width: 220px;
      }
      .view-controls {
        top: 0.65rem;
        right: 0.65rem;
      }
      .mode-switcher {
        grid-template-columns: repeat(4, 52px);
      }
      .assistant-panel {
        top: 4.3rem;
        bottom: 0.65rem;
        right: 0.65rem;
        width: min(290px, calc(100vw - 1.3rem));
        max-height: calc(100% - 5rem);
      }
      .timeline {
        grid-template-columns: auto minmax(100px, 1fr) auto;
        gap: 0.6rem;
        padding: 0 0.65rem;
      }
      .timeline.spatial {
        grid-template-columns: minmax(0, 1fr) auto;
      }
      .timeline.spatial > p {
        display: none;
      }
      .timeline > strong {
        display: none;
      }
      .playback-controls button {
        width: 38px;
        height: 38px;
      }
    }
    @media (max-width: 560px) {
      .case-banner {
        top: 0.65rem;
        right: 0.65rem;
        left: 0.65rem;
        width: auto;
        transform: none;
      }
      .view-controls {
        top: 5.4rem;
      }
      .sensor-stage .view-controls {
        top: 3.2rem;
      }
      .scene-selector span {
        max-width: 130px;
      }
      .scenario-controls {
        top: auto;
        right: 0.65rem;
        bottom: 0.65rem;
        width: auto;
        max-height: min(248px, calc(100% - 10.45rem));
        overflow-y: auto;
        overscroll-behavior: contain;
      }
      .sensor-stage .scenario-controls {
        top: auto;
      }
      .scenario-controls.collapsed {
        right: auto;
        width: min(220px, calc(100vw - 1.3rem));
        max-height: none;
        overflow: hidden;
      }
      .scenario-controls > header {
        position: sticky;
        z-index: 1;
        top: 0;
        background: #050d14;
      }
      .scene-stage:not(.spatial-stage) .scenario-controls:not(.collapsed) + .view-controls {
        opacity: 0;
        pointer-events: none;
      }
    }
  `,
})
export class SimulatorWorkspace {
  protected readonly simulator = inject(SimulatorStore);
  protected readonly local = inject(LocalEvidenceService);
  protected readonly debuggerStore = inject(DebuggerStore);
  readonly connectRequested = output<void>();
  readonly evidenceRequested = output<void>();
  readonly modeChanged = output<SensorMode>();
  readonly embedded = input(false);

  constructor() {
    afterNextRender(() => {
      if (
        window.matchMedia('(max-width: 560px)').matches &&
        this.simulator.sensorMode() !== 'planning'
      ) {
        this.simulator.controlsOpen.set(false);
      }
    });
  }

  protected selectMode(mode: SensorMode): void {
    this.modeChanged.emit(mode);
    if (!this.local.connected()) {
      this.connectRequested.emit();
      return;
    }
    this.simulator.selectMode(mode);
  }

  protected runStressTest(): void {
    if (!this.local.connected()) {
      this.connectRequested.emit();
      return;
    }
    this.simulator.runStressTest();
  }

  protected toggleAssistant(): void {
    if (!this.local.connected()) {
      this.connectRequested.emit();
      return;
    }
    const opening = !this.simulator.assistantOpen();
    if (opening) this.simulator.selectMode('planning');
    this.simulator.assistantOpen.set(opening);
  }

  protected controlPanelTitle(): string {
    return {
      planning: 'Planning evidence',
      camera: 'Perception overlays',
      reconstruction: '3D reconstruction',
      lidar: 'LiDAR field',
    }[this.simulator.sensorMode()];
  }

  protected isCandidateRegression(): boolean {
    if (this.debuggerStore.selectedHypothesis().behaviorDecision) return false;
    const outcome = this.debuggerStore.selectedHypothesis().controllerOutcome;
    return outcome.tested === 'fails' && outcome.reference === 'succeeds';
  }

  protected workbenchDecisionTitle(): string {
    const behavior = this.debuggerStore.selectedHypothesis().behaviorDecision;
    if (behavior)
      return behavior === 'checks_passed' ? 'Behavior checks passed' : 'Behavior checks failed';
    const outcome = this.debuggerStore.selectedHypothesis().controllerOutcome;
    if (outcome.reference === 'fails') return 'Reference planner also fails';
    return outcome.tested === 'fails'
      ? 'Candidate planner regression'
      : 'Tested planner holds margin';
  }

  protected workbenchDecisionSummary(): string {
    if (this.debuggerStore.selectedHypothesis().behaviorDecision)
      return 'Compare primary baseline, unprotected command loss, and protection. Jump to observed events in the planning controls.';
    const outcome = this.debuggerStore.selectedHypothesis().controllerOutcome;
    if (outcome.reference === 'fails') {
      return 'The control baseline fails under the same change, so this case cannot isolate the tested planner.';
    }
    if (outcome.tested === 'fails') {
      return 'The tested planner fails while the reference planner succeeds under the same recorded scenario change.';
    }
    return this.debuggerStore.selectedHypothesis().supported
      ? 'The tested planner succeeds under this change. Review the experiment finding gates before drawing a safety conclusion.'
      : 'The tested planner succeeds. Empirical realism support has not passed, so this run cannot qualify a regression.';
  }

  protected mutationLabel(): string {
    return this.debuggerStore
      .selectedHypothesis()
      .mutationType.replaceAll('_', ' ')
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  protected currentTtc(): string {
    const ttc = this.debuggerStore.metricSample().longitudinalTtcSeconds;
    return ttc === null ? '—' : `${ttc.toFixed(2)} s`;
  }

  protected spatialTitle(): string {
    return this.simulator.sensorMode() === 'reconstruction'
      ? '3D Gaussian reconstruction'
      : 'Recorded LiDAR field';
  }

  protected seekFrame(event: Event): void {
    this.simulator.seekFrame(Number((event.target as HTMLInputElement).value));
  }
  protected jumpToMinimum(): void {
    const metrics = this.debuggerStore.selectedHypothesis().metrics;
    const index = metrics.reduce(
      (best, item, current) =>
        (item.signedSeparationMeters ?? Infinity) <
        (metrics[best].signedSeparationMeters ?? Infinity)
          ? current
          : best,
      0,
    );
    this.simulator.showPlanningFrame(index);
  }

  protected cycleSpeed(): void {
    const current = this.simulator.playbackSpeed();
    this.simulator.setPlaybackSpeed(current === 0.5 ? 1 : current === 1 ? 2 : 0.5);
  }

  protected async toggleFullscreen(): Promise<void> {
    if (document.fullscreenElement === null) await document.documentElement.requestFullscreen();
    else await document.exitFullscreen();
  }

  protected paddedFrame(): string {
    return this.simulator.frameIndex().toString().padStart(3, '0');
  }

  protected paddedTimelineIndex(): string {
    return this.simulator.timelineIndex().toString().padStart(3, '0');
  }

  protected midpointLabel(): string {
    return Math.floor((this.simulator.timelineCount() - 1) / 2)
      .toString()
      .padStart(3, '0');
  }

  protected finalTimelineLabel(): string {
    return Math.max(0, this.simulator.timelineCount() - 1)
      .toString()
      .padStart(3, '0');
  }
}
