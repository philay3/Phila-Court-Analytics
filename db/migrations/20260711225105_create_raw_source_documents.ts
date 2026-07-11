import type { Kysely } from 'kysely';
import { sql } from 'kysely';

// The internal source-document layer: one row per imported PDF, mirroring the
// 16.3 manual-import metadata record (services/pipeline manual_import.py). The
// 21.3 loader writes these rows; nothing writes to them in this migration's
// task (21.1).
//
// `raw.source_documents` is MUTABLE (pinned decision 2): status/error_code and
// import bookkeeping can change on re-import, so it carries created_at +
// updated_at and reuses the shared `public.set_updated_at()` trigger created in
// migration 6.1. The function is NOT recreated here — it is owned by 6.1 and
// shared across schemas by standing decision.
//
// Column note: `court_type` here is the RAW CP/MC filename code from the 16.3
// provenance derivation (null when the docket-number pattern does not match) —
// deliberately distinct in meaning from `parsed.dockets.court_type_recorded`
// ("Municipal Court"/"Common Pleas"), which lives in the parsed layer.
//
// `down` drops the trigger then the table; the trigger function is left intact
// (owned by 6.1).

export async function up(db: Kysely<unknown>): Promise<void> {
  await db.schema
    .createTable('raw.source_documents')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('file_hash', 'text', (col) => col.notNull())
    .addColumn('original_filename', 'text', (col) => col.notNull())
    .addColumn('file_size_bytes', 'bigint', (col) => col.notNull())
    .addColumn('imported_at', 'timestamptz', (col) => col.notNull())
    .addColumn('import_mode', 'text', (col) => col.notNull())
    .addColumn('status', 'text', (col) => col.notNull())
    .addColumn('error_code', 'text')
    .addColumn('docket_number_provenance', 'text')
    .addColumn('court_type', 'text')
    .addColumn('county', 'text')
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addColumn('updated_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addUniqueConstraint('source_documents_file_hash_key', ['file_hash'])
    .execute();

  await sql`
    CREATE TRIGGER set_updated_at BEFORE UPDATE ON raw.source_documents
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()
  `.execute(db);
}

export async function down(db: Kysely<unknown>): Promise<void> {
  await sql`DROP TRIGGER set_updated_at ON raw.source_documents`.execute(db);
  await db.schema.dropTable('raw.source_documents').execute();
}
