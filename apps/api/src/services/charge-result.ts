import type { Kysely } from 'kysely';
import {
  CHARGE_NOT_FOUND_MESSAGE,
  CHARGE_RESULT_UNAVAILABLE_MESSAGE,
  CHARGE_VOLUME_ONLY_MESSAGE,
  PUBLIC_ERROR_CODES,
  type ChargeOnlyResultResponse,
  type ChargeVolume,
  type OutcomeCategoryCode,
} from '@pca/shared';
import type { PublicApiDatabase } from '../db.js';
import { publicError } from '../public-error.js';
import {
  findActiveChargeById,
  findActiveChargeBySlug,
  findActivePublishedRun,
  getChargeConvictionGradeRows,
  getChargeOutcomeRows,
  getChargeSentencingIndexCategoryRows,
  getChargeSentencingIndexSummary,
  getChargeSentencingRows,
  getChargeVolumeRow,
  type ActivePublishedRunRow,
  type ChargeRow,
  type ChargeVolumeAggregateRow,
} from '../repositories/charge-result.js';
import {
  UUID_PATTERN,
  buildChargeSentencingIndex,
  buildDistributionBlock,
  buildSentencing,
} from './result-helpers.js';

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
 * The HTTP 200 volume arm (Phase 36, R6 shape ii): the published run has SEEN
 * this charge (a volume row exists) but no recorded outcome does — every
 * newly rostered charge starts here. Replaces the dead-end unavailable arm
 * for exactly this state; the bare unavailable arm stays for the
 * truly-nothing case (no published run, or no volume row in it).
 */
function chargeOnlyResultVolume(
  charge: ChargeRow,
  run: ActivePublishedRunRow,
  volumeRow: ChargeVolumeAggregateRow,
): ChargeOnlyResultResponse {
  return {
    resultType: 'charge_only_volume',
    message: CHARGE_VOLUME_ONLY_MESSAGE,
    charge: chargeSummary(charge),
    geography: 'philadelphia',
    dateRange: { start: run.data_range_start, end: run.data_range_end },
    lastRefreshed: run.published_at.toISOString(),
    taxonomyVersion: run.taxonomy_version,
    aggregateRunId: run.id,
    volume: {
      available: true,
      chargesSeen: volumeRow.charges_seen,
      outcomesRecorded: volumeRow.outcomes_recorded,
    },
    links: { methodology: '/methodology', definitions: '/definitions' },
  };
}

/** The success-arm volume block: present when the run carries the row. */
function volumeBlock(volumeRow: ChargeVolumeAggregateRow | undefined): ChargeVolume {
  return volumeRow
    ? {
        available: true,
        chargesSeen: volumeRow.charges_seen,
        outcomesRecorded: volumeRow.outcomes_recorded,
      }
    : { available: false };
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

  const volumeRow = await getChargeVolumeRow(db, run.id, charge.id);
  const outcomeRows = await getChargeOutcomeRows(db, run.id, charge.id);
  if (outcomeRows.length === 0) {
    // Phase 36: seen-but-unresolved serves the volume arm instead of the dead
    // end; with no volume row either, the bare unavailable arm stands.
    return volumeRow
      ? chargeOnlyResultVolume(charge, run, volumeRow)
      : chargeOnlyResultUnavailable(charge);
  }
  const outcomes = buildDistributionBlock<OutcomeCategoryCode>(
    'outcome',
    outcomeRows,
    outcomeRows.map((row) => row.sample_size),
  );

  const sentencing = buildSentencing(await getChargeSentencingRows(db, run.id, charge.id));

  // Task 35.2: the conviction-grain index, a sibling of the sentencing
  // section above. The summary row is the servable anchor — its absence is
  // the absent arm (run predating the population, or a zero-conviction
  // cell; publicly indistinguishable by design) and short-circuits the row
  // reads.
  const indexSummary = await getChargeSentencingIndexSummary(db, run.id, charge.id);
  const sentencingIndex = indexSummary
    ? buildChargeSentencingIndex(
        indexSummary,
        await getChargeSentencingIndexCategoryRows(db, run.id, charge.id),
        await getChargeConvictionGradeRows(db, run.id, charge.id),
      )
    : { available: false as const };

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
    sentencingIndex,
    volume: volumeBlock(volumeRow),
    links: { methodology: '/methodology', definitions: '/definitions' },
  };
}
