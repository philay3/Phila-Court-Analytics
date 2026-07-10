import { expect, test } from '@playwright/test';
import { CHARGE_NOT_FOUND_MESSAGE, CHARGE_RESULT_UNAVAILABLE_MESSAGE } from '@pca/shared';
import { assertPageClean } from '../support/checks';
import { SLUGS } from '../support/constants';
import { CHARGE_RESULT_COPY } from '../../apps/web/app/components/charge-result-copy';

/**
 * Charge/judge unavailable + not-found designed states (task 15.2 scope 2),
 * including the W1 regression lock. Pinned messages are asserted via
 * @pca/shared imports; the generic error boundary's heading is imported from
 * the web copy module and asserted ABSENT so a regression to the boundary fails.
 */

test('W1 regression: harassment + judge renders friendly CHARGE_RESULT_UNAVAILABLE, not the error boundary', async ({
  page,
}) => {
  // The judge route returns this case as a 404 CHARGE_RESULT_UNAVAILABLE error
  // envelope; task 15.1 mapped it to the designed JudgeChargeUnavailableView.
  await page.goto(`/charges/${SLUGS.chargeUnavailable}/judge/${SLUGS.judgeDataBearing}`);

  // Friendly designed state: pinned message (imported) + its designed heading.
  await expect(page.getByText(CHARGE_RESULT_UNAVAILABLE_MESSAGE)).toBeVisible();
  await expect(
    page.getByRole('heading', { level: 1, name: CHARGE_RESULT_COPY.chargeUnavailableHeading }),
  ).toBeVisible();

  // NOT the generic error boundary.
  await expect(page.getByText(CHARGE_RESULT_COPY.errorHeading)).toHaveCount(0);

  await assertPageClean(page, 'W1 — judge-route charge-result-unavailable');
});

test('charge-only unavailable: harassment renders its designed unavailable state', async ({
  page,
}) => {
  await page.goto(`/charges/${SLUGS.chargeUnavailable}`);

  await expect(page.getByText(CHARGE_RESULT_UNAVAILABLE_MESSAGE)).toBeVisible();
  // The charge-only arm carries the charge identity as its h1 (not the generic
  // heading the judge route uses), and it is not the error boundary.
  await expect(page.getByText(CHARGE_RESULT_COPY.errorHeading)).toHaveCount(0);

  await assertPageClean(page, 'charge-only unavailable');
});

test('not-found: unknown charge slug renders the friendly not-found state', async ({ page }) => {
  await page.goto(`/charges/${SLUGS.chargeUnknown}`);

  await expect(
    page.getByRole('heading', { level: 1, name: CHARGE_RESULT_COPY.notFoundHeading }),
  ).toBeVisible();
  await expect(page.getByText(CHARGE_NOT_FOUND_MESSAGE)).toBeVisible();
  await expect(page.getByText(CHARGE_RESULT_COPY.errorHeading)).toHaveCount(0);

  await assertPageClean(page, 'charge not-found');
});
