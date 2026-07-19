import { Type, type Static } from '@sinclair/typebox';
import { sentencingCategoryCodeSchema } from './categories.js';
import { dateRangeSchema, thinDataStatusSchema } from './common.js';

/**
 * Conviction-grain sentencing-index section (task 35.2), the API surface of
 * the five task 35.1 aggregate tables. Joined as a NEW sibling section named
 * `sentencingIndex` on the SUCCESS arm of both result payloads — strictly
 * additive; the existing component-grain sentencing section is untouched and
 * keeps its own semantics.
 *
 * Two arms, discriminated by the house section-level `available` boolean
 * (same convention as the sentencing section):
 *
 * - present: summary always; `categories` possibly empty (a cell with
 *   convictions but zero sentenced convictions still has its summary row);
 *   `grades` on the charge arm only (ruling 2 — the judge arm carries no
 *   grade mix, so its present arm has no `grades` key at all).
 * - absent: no summary row for the cell in the active published run — covers
 *   both a run predating the index population and a zero-conviction cell,
 *   deliberately indistinguishable. Carries NO message: all user-facing copy
 *   (including the ruling-4 zero-sentenced fallback line) is 35.3's job;
 *   this payload only makes the display states derivable.
 *
 * Everything served is what 35.1 stored — the API computes no analytics.
 * The single derivation is representational: stored day medians are served
 * in MONTHS only (÷30 under the 360-day-year convention, ≤1 decimal,
 * half-up, decimal-safe), and raw day values are never served.
 */

export const sentencingIndexSummarySchema = Type.Object(
  {
    // The conviction denominator; a summary row exists only for cells with
    // at least one conviction (the stored `convictions > 0` CHECK).
    convictions: Type.Integer({ minimum: 1 }),
    sentencedConvictions: Type.Integer({ minimum: 0 }),
    // The wedge: convictions with no public-eligible sentencing component —
    // excluded-with-disclosure (ruling 1), never "no penalty".
    wedgeCount: Type.Integer({ minimum: 0 }),
    wedgePercentage: Type.Number({ minimum: 0, maximum: 100 }),
    // Thin flag keyed on sentenced convictions (ruling 4), passed through.
    thinData: thinDataStatusSchema,
    // The cell's conviction disposition-date envelope — narrower than the
    // result-level run date range.
    dateRange: dateRangeSchema,
  },
  { additionalProperties: false },
);
export type SentencingIndexSummary = Static<typeof sentencingIndexSummarySchema>;

/**
 * One occurring category (ruling 5: absence = zero, categories come from the
 * taxonomy — the code set is the public sentencing-category union). The
 * duration trio is all-present-or-all-absent (the stored CHECK); it exists
 * only for duration-bearing categories. Medians are months, never days.
 */
export const sentencingIndexCategoryRowSchema = Type.Object(
  {
    categoryCode: sentencingCategoryCodeSchema,
    convictionCount: Type.Integer({ minimum: 1 }),
    percentageOfSentenced: Type.Number({ minimum: 0, maximum: 100 }),
    medianMinMonths: Type.Optional(Type.Number({ minimum: 0 })),
    medianMaxMonths: Type.Optional(Type.Number({ minimum: 0 })),
    minAssumedPercentage: Type.Optional(Type.Number({ minimum: 0, maximum: 100 })),
  },
  { additionalProperties: false },
);
export type SentencingIndexCategoryRow = Static<typeof sentencingIndexCategoryRowSchema>;

/**
 * One grade-mix row (charge arm only). `grade` is a parsed CPCMS grade code
 * or the explicit `ungraded` bucket — grades are not a taxonomy, so the
 * schema constrains shape, not vocabulary. Percentage is of the cell's
 * convictions (not sentenced convictions).
 */
export const convictionGradeRowSchema = Type.Object(
  {
    grade: Type.String(),
    convictionCount: Type.Integer({ minimum: 1 }),
    percentageOfConvictions: Type.Number({ minimum: 0, maximum: 100 }),
  },
  { additionalProperties: false },
);
export type ConvictionGradeRow = Static<typeof convictionGradeRowSchema>;

/** The shared absent arm: no summary row for the cell — and nothing else. */
export const sentencingIndexAbsentSchema = Type.Object(
  {
    available: Type.Literal(false),
  },
  { additionalProperties: false },
);
export type SentencingIndexAbsent = Static<typeof sentencingIndexAbsentSchema>;

export const chargeSentencingIndexPresentSchema = Type.Object(
  {
    available: Type.Literal(true),
    summary: sentencingIndexSummarySchema,
    categories: Type.Array(sentencingIndexCategoryRowSchema),
    grades: Type.Array(convictionGradeRowSchema),
  },
  { additionalProperties: false },
);
export type ChargeSentencingIndexPresent = Static<typeof chargeSentencingIndexPresentSchema>;

export const judgeSentencingIndexPresentSchema = Type.Object(
  {
    available: Type.Literal(true),
    summary: sentencingIndexSummarySchema,
    categories: Type.Array(sentencingIndexCategoryRowSchema),
  },
  { additionalProperties: false },
);
export type JudgeSentencingIndexPresent = Static<typeof judgeSentencingIndexPresentSchema>;

export const chargeSentencingIndexSchema = Type.Union([
  chargeSentencingIndexPresentSchema,
  sentencingIndexAbsentSchema,
]);
export type ChargeSentencingIndex = Static<typeof chargeSentencingIndexSchema>;

export const judgeSentencingIndexSchema = Type.Union([
  judgeSentencingIndexPresentSchema,
  sentencingIndexAbsentSchema,
]);
export type JudgeSentencingIndex = Static<typeof judgeSentencingIndexSchema>;
