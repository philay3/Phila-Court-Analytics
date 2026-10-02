import { Type, type Static } from '@sinclair/typebox';
import { taxonomyVersionSchema } from './common.js';

/**
 * Search-index contract (task STATIC-2a, pin 1):
 * GET /api/v1/public/search-index.
 *
 * One payload enumerating what the static build and the client-side matcher
 * need from the published run: every ACTIVE roster charge with its aliases
 * (including charges with no outcome aggregates — the volume-only arm), every
 * judge that has at least one judge-specific result in the active published
 * run with its aliases, and the distinct charge/judge pairs that have one.
 * Tagged union per the charge-directory precedent: "no active published run"
 * is the unavailable arm of an HTTP-200 response, never an error.
 *
 * No ids anywhere: slugs are the public keys, and `additionalProperties: false`
 * on every object means serialization strips anything else. Run metadata
 * field names mirror the result and data-coverage payloads.
 */

/**
 * The ONLY message the unavailable arm may carry — public-safe by
 * construction: no run states, no internal reasons, no system detail.
 */
export const SEARCH_INDEX_UNAVAILABLE_MESSAGE =
  'Search is not available yet. It will return once published data is available.';

export const searchIndexChargeSchema = Type.Object(
  {
    slug: Type.String(),
    displayName: Type.String(),
    statuteCode: Type.Optional(Type.String()),
    grade: Type.Optional(Type.String()),
    aliases: Type.Array(Type.String()),
  },
  { additionalProperties: false },
);
export type SearchIndexCharge = Static<typeof searchIndexChargeSchema>;

// Identity fields and aliases only — never counts, scores, or rankings.
export const searchIndexJudgeSchema = Type.Object(
  {
    slug: Type.String(),
    displayName: Type.String(),
    aliases: Type.Array(Type.String()),
  },
  { additionalProperties: false },
);
export type SearchIndexJudge = Static<typeof searchIndexJudgeSchema>;

export const searchIndexPairSchema = Type.Object(
  {
    chargeSlug: Type.String(),
    judgeSlug: Type.String(),
  },
  { additionalProperties: false },
);
export type SearchIndexPair = Static<typeof searchIndexPairSchema>;

export const searchIndexAvailableSchema = Type.Object(
  {
    available: Type.Literal(true),
    // Public-safe run reference — same exposure as the result payloads.
    aggregateRunId: Type.String({ format: 'uuid' }),
    taxonomyVersion: taxonomyVersionSchema,
    lastRefreshed: Type.String({ format: 'date-time' }),
    charges: Type.Array(searchIndexChargeSchema),
    judges: Type.Array(searchIndexJudgeSchema),
    pairs: Type.Array(searchIndexPairSchema),
  },
  { additionalProperties: false },
);
export type SearchIndexAvailable = Static<typeof searchIndexAvailableSchema>;

export const searchIndexUnavailableSchema = Type.Object(
  {
    available: Type.Literal(false),
    message: Type.Literal(SEARCH_INDEX_UNAVAILABLE_MESSAGE),
  },
  { additionalProperties: false },
);
export type SearchIndexUnavailable = Static<typeof searchIndexUnavailableSchema>;

// Structurally disjoint via the `available` literals; used as the single 200
// response schema so serialization stripping covers both arms.
export const searchIndexResponseSchema = Type.Union([
  searchIndexAvailableSchema,
  searchIndexUnavailableSchema,
]);
export type SearchIndexResponse = Static<typeof searchIndexResponseSchema>;
