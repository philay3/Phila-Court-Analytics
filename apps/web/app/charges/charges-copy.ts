/**
 * Charges-directory framing copy (task DP-4). Only the page's own chrome
 * lives here — each value an exported constant so the app/-walking copy guard
 * covers it and `charges-copy.test.ts` can scan every value with
 * `scanPublicCopy` directly (same pattern as methodology-copy).
 *
 * NOT here (single-authoring rule): the empty-publication body is the
 * @pca/shared CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE, served on the API's
 * unavailable arm and rendered verbatim; the error-state heading and retry
 * label are reused byte-identically from CHARGE_RESULT_COPY.
 *
 * "charges" in the count line counts charge types, not cases (framing review
 * recorded in the DP-4 task spec).
 */
export const CHARGES_COPY = {
  // Page heading (h1) and lead.
  heading: 'Charges',
  lead: 'Browse charges with available historical aggregate results.',

  // Client-side filter control.
  filterLabel: 'Filter charges',
  filterPlaceholder: 'Search by charge name',

  // Count line, exactly the two sanctioned rendered forms; assembled by
  // formatChargeCountLine below.
  countLineSingular: '1 available charge',
  countLinePlural: '{count} available charges',

  // Row availability line, exactly two states keyed off hasSentencing.
  availabilityWithSentencing: 'Historical outcome and sentencing distributions available',
  availabilityOutcomesOnly: 'Historical outcome distributions available',

  // Row action (the arrow glyph is CSS generated content, never copy).
  rowAction: 'View results',

  // Filter no-match state.
  noMatchBody: 'No available charges match your search.',
  clearAction: 'Clear search',

  // Route-level loading state — describes the in-flight fetch only.
  loadingMessage: 'Loading charges…',

  // Error state body; heading and retry come from CHARGE_RESULT_COPY.
  errorBody: 'Available charges could not load.',
} as const;

/** Renders the sanctioned count-line forms: singular at exactly 1, else plural. */
export function formatChargeCountLine(count: number): string {
  return count === 1
    ? CHARGES_COPY.countLineSingular
    : CHARGES_COPY.countLinePlural.replace('{count}', String(count));
}

/**
 * The availability line, exactly two states keyed off hasSentencing. Homed
 * here (a plain module, not 'use client') so directory rows and the DP-5
 * homepage featured cards — a server component — render it byte-identically.
 */
export function availabilityText(hasSentencing: boolean): string {
  return hasSentencing
    ? CHARGES_COPY.availabilityWithSentencing
    : CHARGES_COPY.availabilityOutcomesOnly;
}
