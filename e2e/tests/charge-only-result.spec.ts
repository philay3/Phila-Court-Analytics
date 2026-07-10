import { expect, test } from '@playwright/test';
import { CHARGE_SENTENCING_UNAVAILABLE_MESSAGE } from '@pca/shared';
import { assertPageClean } from '../support/checks';
import { DISPLAY_NAMES, SLUGS } from '../support/constants';

/**
 * Charge-only result page across its seeded scenarios (task 15.2 scope 2):
 * a data-bearing charge (outcome table + bars, sentencing, sample size, date
 * range, responsible-use), a thin-data charge, and a sentencing-unavailable
 * charge (outcome persists, callout renders). Each state passes the page gate.
 */

test('data-bearing charge: outcome + sentencing distributions and framing render', async ({
  page,
}) => {
  await page.goto(`/charges/${SLUGS.chargeDataBearing}`);

  await expect(
    page.getByRole('heading', { level: 1, name: DISPLAY_NAMES.chargeDataBearing }),
  ).toBeVisible();

  // Summary block: sample size + date range are shown.
  const summary = page.getByTestId('section-summary');
  await expect(summary).toContainText(/2025/);
  await expect(summary).toContainText(/2026/);

  // Responsible-use notice is present.
  await expect(page.getByTestId('section-responsible-use')).toBeVisible();

  // Outcome distribution: the accessible table AND the presentational bars.
  const outcome = page.getByTestId('section-outcome');
  await expect(outcome.getByRole('table')).toBeVisible();
  await expect(outcome.getByText(/Sample size:/)).toBeVisible();
  expect(await outcome.locator('[data-testid^="distribution-bar-fill-"]').count()).toBeGreaterThan(
    0,
  );

  // Sentencing distribution renders in full for this charge (n present).
  const sentencing = page.getByTestId('section-sentencing');
  await expect(sentencing.getByRole('table')).toBeVisible();

  await assertPageClean(page, 'charge-only result (data-bearing)');
});

test('thin-data charge: page-level thin-data callout renders, outcome persists', async ({
  page,
}) => {
  await page.goto(`/charges/${SLUGS.chargeThin}`);

  await expect(page.getByTestId('section-thin-data')).toBeVisible();
  await expect(page.getByTestId('section-outcome').getByRole('table')).toBeVisible();

  await assertPageClean(page, 'charge-only result (thin data)');
});

test('sentencing-unavailable charge: outcome distribution persists, callout renders', async ({
  page,
}) => {
  await page.goto(`/charges/${SLUGS.chargeSentencingUnavailable}`);

  // Outcome distribution still renders in full.
  await expect(page.getByTestId('section-outcome').getByRole('table')).toBeVisible();

  // Sentencing slot shows the pinned callout instead of a table — asserted via
  // the imported @pca/shared constant, never a re-typed string.
  await expect(page.getByTestId('section-sentencing')).toContainText(
    CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  );

  await assertPageClean(page, 'charge-only result (sentencing unavailable)');
});
