/**
 * Charge-result page user-facing copy (task 13.2). Every incidental string the
 * charge-only result page, its error state, and the judge-filter entry point
 * render lives here as an exported constant, so
 * the app/-walking copy guard covers it automatically and
 * `charge-result-copy.test.ts` can scan each value with `scanPublicCopy` from
 * @pca/shared directly (same pattern as result-display-copy / home-copy).
 *
 * The pinned MESSAGE literals are NOT defined here: the charge-unavailable and
 * sentencing-unavailable messages are imported from @pca/shared and rendered
 * verbatim, so each stays typed in exactly one place; the root 404 copy lives
 * in @pca/shared too (task STATIC-2b — the static site has one not-found
 * page). Only page chrome — labels, link text, and the generic error copy —
 * lives in this module.
 *
 * Copy-safety: values are neutral, non-comparative framing. The judge-filter
 * help is the shared JUDGE_FILTER_HELP_MESSAGE (DP-5), rendered verbatim from
 * @pca/shared rather than defined here.
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

  // Judge-disclosure trigger (task DP-3, sanctioned string 4 of 4). One
  // source for both surfaces (charge-page aside and homepage search card) via
  // the shared JudgeDisclosure component. The plus/minus glyph is CSS
  // generated content (disclosure-glyph utility), never part of this string.
  judgeDisclosureTriggerText: 'Add judge filter',

  // Judge-filter entry point (pinned decision 5; DP-5 sanctioned copy
  // change: the "(optional)" suffix is retired and the multi-line help is
  // replaced by the shared JUDGE_FILTER_HELP_MESSAGE, imported where
  // rendered — the disclosure trigger is the opt-in signal).
  judgeFilterHeading: 'View this charge for a specific judge',
  judgeFilterLabel: 'Judge',

  // error.tsx generic, internal-detail-free copy (pinned decision 2).
  errorHeading: 'Something went wrong',
  errorBody: 'We could not load this page. Please try again.',
  errorRetryText: 'Try again',
} as const;
