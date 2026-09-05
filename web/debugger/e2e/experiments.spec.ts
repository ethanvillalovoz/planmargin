import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { API_RUN } from '../src/app/local-evidence.test-fixtures';

// Data-free UI contract tests. Real Waymax execution is verified separately;
// these fixtures never enter product evidence or the published application.
test('experiment config, progress, cancellation, completion, replay and reload', async ({
  page,
}) => {
  const jobId = 'a'.repeat(32);
  let calls = 0;
  let state: Record<string, any> | undefined;
  let createCount = 0;
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route('**/api/v1/**', async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname.replace('/api/v1', '');
    let value: unknown = {};
    let status = 200;
    if (req.method() === 'OPTIONS') value = {};
    else if (path === '/health')
      value = { status: 'ready', campaign_ready: false, evidence_mode: 'real_local_redacted' };
    else if (path === '/experiments/readiness')
      value = {
        ready: true,
        missing: [],
        empirical_support_ready: true,
        setup_command: 'uv run --frozen planmargin-prepare-planning --accept-waymo-terms',
        boundary: 'Exploratory local runs, separate from the frozen campaign.',
      };
    else if (path === '/experiments' && req.method() === 'POST') {
      createCount++;
      const { request_id, ...config } = req.postDataJSON();
      expect(request_id).toMatch(/^[0-9a-f-]{36}$/);
      state = {
        job_id: jobId,
        config,
        status: 'running',
        stage: 'loading',
        stage_label: 'Loading the selected WOMD scenario',
        created_at: Date.now() / 1000,
        elapsed_seconds: 1,
        events: [],
        error: null,
        result: null,
      };
      value = state;
      status = 202;
    } else if (path === '/experiments') {
      calls++;
      value = state ? [state] : [];
    } else if (path === `/experiments/${jobId}/cancel`) {
      state = {
        ...state,
        status: 'cancelled',
        error: {
          code: 'cancelled',
          component: 'loading',
          recovery: 'The worker was stopped. Rerun this configuration.',
        },
      };
      value = state;
    } else if (path === `/experiments/${jobId}/replay`)
      value = {
        ...API_RUN,
        run_id: `experiment_${jobId}`,
        scenario_label: 'Local experiment · scenario 1',
        hypothesis: {
          ...API_RUN.hypothesis,
          id: 'interactive-counterfactual',
          label: 'New local experiment',
        },
      };
    else if (path === `/experiments/${jobId}/result`) value = state?.['result'];
    else {
      status = 404;
      value = { detail: 'Not available in this test workspace' };
    }
    await route.fulfill({
      status,
      contentType: 'application/json',
      headers: {
        'Access-Control-Allow-Origin': 'http://127.0.0.1:4200',
        'Access-Control-Allow-Credentials': 'true',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
      },
      body: JSON.stringify(value),
    });
  });
  await page.goto('/?view=experiments');
  await expect(page.getByRole('heading', { name: 'Test a scenario change' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Run experiment', exact: true })).toBeEnabled();
  await page.getByRole('spinbutton', { name: 'Lead speed multiplier' }).fill('1.1');
  await page.getByRole('button', { name: 'Run experiment', exact: true }).click();
  expect(createCount).toBe(0); // Browser numeric constraints reject out-of-range edits.
  await page.getByRole('spinbutton', { name: 'Lead speed multiplier' }).fill('0.9');
  await page.getByRole('button', { name: 'Run experiment', exact: true }).click();
  await expect(page.getByRole('button', { name: 'An experiment is running' })).toBeDisabled();
  await expect(page.getByRole('status')).toContainText('Loading the selected WOMD scenario');
  await page.getByRole('button', { name: 'Cancel experiment' }).click();
  await expect(page.getByRole('region', { name: 'Experiment result' })).toContainText('Cancelled');
  await expect(page.getByRole('button', { name: 'Open this experiment replay' })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('region', { name: 'Run history' })).toContainText('Cancelled');
  await page.getByRole('button', { name: 'Run experiment', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Cancel experiment' })).toBeVisible();
  state = {
    ...state,
    status: 'succeeded',
    stage: 'complete',
    stage_label: 'Experiment complete',
    elapsed_seconds: 24,
    result: {
      decision: 'not_qualified',
      explanation:
        'The tested planner succeeds under this change; this is not a planner regression.',
      gates: { mutation_valid: true, tested_planner_fails: false },
      support_probability: 0.6,
      collection_sha256: 'b'.repeat(64),
      result_sha256: 'c'.repeat(64),
      rejection_reasons: [],
      boundary: 'Exploratory local evidence.',
      controllers: Object.fromEntries(
        ['tested', 'reference'].map((role) => [
          role,
          {
            outcome: { success: true, failure_reasons: [] },
            interaction_metrics: { minimum_signed_separation_m: 8.3 },
          },
        ]),
      ),
    },
  };
  await expect(
    page.getByRole('heading', { name: 'Not a qualifying regression', exact: true }),
  ).toBeVisible();
  await page.getByText('Finding gates and integrity', { exact: true }).click();
  await expect(page.getByRole('region', { name: 'Experiment result' })).toContainText(
    'tested planner fails',
  );
  await expect(page.getByRole('region', { name: 'Experiment result' })).toContainText('Not passed');
  const audit = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze();
  expect(audit.violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', { name: 'Open this experiment replay' }).click();
  await expect(page).toHaveURL(new RegExp(`experiment=${jobId}`));
  await expect(page.getByRole('button', { name: 'Return to experiments' })).toBeVisible();
  await expect(page.locator('polyline.tested')).toHaveCSS('fill', 'none');
  await expect(page.locator('polyline.lead')).toHaveCSS('fill', 'none');
  await expect(page.locator('app-scene-viewport canvas')).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('button', { name: 'Return to experiments' })).toBeVisible();
  await page.getByRole('button', { name: 'Return to experiments' }).click();
  await expect(page.getByRole('heading', { name: 'Test a scenario change' })).toBeVisible();
  expect(calls).toBeGreaterThan(2);
  expect(createCount).toBe(2);
  expect(errors).toEqual([]);
});
