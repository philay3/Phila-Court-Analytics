import { describe, expect, it } from 'vitest';
import { scanPublicCopy } from '@pca/shared';
import { JUDGE_RESULT_COPY } from './judge-result-copy.js';

describe('judge result copy safety', () => {
  it('every exported judge-result copy constant passes scanPublicCopy', () => {
    for (const [key, value] of Object.entries(JUDGE_RESULT_COPY)) {
      expect(scanPublicCopy(value), `JUDGE_RESULT_COPY.${key}: "${value}"`).toEqual([]);
    }
  });
});
