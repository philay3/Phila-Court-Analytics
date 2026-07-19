import { sql, type Kysely } from 'kysely';
import type { PublicApiDatabase } from '../db.js';

export interface ChargeDirectoryRow {
  slug: string;
  display_name: string;
  statute_code: string | null;
  sample_size: number;
  has_sentencing: boolean;
}

/**
 * Directory rows for one run: every charge with at least one outcome
 * aggregate in that run. Same source as data-coverage's
 * chargesWithOutcomeAggregates count (DISTINCT charge_id over
 * charge_outcome_aggregates), so the directory total equals that count by
 * construction — the cross-check AC holds without reconciliation logic.
 * Deliberately NOT the search repository: search reads ref.* unscoped to any
 * run and would not match the coverage count.
 *
 * sample_size is invariant per (charge, run); MAX collapses the per-category
 * rows without asserting that invariant here.
 *
 * Sort (task DP-5, pinned): outcome sample size DESCENDING, then
 * lower(display_name) ascending, then slug ascending — slug is unique, so
 * the total order is deterministic regardless of name collation. The ORDER BY
 * sample-size key is the IDENTICAL max(coa.sample_size) expression that
 * produces the served outcomeSampleSize, so rendered values are monotonically
 * non-increasing under the served order by construction.
 */
export async function listChargesWithOutcomeAggregates(
  db: Kysely<PublicApiDatabase>,
  runId: string,
): Promise<ChargeDirectoryRow[]> {
  return db
    .selectFrom('analytics.charge_outcome_aggregates as coa')
    .innerJoin('ref.normalized_charges as nc', 'nc.id', 'coa.charge_id')
    .where('coa.aggregate_run_id', '=', runId)
    .groupBy(['nc.id', 'nc.slug', 'nc.display_name', 'nc.statute_code'])
    .select([
      'nc.slug',
      'nc.display_name',
      'nc.statute_code',
      sql<number>`max(coa.sample_size)`.as('sample_size'),
      sql<boolean>`exists (
        select 1 from analytics.charge_sentencing_aggregates csa
        where csa.aggregate_run_id = ${runId} and csa.charge_id = nc.id
      )`.as('has_sentencing'),
    ])
    .orderBy(sql`max(coa.sample_size)`, 'desc')
    .orderBy(sql`lower(nc.display_name)`)
    .orderBy('nc.slug')
    .execute();
}
