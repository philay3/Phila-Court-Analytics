import { describe, expect, it } from 'vitest';
import type {
  ChargeSentencingIndexPresent,
  JudgeSentencingIndexPresent,
  SentencingIndexSummary,
} from '@pca/shared';
import {
  resolveChargeSentencingIndexDisplay,
  resolveJudgeSentencingIndexDisplay,
} from './sentencing-index-display.js';

/** Fabricated summary; every number is a test-only value. */
function summary(overrides: Partial<SentencingIndexSummary> = {}): SentencingIndexSummary {
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

const chargePresent: ChargeSentencingIndexPresent = {
  available: true,
  summary: summary(),
  categories: [{ categoryCode: 'probation', convictionCount: 290, percentageOfSentenced: 49.3 }],
  grades: [{ grade: 'F3', convictionCount: 300, percentageOfConvictions: 50 }],
};

const judgePresent: JudgeSentencingIndexPresent = {
  available: true,
  summary: summary({ convictions: 49, sentencedConvictions: 45, wedgeCount: 4 }),
  categories: [{ categoryCode: 'probation', convictionCount: 30, percentageOfSentenced: 66.7 }],
};

describe('resolveChargeSentencingIndexDisplay', () => {
  it('maps a present arm with categories to lead', () => {
    expect(resolveChargeSentencingIndexDisplay(chargePresent)).toEqual({
      kind: 'lead',
      index: chargePresent,
    });
  });

  it('maps a present arm with empty categories to zero-sentenced', () => {
    const zeroSentenced: ChargeSentencingIndexPresent = {
      available: true,
      summary: summary({
        convictions: 323,
        sentencedConvictions: 0,
        wedgeCount: 323,
        wedgePercentage: 100,
        thinData: true,
      }),
      categories: [],
      grades: [{ grade: 'M1', convictionCount: 200, percentageOfConvictions: 61.9 }],
    };
    expect(resolveChargeSentencingIndexDisplay(zeroSentenced)).toEqual({
      kind: 'zero-sentenced',
      index: zeroSentenced,
    });
  });

  it('maps the absent arm to absent', () => {
    expect(resolveChargeSentencingIndexDisplay({ available: false })).toEqual({ kind: 'absent' });
  });
});

describe('resolveJudgeSentencingIndexDisplay', () => {
  it('maps a present arm with categories to lead', () => {
    expect(resolveJudgeSentencingIndexDisplay(judgePresent)).toEqual({
      kind: 'lead',
      index: judgePresent,
    });
  });

  it('maps a present arm with empty categories to zero-sentenced', () => {
    const zeroSentenced: JudgeSentencingIndexPresent = {
      available: true,
      summary: summary({
        convictions: 7,
        sentencedConvictions: 0,
        wedgeCount: 7,
        wedgePercentage: 100,
        thinData: true,
      }),
      categories: [],
    };
    expect(resolveJudgeSentencingIndexDisplay(zeroSentenced)).toEqual({
      kind: 'zero-sentenced',
      index: zeroSentenced,
    });
  });

  it('maps the absent arm to absent', () => {
    expect(resolveJudgeSentencingIndexDisplay({ available: false })).toEqual({ kind: 'absent' });
  });
});
