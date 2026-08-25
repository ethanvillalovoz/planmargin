import { Injectable } from '@angular/core';
import { CampaignEvidence } from './campaign-evidence';
import { LocalCell, LocalProposal } from './local-evidence.types';

export interface InvestigationReportInput {
  readonly campaign: CampaignEvidence;
  readonly cell: LocalCell;
  readonly proposal: LocalProposal;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function gateReason(proposal: LocalProposal): string {
  if (proposal.attemptStatus === 'mutation_rejected') return 'Scenario edit was invalid';
  if (proposal.attemptStatus === 'scenario_rejected') return 'Closed-loop replay became invalid';
  if (!proposal.pipelinePasses) return 'Replay was not reproducible';
  if (proposal.supportPasses !== true) return 'Change was outside recorded behavior';
  if (!proposal.referencePasses) return 'Reference planner failed';
  if (proposal.testedMutatedFailure !== true) return 'Tested planner still succeeds';
  return proposal.policySpecificAvoidableFailure
    ? 'Candidate planner regression'
    : 'Regression contract not met';
}

function proximityLabel(value: number): string {
  if (value <= 0) return 'Minimum clearance unavailable';
  const clearanceMeters = Math.max(1 / value - 1, 0);
  if (clearanceMeters < 0.005) return 'Contact boundary reached';
  return `${clearanceMeters.toFixed(2)} m minimum clearance`;
}

function changeSizeLabel(value: number): string {
  const boundedEditPercent = Math.min(Math.max((1 - value) * 100, 0), 100);
  const size = boundedEditPercent <= 20 ? 'Small' : boundedEditPercent <= 50 ? 'Moderate' : 'Large';
  return `${size} edit · ${boundedEditPercent.toFixed(0)}% of bounded range`;
}

function outcomeLabel(value: boolean | null, failureQuestion: boolean): string {
  if (value === null) return 'Not evaluated';
  if (failureQuestion) return value ? 'Failed' : 'Succeeded';
  return value ? 'Succeeded' : 'Failed';
}

@Injectable({ providedIn: 'root' })
export class InvestigationReportService {
  async html(input: InvestigationReportInput): Promise<string> {
    const evidence = JSON.stringify({
      campaign: input.campaign.campaignId,
      cell: input.cell.cellId,
      method: input.cell.method,
      seed: input.cell.seed,
      selectionOrder: input.cell.selectionOrder,
      proposal: input.proposal,
    });
    const digest = Array.from(
      new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(evidence))),
    )
      .map((value) => value.toString(16).padStart(2, '0'))
      .join('');
    const reason = gateReason(input.proposal);
    return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>PlanMargin investigation report</title><style>
body{max-width:780px;margin:48px auto;padding:0 24px;color:#102632;font:15px/1.55 Inter,system-ui,sans-serif}
h1{font-size:30px;letter-spacing:-.04em}h2{margin-top:32px;font-size:17px}dl{display:grid;grid-template-columns:1fr 1fr;gap:12px}
div{padding:12px;border-bottom:1px solid #dbe5e9}dt{color:#607683;font-size:12px}dd{margin:4px 0 0;font-weight:650}small{display:block;margin-top:3px;color:#718793;font-size:11px;font-weight:450}
.decision{padding:18px;border-left:4px solid #ff6b55;background:#f5f9fa}code{word-break:break-all;font-size:11px;color:#526872}
</style></head><body>
<h1>PlanMargin investigation report</h1>
<p>Privacy-reduced evidence from the immutable v1 development campaign. This report does not evaluate the production Waymo Driver.</p>
<section class="decision"><strong>${escapeHtml(reason)}</strong><br>Proposal ${input.proposal.proposalNumber} in ${escapeHtml(input.cell.method)} cell ${input.cell.selectionOrder}, seed ${input.cell.seed}.</section>
<h2>Scenario change</h2><dl>
<div><dt>Lead braking onset shift</dt><dd>${input.proposal.brakingOnsetOffsetSeconds >= 0 ? '+' : '−'}${Math.abs(input.proposal.brakingOnsetOffsetSeconds).toFixed(1)} s</dd></div>
<div><dt>Lead speed scale</dt><dd>${input.proposal.speedMultiplier.toFixed(2)}×</dd></div>
</dl>
<h2>Planner decision</h2><dl>
<div><dt>Tested planner</dt><dd>${outcomeLabel(input.proposal.testedMutatedFailure, true)}</dd></div>
<div><dt>Reference planner</dt><dd>${outcomeLabel(input.proposal.referenceMutatedSuccess, false)}</dd></div>
<div><dt>Safety result</dt><dd>${proximityLabel(input.proposal.criticality)}<small>derived from the measured minimum signed separation; criticality ${input.proposal.criticality.toFixed(4)}</small></dd></div>
<div><dt>Change size</dt><dd>${changeSizeLabel(input.proposal.minimality)}<small>derived from the normalized distance to the recorded scenario; minimality ${input.proposal.minimality.toFixed(4)}</small></dd></div>
<div><dt>Recorded precedent</dt><dd>${input.proposal.supportPasses === true ? 'Seen in recorded behavior' : input.proposal.empiricalSupportProbability === null ? 'Not evaluated' : 'Outside recorded behavior'}<small>support probability ${input.proposal.empiricalSupportProbability?.toFixed(4) ?? 'not evaluated'}; pass threshold 0.05</small></dd></div>
<div><dt>Normalized edit distance</dt><dd>${input.proposal.normalizedMutationDistance.toFixed(4)}<small>distance from the unchanged scenario</small></dd></div>
</dl>
<h2>Campaign boundary</h2><p>${input.campaign.proposals.toLocaleString()} proposals and ${input.campaign.physicalRollouts.toLocaleString()} physical rollouts produced zero qualifying findings. Bayesian search increased eligible-proposal yield by ${(input.campaign.methods.bayesian.validRatePercent - input.campaign.methods.random.validRatePercent).toFixed(4)} percentage points. H1 and H2 remained untestable; H3 was supported.</p>
<h2>Integrity</h2><p>SHA-256 over the canonical local report payload:</p><code>${digest}</code>
</body></html>`;
  }

  async download(input: InvestigationReportInput): Promise<void> {
    const html = await this.html(input);
    const url = URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `planmargin-${input.cell.method}-${input.cell.selectionOrder}-${input.cell.seed}-p${input.proposal.proposalNumber}.html`;
    anchor.style.display = 'none';
    document.body.append(anchor);
    try {
      anchor.click();
      // Keep the object URL alive through the browser's next task. Detached anchors
      // and immediate revocation can silently cancel downloads in embedded browsers.
      await new Promise<void>((resolve) => setTimeout(resolve, 0));
    } finally {
      anchor.remove();
      URL.revokeObjectURL(url);
    }
  }
}
