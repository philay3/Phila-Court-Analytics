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
  constraints, `*_idx` for indexes, `*_fkey` for foreign keys, `*_check` for
  CHECK constraints.
- Names spell out the full column list, abbreviated only when that would
  exceed Postgres's 63-character identifier limit (e.g.
  `charge_outcome_aggregates_run_charge_category_key`).
- Every foreign-key column is indexed (Postgres does not auto-index FKs), but
  a `UNIQUE` constraint whose index _leads_ with the FK column already provides
  that index — so no separate `*_idx` is created in that case. Examples from
  21.1: `parsed.dockets.source_document_id` (its `_source_document_id_key`
  unique index covers the FK) and `parsed.charges.docket_id` (leading column of
  the `_docket_id_sequence_key` unique index) get no standalone FK index; only
  FK columns _not_ fronted by a unique index do (e.g. `sentences_charge_id_idx`,
  `warnings_docket_id_idx`, `related_cases_docket_id_idx`).

## Migrations

Migration files, in execution (lexicographic) order:

| File                                                   | What it creates                                                                                                                                                                                                    |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `20260708030321_create_core_schemas.ts`                | The eight core schemas.                                                                                                                                                                                            |
| `20260708220303_create_ref_charge_and_judge_tables.ts` | `ref.*` charge/judge tables + `public.set_updated_at()`.                                                                                                                                                           |
| `20260708223601_create_analytics_aggregate_tables.ts`  | `analytics.*` run + aggregate tables.                                                                                                                                                                              |
| `20260711225105_create_raw_source_documents.ts`        | `raw.source_documents` (mutable; reuses the `set_updated_at` trigger).                                                                                                                                             |
| `20260711225106_create_parsed_tables.ts`               | The `parsed.*` family (`dockets`, `charges`, `sentences`, `warnings`, `related_cases`) — immutable load artifacts; CASCADE within the family, RESTRICT to `raw.source_documents`.                                  |
| `20260711230001_create_fact_tables.ts`                 | `fact.fact_build_runs` (mutable; reuses `set_updated_at`) + `fact.charge_outcomes`, `fact.charge_sentences` (immutable facts). Per-run natural keys; CASCADE from the build run, RESTRICT into `parsed.*`/`ref.*`. |
| `20260711230002_create_review_queue_items.ts`          | `review.queue_items` (mutable; reuses `set_updated_at`) — the deduplicated review worklist; `dedup_key` UNIQUE, RESTRICT to `raw.source_documents`, SET NULL to `parsed.*`.                                        |

## Structural-only review columns

`review.queue_items.raw_value` and `review.queue_items.candidate_context` carry
**structural values only** — an unmapped statute code, a `sentence_type`, or a
set of ambiguous-match candidate ids/slugs. They never carry raw docket text,
docket numbers, or any defendant-identifying data. This is enforced by
convention (the 22.1 review-item helpers) and documented as Postgres column
comments in the creating migration; no defendant-identifying column exists or is
invited anywhere in `fact.*` or `review.*`.

## Bookkeeping tables

Kysely's Migrator maintains its own state in `public.kysely_migration` and
`public.kysely_migration_lock` (created automatically on first run). Leave
them alone.
