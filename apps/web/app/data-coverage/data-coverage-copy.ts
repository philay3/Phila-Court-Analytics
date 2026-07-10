/**
 * Data-coverage-page framing copy (task 14.2). Only the page's own structural
 * labels and chrome live here — section labels, list headings, page heading,
 * error heading, loading message — each an exported constant so the app/-walking
 * copy guard covers it and `data-coverage-copy.test.ts` can scan every value
 * with `scanPublicCopy` directly (same pattern as definitions-copy).
 *
 * Served VALUES are never duplicated here: `jurisdiction`, `courtScope`,
 * `plannedDataStart`, the coverage figures, the unavailable-arm message, and —
 * critically — `knownLimitations` (including the seeded-data disclosure) all
 * come straight from the typed API response and render verbatim. This module
 * holds no third copy of any of them. The error BODY likewise comes from the
 * @pca/shared error-message constants, selected per failure arm (see
 * data-coverage-failure.ts).
 *
 * All values are neutral, plain-language labels that make no claim about any
 * individual case (verified by the direct scan test).
 */
export const DATA_COVERAGE_COPY = {
  // Page heading (h1).
  heading: 'Data coverage',

  // Overview section (always shown, both coverage arms).
  jurisdictionLabel: 'Jurisdiction',
  courtScopeLabel: 'Court scope',
  dataStartLabel: 'Planned data start',

  // Current-aggregate section (available arm only).
  currentCoverageHeading: 'Current coverage',
  dataWindowLabel: 'Covered data window',
  lastRefreshedLabel: 'Last refreshed',
  aggregateRunLabel: 'Aggregate run',
  taxonomyVersionLabel: 'Taxonomy version',
  chargesWithOutcomeAggregatesLabel: 'Charges with outcome aggregates',
  chargesWithSentencingAggregatesLabel: 'Charges with sentencing aggregates',
  judgeChargePairsLabel: 'Judge–charge pairs',

  // Known-limitations section (always shown). The heading is framing; the
  // entries themselves are served verbatim.
  knownLimitationsHeading: 'Known limitations',

  // Route-level loading state — describes the in-flight fetch only.
  loadingMessage: 'Loading data coverage…',

  // Error state heading. The error body is a shared @pca/shared constant chosen
  // by failure arm; no internal detail is ever shown.
  errorHeading: 'Data coverage is unavailable',
} as const;
