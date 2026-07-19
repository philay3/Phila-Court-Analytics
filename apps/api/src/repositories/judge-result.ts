import { sql, type Kysely } from 'kysely';
import type { PublicApiDatabase } from '../db.js';
import type {
  ChargeOutcomeAggregateRow,
  ChargeSentencingAggregateRow,
  SentencingIndexCategoryAggregateRow,
  SentencingIndexSummaryAggregateRow,
} from './charge-result.js';

export interface JudgeRow {
  id: string;
  slug: string;
  display_name: string;
}

const JUDGE_COLUMNS = ['id', 'slug', 'display_name'] as const;

function selectActiveJudges(db: Kysely<PublicApiDatabase>) {
  return db.selectFrom('ref.normalized_judges').where('is_active', '=', true);
}

/**
 * id-mode judge lookup. Callers must pass a regex-validated UUID: Postgres
 * raises a cast error (not a miss) for a non-UUID string. Deliberately
 * separate from findActiveJudgeBySlug — no fallthrough between the modes,
 * mirroring the charge lookups.
 */
export async function findActiveJudgeById(
  db: Kysely<PublicApiDatabase>,
  id: string,
): Promise<JudgeRow | undefined> {
  return selectActiveJudges(db).where('id', '=', id).select(JUDGE_COLUMNS).executeTakeFirst();
}

export async function findActiveJudgeBySlug(
  db: Kysely<PublicApiDatabase>,
  slug: string,
): Promise<JudgeRow | undefined> {
  return selectActiveJudges(db).where('slug', '=', slug).select(JUDGE_COLUMNS).executeTakeFirst();
}

// Judge-scoped distribution reads mirror the charge-only ones: scoped to one
// run id (the unpublished decoy and any invalidated run are excluded by
// construction) plus the charge/judge pair. The row shapes are identical to
// the charge aggregate tables', so the exported 8.1 row types are reused.
// category_code ordering is for determinism only; presentation order
// (taxonomy sortOrder) is applied in the service.

export async function getJudgeOutcomeRows(
  db: Kysely<PublicApiDatabase>,
  runId: string,
  chargeId: string,
  judgeId: string,
): Promise<ChargeOutcomeAggregateRow[]> {
  return db
    .selectFrom('analytics.judge_outcome_aggregates')
    .where('aggregate_run_id', '=', runId)
    .where('charge_id', '=', chargeId)
    .where('judge_id', '=', judgeId)
    .select(['category_code', 'count', 'percentage', 'sample_size', 'is_thin_data'])
    .orderBy('category_code')
    .execute();
}

export async function getJudgeSentencingRows(
  db: Kysely<PublicApiDatabase>,
  runId: string,
  chargeId: string,
  judgeId: string,
): Promise<ChargeSentencingAggregateRow[]> {
  return db
    .selectFrom('analytics.judge_sentencing_aggregates')
    .where('aggregate_run_id', '=', runId)
    .where('charge_id', '=', chargeId)
    .where('judge_id', '=', judgeId)
    .select(['category_code', 'count', 'percentage', 'sentencing_sample_size', 'is_thin_data'])
    .orderBy('category_code')
    .execute();
}

// Task 35.2 sentencing-index reads for the charge x judge cell, mirroring the
// charge-grain reads (row types reused). No grade read exists at this grain —
// ruling 2: the judge arm carries no grade mix.

export async function getJudgeSentencingIndexSummary(
  db: Kysely<PublicApiDatabase>,
  runId: string,
  chargeId: string,
  judgeId: string,
): Promise<SentencingIndexSummaryAggregateRow | undefined> {
  return db
    .selectFrom('analytics.judge_sentencing_index_summaries')
    .where('aggregate_run_id', '=', runId)
    .where('charge_id', '=', chargeId)
    .where('judge_id', '=', judgeId)
    .select([
      'convictions',
      'sentenced_convictions',
      'wedge_count',
      'wedge_percentage',
      'is_thin_data',
      sql<string>`date_range_start::text`.as('date_range_start'),
      sql<string>`date_range_end::text`.as('date_range_end'),
    ])
    .executeTakeFirst();
}

export async function getJudgeSentencingIndexCategoryRows(
  db: Kysely<PublicApiDatabase>,
  runId: string,
  chargeId: string,
  judgeId: string,
): Promise<SentencingIndexCategoryAggregateRow[]> {
  return db
    .selectFrom('analytics.judge_sentencing_index_aggregates')
    .where('aggregate_run_id', '=', runId)
    .where('charge_id', '=', chargeId)
    .where('judge_id', '=', judgeId)
    .select([
      'category_code',
      'conviction_count',
      'percentage_of_sentenced',
      'median_min_days',
      'median_max_days',
      'min_assumed_percentage',
    ])
    .orderBy('category_code')
    .execute();
}
