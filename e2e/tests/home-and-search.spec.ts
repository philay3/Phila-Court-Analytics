import { expect, test } from '@playwright/test';
import {
  BROWSE_ALL_CHARGES_LINK_TEXT,
  FEATURED_CHARGES_HEADING,
  JUDGE_FILTER_HELP_MESSAGE,
} from '@pca/shared';
import { assertPageClean } from '../support/checks';
import { selectFromCombobox } from '../support/combobox';
import { DISPLAY_NAMES, SLUGS } from '../support/constants';
import { HOME_COPY } from '../../apps/web/app/components/home-copy';
import { CHARGE_RESULT_COPY } from '../../apps/web/app/components/charge-result-copy';
import { JUDGE_SEARCH_COPY } from '../../apps/web/app/components/judge-search-copy';

/**
 * Homepage layout + the charge autocomplete happy path (task 15.2 scope 2:
 * homepage, charge-primary/judge-optional, keyboard selection → charge-only
 * result). Since task STATIC-2b both comboboxes match client-side over the
 * exported `/data/search-index.json` — no request to the public API leaves
 * the browser — and the judge field waits for a charge, then offers only the
 * judges with results for it (pins 4 and 5). Every rendered state is run
 * through the axe + copy + privacy gate.
 */

test('homepage: charge search is primary, judge input is visibly optional and waits for a charge', async ({
  page,
}) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { level: 1, name: HOME_COPY.heading })).toBeVisible();

  // The charge combobox is present and labelled as the primary entry point.
  await expect(page.locator('#charge-search')).toBeVisible();
  await expect(page.getByText(HOME_COPY.chargeLabel, { exact: true })).toBeVisible();

  // DP-3: the judge control sits behind the disclosure — the trigger renders
  // closed by default; opening it reveals the judge region (every pre-DP-3
  // assertion below is retained post-open).
  const judgeTrigger = page.getByRole('button', {
    name: CHARGE_RESULT_COPY.judgeDisclosureTriggerText,
  });
  await expect(judgeTrigger).toBeVisible();
  await expect(judgeTrigger).toHaveAttribute('aria-expanded', 'false');
  await judgeTrigger.click();
  await expect(judgeTrigger).toHaveAttribute('aria-expanded', 'true');

  // The judge input is present and — with no charge chosen yet — disabled
  // (STATIC-2b pin 5); the open state's help is exactly the DP-5 sanctioned
  // shared line (AC1) — the retired multi-line help never renders.
  await expect(page.locator('#judge-search')).toBeVisible();
  await expect(page.locator('#judge-search')).toBeDisabled();
  await expect(page.getByText(HOME_COPY.judgeLabel, { exact: true })).toBeVisible();
  await expect(page.locator('#judge-search-help')).toHaveText(JUDGE_FILTER_HELP_MESSAGE);

  // The gate runs with the disclosure OPEN, so axe scans the revealed region
  // (and the DP-5 featured section, present on the seeded homepage).
  await assertPageClean(page, 'homepage');
});

test('featured charges: top-4 seed cards in sample-size order, card and browse-all navigation', async ({
  page,
}) => {
  await page.goto('/');

  // Seed reality (the seeded test database): five charges carry outcome
  // aggregates, so the section renders exactly its top-4 arm. Served order is
  // sample-size descending — DUI (1,500) leads, criminal-trespass (18, fifth)
  // never renders on the homepage.
  const section = page.getByRole('region', { name: FEATURED_CHARGES_HEADING });
  await expect(section.getByRole('heading', { level: 2 })).toHaveText(FEATURED_CHARGES_HEADING);
  const cards = section.getByRole('listitem');
  await expect(cards).toHaveCount(4);
  await expect(cards.first().getByRole('link')).toHaveText('DUI: General Impairment');
  await expect(cards.first().getByText('Recorded outcomes: 1,500')).toBeVisible();
  // Every card carries the availability line and the pinned Amendment A line.
  for (let i = 0; i < 4; i += 1) {
    await expect(cards.nth(i).getByText(/^Historical outcome/)).toBeVisible();
    await expect(cards.nth(i).getByText(/^Recorded outcomes: /)).toBeVisible();
  }
  await expect(section.getByText('Criminal Trespass')).toHaveCount(0);

  // Browse-all navigates to the directory.
  await section.getByRole('link', { name: BROWSE_ALL_CHARGES_LINK_TEXT }).click();
  await expect(page).toHaveURL(/\/charges$/);

  // A card links to its charge page via the row-link mechanism.
  await page.goto('/');
  await section.getByRole('link', { name: 'DUI: General Impairment' }).click();
  await expect(page).toHaveURL(/\/charges\/dui-general-impairment$/);
});

test('charge autocomplete: query → suggestion → keyboard select → charge-only result, no public-API request', async ({
  page,
}) => {
  // STATIC-2b: the browser never calls the public API — the comboboxes read
  // the exported index file. Any such request during the flow is a regression.
  const apiRequests: string[] = [];
  page.on('request', (request) => {
    if (request.url().includes('/api/v1/public/')) {
      apiRequests.push(request.url());
    }
  });

  await page.goto('/');

  // Type a query, wait for the debounced listbox, move with ArrowDown, commit
  // with Enter (the keyboard contract the task calls out explicitly).
  await selectFromCombobox(page, '#charge-search', 'retail', DISPLAY_NAMES.chargeDataBearing);

  await page.locator('form button[type="submit"]').click();

  await expect(page).toHaveURL(new RegExp(`/charges/${SLUGS.chargeDataBearing}$`));
  await expect(
    page.getByRole('heading', { level: 1, name: DISPLAY_NAMES.chargeDataBearing }),
  ).toBeVisible();
  expect(apiRequests).toEqual([]);

  await assertPageClean(page, 'charge-only result (reached via search)');
});

test('judge field: enabled once a charge is chosen, offering only judges with results for it', async ({
  page,
}) => {
  await page.goto('/');
  await selectFromCombobox(page, '#charge-search', 'retail', DISPLAY_NAMES.chargeDataBearing);
  await page.getByRole('button', { name: CHARGE_RESULT_COPY.judgeDisclosureTriggerText }).click();

  const judgeInput = page.locator('#judge-search');
  await expect(judgeInput).toBeEnabled();

  // Pin 4: a judge with no results for this charge is never offered — the
  // seeded no-results judge yields the no-result status, not an option.
  await judgeInput.fill('fakename');
  await expect(page.getByText(JUDGE_SEARCH_COPY.noResult)).toBeVisible();
  await expect(page.getByRole('option')).toHaveCount(0);

  // The data-bearing judge for this charge is offered.
  await judgeInput.fill('testina');
  await expect(page.getByRole('option', { name: DISPLAY_NAMES.judgeDataBearing })).toBeVisible();
});
