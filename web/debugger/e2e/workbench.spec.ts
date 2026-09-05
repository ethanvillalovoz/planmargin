import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page, type Route } from '@playwright/test';
import { readFile } from 'node:fs/promises';
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
  await expect(page).toHaveTitle('PlanMargin · planner stress testing');
  await expect(page.getByRole('heading', { name: 'Local evidence' })).toBeHidden();
  await expect(
    page.getByRole('heading', { name: 'Lead-vehicle braking', exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel('Campaign result')).toContainText('0 qualifying regressions');
  await page.getByRole('button', { name: 'Test health', exact: true }).click();
  await expect(page.getByLabel('Test suite registry')).toContainText('3 suites');
  await expect(
    page.getByRole('heading', { name: 'The saved test run passed its checks.' }),
  ).toBeVisible();
  await expect(page.getByText('Not live pipeline monitoring.')).toBeVisible();

  await page.getByRole('button', { name: 'Coverage', exact: true }).click();
  await expect(page.getByText('Versioned behavior coverage', { exact: true })).toBeVisible();
  await expect(
    page.locator('.coverage-table').getByText('Command-dropout fallback', { exact: true }),
  ).toBeVisible();
  await expect(page.getByText('Cross-simulator agreement')).toBeVisible();
  await page.getByRole('button', { name: /^Triage/ }).click();
  await expect(page.getByRole('button', { name: 'Pending', exact: true })).toBeVisible();
  await expect(page.getByText('Measured decisions')).toBeVisible();

  await page.getByRole('button', { name: 'Investigate', exact: true }).click();
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

  await page.getByRole('button', { name: 'Replay', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'No retained replay loaded' })).toBeVisible();
  const lockedWorkspaceAccessibility = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze();
  expect(lockedWorkspaceAccessibility.violations).toEqual([]);
  await page.getByRole('button', { name: 'Connect sealed records', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Local evidence' })).toBeVisible();
  const connectionAccessibility = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze();
  expect(connectionAccessibility.violations).toEqual([]);
  await page.getByRole('button', { name: 'Close local evidence' }).click();
  await page.getByRole('button', { name: 'Investigate', exact: true }).click();

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
  await expect(page.getByText('Local workspace connected')).toBeVisible();
  await page.getByRole('button', { name: 'Investigate', exact: true }).click();
  await expect(page.getByText('Exact proposal replay retained and verified.')).toBeVisible();
  await page.getByRole('button', { name: 'Open exact proposal replay' }).click();
  await expect(page.getByRole('button', { name: 'Collapse controls' })).toBeVisible();
  const planning = page.getByLabel('Planning evidence', { exact: true });
  await expect(planning.getByText('Exact retained proposal 1').first()).toBeVisible();
  await expect(planning.getByText('Exact campaign link verified', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Forward one second in planning evidence' }).click();
  await expect(page.getByRole('contentinfo').locator('strong')).toContainText('Step 001');
});

test('mobile exact replay keeps controls bounded below the scene', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile-chromium');
  await mockExactReplayApi(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'Investigate', exact: true }).click();
  await page.getByRole('button', { name: 'Open exact proposal replay' }).click();

  const planning = page.getByLabel('Planning evidence', { exact: true });
  const panel = await planning.boundingBox();
  const scene = await page.getByLabel('Real local trajectory scene').boundingBox();
  expect(panel).not.toBeNull();
  expect(scene).not.toBeNull();
  expect(panel!.width).toBeGreaterThan(350);
  expect(panel!.height).toBeLessThanOrEqual(250);
  expect(panel!.y).toBeGreaterThan(scene!.y + scene!.height / 2);
});

test('local workspace supports an end-to-end evidence investigation', async ({ page }) => {
  await mockExactReplayApi(page);
  await page.goto('/');
  await expect(page.getByText('Local workspace connected')).toBeVisible();
  await page.getByRole('button', { name: 'Investigate', exact: true }).click();

  await expect(page.getByText('Counterfactual investigation')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Browse recorded tests' })).toBeVisible();
  await page.getByRole('combobox', { name: 'Sort proposals' }).selectOption('support');
  await page.getByRole('button', { name: /^Compare scenario/ }).click();
  await expect(page.getByRole('heading', { name: 'Proposal comparison' })).toBeVisible();
  await expect(
    page.getByRole('table', { name: 'Proposal measurements side by side' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Inspect A', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Tested planner still succeeds' })).toBeVisible();

  await page.getByRole('button', { name: 'Analyze selected proposal' }).click();
  await expect(page.getByText('Proposal-specific evidence analysis')).toBeVisible();
  await expect(page.getByText('sealed record · cccccccccccccccc')).toBeVisible();

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export investigation' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('planmargin-bayesian-1-0-p1.html');
  const downloadPath = await download.path();
  expect(downloadPath).not.toBeNull();
  const report = await readFile(downloadPath!, 'utf8');
  expect(report).toContain('PlanMargin investigation report');
  expect(report).toContain('Tested planner still succeeds');
  expect(report).toMatch(/SHA-256[\s\S]*[a-f0-9]{64}/);

  const investigationAccessibility = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze();
  expect(investigationAccessibility.violations).toEqual([]);

  await page.getByRole('button', { name: 'Models', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Models & runtime', exact: true })).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Trajectory prediction', exact: true }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: 'TensorRT deployment Scaled model · Tesla T4 Not promoted' })
    .click();
  await expect(page.getByText(/FP16 is not promoted: 0.101 m maximum drift/)).toBeVisible();
  const deploymentAccessibility = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze();
  expect(deploymentAccessibility.violations).toEqual([]);

  await page.getByRole('button', { name: 'Ask PlanMargin' }).click();
  await expect(page.getByText('PlanMargin assistant')).toBeVisible();
  await page.getByPlaceholder('Ask about campaign evidence…').fill('hi');
  await page.getByRole('button', { name: 'Ask evidence assistant' }).click();
  await expect(
    page.getByRole('heading', { name: 'Hi. I’m ready to inspect the run.' }),
  ).toBeVisible();
  await expect(page.getByText('Local guide · no model request', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'How did Bayesian compare with random search?' }).click();
  await expect(
    page.getByText('Bayesian search produced more feasible proposals in this measured campaign.'),
  ).toBeVisible();
  await expect(
    page.getByText('Gemini response · verified campaign aggregates', { exact: true }),
  ).toBeVisible();
  await page.getByText('Show verified facts (1)', { exact: true }).click();
  await expect(page.locator('.verified-facts')).toContainText('25 percentage points');
  await expect(page.getByRole('heading', { name: 'Models & runtime', exact: true })).toBeVisible();
  const assistantAccessibility = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze();
  expect(assistantAccessibility.violations).toEqual([]);
  await page.getByRole('textbox', { name: 'Ask about campaign evidence…' }).press('Escape');
  await expect(page.getByRole('button', { name: 'Ask PlanMargin', exact: true })).toBeFocused();

  await page.reload();
  await expect(page.getByText('Local workspace connected')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Investigate', exact: true })).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
});

test('an expired evidence session produces a recovery state rather than an empty inspector', async ({
  page,
}) => {
  await mockExactReplayApi(page);
  await page.goto('/');
  await expect(page.getByText('Local workspace connected')).toBeVisible();
  await page.route('**/api/v1/cells/cell_opaque/proposals', (route) =>
    route.fulfill({ status: 401, body: '{}' }),
  );
  await page.getByRole('button', { name: /^Inspect scenario/ }).click();
  await expect(
    page.getByRole('button', { name: 'Reconnect workspace', exact: true }),
  ).toBeVisible();
  await expect(page.locator('.connection-error')).toBeVisible();
  await expect(
    page.getByRole('heading', {
      name: '3,200 counterfactual proposals. Zero qualifying regressions.',
    }),
  ).toBeVisible();
});

test('a replay route restores the planning mode after refresh', async ({ page }) => {
  const runtimeErrors: string[] = [];
  page.on('pageerror', (error) => runtimeErrors.push(error.message));
  await mockExactReplayApi(page);
  await page.goto('/?view=replay');
  await expect(page.getByRole('tab', { name: 'Planning', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await page.reload();
  await expect(page.getByRole('tab', { name: 'Planning', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  expect(runtimeErrors).toEqual([]);
});
