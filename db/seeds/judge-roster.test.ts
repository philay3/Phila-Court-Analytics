import type { Kysely } from 'kysely';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import { createDb } from '../src/connection.js';
import type { Database } from '../src/types.js';
import { assertNoSlugCollision, seedJudgeRoster } from './judge-roster.js';
import { JUDGE_ROSTER_SEEDS } from './judge-roster-data.js';
import { seedReference, type SeedResult } from './reference.js';
import { JUDGE_SEEDS } from './reference-data.js';

// --- collision assertion: pure, no database ---------------------------------

describe('judge-roster slug integrity', () => {
  it('has no slug colliding with the fake-judge registry and no internal duplicate', () => {
    expect(() => assertNoSlugCollision()).not.toThrow();
  });

  it('shares no slug with the fake Sprint 2 judge seeds (real<->fake)', () => {
    const fake = new Set(JUDGE_SEEDS.map((j) => j.slug));
    for (const { slug } of JUDGE_ROSTER_SEEDS) {
      expect(fake.has(slug)).toBe(false);
    }
  });

  it('has unique roster slugs (real<->real)', () => {
    const slugs = JUDGE_ROSTER_SEEDS.map((j) => j.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
  });

  it('stores display names in natural (non-comma) public order', () => {
    // Answer 3: display_name is the public natural-order string, not comma form.
    for (const { displayName } of JUDGE_ROSTER_SEEDS) {
      expect(displayName).not.toContain(',');
    }
  });
});

// --- idempotency + coexistence: requires the local database -----------------

const hasDb = Boolean(process.env.DATABASE_URL);
if (!hasDb) {
  console.warn(
    'DATABASE_URL not set — skipping judge-roster DB tests. ' +
      'Start Postgres (pnpm db:up), apply migrations, create the root .env.',
  );
}

async function snapshotRoster(db: Kysely<Database>) {
  return {
    judges: await db.selectFrom('ref.normalized_judges').selectAll().orderBy('slug').execute(),
    aliases: await db
      .selectFrom('ref.judge_aliases')
      .selectAll()
      .orderBy('normalized_judge_id')
      .orderBy('alias_text')
      .execute(),
  };
}

describe.skipIf(!hasDb)('judge-roster seeds', () => {
  let db: Kysely<Database>;
  let secondRun: SeedResult[];
  let afterFirst: Awaited<ReturnType<typeof snapshotRoster>>;
  let afterSecond: Awaited<ReturnType<typeof snapshotRoster>>;

  beforeAll(async () => {
    db = createDb();
    await seedReference(db);
    await seedJudgeRoster(db);
    afterFirst = await snapshotRoster(db);
    secondRun = await seedJudgeRoster(db);
    afterSecond = await snapshotRoster(db);
  });

  afterAll(async () => {
    await db?.destroy();
  });

  it('seeds every roster judge with its display name', () => {
    const bySlug = new Map(afterSecond.judges.map((row) => [row.slug, row]));
    for (const seed of JUDGE_ROSTER_SEEDS) {
      const row = bySlug.get(seed.slug);
      expect(row).toBeDefined();
      expect(row?.display_name).toBe(seed.displayName);
    }
  });

  it('leaves the fake judge rows untouched', () => {
    const bySlug = new Map(afterSecond.judges.map((row) => [row.slug, row]));
    for (const fake of JUDGE_SEEDS) {
      const row = bySlug.get(fake.slug);
      expect(row?.display_name).toBe(fake.displayName);
    }
  });

  it('reports zero upserted rows on the second run', () => {
    expect(secondRun.map(({ upserted }) => upserted)).toEqual([0, 0]);
  });

  it('leaves database state identical after the second run', () => {
    expect(afterSecond).toEqual(afterFirst);
  });
});
