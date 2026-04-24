import { expect, test } from '@playwright/test';
import { firstPublicPathId } from './helpers';

test('public overview, path, and role pages render and refresh', async ({ page, request }) => {
  await page.goto('/');
  await expect(page.getByText('Public Panel', { exact: true })).toBeVisible();
  await expect(page.getByTestId('build-label')).toBeVisible();

  const pathId = await firstPublicPathId(request);
  await page.goto(`/public/path/${encodeURIComponent(pathId)}`);
  await expect(page.getByRole('heading', { name: pathId })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: pathId })).toBeVisible();

  await page.goto('/public/role/client');
  await expect(page.getByRole('heading', { name: 'client role' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'client role' })).toBeVisible();
});
