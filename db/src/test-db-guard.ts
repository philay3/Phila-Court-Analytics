/**
 * Test-database guard (task 29.2): structural enforcement of the rule that
 * test runs which write `aggregate_runs` or seed data only ever target a
 * test database.
 *
 * Name-shaped and PRE-CONNECTION: the check parses the database name out of
 * the connection URL and throws before any pool or connection is created, so
 * a mispointed DATABASE_URL (e.g. the root .env pointing at the live
 * database — the 28.2 incident vector) fails loudly before any write. This
 * complements the 29.1 seed-guard, which is data-shaped and only covers the
 * `db:seed` script path; vitest global-setups seed via direct function calls
 * and are guarded here instead.
 *
 * Pattern (29.2 plan-review ruling): a database name is a test name iff it
 * contains "test" (case-insensitive) — the established
 * PIPELINE_TEST_DATABASE_URL dbname convention (services/pipeline
 * tests/test_load.py guard 2) — OR is exactly `pca_ci`, the CI service
 * database. Fail-closed: a URL whose database name cannot be determined is
 * rejected.
 *
 * Exposed via the dedicated `@pca/db/test-db-guard` subpath (the
 * @pca/shared/forbidden-scan precedent) so test tooling stays off the main
 * runtime surface the API consumes.
 *
 * Error messages name the offending DBNAME ONLY — never the connection URL,
 * which can carry credentials and may end up in public CI logs.
 */

/** CI service databases that are test targets but do not contain "test". */
const CI_DBNAME_ALLOWLIST: ReadonlySet<string> = new Set(['pca_ci']);

/** Pure predicate: is `dbname` positively a test-database name? */
export function isTestDbName(dbname: string): boolean {
  return /test/i.test(dbname) || CI_DBNAME_ALLOWLIST.has(dbname);
}

/**
 * Extracts the database name from a Postgres connection URL, or returns null
 * when it cannot be determined (unparseable URL, empty path) — callers treat
 * null as a refusal (fail-closed).
 */
export function dbNameFromUrl(url: string): string | null {
  let pathname: string;
  try {
    pathname = new URL(url).pathname;
  } catch {
    return null;
  }
  const dbname = decodeURIComponent(pathname.replace(/^\//, ''));
  return dbname.length > 0 ? dbname : null;
}

/**
 * Throws unless `url` names a test database. `context` prefixes the message
 * so the failing entry path is identifiable (e.g. "api vitest globalSetup").
 * The thrown message includes the database name only, never the URL.
 */
export function assertTestDatabaseUrl(url: string, context: string): void {
  const dbname = dbNameFromUrl(url);
  if (dbname === null) {
    throw new Error(
      `${context}: refusing to run — the database name could not be determined ` +
        'from DATABASE_URL (fail-closed). Point DATABASE_URL at a dedicated ' +
        'test database (e.g. pca_test).',
    );
  }
  if (!isTestDbName(dbname)) {
    throw new Error(
      `${context}: refusing to run against database "${dbname}" — the name does ` +
        'not match the test-database pattern (contains "test", or is the CI ' +
        'database pca_ci). DB-backed test runs seed reference data and ' +
        'delete-and-reinsert aggregate rows, and must never touch a live ' +
        'database. Point DATABASE_URL at a dedicated test database ' +
        '(e.g. pca_test).',
    );
  }
}
