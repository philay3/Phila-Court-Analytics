/**
 * Charge-result page user-facing copy (task 13.2). Every incidental string the
 * charge-only result page, its state files (loading / not-found / error), and
 * the judge-filter entry point render lives here as an exported constant, so
 * the app/-walking copy guard covers it automatically and
 * `charge-result-copy.test.ts` can scan each value with `scanPublicCopy` from
 * @pca/shared directly (same pattern as result-display-copy / home-copy).
 *
 * The pinned MESSAGE literals are NOT defined here: the charge-unavailable,
 * sentencing-unavailable, and charge-not-found messages are imported from
 * @pca/shared and rendered verbatim, so each stays typed in exactly one place.
 * Only page chrome — labels, link text, and the generic state copy — lives in
 * this module.
 *
 * Copy-safety: values are neutral, non-comparative framing. The judge-filter
 * help states that judge-specific data is not available for every charge/judge
 * pair without any restricted vocabulary (verified by the direct scan test).
 */
export const CHARGE_RESULT_COPY = {
  // Result summary chrome. The result-type label and the formatted timestamp
  // come from the 11.4 formatters; this is only the field label beside them.
  lastRefreshedLabel: 'Last refreshed',

  // Page-level links, sourced from the API `links` object (href) with the
  // visible text here.
  methodologyLinkText: 'Read the methodology',
  definitionsLinkText: 'See the definitions',

  // Metadata-aside sample-size context labels (task DP-3, sanctioned strings
  // 2–3 of 4). One-word labels over the existing SampleSizeLabel value line;
  // charge-page aside only.
  asideOutcomesLabel: 'Outcomes',
  asideSentencingLabel: 'Sentencing',

  // Judge-filter entry point (pinned decision 5). The help copy states the
  // availability caveat in guard-passing language.
  judgeFilterHeading: 'View this charge for a specific judge',
  judgeFilterLabel: 'Judge (optional)',
  judgeFilterHelp:
    'Add a judge to view historical outcomes for this charge and that judge. Judge-specific data is not available for every charge and judge.',

  // Route-level loading placeholder (pinned decision 2). Neutral: it
  // describes the fetch in progress, nothing about any outcome.
  loadingMessage: 'Loading historical results…',

  // not-found.tsx chrome. The message itself is the imported
  // CHARGE_NOT_FOUND_MESSAGE; this is the page heading (task 15.1 a11y pass —
  // every terminal state carries an h1 for heading navigation) and the link
  // back to search.
  notFoundHeading: 'Result not found',
  notFoundHomeLinkText: 'Return to search',

  // Heading for the charge-result-unavailable state on the JUDGE route (task
  // 15.1 walkthrough Finding 1). The judge endpoint returns this case as a 404
  // error envelope carrying only the pinned CHARGE_RESULT_UNAVAILABLE_MESSAGE —
  // no charge identity — so this generic heading stands in for the charge name
  // the charge-only route's unavailable view shows as its h1.
  chargeUnavailableHeading: 'Results not available',

  // error.tsx generic, internal-detail-free copy (pinned decision 2).
  errorHeading: 'Something went wrong',
  errorBody: 'We could not load this page. Please try again.',
  errorRetryText: 'Try again',
} as const;
