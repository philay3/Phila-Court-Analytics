import type { Kysely } from 'kysely';
import {
  SEARCH_INDEX_UNAVAILABLE_MESSAGE,
  type SearchIndexCharge,
  type SearchIndexJudge,
  type SearchIndexPair,
  type SearchIndexResponse,
} from '@pca/shared';
import type { PublicApiDatabase } from '../db.js';
import { findActivePublishedRun } from '../repositories/charge-result.js';
import {
  listActiveChargesWithAliases,
  listJudgeChargePairs,
  listJudgesWithPairs,
} from '../repositories/search-index.js';

/**
 * Public search index (task STATIC-2a). Reuses the 8.1 active-published-run
 * resolver (never a second one); "no active published run" is the unavailable
 * arm of an HTTP-200 tagged union, not an error. Unexpected failures fall
 * through to the central handler as INTERNAL_ERROR.
 *
 * Reads run sequentially, not via Promise.all: the handle may be a single
 * transaction connection, which cannot serve concurrent queries.
 */
export async function getSearchIndex(
  getDb: () => Kysely<PublicApiDatabase>,
): Promise<SearchIndexResponse> {
  const db = getDb();

  const run = await findActivePublishedRun(db);
  if (!run) {
    return { available: false, message: SEARCH_INDEX_UNAVAILABLE_MESSAGE };
  }

  const chargeRows = await listActiveChargesWithAliases(db);
  const judgeRows = await listJudgesWithPairs(db, run.id);
  const pairRows = await listJudgeChargePairs(db, run.id);

  return {
    available: true,
    aggregateRunId: run.id,
    taxonomyVersion: run.taxonomy_version,
    lastRefreshed: run.published_at.toISOString(),
    charges: chargeRows.map((row): SearchIndexCharge => ({
      slug: row.slug,
      displayName: row.display_name,
      ...(row.statute_code !== null ? { statuteCode: row.statute_code } : {}),
      ...(row.grade !== null ? { grade: row.grade } : {}),
      aliases: row.aliases,
    })),
    judges: judgeRows.map((row): SearchIndexJudge => ({
      slug: row.slug,
      displayName: row.display_name,
      aliases: row.aliases,
    })),
    pairs: pairRows.map((row): SearchIndexPair => ({
      chargeSlug: row.charge_slug,
      judgeSlug: row.judge_slug,
    })),
  };
}
