import type { Kysely } from 'kysely';
import { sql } from 'kysely';

// First reference-layer tables: normalized public entities (charges, judges)
// and their alias lookup tables. ref.* holds normalized public entities only —
// no defendant data, docket numbers, or source-document references.
//
// `public.set_updated_at()` lives in `public`, not `ref`: the standing
// decision is that every table with an `updated_at` column (current and
// future, in any schema) uses this trigger, so the function belongs in the
// shared schema rather than coupling other schemas to `ref`.
//
// `down` drops the triggers, then the tables (aliases before parents, FK-safe,
// no CASCADE — reverts fail loudly if anything unexpected depends on them),
// then the function. Constraints and indexes are dropped with their tables.

export async function up(db: Kysely<unknown>): Promise<void> {
  await sql`
    CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      NEW.updated_at = now();
      RETURN NEW;
    END;
    $$
  `.execute(db);

  await db.schema
    .createTable('ref.normalized_charges')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('slug', 'text', (col) => col.notNull())
    .addColumn('display_name', 'text', (col) => col.notNull())
    .addColumn('statute_code', 'text')
    .addColumn('grade', 'text')
    .addColumn('is_active', 'boolean', (col) => col.notNull().defaultTo(true))
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addColumn('updated_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addUniqueConstraint('normalized_charges_slug_key', ['slug'])
    .execute();

  await db.schema
    .createTable('ref.charge_aliases')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('normalized_charge_id', 'uuid', (col) => col.notNull())
    .addColumn('alias_text', 'text', (col) => col.notNull())
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addForeignKeyConstraint(
      'charge_aliases_normalized_charge_id_fkey',
      ['normalized_charge_id'],
      'ref.normalized_charges',
      ['id'],
      (cb) => cb.onDelete('cascade'),
    )
    .addUniqueConstraint('charge_aliases_normalized_charge_id_alias_text_key', [
      'normalized_charge_id',
      'alias_text',
    ])
    .execute();

  await db.schema
    .createTable('ref.normalized_judges')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('slug', 'text', (col) => col.notNull())
    .addColumn('display_name', 'text', (col) => col.notNull())
    .addColumn('is_active', 'boolean', (col) => col.notNull().defaultTo(true))
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addColumn('updated_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addUniqueConstraint('normalized_judges_slug_key', ['slug'])
    .execute();

  await db.schema
    .createTable('ref.judge_aliases')
    .addColumn('id', 'uuid', (col) => col.primaryKey().defaultTo(sql`gen_random_uuid()`))
    .addColumn('normalized_judge_id', 'uuid', (col) => col.notNull())
    .addColumn('alias_text', 'text', (col) => col.notNull())
    .addColumn('created_at', 'timestamptz', (col) => col.notNull().defaultTo(sql`now()`))
    .addForeignKeyConstraint(
      'judge_aliases_normalized_judge_id_fkey',
      ['normalized_judge_id'],
      'ref.normalized_judges',
      ['id'],
      (cb) => cb.onDelete('cascade'),
    )
    .addUniqueConstraint('judge_aliases_normalized_judge_id_alias_text_key', [
      'normalized_judge_id',
      'alias_text',
    ])
    .execute();

  await db.schema
    .createIndex('charge_aliases_alias_text_idx')
    .on('ref.charge_aliases')
    .column('alias_text')
    .execute();

  await db.schema
    .createIndex('judge_aliases_alias_text_idx')
    .on('ref.judge_aliases')
    .column('alias_text')
    .execute();

  await sql`
    CREATE TRIGGER set_updated_at BEFORE UPDATE ON ref.normalized_charges
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()
  `.execute(db);

  await sql`
    CREATE TRIGGER set_updated_at BEFORE UPDATE ON ref.normalized_judges
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()
  `.execute(db);
}

export async function down(db: Kysely<unknown>): Promise<void> {
  await sql`DROP TRIGGER set_updated_at ON ref.normalized_judges`.execute(db);
  await sql`DROP TRIGGER set_updated_at ON ref.normalized_charges`.execute(db);
  await db.schema.dropTable('ref.judge_aliases').execute();
  await db.schema.dropTable('ref.normalized_judges').execute();
  await db.schema.dropTable('ref.charge_aliases').execute();
  await db.schema.dropTable('ref.normalized_charges').execute();
  await sql`DROP FUNCTION public.set_updated_at()`.execute(db);
}
