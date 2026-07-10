/**
 * Judge-specific result page user-facing copy (task 13.3). The chrome strings
 * unique to the judge-specific result view live here as exported constants, so
 * the app/-walking copy guard covers them automatically and
 * `judge-result-copy.test.ts` can scan each value with `scanPublicCopy` from
 * @pca/shared directly (same pattern as charge-result-copy / result-display-copy).
 *
 * Only strings NOT already covered elsewhere live here: the two section
 * headings and the remove-filter link text (pinned decisions 2 and 5). Generic
 * page chrome (last-refreshed label, methodology/definitions link text,
 * loading, error, and not-found "return to search" copy) is reused from
 * `CHARGE_RESULT_COPY`, and every pinned MESSAGE literal (judge-unavailable,
 * charge/judge not-found, sentencing-unavailable) is imported from @pca/shared
 * and rendered verbatim — so each stays typed in exactly one place.
 *
 * Copy-safety: values are neutral and non-comparative. "Philadelphia-wide
 * baseline" describes the reference group only; there is no comparative
 * language anywhere here (verified by the direct scan test).
 */
export const JUDGE_RESULT_COPY = {
  // Section headings (pinned decision 2) — exact literals, no comparative
  // language. Each wraps its own outcome + sentencing slots.
  sectionJudgeSpecificHeading: 'Judge-specific result',
  sectionBaselineHeading: 'Philadelphia-wide baseline',

  // Remove-filter link (pinned decision 5) and the charge-only link on the
  // judge-unavailable branch (pinned decision 4) — both route to the
  // charge-only page and share this exact label.
  removeFilterLinkText: 'View Philadelphia-wide result instead',
} as const;
