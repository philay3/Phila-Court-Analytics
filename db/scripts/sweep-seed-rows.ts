import type { Kysely, Transaction } from 'kysely';

import { SEED_PUBLISHED_RUN_ID, SEED_UNPUBLISHED_RUN_ID } from '../seeds/aggregate-data.js';
import { JUDGE_SEEDS } from '../seeds/reference-data.js';
import type { Database } from '../src/types.js';

/**
 * Seed sweep (task 29.1): deletes the fake seed judges, their aliases, and
 * both registry aggregate runs (the invalidated seeded published run and the
 * unpublished decoy) with all their aggregate rows.
 *
 * Every target is identified via the `db/seeds/` registry — the slugs and run
 * UUIDs are IMPORTED from the seed data modules, never name-matched or
 * guessed. Demo charges (`CHARGE_SEEDS`) and all roster rows are untouched by
 * construction: no statement here names their tables' rows.
 *
 * The whole sweep — interlocks, deletes, report — is ONE transaction. Any
 * interlock violation throws `SweepAbortError` and rolls everything back;
 * partial deletion is structurally impossible. A dry run (the default at the
 * CLI) executes the same deletes and then rolls back via a sentinel, so its
 * would-delete counts are exact.
 *
 * Idempotency: every delete is keyed on registry identifiers, so a second run
 * matches zero rows and reports itself as a no-op.
 */

export const SWEEP_JUDGE_SLUGS: readonly string[] = JUDGE_SEEDS.map((judge) => judge.slug);
export const SWEEP_RUN_IDS: readonly string[] = [SEED_PUBLISHED_RUN_ID, SEED_UNPUBLISHED_RUN_ID];

const AGGREGATE_TABLES = [
  'analytics.charge_outcome_aggregates',
  'analytics.charge_sentencing_aggregates',
  'analytics.judge_outcome_aggregates',
  'analytics.judge_sentencing_aggregates',
] as const;

const JUDGE_AGGREGATE_TABLES = [
  'analytics.judge_outcome_aggregates',
  'analytics.judge_sentencing_aggregates',
] as const;

const FACT_TABLES = ['fact.charge_outcomes', 'fact.charge_sentences'] as const;

/** An interlock violation: the transaction is rolled back, nothing deleted. */
export class SweepAbortError extends Error {}

/** Sentinel that rolls the transaction back after a dry run's deletes. */
class DryRunRollback extends Error {
  constructor(public readonly report: SweepReport) {
    super('dry-run rollback');
  }
}

export interface SweepTableResult {
  table: string;
  deleted: number;
}

export interface SweepReport {
  mode: 'dry-run' | 'swept';
  noOp: boolean;
  activePublishedRunId: string | null;
  /** Registry slugs of the fake judges actually present (and deleted). */
  judgeSlugsDeleted: string[];
  /** Registry run ids actually present (and deleted). */
  runIdsDeleted: string[];
  tables: SweepTableResult[];
}

export async function runSweep(
  db: Kysely<Database>,
  opts: { confirm: boolean },
): Promise<SweepReport> {
  try {
    return await db.transaction().execute(async (trx) => {
      const report = await sweepInTransaction(trx);
      if (!opts.confirm) {
        throw new DryRunRollback({ ...report, mode: 'dry-run' });
      }
      return report;
    });
  } catch (error) {
    if (error instanceof DryRunRollback) {
      return error.report;
    }
    throw error;
  }
}

function abort(message: string): never {
  throw new SweepAbortError(message);
}

async function sweepInTransaction(trx: Transaction<Database>): Promise<SweepReport> {
  const fakeJudges = await trx
    .selectFrom('ref.normalized_judges')
    .select(['id', 'slug'])
    .where('slug', 'in', [...SWEEP_JUDGE_SLUGS])
    .orderBy('slug')
    .execute();
  const fakeJudgeIds = fakeJudges.map((judge) => judge.id);

  const registryRuns = await trx
    .selectFrom('analytics.aggregate_runs')
    .select(['id', 'published_at', 'invalidated_at'])
    .where('id', 'in', [...SWEEP_RUN_IDS])
    .orderBy('id')
    .execute();

  const activeRuns = await trx
    .selectFrom('analytics.aggregate_runs')
    .select('id')
    .where('published_at', 'is not', null)
    .where('invalidated_at', 'is', null)
    .execute();
  const activePublishedRunId = activeRuns[0]?.id ?? null;
  if (activeRuns.length > 1) {
    abort(`expected at most one active published run, found ${activeRuns.length}`);
  }

  // Interlock (F1): the sweep is structurally incapable of deleting an
  // active published run. Registry runs must be invalidated (the seeded
  // published run) or never published (the decoy).
  for (const run of registryRuns) {
    if (run.published_at !== null && run.invalidated_at === null) {
      abort(`registry run ${run.id} is the active published run`);
    }
    if (run.id === SEED_PUBLISHED_RUN_ID && run.invalidated_at === null) {
      abort(
        `registry run ${run.id} is present but not invalidated — spec expects the seeded published run to be an invalidated rollback target`,
      );
    }
  }
  if (activePublishedRunId !== null && SWEEP_RUN_IDS.includes(activePublishedRunId)) {
    abort(`active published run ${activePublishedRunId} is a registry run`);
  }

  // Interlock: no real-data row may reference a row the sweep deletes.
  if (fakeJudgeIds.length > 0) {
    for (const table of FACT_TABLES) {
      const row = await trx
        .selectFrom(table)
        .select((eb) => eb.fn.countAll().as('n'))
        .where('normalized_judge_id', 'in', fakeJudgeIds)
        .executeTakeFirstOrThrow();
      if (Number(row.n) !== 0) {
        abort(`${row.n} row(s) in ${table} reference a fake seed judge`);
      }
    }
    for (const table of JUDGE_AGGREGATE_TABLES) {
      const row = await trx
        .selectFrom(table)
        .select((eb) => eb.fn.countAll().as('n'))
        .where('judge_id', 'in', fakeJudgeIds)
        .where('aggregate_run_id', 'not in', [...SWEEP_RUN_IDS])
        .executeTakeFirstOrThrow();
      if (Number(row.n) !== 0) {
        abort(`${row.n} row(s) in ${table} outside the registry runs reference a fake seed judge`);
      }
    }
  }

  const tables: SweepTableResult[] = [];
  for (const table of AGGREGATE_TABLES) {
    const result = await trx
      .deleteFrom(table)
      .where('aggregate_run_id', 'in', [...SWEEP_RUN_IDS])
      .executeTakeFirst();
    tables.push({ table, deleted: Number(result.numDeletedRows) });
  }

  const runsResult = await trx
    .deleteFrom('analytics.aggregate_runs')
    .where('id', 'in', [...SWEEP_RUN_IDS])
    .executeTakeFirst();
  tables.push({ table: 'analytics.aggregate_runs', deleted: Number(runsResult.numDeletedRows) });

  // Aliases would go via ON DELETE CASCADE; delete explicitly so the count
  // is reported instead of hidden in the cascade.
  let aliasesDeleted = 0;
  let judgesDeleted = 0;
  if (fakeJudgeIds.length > 0) {
    const aliasResult = await trx
      .deleteFrom('ref.judge_aliases')
      .where('normalized_judge_id', 'in', fakeJudgeIds)
      .executeTakeFirst();
    aliasesDeleted = Number(aliasResult.numDeletedRows);
    const judgeResult = await trx
      .deleteFrom('ref.normalized_judges')
      .where('id', 'in', fakeJudgeIds)
      .executeTakeFirst();
    judgesDeleted = Number(judgeResult.numDeletedRows);
  }
  tables.push({ table: 'ref.judge_aliases', deleted: aliasesDeleted });
  tables.push({ table: 'ref.normalized_judges', deleted: judgesDeleted });

  return {
    mode: 'swept',
    noOp: tables.every((entry) => entry.deleted === 0),
    activePublishedRunId,
    judgeSlugsDeleted: fakeJudges.map((judge) => judge.slug),
    runIdsDeleted: registryRuns.map((run) => run.id),
    tables,
  };
}
