import { Type, type Static } from '@sinclair/typebox';

// q carries no length constraint here: the 1–100 rule applies to the *trimmed*
// value, which Ajv cannot compute — the API service trims and enforces it via a
// catalog INVALID_REQUEST throw. Missing q is rejected here (required property).
export const chargeSearchQuerySchema = Type.Object(
  {
    q: Type.String(),
    limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 25, default: 10 })),
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

export const judgeSuggestionSchema = Type.Object(
  {
    judgeId: Type.String(),
    displayName: Type.String(),
    slug: Type.String(),
  },
  { additionalProperties: false },
);
export type JudgeSuggestion = Static<typeof judgeSuggestionSchema>;

export const judgeSearchResponseSchema = Type.Object(
  {
    results: Type.Array(judgeSuggestionSchema),
  },
  { additionalProperties: false },
);
export type JudgeSearchResponse = Static<typeof judgeSearchResponseSchema>;
