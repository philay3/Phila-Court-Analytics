/**
 * Definitions-page user-facing copy (task 14.1). Every string the page and its
 * page-local components render lives here as an exported constant, so the
 * app/-walking copy guard covers it automatically and `definitions-copy.test.ts`
 * can scan each value with `scanPublicCopy` from @pca/shared directly (same
 * pattern as result-display-copy / home-copy).
 *
 * The category display names and definitions themselves are NOT here — those are
 * served live by GET /public/definitions from the @pca/taxonomy artifact. This
 * module holds only the page's own framing copy. The error BODY is not here
 * either: it comes from @pca/shared error-message constants, selected per
 * failure arm (see definitions-failure.ts).
 *
 * All values are neutral, plain-language framing that makes no claims about any
 * individual case (verified by the direct scan test).
 */
export const DEFINITIONS_COPY = {
  // Page heading + short plain-language intro.
  heading: 'Definitions',
  intro:
    'These are plain-language descriptions of the outcome and sentencing categories used across this site. Each category groups together records that share a common result, so the figures elsewhere on the site can be read consistently.',

  // Section headings (h2), one per served group.
  outcomeSectionHeading: 'Outcome categories',
  sentencingSectionHeading: 'Sentencing categories',

  // Taxonomy version, shown unobtrusively near the page footer. The version
  // value is interpolated from the API response after this label.
  taxonomyVersionLabel: 'Taxonomy version',

  // Route-level loading state — describes the in-flight fetch only, never any
  // outcome or figure.
  loadingMessage: 'Loading definitions…',

  // Error state heading. The error body text is a shared @pca/shared constant
  // selected by failure arm; no internal detail is ever shown.
  errorHeading: 'Definitions are unavailable',
} as const;
