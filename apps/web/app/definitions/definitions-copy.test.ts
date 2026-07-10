import { describe, expect, it } from 'vitest';
import { scanPublicCopy } from '@pca/shared';
import { DEFINITIONS_COPY } from './definitions-copy.js';

describe('definitions copy safety', () => {
  it('every exported definitions copy constant passes scanPublicCopy', () => {
    for (const [key, value] of Object.entries(DEFINITIONS_COPY)) {
      expect(scanPublicCopy(value), `DEFINITIONS_COPY.${key}: "${value}"`).toEqual([]);
    }
  });
});
