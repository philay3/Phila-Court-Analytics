import type { Kysely } from 'kysely';
import {
  CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE,
  type ChargeDirectoryEntry,
  type ChargeDirectoryResponse,
} from '@pca/shared';
import type { PublicApiDatabase } from '../db.js';
import { listChargesWithOutcomeAggregates } from '../repositories/charge-directory.js';
import { findActivePublishedRun } from '../repositories/charge-result.js';

/**
 * Public charge directory. Reuses the 8.1 active-published-run resolver
 * (never a second one); "no active published run" is the unavailable arm of
 * an HTTP-200 tagged union (Phase 8 standing decision), not an error.
 * Unexpected failures fall through to the central handler as INTERNAL_ERROR.
 */
export async function getChargeDirectory(
  getDb: () => Kysely<PublicApiDatabase>,
): Promise<ChargeDirectoryResponse> {
  const db = getDb();

  const run = await findActivePublishedRun(db);
  if (!run) {
    return { available: false, message: CHARGE_DIRECTORY_UNAVAILABLE_MESSAGE };
  }

  const rows = await listChargesWithOutcomeAggregates(db, run.id);
  return {
    available: true,
    charges: rows.map((row): ChargeDirectoryEntry => ({
      slug: row.slug,
      displayName: row.display_name,
      ...(row.statute_code !== null ? { statuteCode: row.statute_code } : {}),
      hasSentencing: row.has_sentencing,
      outcomeSampleSize: row.sample_size,
    })),
  };
}
