import { describe, expect, it } from 'vitest';

import {
  EXPECTED_OUTCOME_CODES,
  loadSeeds,
  validateAll,
  validateCategoryFile,
  validateVersion,
  type TaxonomyCategory,
} from './validation.js';

function outcomeSeedCopy(): TaxonomyCategory[] {
  return structuredClone(loadSeeds().outcome) as TaxonomyCategory[];
}

describe('validateAll on real seeds', () => {
  it('passes with no errors', () => {
    expect(validateAll(loadSeeds())).toEqual([]);
  });
});

describe('validateCategoryFile failures', () => {
  it('rejects a duplicate code', () => {
    const seed = outcomeSeedCopy();
    const second = seed[1];
    if (!second) throw new Error('seed fixture too small');
    second.code = 'dismissed';
    const errors = validateCategoryFile('outcome', seed, EXPECTED_OUTCOME_CODES);
    expect(errors.join('\n')).toContain('duplicate code "dismissed"');
  });

  it('rejects a missing field', () => {
    const seed = outcomeSeedCopy();
    delete (seed[0] as Partial<TaxonomyCategory>).displayName;
    const errors = validateCategoryFile('outcome', seed, EXPECTED_OUTCOME_CODES);
    expect(errors.join('\n')).toContain('"displayName" must be a non-empty string');
  });

  it('rejects a banned term in a definition, case-insensitively', () => {
    const seed = outcomeSeedCopy();
    const first = seed[0];
    if (!first) throw new Error('seed fixture too small');
    first.definition = 'This category helps Predict how a case will end.';
    const errors = validateCategoryFile('outcome', seed, EXPECTED_OUTCOME_CODES);
    expect(errors.join('\n')).toContain('banned term "predict"');
  });

  it('rejects an unexpected category code', () => {
    const seed = outcomeSeedCopy();
    seed.push({
      code: 'mystery',
      displayName: 'Mystery',
      definition: 'A category that should not exist.',
      sortOrder: 99,
      public: true,
    });
    const errors = validateCategoryFile('outcome', seed, EXPECTED_OUTCOME_CODES);
    expect(errors.join('\n')).toContain('unexpected category code "mystery"');
  });

  it('rejects a missing expected category code', () => {
    const seed = outcomeSeedCopy().filter((entry) => entry.code !== 'ard');
    const errors = validateCategoryFile('outcome', seed, EXPECTED_OUTCOME_CODES);
    expect(errors.join('\n')).toContain('missing expected category code "ard"');
  });

  it('rejects a non-snake_case code', () => {
    const seed = outcomeSeedCopy();
    const first = seed[0];
    if (!first) throw new Error('seed fixture too small');
    first.code = 'Dismissed';
    const errors = validateCategoryFile('outcome', seed, EXPECTED_OUTCOME_CODES);
    expect(errors.join('\n')).toContain('is not snake_case');
  });

  it('rejects a duplicate sortOrder', () => {
    const seed = outcomeSeedCopy();
    const second = seed[1];
    if (!second) throw new Error('seed fixture too small');
    second.sortOrder = 1;
    const errors = validateCategoryFile('outcome', seed, EXPECTED_OUTCOME_CODES);
    expect(errors.join('\n')).toContain('duplicate sortOrder 1');
  });
});

describe('validateVersion', () => {
  it('accepts valid semver', () => {
    expect(validateVersion({ taxonomyVersion: '1.0.0' })).toEqual([]);
  });

  it('rejects invalid semver', () => {
    expect(validateVersion({ taxonomyVersion: 'v1' })).toHaveLength(1);
    expect(validateVersion({ taxonomyVersion: '1.0' })).toHaveLength(1);
    expect(validateVersion({})).toHaveLength(1);
  });
});
