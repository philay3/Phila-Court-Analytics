/**
 * Judge autocomplete user-facing copy (task 12.3). Holds only the strings
 * introduced by the judge search component — the judge label, placeholder, and
 * help text remain sourced from HOME_COPY (already a scanned constants module),
 * so they are not duplicated here.
 *
 * Every value is user-facing, so `judge-search-copy.test.ts` scans each one
 * with `scanPublicCopy` from @pca/shared directly, and the app/-walking copy
 * guard covers this file automatically. No inline user-facing strings may live
 * in JudgeSearchInput.tsx or SearchForm.tsx — add them here. The judge is
 * OPTIONAL: nothing below implies a judge is required or promises judge-specific
 * results, and the no-result value never asserts the judge does not exist — it
 * points at spelling and a different form of the name and reaffirms that
 * Philadelphia-wide charge results remain available.
 */
export const JUDGE_SEARCH_COPY = {
  // Shown in the polite live region while a suggestions request is in flight.
  loading: 'Searching judges…',
  // Shown when a valid query returns zero suggestions. Deliberately does NOT
  // assert the judge does not exist — it points at spelling and name form, and
  // reminds that Philadelphia-wide charge results are still available.
  noResult:
    'No matching judges to show. Try a different spelling or another form of the name. Philadelphia-wide results for the charge are still available.',
  // Screen-reader instructions wired to the combobox via aria-describedby.
  listInstructions:
    'Suggestions appear below as you type. Use the up and down arrow keys to review them, then press Enter to select a judge.',
  // Secondary label prefix shown when a suggestion matched via an alias.
  matchedAliasPrefix: 'matched: ',
} as const;
