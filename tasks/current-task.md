# Task 6.2 — `analytics.*` Table Migrations

## Goal

Create the five analytics-layer tables via one new Kysely migration:
`analytics.aggregate_runs`, `analytics.charge_outcome_aggregates`,
`analytics.charge_sentencing_aggregates`, `analytics.judge_outcome_aggregates`,
`analytics.judge_sentencing_aggregates`. These back the Sprint 2 public
result endpoints (8.1/8.2) and the seeded aggregate run (6.4).

## Context

- Migration runner, naming convention, and local Postgres (17.10, port 5433)
  exist from 2.1–2.3. Migration 6.1 created the `ref.*` tables, the shared
  `set_updated_at()` trigger function, and documented the naming convention
  in db/README.md (*_key unique constraints, *_idx indexes, *_fkey FKs).
- One migration file for all five tables (standing decision: FK-related
  tables shipping together go in one file).
- Privacy rule: `analytics.*` holds public aggregate data only. No defendant
  columns, no docket numbers, no source-document references, no parsed/fact
  record references.

## Standing decisions applied in this task

- UUID primary keys via gen_random_uuid() on all five tables.
- `analytics.aggregate_runs` gets created_at + updated_at with the existing
  set_updated_at() trigger attached (first reuse — do NOT recreate the
  function).
- Aggregate rows are immutable: the four aggregate tables get created_at
  only, no updated_at, no trigger.
- Publication model: a run is "active published" iff
  published_at IS NOT NULL AND invalidated_at IS NULL. At most one active
  published run may exist, enforced by a unique partial index.
- taxonomy_version and category_code are plain text — no FK to taxonomy
  tables (taxonomy is package-only through Sprint 2; DB taxonomy tables are
  Sprint 7).

## Table definitions

### analytics.aggregate_runs

- id uuid PK default gen_random_uuid()
- status text NOT NULL, CHECK status IN ('in_progress','completed','failed')
- started_at timestamptz NOT NULL
- completed_at timestamptz NULL
- published_at timestamptz NULL
- invalidated_at timestamptz NULL
- invalidated_reason text NULL
- parser_version text NULL (placeholder; real values arrive Sprint 4/5)
- taxonomy_version text NOT NULL
- data_range_start date NOT NULL
- data_range_end date NOT NULL
- created_at timestamptz NOT NULL default now()
- updated_at timestamptz NOT NULL default now() + set_updated_at() trigger

CHECK constraints:
- data_range_start <= data_range_end
- status = 'completed' OR completed_at IS NULL... specifically:
  (status <> 'completed') OR (completed_at IS NOT NULL) — completed runs
  must have a completion time
- published_at IS NULL OR status = 'completed' — only completed runs can
  be published
- invalidated_at IS NULL OR published_at IS NOT NULL — only published runs
  can be invalidated
- (invalidated_at IS NULL) = (invalidated_reason IS NULL) — reason required
  with invalidation, forbidden without

Unique partial index (at most one active published run):
- ON ((true)) WHERE published_at IS NOT NULL AND invalidated_at IS NULL
- name per convention: aggregate_runs_active_published_idx

### Common shape for the four aggregate tables

- id uuid PK default gen_random_uuid()
- aggregate_run_id uuid NOT NULL, FK -> analytics.aggregate_runs(id)
- charge_id uuid NOT NULL, FK -> ref.normalized_charges(id)
- judge_id uuid NOT NULL, FK -> ref.normalized_judges(id) — judge tables only
- category_code text NOT NULL
- count integer NOT NULL, CHECK count >= 0
- percentage numeric(5,2) NOT NULL, CHECK percentage BETWEEN 0 AND 100
- sample size column (see below), integer NOT NULL, CHECK > 0
- date_range_start date NOT NULL
- date_range_end date NOT NULL, CHECK date_range_start <= date_range_end
- is_thin_data boolean NOT NULL
- taxonomy_version text NOT NULL
- created_at timestamptz NOT NULL default now()
- NO updated_at (immutable rows)

Sample size naming:
- outcome tables: sample_size
- sentencing tables: sentencing_sample_size (kept distinct by name so
  outcome and sentencing sample sizes can never be silently conflated when
  building API payloads)

Unique constraints (also the ON CONFLICT keys for 6.4 seeding):
- charge tables: (aggregate_run_id, charge_id, category_code)
- judge tables: (aggregate_run_id, charge_id, judge_id, category_code)

Secondary indexes (FKs are not auto-indexed in Postgres):
- charge_id on all four tables
- judge_id on the two judge tables

FK behavior: default NO ACTION everywhere. No CASCADE — deleting a ref row
must never silently delete published aggregates; ref rows deactivate via
their active flag instead.

## Migration mechanics

- One migration file, established naming convention.
- Down migration drops the four aggregate tables first, then aggregate_runs
  (FK-safe order), plain dropTable, no CASCADE. Do NOT drop the
  set_updated_at() function — it is owned by migration 6.1.
- Update db/src/types.ts: add all five tables to the Database interface with
  schema-qualified keys ('analytics.aggregate_runs', etc.), Generated<> for
  defaulted columns (id, created_at, updated_at).

## Verification requirements

- Migration applies, rolls back, and reapplies cleanly against local
  Postgres (fresh db:reset cycle).
- Violating-insert checks run inside a transaction that is rolled back
  (6.1 precedent — no insert-then-delete), covering at minimum:
  - FK violation on aggregate_run_id, charge_id, judge_id
  - status CHECK violation
  - publishing a non-completed run (published_at CHECK)
  - invalidation without reason (paired CHECK)
  - second active published run rejected by the partial unique index
  - duplicate (run, charge, category) rejected by unique constraint
  - percentage out of range
- Trigger check: UPDATE on aggregate_runs advances updated_at.
- lint, typecheck, format:check, tests pass.

## Out of scope

- Seed data of any kind (6.3 reference seeds, 6.4 aggregate seeds).
- Any API endpoint work.
- ref.outcome_categories / ref.sentencing_categories tables (Sprint 7).
- A CHECK enforcing data_range_start >= 2025-01-01 — the MVP window is a
  data policy enforced in 6.4 seeds and Sprint 7 aggregate validation, not
  a schema invariant.
- sum(count) = sample_size consistency — cross-row invariant; enforced in
  6.4 seed assertions and Sprint 7 aggregate validation.

## Files the agent may touch

- db/migrations/ (one new migration file)
- db/src/types.ts
- db/README.md (only if a naming-convention note needs extending)
- tasks/worklog.md (append entry on completion)

## Process

Return an implementation plan before writing any code. Flag any point where
you'd deviate from this spec.