import pg from 'pg';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// Task 31.3c lock test: the migration runner's TLS posture is carried entirely
// by the connection string (db/src/connection.ts passes DATABASE_URL to
// pg.Pool unmodified), so these tests pin the pinned driver's parsing
// semantics — the load-bearing facts behind runbook-go-live.md Step 3:
//
//   1. A URL with no ssl parameters (local docker, CI service container)
//      resolves to ssl=false — TLS stays strictly opt-in.
//   2. `?sslmode=verify-full` resolves to full verification: TLS on, with
//      NEITHER rejectUnauthorized disabled NOR checkServerIdentity overridden
//      (i.e. Node's default chain + hostname checks stay active).
//
// pg has pre-announced weaker libpq-compatible sslmode semantics for v9.
// When an upgrade changes this behavior, these tests fail and force the
// Step 3 posture to be re-adjudicated at exactly the right moment.
//
// URLs below are the synthetic local-dev shape — no real hosts or secrets.

// ConnectionParameters is how pg actually configures a connection; @types/pg
// does not declare it, so model just the field under test.
interface ClientWithConnectionParameters {
  connectionParameters: {
    ssl: boolean | { rejectUnauthorized?: boolean; checkServerIdentity?: unknown };
  };
}

function resolvedSsl(connectionString: string) {
  const client = new pg.Client({ connectionString }) as unknown as ClientWithConnectionParameters;
  return client.connectionParameters.ssl;
}

const BASE_URL = 'postgres://pca:pca@localhost:5432/pca';

describe('task 31.3c: migration-runner TLS is opt-in via the connection string', () => {
  let savedPgSslMode: string | undefined;

  beforeAll(() => {
    // PGSSLMODE is only consulted when the URL carries no ssl parameters;
    // clear it so the no-parameter case tests the true default.
    savedPgSslMode = process.env.PGSSLMODE;
    delete process.env.PGSSLMODE;
  });

  afterAll(() => {
    if (savedPgSslMode !== undefined) {
      process.env.PGSSLMODE = savedPgSslMode;
    }
  });

  it('a URL without ssl parameters resolves to ssl=false (local/CI default unchanged)', () => {
    expect(resolvedSsl(BASE_URL)).toBe(false);
  });

  it('?sslmode=verify-full enables TLS with full verification left intact', () => {
    const ssl = resolvedSsl(`${BASE_URL}?sslmode=verify-full`);
    // Exactly the empty object: truthy (TLS on) with no weakening keys —
    // rejectUnauthorized stays at Node's default (true) and hostname
    // verification is not overridden.
    expect(ssl).toEqual({});
  });
});
