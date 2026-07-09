import { Type, type Static } from '@sinclair/typebox';
import { PUBLIC_ERROR_CODES } from '../errors.js';
import {
  chargeOutcomesSchema,
  chargeSentencingSchema,
  chargeSummarySchema,
} from './charge-result.js';
import { dateRangeSchema, taxonomyVersionSchema } from './common.js';

/**
 * Judge-specific public result contract (task 8.2):
 * GET /api/v1/public/results/charge/{chargeIdOrSlug}/judge/{judgeIdOrSlug}.
 *
 * The response is a top-level tagged union discriminated by `resultType`.
 * The unavailable arm is an HTTP 200 answer, not an error: it exists so the
 * charge/judge identity and the charge-only fallback can travel together
 * without bending the flat error contract. It is only ever emitted when the
 * charge-only baseline exists, so the fallback path never dead-ends.
 */

/**
 * The ONLY message the judge-specific-unavailable arm may carry. Pinned as a
 * schema literal so internal wording (parser/review/extraction) is a contract
 * violation, not just a convention — same rule as the sentencing arm in 8.1.
 */
export const JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE =
  'No judge-specific aggregate is available for this charge and judge yet. ' +
  'Philadelphia-wide historical data for this charge is still available.';

/**
 * Pinned public message literal for PUBLIC_ERROR_CODES.JUDGE_NOT_FOUND
 * (migrated from the 8.2 service in task 10.2).
 */
export const JUDGE_NOT_FOUND_MESSAGE = 'No judge matches the requested identifier.';

export const judgeSummarySchema = Type.Object(
  {
    id: Type.String({ format: 'uuid' }),
    slug: Type.String(),
    displayName: Type.String(),
  },
  { additionalProperties: false },
);
export type JudgeSummary = Static<typeof judgeSummarySchema>;

/**
 * One scope's distributions (judge-specific or baseline). Both reuse 8.1's
 * block and sentencing-union schemas verbatim: identical row shape, and all
 * four sample sizes across the two scopes are independent.
 */
export const resultDistributionsSchema = Type.Object(
  {
    outcomes: chargeOutcomesSchema,
    sentencing: chargeSentencingSchema,
  },
  { additionalProperties: false },
);
export type ResultDistributions = Static<typeof resultDistributionsSchema>;

export const judgeSpecificResultSuccessSchema = Type.Object(
  {
    resultType: Type.Literal('judge_specific'),
    charge: chargeSummarySchema,
    judge: judgeSummarySchema,
    geography: Type.Literal('philadelphia'),
    dateRange: dateRangeSchema,
    lastRefreshed: Type.String({ format: 'date-time' }),
    taxonomyVersion: taxonomyVersionSchema,
    // Public-safe run reference; no other run fields are ever exposed.
    aggregateRunId: Type.String({ format: 'uuid' }),
    judgeSpecific: resultDistributionsSchema,
    // The Philadelphia baseline is REQUIRED on every success response.
    baseline: resultDistributionsSchema,
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
export type JudgeSpecificResultSuccess = Static<typeof judgeSpecificResultSuccessSchema>;

/**
 * HTTP 200 unavailable arm: identity, the pinned code/message literals, and
 * the fallback only — no distributions, no sample sizes, no run metadata, no
 * links.
 */
export const judgeSpecificResultUnavailableSchema = Type.Object(
  {
    resultType: Type.Literal('judge_specific_unavailable'),
    code: Type.Literal(PUBLIC_ERROR_CODES.JUDGE_SPECIFIC_RESULT_UNAVAILABLE),
    message: Type.Literal(JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE),
    charge: chargeSummarySchema,
    judge: judgeSummarySchema,
    fallback: Type.Object(
      {
        // The public API path of the charge-only result for the same charge.
        chargeOnlyResultPath: Type.String(),
      },
      { additionalProperties: false },
    ),
  },
  { additionalProperties: false },
);
export type JudgeSpecificResultUnavailable = Static<typeof judgeSpecificResultUnavailableSchema>;

// Structurally disjoint via the resultType literals; used as the single 200
// response schema so serialization stripping covers both arms.
export const judgeSpecificResultResponseSchema = Type.Union([
  judgeSpecificResultSuccessSchema,
  judgeSpecificResultUnavailableSchema,
]);
export type JudgeSpecificResultResponse = Static<typeof judgeSpecificResultResponseSchema>;
