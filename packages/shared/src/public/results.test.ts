import { Value } from '@sinclair/typebox/value';
import { describe, expect, it } from 'vitest';

import { validChargeOnlyResult, validJudgeSpecificResult } from '../test-support/fixtures.js';
import { registerStringFormats } from '../test-support/formats.js';
import { chargeOnlyResultSchema, judgeSpecificResultSchema } from './results.js';

registerStringFormats();

describe('chargeOnlyResultSchema', () => {
  it('accepts a valid result with sentencing', () => {
    expect(Value.Check(chargeOnlyResultSchema, validChargeOnlyResult())).toBe(true);
  });

  it('accepts a valid result without sentencing (optional)', () => {
    const withoutSentencing: Record<string, unknown> = { ...validChargeOnlyResult() };
    delete withoutSentencing.sentencing;
    expect(Value.Check(chargeOnlyResultSchema, withoutSentencing)).toBe(true);
  });

  it('requires outcome distribution, taxonomy version, and lastRefreshed', () => {
    for (const field of ['outcomes', 'taxonomyVersion', 'lastRefreshed'] as const) {
      const result: Record<string, unknown> = { ...validChargeOnlyResult() };
      delete result[field];
      expect(Value.Check(chargeOnlyResultSchema, result)).toBe(false);
    }
  });

  it('rejects a non-semver taxonomy version and a non-ISO lastRefreshed', () => {
    expect(
      Value.Check(chargeOnlyResultSchema, { ...validChargeOnlyResult(), taxonomyVersion: 'v1' }),
    ).toBe(false);
    expect(
      Value.Check(chargeOnlyResultSchema, { ...validChargeOnlyResult(), lastRefreshed: 'today' }),
    ).toBe(false);
  });

  it('rejects unknown extra properties', () => {
    expect(
      Value.Check(chargeOnlyResultSchema, { ...validChargeOnlyResult(), docketNumber: 'CP-0000' }),
    ).toBe(false);
  });
});

describe('judgeSpecificResultSchema', () => {
  it('accepts a valid result with sentencing distributions', () => {
    expect(Value.Check(judgeSpecificResultSchema, validJudgeSpecificResult())).toBe(true);
  });

  it('accepts a valid result without the optional sentencing distributions', () => {
    const withoutSentencing: Record<string, unknown> = { ...validJudgeSpecificResult() };
    delete withoutSentencing.judgeSentencing;
    delete withoutSentencing.baselineSentencing;
    expect(Value.Check(judgeSpecificResultSchema, withoutSentencing)).toBe(true);
  });

  it('requires both judge and baseline outcome distributions', () => {
    for (const field of ['judgeOutcomes', 'baselineOutcomes'] as const) {
      const result: Record<string, unknown> = { ...validJudgeSpecificResult() };
      delete result[field];
      expect(Value.Check(judgeSpecificResultSchema, result)).toBe(false);
    }
  });

  it('rejects unknown extra properties', () => {
    expect(
      Value.Check(judgeSpecificResultSchema, { ...validJudgeSpecificResult(), defendantName: 'x' }),
    ).toBe(false);
  });
});
