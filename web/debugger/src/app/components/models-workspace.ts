import { ChangeDetectionStrategy, Component, computed, input, output, signal } from '@angular/core';
import { MODEL_STUDIES, sourceLink } from '../model-studies';

@Component({
  selector: 'app-models-workspace',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="model-browser" aria-label="Model studies">
      <aside class="study-list">
        <header>
          <h2>Studies</h2>
          <span>{{ studies.length }} records</span>
        </header>
        <nav aria-label="Model study selection">
          @for (study of studies; track study.id) {
            <button
              type="button"
              [attr.aria-current]="selected().id === study.id ? 'true' : null"
              [class.selected]="selected().id === study.id"
              (click)="select(study.id)"
            >
              <strong>{{ study.title }}</strong
              ><span>{{ study.subtitle }}</span>
              <small [class.measured]="study.status === 'Measured'">{{ study.status }}</small>
            </button>
          }
        </nav>
        <p>Supporting research. These models do not drive the planning replay.</p>
      </aside>
      <article class="study-detail" aria-labelledby="study-title">
        <header class="study-heading">
          <div>
            <p>{{ selected().subtitle }}</p>
            <h2 id="study-title">{{ selected().title }}</h2>
          </div>
          <span class="decision" [class.measured]="selected().status === 'Measured'">{{
            selected().status
          }}</span>
        </header>
        <section class="finding">
          <h3>{{ selected().question }}</h3>
          <p>{{ selected().conclusion }}</p>
        </section>
        <div class="table-scroll">
          <table aria-label="Study comparison">
            <thead>
              <tr>
                @for (column of selected().columns; track column) {
                  <th scope="col">{{ column }}</th>
                }
              </tr>
            </thead>
            <tbody>
              @for (row of selected().rows; track row.label) {
                <tr>
                  <th scope="row">{{ row.label }}</th>
                  @for (value of row.values; track $index) {
                    <td>{{ value }}</td>
                  }
                </tr>
              }
            </tbody>
          </table>
        </div>
        <p class="measurement-context">{{ selected().context }}</p>
        <details class="gate-details">
          <summary>
            Qualification gates
            <span>{{ passedGates() }}/{{ selected().gates.length }} passed</span>
          </summary>
          <ul>
            @for (gate of selected().gates; track gate.label) {
              <li>
                <span>{{ gate.label }}</span
                ><strong [class.pass]="gate.passed">{{
                  gate.passed ? 'Passed' : 'Not passed'
                }}</strong>
              </li>
            }
          </ul>
        </details>
        <section class="reproduction" aria-labelledby="reproduce-title">
          <h3 id="reproduce-title">Inspect or reproduce</h3>
          <p>{{ selected().requirement }}</p>
          <div class="resources">
            <a [href]="sourceLink(selected().report)" target="_blank" rel="noopener noreferrer"
              >Open source report</a
            >
            <a [href]="sourceLink(selected().guide)" target="_blank" rel="noopener noreferrer"
              >Reproduction guide</a
            >
            @for (artifact of selected().artifacts ?? []; track artifact.url) {
              <a [href]="artifact.url" target="_blank" rel="noopener noreferrer">{{
                artifact.label
              }}</a>
            }
          </div>
          @if (selected().command; as command) {
            <details>
              <summary>
                {{ command.endsWith('--help') ? 'CLI options' : 'Training command' }}
              </summary>
              <pre><code>{{ command }}</code></pre>
              <button type="button" (click)="copy(command)">Copy command</button>
              <span class="copy-status" role="status">{{ copyStatus() }}</span>
            </details>
          }
        </section>
      </article>
    </section>
  `,
  styleUrl: './models-workspace.css',
})
export class ModelsWorkspace {
  readonly initialStudy = input('prediction');
  readonly studySelected = output<string>();
  protected readonly studies = MODEL_STUDIES;
  protected readonly sourceLink = sourceLink;
  private readonly selectedId = signal<string | undefined>(undefined);
  protected readonly selected = computed(
    () =>
      this.studies.find((study) => study.id === (this.selectedId() ?? this.initialStudy())) ??
      this.studies[0],
  );
  protected readonly passedGates = computed(
    () => this.selected().gates.filter((gate) => gate.passed).length,
  );
  protected readonly copyStatus = signal('');
  protected select(id: string): void {
    this.selectedId.set(id);
    this.studySelected.emit(id);
    this.copyStatus.set('');
    const url = new URL(window.location.href);
    url.searchParams.set('study', id);
    window.history.replaceState(null, '', url.pathname + url.search);
  }
  protected async copy(command: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(command);
      this.copyStatus.set('Copied');
    } catch {
      this.copyStatus.set('Clipboard unavailable. Select and copy the command above.');
    }
  }
}
