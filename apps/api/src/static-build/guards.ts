import { assertTestDatabaseUrl, dbNameFromUrl } from '@pca/db/test-db-guard';

/**
 * Static-build safeguards (task STATIC-2b, pin 11.3). Pure, name-shaped,
 * pre-connection, fail-closed — the 29.2 test-db-guard and 34.6 local-db-guard
 * patterns applied to the one path that reads the canonical database to
 * publish from it. Messages name the database and host only, never the URL,
 * which carries credentials.
 */

export type BuildMode = 'publish' | 'ci';

/** The only database publish mode may build from: the local canonical one. */
export const PUBLISH_DATABASE_NAME = 'pca';

const LOCAL_HOSTNAMES: ReadonlySet<string> = new Set(['localhost', '127.0.0.1', '::1']);

/** `--mode publish` or `--mode ci`; anything else (including no flag) refuses. */
export function parseBuildMode(argv: readonly string[]): BuildMode {
  const at = argv.indexOf('--mode');
  const value = at >= 0 ? argv[at + 1] : undefined;
  if (value === 'publish' || value === 'ci') {
    return value;
  }
  throw new Error(
    'a mode flag is required: `--mode publish` (the local canonical database) or ' +
      '`--mode ci` (a seeded test database). No flag, no build.',
  );
}

/** Hostname from a connection URL (IPv6 brackets stripped), or null when undeterminable. */
export function hostFromUrl(url: string): string | null {
  let hostname: string;
  try {
    hostname = new URL(url).hostname;
  } catch {
    return null;
  }
  const bare = hostname.replace(/^\[/, '').replace(/\]$/, '');
  return bare.length > 0 ? bare.toLowerCase() : null;
}

/**
 * Throws unless `url` is acceptable for `mode`; returns the database name on
 * success so the caller can compare it with `SELECT current_database()`.
 *
 *   publish → the database name is exactly `pca` AND the host is local;
 *   ci      → a test-shaped name per the 29.2 guard (contains "test", or
 *             exactly `pca_ci`).
 */
export function assertDatabaseUrlForMode(url: string | undefined, mode: BuildMode): string {
  if (!url) {
    throw new Error('DATABASE_URL is not set; the build reads the database through the API.');
  }
  const dbname = dbNameFromUrl(url);
  if (dbname === null) {
    throw new Error(
      'refusing to run — the database name could not be determined from DATABASE_URL (fail-closed).',
    );
  }
  if (mode === 'publish') {
    if (dbname !== PUBLISH_DATABASE_NAME) {
      throw new Error(
        `publish mode refuses database "${dbname}" — it builds only from the local canonical ` +
          `database "${PUBLISH_DATABASE_NAME}". Use --mode ci for a test database.`,
      );
    }
    const host = hostFromUrl(url);
    if (host === null || !LOCAL_HOSTNAMES.has(host)) {
      throw new Error(
        `publish mode refuses host "${host ?? '(undetermined)'}" for database "${dbname}" — the ` +
          'canonical database must be reached on a local host (localhost, 127.0.0.1, or ::1).',
      );
    }
    return dbname;
  }
  assertTestDatabaseUrl(url, 'static-build (ci)');
  return dbname;
}

/** First eight characters of a run id for console output; never the whole id in errors. */
export function shortRunId(id: string | undefined): string {
  return id ? id.slice(0, 8) : '(none)';
}

/** Every materialized payload that carries a run id must carry the pinned one. */
export function assertPinnedRunId(pinned: string, actual: string | undefined, where: string): void {
  if (actual !== pinned) {
    throw new Error(
      `${where} carries aggregateRunId ${shortRunId(actual)} but the pinned run is ` +
        `${shortRunId(pinned)} — the published run changed mid-build; refusing to emit.`,
    );
  }
}
