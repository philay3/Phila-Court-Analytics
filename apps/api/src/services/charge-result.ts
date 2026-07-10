import type { Kysely } from 'kysely';
import {
  CHARGE_NOT_FOUND_MESSAGE,
  CHARGE_RESULT_UNAVAILABLE_MESSAGE,
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
  type ChargeRow,
} from '../repositories/charge-result.js';
import { UUID_PATTERN, buildDistributionBlock, buildSentencing } from './result-helpers.js';

function chargeSummary(charge: ChargeRow) {
  return {
    id: charge.id,
    slug: charge.slug,
    displayName: charge.display_name,
    ...(charge.statute_code !== null ? { statuteCode: charge.statute_code } : {}),
    ...(charge.grade !== null ? { grade: charge.grade } : {}),
  };
}

/**
 * The HTTP 200 "entity exists, data absent" arm (task 13.2a). Both
 * unavailable causes — no published run, and zero aggregate rows for the
 * charge in the published run — converge here, mirroring the 8.2
 * judge-unavailable answer. The two causes are publicly indistinguishable by
 * design, so they carry the identical pinned message.
 */
function chargeOnlyResultUnavailable(charge: ChargeRow): ChargeOnlyResultResponse {
  return {
    resultType: 'charge_only_unavailable',
    code: PUBLIC_ERROR_CODES.CHARGE_RESULT_UNAVAILABLE,
    message: CHARGE_RESULT_UNAVAILABLE_MESSAGE,
    charge: chargeSummary(charge),
    links: { methodology: '/methodology', definitions: '/definitions' },
  };
}

/**
 * Charge-only public result: resolves the charge (id or slug, no
 * fallthrough), then the single active published run, then both
 * distributions scoped to that run. An unknown charge throws
 * CHARGE_NOT_FOUND; a resolvable charge with no publishable aggregate returns
 * the HTTP 200 unavailable arm instead of an error. The central handler
 * shapes every error response. The distribution machinery lives in
 * result-helpers.ts, shared with the 8.2 judge-specific service.
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
    return chargeOnlyResultUnavailable(charge);
  }

  const outcomeRows = await getChargeOutcomeRows(db, run.id, charge.id);
  if (outcomeRows.length === 0) {
    return chargeOnlyResultUnavailable(charge);
  }
  const outcomes = buildDistributionBlock<OutcomeCategoryCode>(
    'outcome',
    outcomeRows,
    outcomeRows.map((row) => row.sample_size),
  );

  const sentencing = buildSentencing(await getChargeSentencingRows(db, run.id, charge.id));

  return {
    charge: chargeSummary(charge),
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
