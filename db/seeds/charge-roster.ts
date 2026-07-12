import type { Kysely } from 'kysely';
import { sql } from 'kysely';

import type { Database } from '../src/types.js';
import { CHARGE_ROSTER_SEEDS, DEMO_ALIAS_ADDITIONS } from './charge-roster-data.js';
import { selectIdBySlug, type SeedResult } from './reference.js';
import { CHARGE_SEEDS } from './reference-data.js';

/**
 * Real charge-roster seed (Task 22.2). Inserts the public-statute-sourced roster
 * into the SAME ref.* tables as the Sprint 2 demo charges (Sprint 5 SD 8: real
 * and seeded rows coexist), using the same idempotent upsert shape as
 * `reference.ts`:
 *
 * - `ref.normalized_charges`: ON CONFLICT (slug) DO UPDATE with an
 *   `IS DISTINCT FROM` guard, so a repeat run reports zero rows and never churns
 *   `updated_at`.
 * - `ref.charge_aliases`: DO NOTHING on the (parent, alias_text) key.
 *
 * Fail-loud collision assertion (SD 8 / pinned decision 8): before any DB write,
 * this asserts that no roster slug collides with the demo-seed slug registry and
 * that the roster's own slugs are unique. A collision throws at seed time.
 *
 * The demo rows are never touched here; they remain the sole targets for the
 * charges they own.
 */

/** Throw if any roster slug collides with a demo slug or repeats within the roster. */
export function assertNoSlugCollision(): void {
  const demoSlugs = new Set(CHARGE_SEEDS.map((charge) => charge.slug));
  const seen = new Set<string>();
  for (const { slug } of CHARGE_ROSTER_SEEDS) {
    if (demoSlugs.has(slug)) {
      throw new Error(
        `charge-roster seed integrity error: slug "${slug}" collides with a demo-seed slug`,
      );
    }
    if (seen.has(slug)) {
      throw new Error(`charge-roster seed integrity error: duplicate roster slug "${slug}"`);
    }
    seen.add(slug);
  }
}

export async function seedChargeRoster(db: Kysely<Database>): Promise<SeedResult[]> {
  assertNoSlugCollision();
  return db
    .transaction()
    .execute(async (trx) => [
      await seedRosterCharges(trx),
      await seedRosterAliases(trx),
      await seedDemoAliases(trx),
    ]);
}

async function seedRosterCharges(db: Kysely<Database>): Promise<SeedResult> {
  const result = await db
    .insertInto('ref.normalized_charges')
    .values(
      CHARGE_ROSTER_SEEDS.map((charge) => ({
        slug: charge.slug,
        display_name: charge.displayName,
        statute_code: charge.statuteCode,
        grade: null,
        is_active: true,
      })),
    )
    .onConflict((oc) =>
      oc
        .constraint('normalized_charges_slug_key')
        .doUpdateSet((eb) => ({
          display_name: eb.ref('excluded.display_name'),
          statute_code: eb.ref('excluded.statute_code'),
          grade: eb.ref('excluded.grade'),
          is_active: eb.ref('excluded.is_active'),
        }))
        .where(
          sql<boolean>`(normalized_charges.display_name, normalized_charges.statute_code, normalized_charges.grade, normalized_charges.is_active)
            is distinct from
            (excluded.display_name, excluded.statute_code, excluded.grade, excluded.is_active)`,
        ),
    )
    .executeTakeFirst();
  return {
    seed: 'ref.normalized_charges (roster)',
    upserted: Number(result.numInsertedOrUpdatedRows ?? 0n),
  };
}

async function seedRosterAliases(db: Kysely<Database>): Promise<SeedResult> {
  const rosterWithAliases = CHARGE_ROSTER_SEEDS.filter((charge) => charge.aliases.length > 0);
  const idBySlug = await selectIdBySlug(
    db,
    'ref.normalized_charges',
    CHARGE_ROSTER_SEEDS.map((charge) => charge.slug),
  );
  const values = rosterWithAliases.flatMap((charge) => {
    const id = idBySlug.get(charge.slug);
    if (!id) {
      throw new Error(`charge-roster seed integrity error: no row for slug "${charge.slug}"`);
    }
    return charge.aliases.map((alias) => ({ normalized_charge_id: id, alias_text: alias }));
  });
  if (values.length === 0) {
    return { seed: 'ref.charge_aliases (roster)', upserted: 0 };
  }
  const result = await db
    .insertInto('ref.charge_aliases')
    .values(values)
    .onConflict((oc) =>
      oc.constraint('charge_aliases_normalized_charge_id_alias_text_key').doNothing(),
    )
    .executeTakeFirst();
  return {
    seed: 'ref.charge_aliases (roster)',
    upserted: Number(result.numInsertedOrUpdatedRows ?? 0n),
  };
}

/**
 * Additively attach standardized-CPCMS aliases to EXISTING demo rows (Decision 4).
 * Only ref.charge_aliases rows are written (FK'd to the demo slug's id); the demo
 * ref.normalized_charges rows are never modified. DO NOTHING keeps it idempotent.
 */
async function seedDemoAliases(db: Kysely<Database>): Promise<SeedResult> {
  const idBySlug = await selectIdBySlug(
    db,
    'ref.normalized_charges',
    DEMO_ALIAS_ADDITIONS.map((addition) => addition.slug),
  );
  const values = DEMO_ALIAS_ADDITIONS.flatMap((addition) => {
    const id = idBySlug.get(addition.slug);
    if (!id) {
      throw new Error(
        `charge-roster seed integrity error: no demo row for slug "${addition.slug}"`,
      );
    }
    return addition.aliases.map((alias) => ({ normalized_charge_id: id, alias_text: alias }));
  });
  if (values.length === 0) {
    return { seed: 'ref.charge_aliases (demo additions)', upserted: 0 };
  }
  const result = await db
    .insertInto('ref.charge_aliases')
    .values(values)
    .onConflict((oc) =>
      oc.constraint('charge_aliases_normalized_charge_id_alias_text_key').doNothing(),
    )
    .executeTakeFirst();
  return {
    seed: 'ref.charge_aliases (demo additions)',
    upserted: Number(result.numInsertedOrUpdatedRows ?? 0n),
  };
}
