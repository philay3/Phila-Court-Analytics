import { sql, type Kysely } from 'kysely';
import type { PublicApiDatabase } from '../db.js';

export interface ActivePublishedRunRow {
  id: string;
  taxonomy_version: string;
  published_at: Date;
  data_range_start: string;
  data_range_end: string;
}

export interface ChargeRow {
  id: string;
  slug: string;
  display_name: string;
  statute_code: string | null;
  grade: string | null;
}

export interface ChargeOutcomeAggregateRow {
  category_code: string;
  count: number;
  percentage: string;
  sample_size: number;
  is_thin_data: boolean;
}

export interface ChargeSentencingAggregateRow {
  category_code: string;
  count: number;
  percentage: string;
  sentencing_sample_size: number;
  is_thin_data: boolean;
}

/**
 * Resolves the single active published aggregate run: published, not
 * invalidated. The 6.2 partial unique index guarantees at most one such row;
 * the ORDER BY + LIMIT 1 keep the query deterministic even if that invariant
 * were ever violated. Date columns are cast to text in SQL so the calendar
 * date can never shift through the driver's Date/timezone handling.
 */
export async function findActivePublishedRun(
  db: Kysely<PublicApiDatabase>,
): Promise<ActivePublishedRunRow | undefined> {
  return (
    db
      .selectFrom('analytics.aggregate_runs')
      .where('published_at', 'is not', null)
      .where('invalidated_at', 'is', null)
      .select([
        'id',
        'taxonomy_version',
        'published_at',
        sql<string>`data_range_start::text`.as('data_range_start'),
        sql<string>`data_range_end::text`.as('data_range_end'),
      ])
      // The WHERE clause guarantees published_at IS NOT NULL; Kysely cannot
      // infer that, so narrow the selected type explicitly.
      .$narrowType<{ published_at: Date }>()
      .orderBy('published_at', 'desc')
      .orderBy('id')
      .limit(1)
      .executeTakeFirst()
  );
}

const CHARGE_COLUMNS = ['id', 'slug', 'display_name', 'statute_code', 'grade'] as const;

function selectActiveCharges(db: Kysely<PublicApiDatabase>) {
  return db.selectFrom('ref.normalized_charges').where('is_active', '=', true);
}

/**
 * id-mode charge lookup. Callers must pass a regex-validated UUID: Postgres
 * raises a cast error (not a miss) for a non-UUID string. Deliberately
 * separate from findActiveChargeBySlug — no fallthrough between the modes.
 */
export async function findActiveChargeById(
  db: Kysely<PublicApiDatabase>,
  id: string,
): Promise<ChargeRow | undefined> {
  return selectActiveCharges(db).where('id', '=', id).select(CHARGE_COLUMNS).executeTakeFirst();
}

export async function findActiveChargeBySlug(
  db: Kysely<PublicApiDatabase>,
  slug: string,
): Promise<ChargeRow | undefined> {
  return selectActiveCharges(db).where('slug', '=', slug).select(CHARGE_COLUMNS).executeTakeFirst();
}

// Both distribution reads are scoped to one run id — the unpublished decoy
// and any invalidated run are excluded by construction, not by filtering.
// Rows come back in category_code order for determinism only; presentation
// order (taxonomy sortOrder) is applied in the service.

export async function getChargeOutcomeRows(
  db: Kysely<PublicApiDatabase>,
  runId: string,
  chargeId: string,
): Promise<ChargeOutcomeAggregateRow[]> {
  return db
    .selectFrom('analytics.charge_outcome_aggregates')
    .where('aggregate_run_id', '=', runId)
    .where('charge_id', '=', chargeId)
    .select(['category_code', 'count', 'percentage', 'sample_size', 'is_thin_data'])
    .orderBy('category_code')
    .execute();
}

// Task 35.2 sentencing-index reads (the 35.1 conviction-grain tables). Same
// scoping rule as the distribution reads; numerics arrive as `pg` strings and
// are converted in the service (months for medians, Number() for
// percentages); summary dates are cast to text so the calendar date can never
// shift through the driver's Date/timezone handling.

export interface SentencingIndexSummaryAggregateRow {
  convictions: number;
  sentenced_convictions: number;
  wedge_count: number;
  wedge_percentage: string;
  is_thin_data: boolean;
  date_range_start: string;
  date_range_end: string;
}

export interface SentencingIndexCategoryAggregateRow {
  category_code: string;
  conviction_count: number;
  percentage_of_sentenced: string;
  median_min_days: string | null;
  median_max_days: string | null;
  min_assumed_percentage: string | null;
}

export interface ConvictionGradeAggregateRow {
  grade: string;
  conviction_count: number;
  percentage_of_convictions: string;
}

const INDEX_SUMMARY_COLUMNS = [
  'convictions',
  'sentenced_convictions',
  'wedge_count',
  'wedge_percentage',
  'is_thin_data',
] as const;

const INDEX_CATEGORY_COLUMNS = [
  'category_code',
  'conviction_count',
  'percentage_of_sentenced',
  'median_min_days',
  'median_max_days',
  'min_assumed_percentage',
] as const;

/**
 * The cell's summary row — the servable anchor of the index. At most one row
 * exists per (run, charge) by unique constraint; absence IS the absent arm
 * (a run predating the population and a zero-conviction cell alike).
 */
export async function getChargeSentencingIndexSummary(
  db: Kysely<PublicApiDatabase>,
  runId: string,
  chargeId: string,
): Promise<SentencingIndexSummaryAggregateRow | undefined> {
  return db
    .selectFrom('analytics.charge_sentencing_index_summaries')
    .where('aggregate_run_id', '=', runId)
    .where('charge_id', '=', chargeId)
    .select([
      ...INDEX_SUMMARY_COLUMNS,
      sql<string>`date_range_start::text`.as('date_range_start'),
      sql<string>`date_range_end::text`.as('date_range_end'),
    ])
    .executeTakeFirst();
}

export async function getChargeSentencingIndexCategoryRows(
  db: Kysely<PublicApiDatabase>,
  runId: string,
  chargeId: string,
): Promise<SentencingIndexCategoryAggregateRow[]> {
  return db
    .selectFrom('analytics.charge_sentencing_index_aggregates')
    .where('aggregate_run_id', '=', runId)
    .where('charge_id', '=', chargeId)
    .select([...INDEX_CATEGORY_COLUMNS])
    .orderBy('category_code')
    .execute();
}

/**
 * Grade-mix rows, charge grain only (ruling 2). Served dominant-first:
 * conviction_count DESC with grade ASC as the deterministic tiebreak — this
 * IS the presentation order (grades have no taxonomy sortOrder), and the
 * ungraded bucket rides wherever its count puts it.
 */
export async function getChargeConvictionGradeRows(
  db: Kysely<PublicApiDatabase>,
  runId: string,
  chargeId: string,
): Promise<ConvictionGradeAggregateRow[]> {
  return db
    .selectFrom('analytics.charge_conviction_grade_aggregates')
    .where('aggregate_run_id', '=', runId)
    .where('charge_id', '=', chargeId)
    .select(['grade', 'conviction_count', 'percentage_of_convictions'])
    .orderBy('conviction_count', 'desc')
    .orderBy('grade')
    .execute();
}

export async function getChargeSentencingRows(
  db: Kysely<PublicApiDatabase>,
  runId: string,
  chargeId: string,
): Promise<ChargeSentencingAggregateRow[]> {
  return db
    .selectFrom('analytics.charge_sentencing_aggregates')
    .where('aggregate_run_id', '=', runId)
    .where('charge_id', '=', chargeId)
    .select(['category_code', 'count', 'percentage', 'sentencing_sample_size', 'is_thin_data'])
    .orderBy('category_code')
    .execute();
}
