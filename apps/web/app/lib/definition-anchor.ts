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
 * Builds the definition anchor for one category. `categoryCode` is the taxonomy
 * code exactly as served by the API (`@pca/shared` `OutcomeCategoryCode` /
 * `SentencingCategoryCode`); it is used verbatim so the fragment matches the
 * id 14.1 will emit.
 */
export function definitionAnchor(kind: DistributionKind, categoryCode: string): string {
  return `${DEFINITIONS_PATH}#${kind}-${categoryCode}`;
}
