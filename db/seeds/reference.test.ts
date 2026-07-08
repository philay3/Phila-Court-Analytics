import type { Kysely } from 'kysely';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import { createDb } from '../src/connection.js';
import type { Database } from '../src/types.js';
import { CHARGE_SEEDS, JUDGE_SEEDS } from './reference-data.js';
import { seedReference, type SeedResult } from './reference.js';

// Requires the local database: `pnpm db:up`, migrations applied
// (`pnpm db:migrate:latest`), and DATABASE_URL (root .env is auto-loaded via
// vitest.config.ts). Skipped when DATABASE_URL is unset so the suite stays
// runnable without a database.
const hasDb = Boolean(process.env.DATABASE_URL);
if (!hasDb) {
  console.warn(
    'DATABASE_URL not set — skipping seed idempotency tests. ' +
      'Start Postgres (pnpm db:up), apply migrations (pnpm db:migrate:latest), ' +
      'and create the root .env (cp .env.example .env).',
  );
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
  let db: Kysely<Database>;
  let secondRunResults: SeedResult[];
  let afterFirstRun: Awaited<ReturnType<typeof snapshotRef>>;
  let afterSecondRun: Awaited<ReturnType<typeof snapshotRef>>;
  let analyticsBefore: Record<string, number>;
  let analyticsAfter: Record<string, number>;

  beforeAll(async () => {
    db = createDb();
    analyticsBefore = await countAnalyticsRows(db);
    await seedReference(db);
    afterFirstRun = await snapshotRef(db);
    secondRunResults = await seedReference(db);
    afterSecondRun = await snapshotRef(db);
    analyticsAfter = await countAnalyticsRows(db);
  });

  afterAll(async () => {
    await db?.destroy();
  });

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
