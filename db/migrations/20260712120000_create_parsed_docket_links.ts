import type { Kysely } from 'kysely';
import { sql } from 'kysely';

// parsed.docket_links (Task 23.5): structured CP<->MC held-case linkage — the 18.3
// deferral landing. One row per (MC held source docket -> CP target docket number)
// reference the linker parses from parsed.dockets.cross_court_dockets. Written by the
// Python linker inside `pipeline build-facts`; the DDL-in-TypeScript / consumer-in-
// Python split is expected (SD 4: Kysely owns ALL DDL, including Python-only tables).
//
// INFORMATIONAL ONLY (AC4): linkage does NOT feed fact eligibility. Attribution
// consequences of held-case linkage are a Sprint 7 aggregation question, deferred.
//
// Lifecycle (pinned decision 3 / SD 6 delete-and-reinsert): the linker rebuilds the
// whole table each build — link rows are a current-state projection of the corpus +
// linker logic, never a durable human-touched artifact. Immutable per row: created_at
// only, NO updated_at, NO set_updated_at trigger (the parsed load-artifact pattern;
// contrast review.queue_items, which is mutable and trigger-managed).
//
// FKs — both into parsed.dockets, both ON DELETE CASCADE:
//  - source_docket_id: OWNERSHIP (the MC docket the link is read from); an MC-docket
//    reload deletes its links.
//  - target_docket_id (nullable; set only when the CP target is in-corpus):
//    CROSS-REFERENCE. CASCADE is deliberate — RESTRICT would block a legitimate CP
//    target reload, and SET NULL would silently degrade a resolved link into a
//    null-FK row indistinguishable from out-of-corpus. Under full-rebuild CASCADE
//    self-heals: a reloaded target's links drop and are rebuilt on the next build.
//
// FK indexes (pinned decision 5): the unique constraint's index LEADS with
// source_docket_id, so that FK needs no separate index; the nullable target_docket_id
// FK is not covered by a leading unique index and gets an explicit *_idx.
//
// Vocab columns (link_type, evidence_source) are plain text — no CHECK, no enum;
// membership is enforced in Python (link_vocab.py), the parser/fact_review_vocab
// precedent. The UNIQUE(source_docket_id, target_docket_number, link_type) is the
// link natural key (name abbreviated to stay within the 63-char identifier limit).
//
// `down` drops the table (plain drop, loud-revert precedent).

export async function up(db: Kysely<unknown>): Promise<void> {
  await db.schema
    .createTable('parsed.docket_links')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('source_docket_id', 'uuid', (col) => col.notNull())
    .addColumn('target_docket_number', 'text', (col) => col.notNull())
    .addColumn('target_docket_id', 'uuid')
    .addColumn('link_type', 'text', (col) => col.notNull())
    .addColumn('evidence_source', 'text', (col) => col.notNull())
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addForeignKeyConstraint(
      'docket_links_source_docket_id_fkey',
      ['source_docket_id'],
      'parsed.dockets',
      ['id'],
      (cb) => cb.onDelete('cascade'),
    )
    .addForeignKeyConstraint(
      'docket_links_target_docket_id_fkey',
      ['target_docket_id'],
      'parsed.dockets',
      ['id'],
      (cb) => cb.onDelete('cascade'),
    )
    // Natural key: (source docket, target docket number, link type). Name abbreviated
    // to fit the 63-char identifier limit; its index leads with source_docket_id, so
    // that FK gets no separate index (pinned decision 5).
    .addUniqueConstraint('docket_links_source_target_link_type_key', [
      'source_docket_id',
      'target_docket_number',
      'link_type',
    ])
    .execute();

  // Explicit index for the nullable target_docket_id FK (not fronted by a leading
  // unique index; pinned decision 5).
  await db.schema
    .createIndex('docket_links_target_docket_id_idx')
    .on('parsed.docket_links')
    .column('target_docket_id')
    .execute();
}

export async function down(db: Kysely<unknown>): Promise<void> {
  await db.schema.dropTable('parsed.docket_links').execute();
}
