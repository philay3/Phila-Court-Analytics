import type { Kysely } from 'kysely';
import {
  PUBLIC_ERROR_CODES,
  type ChargeOnlyResultResponse,
  type OutcomeCategoryCode,
} from '@pca/shared';
import type { PublicApiDatabase } from '../db.js';
import { publicError } from '../public-error.js';
import {
  findActiveChargeById,
  findActiveChargeBySlug,
  findActivePublishedRun,
  getChargeOutcomeRows,
  getChargeSentencingRows,
} from '../repositories/charge-result.js';
import { UUID_PATTERN, buildDistributionBlock, buildSentencing } from './result-helpers.js';

const CHARGE_NOT_FOUND_MESSAGE = 'No charge matches the requested identifier.';
// One message for both no-published-run and zero-outcome-rows: the two states
// are publicly indistinguishable by design. Exported for the 8.2 service,
// which throws the same code for the same two states.
export const CHARGE_RESULT_UNAVAILABLE_MESSAGE = 'Results are not available for this charge yet.';

/**
 * Charge-only public result: resolves the charge (id or slug, no
 * fallthrough), then the single active published run, then both
 * distributions scoped to that run. All misses throw catalog-coded errors;
 * the central handler shapes every response. The distribution machinery
 * lives in result-helpers.ts, shared with the 8.2 judge-specific service.
 */
export async function getChargeOnlyResult(
  getDb: () => Kysely<PublicApiDatabase>,
  chargeIdOrSlug: string,
): Promise<ChargeOnlyResultResponse> {
  const db = getDb();

  // Charge resolution comes first: an unknown charge is CHARGE_NOT_FOUND
  // even when no published run exists.
  const charge = UUID_PATTERN.test(chargeIdOrSlug)
    ? await findActiveChargeById(db, chargeIdOrSlug)
    : await findActiveChargeBySlug(db, chargeIdOrSlug);
  if (!charge) {
    throw publicError(PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND, CHARGE_NOT_FOUND_MESSAGE);
  }

  const run = await findActivePublishedRun(db);
  if (!run) {
    throw publicError(
      PUBLIC_ERROR_CODES.CHARGE_RESULT_UNAVAILABLE,
      CHARGE_RESULT_UNAVAILABLE_MESSAGE,
    );
  }

  const outcomeRows = await getChargeOutcomeRows(db, run.id, charge.id);
  if (outcomeRows.length === 0) {
    throw publicError(
      PUBLIC_ERROR_CODES.CHARGE_RESULT_UNAVAILABLE,
      CHARGE_RESULT_UNAVAILABLE_MESSAGE,
    );
  }
  const outcomes = buildDistributionBlock<OutcomeCategoryCode>(
    'outcome',
    outcomeRows,
    outcomeRows.map((row) => row.sample_size),
  );

  const sentencing = buildSentencing(await getChargeSentencingRows(db, run.id, charge.id));

  return {
    charge: {
      id: charge.id,
      slug: charge.slug,
      displayName: charge.display_name,
      ...(charge.statute_code !== null ? { statuteCode: charge.statute_code } : {}),
      ...(charge.grade !== null ? { grade: charge.grade } : {}),
    },
    resultType: 'charge_only',
    geography: 'philadelphia',
    dateRange: { start: run.data_range_start, end: run.data_range_end },
    lastRefreshed: run.published_at.toISOString(),
    taxonomyVersion: run.taxonomy_version,
    aggregateRunId: run.id,
    outcomes,
    sentencing,
    links: { methodology: '/methodology', definitions: '/definitions' },
  };
}
