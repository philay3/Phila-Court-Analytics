import { expect, test } from '@playwright/test';
import { assertPageClean } from '../support/checks';
import { SLUGS } from '../support/constants';

/**
 * Mobile (390px) pass of the charge-only result page (task 15.2 scope 2 /
 * pinned 13.2 decision 6). Asserts the DOM-source content order and that the
 * page never scrolls horizontally at a narrow viewport, then runs the page gate.
 */

// The pinned 13.2 mobile content order for a NON-thin charge (retail-theft has
// no thin-data callout): summary → responsible-use → outcome → sentencing →
// links → judge-filter entry. Source order in a single-column, mobile-first
// layout — no CSS `order`.
const EXPECTED_SECTION_ORDER = [
  'section-summary',
  'section-responsible-use',
  'section-outcome',
  'section-sentencing',
  'section-links',
  'section-judge-filter',
];

test.use({ viewport: { width: 390, height: 844 } });

test('charge-only result at 390px: content order holds and no horizontal scroll', async ({
  page,
}) => {
  await page.goto(`/charges/${SLUGS.chargeDataBearing}`);
  await expect(page.getByTestId('section-summary')).toBeVisible();

  const order = await page
    .locator('[data-testid^="section-"]')
    .evaluateAll((nodes) => nodes.map((n) => n.getAttribute('data-testid')));
  expect(order).toEqual(EXPECTED_SECTION_ORDER);

  // No horizontal overflow: the document is not wider than the viewport.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);

  await assertPageClean(page, 'charge-only result (390px mobile)');
});
