import type { Kysely } from 'kysely';
import {
  CHARGE_NOT_FOUND_MESSAGE,
  CHARGE_RESULT_UNAVAILABLE_MESSAGE,
  JUDGE_NOT_FOUND_MESSAGE,
  JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
  PUBLIC_ERROR_CODES,
  type JudgeSpecificResultResponse,
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
  type ChargeOutcomeAggregateRow,
  type ChargeRow,
} from '../repositories/charge-result.js';
import {
  findActiveJudgeById,
  findActiveJudgeBySlug,
  getJudgeOutcomeRows,
  getJudgeSentencingRows,
} from '../repositories/judge-result.js';
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

function buildOutcomes(rows: readonly ChargeOutcomeAggregateRow[]) {
  return buildDistributionBlock<OutcomeCategoryCode>(
    'outcome',
    rows,
    rows.map((row) => row.sample_size),
  );
}

/**
 * Judge-specific public result with mandatory Philadelphia baseline.
 *
 * Resolution order: charge, then judge (each id-or-slug with no fallthrough,
 * independent of publication state), then the single active published run.
 *
 * Availability quadrant on the two outcome-row sets (per the approved plan,
 * this supersedes the strictly top-down reading of the task file's decision
 * tree, whose steps 2 and 4 cannot both be reachable in written order):
 *
 * - baseline empty,   judge rows empty   → 404 CHARGE_RESULT_UNAVAILABLE
 *   (the unavailable variant's fallback must never point at a dead end)
 * - baseline empty,   judge rows present → 500 INTERNAL_ERROR
 *   (aggregation must always produce the baseline superset)
 * - baseline present, judge rows empty   → HTTP 200 unavailable arm
 *   (an answer, not an error — the fallback is truthful by construction)
 * - baseline present, judge rows present → success
 */
export async function getJudgeSpecificResult(
  getDb: () => Kysely<PublicApiDatabase>,
  chargeIdOrSlug: string,
  judgeIdOrSlug: string,
): Promise<JudgeSpecificResultResponse> {
  const db = getDb();

  const charge = UUID_PATTERN.test(chargeIdOrSlug)
    ? await findActiveChargeById(db, chargeIdOrSlug)
    : await findActiveChargeBySlug(db, chargeIdOrSlug);
  if (!charge) {
    throw publicError(PUBLIC_ERROR_CODES.CHARGE_NOT_FOUND, CHARGE_NOT_FOUND_MESSAGE);
  }

  const judge = UUID_PATTERN.test(judgeIdOrSlug)
    ? await findActiveJudgeById(db, judgeIdOrSlug)
    : await findActiveJudgeBySlug(db, judgeIdOrSlug);
  if (!judge) {
    throw publicError(PUBLIC_ERROR_CODES.JUDGE_NOT_FOUND, JUDGE_NOT_FOUND_MESSAGE);
  }

  const judgeSummary = { id: judge.id, slug: judge.slug, displayName: judge.display_name };

  const run = await findActivePublishedRun(db);
  if (!run) {
    throw publicError(
      PUBLIC_ERROR_CODES.CHARGE_RESULT_UNAVAILABLE,
      CHARGE_RESULT_UNAVAILABLE_MESSAGE,
    );
  }

  const baselineOutcomeRows = await getChargeOutcomeRows(db, run.id, charge.id);
  const judgeOutcomeRows = await getJudgeOutcomeRows(db, run.id, charge.id, judge.id);

  if (baselineOutcomeRows.length === 0) {
    if (judgeOutcomeRows.length > 0) {
      throw publicError(
        PUBLIC_ERROR_CODES.INTERNAL_ERROR,
        'judge-specific aggregate rows exist without their charge-only baseline',
      );
    }
    throw publicError(
      PUBLIC_ERROR_CODES.CHARGE_RESULT_UNAVAILABLE,
      CHARGE_RESULT_UNAVAILABLE_MESSAGE,
    );
  }

  if (judgeOutcomeRows.length === 0) {
    return {
      resultType: 'judge_specific_unavailable',
      code: PUBLIC_ERROR_CODES.JUDGE_SPECIFIC_RESULT_UNAVAILABLE,
      message: JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE,
      charge: chargeSummary(charge),
      judge: judgeSummary,
      // Truthful by construction: the baseline was just verified non-empty.
      fallback: { chargeOnlyResultPath: `/api/v1/public/results/charge/${charge.slug}` },
    };
  }

  // All four distributions are independent: separate rows, separate sample
  // sizes, separate integrity checks, separate sentencing unions.
  const judgeSentencingRows = await getJudgeSentencingRows(db, run.id, charge.id, judge.id);
  const baselineSentencingRows = await getChargeSentencingRows(db, run.id, charge.id);

  return {
    resultType: 'judge_specific',
    charge: chargeSummary(charge),
    judge: judgeSummary,
    geography: 'philadelphia',
    dateRange: { start: run.data_range_start, end: run.data_range_end },
    lastRefreshed: run.published_at.toISOString(),
    taxonomyVersion: run.taxonomy_version,
    aggregateRunId: run.id,
    judgeSpecific: {
      outcomes: buildOutcomes(judgeOutcomeRows),
      sentencing: buildSentencing(judgeSentencingRows),
    },
    baseline: {
      outcomes: buildOutcomes(baselineOutcomeRows),
      sentencing: buildSentencing(baselineSentencingRows),
    },
    links: { methodology: '/methodology', definitions: '/definitions' },
  };
}
