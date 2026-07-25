import type { FastifyInstance } from 'fastify';
import { Kysely, PostgresDialect } from 'kysely';
import pg from 'pg';
import type { Database } from '@pca/db';

/**
 * The OPS dashboard's view of the database (Phase 36). Deliberately broader
 * than PublicApiDatabase: the operator dashboard reads the internal layers —
 * raw / parsed / fact / review — that the public surface may never touch.
 *
 * Containment is structural in the other direction: nothing in the PUBLIC
 * route tree can reach this type (public code imports PublicApiDatabase and
 * its compile-enforced pick), and the ops routes that consume it are only
 * registered when ADMIN_OPS_ENABLED is set — which is never the case in the
 * deployed topology, where these tables do not even exist. Every consumer is
 * counts-only: no docket numbers, defendant hashes, raw captured text, or
 * review-queue payload values are ever selected (see services/ops-numbers.ts).
 */
export type OpsDatabase = Pick<
  Database,
  | 'raw.source_documents'
  | 'parsed.dockets'
  | 'parsed.charges'
  | 'parsed.warnings'
  | 'parsed.docket_links'
  | 'fact.fact_build_runs'
  | 'fact.charge_outcomes'
  | 'fact.charge_sentences'
  | 'review.queue_items'
  | 'ref.normalized_charges'
  | 'ref.charge_aliases'
  | 'ref.normalized_judges'
  | 'ref.judge_aliases'
  | 'analytics.aggregate_runs'
  | 'analytics.charge_outcome_aggregates'
  | 'analytics.charge_sentencing_aggregates'
  | 'analytics.judge_outcome_aggregates'
  | 'analytics.judge_sentencing_aggregates'
  | 'analytics.charge_sentencing_index_summaries'
  | 'analytics.charge_sentencing_index_aggregates'
  | 'analytics.charge_conviction_grade_aggregates'
  | 'analytics.judge_sentencing_index_summaries'
  | 'analytics.judge_sentencing_index_aggregates'
  | 'analytics.charge_volume_aggregates'
>;

export function createOpsDb(): Kysely<OpsDatabase> {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error(
      'DATABASE_URL is not set. The ops dashboard reads the local canonical ' +
        'database; set DATABASE_URL in the environment.',
    );
  }
  return new Kysely<OpsDatabase>({
    dialect: new PostgresDialect({
      pool: new pg.Pool({ connectionString }),
    }),
  });
}

/**
 * Decorates the app with `getOpsDb()` — same lazy pattern as registerDb.
 * Only called when the ops routes are registered (flag on); an injected
 * handle belongs to the caller, an owned one is destroyed on close.
 */
export function registerOpsDb(app: FastifyInstance, injected?: Kysely<OpsDatabase>): void {
  let instance = injected;
  let owned = false;
  app.decorate('getOpsDb', () => {
    if (!instance) {
      instance = createOpsDb();
      owned = true;
    }
    return instance;
  });
  app.addHook('onClose', async () => {
    if (owned && instance) {
      await instance.destroy();
    }
  });
}

declare module 'fastify' {
  interface FastifyInstance {
    getOpsDb(): Kysely<OpsDatabase>;
  }
}
