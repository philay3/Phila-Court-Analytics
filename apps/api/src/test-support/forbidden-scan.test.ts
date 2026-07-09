import { describe, expect, it } from 'vitest';
import { FORBIDDEN_FIELD_STEMS, FORBIDDEN_VALUE_PATTERNS } from '@pca/shared';
import { formatViolations, scanForForbidden } from './forbidden-scan.js';

// Checker self-tests (task 10.1, pinned decision 6): poisoned fixtures prove
// every stem and every value pattern is caught — through nesting, arrays, and
// key-casing variants — and a realistic clean payload proves no false
// positive. The checker itself is what makes the main suite trustworthy, so
// it gets the same adversarial treatment as the endpoints.

// One representative poisoned KEY per stem. Keys deliberately embed the stem
// inside a longer name (the check is CONTAINS on the normalized key, not
// equality), mixing casing/separator styles across entries.
const POISONED_KEY_BY_STEM: Record<string, string> = {
  defendant: 'defendantName',
  docket: 'docketNumber',
  sourcedocument: 'source_document_id',
  sourceid: 'sourceId',
  sourceurl: 'source-url',
  storagekey: 'storageKey',
  rawtext: 'raw_text',
  extractedtext: 'extractedText',
  parseddocket: 'parsed_docket_id',
  parsedcharge: 'parsedChargeId',
  factid: 'chargeOutcomeFactId',
  reviewstatus: 'review_status',
  admincorrection: 'adminCorrectionNote',
  confidence: 'parserConfidence',
};

// A realistic charge-only result payload (the 8.1 contract shape) — the
// clean fixture for the no-false-positive assertion.
const CLEAN_CHARGE_ONLY_RESULT = {
  charge: {
    id: '3f0a2f9e-7f52-4e6b-8a53-0d5f4bfb0f6c',
    slug: 'retail-theft',
    displayName: 'Retail theft',
    statuteCode: '18 § 3929',
    grade: 'M1',
  },
  resultType: 'charge_only',
  geography: 'philadelphia',
  dateRange: { start: '2020-01-01', end: '2024-12-31' },
  lastRefreshed: '2025-01-15T00:00:00.000Z',
  taxonomyVersion: '1.0.0',
  aggregateRunId: '9d3e7b1a-2c4f-4a8b-9e0d-6f5a3c2b1d0e',
  outcomes: {
    sampleSize: 1200,
    thinData: false,
    rows: [
      { categoryCode: 'dismissed', displayName: 'Dismissed', count: 264, percentage: 22 },
      { categoryCode: 'guilty_plea', displayName: 'Guilty plea', count: 540, percentage: 45 },
    ],
  },
  sentencing: {
    available: true,
    sampleSize: 700,
    thinData: false,
    rows: [{ categoryCode: 'probation', displayName: 'Probation', count: 245, percentage: 35 }],
  },
};

describe('scanForForbidden — key checks', () => {
  it('covers every shared stem with a poisoned-key fixture', () => {
    expect(Object.keys(POISONED_KEY_BY_STEM).sort()).toEqual([...FORBIDDEN_FIELD_STEMS].sort());
  });

  for (const [stem, poisonedKey] of Object.entries(POISONED_KEY_BY_STEM)) {
    it(`catches the ${stem} stem via key ${JSON.stringify(poisonedKey)}`, () => {
      // toContainEqual, not toEqual: overlapping stems legitimately produce
      // extra violations (e.g. parsed_docket_id matches parseddocket AND docket).
      expect(scanForForbidden({ [poisonedKey]: 'x' })).toContainEqual({
        jsonPath: `$.${poisonedKey}`,
        kind: 'key',
        offender: poisonedKey,
        matched: stem,
      });
    });
  }

  it('catches both camelCase and snake_case variants of the same stem', () => {
    for (const key of ['docketNumber', 'docket_number']) {
      const violations = scanForForbidden({ [key]: 'x' });
      expect(violations).toHaveLength(1);
      expect(violations[0]).toMatchObject({ kind: 'key', offender: key, matched: 'docket' });
    }
  });

  it('catches a poisoned key nested three levels deep inside an array', () => {
    const violations = scanForForbidden({
      outcomes: { rows: [{ categoryCode: 'dismissed' }, { nested: { defendantName: 'leak' } }] },
    });
    expect(violations).toEqual([
      {
        jsonPath: '$.outcomes.rows[1].nested.defendantName',
        kind: 'key',
        offender: 'defendantName',
        matched: 'defendant',
      },
    ]);
  });
});

describe('scanForForbidden — value checks', () => {
  it('covers every shared value pattern with a poisoned-value fixture', () => {
    // One poisoned string per pattern, index-aligned. Extend when patterns grow.
    const poisonedValueByPattern = ['Case CP-51-CR-0001234-2025 continued'];
    expect(poisonedValueByPattern).toHaveLength(FORBIDDEN_VALUE_PATTERNS.length);

    poisonedValueByPattern.forEach((poisoned, index) => {
      const violations = scanForForbidden({ note: poisoned });
      expect(violations).toEqual([
        {
          jsonPath: '$.note',
          kind: 'value',
          offender: poisoned,
          matched: `${FORBIDDEN_VALUE_PATTERNS[index]}`,
        },
      ]);
    });
  });

  it('catches a docket-shaped value inside a nested array element', () => {
    const violations = scanForForbidden({
      results: [{ ok: 'fine' }, { rows: ['clean', 'MC-51-CR-0007654-2024'] }],
    });
    expect(violations).toEqual([
      {
        jsonPath: '$.results[1].rows[1]',
        kind: 'value',
        offender: 'MC-51-CR-0007654-2024',
        matched: `${FORBIDDEN_VALUE_PATTERNS[0]}`,
      },
    ]);
  });
});

describe('scanForForbidden — clean fixture and reporting', () => {
  it('reports zero violations on a realistic charge-only result payload', () => {
    expect(scanForForbidden(CLEAN_CHARGE_ONLY_RESULT)).toEqual([]);
  });

  it('handles non-object bodies without violations', () => {
    expect(scanForForbidden(null)).toEqual([]);
    expect(scanForForbidden(42)).toEqual([]);
    expect(scanForForbidden('Retail theft')).toEqual([]);
  });

  it('formats violations with path, kind, offender, and matched rule', () => {
    const formatted = formatViolations(scanForForbidden({ docketNumber: 'x' }));
    expect(formatted).toContain('$.docketNumber');
    expect(formatted).toContain('key');
    expect(formatted).toContain('docket');
  });
});
