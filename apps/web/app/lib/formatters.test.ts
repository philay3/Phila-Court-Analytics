import { afterAll, describe, expect, it } from 'vitest';
import { scanPublicCopy } from '@pca/shared';
import {
  RESULT_TYPE_CHARGE_ONLY_LABEL,
  RESULT_TYPE_JUDGE_SPECIFIC_LABEL,
  THIN_DATA_LABEL,
  formatCount,
  formatDateOnly,
  formatDateRange,
  formatLastRefreshed,
  formatPercentage,
  formatResultTypeLabel,
  formatSampleSize,
  formatThinDataLabel,
} from './formatters.js';

describe('formatCount', () => {
  it('renders zero as "0" (not blank or dropped)', () => {
    expect(formatCount(0)).toBe('0');
  });

  it('applies en-US grouping separators', () => {
    expect(formatCount(1234)).toBe('1,234');
    expect(formatCount(1234567)).toBe('1,234,567');
  });
});

describe('formatPercentage', () => {
  it('always includes the percent sign, including at the bounds', () => {
    expect(formatPercentage(0)).toBe('0%');
    expect(formatPercentage(100)).toBe('100%');
  });

  it('rounds to at most one decimal place', () => {
    expect(formatPercentage(12.34)).toBe('12.3%');
  });

  it('drops a trailing .0', () => {
    expect(formatPercentage(50)).toBe('50%');
    expect(formatPercentage(50.0)).toBe('50%');
  });
});

describe('formatSampleSize', () => {
  it('locks the noun-free "Sample size: N" format', () => {
    // n = 1 exists only to pin the format — there is no singular/plural noun.
    expect(formatSampleSize(1)).toBe('Sample size: 1');
    expect(formatSampleSize(1234)).toBe('Sample size: 1,234');
  });

  it('renders a zero sample size', () => {
    expect(formatSampleSize(0)).toBe('Sample size: 0');
  });
});

describe('formatDateRange', () => {
  it('renders a full cross-month, cross-year range', () => {
    expect(formatDateRange({ start: '2025-01-01', end: '2026-06-30' })).toBe(
      'January 1, 2025 – June 30, 2026',
    );
  });

  it('renders January 1 as January 1 — no UTC-midnight shift', () => {
    // Load-bearing timezone proof: the Date.UTC construction + UTC-pinned
    // formatter keep the calendar day stable irrespective of host timezone.
    expect(formatDateRange({ start: '2025-01-01', end: '2025-12-31' })).toBe(
      'January 1, 2025 – December 31, 2025',
    );
  });

  describe('under a spoofed host timezone (supplementary)', () => {
    const originalTz = process.env.TZ;
    afterAll(() => {
      process.env.TZ = originalTz;
    });

    it('still renders January 1 as January 1 at UTC+14', () => {
      // Supplementary only: process.env.TZ mutation is platform-inconsistent in
      // Node. The UTC-pinned formatter makes the output stable regardless.
      process.env.TZ = 'Pacific/Kiritimati';
      expect(formatDateRange({ start: '2025-01-01', end: '2025-01-01' })).toBe(
        'January 1, 2025 – January 1, 2025',
      );
    });
  });
});

describe('formatDateOnly', () => {
  it('renders a single YYYY-MM-DD as a long-form calendar date', () => {
    expect(formatDateOnly('2025-01-01')).toBe('January 1, 2025');
    expect(formatDateOnly('2026-06-30')).toBe('June 30, 2026');
  });

  it('renders January 1 as January 1 — no UTC-midnight off-by-one', () => {
    // Load-bearing timezone proof for the lone-date path: Date.UTC + the
    // UTC-pinned formatter keep the calendar day stable, so the naive
    // `new Date("2025-01-01")` midnight shift never rolls it back to Dec 31.
    expect(formatDateOnly('2025-01-01')).toBe('January 1, 2025');
    expect(formatDateOnly('2025-12-31')).toBe('December 31, 2025');
  });

  describe('under a spoofed host timezone (supplementary)', () => {
    const originalTz = process.env.TZ;
    afterAll(() => {
      process.env.TZ = originalTz;
    });

    it('still renders January 1 as January 1 at UTC+14', () => {
      // Supplementary only: process.env.TZ mutation is platform-inconsistent in
      // Node. The UTC-pinned formatter makes the output stable regardless.
      process.env.TZ = 'Pacific/Kiritimati';
      expect(formatDateOnly('2025-01-01')).toBe('January 1, 2025');
    });
  });

  it('throws on a value that is not YYYY-MM-DD', () => {
    expect(() => formatDateOnly('2025/01/01')).toThrow();
  });
});

describe('formatLastRefreshed', () => {
  it('renders an RFC 3339 instant in UTC with an explicit UTC suffix', () => {
    expect(formatLastRefreshed('2026-01-05T14:30:00Z')).toBe('January 5, 2026 at 2:30 PM UTC');
  });

  it('renders a non-UTC-offset instant in UTC', () => {
    // 09:30-05:00 is 14:30 UTC — the same instant as the case above.
    expect(formatLastRefreshed('2026-01-05T09:30:00-05:00')).toBe('January 5, 2026 at 2:30 PM UTC');
  });
});

describe('formatResultTypeLabel', () => {
  it('labels charge_only', () => {
    expect(formatResultTypeLabel('charge_only')).toBe(RESULT_TYPE_CHARGE_ONLY_LABEL);
  });

  it('labels judge_specific', () => {
    expect(formatResultTypeLabel('judge_specific')).toBe(RESULT_TYPE_JUDGE_SPECIFIC_LABEL);
  });
});

describe('formatThinDataLabel', () => {
  it('returns the label when the flag is set', () => {
    expect(formatThinDataLabel(true)).toBe(THIN_DATA_LABEL);
  });

  it('returns null when the flag is not set', () => {
    expect(formatThinDataLabel(false)).toBeNull();
  });
});

describe('copy safety', () => {
  it('has no forbidden or unguarded terms in any exported label', () => {
    const labels = [
      RESULT_TYPE_CHARGE_ONLY_LABEL,
      RESULT_TYPE_JUDGE_SPECIFIC_LABEL,
      THIN_DATA_LABEL,
      formatSampleSize(1234),
    ];
    for (const label of labels) {
      expect(scanPublicCopy(label)).toEqual([]);
    }
  });
});
