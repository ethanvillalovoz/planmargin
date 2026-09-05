import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

test('all model studies remain usable offline with keyboard-accessible evidence and links', async ({
  page,
}) => {
  const trackingWarnings: string[] = [];
  page.on('console', (message) => {
    if (message.text().includes('NG0956')) trackingWarnings.push(message.text());
  });
  await page.route('**/api/v1/**', (route) => route.abort('connectionrefused'));
  await page.goto('/?view=evidence&panel=runtime');
  const studyNav = page.getByRole('navigation', { name: 'Model study selection' });
  await expect(studyNav.getByRole('button')).toHaveCount(6);
  const titles = [
    'Trajectory prediction',
    'TensorRT deployment',
    'Earlier deployment reference',
    'Proposal ranking',
    'Neighbor-context ablation',
    'Residual FP16 candidate',
  ];
  for (let index = 0; index < titles.length; index++) {
    const button = studyNav.getByRole('button').nth(index);
    await button.focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('heading', { name: titles[index], exact: true })).toBeVisible();
    await expect(
      page.getByRole('link', { name: 'Open source report', exact: true }),
    ).toHaveAttribute(
      'href',
      /^https:\/\/github.com\/ethanvillalovoz\/planmargin\/blob\/[a-f0-9]{40}\//,
    );
    const summary = page.locator('.gate-details > summary');
    await summary.focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('.gate-details')).toHaveAttribute('open', '');
    expect(
      (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
        .violations,
    ).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await summary.focus();
    await page.keyboard.press('Enter');
  }
  await page.reload();
  await expect(
    page.getByRole('heading', { name: 'Residual FP16 candidate', exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Test health', exact: true }).click();
  await page.getByRole('button', { name: /Triage/ }).click();
  await page.getByRole('button', { name: 'Pending', exact: true }).click();
  await page.getByRole('button', { name: 'Inspect model evidence', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Residual FP16 candidate', exact: true }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Test health', exact: true }).click();
  await expect(page.locator('.context-inspector')).toContainText('PM-TRT-011');
  expect(trackingWarnings).toEqual([]);
});
