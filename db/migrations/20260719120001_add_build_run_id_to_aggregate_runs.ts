import type { Kysely } from 'kysely';

// Task 35.1: persist the resolved fact build-run id on analytics.aggregate_runs
// (the ops-track item — the generator already resolves it; now it is written,
// not just printed). Nullable: historical rows stay NULL; every new run writes
// it, and validation asserts presence on new runs.
//
// DELIBERATELY NO FOREIGN KEY to fact.fact_build_runs — do not "fix" this.
// analytics.aggregate_runs is part of the ADR 0004 nine-table (now
// fourteen-table) public dump/restore set, but the fact schema is NOT: the
// production database is restored with empty fact.* tables, so an FK here
// would make every restored aggregate_runs row violate the constraint and
// break the prod data path. The column is bookkeeping provenance, enforced by
// the generator and validator, never referentially.

export async function up(db: Kysely<unknown>): Promise<void> {
  await db.schema
    .alterTable('analytics.aggregate_runs')
    .addColumn('build_run_id', 'uuid')
    .execute();
}

export async function down(db: Kysely<unknown>): Promise<void> {
  await db.schema.alterTable('analytics.aggregate_runs').dropColumn('build_run_id').execute();
}
