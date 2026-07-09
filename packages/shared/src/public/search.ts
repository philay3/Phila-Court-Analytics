import { Type, type Static } from '@sinclair/typebox';

// Validation rules shared by every public search endpoint (charges, judges).
// Endpoint schemas and the API services import these — never restate the
// literals; the endpoints are contractually identical on q and limit.
export const SEARCH_Q_MIN_LENGTH = 1;
export const SEARCH_Q_MAX_LENGTH = 100;
export const SEARCH_LIMIT_MIN = 1;
export const SEARCH_LIMIT_MAX = 25;
export const SEARCH_LIMIT_DEFAULT = 10;

// q carries no length constraint here: the 1–100 rule applies to the *trimmed*
// value, which Ajv cannot compute — the API service trims and enforces it via a
// catalog INVALID_REQUEST throw. Missing q is rejected here (required property).
export const chargeSearchQuerySchema = Type.Object(
  {
    q: Type.String(),
    limit: Type.Optional(
      Type.Integer({
        minimum: SEARCH_LIMIT_MIN,
        maximum: SEARCH_LIMIT_MAX,
        default: SEARCH_LIMIT_DEFAULT,
      }),
    ),
  },
  { additionalProperties: false },
);
export type ChargeSearchQuery = Static<typeof chargeSearchQuerySchema>;

export const chargeSearchResultSchema = Type.Object(
  {
    id: Type.String({ format: 'uuid' }),
    slug: Type.String(),
    displayName: Type.String(),
    statuteCode: Type.Optional(Type.String()),
    grade: Type.Optional(Type.String()),
    // Present only when the charge matched via an alias and not via its display
    // name; never populated for statute-code-only matches.
    matchedAlias: Type.Optional(Type.String()),
  },
  { additionalProperties: false },
);
export type ChargeSearchResult = Static<typeof chargeSearchResultSchema>;

export const chargeSearchResponseSchema = Type.Object(
  {
    results: Type.Array(chargeSearchResultSchema),
  },
  { additionalProperties: false },
);
export type ChargeSearchResponse = Static<typeof chargeSearchResponseSchema>;

// Same trimmed-length caveat as chargeSearchQuerySchema: the q length rule is
// enforced by the API service, not here.
export const judgeSearchQuerySchema = Type.Object(
  {
    q: Type.String(),
    limit: Type.Optional(
      Type.Integer({
        minimum: SEARCH_LIMIT_MIN,
        maximum: SEARCH_LIMIT_MAX,
        default: SEARCH_LIMIT_DEFAULT,
      }),
    ),
  },
  { additionalProperties: false },
);
export type JudgeSearchQuery = Static<typeof judgeSearchQuerySchema>;

// Identity fields only — never counts, scores, rankings, or any numeric judge
// metadata. Judge search is optional in the product and must not imply judges
// are required or comparable.
export const judgeSearchResultSchema = Type.Object(
  {
    id: Type.String({ format: 'uuid' }),
    slug: Type.String(),
    displayName: Type.String(),
    // Present only when the judge matched via an alias and not via its display
    // name; alphabetically first matching alias when several match.
    matchedAlias: Type.Optional(Type.String()),
  },
  { additionalProperties: false },
);
export type JudgeSearchResult = Static<typeof judgeSearchResultSchema>;

export const judgeSearchResponseSchema = Type.Object(
  {
    results: Type.Array(judgeSearchResultSchema),
  },
  { additionalProperties: false },
);
export type JudgeSearchResponse = Static<typeof judgeSearchResponseSchema>;
