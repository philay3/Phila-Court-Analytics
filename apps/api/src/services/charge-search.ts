import type { Kysely } from 'kysely';
import { PUBLIC_ERROR_CODES, type ChargeSearchResult } from '@pca/shared';
import type { PublicApiDatabase } from '../db.js';
import { publicError } from '../public-error.js';
import { searchChargeRows } from '../repositories/charge-search.js';

/**
 * Trims q, enforces the post-trim 1–100 length rule via a catalog throw, and
 * maps repository rows to the public contract (nulls become omitted keys, per
 * the shared-type convention). Validation runs before the database is touched,
 * so `getDb` is a thunk: bad requests never open a connection.
 */
export async function searchCharges(
  getDb: () => Kysely<PublicApiDatabase>,
  rawQ: string,
  limit: number,
): Promise<ChargeSearchResult[]> {
  const q = rawQ.trim();
  if (q.length < 1 || q.length > 100) {
    throw publicError(
      PUBLIC_ERROR_CODES.INVALID_REQUEST,
      'q must be between 1 and 100 characters after trimming.',
    );
  }

  const rows = await searchChargeRows(getDb(), q, limit);
  return rows.map((row) => ({
    id: row.id,
    slug: row.slug,
    displayName: row.display_name,
    ...(row.statute_code !== null ? { statuteCode: row.statute_code } : {}),
    ...(row.grade !== null ? { grade: row.grade } : {}),
    ...(row.matched_alias !== null ? { matchedAlias: row.matched_alias } : {}),
  }));
}
