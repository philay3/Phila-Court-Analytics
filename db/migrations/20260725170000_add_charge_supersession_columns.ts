import type { Kysely } from 'kysely';
import { sql } from 'kysely';

// Phase 36 dedupe (operator ruling 2026-07-25): fix MC→CP double counting at
// the root, in the data. Three columns:
//
// - parsed.dockets.originating_docket_no (text, null): the CP sheet's Case
//   Information pointer at its parent MC case — the authoritative CP→MC
//   continuation evidence. Captured by record parser v3; null on v2-era rows
//   until the reload.
//
// - parsed.charges.orig_seq (integer, null): the charge table's "Orig Seq"
//   column — the charge's sequence on the originating docket, the
//   deterministic charge-level join key. Captured by record parser v3.
//
// - parsed.charges.superseded_by_charge_id (uuid, null, FK → parsed.charges
//   ON DELETE SET NULL): points an MC held charge at the CP charge it
//   continues as. THE dedupe pointer — every volume-style count filters
//   `WHERE superseded_by_charge_id IS NULL`. Derived, never parsed: the fact
//   build re-derives the whole mapping each run (clear + re-point) from the
//   deterministic join (CP.originating_docket_no = MC.docket_number AND OTN
//   match AND CP.orig_seq = MC.sequence AND statute match, MC side currently
//   held-form only), and `pipeline backfill-charge-supersession` runs the
//   same derivation standalone. ON DELETE SET NULL so a re-parse that
//   replaces the CP graph clears stale pointers instead of blocking the
//   delete; the next build re-points them.
//
// Doctrine note: parsed.* rows stay immutable load artifacts in every parsed
// column; superseded_by_charge_id is the single DERIVED column on the layer,
// operator-ruled, and is excluded from that contract (see db/src/types.ts).

export async function up(db: Kysely<unknown>): Promise<void> {
  await db.schema.alterTable('parsed.dockets').addColumn('originating_docket_no', 'text').execute();

  await db.schema.alterTable('parsed.charges').addColumn('orig_seq', 'integer').execute();

  await db.schema
    .alterTable('parsed.charges')
    .addColumn('superseded_by_charge_id', 'uuid', (col) =>
      col.references('parsed.charges.id').onDelete('set null'),
    )
    .execute();

  // The CP→MC case-level join probes MC dockets by docket_number (already
  // indexed) and CP dockets by originating presence; partial indexes keep
  // both cheap and skip the (large) null majority.
  await db.schema
    .createIndex('dockets_originating_docket_no_idx')
    .on('parsed.dockets')
    .column('originating_docket_no')
    .where(sql.ref('originating_docket_no'), 'is not', null)
    .execute();

  await db.schema
    .createIndex('charges_superseded_by_charge_id_idx')
    .on('parsed.charges')
    .column('superseded_by_charge_id')
    .where(sql.ref('superseded_by_charge_id'), 'is not', null)
    .execute();
}

export async function down(db: Kysely<unknown>): Promise<void> {
  await db.schema.dropIndex('charges_superseded_by_charge_id_idx').execute();
  await db.schema.dropIndex('dockets_originating_docket_no_idx').execute();
  await db.schema.alterTable('parsed.charges').dropColumn('superseded_by_charge_id').execute();
  await db.schema.alterTable('parsed.charges').dropColumn('orig_seq').execute();
  await db.schema.alterTable('parsed.dockets').dropColumn('originating_docket_no').execute();
}
