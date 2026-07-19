import { Type, type Static } from '@sinclair/typebox';
import { sampleSizeSchema } from './common.js';

/**
 * Charge-directory contract (task DP-4): GET /api/v1/public/charges.
 *
 * Tagged union per the data-coverage precedent: "no active published run" is
 * the unavailable arm of an HTTP-200 response, never an error. Rows are
 * server-sorted by outcome sample size descending, then normalized display
 * name ascending, then slug ascending (task DP-5, pinned; supersedes the
 * DP-4 alphabetical order). The sample size renders on directory rows and
 * homepage featured cards as the pinned `Recorded outcomes: N` line
 * (DP-5 Amendment A) — the only statistic those surfaces carry.
 */

/**
 * The ONLY message the unavailable arm may carry — public-safe by
 * construction: no run states, no internal reasons, no system detail.
 */
export const CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE = 'No charges have published results yet.';

/**
 * Homepage featured-charges section (task DP-5, sanctioned; heading amended
 * at the DP-5 review gate). The section is fed by the top rows of the
 * directory response in served order — zero new API surface — and these are
 * its only two chrome strings: the heading and the browse-all link to
 * /charges. Rendered verbatim, never re-typed.
 */
export const FEATURED_CHARGES_HEADING = 'Find your charge';
export const BROWSE_ALL_CHARGES_LINK_TEXT = 'Browse all charges';

/**
 * Sample-size label prefix for EXACTLY two surfaces: /charges directory rows
 * and the homepage featured cards (DP-5 Amendment A). N counts disposed
 * charge outcomes — one per outcome fact — hence "Recorded outcomes", not
 * "charges" (reads as the filed universe) or internal vocabulary. The result
 * pages' `Sample size:` convention (SAMPLE_SIZE_LABEL_PREFIX,
 * formatSampleSize) is deliberately untouched; site-wide label
 * reconciliation is a named Sprint 9 copy item.
 */
export const RECORDED_OUTCOMES_LABEL_PREFIX = 'Recorded outcomes: ';

export const chargeDirectoryEntrySchema = Type.Object(
  {
    slug: Type.String(),
    displayName: Type.String(),
    statuteCode: Type.Optional(Type.String()),
    hasSentencing: Type.Boolean(),
    outcomeSampleSize: sampleSizeSchema,
  },
  { additionalProperties: false },
);
export type ChargeDirectoryEntry = Static<typeof chargeDirectoryEntrySchema>;

export const chargeDirectoryAvailableSchema = Type.Object(
  {
    available: Type.Literal(true),
    charges: Type.Array(chargeDirectoryEntrySchema),
  },
  { additionalProperties: false },
);
export type ChargeDirectoryAvailable = Static<typeof chargeDirectoryAvailableSchema>;

export const chargeDirectoryUnavailableSchema = Type.Object(
  {
    available: Type.Literal(false),
    message: Type.Literal(CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE),
  },
  { additionalProperties: false },
);
export type ChargeDirectoryUnavailable = Static<typeof chargeDirectoryUnavailableSchema>;

export const chargeDirectoryResponseSchema = Type.Union([
  chargeDirectoryAvailableSchema,
  chargeDirectoryUnavailableSchema,
]);
export type ChargeDirectoryResponse = Static<typeof chargeDirectoryResponseSchema>;
