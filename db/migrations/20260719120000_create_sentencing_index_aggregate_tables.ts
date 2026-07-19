import type { CreateTableBuilder, Kysely } from 'kysely';
import { sql } from 'kysely';

// Task 35.1: conviction-grain sentencing-index aggregate tables, charge grain
// and charge x judge grain. Five tables under the Phase 35 design-gate rulings:
//
// - *_sentencing_index_summaries: one row per (run, charge[, judge]) cell —
//   convictions, sentenced convictions, wedge (convictions with no
//   public-eligible sentencing component; ruling 1: exclude-with-disclosure,
//   never counted as "no penalty"), wedge percentage, and the thin flag keyed
//   on sentenced convictions (ruling 4). The summary row is the servable
//   anchor: a cell with convictions but ZERO sentenced convictions still gets
//   a row (wedge = 100%), which is why `convictions` carries the `> 0` CHECK
//   (the zero-sample convention of the Sprint 2 tables applied to the
//   conviction denominator) while `sentenced_convictions` may be 0. The date
//   range is the cell's conviction disposition-date envelope.
// - *_sentencing_index_aggregates: one row per (run, cell, category) that
//   OCCURS (absence = zero; ruling 5 — categories come from the taxonomy, none
//   hardcoded). Conviction-grain counts (a conviction counts once per category
//   it has >= 1 public-eligible component of), percentage of sentenced
//   convictions, and — for duration-bearing categories only — the
//   component-grain median pair in DAYS plus the min_assumed share
//   (ruling 3; month conversion is an API-layer concern, never stored). The
//   three duration columns are all-present-or-all-null by CHECK.
// - charge_conviction_grade_aggregates: charge grain only (ruling 2 — judge
//   grain carries no grade mix); one row per (run, charge, grade) with NULL
//   parsed grades folded into an explicit 'ungraded' bucket, counts and
//   percentage of convictions.
//
// House conventions follow the Sprint 2 aggregate tables: UUID PKs, run FK
// (NO ACTION, never CASCADE), unique constraint leading with aggregate_run_id
// (doubling as the run index), charge_id/judge_id secondary indexes, immutable
// rows (created_at only, no updated_at/trigger; delete-and-reinsert per run),
// percentages numeric(4,1) BETWEEN 0 AND 100 (1-decimal wire precision per the
// Phase 35 gate — stored precision = displayed precision).
//
// Unique constraint names abbreviate the column list where the full form would
// exceed Postgres's 63-char identifier limit (db/README.md): the judge index
// table uses `run_cell` for (aggregate_run_id, charge_id, judge_id).
//
// `down` drops the five tables only (no shared objects are created here).

const PCT = sql`numeric(4, 1)`;
const MEDIAN_DAYS = sql`numeric(6, 1)`;

function withSummaryColumns(
  table: CreateTableBuilder<string, string>,
  name: string,
): CreateTableBuilder<string, string> {
  return table
    .addColumn('convictions', 'integer', (col) => col.notNull())
    .addColumn('sentenced_convictions', 'integer', (col) => col.notNull())
    .addColumn('wedge_count', 'integer', (col) => col.notNull())
    .addColumn('wedge_percentage', PCT, (col) => col.notNull())
    .addColumn('is_thin_data', 'boolean', (col) => col.notNull())
    .addColumn('date_range_start', 'date', (col) => col.notNull())
    .addColumn('date_range_end', 'date', (col) => col.notNull())
    .addCheckConstraint(`${name}_convictions_check`, sql`convictions > 0`)
    .addCheckConstraint(`${name}_sentenced_convictions_check`, sql`sentenced_convictions >= 0`)
    .addCheckConstraint(`${name}_wedge_count_check`, sql`wedge_count >= 0`)
    .addCheckConstraint(
      `${name}_wedge_identity_check`,
      sql`sentenced_convictions + wedge_count = convictions`,
    )
    .addCheckConstraint(`${name}_wedge_percentage_check`, sql`wedge_percentage BETWEEN 0 AND 100`)
    .addCheckConstraint(`${name}_date_range_check`, sql`date_range_start <= date_range_end`);
}

function withCategoryColumns(
  table: CreateTableBuilder<string, string>,
  name: string,
): CreateTableBuilder<string, string> {
  return table
    .addColumn('category_code', 'text', (col) => col.notNull())
    .addColumn('conviction_count', 'integer', (col) => col.notNull())
    .addColumn('percentage_of_sentenced', PCT, (col) => col.notNull())
    .addColumn('median_min_days', MEDIAN_DAYS)
    .addColumn('median_max_days', MEDIAN_DAYS)
    .addColumn('min_assumed_percentage', PCT)
    .addCheckConstraint(`${name}_conviction_count_check`, sql`conviction_count > 0`)
    .addCheckConstraint(
      `${name}_percentage_of_sentenced_check`,
      sql`percentage_of_sentenced BETWEEN 0 AND 100`,
    )
    .addCheckConstraint(
      `${name}_duration_columns_check`,
      sql`(median_min_days IS NULL) = (median_max_days IS NULL)
          AND (median_min_days IS NULL) = (min_assumed_percentage IS NULL)`,
    )
    .addCheckConstraint(
      `${name}_median_days_check`,
      sql`median_min_days IS NULL
          OR (median_min_days >= 0 AND median_min_days <= median_max_days)`,
    )
    .addCheckConstraint(
      `${name}_min_assumed_percentage_check`,
      sql`min_assumed_percentage IS NULL
          OR min_assumed_percentage BETWEEN 0 AND 100`,
    );
}

interface IndexTableSpec {
  name: string;
  hasJudgeId: boolean;
  kind: 'summary' | 'category' | 'grade';
  uniqueName: string;
  uniqueColumns: string[];
}

const INDEX_TABLES: IndexTableSpec[] = [
  {
    name: 'charge_sentencing_index_summaries',
    hasJudgeId: false,
    kind: 'summary',
    uniqueName: 'charge_sentencing_index_summaries_run_charge_key',
    uniqueColumns: ['aggregate_run_id', 'charge_id'],
  },
  {
    name: 'charge_sentencing_index_aggregates',
    hasJudgeId: false,
    kind: 'category',
    uniqueName: 'charge_sentencing_index_aggregates_run_charge_category_key',
    uniqueColumns: ['aggregate_run_id', 'charge_id', 'category_code'],
  },
  {
    name: 'charge_conviction_grade_aggregates',
    hasJudgeId: false,
    kind: 'grade',
    uniqueName: 'charge_conviction_grade_aggregates_run_charge_grade_key',
    uniqueColumns: ['aggregate_run_id', 'charge_id', 'grade'],
  },
  {
    name: 'judge_sentencing_index_summaries',
    hasJudgeId: true,
    kind: 'summary',
    uniqueName: 'judge_sentencing_index_summaries_run_charge_judge_key',
    uniqueColumns: ['aggregate_run_id', 'charge_id', 'judge_id'],
  },
  {
    name: 'judge_sentencing_index_aggregates',
    hasJudgeId: true,
    kind: 'category',
    // `run_cell` abbreviates (aggregate_run_id, charge_id, judge_id): the
    // full column list would exceed the 63-char identifier limit.
    uniqueName: 'judge_sentencing_index_aggregates_run_cell_category_key',
    uniqueColumns: ['aggregate_run_id', 'charge_id', 'judge_id', 'category_code'],
  },
];

async function createIndexTable(db: Kysely<unknown>, spec: IndexTableSpec): Promise<void> {
  const { name, hasJudgeId, kind } = spec;

  let table: CreateTableBuilder<string, string> = db.schema
    .createTable(`analytics.${name}`)
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('aggregate_run_id', 'uuid', (col) => col.notNull())
    .addColumn('charge_id', 'uuid', (col) => col.notNull());

  if (hasJudgeId) {
    table = table.addColumn('judge_id', 'uuid', (col) => col.notNull());
  }

  if (kind === 'summary') {
    table = withSummaryColumns(table, name);
  } else if (kind === 'category') {
    table = withCategoryColumns(table, name);
  } else {
    table = table
      .addColumn('grade', 'text', (col) => col.notNull())
      .addColumn('conviction_count', 'integer', (col) => col.notNull())
      .addColumn('percentage_of_convictions', PCT, (col) => col.notNull())
      .addCheckConstraint(`${name}_conviction_count_check`, sql`conviction_count > 0`)
      .addCheckConstraint(
        `${name}_percentage_of_convictions_check`,
        sql`percentage_of_convictions BETWEEN 0 AND 100`,
      );
  }

  table = table
    .addColumn('taxonomy_version', 'text', (col) => col.notNull())
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addForeignKeyConstraint(
      `${name}_aggregate_run_id_fkey`,
      ['aggregate_run_id'],
      'analytics.aggregate_runs',
      ['id'],
    )
    .addForeignKeyConstraint(`${name}_charge_id_fkey`, ['charge_id'], 'ref.normalized_charges', [
      'id',
    ]);

  if (hasJudgeId) {
    table = table.addForeignKeyConstraint(
      `${name}_judge_id_fkey`,
      ['judge_id'],
      'ref.normalized_judges',
      ['id'],
    );
  }

  table = table.addUniqueConstraint(spec.uniqueName, spec.uniqueColumns);

  await table.execute();

  await db.schema
    .createIndex(`${name}_charge_id_idx`)
    .on(`analytics.${name}`)
    .column('charge_id')
    .execute();

  if (hasJudgeId) {
    await db.schema
      .createIndex(`${name}_judge_id_idx`)
      .on(`analytics.${name}`)
      .column('judge_id')
      .execute();
  }
}

export async function up(db: Kysely<unknown>): Promise<void> {
  for (const spec of INDEX_TABLES) {
    await createIndexTable(db, spec);
  }
}

export async function down(db: Kysely<unknown>): Promise<void> {
  for (const spec of [...INDEX_TABLES].reverse()) {
    await db.schema.dropTable(`analytics.${spec.name}`).execute();
  }
}
