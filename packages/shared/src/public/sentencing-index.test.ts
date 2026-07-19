import { Value } from '@sinclair/typebox/value';
import { describe, expect, it } from 'vitest';

import {
  validChargeOnlyResult,
  validChargeSentencingIndex,
  validJudgeSentencingIndex,
  validJudgeSpecificResultSuccess,
} from '../test-support/fixtures.js';
import { chargeOnlyResultResponseSchema } from './charge-result.js';
import { judgeSpecificResultResponseSchema } from './judge-result.js';
import {
  chargeSentencingIndexSchema,
  judgeSentencingIndexSchema,
  sentencingIndexAbsentSchema,
} from './sentencing-index.js';

// The present fixtures are the charge arm (grades required) and the judge arm
// (no grades key); the absent arm is the shared `{ available: false }` and is
// deliberately message-free — all copy is 35.3's.

describe('chargeSentencingIndexSchema (tagged union)', () => {
  it('accepts the present arm and the bare absent arm', () => {
    expect(Value.Check(chargeSentencingIndexSchema, validChargeSentencingIndex())).toBe(true);
    expect(Value.Check(chargeSentencingIndexSchema, { available: false })).toBe(true);
  });

  it('accepts a present arm with empty categories (zero-sentenced summary) and empty grades', () => {
    const index = validChargeSentencingIndex();
    expect(index.available).toBe(true);
    if (!index.available) return;
    index.summary = {
      ...index.summary,
      sentencedConvictions: 0,
      wedgeCount: index.summary.convictions,
      wedgePercentage: 100,
      thinData: true,
    };
    index.categories = [];
    index.grades = [];
    expect(Value.Check(chargeSentencingIndexSchema, index)).toBe(true);
  });

  it('rejects the absent arm with a message or any data key (no copy in 35.2)', () => {
    expect(Value.Check(sentencingIndexAbsentSchema, { available: false, message: 'soon' })).toBe(
      false,
    );
    const present = validChargeSentencingIndex();
    expect(present.available).toBe(true);
    if (!present.available) return;
    expect(
      Value.Check(chargeSentencingIndexSchema, { available: false, summary: present.summary }),
    ).toBe(false);
  });

  it('requires summary, categories, and grades on the charge present arm', () => {
    for (const field of ['summary', 'categories', 'grades'] as const) {
      const index: Record<string, unknown> = { ...validChargeSentencingIndex() };
      delete index[field];
      expect(Value.Check(chargeSentencingIndexSchema, index), `missing ${field}`).toBe(false);
    }
  });

  it('accepts category rows only with the all-or-none duration trio intact', () => {
    const index = validChargeSentencingIndex();
    expect(index.available).toBe(true);
    if (!index.available) return;
    const durationRow = index.categories[0];
    expect(durationRow?.medianMinMonths).toBeDefined();
    const bareRow = index.categories[1];
    expect(bareRow?.medianMinMonths).toBeUndefined();
    // The schema allows each optional independently (the all-or-none rule is
    // the stored CHECK, passed through by the service) — but day-named keys
    // must never validate: months are the only served unit.
    expect(
      Value.Check(chargeSentencingIndexSchema, {
        ...index,
        categories: [{ ...durationRow, medianMinDays: 345 }],
      }),
    ).toBe(false);
  });

  it('rejects non-public and unknown category codes', () => {
    const index = validChargeSentencingIndex();
    expect(index.available).toBe(true);
    if (!index.available) return;
    for (const code of ['unknown', 'not-a-category']) {
      expect(
        Value.Check(chargeSentencingIndexSchema, {
          ...index,
          categories: [{ categoryCode: code, convictionCount: 1, percentageOfSentenced: 1 }],
        }),
        `code ${code} must fail`,
      ).toBe(false);
    }
  });

  it('rejects extra properties on summary, category rows, and grade rows', () => {
    const index = validChargeSentencingIndex();
    expect(index.available).toBe(true);
    if (!index.available) return;
    expect(
      Value.Check(chargeSentencingIndexSchema, {
        ...index,
        summary: { ...index.summary, sampleSize: 60 },
      }),
    ).toBe(false);
    expect(
      Value.Check(chargeSentencingIndexSchema, {
        ...index,
        grades: [{ grade: 'F3', convictionCount: 1, percentageOfConvictions: 1, count: 1 }],
      }),
    ).toBe(false);
  });
});

describe('judgeSentencingIndexSchema (ruling 2: no grade mix)', () => {
  it('accepts the present arm without grades and the absent arm', () => {
    expect(Value.Check(judgeSentencingIndexSchema, validJudgeSentencingIndex())).toBe(true);
    expect(Value.Check(judgeSentencingIndexSchema, { available: false })).toBe(true);
  });

  it('rejects a judge present arm carrying a grades key', () => {
    const index = validJudgeSentencingIndex();
    expect(index.available).toBe(true);
    if (!index.available) return;
    expect(
      Value.Check(judgeSentencingIndexSchema, {
        ...index,
        grades: [{ grade: 'F3', convictionCount: 1, percentageOfConvictions: 1 }],
      }),
    ).toBe(false);
  });
});

describe('sentencingIndex placement on the result payloads (task 35.2, additive)', () => {
  it('is required on both success arms', () => {
    const charge: Record<string, unknown> = { ...validChargeOnlyResult() };
    delete charge.sentencingIndex;
    expect(Value.Check(chargeOnlyResultResponseSchema, charge)).toBe(false);

    const judge: Record<string, unknown> = { ...validJudgeSpecificResultSuccess() };
    delete judge.sentencingIndex;
    expect(Value.Check(judgeSpecificResultResponseSchema, judge)).toBe(false);
  });

  it('accepts the absent arm on both success payloads (the pre-population degraded state)', () => {
    expect(
      Value.Check(chargeOnlyResultResponseSchema, {
        ...validChargeOnlyResult(),
        sentencingIndex: { available: false },
      }),
    ).toBe(true);
    expect(
      Value.Check(judgeSpecificResultResponseSchema, {
        ...validJudgeSpecificResultSuccess(),
        sentencingIndex: { available: false },
      }),
    ).toBe(true);
  });

  it('rejects the charge-shaped present arm (with grades) on the judge payload', () => {
    expect(
      Value.Check(judgeSpecificResultResponseSchema, {
        ...validJudgeSpecificResultSuccess(),
        sentencingIndex: validChargeSentencingIndex(),
      }),
    ).toBe(false);
  });
});
