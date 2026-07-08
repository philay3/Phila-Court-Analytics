import type { CreateTableBuilder, Kysely } from 'kysely';
import { sql } from 'kysely';

// Analytics-layer tables backing the Sprint 2 public result endpoints:
// `analytics.aggregate_runs` (run bookkeeping) plus four aggregate tables
// (charge/judge x outcome/sentencing). analytics.* holds public aggregate
// data only — no defendant columns, docket numbers, source-document
// references, or parsed/fact record references.
//
// aggregate_runs is mutable (status transitions), so it gets updated_at and
// reuses `public.set_updated_at()` from the 6.1 migration — the function is
// owned there and must never be recreated or dropped here. Aggregate rows are
// immutable: created_at only, no updated_at, no trigger.
//
// Publication model: a run is "active published" iff published_at IS NOT NULL
// AND invalidated_at IS NULL. The partial unique index over the constant
// expression `(true)` allows at most one row matching that predicate.
//
// taxonomy_version and category_code are plain text — the taxonomy is
// package-only through Sprint 2; DB taxonomy tables arrive in Sprint 7.
//
// FKs are default NO ACTION, never CASCADE: deleting a ref row must never
// silently delete published aggregates (ref rows deactivate via is_active).
//
// Unique constraint names abbreviate the column list (run/charge/judge/
// category) — the full-column-name convention would exceed Postgres's 63-char
// identifier limit (see db/README.md).
//
// `down` drops the four aggregate tables first, then the trigger and
// aggregate_runs (FK-safe order, plain drops, no CASCADE).

interface AggregateTableSpec {
  name: string;
  hasJudgeId: boolean;
  sampleSizeColumn: 'sample_size' | 'sentencing_sample_size';
}

const AGGREGATE_TABLES: AggregateTableSpec[] = [
  { name: 'charge_outcome_aggregates', hasJudgeId: false, sampleSizeColumn: 'sample_size' },
  {
    name: 'charge_sentencing_aggregates',
    hasJudgeId: false,
    sampleSizeColumn: 'sentencing_sample_size',
  },
  { name: 'judge_outcome_aggregates', hasJudgeId: true, sampleSizeColumn: 'sample_size' },
  {
    name: 'judge_sentencing_aggregates',
    hasJudgeId: true,
    sampleSizeColumn: 'sentencing_sample_size',
  },
];

async function createAggregateTable(db: Kysely<unknown>, spec: AggregateTableSpec): Promise<void> {
  const { name, hasJudgeId, sampleSizeColumn } = spec;

  // Widened builder type: reassignment across the judge_id branch would
  // otherwise pin the column union to the first three columns, rejecting
  // 'judge_id' in addUniqueConstraint below.
  let table: CreateTableBuilder<string, string> = db.schema
    .createTable(`analytics.${name}`)
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('aggregate_run_id', 'uuid', (col) => col.notNull())
    .addColumn('charge_id', 'uuid', (col) => col.notNull());

  if (hasJudgeId) {
    table = table.addColumn('judge_id', 'uuid', (col) => col.notNull());
  }

  table = table
    .addColumn('category_code', 'text', (col) => col.notNull())
    .addColumn('count', 'integer', (col) => col.notNull())
    .addColumn('percentage', sql`numeric(5, 2)`, (col) => col.notNull())
    .addColumn(sampleSizeColumn, 'integer', (col) => col.notNull())
    .addColumn('date_range_start', 'date', (col) => col.notNull())
    .addColumn('date_range_end', 'date', (col) => col.notNull())
    .addColumn('is_thin_data', 'boolean', (col) => col.notNull())
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

  table = table
    .addUniqueConstraint(
      hasJudgeId ? `${name}_run_charge_judge_category_key` : `${name}_run_charge_category_key`,
      hasJudgeId
        ? ['aggregate_run_id', 'charge_id', 'judge_id', 'category_code']
        : ['aggregate_run_id', 'charge_id', 'category_code'],
    )
    .addCheckConstraint(`${name}_count_check`, sql`count >= 0`)
    .addCheckConstraint(`${name}_percentage_check`, sql`percentage BETWEEN 0 AND 100`)
    .addCheckConstraint(`${name}_${sampleSizeColumn}_check`, sql`${sql.ref(sampleSizeColumn)} > 0`)
    .addCheckConstraint(`${name}_date_range_check`, sql`date_range_start <= date_range_end`);

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
  await db.schema
    .createTable('analytics.aggregate_runs')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('status', 'text', (col) => col.notNull())
    .addColumn('started_at', 'timestamptz', (col) => col.notNull())
    .addColumn('completed_at', 'timestamptz')
    .addColumn('published_at', 'timestamptz')
    .addColumn('invalidated_at', 'timestamptz')
    .addColumn('invalidated_reason', 'text')
    .addColumn('parser_version', 'text')
    .addColumn('taxonomy_version', 'text', (col) => col.notNull())
    .addColumn('data_range_start', 'date', (col) => col.notNull())
    .addColumn('data_range_end', 'date', (col) => col.notNull())
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addColumn('updated_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addCheckConstraint(
      'aggregate_runs_status_check',
      sql`status IN ('in_progress', 'completed', 'failed')`,
    )
    .addCheckConstraint('aggregate_runs_data_range_check', sql`data_range_start <= data_range_end`)
    .addCheckConstraint(
      'aggregate_runs_completed_at_check',
      sql`(status <> 'completed') OR (completed_at IS NOT NULL)`,
    )
    .addCheckConstraint(
      'aggregate_runs_published_at_check',
      sql`published_at IS NULL OR status = 'completed'`,
    )
    .addCheckConstraint(
      'aggregate_runs_invalidated_at_check',
      sql`invalidated_at IS NULL OR published_at IS NOT NULL`,
    )
    .addCheckConstraint(
      'aggregate_runs_invalidated_reason_check',
      sql`(invalidated_at IS NULL) = (invalidated_reason IS NULL)`,
    )
    .execute();

  await sql`
    CREATE UNIQUE INDEX aggregate_runs_active_published_idx
    ON analytics.aggregate_runs ((true))
    WHERE published_at IS NOT NULL AND invalidated_at IS NULL
  `.execute(db);

  await sql`
    CREATE TRIGGER set_updated_at BEFORE UPDATE ON analytics.aggregate_runs
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()
  `.execute(db);

  for (const spec of AGGREGATE_TABLES) {
    await createAggregateTable(db, spec);
  }
}

export async function down(db: Kysely<unknown>): Promise<void> {
  for (const spec of [...AGGREGATE_TABLES].reverse()) {
    await db.schema.dropTable(`analytics.${spec.name}`).execute();
  }
  await sql`DROP TRIGGER set_updated_at ON analytics.aggregate_runs`.execute(db);
  await db.schema.dropTable('analytics.aggregate_runs').execute();
}
