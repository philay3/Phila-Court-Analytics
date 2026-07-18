import { Type, type Static } from '@sinclair/typebox';
import { sampleSizeSchema } from './common.js';

/**
 * Charge-directory contract (task DP-4): GET /api/v1/public/charges.
 *
 * Tagged union per the data-coverage precedent: "no active published run" is
 * the unavailable arm of an HTTP-200 response, never an error. Rows are
 * server-sorted alphabetically by normalized display name (slug tie-break);
 * the sample size rides the payload for featured-charge selection and future
 * sorting but is never rendered in v1.
 */

/**
 * The ONLY message the unavailable arm may carry — public-safe by
 * construction: no run states, no internal reasons, no system detail.
 */
export const CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE = 'No charges have published results yet.';

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
