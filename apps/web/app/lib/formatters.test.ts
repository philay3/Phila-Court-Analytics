import { afterAll, describe, expect, it } from 'vitest';
import { scanPublicCopy } from '@pca/shared';
import type { SentencingIndexSummary } from '@pca/shared';
import {
  RESULT_TYPE_CHARGE_ONLY_LABEL,
  RESULT_TYPE_JUDGE_SPECIFIC_LABEL,
  THIN_DATA_LABEL,
  formatAggregateRunLabel,
  formatCount,
  formatDateOnly,
  formatDateRange,
  formatGradeMixLine,
  formatLastRefreshed,
  formatMedianMonths,
  formatPercentage,
  formatRecordedOutcomes,
  formatRecordsLabel,
  formatResultTypeLabel,
  formatSentenceComponentsLabel,
  formatSentencedConvictionsLabel,
  formatThinDataLabel,
  formatWedgeDisclosure,
  formatZeroSentencedFallback,
} from './formatters.js';

/** Fabricated summary for wedge tests; every number is a test-only value. */
function summaryWith(overrides: Partial<SentencingIndexSummary>): SentencingIndexSummary {
  return {
    convictions: 600,
    sentencedConvictions: 588,
    wedgeCount: 12,
    wedgePercentage: 2,
    thinData: false,
    dateRange: { start: '2025-01-03', end: '2026-06-27' },
    ...overrides,
  };
}

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

describe('reconciled sample labels (35.3, pin 11)', () => {
  it('locks the "Records: N" outcome-block format', () => {
    expect(formatRecordsLabel(1234)).toBe('Records: 1,234');
    expect(formatRecordsLabel(0)).toBe('Records: 0');
  });

  it('locks the "Sentence components: N" component-block format', () => {
    expect(formatSentenceComponentsLabel(987)).toBe('Sentence components: 987');
  });

  it('locks the "Sentenced convictions: N" index-block format', () => {
    expect(formatSentencedConvictionsLabel(588)).toBe('Sentenced convictions: 588');
    expect(formatSentencedConvictionsLabel(1234)).toBe('Sentenced convictions: 1,234');
  });
});

describe('formatMedianMonths (35.3, pin 4)', () => {
  it('collapses a flat pair to a single figure', () => {
    expect(formatMedianMonths(3, 3)).toBe('3');
  });

  it('renders a distinct pair as an unspaced en-dash range', () => {
    expect(formatMedianMonths(12, 18)).toBe('12–18');
    expect(formatMedianMonths(0.4, 3)).toBe('0.4–3');
  });

  it('returns null for a duration-free category (empty cell, ruling Q7)', () => {
    expect(formatMedianMonths(undefined, undefined)).toBeNull();
  });
});

describe('formatWedgeDisclosure (35.3, pin 10)', () => {
  it('fills the plural template with served values', () => {
    expect(formatWedgeDisclosure(summaryWith({}))).toBe(
      '12 of 600 recorded convictions (2%) have no public sentencing record in the collected data and are not counted in the rates above.',
    );
  });

  it('uses the singular variant at wedgeCount = 1', () => {
    expect(formatWedgeDisclosure(summaryWith({ wedgeCount: 1, wedgePercentage: 0.2 }))).toBe(
      '1 of 600 recorded convictions (0.2%) has no public sentencing record in the collected data and is not counted in the rates above.',
    );
  });

  it('renders the zero-wedge case through the plural form', () => {
    expect(formatWedgeDisclosure(summaryWith({ wedgeCount: 0, wedgePercentage: 0 }))).toBe(
      '0 of 600 recorded convictions (0%) have no public sentencing record in the collected data and are not counted in the rates above.',
    );
  });
});

describe('formatZeroSentencedFallback (35.3, ruling 4)', () => {
  it('fills the plural template with the served conviction count', () => {
    expect(formatZeroSentencedFallback(323)).toBe(
      'None of the 323 recorded convictions here has a public sentencing record in the collected data.',
    );
  });

  it('uses the singular variant at convictions = 1', () => {
    expect(formatZeroSentencedFallback(1)).toBe(
      'The 1 recorded conviction here has no public sentencing record in the collected data.',
    );
  });
});

describe('formatGradeMixLine (35.3, pin 5)', () => {
  it('renders a multi-grade mix dominant-first as served, with the gated ungraded label', () => {
    expect(
      formatGradeMixLine([
        { grade: 'F3', convictionCount: 300, percentageOfConvictions: 50 },
        { grade: 'M1', convictionCount: 150, percentageOfConvictions: 25 },
        { grade: 'ungraded', convictionCount: 30, percentageOfConvictions: 5 },
      ]),
    ).toBe('Conviction grades: F3 50% · M1 25% · no recorded grade 5%');
  });

  it('states the grade rather than a mix on a single-grade page', () => {
    expect(
      formatGradeMixLine([{ grade: 'M1', convictionCount: 9, percentageOfConvictions: 100 }]),
    ).toBe('Every recorded conviction here is grade M1.');
  });

  it('uses the ungraded wording when the single grade row is the ungraded bucket', () => {
    expect(
      formatGradeMixLine([{ grade: 'ungraded', convictionCount: 4, percentageOfConvictions: 100 }]),
    ).toBe('Every recorded conviction here has no recorded grade.');
  });

  it('returns null for an empty grade list', () => {
    expect(formatGradeMixLine([])).toBeNull();
  });
});

describe('formatAggregateRunLabel (35.3, pin 7)', () => {
  it('renders the pinned prefix plus the first 8 characters of the run id', () => {
    expect(formatAggregateRunLabel('2f9c1e04-8d5b-4c33-9a67-0d1e2f3a4b5c')).toBe(
      'Data release: 2f9c1e04',
    );
  });
});

describe('formatRecordedOutcomes', () => {
  it('locks the surface-scoped "Recorded outcomes: N" format (DP-5 Amendment A)', () => {
    expect(formatRecordedOutcomes(1)).toBe('Recorded outcomes: 1');
    expect(formatRecordedOutcomes(1234)).toBe('Recorded outcomes: 1,234');
    expect(formatRecordedOutcomes(0)).toBe('Recorded outcomes: 0');
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
      formatRecordsLabel(1234),
      formatSentenceComponentsLabel(987),
      formatSentencedConvictionsLabel(588),
      formatWedgeDisclosure(summaryWith({})),
      formatZeroSentencedFallback(323),
      formatGradeMixLine([
        { grade: 'F3', convictionCount: 300, percentageOfConvictions: 50 },
        { grade: 'M1', convictionCount: 150, percentageOfConvictions: 25 },
      ]) ?? '',
      formatAggregateRunLabel('2f9c1e04-8d5b-4c33-9a67-0d1e2f3a4b5c'),
    ];
    for (const label of labels) {
      expect(scanPublicCopy(label)).toEqual([]);
    }
  });
});
