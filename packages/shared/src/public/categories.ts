import { Type, type Static } from '@sinclair/typebox';
import { OUTCOME_CATEGORIES, SENTENCING_CATEGORIES } from '@pca/taxonomy';

type OutcomeCategory = (typeof OUTCOME_CATEGORIES)[number];
type SentencingCategory = (typeof SENTENCING_CATEGORIES)[number];

// Public contracts accept only categories flagged `public` in the taxonomy; internal
// buckets (e.g. "unknown" for unmapped parser output) must fail schema validation so
// they can never appear in a public response, even through an aggregation bug.
export const publicOutcomeCategories = OUTCOME_CATEGORIES.filter(
  (category): category is Extract<OutcomeCategory, { public: true }> => category.public,
);

export const publicSentencingCategories = SENTENCING_CATEGORIES.filter(
  (category): category is Extract<SentencingCategory, { public: true }> => category.public,
);

export const outcomeCategoryCodeSchema = Type.Union(
  publicOutcomeCategories.map((category) => Type.Literal(category.code)),
);
export type OutcomeCategoryCode = Static<typeof outcomeCategoryCodeSchema>;

export const sentencingCategoryCodeSchema = Type.Union(
  publicSentencingCategories.map((category) => Type.Literal(category.code)),
);
export type SentencingCategoryCode = Static<typeof sentencingCategoryCodeSchema>;
