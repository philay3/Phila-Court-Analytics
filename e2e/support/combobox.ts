import { expect, type Page } from '@playwright/test';

/**
 * Drive a WAI-ARIA combobox (ChargeSearchInput / JudgeSearchInput) purely by
 * keyboard, exercising the task-12 autocomplete contract the way a keyboard
 * user does: type a query, wait for the debounced suggestion listbox, move the
 * active option with ArrowDown, and commit it with Enter.
 *
 * Seed queries are chosen (in the spec) to return a single suggestion, so one
 * ArrowDown lands on the intended option; the option text is asserted before
 * commit so a drift in seed data fails loudly rather than silently selecting
 * the wrong row.
 */
export async function selectFromCombobox(
  page: Page,
  inputSelector: string,
  query: string,
  optionName: string,
): Promise<void> {
  const input = page.locator(inputSelector);
  await input.click();
  await input.fill(query);

  const option = page.getByRole('option', { name: optionName });
  await expect(option).toBeVisible();

  await input.press('ArrowDown');
  await input.press('Enter');

  // Commit reflects the selection back into the input and closes the listbox.
  await expect(input).toHaveValue(optionName);
  await expect(page.getByRole('listbox')).toHaveCount(0);
}
