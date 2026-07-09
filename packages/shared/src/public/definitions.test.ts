import { Value } from '@sinclair/typebox/value';
import { describe, expect, it } from 'vitest';

import { definitionEntrySchema, definitionsResponseSchema } from './definitions.js';

function validEntry() {
  return {
    code: 'dismissed',
    displayName: 'Dismissed',
    definition: 'The court dismissed the charge.',
    sortOrder: 1,
  };
}

function validResponse() {
  return {
    taxonomyVersion: '1.0.0',
    outcomes: [validEntry()],
    sentencing: [validEntry()],
  };
}

describe('definitionEntrySchema', () => {
  it('accepts a well-formed entry', () => {
    expect(Value.Check(definitionEntrySchema, validEntry())).toBe(true);
  });

  it('rejects the internal public flag (additionalProperties)', () => {
    expect(Value.Check(definitionEntrySchema, { ...validEntry(), public: true })).toBe(false);
  });

  it.each(['code', 'displayName', 'definition', 'sortOrder'] as const)(
    'rejects an entry missing %s',
    (field) => {
      const entry: Record<string, unknown> = validEntry();
      delete entry[field];
      expect(Value.Check(definitionEntrySchema, entry)).toBe(false);
    },
  );

  it('rejects a non-integer sortOrder', () => {
    expect(Value.Check(definitionEntrySchema, { ...validEntry(), sortOrder: 1.5 })).toBe(false);
    expect(Value.Check(definitionEntrySchema, { ...validEntry(), sortOrder: '1' })).toBe(false);
  });
});

describe('definitionsResponseSchema', () => {
  it('accepts a well-formed response', () => {
    expect(Value.Check(definitionsResponseSchema, validResponse())).toBe(true);
  });

  it.each(['taxonomyVersion', 'outcomes', 'sentencing'] as const)(
    'rejects a response missing %s',
    (field) => {
      const response: Record<string, unknown> = validResponse();
      delete response[field];
      expect(Value.Check(definitionsResponseSchema, response)).toBe(false);
    },
  );

  it('rejects unknown top-level properties', () => {
    expect(Value.Check(definitionsResponseSchema, { ...validResponse(), extra: 1 })).toBe(false);
  });

  it('rejects a response whose entries carry the internal public flag', () => {
    const response = validResponse();
    response.outcomes = [{ ...validEntry(), public: false } as never];
    expect(Value.Check(definitionsResponseSchema, response)).toBe(false);
  });
});
