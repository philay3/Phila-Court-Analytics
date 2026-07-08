import { Type, type Static } from '@sinclair/typebox';

export const chargeSuggestionSchema = Type.Object(
  {
    chargeId: Type.String(),
    displayName: Type.String(),
    slug: Type.String(),
  },
  { additionalProperties: false },
);
export type ChargeSuggestion = Static<typeof chargeSuggestionSchema>;

export const chargeSearchResponseSchema = Type.Object(
  {
    results: Type.Array(chargeSuggestionSchema),
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
