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
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PlanMargin investigation report</title><style>
:root{color-scheme:light;font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-synthesis:none}
*{box-sizing:border-box}body{margin:0;background:#f4f6f3;color:#141b2d;font-size:15px;line-height:1.55}
.topbar{display:flex;align-items:center;justify-content:space-between;min-height:72px;padding:0 28px;border-bottom:1px solid #e3e7e3;background:#fff}
.brand{display:grid;gap:1px}.brand strong{font-size:15px;letter-spacing:-.03em}.brand span,.status{font-size:9px;font-weight:750;letter-spacing:.08em;text-transform:uppercase}
.brand span{color:#59636f}.status{padding:9px 12px;border-radius:999px;background:#e1f4e8;color:#276e49}
main{width:min(1040px,calc(100% - 32px));margin:34px auto 64px}.eyebrow{margin:0;color:#0758c7;font-size:10px;font-weight:750;letter-spacing:.09em;text-transform:uppercase}
h1{max-width:760px;margin:8px 0 10px;font-size:clamp(32px,5vw,54px);font-weight:520;line-height:1.02;letter-spacing:-.055em}
.lede{max-width:720px;margin:0;color:#4d5764}.decision{display:flex;align-items:center;justify-content:space-between;gap:24px;margin:30px 0 24px;padding:24px;border:1px solid #e0e5e1;border-radius:20px;background:#fff;box-shadow:0 8px 30px rgb(17 31 45 / 6%)}
.decision div{display:grid;gap:4px}.decision strong{font-size:22px;font-weight:560;letter-spacing:-.035em}.decision span{color:#59636f}.badge{flex:none;padding:9px 12px;border-radius:999px;background:#fff5e6;color:#7b5100;font-size:10px;font-weight:750;letter-spacing:.06em;text-transform:uppercase}
.report-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.card{padding:22px;border:1px solid #e0e5e1;border-radius:20px;background:#fff;box-shadow:0 8px 30px rgb(17 31 45 / 5%)}
h2{margin:0 0 16px;font-size:18px;font-weight:560;letter-spacing:-.03em}.card>p{margin:0;color:#4d5764}.card.wide{grid-column:1/-1}
dl{display:grid;grid-template-columns:1fr 1fr;margin:0;border:1px solid #e7eae7;border-radius:14px;overflow:hidden}dl div{padding:14px;border-right:1px solid #e7eae7;border-bottom:1px solid #e7eae7}dl div:nth-child(2n){border-right:0}dl div:nth-last-child(-n+2){border-bottom:0}
dt{color:#59636f;font-size:11px}dd{margin:4px 0 0;font-weight:680}small{display:block;margin-top:4px;color:#67717d;font-size:11px;font-weight:450}
.integrity{display:grid;gap:10px}.integrity code{padding:14px;border-radius:12px;background:#f0f2ef;color:#164ca9;font:11px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;overflow-wrap:anywhere}
footer{margin-top:18px;color:#67717d;font-size:11px;text-align:center}
@media(max-width:680px){.topbar{padding:0 16px}main{margin-top:24px}.report-grid{grid-template-columns:1fr}.decision{align-items:flex-start;flex-direction:column}dl{grid-template-columns:1fr}dl div,dl div:nth-child(2n),dl div:nth-last-child(2){border-right:0;border-bottom:1px solid #e7eae7}dl div:last-child{border-bottom:0}}
@media print{body{background:#fff}.topbar{padding:0 0 16px}.decision,.card{box-shadow:none}main{width:100%;margin:24px 0}.status{border:1px solid #b9d8c4}}
</style></head><body>
<header class="topbar"><div class="brand"><strong>PlanMargin</strong><span>Behavior Test Studio</span></div><span class="status">Sealed evidence report</span></header>
<main><p class="eyebrow">Counterfactual investigation</p><h1>PlanMargin investigation report</h1>
<p class="lede">Privacy-reduced evidence from the immutable v1 development campaign. This report does not evaluate the production Waymo Driver.</p>
<section class="decision"><div><strong>${escapeHtml(reason)}</strong><span>Proposal ${input.proposal.proposalNumber} in ${escapeHtml(input.cell.method)} cell ${input.cell.selectionOrder}, seed ${input.cell.seed}.</span></div><span class="badge">Evidence decision</span></section>
<div class="report-grid"><section class="card"><h2>Scenario change</h2><dl>
<div><dt>Lead braking onset shift</dt><dd>${input.proposal.brakingOnsetOffsetSeconds >= 0 ? '+' : '−'}${Math.abs(input.proposal.brakingOnsetOffsetSeconds).toFixed(1)} s</dd></div>
<div><dt>Lead speed scale</dt><dd>${input.proposal.speedMultiplier.toFixed(2)}×</dd></div>
</dl></section>
<section class="card"><h2>Planner decision</h2><dl>
<div><dt>Tested planner</dt><dd>${outcomeLabel(input.proposal.testedMutatedFailure, true)}</dd></div>
<div><dt>Reference planner</dt><dd>${outcomeLabel(input.proposal.referenceMutatedSuccess, false)}</dd></div>
<div><dt>Safety result</dt><dd>${proximityLabel(input.proposal.criticality)}<small>derived from the measured minimum signed separation; criticality ${input.proposal.criticality.toFixed(4)}</small></dd></div>
<div><dt>Change size</dt><dd>${changeSizeLabel(input.proposal.minimality)}<small>derived from the normalized distance to the recorded scenario; minimality ${input.proposal.minimality.toFixed(4)}</small></dd></div>
<div><dt>Recorded precedent</dt><dd>${input.proposal.supportPasses === true ? 'Seen in recorded behavior' : input.proposal.empiricalSupportProbability === null ? 'Not evaluated' : 'Outside recorded behavior'}<small>support probability ${input.proposal.empiricalSupportProbability?.toFixed(4) ?? 'not evaluated'}; pass threshold 0.05</small></dd></div>
<div><dt>Normalized edit distance</dt><dd>${input.proposal.normalizedMutationDistance.toFixed(4)}<small>distance from the unchanged scenario</small></dd></div>
</dl></section>
<section class="card wide"><h2>Campaign boundary</h2><p>${input.campaign.proposals.toLocaleString()} proposals and ${input.campaign.physicalRollouts.toLocaleString()} physical rollouts produced zero qualifying findings. Bayesian search increased eligible-proposal yield by ${(input.campaign.methods.bayesian.validRatePercent - input.campaign.methods.random.validRatePercent).toFixed(4)} percentage points. H1 and H2 remained untestable; H3 was supported.</p></section>
<section class="card wide integrity"><h2>Integrity</h2><p>SHA-256 over the canonical local report payload:</p><code>${digest}</code></section></div>
<footer>Generated locally from verified PlanMargin evidence. Licensed source records were not embedded.</footer></main>
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
