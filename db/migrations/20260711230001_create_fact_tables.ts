import type { Kysely } from 'kysely';
import { sql } from 'kysely';

// The fact layer (task 21.2): the Phase 23 fact builder's write target. Three
// tables — one mutable run-bookkeeping table plus two immutable fact tables.
// Nothing writes to them in this migration's task; the 23.2/23.3 builders do.
//
// Mutability (pinned decision 1):
// - fact.fact_build_runs is MUTABLE (status transitions in_progress ->
//   completed/failed during a build): created_at + updated_at + the shared
//   `public.set_updated_at()` trigger (owned by 6.1, never recreated here).
// - fact.charge_outcomes and fact.charge_sentences are IMMUTABLE load
//   artifacts: created_at only, NO updated_at, NO trigger. A rebuild deletes
//   and reinserts under a new run rather than updating in place; immutability
//   is enforced at the type level in db/src/types.ts (Immutable<>), mirroring
//   the analytics aggregate-row precedent (6.2).
//
// FK ON DELETE (pinned decision 2):
// - charge_outcomes.build_run_id, charge_sentences.build_run_id ->
//   fact.fact_build_runs: CASCADE (run deletion is the delete-and-reinsert
//   mechanism).
// - charge_sentences.charge_outcome_id -> fact.charge_outcomes: CASCADE
//   (a sentence fact never outlives its parent outcome fact).
// - all fact.* FKs into parsed.* (parsed_charge_id, parsed_docket_id,
//   parsed_sentence_id): RESTRICT — a parsed reload with dependent facts must
//   fail loudly; deleting the fact run first is a conscious operation.
// - fact.* FKs into ref.* (normalized_charge_id, normalized_judge_id):
//   RESTRICT — ref rows deactivate via is_active, never delete out from under
//   a fact.
//
// Natural keys + FK indexes (pinned decision 6 as amended in approval): each
// fact table carries a UNIQUE that DB-enforces "one fact candidate per parsed
// charge/sentence per build run" (Sprint 5 plan 23.2 AC1):
//   charge_outcomes  UNIQUE (build_run_id, parsed_charge_id)
//   charge_sentences UNIQUE (build_run_id, parsed_sentence_id)
// Each unique LEADS with build_run_id, so build_run_id needs no standalone FK
// index. The second column (parsed_charge_id / parsed_sentence_id) is NOT the
// leading column, so it keeps its own index, as do all remaining FK columns.
// Delete-and-reinsert semantics are unaffected: the build_run FK CASCADE stays
// the reinsert mechanism.
//
// Nullability judgment calls (stated in the completion report / worklog):
// normalized_charge_id and normalized_judge_id are NULLABLE (an unmatched
// charge/judge still produces an ineligible fact — "unmatched is a state",
// Sprint 5 SD 9). disposition_date is NULLABLE (a MISSING_DISPOSITION_DATE
// charge yields an ineligible fact, not a dropped one). min_days AND max_days
// are both NULLABLE, mirroring parsed.sentences: an UNPARSEABLE_DURATION
// component (e.g. "Life") carries no parseable duration and its fact must exist
// as an ineligible row, not be dropped or faked. parser_version and
// envelope_parser_version are `integer`, mirroring the 21.1
// parsed.dockets.record_parser_version / envelope_parser_version types exactly
// (no cross-layer type mismatch).
//
// `down` drops children before parents (FK-safe): sentences, outcomes, then the
// trigger and fact_build_runs. Plain drops, no CASCADE (loud-revert precedent).

export async function up(db: Kysely<unknown>): Promise<void> {
  await db.schema
    .createTable('fact.fact_build_runs')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('status', 'text', (col) => col.notNull())
    .addColumn('parser_version', 'integer', (col) => col.notNull())
    .addColumn('envelope_parser_version', 'integer', (col) => col.notNull())
    .addColumn('taxonomy_version', 'text', (col) => col.notNull())
    .addColumn('roster_snapshot_note', 'text')
    .addColumn('started_at', 'timestamptz', (col) => col.notNull())
    .addColumn('completed_at', 'timestamptz')
    .addColumn('counts', 'jsonb')
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addColumn('updated_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .execute();

  await sql`
    CREATE TRIGGER set_updated_at BEFORE UPDATE ON fact.fact_build_runs
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()
  `.execute(db);

  await db.schema
    .createTable('fact.charge_outcomes')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('build_run_id', 'uuid', (col) => col.notNull())
    .addColumn('parsed_charge_id', 'uuid', (col) => col.notNull())
    .addColumn('parsed_docket_id', 'uuid', (col) => col.notNull())
    .addColumn('normalized_charge_id', 'uuid')
    .addColumn('outcome_category_code', 'text', (col) => col.notNull())
    .addColumn('disposition_date', 'date')
    .addColumn('normalized_judge_id', 'uuid')
    .addColumn('judge_attribution_method', 'text')
    .addColumn('attribution_method', 'text', (col) => col.notNull())
    .addColumn('charge_match_method', 'text', (col) => col.notNull())
    .addColumn('outcome_match_method', 'text', (col) => col.notNull())
    .addColumn('mvp_eligible', 'boolean', (col) => col.notNull())
    .addColumn('public_eligible', 'boolean', (col) => col.notNull())
    .addColumn('judge_specific_eligible', 'boolean', (col) => col.notNull())
    .addColumn('ineligibility_reason_codes', sql`text[]`, (col) =>
      col.notNull().defaultTo(sql`'{}'::text[]`),
    )
    .addColumn('review_needed', 'boolean', (col) => col.notNull())
    .addColumn('taxonomy_version', 'text', (col) => col.notNull())
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addForeignKeyConstraint(
      'charge_outcomes_build_run_id_fkey',
      ['build_run_id'],
      'fact.fact_build_runs',
      ['id'],
      (cb) => cb.onDelete('cascade'),
    )
    .addForeignKeyConstraint(
      'charge_outcomes_parsed_charge_id_fkey',
      ['parsed_charge_id'],
      'parsed.charges',
      ['id'],
      (cb) => cb.onDelete('restrict'),
    )
    .addForeignKeyConstraint(
      'charge_outcomes_parsed_docket_id_fkey',
      ['parsed_docket_id'],
      'parsed.dockets',
      ['id'],
      (cb) => cb.onDelete('restrict'),
    )
    .addForeignKeyConstraint(
      'charge_outcomes_normalized_charge_id_fkey',
      ['normalized_charge_id'],
      'ref.normalized_charges',
      ['id'],
      (cb) => cb.onDelete('restrict'),
    )
    .addForeignKeyConstraint(
      'charge_outcomes_normalized_judge_id_fkey',
      ['normalized_judge_id'],
      'ref.normalized_judges',
      ['id'],
      (cb) => cb.onDelete('restrict'),
    )
    .addUniqueConstraint('charge_outcomes_build_run_id_parsed_charge_id_key', [
      'build_run_id',
      'parsed_charge_id',
    ])
    .execute();

  await db.schema
    .createTable('fact.charge_sentences')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('build_run_id', 'uuid', (col) => col.notNull())
    .addColumn('charge_outcome_id', 'uuid', (col) => col.notNull())
    .addColumn('parsed_sentence_id', 'uuid', (col) => col.notNull())
    .addColumn('normalized_charge_id', 'uuid')
    .addColumn('sentencing_category_code', 'text', (col) => col.notNull())
    .addColumn('sentence_date', 'date')
    .addColumn('min_days', 'integer')
    .addColumn('max_days', 'integer')
    .addColumn('min_assumed', 'boolean', (col) => col.notNull().defaultTo(false))
    .addColumn('amount_cents', 'bigint')
    .addColumn('normalized_judge_id', 'uuid')
    .addColumn('judge_attribution_method', 'text')
    .addColumn('attribution_method', 'text', (col) => col.notNull())
    .addColumn('component_match_method', 'text', (col) => col.notNull())
    .addColumn('mvp_eligible', 'boolean', (col) => col.notNull())
    .addColumn('public_eligible', 'boolean', (col) => col.notNull())
    .addColumn('judge_specific_eligible', 'boolean', (col) => col.notNull())
    .addColumn('ineligibility_reason_codes', sql`text[]`, (col) =>
      col.notNull().defaultTo(sql`'{}'::text[]`),
    )
    .addColumn('review_needed', 'boolean', (col) => col.notNull())
    .addColumn('taxonomy_version', 'text', (col) => col.notNull())
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addForeignKeyConstraint(
      'charge_sentences_build_run_id_fkey',
      ['build_run_id'],
      'fact.fact_build_runs',
      ['id'],
      (cb) => cb.onDelete('cascade'),
    )
    .addForeignKeyConstraint(
      'charge_sentences_charge_outcome_id_fkey',
      ['charge_outcome_id'],
      'fact.charge_outcomes',
      ['id'],
      (cb) => cb.onDelete('cascade'),
    )
    .addForeignKeyConstraint(
      'charge_sentences_parsed_sentence_id_fkey',
      ['parsed_sentence_id'],
      'parsed.sentences',
      ['id'],
      (cb) => cb.onDelete('restrict'),
    )
    .addForeignKeyConstraint(
      'charge_sentences_normalized_charge_id_fkey',
      ['normalized_charge_id'],
      'ref.normalized_charges',
      ['id'],
      (cb) => cb.onDelete('restrict'),
    )
    .addForeignKeyConstraint(
      'charge_sentences_normalized_judge_id_fkey',
      ['normalized_judge_id'],
      'ref.normalized_judges',
      ['id'],
      (cb) => cb.onDelete('restrict'),
    )
    .addUniqueConstraint('charge_sentences_build_run_id_parsed_sentence_id_key', [
      'build_run_id',
      'parsed_sentence_id',
    ])
    .execute();

  // FK indexes for FK columns not fronted by a leading unique index (pinned
  // decision 6). build_run_id on both tables leads its unique constraint and
  // gets none here; every other FK column does.
  await db.schema
    .createIndex('charge_outcomes_parsed_charge_id_idx')
    .on('fact.charge_outcomes')
    .column('parsed_charge_id')
    .execute();

  await db.schema
    .createIndex('charge_outcomes_parsed_docket_id_idx')
    .on('fact.charge_outcomes')
    .column('parsed_docket_id')
    .execute();

  await db.schema
    .createIndex('charge_outcomes_normalized_charge_id_idx')
    .on('fact.charge_outcomes')
    .column('normalized_charge_id')
    .execute();

  await db.schema
    .createIndex('charge_outcomes_normalized_judge_id_idx')
    .on('fact.charge_outcomes')
    .column('normalized_judge_id')
    .execute();

  await db.schema
    .createIndex('charge_sentences_parsed_sentence_id_idx')
    .on('fact.charge_sentences')
    .column('parsed_sentence_id')
    .execute();

  await db.schema
    .createIndex('charge_sentences_charge_outcome_id_idx')
    .on('fact.charge_sentences')
    .column('charge_outcome_id')
    .execute();

  await db.schema
    .createIndex('charge_sentences_normalized_charge_id_idx')
    .on('fact.charge_sentences')
    .column('normalized_charge_id')
    .execute();

  await db.schema
    .createIndex('charge_sentences_normalized_judge_id_idx')
    .on('fact.charge_sentences')
    .column('normalized_judge_id')
    .execute();
}

export async function down(db: Kysely<unknown>): Promise<void> {
  await db.schema.dropTable('fact.charge_sentences').execute();
  await db.schema.dropTable('fact.charge_outcomes').execute();
  await sql`DROP TRIGGER set_updated_at ON fact.fact_build_runs`.execute(db);
  await db.schema.dropTable('fact.fact_build_runs').execute();
}
