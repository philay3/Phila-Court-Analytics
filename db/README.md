# @pca/db

Workspace package that owns database connection config and PostgreSQL
migrations, using [Kysely](https://kysely.dev) with its built-in `Migrator`
and the `pg` driver.

- `src/connection.ts` — creates a Kysely instance from `DATABASE_URL`. Fails
  fast with a clear error if it's unset. No credentials, hosts, or ports are
  hardcoded anywhere.
- `src/migrate.ts` — the migration runner CLI (`latest`, `up`, `down`,
  `status`).
- `migrations/` — migration files, one per change.

The first migration (`20260708030321_create_core_schemas.ts`) is the
schema-namespace baseline: it creates the eight core PostgreSQL schemas
(`raw`, `parsed`, `ref`, `fact`, `analytics`, `review`, `audit`, `auth`).
Tables arrive in later migrations.

## Prerequisites

- **Postgres must be running first**: `pnpm db:up` from the repo root (see
  `docs/local-setup.md`).
- **`DATABASE_URL` must be available.** The runner auto-loads the root `.env`
  if one exists (`cp .env.example .env`); an exported shell variable also
  works and takes precedence over `.env`.
- **Node ≥ 22.9** (the runner uses Node's `--env-file-if-exists` flag, added
  in 22.9; any current Node 22 LTS patch qualifies).

## Running migrations

From the repo root:

| Command                  | Effect                                          |
| ------------------------ | ----------------------------------------------- |
| `pnpm db:migrate:latest` | Apply all pending migrations                    |
| `pnpm db:migrate:up`     | Apply the next pending migration (one step)     |
| `pnpm db:migrate:down`   | Revert the most recent migration (one step)     |
| `pnpm db:migrate:status` | List all migrations with executed/pending state |

The same commands exist inside this package without the `db:` prefix
(`pnpm --filter @pca/db migrate:latest`, etc.).

The runner exits nonzero on failure and prints which migration failed.

## Migration naming convention

```
YYYYMMDDHHMMSS_snake_case_description.ts
```

Example: `20260708030321_create_core_schemas.ts`

- The prefix is a UTC timestamp (second precision) taken when the migration
  is created. Lexicographic order = execution order — Kysely runs files
  sorted by name, so never rename or re-timestamp a migration once it has
  been applied anywhere.
- The description is lowercase `snake_case`.
- Each migration exports `up` and `down` functions taking `Kysely<unknown>`.
- Constraints and indexes use Postgres-conventional names: `*_key` for unique
  constraints, `*_idx` for indexes, `*_fkey` for foreign keys.

## Bookkeeping tables

Kysely's Migrator maintains its own state in `public.kysely_migration` and
`public.kysely_migration_lock` (created automatically on first run). Leave
them alone.
