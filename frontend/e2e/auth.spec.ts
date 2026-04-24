import { expect, test } from '@playwright/test';
import { loginAsAdmin } from './helpers';

test.use({ storageState: { cookies: [], origins: [] } });

test('admin login and logout work end-to-end', async ({ page }) => {
  await loginAsAdmin(page);
  await Promise.all([
    page.waitForURL(/\/$/),
    page.getByRole('button', { name: 'Sign out' }).click(),
  ]);
  await expect(page.getByText('Public Panel', { exact: true })).toBeVisible();

  await page.goto('/admin');
  await expect(page).toHaveURL(/\/login\?next=(%2F|\/)admin$/);
  await expect(page.getByRole('heading', { name: 'Control Panel Login' })).toBeVisible();
});
