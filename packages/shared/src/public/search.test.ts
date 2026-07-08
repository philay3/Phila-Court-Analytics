import { Value } from '@sinclair/typebox/value';
import { describe, expect, it } from 'vitest';

import { validChargeSearchResponse, validJudgeSearchResponse } from '../test-support/fixtures.js';
import {
  chargeSearchResponseSchema,
  chargeSuggestionSchema,
  judgeSearchResponseSchema,
  judgeSuggestionSchema,
} from './search.js';

describe('chargeSearchResponseSchema', () => {
  it('accepts a valid response, including an empty result list', () => {
    expect(Value.Check(chargeSearchResponseSchema, validChargeSearchResponse())).toBe(true);
    expect(Value.Check(chargeSearchResponseSchema, { results: [] })).toBe(true);
  });

  it('rejects unknown extra properties on the envelope', () => {
    expect(
      Value.Check(chargeSearchResponseSchema, { ...validChargeSearchResponse(), total: 1 }),
    ).toBe(false);
  });

  it('rejects unknown extra properties on a suggestion', () => {
    const response = validChargeSearchResponse();
    const suggestion = { ...response.results[0], docketNumber: 'CP-0000' };
    expect(Value.Check(chargeSuggestionSchema, suggestion)).toBe(false);
    expect(Value.Check(chargeSearchResponseSchema, { results: [suggestion] })).toBe(false);
  });

  it('rejects a suggestion missing a required field', () => {
    expect(
      Value.Check(chargeSuggestionSchema, { chargeId: 'charge-1', displayName: 'Example charge' }),
    ).toBe(false);
  });
});

describe('judgeSearchResponseSchema', () => {
  it('accepts a valid response', () => {
    expect(Value.Check(judgeSearchResponseSchema, validJudgeSearchResponse())).toBe(true);
  });

  it('rejects unknown extra properties on the envelope', () => {
    expect(
      Value.Check(judgeSearchResponseSchema, { ...validJudgeSearchResponse(), total: 1 }),
    ).toBe(false);
  });

  it('rejects unknown extra properties on a suggestion', () => {
    const response = validJudgeSearchResponse();
    const suggestion = { ...response.results[0], internalId: 7 };
    expect(Value.Check(judgeSuggestionSchema, suggestion)).toBe(false);
    expect(Value.Check(judgeSearchResponseSchema, { results: [suggestion] })).toBe(false);
  });
});
