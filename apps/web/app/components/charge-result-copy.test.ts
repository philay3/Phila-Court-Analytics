import { describe, expect, it } from 'vitest';
import { scanPublicCopy } from '@pca/shared';
import { CHARGE_RESULT_COPY } from './charge-result-copy.js';

describe('charge result copy safety', () => {
  it('every exported charge-result copy constant passes scanPublicCopy', () => {
    for (const [key, value] of Object.entries(CHARGE_RESULT_COPY)) {
      expect(scanPublicCopy(value), `CHARGE_RESULT_COPY.${key}: "${value}"`).toEqual([]);
    }
  });
});
