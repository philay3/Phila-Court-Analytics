import { Value } from '@sinclair/typebox/value';
import { describe, expect, it } from 'vitest';

import { validChargeSearchResponse, validJudgeSearchResponse } from '../test-support/fixtures.js';
import {
  chargeSearchQuerySchema,
  chargeSearchResponseSchema,
  chargeSearchResultSchema,
  judgeSearchQuerySchema,
  judgeSearchResponseSchema,
  judgeSearchResultSchema,
} from './search.js';

describe('chargeSearchQuerySchema', () => {
  it('accepts q alone and q with an in-range limit', () => {
    expect(Value.Check(chargeSearchQuerySchema, { q: 'theft' })).toBe(true);
    expect(Value.Check(chargeSearchQuerySchema, { q: 'theft', limit: 1 })).toBe(true);
    expect(Value.Check(chargeSearchQuerySchema, { q: 'theft', limit: 25 })).toBe(true);
  });

  it('rejects a missing q', () => {
    expect(Value.Check(chargeSearchQuerySchema, {})).toBe(false);
    expect(Value.Check(chargeSearchQuerySchema, { limit: 10 })).toBe(false);
  });

  it('rejects out-of-range and non-integer limits', () => {
    expect(Value.Check(chargeSearchQuerySchema, { q: 'theft', limit: 0 })).toBe(false);
    expect(Value.Check(chargeSearchQuerySchema, { q: 'theft', limit: 26 })).toBe(false);
    expect(Value.Check(chargeSearchQuerySchema, { q: 'theft', limit: 1.5 })).toBe(false);
  });

  it('rejects unknown extra properties', () => {
    expect(Value.Check(chargeSearchQuerySchema, { q: 'theft', offset: 5 })).toBe(false);
  });
});

describe('chargeSearchResponseSchema', () => {
  it('accepts a valid response, including an empty result list', () => {
    expect(Value.Check(chargeSearchResponseSchema, validChargeSearchResponse())).toBe(true);
    expect(Value.Check(chargeSearchResponseSchema, { results: [] })).toBe(true);
  });

  it('accepts a result with every optional omitted', () => {
    const minimal = validChargeSearchResponse().results[1];
    expect(minimal).toBeDefined();
    expect(Value.Check(chargeSearchResultSchema, minimal)).toBe(true);
  });

  it('rejects a non-uuid id', () => {
    const result = { ...validChargeSearchResponse().results[0], id: 'charge-1' };
    expect(Value.Check(chargeSearchResultSchema, result)).toBe(false);
  });

  it('rejects unknown extra properties on the envelope', () => {
    expect(
      Value.Check(chargeSearchResponseSchema, { ...validChargeSearchResponse(), total: 1 }),
    ).toBe(false);
  });

  it('rejects unknown extra properties on a result', () => {
    const response = validChargeSearchResponse();
    const result = { ...response.results[0], docketNumber: 'CP-0000' };
    expect(Value.Check(chargeSearchResultSchema, result)).toBe(false);
    expect(Value.Check(chargeSearchResponseSchema, { results: [result] })).toBe(false);
  });

  it('rejects a result missing a required field', () => {
    const withoutSlug: Record<string, unknown> = { ...validChargeSearchResponse().results[0] };
    delete withoutSlug['slug'];
    expect(Value.Check(chargeSearchResultSchema, withoutSlug)).toBe(false);
  });
});

describe('judgeSearchQuerySchema', () => {
  it('accepts q alone and q with an in-range limit', () => {
    expect(Value.Check(judgeSearchQuerySchema, { q: 'placeholder' })).toBe(true);
    expect(Value.Check(judgeSearchQuerySchema, { q: 'placeholder', limit: 1 })).toBe(true);
    expect(Value.Check(judgeSearchQuerySchema, { q: 'placeholder', limit: 25 })).toBe(true);
  });

  it('rejects a missing q', () => {
    expect(Value.Check(judgeSearchQuerySchema, {})).toBe(false);
    expect(Value.Check(judgeSearchQuerySchema, { limit: 10 })).toBe(false);
  });

  it('rejects out-of-range and non-integer limits', () => {
    expect(Value.Check(judgeSearchQuerySchema, { q: 'placeholder', limit: 0 })).toBe(false);
    expect(Value.Check(judgeSearchQuerySchema, { q: 'placeholder', limit: 26 })).toBe(false);
    expect(Value.Check(judgeSearchQuerySchema, { q: 'placeholder', limit: 1.5 })).toBe(false);
  });

  it('rejects unknown extra properties', () => {
    expect(Value.Check(judgeSearchQuerySchema, { q: 'placeholder', offset: 5 })).toBe(false);
  });
});

describe('judgeSearchResponseSchema', () => {
  it('accepts a valid response, including an empty result list', () => {
    expect(Value.Check(judgeSearchResponseSchema, validJudgeSearchResponse())).toBe(true);
    expect(Value.Check(judgeSearchResponseSchema, { results: [] })).toBe(true);
  });

  it('accepts a result with matchedAlias omitted', () => {
    const minimal = validJudgeSearchResponse().results[1];
    expect(minimal).toBeDefined();
    expect(Value.Check(judgeSearchResultSchema, minimal)).toBe(true);
  });

  it('rejects a non-uuid id', () => {
    const result = { ...validJudgeSearchResponse().results[0], id: 'judge-1' };
    expect(Value.Check(judgeSearchResultSchema, result)).toBe(false);
  });

  it('rejects unknown extra properties on the envelope', () => {
    expect(
      Value.Check(judgeSearchResponseSchema, { ...validJudgeSearchResponse(), total: 1 }),
    ).toBe(false);
  });

  it('rejects unknown extra properties on a result', () => {
    const response = validJudgeSearchResponse();
    const result = { ...response.results[0], caseCount: 7 };
    expect(Value.Check(judgeSearchResultSchema, result)).toBe(false);
    expect(Value.Check(judgeSearchResponseSchema, { results: [result] })).toBe(false);
  });

  it('rejects a result missing a required field', () => {
    const withoutSlug: Record<string, unknown> = { ...validJudgeSearchResponse().results[0] };
    delete withoutSlug['slug'];
    expect(Value.Check(judgeSearchResultSchema, withoutSlug)).toBe(false);
  });
});
