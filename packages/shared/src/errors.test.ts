import { Value } from '@sinclair/typebox/value';
import { describe, expect, it } from 'vitest';

import {
  PUBLIC_ERROR_CODES,
  PUBLIC_ERROR_CODE_STATUS,
  isPublicErrorCode,
  publicErrorCodeSchema,
  publicErrorResponseSchema,
} from './errors.js';

const EXPECTED_CODES = [
  'INVALID_REQUEST',
  'NOT_FOUND',
  'CHARGE_NOT_FOUND',
  'JUDGE_NOT_FOUND',
  'CHARGE_RESULT_UNAVAILABLE',
  'JUDGE_SPECIFIC_RESULT_UNAVAILABLE',
  'SENTENCING_RESULT_UNAVAILABLE',
  'RATE_LIMITED',
  'INTERNAL_ERROR',
] as const;

function validErrorResponse() {
  return {
    statusCode: 404,
    code: PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND,
    error: 'Not Found',
    message: 'Charge not found.',
    requestId: 'a-request-id',
  };
}

describe('PUBLIC_ERROR_CODES', () => {
  it('contains exactly the nine catalog codes, each equal to its own key', () => {
    expect(Object.keys(PUBLIC_ERROR_CODES).sort()).toEqual([...EXPECTED_CODES].sort());
    for (const [key, value] of Object.entries(PUBLIC_ERROR_CODES)) {
      expect(value).toBe(key);
    }
  });

  it('maps every code to its documented default status', () => {
    expect(PUBLIC_ERROR_CODE_STATUS).toEqual({
      INVALID_REQUEST: 400,
      NOT_FOUND: 404,
      CHARGE_NOT_FOUND: 404,
      JUDGE_NOT_FOUND: 404,
      CHARGE_RESULT_UNAVAILABLE: 404,
      JUDGE_SPECIFIC_RESULT_UNAVAILABLE: 404,
      SENTENCING_RESULT_UNAVAILABLE: 404,
      RATE_LIMITED: 429,
      INTERNAL_ERROR: 500,
    });
  });
});

describe('isPublicErrorCode', () => {
  it('accepts every catalog code', () => {
    for (const code of EXPECTED_CODES) {
      expect(isPublicErrorCode(code)).toBe(true);
    }
  });

  it('rejects non-catalog strings and non-strings', () => {
    expect(isPublicErrorCode('FST_ERR_VALIDATION')).toBe(false);
    expect(isPublicErrorCode('charge_not_found')).toBe(false);
    // Object.hasOwn guard: prototype members must not count as codes.
    expect(isPublicErrorCode('toString')).toBe(false);
    expect(isPublicErrorCode(undefined)).toBe(false);
    expect(isPublicErrorCode(null)).toBe(false);
    expect(isPublicErrorCode(404)).toBe(false);
  });
});

describe('publicErrorCodeSchema', () => {
  it('mirrors the catalog exactly', () => {
    const schemaCodes = publicErrorCodeSchema.anyOf.map((literal) => literal.const);
    expect(schemaCodes).toEqual(Object.values(PUBLIC_ERROR_CODES));
  });
});

describe('publicErrorResponseSchema', () => {
  it('accepts a valid error response', () => {
    expect(Value.Check(publicErrorResponseSchema, validErrorResponse())).toBe(true);
  });

  it('accepts every catalog code in the code field', () => {
    for (const code of EXPECTED_CODES) {
      expect(Value.Check(publicErrorResponseSchema, { ...validErrorResponse(), code })).toBe(true);
    }
  });

  it('rejects unknown codes', () => {
    expect(
      Value.Check(publicErrorResponseSchema, { ...validErrorResponse(), code: 'NOT_A_CODE' }),
    ).toBe(false);
  });

  it('requires all five fields', () => {
    for (const field of ['statusCode', 'code', 'error', 'message', 'requestId'] as const) {
      const response: Record<string, unknown> = { ...validErrorResponse() };
      delete response[field];
      expect(Value.Check(publicErrorResponseSchema, response)).toBe(false);
    }
  });

  it('rejects unknown extra properties', () => {
    expect(Value.Check(publicErrorResponseSchema, { ...validErrorResponse(), stack: 'x' })).toBe(
      false,
    );
  });

  it('rejects non-error status codes', () => {
    expect(
      Value.Check(publicErrorResponseSchema, { ...validErrorResponse(), statusCode: 200 }),
    ).toBe(false);
    expect(
      Value.Check(publicErrorResponseSchema, { ...validErrorResponse(), statusCode: 600 }),
    ).toBe(false);
  });
});
