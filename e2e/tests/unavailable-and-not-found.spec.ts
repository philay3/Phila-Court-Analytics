import { expect, test } from '@playwright/test';
import {
  BROWSE_ALL_CHARGES_LINK_TEXT,
  CHARGE_RESULT_UNAVAILABLE_MESSAGE,
  JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
  ROOT_NOT_FOUND_HEADING,
  ROOT_NOT_FOUND_HOME_LINK_TEXT,
  ROOT_NOT_FOUND_MESSAGE,
} from '@pca/shared';
import { assertPageClean } from '../support/checks';
import { SLUGS } from '../support/constants';
import { CHARGE_RESULT_COPY } from '../../apps/web/app/components/charge-result-copy';
import { JUDGE_RESULT_COPY } from '../../apps/web/app/components/judge-result-copy';

/**
 * Unavailable + not-found states on the static site (task 15.2 scope 2; task
 * STATIC-2b). The W1 regression lock moves to the in-page `?judge=` form; an
 * unknown charge slug — like any unknown path — is answered by Cloudflare
 * Pages with the ROOT 404 page and a real 404 status (pin 7); the retired
 * `/charges/<charge>/judge/<judge>` form is a 301 to the `?judge=` form via
 * `_redirects` (pin 9). Pinned messages are asserted via @pca/shared imports;
 * the generic error boundary's heading is imported from the web copy module
 * and asserted ABSENT so a regression to the boundary fails.
 */

test('W1 regression: harassment + ?judge= renders the in-page unavailable notice over the charge-only unavailable state, not the error boundary', async ({
  page,
}) => {
  // No judge has results for this charge, so its page bakes an empty judge
  // list: any `?judge=` is unpaired and the shell renders the pinned notice
  // above the charge-only unavailable state.
  await page.goto(`/charges/${SLUGS.chargeUnavailable}?judge=${SLUGS.judgeDataBearing}`);

  const notice = page.getByTestId('judge-filter-notice');
  await expect(notice).toContainText(JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE);
  await expect(
    notice.getByRole('link', { name: JUDGE_RESULT_COPY.removeFilterLinkText }),
  ).toHaveAttribute('href', `/charges/${SLUGS.chargeUnavailable}`);
  await expect(page.getByText(CHARGE_RESULT_UNAVAILABLE_MESSAGE)).toBeVisible();

  // NOT the generic error boundary.
  await expect(page.getByText(CHARGE_RESULT_COPY.errorHeading)).toHaveCount(0);

  await assertPageClean(page, 'W1 — ?judge= over charge-result-unavailable');
});

test('charge-only unavailable: harassment renders its designed unavailable state', async ({
  page,
}) => {
  await page.goto(`/charges/${SLUGS.chargeUnavailable}`);

  await expect(page.getByText(CHARGE_RESULT_UNAVAILABLE_MESSAGE)).toBeVisible();
  // The charge-only arm carries the charge identity as its h1, and it is not
  // the error boundary. No judge filter is offered: no judge has results here.
  await expect(page.getByText(CHARGE_RESULT_COPY.errorHeading)).toHaveCount(0);
  await expect(page.getByTestId('section-judge-filter')).toHaveCount(0);

  await assertPageClean(page, 'charge-only unavailable');
});

test('not-found: an unknown charge slug is served the root 404 page with a 404 status', async ({
  page,
}) => {
  const response = await page.goto(`/charges/${SLUGS.chargeUnknown}`);
  expect(response?.status()).toBe(404);

  await expect(page.getByRole('heading', { level: 1, name: ROOT_NOT_FOUND_HEADING })).toBeVisible();
  await expect(page.getByText(ROOT_NOT_FOUND_MESSAGE)).toBeVisible();
  await expect(page.getByRole('link', { name: ROOT_NOT_FOUND_HOME_LINK_TEXT })).toHaveAttribute(
    'href',
    '/',
  );
  await expect(page.getByRole('link', { name: BROWSE_ALL_CHARGES_LINK_TEXT })).toHaveAttribute(
    'href',
    '/charges',
  );
  await expect(page.getByText(CHARGE_RESULT_COPY.errorHeading)).toHaveCount(0);

  await assertPageClean(page, 'root not-found (unknown charge)');
});

test('not-found: an unknown path outside /charges gets the same root 404', async ({ page }) => {
  const response = await page.goto('/no-such-path');
  expect(response?.status()).toBe(404);
  await expect(page.getByRole('heading', { level: 1, name: ROOT_NOT_FOUND_HEADING })).toBeVisible();
});

test('legacy judge URL: /charges/<charge>/judge/<judge> is a 301 to the ?judge= form', async ({
  page,
}) => {
  const legacy = `/charges/${SLUGS.chargeDataBearing}/judge/${SLUGS.judgeDataBearing}`;
  const target = `/charges/${SLUGS.chargeDataBearing}?judge=${SLUGS.judgeDataBearing}`;

  const response = await page.request.get(legacy, { maxRedirects: 0 });
  expect(response.status()).toBe(301);
  expect(response.headers()['location']).toBe(target);

  // Following it lands on the in-page judge-specific result.
  await page.goto(legacy);
  await expect(page).toHaveURL(new RegExp(`${target.replace('?', '\\?')}$`));
  await expect(
    page.getByRole('heading', { name: JUDGE_RESULT_COPY.sectionJudgeSpecificHeading }),
  ).toBeVisible();
});
