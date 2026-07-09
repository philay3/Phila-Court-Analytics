import type { Kysely } from 'kysely';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
  PUBLIC_ERROR_CODES,
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
import {
  findActiveJudgeById,
  findActiveJudgeBySlug,
  getJudgeOutcomeRows,
  getJudgeSentencingRows,
} from '../repositories/judge-result.js';
import { getJudgeSpecificResult } from './judge-result.js';

vi.mock('../repositories/charge-result.js');
vi.mock('../repositories/judge-result.js');

// Unit coverage for the 8.2 decision quadrant and the judge-scoped integrity
// rules against stubbed repositories — no database required. The seeded data
// is uniform by construction, so the corrupt-row paths are exercised here.

// The repositories are mocked, so the db handle is never dereferenced.
const db = {} as unknown as Kysely<PublicApiDatabase>;
const getDb = () => db;

const CHARGE = {
  id: '3f0e9a4c-7b21-4d58-9c36-1a2b3c4d5e6f',
  slug: 'retail-theft',
  display_name: 'Retail Theft',
  statute_code: '18 § 3929',
  grade: 'M1',
};

const JUDGE = {
  id: '7c1d2e3f-4a5b-4c6d-8e7f-9a0b1c2d3e4f',
  slug: 'judge-testina-placeholder',
  display_name: 'Testina Placeholder',
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
  vi.mocked(findActiveJudgeBySlug).mockResolvedValue(JUDGE);
  vi.mocked(findActiveJudgeById).mockResolvedValue(JUDGE);
  vi.mocked(findActivePublishedRun).mockResolvedValue(RUN);
  // Four distinct sample sizes so cross-contamination between the scopes
  // would be visible in any assertion.
  vi.mocked(getChargeOutcomeRows).mockResolvedValue([
    outcomeRow({ category_code: 'dismissed', sample_size: 20 }),
    outcomeRow({ category_code: 'guilty_plea', sample_size: 20 }),
  ]);
  vi.mocked(getChargeSentencingRows).mockResolvedValue([
    sentencingRow({ category_code: 'probation', sentencing_sample_size: 10 }),
    sentencingRow({ category_code: 'fine', sentencing_sample_size: 10 }),
  ]);
  vi.mocked(getJudgeOutcomeRows).mockResolvedValue([
    outcomeRow({ category_code: 'dismissed', count: 3, percentage: '37.50', sample_size: 8 }),
    outcomeRow({ category_code: 'guilty_plea', count: 5, percentage: '62.50', sample_size: 8 }),
  ]);
  vi.mocked(getJudgeSentencingRows).mockResolvedValue([
    sentencingRow({
      category_code: 'probation',
      count: 3,
      percentage: '60.00',
      sentencing_sample_size: 5,
    }),
    sentencingRow({
      category_code: 'fine',
      count: 2,
      percentage: '40.00',
      sentencing_sample_size: 5,
    }),
  ]);
}

function call(chargeParam = 'retail-theft', judgeParam = 'judge-testina-placeholder') {
  return getJudgeSpecificResult(getDb, chargeParam, judgeParam);
}

beforeEach(() => {
  vi.resetAllMocks();
  stubHappyPath();
});

describe('entity resolution (charge, then judge, no fallthrough on either)', () => {
  it('throws CHARGE_NOT_FOUND before consulting the judge or the run', async () => {
    vi.mocked(findActiveChargeBySlug).mockResolvedValue(undefined);
    await expect(call('no-such-charge')).rejects.toMatchObject({
      code: PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND,
    });
    expect(findActiveJudgeBySlug).not.toHaveBeenCalled();
    expect(findActiveJudgeById).not.toHaveBeenCalled();
    expect(findActivePublishedRun).not.toHaveBeenCalled();
  });

  it('throws JUDGE_NOT_FOUND before touching the run', async () => {
    vi.mocked(findActiveJudgeBySlug).mockResolvedValue(undefined);
    await expect(call('retail-theft', 'no-such-judge')).rejects.toMatchObject({
      code: PUBLIC_ERROR_CODES.JUDGE_NOT_FOUND,
    });
    expect(findActivePublishedRun).not.toHaveBeenCalled();
  });

  it('routes UUID-shaped params to the id lookups only, independently per param', async () => {
    await call('AAAAAAAA-BBBB-1CCC-8DDD-EEEEEEEEEEEE', 'judge-testina-placeholder');
    expect(findActiveChargeById).toHaveBeenCalledWith(db, 'AAAAAAAA-BBBB-1CCC-8DDD-EEEEEEEEEEEE');
    expect(findActiveChargeBySlug).not.toHaveBeenCalled();
    expect(findActiveJudgeBySlug).toHaveBeenCalledWith(db, 'judge-testina-placeholder');
    expect(findActiveJudgeById).not.toHaveBeenCalled();
  });

  it('a UUID-shaped judge miss throws JUDGE_NOT_FOUND without consulting slugs', async () => {
    vi.mocked(findActiveJudgeById).mockResolvedValue(undefined);
    await expect(
      call('retail-theft', 'aaaaaaaa-bbbb-1ccc-8ddd-eeeeeeeeeeee'),
    ).rejects.toMatchObject({ code: PUBLIC_ERROR_CODES.JUDGE_NOT_FOUND });
    expect(findActiveJudgeBySlug).not.toHaveBeenCalled();
  });
});

describe('availability quadrant', () => {
  it('throws CHARGE_RESULT_UNAVAILABLE when no active published run exists', async () => {
    vi.mocked(findActivePublishedRun).mockResolvedValue(undefined);
    await expect(call()).rejects.toMatchObject({
      code: PUBLIC_ERROR_CODES.CHARGE_RESULT_UNAVAILABLE,
    });
  });

  it('throws CHARGE_RESULT_UNAVAILABLE when baseline and judge rows are both absent', async () => {
    vi.mocked(getChargeOutcomeRows).mockResolvedValue([]);
    vi.mocked(getJudgeOutcomeRows).mockResolvedValue([]);
    await expect(call()).rejects.toMatchObject({
      code: PUBLIC_ERROR_CODES.CHARGE_RESULT_UNAVAILABLE,
    });
  });

  it('throws INTERNAL_ERROR when judge rows exist without their baseline', async () => {
    vi.mocked(getChargeOutcomeRows).mockResolvedValue([]);
    await expect(call()).rejects.toMatchObject({
      code: PUBLIC_ERROR_CODES.INTERNAL_ERROR,
    });
  });

  it('returns the HTTP-200 unavailable arm when only the judge rows are absent', async () => {
    vi.mocked(getJudgeOutcomeRows).mockResolvedValue([]);
    const result = await call();
    expect(result).toEqual({
      resultType: 'judge_specific_unavailable',
      code: PUBLIC_ERROR_CODES.JUDGE_SPECIFIC_RESULT_UNAVAILABLE,
      message: JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
      charge: {
        id: CHARGE.id,
        slug: CHARGE.slug,
        displayName: CHARGE.display_name,
        statuteCode: CHARGE.statute_code,
        grade: CHARGE.grade,
      },
      judge: { id: JUDGE.id, slug: JUDGE.slug, displayName: JUDGE.display_name },
      fallback: { chargeOnlyResultPath: '/api/v1/public/results/charge/retail-theft' },
    });
    // No distribution reads happen for the unavailable arm.
    expect(getJudgeSentencingRows).not.toHaveBeenCalled();
    expect(getChargeSentencingRows).not.toHaveBeenCalled();
  });
});

describe('success response', () => {
  it('renders both scopes with four independent sample sizes', async () => {
    const result = await call();
    if (result.resultType !== 'judge_specific') {
      throw new Error(`expected the success arm, got ${result.resultType}`);
    }
    expect(result.judgeSpecific.outcomes.sampleSize).toBe(8);
    expect(result.judgeSpecific.sentencing).toMatchObject({ available: true, sampleSize: 5 });
    expect(result.baseline.outcomes.sampleSize).toBe(20);
    expect(result.baseline.sentencing).toMatchObject({ available: true, sampleSize: 10 });
    expect(result.judge).toEqual({
      id: JUDGE.id,
      slug: JUDGE.slug,
      displayName: JUDGE.display_name,
    });
    expect(result.aggregateRunId).toBe(RUN.id);
    expect(result.lastRefreshed).toBe('2026-07-01T02:00:00.000Z');
  });

  it('returns the judge-scoped sentencing-unavailable arm while the baseline union stays available', async () => {
    vi.mocked(getJudgeSentencingRows).mockResolvedValue([]);
    const result = await call();
    if (result.resultType !== 'judge_specific') {
      throw new Error(`expected the success arm, got ${result.resultType}`);
    }
    expect(result.judgeSpecific.sentencing).toEqual({
      available: false,
      message: CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
    });
    expect(result.baseline.sentencing).toMatchObject({ available: true, sampleSize: 10 });
  });
});

describe('integrity failures on judge-scoped distributions → INTERNAL_ERROR', () => {
  it('rejects a sample-size disagreement within the judge outcome distribution', async () => {
    vi.mocked(getJudgeOutcomeRows).mockResolvedValue([
      outcomeRow({ category_code: 'dismissed', sample_size: 8 }),
      outcomeRow({ category_code: 'guilty_plea', sample_size: 9 }),
    ]);
    await expect(call()).rejects.toMatchObject({ code: PUBLIC_ERROR_CODES.INTERNAL_ERROR });
  });

  it('rejects a sample-size disagreement within the judge sentencing distribution', async () => {
    vi.mocked(getJudgeSentencingRows).mockResolvedValue([
      sentencingRow({ category_code: 'probation', sentencing_sample_size: 5 }),
      sentencingRow({ category_code: 'fine', sentencing_sample_size: 6 }),
    ]);
    await expect(call()).rejects.toMatchObject({ code: PUBLIC_ERROR_CODES.INTERNAL_ERROR });
  });

  it('rejects unknown and known-but-non-public category codes on judge rows', async () => {
    for (const category_code of ['bogus_code', 'unknown']) {
      vi.mocked(getJudgeOutcomeRows).mockResolvedValue([outcomeRow({ category_code })]);
      await expect(call(), category_code).rejects.toMatchObject({
        code: PUBLIC_ERROR_CODES.INTERNAL_ERROR,
      });
    }
  });
});
