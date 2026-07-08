Task 6.1 — ref.* Table Migrations
Goal
Create the four reference-layer tables (ref.normalized_charges, ref.charge_aliases, ref.normalized_judges, ref.judge_aliases) via new Kysely migrations. Sprint 1's migration 2.3 created the eight schemas only; this task adds the first real tables.
Context

Migration runner, naming convention, and local Postgres (17.10, port 5433) already exist from tasks 2.1–2.3. Follow the documented naming convention exactly.
These tables back the Sprint 2 seeded public API: charge/judge search (7.2/7.3) and result endpoints (8.x) will FK into them.
Privacy rule: ref.* holds normalized public entities only. No defendant-related columns, no docket numbers, no source-document references.

Standing decision for this task

Primary keys are UUIDs generated with gen_random_uuid() (Postgres built-in; no extension).
slug is the unique, public, URL-stable lookup key on both normalized_charges and normalized_judges.

Scope
One migration file (or two, one for charges and one for judges, if that fits the established convention better — agent's call, justify in the plan) creating:
ref.normalized_charges

id uuid PK default gen_random_uuid()
slug text, unique, not null
display_name text, not null
statute_code text, nullable
grade text, nullable
is_active boolean, not null, default true
created_at / updated_at timestamptz, not null, default now()

ref.charge_aliases

id uuid PK default gen_random_uuid()
normalized_charge_id uuid, not null, FK → ref.normalized_charges(id), ON DELETE CASCADE
alias_text text, not null
created_at timestamptz, not null, default now()
unique constraint on (normalized_charge_id, alias_text)

ref.normalized_judges

id uuid PK default gen_random_uuid()
slug text, unique, not null
display_name text, not null
is_active boolean, not null, default true
created_at / updated_at timestamptz, not null, default now()

ref.judge_aliases

id uuid PK default gen_random_uuid()
normalized_judge_id uuid, not null, FK → ref.normalized_judges(id), ON DELETE CASCADE
alias_text text, not null
created_at timestamptz, not null, default now()
unique constraint on (normalized_judge_id, alias_text)

Indexes

Unique indexes come from the constraints above.
Add non-unique indexes on charge_aliases.alias_text and judge_aliases.alias_text (search endpoints will query these in 7.2/7.3). Plain b-tree is sufficient for this sprint; trigram/FTS is out of scope.

Kysely types

Update the Kysely Database interface (wherever 2.2 established it) with typed definitions for all four tables, following the existing pattern for schema-qualified tables.

Acceptance criteria

Migrations follow the established naming convention and run via the existing runner.
up applies cleanly against local Postgres; down rolls back cleanly (tables dropped in FK-safe order).
Unique constraints on both slugs; FKs enforced; alias uniqueness per parent enforced.
Alias alias_text columns are indexed.
Kysely Database types updated and typecheck passes.
No defendant-related columns, docket numbers, or source-document references anywhere in ref.*.
Worklog entry appended to tasks/worklog.md.

Out of scope

analytics.* tables (task 6.2)
Seed data (tasks 6.3/6.4)
Trigram/full-text search indexes
ref.outcome_categories / ref.sentencing_categories (deferred to Sprint 7 per standing decision)
Any API endpoint work
Any changes to existing migrations

Files the agent may touch

New migration file(s) in the established migrations directory
The Kysely database types file from task 2.2
tasks/worklog.md (append only)
Migration docs, only if the convention doc needs a one-line addition

Process reminder
Return an implementation plan before writing any code. The plan should state: migration file name(s), one-vs-two migration decision with reasoning, and where the Kysely type updates land.