/**
 * Local-database guard (task 34.6): structural enforcement that local db
 * entry points only ever target a LOCAL database host.
 *
 * Host-shaped and PRE-CONNECTION — the 29.2 test-db-guard pattern
 * transplanted to the host axis. The 29.2 guard covers test runs and the
 * 29.1 seed-guard is data-shaped; the surface neither covers is the
 * migrator: every `db:migrate:*` script auto-loads the root .env
 * (`--env-file-if-exists=../.env`) and connects to whatever DATABASE_URL
 * arrives, so a mispointed .env (the 28.2 incident vector) could silently
 * run schema changes against the production database. This guard parses the
 * host out of the connection URL and throws before any pool or connection
 * is created.
 *
 * A host is local iff it is `localhost`, `127.0.0.1`, or `::1`. Fail-closed:
 * a URL whose host cannot be determined (unparseable, or empty — the
 * unix-socket shorthand) is rejected; spell the local host explicitly.
 *
 * Override (34.6 plan-gate ruling): setting PCA_REMOTE_DB_OK=1 (exact value)
 * permits a remote host — but ONLY where the call site opts in via
 * `allowRemoteOverride`. The migrator opts in (docs/runbook-go-live.md
 * Step 3, the one documented remote-migrate path). The seed boundary does
 * NOT opt in: remote seeding refuses unconditionally, no env escape —
 * seeding a remote database is permanently prohibited, made structural.
 *
 * Error messages name the offending HOST and DBNAME ONLY — never the
 * connection URL, which can carry credentials.
 */

import { dbNameFromUrl } from './test-db-guard.js';

/** Environment variable + exact value that arm the remote-migrate override. */
export const REMOTE_DB_OK_ENV = 'PCA_REMOTE_DB_OK';
export const REMOTE_DB_OK_VALUE = '1';

/** Hostnames that are positively local. */
const LOCAL_HOSTNAMES: ReadonlySet<string> = new Set(['localhost', '127.0.0.1', '::1']);

/**
 * Extracts the hostname from a Postgres connection URL, or returns null when
 * it cannot be determined (unparseable URL, empty host) — callers treat null
 * as a refusal (fail-closed). IPv6 brackets are stripped so `[::1]`
 * classifies as `::1`.
 */
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

/** Pure predicate: is `hostname` positively a local host? */
export function isLocalDbHost(hostname: string): boolean {
  return LOCAL_HOSTNAMES.has(hostname.toLowerCase());
}

/** Pure predicate: is the remote override armed in `env` (exact-value match)? */
export function remoteDbOverrideActive(env: NodeJS.ProcessEnv): boolean {
  return env[REMOTE_DB_OK_ENV] === REMOTE_DB_OK_VALUE;
}

/**
 * Throws unless `url` names a local database host. `context` prefixes the
 * message so the failing entry path is identifiable (e.g. "db:migrate:latest").
 *
 * `allowRemoteOverride: true` (migrator only) lets PCA_REMOTE_DB_OK=1 in
 * `env` skip the host check; `false` (seed boundary) refuses a remote host
 * unconditionally and never consults the variable. The thrown message
 * includes host and database name only, never the URL.
 */
export function assertLocalDatabaseUrl(
  url: string,
  context: string,
  options: { allowRemoteOverride: boolean; env?: NodeJS.ProcessEnv },
): void {
  const env = options.env ?? process.env;
  if (options.allowRemoteOverride && remoteDbOverrideActive(env)) {
    return;
  }
  const host = hostFromUrl(url);
  const dbname = dbNameFromUrl(url) ?? '(undetermined)';
  if (host === null) {
    throw new Error(
      `${context}: refusing to run — the database host could not be determined ` +
        'from DATABASE_URL (fail-closed). Point DATABASE_URL at an explicit ' +
        'local host (localhost, 127.0.0.1, or ::1).',
    );
  }
  if (!isLocalDbHost(host)) {
    const remedy = options.allowRemoteOverride
      ? `A deliberate remote migration must set ${REMOTE_DB_OK_ENV}=${REMOTE_DB_OK_VALUE} ` +
        'explicitly (see docs/runbook-go-live.md Step 3).'
      : 'Seeding a remote database is prohibited unconditionally — there is no override.';
    throw new Error(
      `${context}: refusing to run against host "${host}" (database "${dbname}") — ` +
        'not a local host. Local entry points must target localhost, 127.0.0.1, ' +
        `or ::1. ${remedy}`,
    );
  }
}
