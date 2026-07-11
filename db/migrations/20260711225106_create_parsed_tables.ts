import type { Kysely } from 'kysely';
import { sql } from 'kysely';

// The parsed layer: the 21.3 loader's write target. Five tables mirroring the
// 17.2 parser record (services/pipeline docket_parser.py) plus the 18.1
// envelope observability surface (envelope.py). Nothing writes to them in this
// migration's task (21.1).
//
// All five tables are IMMUTABLE load artifacts (pinned decision 3): created_at
// only (plus loaded_at on dockets), NO updated_at, NO set_updated_at trigger.
// A docket reload deletes and reinserts the tree rather than updating in place;
// immutability is enforced at the type level in db/src/types.ts (Immutable<>),
// mirroring the analytics aggregate-row precedent from 6.2.
//
// FK ON DELETE (pinned decision 6): CASCADE within the parsed.* family (a
// docket reload deletes its charges/sentences/warnings/related_cases), RESTRICT
// from parsed.dockets to raw.source_documents (a source document cannot be
// deleted while a parsed docket references it).
//
// FK indexes (pinned decision 5): every FK column is indexed, but a unique
// constraint whose index LEADS with the FK column already provides that index —
// so parsed.dockets.source_document_id (unique) and parsed.charges.docket_id
// (leading column of the (docket_id, sequence) unique) get NO separate *_idx.
// Only sentences.charge_id, warnings.docket_id, and related_cases.docket_id —
// FK columns not covered by a leading unique index — get an explicit index.
//
// Nullability is derived from the committed record/envelope shapes; see the
// completion report / worklog for the per-column reading. No defendant-name
// column exists anywhere (pinned decision 8) — defendant_hash is the only
// identity field. The always-empty record `notes` field is intentionally not
// stored (no producer).
//
// `down` drops children before parents (FK-safe), then dockets; plain drops, no
// CASCADE, consistent with the loud-revert precedent.

export async function up(db: Kysely<unknown>): Promise<void> {
  await db.schema
    .createTable('parsed.dockets')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('source_document_id', 'uuid', (col) => col.notNull())
    .addColumn('docket_number', 'text', (col) => col.notNull())
    .addColumn('record_parser_version', 'integer', (col) => col.notNull())
    .addColumn('envelope_parser_version', 'integer', (col) => col.notNull())
    .addColumn('parsed_at', 'timestamptz', (col) => col.notNull())
    .addColumn('county', 'text', (col) => col.notNull())
    .addColumn('court_type_recorded', 'text')
    .addColumn('court_type_derived', 'text')
    .addColumn('case_status', 'text')
    .addColumn('filed_date', 'date')
    .addColumn('otn', 'text')
    .addColumn('dc_number', 'text')
    .addColumn('cross_court_dockets', 'jsonb')
    .addColumn('defendant_hash', 'text', (col) => col.notNull())
    .addColumn('assigned_judge_raw', 'text')
    .addColumn('envelope_status', 'text', (col) => col.notNull())
    .addColumn('review_needed', 'boolean', (col) => col.notNull())
    .addColumn('loaded_at', 'timestamptz')
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addForeignKeyConstraint(
      'dockets_source_document_id_fkey',
      ['source_document_id'],
      'raw.source_documents',
      ['id'],
      (cb) => cb.onDelete('restrict'),
    )
    .addUniqueConstraint('dockets_source_document_id_key', ['source_document_id'])
    .execute();

  await db.schema
    .createTable('parsed.charges')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('docket_id', 'uuid', (col) => col.notNull())
    .addColumn('sequence', 'integer', (col) => col.notNull())
    .addColumn('statute', 'text')
    .addColumn('grade', 'text')
    .addColumn('offense', 'text')
    .addColumn('disposition_raw', 'text')
    .addColumn('disposition_date', 'date')
    .addColumn('disposition_judge_raw', 'text')
    .addColumn('event_name', 'text')
    .addColumn('event_date', 'date')
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addForeignKeyConstraint(
      'charges_docket_id_fkey',
      ['docket_id'],
      'parsed.dockets',
      ['id'],
      (cb) => cb.onDelete('cascade'),
    )
    .addUniqueConstraint('charges_docket_id_sequence_key', ['docket_id', 'sequence'])
    .execute();

  await db.schema
    .createTable('parsed.sentences')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('charge_id', 'uuid', (col) => col.notNull())
    .addColumn('component_order', 'integer', (col) => col.notNull())
    .addColumn('sentence_type', 'text', (col) => col.notNull())
    .addColumn('min_days', 'integer')
    .addColumn('max_days', 'integer')
    .addColumn('min_assumed', 'boolean', (col) => col.notNull().defaultTo(false))
    .addColumn('program', 'text')
    .addColumn('sentence_date', 'date')
    .addColumn('raw_text', 'text', (col) => col.notNull())
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addForeignKeyConstraint(
      'sentences_charge_id_fkey',
      ['charge_id'],
      'parsed.charges',
      ['id'],
      (cb) => cb.onDelete('cascade'),
    )
    .execute();

  await db.schema
    .createTable('parsed.warnings')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('docket_id', 'uuid', (col) => col.notNull())
    .addColumn('code', 'text', (col) => col.notNull())
    .addColumn('section', 'text')
    .addColumn('charge_sequence', 'integer')
    .addColumn('page', 'integer')
    .addColumn('field', 'text')
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addForeignKeyConstraint(
      'warnings_docket_id_fkey',
      ['docket_id'],
      'parsed.dockets',
      ['id'],
      (cb) => cb.onDelete('cascade'),
    )
    .execute();

  await db.schema
    .createTable('parsed.related_cases')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('docket_id', 'uuid', (col) => col.notNull())
    .addColumn('docket_number', 'text', (col) => col.notNull())
    .addColumn('court', 'text')
    .addColumn('association_reason', 'text')
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addForeignKeyConstraint(
      'related_cases_docket_id_fkey',
      ['docket_id'],
      'parsed.dockets',
      ['id'],
      (cb) => cb.onDelete('cascade'),
    )
    .execute();

  // FK indexes for FK columns not already covered by a leading unique index
  // (pinned decision 5). dockets.source_document_id and charges.docket_id are
  // covered by their unique constraints' indexes and get none here.
  await db.schema
    .createIndex('sentences_charge_id_idx')
    .on('parsed.sentences')
    .column('charge_id')
    .execute();

  await db.schema
    .createIndex('warnings_docket_id_idx')
    .on('parsed.warnings')
    .column('docket_id')
    .execute();

  await db.schema
    .createIndex('related_cases_docket_id_idx')
    .on('parsed.related_cases')
    .column('docket_id')
    .execute();
}

export async function down(db: Kysely<unknown>): Promise<void> {
  await db.schema.dropTable('parsed.related_cases').execute();
  await db.schema.dropTable('parsed.warnings').execute();
  await db.schema.dropTable('parsed.sentences').execute();
  await db.schema.dropTable('parsed.charges').execute();
  await db.schema.dropTable('parsed.dockets').execute();
}
