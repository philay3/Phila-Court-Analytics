import { randomBytes } from 'node:crypto';
import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

import { Kysely, PostgresDialect, sql } from 'kysely';
import { FileMigrationProvider, Migrator } from 'kysely/migration';
import pg from 'pg';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import type { Database } from '../src/types.js';
import { CHARGE_SEEDS, JUDGE_SEEDS } from './reference-data.js';
import { seedReference, type SeedResult } from './reference.js';

const dbPackageDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');

// Exact-equality suite (H-30.0): the assertions below compare entire ref.*
// tables against the demo seeds, which is only valid with sole tenancy — the
// roster suites legitimately add rows to the shared test database, and rows
// persist across invocations (seeds are additive-only). So this suite runs in
// a SCRATCH database created on the connected server (sweep-seed-rows
// precedent; identifiable prefix so a leaked database from a crashed run is
// recognizable), migrated to latest and force-dropped in afterAll. Standing
// rule: no db-suite file may assert exactness against the shared test
// database — exactness assertions get a scratch database; everything else
// must tolerate a non-pristine shared test DB.
//
// Skipped when DATABASE_URL is unset so the suite stays runnable without a
// database.
const databaseUrl = process.env.DATABASE_URL;
const hasDb = Boolean(databaseUrl);
if (!hasDb) {
  console.warn(
    'DATABASE_URL not set — skipping seed idempotency tests. ' +
      'Start Postgres (pnpm db:up) and point DATABASE_URL at a test database ' +
      '(e.g. pca_test); this suite migrates its own scratch database.',
  );
}

function makeKysely(connectionString: string): Kysely<Database> {
  return new Kysely<Database>({
    dialect: new PostgresDialect({ pool: new pg.Pool({ connectionString }) }),
  });
}

const ANALYTICS_TABLES = [
  'analytics.aggregate_runs',
  'analytics.charge_outcome_aggregates',
  'analytics.charge_sentencing_aggregates',
  'analytics.judge_outcome_aggregates',
  'analytics.judge_sentencing_aggregates',
] as const;

async function snapshotRef(db: Kysely<Database>) {
  return {
    charges: await db.selectFrom('ref.normalized_charges').selectAll().orderBy('slug').execute(),
    chargeAliases: await db
      .selectFrom('ref.charge_aliases')
      .selectAll()
      .orderBy('normalized_charge_id')
      .orderBy('alias_text')
      .execute(),
    judges: await db.selectFrom('ref.normalized_judges').selectAll().orderBy('slug').execute(),
    judgeAliases: await db
      .selectFrom('ref.judge_aliases')
      .selectAll()
      .orderBy('normalized_judge_id')
      .orderBy('alias_text')
      .execute(),
  };
}

async function countAnalyticsRows(db: Kysely<Database>): Promise<Record<string, number>> {
  const counts: Record<string, number> = {};
  for (const table of ANALYTICS_TABLES) {
    const row = await db
      .selectFrom(table)
      .select((eb) => eb.fn.countAll().as('n'))
      .executeTakeFirstOrThrow();
    counts[table] = Number(row.n);
  }
  return counts;
}

describe.skipIf(!hasDb)('reference seeds', () => {
  const scratchName = `pca_ref_test_${randomBytes(6).toString('hex')}`;
  let admin: Kysely<Database>;
  let db: Kysely<Database>;
  let secondRunResults: SeedResult[];
  let afterFirstRun: Awaited<ReturnType<typeof snapshotRef>>;
  let afterSecondRun: Awaited<ReturnType<typeof snapshotRef>>;
  let analyticsBefore: Record<string, number>;
  let analyticsAfter: Record<string, number>;

  beforeAll(async () => {
    admin = makeKysely(databaseUrl!);
    await sql`create database ${sql.id(scratchName)}`.execute(admin);
    const url = new URL(databaseUrl!);
    url.pathname = `/${scratchName}`;
    db = makeKysely(url.toString());

    const migrator = new Migrator({
      db,
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

    analyticsBefore = await countAnalyticsRows(db);
    await seedReference(db);
    afterFirstRun = await snapshotRef(db);
    secondRunResults = await seedReference(db);
    afterSecondRun = await snapshotRef(db);
    analyticsAfter = await countAnalyticsRows(db);
  }, 120_000);

  afterAll(async () => {
    // Robust teardown (sweep parity): destroy the scratch connection first,
    // then force-drop the scratch database even if a test failed midway.
    if (db) {
      await db.destroy().catch((error: unknown) => {
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

  it('seeds exactly the expected charges', () => {
    expect(
      afterSecondRun.charges.map((row) => ({
        slug: row.slug,
        display_name: row.display_name,
        statute_code: row.statute_code,
        grade: row.grade,
        is_active: row.is_active,
      })),
    ).toEqual(
      [...CHARGE_SEEDS]
        .sort((a, b) => a.slug.localeCompare(b.slug))
        .map((charge) => ({
          slug: charge.slug,
          display_name: charge.displayName,
          statute_code: charge.statuteCode,
          grade: null,
          is_active: true,
        })),
    );
  });

  it('seeds exactly the expected judges', () => {
    expect(
      afterSecondRun.judges.map((row) => ({
        slug: row.slug,
        display_name: row.display_name,
        is_active: row.is_active,
      })),
    ).toEqual(
      [...JUDGE_SEEDS]
        .sort((a, b) => a.slug.localeCompare(b.slug))
        .map((judge) => ({
          slug: judge.slug,
          display_name: judge.displayName,
          is_active: true,
        })),
    );
  });

  it('resolves every alias to its parent record', async () => {
    const chargeAliasPairs = await db
      .selectFrom('ref.charge_aliases')
      .innerJoin(
        'ref.normalized_charges',
        'ref.normalized_charges.id',
        'ref.charge_aliases.normalized_charge_id',
      )
      .select(['ref.normalized_charges.slug', 'ref.charge_aliases.alias_text'])
      .execute();
    const judgeAliasPairs = await db
      .selectFrom('ref.judge_aliases')
      .innerJoin(
        'ref.normalized_judges',
        'ref.normalized_judges.id',
        'ref.judge_aliases.normalized_judge_id',
      )
      .select(['ref.normalized_judges.slug', 'ref.judge_aliases.alias_text'])
      .execute();

    expect(new Set(chargeAliasPairs.map((pair) => `${pair.slug} → ${pair.alias_text}`))).toEqual(
      new Set(
        CHARGE_SEEDS.flatMap((charge) =>
          charge.aliases.map((alias) => `${charge.slug} → ${alias}`),
        ),
      ),
    );
    expect(new Set(judgeAliasPairs.map((pair) => `${pair.slug} → ${pair.alias_text}`))).toEqual(
      new Set(
        JUDGE_SEEDS.flatMap((judge) => judge.aliases.map((alias) => `${judge.slug} → ${alias}`)),
      ),
    );
    // Every alias row joined to a parent — none orphaned.
    expect(chargeAliasPairs).toHaveLength(afterSecondRun.chargeAliases.length);
    expect(judgeAliasPairs).toHaveLength(afterSecondRun.judgeAliases.length);
  });

  it('reports zero upserted rows on the second run', () => {
    expect(secondRunResults.map(({ seed, upserted }) => ({ seed, upserted }))).toEqual([
      { seed: 'ref.normalized_charges', upserted: 0 },
      { seed: 'ref.charge_aliases', upserted: 0 },
      { seed: 'ref.normalized_judges', upserted: 0 },
      { seed: 'ref.judge_aliases', upserted: 0 },
    ]);
  });

  it('leaves database state identical after the second run (ids, timestamps, row counts)', () => {
    // Full-row comparison including id, created_at, and updated_at: the
    // second run must not insert, mutate, or churn updated_at.
    expect(afterSecondRun).toEqual(afterFirstRun);
  });

  it('does not touch analytics.* tables', () => {
    expect(analyticsAfter).toEqual(analyticsBefore);
  });
});
