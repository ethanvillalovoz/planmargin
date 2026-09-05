import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { API_RUN } from '../src/app/local-evidence.test-fixtures';
import { readFile } from 'node:fs/promises';

// UI contracts only. These controlled fixtures are NOT scientific measurements.
test('fault and recovery plans, measured event seeking, linked rerun and JSON download', async ({
  page,
}) => {
  const id = 'd'.repeat(32);
  let submitted: any;
  let job: any;
  const events = [
    { step: 20, time_seconds: 2, label: 'Command lost · fallback activated' },
    { step: 30, time_seconds: 3, label: 'Recovery signal · primary resumed' },
  ];
  const result = {
    decision: 'checks_passed',
    explanation: 'Test-only fixture: all named behavior gates passed.',
    gates: { baseline_success: true, assisted_progress_recovered: true },
    behavior_events: events,
    qualification: {
      baseline: { post_fault_progress_m: 40 },
      unprotected: { post_fault_progress_m: 0 },
      assisted: { post_fault_progress_m: 38 },
    },
    collection_sha256: 'a'.repeat(64),
    result_sha256: 'b'.repeat(64),
    support_probability: null,
    controllers: null,
    rejection_reasons: [],
    boundary: 'Test fixture',
  };
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route('**/api/v1/**', async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname.replace('/api/v1', '');
    let value: unknown = {};
    if (req.method() === 'OPTIONS') value = {};
    else if (path === '/health')
      value = { status: 'ready', campaign_ready: false, evidence_mode: 'real_local_redacted' };
    else if (path === '/experiments/readiness')
      value = { ready: true, empirical_support_ready: false, missing: [] };
    else if (path === '/experiments/health')
      value = {
        status: 'healthy',
        total_jobs: job ? 1 : 0,
        active_incidents: 0,
        resolved_incidents: 0,
        deadline_measured_jobs: job ? 1 : 0,
        on_time_completed_jobs: job ? 1 : 0,
        unmeasured_jobs: 0,
        incidents: [],
      };
    else if (path === '/experiments' && req.method() === 'POST') {
      submitted = req.postDataJSON();
      const { request_id, completion_deadline_seconds, rerun_of, ...config } = submitted;
      job = {
        job_id: id,
        config,
        request_id,
        completion_deadline_seconds,
        rerun_of,
        status: 'succeeded',
        stage: 'complete',
        stage_label: 'Experiment complete',
        created_at: 1,
        elapsed_seconds: 20,
        events: [],
        error: null,
        result,
      };
      value = job;
    } else if (path === '/experiments') value = job ? [job] : [];
    else if (path.endsWith('/result')) value = result;
    else if (path.endsWith('/replay')) {
      const points = Array.from({ length: 81 }, (_, i) => ({ x: i, y: 0 }));
      value = {
        ...API_RUN,
        run_id: `experiment_${id}`,
        step_seconds: 0.1,
        mutation_target: {
          original: points.map((p, i) => (i < 79 ? p : null)),
          counterfactual: points.map((p, i) => (i < 79 ? p : null)),
        },
        hypothesis: {
          ...API_RUN.hypothesis,
          id: 'interactive-counterfactual',
          mutation_type: 'assistance_handoff',
          mutation_parameters: { fault_onset_seconds: 2, recovery_seconds: 3 },
          onset_seconds: 2,
          supported: false,
          behavior_decision: 'checks_passed',
          behavior_boundary: 'Scripted recovery signal, not a human operator.',
          behavior_events: events,
          trajectory_labels: {
            tested: 'Unprotected',
            reference: 'Protected',
            recorded: 'Primary baseline',
          },
          trajectories: { tested: points, reference: points, recorded: points },
          metrics: points.map((_, i) => ({
            time_seconds: i / 10,
            signed_separation_meters: i < 79 ? 5 : null,
            longitudinal_ttc_seconds: null,
          })),
        },
      };
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: {
        'Access-Control-Allow-Origin': 'http://127.0.0.1:4200',
        'Access-Control-Allow-Credentials': 'true',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, X-PlanMargin-Token',
      },
      body: JSON.stringify(value),
    });
  });
  await page.goto('/?view=experiments');
  await expect(page.getByRole('button', { name: 'Run experiment', exact: true })).toBeEnabled();
  await page
    .getByRole('combobox', { name: 'Test plan', exact: true })
    .selectOption('command_dropout');
  await expect(page.getByRole('spinbutton', { name: 'Lead speed multiplier' })).toHaveCount(0);
  await expect(
    page.getByText('The fallback remains active through the end of the rollout.'),
  ).toBeVisible();
  await page
    .getByRole('combobox', { name: 'Test plan', exact: true })
    .selectOption('assistance_handoff');
  await page.getByRole('button', { name: 'Run experiment', exact: true }).click();
  expect(submitted.test_plan).toBe('assistance_handoff');
  expect(submitted.speed_multiplier).toBe(1);
  expect(submitted.braking_onset_offset_s).toBe(0);
  expect(submitted.tested_controller).toBeUndefined();
  expect(submitted.completion_deadline_seconds).toBe(120);
  await expect(
    page.getByRole('heading', { name: 'Behavior checks passed', exact: true }),
  ).toBeVisible();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export result JSON' }).click();
  const download = await downloadPromise;
  expect(JSON.parse(await readFile((await download.path())!, 'utf8'))).toEqual(result);
  await page.getByRole('button', { name: 'Prepare linked rerun' }).click();
  await page.getByRole('spinbutton', { name: 'Completion deadline (seconds)' }).fill('180');
  await page.getByRole('button', { name: 'Run experiment', exact: true }).click();
  expect(submitted.rerun_of).toBe(id);
  expect(submitted.completion_deadline_seconds).toBe(180);
  await page.getByRole('button', { name: 'Open this experiment replay' }).click();
  await page
    .getByRole('button', { name: '3.0 s · Recovery signal · primary resumed', exact: true })
    .click();
  await expect(page.getByRole('slider', { name: 'Evidence timeline' })).toHaveValue('30');
  await expect(page.getByLabel('Trajectory legend')).toContainText('Unprotected');
  await expect(page.getByLabel('Trajectory legend')).toContainText('Primary baseline');
  await page.getByRole('slider', { name: 'Evidence timeline' }).fill('80');
  await expect(page.locator('app-scene-viewport .planning-guide')).toContainText(
    'Recorded lead not observed',
  );
  await expect(page.locator('app-scene-viewport rect.lead')).toHaveCount(0);
  await expect(page.locator('app-scene-viewport rect.tested')).toHaveCount(1);
  await page.reload();
  await expect(
    page.getByRole('button', { name: '3.0 s · Recovery signal · primary resumed', exact: true }),
  ).toBeVisible();
  const audit = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze();
  expect(audit.violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});
