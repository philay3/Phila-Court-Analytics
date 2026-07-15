import { pathToFileURL } from 'node:url';

import { sql, type Kysely } from 'kysely';

import { createDb } from '../src/connection.js';
import { describeError } from '../src/errors.js';
import type { Database } from '../src/types.js';

/**
 * Seed guard (task 29.1, SD-3 resolution): `db:seed` refuses to run against
 * a database that contains real corpus data.
 *
 * Seeding the post-sweep live database would re-insert the fake seed judges
 * (reference seeds commit in their own transaction) and then fail on the
 * active-published unique index — partially reintroducing the launch-blocking
 * defect. The probe is data-shaped, not name-shaped: any rows in
 * `raw.source_documents` or `fact.fact_build_runs` mean real corpus data is
 * present and seeding is refused. Fresh dev databases, `pca_test`, and the CI
 * service databases are always empty at seed time and pass unchanged.
 *
 * The guard lives OUTSIDE `db/seeds/` by pinned decision — the seed scripts
 * themselves stay byte-identical; the package's `seed` script runs this
 * first. An unmigrated database (probe tables absent) is refused with a
 * run-migrations-first message rather than falling through to the seeds'
 * missing-relation error.
 */

const PROBE_TABLES = ['raw.source_documents', 'fact.fact_build_runs'] as const;

export type SeedGuardVerdict =
  { ok: true } | { ok: false; reason: 'unmigrated' | 'real-corpus'; message: string };

export async function checkSeedTarget(db: Kysely<Database>): Promise<SeedGuardVerdict> {
  for (const table of PROBE_TABLES) {
    const reg = await sql<{ oid: string | null }>`
      select to_regclass(${table})::text as oid
    `.execute(db);
    if (!reg.rows[0]?.oid) {
      return {
        ok: false,
        reason: 'unmigrated',
        message:
          `refusing to seed: ${table} does not exist in the target database — ` +
          'run migrations first (pnpm db:migrate:latest)',
      };
    }
  }
  for (const table of PROBE_TABLES) {
    const probe = await sql<{ present: boolean }>`
      select exists (select 1 from ${sql.table(table)}) as present
    `.execute(db);
    if (probe.rows[0]?.present) {
      return {
        ok: false,
        reason: 'real-corpus',
        message:
          `refusing to seed: the target database contains real corpus data ` +
          `(${table} is nonempty). Seeding a live database would re-insert the ` +
          'fake seed judges. See docs/seed-sweep-runbook.md.',
      };
    }
  }
  return { ok: true };
}

export async function guardMain(): Promise<number> {
  let db: Kysely<Database>;
  try {
    db = createDb();
  } catch (error) {
    console.error(`seed guard failed: ${describeError(error)}`);
    return 1;
  }
  try {
    const verdict = await checkSeedTarget(db);
    if (!verdict.ok) {
      console.error(verdict.message);
      return 2;
    }
    console.log('seed guard: no real corpus data in the target database — seeding allowed');
    return 0;
  } catch (error) {
    console.error(`seed guard failed: ${describeError(error)}`);
    return 1;
  } finally {
    await db.destroy();
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  guardMain().then((code) => {
    process.exitCode = code;
  });
}
