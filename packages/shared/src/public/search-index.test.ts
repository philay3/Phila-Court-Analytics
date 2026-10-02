import { describe, expect, it } from 'vitest';
import {
  SEARCH_INDEX_UNAVAILABLE_MESSAGE,
  searchIndexAvailableSchema,
  searchIndexChargeSchema,
  searchIndexJudgeSchema,
  searchIndexPairSchema,
} from './search-index.js';
import { scanPublicCopy } from './copy-safety.js';

describe('search-index pinned copy', () => {
  it('pins the unavailable-arm message to its sanctioned value', () => {
    expect(SEARCH_INDEX_UNAVAILABLE_MESSAGE).toBe(
      'Search is not available yet. It will return once published data is available.',
    );
  });

  it('the pinned message scans clean and carries no em dash', () => {
    expect(scanPublicCopy(SEARCH_INDEX_UNAVAILABLE_MESSAGE)).toEqual([]);
    expect(SEARCH_INDEX_UNAVAILABLE_MESSAGE).not.toContain('—');
  });
});

describe('search-index schema shape (pin 1: slugs only, no ids)', () => {
  it('no object in the contract declares an id property', () => {
    for (const schema of [
      searchIndexChargeSchema,
      searchIndexJudgeSchema,
      searchIndexPairSchema,
      searchIndexAvailableSchema,
    ]) {
      expect(Object.keys(schema.properties)).not.toContain('id');
      expect(schema.additionalProperties).toBe(false);
    }
  });

  it('declares exactly the pinned field sets', () => {
    expect(Object.keys(searchIndexChargeSchema.properties).sort()).toEqual([
      'aliases',
      'displayName',
      'grade',
      'slug',
      'statuteCode',
    ]);
    expect(Object.keys(searchIndexJudgeSchema.properties).sort()).toEqual([
      'aliases',
      'displayName',
      'slug',
    ]);
    expect(Object.keys(searchIndexPairSchema.properties).sort()).toEqual([
      'chargeSlug',
      'judgeSlug',
    ]);
    expect(Object.keys(searchIndexAvailableSchema.properties).sort()).toEqual([
      'aggregateRunId',
      'available',
      'charges',
      'judges',
      'lastRefreshed',
      'pairs',
      'taxonomyVersion',
    ]);
  });
});
