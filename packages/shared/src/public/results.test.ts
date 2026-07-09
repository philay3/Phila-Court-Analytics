import { Value } from '@sinclair/typebox/value';
import { describe, expect, it } from 'vitest';

import { validJudgeSpecificResult } from '../test-support/fixtures.js';
import { judgeSpecificResultSchema } from './results.js';

// The charge-only result schema (task 8.1 shape) is tested in
// charge-result.test.ts.

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
