/**
 * Definition-anchor convention (task 13.1, pinned decision 2). Each category
 * row in a distribution links to its definition on the definitions page via an
 * anchor of the form `/definitions#<kind>-<categoryCode>`, e.g.
 * `/definitions#outcome-guilty_plea`.
 *
 * This is the SINGLE source of the convention: `DistributionSection` builds its
 * per-row links from it now, and task 14.1 (the definitions page) imports the
 * same helper to mint the matching element ids. Keeping the format in exactly
 * one place is what keeps the links and their targets in lockstep.
 */

/** Presentational discriminator for the two distribution kinds. */
export type DistributionKind = 'outcome' | 'sentencing';

/** Base path of the definitions page the anchors point into. */
export const DEFINITIONS_PATH = '/definitions';

/**
 * Builds the fragment id for one category's definition entry: `<kind>-<code>`,
 * e.g. `outcome-guilty_plea`. `categoryCode` is the taxonomy code exactly as
 * served by the API (`@pca/shared` `OutcomeCategoryCode` /
 * `SentencingCategoryCode`); it is used verbatim.
 *
 * This is the single place the fragment format lives. The 14.1 definitions page
 * mints its per-entry element ids from this helper, and `definitionAnchor`
 * composes it into the full result-page link, so the two stay in lockstep.
 */
export function definitionAnchorId(kind: DistributionKind, categoryCode: string): string {
  return `${kind}-${categoryCode}`;
}

/**
 * Builds the definition anchor for one category: the definitions-page path plus
 * the `definitionAnchorId` fragment, so the result-page link and the page's
 * element id are minted from the same source and never drift.
 */
export function definitionAnchor(kind: DistributionKind, categoryCode: string): string {
  return `${DEFINITIONS_PATH}#${definitionAnchorId(kind, categoryCode)}`;
}
