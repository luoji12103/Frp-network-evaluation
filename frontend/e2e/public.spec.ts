import { expect, test } from '@playwright/test';
import { expectNoHorizontalOverflow, firstPublicPathId } from './helpers';

test('public overview, path, and role pages render and refresh', async ({ page, request }) => {
  await page.goto('/');
  await expect(page.getByText('Public Panel', { exact: true })).toBeVisible();
  await expect(page.getByTestId('build-label')).toBeVisible();
  await expectNoHorizontalOverflow(page);

  const pathId = await firstPublicPathId(request);
  await page.goto(`/public/path/${encodeURIComponent(pathId)}`);
  await expect(page.getByRole('heading', { name: pathId })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.reload();
  await expect(page.getByRole('heading', { name: pathId })).toBeVisible();

  await page.goto('/public/role/client');
  await expect(page.getByRole('heading', { name: 'client role' })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'client role' })).toBeVisible();
});

test('public overview collapses empty trend groups into one compact notice', async ({ page }) => {
  await page.route('**/api/v1/public-dashboard', async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    await route.fulfill({
      response,
      json: {
        ...payload,
        history: {
          ...(payload.history ?? {}),
          trend_groups: {
            latency: { series: [] },
            jitter: { series: [] },
            loss: { series: [] },
            throughput: { series: [] },
          },
        },
      },
    });
  });

  await page.goto('/');
  await expect(page.getByText('No public metric series are available')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'latency' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'jitter' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'loss' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'throughput' })).toHaveCount(0);
});
