import type { Kysely } from 'kysely';
import {
  CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  PUBLIC_ERROR_CODES,
  type ChargeOnlyResultResponse,
  type ChargeSentencing,
  type OutcomeCategoryCode,
  type SentencingCategoryCode,
} from '@pca/shared';
import type { PublicApiDatabase } from '../db.js';
import { publicError } from '../public-error.js';
import { resolvePublicCategory, type CategoryKind } from '../taxonomy.js';
import {
  findActiveChargeById,
  findActiveChargeBySlug,
  findActivePublishedRun,
  getChargeOutcomeRows,
  getChargeSentencingRows,
} from '../repositories/charge-result.js';

// Pinned 8.1 disambiguation rule: generic case-insensitive 8-4-4-4-12 hex
// (deliberately no v4 version-nibble check). A match ALWAYS resolves by id;
// there is no fallthrough between id and slug lookup in either direction.
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const CHARGE_NOT_FOUND_MESSAGE = 'No charge matches the requested identifier.';
// One message for both no-published-run and zero-outcome-rows: the two states
// are publicly indistinguishable by design.
const CHARGE_RESULT_UNAVAILABLE_MESSAGE = 'Results are not available for this charge yet.';

interface AggregateDistributionRow {
  category_code: string;
  count: number;
  percentage: string;
  is_thin_data: boolean;
}

interface DistributionBlock<Code extends string> {
  sampleSize: number;
  thinData: boolean;
  rows: { categoryCode: Code; displayName: string; count: number; percentage: number }[];
}

/**
 * Maps one distribution's stored rows (non-empty) to its public block.
 *
 * - The sample size must be uniform across the distribution's rows; a
 *   disagreement is an integrity failure (INTERNAL_ERROR), never a value to
 *   silently pick from — mirroring the unknown-category-code rule.
 * - thinData is true if ANY row carries the flag (defensive any-row contract).
 * - Rows are ordered by taxonomy sortOrder with taxonomy display names;
 *   resolvePublicCategory throws INTERNAL_ERROR for unknown or non-public
 *   codes.
 * - percentage converts the numeric(5,2) string to a JSON number — a
 *   representation change, never recomputation.
 */
function buildDistributionBlock<Code extends string>(
  kind: CategoryKind,
  rows: readonly AggregateDistributionRow[],
  sampleSizes: readonly number[],
): DistributionBlock<Code> {
  const uniqueSampleSizes = new Set(sampleSizes);
  const [sampleSize] = uniqueSampleSizes;
  if (sampleSize === undefined || uniqueSampleSizes.size !== 1) {
    throw publicError(
      PUBLIC_ERROR_CODES.INTERNAL_ERROR,
      `aggregate ${kind} rows disagree on sample size within one charge/run distribution`,
    );
  }

  const mapped = rows.map((row) => {
    const category = resolvePublicCategory(kind, row.category_code);
    return {
      sortOrder: category.sortOrder,
      row: {
        // Cast: resolvePublicCategory just proved membership in the public
        // category set, which is exactly what Code represents.
        categoryCode: row.category_code as Code,
        displayName: category.displayName,
        count: row.count,
        percentage: Number(row.percentage),
      },
    };
  });
  mapped.sort((a, b) => a.sortOrder - b.sortOrder);

  return {
    sampleSize,
    thinData: rows.some((row) => row.is_thin_data),
    rows: mapped.map((entry) => entry.row),
  };
}

/**
 * Charge-only public result: resolves the charge (id or slug, no
 * fallthrough), then the single active published run, then both
 * distributions scoped to that run. All misses throw catalog-coded errors;
 * the central handler shapes every response.
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

  const sentencingRows = await getChargeSentencingRows(db, run.id, charge.id);
  const sentencing: ChargeSentencing =
    sentencingRows.length === 0
      ? { available: false, message: CHARGE_SENTENCING_UNAVAILABLE_MESSAGE }
      : {
          available: true,
          ...buildDistributionBlock<SentencingCategoryCode>(
            'sentencing',
            sentencingRows,
            sentencingRows.map((row) => row.sentencing_sample_size),
          ),
        };

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
