import type { Kysely } from 'kysely';
import { sql } from 'kysely';

import type { Database } from '../src/types.js';
import { CHARGE_SEEDS, JUDGE_SEEDS } from './reference-data.js';

/**
 * Reference-layer seeds: idempotent ON CONFLICT upserts, per standing
 * decision (aggregate seeds in 6.4 use delete-and-reinsert instead).
 *
 * Parent tables upsert on the slug unique constraint with an
 * `IS DISTINCT FROM` guard so the UPDATE — and with it the `updated_at`
 * trigger — only fires when seed data actually changed. A repeat run is a
 * literal no-op: identical database state, zero rows reported.
 *
 * Alias tables use DO NOTHING: the (parent_id, alias_text) conflict key is
 * the entire payload, so there is nothing to update.
 *
 * Seeds are additive-only — rows removed from the seed data are NOT deleted
 * from the database.
 */

export interface SeedResult {
  seed: string;
  upserted: number;
}

export async function seedReference(db: Kysely<Database>): Promise<SeedResult[]> {
  return db
    .transaction()
    .execute(async (trx) => [
      await seedCharges(trx),
      await seedChargeAliases(trx),
      await seedJudges(trx),
      await seedJudgeAliases(trx),
    ]);
}

async function seedCharges(db: Kysely<Database>): Promise<SeedResult> {
  const result = await db
    .insertInto('ref.normalized_charges')
    .values(
      CHARGE_SEEDS.map((charge) => ({
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
    seed: 'ref.normalized_charges',
    upserted: Number(result.numInsertedOrUpdatedRows ?? 0n),
  };
}

async function seedChargeAliases(db: Kysely<Database>): Promise<SeedResult> {
  const idBySlug = await selectIdBySlug(
    db,
    'ref.normalized_charges',
    CHARGE_SEEDS.map((charge) => charge.slug),
  );
  const result = await db
    .insertInto('ref.charge_aliases')
    .values(
      CHARGE_SEEDS.flatMap((charge) =>
        charge.aliases.map((alias) => ({
          normalized_charge_id: requireId(idBySlug, charge.slug),
          alias_text: alias,
        })),
      ),
    )
    .onConflict((oc) =>
      oc.constraint('charge_aliases_normalized_charge_id_alias_text_key').doNothing(),
    )
    .executeTakeFirst();
  return { seed: 'ref.charge_aliases', upserted: Number(result.numInsertedOrUpdatedRows ?? 0n) };
}

async function seedJudges(db: Kysely<Database>): Promise<SeedResult> {
  const result = await db
    .insertInto('ref.normalized_judges')
    .values(
      JUDGE_SEEDS.map((judge) => ({
        slug: judge.slug,
        display_name: judge.displayName,
        is_active: true,
      })),
    )
    .onConflict((oc) =>
      oc
        .constraint('normalized_judges_slug_key')
        .doUpdateSet((eb) => ({
          display_name: eb.ref('excluded.display_name'),
          is_active: eb.ref('excluded.is_active'),
        }))
        .where(
          sql<boolean>`(normalized_judges.display_name, normalized_judges.is_active)
            is distinct from
            (excluded.display_name, excluded.is_active)`,
        ),
    )
    .executeTakeFirst();
  return { seed: 'ref.normalized_judges', upserted: Number(result.numInsertedOrUpdatedRows ?? 0n) };
}

async function seedJudgeAliases(db: Kysely<Database>): Promise<SeedResult> {
  const idBySlug = await selectIdBySlug(
    db,
    'ref.normalized_judges',
    JUDGE_SEEDS.map((judge) => judge.slug),
  );
  const result = await db
    .insertInto('ref.judge_aliases')
    .values(
      JUDGE_SEEDS.flatMap((judge) =>
        judge.aliases.map((alias) => ({
          normalized_judge_id: requireId(idBySlug, judge.slug),
          alias_text: alias,
        })),
      ),
    )
    .onConflict((oc) =>
      oc.constraint('judge_aliases_normalized_judge_id_alias_text_key').doNothing(),
    )
    .executeTakeFirst();
  return { seed: 'ref.judge_aliases', upserted: Number(result.numInsertedOrUpdatedRows ?? 0n) };
}

async function selectIdBySlug(
  db: Kysely<Database>,
  table: 'ref.normalized_charges' | 'ref.normalized_judges',
  slugs: string[],
): Promise<Map<string, string>> {
  const rows = await db
    .selectFrom(table)
    .select(['id', 'slug'])
    .where('slug', 'in', slugs)
    .execute();
  return new Map(rows.map((row) => [row.slug, row.id]));
}

function requireId(idBySlug: Map<string, string>, slug: string): string {
  const id = idBySlug.get(slug);
  if (!id) {
    throw new Error(`seed integrity error: no row found for slug "${slug}"`);
  }
  return id;
}
