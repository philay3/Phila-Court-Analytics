import { Type, type Static } from '@sinclair/typebox';
import {
  dateRangeSchema,
  outcomeDistributionEntrySchema,
  sampleSizeSchema,
  sentencingDistributionEntrySchema,
  taxonomyVersionSchema,
  thinDataStatusSchema,
} from './common.js';

/**
 * Charge-only public result contract (task 8.1):
 * GET /api/v1/public/results/charge/{chargeIdOrSlug}.
 *
 * Sample sizes live on each distribution block, never per row, and the
 * outcome and sentencing sample sizes are independent. The date range is
 * result-level — it describes the aggregate run, not a single distribution.
 */

/**
 * The ONLY message the sentencing-unavailable arm may carry. Public-safe by
 * construction: schema-pinned as a literal below, so any internal wording
 * (parser/review/extraction) is a contract violation, not just a convention.
 */
export const CHARGE_SENTENCING_UNAVAILABLE_MESSAGE =
  'Historical sentencing data is not available for this charge yet.';

export const chargeSummarySchema = Type.Object(
  {
    id: Type.String({ format: 'uuid' }),
    slug: Type.String(),
    displayName: Type.String(),
    statuteCode: Type.Optional(Type.String()),
    grade: Type.Optional(Type.String()),
  },
  { additionalProperties: false },
);
export type ChargeSummary = Static<typeof chargeSummarySchema>;

export const chargeOutcomesSchema = Type.Object(
  {
    sampleSize: sampleSizeSchema,
    thinData: thinDataStatusSchema,
    rows: Type.Array(outcomeDistributionEntrySchema),
  },
  { additionalProperties: false },
);
export type ChargeOutcomes = Static<typeof chargeOutcomesSchema>;

export const chargeSentencingAvailableSchema = Type.Object(
  {
    available: Type.Literal(true),
    // The SENTENCING sample size — independent of the outcomes sample size.
    sampleSize: sampleSizeSchema,
    thinData: thinDataStatusSchema,
    rows: Type.Array(sentencingDistributionEntrySchema),
  },
  { additionalProperties: false },
);
export type ChargeSentencingAvailable = Static<typeof chargeSentencingAvailableSchema>;

export const chargeSentencingUnavailableSchema = Type.Object(
  {
    available: Type.Literal(false),
    message: Type.Literal(CHARGE_SENTENCING_UNAVAILABLE_MESSAGE),
  },
  { additionalProperties: false },
);
export type ChargeSentencingUnavailable = Static<typeof chargeSentencingUnavailableSchema>;

export const chargeSentencingSchema = Type.Union([
  chargeSentencingAvailableSchema,
  chargeSentencingUnavailableSchema,
]);
export type ChargeSentencing = Static<typeof chargeSentencingSchema>;

export const chargeOnlyResultResponseSchema = Type.Object(
  {
    charge: chargeSummarySchema,
    resultType: Type.Literal('charge_only'),
    geography: Type.Literal('philadelphia'),
    dateRange: dateRangeSchema,
    lastRefreshed: Type.String({ format: 'date-time' }),
    taxonomyVersion: taxonomyVersionSchema,
    // Public-safe run reference; no other run fields are ever exposed.
    aggregateRunId: Type.String({ format: 'uuid' }),
    outcomes: chargeOutcomesSchema,
    sentencing: chargeSentencingSchema,
    links: Type.Object(
      {
        methodology: Type.Literal('/methodology'),
        definitions: Type.Literal('/definitions'),
      },
      { additionalProperties: false },
    ),
  },
  { additionalProperties: false },
);
export type ChargeOnlyResultResponse = Static<typeof chargeOnlyResultResponseSchema>;
