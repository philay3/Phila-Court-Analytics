import { describe, expect, it } from 'vitest';
import { scanPublicCopy } from '@pca/shared';
import { CHARGES_COPY, formatChargeCountLine } from './charges-copy.js';

describe('charges directory copy safety', () => {
  it('every exported charges copy constant passes scanPublicCopy', () => {
    for (const [key, value] of Object.entries(CHARGES_COPY)) {
      expect(scanPublicCopy(value), `CHARGES_COPY.${key}: "${value}"`).toEqual([]);
    }
  });

  it('formatChargeCountLine outputs pass scanPublicCopy', () => {
    for (const count of [0, 1, 2, 74]) {
      expect(scanPublicCopy(formatChargeCountLine(count))).toEqual([]);
    }
  });
});

describe('formatChargeCountLine', () => {
  it('renders the sanctioned singular form at exactly 1', () => {
    expect(formatChargeCountLine(1)).toBe('1 available charge');
  });

  it('renders the sanctioned plural form for every other count', () => {
    expect(formatChargeCountLine(0)).toBe('0 available charges');
    expect(formatChargeCountLine(2)).toBe('2 available charges');
    expect(formatChargeCountLine(74)).toBe('74 available charges');
  });
});
