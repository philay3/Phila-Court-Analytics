import { expect, test } from '@playwright/test';
import { JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE } from '@pca/shared';
import { assertPageClean } from '../support/checks';
import { selectFromCombobox } from '../support/combobox';
import { DISPLAY_NAMES, SLUGS } from '../support/constants';
import { JUDGE_RESULT_COPY } from '../../apps/web/app/components/judge-result-copy';
import { CHARGE_RESULT_COPY } from '../../apps/web/app/components/charge-result-copy';

/**
 * Judge filter flows (task 15.2 scope 2): add a judge to reach the
 * judge-specific result (judge distribution AND Philadelphia baseline, each
 * with its own sample size), remove the filter to return to the charge-only
 * result, and the judge-unavailable pair (valid charge + valid judge, no judge
 * aggregate → pinned fallback). Pinned copy is asserted via @pca/shared imports.
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
  // Separate sample sizes: each scope carries its own count label.
  await expect(judgeOutcome.getByText(/Sample size:/)).toBeVisible();
  await expect(baselineOutcome.getByText(/Sample size:/)).toBeVisible();

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
