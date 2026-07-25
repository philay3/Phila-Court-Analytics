import type { Kysely } from 'kysely';
import { sql } from 'kysely';

// Phase 36: the charge-volume aggregate population — the deduplicated
// denominator behind "charges seen", one row per (run, charge).
//
// Deduplication happens UPSTREAM in the data (operator ruling 2026-07-25):
// an MC held charge traced to its CP continuation carries
// parsed.charges.superseded_by_charge_id and is folded into the CP side by
// the volume generator, so `charges_seen` counts charge JOURNEYS — never the
// same charge twice. Column semantics:
//
// - charges_seen      (> 0): journeys in the filed universe (docket
//   filed_date >= the 2025-01-01 floor, NULL fail-closed).
// - outcomes_recorded: journeys with a public-eligible recorded outcome —
//   equal by validation to the charge's outcome-aggregate sample_size in the
//   same run.
// - held_for_court:    held-form journeys with NO traced CP continuation
//   (includes time lag: CP cases not yet filed/collected — expected to
//   shrink on refreshes).
// - still_pending:     journeys awaiting any disposition.
// - disposed_excluded: journeys disposed but not fact-eligible.
// - held_superseded:   folded MC held rows (ops/provenance; NOT in the
//   closure sum — each folded row's journey is already counted above,
//   wherever its CP side stands).
//
// The closure CHECK is the wedge-identity precedent (35.1): stored rows
// cannot fail to add up. Validation re-asserts it in check-code form and owns
// the cross-table identities. Public display serves charges_seen +
// outcomes_recorded only (operator display ruling); the full breakdown feeds
// methodology-grade description and operator views.
//
// House conventions: UUID PK, run FK (NO ACTION), UNIQUE leading with
// aggregate_run_id, charge_id secondary index, immutable rows (created_at
// only; delete-and-reinsert per run), taxonomy_version stamped.

export async function up(db: Kysely<unknown>): Promise<void> {
  await db.schema
    .createTable('analytics.charge_volume_aggregates')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('aggregate_run_id', 'uuid', (col) => col.notNull())
    .addColumn('charge_id', 'uuid', (col) => col.notNull())
    .addColumn('charges_seen', 'integer', (col) => col.notNull())
    .addColumn('outcomes_recorded', 'integer', (col) => col.notNull())
    .addColumn('held_for_court', 'integer', (col) => col.notNull())
    .addColumn('still_pending', 'integer', (col) => col.notNull())
    .addColumn('disposed_excluded', 'integer', (col) => col.notNull())
    .addColumn('held_superseded', 'integer', (col) => col.notNull())
    .addColumn('taxonomy_version', 'text', (col) => col.notNull())
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addCheckConstraint('charge_volume_aggregates_charges_seen_check', sql`charges_seen > 0`)
    .addCheckConstraint(
      'charge_volume_aggregates_outcomes_recorded_check',
      sql`outcomes_recorded >= 0`,
    )
    .addCheckConstraint('charge_volume_aggregates_held_for_court_check', sql`held_for_court >= 0`)
    .addCheckConstraint('charge_volume_aggregates_still_pending_check', sql`still_pending >= 0`)
    .addCheckConstraint(
      'charge_volume_aggregates_disposed_excluded_check',
      sql`disposed_excluded >= 0`,
    )
    .addCheckConstraint('charge_volume_aggregates_held_superseded_check', sql`held_superseded >= 0`)
    .addCheckConstraint(
      'charge_volume_aggregates_closure_check',
      sql`outcomes_recorded + held_for_court + still_pending + disposed_excluded = charges_seen`,
    )
    .addForeignKeyConstraint(
      'charge_volume_aggregates_aggregate_run_id_fkey',
      ['aggregate_run_id'],
      'analytics.aggregate_runs',
      ['id'],
    )
    .addForeignKeyConstraint(
      'charge_volume_aggregates_charge_id_fkey',
      ['charge_id'],
      'ref.normalized_charges',
      ['id'],
    )
    .addUniqueConstraint('charge_volume_aggregates_run_charge_key', [
      'aggregate_run_id',
      'charge_id',
    ])
    .execute();

  await db.schema
    .createIndex('charge_volume_aggregates_charge_id_idx')
    .on('analytics.charge_volume_aggregates')
    .column('charge_id')
    .execute();
}

export async function down(db: Kysely<unknown>): Promise<void> {
  await db.schema.dropTable('analytics.charge_volume_aggregates').execute();
}
