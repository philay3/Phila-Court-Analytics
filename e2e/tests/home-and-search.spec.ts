import { expect, test } from '@playwright/test';
import { assertPageClean } from '../support/checks';
import { selectFromCombobox } from '../support/combobox';
import { DISPLAY_NAMES, SLUGS } from '../support/constants';
import { HOME_COPY } from '../../apps/web/app/components/home-copy';

/**
 * Homepage layout + the charge autocomplete happy path (task 15.2 scope 2:
 * homepage, charge-primary/judge-optional, keyboard selection → charge-only
 * result). Every rendered state is run through the axe + copy + privacy gate.
 */

test('homepage: charge search is primary, judge input is visibly optional', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { level: 1, name: HOME_COPY.heading })).toBeVisible();

  // The charge combobox is present and labelled as the primary entry point.
  await expect(page.locator('#charge-search')).toBeVisible();
  await expect(page.getByText(HOME_COPY.chargeLabel, { exact: true })).toBeVisible();

  // The judge input is present but flagged optional in its own label copy.
  await expect(page.locator('#judge-search')).toBeVisible();
  await expect(page.getByText(HOME_COPY.judgeLabel, { exact: true })).toBeVisible();

  await assertPageClean(page, 'homepage');
});

test('charge autocomplete: query → suggestion → keyboard select → charge-only result', async ({
  page,
}) => {
  await page.goto('/');

  // Type a query, wait for the debounced listbox, move with ArrowDown, commit
  // with Enter (the keyboard contract the task calls out explicitly).
  await selectFromCombobox(page, '#charge-search', 'retail', DISPLAY_NAMES.chargeDataBearing);

  await page.locator('form button[type="submit"]').click();

  await expect(page).toHaveURL(new RegExp(`/charges/${SLUGS.chargeDataBearing}$`));
  await expect(
    page.getByRole('heading', { level: 1, name: DISPLAY_NAMES.chargeDataBearing }),
  ).toBeVisible();

  await assertPageClean(page, 'charge-only result (reached via search)');
});
