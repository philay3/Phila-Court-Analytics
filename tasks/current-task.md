# Task 2.3 — Initial Eight-Schema Migration

## Goal

Replace the sentinel migration with the project's first real migration: a single
migration that creates the eight PostgreSQL schemas that form the namespace
skeleton of the architecture (`raw`, `parsed`, `ref`, `fact`, `analytics`,
`review`, `audit`, `auth`). Reset local migration history so it starts clean
with this migration.

## Context

- The migration system lives in the `@pca/db` workspace (`db/`), built in 2.2:
  Kysely `Migrator` + `FileMigrationProvider`, commands `latest`/`up`/`down`/
  `status`, root scripts `db:migrate:*`, env via `tsx --env-file-if-exists`.
- Migration naming convention (documented in `db/README.md`):
  `YYYYMMDDHHMMSS_snake_case_description.ts`.
- The sentinel migration (`20260707223956_migration_system_sentinel.ts`) exists
  only to prove the runner works end-to-end. It is already commented as
  removable. Nothing production-like exists in any environment; the local
  database is disposable.
- These eight schemas mirror the data model layers in `architecture.md`. This
  task creates the namespaces only — tables come in later tasks (FDN-002.3+).
- Local Postgres from 2.1 (`postgres:17.10`, host port 5433, `pnpm db:up`) must
  be running for verification.

## Scope

1. **Delete the sentinel migration file.** Do not write a new migration to drop
   the sentinel table — local history is reset instead (see verification).
   Update any reference to the sentinel in `db/README.md`.
2. **Create one new migration** named per convention, e.g.
   `YYYYMMDDHHMMSS_create_core_schemas.ts` (generate a real current timestamp):
   - `up`: creates all eight schemas: `raw`, `parsed`, `ref`, `fact`,
     `analytics`, `review`, `audit`, `auth`.
   - `down`: drops all eight schemas using plain `DROP SCHEMA` — **never
     `CASCADE`**. This is deliberate: if tables ever exist, `down` must fail
     loudly rather than destroy data. Drop order is irrelevant while empty.
   - Kysely's schema builder (`db.schema.createSchema(...)`) or raw `sql`
     template are both acceptable; pick one and use it consistently.
   - No `IF NOT EXISTS` / `IF EXISTS` guards — history is clean and migrations
     should fail on unexpected state.
3. **Document** in `db/README.md`: a short note that this migration is the
   schema-namespace baseline and that tables arrive in later migrations.
4. **Worklog**: append an entry to `tasks/worklog.md` after completion.

## Acceptance Criteria

- Sentinel migration file is deleted; no migration in the directory references
  `migration_sentinel`.
- Exactly one migration exists, correctly named, creating the eight schemas in
  `up` and dropping them (no CASCADE) in `down`.
- After `pnpm db:reset` + `db:up` (fresh database), the full cycle verifies:
  1. `migrate:status` shows exactly one pending migration
  2. `migrate:latest` applies it
  3. all eight schemas exist — verify via
     `SELECT schema_name FROM information_schema.schemata` (psql or a query
     through the runner's connection)
  4. `migrate:down` removes all eight schemas
  5. `migrate:latest` reapplies cleanly
- The old `public.migration_sentinel` table does not exist (guaranteed by the
  volume reset; confirm anyway).
- Root `pnpm lint`, `typecheck`, and `format:check` pass.
- No credentials, hosts, or ports hardcoded; connection still comes from
  `DATABASE_URL` only.
- Worklog entry appended.

## Out of Scope

- **Any tables, in any schema** — FDN-002.3 (initial reference and aggregate
  tables) is a separate task. Do not create "just one table while you're in
  here."
- Database roles, grants, or least-privilege setup.
- Postgres extensions.
- Connecting the API (`@pca/api`) to the database.
- Seed data of any kind.
- Changes to Docker Compose or `.env.example`.

## Files You May Touch

- `db/migrations/` (delete sentinel, add new migration)
- `db/README.md`
- `tasks/worklog.md`

## Process Reminder

Return an implementation plan before writing any code. The plan is reviewed
and approved in the planning chat first.