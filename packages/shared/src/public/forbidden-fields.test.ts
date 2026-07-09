import { describe, expect, it } from 'vitest';

import { FORBIDDEN_FIELD_STEMS, FORBIDDEN_VALUE_PATTERNS } from './forbidden-fields.js';

// An independent copy of the pinned stem list (task 10.1) so an accidental
// edit — dropped stem, typo, un-normalized entry — fails here.
const EXPECTED_STEMS = [
  'defendant',
  'docket',
  'sourcedocument',
  'sourceid',
  'sourceurl',
  'storagekey',
  'rawtext',
  'extractedtext',
  'parseddocket',
  'parsedcharge',
  'factid',
  'reviewstatus',
  'admincorrection',
  'confidence',
] as const;

describe('FORBIDDEN_FIELD_STEMS', () => {
  it('contains exactly the fourteen pinned stems', () => {
    expect([...FORBIDDEN_FIELD_STEMS].sort()).toEqual([...EXPECTED_STEMS].sort());
  });

  it('holds only normalized stems (lowercase, no underscores or hyphens)', () => {
    for (const stem of FORBIDDEN_FIELD_STEMS) {
      expect(stem).toBe(stem.toLowerCase());
      expect(stem).not.toMatch(/[_-]/);
    }
  });
});

describe('FORBIDDEN_VALUE_PATTERNS', () => {
  const docketNumbers = [
    'CP-51-CR-0001234-2025',
    'MC-51-CR-0001234-2024',
    'cp-51-cr-0001234-2025', // case-insensitive
    'CP-51-MD-1234567-2020', // other court types
    'MC-51-SU-1234-2023', // non-zero-padded sequence
  ];

  const legitimateStrings = [
    'Retail theft',
    'Percentages are rounded to whole numbers.',
    '2024-01-01', // ISO dates must not match
    'CP-51', // bare prefix without the full docket shape
    'MJ-51201-CR-0001234-2025', // magisterial format is out of scope by design
  ];

  it('matches Philadelphia UJS docket numbers in all rendered variants', () => {
    for (const docket of docketNumbers) {
      expect(
        FORBIDDEN_VALUE_PATTERNS.some((pattern) => pattern.test(docket)),
        `expected a pattern to match: ${docket}`,
      ).toBe(true);
    }
  });

  it('matches docket numbers embedded in longer strings', () => {
    expect(
      FORBIDDEN_VALUE_PATTERNS.some((pattern) => pattern.test('see CP-51-CR-0001234-2025 filed')),
    ).toBe(true);
  });

  it('does not match legitimate public content', () => {
    for (const value of legitimateStrings) {
      for (const pattern of FORBIDDEN_VALUE_PATTERNS) {
        expect(pattern.test(value), `pattern ${pattern} must not match: ${value}`).toBe(false);
      }
    }
  });

  it('contains no global-flag patterns (stateful lastIndex would skip matches)', () => {
    for (const pattern of FORBIDDEN_VALUE_PATTERNS) {
      expect(pattern.global, `pattern ${pattern} must not use the g flag`).toBe(false);
    }
  });
});
