import { expect, test } from '@playwright/test';
import { assertPageClean } from '../support/checks';
import { DISPLAY_NAMES, SLUGS } from '../support/constants';
import { CHARGES_COPY, formatChargeCountLine } from '../../apps/web/app/charges/charges-copy';
import { CHARGE_RESULT_COPY } from '../../apps/web/app/components/charge-result-copy';

/**
 * Charges directory flow (task DP-4): load, filter, no-match/clear, row
 * navigation, nav active state — with the page gate (axe + copy + privacy) on
 * the default and no-match states. Pinned copy is imported from the web copy
 * module, never re-typed.
 */

function directoryRows(page: import('@playwright/test').Page) {
  return page.getByRole('main').getByRole('listitem');
}

function filterInput(page: import('@playwright/test').Page) {
  return page.getByRole('textbox', { name: CHARGES_COPY.filterLabel });
}

test('directory loads: rows, reconciling count line, nav active state', async ({ page }) => {
  await page.goto('/charges');

  await expect(page.getByRole('heading', { level: 1, name: CHARGES_COPY.heading })).toBeVisible();
  // Loading resolved to the content arm — neither the loading message nor the
  // error heading remains.
  await expect(page.getByText(CHARGES_COPY.loadingMessage)).toHaveCount(0);
  await expect(page.getByText(CHARGE_RESULT_COPY.errorHeading)).toHaveCount(0);

  // The count line renders the sanctioned form for exactly the row count.
  const rowCount = await directoryRows(page).count();
  expect(rowCount).toBeGreaterThan(0);
  await expect(page.getByText(formatChargeCountLine(rowCount))).toBeVisible();

  // Review-gate pin, end-to-end: the row link is named by its charge.
  await expect(page.getByRole('link', { name: DISPLAY_NAMES.chargeDataBearing })).toBeVisible();

  // DP-5: every row carries the pinned sample-size line, and the served order
  // is sample-size descending — the rendered values never increase down the
  // list (the ORDER BY key is the served outcomeSampleSize expression).
  const sampleLines = await directoryRows(page)
    .locator('p', { hasText: /^Sample size: / })
    .allTextContents();
  expect(sampleLines).toHaveLength(rowCount);
  const values = sampleLines.map((line) =>
    Number(line.replace('Sample size: ', '').replaceAll(',', '')),
  );
  for (const value of values) {
    expect(Number.isFinite(value)).toBe(true);
  }
  expect(values).toEqual([...values].sort((a, b) => b - a));

  // Nav: Home · Charges · Methodology with the directory active — and only it.
  const nav = page.getByRole('navigation', { name: 'Main navigation' });
  await expect(nav.getByRole('link')).toHaveText(['Home', 'Charges', 'Methodology']);
  await expect(nav.getByRole('link', { name: 'Charges' })).toHaveAttribute('aria-current', 'page');
  await expect(nav.getByRole('link', { name: 'Home' })).not.toHaveAttribute('aria-current', 'page');

  await assertPageClean(page, 'charges directory (default)');
});

test('filter narrows to a match and the live count follows', async ({ page }) => {
  await page.goto('/charges');
  await expect(directoryRows(page).first()).toBeVisible();

  await filterInput(page).fill(DISPLAY_NAMES.chargeDataBearing);

  await expect(directoryRows(page)).toHaveCount(1);
  await expect(page.getByText(formatChargeCountLine(1))).toBeVisible();
  await expect(page.getByRole('link', { name: DISPLAY_NAMES.chargeDataBearing })).toBeVisible();
});

test('no-match state offers clear, which restores the list and refocuses', async ({ page }) => {
  await page.goto('/charges');
  await expect(directoryRows(page).first()).toBeVisible();
  const rowCount = await directoryRows(page).count();

  await filterInput(page).fill('zzz no such charge');

  await expect(page.getByText(CHARGES_COPY.noMatchBody)).toBeVisible();
  await expect(page.getByText(formatChargeCountLine(0))).toBeVisible();
  await expect(directoryRows(page)).toHaveCount(0);

  await assertPageClean(page, 'charges directory (no-match)');

  await page.getByRole('button', { name: CHARGES_COPY.clearAction }).click();
  await expect(filterInput(page)).toHaveValue('');
  await expect(filterInput(page)).toBeFocused();
  await expect(directoryRows(page)).toHaveCount(rowCount);
});

test('a directory row navigates to its charge result page', async ({ page }) => {
  await page.goto('/charges');

  await page.getByRole('link', { name: DISPLAY_NAMES.chargeDataBearing }).click();

  await expect(page).toHaveURL(`/charges/${SLUGS.chargeDataBearing}`);
  await expect(page.getByTestId('section-summary')).toBeVisible();
});

test.describe('390px mobile', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test('directory at 390px: no horizontal scroll', async ({ page }) => {
    await page.goto('/charges');
    await expect(directoryRows(page).first()).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

test.describe('1440px wide desktop', () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test('directory at 1440px: no horizontal scroll', async ({ page }) => {
    await page.goto('/charges');
    await expect(directoryRows(page).first()).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
});
