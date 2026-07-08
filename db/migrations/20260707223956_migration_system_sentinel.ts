import type { Kysely } from 'kysely';

// Sentinel migration whose only purpose is proving the migration runner
// round-trips (task 2.2). Task 2.3 (domain schemas) may remove or supersede it.

export async function up(db: Kysely<unknown>): Promise<void> {
  await db.schema
    .createTable('migration_sentinel')
    .addColumn('id', 'integer', (col) => col.primaryKey())
    .execute();
}

export async function down(db: Kysely<unknown>): Promise<void> {
  await db.schema.dropTable('migration_sentinel').execute();
}
