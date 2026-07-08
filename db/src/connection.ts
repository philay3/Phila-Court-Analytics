import { Kysely, PostgresDialect } from 'kysely';
import pg from 'pg';

import type { Database } from './types.js';

/**
 * Creates a Kysely instance from `DATABASE_URL`, typed against the
 * schema-qualified table definitions in `types.ts`.
 */
export function createDb(): Kysely<Database> {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error(
      'DATABASE_URL is not set. Copy .env.example to .env at the repo root ' +
        '(cp .env.example .env) or export DATABASE_URL in your shell.',
    );
  }
  return new Kysely<Database>({
    dialect: new PostgresDialect({
      pool: new pg.Pool({ connectionString }),
    }),
  });
}
