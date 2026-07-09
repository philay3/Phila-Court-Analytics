import { sql, type Kysely } from 'kysely';
import type { DataCoverageCounts } from '@pca/shared';
import type { PublicApiDatabase } from '../db.js';

/**
 * High-level coverage counts for one aggregate run — COUNT(DISTINCT) only;
 * no names, no lists, no row-level data ever leaves this module. Judge pairs
 * are counted from judge_outcome_aggregates alone: per the 8.2 quadrant
 * invariant, judge sentencing rows without judge outcome rows are an
 * integrity error, so the outcome table is the authoritative pair set.
 *
 * Queries run sequentially, not via Promise.all: the handle may be a single
 * transaction connection, which cannot serve concurrent queries.
 */
export async function getCoverageCounts(
  db: Kysely<PublicApiDatabase>,
  runId: string,
): Promise<DataCoverageCounts> {
  const outcomes = await db
    .selectFrom('analytics.charge_outcome_aggregates')
    .where('aggregate_run_id', '=', runId)
    .select(sql<number>`count(distinct charge_id)::int`.as('n'))
    .executeTakeFirstOrThrow();

  const sentencing = await db
    .selectFrom('analytics.charge_sentencing_aggregates')
    .where('aggregate_run_id', '=', runId)
    .select(sql<number>`count(distinct charge_id)::int`.as('n'))
    .executeTakeFirstOrThrow();

  const judgePairs = await db
    .selectFrom('analytics.judge_outcome_aggregates')
    .where('aggregate_run_id', '=', runId)
    .select(sql<number>`count(distinct (charge_id, judge_id))::int`.as('n'))
    .executeTakeFirstOrThrow();

  return {
    chargesWithOutcomeAggregates: outcomes.n,
    chargesWithSentencingAggregates: sentencing.n,
    judgeChargePairs: judgePairs.n,
  };
}
