import { sql, type Kysely } from 'kysely';
import type { PublicApiDatabase } from '../db.js';
import { escapeLike } from './search-helpers.js';

export interface JudgeSearchRow {
  id: string;
  slug: string;
  display_name: string;
  matched_alias: string | null;
}

/**
 * Case-insensitive search over active normalized judges by display name and
 * alias text. Mirrors the charge search query minus its statute-code column;
 * the two queries stay separate deliberately — only the escape helper is
 * shared (see search-helpers.ts).
 *
 * - One output row per judge (the base table is normalized_judges and alias
 *   matching goes through EXISTS/subselects, so there is no join fan-out).
 * - match_rank: 1 = case-insensitive equality on the name or any alias,
 *   2 = prefix match on either, 3 = substring match. The rank is the best the
 *   judge achieves across the name and all aliases.
 * - matched_alias: the alphabetically first alias that MATCHED the query —
 *   the min() subselect filters to matching aliases, never the full alias
 *   set — and only when the display name itself did not match.
 *
 * `q` must already be trimmed and length-validated by the service layer.
 */
export async function searchJudgeRows(
  db: Kysely<PublicApiDatabase>,
  q: string,
  limit: number,
): Promise<JudgeSearchRow[]> {
  const lowered = q.toLowerCase();
  const escaped = escapeLike(q);
  const prefix = `${escaped}%`;
  const substring = `%${escaped}%`;

  return db
    .selectFrom('ref.normalized_judges as j')
    .where('j.is_active', '=', true)
    .where((eb) =>
      eb.or([
        sql<boolean>`j.display_name ilike ${substring} escape '\\'`,
        eb.exists(
          eb
            .selectFrom('ref.judge_aliases as a')
            .select('a.id')
            .whereRef('a.normalized_judge_id', '=', 'j.id')
            .where(sql<boolean>`a.alias_text ilike ${substring} escape '\\'`),
        ),
      ]),
    )
    .select([
      'j.id',
      'j.slug',
      'j.display_name',
      sql<number>`case
        when lower(j.display_name) = ${lowered}
          or exists (
            select 1 from ref.judge_aliases a
            where a.normalized_judge_id = j.id and lower(a.alias_text) = ${lowered}
          )
        then 1
        when j.display_name ilike ${prefix} escape '\\'
          or exists (
            select 1 from ref.judge_aliases a
            where a.normalized_judge_id = j.id
              and a.alias_text ilike ${prefix} escape '\\'
          )
        then 2
        else 3
      end`.as('match_rank'),
      sql<string | null>`case
        when j.display_name not ilike ${substring} escape '\\'
        then (
          select min(a.alias_text) from ref.judge_aliases a
          where a.normalized_judge_id = j.id
            and a.alias_text ilike ${substring} escape '\\'
        )
      end`.as('matched_alias'),
    ])
    .orderBy('match_rank')
    .orderBy('j.display_name')
    .orderBy('j.slug')
    .limit(limit)
    .execute();
}
