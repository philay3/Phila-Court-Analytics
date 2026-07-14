import { assertTestDatabaseUrl } from './src/test-db-guard.js';

/**
 * Test-database guard at the db-package test entry (task 29.2). The seed
 * suites (seeds/*.test.ts) call seedReference/roster seed functions directly
 * against DATABASE_URL, and the sweep suite creates scratch databases from
 * it — none of which pass through the 29.1-guarded `db:seed` script. A
 * throwing globalSetup aborts the entire vitest run before any suite
 * executes, so a DATABASE_URL naming a non-test database (e.g. auto-loaded
 * from the root .env) fails loudly before any write.
 *
 * When DATABASE_URL is unset, the DB-backed suites skip themselves with
 * their own warnings — nothing to guard, so this stays silent.
 */
export default function globalSetup(): void {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    return;
  }
  assertTestDatabaseUrl(connectionString, 'db vitest globalSetup');
}
