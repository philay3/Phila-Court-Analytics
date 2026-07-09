import { sql, type Kysely } from 'kysely';
import type { PublicApiDatabase } from '../db.js';

/**
 * Escapes LIKE/ILIKE wildcards (%, _) and the escape character itself so user
 * input always matches literally. Patterns built from the result must be used
 * with `ESCAPE '\'`.
 */
export function escapeLike(input: string): string {
  return input.replace(/[\\%_]/g, (ch) => `\\${ch}`);
}

export interface ChargeSearchRow {
  id: string;
  slug: string;
  display_name: string;
  statute_code: string | null;
  grade: string | null;
  matched_alias: string | null;
}

/**
 * Case-insensitive search over active normalized charges by display name,
 * alias text, and statute code.
 *
 * - One output row per charge (the base table is normalized_charges and alias
 *   matching goes through EXISTS/subselects, so there is no join fan-out).
 * - match_rank: 1 = case-insensitive equality on any of the three fields,
 *   2 = prefix match on any, 3 = substring match. The rank is the best the
 *   charge achieves across all fields and aliases.
 * - matched_alias: the alphabetically first alias that matched, and only when
 *   the display name itself did not match; statute-only matches leave it NULL
 *   (no alias matched, so MIN over the empty set is NULL).
 *
 * `q` must already be trimmed and length-validated by the service layer.
 */
export async function searchChargeRows(
  db: Kysely<PublicApiDatabase>,
  q: string,
  limit: number,
): Promise<ChargeSearchRow[]> {
  const lowered = q.toLowerCase();
  const escaped = escapeLike(q);
  const prefix = `${escaped}%`;
  const substring = `%${escaped}%`;

  return db
    .selectFrom('ref.normalized_charges as c')
    .where('c.is_active', '=', true)
    .where((eb) =>
      eb.or([
        sql<boolean>`c.display_name ilike ${substring} escape '\\'`,
        sql<boolean>`c.statute_code ilike ${substring} escape '\\'`,
        eb.exists(
          eb
            .selectFrom('ref.charge_aliases as a')
            .select('a.id')
            .whereRef('a.normalized_charge_id', '=', 'c.id')
            .where(sql<boolean>`a.alias_text ilike ${substring} escape '\\'`),
        ),
      ]),
    )
    .select([
      'c.id',
      'c.slug',
      'c.display_name',
      'c.statute_code',
      'c.grade',
      sql<number>`case
        when lower(c.display_name) = ${lowered}
          or lower(c.statute_code) = ${lowered}
          or exists (
            select 1 from ref.charge_aliases a
            where a.normalized_charge_id = c.id and lower(a.alias_text) = ${lowered}
          )
        then 1
        when c.display_name ilike ${prefix} escape '\\'
          or c.statute_code ilike ${prefix} escape '\\'
          or exists (
            select 1 from ref.charge_aliases a
            where a.normalized_charge_id = c.id
              and a.alias_text ilike ${prefix} escape '\\'
          )
        then 2
        else 3
      end`.as('match_rank'),
      sql<string | null>`case
        when c.display_name not ilike ${substring} escape '\\'
        then (
          select min(a.alias_text) from ref.charge_aliases a
          where a.normalized_charge_id = c.id
            and a.alias_text ilike ${substring} escape '\\'
        )
      end`.as('matched_alias'),
    ])
    .orderBy('match_rank')
    .orderBy('c.display_name')
    .orderBy('c.slug')
    .limit(limit)
    .execute();
}
