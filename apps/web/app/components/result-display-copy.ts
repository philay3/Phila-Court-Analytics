/**
 * Result-display user-facing copy (task 13.1). Every string the 13.1 display
 * components render lives here as an exported constant, so the app/-walking
 * copy guard covers it automatically and `result-display-copy.test.ts` can scan
 * each value with `scanPublicCopy` from @pca/shared directly (same pattern as
 * home-copy / charge-search-copy from Phase 12).
 *
 * No inline JSX string literals for user-facing copy may live in the display
 * components — add them here. Values are flat strings so the copy guard walks
 * them one-for-one; the four responsible-use statements are separate keys that
 * `ResponsibleUseNotice` assembles into its list.
 *
 * The thin-data BADGE label is not defined here: it is the pinned
 * `THIN_DATA_LABEL` from the 11.4 formatters ("Based on a small sample."),
 * rendered via `formatThinDataLabel`, so it stays typed in exactly one place.
 *
 * Copy-safety: the responsible-use statements deliberately use the exact
 * guarded disclaimer phrases so they pass the scanner; every value here is
 * neutral, non-comparative framing (verified by the direct scan test).
 */
export const RESULT_DISPLAY_COPY = {
  // Table captions — name each distribution (acceptance criterion 6).
  outcomeCaption: 'Historical outcome distribution',
  sentencingCaption: 'Historical sentencing distribution',

  // Column headers. The category column is named per kind; count and
  // percentage are always shown together.
  outcomeCategoryHeader: 'Outcome',
  sentencingCategoryHeader: 'Sentence category',
  countHeader: 'Count',
  percentageHeader: 'Percentage',

  // Per-row definition link. The visible text is compact; the accessible name
  // is built by prefixing the category display name (see DistributionSection).
  definitionLinkText: 'Definition',
  definitionLinkLabelPrefix: 'Definition of ',

  // Standalone thin-data callout body (task pins: plain-English; explains what
  // a small sample means for reading the figures, in neutral terms, without
  // discouraging language or internal detail).
  thinDataCalloutBody:
    'These figures come from a small number of records. With so little data behind them, the percentages can shift noticeably as more records are added, so read them as a rough summary rather than a settled pattern.',

  // ResponsibleUseNotice — the four required statements, in order.
  responsibleUseHistorical: 'These figures are historical aggregates.',
  responsibleUseNotLegalAdvice: 'They are not legal advice.',
  responsibleUseNotPrediction: 'They are not a prediction of any current or future case.',
  responsibleUseCasesVary:
    'Individual cases vary, and past patterns do not determine any specific outcome.',
} as const;
