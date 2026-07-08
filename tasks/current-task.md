# Task 2.2 — Kysely + Migration Runner

## Goal

Install Kysely and the pg driver, stand up a dedicated `@pca/db` workspace package
that owns database connection config and migrations, and prove the migration
runner works end-to-end (up, down, status) against the local Postgres from 2.1
using one trivial sentinel migration.

## Context

- Local Postgres runs via Docker Compose (task 2.1): image `postgres:17.10`,
  host port 5433, started with the root `db:up` script. It must be running for
  verification.
- `DATABASE_URL` is already documented in `.env.example` from 2.1. The runner
  must read the connection string from `DATABASE_URL` — never hardcode
  credentials.
- The architecture's monorepo layout includes a top-level `db/` directory.
  This task turns it into workspace package `@pca/db`.
- TypeScript is installed at the root only; workspaces use the root binary.
  Strict mode, extending `tsconfig.base.json`.
- The eight domain schemas (raw, parsed, ref, fact, analytics, review, audit,
  auth) are task 2.3, NOT this task.

## Scope

1. **Workspace package `@pca/db`** at `db/`:
   - `package.json` (name `@pca/db`, private), `tsconfig.json` extending the
     base config, included in `pnpm-workspace.yaml` if the glob doesn't
     already cover it.
   - Dependencies: `kysely`, `pg`. Dev dependencies: `tsx`, `@types/pg`.
2. **Connection module** (`db/src/connection.ts` or similar):
   - Creates a Kysely instance from `DATABASE_URL` via the pg Pool.
   - Fails fast with a clear error message if `DATABASE_URL` is unset.
   - No credentials, hosts, or ports hardcoded anywhere.
3. **Migration runner** (`db/src/migrate.ts` or similar) using Kysely's
   `Migrator` with `FileMigrationProvider`:
   - Commands: `migrate:latest` (apply all pending), `migrate:up` (one step),
     `migrate:down` (one step), `migrate:status` (list migrations with
     executed/pending state).
   - Exposed as package scripts in `@pca/db` and mirrored as root scripts
     (`db:migrate:latest`, `db:migrate:up`, `db:migrate:down`,
     `db:migrate:status`).
   - Runner exits nonzero on migration failure and prints which migration
     failed.
4. **Migrations directory**: `db/migrations/`.
   - Naming convention: `YYYYMMDDHHMMSS_snake_case_description.ts`
     (lexicographic order = execution order). Document this.
5. **Sentinel migration**: one migration
   (`..._migration_system_sentinel.ts`) that creates a trivial table
   `public.migration_sentinel` (single `id` column is fine) in `up` and drops
   it in `down`. Its only purpose is proving the runner round-trips. Note in
   a comment that 2.3 may remove or supersede it.
6. **Documentation**: `db/README.md` covering: what `@pca/db` is, the naming
   convention, how to run each migration command, and the requirement that
   Postgres (`pnpm db:up`) is running first.
7. **Lint/typecheck integration**: `@pca/db` participates in root `lint` and
   `typecheck` scripts like the other workspaces.

## Out of Scope

- The eight domain schemas and any real tables (task 2.3).
- Using Kysely from `apps/api` (no API changes at all in this task).
- Database type generation / codegen.
- Seed data of any kind.
- CI integration (task 5.2).
- Changes to Docker Compose or the Postgres setup from 2.1.

## Acceptance Criteria

- [ ] `@pca/db` exists as a workspace package; `pnpm install` succeeds from root.
- [ ] Root `typecheck` and `lint` pass and include the new package.
- [ ] With Postgres running: `pnpm db:migrate:latest` applies the sentinel
      migration; `migration_sentinel` table exists.
- [ ] `pnpm db:migrate:status` correctly shows executed vs pending state
      before and after applying.
- [ ] `pnpm db:migrate:down` drops the sentinel table; re-running
      `db:migrate:latest` reapplies it cleanly (full round-trip).
- [ ] Runner fails with a clear message (nonzero exit) when `DATABASE_URL`
      is unset or Postgres is down — no stack-trace-only failures.
- [ ] Migration naming convention documented in `db/README.md`.
- [ ] No credentials, `.env` files, or secrets committed. `.env.example`
      updated only if something new is genuinely required (expected: nothing).

## Files the Agent May Touch

- `db/**` (new package: source, migrations, README, configs)
- Root `package.json` (new `db:migrate:*` scripts only)
- `pnpm-workspace.yaml` (only if the existing glob doesn't cover `db/`)
- `pnpm-lock.yaml`
- ESLint config only if needed to include `db/` in linting

## Process Reminder

Respond with an implementation plan BEFORE writing any code. The plan will be
reviewed and approved separately. Append a worklog entry to `tasks/worklog.md`
when the task is complete.