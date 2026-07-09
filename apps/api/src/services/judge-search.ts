import type { Kysely } from 'kysely';
import {
  PUBLIC_ERROR_CODES,
  SEARCH_Q_MAX_LENGTH,
  SEARCH_Q_MIN_LENGTH,
  type JudgeSearchResult,
} from '@pca/shared';
import type { PublicApiDatabase } from '../db.js';
import { publicError } from '../public-error.js';
import { searchJudgeRows } from '../repositories/judge-search.js';

/**
 * Trims q, enforces the post-trim 1–100 length rule via a catalog throw, and
 * maps repository rows to the public contract (nulls become omitted keys, per
 * the shared-type convention). Validation runs before the database is touched,
 * so `getDb` is a thunk: bad requests never open a connection.
 */
export async function searchJudges(
  getDb: () => Kysely<PublicApiDatabase>,
  rawQ: string,
  limit: number,
): Promise<JudgeSearchResult[]> {
  const q = rawQ.trim();
  if (q.length < SEARCH_Q_MIN_LENGTH || q.length > SEARCH_Q_MAX_LENGTH) {
    throw publicError(
      PUBLIC_ERROR_CODES.INVALID_REQUEST,
      `q must be between ${SEARCH_Q_MIN_LENGTH} and ${SEARCH_Q_MAX_LENGTH} characters after trimming.`,
    );
  }

  const rows = await searchJudgeRows(getDb(), q, limit);
  return rows.map((row) => ({
    id: row.id,
    slug: row.slug,
    displayName: row.display_name,
    ...(row.matched_alias !== null ? { matchedAlias: row.matched_alias } : {}),
  }));
}
