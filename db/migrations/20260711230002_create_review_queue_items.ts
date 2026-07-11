import type { Kysely } from 'kysely';
import { sql } from 'kysely';

// The review queue (task 21.2): the deduplicated worklist Sprint 6's admin
// review UI consumes. The 22.x/23.x review paths write these rows through the
// 22.1 helpers; nothing writes to them in this migration's task.
//
// review.queue_items is MUTABLE (pinned decision 1): Sprint 6 triage transitions
// `status` (open -> in_review -> resolved/dismissed), so it carries created_at +
// updated_at and reuses the shared `public.set_updated_at()` trigger (owned by
// 6.1, never recreated here).
//
// FK ON DELETE (pinned decision 2): review items are anchored to the source
// document and survive parsed reloads with their triage status intact.
// - source_document_id -> raw.source_documents: NOT NULL, RESTRICT. The anchor
//   cannot vanish out from under an open review item.
// - parsed_docket_id / parsed_charge_id / parsed_sentence_id -> parsed.*:
//   NULLABLE, SET NULL. A parsed reload mints new UUIDs; the review item's
//   parsed pointers null out while the item itself (and its status) survives,
//   re-anchorable via the source document.
//
// Dedup (pinned decisions 3 + 4): dedup_key is NOT NULL text under a DB UNIQUE
// constraint, composed deterministically from STABLE identifiers only —
// source_document_id (a raw.* UUID that survives reloads), item_type, and a
// structural locator (charge sequence, sentence component order, entity type /
// field as applicable). It incorporates NO parsed.* UUID, which reloads
// re-mint. The exact composition is documented in the fact_review_vocab.py
// docstring; 22.1 implements the builder, this table stores the result and
// enforces uniqueness.
//
// Data-hygiene (pinned decision + AC7): raw_value carries STRUCTURAL values
// only (never defendant-identifying content; docket numbers do not belong
// here) and candidate_context carries STRUCTURAL jsonb only. Both are
// documented as structural-only via column comments below and in db/README.md.
// No defendant-identifying column exists or is invited.
//
// FK indexes (pinned decision 6): dedup_key's unique index does not front any
// FK column, so every FK column gets a standalone index.
//
// `down` drops the trigger then the table (the trigger function is left intact,
// owned by 6.1).

export async function up(db: Kysely<unknown>): Promise<void> {
  await db.schema
    .createTable('review.queue_items')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('item_type', 'text', (col) => col.notNull())
    .addColumn('severity', 'text', (col) => col.notNull())
    .addColumn('source_document_id', 'uuid', (col) => col.notNull())
    .addColumn('parsed_docket_id', 'uuid')
    .addColumn('parsed_charge_id', 'uuid')
    .addColumn('parsed_sentence_id', 'uuid')
    .addColumn('entity_type', 'text')
    .addColumn('raw_value', 'text')
    .addColumn('candidate_context', 'jsonb')
    .addColumn('reason_code', 'text', (col) => col.notNull())
    .addColumn('status', 'text', (col) => col.notNull().defaultTo('open'))
    .addColumn('dedup_key', 'text', (col) => col.notNull())
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addColumn('updated_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addForeignKeyConstraint(
      'queue_items_source_document_id_fkey',
      ['source_document_id'],
      'raw.source_documents',
      ['id'],
      (cb) => cb.onDelete('restrict'),
    )
    .addForeignKeyConstraint(
      'queue_items_parsed_docket_id_fkey',
      ['parsed_docket_id'],
      'parsed.dockets',
      ['id'],
      (cb) => cb.onDelete('set null'),
    )
    .addForeignKeyConstraint(
      'queue_items_parsed_charge_id_fkey',
      ['parsed_charge_id'],
      'parsed.charges',
      ['id'],
      (cb) => cb.onDelete('set null'),
    )
    .addForeignKeyConstraint(
      'queue_items_parsed_sentence_id_fkey',
      ['parsed_sentence_id'],
      'parsed.sentences',
      ['id'],
      (cb) => cb.onDelete('set null'),
    )
    .addUniqueConstraint('queue_items_dedup_key_key', ['dedup_key'])
    .execute();

  await sql`
    COMMENT ON COLUMN review.queue_items.raw_value IS
      'Structural value only (e.g. an unmapped statute code or sentence_type). Never defendant-identifying content; docket numbers do not belong here.'
  `.execute(db);

  await sql`
    COMMENT ON COLUMN review.queue_items.candidate_context IS
      'Structural jsonb only (e.g. ambiguous-match candidate ids/slugs). Never raw docket text or defendant-identifying data.'
  `.execute(db);

  await sql`
    CREATE TRIGGER set_updated_at BEFORE UPDATE ON review.queue_items
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()
  `.execute(db);

  // FK indexes — dedup_key's unique index fronts no FK column, so each FK
  // column gets its own index.
  await db.schema
    .createIndex('queue_items_source_document_id_idx')
    .on('review.queue_items')
    .column('source_document_id')
    .execute();

  await db.schema
    .createIndex('queue_items_parsed_docket_id_idx')
    .on('review.queue_items')
    .column('parsed_docket_id')
    .execute();

  await db.schema
    .createIndex('queue_items_parsed_charge_id_idx')
    .on('review.queue_items')
    .column('parsed_charge_id')
    .execute();

  await db.schema
    .createIndex('queue_items_parsed_sentence_id_idx')
    .on('review.queue_items')
    .column('parsed_sentence_id')
    .execute();
}

export async function down(db: Kysely<unknown>): Promise<void> {
  await sql`DROP TRIGGER set_updated_at ON review.queue_items`.execute(db);
  await db.schema.dropTable('review.queue_items').execute();
}
