import { Type, type Static, type TSchema } from '@sinclair/typebox';
import { outcomeCategoryCodeSchema, sentencingCategoryCodeSchema } from './categories.js';

export const sampleSizeSchema = Type.Integer({ minimum: 0 });
export type SampleSize = Static<typeof sampleSizeSchema>;

export const dateRangeSchema = Type.Object(
  {
    start: Type.String({ format: 'date' }),
    end: Type.String({ format: 'date' }),
  },
  { additionalProperties: false },
);
export type DateRange = Static<typeof dateRangeSchema>;

export const taxonomyVersionSchema = Type.String({ pattern: '^\\d+\\.\\d+\\.\\d+$' });
export type TaxonomyVersion = Static<typeof taxonomyVersionSchema>;

export const thinDataStatusSchema = Type.Boolean();
export type ThinDataStatus = Static<typeof thinDataStatusSchema>;

// Counts and percentages are always returned together: both properties are required.
function buildDistributionEntrySchema<Code extends TSchema>(categoryCodeSchema: Code) {
  return Type.Object(
    {
      categoryCode: categoryCodeSchema,
      displayName: Type.String(),
      count: Type.Integer({ minimum: 0 }),
      percentage: Type.Number({ minimum: 0, maximum: 100 }),
    },
    { additionalProperties: false },
  );
}

// Every distribution carries its own sample size, date range, and thin-data status,
// because sentencing sample size differs from outcome sample size.
function buildDistributionSchema<Entry extends TSchema>(entrySchema: Entry) {
  return Type.Object(
    {
      entries: Type.Array(entrySchema),
      sampleSize: sampleSizeSchema,
      dateRange: dateRangeSchema,
      thinData: thinDataStatusSchema,
    },
    { additionalProperties: false },
  );
}

export const outcomeDistributionEntrySchema =
  buildDistributionEntrySchema(outcomeCategoryCodeSchema);
export type OutcomeDistributionEntry = Static<typeof outcomeDistributionEntrySchema>;

export const outcomeDistributionSchema = buildDistributionSchema(outcomeDistributionEntrySchema);
export type OutcomeDistribution = Static<typeof outcomeDistributionSchema>;

export const sentencingDistributionEntrySchema = buildDistributionEntrySchema(
  sentencingCategoryCodeSchema,
);
export type SentencingDistributionEntry = Static<typeof sentencingDistributionEntrySchema>;

export const sentencingDistributionSchema = buildDistributionSchema(
  sentencingDistributionEntrySchema,
);
export type SentencingDistribution = Static<typeof sentencingDistributionSchema>;
