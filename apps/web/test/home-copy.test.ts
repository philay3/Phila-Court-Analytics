import { describe, expect, it } from 'vitest';
import { scanPublicCopy } from '@pca/shared';
import { HOME_COPY } from '../app/components/home-copy.js';

describe('home copy safety', () => {
  it('every exported homepage copy constant passes scanPublicCopy', () => {
    for (const [key, value] of Object.entries(HOME_COPY)) {
      expect(scanPublicCopy(value), `HOME_COPY.${key}: "${value}"`).toEqual([]);
    }
  });
});
