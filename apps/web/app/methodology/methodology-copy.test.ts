import { describe, expect, it } from 'vitest';
import { scanPublicCopy } from '@pca/shared';
import { METHODOLOGY_COPY } from './methodology-copy.js';

describe('methodology copy safety', () => {
  it('every exported methodology copy constant passes scanPublicCopy', () => {
    for (const [key, value] of Object.entries(METHODOLOGY_COPY)) {
      expect(scanPublicCopy(value), `METHODOLOGY_COPY.${key}: "${value}"`).toEqual([]);
    }
  });
});
