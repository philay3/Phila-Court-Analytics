/**
 * Failure-state chrome the web app renders when a page cannot load (task
 * STATIC-2c, pin 3.A.5). Pinned here — rather than only in the web copy
 * modules that render them — so the export gate can import the exact literals
 * and fail any prerendered page whose visible text baked one of these states.
 * The web copy modules re-export them under their existing keys; nothing a page
 * renders changes.
 */

/** The route error boundaries (`/charges`, `/charges/[chargeSlug]`): heading, body, retry label. */
export const ERROR_BOUNDARY_COPY = {
  heading: 'Something went wrong',
  body: 'We could not load this page. Please try again.',
  retryText: 'Try again',
} as const;

/** Body of the charges-directory error boundary (its heading and retry label come from ERROR_BOUNDARY_COPY). */
export const CHARGES_DIRECTORY_ERROR_BODY = 'Available charges could not load.';

/**
 * Headings of the three content pages' failure arms. Their bodies are the
 * PUBLIC_ERROR_MESSAGES / FETCH_FAILURE_MESSAGE constants, selected per arm.
 */
export const CONTENT_PAGE_FAILURE_HEADINGS = {
  definitions: 'Definitions are unavailable',
  methodology: 'Methodology is unavailable',
  dataCoverage: 'Data coverage is unavailable',
} as const;
