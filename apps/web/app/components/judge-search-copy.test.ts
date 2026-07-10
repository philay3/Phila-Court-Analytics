import { describe, expect, it } from 'vitest';
import { scanPublicCopy } from '@pca/shared';
import { JUDGE_SEARCH_COPY } from './judge-search-copy.js';

describe('judge search copy safety', () => {
  it('every exported judge-search copy constant passes scanPublicCopy', () => {
    for (const [key, value] of Object.entries(JUDGE_SEARCH_COPY)) {
      expect(scanPublicCopy(value), `JUDGE_SEARCH_COPY.${key}: "${value}"`).toEqual([]);
    }
  });
});
