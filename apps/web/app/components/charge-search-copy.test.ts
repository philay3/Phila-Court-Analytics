import { describe, expect, it } from 'vitest';
import { scanPublicCopy } from '@pca/shared';
import { CHARGE_SEARCH_COPY } from './charge-search-copy.js';

describe('charge search copy safety', () => {
  it('every exported charge-search copy constant passes scanPublicCopy', () => {
    for (const [key, value] of Object.entries(CHARGE_SEARCH_COPY)) {
      expect(scanPublicCopy(value), `CHARGE_SEARCH_COPY.${key}: "${value}"`).toEqual([]);
    }
  });
});
