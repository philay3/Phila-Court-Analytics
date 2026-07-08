import type { ColumnType, Generated } from 'kysely';

/**
 * Kysely table definitions, keyed by schema-qualified name.
 *
 * `updated_at` is typed `ColumnType<Date, never, never>`: it is set by the
 * `public.set_updated_at()` trigger (insert default + BEFORE UPDATE) and is
 * never application-managed, so neither inserts nor updates may write it.
 *
 * The four analytics aggregate tables use `Immutable<>` (update position
 * `never`) on every column: aggregate rows are immutable by standing
 * decision, enforced at the type level rather than by any DB trigger. A
 * consequence is that these tables cannot be written via
 * `ON CONFLICT DO UPDATE` — seeding replaces rows by delete-and-reinsert
 * within a transaction.
 */

/** A column that can never be written by an UPDATE. */
type Immutable<Select, Insert = Select> = ColumnType<Select, Insert, never>;

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

export type AggregateRunStatus = 'in_progress' | 'completed' | 'failed';

export interface AggregateRunsTable {
  id: Generated<string>;
  status: AggregateRunStatus;
  started_at: ColumnType<Date, Date | string, Date | string>;
  completed_at: ColumnType<Date | null, Date | string | null, Date | string | null>;
  published_at: ColumnType<Date | null, Date | string | null, Date | string | null>;
  invalidated_at: ColumnType<Date | null, Date | string | null, Date | string | null>;
  invalidated_reason: string | null;
  parser_version: string | null;
  taxonomy_version: string;
  data_range_start: ColumnType<Date, Date | string, Date | string>;
  data_range_end: ColumnType<Date, Date | string, Date | string>;
  created_at: Generated<Date>;
  updated_at: ColumnType<Date, never, never>;
}

/**
 * Columns shared by all four aggregate tables. `percentage` is Postgres
 * `numeric(5,2)`: the `pg` driver returns numerics as strings to avoid
 * float precision loss, and inserts accept numbers or strings.
 */
interface AggregateRowBase {
  id: Immutable<string, string | undefined>;
  aggregate_run_id: Immutable<string>;
  charge_id: Immutable<string>;
  category_code: Immutable<string>;
  count: Immutable<number>;
  percentage: Immutable<string, number | string>;
  date_range_start: Immutable<Date, Date | string>;
  date_range_end: Immutable<Date, Date | string>;
  is_thin_data: Immutable<boolean>;
  taxonomy_version: Immutable<string>;
  created_at: Immutable<Date, Date | string | undefined>;
}

export interface ChargeOutcomeAggregatesTable extends AggregateRowBase {
  sample_size: Immutable<number>;
}

export interface ChargeSentencingAggregatesTable extends AggregateRowBase {
  sentencing_sample_size: Immutable<number>;
}

export interface JudgeOutcomeAggregatesTable extends AggregateRowBase {
  judge_id: Immutable<string>;
  sample_size: Immutable<number>;
}

export interface JudgeSentencingAggregatesTable extends AggregateRowBase {
  judge_id: Immutable<string>;
  sentencing_sample_size: Immutable<number>;
}

export interface Database {
  'ref.normalized_charges': NormalizedChargesTable;
  'ref.charge_aliases': ChargeAliasesTable;
  'ref.normalized_judges': NormalizedJudgesTable;
  'ref.judge_aliases': JudgeAliasesTable;
  'analytics.aggregate_runs': AggregateRunsTable;
  'analytics.charge_outcome_aggregates': ChargeOutcomeAggregatesTable;
  'analytics.charge_sentencing_aggregates': ChargeSentencingAggregatesTable;
  'analytics.judge_outcome_aggregates': JudgeOutcomeAggregatesTable;
  'analytics.judge_sentencing_aggregates': JudgeSentencingAggregatesTable;
}
