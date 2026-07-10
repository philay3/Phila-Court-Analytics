import { expect, test } from '@playwright/test';
import { DATA_COVERAGE_PLANNED_DATA_START } from '@pca/shared';
import { assertPageClean } from '../support/checks';
import { DEFINITIONS_COPY } from '../../apps/web/app/definitions/definitions-copy';
import { METHODOLOGY_COPY } from '../../apps/web/app/methodology/methodology-copy';
import { DATA_COVERAGE_COPY } from '../../apps/web/app/data-coverage/data-coverage-copy';
import { formatDateOnly } from '../../apps/web/app/lib/formatters';

/**
 * API-backed content pages + the static About page (task 15.2 scope 2). Each
 * asserts its page heading (proving the content arm rendered, not the error
 * arm — the error heading is asserted absent) and passes the page gate.
 */

test('definitions page renders API-backed content', async ({ page }) => {
  await page.goto('/definitions');

  await expect(
    page.getByRole('heading', { level: 1, name: DEFINITIONS_COPY.heading }),
  ).toBeVisible();
  await expect(page.getByText(DEFINITIONS_COPY.errorHeading)).toHaveCount(0);
  // Served definition groups render as h2 sections.
  expect(await page.getByRole('heading', { level: 2 }).count()).toBeGreaterThan(0);

  await assertPageClean(page, 'definitions');
});

test('methodology page renders API-backed content', async ({ page }) => {
  await page.goto('/methodology');

  await expect(
    page.getByRole('heading', { level: 1, name: METHODOLOGY_COPY.heading }),
  ).toBeVisible();
  await expect(page.getByText(METHODOLOGY_COPY.errorHeading)).toHaveCount(0);
  expect(await page.getByRole('heading', { level: 2 }).count()).toBeGreaterThan(0);

  await assertPageClean(page, 'methodology');
});

test('data-coverage page renders API content and shows the 2025-01-01 start date', async ({
  page,
}) => {
  await page.goto('/data-coverage');

  await expect(
    page.getByRole('heading', { level: 1, name: DATA_COVERAGE_COPY.heading }),
  ).toBeVisible();
  await expect(page.getByText(DATA_COVERAGE_COPY.errorHeading)).toHaveCount(0);

  // The planned data start renders through the same formatter the app uses, so
  // the 2025-01-01 value is asserted without re-typing the formatted string.
  // Exact match targets the plannedDataStart field specifically (the same
  // formatted date also appears inside the data-window range and a limitation).
  await expect(
    page.getByText(formatDateOnly(DATA_COVERAGE_PLANNED_DATA_START), { exact: true }).first(),
  ).toBeVisible();

  await assertPageClean(page, 'data-coverage');
});

test('about page renders', async ({ page }) => {
  await page.goto('/about');

  await expect(page.getByRole('heading', { level: 1, name: 'About this site' })).toBeVisible();

  await assertPageClean(page, 'about');
});
