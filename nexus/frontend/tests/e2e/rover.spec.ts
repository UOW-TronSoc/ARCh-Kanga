import { expect, test } from '@playwright/test';

test('renders the Rover workspace in the default safe mock state', async ({ page }) => {
  await page.goto('/rover');
  await expect(page.getByRole('heading', { name: 'Kanga' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Release drivestop/ })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Main view: Rover model' })).toBeVisible();
  await expect(page.getByLabel('Mock scenario')).toHaveCount(0);
});

test('swaps a camera inset into the main view', async ({ page }) => {
  await page.goto('/rover');
  await page.getByRole('button', { name: 'Show Front navigation in main view' }).click();
  await expect(page.getByRole('region', { name: 'Main view: Front navigation' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Inset 1: Rover model' })).toBeVisible();
});

test('captures the default safe workspace state', async ({ page }, testInfo) => {
  await page.goto('/rover');
  await expect(page).toHaveScreenshot(`rover-safe-default-${testInfo.project.name}.png`, { fullPage: true });
});