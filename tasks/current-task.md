# Task 6.3 — Seed Runner + Reference Seeds

## Goal

Create the database seed infrastructure and seed the reference layer:
normalized charges with aliases and obviously-fake normalized judges with
aliases. This is the first task that inserts rows. Aggregate seeds are the
NEXT task (6.4) and are out of scope here.

## Context

- Migrations 6.1/6.2 created all ref.* and analytics.* tables. Schemas-only
  migration 2.3 preceded them.
- Standing decision: seeds are TypeScript, live in db/seeds/, run through
  Kysely, idempotent via ON CONFLICT upserts, root script `db:seed`.
- Standing decision: reference seeds use standard ON CONFLICT upserts
  (aggregate seeds in 6.4 will use delete-and-reinsert instead — not your
  concern in this task).
- Standing decision: seeded judges must have obviously fake names. Fabricated
  statistics must never be attachable to a real Philadelphia judge. Charges
  use real statute names (statutes are not people).
- ref.* tables use UUID PKs (gen_random_uuid()), slug as the public lookup
  key, trigger-maintained updated_at.

## Scope

### 1. Alias uniqueness (verify or migrate)

Seeds upsert aliases keyed on (normalized_charge_id, alias_text) and
(normalized_judge_id, alias_text). Check whether migration 6.1 created unique
constraints on those pairs.

- If they exist: state so in your implementation plan and proceed.
- If not: add ONE new migration (following the established naming convention
  and *_key naming) that adds both unique constraints. Do not modify the 6.1
  migration file.

### 2. Seed infrastructure

- db/seeds/ directory, TypeScript, executed through Kysely using the existing
  db package connection/config conventions.
- A single entrypoint that runs all reference seeds in order
  (charges → charge aliases → judges → judge aliases).
- Root script `db:seed` wired in the root package.json.
- Seeds are idempotent: running `db:seed` twice produces identical database
  state — no duplicate rows, no errors, no spurious updated_at churn beyond
  what an upsert implies.
- Seed run must NOT touch analytics.* tables.
- Structured console output: which seed ran, how many rows upserted. No
  raw SQL dumps.

### 3. Reference seed data

Charges (5, real Pennsylvania statutes), each with at least one alias:

| slug | display name | statute | alias(es) |
|---|---|---|---|
| retail-theft | Retail Theft | 18 § 3929 | "shoplifting" |
| simple-assault | Simple Assault | 18 § 2701 | "assault (simple)" |
| dui-general-impairment | DUI: General Impairment | 75 § 3802(a)(1) | "driving under the influence", "drunk driving" |
| possession-controlled-substance | Possession of a Controlled Substance | 35 § 780-113(a)(16) | "drug possession" |
| criminal-trespass | Criminal Trespass | 18 § 3503 | "trespassing" |

Judges (3, obviously fake — names that no real person plausibly holds),
each with at least one alias:

| slug | display name | alias(es) |
|---|---|---|
| judge-testina-placeholder | Judge Testina Placeholder | "T. Placeholder" |
| judge-samuel-seeddata | Judge Samuel Seeddata | "S. Seeddata" |
| judge-fakename-example | Judge Fakename Example | "F. Example" |

- All records active.
- Grade may be left null (grades vary by offense circumstances; do not
  invent them).

### 4. Tests

- A test (Vitest, in the db package or wherever db tests live per repo
  convention) that runs the seed twice against the local database and
  asserts: row counts unchanged after second run, no errors, aliases
  resolve to their parent records.
- If existing test setup can't hit the local DB, say so in your plan and
  propose the minimal correct approach — do not silently skip the test.

## Acceptance Criteria

1. Alias unique constraints on (parent_id, alias_text) exist for both alias
   tables (pre-existing or via one new migration).
2. db/seeds/ exists with a TypeScript entrypoint run via Kysely.
3. Root `db:seed` script works from repo root.
4. Exactly 5 charges, 3 judges seeded, each with ≥1 alias, matching the
   tables above.
5. Judges are obviously fake per the table; no real-sounding names.
6. Running `db:seed` twice: no duplicates, no errors, identical state.
7. analytics.* untouched by the seed run.
8. Idempotency test exists and passes.
9. No defendant-identifying data, no raw docket data, no secrets.
10. Worklog entry appended to tasks/worklog.md.

## Out of Scope

- Aggregate seeds of any kind (task 6.4).
- analytics.* rows, aggregate runs, published-run logic.
- ref.outcome_categories / ref.sentencing_categories tables (deferred to
  Sprint 7 per standing decision).
- Any API endpoint work.
- Modifying existing 6.1/6.2 migration files.

## Files You May Touch

- db/seeds/** (new)
- db/migrations/** (one new file ONLY if alias unique constraints are missing)
- db/src/** (only if seed code needs a small shared helper; justify in plan)
- db/package.json, root package.json (scripts)
- db test files per repo convention
- tasks/worklog.md

## Process

Return an implementation plan BEFORE writing code. The plan must state
whether the alias unique constraints already exist in 6.1, and where the
idempotency test will live and how it connects to the local DB.