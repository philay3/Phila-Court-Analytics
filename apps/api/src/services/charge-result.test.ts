import type { Kysely } from 'kysely';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  CHARGE_RESULT_UNAVAILABLE_MESSAGE,
  CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  PUBLIC_ERROR_CODES,
  type ChargeOnlyResultSuccess,
} from '@pca/shared';
import type { PublicApiDatabase } from '../db.js';
import {
  findActiveChargeById,
  findActiveChargeBySlug,
  findActivePublishedRun,
  getChargeOutcomeRows,
  getChargeSentencingRows,
  type ChargeOutcomeAggregateRow,
  type ChargeSentencingAggregateRow,
} from '../repositories/charge-result.js';
import { getChargeOnlyResult } from './charge-result.js';

vi.mock('../repositories/charge-result.js');

// Unit coverage for the service's integrity rules against a stubbed
// repository — no database required. The seeded data is uniform by
// construction, so the corrupt-row paths (sample-size disagreement, unknown
// or non-public category codes) are exercised here rather than via temp
// aggregate rows.

// The repository is mocked, so the db handle is never dereferenced.
const db = {} as unknown as Kysely<PublicApiDatabase>;
const getDb = () => db;

// Narrows the response union to the success arm for the mapping-rules tests,
// which all run on the happy-path stub. A wrong arm fails loudly here rather
// than via a confusing property-access error downstream.
async function getSuccess(param: string): Promise<ChargeOnlyResultSuccess> {
  const result = await getChargeOnlyResult(getDb, param);
  if (result.resultType !== 'charge_only') {
    throw new Error(`expected the charge_only success arm, got ${result.resultType}`);
  }
  return result;
}

const CHARGE = {
  id: '3f0e9a4c-7b21-4d58-9c36-1a2b3c4d5e6f',
  slug: 'retail-theft',
  display_name: 'Retail Theft',
  statute_code: '18 § 3929',
  grade: 'M1',
};

const RUN = {
  id: '5eedda7a-0000-4000-8000-000000000001',
  taxonomy_version: '1.0.0',
  published_at: new Date('2026-07-01T02:00:00.000Z'),
  data_range_start: '2025-01-01',
  data_range_end: '2026-06-30',
};

function outcomeRow(overrides: Partial<ChargeOutcomeAggregateRow> = {}): ChargeOutcomeAggregateRow {
  return {
    category_code: 'dismissed',
    count: 10,
    percentage: '50.00',
    sample_size: 20,
    is_thin_data: false,
    ...overrides,
  };
}

function sentencingRow(
  overrides: Partial<ChargeSentencingAggregateRow> = {},
): ChargeSentencingAggregateRow {
  return {
    category_code: 'probation',
    count: 5,
    percentage: '50.00',
    sentencing_sample_size: 10,
    is_thin_data: false,
    ...overrides,
  };
}

function stubHappyPath() {
  vi.mocked(findActiveChargeBySlug).mockResolvedValue(CHARGE);
  vi.mocked(findActiveChargeById).mockResolvedValue(CHARGE);
  vi.mocked(findActivePublishedRun).mockResolvedValue(RUN);
  vi.mocked(getChargeOutcomeRows).mockResolvedValue([
    outcomeRow({ category_code: 'dismissed', count: 10, percentage: '50.00' }),
    outcomeRow({ category_code: 'guilty_plea', count: 10, percentage: '50.00' }),
  ]);
  vi.mocked(getChargeSentencingRows).mockResolvedValue([
    sentencingRow({ category_code: 'probation', count: 5, percentage: '50.00' }),
    sentencingRow({ category_code: 'fine', count: 5, percentage: '50.00' }),
  ]);
}

beforeEach(() => {
  vi.resetAllMocks();
  stubHappyPath();
});

describe('id/slug dispatch (no fallthrough)', () => {
  it('routes a UUID-shaped param to the id lookup only, case-insensitively', async () => {
    for (const param of [
      'aaaaaaaa-bbbb-1ccc-8ddd-eeeeeeeeeeee',
      'AAAAAAAA-BBBB-1CCC-8DDD-EEEEEEEEEEEE',
    ]) {
      vi.clearAllMocks();
      stubHappyPath();
      await getChargeOnlyResult(getDb, param);
      expect(findActiveChargeById).toHaveBeenCalledWith(db, param);
      expect(findActiveChargeBySlug).not.toHaveBeenCalled();
    }
  });

  it('routes anything else to the slug lookup only', async () => {
    await getChargeOnlyResult(getDb, 'retail-theft');
    expect(findActiveChargeBySlug).toHaveBeenCalledWith(db, 'retail-theft');
    expect(findActiveChargeById).not.toHaveBeenCalled();
  });

  it('a UUID-shaped miss throws CHARGE_NOT_FOUND without consulting slugs', async () => {
    vi.mocked(findActiveChargeById).mockResolvedValue(undefined);
    await expect(
      getChargeOnlyResult(getDb, 'aaaaaaaa-bbbb-1ccc-8ddd-eeeeeeeeeeee'),
    ).rejects.toMatchObject({ code: PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND });
    expect(findActiveChargeBySlug).not.toHaveBeenCalled();
  });
});

describe('unavailable states', () => {
  it('throws CHARGE_NOT_FOUND before touching the run when the charge misses', async () => {
    vi.mocked(findActiveChargeBySlug).mockResolvedValue(undefined);
    await expect(getChargeOnlyResult(getDb, 'no-such-charge')).rejects.toMatchObject({
      code: PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND,
    });
    expect(findActivePublishedRun).not.toHaveBeenCalled();
  });

  // Both unavailable causes converge on the identical HTTP 200 arm (task
  // 13.2a): charge identity as served, the pinned code/message literals, and
  // the links only — never a thrown error. The no-published-run cause is
  // covered here at the unit level only; it cannot be exercised end-to-end
  // without dropping the globally-seeded published run out from under every
  // parallel DB suite (see the endpoint suite for the zero-rows cause).
  it('returns the 200 unavailable arm when no active published run exists', async () => {
    vi.mocked(findActivePublishedRun).mockResolvedValue(undefined);
    const result = await getChargeOnlyResult(getDb, 'retail-theft');
    expect(result).toEqual({
      resultType: 'charge_only_unavailable',
      code: PUBLIC_ERROR_CODES.CHARGE_RESULT_UNAVAILABLE,
      message: CHARGE_RESULT_UNAVAILABLE_MESSAGE,
      charge: {
        id: CHARGE.id,
        slug: CHARGE.slug,
        displayName: CHARGE.display_name,
        statuteCode: CHARGE.statute_code,
        grade: CHARGE.grade,
      },
      links: { methodology: '/methodology', definitions: '/definitions' },
    });
  });

  it('returns the 200 unavailable arm when the run has zero outcome rows', async () => {
    vi.mocked(getChargeOutcomeRows).mockResolvedValue([]);
    const result = await getChargeOnlyResult(getDb, 'retail-theft');
    expect(result).toMatchObject({
      resultType: 'charge_only_unavailable',
      code: PUBLIC_ERROR_CODES.CHARGE_RESULT_UNAVAILABLE,
      message: CHARGE_RESULT_UNAVAILABLE_MESSAGE,
      charge: { slug: CHARGE.slug },
    });
    // Never touches sentencing once outcomes are empty.
    expect(getChargeSentencingRows).not.toHaveBeenCalled();
  });
});

describe('integrity failures → INTERNAL_ERROR', () => {
  it('rejects a sample-size disagreement within the outcome distribution', async () => {
    vi.mocked(getChargeOutcomeRows).mockResolvedValue([
      outcomeRow({ category_code: 'dismissed', sample_size: 20 }),
      outcomeRow({ category_code: 'guilty_plea', sample_size: 21 }),
    ]);
    await expect(getChargeOnlyResult(getDb, 'retail-theft')).rejects.toMatchObject({
      code: PUBLIC_ERROR_CODES.INTERNAL_ERROR,
    });
  });

  it('rejects a sample-size disagreement within the sentencing distribution', async () => {
    vi.mocked(getChargeSentencingRows).mockResolvedValue([
      sentencingRow({ category_code: 'probation', sentencing_sample_size: 10 }),
      sentencingRow({ category_code: 'fine', sentencing_sample_size: 11 }),
    ]);
    await expect(getChargeOnlyResult(getDb, 'retail-theft')).rejects.toMatchObject({
      code: PUBLIC_ERROR_CODES.INTERNAL_ERROR,
    });
  });

  it('rejects a category code unknown to the taxonomy artifact', async () => {
    vi.mocked(getChargeOutcomeRows).mockResolvedValue([
      outcomeRow({ category_code: 'bogus_code' }),
    ]);
    await expect(getChargeOnlyResult(getDb, 'retail-theft')).rejects.toMatchObject({
      code: PUBLIC_ERROR_CODES.INTERNAL_ERROR,
    });
  });

  it('rejects a known-but-non-public category code ("unknown") identically', async () => {
    vi.mocked(getChargeOutcomeRows).mockResolvedValue([outcomeRow({ category_code: 'unknown' })]);
    await expect(getChargeOnlyResult(getDb, 'retail-theft')).rejects.toMatchObject({
      code: PUBLIC_ERROR_CODES.INTERNAL_ERROR,
    });
  });
});

describe('mapping rules', () => {
  it('orders rows by taxonomy sortOrder regardless of storage order', async () => {
    vi.mocked(getChargeOutcomeRows).mockResolvedValue([
      outcomeRow({ category_code: 'guilty_plea' }),
      outcomeRow({ category_code: 'dismissed' }),
    ]);
    const result = await getSuccess('retail-theft');
    expect(result.outcomes.rows.map((row) => row.categoryCode)).toEqual([
      'dismissed',
      'guilty_plea',
    ]);
    expect(result.outcomes.rows.map((row) => row.displayName)).toEqual([
      'Dismissed',
      'Guilty plea',
    ]);
  });

  it('sets thinData when ANY row carries the flag (any-row rule)', async () => {
    vi.mocked(getChargeOutcomeRows).mockResolvedValue([
      outcomeRow({ category_code: 'dismissed', is_thin_data: false }),
      outcomeRow({ category_code: 'guilty_plea', is_thin_data: true }),
    ]);
    const result = await getSuccess('retail-theft');
    expect(result.outcomes.thinData).toBe(true);
  });

  it('returns the sentencing-unavailable arm with the pinned constant when no rows exist', async () => {
    vi.mocked(getChargeSentencingRows).mockResolvedValue([]);
    const result = await getSuccess('retail-theft');
    expect(result.sentencing).toEqual({
      available: false,
      message: CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
    });
    expect(result.outcomes.rows).toHaveLength(2);
  });

  it('keeps sentencing sample size independent of the outcome sample size', async () => {
    const result = await getSuccess('retail-theft');
    expect(result.outcomes.sampleSize).toBe(20);
    expect(result.sentencing).toMatchObject({ available: true, sampleSize: 10 });
  });
});
