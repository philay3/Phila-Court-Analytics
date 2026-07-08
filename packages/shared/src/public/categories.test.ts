import { OUTCOME_CATEGORIES, SENTENCING_CATEGORIES } from '@pca/taxonomy';
import { Value } from '@sinclair/typebox/value';
import { describe, expect, it } from 'vitest';

import { validOutcomeDistribution, validSentencingDistribution } from '../test-support/fixtures.js';
import { registerStringFormats } from '../test-support/formats.js';
import { outcomeCategoryCodeSchema, sentencingCategoryCodeSchema } from './categories.js';
import { outcomeDistributionEntrySchema, sentencingDistributionEntrySchema } from './common.js';

registerStringFormats();

describe('category code schemas', () => {
  it('outcome codes match the taxonomy generated artifact (public categories) exactly', () => {
    const schemaCodes = outcomeCategoryCodeSchema.anyOf.map((literal) => literal.const);
    const artifactCodes = OUTCOME_CATEGORIES.filter((c) => c.public).map((c) => c.code);
    expect(schemaCodes).toEqual(artifactCodes);
  });

  it('sentencing codes match the taxonomy generated artifact (public categories) exactly', () => {
    const schemaCodes = sentencingCategoryCodeSchema.anyOf.map((literal) => literal.const);
    const artifactCodes = SENTENCING_CATEGORIES.filter((c) => c.public).map((c) => c.code);
    expect(schemaCodes).toEqual(artifactCodes);
  });

  it('accepts every public code', () => {
    for (const category of OUTCOME_CATEGORIES.filter((c) => c.public)) {
      expect(Value.Check(outcomeCategoryCodeSchema, category.code)).toBe(true);
    }
    for (const category of SENTENCING_CATEGORIES.filter((c) => c.public)) {
      expect(Value.Check(sentencingCategoryCodeSchema, category.code)).toBe(true);
    }
  });

  it('rejects every non-public outcome code, standalone and inside a distribution entry', () => {
    const internalCodes = OUTCOME_CATEGORIES.filter((c) => !c.public).map((c) => c.code);
    expect(internalCodes.length).toBeGreaterThan(0);
    const [entry] = validOutcomeDistribution().entries;
    for (const code of internalCodes) {
      expect(Value.Check(outcomeCategoryCodeSchema, code)).toBe(false);
      expect(Value.Check(outcomeDistributionEntrySchema, { ...entry, categoryCode: code })).toBe(
        false,
      );
    }
  });

  it('rejects every non-public sentencing code, standalone and inside a distribution entry', () => {
    const internalCodes = SENTENCING_CATEGORIES.filter((c) => !c.public).map((c) => c.code);
    expect(internalCodes.length).toBeGreaterThan(0);
    const [entry] = validSentencingDistribution().entries;
    for (const code of internalCodes) {
      expect(Value.Check(sentencingCategoryCodeSchema, code)).toBe(false);
      expect(Value.Check(sentencingDistributionEntrySchema, { ...entry, categoryCode: code })).toBe(
        false,
      );
    }
  });
});
