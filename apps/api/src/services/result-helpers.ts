import {
  CHARGE_SENTENCING_UNAVAILABLE_MESSAGE,
  PUBLIC_ERROR_CODES,
  type ChargeSentencing,
  type ChargeSentencingIndex,
  type ConvictionGradeRow,
  type JudgeSentencingIndex,
  type SentencingCategoryCode,
  type SentencingIndexCategoryRow,
  type SentencingIndexSummary,
} from '@pca/shared';
import { publicError } from '../public-error.js';
import { resolvePublicCategory, type CategoryKind } from '../taxonomy.js';
import type {
  ChargeSentencingAggregateRow,
  ConvictionGradeAggregateRow,
  SentencingIndexCategoryAggregateRow,
  SentencingIndexSummaryAggregateRow,
} from '../repositories/charge-result.js';
import { daysToMonths } from './months.js';

/**
 * Shared machinery of the public result endpoints (8.1 charge-only, 8.2
 * judge-specific). Extracted verbatim from the 8.1 service; its test suite is
 * the regression lock on this move.
 */

// Pinned 8.1 disambiguation rule: generic case-insensitive 8-4-4-4-12 hex
// (deliberately no v4 version-nibble check). A match ALWAYS resolves by id;
// there is no fallthrough between id and slug lookup in either direction.
// 8.2 applies the same rule independently to each path param.
export const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export interface AggregateDistributionRow {
  category_code: string;
  count: number;
  percentage: string;
  is_thin_data: boolean;
}

export interface DistributionBlock<Code extends string> {
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
export function buildDistributionBlock<Code extends string>(
  kind: CategoryKind,
  rows: readonly AggregateDistributionRow[],
  sampleSizes: readonly number[],
): DistributionBlock<Code> {
  const uniqueSampleSizes = new Set(sampleSizes);
  const [sampleSize] = uniqueSampleSizes;
  if (sampleSize === undefined || uniqueSampleSizes.size !== 1) {
    throw publicError(
      PUBLIC_ERROR_CODES.INTERNAL_ERROR,
      `aggregate ${kind} rows disagree on sample size within one result distribution`,
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
 * Assembles the sentencing tagged union from one scope's stored rows: zero
 * rows is the unavailable arm with the single pinned public message; anything
 * else builds the block (and inherits its integrity checks). Used for the
 * charge-only, judge-scoped, and baseline sentencing distributions alike.
 */
export function buildSentencing(rows: readonly ChargeSentencingAggregateRow[]): ChargeSentencing {
  return rows.length === 0
    ? { available: false, message: CHARGE_SENTENCING_UNAVAILABLE_MESSAGE }
    : {
        available: true,
        ...buildDistributionBlock<SentencingCategoryCode>(
          'sentencing',
          rows,
          rows.map((row) => row.sentencing_sample_size),
        ),
      };
}

// ---------------------------------------------------------------------------
// Task 35.2: conviction-grain sentencing-index assembly. Serves what 35.1
// stored — the only derivation is representational (day medians → months via
// daysToMonths, numeric strings → JSON numbers). The summary row is the
// servable anchor: its absence IS the absent arm, decided by the services
// before any row fetch.
// ---------------------------------------------------------------------------

function buildIndexSummary(row: SentencingIndexSummaryAggregateRow): SentencingIndexSummary {
  return {
    convictions: row.convictions,
    sentencedConvictions: row.sentenced_convictions,
    wedgeCount: row.wedge_count,
    wedgePercentage: Number(row.wedge_percentage),
    thinData: row.is_thin_data,
    dateRange: { start: row.date_range_start, end: row.date_range_end },
  };
}

/**
 * Maps stored category rows to public rows, ordered by taxonomy sortOrder.
 * resolvePublicCategory both validates the code (unknown/non-public →
 * INTERNAL_ERROR) and supplies the order; its display name is deliberately
 * NOT served (pin 4 — stored fields only; strings are 35.3's). The duration
 * trio is all-or-none by stored CHECK; a half-present trio can only mean
 * corruption and is the same class of integrity failure.
 */
function buildIndexCategoryRows(
  rows: readonly SentencingIndexCategoryAggregateRow[],
): SentencingIndexCategoryRow[] {
  const mapped = rows.map((row) => {
    const category = resolvePublicCategory('sentencing', row.category_code);
    const nulls = [row.median_min_days, row.median_max_days, row.min_assumed_percentage].filter(
      (value) => value === null,
    ).length;
    if (nulls !== 0 && nulls !== 3) {
      throw publicError(
        PUBLIC_ERROR_CODES.INTERNAL_ERROR,
        'sentencing-index category row carries a half-present duration trio',
      );
    }
    return {
      sortOrder: category.sortOrder,
      row: {
        // Cast: resolvePublicCategory just proved membership in the public
        // category set, which is exactly what SentencingCategoryCode is.
        categoryCode: row.category_code as SentencingCategoryCode,
        convictionCount: row.conviction_count,
        percentageOfSentenced: Number(row.percentage_of_sentenced),
        // Casts: the trio check above proved all three columns present in
        // this branch, so daysToMonths cannot return null here.
        ...(row.min_assumed_percentage !== null
          ? {
              medianMinMonths: daysToMonths(row.median_min_days) as number,
              medianMaxMonths: daysToMonths(row.median_max_days) as number,
              minAssumedPercentage: Number(row.min_assumed_percentage),
            }
          : {}),
      },
    };
  });
  mapped.sort((a, b) => a.sortOrder - b.sortOrder);
  return mapped.map((entry) => entry.row);
}

/** Grade rows arrive in serving order (conviction_count DESC, grade ASC). */
function buildGradeRows(rows: readonly ConvictionGradeAggregateRow[]): ConvictionGradeRow[] {
  return rows.map((row) => ({
    grade: row.grade,
    convictionCount: row.conviction_count,
    percentageOfConvictions: Number(row.percentage_of_convictions),
  }));
}

export function buildChargeSentencingIndex(
  summary: SentencingIndexSummaryAggregateRow,
  categoryRows: readonly SentencingIndexCategoryAggregateRow[],
  gradeRows: readonly ConvictionGradeAggregateRow[],
): ChargeSentencingIndex {
  return {
    available: true,
    summary: buildIndexSummary(summary),
    categories: buildIndexCategoryRows(categoryRows),
    grades: buildGradeRows(gradeRows),
  };
}

/** Judge arm: no grade mix (ruling 2) — the present arm has no grades key. */
export function buildJudgeSentencingIndex(
  summary: SentencingIndexSummaryAggregateRow,
  categoryRows: readonly SentencingIndexCategoryAggregateRow[],
): JudgeSentencingIndex {
  return {
    available: true,
    summary: buildIndexSummary(summary),
    categories: buildIndexCategoryRows(categoryRows),
  };
}
