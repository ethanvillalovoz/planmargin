import { Injectable } from '@angular/core';
import { DebuggerRun, ExportedView } from './debugger.types';

export function serializeView(
  run: DebuggerRun,
  selectedHypothesisId: string,
  timestepIndex: number,
  exportedAt: string,
): ExportedView {
  const hypothesis = run.hypotheses.find((candidate) => candidate.id === selectedHypothesisId);
  if (hypothesis === undefined) {
    throw new Error(`Unknown hypothesis: ${selectedHypothesisId}`);
  }
  if (
    !Number.isInteger(timestepIndex) ||
    timestepIndex < 0 ||
    timestepIndex >= hypothesis.metrics.length
  ) {
    throw new Error('Timestep is outside the run timeline');
  }
  return {
    schemaVersion: 'planmargin.debugger-view.v1',
    exportedAt,
    runId: run.runId,
    scenarioLabel: run.scenarioLabel,
    synthetic: true,
    selectedHypothesisId,
    timestepIndex,
    timeSeconds: hypothesis.metrics[timestepIndex].timeSeconds,
  };
}

@Injectable({ providedIn: 'root' })
export class ExportService {
  download(run: DebuggerRun, selectedHypothesisId: string, timestepIndex: number): void {
    const view = serializeView(run, selectedHypothesisId, timestepIndex, new Date().toISOString());
    const blob = new Blob([`${JSON.stringify(view, null, 2)}\n`], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${run.runId}-${selectedHypothesisId}-view.json`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
}
