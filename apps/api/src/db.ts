import type { FastifyInstance } from 'fastify';
import { Kysely, PostgresDialect } from 'kysely';
import pg from 'pg';
import type { Database } from '@pca/db';

/**
 * The public API's view of the database: exactly the tables the public
 * surface may read, derived from @pca/db's Database so column types can
 * never drift — the four ref.* tables plus the aggregate-run bookkeeping, the
 * four aggregate tables the 8.1/8.2 result endpoints consume, and the five
 * Task 35.1 conviction-grain sentencing-index tables (served starting 35.2).
 * Everything else (the raw/parsed/fact/review layers) is a compile error, not
 * a convention. This Pick is the compile-enforced public-surface manifest:
 * the ADR 0004 dump/restore table set mirrors it exactly.
 */
export type PublicApiDatabase = Pick<
  Database,
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
>;

export function createApiDb(): Kysely<PublicApiDatabase> {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error(
      'DATABASE_URL is not set. Copy .env.example to .env at the repo root ' +
        '(cp .env.example .env) or export DATABASE_URL in your shell.',
    );
  }
  return new Kysely<PublicApiDatabase>({
    dialect: new PostgresDialect({
      pool: new pg.Pool({ connectionString }),
    }),
  });
}

/**
 * Decorates the app with `getDb()`. The connection is created lazily on first
 * use so buildApp() works without DATABASE_URL (config errors surface as a
 * logged 500 on the first data-touching request, not at construction time).
 * A connection the app created itself is destroyed on close; an injected one
 * belongs to the caller.
 */
export function registerDb(app: FastifyInstance, injected?: Kysely<PublicApiDatabase>): void {
  let instance = injected;
  let owned = false;
  app.decorate('getDb', () => {
    if (!instance) {
      instance = createApiDb();
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
    getDb(): Kysely<PublicApiDatabase>;
  }
}
