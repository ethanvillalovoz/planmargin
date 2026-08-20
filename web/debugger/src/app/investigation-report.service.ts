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
  if (proposal.attemptStatus === 'mutation_rejected') return 'Mutation geometry gate rejected';
  if (proposal.attemptStatus === 'scenario_rejected') return 'Scenario validity gate rejected';
  if (!proposal.pipelinePasses) return 'Deterministic pipeline gate rejected';
  if (proposal.supportPasses !== true) return 'Empirical-support gate rejected';
  if (!proposal.referencePasses) return 'Reference-controller gate rejected';
  if (proposal.testedMutatedFailure !== true) return 'Tested controller did not fail';
  return proposal.policySpecificAvoidableFailure
    ? 'Qualifying finding'
    : 'Finding contract not met';
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
div{padding:12px;border-bottom:1px solid #dbe5e9}dt{color:#607683;font-size:12px}dd{margin:4px 0 0;font-weight:650}
.decision{padding:18px;border-left:4px solid #ff6b55;background:#f5f9fa}code{word-break:break-all;font-size:11px;color:#526872}
</style></head><body>
<h1>PlanMargin investigation report</h1>
<p>Privacy-reduced evidence from the immutable v1 development campaign. This report does not evaluate the production Waymo Driver.</p>
<section class="decision"><strong>${escapeHtml(reason)}</strong><br>Proposal ${input.proposal.proposalNumber} in ${escapeHtml(input.cell.method)} cell ${input.cell.selectionOrder}, seed ${input.cell.seed}.</section>
<h2>Selected evidence</h2><dl>
<div><dt>Mutation distance</dt><dd>${input.proposal.normalizedMutationDistance.toFixed(4)}</dd></div>
<div><dt>Criticality</dt><dd>${input.proposal.criticality.toFixed(4)}</dd></div>
<div><dt>Minimality</dt><dd>${input.proposal.minimality.toFixed(4)}</dd></div>
<div><dt>Support probability</dt><dd>${input.proposal.empiricalSupportProbability?.toFixed(4) ?? 'not evaluated'}</dd></div>
<div><dt>Onset offset</dt><dd>${input.proposal.brakingOnsetOffsetSeconds.toFixed(1)} s</dd></div>
<div><dt>Speed multiplier</dt><dd>${input.proposal.speedMultiplier.toFixed(4)}</dd></div>
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
    anchor.click();
    URL.revokeObjectURL(url);
  }
}
