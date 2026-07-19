import { OUTCOME_CATEGORIES, SENTENCING_CATEGORIES, TAXONOMY_VERSION } from '@pca/taxonomy';
import type { Kysely, Transaction } from 'kysely';
import { sql } from 'kysely';

import type { Database } from '../src/types.js';
import {
  AGGREGATE_DATE_RANGE,
  DECOY_CHARGE_OUTCOMES,
  PUBLISHED_CHARGE_OUTCOMES,
  PUBLISHED_CHARGE_SENTENCING,
  PUBLISHED_CHARGE_SENTENCING_INDEX,
  PUBLISHED_JUDGE_OUTCOMES,
  PUBLISHED_JUDGE_SENTENCING,
  PUBLISHED_JUDGE_SENTENCING_INDEX,
  PUBLISHED_RUN_TIMESTAMPS,
  SEED_AGGREGATE_CREATED_AT,
  SEED_PUBLISHED_RUN_ID,
  SEED_RUN_CREATED_AT,
  SEED_UNPUBLISHED_RUN_ID,
  UNPUBLISHED_RUN_STARTED_AT,
  type CategoryCount,
  type ChargeOutcomeDistribution,
  type ChargeSentencingDistribution,
  type ChargeSentencingIndexSeed,
  type JudgeOutcomeDistribution,
  type JudgeSentencingDistribution,
  type JudgeSentencingIndexSeed,
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
  // Task 35.2: the five 35.1 conviction-grain sentencing-index tables share
  // the delete-and-reinsert lifecycle (immutable rows, same run scoping).
  'analytics.charge_sentencing_index_summaries',
  'analytics.charge_sentencing_index_aggregates',
  'analytics.charge_conviction_grade_aggregates',
  'analytics.judge_sentencing_index_summaries',
  'analytics.judge_sentencing_index_aggregates',
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

/** numeric(4,1) column: the index percentages carry exactly one decimal. */
export function percentage1Of(count: number, denominator: number): string {
  return (Math.round((count * 1000) / denominator) / 10).toFixed(1);
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

/**
 * Task 35.2 index-scenario matrix, restated independently of the data file:
 * thin cells, the deliberately index-absent charge (distributions exist,
 * index rows do not — the run-predates-population shape), and the
 * deliberately index-absent judge cell (pair outcomes exist, index absent).
 */
const EXPECTED_THIN_CHARGE_INDEX = new Set([
  'possession-controlled-substance',
  'criminal-trespass',
]);
const INDEX_ABSENT_CHARGE_SLUG = 'simple-assault';
const INDEX_ABSENT_JUDGE_PAIR = 'dui-general-impairment|judge-samuel-seeddata';

/** numeric(6,1) / numeric(4,1) literals as the seed files write them. */
const NUMERIC_1DP_PATTERN = /^\d{1,5}\.\d$/;

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

  const judgeSlugs = [
    ...PUBLISHED_JUDGE_OUTCOMES,
    ...PUBLISHED_JUDGE_SENTENCING,
    ...PUBLISHED_JUDGE_SENTENCING_INDEX,
  ].map((dist) => dist.judgeSlug);
  if (judgeSlugs.includes(UNAVAILABLE_JUDGE_SLUG)) {
    fail(
      'unavailable judge',
      `${UNAVAILABLE_JUDGE_SLUG} must receive no aggregate rows — its absence is the fixture`,
    );
  }

  validateSentencingIndexSeeds();
}

function validateIndexCell(
  label: string,
  seed: ChargeSentencingIndexSeed | JudgeSentencingIndexSeed,
  publicSentencing: Set<string>,
): void {
  const { convictions, sentencedConvictions, dateRange, categories } = seed;
  if (!Number.isInteger(convictions) || convictions <= 0) {
    fail(label, `convictions must be a positive integer, got ${convictions}`);
  }
  if (
    !Number.isInteger(sentencedConvictions) ||
    sentencedConvictions < 0 ||
    sentencedConvictions > convictions
  ) {
    fail(label, `sentenced ${sentencedConvictions} must be an integer in [0, ${convictions}]`);
  }
  if (
    dateRange.start < AGGREGATE_DATE_RANGE.start ||
    dateRange.end > AGGREGATE_DATE_RANGE.end ||
    dateRange.start > dateRange.end
  ) {
    fail(label, `cell date range ${dateRange.start}..${dateRange.end} must nest in the run range`);
  }
  if (sentencedConvictions === 0 && categories.length > 0) {
    fail(label, 'a zero-sentenced cell must have no category rows');
  }

  const seen = new Set<string>();
  for (const category of categories) {
    if (!publicSentencing.has(category.code)) {
      fail(label, `category "${category.code}" is not a public sentencing category`);
    }
    if (seen.has(category.code)) {
      fail(label, `duplicate category "${category.code}"`);
    }
    seen.add(category.code);
    if (
      !Number.isInteger(category.convictionCount) ||
      category.convictionCount <= 0 ||
      category.convictionCount > sentencedConvictions
    ) {
      fail(
        label,
        `count ${category.convictionCount} for "${category.code}" must be in [1, ${sentencedConvictions}]`,
      );
    }
    const trio = [category.medianMinDays, category.medianMaxDays, category.minAssumedPercentage];
    const present = trio.filter((value) => value !== undefined).length;
    if (present !== 0 && present !== 3) {
      fail(label, `duration trio for "${category.code}" must be all-present or all-absent`);
    }
    if (present === 3) {
      for (const value of trio) {
        if (!NUMERIC_1DP_PATTERN.test(value as string)) {
          fail(label, `"${value}" for "${category.code}" is not a 1-decimal numeric literal`);
        }
      }
      if (Number(category.medianMinDays) > Number(category.medianMaxDays)) {
        fail(label, `median min > max for "${category.code}"`);
      }
      if (Number(category.minAssumedPercentage) > 100) {
        fail(label, `min_assumed percentage for "${category.code}" exceeds 100`);
      }
    }
  }
}

function validateSentencingIndexSeeds(): void {
  const publicSentencing = publicCodes(SENTENCING_CATEGORIES);

  const indexedCharges = new Set<string>();
  for (const seed of PUBLISHED_CHARGE_SENTENCING_INDEX) {
    const label = `published charge sentencing index: ${seed.chargeSlug}`;
    if (indexedCharges.has(seed.chargeSlug)) {
      fail(label, 'duplicate charge cell');
    }
    indexedCharges.add(seed.chargeSlug);
    validateIndexCell(label, seed, publicSentencing);
    if (seed.isThinData !== EXPECTED_THIN_CHARGE_INDEX.has(seed.chargeSlug)) {
      fail(label, `is_thin_data is ${seed.isThinData}, matrix expects the opposite`);
    }

    const gradesSeen = new Set<string>();
    let gradeSum = 0;
    for (const { grade, count } of seed.grades) {
      if (gradesSeen.has(grade)) {
        fail(label, `duplicate grade "${grade}"`);
      }
      gradesSeen.add(grade);
      if (!Number.isInteger(count) || count <= 0) {
        fail(label, `grade count for "${grade}" must be a positive integer, got ${count}`);
      }
      gradeSum += count;
    }
    if (gradeSum !== seed.convictions) {
      fail(label, `grade counts sum to ${gradeSum}, expected convictions ${seed.convictions}`);
    }
  }
  if (indexedCharges.has(INDEX_ABSENT_CHARGE_SLUG)) {
    fail(
      'index-absent charge',
      `${INDEX_ABSENT_CHARGE_SLUG} must receive no index rows — its absence is the fixture`,
    );
  }

  const indexedPairs = new Set<string>();
  for (const seed of PUBLISHED_JUDGE_SENTENCING_INDEX) {
    const pair = `${seed.chargeSlug}|${seed.judgeSlug}`;
    const label = `published judge sentencing index: ${seed.chargeSlug}/${seed.judgeSlug}`;
    if (indexedPairs.has(pair)) {
      fail(label, 'duplicate judge cell');
    }
    indexedPairs.add(pair);
    validateIndexCell(label, seed, publicSentencing);
    if (seed.isThinData) {
      fail(label, 'no judge index cell is in the thin matrix');
    }
  }
  if (indexedPairs.has(INDEX_ABSENT_JUDGE_PAIR)) {
    fail(
      'index-absent judge cell',
      `${INDEX_ABSENT_JUDGE_PAIR} must receive no index rows — its absence is the fixture`,
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
        ...PUBLISHED_CHARGE_SENTENCING_INDEX,
        ...PUBLISHED_JUDGE_SENTENCING_INDEX,
      ].map((dist) => dist.chargeSlug),
    ),
  ]);
  const judgeIds = await selectIdBySlug(trx, 'ref.normalized_judges', [
    ...new Set(
      [
        ...PUBLISHED_JUDGE_OUTCOMES,
        ...PUBLISHED_JUDGE_SENTENCING,
        ...PUBLISHED_JUDGE_SENTENCING_INDEX,
      ].map((dist) => dist.judgeSlug),
    ),
  ]);

  const chargeIndex = await insertChargeSentencingIndex(
    trx,
    SEED_PUBLISHED_RUN_ID,
    PUBLISHED_CHARGE_SENTENCING_INDEX,
    chargeIds,
  );
  const judgeIndex = await insertJudgeSentencingIndex(
    trx,
    SEED_PUBLISHED_RUN_ID,
    PUBLISHED_JUDGE_SENTENCING_INDEX,
    chargeIds,
    judgeIds,
  );

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
    'analytics.charge_sentencing_index_summaries': chargeIndex.summaries,
    'analytics.charge_sentencing_index_aggregates': chargeIndex.categories,
    'analytics.charge_conviction_grade_aggregates': chargeIndex.grades,
    'analytics.judge_sentencing_index_summaries': judgeIndex.summaries,
    'analytics.judge_sentencing_index_aggregates': judgeIndex.categories,
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

// Task 35.2: index-cell inserts. Wedge count/percentage are derived here so
// the stored wedge identity (sentenced + wedge = convictions) holds by
// construction; created_at pins to the shared constant so re-runs stay
// content-identical (only surrogate ids regenerate).

function indexSummaryValues(
  runId: string,
  seed: ChargeSentencingIndexSeed | JudgeSentencingIndexSeed,
) {
  const wedge = seed.convictions - seed.sentencedConvictions;
  return {
    aggregate_run_id: runId,
    convictions: seed.convictions,
    sentenced_convictions: seed.sentencedConvictions,
    wedge_count: wedge,
    wedge_percentage: percentage1Of(wedge, seed.convictions),
    is_thin_data: seed.isThinData,
    date_range_start: seed.dateRange.start,
    date_range_end: seed.dateRange.end,
    taxonomy_version: TAXONOMY_VERSION,
    created_at: SEED_AGGREGATE_CREATED_AT,
  };
}

function indexCategoryValues(
  runId: string,
  seed: ChargeSentencingIndexSeed | JudgeSentencingIndexSeed,
) {
  return seed.categories.map((category) => ({
    aggregate_run_id: runId,
    category_code: category.code,
    conviction_count: category.convictionCount,
    percentage_of_sentenced: percentage1Of(category.convictionCount, seed.sentencedConvictions),
    median_min_days: category.medianMinDays ?? null,
    median_max_days: category.medianMaxDays ?? null,
    min_assumed_percentage: category.minAssumedPercentage ?? null,
    taxonomy_version: TAXONOMY_VERSION,
    created_at: SEED_AGGREGATE_CREATED_AT,
  }));
}

async function insertChargeSentencingIndex(
  trx: Transaction<Database>,
  runId: string,
  seeds: readonly ChargeSentencingIndexSeed[],
  chargeIds: Map<string, string>,
): Promise<{ summaries: number; categories: number; grades: number }> {
  const summaryRows = seeds.map((seed) => ({
    charge_id: requireId(chargeIds, seed.chargeSlug),
    ...indexSummaryValues(runId, seed),
  }));
  const categoryRows = seeds.flatMap((seed) =>
    indexCategoryValues(runId, seed).map((row) => ({
      charge_id: requireId(chargeIds, seed.chargeSlug),
      ...row,
    })),
  );
  const gradeRows = seeds.flatMap((seed) =>
    seed.grades.map(({ grade, count }) => ({
      aggregate_run_id: runId,
      charge_id: requireId(chargeIds, seed.chargeSlug),
      grade,
      conviction_count: count,
      percentage_of_convictions: percentage1Of(count, seed.convictions),
      taxonomy_version: TAXONOMY_VERSION,
      created_at: SEED_AGGREGATE_CREATED_AT,
    })),
  );

  if (summaryRows.length > 0) {
    await trx
      .insertInto('analytics.charge_sentencing_index_summaries')
      .values(summaryRows)
      .execute();
  }
  if (categoryRows.length > 0) {
    await trx
      .insertInto('analytics.charge_sentencing_index_aggregates')
      .values(categoryRows)
      .execute();
  }
  if (gradeRows.length > 0) {
    await trx
      .insertInto('analytics.charge_conviction_grade_aggregates')
      .values(gradeRows)
      .execute();
  }
  return {
    summaries: summaryRows.length,
    categories: categoryRows.length,
    grades: gradeRows.length,
  };
}

async function insertJudgeSentencingIndex(
  trx: Transaction<Database>,
  runId: string,
  seeds: readonly JudgeSentencingIndexSeed[],
  chargeIds: Map<string, string>,
  judgeIds: Map<string, string>,
): Promise<{ summaries: number; categories: number }> {
  const summaryRows = seeds.map((seed) => ({
    charge_id: requireId(chargeIds, seed.chargeSlug),
    judge_id: requireId(judgeIds, seed.judgeSlug),
    ...indexSummaryValues(runId, seed),
  }));
  const categoryRows = seeds.flatMap((seed) =>
    indexCategoryValues(runId, seed).map((row) => ({
      charge_id: requireId(chargeIds, seed.chargeSlug),
      judge_id: requireId(judgeIds, seed.judgeSlug),
      ...row,
    })),
  );

  if (summaryRows.length > 0) {
    await trx
      .insertInto('analytics.judge_sentencing_index_summaries')
      .values(summaryRows)
      .execute();
  }
  if (categoryRows.length > 0) {
    await trx
      .insertInto('analytics.judge_sentencing_index_aggregates')
      .values(categoryRows)
      .execute();
  }
  return { summaries: summaryRows.length, categories: categoryRows.length };
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
