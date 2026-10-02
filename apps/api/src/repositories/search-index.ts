import { sql, type Kysely } from 'kysely';
import type { PublicApiDatabase } from '../db.js';

/**
 * Search-index reads (task STATIC-2a). Three run-scoped enumerations over the
 * compile-enforced public pick; nothing here selects an id into the payload.
 *
 * Set rules (pin 1), stated once:
 *   - charges = every ACTIVE roster charge, with or without aggregates;
 *   - judges  = ACTIVE judges with at least one judge-specific outcome
 *               aggregate in the run for an ACTIVE charge;
 *   - pairs   = distinct (active charge, active judge) with such a row.
 * The is_active restriction on judges and pairs mirrors the result endpoints,
 * which resolve only active rows (findActiveChargeBySlug /
 * findActiveJudgeBySlug): an index entry for an inactive row would enumerate
 * a page that cannot be served.
 *
 * Ordering is deterministic so the payload is reproducible build to build:
 * charges and judges by lower(display_name) then slug; pairs by charge slug
 * then judge slug; aliases by alias text.
 */

export interface SearchIndexChargeRow {
  slug: string;
  display_name: string;
  statute_code: string | null;
  grade: string | null;
  aliases: string[];
}

export interface SearchIndexJudgeRow {
  slug: string;
  display_name: string;
  aliases: string[];
}

export interface SearchIndexPairRow {
  charge_slug: string;
  judge_slug: string;
}

// `array_agg ... filter` collapses the LEFT JOIN to one row per parent with
// an empty array (never NULL) when no alias exists; `pg` parses text[].
const ALIAS_AGG = sql<string[]>`coalesce(
  array_agg(a.alias_text order by a.alias_text) filter (where a.alias_text is not null),
  '{}'
)`;

export async function listActiveChargesWithAliases(
  db: Kysely<PublicApiDatabase>,
): Promise<SearchIndexChargeRow[]> {
  return db
    .selectFrom('ref.normalized_charges as c')
    .leftJoin('ref.charge_aliases as a', 'a.normalized_charge_id', 'c.id')
    .where('c.is_active', '=', true)
    .groupBy(['c.id', 'c.slug', 'c.display_name', 'c.statute_code', 'c.grade'])
    .select(['c.slug', 'c.display_name', 'c.statute_code', 'c.grade', ALIAS_AGG.as('aliases')])
    .orderBy(sql`lower(c.display_name)`)
    .orderBy('c.slug')
    .execute();
}

export async function listJudgesWithPairs(
  db: Kysely<PublicApiDatabase>,
  runId: string,
): Promise<SearchIndexJudgeRow[]> {
  return db
    .selectFrom('ref.normalized_judges as j')
    .leftJoin('ref.judge_aliases as a', 'a.normalized_judge_id', 'j.id')
    .where('j.is_active', '=', true)
    .where((eb) =>
      eb.exists(
        eb
          .selectFrom('analytics.judge_outcome_aggregates as joa')
          .innerJoin('ref.normalized_charges as c', 'c.id', 'joa.charge_id')
          .select('joa.id')
          .whereRef('joa.judge_id', '=', 'j.id')
          .where('joa.aggregate_run_id', '=', runId)
          .where('c.is_active', '=', true),
      ),
    )
    .groupBy(['j.id', 'j.slug', 'j.display_name'])
    .select(['j.slug', 'j.display_name', ALIAS_AGG.as('aliases')])
    .orderBy(sql`lower(j.display_name)`)
    .orderBy('j.slug')
    .execute();
}

export async function listJudgeChargePairs(
  db: Kysely<PublicApiDatabase>,
  runId: string,
): Promise<SearchIndexPairRow[]> {
  return db
    .selectFrom('analytics.judge_outcome_aggregates as joa')
    .innerJoin('ref.normalized_charges as c', 'c.id', 'joa.charge_id')
    .innerJoin('ref.normalized_judges as j', 'j.id', 'joa.judge_id')
    .where('joa.aggregate_run_id', '=', runId)
    .where('c.is_active', '=', true)
    .where('j.is_active', '=', true)
    .select(['c.slug as charge_slug', 'j.slug as judge_slug'])
    .distinct()
    .orderBy('c.slug')
    .orderBy('j.slug')
    .execute();
}
