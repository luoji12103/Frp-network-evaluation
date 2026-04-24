import { expect, test } from '@playwright/test';
import { ADMIN_STORAGE_STATE, openAdminRoute } from './helpers';

test.use({ storageState: ADMIN_STORAGE_STATE });

const adminRoutes = [
  { path: '/admin', heading: 'Overview' },
  { path: '/admin/nodes', heading: 'Nodes' },
  { path: '/admin/paths', heading: 'Paths' },
  { path: '/admin/runs', heading: 'Runs' },
  { path: '/admin/alerts', heading: 'Alerts' },
  { path: '/admin/actions', heading: 'Actions' },
  { path: '/admin/schedules', heading: 'Schedules' },
  { path: '/admin/settings', heading: 'Settings' },
];

test('admin routes support direct navigation and refresh', async ({ page }) => {
  for (const route of adminRoutes) {
    await openAdminRoute(page, route.path, route.heading);
  }
});

test('nodes page exposes detail, pair code, and CTA navigation', async ({ page }) => {
  await openAdminRoute(page, '/admin/nodes', 'Nodes');

  await page.getByRole('button', { name: /relay-legacy-fixture|client-push-only-fixture|server-protocol-fixture/i }).first().click();
  await expect(page.getByRole('heading', { name: 'Node Detail' })).toBeVisible();

  await page.getByRole('button', { name: 'Pair code' }).click();
  await expect(page.getByTestId('pair-code-modal')).toBeVisible();
  await expect(page.getByText('Startup command')).toBeVisible();
  await page.getByRole('button', { name: 'Close' }).click();
  await expect(page.getByTestId('pair-code-modal')).toBeHidden();

  const detailSurface = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Node Detail' }) }).first();
  const suggestedAction = detailSurface.locator('a[href*="/admin"]').first();
  await expect(suggestedAction).toBeVisible();
  const previousUrl = page.url();
  await suggestedAction.click();
  await expect.poll(() => page.url()).not.toBe(previousUrl);
  await expect(page).toHaveURL(/\/admin/);
});

test('manual run produces detail and timeline data', async ({ page }) => {
  await openAdminRoute(page, '/admin/runs', 'Runs');

  const controls = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Manual Run and Filters' }) }).first();
  await controls.getByRole('button', { name: /system/i }).click();

  await expect(page.getByText(/^Started /)).toBeVisible();
  const detailSurface = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Run Detail' }) }).first();
  await expect(detailSurface).toContainText(/running|completed|failed/i);
  await expect(page.locator('section').filter({ has: page.getByRole('heading', { name: 'Event Timeline' }) }).locator('.rounded-2xl').first()).toBeVisible({ timeout: 60_000 });
});

test('alerts mutation and actions detail remain usable', async ({ page }) => {
  await openAdminRoute(page, '/admin/alerts', 'Alerts');

  await page.getByRole('button', { name: 'ack' }).first().click();
  await expect(page.getByText(/Alert .* ack succeeded/)).toBeVisible();
  await page.getByRole('button', { name: 'silence' }).first().click();
  await expect(page.getByText(/Alert .* silence succeeded/)).toBeVisible();

  await openAdminRoute(page, '/admin/actions', 'Actions');
  await page.getByRole('button', { name: /sync_runtime|tail_log|restart/i }).first().click();
  await expect(page.getByRole('heading', { name: 'Action Detail' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Target Snapshot' })).toBeVisible();
});

test('stale dashboard refresh cannot overwrite newer SSR snapshot', async ({ page }) => {
  let servedStaleDashboard = false;

  await page.route('**/api/v1/dashboard', async (route) => {
    servedStaleDashboard = true;
    const response = await route.fetch();
    const payload = await response.json();
    await route.fulfill({
      response,
      json: {
        ...payload,
        generated_at: '2000-01-01T00:00:00+00:00',
        settings: {
          ...payload.settings,
          topology_name: 'stale-regression-should-not-render',
        },
      },
    });
  });

  await page.goto('/admin/settings');
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
  await expect.poll(() => servedStaleDashboard).toBeTruthy();
  await expect(page.getByDisplayValue('stale-regression-should-not-render')).toHaveCount(0);
});
