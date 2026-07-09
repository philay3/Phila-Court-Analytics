import { Value } from '@sinclair/typebox/value';
import { describe, expect, it } from 'vitest';

import { validOutcomeDistribution, validSentencingDistribution } from '../test-support/fixtures.js';
import {
  dateRangeSchema,
  outcomeDistributionEntrySchema,
  outcomeDistributionSchema,
  sampleSizeSchema,
  sentencingDistributionSchema,
  taxonomyVersionSchema,
} from './common.js';

function firstEntry() {
  const [entry] = validOutcomeDistribution().entries;
  if (!entry) throw new Error('taxonomy has no public outcome categories');
  return entry;
}

describe('sampleSizeSchema', () => {
  it('accepts non-negative integers and rejects negatives and non-integers', () => {
    expect(Value.Check(sampleSizeSchema, 0)).toBe(true);
    expect(Value.Check(sampleSizeSchema, 120)).toBe(true);
    expect(Value.Check(sampleSizeSchema, -1)).toBe(false);
    expect(Value.Check(sampleSizeSchema, 1.5)).toBe(false);
  });
});

describe('dateRangeSchema', () => {
  it('accepts ISO date strings', () => {
    expect(Value.Check(dateRangeSchema, { start: '2020-01-01', end: '2025-12-31' })).toBe(true);
  });

  it('rejects non-date strings', () => {
    expect(Value.Check(dateRangeSchema, { start: 'not-a-date', end: '2025-12-31' })).toBe(false);
  });

  it('rejects unknown extra properties', () => {
    expect(
      Value.Check(dateRangeSchema, { start: '2020-01-01', end: '2025-12-31', tz: 'UTC' }),
    ).toBe(false);
  });
});

describe('taxonomyVersionSchema', () => {
  it('accepts semver-shaped strings and rejects others', () => {
    expect(Value.Check(taxonomyVersionSchema, '1.0.0')).toBe(true);
    expect(Value.Check(taxonomyVersionSchema, '12.34.56')).toBe(true);
    expect(Value.Check(taxonomyVersionSchema, '1.0')).toBe(false);
    expect(Value.Check(taxonomyVersionSchema, 'not-semver')).toBe(false);
  });
});

describe('distribution entries', () => {
  it('accepts a valid entry', () => {
    expect(Value.Check(outcomeDistributionEntrySchema, firstEntry())).toBe(true);
  });

  it('rejects negative counts', () => {
    expect(Value.Check(outcomeDistributionEntrySchema, { ...firstEntry(), count: -1 })).toBe(false);
  });

  it('rejects non-integer counts', () => {
    expect(Value.Check(outcomeDistributionEntrySchema, { ...firstEntry(), count: 1.5 })).toBe(
      false,
    );
  });

  it('rejects percentages outside 0-100', () => {
    expect(Value.Check(outcomeDistributionEntrySchema, { ...firstEntry(), percentage: -1 })).toBe(
      false,
    );
    expect(
      Value.Check(outcomeDistributionEntrySchema, { ...firstEntry(), percentage: 100.01 }),
    ).toBe(false);
  });

  it('rejects a count without a percentage and a percentage without a count', () => {
    const withoutPercentage: Record<string, unknown> = { ...firstEntry() };
    delete withoutPercentage.percentage;
    const withoutCount: Record<string, unknown> = { ...firstEntry() };
    delete withoutCount.count;
    expect(Value.Check(outcomeDistributionEntrySchema, withoutPercentage)).toBe(false);
    expect(Value.Check(outcomeDistributionEntrySchema, withoutCount)).toBe(false);
  });

  it('rejects unknown extra properties', () => {
    expect(Value.Check(outcomeDistributionEntrySchema, { ...firstEntry(), internalId: 42 })).toBe(
      false,
    );
  });
});

describe('distribution wrappers', () => {
  it('accepts valid outcome and sentencing distributions', () => {
    expect(Value.Check(outcomeDistributionSchema, validOutcomeDistribution())).toBe(true);
    expect(Value.Check(sentencingDistributionSchema, validSentencingDistribution())).toBe(true);
  });

  it('requires sampleSize, dateRange, and thinData on every distribution', () => {
    for (const field of ['sampleSize', 'dateRange', 'thinData'] as const) {
      const distribution: Record<string, unknown> = { ...validOutcomeDistribution() };
      delete distribution[field];
      expect(Value.Check(outcomeDistributionSchema, distribution)).toBe(false);
    }
  });

  it('rejects a negative sample size', () => {
    expect(
      Value.Check(outcomeDistributionSchema, { ...validOutcomeDistribution(), sampleSize: -1 }),
    ).toBe(false);
  });

  it('rejects unknown extra properties', () => {
    expect(
      Value.Check(outcomeDistributionSchema, { ...validOutcomeDistribution(), rawText: 'x' }),
    ).toBe(false);
  });
});
