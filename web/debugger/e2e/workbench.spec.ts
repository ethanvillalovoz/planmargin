import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page, type Route } from '@playwright/test';
import {
  API_CAMPAIGN,
  API_CELLS,
  API_HYPOTHESES,
  API_INVESTIGATION,
  API_METHODS,
  API_PROPOSALS,
  API_RUN,
  API_RUNS,
} from '../src/app/local-evidence.test-fixtures';

function fulfill(route: Route, value: unknown): Promise<void> {
  return route.fulfill({
    status: 200,
    contentType: 'application/json',
    headers: {
      'Access-Control-Allow-Origin': 'http://127.0.0.1:4200',
      'Access-Control-Allow-Credentials': 'true',
    },
    body: JSON.stringify(value),
  });
}

const ASSISTANT_ANSWER = {
  record_type: 'planmargin.evidence_assistant_response',
  schema_version: '1.0.0',
  status: 'answered',
  question: {
    sha256: 'a'.repeat(64),
    query_id: 'method_comparison',
    query_label: 'Method comparison',
  },
  provider: {
    id: 'gemini_public_aggregate',
    model: 'gemini-test',
    role: 'explanation_only',
  },
  tool_result: {
    query_id: 'method_comparison',
    title: 'Search-method comparison',
    source_mode: 'public_aggregate',
    facts: [
      {
        fact_id: 'valid-rate-delta',
        statement: 'Bayesian valid-rate advantage',
        value: 25,
        unit: 'percentage points',
        citation_id: 'campaign',
      },
    ],
    citations: [
      {
        citation_id: 'campaign',
        title: 'Campaign evidence',
        repository_path: 'evidence/public/campaign.json',
        sha256: 'b'.repeat(64),
      },
    ],
  },
  explanation: {
    summary: 'Bayesian search produced more feasible proposals in this measured campaign.',
    interpretation: 'The comparison supports proposal efficiency, not a safety-regression claim.',
    cited_fact_ids: ['valid-rate-delta'],
    limitation: 'This answer is limited to the verified aggregate supplied by the evidence tool.',
    citation_ids: ['campaign'],
  },
  privacy: {
    raw_question_persisted: false,
    raw_question_sent_to_provider: false,
    private_data_sent_to_provider: false,
    provider_input_scope: 'public_aggregate_tool_result_only',
  },
  limitations: ['No private scenario record was sent to the provider.'],
};

async function mockExactReplayApi(page: Page): Promise<void> {
  const proposal = {
    ...API_PROPOSALS[0],
    trajectory_available: true,
    replay_run_id: 'run_exact',
  };
  const investigation = {
    ...API_INVESTIGATION,
    closest_margin: [{ ...API_INVESTIGATION.closest_margin[0], ...proposal }],
    smallest_mutation: [{ ...API_INVESTIGATION.smallest_mutation[0], ...proposal }],
    highest_support: [{ ...API_INVESTIGATION.highest_support[0], ...proposal }],
  };
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '');
    if (path === '/health')
      return fulfill(route, { status: 'ready', evidence_mode: 'real_local_redacted' });
    if (path === '/campaign') return fulfill(route, API_CAMPAIGN);
    if (path === '/methods') return fulfill(route, API_METHODS);
    if (path === '/hypotheses') return fulfill(route, API_HYPOTHESES);
    if (path === '/cells') return fulfill(route, API_CELLS);
    if (path === '/runs')
      return fulfill(route, [
        ...API_RUNS,
        {
          ...API_RUNS[0],
          run_id: 'run_exact',
          label: 'Exact campaign replay · bayesian · S1 · seed 0 · proposal 1',
        },
      ]);
    if (path === '/runs/run_opaque') return fulfill(route, API_RUN);
    if (path === '/runs/run_exact')
      return fulfill(route, {
        ...API_RUN,
        run_id: 'run_exact',
        scenario_label: 'Campaign replay · bayesian · S1 · seed 0',
        hypothesis: {
          ...API_RUN.hypothesis,
          id: 'proposal-linked-counterfactual',
          label: 'Exact retained proposal 1',
        },
      });
    if (path === '/investigation') return fulfill(route, investigation);
    if (path === '/cells/cell_opaque/proposals') return fulfill(route, [proposal]);
    if (path === '/cells/cell_opaque/proposals/1/analysis')
      return fulfill(route, {
        evidence_mode: 'real_local_redacted',
        analysis_mode: 'deterministic_proposal_specific',
        cell_id: 'cell_opaque',
        proposal_number: 1,
        decision: 'not_qualified',
        decisive_gate: 'tested_controller_failure',
        explanation: 'The tested planner remained successful under the verified mutation.',
        facts: [{ label: 'method', value: 'bayesian' }],
        record_sha256: 'c'.repeat(64),
        trajectory_available: true,
        replay_run_id: 'run_exact',
      });
    if (path === '/assistant/status')
      return fulfill(route, {
        provider_id: 'gemini_public_aggregate',
        model: 'gemini-test',
        source_mode: 'public_aggregate',
        gemini_configured: true,
        explanation_only: true,
      });
    if (path === '/assistant/questions')
      return fulfill(route, [
        {
          query_id: 'method_comparison',
          label: 'method comparison',
          question: 'How did Bayesian compare with random search?',
        },
      ]);
    if (path === '/assistant/method_comparison') return fulfill(route, ASSISTANT_ANSWER);
    return route.fulfill({ status: 404, body: '{}' });
  });
}

test('public clone stays honest, usable, and accessible without licensed records', async ({
  page,
}) => {
  const consoleErrors: string[] = [];
  await page.route('http://127.0.0.1:8765/**', (route) => route.abort('connectionrefused'));
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  await page.goto('/');
  await expect(page).toHaveTitle('PlanMargin campaign workbench');
  await expect(page.getByRole('heading', { name: 'Local evidence' })).toBeHidden();
  await expect(
    page.getByRole('heading', {
      name: '3,200 counterfactual proposals. Zero qualifying regressions.',
    }),
  ).toBeVisible();
  await expect(page.getByLabel('Published campaign totals')).toContainText('14,110');
  await expect(page.getByRole('heading', { name: 'Feasible proposal yield' })).toBeVisible();
  await expect(page.getByText('14.81 percentage points')).toBeVisible();
  await expect(page.getByText('never substitute or synthetic cases')).toBeVisible();
  await expect(page.getByText('Licensed local only')).toBeVisible();

  await page.getByRole('button', { name: 'Workbench', exact: true }).click();
  await expect(page.getByText('Replay sealed planner evidence locally.')).toBeVisible();
  await page.getByRole('button', { name: 'Open local workspace', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: 'Local evidence' })).toBeVisible();
  await page.getByRole('button', { name: 'Close local evidence' }).click();
  await page.getByRole('button', { name: 'Evidence', exact: true }).click();

  const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(accessibility.violations).toEqual([]);
  expect(
    consoleErrors.filter(
      (message) => !message.includes('Failed to load resource: net::ERR_CONNECTION_REFUSED'),
    ),
  ).toEqual([]);

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
});

test('retained proposal opens its exact planning replay', async ({ page }) => {
  await mockExactReplayApi(page);
  await page.goto('/');
  await expect(page.getByText('Local records verified')).toBeVisible();
  await page.getByRole('button', { name: 'Evidence', exact: true }).click();
  await expect(page.getByText('Exact proposal replay retained and verified.')).toBeVisible();
  await page.getByRole('button', { name: 'Open exact proposal replay' }).click();
  const planning = page.getByLabel('Planning evidence', { exact: true });
  await expect(planning.getByText('Exact retained proposal 1').first()).toBeVisible();
  await expect(planning.getByText('Exact campaign link verified', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Forward one second in planning evidence' }).click();
  await expect(page.getByRole('contentinfo').locator('strong')).toContainText('Step 001');
});

test('local workspace supports an end-to-end evidence investigation', async ({ page }) => {
  await mockExactReplayApi(page);
  await page.goto('/');
  await expect(page.getByText('Local records verified')).toBeVisible();
  await page.getByRole('button', { name: 'Evidence', exact: true }).click();

  await expect(page.getByText('Counterfactual investigation')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Priority review queue' })).toBeVisible();
  await page.getByRole('button', { name: 'Strongest precedent' }).click();
  await page.getByRole('button', { name: 'Compare' }).click();
  await expect(page.getByText('Comparison · 1/2')).toBeVisible();
  await page.getByRole('button', { name: 'Inspect' }).click();
  await expect(page.getByRole('heading', { name: 'Tested planner still succeeds' })).toBeVisible();

  await page.getByRole('button', { name: 'Analyze selected proposal' }).click();
  await expect(page.getByText('Proposal-specific evidence analysis')).toBeVisible();
  await expect(page.getByText('sealed record · cccccccccccccccc')).toBeVisible();

  const investigationAccessibility = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze();
  expect(investigationAccessibility.violations).toEqual([]);

  await page.getByRole('button', { name: 'Model & runtime' }).click();
  await expect(page.getByText('Model qualification')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Real-WOMD prediction quality' })).toBeVisible();
  await expect(page.getByText('Scale-model deployment · pending')).toBeVisible();

  await page.getByRole('button', { name: 'Ask analysis' }).click();
  await expect(page.getByText('Gemini analysis')).toBeVisible();
  await page.getByRole('button', { name: 'How did Bayesian compare with random search?' }).click();
  await expect(
    page.getByText('Bayesian search produced more feasible proposals in this measured campaign.'),
  ).toBeVisible();
  await expect(page.getByLabel('Verified facts used in this answer')).toContainText(
    '25 percentage points',
  );

  await page.reload();
  await expect(page.getByText('Local records verified')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Workbench', exact: true })).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
});
