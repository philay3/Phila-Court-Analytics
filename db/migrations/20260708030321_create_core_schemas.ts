import type { Kysely } from 'kysely';

// Schema-namespace baseline: creates the eight PostgreSQL schemas that form
// the namespace skeleton of the architecture. Tables arrive in later
// migrations (FDN-002.3+).
//
// `down` deliberately uses plain DROP SCHEMA (no CASCADE): once any schema
// contains objects, reverting must fail loudly rather than destroy data.

const SCHEMAS = ['raw', 'parsed', 'ref', 'fact', 'analytics', 'review', 'audit', 'auth'] as const;

export async function up(db: Kysely<unknown>): Promise<void> {
  for (const schema of SCHEMAS) {
    await db.schema.createSchema(schema).execute();
  }
}

export async function down(db: Kysely<unknown>): Promise<void> {
  for (const schema of SCHEMAS) {
    await db.schema.dropSchema(schema).execute();
  }
}
