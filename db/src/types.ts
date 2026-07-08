import type { ColumnType, Generated } from 'kysely';

/**
 * Kysely table definitions, keyed by schema-qualified name.
 *
 * `updated_at` is typed `ColumnType<Date, never, never>`: it is set by the
 * `public.set_updated_at()` trigger (insert default + BEFORE UPDATE) and is
 * never application-managed, so neither inserts nor updates may write it.
 */

export interface NormalizedChargesTable {
  id: Generated<string>;
  slug: string;
  display_name: string;
  statute_code: string | null;
  grade: string | null;
  is_active: Generated<boolean>;
  created_at: Generated<Date>;
  updated_at: ColumnType<Date, never, never>;
}

export interface ChargeAliasesTable {
  id: Generated<string>;
  normalized_charge_id: string;
  alias_text: string;
  created_at: Generated<Date>;
}

export interface NormalizedJudgesTable {
  id: Generated<string>;
  slug: string;
  display_name: string;
  is_active: Generated<boolean>;
  created_at: Generated<Date>;
  updated_at: ColumnType<Date, never, never>;
}

export interface JudgeAliasesTable {
  id: Generated<string>;
  normalized_judge_id: string;
  alias_text: string;
  created_at: Generated<Date>;
}

export interface Database {
  'ref.normalized_charges': NormalizedChargesTable;
  'ref.charge_aliases': ChargeAliasesTable;
  'ref.normalized_judges': NormalizedJudgesTable;
  'ref.judge_aliases': JudgeAliasesTable;
}
