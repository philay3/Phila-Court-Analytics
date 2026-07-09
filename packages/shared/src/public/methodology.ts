import { Type, type Static } from '@sinclair/typebox';

/**
 * Methodology contract (task 9.2): GET /api/v1/public/methodology.
 *
 * Structured, keyed sections — never one text blob — so the Sprint 3
 * frontend can render sections independently and copy tests can target
 * individual fields. The copy itself lives in apps/api (static per deploy,
 * no database dependency); this schema pins the section set, so adding or
 * dropping a section is a contract change, not a copy edit.
 */

export const methodologySectionSchema = Type.Object(
  {
    heading: Type.String({ minLength: 1 }),
    body: Type.String({ minLength: 1 }),
  },
  { additionalProperties: false },
);
export type MethodologySection = Static<typeof methodologySectionSchema>;

/**
 * The ten required section keys, in presentation order. Kept in sync with
 * the response schema by a shared test; consumers (tests, frontend) iterate
 * this array instead of hand-copying key lists.
 */
export const METHODOLOGY_SECTION_KEYS = [
  'dataSource',
  'dataRange',
  'whatResultsMean',
  'notPrediction',
  'notLegalAdvice',
  'sampleSize',
  'thinData',
  'chargeLevelAnalytics',
  'sentencing',
  'limitations',
] as const;
export type MethodologySectionKey = (typeof METHODOLOGY_SECTION_KEYS)[number];

export const methodologySectionsSchema = Type.Object(
  {
    dataSource: methodologySectionSchema,
    dataRange: methodologySectionSchema,
    whatResultsMean: methodologySectionSchema,
    notPrediction: methodologySectionSchema,
    notLegalAdvice: methodologySectionSchema,
    sampleSize: methodologySectionSchema,
    thinData: methodologySectionSchema,
    chargeLevelAnalytics: methodologySectionSchema,
    sentencing: methodologySectionSchema,
    limitations: methodologySectionSchema,
  },
  { additionalProperties: false },
);
export type MethodologySections = Static<typeof methodologySectionsSchema>;

export const methodologyResponseSchema = Type.Object(
  {
    sections: methodologySectionsSchema,
  },
  { additionalProperties: false },
);
export type MethodologyResponse = Static<typeof methodologyResponseSchema>;
