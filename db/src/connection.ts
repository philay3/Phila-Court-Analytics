import { Kysely, PostgresDialect } from 'kysely';
import pg from 'pg';

/**
 * Creates a Kysely instance from `DATABASE_URL`.
 *
 * Typed `Kysely<unknown>` deliberately: the migration runner needs no schema
 * type, and the real database interface arrives with the domain schemas (2.3+).
 */
export function createDb(): Kysely<unknown> {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error(
      'DATABASE_URL is not set. Copy .env.example to .env at the repo root ' +
        '(cp .env.example .env) or export DATABASE_URL in your shell.',
    );
  }
  return new Kysely<unknown>({
    dialect: new PostgresDialect({
      pool: new pg.Pool({ connectionString }),
    }),
  });
}
