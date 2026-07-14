import { pathToFileURL } from 'node:url';

import { Kysely, PostgresDialect, sql } from 'kysely';
import pg from 'pg';

import { describeError } from '../src/errors.js';
import type { Database } from '../src/types.js';
import { runSweep, SweepAbortError } from './sweep-seed-rows.js';

/**
 * CLI for the task 29.1 seed sweep.
 *
 * Refusals, in order, before any row is touched:
 *  1. CI: the sweep targets the live database by explicit intent and must be
 *     impossible to run in CI — refuse (exit 2) before any connection when a
 *     CI environment variable is set.
 *  2. `--database <name>` is REQUIRED and must match `current_database()` on
 *     the connection: the target is always named explicitly, never implied.
 *  3. `DATABASE_URL` must be sourced at the CLI boundary (`set -a; source
 *     .env; set +a`) — the package script deliberately does NOT auto-load
 *     the root .env.
 *
 * Default is a DRY RUN (deletes executed, transaction rolled back, exact
 * would-delete counts reported); `--confirm` commits. Output hygiene: counts,
 * seeded slugs (fake by standing decision), and registry run UUIDs
 * (synthetic constants committed in db/seeds/) only.
 */

const CI_ENV_VARS = ['CI', 'GITHUB_ACTIONS'] as const;

export async function cliMain(argv: string[], env: NodeJS.ProcessEnv): Promise<number> {
  if (CI_ENV_VARS.some((name) => env[name])) {
    console.error(
      'sweep-seed-rows deletes rows from the live database and must never run ' +
        'in a CI environment; refusing (CI builds fresh seeded databases and ' +
        'never needs the sweep)',
    );
    return 2;
  }

  let database: string | undefined;
  let confirm = false;
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    // pnpm forwards the `--` args separator verbatim; ignore it.
    if (arg === '--') {
      continue;
    }
    if (arg === '--confirm') {
      confirm = true;
    } else if (arg === '--database') {
      database = argv[i + 1];
      i += 1;
    } else {
      console.error(`unknown argument: ${arg} (usage: --database <name> [--confirm])`);
      return 1;
    }
  }
  if (!database) {
    console.error(
      '--database <name> is required: the sweep names its target explicitly ' +
        '(e.g. --database pca)',
    );
    return 1;
  }
  if (!env.DATABASE_URL) {
    console.error(
      'DATABASE_URL is not set; source it at the CLI boundary ' +
        '(set -a; source .env; set +a) — it is never auto-loaded',
    );
    return 1;
  }

  const db = new Kysely<Database>({
    dialect: new PostgresDialect({
      pool: new pg.Pool({ connectionString: env.DATABASE_URL }),
    }),
  });
  try {
    const current = await sql<{ db: string }>`select current_database() as db`.execute(db);
    const connectedTo = current.rows[0]?.db ?? '';
    if (connectedTo !== database) {
      console.error(
        `--database ${database} does not match the connected database ` +
          `"${connectedTo}"; refusing`,
      );
      return 1;
    }

    const report = await runSweep(db, { confirm });
    console.log(`sweep-seed-rows: mode=${report.mode} database=${connectedTo}`);
    console.log(`active published run: ${report.activePublishedRunId ?? 'none'}`);
    for (const { table, deleted } of report.tables) {
      const detail =
        table === 'analytics.aggregate_runs'
          ? ` [${report.runIdsDeleted.join(', ')}]`
          : table === 'ref.normalized_judges'
            ? ` [${report.judgeSlugsDeleted.join(', ')}]`
            : '';
      console.log(`  ${table}: ${deleted} row(s)${detail}`);
    }
    if (report.noOp) {
      console.log('no-op: nothing to sweep (all registry rows already absent)');
    } else if (report.mode === 'dry-run') {
      console.log('dry run: nothing deleted; pass --confirm to execute');
    }
    return 0;
  } catch (error) {
    if (error instanceof SweepAbortError) {
      console.error(`sweep refused: ${error.message}; transaction rolled back, nothing deleted`);
      return 1;
    }
    console.error(`sweep failed: ${describeError(error)}`);
    return 1;
  } finally {
    await db.destroy();
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  cliMain(process.argv.slice(2), process.env).then((code) => {
    process.exitCode = code;
  });
}
