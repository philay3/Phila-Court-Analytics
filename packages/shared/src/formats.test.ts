import { FormatRegistry, Type } from '@sinclair/typebox';
import { Value } from '@sinclair/typebox/value';
import { describe, expect, it } from 'vitest';

import { registerFormats } from './formats.js';
import { chargeOnlyResultResponseSchema } from './public/charge-result.js';
import { dateRangeSchema } from './public/common.js';
import { validChargeOnlyResult } from './test-support/fixtures.js';

// The vitest setup file already called registerFormats() once before this file runs.

describe('registerFormats', () => {
  it('registers the three public formats', () => {
    for (const format of ['date', 'date-time', 'uuid']) {
      expect(FormatRegistry.Has(format)).toBe(true);
    }
  });

  it('is idempotent: a second call does not throw and does not replace checkers', () => {
    const before = {
      date: FormatRegistry.Get('date'),
      'date-time': FormatRegistry.Get('date-time'),
      uuid: FormatRegistry.Get('uuid'),
    };
    expect(() => registerFormats()).not.toThrow();
    expect(FormatRegistry.Get('date')).toBe(before.date);
    expect(FormatRegistry.Get('date-time')).toBe(before['date-time']);
    expect(FormatRegistry.Get('uuid')).toBe(before.uuid);
    // Behavior unchanged after the second call.
    expect(Value.Check(Type.String({ format: 'date' }), '2026-01-15')).toBe(true);
    expect(Value.Check(Type.String({ format: 'date' }), 'not-a-date')).toBe(false);
  });

  // Why registration is load-bearing: TypeBox 0.34 fails CLOSED on formats it has no
  // checker for — an unregistered format rejects every value, valid or not. (Older
  // TypeBox versions instead passed them silently — the task 3.2 finding; both
  // behaviors mean format-carrying schemas need registerFormats() to work.)
  it('unregistered formats reject everything (fail closed)', () => {
    expect(FormatRegistry.Has('never-registered-format')).toBe(false);
    expect(Value.Check(Type.String({ format: 'never-registered-format' }), 'anything')).toBe(false);
  });
});

describe('date format (via the real dateRangeSchema)', () => {
  it('accepts calendar-valid dates', () => {
    expect(Value.Check(dateRangeSchema, { start: '2025-01-01', end: '2026-06-30' })).toBe(true);
  });

  it('rejects malformed dates', () => {
    expect(Value.Check(dateRangeSchema, { start: 'not-a-date', end: '2026-06-30' })).toBe(false);
    expect(Value.Check(dateRangeSchema, { start: '2025-1-1', end: '2026-06-30' })).toBe(false);
  });

  it('rejects calendar-invalid dates (matching ajv-formats "full" semantics)', () => {
    expect(Value.Check(dateRangeSchema, { start: '2026-02-31', end: '2026-06-30' })).toBe(false);
    expect(Value.Check(dateRangeSchema, { start: '2026-13-01', end: '2026-06-30' })).toBe(false);
    expect(Value.Check(dateRangeSchema, { start: '2026-00-10', end: '2026-06-30' })).toBe(false);
    expect(Value.Check(dateRangeSchema, { start: '2026-04-31', end: '2026-06-30' })).toBe(false);
  });

  it('handles leap years', () => {
    expect(Value.Check(dateRangeSchema, { start: '2024-02-29', end: '2026-06-30' })).toBe(true);
    expect(Value.Check(dateRangeSchema, { start: '2023-02-29', end: '2026-06-30' })).toBe(false);
    expect(Value.Check(dateRangeSchema, { start: '2000-02-29', end: '2026-06-30' })).toBe(true);
    expect(Value.Check(dateRangeSchema, { start: '1900-02-29', end: '2026-06-30' })).toBe(false);
  });
});

describe('date-time format (via the real chargeOnlyResultResponseSchema)', () => {
  it('accepts the valid fixture and RFC 3339 variants', () => {
    expect(Value.Check(chargeOnlyResultResponseSchema, validChargeOnlyResult())).toBe(true);
    const withOffset = {
      ...validChargeOnlyResult(),
      lastRefreshed: '2026-07-01T08:30:00.250-04:00',
    };
    expect(Value.Check(chargeOnlyResultResponseSchema, withOffset)).toBe(true);
  });

  it('rejects malformed date-times', () => {
    for (const lastRefreshed of [
      'not-a-timestamp',
      '2026-07-01',
      '2026-07-01T25:00:00Z',
      '2026-07-01T08:61:00Z',
      '2026-02-31T08:30:00Z',
      '2026-07-01T08:30:00',
    ]) {
      expect(
        Value.Check(chargeOnlyResultResponseSchema, { ...validChargeOnlyResult(), lastRefreshed }),
      ).toBe(false);
    }
  });
});

describe('uuid format', () => {
  const uuidSchema = Type.String({ format: 'uuid' });

  it('accepts canonical uuids', () => {
    expect(Value.Check(uuidSchema, 'b8eb27a6-6fa1-4d0c-816b-96be2e3428b6')).toBe(true);
    expect(Value.Check(uuidSchema, 'B8EB27A6-6FA1-4D0C-816B-96BE2E3428B6')).toBe(true);
  });

  it('rejects malformed uuids', () => {
    expect(Value.Check(uuidSchema, 'not-a-uuid')).toBe(false);
    expect(Value.Check(uuidSchema, 'b8eb27a66fa14d0c816b96be2e3428b6')).toBe(false);
    expect(Value.Check(uuidSchema, 'b8eb27a6-6fa1-4d0c-816b-96be2e3428b')).toBe(false);
    expect(Value.Check(uuidSchema, 'g8eb27a6-6fa1-4d0c-816b-96be2e3428b6')).toBe(false);
  });
});
