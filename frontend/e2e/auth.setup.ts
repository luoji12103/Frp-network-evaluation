import fs from 'node:fs/promises';
import path from 'node:path';
import { test as setup } from '@playwright/test';
import { ADMIN_STORAGE_STATE, loginAsAdmin } from './helpers';

setup('login and persist admin storage state', async ({ page }) => {
  await loginAsAdmin(page);
  await fs.mkdir(path.dirname(ADMIN_STORAGE_STATE), { recursive: true });
  await page.context().storageState({ path: ADMIN_STORAGE_STATE });
});
