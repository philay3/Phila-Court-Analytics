import { Value } from '@sinclair/typebox/value';
import { describe, expect, it } from 'vitest';

import {
  validDataCoverageAvailable,
  validDataCoverageUnavailable,
} from '../test-support/fixtures.js';
import {
  DATA_COVERAGE_UNAVAILABLE_MESSAGE,
  dataCoverageCountsSchema,
  dataCoverageResponseSchema,
  dataCoverageSchema,
} from './data-coverage.js';

type Mutable = Record<string, unknown>;

describe('dataCoverageCountsSchema', () => {
  const validCounts = () => ({
    chargesWithOutcomeAggregates: 5,
    chargesWithSentencingAggregates: 3,
    judgeChargePairs: 3,
  });

  it('accepts well-formed counts', () => {
    expect(Value.Check(dataCoverageCountsSchema, validCounts())).toBe(true);
  });

  it.each([
    'chargesWithOutcomeAggregates',
    'chargesWithSentencingAggregates',
    'judgeChargePairs',
  ] as const)('rejects counts missing %s', (field) => {
    const counts: Mutable = validCounts();
    delete counts[field];
    expect(Value.Check(dataCoverageCountsSchema, counts)).toBe(false);
  });

  it('rejects negative and non-integer counts', () => {
    expect(Value.Check(dataCoverageCountsSchema, { ...validCounts(), judgeChargePairs: -1 })).toBe(
      false,
    );
    expect(Value.Check(dataCoverageCountsSchema, { ...validCounts(), judgeChargePairs: 1.5 })).toBe(
      false,
    );
  });

  it('rejects unknown count properties (no smuggled lists)', () => {
    expect(Value.Check(dataCoverageCountsSchema, { ...validCounts(), chargeNames: ['x'] })).toBe(
      false,
    );
  });
});

describe('dataCoverageSchema (tagged union)', () => {
  it('accepts both arms', () => {
    expect(Value.Check(dataCoverageSchema, validDataCoverageAvailable().coverage)).toBe(true);
    expect(Value.Check(dataCoverageSchema, validDataCoverageUnavailable().coverage)).toBe(true);
  });

  it('rejects an unavailable arm carrying run-derived fields', () => {
    const coverage = {
      ...validDataCoverageUnavailable().coverage,
      aggregateRunId: '2f9c1e04-8d5b-4c33-9a67-0d1e2f3a4b5c',
    };
    expect(Value.Check(dataCoverageSchema, coverage)).toBe(false);
  });

  it('rejects an available arm carrying the unavailable message', () => {
    const coverage = {
      ...validDataCoverageAvailable().coverage,
      message: DATA_COVERAGE_UNAVAILABLE_MESSAGE,
    };
    expect(Value.Check(dataCoverageSchema, coverage)).toBe(false);
  });

  it('pins the unavailable message to the exact public-safe literal', () => {
    const coverage = { available: false, message: 'Run 42 is invalidated.' };
    expect(Value.Check(dataCoverageSchema, coverage)).toBe(false);
  });

  it.each([
    'dataStart',
    'dataEnd',
    'lastRefreshed',
    'taxonomyVersion',
    'aggregateRunId',
    'counts',
  ] as const)('rejects an available arm missing %s', (field) => {
    const coverage: Mutable = { ...validDataCoverageAvailable().coverage };
    delete coverage[field];
    expect(Value.Check(dataCoverageSchema, coverage)).toBe(false);
  });
});

describe('dataCoverageResponseSchema', () => {
  it('accepts well-formed responses for both arms', () => {
    expect(Value.Check(dataCoverageResponseSchema, validDataCoverageAvailable())).toBe(true);
    expect(Value.Check(dataCoverageResponseSchema, validDataCoverageUnavailable())).toBe(true);
  });

  it.each(['jurisdiction', 'courtScope', 'plannedDataStart', 'knownLimitations'] as const)(
    'rejects a response missing the common field %s',
    (field) => {
      const response: Mutable = { ...validDataCoverageUnavailable() };
      delete response[field];
      expect(Value.Check(dataCoverageResponseSchema, response)).toBe(false);
    },
  );

  it('pins jurisdiction, courtScope, and plannedDataStart as literals', () => {
    const valid = validDataCoverageAvailable();
    expect(Value.Check(dataCoverageResponseSchema, { ...valid, jurisdiction: 'Pittsburgh' })).toBe(
      false,
    );
    expect(Value.Check(dataCoverageResponseSchema, { ...valid, courtScope: 'All courts.' })).toBe(
      false,
    );
    expect(
      Value.Check(dataCoverageResponseSchema, { ...valid, plannedDataStart: '2024-01-01' }),
    ).toBe(false);
  });

  it('rejects an empty knownLimitations list and empty entries', () => {
    const valid = validDataCoverageAvailable();
    expect(Value.Check(dataCoverageResponseSchema, { ...valid, knownLimitations: [] })).toBe(false);
    expect(Value.Check(dataCoverageResponseSchema, { ...valid, knownLimitations: [''] })).toBe(
      false,
    );
  });

  it('rejects unknown top-level properties', () => {
    expect(
      Value.Check(dataCoverageResponseSchema, { ...validDataCoverageAvailable(), extra: 1 }),
    ).toBe(false);
  });
});
