import { Value } from '@sinclair/typebox/value';
import { describe, expect, it } from 'vitest';

import {
  validChargeOnlyResult,
  validChargeOnlyResultSentencingUnavailable,
} from '../test-support/fixtures.js';
import {
  CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  chargeOnlyResultResponseSchema,
  chargeSentencingSchema,
} from './charge-result.js';

describe('chargeOnlyResultResponseSchema', () => {
  it('accepts a valid result with sentencing available', () => {
    expect(Value.Check(chargeOnlyResultResponseSchema, validChargeOnlyResult())).toBe(true);
  });

  it('accepts a valid result with the sentencing-unavailable arm', () => {
    expect(
      Value.Check(chargeOnlyResultResponseSchema, validChargeOnlyResultSentencingUnavailable()),
    ).toBe(true);
  });

  it('accepts a charge without the optional statuteCode and grade', () => {
    const result = validChargeOnlyResult();
    result.charge = {
      id: result.charge.id,
      slug: result.charge.slug,
      displayName: result.charge.displayName,
    };
    expect(Value.Check(chargeOnlyResultResponseSchema, result)).toBe(true);
  });

  it('requires every non-optional top-level field', () => {
    for (const field of [
      'charge',
      'resultType',
      'geography',
      'dateRange',
      'lastRefreshed',
      'taxonomyVersion',
      'aggregateRunId',
      'outcomes',
      'sentencing',
      'links',
    ] as const) {
      const result: Record<string, unknown> = { ...validChargeOnlyResult() };
      delete result[field];
      expect(Value.Check(chargeOnlyResultResponseSchema, result), `missing ${field}`).toBe(false);
    }
  });

  it('pins resultType, geography, and links to their literals', () => {
    expect(
      Value.Check(chargeOnlyResultResponseSchema, {
        ...validChargeOnlyResult(),
        resultType: 'judge_specific',
      }),
    ).toBe(false);
    expect(
      Value.Check(chargeOnlyResultResponseSchema, {
        ...validChargeOnlyResult(),
        geography: 'pennsylvania',
      }),
    ).toBe(false);
    expect(
      Value.Check(chargeOnlyResultResponseSchema, {
        ...validChargeOnlyResult(),
        links: { methodology: '/somewhere-else', definitions: '/definitions' },
      }),
    ).toBe(false);
  });

  it('rejects a non-semver taxonomy version, a non-ISO lastRefreshed, and a non-uuid run id', () => {
    expect(
      Value.Check(chargeOnlyResultResponseSchema, {
        ...validChargeOnlyResult(),
        taxonomyVersion: 'v1',
      }),
    ).toBe(false);
    expect(
      Value.Check(chargeOnlyResultResponseSchema, {
        ...validChargeOnlyResult(),
        lastRefreshed: 'today',
      }),
    ).toBe(false);
    expect(
      Value.Check(chargeOnlyResultResponseSchema, {
        ...validChargeOnlyResult(),
        aggregateRunId: 'run-42',
      }),
    ).toBe(false);
  });

  it('rejects the legacy task-3.2 distribution shape (entries key)', () => {
    const result: Record<string, unknown> = {
      ...validChargeOnlyResult(),
      outcomes: {
        sampleSize: 120,
        thinData: false,
        entries: validChargeOnlyResult().outcomes.rows,
      },
    };
    expect(Value.Check(chargeOnlyResultResponseSchema, result)).toBe(false);
  });

  it('rejects extra properties at every level', () => {
    const withRootExtra = { ...validChargeOnlyResult(), docketNumber: 'CP-0000' };
    expect(Value.Check(chargeOnlyResultResponseSchema, withRootExtra)).toBe(false);

    const withChargeExtra = validChargeOnlyResult() as Record<string, unknown>;
    withChargeExtra.charge = { ...validChargeOnlyResult().charge, defendantName: 'x' };
    expect(Value.Check(chargeOnlyResultResponseSchema, withChargeExtra)).toBe(false);

    const withOutcomesExtra = validChargeOnlyResult() as Record<string, unknown>;
    withOutcomesExtra.outcomes = { ...validChargeOnlyResult().outcomes, dateRange: {} };
    expect(Value.Check(chargeOnlyResultResponseSchema, withOutcomesExtra)).toBe(false);

    const base = validChargeOnlyResult();
    const firstRow = base.outcomes.rows[0];
    expect(firstRow).toBeDefined();
    const withRowExtra = validChargeOnlyResult() as Record<string, unknown>;
    withRowExtra.outcomes = {
      ...base.outcomes,
      rows: [{ ...firstRow, sampleSize: 120 }, ...base.outcomes.rows.slice(1)],
    };
    expect(Value.Check(chargeOnlyResultResponseSchema, withRowExtra)).toBe(false);
  });
});

describe('chargeSentencingSchema (tagged union)', () => {
  it('rejects the unavailable arm with any message other than the pinned constant', () => {
    expect(
      Value.Check(chargeSentencingSchema, {
        available: false,
        message: CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
      }),
    ).toBe(true);
    expect(
      Value.Check(chargeSentencingSchema, {
        available: false,
        message: 'Sentencing rows failed parser review.',
      }),
    ).toBe(false);
  });

  it('rejects arm mixtures: unavailable with rows, available with message', () => {
    expect(
      Value.Check(chargeSentencingSchema, {
        available: false,
        message: CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
        rows: [],
      }),
    ).toBe(false);
    const available = validChargeOnlyResult().sentencing;
    expect(
      Value.Check(chargeSentencingSchema, {
        ...available,
        message: CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
      }),
    ).toBe(false);
  });

  it('rejects the available arm without its own sampleSize', () => {
    const arm: Record<string, unknown> = { ...validChargeOnlyResult().sentencing };
    delete arm.sampleSize;
    expect(Value.Check(chargeSentencingSchema, arm)).toBe(false);
  });
});
