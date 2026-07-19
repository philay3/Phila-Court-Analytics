import { spawnSync } from 'node:child_process';
import { randomBytes, randomUUID } from 'node:crypto';
import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

import { Kysely, PostgresDialect, sql } from 'kysely';
import { FileMigrationProvider, Migrator } from 'kysely/migration';
import pg from 'pg';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import { checkSeedTarget, type SeedGuardVerdict } from '../scripts/seed-guard.js';
import { cliMain } from '../scripts/sweep-seed-rows-cli.js';
import {
  runSweep,
  SweepAbortError,
  SWEEP_JUDGE_SLUGS,
  SWEEP_RUN_IDS,
} from '../scripts/sweep-seed-rows.js';
import { SEED_PUBLISHED_RUN_ID, SEED_UNPUBLISHED_RUN_ID } from '../seeds/aggregate-data.js';
import { seedAggregates } from '../seeds/aggregates.js';
import { seedChargeRoster } from '../seeds/charge-roster.js';
import { seedJudgeRoster } from '../seeds/judge-roster.js';
import { JUDGE_ROSTER_SEEDS } from '../seeds/judge-roster-data.js';
import { CHARGE_SEEDS, JUDGE_SEEDS } from '../seeds/reference-data.js';
import { seedReference } from '../seeds/reference.js';
import type { Database } from '../src/types.js';

const dbPackageDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');

// The behavior tests run in a SCRATCH database created on the connected
// server (identifiable prefix so a leaked database from a crashed run is
// recognizable), never in the database DATABASE_URL names. They are skipped
// LOUDLY when DATABASE_URL is unset or points at the live database "pca" —
// never a silent green (task 29.1 plan review F3).
const databaseUrl = process.env.DATABASE_URL;
const connectedDbName = databaseUrl ? new URL(databaseUrl).pathname.replace(/^\//, '') : null;
const isLiveDb = connectedDbName === 'pca';
const canRunBehaviorTests = Boolean(databaseUrl) && !isLiveDb;

if (!databaseUrl) {
  console.warn(
    'DATABASE_URL not set — skipping sweep behavior tests. Point DATABASE_URL ' +
      'at a test database (e.g. pca_test) to run them.',
  );
} else if (isLiveDb) {
  console.warn(
    '*** SKIPPING sweep behavior tests: DATABASE_URL points at the LIVE ' +
      'database "pca". These tests create and drop a scratch database and must ' +
      'never run off the live connection. Point DATABASE_URL at a test ' +
      'database (e.g. pca_test) to run them. ***',
  );
}

function makeKysely(connectionString: string): Kysely<Database> {
  return new Kysely<Database>({
    dialect: new PostgresDialect({ pool: new pg.Pool({ connectionString }) }),
  });
}

async function countWhereRegistry(
  db: Kysely<Database>,
): Promise<{ runs: number; aggregates: number; judges: number; aliases: number }> {
  const runs = await db
    .selectFrom('analytics.aggregate_runs')
    .select((eb) => eb.fn.countAll().as('n'))
    .where('id', 'in', [...SWEEP_RUN_IDS])
    .executeTakeFirstOrThrow();
  const aggregateTables = [
    'analytics.charge_outcome_aggregates',
    'analytics.charge_sentencing_aggregates',
    'analytics.judge_outcome_aggregates',
    'analytics.judge_sentencing_aggregates',
    // Task 35.2: the five sentencing-index tables ride the same registry runs.
    'analytics.charge_sentencing_index_summaries',
    'analytics.charge_sentencing_index_aggregates',
    'analytics.charge_conviction_grade_aggregates',
    'analytics.judge_sentencing_index_summaries',
    'analytics.judge_sentencing_index_aggregates',
  ] as const;
  let aggregates = 0;
  for (const table of aggregateTables) {
    const row = await db
      .selectFrom(table)
      .select((eb) => eb.fn.countAll().as('n'))
      .where('aggregate_run_id', 'in', [...SWEEP_RUN_IDS])
      .executeTakeFirstOrThrow();
    aggregates += Number(row.n);
  }
  const judges = await db
    .selectFrom('ref.normalized_judges')
    .select((eb) => eb.fn.countAll().as('n'))
    .where('slug', 'in', [...SWEEP_JUDGE_SLUGS])
    .executeTakeFirstOrThrow();
  const aliases = await db
    .selectFrom('ref.judge_aliases')
    .innerJoin(
      'ref.normalized_judges',
      'ref.normalized_judges.id',
      'ref.judge_aliases.normalized_judge_id',
    )
    .select((eb) => eb.fn.countAll().as('n'))
    .where('ref.normalized_judges.slug', 'in', [...SWEEP_JUDGE_SLUGS])
    .executeTakeFirstOrThrow();
  return {
    runs: Number(runs.n),
    aggregates: aggregates,
    judges: Number(judges.n),
    aliases: Number(aliases.n),
  };
}

describe('sweep-seed-rows CLI refusals (no database required)', () => {
  it('refuses to run in a CI environment, before any connection', () => {
    // Spawned through the real package script path; the bogus DATABASE_URL
    // (closed port) proves the refusal happens before any connection attempt.
    const result = spawnSync(
      'pnpm',
      [
        'exec',
        'tsx',
        '--conditions',
        'pca-source',
        'scripts/sweep-seed-rows-cli.ts',
        '--database',
        'pca',
      ],
      {
        cwd: dbPackageDir,
        env: {
          ...process.env,
          CI: '1',
          DATABASE_URL: 'postgresql://nobody:nothing@127.0.0.1:1/nowhere',
        },
        encoding: 'utf8',
        timeout: 60_000,
      },
    );
    expect(result.status).toBe(2);
    expect(result.stderr).toContain('must never run in a CI environment; refusing');
  });

  it('refuses when GITHUB_ACTIONS is set', async () => {
    const code = await cliMain(['--database', 'pca'], {
      GITHUB_ACTIONS: 'true',
      DATABASE_URL: 'postgresql://nobody:nothing@127.0.0.1:1/nowhere',
    });
    expect(code).toBe(2);
  });

  it('requires --database', async () => {
    const code = await cliMain([], {});
    expect(code).toBe(1);
  });

  it('requires DATABASE_URL from the CLI boundary', async () => {
    const code = await cliMain(['--database', 'pca'], {});
    expect(code).toBe(1);
  });
});

describe.runIf(canRunBehaviorTests)('sweep-seed-rows behavior (scratch database)', () => {
  const scratchName = `pca_sweep_test_${randomBytes(6).toString('hex')}`;
  let admin: Kysely<Database>;
  let scratch: Kysely<Database>;
  let scratchUrl: string;
  let unmigratedVerdict: SeedGuardVerdict;
  const simulatedRealRunId = randomUUID();

  beforeAll(async () => {
    admin = makeKysely(databaseUrl!);
    await sql`create database ${sql.id(scratchName)}`.execute(admin);
    const url = new URL(databaseUrl!);
    url.pathname = `/${scratchName}`;
    scratchUrl = url.toString();
    scratch = makeKysely(scratchUrl);

    // F2: the guard's verdict on a fresh, unmigrated database is captured
    // before migrations run and asserted in its own test below.
    unmigratedVerdict = await checkSeedTarget(scratch);

    const migrator = new Migrator({
      db: scratch,
      provider: new FileMigrationProvider({
        fs,
        path,
        migrationFolder: path.join(dbPackageDir, 'migrations'),
      }),
    });
    const { error } = await migrator.migrateToLatest();
    if (error) {
      throw error;
    }

    await seedReference(scratch);
    await seedChargeRoster(scratch);
    await seedJudgeRoster(scratch);
    await seedAggregates(scratch);
  }, 120_000);

  afterAll(async () => {
    // Robust teardown: destroy the scratch connection first, then force-drop
    // the scratch database even if a test failed midway.
    if (scratch) {
      await scratch.destroy().catch((error: unknown) => {
        console.error(`scratch pool teardown failed: ${String(error)}`);
      });
    }
    if (admin) {
      await sql`drop database if exists ${sql.id(scratchName)} with (force)`
        .execute(admin)
        .catch((error: unknown) => {
          console.error(`scratch database drop failed: ${String(error)}`);
        });
      await admin.destroy();
    }
  }, 60_000);

  it('seed guard refuses an unmigrated database with a run-migrations-first message', () => {
    expect(unmigratedVerdict.ok).toBe(false);
    if (!unmigratedVerdict.ok) {
      expect(unmigratedVerdict.reason).toBe('unmigrated');
      expect(unmigratedVerdict.message).toContain('run migrations first');
    }
  });

  it('seed guard allows a migrated, seeded database with no real corpus data', async () => {
    const verdict = await checkSeedTarget(scratch);
    expect(verdict).toEqual({ ok: true });
  });

  it('seed guard refuses a database holding real corpus data, pointing at the runbook', async () => {
    const buildRunId = randomUUID();
    await scratch
      .insertInto('fact.fact_build_runs')
      .values({
        id: buildRunId,
        status: 'in_progress',
        parser_version: 1,
        envelope_parser_version: 1,
        taxonomy_version: 'test',
        roster_snapshot_note: null,
        started_at: new Date(),
        completed_at: null,
        counts: null,
      })
      .execute();
    const verdict = await checkSeedTarget(scratch);
    expect(verdict.ok).toBe(false);
    if (!verdict.ok) {
      expect(verdict.reason).toBe('real-corpus');
      expect(verdict.message).toContain('docs/seed-sweep-runbook.md');
    }
    await scratch.deleteFrom('fact.fact_build_runs').where('id', '=', buildRunId).execute();
  });

  it('refuses to sweep while the seeded run is the active published run (F1)', async () => {
    await expect(runSweep(scratch, { confirm: true })).rejects.toThrow(SweepAbortError);
    const counts = await countWhereRegistry(scratch);
    expect(counts.judges).toBe(JUDGE_SEEDS.length);
    expect(counts.runs).toBe(SWEEP_RUN_IDS.length);
  });

  it('CLI refuses a --database name that does not match the connection', async () => {
    const code = await cliMain(['--database', 'not_this_database'], {
      DATABASE_URL: scratchUrl,
    });
    expect(code).toBe(1);
  });

  it('dry run reports exact would-delete counts and deletes nothing', async () => {
    // Reproduce the live shape first: the seeded published run is invalidated
    // and a later run is published (the Sprint 6 publish swap). Invalidation
    // must precede the insert — the active-published partial unique index
    // allows only one qualifying row at a time.
    await scratch
      .updateTable('analytics.aggregate_runs')
      .set({
        invalidated_at: '2026-07-03T02:00:00.000Z',
        invalidated_reason: `superseded by publish of run ${simulatedRealRunId}`,
      })
      .where('id', '=', SEED_PUBLISHED_RUN_ID)
      .execute();
    await scratch
      .insertInto('analytics.aggregate_runs')
      .values({
        id: simulatedRealRunId,
        status: 'completed',
        started_at: '2026-07-03T00:00:00.000Z',
        completed_at: '2026-07-03T01:00:00.000Z',
        published_at: '2026-07-03T02:00:00.000Z',
        invalidated_at: null,
        invalidated_reason: null,
        parser_version: null,
        taxonomy_version: 'test',
        data_range_start: '2025-01-01',
        data_range_end: '2026-06-30',
      })
      .execute();

    const before = await countWhereRegistry(scratch);
    const report = await runSweep(scratch, { confirm: false });

    expect(report.mode).toBe('dry-run');
    expect(report.noOp).toBe(false);
    expect(report.activePublishedRunId).toBe(simulatedRealRunId);
    expect(report.judgeSlugsDeleted).toEqual([...SWEEP_JUDGE_SLUGS].sort());
    expect(report.runIdsDeleted).toEqual([SEED_PUBLISHED_RUN_ID, SEED_UNPUBLISHED_RUN_ID].sort());
    const judgesEntry = report.tables.find((t) => t.table === 'ref.normalized_judges');
    expect(judgesEntry?.deleted).toBe(JUDGE_SEEDS.length);

    const after = await countWhereRegistry(scratch);
    expect(after).toEqual(before);
    expect(after.judges).toBe(JUDGE_SEEDS.length);
  });

  async function countDemoChargeAliases(): Promise<number> {
    const row = await scratch
      .selectFrom('ref.charge_aliases')
      .innerJoin(
        'ref.normalized_charges',
        'ref.normalized_charges.id',
        'ref.charge_aliases.normalized_charge_id',
      )
      .select((eb) => eb.fn.countAll().as('n'))
      .where(
        'ref.normalized_charges.slug',
        'in',
        CHARGE_SEEDS.map((charge) => charge.slug),
      )
      .executeTakeFirstOrThrow();
    return Number(row.n);
  }

  it('confirmed sweep deletes the registry rows and nothing else', async () => {
    const rosterJudgesBefore = await scratch
      .selectFrom('ref.normalized_judges')
      .select((eb) => eb.fn.countAll().as('n'))
      .where('slug', 'not in', [...SWEEP_JUDGE_SLUGS])
      .executeTakeFirstOrThrow();
    // Demo-charge aliases include the 22.2 roster task's DEMO_ALIAS_ADDITIONS,
    // so retention is asserted by before/after snapshot, not recomputation.
    const demoAliasesBefore = await countDemoChargeAliases();
    expect(demoAliasesBefore).toBeGreaterThan(0);

    const report = await runSweep(scratch, { confirm: true });
    expect(report.mode).toBe('swept');
    expect(report.noOp).toBe(false);
    expect(report.activePublishedRunId).toBe(simulatedRealRunId);

    const after = await countWhereRegistry(scratch);
    expect(after).toEqual({ runs: 0, aggregates: 0, judges: 0, aliases: 0 });

    // Retention: demo charges (and aliases), the full judge roster, and the
    // active published run are untouched.
    const demoCharges = await scratch
      .selectFrom('ref.normalized_charges')
      .select('slug')
      .where(
        'slug',
        'in',
        CHARGE_SEEDS.map((charge) => charge.slug),
      )
      .execute();
    expect(demoCharges).toHaveLength(CHARGE_SEEDS.length);
    expect(await countDemoChargeAliases()).toBe(demoAliasesBefore);
    const rosterJudgesAfter = await scratch
      .selectFrom('ref.normalized_judges')
      .select((eb) => eb.fn.countAll().as('n'))
      .executeTakeFirstOrThrow();
    expect(Number(rosterJudgesAfter.n)).toBe(Number(rosterJudgesBefore.n));
    expect(Number(rosterJudgesAfter.n)).toBe(JUDGE_ROSTER_SEEDS.length);
    const activeRun = await scratch
      .selectFrom('analytics.aggregate_runs')
      .select(['id'])
      .where('published_at', 'is not', null)
      .where('invalidated_at', 'is', null)
      .execute();
    expect(activeRun).toEqual([{ id: simulatedRealRunId }]);
  });

  it('a second run is a no-op and reports itself as such', async () => {
    const report = await runSweep(scratch, { confirm: true });
    expect(report.noOp).toBe(true);
    expect(report.judgeSlugsDeleted).toEqual([]);
    expect(report.runIdsDeleted).toEqual([]);
    for (const entry of report.tables) {
      expect(entry.deleted).toBe(0);
    }
  });
});
