import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('saved health, coverage suites and triage remain legible and actionable without a server', async ({
  page,
}) => {
  await page.route('**/api/v1/**', (route) => route.abort());
  await page.goto('/?view=health');
  await expect(
    page.getByRole('heading', { name: 'The saved test run passed its checks.', exact: true }),
  ).toBeVisible();
  const check = async () => {
    const result = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze();
    expect(result.violations).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(
      true,
    );
  };
  await check();
  await page.getByRole('button', { name: 'Coverage', exact: true }).click();
  for (const suite of [
    'Lead-vehicle braking',
    'Command-dropout fallback',
    'Assistance handoff recovery',
  ]) {
    await page
      .getByRole('region', { name: 'Versioned behavior coverage' })
      .getByRole('button', { name: new RegExp('^' + suite) })
      .click();
    await expect(page.getByRole('heading', { name: suite, exact: true })).toBeVisible();
    await check();
  }
  await page.getByRole('button', { name: /^Triage/ }).click();
  await page.getByRole('button', { name: 'Pending', exact: true }).click();
  await check();
  await page.reload();
  await expect(
    page.getByRole('button', { name: 'Inspect model evidence', exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Inspect model evidence', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Residual FP16 candidate', exact: true }),
  ).toBeVisible();
});
