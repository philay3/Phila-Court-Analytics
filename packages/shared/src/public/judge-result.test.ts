import { Value } from '@sinclair/typebox/value';
import { describe, expect, it } from 'vitest';

import {
  validJudgeSpecificResultSuccess,
  validJudgeSpecificResultUnavailable,
} from '../test-support/fixtures.js';
import {
  JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
  judgeSpecificResultResponseSchema,
  judgeSpecificResultSuccessSchema,
  judgeSpecificResultUnavailableSchema,
} from './judge-result.js';

describe('judgeSpecificResultResponseSchema (top-level union)', () => {
  it('accepts both arms', () => {
    expect(
      Value.Check(judgeSpecificResultResponseSchema, validJudgeSpecificResultSuccess()),
    ).toBe(true);
    expect(
      Value.Check(judgeSpecificResultResponseSchema, validJudgeSpecificResultUnavailable()),
    ).toBe(true);
  });

  it('keeps the arms structurally disjoint via resultType', () => {
    // A success body relabeled as unavailable (and vice versa) matches
    // neither arm: the literals disagree and the property sets differ.
    expect(
      Value.Check(judgeSpecificResultResponseSchema, {
        ...validJudgeSpecificResultSuccess(),
        resultType: 'judge_specific_unavailable',
      }),
    ).toBe(false);
    expect(
      Value.Check(judgeSpecificResultResponseSchema, {
        ...validJudgeSpecificResultUnavailable(),
        resultType: 'judge_specific',
      }),
    ).toBe(false);
  });
});

describe('judgeSpecificResultSuccessSchema', () => {
  it('requires every top-level field, including the baseline', () => {
    for (const field of [
      'resultType',
      'charge',
      'judge',
      'geography',
      'dateRange',
      'lastRefreshed',
      'taxonomyVersion',
      'aggregateRunId',
      'judgeSpecific',
      'baseline',
      'links',
    ] as const) {
      const result: Record<string, unknown> = { ...validJudgeSpecificResultSuccess() };
      delete result[field];
      expect(Value.Check(judgeSpecificResultSuccessSchema, result), `missing ${field}`).toBe(
        false,
      );
    }
  });

  it('requires outcomes and sentencing inside both scopes', () => {
    for (const scope of ['judgeSpecific', 'baseline'] as const) {
      for (const block of ['outcomes', 'sentencing'] as const) {
        const result = validJudgeSpecificResultSuccess();
        const scoped: Record<string, unknown> = { ...result[scope] };
        delete scoped[block];
        expect(
          Value.Check(judgeSpecificResultSuccessSchema, { ...result, [scope]: scoped }),
          `missing ${scope}.${block}`,
        ).toBe(false);
      }
    }
  });

  it('accepts independent sentencing unions per scope', () => {
    const result = validJudgeSpecificResultSuccess();
    result.judgeSpecific = {
      outcomes: result.judgeSpecific.outcomes,
      sentencing: {
        available: false,
        message: 'Historical sentencing data is not available for this charge yet.',
      },
    };
    expect(Value.Check(judgeSpecificResultSuccessSchema, result)).toBe(true);
  });

  it('rejects extra properties at the root, judge, and scope levels', () => {
    expect(
      Value.Check(judgeSpecificResultSuccessSchema, {
        ...validJudgeSpecificResultSuccess(),
        docketNumber: 'CP-0000',
      }),
    ).toBe(false);

    const withJudgeExtra = validJudgeSpecificResultSuccess() as Record<string, unknown>;
    withJudgeExtra.judge = { ...validJudgeSpecificResultSuccess().judge, courtroom: '1104' };
    expect(Value.Check(judgeSpecificResultSuccessSchema, withJudgeExtra)).toBe(false);

    const withScopeExtra = validJudgeSpecificResultSuccess() as Record<string, unknown>;
    withScopeExtra.judgeSpecific = {
      ...validJudgeSpecificResultSuccess().judgeSpecific,
      caseCount: 3,
    };
    expect(Value.Check(judgeSpecificResultSuccessSchema, withScopeExtra)).toBe(false);
  });

  it('pins resultType and geography to their literals', () => {
    expect(
      Value.Check(judgeSpecificResultSuccessSchema, {
        ...validJudgeSpecificResultSuccess(),
        resultType: 'charge_only',
      }),
    ).toBe(false);
    expect(
      Value.Check(judgeSpecificResultSuccessSchema, {
        ...validJudgeSpecificResultSuccess(),
        geography: 'pennsylvania',
      }),
    ).toBe(false);
  });
});

describe('judgeSpecificResultUnavailableSchema', () => {
  it('pins code and message to the exported literals', () => {
    expect(
      Value.Check(judgeSpecificResultUnavailableSchema, {
        ...validJudgeSpecificResultUnavailable(),
        code: 'CHARGE_RESULT_UNAVAILABLE',
      }),
    ).toBe(false);
    expect(
      Value.Check(judgeSpecificResultUnavailableSchema, {
        ...validJudgeSpecificResultUnavailable(),
        message: `${JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE} (low parser confidence)`,
      }),
    ).toBe(false);
  });

  it('requires charge, judge, and the fallback path', () => {
    for (const field of ['charge', 'judge', 'fallback'] as const) {
      const result: Record<string, unknown> = { ...validJudgeSpecificResultUnavailable() };
      delete result[field];
      expect(Value.Check(judgeSpecificResultUnavailableSchema, result), `missing ${field}`).toBe(
        false,
      );
    }
  });

  it('rejects distributions, sample sizes, or run metadata smuggled into the arm', () => {
    for (const extra of [
      { judgeSpecific: {} },
      { baseline: {} },
      { sampleSize: 9 },
      { aggregateRunId: '2f9c1e04-8d5b-4c33-9a67-0d1e2f3a4b5c' },
      { links: { methodology: '/methodology', definitions: '/definitions' } },
    ]) {
      expect(
        Value.Check(judgeSpecificResultUnavailableSchema, {
          ...validJudgeSpecificResultUnavailable(),
          ...extra,
        }),
        `extra: ${Object.keys(extra).join()}`,
      ).toBe(false);
    }
  });
});
