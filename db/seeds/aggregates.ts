import { OUTCOME_CATEGORIES, SENTENCING_CATEGORIES, TAXONOMY_VERSION } from '@pca/taxonomy';
import type { Kysely, Transaction } from 'kysely';
import { sql } from 'kysely';

import type { Database } from '../src/types.js';
import {
  AGGREGATE_DATE_RANGE,
  DECOY_CHARGE_OUTCOMES,
  PUBLISHED_CHARGE_OUTCOMES,
  PUBLISHED_CHARGE_SENTENCING,
  PUBLISHED_JUDGE_OUTCOMES,
  PUBLISHED_JUDGE_SENTENCING,
  PUBLISHED_RUN_TIMESTAMPS,
  SEED_AGGREGATE_CREATED_AT,
  SEED_PUBLISHED_RUN_ID,
  SEED_RUN_CREATED_AT,
  SEED_UNPUBLISHED_RUN_ID,
  UNPUBLISHED_RUN_STARTED_AT,
  type CategoryCount,
  type ChargeOutcomeDistribution,
  type ChargeSentencingDistribution,
  type JudgeOutcomeDistribution,
  type JudgeSentencingDistribution,
} from './aggregate-data.js';
import { requireId, selectIdBySlug } from './reference.js';

/**
 * Aggregate-layer seeds (task 6.4): one published run populating all four
 * analytics aggregate tables, plus one unpublished decoy run.
 *
 * Aggregate rows are IMMUTABLE by standing decision (update-never typing in
 * types.ts), so re-runs use delete-and-reinsert inside one transaction per
 * run — never ON CONFLICT DO UPDATE. Only the run rows upsert, by primary
 * key, guarded with IS DISTINCT FROM so an unchanged re-run performs no
 * UPDATE at all: the updated_at trigger stays quiet and the active-published
 * partial unique index keeps its single row.
 *
 * Re-run identity is content identity: every content column is fixed
 * (constant timestamps, derived percentages); only the aggregate rows'
 * surrogate ids regenerate, and nothing may ever reference those.
 *
 * If the seed run were manually invalidated and a different run published,
 * re-seeding fails loudly on the partial unique index rather than silently
 * un-invalidating — intended behavior; seeds target fresh migrated databases.
 */

const AGGREGATE_TABLES = [
  'analytics.charge_outcome_aggregates',
  'analytics.charge_sentencing_aggregates',
  'analytics.judge_outcome_aggregates',
  'analytics.judge_sentencing_aggregates',
] as const;

type AggregateTable = (typeof AGGREGATE_TABLES)[number];

export interface AggregateTableResult {
  table: AggregateTable;
  deleted: number;
  inserted: number;
}

export interface AggregateRunResult {
  run: string;
  runId: string;
  runRowChanged: boolean;
  tables: AggregateTableResult[];
}

/** numeric(5,2) column: percentages carry exactly two decimal places. */
export function percentageOf(count: number, sampleSize: number): string {
  return (Math.round((count * 10_000) / sampleSize) / 100).toFixed(2);
}

// ---------------------------------------------------------------------------
// Self-validation: runs in memory before any write and throws on violation.
// ---------------------------------------------------------------------------

const MIN_CATEGORIES = { outcome: 5, sentencing: 4 } as const;
const PERCENTAGE_TOLERANCE = 0.005 + Number.EPSILON * 100;

/**
 * Thin-data expectations restated from the task 6.4 matrix, independently of
 * the data file, so an accidental edit to either side fails the seed.
 */
const EXPECTED_THIN_CHARGE_OUTCOMES = new Set(['criminal-trespass']);
const EXPECTED_THIN_JUDGE_OUTCOMES = new Set(['simple-assault|judge-testina-placeholder']);

/** Fully-unavailable judge: ref rows exist, aggregate rows must not. */
const UNAVAILABLE_JUDGE_SLUG = 'judge-fakename-example';

interface DistributionCheck {
  label: string;
  kind: keyof typeof MIN_CATEGORIES;
  sampleSize: number;
  isThinData: boolean;
  expectedThin: boolean;
  counts: readonly CategoryCount<string>[];
}

function fail(label: string, message: string): never {
  throw new Error(`aggregate seed validation failed [${label}]: ${message}`);
}

function publicCodes(categories: readonly { code: string; public: boolean }[]): Set<string> {
  return new Set(categories.filter((c) => c.public).map((c) => c.code));
}

export function validateAggregateSeeds(): void {
  if (AGGREGATE_DATE_RANGE.start !== '2025-01-01') {
    fail('date range', `must start 2025-01-01, got ${AGGREGATE_DATE_RANGE.start}`);
  }
  if (AGGREGATE_DATE_RANGE.start > AGGREGATE_DATE_RANGE.end) {
    fail(
      'date range',
      `start ${AGGREGATE_DATE_RANGE.start} is after end ${AGGREGATE_DATE_RANGE.end}`,
    );
  }

  const checks: DistributionCheck[] = [
    ...PUBLISHED_CHARGE_OUTCOMES.map((dist) => ({
      label: `published charge outcomes: ${dist.chargeSlug}`,
      kind: 'outcome' as const,
      sampleSize: dist.sampleSize,
      isThinData: dist.isThinData,
      expectedThin: EXPECTED_THIN_CHARGE_OUTCOMES.has(dist.chargeSlug),
      counts: dist.counts,
    })),
    ...PUBLISHED_CHARGE_SENTENCING.map((dist) => ({
      label: `published charge sentencing: ${dist.chargeSlug}`,
      kind: 'sentencing' as const,
      sampleSize: dist.sentencingSampleSize,
      isThinData: dist.isThinData,
      expectedThin: false,
      counts: dist.counts,
    })),
    ...PUBLISHED_JUDGE_OUTCOMES.map((dist) => ({
      label: `published judge outcomes: ${dist.chargeSlug}/${dist.judgeSlug}`,
      kind: 'outcome' as const,
      sampleSize: dist.sampleSize,
      isThinData: dist.isThinData,
      expectedThin: EXPECTED_THIN_JUDGE_OUTCOMES.has(`${dist.chargeSlug}|${dist.judgeSlug}`),
      counts: dist.counts,
    })),
    ...PUBLISHED_JUDGE_SENTENCING.map((dist) => ({
      label: `published judge sentencing: ${dist.chargeSlug}/${dist.judgeSlug}`,
      kind: 'sentencing' as const,
      sampleSize: dist.sentencingSampleSize,
      isThinData: dist.isThinData,
      expectedThin: false,
      counts: dist.counts,
    })),
    ...DECOY_CHARGE_OUTCOMES.map((dist) => ({
      label: `decoy charge outcomes: ${dist.chargeSlug}`,
      kind: 'outcome' as const,
      sampleSize: dist.sampleSize,
      isThinData: dist.isThinData,
      expectedThin: false,
      counts: dist.counts,
    })),
  ];

  const publicByKind = {
    outcome: publicCodes(OUTCOME_CATEGORIES),
    sentencing: publicCodes(SENTENCING_CATEGORIES),
  };

  for (const check of checks) {
    const { label, kind, sampleSize, counts } = check;

    if (!Number.isInteger(sampleSize) || sampleSize <= 0) {
      fail(label, `sample size must be a positive integer, got ${sampleSize}`);
    }
    if (counts.length < MIN_CATEGORIES[kind]) {
      fail(label, `needs >= ${MIN_CATEGORIES[kind]} ${kind} categories, got ${counts.length}`);
    }

    const seen = new Set<string>();
    let sum = 0;
    for (const { code, count } of counts) {
      if (!publicByKind[kind].has(code)) {
        fail(label, `category "${code}" is not a public ${kind} category`);
      }
      if (seen.has(code)) {
        fail(label, `duplicate category "${code}"`);
      }
      seen.add(code);
      if (!Number.isInteger(count) || count <= 0) {
        fail(label, `count for "${code}" must be a positive integer, got ${count}`);
      }
      sum += count;

      const exact = (count / sampleSize) * 100;
      const stored = Number(percentageOf(count, sampleSize));
      if (Math.abs(stored - exact) > PERCENTAGE_TOLERANCE) {
        fail(label, `percentage ${stored} for "${code}" is not ${exact} within rounding tolerance`);
      }
    }
    if (sum !== sampleSize) {
      fail(label, `category counts sum to ${sum}, expected sample size ${sampleSize}`);
    }

    if (check.isThinData !== check.expectedThin) {
      fail(label, `is_thin_data is ${check.isThinData}, matrix expects ${check.expectedThin}`);
    }
  }

  const outcomeSampleByCharge = new Map(
    PUBLISHED_CHARGE_OUTCOMES.map((dist) => [dist.chargeSlug, dist.sampleSize]),
  );
  for (const dist of PUBLISHED_CHARGE_SENTENCING) {
    const outcomeSample = outcomeSampleByCharge.get(dist.chargeSlug);
    if (outcomeSample === undefined || dist.sentencingSampleSize >= outcomeSample) {
      fail(
        `published charge sentencing: ${dist.chargeSlug}`,
        `sentencing n ${dist.sentencingSampleSize} must be below the charge's outcome n ${outcomeSample}`,
      );
    }
  }

  const outcomeSampleByPair = new Map(
    PUBLISHED_JUDGE_OUTCOMES.map((dist) => [
      `${dist.chargeSlug}|${dist.judgeSlug}`,
      dist.sampleSize,
    ]),
  );
  for (const dist of PUBLISHED_JUDGE_SENTENCING) {
    const outcomeSample = outcomeSampleByPair.get(`${dist.chargeSlug}|${dist.judgeSlug}`);
    if (outcomeSample === undefined || dist.sentencingSampleSize >= outcomeSample) {
      fail(
        `published judge sentencing: ${dist.chargeSlug}/${dist.judgeSlug}`,
        `sentencing n ${dist.sentencingSampleSize} must be below the pair's outcome n ${outcomeSample}`,
      );
    }
  }

  const judgeSlugs = [...PUBLISHED_JUDGE_OUTCOMES, ...PUBLISHED_JUDGE_SENTENCING].map(
    (dist) => dist.judgeSlug,
  );
  if (judgeSlugs.includes(UNAVAILABLE_JUDGE_SLUG)) {
    fail(
      'unavailable judge',
      `${UNAVAILABLE_JUDGE_SLUG} must receive no aggregate rows — its absence is the fixture`,
    );
  }
}

// ---------------------------------------------------------------------------
// Seeding: one transaction per run, delete-and-reinsert.
// ---------------------------------------------------------------------------

export async function seedAggregates(db: Kysely<Database>): Promise<AggregateRunResult[]> {
  validateAggregateSeeds();
  return [
    await db.transaction().execute((trx) => seedPublishedRun(trx)),
    await db.transaction().execute((trx) => seedDecoyRun(trx)),
  ];
}

async function seedPublishedRun(trx: Transaction<Database>): Promise<AggregateRunResult> {
  const runRowChanged = await upsertRun(trx, {
    id: SEED_PUBLISHED_RUN_ID,
    status: 'completed',
    started_at: PUBLISHED_RUN_TIMESTAMPS.startedAt,
    completed_at: PUBLISHED_RUN_TIMESTAMPS.completedAt,
    published_at: PUBLISHED_RUN_TIMESTAMPS.publishedAt,
  });
  const deleted = await deleteRunAggregates(trx, SEED_PUBLISHED_RUN_ID);

  const chargeIds = await selectIdBySlug(trx, 'ref.normalized_charges', [
    ...new Set(
      [
        ...PUBLISHED_CHARGE_OUTCOMES,
        ...PUBLISHED_CHARGE_SENTENCING,
        ...PUBLISHED_JUDGE_OUTCOMES,
        ...PUBLISHED_JUDGE_SENTENCING,
      ].map((dist) => dist.chargeSlug),
    ),
  ]);
  const judgeIds = await selectIdBySlug(trx, 'ref.normalized_judges', [
    ...new Set(
      [...PUBLISHED_JUDGE_OUTCOMES, ...PUBLISHED_JUDGE_SENTENCING].map((dist) => dist.judgeSlug),
    ),
  ]);

  const inserted: Record<AggregateTable, number> = {
    'analytics.charge_outcome_aggregates': await insertChargeOutcomes(
      trx,
      SEED_PUBLISHED_RUN_ID,
      PUBLISHED_CHARGE_OUTCOMES,
      chargeIds,
    ),
    'analytics.charge_sentencing_aggregates': await insertChargeSentencing(
      trx,
      SEED_PUBLISHED_RUN_ID,
      PUBLISHED_CHARGE_SENTENCING,
      chargeIds,
    ),
    'analytics.judge_outcome_aggregates': await insertJudgeOutcomes(
      trx,
      SEED_PUBLISHED_RUN_ID,
      PUBLISHED_JUDGE_OUTCOMES,
      chargeIds,
      judgeIds,
    ),
    'analytics.judge_sentencing_aggregates': await insertJudgeSentencing(
      trx,
      SEED_PUBLISHED_RUN_ID,
      PUBLISHED_JUDGE_SENTENCING,
      chargeIds,
      judgeIds,
    ),
  };

  return {
    run: 'published',
    runId: SEED_PUBLISHED_RUN_ID,
    runRowChanged,
    tables: AGGREGATE_TABLES.map((table) => ({
      table,
      deleted: deleted[table],
      inserted: inserted[table],
    })),
  };
}

async function seedDecoyRun(trx: Transaction<Database>): Promise<AggregateRunResult> {
  const runRowChanged = await upsertRun(trx, {
    id: SEED_UNPUBLISHED_RUN_ID,
    status: 'in_progress',
    started_at: UNPUBLISHED_RUN_STARTED_AT,
    completed_at: null,
    published_at: null,
  });
  const deleted = await deleteRunAggregates(trx, SEED_UNPUBLISHED_RUN_ID);

  const chargeIds = await selectIdBySlug(trx, 'ref.normalized_charges', [
    ...new Set(DECOY_CHARGE_OUTCOMES.map((dist) => dist.chargeSlug)),
  ]);
  const insertedOutcomes = await insertChargeOutcomes(
    trx,
    SEED_UNPUBLISHED_RUN_ID,
    DECOY_CHARGE_OUTCOMES,
    chargeIds,
  );

  return {
    run: 'unpublished decoy',
    runId: SEED_UNPUBLISHED_RUN_ID,
    runRowChanged,
    tables: AGGREGATE_TABLES.map((table) => ({
      table,
      deleted: deleted[table],
      inserted: table === 'analytics.charge_outcome_aggregates' ? insertedOutcomes : 0,
    })),
  };
}

interface RunUpsertValues {
  id: string;
  status: 'completed' | 'in_progress';
  started_at: string;
  completed_at: string | null;
  published_at: string | null;
}

/**
 * Upsert by primary key with the same IS DISTINCT FROM guard as the 6.3
 * reference seeds: an unchanged re-run fires no UPDATE, so updated_at does
 * not churn and the run row is byte-identical across runs. The conflict
 * target is (id); the active-published partial unique index is never the
 * arbiter, and since a no-op re-run never moves published_at/invalidated_at,
 * the index keeps exactly one qualifying row.
 */
async function upsertRun(trx: Transaction<Database>, run: RunUpsertValues): Promise<boolean> {
  const result = await trx
    .insertInto('analytics.aggregate_runs')
    .values({
      ...run,
      invalidated_at: null,
      invalidated_reason: null,
      parser_version: null,
      taxonomy_version: TAXONOMY_VERSION,
      data_range_start: AGGREGATE_DATE_RANGE.start,
      data_range_end: AGGREGATE_DATE_RANGE.end,
      created_at: SEED_RUN_CREATED_AT,
    })
    .onConflict((oc) =>
      oc
        .column('id')
        .doUpdateSet((eb) => ({
          status: eb.ref('excluded.status'),
          started_at: eb.ref('excluded.started_at'),
          completed_at: eb.ref('excluded.completed_at'),
          published_at: eb.ref('excluded.published_at'),
          invalidated_at: eb.ref('excluded.invalidated_at'),
          invalidated_reason: eb.ref('excluded.invalidated_reason'),
          parser_version: eb.ref('excluded.parser_version'),
          taxonomy_version: eb.ref('excluded.taxonomy_version'),
          data_range_start: eb.ref('excluded.data_range_start'),
          data_range_end: eb.ref('excluded.data_range_end'),
        }))
        .where(
          sql<boolean>`(aggregate_runs.status, aggregate_runs.started_at, aggregate_runs.completed_at, aggregate_runs.published_at, aggregate_runs.invalidated_at, aggregate_runs.invalidated_reason, aggregate_runs.parser_version, aggregate_runs.taxonomy_version, aggregate_runs.data_range_start, aggregate_runs.data_range_end)
            is distinct from
            (excluded.status, excluded.started_at, excluded.completed_at, excluded.published_at, excluded.invalidated_at, excluded.invalidated_reason, excluded.parser_version, excluded.taxonomy_version, excluded.data_range_start, excluded.data_range_end)`,
        ),
    )
    .executeTakeFirst();
  return Number(result.numInsertedOrUpdatedRows ?? 0n) > 0;
}

async function deleteRunAggregates(
  trx: Transaction<Database>,
  runId: string,
): Promise<Record<AggregateTable, number>> {
  const deleted = {} as Record<AggregateTable, number>;
  for (const table of AGGREGATE_TABLES) {
    const result = await trx
      .deleteFrom(table)
      .where('aggregate_run_id', '=', runId)
      .executeTakeFirst();
    deleted[table] = Number(result.numDeletedRows);
  }
  return deleted;
}

function commonRowColumns(isThinData: boolean) {
  return {
    date_range_start: AGGREGATE_DATE_RANGE.start,
    date_range_end: AGGREGATE_DATE_RANGE.end,
    is_thin_data: isThinData,
    taxonomy_version: TAXONOMY_VERSION,
    created_at: SEED_AGGREGATE_CREATED_AT,
  };
}

async function insertChargeOutcomes(
  trx: Transaction<Database>,
  runId: string,
  dists: readonly ChargeOutcomeDistribution[],
  chargeIds: Map<string, string>,
): Promise<number> {
  const rows = dists.flatMap((dist) =>
    dist.counts.map(({ code, count }) => ({
      aggregate_run_id: runId,
      charge_id: requireId(chargeIds, dist.chargeSlug),
      category_code: code,
      count,
      percentage: percentageOf(count, dist.sampleSize),
      sample_size: dist.sampleSize,
      ...commonRowColumns(dist.isThinData),
    })),
  );
  await trx.insertInto('analytics.charge_outcome_aggregates').values(rows).execute();
  return rows.length;
}

async function insertChargeSentencing(
  trx: Transaction<Database>,
  runId: string,
  dists: readonly ChargeSentencingDistribution[],
  chargeIds: Map<string, string>,
): Promise<number> {
  const rows = dists.flatMap((dist) =>
    dist.counts.map(({ code, count }) => ({
      aggregate_run_id: runId,
      charge_id: requireId(chargeIds, dist.chargeSlug),
      category_code: code,
      count,
      percentage: percentageOf(count, dist.sentencingSampleSize),
      sentencing_sample_size: dist.sentencingSampleSize,
      ...commonRowColumns(dist.isThinData),
    })),
  );
  await trx.insertInto('analytics.charge_sentencing_aggregates').values(rows).execute();
  return rows.length;
}

async function insertJudgeOutcomes(
  trx: Transaction<Database>,
  runId: string,
  dists: readonly JudgeOutcomeDistribution[],
  chargeIds: Map<string, string>,
  judgeIds: Map<string, string>,
): Promise<number> {
  const rows = dists.flatMap((dist) =>
    dist.counts.map(({ code, count }) => ({
      aggregate_run_id: runId,
      charge_id: requireId(chargeIds, dist.chargeSlug),
      judge_id: requireId(judgeIds, dist.judgeSlug),
      category_code: code,
      count,
      percentage: percentageOf(count, dist.sampleSize),
      sample_size: dist.sampleSize,
      ...commonRowColumns(dist.isThinData),
    })),
  );
  await trx.insertInto('analytics.judge_outcome_aggregates').values(rows).execute();
  return rows.length;
}

async function insertJudgeSentencing(
  trx: Transaction<Database>,
  runId: string,
  dists: readonly JudgeSentencingDistribution[],
  chargeIds: Map<string, string>,
  judgeIds: Map<string, string>,
): Promise<number> {
  const rows = dists.flatMap((dist) =>
    dist.counts.map(({ code, count }) => ({
      aggregate_run_id: runId,
      charge_id: requireId(chargeIds, dist.chargeSlug),
      judge_id: requireId(judgeIds, dist.judgeSlug),
      category_code: code,
      count,
      percentage: percentageOf(count, dist.sentencingSampleSize),
      sentencing_sample_size: dist.sentencingSampleSize,
      ...commonRowColumns(dist.isThinData),
    })),
  );
  await trx.insertInto('analytics.judge_sentencing_aggregates').values(rows).execute();
  return rows.length;
}
