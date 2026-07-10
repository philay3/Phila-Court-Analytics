/**
 * Methodology-page framing copy (task 14.2). Only the page's own chrome lives
 * here — page heading, error heading, loading message — each an exported
 * constant so the app/-walking copy guard covers it and `methodology-copy.test.ts`
 * can scan every value with `scanPublicCopy` directly (same pattern as
 * definitions-copy / result-display-copy).
 *
 * The methodology section headings and bodies are NOT here: they are served
 * live by GET /public/methodology (static per deploy, from apps/api) and render
 * verbatim. The error BODY is not here either — it comes from the @pca/shared
 * error-message constants, selected per failure arm (see methodology-failure.ts).
 *
 * All values are neutral, plain-language framing that makes no claim about any
 * individual case (verified by the direct scan test).
 */
export const METHODOLOGY_COPY = {
  // Page heading (h1).
  heading: 'Methodology',

  // Route-level loading state — describes the in-flight fetch only.
  loadingMessage: 'Loading methodology…',

  // Error state heading. The error body is a shared @pca/shared constant chosen
  // by failure arm; no internal detail is ever shown.
  errorHeading: 'Methodology is unavailable',
} as const;
