import type { Kysely } from 'kysely';
import { sql } from 'kysely';

import type { Database } from '../src/types.js';
import { JUDGE_ROSTER_SEEDS } from './judge-roster-data.js';
import { selectIdBySlug, type SeedResult } from './reference.js';
import { JUDGE_SEEDS } from './reference-data.js';

/**
 * Real judge-roster seed (Task 22.3). Inserts the public-directory-sourced roster
 * into the SAME ref.* tables as the Sprint 2 fake judges (real and seeded rows
 * coexist), using the same idempotent upsert shape as `reference.ts`:
 *
 * - `ref.normalized_judges`: ON CONFLICT (slug) DO UPDATE with an
 *   `IS DISTINCT FROM` guard, so a repeat run reports zero rows and never churns
 *   `updated_at`.
 * - `ref.judge_aliases`: DO NOTHING on the (parent, alias_text) key.
 *
 * Fail-loud collision assertion (AC 2): before any DB write, this asserts that no
 * roster slug collides with the fake Sprint 2 judge slugs (real<->fake) and that
 * the roster's own slugs are unique (real<->real). A collision throws at seed
 * time. The fake judges are never touched here; the Sprint 7 sweep deletes them.
 */

/** Throw if any roster slug collides with a fake-judge slug or repeats internally. */
export function assertNoSlugCollision(): void {
  const fakeSlugs = new Set(JUDGE_SEEDS.map((judge) => judge.slug));
  const seen = new Set<string>();
  for (const { slug } of JUDGE_ROSTER_SEEDS) {
    if (fakeSlugs.has(slug)) {
      throw new Error(
        `judge-roster seed integrity error: slug "${slug}" collides with a fake-judge slug`,
      );
    }
    if (seen.has(slug)) {
      throw new Error(`judge-roster seed integrity error: duplicate roster slug "${slug}"`);
    }
    seen.add(slug);
  }
}

export async function seedJudgeRoster(db: Kysely<Database>): Promise<SeedResult[]> {
  assertNoSlugCollision();
  return db
    .transaction()
    .execute(async (trx) => [await seedRosterJudges(trx), await seedRosterAliases(trx)]);
}

async function seedRosterJudges(db: Kysely<Database>): Promise<SeedResult> {
  const result = await db
    .insertInto('ref.normalized_judges')
    .values(
      JUDGE_ROSTER_SEEDS.map((judge) => ({
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
  return {
    seed: 'ref.normalized_judges (roster)',
    upserted: Number(result.numInsertedOrUpdatedRows ?? 0n),
  };
}

async function seedRosterAliases(db: Kysely<Database>): Promise<SeedResult> {
  const rosterWithAliases = JUDGE_ROSTER_SEEDS.filter((judge) => judge.aliases.length > 0);
  if (rosterWithAliases.length === 0) {
    return { seed: 'ref.judge_aliases (roster)', upserted: 0 };
  }
  const idBySlug = await selectIdBySlug(
    db,
    'ref.normalized_judges',
    JUDGE_ROSTER_SEEDS.map((judge) => judge.slug),
  );
  const values = rosterWithAliases.flatMap((judge) => {
    const id = idBySlug.get(judge.slug);
    if (!id) {
      throw new Error(`judge-roster seed integrity error: no row for slug "${judge.slug}"`);
    }
    return judge.aliases.map((alias) => ({ normalized_judge_id: id, alias_text: alias }));
  });
  const result = await db
    .insertInto('ref.judge_aliases')
    .values(values)
    .onConflict((oc) =>
      oc.constraint('judge_aliases_normalized_judge_id_alias_text_key').doNothing(),
    )
    .executeTakeFirst();
  return {
    seed: 'ref.judge_aliases (roster)',
    upserted: Number(result.numInsertedOrUpdatedRows ?? 0n),
  };
}
