import { describe, expect, it } from 'vitest';
import { scanPublicCopy } from '@pca/shared';
import { DATA_COVERAGE_COPY } from './data-coverage-copy.js';

describe('data coverage copy safety', () => {
  it('every exported data coverage copy constant passes scanPublicCopy', () => {
    for (const [key, value] of Object.entries(DATA_COVERAGE_COPY)) {
      expect(scanPublicCopy(value), `DATA_COVERAGE_COPY.${key}: "${value}"`).toEqual([]);
    }
  });
});
