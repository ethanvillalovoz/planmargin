// Opt-in verification against the user's running, authorized local sensor workspace.
// No mocked API, new data download, provider request, or public artifact is created.
import { chromium, expect } from '@playwright/test';

const token = process.env.PLANMARGIN_LOCAL_TOKEN;
if (!token) {
  console.error(
    'Set PLANMARGIN_LOCAL_TOKEN to the running workbench session token (not an API key).',
  );
  process.exit(1);
}

const browser = await chromium.launch({ headless: true, channel: 'chromium' });
try {
  for (const viewport of [
    { width: 1440, height: 1080 },
    { width: 412, height: 915 },
  ]) {
    const context = await browser.newContext({ viewport });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto(`http://127.0.0.1:4200/?view=sensors#token=${encodeURIComponent(token)}`);
    await expect(
      page.getByRole('button', { name: 'Local workspace connected', exact: true }),
    ).toBeVisible();
    await page.getByRole('button', { name: 'Sensor lab', exact: true }).click();
    await expect(page.locator('app-sensor-viewport img')).toBeVisible();
    // The camera's annotation panel is interactive; inspect its expanded desktop
    // placement and collapsed mobile placement before exercising spatial controls.
    if (
      viewport.width < 560 &&
      (await page.getByRole('button', { name: 'Collapse controls', exact: true }).isVisible())
    ) {
      await page.getByRole('button', { name: 'Collapse controls', exact: true }).click();
    }
    await assertNoOverlap(page);
    for (const mode of ['LiDAR', '3DGS']) {
      await page.getByRole('tab', { name: mode, exact: true }).click();
      await expect(
        page.getByRole('button', {
          name: mode === 'LiDAR' ? 'Reset view' : 'Source view',
          exact: true,
        }),
      ).toBeVisible({ timeout: 120_000 });
      await expect(page.locator('.splat-viewport canvas')).toHaveCount(1);
      await expect(page.locator('.scenario-controls')).toHaveCount(0);
      await assertNoOverlap(page);
    }
    await page.getByRole('button', { name: 'Left', exact: true }).click();
    await expect(page.locator('.reconstruction-explainer')).toContainText('Left novel viewpoint');
    expect(errors).toEqual([]);
    console.log(
      `PASS ${viewport.width}×${viewport.height}: real camera, LiDAR, 3DGS, viewpoint and overlay geometry`,
    );
    await context.close();
  }
} catch (error) {
  console.error(String(error).replaceAll(token, '[redacted]'));
  process.exitCode = 1;
} finally {
  await browser.close();
}

async function assertNoOverlap(page) {
  const boxes = await page
    .locator(
      '.source-badge, .view-controls, .scenario-controls, .reset-view, .reconstruction-scenes, .reconstruction-views, .trajectory-evidence, .reconstruction-explainer',
    )
    .evaluateAll((elements) =>
      elements
        .filter((element) =>
          element.checkVisibility({ opacityProperty: true, visibilityProperty: true }),
        )
        .map((element) => ({
          name: element.className,
          rect: element.getBoundingClientRect().toJSON(),
        })),
    );
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i].rect,
        b = boxes[j].rect;
      if (!(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top)) {
        throw new Error(`${boxes[i].name} overlaps ${boxes[j].name}`);
      }
    }
  }
}
