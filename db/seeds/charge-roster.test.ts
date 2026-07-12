import type { Kysely } from 'kysely';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import { createDb } from '../src/connection.js';
import type { Database } from '../src/types.js';
import { assertNoSlugCollision, seedChargeRoster } from './charge-roster.js';
import { CHARGE_ROSTER_SEEDS, DEMO_ALIAS_ADDITIONS } from './charge-roster-data.js';
import { seedReference, type SeedResult } from './reference.js';
import { CHARGE_SEEDS } from './reference-data.js';

// --- collision assertion: pure, no database ---------------------------------

describe('charge-roster slug integrity', () => {
  it('has no slug colliding with the demo-seed registry and no internal duplicate', () => {
    expect(() => assertNoSlugCollision()).not.toThrow();
  });

  it('shares no slug with the demo charge seeds', () => {
    const demo = new Set(CHARGE_SEEDS.map((c) => c.slug));
    for (const { slug } of CHARGE_ROSTER_SEEDS) {
      expect(demo.has(slug)).toBe(false);
    }
  });

  it('shares no statute code with the demo charge seeds (coexistence)', () => {
    // Canonicalization mirrors the 22.2 statute canonicalizer: upper-case, keep
    // only [A-Z0-9.-]. No roster row may collide with a demo statute code.
    const canon = (code: string | null): string =>
      (code ?? '').toUpperCase().replace(/[^A-Z0-9.-]+/g, '');
    const demoCodes = new Set(CHARGE_SEEDS.map((c) => canon(c.statuteCode)));
    const rosterCodes = CHARGE_ROSTER_SEEDS.map((c) => canon(c.statuteCode));
    for (const code of rosterCodes) {
      expect(demoCodes.has(code)).toBe(false);
    }
    // Roster statute codes are themselves unique (no spurious statute ambiguity).
    expect(new Set(rosterCodes).size).toBe(rosterCodes.length);
  });
});

// --- idempotency + coexistence: requires the local database -----------------

const hasDb = Boolean(process.env.DATABASE_URL);
if (!hasDb) {
  console.warn(
    'DATABASE_URL not set — skipping charge-roster DB tests. ' +
      'Start Postgres (pnpm db:up), apply migrations, create the root .env.',
  );
}

async function snapshotRoster(db: Kysely<Database>) {
  return {
    charges: await db.selectFrom('ref.normalized_charges').selectAll().orderBy('slug').execute(),
    aliases: await db
      .selectFrom('ref.charge_aliases')
      .selectAll()
      .orderBy('normalized_charge_id')
      .orderBy('alias_text')
      .execute(),
  };
}

describe.skipIf(!hasDb)('charge-roster seeds', () => {
  let db: Kysely<Database>;
  let secondRun: SeedResult[];
  let afterFirst: Awaited<ReturnType<typeof snapshotRoster>>;
  let afterSecond: Awaited<ReturnType<typeof snapshotRoster>>;

  beforeAll(async () => {
    db = createDb();
    await seedReference(db);
    await seedChargeRoster(db);
    afterFirst = await snapshotRoster(db);
    secondRun = await seedChargeRoster(db);
    afterSecond = await snapshotRoster(db);
  });

  afterAll(async () => {
    await db?.destroy();
  });

  it('seeds every roster charge with its statute code', () => {
    const bySlug = new Map(afterSecond.charges.map((row) => [row.slug, row]));
    for (const seed of CHARGE_ROSTER_SEEDS) {
      const row = bySlug.get(seed.slug);
      expect(row).toBeDefined();
      expect(row?.display_name).toBe(seed.displayName);
      expect(row?.statute_code).toBe(seed.statuteCode);
    }
  });

  it('leaves the demo charge rows untouched', () => {
    const bySlug = new Map(afterSecond.charges.map((row) => [row.slug, row]));
    for (const demo of CHARGE_SEEDS) {
      const row = bySlug.get(demo.slug);
      expect(row?.display_name).toBe(demo.displayName);
      expect(row?.statute_code).toBe(demo.statuteCode);
    }
  });

  it('resolves every roster alias to its parent row', async () => {
    const pairs = await db
      .selectFrom('ref.charge_aliases')
      .innerJoin(
        'ref.normalized_charges',
        'ref.normalized_charges.id',
        'ref.charge_aliases.normalized_charge_id',
      )
      .select(['ref.normalized_charges.slug', 'ref.charge_aliases.alias_text'])
      .execute();
    const bySlug = new Set(pairs.map((p) => `${p.slug} → ${p.alias_text}`));
    for (const seed of CHARGE_ROSTER_SEEDS) {
      for (const alias of seed.aliases) {
        expect(bySlug.has(`${seed.slug} → ${alias}`)).toBe(true);
      }
    }
  });

  it('attaches the additive CPCMS aliases to the demo rows (rows untouched)', async () => {
    const pairs = await db
      .selectFrom('ref.charge_aliases')
      .innerJoin(
        'ref.normalized_charges',
        'ref.normalized_charges.id',
        'ref.charge_aliases.normalized_charge_id',
      )
      .select(['ref.normalized_charges.slug', 'ref.charge_aliases.alias_text'])
      .execute();
    const bySlug = new Set(pairs.map((p) => `${p.slug} → ${p.alias_text}`));
    for (const addition of DEMO_ALIAS_ADDITIONS) {
      for (const alias of addition.aliases) {
        expect(bySlug.has(`${addition.slug} → ${alias}`)).toBe(true);
      }
    }
  });

  it('reports zero upserted rows on the second run', () => {
    expect(secondRun.map(({ upserted }) => upserted)).toEqual([0, 0, 0]);
  });

  it('leaves database state identical after the second run', () => {
    expect(afterSecond).toEqual(afterFirst);
  });
});
