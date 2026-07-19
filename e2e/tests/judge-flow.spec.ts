import { expect, test } from '@playwright/test';
import {
  JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
  RECORDS_LABEL_PREFIX,
  SENTENCED_CONVICTIONS_LABEL_PREFIX,
  SENTENCING_DETAIL_CAPTION,
  SENTENCING_INDEX_CAPTION,
} from '@pca/shared';
import { assertPageClean } from '../support/checks';
import { selectFromCombobox } from '../support/combobox';
import { DISPLAY_NAMES, SLUGS } from '../support/constants';
import { JUDGE_RESULT_COPY } from '../../apps/web/app/components/judge-result-copy';
import { CHARGE_RESULT_COPY } from '../../apps/web/app/components/charge-result-copy';
import { RESULT_DISPLAY_COPY } from '../../apps/web/app/components/result-display-copy';

/**
 * Judge filter flows (task 15.2 scope 2; 35.3 pin 6): add a judge to reach
 * the judge-specific result (the cell's index leads the judge scope with NO
 * grade line; the baseline scope is unchanged), remove the filter to return
 * to the charge-only result, the judge-unavailable pair (valid charge +
 * valid judge, no judge aggregate → pinned fallback), and the absent-index
 * judge cell (success payload, no index rows → today's scope order). Pinned
 * copy is asserted via @pca/shared imports.
 */

test('add judge → judge-specific result, then remove filter → charge-only', async ({ page }) => {
  await page.goto('/');

  await selectFromCombobox(page, '#charge-search', 'retail', DISPLAY_NAMES.chargeDataBearing);
  // DP-3: open the judge disclosure before driving the (unchanged) combobox.
  await page.getByRole('button', { name: CHARGE_RESULT_COPY.judgeDisclosureTriggerText }).click();
  await selectFromCombobox(page, '#judge-search', 'testina', DISPLAY_NAMES.judgeDataBearing);
  await page.locator('form button[type="submit"]').click();

  await expect(page).toHaveURL(
    new RegExp(`/charges/${SLUGS.chargeDataBearing}/judge/${SLUGS.judgeDataBearing}$`),
  );

  // Both scopes render: the judge-specific section AND the Philadelphia-wide
  // baseline, each with its own outcome distribution and sample size.
  await expect(
    page.getByRole('heading', { name: JUDGE_RESULT_COPY.sectionJudgeSpecificHeading }),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: JUDGE_RESULT_COPY.sectionBaselineHeading }),
  ).toBeVisible();

  const judgeOutcome = page.getByTestId('section-judge-outcome');
  const baselineOutcome = page.getByTestId('section-baseline-outcome');
  await expect(judgeOutcome.getByRole('table')).toBeVisible();
  await expect(baselineOutcome.getByRole('table')).toBeVisible();
  // Separate samples: each scope carries its own reconciled records label.
  await expect(judgeOutcome.getByText(new RegExp(`^${RECORDS_LABEL_PREFIX}`))).toBeVisible();
  await expect(baselineOutcome.getByText(new RegExp(`^${RECORDS_LABEL_PREFIX}`))).toBeVisible();

  // 35.3 pin 6: the cell index leads the judge scope (seeded: 45 sentenced,
  // flat pair 90/90 days → single figure 3), with NO grade line at this
  // grain; the component block below carries the detail caption while the
  // baseline keeps today's caption.
  const judgeIndex = page.getByTestId('section-judge-sentencing-index');
  await expect(judgeIndex.getByRole('table')).toBeVisible();
  await expect(judgeIndex.getByText(SENTENCING_INDEX_CAPTION)).toBeVisible();
  await expect(judgeIndex.getByText(`${SENTENCED_CONVICTIONS_LABEL_PREFIX}45`)).toBeVisible();
  await expect(judgeIndex.getByRole('table')).toContainText('2–6');
  // Flat pair 90/90 days → the median CELL collapses to the single figure 3.
  await expect(
    judgeIndex
      .getByRole('row', { name: /Incarceration/ })
      .getByRole('cell')
      .nth(2),
  ).toHaveText('3');
  await expect(page.getByTestId('index-grade-mix')).toHaveCount(0);
  await expect(
    page.getByTestId('section-judge-sentencing').getByText(SENTENCING_DETAIL_CAPTION),
  ).toBeVisible();
  await expect(
    page
      .getByTestId('section-baseline-sentencing')
      .getByText(RESULT_DISPLAY_COPY.sentencingCaption),
  ).toBeVisible();

  await assertPageClean(page, 'judge-specific result');

  // Remove the judge filter → back to the charge-only result.
  await page.getByRole('link', { name: JUDGE_RESULT_COPY.removeFilterLinkText }).first().click();
  await expect(page).toHaveURL(new RegExp(`/charges/${SLUGS.chargeDataBearing}$`));
  await expect(
    page.getByRole('heading', { level: 1, name: DISPLAY_NAMES.chargeDataBearing }),
  ).toBeVisible();
  await expect(page.getByTestId('section-judge-outcome')).toHaveCount(0);

  await assertPageClean(page, 'charge-only result (after removing judge filter)');
});

test('judge-unavailable pair: valid charge + judge, no judge aggregate → pinned fallback', async ({
  page,
}) => {
  await page.goto(`/charges/${SLUGS.chargeDataBearing}/judge/${SLUGS.judgeNoAggregate}`);

  // The pinned message is asserted via the imported @pca/shared constant.
  await expect(page.getByText(JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE)).toBeVisible();

  // It is a content branch, not a result: no distribution sections render, and
  // there is a link back to the charge-only result.
  await expect(page.getByTestId('section-judge-outcome')).toHaveCount(0);
  await expect(
    page.getByRole('link', { name: JUDGE_RESULT_COPY.removeFilterLinkText }),
  ).toHaveAttribute('href', `/charges/${SLUGS.chargeDataBearing}`);

  await assertPageClean(page, 'judge-specific unavailable');
});

test("absent-index judge cell: success payload renders today's scope order, no index section", async ({
  page,
}) => {
  await page.goto(`/charges/${SLUGS.chargeJudgeIndexAbsent}/judge/${SLUGS.judgeIndexAbsent}`);

  // A full judge-specific result (both scopes) with NO index section anywhere
  // (35.3 pin 2 at the judge grain) and today's caption in the judge scope.
  await expect(page.getByTestId('section-judge-outcome').getByRole('table')).toBeVisible();
  await expect(page.getByTestId('section-baseline-outcome').getByRole('table')).toBeVisible();
  await expect(page.getByTestId('section-judge-sentencing-index')).toHaveCount(0);
  await expect(
    page.getByTestId('section-judge-sentencing').getByText(RESULT_DISPLAY_COPY.sentencingCaption),
  ).toBeVisible();

  await assertPageClean(page, 'judge-specific result (absent index cell)');
});
