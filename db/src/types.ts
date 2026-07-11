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

/**
 * The internal source-document layer (task 21.1), mirroring the 16.3
 * manual-import metadata record. MUTABLE: `updated_at` is trigger-managed
 * (`ColumnType<Date, never, never>`, 6.1 precedent). `file_size_bytes` is
 * Postgres `bigint`, which the `pg` driver returns as a string. `court_type`
 * here is the raw CP/MC filename code (distinct from
 * `parsed.dockets.court_type_recorded`).
 */
export interface RawSourceDocumentsTable {
  id: Generated<string>;
  file_hash: string;
  original_filename: string;
  file_size_bytes: ColumnType<string, number | string, number | string>;
  imported_at: ColumnType<Date, Date | string, Date | string>;
  import_mode: string;
  status: string;
  error_code: string | null;
  docket_number_provenance: string | null;
  court_type: string | null;
  county: string | null;
  created_at: Generated<Date>;
  updated_at: ColumnType<Date, never, never>;
}

/**
 * The parsed layer (task 21.1): the 21.3 loader's write target, mirroring the
 * 17.2 parser record + 18.1 envelope. All five tables are immutable load
 * artifacts — every column uses `Immutable<>` (update position `never`),
 * matching the analytics aggregate-row precedent. `cross_court_dockets` is
 * `jsonb`; `court_type_derived` and `loaded_at` are populated by the 21.3
 * loader (nullable until then).
 */
export interface ParsedDocketsTable {
  id: Immutable<string, string | undefined>;
  source_document_id: Immutable<string>;
  docket_number: Immutable<string>;
  record_parser_version: Immutable<number>;
  envelope_parser_version: Immutable<number>;
  parsed_at: Immutable<Date, Date | string>;
  county: Immutable<string>;
  court_type_recorded: Immutable<string | null>;
  court_type_derived: Immutable<string | null>;
  case_status: Immutable<string | null>;
  filed_date: Immutable<Date | null, Date | string | null>;
  otn: Immutable<string | null>;
  dc_number: Immutable<string | null>;
  cross_court_dockets: Immutable<unknown | null>;
  defendant_hash: Immutable<string>;
  assigned_judge_raw: Immutable<string | null>;
  envelope_status: Immutable<string>;
  review_needed: Immutable<boolean>;
  loaded_at: Immutable<Date | null, Date | string | null>;
  created_at: Immutable<Date, Date | string | undefined>;
}

export interface ParsedChargesTable {
  id: Immutable<string, string | undefined>;
  docket_id: Immutable<string>;
  sequence: Immutable<number>;
  statute: Immutable<string | null>;
  grade: Immutable<string | null>;
  offense: Immutable<string | null>;
  disposition_raw: Immutable<string | null>;
  disposition_date: Immutable<Date | null, Date | string | null>;
  disposition_judge_raw: Immutable<string | null>;
  event_name: Immutable<string | null>;
  event_date: Immutable<Date | null, Date | string | null>;
  created_at: Immutable<Date, Date | string | undefined>;
}

export interface ParsedSentencesTable {
  id: Immutable<string, string | undefined>;
  charge_id: Immutable<string>;
  component_order: Immutable<number>;
  sentence_type: Immutable<string>;
  min_days: Immutable<number | null>;
  max_days: Immutable<number | null>;
  min_assumed: Immutable<boolean, boolean | undefined>;
  program: Immutable<string | null>;
  sentence_date: Immutable<Date | null, Date | string | null>;
  raw_text: Immutable<string>;
  created_at: Immutable<Date, Date | string | undefined>;
}

export interface ParsedWarningsTable {
  id: Immutable<string, string | undefined>;
  docket_id: Immutable<string>;
  code: Immutable<string>;
  section: Immutable<string | null>;
  charge_sequence: Immutable<number | null>;
  page: Immutable<number | null>;
  field: Immutable<string | null>;
  created_at: Immutable<Date, Date | string | undefined>;
}

export interface ParsedRelatedCasesTable {
  id: Immutable<string, string | undefined>;
  docket_id: Immutable<string>;
  docket_number: Immutable<string>;
  court: Immutable<string | null>;
  association_reason: Immutable<string | null>;
  created_at: Immutable<Date, Date | string | undefined>;
}

/**
 * The fact layer (task 21.2): the Phase 23 fact builder's write target.
 *
 * `fact.fact_build_runs` is MUTABLE (status transitions during a build):
 * `updated_at` is trigger-managed (`ColumnType<Date, never, never>`, 6.1
 * precedent). `parser_version` and `envelope_parser_version` are `integer`,
 * mirroring the 21.1 `parsed.dockets` column types exactly. `counts` is
 * nullable `jsonb` (null while in_progress).
 */
export type FactBuildRunStatus = 'in_progress' | 'completed' | 'failed';

export interface FactBuildRunsTable {
  id: Generated<string>;
  status: FactBuildRunStatus;
  parser_version: number;
  envelope_parser_version: number;
  taxonomy_version: string;
  roster_snapshot_note: string | null;
  started_at: ColumnType<Date, Date | string, Date | string>;
  completed_at: ColumnType<Date | null, Date | string | null, Date | string | null>;
  counts: ColumnType<unknown | null, unknown | null, unknown | null>;
  created_at: Generated<Date>;
  updated_at: ColumnType<Date, never, never>;
}

/**
 * `fact.charge_outcomes` and `fact.charge_sentences` are IMMUTABLE fact
 * artifacts — every column uses `Immutable<>` (update position `never`),
 * matching the analytics aggregate-row precedent. A rebuild is delete-and-
 * reinsert under a new run, never an UPDATE. `normalized_charge_id` /
 * `normalized_judge_id` / `disposition_date` are nullable (unmatched charge /
 * judge and missing disposition date still produce ineligible facts).
 * `ineligibility_reason_codes` is `text[]` with a `'{}'` default (insert
 * optional). `amount_cents` is `bigint`, which the `pg` driver returns as a
 * string.
 */
export interface ChargeOutcomesTable {
  id: Immutable<string, string | undefined>;
  build_run_id: Immutable<string>;
  parsed_charge_id: Immutable<string>;
  parsed_docket_id: Immutable<string>;
  normalized_charge_id: Immutable<string | null>;
  outcome_category_code: Immutable<string>;
  disposition_date: Immutable<Date | null, Date | string | null>;
  normalized_judge_id: Immutable<string | null>;
  judge_attribution_method: Immutable<string | null>;
  attribution_method: Immutable<string>;
  charge_match_method: Immutable<string>;
  outcome_match_method: Immutable<string>;
  mvp_eligible: Immutable<boolean>;
  public_eligible: Immutable<boolean>;
  judge_specific_eligible: Immutable<boolean>;
  ineligibility_reason_codes: Immutable<string[], string[] | undefined>;
  review_needed: Immutable<boolean>;
  taxonomy_version: Immutable<string>;
  created_at: Immutable<Date, Date | string | undefined>;
}

export interface ChargeSentencesTable {
  id: Immutable<string, string | undefined>;
  build_run_id: Immutable<string>;
  charge_outcome_id: Immutable<string>;
  parsed_sentence_id: Immutable<string>;
  normalized_charge_id: Immutable<string | null>;
  sentencing_category_code: Immutable<string>;
  sentence_date: Immutable<Date | null, Date | string | null>;
  min_days: Immutable<number | null>;
  max_days: Immutable<number | null>;
  min_assumed: Immutable<boolean, boolean | undefined>;
  amount_cents: Immutable<string | null, number | string | null>;
  normalized_judge_id: Immutable<string | null>;
  judge_attribution_method: Immutable<string | null>;
  attribution_method: Immutable<string>;
  component_match_method: Immutable<string>;
  mvp_eligible: Immutable<boolean>;
  public_eligible: Immutable<boolean>;
  judge_specific_eligible: Immutable<boolean>;
  ineligibility_reason_codes: Immutable<string[], string[] | undefined>;
  review_needed: Immutable<boolean>;
  taxonomy_version: Immutable<string>;
  created_at: Immutable<Date, Date | string | undefined>;
}

/**
 * The review queue (task 21.2): the deduplicated worklist Sprint 6 consumes.
 * MUTABLE — Sprint 6 triage transitions `status` (default `open`, hence insert
 * optional + update-writable); `updated_at` is trigger-managed. `raw_value`
 * and `candidate_context` carry structural values only (never defendant-
 * identifying data). `dedup_key` is the DB-unique idempotency key.
 */
export interface ReviewQueueItemsTable {
  id: Generated<string>;
  item_type: string;
  severity: string;
  source_document_id: string;
  parsed_docket_id: string | null;
  parsed_charge_id: string | null;
  parsed_sentence_id: string | null;
  entity_type: string | null;
  raw_value: string | null;
  candidate_context: ColumnType<unknown | null, unknown | null, unknown | null>;
  reason_code: string;
  status: ColumnType<string, string | undefined, string>;
  dedup_key: string;
  created_at: Generated<Date>;
  updated_at: ColumnType<Date, never, never>;
}

export interface Database {
  'raw.source_documents': RawSourceDocumentsTable;
  'parsed.dockets': ParsedDocketsTable;
  'parsed.charges': ParsedChargesTable;
  'parsed.sentences': ParsedSentencesTable;
  'parsed.warnings': ParsedWarningsTable;
  'parsed.related_cases': ParsedRelatedCasesTable;
  'fact.fact_build_runs': FactBuildRunsTable;
  'fact.charge_outcomes': ChargeOutcomesTable;
  'fact.charge_sentences': ChargeSentencesTable;
  'review.queue_items': ReviewQueueItemsTable;
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
