import { Type, type Static } from '@sinclair/typebox';
import { taxonomyVersionSchema } from './common.js';

/**
 * Data-coverage contract (task 9.2): GET /api/v1/public/data-coverage.
 *
 * Tagged union per the Phase 8 precedent: "no active published run" is the
 * unavailable arm of an HTTP-200 response, never an error. Fixed copy is
 * schema-pinned as literals (8.x pattern) so any wording drift — or any
 * internal detail creeping into the public message — is a contract
 * violation, not just a convention.
 */

export const DATA_COVERAGE_JURISDICTION = 'Philadelphia';
export const DATA_COVERAGE_COURT_SCOPE =
  'Criminal cases in the Philadelphia courts. Civil matters and courts outside Philadelphia are not covered.';
export const DATA_COVERAGE_PLANNED_DATA_START = '2025-01-01';

/**
 * The ONLY message the unavailable arm may carry — public-safe by
 * construction: no run states, no internal reasons, no system detail.
 */
export const DATA_COVERAGE_UNAVAILABLE_MESSAGE =
  'Coverage details are not available yet. They will appear here once published data is available.';

/** High-level counts only — never names, lists, or row-level data. */
export const dataCoverageCountsSchema = Type.Object(
  {
    chargesWithOutcomeAggregates: Type.Integer({ minimum: 0 }),
    chargesWithSentencingAggregates: Type.Integer({ minimum: 0 }),
    judgeChargePairs: Type.Integer({ minimum: 0 }),
  },
  { additionalProperties: false },
);
export type DataCoverageCounts = Static<typeof dataCoverageCountsSchema>;

export const dataCoverageAvailableSchema = Type.Object(
  {
    available: Type.Literal(true),
    dataStart: Type.String({ format: 'date' }),
    dataEnd: Type.String({ format: 'date' }),
    lastRefreshed: Type.String({ format: 'date-time' }),
    taxonomyVersion: taxonomyVersionSchema,
    // Public-safe run reference — same exposure as the 8.1/8.2 results.
    aggregateRunId: Type.String({ format: 'uuid' }),
    counts: dataCoverageCountsSchema,
  },
  { additionalProperties: false },
);
export type DataCoverageAvailable = Static<typeof dataCoverageAvailableSchema>;

export const dataCoverageUnavailableSchema = Type.Object(
  {
    available: Type.Literal(false),
    message: Type.Literal(DATA_COVERAGE_UNAVAILABLE_MESSAGE),
  },
  { additionalProperties: false },
);
export type DataCoverageUnavailable = Static<typeof dataCoverageUnavailableSchema>;

export const dataCoverageSchema = Type.Union([
  dataCoverageAvailableSchema,
  dataCoverageUnavailableSchema,
]);
export type DataCoverage = Static<typeof dataCoverageSchema>;

export const dataCoverageResponseSchema = Type.Object(
  {
    jurisdiction: Type.Literal(DATA_COVERAGE_JURISDICTION),
    courtScope: Type.Literal(DATA_COVERAGE_COURT_SCOPE),
    plannedDataStart: Type.Literal(DATA_COVERAGE_PLANNED_DATA_START),
    knownLimitations: Type.Array(Type.String({ minLength: 1 }), { minItems: 1 }),
    coverage: dataCoverageSchema,
  },
  { additionalProperties: false },
);
export type DataCoverageResponse = Static<typeof dataCoverageResponseSchema>;
