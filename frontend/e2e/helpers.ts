import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { expect, type APIRequestContext, type Page } from '@playwright/test';

const E2E_DIR = path.dirname(fileURLToPath(import.meta.url));

export const ADMIN_STORAGE_STATE = path.join(E2E_DIR, '.auth', 'admin.json');

export function adminCredentials() {
  return {
    username: process.env.PANEL_ADMIN_USERNAME ?? 'admin',
    password: process.env.PANEL_ADMIN_PASSWORD ?? 'change-me',
  };
}

export async function loginAsAdmin(page: Page, nextPath = '/admin') {
  const creds = adminCredentials();
  await page.goto(`/login?next=${encodeURIComponent(nextPath)}`);
  await expect(page.getByRole('heading', { name: 'Control Panel Login' })).toBeVisible();
  await page.getByLabel('Username').fill(creds.username);
  await page.getByLabel('Password').fill(creds.password);
  await Promise.all([
    page.waitForURL(/\/admin(?:[/?#].*)?$/),
    page.getByRole('button', { name: 'Sign In' }).click(),
  ]);
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible();
}

export function visibleBuildLabel(page: Page) {
  return page.locator('[data-testid="build-label"], [data-testid="mobile-build-label"]').filter({ visible: true }).first();
}

export async function openAdminRoute(page: Page, route: string, heading: string) {
  await page.goto(route);
  await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
  await expect(visibleBuildLabel(page)).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
}

export async function expectNoHorizontalOverflow(page: Page) {
  await expect.poll(async () => {
    return page.evaluate(() => document.body.scrollWidth <= document.documentElement.clientWidth + 1);
  }).toBeTruthy();
}

export async function firstPublicPathId(request: APIRequestContext) {
  const response = await request.get('/api/v1/public-dashboard');
  expect(response.ok()).toBeTruthy();
  const payload = await response.json();
  const item = payload.paths?.[0];
  const pathId = item?.path_id || item?.path_label;
  if (!pathId) {
    throw new Error('Public dashboard did not return a path id for E2E navigation');
  }
  return String(pathId);
}
