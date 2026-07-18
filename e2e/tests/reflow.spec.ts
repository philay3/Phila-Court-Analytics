import { expect, test, type Page } from '@playwright/test';
import { assertPageClean } from '../support/checks';
import { SLUGS } from '../support/constants';
import { CHARGE_RESULT_COPY } from '../../apps/web/app/components/charge-result-copy';
import { CHARGES_COPY } from '../../apps/web/app/charges/charges-copy';

/**
 * DP-3 reflow checks (pre-authorized E2E additions); DP-4 adds the charges
 * directory to both tiers.
 *
 * 320px (WCAG 1.4.10 reflow): the homepage — with the judge disclosure both
 * closed and open — the charge result page, and the charges directory must
 * not scroll horizontally at the narrowest supported viewport. 1024px
 * (compact desktop, 900–1199 tier): the charge result page renders the
 * two-column grid — metadata aside beside the main column, not below it —
 * still with no horizontal scroll.
 */

function horizontalOverflow(page: Page): Promise<number> {
  return page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
}

test.describe('320px reflow (WCAG 1.4.10)', () => {
  test.use({ viewport: { width: 320, height: 568 } });

  test('homepage at 320px: no horizontal scroll, disclosure closed and open', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();

    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);

    // Opening the judge disclosure must not introduce overflow either.
    await page.getByRole('button', { name: CHARGE_RESULT_COPY.judgeDisclosureTriggerText }).click();
    await expect(page.locator('#judge-search')).toBeVisible();
    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);

    await assertPageClean(page, 'homepage (320px, judge disclosure open)');
  });

  test('charge result at 320px: no horizontal scroll, aside in flow', async ({ page }) => {
    await page.goto(`/charges/${SLUGS.chargeDataBearing}`);
    await expect(page.getByTestId('section-summary')).toBeVisible();

    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);

    // Single column below 900px: the aside renders at its DOM position —
    // BELOW the distributions, never beside them.
    const outcomeBox = await page.getByTestId('section-outcome').boundingBox();
    const asideBox = await page.getByTestId('section-metadata').boundingBox();
    expect(outcomeBox).not.toBeNull();
    expect(asideBox).not.toBeNull();
    expect(asideBox!.y).toBeGreaterThan(outcomeBox!.y + outcomeBox!.height - 1);

    await assertPageClean(page, 'charge-only result (320px)');
  });

  test('charges directory at 320px: no horizontal scroll, three-item nav fits', async ({
    page,
  }) => {
    await page.goto('/charges');
    await expect(page.getByRole('heading', { level: 1, name: CHARGES_COPY.heading })).toBeVisible();

    // AC 6: the 320px fit re-proven with the live third nav item.
    const nav = page.getByRole('navigation', { name: 'Main navigation' });
    await expect(nav.getByRole('link')).toHaveText(['Home', 'Charges', 'Methodology']);
    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);

    await assertPageClean(page, 'charges directory (320px)');
  });
});

test.describe('1024px compact desktop smoke (900–1199 tier)', () => {
  test.use({ viewport: { width: 1024, height: 768 } });

  test('charge result at 1024px: two-column grid with the aside beside the main column', async ({
    page,
  }) => {
    await page.goto(`/charges/${SLUGS.chargeDataBearing}`);
    await expect(page.getByTestId('section-summary')).toBeVisible();

    const summaryBox = await page.getByTestId('section-summary').boundingBox();
    const asideBox = await page.getByTestId('section-metadata').boundingBox();
    expect(summaryBox).not.toBeNull();
    expect(asideBox).not.toBeNull();
    // Beside, not below: the aside starts right of the main column and
    // overlaps it vertically (sticky top offset keeps it near the top).
    expect(asideBox!.x).toBeGreaterThan(summaryBox!.x + summaryBox!.width);
    expect(asideBox!.y).toBeLessThan(summaryBox!.y + summaryBox!.height);

    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);

    await assertPageClean(page, 'charge-only result (1024px compact desktop)');
  });

  test('charges directory at 1024px: no horizontal scroll', async ({ page }) => {
    await page.goto('/charges');
    await expect(page.getByRole('heading', { level: 1, name: CHARGES_COPY.heading })).toBeVisible();

    expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);

    await assertPageClean(page, 'charges directory (1024px compact desktop)');
  });
});
