import type { SearchIndexCharge, SearchIndexJudge } from './search-index.js';
import {
  SEARCH_LIMIT_DEFAULT,
  SEARCH_LIMIT_MAX,
  SEARCH_LIMIT_MIN,
  SEARCH_Q_MAX_LENGTH,
  SEARCH_Q_MIN_LENGTH,
} from './search.js';

/**
 * Client-side matcher over the search index (task STATIC-2a, pin 2). Pure and
 * synchronous: no DOM, no fetch, no async. It reproduces the two public search
 * endpoints so a static site can answer autocomplete from the index file:
 *
 *   - the query rule of the services (apps/api/src/services/charge-search.ts
 *     and judge-search.ts): trim, then 1–100 characters — outside that the
 *     API answers 400 INVALID_REQUEST; here the answer is no results;
 *   - the WHERE and `match_rank` of the repositories
 *     (apps/api/src/repositories/charge-search.ts:43-96, judge-search.ts:39-88):
 *     a row matches when the display name, the statute code (charges only), or
 *     any alias contains the query case-insensitively; rank 1 = case-insensitive
 *     equality on any of those fields, 2 = prefix on any, 3 = otherwise; the
 *     rank is the best the row achieves across all fields and aliases;
 *   - `matched_alias`: the alphabetically first alias that matched, and ONLY
 *     when the display name itself did not match (a statute-only match carries
 *     none);
 *   - ORDER BY match_rank, display_name, slug; LIMIT capped at 25 (default 10).
 *
 * User text is literal: the SQL escapes `%` and `_` before ILIKE, so a query of
 * `50%` matches the characters `50%` — the substring comparison here does the
 * same without any escaping step.
 *
 * Known difference class, deliberately accepted: the SQL tiebreaks and the
 * alias minimum use the database collation (en_US.utf8, whose first-level
 * comparison ignores case and punctuation); this module uses `Intl.Collator`
 * for English, which also folds case at the first level but weighs punctuation.
 * Rows that differ only in punctuation placement may therefore tie-break
 * differently. Rank assignment itself is exact.
 */

export interface ChargeMatch {
  slug: string;
  displayName: string;
  statuteCode?: string;
  grade?: string;
  matchedAlias?: string;
}

export interface JudgeMatch {
  slug: string;
  displayName: string;
  matchedAlias?: string;
}

/** The trimmed query when it satisfies the 1–100 rule, else null (the API's 400 arm). */
export function normalizeSearchQuery(raw: string): string | null {
  const q = raw.trim();
  return q.length < SEARCH_Q_MIN_LENGTH || q.length > SEARCH_Q_MAX_LENGTH ? null : q;
}

/**
 * The effective limit: default 10, floor to an integer, clamp to [1, 25]. The
 * endpoint schema rejects out-of-range limits with 400; a client cannot, so it
 * clamps instead — the cap of 25 is the pinned behavior.
 */
export function clampSearchLimit(limit?: number): number {
  if (limit === undefined || !Number.isFinite(limit)) {
    return SEARCH_LIMIT_DEFAULT;
  }
  return Math.min(SEARCH_LIMIT_MAX, Math.max(SEARCH_LIMIT_MIN, Math.floor(limit)));
}

const collator = new Intl.Collator('en');

interface Ranked<T> {
  entry: T;
  rank: number;
  matchedAlias: string | undefined;
}

/**
 * The repository's WHERE + match_rank + matched_alias for one row, over the
 * lower-cased query. `code` is null for judges (no statute field).
 */
function rankEntry<T extends { displayName: string; aliases: readonly string[] }>(
  entry: T,
  code: string | null,
  q: string,
): Ranked<T> | null {
  const name = entry.displayName.toLowerCase();
  const statute = code === null ? null : code.toLowerCase();
  const aliases = entry.aliases.map((alias) => ({ text: alias, lower: alias.toLowerCase() }));

  const nameHit = name.includes(q);
  const statuteHit = statute !== null && statute.includes(q);
  const aliasHits = aliases.filter((alias) => alias.lower.includes(q));
  if (!nameHit && !statuteHit && aliasHits.length === 0) {
    return null;
  }

  let rank = 3;
  if (name === q || statute === q || aliases.some((alias) => alias.lower === q)) {
    rank = 1;
  } else if (
    name.startsWith(q) ||
    (statute !== null && statute.startsWith(q)) ||
    aliases.some((alias) => alias.lower.startsWith(q))
  ) {
    rank = 2;
  }

  // `CASE WHEN display_name NOT ILIKE %q% THEN (SELECT min(alias_text) ... WHERE
  // alias_text ILIKE %q%) END`: undefined when the name matched, or when no
  // alias matched (statute-only), else the collation-minimum matching alias.
  let matchedAlias: string | undefined;
  if (!nameHit && aliasHits.length > 0) {
    matchedAlias = aliasHits
      .map((alias) => alias.text)
      .reduce((min, text) => (collator.compare(text, min) < 0 ? text : min));
  }

  return { entry, rank, matchedAlias };
}

function orderAndLimit<T extends { displayName: string; slug: string }>(
  ranked: Ranked<T>[],
  limit: number,
): Ranked<T>[] {
  return ranked
    .sort(
      (a, b) =>
        a.rank - b.rank ||
        collator.compare(a.entry.displayName, b.entry.displayName) ||
        collator.compare(a.entry.slug, b.entry.slug),
    )
    .slice(0, limit);
}

/** Charge autocomplete over the index, reproducing GET /charges/search. */
export function matchCharges(
  index: { charges: readonly SearchIndexCharge[] },
  query: string,
  limit?: number,
): ChargeMatch[] {
  const q = normalizeSearchQuery(query);
  if (q === null) {
    return [];
  }
  const lowered = q.toLowerCase();
  const ranked: Ranked<SearchIndexCharge>[] = [];
  for (const charge of index.charges) {
    const hit = rankEntry(charge, charge.statuteCode ?? null, lowered);
    if (hit) ranked.push(hit);
  }
  return orderAndLimit(ranked, clampSearchLimit(limit)).map(({ entry, matchedAlias }) => ({
    slug: entry.slug,
    displayName: entry.displayName,
    ...(entry.statuteCode !== undefined ? { statuteCode: entry.statuteCode } : {}),
    ...(entry.grade !== undefined ? { grade: entry.grade } : {}),
    ...(matchedAlias !== undefined ? { matchedAlias } : {}),
  }));
}

/** Judge autocomplete over the index, reproducing GET /judges/search. */
export function matchJudges(
  index: { judges: readonly SearchIndexJudge[] },
  query: string,
  limit?: number,
): JudgeMatch[] {
  const q = normalizeSearchQuery(query);
  if (q === null) {
    return [];
  }
  const lowered = q.toLowerCase();
  const ranked: Ranked<SearchIndexJudge>[] = [];
  for (const judge of index.judges) {
    const hit = rankEntry(judge, null, lowered);
    if (hit) ranked.push(hit);
  }
  return orderAndLimit(ranked, clampSearchLimit(limit)).map(({ entry, matchedAlias }) => ({
    slug: entry.slug,
    displayName: entry.displayName,
    ...(matchedAlias !== undefined ? { matchedAlias } : {}),
  }));
}
