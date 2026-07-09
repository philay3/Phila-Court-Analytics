import { Value } from '@sinclair/typebox/value';
import { describe, expect, it } from 'vitest';

import { validMethodologyResponse } from '../test-support/fixtures.js';
import {
  METHODOLOGY_SECTION_KEYS,
  methodologyResponseSchema,
  methodologySectionSchema,
  methodologySectionsSchema,
} from './methodology.js';

function validSection() {
  return { heading: 'A heading', body: 'Body copy.' };
}

describe('methodologySectionSchema', () => {
  it('accepts a well-formed section', () => {
    expect(Value.Check(methodologySectionSchema, validSection())).toBe(true);
  });

  it.each(['heading', 'body'] as const)('rejects a section missing %s', (field) => {
    const section: Record<string, unknown> = validSection();
    delete section[field];
    expect(Value.Check(methodologySectionSchema, section)).toBe(false);
  });

  it.each(['heading', 'body'] as const)('rejects an empty %s', (field) => {
    expect(Value.Check(methodologySectionSchema, { ...validSection(), [field]: '' })).toBe(false);
  });

  it('rejects unknown section properties', () => {
    expect(Value.Check(methodologySectionSchema, { ...validSection(), extra: 'x' })).toBe(false);
  });
});

describe('methodologyResponseSchema', () => {
  it('accepts a well-formed response', () => {
    expect(Value.Check(methodologyResponseSchema, validMethodologyResponse())).toBe(true);
  });

  it('declares exactly the ten exported section keys, in order', () => {
    expect(Object.keys(methodologySectionsSchema.properties)).toEqual([
      ...METHODOLOGY_SECTION_KEYS,
    ]);
    expect(METHODOLOGY_SECTION_KEYS).toHaveLength(10);
  });

  it.each(METHODOLOGY_SECTION_KEYS)('rejects a response missing the %s section', (key) => {
    const response = validMethodologyResponse();
    delete (response.sections as Record<string, unknown>)[key];
    expect(Value.Check(methodologyResponseSchema, response)).toBe(false);
  });

  it('rejects an unknown section key', () => {
    const response = validMethodologyResponse();
    (response.sections as Record<string, unknown>).internalNotes = validSection();
    expect(Value.Check(methodologyResponseSchema, response)).toBe(false);
  });

  it('rejects a response missing sections', () => {
    expect(Value.Check(methodologyResponseSchema, {})).toBe(false);
  });

  it('rejects unknown top-level properties', () => {
    expect(
      Value.Check(methodologyResponseSchema, { ...validMethodologyResponse(), extra: 1 }),
    ).toBe(false);
  });
});
