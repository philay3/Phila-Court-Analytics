/**
 * Charge autocomplete user-facing copy (task 12.2). Holds only the strings
 * introduced by the charge search component — the charge label, placeholder,
 * and help text remain sourced from HOME_COPY (already a scanned constants
 * module under app/components/), so they are not duplicated here.
 *
 * Every value is user-facing, so `charge-search-copy.test.ts` scans each one
 * with `scanPublicCopy` from @pca/shared directly, and the app/-walking copy
 * guard covers this file automatically. No inline user-facing strings may live
 * in ChargeSearchInput.tsx or SearchForm.tsx — add them here. Nothing below
 * asserts that a charge does not exist; every value is written to pass the
 * @pca/shared copy-safety scanner (no forbidden vocabulary).
 */
export const CHARGE_SEARCH_COPY = {
  // Shown in the polite live region while a suggestions request is in flight.
  loading: 'Searching charges…',
  // Shown when a valid query returns zero suggestions. Deliberately does NOT
  // assert the charge does not exist — it points at spelling and common names.
  noResult: 'No suggestions to show. Try a different spelling or a common name for the charge.',
  // Shown when the form is submitted with no charge selected from the list.
  submitHint: 'Choose a charge from the suggestions to continue.',
  // Screen-reader instructions wired to the combobox via aria-describedby.
  listInstructions:
    'Suggestions appear below as you type. Use the up and down arrow keys to review them, then press Enter to select a charge.',
  // Secondary label prefix shown when a suggestion matched via an alias.
  matchedAliasPrefix: 'matched: ',
  // Visible submit button label (the mouse path to the same submit as Enter).
  submitButton: 'View outcomes',
} as const;
