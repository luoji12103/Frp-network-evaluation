import { expect, test } from '@playwright/test';
import { ADMIN_STORAGE_STATE, expectNoHorizontalOverflow, openAdminRoute } from './helpers';

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
    await expectNoHorizontalOverflow(page);
  }
});

test('mobile admin navigation uses a drawer and returns to content', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'mobile drawer is only rendered on mobile viewports');

  await page.goto('/admin/nodes');
  await expect(page.getByRole('heading', { name: 'Nodes', exact: true })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.getByRole('button', { name: /menu/i }).click();
  await expect(page.locator('#admin-mobile-nav')).toBeVisible();
  await page.getByRole('link', { name: 'Alerts' }).click();
  await expect(page.getByRole('heading', { name: 'Alerts', exact: true })).toBeVisible();
  await expect(page.locator('#admin-mobile-nav')).toBeHidden();
});

test('slow runtime response still renders runtime detail', async ({ page }) => {
  let delayed = false;
  await page.route('**/api/v1/admin/runtime', async (route) => {
    if (!delayed) {
      delayed = true;
      await new Promise((resolve) => setTimeout(resolve, 11_000));
    }
    const response = await route.fetch();
    await route.fulfill({ response });
  });

  await page.goto('/admin');
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible();
  await expect(page.getByText('Deployment')).toBeVisible({ timeout: 25_000 });
  await expect(page.getByText('Control Mode')).toBeVisible();
});

test('nodes page exposes detail, pair code, and overview CTA navigation', async ({ page }) => {
  await openAdminRoute(page, '/admin/nodes', 'Nodes');

  await page.getByRole('button', { name: /relay-legacy-fixture|client-push-only-fixture|server-protocol-fixture/i }).first().click();
  await expect(page.getByRole('heading', { name: 'Node Detail' })).toBeVisible();

  await page.getByRole('button', { name: 'Pair code' }).click();
  await expect(page.getByTestId('pair-code-modal')).toBeVisible();
  await expect(page.getByText('Startup command', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Close' }).click();
  await expect(page.getByTestId('pair-code-modal')).toBeHidden();

  await openAdminRoute(page, '/admin', 'Overview');
  const suggestedAction = page.getByRole('link', { name: 'Open node' }).first();
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

  const startedBanner = page.getByText(/^Started /);
  await expect(startedBanner).toBeVisible();
  const runId = (await startedBanner.textContent())?.replace(/^Started\s+/, '').trim();
  if (!runId) {
    throw new Error('Manual run did not expose a run id in the success banner');
  }

  await expect.poll(async () => {
    return page.evaluate(async (id) => {
      const response = await fetch(`/api/v1/admin/runs/${id}`, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) {
        return 'missing';
      }
      const payload = await response.json();
      return String(payload.status || 'missing');
    }, runId);
  }).toMatch(/running|completed|failed/);

  await expect.poll(async () => {
    return page.evaluate(async (id) => {
      const response = await fetch(`/api/v1/admin/runs/${id}/events`, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) {
        return 0;
      }
      const payload = await response.json();
      return Array.isArray(payload.items) ? payload.items.length : 0;
    }, runId);
  }, { timeout: 60_000 }).toBeGreaterThan(0);
});

test('alerts mutation and actions detail remain usable', async ({ page }) => {
  await openAdminRoute(page, '/admin/alerts', 'Alerts');

  const acknowledge = page.getByRole('button', { name: 'Acknowledge' }).first();
  if ((await acknowledge.count()) && (await acknowledge.isEnabled())) {
    await acknowledge.click();
    await expect(page.getByText(/Alert .* acknowledged/)).toBeVisible();
  }

  const silenceButtons = page.getByRole('button', { name: /^Silence$/ });
  let openedSilence = false;
  for (let index = 0; index < await silenceButtons.count(); index += 1) {
    const silenceButton = silenceButtons.nth(index);
    if (await silenceButton.isEnabled()) {
      await silenceButton.click();
      openedSilence = true;
      break;
    }
  }

  if (openedSilence) {
    await expect(page.getByTestId('silence-modal')).toBeVisible();
    await expect(page.getByRole('button', { name: /Silence alert #/ })).toBeDisabled();
    await page.getByLabel('Duration').selectOption('6');
    await page.getByLabel('Reason').fill('E2E validation silence reason');
    await page.getByRole('button', { name: /Silence alert #/ }).click();
    await expect(page.getByText(/Alert .* silenced until/)).toBeVisible();
  } else {
    await expect(page.getByRole('button', { name: 'Silenced' }).first()).toBeVisible();
  }

  await openAdminRoute(page, '/admin/actions', 'Actions');
  await page.getByRole('button', { name: /sync_runtime|tail_log|restart/i }).first().click();
  await expect(page.getByRole('heading', { name: 'Action Detail' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Target Snapshot' })).toBeVisible();
});

test('stale dashboard refresh cannot overwrite newer SSR snapshot', async ({ page }) => {
  let servedStaleDashboard = false;

  try {
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
    await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible();
    await expect.poll(() => servedStaleDashboard).toBeTruthy();
    await expect(page.getByLabel('Topology Name')).not.toHaveValue('stale-regression-should-not-render');
  } finally {
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  }
});
