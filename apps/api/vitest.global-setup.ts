import { Kysely, PostgresDialect } from 'kysely';
import pg from 'pg';
import { seedAggregates, seedReference, type Database } from '@pca/db';
import { assertTestDatabaseUrl } from '@pca/db/test-db-guard';

/**
 * Seeds reference + aggregate data ONCE per test run, before any suite
 * (task 8.2). Replaces the per-suite self-seeding beforeAll calls, which
 * raced each other: seedAggregates is delete-and-reinsert per run, so two
 * DB-backed suites seeding concurrently could observe each other's window
 * of deleted aggregate rows.
 *
 * DATABASE_URL is loaded by vitest.config.ts (root .env) before this module
 * runs; without it the DB-backed suites skip themselves and seeding is
 * skipped too. When it IS set, any connection or seeding error must fail the
 * whole test run — never catch-and-continue, so a broken DB environment can
 * not silently turn every DB-backed suite into a skip while CI stays green.
 */
export default async function globalSetup(): Promise<void> {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    console.warn('vitest globalSetup: DATABASE_URL not set — skipping database seeding.');
    return;
  }

  // Test-database guard (task 29.2): seeding below runs via direct function
  // calls, bypassing the 29.1-guarded `db:seed` script — so the name-shaped
  // check happens here, before any pool or connection exists. A non-test
  // database name (e.g. the live DB auto-loaded from the root .env) aborts
  // the whole test run before any write.
  assertTestDatabaseUrl(connectionString, 'api vitest globalSetup');

  const db = new Kysely<Database>({
    dialect: new PostgresDialect({ pool: new pg.Pool({ connectionString }) }),
  });
  try {
    console.info('vitest globalSetup: seeding reference and aggregate data…');
    await seedReference(db);
    await seedAggregates(db);
    console.info('vitest globalSetup: seeding complete.');
  } finally {
    await db.destroy();
  }
}
