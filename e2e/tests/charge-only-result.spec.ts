import { expect, test } from '@playwright/test';
import {
  AGGREGATE_RUN_LABEL_PREFIX,
  RECORDS_LABEL_PREFIX,
  SENTENCED_CONVICTIONS_LABEL_PREFIX,
  SENTENCE_COMPONENTS_LABEL_PREFIX,
  SENTENCING_DETAIL_CAPTION,
  SENTENCING_INDEX_CAPTION,
} from '@pca/shared';
import { assertPageClean } from '../support/checks';
import { DISPLAY_NAMES, SLUGS } from '../support/constants';
import { RESULT_DISPLAY_COPY } from '../../apps/web/app/components/result-display-copy';
import {
  formatGradeMixLine,
  formatZeroSentencedFallback,
  formatWedgeDisclosure,
  THIN_DATA_LABEL,
} from '../../apps/web/app/lib/formatters';

/**
 * Charge-only result page across its seeded scenarios (task 15.2 scope 2;
 * 35.3 index arms): the present arm (index lead block, detail block below,
 * outcome last), a thin-data charge, the zero-sentenced fallback arm, and the
 * absent-arm stability lock (today's post-Phase-33 page). Each state passes
 * the page gate (axe + both copy scanners). All numbers asserted here are the
 * fabricated seeded-matrix values — never corpus figures.
 */

// Top-level pinned order helper (parity with the unit-test helper): testids
// nested inside the metadata aside are its contents, not page-level order.
async function sectionOrder(page: import('@playwright/test').Page): Promise<(string | null)[]> {
  return page.locator('[data-testid^="section-"]').evaluateAll((nodes) =>
    nodes
      .filter((n) => {
        const aside = n.closest('[data-testid="section-metadata"]');
        return aside === null || aside === n;
      })
      .map((n) => n.getAttribute('data-testid')),
  );
}

test('present arm: index leads, detail below, outcome last; wedge, grades, medians render', async ({
  page,
}) => {
  await page.goto(`/charges/${SLUGS.chargeDataBearing}`);

  await expect(
    page.getByRole('heading', { level: 1, name: DISPLAY_NAMES.chargeDataBearing }),
  ).toBeVisible();

  // 35.3 pin 1 order: index lead → component-grain sentencing detail →
  // outcome → aside.
  expect(await sectionOrder(page)).toEqual([
    'section-summary',
    'section-responsible-use',
    'section-sentencing-index',
    'section-sentencing',
    'section-outcome',
    'section-metadata',
  ]);

  // The lead block: conditional caption, sentenced-convictions label
  // (seeded: 588), index bars, wedge disclosure with the seeded values
  // (12 of 600, 2%), and the grade-mix line (dominant-first, gated ungraded
  // label, M2/S equal-count tiebreak as served).
  const index = page.getByTestId('section-sentencing-index');
  await expect(index.getByRole('table')).toBeVisible();
  await expect(index.getByText(SENTENCING_INDEX_CAPTION)).toBeVisible();
  await expect(index.getByText(`${SENTENCED_CONVICTIONS_LABEL_PREFIX}588`)).toBeVisible();
  expect(await index.locator('[data-testid^="index-bar-fill-"]').count()).toBeGreaterThan(0);
  await expect(index.getByTestId('index-wedge-disclosure')).toHaveText(
    formatWedgeDisclosure({
      convictions: 600,
      sentencedConvictions: 588,
      wedgeCount: 12,
      wedgePercentage: 2,
      thinData: false,
      dateRange: { start: '2025-01-03', end: '2026-06-27' },
    }),
  );
  await expect(index.getByTestId('index-grade-mix')).toHaveText(
    formatGradeMixLine([
      { grade: 'F3', convictionCount: 300, percentageOfConvictions: 50 },
      { grade: 'M1', convictionCount: 150, percentageOfConvictions: 25 },
      { grade: 'M2', convictionCount: 60, percentageOfConvictions: 10 },
      { grade: 'S', convictionCount: 60, percentageOfConvictions: 10 },
      { grade: 'ungraded', convictionCount: 30, percentageOfConvictions: 5 },
    ]) ?? '',
  );

  // Median pairs (pin 4): the seeded probation range (360/540 days → 12–18)
  // and the half-up tie (10.5/90 days → 0.4–3) render as served months.
  await expect(index.getByRole('table')).toContainText('12–18');
  await expect(index.getByRole('table')).toContainText('0.4–3');

  // The component-grain block renders below under the distinct detail
  // caption (pin 11) with its reconciled sentence-components label; the
  // outcome block carries the records label.
  const sentencing = page.getByTestId('section-sentencing');
  await expect(sentencing.getByRole('table')).toBeVisible();
  await expect(sentencing.getByText(SENTENCING_DETAIL_CAPTION)).toBeVisible();
  await expect(
    sentencing.getByText(new RegExp(`^${SENTENCE_COMPONENTS_LABEL_PREFIX}`)),
  ).toBeVisible();

  const outcome = page.getByTestId('section-outcome');
  await expect(outcome.getByRole('table')).toBeVisible();
  await expect(outcome.getByText(new RegExp(`^${RECORDS_LABEL_PREFIX}`))).toBeVisible();
  expect(await outcome.locator('[data-testid^="distribution-bar-fill-"]').count()).toBeGreaterThan(
    0,
  );

  // Provenance line (pin 7): pinned prefix + the 8-char short id.
  await expect(page.getByTestId('aggregate-run-line')).toHaveText(
    new RegExp(`^${AGGREGATE_RUN_LABEL_PREFIX}[0-9a-f]{8}$`),
  );

  await assertPageClean(page, 'charge-only result (present arm)');
});

test('thin-data charge: page-level thin callout renders; index thin badge present', async ({
  page,
}) => {
  await page.goto(`/charges/${SLUGS.chargeThin}`);

  await expect(page.getByTestId('section-thin-data')).toBeVisible();
  await expect(page.getByTestId('section-outcome').getByRole('table')).toBeVisible();
  // The seeded criminal-trespass index cell is thin (5 sentenced): the lead
  // block renders with the byte-identical thin badge inside it.
  const index = page.getByTestId('section-sentencing-index');
  await expect(index.getByRole('table')).toBeVisible();
  await expect(index.getByText(THIN_DATA_LABEL)).toBeVisible();

  await assertPageClean(page, 'charge-only result (thin data)');
});

test('zero-sentenced arm: outcome first, fallback line carries the conviction count, no generic notice', async ({
  page,
}) => {
  await page.goto(`/charges/${SLUGS.chargeZeroSentenced}`);

  // Ruling 4 / pin 3: outcome leads; the index slot renders the fallback
  // line; the seeded summary is thin so the page-level callout renders too.
  expect(await sectionOrder(page)).toEqual([
    'section-summary',
    'section-responsible-use',
    'section-thin-data',
    'section-outcome',
    'section-sentencing-index',
    'section-metadata',
  ]);

  await expect(page.getByTestId('section-sentencing-index')).toHaveText(
    formatZeroSentencedFallback(323),
  );
  // Ruling Q4: the fallback line REPLACES the generic sentencing-unavailable
  // notice, and no index table renders on this arm.
  await expect(page.getByTestId('section-sentencing')).toHaveCount(0);
  await expect(page.getByTestId('section-sentencing-index').getByRole('table')).toHaveCount(0);

  await assertPageClean(page, 'charge-only result (zero-sentenced arm)');
});

test("absent arm: today's post-Phase-33 page, structurally locked, with reconciled labels", async ({
  page,
}) => {
  await page.goto(`/charges/${SLUGS.chargeIndexAbsent}`);

  // Pin 2: no index section anywhere; the 33.2 conditional order holds
  // (sentencing available for this seed → sentencing leads, outcome below).
  expect(await sectionOrder(page)).toEqual([
    'section-summary',
    'section-responsible-use',
    'section-sentencing',
    'section-outcome',
    'section-metadata',
  ]);
  await expect(page.getByTestId('section-sentencing-index')).toHaveCount(0);

  // Today's conditional-framing caption is byte-unchanged on this arm; only
  // the reconciled sample labels differ (ruling Q1).
  const sentencing = page.getByTestId('section-sentencing');
  await expect(sentencing.getByText(RESULT_DISPLAY_COPY.sentencingCaption)).toBeVisible();
  await expect(
    sentencing.getByText(new RegExp(`^${SENTENCE_COMPONENTS_LABEL_PREFIX}`)),
  ).toBeVisible();
  await expect(
    page.getByTestId('section-outcome').getByText(new RegExp(`^${RECORDS_LABEL_PREFIX}`)),
  ).toBeVisible();

  await assertPageClean(page, 'charge-only result (absent arm lock)');
});
