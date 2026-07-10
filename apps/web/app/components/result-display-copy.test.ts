import { describe, expect, it } from 'vitest';
import { scanPublicCopy } from '@pca/shared';
import { RESULT_DISPLAY_COPY } from './result-display-copy.js';

describe('result display copy safety', () => {
  it('every exported result-display copy constant passes scanPublicCopy', () => {
    for (const [key, value] of Object.entries(RESULT_DISPLAY_COPY)) {
      expect(scanPublicCopy(value), `RESULT_DISPLAY_COPY.${key}: "${value}"`).toEqual([]);
    }
  });
});
