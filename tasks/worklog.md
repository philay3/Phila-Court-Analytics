# Worklog

## Task 1.1 — Initialize Monorepo (FDN-001.1)

- **Date:** 2026-07-07
- **What was built:** pnpm-workspace monorepo skeleton: `pnpm-workspace.yaml` (covers `apps/*`, `packages/*`, `services/*`), root `package.json` (`private: true`, `packageManager: pnpm@11.10.0`, `engines.node >=22`, recursive `dev`/`build`/`lint`/`typecheck`/`test` scripts), `.npmrc` with `engine-strict=true`, privacy-enforcing `.gitignore`, root `README.md` (setup, layout table, privacy rules), placeholder READMEs in all ten workspace folders. Zero dependencies.
- **Files touched:** `pnpm-workspace.yaml`, `package.json`, `.npmrc`, `.gitignore`, `README.md`, `pnpm-lock.yaml` (generated), `apps/web/README.md`, `apps/api/README.md`, `services/pipeline/README.md`, `packages/shared/README.md`, `packages/taxonomy/README.md`, `packages/ui/README.md`, `db/README.md`, `infra/README.md`, `scripts/README.md`, `tests/README.md`
- **Deviations from plan:** none.
- **Notes for next task:** No placeholder `package.json` files exist in workspace folders — `pnpm -r run <script>` exits 0 with no packages, so none were needed. Task 1.2 (TypeScript/ESLint config) will add the first real package manifests. `.gitignore` uses `!.env.example` negation; keep that if patterns are edited. CLAUDE.md references `docs/current-task.md` but the task file actually lives at `tasks/current-task.md`.

## Task 1.2 — TypeScript Base Tooling (FDN-001.2)

- **Date:** 2026-07-07
- **What was built:** Root-level shared tooling: `tsconfig.base.json` (strict + `noUncheckedIndexedAccess`, `noImplicitOverride`, `forceConsistentCasingInFileNames`, `esModuleInterop`, `skipLibCheck`, `isolatedModules`; target/lib ES2023; module/moduleResolution NodeNext), root `tsconfig.json` (extends base, `allowJs`+`noEmit`, includes only `eslint.config.mjs` so `tsc` has an input), ESLint 9 flat config (`@eslint/js` recommended + typescript-eslint recommended non-type-checked + eslint-config-prettier), `.prettierrc` (singleQuote, printWidth 100) + `.prettierignore`, `.editorconfig`, root scripts `lint`/`format`/`format:check`/`typecheck` (all verified exit 0), and `docs/tooling.md` documenting the workspace extension pattern. devDependencies: typescript 6.0.3, eslint 9.39.4, @eslint/js 9.39.4, typescript-eslint 8.63.0, prettier 3.9.4, eslint-config-prettier 10.1.8.
- **Files touched:** `tsconfig.base.json`, `tsconfig.json`, `eslint.config.mjs`, `.prettierrc`, `.prettierignore`, `.editorconfig`, `package.json`, `pnpm-lock.yaml`, `docs/tooling.md`, `pnpm-workspace.yaml` (out-of-scope but trivial: Prettier re-quoted three lines, no semantic change).
- **Deviations from plan:** none from the approved plan. Two mid-flight notes: `pnpm add` initially resolved ESLint 10, pinned back to `eslint@^9`/`@eslint/js@^9` per the locked "ESLint 9" decision; `@eslint/js` was an approved extra devDependency beyond the task's list (pnpm strict node_modules won't resolve it undeclared).
- **Notes for next task:** Recursive root `lint`/`typecheck` scripts were replaced with root-level tool invocations (`eslint .`, `tsc -p tsconfig.json`) — the flat ESLint config lints all workspaces from the root, so new workspaces need no ESLint config, only a `tsconfig.json` extending `../../tsconfig.base.json` and a `typecheck` script (pattern in `docs/tooling.md`). typescript-eslint runs non-type-checked; consider type-aware linting once workspace tsconfigs exist. The task file's suggested "empty include" for the root tsconfig fails with TS18003 — that's why the root `tsconfig.json` includes `eslint.config.mjs`; don't empty it. No `paths`/project references yet. TypeScript resolved to 6.0.3 (task pinned no version) and runs clean.

## Task 1.3 — Fastify API Shell (FDN-005.2)

- **Date:** 2026-07-07
- **What was built:** First real workspace `apps/api` (`@pca/api` — this scoped naming is now the convention for all workspaces). Fastify v5 + TypeBox type provider, strict TS, ESM. `buildApp()` factory ([src/app.ts](../apps/api/src/app.ts)) separate from the listen entrypoint (`src/server.ts`) so tests use `fastify.inject`. `GET /health` with TypeBox response schema; empty `/api/v1/public` and `/api/v1/admin` namespace plugins (`src/routes/public/`, `src/routes/admin/`). Request IDs via `requestIdHeader: 'x-request-id'` + `genReqId` (UUID), echoed on responses by an `onRequest` hook, present in logs as `reqId`. Central `setErrorHandler`/`setNotFoundHandler` return `{statusCode, error, message, requestId}`; validation errors → 400; statusCode ≥ 500 always gets a generic message (real error to logs only; per plan-review change). Env: plain `process.env` with defaults (`PORT` 3000, `HOST` 127.0.0.1, `LOG_LEVEL` info), no dotenv, no `.env.example`. Scripts: `dev` (tsx watch), `build` (tsc via `tsconfig.build.json`, which excludes colocated `*.test.ts`), `start`, `lint`, `typecheck`, `test` (Vitest, 4 tests). Root `typecheck` now also runs workspace typechecks (`tsc -p tsconfig.json && pnpm -r run typecheck`). All root scripts + dev-server curl verification passed.
- **Files touched:** `apps/api/**` (package.json, tsconfig.json, tsconfig.build.json, README.md, src/{app,server,env}.ts, src/app.test.ts, src/routes/{health.ts,public/index.ts,admin/index.ts}), root `package.json` (typecheck script only), `pnpm-lock.yaml`, `pnpm-workspace.yaml` (deviation, see below).
- **Deviations from plan (both accepted):** (1) `pnpm-workspace.yaml`: pnpm 11 refused to run scripts with esbuild's postinstall unapproved (tsx/vitest need it) and scaffolded an `allowBuilds` entry — set `esbuild: true`. Future deps with build scripts will need the same approval. (2) This Fastify version types the error-handler arg as `unknown`; handler is `setErrorHandler<FastifyError>` — typing only.
- **Notes for next task:** Workspace pattern proven end to end: scoped name `@pca/<name>`, tsconfig extending base + `typecheck` script, no per-workspace ESLint/Prettier config, TypeScript stays root-only (pnpm exposes root bins to workspace scripts), dev runner is tsx (NodeNext `.js`-extension imports rule out Node's native type stripping). Vitest needs no config file — defaults find colocated `src/**/*.test.ts`; `tsconfig.build.json` excludes them from emit. `@sinclair/typebox` pinned `^0.34` (type-provider peer range is `<1`). `dist/` already gitignored. Shell only: no DB, auth, CORS, security plugins, or OpenAPI yet.

## Task 2.1 — Local Docker Compose + PostgreSQL (FDN-002.1)

- **Date:** 2026-07-07
- **What was built:** Local Postgres dev environment. `docker-compose.yml` at root: single `postgres` service pinned to `postgres:17.10` (newest 17.x patch at implementation time; Debian variant), host port `${POSTGRES_PORT:-5433}` (non-default to avoid host-Postgres collisions), `pg_isready` healthcheck (5s interval/timeout, 10 retries, 10s start_period), named volume `postgres-data` (materializes as `pca_postgres-data`), env via `${VAR:-default}` interpolation (Compose auto-reads root `.env`; defaults mean it works without one), no restart policy (deliberate — `db:up` is the explicit contract). `.env.example` at root: `POSTGRES_HOST/PORT/DB/USER/PASSWORD` (pca/pca/pca_local_dev_password) plus composed `DATABASE_URL`, placeholders only. Root scripts `db:up`/`db:down`/`db:logs`/`db:reset` (`db:reset` = `down -v`, approved fourth script). `docs/local-setup.md`: prerequisites, first-run, start/stop/reset table, health verification, DATABASE_URL-must-stay-in-sync-with-discrete-vars note, no-restart-policy note, one-sentence object-storage-emulator deferral (FDN-002.1 "documented" option). Verified end to end: container healthy in ~20s, row survived `db:down`+`db:up`, `db:reset` removed the volume, `.env` confirmed gitignored (no `.gitignore` changes needed), lint/typecheck/test all pass.
- **Files touched:** `docker-compose.yml` (new), `.env.example` (new), `package.json` (root, `db:*` scripts only), `docs/local-setup.md` (new), `tasks/worklog.md`.
- **Deviations from plan:** none from the approved plan (plan-stage changes: no restart policy, `db:reset` added, DATABASE_URL sync sentence). Trivial: ran Prettier on `docker-compose.yml` after `format:check` flagged it (quote style only).
- **Notes for next task:** Task 2.2 (Kysely) can read either `DATABASE_URL` or the discrete `POSTGRES_*` vars — both are defined and must be kept in sync manually. Host port is 5433, not 5432; connection strings must say so. `POSTGRES_HOST`/`POSTGRES_PORT` are host-side values (inside the compose network it's `postgres:5432`). Pre-existing issue, out of scope here: `apps/api/src/routes/health.ts` from task 1.3 fails `pnpm format:check` — worth a one-line format fix in a future commit. If a `pg`-style dep with a build script arrives, remember `pnpm-workspace.yaml` `allowBuilds` (see task 1.3 deviation).

## Task 2.2 — Kysely + Migration Runner

- **Date:** 2026-07-07
- **What was built:** Workspace package `@pca/db` at `db/`: `src/connection.ts` (`createDb()` returning `Kysely<unknown>` from `DATABASE_URL` via `pg.Pool`, fail-fast with actionable error if unset, no hardcoded credentials/hosts/ports), `src/migrate.ts` (CLI over Kysely `Migrator` + `FileMigrationProvider` with `latest`/`up`/`down`/`status` commands; migration folder resolved relative to the module so cwd doesn't matter; nonzero exit + names the failing migration on error), sentinel migration `migrations/20260707223956_migration_system_sentinel.ts` (creates/drops `public.migration_sentinel`, `id integer primary key`; 2.3 may supersede it), rewritten `db/README.md` (commands, `YYYYMMDDHHMMSS_snake_case_description.ts` naming convention, Postgres-first prerequisite, Node ≥ 22.9 requirement, bookkeeping-tables note). Env loading via `tsx --env-file-if-exists=../.env` (root `.env` auto-loads; exported shell vars win; works when `.env` absent). Package scripts `migrate:*`, `lint`, `typecheck`; root scripts `db:migrate:latest/up/down/status` via `pnpm --filter @pca/db`. Deps: kysely 0.29.3, pg 8.22.0; dev: tsx, @types/pg, @types/node. Verified live end-to-end: status→latest→status→psql table check→down→latest round-trip, one-step `up`, and all three failure modes (unset `DATABASE_URL`, unknown command, Postgres down) exit 1 with one-line messages; confirmed `--env-file-if-exists` actually reaches Node through tsx (`DATABASE_URL` unset in shell, still loaded from `.env`). Root install/lint/typecheck/format all pass.
- **Files touched:** `db/package.json`, `db/tsconfig.json`, `db/src/connection.ts`, `db/src/migrate.ts`, `db/migrations/20260707223956_migration_system_sentinel.ts`, `db/README.md` (rewritten), `pnpm-workspace.yaml` (added `db` entry — globs didn't cover it), root `package.json` (`db:migrate:*` scripts only), `pnpm-lock.yaml`, `tasks/worklog.md`.
- **Deviations from plan:** (1) `@types/node` added as devDependency beyond the task's list — required for `process`/`node:fs` types under pnpm strict node_modules, same as `@pca/api`. (2) Post-plan fix found in failure-mode testing: pg reports "Postgres unreachable" as an `AggregateError` with an empty message, which printed as a blank error; added `describeError()` unwrapper (joins sub-error messages) plus an "Is Postgres running? Start it with: pnpm db:up" hint on ECONNREFUSED. Error-output-only change.
- **Notes for next task:** Import migration APIs from `kysely/migration`, NOT `kysely` — the main-package re-exports of `Migrator`/`FileMigrationProvider`/`MigrationResultSet` are deprecated in kysely 0.29. Migrator keeps state in `public.kysely_migration` + `public.kysely_migration_lock` (auto-created; leave alone). `createDb()` is typed `Kysely<unknown>` deliberately — 2.3 should introduce the real `DB` interface type when domain tables exist, and may remove/supersede the sentinel migration (if removing after it's been applied, `db:migrate:down` first or `db:reset`). Never rename/re-timestamp an applied migration (lexicographic order = execution order). `pg` has no build script, so no `allowBuilds` change was needed. `--env-file-if-exists` needs Node ≥ 22.9 (documented in db/README). Pre-existing `agent-docs/` vs `docs/` reorganization was in flight during this task — not part of 2.2's commit.

## Task 2.3 — Initial Eight-Schema Migration

- **Date:** 2026-07-08
- **What was built:** First real migration, replacing the sentinel. Deleted `migrations/20260707223956_migration_system_sentinel.ts` (no new drop migration — local history reset instead via `db:reset`). Added `migrations/20260708030321_create_core_schemas.ts`: `up` creates the eight namespace schemas (`raw`, `parsed`, `ref`, `fact`, `analytics`, `review`, `audit`, `auth`) by iterating a `SCHEMAS` const array with Kysely's schema builder (`createSchema`); `down` uses plain `dropSchema` — deliberately no CASCADE, so revert fails loudly once any schema contains objects; no `IF [NOT] EXISTS` guards. `db/README.md` updated: naming-convention example now cites the new file, plus a note that this migration is the schema-namespace baseline (tables arrive in later migrations). Verified on a fresh database (`db:reset` + `db:up`): status showed exactly one pending → `latest` applied → all eight schemas present in `information_schema.schemata` → `to_regclass('public.migration_sentinel')` NULL → `down` removed all eight (count 0) → `latest` reapplied cleanly. Root lint/typecheck/format:check pass.
- **Files touched:** `db/migrations/20260707223956_migration_system_sentinel.ts` (deleted), `db/migrations/20260708030321_create_core_schemas.ts` (new), `db/README.md`, `agent-docs/local-setup.md` + `agent-docs/tooling.md` (out-of-scope but trivially necessary, see deviations), `tasks/worklog.md`.
- **Deviations from plan:** (1) Migration iterates a `SCHEMAS` const array instead of eight literal statements — identical order/behavior, less repetition. (2) `format:check` was already failing on clean HEAD (`agent-docs/local-setup.md`, `agent-docs/tooling.md` — the leftover of the docs reorganization noted in 2.2); the "format:check passes" criterion couldn't be met without fixing them, so Prettier was run on those two files (14 lines, whitespace/wrapping only, no content change), called out and accepted.
- **Notes for next task:** FDN-002.3 (first reference/aggregate tables) should introduce the real `DB` interface type for `createDb()` (still `Kysely<unknown>`, carried over from 2.2). The no-CASCADE `down` convention is now precedent — keep destructive reverts loud. Local dev database was volume-reset during this task; anyone with an older local volume needs `pnpm db:reset` + `db:up` + `db:migrate:latest` since the sentinel migration no longer exists in the directory (Kysely errors on executed-but-missing migration files). Schema list order in the migration matches the task/architecture doc ordering, not alphabetical.

## Task 3.1 — Create Taxonomy Package

- **Date:** 2026-07-07
- **What was built:** New workspace package `packages/taxonomy` (`@pca/taxonomy`), the single source of truth for outcome categories, sentencing categories, and thin-data config. Seeds (JSON source of truth): `seeds/outcome-categories.json` and `seeds/sentencing-categories.json` (exactly the 9+9 specced codes; every record has `code`/`displayName`/`definition`/`sortOrder`/`public`; `unknown` is `public: false` in both), `seeds/thin-data.json` (provisional `minSampleSize: 30` for outcome + sentencing distributions, `provisional: true`, comment noting thresholds finalize after parser/data review), `seeds/version.json` (`1.0.0`). Validation: pure functions in `src/validation.ts` (field presence/types, snake_case codes, code + sortOrder uniqueness per file, non-empty displayName/definition, exact expected code sets, case-insensitive banned-term scan of definitions, semver via the official semver.org regex — no `semver` dep) with thin CLI `src/validate.ts` (exit 1 on any error). Generation: `src/build.ts` (pure, deterministic — sorts by sortOrder, fixed key order, no timestamps; byte-identical across runs, checksum-verified) + `src/generate.ts` CLI that validates first, then emits `generated/taxonomy.json` and `generated/index.ts` (exports `TaxonomyCategory` interface, `TAXONOMY_VERSION`, `OUTCOME_CATEGORIES`/`SENTENCING_CATEGORIES` as const with `satisfies`, `THIN_DATA_CONFIG`, and `OutcomeCategoryCode`/`SentencingCategoryCode` union types). `generated/` is gitignored; package `main`/`exports` point at `./generated/index.ts`; package `typecheck` runs generate first so root `pnpm typecheck` passes on a fresh clone. 14 Vitest tests (pass-on-real-seeds; failures for duplicate code, missing field, banned term, unexpected/missing code, non-snake_case, duplicate sortOrder, bad semver; artifact completeness, ordering, determinism). Root wiring: `taxonomy:validate`/`taxonomy:generate` scripts (mirroring the `db:*` pattern; tests/lint need no new wiring — `pnpm test` recurses and root `eslint .` covers the package), Taxonomy section in root README. Dev-only deps (`vitest`, `tsx`, `@types/node` — versions already in the workspace); TypeScript stays root-only. Verified: validate, generate ×2 (identical checksums), all tests, repo-wide lint/typecheck/format:check green.
- **Files touched:** `packages/taxonomy/**` (package.json, tsconfig.json, README.md rewritten from stub, seeds/{outcome-categories,sentencing-categories,thin-data,version}.json, src/{validation,validate,build,generate}.ts, src/{validation,generate}.test.ts), root `package.json` (taxonomy scripts only), root `README.md` (Taxonomy section), `.gitignore` (`packages/taxonomy/generated/`), `eslint.config.mjs` (approved out-of-scope one-liner: `**/generated/` added to ignores), `pnpm-lock.yaml`, `tasks/worklog.md`.
- **Deviations from plan:** none from the approved plan (the `eslint.config.mjs` touch was flagged and approved at plan review). Trivial: Prettier reflowed one import in `src/generate.test.ts` after `format:check` flagged it.
- **Notes for next task:** For 3.2 (`@pca/shared`): the typecheck-runs-generate approach works for this package in isolation, but once `@pca/shared` imports `@pca/taxonomy`, fresh-clone ordering becomes a real question — the 3.2 spec will address it (likely a root-level generate step or a `prepare` script). Consumers import the generated TS entry (`@pca/taxonomy` resolves to `generated/index.ts`), so generate must have run before anything downstream typechecks or builds. Category `code` values are stable identifiers — never rename; the validator hardcodes the expected code sets, so adding/removing a category means updating both the seed file and `EXPECTED_*_CODES` in `src/validation.ts` deliberately. Thin-data thresholds are provisional (criterion of a later task); DB seeding of `ref.*` tables from these seeds is a later task; CI wiring of taxonomy validation is task 5.2.

## Task 3.2 — Create Shared API Types Package

- **Date:** 2026-07-07
- **What was built:** New workspace package `packages/shared` (`@pca/shared`), the single source of truth for public API contracts: TypeBox schemas with derived static types (naming convention: `xxxSchema` value + PascalCase `Static<typeof xxxSchema>` type, e.g. `chargeOnlyResultSchema`/`ChargeOnlyResult`), exported from `src/index.ts`. `src/public/categories.ts` derives `outcomeCategoryCodeSchema`/`sentencingCategoryCodeSchema` as `Type.Union` of `Type.Literal`s from the `@pca/taxonomy` generated arrays, **filtered to `public: true`** (approved decision: non-public codes like `unknown` must fail public schema validation — schema-as-privacy-wall; a type-guard filter keeps the static types public-only too). `src/public/common.ts`: `sampleSizeSchema` (integer ≥ 0), `dateRangeSchema` (`format: 'date'`), `taxonomyVersionSchema` (semver-shaped pattern), `thinDataStatusSchema`, and outcome/sentencing `DistributionEntry`/`Distribution` schemas from a shared internal factory — count + percentage both required, every distribution carries its own sampleSize/dateRange/thinData. `src/public/search.ts`: charge/judge suggestion schemas (`id`/`displayName`/`slug` only) in an approved `{ results: [...] }` object envelope (extensible without breaking change; no count field). `src/public/results.ts`: `chargeOnlyResultSchema` and `judgeSpecificResultSchema` (optional sentencing distributions, `taxonomyVersion`, `lastRefreshed` `format: 'date-time'`). Every object schema sets `additionalProperties: false`. 36 Vitest tests: round-trips (fixtures typed against Static types and built from taxonomy artifacts — no hand-copied codes even in tests), extra-property rejection per top-level schema plus nested objects, drift test comparing schema literals to the filtered artifact list, explicit rejection of every non-public code (derived, not hardcoded) standalone and inside entries, percentage/count/sampleSize bounds. Root wiring: added `generate` script (`pnpm -r run generate`); `typecheck` and `test` now run generate first; fresh-clone ordering documented in root README ("Generated artifacts" section, pre-approved addition) and cross-referenced from the package README. Taxonomy's package-local typecheck-runs-generate left intact (generation runs twice in root typecheck; idempotent, deliberate). All four root checks green: lint, typecheck, test (54 tests workspace-wide), format:check.
- **Files touched:** `packages/shared/**` (package.json, tsconfig.json, README.md rewritten from stub, src/index.ts, src/public/{categories,common,search,results}.ts, src/public/{categories,common,search,results}.test.ts, src/test-support/{formats,fixtures}.ts), root `package.json` (generate/typecheck/test scripts only), root `README.md` (Generated artifacts section only), `pnpm-lock.yaml`, `tasks/worklog.md`.
- **Deviations from plan:** none from the approved plan. The pre-authorized narrow fix to `packages/taxonomy/package.json` (export/resolution fields, in case root tsc rejected the cross-package `.ts` import) was **not needed** — NodeNext resolved it cleanly; taxonomy is untouched. Trivial: Prettier reformat pass limited to `packages/shared/`.
- **Notes for next task:** TypeBox's `Value` module only enforces `format:` constraints for formats the host registers via `FormatRegistry` — tests register minimal `date`/`date-time` checkers in `src/test-support/formats.ts`; when `@pca/api` adopts these schemas in Sprint 2, Fastify/Ajv handles formats (verify ajv-formats is wired) and `@pca/web` needs registration only if it does client-side `Value.Check`. Package-scoped `pnpm --filter @pca/shared typecheck|test` requires `pnpm generate` at the root first (root scripts handle it automatically). The public-only filter means a taxonomy `public` flag flip propagates by regeneration alone. The error response schema still lives in `@pca/api` (task 1.3) and is slated to lift into `@pca/shared` later; definitions/methodology/data-coverage schemas and the judge-specific-unavailable response are Sprint 2 (PUB-003.3).

## Task 4.1 — Next.js Web App Shell

- **Date:** 2026-07-08
- **What was built:** Public web app shell at `apps/web` (`@pca/web`), hand-scaffolded (no `create-next-app`). Pins (exact, no ranges): `next` 16.2.10, `react`/`react-dom` 19.2.7, `@types/react` 19.2.17, `@types/react-dom` 19.2.3; dev-only `vitest` ^3 + `@types/node` ^22 (approved at plan review; version lines match `@pca/api`). Turbopack default, no webpack config, TypeScript from the root install. Six static routes: `/` (product name, plain-English description, responsible-use paragraph, links to Methodology and Data Coverage, "Search is coming soon"), `/methodology`, `/definitions`, `/about` (heading + placeholder each), `/data-coverage` (coverage window: disposition/sentencing event dates on or after January 1, 2025), `/admin` ("Admin — not yet available.", not in nav). Root layout: header (site name + nav to the five public routes only), main, footer responsible-use one-liner; site-wide `robots: noindex, nofollow` via layout metadata with a code comment (deliberate, revisit at launch readiness); plain global CSS (semantic HTML, visible focus outlines, no Tailwind/UI library). Copy guard: `test/copy-terms.ts` exports `FORBIDDEN_TERMS`, `GUARDED_STEM` (`predict`), `DISCLAIMER_ALLOWLIST` for PUB-008 to import/extend; `test/copy-guard.test.ts` recursively scans `.ts`/`.tsx`/`.css`/`.md` under `apps/web/app`, case-insensitive, whitespace-normalized (see deviations), reports file + term, plus a sanity test that the scan finds files. Scripts `dev`/`build`/`start`/`typecheck`/`test` named per workspace convention; `typecheck` runs `next typegen && tsc --noEmit` — **confirmed `next typegen` does emit `next-env.d.ts`**, so the file stays gitignored (the commit-it fallback was not needed). ESLint: `eslint-config-next` 16.2.10 (exact, tracks the next pin) added at root; its `core-web-vitals` + `typescript` flat presets scoped to `apps/web/**` with `settings.next.rootDir` pointing at the workspace — integrated cleanly with ESLint 9 flat + typescript-eslint (no friction fallback needed). Verified: all six routes 200 on `next dev` (port 3000, clean log), `noindex, nofollow` meta present in served HTML, `pnpm --filter @pca/web build` green (8/8 static pages), and root `pnpm lint` / `typecheck` / `test` / `format:check` all pass.
- **Copy-guard failure demo (criterion 6):** temporarily inserted "the best judge of that is you" into `app/about/page.tsx`; `pnpm test` failed with `AssertionError: about/page.tsx: "best judge": expected [ 'about/page.tsx: "best judge"' ] to deeply equal []`. Term removed before commit; guard re-verified green afterwards (and `grep -c 'best judge' app/**` = 0).
- **Files touched:** `apps/web/**` (package.json, tsconfig.json, next.config.ts, app/{layout.tsx,globals.css,page.tsx}, app/{methodology,definitions,data-coverage,about,admin}/page.tsx, test/{copy-terms.ts,copy-guard.test.ts}), root `package.json` (eslint-config-next dev dep only), `eslint.config.mjs` (scoped Next presets, pre-approved optional addition), `.gitignore` (`next-env.d.ts`, `*.tsbuildinfo`), `pnpm-workspace.yaml` (allowBuilds decisions, see deviations), `pnpm-lock.yaml`, `tasks/worklog.md`.
- **Deviations from plan:** (1) `pnpm-workspace.yaml` `allowBuilds`: filled in the existing `sharp` placeholder as `false` (Next's optional native image-optimizer; the shell has no images — revisit when images arrive in Sprint 3) and added `unrs-resolver: false` (arrived with eslint-config-next's import resolver; ships prebuilt binaries via optionalDependencies, postinstall is only a fallback check). Trivially necessary — installs fail while a placeholder is unresolved. (2) Copy guard normalizes whitespace before matching: Prettier wrapped "not a prediction" across two source lines in `app/page.tsx`, which broke literal phrase matching — the guard collapses `\s+` to a single space so multi-word terms and disclaimer phrases are line-wrap-proof. Found because the guard genuinely failed on it after the repo-wide format pass. (3) Nothing else; root `package.json` scripts needed no changes (all recursive already).
- **Notes for next task:** Root `pnpm dev` (`pnpm -r run dev`) now hits two watch scripts (api + web) and pnpm runs them **sequentially** — api's watcher blocks web. Use `pnpm --filter @pca/web dev` (or `--parallel`) until a future task addresses it; acceptance flows all use `--filter`. PUB-008 should import `FORBIDDEN_TERMS`/`GUARDED_STEM`/`DISCLAIMER_ALLOWLIST` from `apps/web/test/copy-terms.ts` — extend the lists there, and note the guard's scan scope is `apps/web/app` only (the term lists themselves live outside it deliberately). The nav is driven by the `NAV_LINKS` const in `app/layout.tsx`; `/admin` stays out of it. `next-env.d.ts` and `.next/` are gitignored; a fresh clone gets them via `pnpm typecheck`/`dev`/`build` (`next typegen` regenerates). Visual design system, search UI, and data fetching are Sprint 3; CI wiring is task 5.2. `tasks/current-task.md` had the human's 3.2→4.1 task swap uncommitted in the working tree — left unstaged for the human to commit.

## Task 4.2 — Python Pipeline Shell

- **Date:** 2026-07-08
- **What was built:** Python pipeline project shell at `services/pipeline` (src layout, managed by **uv**). Distribution name `pca-pipeline` (matching the `@pca/*` convention; import package and console script stay `pipeline`), `requires-python = ">=3.12"`, build backend `uv_build` with `module-name = "pipeline"`, **zero runtime dependencies**; dev group: pytest ≥8, ruff ≥0.12 (both configured in `pyproject.toml` — ruff `target-version py312`, lint select `E,F,W,I,UP,B`; pytest `testpaths = ["tests"]`). CLI (`src/pipeline/cli.py`, stdlib argparse subparsers, registered via `[project.scripts]`): four placeholder subcommands (`import-manual`, `extract-text`, `evaluate-extractors`, `run-fixtures`), each logs a structured `"command not implemented"` line with a `command` extra field and exits 0; no subcommand prints usage to stderr and exits 2; top-level and per-subcommand `--help` work. Structured logging (`src/pipeline/logging_utils.py` — named to avoid shadowing stdlib `logging`): `JSONFormatter` emitting one JSON object per line (UTC ISO timestamp, level, logger, message, plus any `extra=` fields, detected by diffing against stdlib LogRecord attributes) and `configure_logging()` attaching a **stderr** handler to the root logger (replaces existing handlers so repeated calls don't duplicate); privacy standing rule in the module docstring. 13 pytest tests: each subcommand exits 0 with parseable JSON (message/command/level asserted), no-subcommand exits non-zero, top-level help lists all four commands, per-subcommand help, formatter fields with %-args, single-line output, `extra=` fields pass through end-to-end via capsys. `.python-version` pinning `3.12` (venv runs CPython 3.12.13). `uv.lock` committed. README documents setup/CLI/tests/ruff and the logging privacy rule. Root `.gitignore` gained `.venv/`, `*.pyc`, `.ruff_cache/` (`__pycache__/` and `.pytest_cache/` were already covered). Verified: `uv sync` → `uv run pipeline --help` works; `uv run pytest` 13 passed; `uv run ruff check .` and `uv run ruff format --check .` clean.
- **Files touched:** `services/pipeline/pyproject.toml`, `services/pipeline/.python-version`, `services/pipeline/uv.lock`, `services/pipeline/src/pipeline/{__init__.py,cli.py,logging_utils.py}`, `services/pipeline/tests/{test_cli.py,test_logging_utils.py}`, `services/pipeline/README.md` (rewritten from stub), root `.gitignore` (Python additions only), `tasks/worklog.md`.
- **Deviations from plan:** (1) `.python-version` added after plan approval (human-requested): `uv sync` had selected CPython 3.14.6, but the project's locked runtime is 3.12 — pinned `3.12`, venv rebuilt on CPython 3.12.13, `uv.lock` unchanged. (2) Environmental, not code: the repo moved from `~/Desktop` to `~/code/PCA` mid-task (resolution of the venv/iCloud-sync problem — Desktop is iCloud-synced); the venv was deleted and rebuilt at the new location.
- **Notes for next task:** Task 5.1 adds the PDF extractor candidates (PyMuPDF/pdfplumber/pypdf) — put them in a dedicated uv group or extras per that task's spec, and remember fixture PDFs live **outside** the repo behind a configurable gitignored path. Logs go to **stderr** by design; stdout is reserved for future machine-readable command output — keep that contract when commands become real. `configure_logging()` replaces root handlers on every call (test-friendliness); pass structured fields via `logging`'s `extra=` dict and they land as top-level JSON keys — never log raw docket text, defendant data, or file contents (rule documented in `logging_utils.py` and the README). uv commands must run from `services/pipeline` (or use `uv run --project`). The venv is per-machine; fresh clones need `uv sync`. CI wiring for pytest + ruff is task 5.2. `tasks/current-task.md` again has the human's task swap (4.1→4.2) uncommitted — left for the human, same as last task.

## Task 5.1 — PDF Extraction Evaluation Harness

- **Date:** 2026-07-08
- **What was built:** The `evaluate-extractors` subcommand, implemented as a new `pipeline.evaluation` package. `src/pipeline/evaluation/extractors.py`: one adapter per candidate library (pymupdf 1.28.0, pdfplumber 0.11.10, pypdf 6.14.2 — added as **runtime** dependencies), each returning one string per page (`None` → `""`), exceptions propagate; `EXTRACTORS` registry maps name → adapter. `src/pipeline/evaluation/harness.py`: `run_evaluation()` — validates the fixtures dir (must exist and contain ≥1 `*.pdf`, case-insensitive, **non-recursive**), refuses any output dir that resolves inside a git working tree (walks resolved ancestors for a `.git` **entry** — `.exists()`, not `.is_dir()`, so plain-file `.git` in linked worktrees/submodules is caught), then runs each selected extractor over every file. Per-file metrics: page count, total/per-page char counts, wall-clock duration (`perf_counter`), empty pages (count + zero-based indices; empty = None/empty/whitespace-only), `needs_ocr_or_review` (all pages empty or open failed), case-insensitive occurrence counts for the nine UJS section keywords, and sanitized error records (exception type + message with path/filename/stem redacted, truncated to 200 chars). A failing file is recorded and skipped, never fatal. Artifacts: `report-<extractor>.json` (per-file metrics keyed by 16-char SHA-256 prefix of file bytes), `file-index.json` (hash → filename, output dir only), `summary.json` (per-extractor rollups: total files, failures, total/mean duration, `needs_ocr_or_review` count, per-keyword hit rates = fraction of successful files with ≥1 hit; covers only extractors that ran), and `--dump-text` (opt-in) text dumps at `text/<extractor>/<hash>.txt` with `--- page N ---` separators. CLI (`cli.py`): `--fixtures-dir`/`--output-dir` required, `--extractors` comma-list validated against the registry (deduped, order-preserving), `--dump-text` flag; `PLACEHOLDER_COMMANDS` now distinguishes the three remaining stubs. Logging: startup line with fixtures dir + counts (the only path logged), per-file lines keyed by hash only. 18 new tests (31 total) using synthetic PyMuPDF-generated PDFs with docket-number-style filenames: metrics per extractor, blank-PDF flagging, junk-file continuation, artifact structure/hash keys, log-leak assertions (body text, filenames, raw file bytes), missing/empty fixtures dir, guard refusal (`.git` as dir AND as file), subsets, unknown extractor, dump-text on/off. README rewritten with usage, artifact docs, and privacy rules. Verified: `uv run pytest` 31 passed, `ruff check` + `ruff format --check` clean, end-to-end smoke run in a scratch dir produced all artifacts correctly.
- **Files touched:** `services/pipeline/src/pipeline/evaluation/{__init__.py,extractors.py,harness.py}` (new), `services/pipeline/tests/test_evaluate_extractors.py` (new), `services/pipeline/src/pipeline/cli.py`, `services/pipeline/tests/test_cli.py` (placeholder-test parametrization excludes `evaluate-extractors`), `services/pipeline/pyproject.toml`, `services/pipeline/uv.lock`, `services/pipeline/README.md`, `tasks/worklog.md`. Root `.gitignore` unchanged (existing patterns sufficed).
- **Deviations from plan:** one addition, found during the end-to-end smoke run: pypdf's own logger propagates to the root handler and **echoes raw file bytes** (`invalid pdf header: b'…'` — first 5 bytes of the file), violating the no-content logging rule. The harness now disables propagation for the `pypdf`/`pdfminer`/`pdfplumber`/`pymupdf`/`fitz` loggers (`_silence_library_loggers()`), and the leak test asserts on the exact echoed byte prefix; verified the test fails without the fix. Library diagnostics still surface via the sanitized error records.
- **Notes for next task:** Task 5.3's human evaluation **requires** `--dump-text` (metrics alone can't judge charge-table/disposition readability) — README example includes it. The fixtures scan is non-recursive by design; stage the whole corpus flat (e.g. `~/court-data/fixtures`). Third-party PDF library loggers are propagation-disabled inside `run_evaluation()` only — if `extract-text` (production path) later uses these libraries, apply the same suppression there; pypdf in particular logs raw header bytes at WARNING. The git-worktree guard rejects `.git` files as well as dirs — don't "simplify" it to `is_dir()`. Section keywords live in `harness.SECTION_KEYWORDS`; hit rates in `summary.json` are computed over successfully-processed files only. Duplicate fixture content collides on hash key (last file wins in `file-index.json`) — dedupe the corpus before staging. CI wiring (task 5.2) can run this package's pytest/ruff as-is; tests generate their own PDFs and need no fixtures.

## Task 5.2 — GitHub Actions CI

- **Date:** 2026-07-08
- **What was built:** Baseline CI at `.github/workflows/ci.yml`: triggers on `pull_request` (all branches) and `push` to `main`; concurrency group `${{ github.workflow }}-${{ github.ref }}` with `cancel-in-progress: true`; two parallel jobs, both `timeout-minutes: 15`. **Node job** (`ubuntu-latest`): `postgres:17.10` service container (inline dummy creds `ci`/`ci`/`pca_ci`, `pg_isready` health check, port 5432 — CI uses the container default; local 5433 is a host-conflict convention only), then checkout → `pnpm/action-setup@v4` with **no version input** (reads root `packageManager`, single source of truth) → `actions/setup-node@v4` (Node 22, pnpm store cache) → `pnpm install --frozen-lockfile` → `pnpm generate` (taxonomy `generated/` artifacts are gitignored; CI is a fresh clone) → `pnpm lint` → `pnpm format:check` → `pnpm typecheck` → `pnpm taxonomy:validate` → `pnpm test` → `pnpm db:migrate:latest` with `DATABASE_URL=postgresql://ci:ci@localhost:5432/pca_ci` (proves migrations apply on a fresh 17.x database). **Python job** (`services/pipeline` working dir): checkout → `astral-sh/setup-uv@v6` (cache keyed on `services/pipeline/uv.lock`; Python version resolved by uv from `.python-version` — no duplicated version string) → `uv sync --locked` → `uv run ruff check .` → `uv run ruff format --check .` → `uv run pytest`. Action pins: `checkout@v4`, `pnpm/action-setup@v4`, `setup-node@v4`, `setup-uv@v6`. No `secrets.*` references; no fixtures touched (pipeline tests generate synthetic PDFs). Also fixed the deferred 4.1 issue: root `dev` script is now `pnpm -r --parallel run dev`. Docs: CI badge atop root README; `agent-docs/ci.md` (what runs and in what order, why generate precedes typecheck, Postgres 17.x/5432-vs-5433 convention, and a note that `cancel-in-progress` on `main` becomes a footgun once a deploy workflow exists — revisit then). Verified locally: workflow YAML parsed and structure-checked; full Node sequence green end to end; migrations applied to a fresh throwaway `postgres:17.10` container with CI's exact credentials; `pnpm dev` started API + web concurrently and one SIGINT to the process group stopped both cleanly. True green run happens on first push (by design).
- **Files touched:** `.github/workflows/ci.yml` (new), root `package.json` (`dev` script only), root `README.md` (badge only), `agent-docs/ci.md` (new), `services/pipeline/README.md` (out-of-scope but trivially necessary, see deviations), `tasks/worklog.md`.
- **Deviations from plan:** (1) Docs location: the task spec suggested `docs/ci.md`, but CLAUDE.md's documentation rules forbid agent-created files in `docs/` — resolved (human-confirmed) to `agent-docs/ci.md`. **Future specs should stop suggesting `docs/` for agent-generated documentation.** (2) `services/pipeline/README.md` had a pre-existing Prettier violation (committed unformatted in an earlier task) that failed `pnpm format:check` — CI's first run would have been red; ran `prettier --write` on it (one-line whitespace diff, no content change), called out and accepted. (3) Post-plan additions from human review notes: `timeout-minutes: 15` on both jobs, and the deploy-workflow footgun note in `agent-docs/ci.md`.
- **Notes for next task:** The README badge 404s until the workflow's first run on `main`. `pnpm generate` runs up to three times in the Node job (explicit step, then inside `typecheck` and `test`) — idempotent and fast, kept for failure attribution; if it ever gets slow, dedupe then. When a deploy workflow arrives, revisit `cancel-in-progress: true` for `main` (see `agent-docs/ci.md`). Branch protection rules are a human task in GitHub settings (out of scope here). Observation from `pnpm dev` verification, pre-existing and untouched: both dev servers report port 3000 (API binds `127.0.0.1:3000`, Next serves `localhost:3000`) — they coexisted on macOS but the overlap may collide on Linux; worth a small future task. Task 5.3 (extraction harness vs real fixtures) is human-run and must never enter CI.

## Task 5.2b — API Default Port → 3001 (micro-task)

- **Date:** 2026-07-08
- **What was built:** Resolved the dev-time port collision flagged in 5.2: the API's default listen port moved from 3000 to 3001, establishing the conventional web-3000 / api-3001 split. The default lives in exactly one place — `apps/api/src/env.ts` (`process.env.PORT ?? 3001`); `apps/api/README.md` updated in both spots (dev-server URL, env-var table). `.env.example` deliberately untouched: it contains only Postgres variables — the API uses plain `process.env` with defaults and no dotenv (task 1.3 decision), so there was no API port variable or URL to update, and adding one would be misleading (the API's `dev` script loads no `.env`). Verified live: root `pnpm dev` started both servers concurrently, web 200 on 3000, `curl http://localhost:3001/health` → `{"status":"ok",...}`, API log shows `listening at http://127.0.0.1:3001`, one SIGINT to the process group stopped both cleanly. Lint/format:check/typecheck green; all 56 tests pass (API tests use `fastify.inject`, nothing hardcodes 3000). Final repo-wide grep: no API-on-3000 references remain — surviving "3000" hits are digit-substring false positives in lockfiles (`caniuse-lite@1.0.30001802`, a pypi hash) and historical worklog narrative (1.3, 4.1, 5.2), left as append-only history per the approved plan; `agent-docs/` came back clean, so the report-don't-edit condition was never triggered.
- **Files touched:** `apps/api/src/env.ts`, `apps/api/README.md`, `tasks/worklog.md`.
- **Deviations from plan:** none.
- **Notes for next task:** web-3000 / api-3001 is now the convention — Sprint 2/3 API base-URL wiring for the web app should assume `http://localhost:3001` in dev (reverse proxy/CORS still unaddressed, deliberately out of scope here). `PORT` env var still overrides the default. CI is unaffected (nothing in CI binds these ports; API tests inject). The 5.2 worklog note about the port-3000 overlap is superseded by this task.

## Task 6.1 — ref.* Table Migrations

- **Date:** 2026-07-08
- **What was built:** Single migration `db/migrations/20260708220303_create_ref_charge_and_judge_tables.ts` (one file, per approved plan — the four tables are one task-level change, precedent from 2.3's schemas migration) creating `ref.normalized_charges`, `ref.charge_aliases`, `ref.normalized_judges`, `ref.judge_aliases` exactly per the task spec: uuid PKs via `gen_random_uuid()`, unique `slug` on both parents, `ON DELETE CASCADE` FKs from aliases, per-parent `(parent_id, alias_text)` unique constraints, non-unique b-tree indexes on both `alias_text` columns, `is_active` default true, `created_at`/`updated_at` timestamptz default `now()`. Plus (approved in-scope change) a shared `public.set_updated_at()` plpgsql trigger function with `BEFORE UPDATE` triggers named `set_updated_at` on both parent tables; **standing decision: every table with an `updated_at` column uses this trigger — never application-managed.** `down` drops triggers → alias tables → parent tables → function (FK-safe order, plain drops, no CASCADE per the loud-revert precedent). New `db/src/types.ts`: per-table interfaces + `Database` interface keyed by schema-qualified names (`'ref.normalized_charges'`, …); `Generated<>` for defaulted columns; `updated_at` typed `ColumnType<Date, never, never>` so application code *cannot* write it (type-level enforcement of the trigger decision). `createDb()` in `db/src/connection.ts` now returns `Kysely<Database>` (fulfilling the 2.2/2.3 worklog hand-off); `migrate.ts` needed no change. `db/README.md` naming convention gained the approved line: `*_key` unique / `*_idx` index / `*_fkey` FK — all names in the migration follow it. Verified live: status→latest→psql `\d` inspection (all constraints/indexes/triggers present, correctly named); constraint checks run inside a single rolled-back transaction with savepoints (per human instruction — no insert-then-delete): duplicate slug rejected, orphan FK rejected, duplicate `(parent, alias_text)` rejected on both alias tables, cascade delete removed child alias, trigger overwrote both a stored stale `updated_at` and an explicit `updated_at` in the UPDATE statement itself with `now()` while leaving `created_at` untouched, and post-rollback counts all 0; then down (tables + function verified gone via `to_regclass`/`pg_proc`) → latest reapplied cleanly. Root lint/typecheck green; the four touched files pass `prettier --check` individually.
- **Files touched:** `db/migrations/20260708220303_create_ref_charge_and_judge_tables.ts` (new), `db/src/types.ts` (new), `db/src/connection.ts`, `db/README.md` (naming-convention line), `tasks/worklog.md`.
- **Deviations from plan:** (1) Trigger function placed in `public`, not the suggested `ref` — the approval allowed "another location" with justification: the standing decision covers future tables in *any* schema (analytics, fact, review…), so a schema-neutral home avoids coupling every other schema to `ref`; `public` already hosts shared infrastructure (Kysely bookkeeping tables). Justified in the migration's header comment. (2) `updated_at` typed as non-writable (`ColumnType<Date, never, never>`) rather than `Generated<>` — a strengthening beyond the approved plan's wording, encoding "never application-managed" into the type system. (3) Root `pnpm format:check` fails on pre-existing, untracked `agent-docs/decisions/0001-pdf-extractor.md` (human's uncommitted file, present before this task) — left untouched, unlike prior tasks' fix-ups, because it's not committed; flagging for the human.
- **Notes for next task:** Task 6.2 (analytics.\*) and any future table with `updated_at` must attach the existing `public.set_updated_at()` — do **not** recreate the function; its `down` lives with this migration, so a future migration's `down` only drops its own triggers. Extend the `Database` interface in `db/src/types.ts` with schema-qualified keys as tables arrive; keep `updated_at` as `ColumnType<Date, never, never>` everywhere (seed tasks 6.3/6.4: inserts/updates must not set it — the trigger and default handle it, and the types will refuse it at compile time). Constraint/index naming (`*_key`/`*_idx`/`*_fkey`) is now codified in db/README.md — use explicit names in Kysely (`addUniqueConstraint`/`addForeignKeyConstraint` require them anyway). `now()` is transaction-frozen in Postgres: within a single transaction `updated_at` will equal `created_at`; the trigger-fired proof used a stale-timestamp insert (see verification note above) — reuse that trick when testing. Trigger names are table-scoped, so both triggers are plainly `set_updated_at`.

## Task 6.2 — analytics.* Table Migrations

- **Date:** 2026-07-08
- **What was built:** Single migration `db/migrations/20260708223601_create_analytics_aggregate_tables.ts` creating the five analytics-layer tables per spec: `analytics.aggregate_runs` (uuid PK, status text + 6 named CHECK constraints covering the status enum, data-range ordering, completed/published/invalidated state machine, and the invalidation⇔reason biconditional; `created_at`/`updated_at` with the existing `public.set_updated_at()` trigger attached — **first reuse; function NOT recreated, owned by 6.1**) and the four immutable aggregate tables (`charge_outcome_aggregates`, `charge_sentencing_aggregates`, `judge_outcome_aggregates`, `judge_sentencing_aggregates`) built via a parameterized in-file helper: uuid PKs, NO ACTION FKs to `aggregate_runs`/`ref.normalized_charges`(/`ref.normalized_judges`), `numeric(5,2)` percentage, `sample_size` vs `sentencing_sample_size` (deliberately distinct names), `created_at` only — no `updated_at`, no trigger. "At most one active published run" enforced by raw-SQL partial unique index `aggregate_runs_active_published_idx ON ((true)) WHERE published_at IS NOT NULL AND invalidated_at IS NULL`. Unique constraints (the 6.4 ON CONFLICT keys) use **abbreviated names** — `<table>_run_charge_category_key` / `<table>_run_charge_judge_category_key` — because full column lists would exceed Postgres's 63-char identifier limit (approved; documented in db/README.md along with the new `*_check` naming rule). Secondary indexes on `charge_id` (all four) and `judge_id` (judge tables); none on `aggregate_run_id` — it's the leading column of each unique constraint. `down` drops the four aggregate tables, then the trigger, then `aggregate_runs`; plain drops, no CASCADE, `set_updated_at()` untouched. `db/src/types.ts`: five interfaces with schema-qualified `Database` keys; `status` typed as union `AggregateRunStatus`; `percentage` selects as `string` (pg returns numerics as strings); date/timestamptz insert positions accept `Date | string`; the four aggregate tables use a new `Immutable<S, I>` helper (`ColumnType<S, I, never>`) on **every** column — approved compile-time immutability. **Consequence: aggregate tables cannot be written via ON CONFLICT DO UPDATE; task 6.4 will seed aggregate rows by delete-and-reinsert within a transaction rather than upsert.** Deliberately no UPDATE-blocking DB trigger — immutability is type-and-convention enforced. Verified live on a fresh `db:reset` cycle: apply → `\d` inspection (all constraint/index/trigger names correct, none truncated) → down (all five tables gone via `to_regclass`, function and ref.* intact) → reapply clean; single rolled-back savepoint transaction covering FK violations on `aggregate_run_id`/`charge_id`/`judge_id`, bogus status, publishing an in_progress run, both directions of the invalidation⇔reason biconditional, invalidating a never-published run, second active published run rejected (and a published-but-invalidated run accepted, proving the partial predicate), duplicate unique keys on both a charge and a judge table, percentage 100.01, count −1, sentencing_sample_size 0; trigger check via 6.1's stale-timestamp trick (stale `updated_at` overwritten with `now()`, `created_at` untouched); post-rollback counts all 0. Root lint, typecheck, format:check, tests all pass (exit 0).
- **Files touched:** `db/migrations/20260708223601_create_analytics_aggregate_tables.ts` (new), `db/src/types.ts`, `db/README.md` (naming-convention lines), `tasks/worklog.md`.
- **Deviations from plan:** none beyond the four pre-approved flags (abbreviated unique names, `*_check` convention, `Immutable<>` typing, db:reset). One implementation detail surfaced during typecheck: the migration's shared table builder needed an explicit `CreateTableBuilder<string, string>` annotation (TS pins a reassigned `let` builder to its initial column union, rejecting `'judge_id'` in `addUniqueConstraint`) — type-level only, no `any`, no DDL change.
- **Notes for next task:** 6.3/6.4 seeding: aggregate-table types refuse UPDATE at compile time — seed via delete-and-reinsert in a transaction, keyed on the `*_run_charge(_judge)_category_key` constraints; plain inserts and `ON CONFLICT DO NOTHING` still typecheck, `DO UPDATE` will not. Publication flow implied by the constraints: publish requires `status = 'completed'`; invalidation requires the run to be published and `invalidated_reason` to be set (biconditional); to publish a new run while one is active, invalidate the old one (with reason) in the same transaction or the partial unique index rejects the second publish. `percentage` comes back from selects as a `string` — parse deliberately when building API payloads, and never conflate `sample_size` (outcome) with `sentencing_sample_size` (sentencing); the column names differ by design. `AggregateRunStatus` union is exported from `db/src/types.ts`.

## Task 6.3 — Seed Runner + Reference Seeds

- **Date:** 2026-07-08
- **What was built:** Seed infrastructure in `db/seeds/` run through Kysely: `reference-data.ts` (typed constants — the 5 real-PA-statute charges with 6 aliases and 3 obviously-fake judges with 3 aliases, exactly per the task tables; grades intentionally null), `reference.ts` (`seedReference(db)` — one transaction, order charges → charge aliases → judges → judge aliases, returns per-table upsert counts), and `run.ts` (CLI entrypoint mirroring `migrate.ts` patterns: `createDb()`, structured one-line-per-seed output, ECONNREFUSED hint, nonzero exit on failure). **Alias unique constraints already existed in migration 6.1** (`charge_aliases_normalized_charge_id_alias_text_key`, `judge_aliases_normalized_judge_id_alias_text_key`) — no new migration. Parent tables upsert `ON CONFLICT ON CONSTRAINT <slug_key> DO UPDATE` guarded by `WHERE (existing cols) IS DISTINCT FROM (excluded cols)` so unchanged rows skip the UPDATE entirely — no `updated_at` trigger churn; a repeat run is a literal no-op reporting 0 rows. Alias tables use `DO NOTHING` (the conflict key is the whole payload); parent IDs resolved by re-select on slug, failing loudly on a missing parent. Scripts: `seed` in `db/package.json` (`tsx --env-file-if-exists=../.env seeds/run.ts`), root `db:seed`. `describeError` extracted from `migrate.ts` into shared `db/src/errors.ts` (approved). Test setup new to `@pca/db`: vitest `^3.0.0` devDep, `test: vitest run`, `db/vitest.config.ts` loads root `.env` via guarded `process.loadEnvFile` (shell env takes precedence — vitest analog of `--env-file-if-exists`). `db/seeds/reference.test.ts` (6 tests): double-run in `beforeAll`, asserts exact charge/judge sets, alias→parent resolution via joins (exact pair sets, no orphans), second run reports 0 upserts, full-row snapshots (ids, `created_at`, `updated_at` included) identical across runs, and `analytics.*` row counts unchanged (captured before/after — seed code never references `analytics.*`). Guarded by `describe.skipIf(!DATABASE_URL)` with a console notice as a local-dev convenience. **Approved scope addition — `.github/workflows/ci.yml`:** "Apply migrations" moved before "Test" and `DATABASE_URL` (CI service container) set on both steps, so CI now executes the idempotency test rather than skipping it; no other workflow restructuring. `db/tsconfig.json` include extended with `seeds` + `vitest.config.ts` (trivially necessary, called out in plan). Verified locally: `pnpm db:seed` twice (run 1: 5/6/3/3 upserted; run 2: 0/0/0/0), db tests 6/6 pass against live DB, skip path prints notice with empty `DATABASE_URL`, root lint/format:check/typecheck/test all pass.
- **Files touched:** `db/seeds/reference-data.ts`, `db/seeds/reference.ts`, `db/seeds/run.ts`, `db/seeds/reference.test.ts`, `db/vitest.config.ts`, `db/src/errors.ts` (all new); `db/src/migrate.ts` (import swap), `db/package.json`, `db/tsconfig.json`, root `package.json`, `pnpm-lock.yaml`, `.github/workflows/ci.yml` (approved scope addition), `tasks/worklog.md`.
- **Deviations from plan:** none; the ci.yml change was a human-approved scope addition, not a silent deviation.
- **Notes for next task:** Reference seeds are **additive-only**: rows removed from seed data are NOT deleted from the database on subsequent runs. Delete-and-reinsert remains reserved for aggregate seeds (6.4). For 6.4: `seedReference` returns `SeedResult[]` and `run.ts` iterates it — a 6.4 aggregate seed step can slot into the same entrypoint; remember the aggregate tables' `Immutable<>` typing means delete-and-reinsert in a transaction, keyed per the 6.2 worklog notes. CI now applies migrations before tests with `DATABASE_URL` set — future DB-backed tests in any package will execute (not skip) in CI.

## Task 6.4 — Aggregate Seeds

- **Date:** 2026-07-08
- **What was built:** Analytics-layer seeds completing the Sprint 2 data layer: `db/seeds/aggregate-data.ts` (exported `SEED_PUBLISHED_RUN_ID` = `5eedda7a-0000-4000-8000-000000000001` and `SEED_UNPUBLISHED_RUN_ID` = `...0002`, fixed timestamp constants, MVP date range 2025-01-01→2026-06-30, and the full task-6.4 distribution matrices as typed data) and `db/seeds/aggregates.ts` (`validateAggregateSeeds()` + `seedAggregates(db)`), wired into `run.ts` after reference seeds with structured per-table output (`N deleted, N inserted`; no SQL dumps). Published run populates all four aggregate tables (34/20/17/12 rows) with every matrix scenario: charge-only thin data (criminal-trespass n=18), judge-specific thin data (simple-assault/testina n=9), sentencing-absent charge (possession-controlled-substance), judge-specific sentencing-absent pair (simple-assault/testina), fully-unavailable judge (judge-fakename-example — zero aggregate rows, ref rows only; the absence is the fixture), and judge distributions that visibly diverge from their charge baselines. Unpublished decoy run (`status in_progress`, `published_at` NULL): 5 retail-theft outcome rows at count 9999 each (sample size 49,995 = sum) — wrong in magnitude, structurally valid. Per run, one transaction: guarded PK upsert of the run row (`ON CONFLICT (id) DO UPDATE ... WHERE (cols) IS DISTINCT FROM (excluded cols)`, same pattern as 6.3, so an unchanged re-run fires no UPDATE and no `updated_at` churn), then DELETE from all four aggregate tables by run id, then INSERT — never `ON CONFLICT DO UPDATE` on aggregate tables. Category codes are addressable only via `publicCodeMap` over the `@pca/taxonomy` generated artifacts (`public: true` only — `unknown` unreachable; removed taxonomy codes become compile errors); `TAXONOMY_VERSION` (1.0.0) imported, never hardcoded. Percentages are `numeric(5,2)`: computed as `count/n×100` rounded to 2 dp, inserted as `toFixed(2)` strings. Self-validation runs in memory before any write and throws on: sum ≠ sample size, percentage off by > 0.005, non-public/duplicate codes, < 5 outcome / < 4 sentencing categories, wrong date range, thin flags diverging from a validator-side restatement of the matrix, sentencing n ≥ outcome n, or any row for the unavailable judge. `@pca/taxonomy` added as workspace dep of `@pca/db`; `db/src/types.ts` untouched. Verified on a fresh reset (`db:reset` → migrate → seed → seed): content-state snapshots byte-identical across re-runs, second run logs `run row unchanged`, exactly one active published run, decoy unpublished, fakename zero rows, 0 percentage mismatches on SQL recomputation across all 88 rows; root lint/format:check/typecheck/test all pass (60 tests).
- **Files touched:** `db/seeds/aggregate-data.ts`, `db/seeds/aggregates.ts` (new); `db/seeds/run.ts`, `db/seeds/reference.ts` (exported existing `selectIdBySlug`/`requireId` helpers only — aggregate seeds resolve charge/judge UUIDs by slug at runtime), `db/package.json`, `pnpm-lock.yaml`, `tasks/worklog.md`.
- **Deviations from plan:** none; all three plan questions were answered before implementation (chain generate into seed script; content-identity; `parser_version` NULL).
- **Seed-script change and rationale:** `db/package.json` `seed` is now `pnpm --filter @pca/taxonomy run generate && tsx --env-file-if-exists=../.env seeds/run.ts`. `packages/taxonomy/generated/` is gitignored and only CI / root `test`/`typecheck` ran generate, so on a fresh clone a standalone `pnpm db:seed` would die on module-not-found; chaining the generate step makes `db:seed` self-sufficient (verified by deleting `generated/` before seeding — it was recreated and the seed ran clean).
- **Idempotency definition (as approved):** re-runs produce **identical content columns**; aggregate rows' surrogate `id`s regenerate on each delete-and-reinsert. That is sufficient because nothing may ever reference an aggregate row's surrogate ID (the public API forbids exposing row/fact IDs). Run rows are byte-identical including `created_at`/`updated_at` (fixed timestamp constants + the IS DISTINCT FROM guard).
- **Criterion 9 demonstration:** with retail-theft `guilty_plea` deliberately corrupted 540→541, `pnpm db:seed` exited 1 with: `Seed runner failed: aggregate seed validation failed [published charge outcomes: retail-theft]: category counts sum to 1201, expected sample size 1200` — and the database was untouched (validation precedes all writes; state diff vs. pre-corruption snapshot was empty). The corruption was then reverted (verified zero occurrences of the bad count in the data file) and a clean reseed restored state byte-identical to the original seed.
- **Known re-seed property (intended):** if the seed run were manually invalidated and a different run published, re-seeding fails loudly on `aggregate_runs_active_published_idx` (the upsert would flip the seed run back to active-published, making a second qualifying row) rather than silently un-invalidating. Seeds target fresh migrated databases; this failure mode is deliberate.
- **Notes for next task:** Phase 7/8 API work can rely on: exactly one active published run (`published_at IS NOT NULL AND invalidated_at IS NULL`) = `SEED_PUBLISHED_RUN_ID`; the decoy run's data must never surface publicly (Phase 8 tests should assert its 9999-count rows are invisible); every published-run scenario in the 6.4 matrix exists for endpoint fixtures, including all absence scenarios. Thin-data flags were set directly per the matrix — threshold logic is still deferred. `pnpm db:seed` now regenerates taxonomy artifacts itself; the `seedAggregates` return shape (`AggregateRunResult[]`) mirrors 6.3's `SeedResult[]` pattern if future steps slot into `run.ts`.

## Task 7.1 — Public Error Catalog + Format Registration

- **Date:** 2026-07-08
- **What was built:** Public error contract in `@pca/shared` plus the API plumbing that emits it. `packages/shared/src/errors.ts`: `PUBLIC_ERROR_CODES` const object with **nine** codes (the task's eight plus `NOT_FOUND`, approved at plan review for unknown routes), derived `PublicErrorCode` union, `PUBLIC_ERROR_CODE_STATUS` default-status map (400/404/429/500; module doc states explicitly these are **defaults, not invariants** — the emitted `statusCode` field is authoritative and may pair a code with a non-default status, e.g. INVALID_REQUEST with 415), `publicErrorCodeSchema` (union of literals derived from the const), `publicErrorResponseSchema` (`{ statusCode, code, error, message, requestId }`, `additionalProperties: false`) + `PublicErrorResponse`, and `isPublicErrorCode()` type guard (`Object.hasOwn`, so prototype members like `toString` don't count). `packages/shared/src/formats.ts`: `registerFormats()` registering `date`/`date-time`/`uuid` in TypeBox's `FormatRegistry`, idempotent via `FormatRegistry.Has` guards (second call no-ops, never throws, never replaces checkers); checkers mirror ajv-formats "full" semantics (calendar-valid dates incl. leap years, RFC 3339 date-time with offset + leap-second 23:59:60, ajv-formats uuid pattern) so the TypeBox path agrees with the API's Ajv path. Supersedes and deletes `src/test-support/formats.ts` (approved); shared tests now get formats from `vitest.config.ts` + `src/test-support/setup.ts` (setup file calls `registerFormats()`), inline `registerStringFormats()` calls removed from the three schema test files. `apps/api/src/app.ts`: `buildApp` calls `registerFormats()` as its first statement (no app instance without formats); error handler extended to three branches, all `satisfies PublicErrorResponse` — (1) `error.validation` → 400 `INVALID_REQUEST` with Ajv's message; (2) errors carrying a catalog `code` (the 7.2+ plumbing: `throw Object.assign(new Error(msg), { code })`) → that code, status from the catalog default unless the error has an explicit `statusCode ≥ 400`; (3) fallback → original 4xx status with `INVALID_REQUEST`, or ≥500 with `INTERNAL_ERROR`; 5xx message-leak protection retained and now applied by final status in every branch (a 503 also gets the generic message). Not-found handler emits `code: NOT_FOUND`. `@pca/shared` added as a workspace dep of `@pca/api`. Tests: `errors.test.ts` (catalog exactness, status map, type guard, response-schema shape/required/extra-prop/status-range) and `formats.test.ts` (idempotency incl. checker identity, fail-closed unregistered formats, calendar/leap-year dates, RFC 3339 date-times through the real `chargeOnlyResultSchema`, uuid) in shared (58 total); API suite rewritten additively to 13 (1.3 tests kept and updated — 404 now asserts `NOT_FOUND` + exact five-key shape): malformed/calendar-invalid date and malformed uuid → 400 `INVALID_REQUEST` through `fastify.inject` on a schema'd route (regression lock), well-formed values pass, 500 and 503 leak tests with sentinel strings, catalog-code passthrough (CHARGE_NOT_FOUND → 404), explicit-status override (INVALID_REQUEST @ 415), malformed JSON body → `INVALID_REQUEST`. Verified: root lint, typecheck, format:check green; 93 tests pass workspace-wide.
- **Two findings for the record (plan-stage probes, empirically verified):** (1) Request validation runs through **Fastify's Ajv** (`@fastify/ajv-compiler@4`, which **bundles ajv-formats**) — `date`/`date-time`/`uuid` were already enforced in the real request path, including calendar validity; the TypeBox type provider is compile-time only. (2) **TypeBox 0.34 fails CLOSED on unregistered formats** — `Value.Check`/`TypeCompiler` reject *every* value (valid or not) for a format with no registered checker; the 3.2-era "passes silently" behavior no longer exists in the installed version. Registration is therefore load-bearing in both worlds: without it, format-carrying schemas reject valid data.
- **Files touched:** `packages/shared/src/errors.ts`, `errors.test.ts`, `formats.ts`, `formats.test.ts`, `src/test-support/setup.ts`, `vitest.config.ts` (new); `packages/shared/src/index.ts`, `src/public/{categories,common,results}.test.ts` (format-registration import swap); `packages/shared/src/test-support/formats.ts` (deleted, approved); `apps/api/src/app.ts`, `apps/api/src/app.test.ts`, `apps/api/package.json` (+`@pca/shared`), `pnpm-lock.yaml`, `tasks/worklog.md`.
- **Deviations from plan:** one, forced by finding (2) above: the plan promised a shared test showing the previously-silent TypeCompiler path "now failing" on malformed values; since TypeBox 0.34 fails closed rather than silently passing, that test instead documents the fail-closed behavior (`unregistered formats reject everything`) and the module comment states the real semantics. Everything else exactly per the approved plan and its four answered questions.
- **Notes for next task (7.2+):** Throw domain errors as `Object.assign(new Error('…'), { code: PUBLIC_ERROR_CODES.X })` — the handler resolves the status from `PUBLIC_ERROR_CODE_STATUS`, or honors an explicit `statusCode ≥ 400` on the error. 4xx messages ARE echoed to clients — keep them generic (the errors.ts module doc lists the forbidden topics); ≥500 is always masked. `RATE_LIMITED` exists in the catalog only — no middleware. Package-scoped `pnpm --filter @pca/api typecheck|test` now needs `pnpm generate` first (api → shared → taxonomy generated artifacts); root scripts and CI already handle it. The 3.2 note about lifting the error schema into `@pca/shared` is now done.

## Task 7.2 — Charge Search Endpoint

- **Date:** 2026-07-08
- **What was built:** The first real public endpoint: `GET /api/v1/public/charges/search?q={query}&limit={limit}`, layered route → validation → service → repository. Validation runs through Fastify's Ajv against the shared TypeBox `chargeSearchQuerySchema` (`q` required; `limit` optional integer 1–25, default 10; `additionalProperties: false`); the post-trim 1–100 length rule on `q` lives in the service as a catalog `INVALID_REQUEST` throw (Ajv cannot trim), invoked before any DB access via a `getDb` thunk. Response contract shipped exactly as specified: `{ results: ChargeSearchResult[] }` with `id` (uuid), `slug`, `displayName`, `statuteCode?`, `grade?`, `matchedAlias?` — optionals omitted (never null), `additionalProperties: false`, and the route serializes through the response schema so anything outside the contract is stripped (aggregate-only defense in depth). **The 3.2 placeholder charge schemas were replaced in place** in `packages/shared/src/public/search.ts` (`chargeSuggestionSchema`/`ChargeSuggestion` with `chargeId` are gone; `chargeSearchResponseSchema` rebuilt on the new result shape); judge schemas untouched pending 7.3. Search semantics per spec, all in one Kysely query with bound parameters: case-insensitive matching against display name, alias text, and statute code (NULL statutes drop out naturally); **LIKE-wildcard safety via `escapeLike()` (escapes `%`, `_`, and `\`) with an explicit `ESCAPE '\'` clause on every ILIKE** — `q="%"`/`q="_"` match only literal content (empty against seeds); ranking exact(1) → prefix(2) → substring(3) computed across the best match on any field, tie-broken by `display_name` then `slug` (stabilizer); dedup is structural (base table `ref.normalized_charges` + `EXISTS`/correlated subselects, no join fan-out); `matched_alias` = `MIN(alias_text)` over matching aliases, gated on the display name NOT matching — so name matches suppress it and statute-only matches leave it NULL; `LIMIT` after ranking; no-match is 200 `{ results: [] }`. All errors flow through the 7.1 handler via `publicError()` (`apps/api/src/public-error.ts`); zero response shaping in route/service. **`@pca/db` gained a public entry point** (`main`/`exports` → `db/src/index.ts`) re-exporting ONLY the `Database` type and `seedReference` — **this is now the standard consumption pattern: future endpoint repositories derive narrowed interfaces via `Pick<Database, ...>`, never copy column types.** `apps/api/src/db.ts` does exactly that: `PublicApiDatabase = Pick<Database, 'ref.normalized_charges' | 'ref.charge_aliases'>`, making any non-`ref` table access a compile error (criterion 4 at the type level); `getDb()` is a lazy decorator so `buildApp()` works without `DATABASE_URL` (app-created connections destroyed on close; injected ones belong to the caller). Tests (23 new; 36 total in api): validation cases run DB-free (missing/whitespace/overlong `q`; `limit` 0/26/1.5/non-numeric — all asserting the exact five-key catalog shape); DB-backed cases (`describe.skipIf(!DATABASE_URL)`) cover the exact→prefix→substring ranking ladder, alias match with `matchedAlias`, substring, case-insensitivity, dedup with name-match suppression, alphabetically-first alias (`q="dr"`), statute exact+substring without `matchedAlias`, empty-result success, wildcard-literal proof, trim-to-100 boundary, default-10 and max-25 limit proofs, inactive-charge exclusion, and a recursive forbidden-content sweep (only contract keys; no count/percentage/sampleSize/docket/defendant/source/parser/review). **API test data pattern (standing): setup calls the exported `seedReference` (idempotent, single source of truth — makes the suite self-sufficient in CI, which migrates but never runs `db:seed`) plus `zz-test-*` temp rows (ranking ladder, inactive decoy, 26 limit rows) deleted both before insert and in `afterAll`** — the db package's exact-seed-snapshot test passes afterward, proving cleanup. Verified: live server smoke test (exact/alias/statute/wildcard/error paths all contract-exact), root lint / typecheck / format:check / test all exit 0 (shared 64, db 6, api 36 tests; DB-backed cases executed, not skipped).
- **Files touched:** `packages/shared/src/public/search.ts`, `search.test.ts`, `src/test-support/fixtures.ts`; `db/package.json` (entry point only), `db/src/index.ts` (new); `apps/api/src/db.ts`, `public-error.ts`, `repositories/charge-search.ts`, `services/charge-search.ts`, `routes/public/charges.ts`, `routes/public/charges.test.ts`, `vitest.config.ts` (all new); `apps/api/src/app.ts` (registerDb + `db` option), `routes/public/index.ts`, `package.json` (+`@pca/db`, `kysely ^0.29.3`, `pg ^8.22.0`, dev `@types/pg`); `pnpm-lock.yaml`; `tasks/worklog.md`.
- **Deviations from plan:** none. The three plan-review modifications (replace 3.2 placeholders in place; `@pca/db` entry point + `Pick`-derived narrowing instead of copied types; `seedReference` in test setup instead of duplicated upserts) were applied exactly as directed.
- **Notes for next task (7.3):** Consume `@pca/db` through its entry point and derive the judge repository's interface via `Pick<Database, 'ref.normalized_judges' | 'ref.judge_aliases'>` — never hand-copy column types. The judge placeholder schemas (`judgeSuggestionSchema` with `judgeId`) are still the 3.2 shape and will need the same in-place replacement. Reuse `escapeLike` + `ESCAPE '\'` for any LIKE matching, `publicError()` for catalog throws, the lazy `getDb` decorator, and the test-data pattern (seedReference + prefixed temp rows with before-and-after cleanup). `limit ?? 10` in the route is type-narrowing only — Ajv `useDefaults` fills the default. CI still never runs `db:seed`; endpoint suites must stay self-seeding.

## Task 7.3 — Judge Search Endpoint

- **Date:** 2026-07-08
- **What was built:** `GET /api/v1/public/judges/search?q={query}&limit={limit}`, the near-mirror of 7.2's charge search, layered route → validation → service → repository. **Shared search constants extracted** (locked design rule 6): `SEARCH_Q_MIN_LENGTH` (1), `SEARCH_Q_MAX_LENGTH` (100), `SEARCH_LIMIT_MIN` (1), `SEARCH_LIMIT_MAX` (25), `SEARCH_LIMIT_DEFAULT` (10) now live in `packages/shared/src/public/search.ts` alongside the schemas; `chargeSearchQuerySchema`, both services' trimmed-length checks, and both routes' `limit ??` fallbacks consume them — no duplicated literals, behavior-neutral (all 23 existing 7.2 tests pass unchanged). **The 3.2 placeholder judge schemas were deleted and replaced in place** (same treatment 7.2 gave the charge placeholders): `judgeSuggestionSchema`/`JudgeSuggestion` (`judgeId`, no uuid format, no `matchedAlias`) are gone; new `judgeSearchQuerySchema` (identical q/limit rules via the constants) and `judgeSearchResultSchema`/`JudgeSearchResult` — exactly `id` (uuid), `slug`, `displayName`, optional `matchedAlias`, `additionalProperties: false` — with `judgeSearchResponseSchema` rebuilt on it; shared fixtures and schema tests updated to match (shared suite now 71 tests). **`escapeLike` moved verbatim** from `apps/api/src/repositories/charge-search.ts` to new `apps/api/src/repositories/search-helpers.ts` and re-exported from charge-search.ts so the 7.2 test's import path (and everything else) is untouched; both repositories import the single helper — no copy-paste, and no generalized two-entity search abstraction (queries deliberately stay separate; charges have a third match column). New `apps/api/src/repositories/judge-search.ts`: one Kysely query with bound parameters — `is_active = true`, ILIKE-with-`ESCAPE '\'` over `display_name` plus an `EXISTS` correlated subselect over `ref.judge_aliases` (structural dedup, no join fan-out), `match_rank` CASE exact(1) → prefix(2) → substring(3) across name and aliases, tie-break `display_name` then `slug`, `LIMIT` after ranking; `matched_alias` = `MIN(alias_text)` **over matching aliases only** (the subselect repeats the ILIKE filter), gated on the display name NOT matching. New `apps/api/src/services/judge-search.ts` (trim + constant-driven length check via `publicError(INVALID_REQUEST)`, `getDb` thunk, omit-when-null mapping) and `apps/api/src/routes/public/judges.ts` (serializes through the response schema; registered in the public plugin). `PublicApiDatabase` widened to the four `ref.*` tables (still `Pick<Database, ...>` — analytics/raw/etc. remain compile errors). Tests: 22 new in `apps/api/src/routes/public/judges.test.ts` mirroring 7.2's structure — 7 DB-free validation cases (exact five-key catalog error shape) + 15 DB-backed cases (seedReference + `zz-test-*` temp judges with before-and-after cleanup, aliases cascade): ranking ladder (`q="fakename"`: temp exact/prefix over seeded substring), alias-only match populating `matchedAlias` (seeded `T. Placeholder`), name-substring without it, case-insensitivity, name+alias dedup with suppression, empty-result 200, wildcard literals, trim-to-100 boundary, default-10/max-25 limits (26 uniform rows), inactive exclusion, **dual exact-key-set assertions** (pinned: `Object.keys().sort()` equals `['displayName','id','slug']` on a name-match row and `['displayName','id','matchedAlias','slug']` on an alias-match row — the omit-when-null mapping is test-locked end to end, not just serializer-enforced), and a recursive contract sweep additionally asserting the absence of `caseCount`/`resultCount`/`sampleSize`/`count`/`score`/`rank` (criterion 6: no numeric judge metadata anywhere). Verified: root lint, typecheck, format:check, and full test suite all exit 0 — 151 tests workspace-wide (shared 71, api 58, db 6, taxonomy 14, web 2), DB-backed cases executed against local Postgres, not skipped.
- **Pin-3 mutation verification (matchedAlias over matching aliases only):** the alias-heavy temp judge carries a decoy alias (`aaa decoy alias`) that sorts alphabetically first across its full alias set but does not match the test query, plus two matching aliases. To prove the test has teeth, the repository was temporarily mutated to take `MIN(alias_text)` over the judge's full alias set: the "alphabetically first MATCHING alias" test failed exactly as pinned (decoy surfaced instead of `bbb querytoken alias`); the mutation was reverted and the full suite re-verified green.
- **Files touched:** `packages/shared/src/public/search.ts`, `packages/shared/src/public/search.test.ts`, `packages/shared/src/test-support/fixtures.ts`; `apps/api/src/repositories/search-helpers.ts` (new), `apps/api/src/repositories/judge-search.ts` (new), `apps/api/src/services/judge-search.ts` (new), `apps/api/src/routes/public/judges.ts` (new), `apps/api/src/routes/public/judges.test.ts` (new); `apps/api/src/repositories/charge-search.ts`, `apps/api/src/services/charge-search.ts`, `apps/api/src/routes/public/charges.ts`, `apps/api/src/routes/public/index.ts`, `apps/api/src/db.ts`; `tasks/worklog.md`. No dependency changes.
- **Deviations from plan:** none. Plan-review resolutions applied as directed: old judge schema symbols deleted outright (no deprecated aliases), constants co-located in `search.ts`, charge-search re-export approved, pins 3 and 4 implemented and demonstrated as specified.
- **Notes for next task (8.1/8.2):** Both search endpoints are identity-only; all statistics come from the 8.x result endpoints, which must read exclusively from the active published run (`SEED_PUBLISHED_RUN_ID` per 6.4 — assert the 9999-count decoy rows never surface). `judge-fakename-example` has zero aggregate rows by design (the judge-specific-unavailable fixture); it IS searchable via this endpoint — availability of statistics is not a search concern. Reuse the shared `SEARCH_*` constants for any future q/limit validation; `search-helpers.ts` is the home for query-building helpers shared across repositories. Result endpoints will need `PublicApiDatabase` widened again (analytics.* aggregate tables + `aggregate_runs`) — keep it a `Pick`, and keep the public plugin free of anything non-aggregate. Fuzzy/trigram search for both entities remains deferred to Sprint 5 with the real corpus.

## Task 8.1 — Charge-Only Result Endpoint

- **Date:** 2026-07-09
- **What was built:** `GET /api/v1/public/results/charge/{chargeIdOrSlug}` — the first public result endpoint and first consumer of the analytics layer, layered route → validation → service → repository. **Shared contract** (new module `packages/shared/src/public/charge-result.ts`, star-exported from the package index): `chargeOnlyResultResponseSchema` per the pinned 8.1 shape — `charge` `{ id (uuid), slug, displayName, statuteCode?, grade? }` (omit-when-null), `resultType`/`geography` pinned literals (`charge_only`/`philadelphia`), result-level `dateRange`, `lastRefreshed` (date-time), `taxonomyVersion`, `aggregateRunId` (uuid; the ONLY run field exposed), `outcomes` `{ sampleSize, thinData, rows }`, the **sentencing tagged union** (`{ available: true, sampleSize, thinData, rows }` | `{ available: false, message }` with `message` schema-pinned via `Type.Literal` to the exported `CHARGE_SENTENCING_UNAVAILABLE_MESSAGE` constant — any other wording is a validation failure, not a convention), and `links` pinned to `/methodology`/`/definitions`. Row schemas reuse `outcomeDistributionEntrySchema`/`sentencingDistributionEntrySchema` from `common.ts` (already the exact pinned row shape with public-only category-code literal unions); all objects `additionalProperties: false`. **The stale task-3.2 `chargeOnlyResultSchema` was deleted from `results.ts`** (approved Q2) — its consumers (results.test.ts, formats.test.ts, fixtures.ts) repointed at the new contract; `judgeSpecificResultSchema` left untouched for 8.2. Error status defaults for `CHARGE_NOT_FOUND`/`CHARGE_RESULT_UNAVAILABLE` were confirmed already 404 in the 7.1 catalog — no change needed. **API:** `repositories/charge-result.ts` — `findActivePublishedRun` (`published_at IS NOT NULL AND invalidated_at IS NULL`, defensive `ORDER BY published_at DESC, id LIMIT 1` atop the 6.2 partial unique index; date columns cast `::text` in SQL so calendar dates can never shift through pg's Date/timezone handling; `$narrowType` for the WHERE-guaranteed non-null `published_at`), structurally separate `findActiveChargeById`/`findActiveChargeBySlug` (both `is_active = true`; no fallthrough is architecture, not a conditional), and two distribution reads scoped `WHERE aggregate_run_id = run AND charge_id = charge` — decoy/invalidated runs are excluded by construction. `services/charge-result.ts` — generic 8-4-4-4-12 case-insensitive UUID regex dispatch (no v4 nibble check, as confirmed); charge resolved BEFORE run so an unknown charge is `CHARGE_NOT_FOUND` even with no published run; no-run and zero-outcome-rows both throw `CHARGE_RESULT_UNAVAILABLE` with one shared message (publicly indistinguishable by design); **sample-size uniformity check per distribution (required fix 1)** — disagreeing `sample_size`/`sentencing_sample_size` within one distribution throws `INTERNAL_ERROR`, never a silent pick; taxonomy mapping via new `apps/api/src/taxonomy.ts` (maps built from `public: true` artifact entries only, so unknown-to-artifact and known-but-internal codes like `unknown` are the identical `INTERNAL_ERROR` integrity failure, offending code never in the public message — the 7.1 handler masks all 5xx bodies); rows sorted by taxonomy `sortOrder`; `thinData` = any-row rule; `percentage` = `Number(numeric(5,2) string)` — representation change, never recomputation. Route serializes through the response schema (strips anything off-contract; fast-json-stringify discriminates the union fine — verified live). `PublicApiDatabase` widened via `Pick` with `analytics.aggregate_runs` + the two charge aggregate tables only (judge tables await 8.2); `@pca/taxonomy` added to `apps/api` deps. **Tests:** 14 service-level unit tests with a `vi.mock`-stubbed repository (no DB): both sample-size-mismatch paths, unknown + non-public category codes, id/slug dispatch incl. case-insensitivity and miss-without-slug-consult, not-found-before-run ordering, both unavailable states, sortOrder-vs-storage-order, any-row thinData, unavailable-arm constant, independent sample sizes. 10 DB-backed endpoint tests (`describe.skipIf(!DATABASE_URL)`, self-seeding via `seedReference` **and `seedAggregates`**): full-metadata success by slug with hand-restated expected rows in taxonomy order (retail-theft 1200/700), byte-identical body by UUID incl. uppercase, thin-data charge (criminal-trespass), sentencing-unavailable charge (possession-controlled-substance) with outcomes intact, unknown slug + UUID-shaped miss → 404 `CHARGE_NOT_FOUND` in the exact five-key shape, **no-fallthrough proof with teeth**: an ACTIVE temp charge whose slug IS a UUID-shaped string returns `CHARGE_NOT_FOUND` (fallthrough would resolve it and produce `CHARGE_RESULT_UNAVAILABLE` — the differing codes make the bug detectable), inactive charge → `CHARGE_NOT_FOUND`, `expect(body).not.toContain('9999')` decoy probe, recursive allowed-key sweep, and a public-safety substring guard run on EVERY response in the suite (bare `raw` would false-positive on "withdrawn", so raw* is caught as the JSON-prefix `"raw` plus the key sweep). 11 new shared schema tests (both union arms, wrong-message rejection, arm mixtures, literal pins, legacy `entries`-shape rejection, extra-prop rejection at every nesting level). Verified: root lint / typecheck / full test suite green — 82 api + 77 shared tests, DB-backed cases executed (not skipped); live server smoke test confirmed contract-exact success, union, and error bodies.
- **APPROVED SCOPE EXCEPTION (Q1):** one line added to the do-not-touch `db/**`: `export { seedAggregates } from '../seeds/aggregates.js';` in `db/src/index.ts`, explicitly authorized at plan review so the endpoint suite can self-seed aggregates in CI (which migrates but never runs `db:seed`; deep imports are blocked by the package `exports` map). No seed data, seed logic, or anything else under `db/**` was touched.
- **Files touched:** `packages/shared/src/public/charge-result.ts` + `charge-result.test.ts` (new); `packages/shared/src/public/results.ts`, `results.test.ts`, `formats.test.ts`, `test-support/fixtures.ts`, `index.ts`; `db/src/index.ts` (the Q1 exception line only); `apps/api/src/taxonomy.ts`, `repositories/charge-result.ts`, `services/charge-result.ts` + `charge-result.test.ts`, `routes/public/results.ts` + `results.test.ts` (all new); `apps/api/src/db.ts`, `routes/public/index.ts`, `package.json` (+`@pca/taxonomy`); `pnpm-lock.yaml`; `tasks/worklog.md`.
- **Deviations from plan:** none beyond the two human-required fixes (sample-size uniformity check + explicit cleanup tracking of the UUID-shaped-slug and inactive temp charges), both implemented as directed. Two additive test extras called out at review: the inactive-charge case (covers a pinned decision absent from the minimum list) and the uppercase-UUID variant.
- **Notes for next task (8.2):** The judge-specific endpoint can mirror this shape wholesale: widen `PublicApiDatabase` with the two `analytics.judge_*` tables (keep it a `Pick`), reuse `resolvePublicCategory` from `apps/api/src/taxonomy.ts` and the service's distribution-block pattern (uniformity check, any-row thinData, sortOrder mapping), and register routes in `routes/public/results.ts`'s plugin. `judgeSpecificResultSchema` in `results.ts` is still the 3.2 sketch and needs the same delete-and-replace treatment (new module recommended, matching `charge-result.ts`). `judge-fakename-example` (ref rows, zero aggregates) is the judge-specific-unavailable fixture; simple-assault/judge-testina-placeholder is the judge sentencing-absent + thin-data pair. **Test-suite isolation rule (standing): vitest runs api test files in parallel against one database — every suite needs its OWN temp-slug prefix** (`zz-test-` = search suites, `zz-result-` = this one) **and any temp row whose slug can't match the prefix must be tracked and deleted explicitly** (this suite's UUID-shaped probe). Temp charges with aggregate rows would need their analytics rows deleted before the ref row (FK NO ACTION); this suite avoided that by giving probes zero aggregates — the corrupt-aggregate paths are unit-tested against a stubbed repository instead, per plan review. `SENTENCING_RESULT_UNAVAILABLE` remains unused in favor of the tagged union (catalog entry exists if 8.2 decides otherwise).

## Task 8.2 — Judge-Specific Result Endpoint

- **Date:** 2026-07-09
- **What was built:** `GET /api/v1/public/results/charge/{chargeIdOrSlug}/judge/{judgeIdOrSlug}` — the judge-specific result with mandatory Philadelphia baseline and the HTTP-200 structured judge-unavailable response. **Shared contract** (new module `packages/shared/src/public/judge-result.ts`, star-exported from the index): a **top-level tagged union** `judgeSpecificResultResponseSchema` discriminated by `resultType` literals, used as the route's single 200 response schema so serialization stripping covers both arms. Success arm (`judge_specific`): `charge` (reuses 8.1's `chargeSummarySchema`), new `judgeSummarySchema` `{ id (uuid), slug, displayName }`, `geography`/`dateRange`/`lastRefreshed`/`taxonomyVersion`/`aggregateRunId`/`links` with identical semantics and sourcing to 8.1, and `judgeSpecific` + `baseline` scopes each holding `{ outcomes: <8.1 block schema>, sentencing: <8.1 tagged union> }` — row shape identical to 8.1, four fully independent sample sizes, baseline REQUIRED on every success. Unavailable arm (`judge_specific_unavailable`, HTTP 200): identity (`charge`, `judge`), `code` pinned via `Type.Literal` to the catalog's `JUDGE_SPECIFIC_RESULT_UNAVAILABLE`, `message` pinned to the new exported constant `JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE`, and `fallback.chargeOnlyResultPath` — **no distributions, no sample sizes, no run metadata, and (confirmed at plan review) no `links`**. `additionalProperties: false` throughout. **STALE 3.2 DELETION:** `packages/shared/src/public/results.ts` (whose only remaining content was the task-3.2 `judgeSpecificResultSchema` sketch) and `results.test.ts` were deleted entirely; the `validJudgeSpecificResult` fixture was replaced with fixtures for both new arms; `common.ts`'s distribution schemas untouched. **API:** `PublicApiDatabase` widened (still a `Pick`) by exactly `analytics.judge_outcome_aggregates` + `analytics.judge_sentencing_aggregates`. **Shared distribution builder extracted** to `apps/api/src/services/result-helpers.ts` — `UUID_PATTERN`, `buildDistributionBlock` (uniformity check → `INTERNAL_ERROR`, any-row thinData, taxonomy sortOrder + display names, numeric(5,2)→number conversion), and `buildSentencing` (the sentencing-union assembly) — consumed by BOTH result services; 8.1's unit suite passed byte-identical and its integration suite changed only by the seeding-removal lines (regression lock held). New `repositories/judge-result.ts` (`findActiveJudgeById`/`BySlug` — active-only, structurally separate, no fallthrough; `getJudgeOutcomeRows`/`getJudgeSentencingRows` scoped run+charge+judge, reusing 8.1's exported row types since the columns are identical) and `services/judge-result.ts`; second route registered in the existing `routes/public/results.ts` plugin. **AVAILABILITY QUADRANT (supersedes the task file's top-down step ordering, confirmed at plan approval and recorded in a comment at the decision site):** resolution order charge → judge → run (entity 404s `CHARGE_NOT_FOUND`/`JUDGE_NOT_FOUND` independent of publication state; no run → 404 `CHARGE_RESULT_UNAVAILABLE`), then on the two outcome-row sets: baseline empty + judge rows empty → 404 `CHARGE_RESULT_UNAVAILABLE`; baseline empty + judge rows present → 500 `INTERNAL_ERROR` (aggregation must produce the baseline superset); baseline present + judge rows empty → HTTP 200 unavailable arm (fallback truthful by construction — baseline just verified); both present → success. The task file's literal steps 2/4 cannot both be reachable in written order; the quadrant satisfies all four pinned outcomes and is the authoritative reading. The catalog's status default for `JUDGE_SPECIFIC_RESULT_UNAVAILABLE` remains unused by this endpoint (defaults are not invariants); catalog untouched. **GLOBALSETUP SEEDING REFACTOR (in scope):** new `apps/api/vitest.global-setup.ts` runs `seedReference` + `seedAggregates` once per test run when `DATABASE_URL` is set (wired via `vitest.config.ts` `test.globalSetup`); the three DB-backed suites (charges, judges, results) dropped their self-seeding `beforeAll` calls, keeping skip guards, temp prefixes, and cleanup unchanged. **Rationale:** vitest runs api test files in parallel against one database and `seedAggregates` is delete-and-reinsert per run — two aggregate-seeding suites racing could observe each other's window of deleted aggregate rows; one seeding pass before any suite removes the race. **Verification duty A (env proven, not assumed):** the run's output shows `vitest globalSetup: seeding reference and aggregate data… / seeding complete.` before any suite executed — `DATABASE_URL` from the root `.env` (loaded by `vitest.config.ts`, same Vitest process, before globalSetup) was observed populated; no extra env loading needed. **Verification duty B (fail loudly):** globalSetup has no catch around connection/seeding; proven empirically — a deliberate bad-DSN run (`DATABASE_URL='postgresql://nobody@localhost:1/nope'`) made globalSetup throw `ECONNREFUSED` and **vitest exited 1**, failing the entire run instead of silently skipping. In the real run the DB-backed suites RAN, not skipped: apps/api 7 files / 105 tests passed, 0 skipped (results 10, judge-results 10, charges 23, judges 22). **Tests:** 13 service unit tests (`vi.mock` on both repositories): all four quadrant branches (incl. no-baseline-with-judge-rows → `INTERNAL_ERROR` and the exact unavailable-arm body with no sentencing reads), charge-before-judge-before-run ordering, per-param UUID/slug dispatch with no fallthrough, judge-scoped uniformity mismatches (outcome + sentencing), unknown/non-public category codes on judge rows, judge-sentencing-unavailable with baseline union independently available, four independent sample sizes. 10 DB-backed endpoint tests (`zz-judge-result-` prefix; UUID-shaped judge-slug probe tracked explicitly in cleanup): full success by slugs with hand-restated rows in taxonomy order and `[140, 85, 1200, 700]` sample sizes (uniqueness asserted), byte-identical bodies for UUID/mixed-both-ways/uppercase param modes, thin-data pair (simple-assault/testina n=9 — the seeded pair also lacks judge sentencing rows, so the same test covers judge-sentencing-unavailable at the integration level), exact-body unavailable arm for retail-theft/judge-fakename-example (slug AND UUID modes) with the pinned literals and truthful fallback path, unknown charge (+unknown judge → `CHARGE_NOT_FOUND`, proving resolution order), unknown judge slug + UUID → `JUDGE_NOT_FOUND` in the exact five-key shape, judge no-fallthrough proof with teeth (ACTIVE temp judge under a UUID-shaped slug → `JUDGE_NOT_FOUND`; fallthrough would yield the 200 unavailable arm), inactive judge → `JUDGE_NOT_FOUND`, decoy-9999 probe, and forbidden-substring + recursive allowed-key guards on every response across both arms. 10 new shared schema tests (both arms, union disjointness, literal pins, required fields incl. baseline and per-scope blocks, smuggled-field rejection on the unavailable arm). Verified: root lint / typecheck / full test suite all green (shared 83, api 105, db 6, taxonomy 14, web 2).
- **CHARGE_RESULT_UNAVAILABLE_MESSAGE export note:** the constant was promoted from module-private to exported in `apps/api/src/services/charge-result.ts` so the 8.2 service throws the identical message for the identical code (disclosed at completion, accepted). **Recorded for later: this constant migrates to `@pca/shared` in Task 10.2 alongside the other copy constants.** No action now.
- **Files touched:** `packages/shared/src/public/judge-result.ts` + `judge-result.test.ts` (new); `packages/shared/src/public/results.ts` + `results.test.ts` (deleted); `packages/shared/src/test-support/fixtures.ts`, `packages/shared/src/index.ts`; `apps/api/src/services/result-helpers.ts`, `services/judge-result.ts` + `judge-result.test.ts`, `repositories/judge-result.ts`, `routes/public/judge-results.test.ts`, `vitest.global-setup.ts` (all new); `apps/api/src/db.ts`, `services/charge-result.ts`, `routes/public/results.ts`, `routes/public/{charges,judges,results}.test.ts` (seeding-removal only), `vitest.config.ts`; `tasks/worklog.md`. No dependency, migration, seed, catalog, or `db/**` changes; `apps/api/package.json` untouched.
- **Deviations from plan:** none. The four plan-review confirmations (quadrant authoritative + superseding comment; unavailable arm omits `links`; file naming as proposed; delete shared `results.ts`/`results.test.ts` outright) and the pre-approved items (internal-only uniformity-message generalization, row-type reuse, `zz-judge-result-` prefix with explicit probe tracking, fallback built from the verified charge's slug) were applied exactly as directed.
- **Notes for next task (Phase 9/10):** Both result endpoints now share `result-helpers.ts` (UUID dispatch + distribution machinery) — new result-shaped endpoints should consume it, not copy it. The globalSetup seeds once per run: **new DB-backed suites must NOT self-seed** (reference or aggregates) — just keep a unique temp prefix, explicit tracking for any non-prefixed temp row, and the `skipIf(!DATABASE_URL)` guard; globalSetup failure fails the whole run by design. The unavailable arm's `fallback.chargeOnlyResultPath` is only ever emitted when the charge-only baseline exists — Phase 10's cross-cutting suites can rely on it never dead-ending. `SENTENCING_RESULT_UNAVAILABLE` remains unused (both endpoints use the in-band tagged union). Task 10.2 should move `CHARGE_RESULT_UNAVAILABLE_MESSAGE` (and siblings like `CHARGE_NOT_FOUND_MESSAGE`/`JUDGE_NOT_FOUND_MESSAGE`, currently duplicated across the two services) into `@pca/shared`.

## Task 9.1 — Public Definitions Endpoint

- **Date:** 2026-07-09
- **What was built:** `GET /api/v1/public/definitions` — outcome and sentencing category definitions served straight from the `@pca/taxonomy` generated artifact; no database dependency, static per deploy. **Shared contract** (new module `packages/shared/src/public/definitions.ts`, star-exported from the index): `definitionEntrySchema` `{ code, displayName, definition, sortOrder }` and `definitionsResponseSchema` `{ taxonomyVersion, outcomes, sentencing }`, both `additionalProperties: false` — the taxonomy's internal `public` flag is deliberately absent from the entry schema, so serialization strips it and validation rejects it. **API:** `apps/api/src/taxonomy.ts` refactored so a single `publicCategories()` filter (public-only, sorted by `sortOrder` ascending) feeds BOTH the existing `PRESENTATION` maps (`resolvePublicCategory` behavior unchanged; 8.1/8.2 suites passed untouched) and a new `PUBLIC_DEFINITIONS` export computed once at module load. New route `routes/public/definitions.ts` returns `{ taxonomyVersion: TAXONOMY_VERSION, ...PUBLIC_DEFINITIONS }` with the response schema attached (Ajv/fast-json-stringify serialization guard), registered in the public namespace plugin; no new error codes — unexpected failures fall through to the central handler as `INTERNAL_ERROR`. **Tests:** 7 endpoint tests (`routes/public/definitions.test.ts`) — every test injects a **poison-proxy DB** (any property access throws) via `buildApp({ db })`, so all pass regardless of `DATABASE_URL` and each 200 is proof the handler chain performs no database access; cover exact top-level keys, exact four-field entries (no `public` flag, no internal fields), public-set equality + non-public `unknown` absent from both arrays, ascending `sortOrder`, `taxonomyVersion === TAXONOMY_VERSION`, and a belt-and-braces forbidden-term check on the raw response body using **word-boundary regexes** (`predict*`, `odds`, `likelihood`, `probability`, `chance(s)`, `rank*`, `best`, `worst`, `recommend*`, `advice`, `guarantee*`, `win*`, `lose/loses/losing` — boundaries so "withdrew"/"losses" can never false-positive). 13 shared schema tests (`public/definitions.test.ts`): valid shapes, `public`-flag rejection at entry and nested-in-response level, per-field missing-required rejection, non-integer `sortOrder`, unknown top-level props. Verified: full workspace green — shared 96, api 112, db 6, taxonomy 14, web 2; lint, typecheck, `format:check` all pass.
- **Format fix on 4 out-of-scope files (accepted):** `apps/api/src/repositories/judge-result.ts`, `apps/api/src/routes/public/judge-results.test.ts`, `apps/api/src/services/judge-result.test.ts`, `packages/shared/src/public/judge-result.test.ts` were committed unformatted during the 8.x tasks (verified: `format:check` failed on a clean tree before this task's changes) and were formatted here with Prettier — pure line-wrapping, no code changes.
- **Files touched:** `packages/shared/src/public/definitions.ts` + `definitions.test.ts` (new); `packages/shared/src/index.ts`; `apps/api/src/taxonomy.ts`; `apps/api/src/routes/public/definitions.ts` + `definitions.test.ts` (new); `apps/api/src/routes/public/index.ts`; the 4 format-only files above; `tasks/worklog.md`.
- **Deviations from plan:** none from the approved plan (word-boundary forbidden-term matching applied as the required fix; test colocation per existing convention as confirmed). The 4-file format fix was disclosed at completion and accepted as part of this task.
- **Notes for next task (9.2 methodology/data coverage):** The poison-proxy pattern in `definitions.test.ts` is the reusable no-DB proof for any DB-free public endpoint. `PUBLIC_DEFINITIONS`/`TAXONOMY_VERSION` show the module-load-computed static-response pattern. Standing consolidation item (planning): the public-filter duplication between `apps/api/src/taxonomy.ts` and `@pca/shared`'s `categories.ts` (`publicOutcomeCategories`/`publicSentencingCategories`) is deferred to Sprint 7 when taxonomy moves to DB tables — do not consolidate before then.

## Task 9.2 — Methodology + Data Coverage Endpoints

- **Date:** 2026-07-09
- **What was built:** The final two Sprint 2 public endpoints. **`GET /api/v1/public/methodology`** — static, DB-independent, structured copy: shared contract (`packages/shared/src/public/methodology.ts`) pins ten required `{ heading, body }` sections (`dataSource`, `dataRange`, `whatResultsMean`, `notPrediction`, `notLegalAdvice`, `sampleSize`, `thinData`, `chargeLevelAnalytics`, `sentencing`, `limitations`) under a `sections` object, `additionalProperties: false` at every level, with `METHODOLOGY_SECTION_KEYS` exported as the single iterable key list (a shared test asserts it matches the schema exactly). Copy lives in a new content module `apps/api/src/content/methodology.ts` (module-load-computed, 9.1 static-response pattern); the route serializes through the response schema; every endpoint test injects the 9.1 poison-proxy DB, so all 8 pass with the database unreachable. **Plan fix 2 (required at plan review):** the allowed prediction/advice phrasings are enumerated ONLY in the named export `GUARDED_DISCLAIMER_PHRASES` on the content module — the copy-safety test strips those exact phrases case-insensitively, then applies the 9.1 word-boundary forbidden-term regexes, so unguarded predict/advice vocabulary still fails; the constant migrates mechanically to `@pca/shared` in task 10.2 with the other copy guards. **`GET /api/v1/public/data-coverage`** — tagged union (`packages/shared/src/public/data-coverage.ts`) per the Phase 8 precedent: common fields `jurisdiction`/`courtScope`/`plannedDataStart` schema-pinned as literals, `knownLimitations` (minItems 1), and `coverage` as available/unavailable arms; the unavailable arm carries ONLY `available: false` plus the pinned `DATA_COVERAGE_UNAVAILABLE_MESSAGE` — no run-derived fields by construction. The service reuses the 8.1 `findActivePublishedRun` resolver (criterion 4 — no second resolver); no active run is an HTTP-200 unavailable arm, never an error. New repository `apps/api/src/repositories/data-coverage.ts` runs three `COUNT(DISTINCT …)` queries scoped to the run id (charges with outcome aggregates, charges with sentencing aggregates, judge/charge pairs from `judge_outcome_aggregates` only — the 8.2 quadrant invariant makes it the authoritative pair set); queries run sequentially so a transaction connection can serve them; all tables were already in the `PublicApiDatabase` Pick (criterion 7, no changes). **Plan fix 1 (required at plan review):** `knownLimitations` (content module `apps/api/src/content/data-coverage.ts`) leads with an explicit seeded-data disclosure — all currently published figures are seeded demonstration data and do not describe real Philadelphia court outcomes. **Copy-review fix (required at verification):** the same disclosure, word-for-word, was appended to the methodology `limitations` body, because `dataSource`/`whatResultsMean` make present-tense UJS-docket claims that are untrue until real aggregates exist. **Both disclosure sites carry a code comment marking them for removal in Sprint 7** when real aggregates replace the seeds. **Tests:** 45 new shared schema tests (methodology 21: section shape, empty-string rejection, exact ten-key sync with `METHODOLOGY_SECTION_KEYS`, per-key missing-section rejection, unknown-key rejection; data-coverage 24: both arms, union disjointness incl. run-fields-on-unavailable-arm and message-on-available-arm rejection, literal pins for jurisdiction/courtScope/plannedDataStart/message, counts field/integer/negative/smuggled-list rejection, empty-limitations rejection). 8 methodology endpoint tests (poison-proxy on every test; exact ten sections with non-empty heading/body; content served verbatim; explicit not-a-prediction and not-legal-advice statements; UJS + 2025-01-01 event-date-anchor assertions; guarded-strip-then-regex forbidden terms; internal-detail substring sweep). 3 DB-backed data-coverage tests (no self-seeding, per the 8.2 globalSetup contract): available arm exact-body against hand-restated 6.4 seed values (dataStart 2025-01-01, dataEnd 2026-06-30, lastRefreshed 2026-07-01T02:00:00.000Z, run `5eedda7a-…0001`, counts 5/3/3) plus an independent predicate-resolved run-id match; unavailable arm via **uncommitted-transaction isolation (reusable pattern)** — `setupDb.startTransaction().execute()`, invalidate the active run inside the transaction (`invalidated_at` + `invalidated_reason` move together per the check constraint), `buildApp({ db: trx })` so the app under test reads the uncommitted state, assert the exact unavailable arm + all common fields, rollback in `finally`, then re-probe the main app to prove the shared seeded state survived; every response passes the forbidden-substring sweep (incl. `invalidat`), the word-boundary forbidden-term regexes, and a recursive allowed-key assertion (criteria 8/9). Verified: root lint / format:check / typecheck / test all exit 0 (shared 141, api 123, db 6, taxonomy 14, web 2; DB-backed suites executed, not skipped) and a live-server smoke test served both endpoints contract-exact. **CI conditional:** not applicable — `.github/workflows/ci.yml` already runs `pnpm format:check` (line 55); workflows untouched.
- **Files touched:** `packages/shared/src/public/methodology.ts` + `methodology.test.ts`, `packages/shared/src/public/data-coverage.ts` + `data-coverage.test.ts` (all new); `packages/shared/src/index.ts`; `packages/shared/src/test-support/fixtures.ts`; `apps/api/src/content/methodology.ts`, `apps/api/src/content/data-coverage.ts`, `apps/api/src/routes/public/methodology.ts` + `methodology.test.ts`, `apps/api/src/routes/public/data-coverage.ts` + `data-coverage.test.ts`, `apps/api/src/repositories/data-coverage.ts`, `apps/api/src/services/data-coverage.ts` (all new); `apps/api/src/routes/public/index.ts`; `tasks/worklog.md`. No dependency, migration, seed, catalog, or `db/**` changes.
- **Deviations from plan:** one, accepted — `packages/shared/src/test-support/fixtures.ts` gained `validMethodologyResponse` / `validDataCoverageAvailable` / `validDataCoverageUnavailable`, following the established shared-fixture convention (it was not on the plan's file list). The two plan-review fixes and the copy-review fix above were applied exactly as directed; everything else shipped as approved.
- **Notes for next task (10.x):** The uncommitted-transaction isolation technique in `data-coverage.test.ts` is the reusable way to test "state X absent" against the shared seeded database without mutating it — controlled transaction, inject `trx` via `buildApp({ db })`, rollback in `finally`. `GUARDED_DISCLAIMER_PHRASES` (apps/api content module) and `CHARGE_RESULT_UNAVAILABLE_MESSAGE` (8.1 service) are both queued for the 10.2 copy-constant migration to `@pca/shared`. The seeded-data disclosure lives in exactly two places — `DATA_COVERAGE_KNOWN_LIMITATIONS[0]` and the tail of the methodology `limitations` body — both commented for Sprint 7 removal. Sprint 3's web `/methodology` page should consume the new endpoint and drop its static copy (explicitly out of scope here).

## Task 10.1 — Public Forbidden-Field Test Suite

- **Date:** 2026-07-09
- **What was built:** The permanent privacy gate over the public API: every public GET endpoint is discovered from the live route table, probed across its response arms, and every response body deep-scanned for forbidden field names and forbidden value patterns. **Constants in `@pca/shared`** (`packages/shared/src/public/forbidden-fields.ts`, exported from the entry point): `FORBIDDEN_FIELD_STEMS` — **fourteen** normalized stems (the task's thirteen plus `sourceid`, a required plan-review fix closing the `sourceId` gap without blunting to a bare `source` stem, which would false-positive on legitimate keys like `dataSource` and force an allowlist the gate must not grow). **Conscious boundary, accepted at review:** only these exact stems are caught — exotic abbreviations of the same concepts (e.g. `srcKey`) pass the key check. `FORBIDDEN_VALUE_PATTERNS` — one UJS docket regex, `/\b(?:CP|MC)-\d{2}-[A-Za-z]{2}-\d{4,7}-\d{4}\b/i`; **Philadelphia-scoped by design** (CP = Common Pleas, MC = Municipal Court; magisterial MJ- dockets use a different format and don't exist in Philadelphia — a statewide expansion must ADD a pattern, never widen this one; comment in the module says so). Shared tests pin the stem list, normalization invariants, match/non-match sets, and a no-`g`-flag guard (stateful `lastIndex` would skip matches). **Checker** (`apps/api/src/test-support/forbidden-scan.ts`): deep-recursive walk of objects/arrays; keys normalized (lowercase, strip `_`/`-`) and failed on CONTAINS-stem; every string value tested against every pattern; returns `ForbiddenViolation[]` (jsonPath, kind, offender, matched rule — reusable later by web E2E) rather than throwing. **Discovery** (`apps/api/src/test-support/public-route-discovery.ts`): `onRoute` hook attached before `ready()` (plugin registration is deferred, so the root hook sees every route), filtered to GET + `/api/v1/public` prefix (drops HEAD twins, /health, admin); plus pure two-directional `checkProbeCoverage` (unprobed routes AND stale registry entries). **Main suite** (`apps/api/src/public-forbidden-fields.test.ts`): probe registry keyed by exact registered route pattern, 18 probes over the 7 routes covering success, thin-data (`criminal-trespass`; `simple-assault`+`judge-testina-placeholder`), 200-unavailable (`possession-controlled-substance` sentencing; `retail-theft`+`judge-fakename-example` judge), 404 CHARGE_NOT_FOUND / JUDGE_NOT_FOUND, and 400 validation arms on both search routes (central-error-handler output is scanned too); `expectedStatus` per probe catches arm drift; bodies scanned regardless of status; globalSetup-seeded targets only, zero inserts/deletes. Route-count assertion (7, commented as the anti-vacuous-pass tripwire), coverage checks both directions, and both deliberate-failure proofs (throwaway route on a local instance → reported unprobed; fabricated registry key → reported stale). **CI no-skip guard (required plan-review fix):** probe execution is `describe.skipIf(!hasDb)` for local runs, but a guard test that ALWAYS runs asserts `hasDb` whenever `process.env.CI` is set, with a message naming the gate and the workflow database service — a CI service-container misconfiguration now fails the run instead of silently skipping every probe. Verified by an actual `CI=1 DATABASE_URL=` run. **Checker self-tests** (`apps/api/src/test-support/forbidden-scan.test.ts`, 22): one poisoned key per stem (incl. `sourceId`/`source_id`), every value pattern, a ≥3-level nested-in-array case, camelCase+snake_case variants, clean realistic charge-only fixture (no false positive), non-object bodies, formatter output. **Overlapping-stem behavior (approved):** per-stem self-tests use `toContainEqual`, not exact equality, because overlapping stems legitimately double-report (e.g. `parsed_docket_id` matches `parseddocket` AND `docket`) — over-reporting is the safe direction. **Result: all 18 probe bodies passed — no real leak found.** Gates: web 2, taxonomy 14, db 6, shared 147, api 170; lint/typecheck/format:check exit 0; `apps/api` clean build with no test-support output in `dist/`.
- **Files touched:** `packages/shared/src/public/forbidden-fields.ts` + `forbidden-fields.test.ts` (new), `packages/shared/src/index.ts`; `apps/api/src/test-support/forbidden-scan.ts`, `forbidden-scan.test.ts`, `public-route-discovery.ts`, `apps/api/src/public-forbidden-fields.test.ts` (all new); `apps/api/tsconfig.build.json` (one-line `src/test-support/**` exclude); `tasks/worklog.md`. No endpoint, schema, seed, dependency, or workflow changes.
- **Deviations from plan:** two, both approved at review — files colocated under `src/` instead of the task's suggested `test/` dir (`tsconfig.json` includes only `src`; the build exclude is the consequence), and the `toContainEqual` overlapping-stem assertion above.
- **Notes for next task (10.2):** The gate checks STRUCTURE and IDENTIFIERS only — prose terms are 10.2's copy-safety suite (`GUARDED_DISCLAIMER_PHRASES` and `CHARGE_RESULT_UNAVAILABLE_MESSAGE` are still queued for the shared migration). When adding a public route: the suite fails until a `PROBE_REGISTRY` entry exists AND the route-count assertion (currently 7) is bumped — that diff is the review trail. `scanForForbidden`'s violation-list shape is deliberately importable for future web E2E reuse; only the constants live in `@pca/shared` for now. The residual key-check boundary (srcKey-style abbreviations) stands until a stem is added — widening existing stems remains off the table.

## Task 10.2 — Copy Safety Suite + Shared Constants Migration

- **Date:** 2026-07-09
- **What was built:** `@pca/shared` is now the single source of truth for public copy-safety rules. **New module** (`packages/shared/src/public/copy-safety.ts`, exported from the entry point): `FORBIDDEN_PUBLIC_TERMS` — ten terms, each a case-insensitive word-boundary `RegExp` (`odds`, predict stem, guarantee stem, `likely sentence`, `best judge`, `worst judge`, `judge score`, `win rate`, `harsher`, `more lenient`; `better`/`worse` deliberately absent); `GUARDED_DISCLAIMER_PHRASES` (six phrases, see reconciliation below); `scanPublicCopy(text)` → `{ term, index, context }[]` via the pinned mask-then-scan algorithm. **Masking design:** guarded phrases are replaced with **equal-length runs of spaces**, not removed — indexes stay true to the original text and masking one phrase can never launder adjacent text (the shared tests prove both properties). Exported patterns stay `/i`-only; the scanner builds fresh `gi` copies so consumers can `.test()` the constants without `lastIndex` state bugs. **Shared unit tests** (12): all mandated deliberate-failure probes plus every stem inflection, with an exhaustiveness check pinning the sample map to the term list. **STOP-report reconciliation (plan-review rulings):** the 4.1 web guard's substring semantics were REPLACED by word-boundary mask-then-scan; where its list was stronger than the original locked list, the stronger protection was kept — `guaranteed` was promoted to a guarantee STEM (guarantee/guarantees/guaranteed/guaranteeing), and `GUARDED_DISCLAIMER_PHRASES` became the UNION of the web allowlist and the 9.2 shared set (`not a prediction`, `not predictions`, `do not predict`, `does not predict`, `not legal advice`, `does not provide legal advice`). Verified zero outcome change on the actual tree before adoption. **Constants migration:** `CHARGE_RESULT_UNAVAILABLE_MESSAGE` + `CHARGE_NOT_FOUND_MESSAGE` → `packages/shared/src/public/charge-result.ts`; `JUDGE_NOT_FOUND_MESSAGE` → `judge-result.ts`; `GUARDED_DISCLAIMER_PHRASES` moved out of `apps/api/src/content/methodology.ts`; both API services and the methodology route test import from `@pca/shared`. **Endpoint-inventory extraction:** the 10.1 `PROBE_REGISTRY` + `PublicRouteProbe` moved verbatim to `apps/api/src/test-support/public-route-probes.ts`, imported by BOTH the 10.1 forbidden-field suite and the new 10.2 copy-safety suite — 10.1's discovery/coverage assertions (route count 7, two-directional unprobed/stale checks) continue to police the now-shared registry, so the two gates cannot drift to different endpoint lists. **API suite** (`apps/api/src/public-copy-safety.test.ts`, 24 tests): static scans of `METHODOLOGY_CONTENT`, `DATA_COVERAGE_KNOWN_LIMITATIONS`, all six pinned message literals, and `PUBLIC_DEFINITIONS` (the public-filtered `@pca/taxonomy` projection); live `fastify.inject` scans of every string value (recursive JSON walk) in all 18 probe arms across the 7 public routes; a poisoned-payload probe routed through the exact collect-and-scan path proves the mechanism flags violations and leaves clean strings alone; same `skipIf(!hasDb)` + always-run CI-gate-integrity test as 10.1. **Web guard migration:** `apps/web/test/copy-terms.ts` deleted; `copy-guard.test.ts` keeps file walking + whitespace-collapse as file-level preprocessing and delegates all matching to shared `scanPublicCopy`; `@pca/shared` added as a workspace devDependency of `apps/web` (approved). **Required fix applied:** the methodology route test now runs canonical terms through `scanPublicCopy` and retains only ten route-specific stricter patterns (likelihood, probability, chances, rank, bare best/worst/win, recommend, advice, lose) in a local array explicitly commented as deliberate additions beyond the shared scanner; its predict/odds/guarantee patterns were removed as locked-list duplicates. **Result: zero copy violations found in existing public copy** — every static source and every live response arm scanned clean; nothing escalated under the violation protocol. Gates: shared 159, api 194 (live probes executed against seeded Postgres), web 2, db 6, taxonomy 14, pytest 31; lint/format:check/typecheck/taxonomy:validate all green. AC5 grep evidence: no message-literal duplicates, no term-list definitions, and no `GUARDED_DISCLAIMER_PHRASES` definition anywhere in `apps/`.
- **Files touched:** `packages/shared/src/public/copy-safety.ts` + `copy-safety.test.ts` (new), `packages/shared/src/index.ts`, `packages/shared/src/public/charge-result.ts`, `packages/shared/src/public/judge-result.ts`; `apps/api/src/test-support/public-route-probes.ts`, `apps/api/src/public-copy-safety.test.ts` (new), `apps/api/src/public-forbidden-fields.test.ts`, `apps/api/src/content/methodology.ts`, `apps/api/src/routes/public/methodology.test.ts`, `apps/api/src/services/charge-result.ts`, `apps/api/src/services/judge-result.ts`; `apps/web/test/copy-guard.test.ts`, `apps/web/test/copy-terms.ts` (deleted), `apps/web/package.json`, `pnpm-lock.yaml`; `tasks/worklog.md`.
- **Deviations from plan:** none beyond the plan-review rulings themselves (guarantee stem, phrase union, not-found-message migration, methodology-test rework — all ruled before implementation). `apps/web/package.json` + lockfile were the only files outside the task's files-in-scope list, pre-approved as Ruling 3.
- **Notes for next task:** All public prose is now gated twice: 10.1 (structure/identifiers) and 10.2 (copy terms), both walking the SAME `PROBE_REGISTRY` — a new public route fails BOTH suites until a registry entry exists and 10.1's route count (7) is bumped. Any new public copy (content modules, error messages, taxonomy definitions) is scanned automatically if it flows through a registered route or one of the imported static sources; a new static content module must be added to the 10.2 static-source tests by hand. The web guard's whitespace collapse is FILE-level preprocessing — `scanPublicCopy` itself deliberately does not match multi-word terms across newlines (pinned single-space discipline), so any new consumer scanning multi-line sources must collapse first. `better`/`worse` remain outside the mechanical list by design; bare `best`/`worst`/`win` are enforced only in the methodology route test's stricter local extras.

## Chore — API dev script loads root .env

- **Date:** 2026-07-09
- **What was built:** `apps/api` `dev` script now runs `tsx watch --env-file-if-exists=../../.env src/server.ts` and `start` runs `node --env-file-if-exists=../../.env dist/server.js`, matching the `@pca/db` scripts' env-loading so local dev needs no shell exports — `cp .env.example .env` at the repo root is enough. Per Ruling 1, engines were tightened to `>=22.11` (Node 22 LTS floor, where `--env-file-if-exists` is universally supported) in `apps/api`, the root `package.json`, `packages/shared`, `packages/taxonomy`, `apps/web`, and `db` (db said `>=22.9`, tightened under the same rationale and flagged in the report). Per Ruling 2, `apps/api/README.md` got a factual refresh: "shell only / no database" framing removed, API described as DB-backed with public aggregate endpoints, `DATABASE_URL` added to the env table, auto-loading + shell-precedence behavior documented. Verified: (1) with nothing exported and a root `.env`, dev serves `GET /api/v1/public/charges/search?q=retail` → 200 with results; (2) shell precedence proven empirically — a bogus exported `DATABASE_URL` produced a 500 (generic body, no leak) over a valid `.env`, a valid exported value worked; (3) `start` env-loading verified in isolation only (see below). All gates green: lint, format:check, typecheck, full JS suites (194 api tests incl. live DB probes), pytest 31.
- **Files touched:** `apps/api/package.json`, `apps/api/README.md`, `package.json`, `packages/shared/package.json`, `packages/taxonomy/package.json`, `apps/web/package.json`, `db/package.json`, `tasks/worklog.md`. Commit `baf828f`.
- **Deviations from plan:** none beyond the two pre-approved rulings; the `db` engines value (`>=22.9` → `>=22.11`) was a judgment call within Ruling 1's rationale, flagged at report time.
- **Notes for next task:** PRE-EXISTING BUG (out of scope here, unrelated to env loading): `pnpm --filter @pca/api start` cannot boot — `@pca/shared`'s `main` points at TS source (`./src/index.ts`), which plain `node` can't resolve (`ERR_MODULE_NOT_FOUND` for `errors.js`); reproduced identically pre-change. The env flag on `start` is correct and ready for whenever workspace-dep builds make `start` runnable. Env-flag paths are cwd-relative to each package (`../../.env` from `apps/api`, `../.env` from `db`) — a package at a different depth needs a different path. Two stale local dev servers holding ports 3001/3199 were killed during verification (user-approved).

## Task 11.1 — Workspace Package Build + Runtime Fix

- **Date:** 2026-07-09
- **What was built:** Per-package `dist` builds (tsc emit) + conditional `exports`
  maps for `@pca/shared`, `@pca/taxonomy`, `@pca/db`, killing the plain-node
  `start` failure documented at the end of the previous chore entry. Each package
  gained a `tsconfig.build.json` (declaration + declarationMap + sourceMap,
  emit-only, published surface only) and an exports map of shape
  `{ types: dist/*.d.ts, "pca-source": <source>, default: dist/*.js }`.
  Plain node / `next build` / consumer typecheck resolve `default`/`types` → dist;
  vitest + tsx opt into `pca-source` → TS source.
- **Mechanism chosen & the naming gotcha:** the source condition is named
  `pca-source`, NOT `development`. Next.js auto-injects `development` in dev mode,
  so a `development` source condition made `next dev` resolve `@pca/shared` to
  `src/index.ts` and fail on its `.js`-extension re-exports (Turbopack won't map
  `.js`→`.ts` for a non-transpiled external; transpilePackages is rejected).
  Namespacing to `pca-source` makes `next dev` fall through to `default`→dist,
  matching `next build`; only tsx (`--conditions pca-source`) and vitest opt in.
- **Exact Vitest knob:** per config —
  `resolve.conditions: ['pca-source']`,
  `ssr.resolve.conditions: ['pca-source','module','node']`,
  `test.server.deps.inline: [/@pca\//]`.
  The `ssr.resolve.conditions` line is load-bearing: Vitest resolves inlined
  package *entries* through the SSR resolver, so top-level `resolve.conditions`
  alone resolved to dist. Applied in `packages/shared`, `db`, `apps/api` vitest
  configs. `@pca/taxonomy` has no vitest config and no workspace deps → exempt.
  `--conditions pca-source` on all boundary-crossing tsx calls: api `dev`, db
  `migrate:*`, db `seed`.
- **Per-package:** shared → `dist/index.js` (rootDir src, tests/test-support
  excluded); taxonomy → build = `tsx src/generate.ts && tsc` so gitignored
  `generated/index.ts` exists before emit (taxonomy.json is inlined, not a runtime
  artifact); db → rootDir `.`, `include: ["src/index.ts"]` so tsc emits exactly the
  published closure (`dist/src/{index,types}.js` + `dist/seeds/*.js`), verified NOT
  to pull migrations/connection/migrate/run.ts.
- **Root ordering:** new `build:packages` (topological via pnpm filters, taxonomy
  first); `typecheck` now `build:packages && tsc && pnpm -r typecheck` (consumers
  read dist `.d.ts`); `test` unchanged (source-resolved, no dist needed). Fresh
  clone proven by wiping `dist/` + `generated/` and running the full pipeline.
- **CI:** added `Build workspace packages` + a plain-node runtime smoke
  (`node --input-type=module -e "await import(...×3)"` from apps/api, no
  `--conditions`) before Lint — because tests resolve source, this is the only
  thing executing dist until the Sprint 3 E2E job, so exports/emit regressions
  fail here instead of shipping silently.
- **Files touched:** new `packages/{shared,taxonomy}/tsconfig.build.json`,
  `db/tsconfig.build.json`, `apps/web/app/import-proof/page.tsx`; modified
  `packages/{shared,taxonomy}/package.json` + `db/package.json` (exports/build),
  `packages/shared/vitest.config.ts`, `db/vitest.config.ts`,
  `apps/api/{package.json,vitest.config.ts}`, root `package.json`,
  `.github/workflows/ci.yml`. No package source logic changed; no public API,
  schema, seed, or endpoint change. dist/ already gitignored.
- **Deviations:** (1) source condition `development`→`pca-source` (Next collision,
  above); (2) `apps/api/vitest.config.ts` already existed — modified, not created.
- **Notes for 11.2 / 11.3:**
  - DELETE `apps/web/app/import-proof/page.tsx` when 11.2 lands the real API client
    module — it exists only to prove a `@pca/shared` value import survives
    `next build`.
  - **Stale-dist tradeoff:** consumer typecheck AND editor intellisense resolve
    `dist/*.d.ts`, so after editing a package's source, editors/`tsc` may lag until
    `pnpm run build:packages` reruns; declarationMap softens go-to-def but not the
    staleness. Tests/tsx are unaffected (they use `pca-source`→source). `next dev`
    /`next build` resolve dist, so web work needs `build:packages` first.
  - Adding a new package export subpath means extending its exports map with the
    same `{types, pca-source, default}` triple.

## Task 11.2 — Rewrites Proxy + Public API Client + Error Message Constants

- **Date:** 2026-07-09
- **What was built:** `apps/web`'s data layer. **(1) Rewrites proxy**
  (`apps/web/next.config.ts`): `async rewrites()` maps `/api/v1/public/:path*` →
  `${API_BASE_URL}/api/v1/public/:path*`, keeping browser calls same-origin (no
  CORS). `API_BASE_URL` is read server-side only (no `NEXT_PUBLIC_` prefix, so it
  never enters a client bundle). The `?? 'http://localhost:3001'` fallback is a
  LOCAL-DEV DEFAULT ONLY, commented as such in both `next.config.ts` and
  `apps/web/.env.example`; CI `next build` relies on it, and production wiring
  that removes the reliance is Sprint 9 scope. **(2) Message constants**
  (`packages/shared/src/public/error-messages.ts`, barrel-exported from
  `src/index.ts` — no new export subpath): `PUBLIC_ERROR_MESSAGES:
  Record<PublicErrorCode, string>` covering exactly the nine catalog codes, plus
  `FETCH_FAILURE_MESSAGE`. Five codes reference the already-pinned 8.1/8.2
  literals **by identity** (`CHARGE_NOT_FOUND`→`CHARGE_NOT_FOUND_MESSAGE`,
  `JUDGE_NOT_FOUND`→`JUDGE_NOT_FOUND_MESSAGE`,
  `CHARGE_RESULT_UNAVAILABLE`→`CHARGE_RESULT_UNAVAILABLE_MESSAGE`,
  `JUDGE_SPECIFIC_RESULT_UNAVAILABLE`→`JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE` (the
  pinned 8.2 literal, never re-typed),
  `SENTENCING_RESULT_UNAVAILABLE`→`CHARGE_SENTENCING_UNAVAILABLE_MESSAGE`); four
  are authored here. The `Record<PublicErrorCode, string>` annotation makes a
  tenth code without a message a compile error; a shared test also pins key-set
  equality at runtime. **Exact final strings** — INVALID_REQUEST: "That request
  wasn't valid. Please check your input and try again." · NOT_FOUND: "We couldn't
  find that page or resource." · CHARGE_NOT_FOUND: "No charge matches the
  requested identifier." · JUDGE_NOT_FOUND: "No judge matches the requested
  identifier." · CHARGE_RESULT_UNAVAILABLE: "Results are not available for this
  charge yet." · JUDGE_SPECIFIC_RESULT_UNAVAILABLE: "No judge-specific aggregate
  is available for this charge and judge yet. Philadelphia-wide historical data
  for this charge is still available." · SENTENCING_RESULT_UNAVAILABLE:
  "Historical sentencing data is not available for this charge yet." ·
  RATE_LIMITED: "You've made too many requests. Please wait a moment and try
  again." · INTERNAL_ERROR: "Something went wrong on our end. Please try again
  later." · FETCH_FAILURE_MESSAGE: "We couldn't reach the server. Please check
  your connection and try again." **(3) Typed client**
  (`apps/web/app/lib/public-api-client.ts`): seven functions — `searchCharges`,
  `searchJudges`, `getChargeResult`, `getJudgeSpecificResult`, `getDefinitions`,
  `getMethodology`, `getDataCoverage` — each returning the pinned tagged union
  `{ ok: true; data: T } | { ok: false; error: PublicApiFailure }`, never throwing
  for API errors or transport failures. `PublicApiFailure` is
  `{ kind: 'api_error', …five flat fields incl. requestId }` for a well-formed
  error envelope (validated via `isPublicErrorCode` + field-type checks) or
  `{ kind: 'fetch_failed' }` for network failure, non-JSON body, or malformed
  error payload. Success bodies are trusted against the `@pca/shared` response
  types (no runtime revalidation); the 200 unavailable arms return as `ok:true`
  data. Base URL: pure `resolvePublicApiUrl(path, { isServer, apiBaseUrl })` —
  server prefixes the absolute base (throws on missing, caught → fetch_failed);
  browser returns the relative path for the rewrite. Context detected via
  `typeof window === 'undefined'`. **(4)** Deleted `apps/web/app/import-proof/`
  (the 11.1 packaging proof; no separate test existed). Packaging stays exercised
  via the client's `@pca/shared` value import + `next build`.
- **Copy-safety coverage:** `FETCH_FAILURE_MESSAGE` and all nine
  `PUBLIC_ERROR_MESSAGES` values were added to the 10.2 suite's scanned
  `PINNED_PUBLIC_MESSAGES` set (`apps/api/src/public-copy-safety.test.ts`), so
  every web-facing string is scanned at definition. The shared
  `error-messages.test.ts` also asserts every value (incl. the fetch-failure
  message) scans clean, plus by-identity references and key-set equality.
- **How to verify:** `pnpm run build:packages` (required after the `@pca/shared`
  edit and before web work), then `pnpm -r run test`, `pnpm run lint`,
  `pnpm run format:check`, `pnpm run typecheck`, `pnpm --filter @pca/web run build`.
- **Acceptance criteria:** all met. Rewrite + `.env.example` + no-`NEXT_PUBLIC_`
  grep test (matches actual `process.env.NEXT_PUBLIC_` refs, not prose; scans
  shippable non-test `app/` files) ✓; seven typed functions, no throw on error or
  network failure ✓; api_error preserves all five flat fields incl. requestId ✓;
  three distinct fetch_failed tests (network / non-JSON / malformed) ✓; key-set
  equality test ✓; JUDGE_SPECIFIC identity-by-import test ✓; new constants scanned
  by the 10.2 suite + shared scan-clean test ✓; no forbidden/prediction/legal
  vocabulary ✓; both base-URL branches unit-tested (incl. server-missing-base
  throw) ✓; import-proof deleted + `next build` green ✓; all gates green — web 16,
  shared 167, api 194, taxonomy 14, db 6; lint/format:check/typecheck 0 errors;
  `next build` compiles 7 routes, no import-proof route. No CI change required.
- **Files touched:** `packages/shared/src/public/error-messages.ts` +
  `error-messages.test.ts` (new), `packages/shared/src/index.ts`;
  `apps/web/app/lib/public-api-client.ts` + `public-api-client.test.ts` (new),
  `apps/web/next.config.ts`, `apps/web/.env.example` (new),
  `apps/web/app/import-proof/page.tsx` (deleted);
  `apps/api/src/public-copy-safety.test.ts` (extended scan set); `tasks/worklog.md`.
  No new dependencies, no export-subpath/`package.json` change, no endpoint/schema
  change.
- **Deviations from plan:** none. Ambiguity resolved at approval (reference the
  five existing pinned literals, author four fresh + fetch-failure). Two
  approved-fix follow-throughs baked in: FETCH_FAILURE_MESSAGE included in the
  scanned set + its own scan-clean assertion; local-dev-default comments in both
  `next.config.ts` and `.env.example`.
- **Notes for next task (Phases 12–14):** the client returns structured failures
  only — mapping a `PublicApiFailure` to user copy via `PUBLIC_ERROR_MESSAGES`
  (api_error → `PUBLIC_ERROR_MESSAGES[error.code]`, fetch_failed →
  `FETCH_FAILURE_MESSAGE`) is the consuming component's job, deliberately not
  wired here. The API's own `message` still rides along on api_error for support
  use; `requestId` too. Any new public route needs a client function AND, if it
  adds a new error code, the `Record<PublicErrorCode, string>` completeness check
  will fail until a message is added. The web copy-guard scans ALL `.ts`/`.tsx`
  under `app/` including test files, so avoid forbidden vocabulary (`guarantee`,
  `predict`, `odds`, …) even in test comments/fixtures.

## Task 11.3 — Tailwind v4 Styling Foundation

- **Date:** 2026-07-09
- **What was built:** Tailwind CSS v4 (CSS-first) installed and wired into
  `apps/web`, the 4.1 design tokens migrated into Tailwind's `@theme`, and the
  layout shell (header/nav/main/footer) restyled with plain Tailwind utilities
  on the unchanged semantic HTML, plus a minimal base heading hierarchy (h1–h6)
  in the base layer to counter preflight's heading reset. No component UI
  library; no dark mode; no page or copy changes.
- **Integration mechanism:** `tailwindcss@4.3.2` + `@tailwindcss/postcss@4.3.2`
  as `apps/web` devDependencies; new `apps/web/postcss.config.mjs`
  (`{ plugins: { '@tailwindcss/postcss': {} } }`); `globals.css` starts with
  `@import 'tailwindcss';`. Next 16 reads the PostCSS config under BOTH `next dev`
  (Turbopack) and `next build` — no `next.config.ts` change needed. Verified:
  `next build` compiled 8 routes cleanly under Turbopack, and `next dev`
  (Turbopack) served the styled homepage with all generated utilities present in
  the emitted CSS.
- **allowBuilds:** added `'@tailwindcss/oxide': true` to the existing
  `allowBuilds:` MAP in `pnpm-workspace.yaml` (Tailwind v4's native Rust engine;
  its install step needs approval to run). This is the ONLY addition. `sharp`
  stays `false`; `esbuild: true` / `unrs-resolver: false` unchanged. `pnpm
  install` reported no other blocked build scripts. NOTE for future tasks: the
  approved-plan wording originally said "onlyBuiltDependencies list" but the repo
  actually manages these as an `allowBuilds` map (pnpm 11.10 honors it — esbuild's
  binary builds); the human confirmed the map is controlling and the `false`
  entries are deliberate-denial documentation to preserve. Do NOT convert to
  `onlyBuiltDependencies`. On darwin-arm64 the oxide native binary is delivered by
  the prebuilt optional dep `@tailwindcss/oxide-darwin-arm64` (a shipped `.node`),
  not compiled locally; the allowBuilds entry still governs oxide's own install
  script.
- **Token rename map (old `:root` custom prop → `@theme` token → generated
  utility).** Values preserved EXACTLY from 4.1; renames are only so the
  generated utility reads naturally (`text-text` would be awkward). Phase 12–14
  should use the NEW names:

  | 4.1 token | value | `@theme` token | utility |
  | --- | --- | --- | --- |
  | `--color-text` | `#1f2733` | `--color-ink` | `text-ink` |
  | `--color-text-muted` | `#5b6572` | `--color-muted` | `text-muted` |
  | `--color-background` | `#ffffff` | `--color-canvas` | `bg-canvas` |
  | `--color-surface` | `#f5f6f8` | `--color-surface` | `bg-surface` (name unchanged) |
  | `--color-border` | `#d9dde3` | `--color-line` | `border-line` |
  | `--color-link` | `#1d4ed8` | `--color-accent` | `text-accent` |
  | `--max-content-width` | `44rem` | `--container-content` | `max-w-content` |

  Accent `#1d4ed8` kept exactly as-is per standing decision — palette tuning is
  deferred to 15.1 against real pages, not done as a side effect here.
- **globals.css** now contains only: the Tailwind import, the `@theme` block, and
  a minimal base layer: body defaults (font stack, line-height, ink color,
  canvas background, flex column, min-height), the global `a:focus-visible`
  outline, and an `@layer base` heading hierarchy (h1 1.75rem, h2 1.375rem,
  h3 1.125rem, all 600-weight with restrained margins; h4–h6 inherit body size
  but stay semibold). No page-specific styles, no dead/duplicate token defs.
- **Shell restyle (`layout.tsx`, className-only):** surface-tinted header/footer
  with `border-line` hairline dividers, a centered `max-w-content` reading column
  (`mx-auto … px-6 py-8`), `text-lg font-semibold` site name, a flex-wrap nav,
  and `text-accent` links with `hover:underline` + an explicit
  `focus-visible:outline` ring (belt-and-suspenders over the global
  `a:focus-visible`). Landmarks, headings, nav `aria-label`, and list structure
  are byte-for-byte identical in shape — only `className` values changed.
- **Stale-reference sweep (required):** grep across `apps/web`
  (`.ts/.tsx/.css/.md/.json`, excl. `node_modules`/`.next`) for every removed
  identifier — `--color-text`, `--color-text-muted`, `--color-background`,
  `--color-border`, `--color-link`, `--max-content-width`, and the `.site-*`
  class prefix — returned ZERO real references. The one grep hit was the word
  `site-wide` inside an existing code comment (substring false positive from the
  `site-` pattern), not a class reference. Renamed tokens fail silently as
  unstyled elements, so this was proven, not assumed.
- **How to verify:** `pnpm run build:packages` (still required before web work
  that resolves `@pca/*` dist), then `pnpm --filter @pca/web run build`,
  `pnpm --filter @pca/web run typecheck`, `pnpm lint`, `pnpm format:check`, and
  the full `pnpm test`. `next dev -p <port>` renders the styled shell.
- **Gates — all green:** `next build` 8 routes clean (Turbopack); typecheck 0
  errors; lint 0; format:check clean; full workspace tests pass (web 16, api 194,
  shared 163, taxonomy 14, db 6). Copy-guard passed UNCHANGED — no copy added,
  removed, or edited.
- **Files touched:** `pnpm-workspace.yaml` (one allowBuilds line),
  `apps/web/package.json` (two devDeps), `apps/web/postcss.config.mjs` (new),
  `apps/web/app/globals.css` (rewritten), `apps/web/app/layout.tsx`
  (className-only), `pnpm-lock.yaml` (install), `tasks/worklog.md`. No CI change
  (see gap below). No page, route, component, or copy change.
- **Deviations from plan:** one human-directed addition after initial review —
  base heading styles (`@layer base` h1–h6) added to `globals.css` beyond the
  originally-approved "body defaults + a:focus-visible" base layer, to prevent a
  visual regression from preflight's heading reset (Sprint 3 acceptance: no
  visual regression to shell pages beyond intended restyling). One approval-time
  clarification: the allowBuilds mechanism is the `allowBuilds` map, not an
  `onlyBuiltDependencies` list (see above).
- **Notes for next task (Phases 12–14):**
  - **CI gap (important):** CI does NOT run `next build` — `ci.yml` only runs
    lint/typecheck/format/test on the Node job, so a Tailwind/PostCSS or web-build
    regression would NOT be caught by CI today. It was verified locally here. This
    gap closes at **task 15.2**, when the E2E job boots web via a production build;
    15.2's spec inherits the requirement to exercise `next build` in CI.
  - **Tailwind v4 preflight flattens headings — MITIGATED with base heading
    styles in 11.3.** Preflight resets `h1–h6` to `font-size/weight: inherit`,
    which would render existing shell-page headings (methodology, definitions,
    about, home) at body size. 11.3 adds an `@layer base` heading hierarchy in
    `globals.css` (h1 1.75rem / h2 1.375rem / h3 1.125rem, all 600; h4–h6 inherit
    size but stay semibold) so the base state is correct rather than broken.
    Because it lives in `@layer base` (which precedes `@layer utilities`), Phase
    12–14 pages remain free to override any heading with utility classes.
  - Tokens are consumed as utilities (`bg-surface`, `text-ink`, `max-w-content`,
    …); the raw `--color-*` / `--container-content` CSS vars also exist for
    arbitrary values if ever needed. Use the new names (table above).
  - No `tailwind.config.*` file exists (CSS-first): all theme config lives in
    `globals.css` `@theme`. Add future tokens there.

## Task 11.4 — Shared Frontend Formatting Utilities

- **Date:** 2026-07-09
- **What was built:** the pure display-formatting module that every Sprint 3
  result and content page will render metadata through — counts, percentages,
  sample-size labels, date ranges, last-refreshed timestamps, result-type
  labels, and thin-data labels. `Intl`-only, no React, no new dependencies, no
  analytics. Closes Phase 11.
- **Files touched:** `apps/web/app/lib/formatters.ts` (new),
  `apps/web/app/lib/formatters.test.ts` (new), `tasks/worklog.md`. Nothing else.
- **API surface:** `formatCount`, `formatPercentage`, `formatSampleSize`,
  `formatDateRange`, `formatLastRefreshed`, `formatResultTypeLabel`,
  `formatThinDataLabel`, plus exported label constants
  (`SAMPLE_SIZE_LABEL_PREFIX`, `RESULT_TYPE_CHARGE_ONLY_LABEL`,
  `RESULT_TYPE_JUDGE_SPECIFIC_LABEL`, `THIN_DATA_LABEL`).
- **Evidence pinned in the plan (contract facts 13.1 inherits):**
  - **Percentage scale is 0–100**, not 0–1 —
    `common.ts` `percentage: Type.Number({ minimum: 0, maximum: 100 })`, seed
    `percentageOf` returns a `.toFixed(2)` 0–100 value, fixtures use `100 / n`.
    The formatter renders the wire value directly and does NO count/sample-size
    arithmetic (locked decision 2 / AC3).
  - **`lastRefreshed` wire format is `date-time`** (RFC 3339 instant) on both
    the charge-only and judge-specific success responses. Rendered in **UTC with
    an explicit `UTC` suffix** (e.g. `January 5, 2026 at 2:30 PM UTC`) so output
    is deterministic and host-timezone-independent.
  - **Thin-data is a plain `boolean`** (`thinDataStatusSchema = Type.Boolean()`),
    one `thinData` flag per distribution block — no reason enum exists. Label
    maps `true` → `"Based on a small sample."`, `false` → `null`. No invented
    categories (AC6).
  - **Result-type union has no single named export.** The labeller's parameter
    is derived from the shared contracts —
    `ChargeOnlyResultResponse['resultType'] | JudgeSpecificResultSuccess['resultType']`
    (= `charge_only | judge_specific`) — with a `never`-assertion default arm, so
    a new labelable result type fails typecheck rather than mislabeling (locked
    decision 4 / AC5). `judge_specific_unavailable` is deliberately excluded — it
    is a fallback state, not a labelable result.
- **Timezone safety (locked decision 3 / AC4):** date-only `YYYY-MM-DD` values
  are parsed via a guarded regex into calendar parts, rebuilt with `Date.UTC`,
  and rendered by a `timeZone:'UTC'`-pinned formatter. The naive
  `new Date("2025-01-01")` UTC-midnight shift is never used. Load-bearing proof
  is the direct assertion that Jan 1 renders as "January 1". A **supplementary**
  `process.env.TZ='Pacific/Kiritimati'` (UTC+14) assertion is included and
  **passes** — kept, not dropped; it was not flaky on this platform (per the
  approval clarification, it is supplementary to the UTC-construction proof).
- **Locale:** every `Intl` call pins `en-US` via a single `LOCALE` constant
  (AC7). All label strings live under `app/` and are additionally asserted clean
  by `scanPublicCopy` inside the module's own tests (AC9); the `app/**` copy
  guard also covers them.
- **Deviations from plan (all from the approved review fixes):**
  - Sample-size label is **noun-free** — `"Sample size: 1,234"`, not
    `"1,234 cases"` (sample sizes are charge-level; one docket carries multiple
    charges). No singular/plural logic; the `n = 1` test exists only to lock the
    format.
  - Thin-data label is the unit-free `"Based on a small sample."`.
  - Every formatted percentage carries `%`, including `0 → "0%"` and
    `100 → "100%"`.
- **How to verify:** `pnpm run build:packages` (prereq for `@pca/*` dist), then
  from root `pnpm typecheck`, `pnpm lint`, `pnpm format:check`, `pnpm test`.
- **Gates — all green:** typecheck 0 errors; lint 0; format:check clean; full
  workspace tests pass (web 33 incl. 17 new formatter tests, api 194, shared 163,
  taxonomy 14). Copy guard green.
- **Notes for next task (13.1):** consume these formatters for all metadata
  rendering; do not re-implement. `formatThinDataLabel` returns `null` when the
  flag is unset — render nothing in that case. `formatDateRange`/
  `formatLastRefreshed` do NOT guard missing fields because `start`, `end`, and
  `lastRefreshed` are all required by the shared types (intentional, noted in
  code); if a future contract makes one optional, add fallback then.

## Task 12.1 — Homepage Search Layout

- **Date:** 2026-07-09
- **What was built:** The public homepage (`/`) rebuilt as the site's search
  surface — layout and copy only, no functional search (pinned decisions 1–2).
  New `apps/web/app/components/SearchForm.tsx` is a server component (no
  `'use client'`, no state, no handlers): a `<form noValidate>` (no `action`,
  no submit wiring) with two regions — a visually **primary** charge region
  (larger, `bg-surface` card, `text-lg` label) and a visually **secondary**,
  optional judge region whose visible label reads "Judge (optional)". Both
  inputs are **disabled** presentational placeholders — disabled inputs cannot
  be focused or submitted, so Enter never navigates (this is why disabled was
  chosen over focusable readOnly). Each region carries an explicit
  `{/* MOUNT: task 12.2/12.3 replaces this disabled placeholder ... */}`
  comment; only the `<input>` swaps in 12.2/12.3 — label + wrapper + styling
  stay, so the swap needs no layout rework. Labels are associated via
  `htmlFor`/`id` (`charge-search`, `judge-search`) with `aria-describedby` help
  text. An `sr-only` `<h2 id="search-heading">` gives the form section a
  heading in hierarchy while keeping the single visible `<h1>` in `page.tsx`.
  `page.tsx` now renders framing intro, `<SearchForm />`, the
  historical/not-a-prediction/not-legal-advice disclaimer, and Methodology
  (`/methodology`) + Data Coverage (`/data-coverage`) links (shell
  focus-visible pattern reused).
- **Copy constants:** all user-facing homepage copy — including input
  placeholder text — lives in `apps/web/app/components/home-copy.ts` as the
  `HOME_COPY` object (pinned decision 4). No inline JSX user-facing string
  literals in `page.tsx`/`SearchForm.tsx` (only punctuation glue: `·`, `()`).
- **Disclaimer sourcing (approved adjustment 3):** checked `@pca/shared` — it
  exposes **no pinned disclaimer literal** suitable for rendering
  (`methodology.notPrediction` is a served-content schema section;
  `GUARDED_DISCLAIMER_PHRASES` are scanner guards, not prose). Per the
  adjustment, wrote the framing copy fresh in `home-copy.ts`, deliberately
  using the exact guarded phrases "not a prediction" and "not legal advice" so
  it passes `scanPublicCopy`.
- **Test added:** `apps/web/test/home-copy.test.ts` asserts every `HOME_COPY`
  value passes `scanPublicCopy` from `@pca/shared` directly (AC5). The existing
  `app/**` copy-guard walker also covers `home-copy.ts` automatically.
- **Files touched:** `apps/web/app/page.tsx` (modified);
  `apps/web/app/components/home-copy.ts`,
  `apps/web/app/components/SearchForm.tsx`,
  `apps/web/test/home-copy.test.ts` (new). `globals.css` untouched — Tailwind
  utilities on the 11.3 tokens sufficed.
- **Deviations from plan:** none.
- **How to verify:** `pnpm run build:packages`, then from root
  `pnpm lint`, `pnpm format:check`, `pnpm typecheck`, `pnpm test`; and
  `pnpm --filter @pca/web build` + `start` (route `/` prerenders static).
- **Gates — all green:** lint 0; format:check clean; typecheck 0; full
  workspace tests pass (web 34 incl. 1 new home-copy test, api 194).
  `next build` succeeds — `/` is a static route. Rendered HTML verified: exactly
  one `<h1>`, two disabled inputs, both labels `for=`-associated with described-by
  help, "Judge (optional)" present, both content links routed.
- **Notes for next task (12.2/12.3):** replace the disabled `#charge-search` /
  `#judge-search` placeholders with the client `ChargeSearchInput` /
  `JudgeSearchInput`; keep the `id` and `aria-describedby` wiring; the region
  wrappers and labels are the stable layout — do not restructure them. Add
  testing-library/jsdom in 12.2.

## Task 12.2 — Charge Autocomplete

- **Date:** 2026-07-09
- **What was built:** The disabled `#charge-search` placeholder is replaced by a
  functional, accessible, debounced WAI-ARIA charge combobox, and charge-only
  form submission now routes to `/charges/[chargeSlug]`. This task also stands
  up the web component-render test setup (jsdom + testing-library).
  - **`apps/web/app/components/ChargeSearchInput.tsx`** (new client component):
    `role="combobox"` input with `aria-expanded`/`aria-controls`/
    `aria-activedescendant`/`aria-autocomplete="list"`, a `role="listbox"` of
    `role="option"` suggestions, and a polite `role="status"` region for
    loading/no-result/error. Debounce 250 ms; no request below
    `SEARCH_Q_MIN_LENGTH` (imported from `@pca/shared` — no inline literal);
    `limit` omitted so the API default applies (no numeric literal). Suggestions
    show display name, `statuteCode` where present, and `matched: <alias>` where
    served — public-safe fields only. Keyboard: ArrowDown/Up move the active
    option (wrapping), Enter commits the active option when the list is open
    (and does nothing when open with **no** active option — required fix 1),
    Escape closes then a second Escape clears, Tab closes, editing after a
    commit clears the committed state. Combobox/listbox/option ids derive from
    `useId()` so the 12.3 judge combobox cannot collide (required fix 3).
  - **Stale-response protection:** a monotonic `seqRef` tags each dispatch;
    a resolved response applies only if its sequence is still the latest.
    Chosen over AbortController because `searchCharges` takes no `AbortSignal`
    and the client lives in the out-of-scope `app/lib` module. The ref is also
    bumped on commit / clear / drop-below-minimum so a late response can never
    reopen the list or repopulate cleared state.
  - **`apps/web/app/components/SearchForm.tsx`** (now a `'use client'`
    component): owns `committedCharge` + submit-hint state, renders
    `<ChargeSearchInput>` in the charge region, and holds one `handleSubmit`
    used by BOTH the Enter path (list closed) and a visible, enabled submit
    button (required fix 2). Committed charge → `router.push('/charges/<slug>')`;
    no committed charge → no navigation, inline hint shown. The judge region is
    the byte-for-byte disabled placeholder from 12.1 with its `MOUNT: task 12.3`
    point preserved. `page.tsx` was not touched (a server page rendering a
    client child needs no change).
  - **Copy:** new `apps/web/app/components/charge-search-copy.ts`
    (`CHARGE_SEARCH_COPY`) holds only the new strings (loading, no-result,
    submit hint, listbox instructions, `matched:` prefix, submit button label);
    the charge label/placeholder/help stay sourced from `HOME_COPY` (no
    duplication). No-result copy points at spelling/common names and does not
    assert nonexistence. API-error rendering uses `PUBLIC_ERROR_MESSAGES` /
    `FETCH_FAILURE_MESSAGE` from `@pca/shared`.
- **Render-test infrastructure:** new `apps/web/vitest.config.ts` uses
  `test.projects` — a `node` project (existing `test/**` + `app/**/*.test.ts`,
  node env, no setup) and a `jsdom` project (`app/**/*.test.tsx`, jsdom env,
  `test/setup.jsdom.ts`). The **`test.projects` approach held** (Vitest 3.2.7);
  no fallback to per-file `@vitest-environment` docblocks was needed. Web keeps
  **dist resolution** (no `pca-source` condition) per the 11.1 standing
  decision, so `pnpm run build:packages` remains the prerequisite and the three
  workspace-resolution knobs in the shared/db/api configs are untouched.
  `esbuild.jsx: 'automatic'` is set so test files need no `import React`.
  devDependencies added (with lockfile): `@testing-library/react`,
  `@testing-library/dom`, `@testing-library/user-event`,
  `@testing-library/jest-dom`, `jsdom`.
- **Tests added:** `ChargeSearchInput.test.tsx` (11 — below-min no request,
  single debounced request, stale-response guard, loading, suggestion fields +
  mouse commit/close, ARIA/activedescendant, Escape/second-Escape, edit-clears,
  no-result, api-error, transport-error); `SearchForm.test.tsx` (5 — full
  keyboard commit→submit push, mouse button submit, Enter-open-no-active does
  nothing, no-commit hint, judge placeholder unchanged); `charge-search-copy.test.ts`
  (scanPublicCopy over every value). Fake timers throughout for the debounce.
- **Files touched:** new — `apps/web/app/components/ChargeSearchInput.tsx`,
  `apps/web/app/components/charge-search-copy.ts`, `apps/web/vitest.config.ts`,
  `apps/web/test/setup.jsdom.ts`, `apps/web/app/components/ChargeSearchInput.test.tsx`,
  `apps/web/app/components/SearchForm.test.tsx`,
  `apps/web/app/components/charge-search-copy.test.ts`; modified —
  `apps/web/app/components/SearchForm.tsx`, `apps/web/package.json`,
  `pnpm-lock.yaml`, `tasks/worklog.md`.
- **Deviations from plan:** none material. Two implementation-detail choices
  surfaced by the gate: (a) below-minimum clearing moved from the effect body
  into `handleChange` to satisfy `react-hooks/set-state-in-effect`; (b) added
  `esbuild.jsx: 'automatic'` so JSX compiles with the React automatic runtime
  under Vitest's esbuild transform.
- **How to verify:** `pnpm run build:packages` (dist prereq for `@pca/*`), then
  from root `pnpm lint`, `pnpm format:check`, `pnpm typecheck`, and
  `pnpm --filter @pca/web test`. Routing to `/charges/<slug>` lands on Next's
  404 in dev until 13.2 — expected; tests assert the `router.push` call.
- **Gates — all green:** lint 0; format:check clean; typecheck 0; web tests 51
  (17 new across node+jsdom projects), existing node suites (formatters 17,
  public-api-client 14, copy-guard 2, home-copy 1) unchanged; shared 163,
  taxonomy pass. api/db suites are DATABASE_URL-gated and were not run here;
  no api/db/shared files were touched.
- **Notes for next task (12.3):** extend this same `SearchForm.handleSubmit`
  for the judge path; the judge region is still the disabled placeholder with
  its mount point intact. Reuse the `ChargeSearchInput` combobox pattern
  (useId-based ids already prevent collision) for `JudgeSearchInput`. The
  jsdom Vitest project already covers `app/**/*.test.tsx`.

## Task 12.3 — Judge Autocomplete + Submission Flows

- **Date:** 2026-07-09
- **What was built:** The disabled `#judge-search` placeholder is replaced by a
  functional, accessible, clearly-optional WAI-ARIA judge combobox, and the
  homepage form's submission routing is completed: charge-only →
  `/charges/[chargeSlug]`, charge + judge → `/charges/[chargeSlug]/judge/[judgeSlug]`.
  This closes Phase 12. The generic combobox mechanics were extracted from the
  12.2 `ChargeSearchInput` into a shared hook that both inputs now consume.
  - **`apps/web/app/components/combobox-search.ts`** (new): `useComboboxSearch<T>`,
    a generic hook owning every piece of the shared mechanics — 250 ms debounce,
    `SEARCH_Q_MIN_LENGTH` gate, monotonic sequence guard (incl. the
    late-response-never-reopens-a-closed-list hardening: `commit`/`clear`/
    sub-min-length all bump the sequence), ArrowDown/Up/Enter/Escape/Tab
    handling, staged commit-on-select, edit-after-commit clears, second-Escape
    clears, `useId`-based ARIA id wiring, and the derived
    `showList/showLoading/showNoResult/showError` flags. It imports no copy
    modules and contains no user-visible string literals (pin 2); error text
    surfaces only via the `@pca/shared` constants it passes through to the
    rendering components. Consumers keep their own JSX, so rendering differences
    (charge shows `statuteCode`; judge does not) stay in the components.
  - **`ChargeSearchInput.tsx`**: mechanics deleted and replaced by a single
    `useComboboxSearch<ChargeSearchResult>` call; JSX unchanged. Rendered output
    and behavior are byte-identical (its whole 12.2 test suite passes unchanged).
  - **`JudgeSearchInput.tsx`** (new client component): mirrors the charge JSX
    minus the statute line, consumes `useComboboxSearch<JudgeSearchResult>` and
    the `searchJudges` typed client, renders display name + `matched: <alias>`
    where served, and keeps the 12.1 secondary layout (`py-2.5`). Its own `useId`
    base gives the second combobox collision-proof ids in the shared form.
  - **`judge-search-copy.ts`** (new): `JUDGE_SEARCH_COPY` (loading, no-result,
    list instructions, matched-alias prefix). The no-result copy points at
    spelling / a different form of the name and reaffirms Philadelphia-wide
    charge results remain available — it never asserts the judge does not exist.
    Direct `scanPublicCopy` assertion test added; the app/-walking copy guard
    covers the file automatically. Judge label/placeholder/help stay in
    `HOME_COPY`; submit button/hint reuse `CHARGE_SEARCH_COPY`; API failures
    reuse the `@pca/shared` error constants — no new form-level copy.
  - **`SearchForm.tsx`**: mounts `JudgeSearchInput`, adds `committedJudge` state,
    and implements the four-state submission matrix in the single `handleSubmit`
    (no charge → hint, no nav; charge-only → charge route; charge + judge →
    combined route; judge-only → hint, no nav, judge commit preserved). The judge
    input never blocks or invalidates submission.
- **Tests:** new `combobox-search.test.tsx` (hook harness: min-length gate,
  debounce, sequence-guard staleness, ArrowDown+Enter commit, Escape
  close/clear), `JudgeSearchInput.test.tsx` (11: optional/non-disabled, min-len
  gate, loading, alias render, keyboard select, Escape close/clear,
  edit-after-commit clears, no-result, API error + transport failure via shared
  constants, stale-response guard), and a new `SearchForm` "judge submission
  matrix" describe (combined route; judge-only preserved then combined; pin-1
  edit-after-commit clears judge → later charge-only submit routes charge-only).
- **How to verify:** `pnpm run build:packages` (dist prereq for `@pca/*`), then
  from root `pnpm lint`, `pnpm format:check`, `pnpm typecheck`, and
  `pnpm --filter @pca/web test`. Combined submission lands on Next's 404 in dev
  until 13.3 — expected; tests assert the `router.push` path, not a rendered page.
- **Gates — all green:** lint 0; format:check clean; typecheck 0; web tests 70
  (node + jsdom projects); shared/taxonomy suites untouched. No api/db/shared/
  taxonomy files were touched.
- **Deviations from plan:** one, approved at review. Mounting the judge combobox
  puts a second `role="combobox"` in the form, so the pre-existing charge-path
  `SearchForm` tests' bare `screen.getByRole('combobox')` became ambiguous
  ("Found multiple elements"). Per the pinned byte-identical constraint I stopped
  and reported; the human amended the constraint to its precise intent and
  approved scoping the shared `combobox()` test helper by accessible name
  (`{ name: HOME_COPY.chargeLabel }`) — the correct testing-library pattern,
  which also locks the charge label association. The full pre-existing-test diff
  for this task is therefore exactly: (a) that one helper line, and (b) deletion
  of the now-obsolete "keeps the judge placeholder disabled and unchanged" test.
  The three charge-path `it()` bodies and all of `ChargeSearchInput.test.tsx`
  remain byte-identical. Also trivial: reworded a doc comment in
  `judge-search-copy.ts` ("promises" not "guarantees") so the whole-file copy
  guard, which scans comments too, stays green.
- **Notes for next task (13.x):** `/charges/[chargeSlug]` (13.2) and
  `/charges/[chargeSlug]/judge/[judgeSlug]` (13.3) still 404 in dev; the form
  already routes to both. Any future combobox reuses `useComboboxSearch<T>` —
  give the parent-owned committed selection, an `onCommitChange`, and a typed
  `search` function returning `PublicApiResult<{ results: T[] }>`. When a form
  hosts multiple comboboxes, query inputs by accessible name, not bare role.

## Task 13.1 — Distribution + Metadata Display Components

- **Date:** 2026-07-09
- **What was built:** The reusable, presentational-only display components that
  13.2/13.3 will compose into the result pages — a generic `DistributionSection`
  (semantic table + paired aria-hidden bars) plus five metadata components
  (`SampleSizeLabel`, `DateRangeLabel`, `ThinDataBadge`, `ThinDataCallout`,
  `ResponsibleUseNotice`) — a copy-constants module, and a single-source
  definition-anchor helper. Components only: no pages, routes, or data fetching.
- **Files touched (all new):**
  - **`apps/web/app/lib/definition-anchor.ts`**: `DistributionKind` type +
    `definitionAnchor(kind, categoryCode)` → `/definitions#<kind>-<categoryCode>`
    (pinned decision 2). The single home of the convention; 14.1 imports it to
    mint matching ids. Uses the taxonomy code verbatim.
  - **`apps/web/app/components/result-display-copy.ts`**: `RESULT_DISPLAY_COPY`
    — every user-facing string the display components render (captions, headers,
    definition-link text/label prefix, thin-data callout body, the four
    responsible-use statements). Flat string values so the app/-walking copy
    guard covers each and the direct scan test iterates them.
  - **`DistributionSection.tsx`**: `<section>` labelled by the table `<caption>`;
    a semantic table (`<th scope="col">` headers, `<th scope="row">` per category
    holding the display name + definition anchor link, count and percentage in
    adjacent `<td>`s — always together, via the 11.4 formatters); a separate
    `aria-hidden="true"` bar block whose fill width is `width: ${percentage}%`
    from the API percentage only. Embeds `ThinDataBadge` adjacent to the sample
    size when thin; does NOT render the callout.
  - **`SampleSizeLabel.tsx` / `DateRangeLabel.tsx` / `ThinDataBadge.tsx` /
    `ThinDataCallout.tsx` / `ResponsibleUseNotice.tsx`**: metadata components,
    all formatting through `app/lib/formatters.ts`. `DateRangeLabel` takes an
    optional range and renders nothing when absent (never invents a default).
    `ThinDataBadge` renders the pinned `THIN_DATA_LABEL` via `formatThinDataLabel`
    only when thin. `ThinDataCallout` is standalone (page-level placement is
    13.2/13.3's job per required mobile content order).
  - **Tests (co-located per the 12.2 jsdom-project convention):**
    `DistributionSection.test.tsx` (7: outcome render; sentencing with its
    separate sample size; shuffled fixture renders in fixture order — proving no
    client re-sort; bar widths = API %, aria-hidden, table mirrors every value;
    per-row anchor; scoped `<th>` + caption; embedded badge both ways with no
    callout in-section), `ThinDataBadge`/`ThinDataCallout`/`SampleSizeLabel`/
    `DateRangeLabel` (incl. missing-range case)/`ResponsibleUseNotice` tests,
    `result-display-copy.test.ts` (direct `scanPublicCopy`), and
    `definition-anchor.test.ts`. Fixtures are typed straight from `@pca/shared`
    (`OutcomeDistributionEntry` / `SentencingDistributionEntry`) — no mock shapes.
- **Pinned-decision-1 verification (recorded per review):** the Sprint 2 result
  endpoints serve distribution rows in taxonomy sort order server-side. Both
  services map stored rows through `apps/api/src/services/result-helpers.ts`,
  which sorts by taxonomy `sortOrder` before serving (`mapped.sort(...)`), and
  the route suites assert "in taxonomy sort order". So `DistributionSection`
  renders `rows` in received order with NO client sort.
- **How to verify:** `pnpm run build:packages` (Phase 13 dist prereq), then from
  root `pnpm lint`, `pnpm format:check`, `pnpm typecheck`, `pnpm test` (or
  `pnpm --filter @pca/web test`).
- **Gates — all green:** lint 0; format:check clean; typecheck 0; web tests 89
  (up from 70; node + jsdom projects), api 194, all other workspace suites
  unaffected.
- **Deviations from plan:** none. As approved at review, the thin-data rendering
  was split — badge embedded in `DistributionSection`, callout standalone only.
  One implementation note: the whole-file copy guard scans comments too, so a
  few doc comments were reworded to avoid the forbidden vocabulary (e.g.
  "guarantees" → "keeps"; dropped "prediction/predictive" from prose); the
  rendered string values are unchanged and pass the direct scan.
- **Notes for next task (13.2/13.3, 14.1):** compose `DistributionSection` per
  distribution and place `ThinDataCallout` at page level (before the sections)
  per the required mobile content order; it is intentionally not embedded.
  `ResponsibleUseNotice` and `DateRangeLabel` are page-composed too — the result
  `dateRange` is result-level, so pass it to `DateRangeLabel` at the page.
  Task 14.1 (definitions page) MUST import `definitionAnchor` from
  `app/lib/definition-anchor.ts` and emit element ids from the same helper so the
  per-row links resolve. Category codes are served verbatim (e.g. `guilty_plea`,
  `no_further_penalty`).

## Task 13.2a — Charge-Unavailable Contract Fix (API + shared)

- **Date:** 2026-07-09
- **What was built:** brought the charge-only result endpoint into compliance
  with the standing "entities exist, data absent → answerable 200, never a 404"
  decision. `ChargeOnlyResultResponse` is now a top-level `resultType`-tagged
  union; a resolvable charge with no publishable aggregate returns an HTTP 200
  unavailable arm carrying charge metadata, mirroring the shipped 8.2
  judge-unavailable pattern. `CHARGE_NOT_FOUND` (charge entity absent) stays a
  404, untouched.
- **The two union shapes, side by side (acceptance criterion 5):**
  - **8.2 judge-unavailable (shipped, unchanged):**
    `{ resultType: 'judge_specific_unavailable', code:
    'JUDGE_SPECIFIC_RESULT_UNAVAILABLE', message: <pinned literal>, charge,
    judge, fallback: { chargeOnlyResultPath } }`
  - **13.2a charge-unavailable (new):**
    `{ resultType: 'charge_only_unavailable', code:
    'CHARGE_RESULT_UNAVAILABLE', message: CHARGE_RESULT_UNAVAILABLE_MESSAGE,
    charge, links: { methodology, definitions } }`
  - The **discriminator mechanism is mirrored exactly** (top-level `resultType`
    string-literal union, `_unavailable` suffix, `code`+`message` literals,
    `charge` summary as served). The **one deliberate structural difference**
    (approved at review): where 8.2 carries a `fallback` pointing *at* the
    charge-only result, this arm carries `links` instead — the charge-only
    result is the terminal baseline with nowhere to fall back to, and pinned
    decision 2 called for methodology/definitions link metadata (also what the
    paused 13.2 render needs). The `links` object is identical in shape to the
    success arm's.
- **Files touched:**
  - **`packages/shared/src/public/charge-result.ts`**: split the object schema
    into `chargeOnlyResultSuccessSchema`/`ChargeOnlyResultSuccess`, added
    `chargeOnlyResultUnavailableSchema`/`ChargeOnlyResultUnavailable`, redefined
    `chargeOnlyResultResponseSchema`/`ChargeOnlyResultResponse` as the union
    (same exported names). Shared `resultLinksSchema` between the arms.
  - **`packages/shared/src/test-support/fixtures.ts`**: pinned
    `validChargeOnlyResult()`/`…SentencingUnavailable()` return types to
    `ChargeOnlyResultSuccess` (so `validJudgeSpecificResultSuccess`'s
    `.sentencing` read still type-checks); added
    `validChargeOnlyResultUnavailable()`.
  - **`packages/shared/src/public/charge-result.test.ts`**: added an
    unavailable-arm describe block (accepts the arm; message = imported literal;
    code pinned; rejects distributions/run metadata). Success-arm tests
    unchanged and still green under the union.
  - **`apps/api/src/services/charge-result.ts`**: extracted a `chargeSummary`
    helper and a `chargeOnlyResultUnavailable(charge)` arm builder; the two
    former throw sites (`!run`; zero outcome rows) now `return` the arm. The
    charge-lookup miss still throws `CHARGE_NOT_FOUND`.
  - **`apps/api/src/routes/public/results.ts`**: comment updated to the
    tagged-union note (schema reference unchanged — it is now the union).
  - **`apps/api/src/services/charge-result.test.ts`**: the two throw-site unit
    tests became arm-return assertions; added a narrowing `getSuccess` helper for
    the happy-path mapping-rules tests.
  - **`apps/api/src/routes/public/results.test.ts`**: added the seeded
    zero-rows → 200 arm exact-body test (message asserted `===` the imported
    `CHARGE_RESULT_UNAVAILABLE_MESSAGE`) plus a by-UUID identity test; added
    `code` to the allowed-keys set and swept the harassment arm.
  - **`apps/api/src/test-support/public-route-probes.ts`**: added the
    `200-charge-unavailable` probe (`/results/charge/harassment`). This
    automatically extended the live forbidden-field and copy-safety suites to
    scan the new arm — no other edits to those suites.
  - **`db/seeds/reference-data.ts`**: added the `harassment` charge (active,
    `18 § 2709`), deliberately absent from every aggregate distribution — the
    seeded fixture proving the "published run, zero rows" cause end-to-end
    (acceptance criterion 9). Chosen collision-free with every charge-search
    test query.
  - **`apps/web/app/lib/formatters.ts`**: retargeted `LabelableResultType` to
    `ChargeOnlyResultSuccess['resultType']` so the new `charge_only_unavailable`
    literal never enters the exhaustive result-type-label switch.
  - **`apps/web/app/lib/public-api-client.test.ts`**: added a charge-only 200
    unavailable-arm → `ok:true` passthrough test. No runtime client change (the
    client already surfaces 200 unavailable arms as data).
- **Coverage split for the no-published-run cause (accepted at review, recorded
  here as rationale):** both unavailable causes converge on the same
  `chargeOnlyResultUnavailable` arm builder, so the no-published-run cause is
  covered at the unit level only (mocked `findActivePublishedRun → undefined`).
  It is intentionally NOT tested end-to-end: dropping the globally-seeded
  published run would break every parallel DB suite. The zero-rows cause is
  proven end-to-end via the harassment seed + the new probe, plus at the unit
  level.
- **Catalog retention:** `CHARGE_RESULT_UNAVAILABLE` stays in the public error
  catalog (404 default in `PUBLIC_ERROR_CODE_STATUS`, entry in
  `PUBLIC_ERROR_MESSAGES`) even though it is now only ever emitted as the 200
  body tag — exactly how 8.2 keeps `JUDGE_SPECIFIC_RESULT_UNAVAILABLE` (pinned
  decision 4). `PUBLIC_ERROR_CODE_STATUS` values are documented defaults, not
  invariants, so a 200 body carrying the code is consistent. `errors.ts` /
  `error-messages.ts` unchanged.
- **Judge-endpoint entanglement:** none. `getChargeOnlyResult` is called only by
  the charge-only route; the judge service has its own separate
  `CHARGE_RESULT_UNAVAILABLE` throw sites, untouched (pinned decision 6).
- **How to verify:** `pnpm db:up && pnpm db:migrate:latest`, then
  `pnpm run build:packages`, then from root `pnpm lint`, `pnpm format:check`,
  `pnpm typecheck`, `pnpm test`.
- **Gates — all green:** lint 0; format:check clean; typecheck 0; shared 166,
  web 90, db 6, api 198 (results.test.ts 12, copy-safety 25, forbidden-fields 26
  — the last two now scanning the new arm). Route-count discovery assertion
  unchanged at 7 (a probe was added, not a route).
- **Deviations from plan:** none.
- **Notes for next task (13.2 resumes):** the client's `getChargeResult` now
  returns the union — branch on `resultType`: `'charge_only'` renders the full
  view, `'charge_only_unavailable'` renders the in-page unavailable state
  (charge metadata + the pinned message + methodology link, NOT `not-found.tsx`).
  A `validChargeOnlyResultUnavailable()` fixture is available in
  `@pca/shared` test-support. `CHARGE_NOT_FOUND` remains the 404 → `notFound()`
  path.

## Task 13.2 — Charge-Only Result Page

- **Date:** 2026-07-09
- **What was built:** the public charge-only result route at
  `/charges/[chargeSlug]` — a thin async server component that fetches via the
  11.2 client and branches into four states, composing the 13.1 display
  components, with a judge-filter entry point and route-level
  loading/not-found/error states. Built against the 13.2a-corrected contract
  (`ChargeOnlyResultResponse` is now a `resultType` union of `charge_only` and
  the HTTP 200 `charge_only_unavailable` arm).
- **Files created:**
  - **Route** `apps/web/app/charges/[chargeSlug]/`:
    - `page.tsx` — async server component; `React.cache`-memoized loader shared
      between `generateMetadata` (dynamic `<title>` = charge display name on
      both 200 arms) and the body; dispatches via the pure state helper:
      success → `ChargeOnlyResultView`, unavailable → `ChargeUnavailableView`,
      not-found → `notFound()`, error → generic `throw` (→ `error.tsx`).
    - `loading.tsx`, `not-found.tsx` (imports `CHARGE_NOT_FOUND_MESSAGE` +
      homepage link), `error.tsx` (`'use client'` boundary, generic copy, never
      renders the thrown error).
    - `charge-result-state.ts` + `.test.ts` — pure `resolveChargeResultState`
      mapping the client's typed result to the four states (node-tested; page.tsx
      itself is exempt from direct tests per pinned decision 1).
  - **Components** `apps/web/app/components/`:
    - `ChargeOnlyResultView.tsx` — presentational success render in the pinned
      mobile DOM order (summary → responsible-use → thin-data callout →
      outcome → sentencing → links → judge-filter), each block tagged
      `data-testid="section-*"` for the order assertion; distributions wrapped
      in `overflow-x-auto` so tables never scroll the page body.
    - `ChargeUnavailableView.tsx` — in-page 200 unavailable arm: charge
      identity + imported `CHARGE_RESULT_UNAVAILABLE_MESSAGE` + methodology and
      definitions links from `data.links`.
    - `SentencingUnavailableNotice.tsx` — in-payload sentencing-unavailable arm:
      imported `CHARGE_SENTENCING_UNAVAILABLE_MESSAGE` + methodology link.
    - `JudgeFilterEntry.tsx` (`'use client'`) — reuses `JudgeSearchInput`;
      routes to `/charges/[chargeSlug]/judge/[judgeSlug]` on judge commit.
    - `charge-result-copy.ts` + `.test.ts` — all new incidental page copy under
      `scanPublicCopy`; pinned `@pca/shared` message literals imported, not
      duplicated.
  - **Tests:** `ChargeOnlyResultView.test.tsx` (full metadata, thin-data,
    sentencing-unavailable, DOM-order), `ChargeUnavailableView.test.tsx`,
    `JudgeFilterEntry.test.tsx` (routing target), and co-located state-file
    tests `loading/not-found/error.test.tsx`.
- **Pinned-decision conformance:** thin-data callout shows when EITHER
  distribution is thin (`outcomes.thinData || (sentencing.available &&
  sentencing.thinData)`) — ruled at review; per-distribution `ThinDataBadge`
  still shows each precise state. Unavailable view renders BOTH methodology and
  definitions links — ruled at review. Judge-filter placed after the links
  block (decision 6 permits). Copy decision 5's "not guaranteed" reworded to
  "not available for every charge and judge" (the `guarantee` stem is a
  forbidden copy term).
- **How to verify:** `pnpm run build:packages`, then in `apps/web`:
  `pnpm typecheck`, `pnpm test`; from root `pnpm lint`, `pnpm exec prettier
  --check`.
- **Gates — all green:** typecheck 0; web tests 107 passed (26 files, +23 new);
  eslint 0; prettier clean; copy guard green.
- **Deviations from plan:** none. No 13.1 components or `@pca/shared`/API files
  modified.
- **Notes for next task (13.3):** the judge-specific route target
  `/charges/[chargeSlug]/judge/[judgeSlug]` is now linked from both the homepage
  submit and the charge page's `JudgeFilterEntry`; it does not yet exist. The
  `resolveChargeResultState` pattern and the `section-*` DOM-order test approach
  are reusable for the judge-specific page.

## Task 13.3 — Judge-Specific Result Page

- **Date:** 2026-07-09
- **What was built:** the public judge-specific result route at
  `/charges/[chargeSlug]/judge/[judgeSlug]` — a thin async server component that
  fetches via the 11.2 client (`getJudgeSpecificResult`) and branches into
  success / in-page unavailable / in-page not-found / error, composing the 13.1
  display components twice per distribution type (one "Judge-specific result"
  section, one "Philadelphia-wide baseline" section — no merged comparison
  component). Four independent distribution slots, each with its own sample
  size, thin-data state, and independent sentencing-unavailable fallback.
- **Files created:**
  - **Route** `apps/web/app/charges/[chargeSlug]/judge/[judgeSlug]/`:
    - `page.tsx` — async server component; `React.cache`-memoized loader shared
      between `generateMetadata` and the body; dispatches via the pure state
      helper: success → `JudgeSpecificResultView`, unavailable →
      `JudgeUnavailableView`, not-found → in-page `ResultNotFoundView`, error →
      generic `throw` (→ `error.tsx`). `generateMetadata` sets `<title>` to
      `"{charge} — {judge}"` on both 200 arms (required fix 1).
    - `judge-result-state.ts` + `.test.ts` — pure resolver mapping the typed
      client result to `success | unavailable | not-found(reason) | error`;
      `JUDGE_SPECIFIC_RESULT_UNAVAILABLE` is handled as the 200 `resultType`
      arm, never as an api_error; `CHARGE_NOT_FOUND`/`JUDGE_NOT_FOUND` map to
      `not-found` with a `reason` discriminator selecting the distinct pinned
      message.
    - `loading.tsx` + `.test.tsx`, `error.tsx` + `.test.tsx` — reuse
      `CHARGE_RESULT_COPY` chrome (loading/error copy shared, no new strings).
  - **Components** `apps/web/app/components/`:
    - `JudgeSpecificResultView.tsx` — presentational success render in the
      pinned mobile DOM order (summary → responsible-use → thin-data callout →
      judge outcome → judge sentencing → baseline outcome → baseline
      sentencing → links). The two section headings wrap their slots without
      their own `section-*` testid, so the leaf `data-testid="section-*"` order
      matches the pinned mobile order one-for-one; each slot wrapped in
      `overflow-x-auto`. Reuses `DistributionSection`/`SentencingUnavailableNotice`
      via a private `ScopeSlots` helper so judge and baseline are structurally
      identical. Remove-filter link "View Philadelphia-wide result instead" →
      `/charges/[chargeSlug]`.
    - `JudgeUnavailableView.tsx` — in-page 200 `judge_specific_unavailable` arm:
      charge + judge identity, imported `JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE`
      (verbatim, not read off `data.message`), charge-only link; renders NO
      distribution sections and never surfaces the internal `code`.
    - `ResultNotFoundView.tsx` — generic in-page not-found view taking the
      pinned message; used for both missing-charge and missing-judge.
    - `judge-result-copy.ts` + `.test.ts` — the three new chrome strings
      (two section headings + remove-filter link) under `scanPublicCopy`; all
      pinned message literals imported from `@pca/shared`, never duplicated.
  - **Tests:** `JudgeSpecificResultView.test.tsx` (success+baseline with four
    distinct sample sizes, server-order rows, thin-data pure-OR + per-slot
    badge, sentencing-unavailable slot, remove-filter target, DOM order),
    `JudgeUnavailableView.test.tsx` (literal via import, names, link, NO
    distribution sections per required fix 3, no internal code),
    `ResultNotFoundView.test.tsx` (both distinct pinned messages).
- **Required-fix conformance:** (1) title names both charge and judge on
  success + unavailable. (2a) per-slot `ThinDataBadge` still renders inside each
  `DistributionSection`; (2b) the page-level callout is a pure OR over the four
  API-provided `thinData` booleans — no counts, sample sizes, or thresholds in
  web code. (3) added the "renders NO distribution sections" assertion.
- **Not-found rendering — deliberate divergence from 13.2 (approved):** both
  missing-charge and missing-judge render IN PAGE via `ResultNotFoundView` with
  the distinct pinned `@pca/shared` literals (HTTP 200), rather than calling
  `notFound()`. This is a **soft 404 on this route** and diverges from 13.2's
  real-404 behavior for a missing charge. It is acceptable because result pages
  are `noindex`, and it is **to be revisited at the Sprint 9 launch-readiness
  indexing review**. Next's not-found boundary is prop-less, so it cannot carry
  the two distinct messages — hence the in-page approach.
- **How to verify:** `pnpm run build:packages`, then from root `pnpm typecheck`,
  `pnpm lint`, `pnpm format:check`, `pnpm test`.
- **Gates — all green:** typecheck 0; web tests 129 passed (33 files, +21 new);
  shared 166; api 198; eslint 0; prettier clean; copy guard + forbidden-field
  suites green.
- **Deviations from plan:** none beyond the approved in-page not-found. No
  changes to `@pca/shared`, the API, 13.1 component contracts, or 11.4
  formatters. Copy-guard note: two source comments were reworded to avoid the
  `predict` and `harsher` forbidden stems (the guard scans raw file text,
  comments included).
- **Notes for next task:** the definitions/methodology anchor targets the
  per-row `Definition` links point at (`/definitions#...`) are still Phase 14
  pages; the judge page renders four sets of those anchors (judge + baseline ×
  outcome + sentencing). E2E coverage of the route is task 15.2.

## Task 14.1 — Definitions Page (API-backed)

- **Date:** 2026-07-09
- **What was built:** Replaced the static `/definitions` placeholder with an
  async server component that fetches `GET /api/v1/public/definitions` via the
  11.2 typed client (server-side, absolute base URL — the standing 13.2/13.3
  pattern) and renders every public outcome and sentencing category definition
  in served (taxonomy) order, each with a stable per-category anchor id, plus
  the taxonomy version near the footer. Loading and error states included.
  - `apps/web/app/definitions/page.tsx` — rewritten: fetch + dispatch only.
    `ok` → `<DefinitionsView>`; `!ok` → inline `<DefinitionsErrorState>` with a
    per-arm `@pca/shared` message (no error.tsx boundary — approved, because
    the client returns `ok:false` with a discriminated failure arm rather than
    throwing, and the page must pick the correct message per arm). No internal
    detail is ever surfaced.
  - `DefinitionsView.tsx` — presentational; exports `DefinitionsView` (success)
    and `DefinitionsErrorState` (message). Semantic h1 → h2 per section → h3 per
    category; each h3 carries `id={definitionAnchorId(kind, entry.code)}` (ids
    present in the server-rendered markup). Renders in served order — no sort.
  - `definitions-copy.ts` (+ `.test.ts`) — all page framing copy as flat
    constants under `scanPublicCopy`; category names/definitions come live from
    the API, error body comes from `@pca/shared`.
  - `definitions-failure.ts` (+ `.test.ts`) — pure `definitionsFailureMessage`:
    `api_error` → `PUBLIC_ERROR_MESSAGES[code]`, `fetch_failed` →
    `FETCH_FAILURE_MESSAGE`; never the API `message` or request id.
  - `loading.tsx` — route-level neutral loading copy.
  - `DefinitionsView.test.tsx` — categories + names + definitions, served order,
    h1/h2/h3 hierarchy, anchor-id presence, taxonomy version, error render, and
    AC 4 link-target resolution: the fragment from `definitionAnchor(kind, code)`
    resolves to a live element on the page, one assertion per distribution type.
- **Anchor scheme (task item 2):** the pinned convention, unchanged. Added
  `definitionAnchorId(kind, code)` → `<kind>-<code>` to
  `apps/web/app/lib/definition-anchor.ts` as the single source of the fragment
  format; refactored `definitionAnchor` to compose it so link and target are
  minted from one place. `definitionAnchor`'s output string is byte-identical —
  the existing `DistributionSection` href test is the regression lock and stayed
  green.
- **13.1 component changes (task item 3):** NONE. The 13.1 links already emit
  the exact target scheme via `definitionAnchor`; no `app/components/**` edits.
- **Files touched:** `apps/web/app/definitions/page.tsx` (rewrite),
  `apps/web/app/definitions/DefinitionsView.tsx` (new),
  `apps/web/app/definitions/DefinitionsView.test.tsx` (new),
  `apps/web/app/definitions/definitions-copy.ts` (new),
  `apps/web/app/definitions/definitions-copy.test.ts` (new),
  `apps/web/app/definitions/definitions-failure.ts` (new),
  `apps/web/app/definitions/definitions-failure.test.ts` (new),
  `apps/web/app/definitions/loading.tsx` (new),
  `apps/web/app/lib/definition-anchor.ts` (add `definitionAnchorId`),
  `apps/web/app/lib/definition-anchor.test.ts` (add cases).
- **How to verify:** `pnpm run build:packages`, then from root `pnpm typecheck`,
  `pnpm lint`, `pnpm format:check`, `pnpm test`.
- **Gates — all green:** typecheck 0; web tests 143 passed (36 files); api 198;
  eslint 0; prettier clean; copy guard + forbidden-field suites green.
- **Deviations from plan:** none. No `@pca/shared`, API, `@pca/taxonomy`, or
  13.1 component-contract changes. Copy-guard note: one source comment was
  reworded to avoid the `predict` forbidden stem (the guard scans raw file text,
  comments included).
- **Notes for next task:** Methodology (14.2) and About (14.3) pages follow the
  same server-fetch + presentational-view + per-arm-error-message shape; the
  data-coverage/methodology clients already exist in `public-api-client.ts`.
  E2E coverage of the definitions route (including real fragment navigation from
  a result page on first load) is task 15.2.

## Task 14.2 — Methodology + Data Coverage Pages (API-backed)

- **Date:** 2026-07-09
- **What was built:** Replaced the static placeholder copy on `/methodology`
  and `/data-coverage` with API-backed pages, following the 14.1 definitions
  shape exactly (thin async server component → presentational view + page-local
  copy/failure modules, per-arm @pca/shared error message, route-level loading).
  - **Methodology:** `page.tsx` (rewrite) fetches `getMethodology()`; on failure
    renders `MethodologyErrorState` with `methodologyFailureMessage`. `MethodologyView`
    iterates the shared `METHODOLOGY_SECTION_KEYS` in pinned presentation order,
    rendering each section's `heading` (h2) and `body` (p) **verbatim as served** —
    the only page-owned prose is the h1/error/loading chrome in `METHODOLOGY_COPY`.
  - **Data coverage:** `page.tsx` (rewrite) fetches `getDataCoverage()`. Two
    distinct not-available cases handled separately: transport/API failure →
    inline `DataCoverageErrorState`; the endpoint's own HTTP-200 `available:false`
    arm → a successful render (served `coverage.message` verbatim). `DataCoverageView`
    always renders top-level `jurisdiction`/`courtScope`/`plannedDataStart` and the
    `knownLimitations` list in BOTH arms (per approval: the seeded-data disclosure
    stays visible when unavailable). Available arm additionally renders the
    `dataStart–dataEnd` window, `lastRefreshed` (UTC suffix), `aggregateRunId` +
    `taxonomyVersion` (public-safe run metadata), and the three counts.
  - **Formatting:** all dates/counts route through the 11.4 `app/lib/formatters.ts`
    exports; nothing inline.
- **Section-labeling approach (methodology):** section headings come from the API
  (`section.heading`), not from page copy. The view adds no per-section labels; it
  only supplies the page h1. Order is the shared `METHODOLOGY_SECTION_KEYS`
  constant, so a schema/key change is a compile-time break, not silent reorder.
- **Named lib change (approved):** exported the previously-private `formatDateOnly`
  from `apps/web/app/lib/formatters.ts` (added `export` + doc note only — no logic
  change). Needed because `plannedDataStart` is a lone `YYYY-MM-DD` with no existing
  single-date exported formatter; `formatDateRange` composes it for the two-bound
  window. Added direct UTC-safe unit coverage in `formatters.test.ts` (long-form
  render, Jan-1 no off-by-one, spoofed UTC+14 timezone, throw on malformed input).
- **Required-fix compliance:**
  - *Limitations order:* `DataCoverageView.test.tsx` collects the rendered
    `<li>` text into an array (via `getByTestId('known-limitations')`) and asserts
    deep equality with the fixture's `knownLimitations` — catches paraphrase,
    truncation, AND reordering. Asserted in both coverage arms.
  - *Non-circular 2025-01-01:* the expected rendered date is pinned as the string
    literal `'January 1, 2025'` in the test, not computed via `formatDateOnly`, so
    a formatter regression cannot keep it green. Same for the window literal.
  - *`formatDateOnly` direct test:* added to `formatters.test.ts` (above).
- **Error-state string sourcing:** page-local `*-failure.ts` mappers mirroring
  14.1's `definitions-failure.ts` — `api_error` → `PUBLIC_ERROR_MESSAGES[code]`,
  `fetch_failed` → `FETCH_FAILURE_MESSAGE`; never the API `message`/request id.
  Directly unit-tested. No `@pca/shared` copy constants added (none needed).
- **Caching/rendering:** identical to 14.1 — no route-segment `dynamic`/`revalidate`
  override; the 11.2 client's plain `fetch` governs caching. Site stays noindex.
- **Files touched:**
  `apps/web/app/methodology/page.tsx` (rewrite),
  `apps/web/app/methodology/MethodologyView.tsx` (new),
  `apps/web/app/methodology/MethodologyView.test.tsx` (new),
  `apps/web/app/methodology/methodology-copy.ts` (new),
  `apps/web/app/methodology/methodology-copy.test.ts` (new),
  `apps/web/app/methodology/methodology-failure.ts` (new),
  `apps/web/app/methodology/methodology-failure.test.ts` (new),
  `apps/web/app/methodology/loading.tsx` (new),
  `apps/web/app/data-coverage/page.tsx` (rewrite),
  `apps/web/app/data-coverage/DataCoverageView.tsx` (new),
  `apps/web/app/data-coverage/DataCoverageView.test.tsx` (new),
  `apps/web/app/data-coverage/data-coverage-copy.ts` (new),
  `apps/web/app/data-coverage/data-coverage-copy.test.ts` (new),
  `apps/web/app/data-coverage/data-coverage-failure.ts` (new),
  `apps/web/app/data-coverage/data-coverage-failure.test.ts` (new),
  `apps/web/app/data-coverage/loading.tsx` (new),
  `apps/web/app/lib/formatters.ts` (export `formatDateOnly`),
  `apps/web/app/lib/formatters.test.ts` (add `formatDateOnly` cases),
  `tasks/worklog.md`.
- **How to verify:** `pnpm run build:packages`, then `pnpm --filter web run typecheck`,
  `pnpm run lint`, `pnpm run format:check`, `pnpm --filter web run test`.
- **Gates — all green:** web typecheck 0; web tests 173 passed (42 files, +30 from
  the new suites); eslint 0; prettier clean; copy guard + copy-safety suites green.
- **Deviations from plan:** none. The only non-page/non-test edit is the approved
  `formatDateOnly` export in `formatters.ts`. No API/payload, `@pca/shared`, or
  definitions (14.1) changes.
- **Notes for next task:** About page (14.3) follows the same server-fetch +
  presentational-view + per-arm-error shape. The failure-mapper logic is now
  duplicated three ways (definitions/methodology/data-coverage) as identical
  one-liners, kept page-local per scope discipline; if a fourth consumer appears,
  a single shared `app/lib` mapper would be worth consolidating. Accessibility
  sweep + E2E for these routes is Phase 15.

## Task 14.3 — About Page

- **Date:** 2026-07-09
- **What was built:** Replaced the 4.1 placeholder `/about` route with the final
  Phase 14 content page: a static server component (no data fetch, no View split,
  no loading/error state) with a single `h1` and four `h2` sections — What this
  site is / Where the data comes from / How to read the numbers / Responsible use
  — using the verbatim task copy, followed by a `Content pages` nav linking
  `/methodology`, `/definitions`, `/data-coverage`. The Responsible Use section
  renders the existing shared `<ResponsibleUseNotice />` (the four
  `RESULT_DISPLAY_COPY` framing statements); the only newly authored
  disclaimer-adjacent sentence is the required attorney-consultation line. Layout
  tokens mirror `MethodologyView` (single-column, mobile-first, `text-ink` /
  `text-muted`, shared `LINK_CLASS` focus-visible ring). One render test
  (vitest + testing-library) asserts the h1, all four section h2s, the shared
  responsible-use framing (via imported `RESULT_DISPLAY_COPY`, not re-typed
  disclaimer text), and the three content-page links by href.
- **Files touched:** `apps/web/app/about/page.tsx` (replace placeholder),
  `apps/web/app/about/AboutPage.test.tsx` (new), `tasks/worklog.md`.
- **How to verify:** `pnpm --filter @pca/web test`, then `pnpm lint`,
  `pnpm format:check`, `pnpm typecheck`.
- **Gates — all green:** web tests 177 passed (43 files, +4 from the new suite);
  copy-guard + copy-safety suites green; eslint 0; prettier clean; full-workspace
  typecheck 0.
- **Scanner-driven copy adjustments:** none. The verbatim task copy passed the
  copy-safety scanner unchanged (no forbidden stems; "small samples are flagged"
  is statistical sample-size language, not a seeded/demo-data disclosure; the
  shared component's "not a prediction"/"not legal advice" strings are guarded
  phrases).
- **Deviations from plan:** none. No nav/layout change — `/about` was already in
  `NAV_LINKS`. No API endpoint, no `@pca/shared` additions.
- **Notes for next task:** `/about` is intentionally the only content page with
  no `-copy.ts` module (copy is inline JSX, covered by the app/-walking copy
  guard) and no server-fetch/error shape, since it has no data source. Team/
  contact/credits content and SEO/indexing remain out of scope (site-wide
  noindex stands).

## Task 15.1 — Accessibility + Mobile Pass (Cross-Cutting Sweep)

- **Date:** 2026-07-10
- **What was built:** A static (code) accessibility + mobile audit of every public
  page, state, and shared component against the task checklist (WCAG 2.2 AA), with
  findings fixed and documented in `agent-docs/a11y-mobile-pass.md`; then fixes for
  the three functional findings from Chops's human keyboard/mobile walkthrough.
- **Agent-audit finding (1, fixed):** the two terminal not-found states rendered no
  `h1` while every other state carries one. Added an `<h1>` to `not-found.tsx` and
  `ResultNotFoundView.tsx`, sourced from a new `CHARGE_RESULT_COPY.notFoundHeading`
  ("Result not found"); added heading assertions to both suites. Every other
  checklist section passed clean (landmarks, table `th`/`scope`, visibly-rendered
  paired tables with `aria-hidden` bars, text bar values via 11.4 formatters,
  text-accessible thin-data, combobox ARIA + arrow/Enter/Escape, 13.2/13.3 DOM
  order, 320px-safe with no fixed widths, no `outline-none`/positive-tabindex/
  hover-only/color-only — grep-proven).
- **Walkthrough findings (3, fixed):**
  - **W1 (highest):** the judge route had no mapping for the `CHARGE_RESULT_UNAVAILABLE`
    404 error envelope (charge with no aggregate), so a designed state fell through
    to the generic error boundary. Added a `charge-unavailable` state to
    `resolveJudgeResultState`, a new `JudgeChargeUnavailableView` (adapts the 13.2
    unavailable pattern; the 404 envelope carries no identity/links, so it renders
    the pinned `CHARGE_RESULT_UNAVAILABLE_MESSAGE` + a generic heading + static
    methodology/definitions links), and wired it into the judge page before the
    generic throw. Audited the full code-to-state mapping for BOTH result routes
    (enumerated in the report) — this was the only unmapped designed-state gap.
  - **W2:** `API_BASE_URL` resolved inconsistently — the rewrite defaulted to
    `localhost:3001` but the server client threw. Unified on a single shared
    local-dev default via new `app/lib/api-base-url.ts` (`resolveApiBaseUrl`), used
    by both `next.config.ts` and the server fetch path. Chose shared-default over
    fail-fast (rationale in report: matches the already-working browser path + CI
    build assumption; prod hardening stays Sprint 9).
  - **W3:** documented the (now-optional) `apps/web` `API_BASE_URL` in
    `apps/web/README.md`, the `apps/web/.env.example` comment, and a root README
    "Environment files" note.
- **Files touched:** `apps/web/app/charges/[chargeSlug]/not-found.tsx` (+test),
  `apps/web/app/components/ResultNotFoundView.tsx` (+test),
  `apps/web/app/components/charge-result-copy.ts`,
  `apps/web/app/components/JudgeChargeUnavailableView.tsx` (new, +test),
  `apps/web/app/charges/[chargeSlug]/judge/[judgeSlug]/judge-result-state.ts`
  (+test), `.../judge/[judgeSlug]/page.tsx`,
  `apps/web/app/lib/api-base-url.ts` (new, +test),
  `apps/web/app/lib/public-api-client.ts`, `apps/web/next.config.ts`,
  `apps/web/.env.example`, `apps/web/README.md`, `README.md`,
  `agent-docs/a11y-mobile-pass.md` (new), `tasks/worklog.md`.
- **Copy-safety call-out:** two app-level copy constants added (`notFoundHeading`,
  `chargeUnavailableHeading` in `charge-result-copy.ts`) — both scanned by
  `charge-result-copy.test.ts` via `scanPublicCopy`, both pass; no `@pca/shared`
  copy touched.
- **Deviations from plan:** W1–W3 are functional (not strictly a11y) and reach
  beyond the task's original "Files you may touch" list (config: `next.config.ts`,
  `apps/web/.env.example`; docs: root + `apps/web` README). Fixed here at Chops's
  explicit direction under the task's two-halves structure; called out as
  authorized deviations.
- **Gates — all green:** eslint 0; prettier clean; full-workspace typecheck 0;
  tests — web 183 (45 files, +6), api 198, shared 166 (copy-safety), taxonomy 14,
  db 6; forbidden-field (`apps/api/src/public-forbidden-fields.test.ts`) green. No
  new dependencies (Playwright/axe-core remain 15.2).
- **Notes for next task (15.2 — E2E + axe-core):** axe should confirm one `h1` per
  page/state (the not-found fix is the only heading change) and combobox ARIA
  toggling live; add an E2E for the W1 judge-route charge-unavailable path
  (`/charges/harassment/judge/{slug}` → friendly view, not the error boundary);
  loading placeholders intentionally have no `h1` (transient `role="status"`) — not
  a violation to flag; the `localhost:3001` local-dev default (now in
  `app/lib/api-base-url.ts`) is what lets result pages render without `API_BASE_URL`
  set. Input focus rings rely on the UA default — worth a visual/axe confirmation.

## Task 15.2 — Playwright E2E + axe-core + CI E2E Job

- **Date:** 2026-07-10
- **What was built:** A chromium Playwright suite (`e2e/`, new `@pca/e2e`
  workspace package) that walks every public flow against a REAL seeded DB, the
  API booted from built `dist` under plain node, and the web app booted from a
  production `next build`/`next start`. On every visited page/state it asserts
  (1) axe-core WCAG 2.2 AA (tags `wcag2a,wcag2aa,wcag21a,wcag21aa,wcag22aa`),
  (2) rendered-copy safety via `scanPublicCopy`, and (3) rendered-page privacy
  via the relocated `scanForForbidden`. Plus a dedicated required-ready CI `e2e`
  job. 15 tests, all green.
- **Suite coverage (15 tests):** homepage (charge primary / judge optional);
  charge autocomplete keyboard select (ArrowDown+Enter) → charge-only result;
  charge-only data-bearing (outcome table + bars, sentencing, sample size, date
  range, responsible-use); thin-data charge; sentencing-unavailable charge; add
  judge → judge-specific (judge dist + Philadelphia baseline, separate sample
  sizes) → remove filter → charge-only; judge-unavailable pair (200 arm);
  **W1 regression lock** (`/charges/harassment/judge/judge-testina-placeholder`
  → friendly `CHARGE_RESULT_UNAVAILABLE` view, not the error boundary);
  charge-only unavailable; not-found; definitions/methodology/data-coverage
  (asserts the 2025-01-01 start) / about; 390px mobile content-order + no
  horizontal scroll. Pinned messages asserted via `@pca/shared` imports only;
  seed slugs centralized in `e2e/support/constants.ts` (read off `db/seeds/`).
- **ForbiddenViolation checker relocation (approved):** moved
  `apps/api/src/test-support/forbidden-scan.ts` (+ its self-test) to
  `packages/shared/src/forbidden-scan.{ts,test.ts}`, exposed via a new
  `@pca/shared/forbidden-scan` subpath export (standard types/pca-source/default
  triple). The 10.1 suite (`apps/api/src/public-forbidden-fields.test.ts`) now
  imports from there; behavior is byte-for-byte identical (only the import path
  changed). No term/field list is duplicated anywhere. The probe registry stayed
  in `apps/api/src/test-support`.
- **webServer + CI:** Playwright `webServer` starts API (`pnpm --filter @pca/api
  run start`, readiness `GET /health`, port 3001) and web (`next start`, port
  3000, `API_BASE_URL` set explicitly). New CI `e2e` job: install → generate →
  build:packages → build api → migrate → real `pnpm db:seed` → build web → cached
  `playwright install` → run suite; `postgres:17.10`, env-driven DB (CI 5432, no
  hardcoded port), `retries: 0`, `forbidOnly` in CI. Root `pnpm test:e2e`
  orchestrates the local build+run; `test:e2e` (not `test`) keeps E2E out of the
  node unit-test sweep; `@pca/e2e` has a `typecheck` script so the root `-r`
  typecheck covers it.
- **F4 (build-time prerender) — resolved favorably:** `next build` passes offline
  (no API). The content pages render LIVE API content at runtime under
  `next start` (verified green in the suite), not a baked error state.
- **Authorized in-scope deviation (a11y fix in apps/web):** the first automated
  axe run against RENDERED pages caught a real WCAG 1.4.1 (Use of Color, Level A)
  `link-in-text-block` defect on the homepage: the two intro-paragraph links
  (Methodology, Data Coverage) used `hover:underline` (underline on hover only),
  so link meaning relied on color at rest (1.13:1 vs surrounding text). Notably
  this passed the 15.1 static a11y audit, which explicitly checked for hover-only
  meaning — evidence for the value of the rendered-page axe gate. Fixed per
  Chops's explicit authorization (class-only: `hover:underline` → `underline` on
  the two links in `apps/web/app/page.tsx`); no copy change, no other apps/web
  edits. Re-ran the full suite: 15/15 green, homepage `link-in-text-block`
  resolved (the fix satisfies the rule, not suppresses it — all WCAG tags still
  run). No web component test asserted the old class string.
- **Files touched:** `e2e/*` (new: package.json, tsconfig.json,
  playwright.config.ts, support/{constants,checks,combobox}.ts, tests/*.spec.ts,
  README.md); `packages/shared/src/forbidden-scan.{ts,test.ts}` (moved),
  `packages/shared/package.json` (subpath export);
  `apps/api/src/public-forbidden-fields.test.ts` (import path);
  removed `apps/api/src/test-support/forbidden-scan.{ts,test.ts}`;
  `apps/web/app/page.tsx` (authorized a11y fix); `pnpm-workspace.yaml`,
  `package.json` (`test:e2e`), `.github/workflows/ci.yml` (e2e job), `README.md`,
  `.gitignore` + `.prettierignore` (Playwright artifacts), `pnpm-lock.yaml`,
  `tasks/worklog.md`.
- **New dependencies (task-authorized):** `@playwright/test` (1.61.1),
  `@axe-core/playwright` (4.12.1), `@types/node`, all devDeps of `@pca/e2e`.
- **Gates — all green:** eslint 0; prettier clean; full-workspace typecheck 0
  (incl. `@pca/e2e`); taxonomy valid; tests — web 183 (45 files), api 26-file
  forbidden suite green via the new import, shared 14 files (incl. relocated
  `forbidden-scan.test.ts`, 22 tests), db, taxonomy; E2E 15/15. Python untouched.
- **Runtime:** local end-to-end `pnpm test:e2e` (build packages + api + web +
  server boot + 15 tests) ≈ 16s wall; the suite alone ≈ 6s. The CI `e2e` job is
  dominated by `pnpm install` + Playwright browser provisioning (cached after the
  first run); estimated ~3–5 min, well under the 15-min budget. The exact CI
  runtime cannot be measured locally (GitHub Actions is not runnable here) and
  will be confirmed on the first CI run.
- **Notes for next task:** the branch-protection "required check" for the `e2e`
  job is a GitHub setting the human enables. The content pages are marked
  `○ (Static)` in the `next build` summary but serve live content at runtime;
  if a future change makes them truly static, the E2E content assertions would
  catch a baked error state.

## Task 15.2 (follow-up) — Content pages render dynamically (build-time prerender fix)

- **Date:** 2026-07-10
- **CI failure:** the CI `e2e` job failed — `/definitions`, `/methodology`, and
  `/data-coverage` rendered their ERROR states. Root cause: these are async
  server components that fetch the API, and with no route-segment override Next
  statically prerendered them during `next build` (which runs before any API
  exists in the CI job), baking the error state into the static HTML.
- **Clean reproduction:** killed all servers, `rm -rf apps/web/.next`, ran
  `next build` with the API down. Route table showed the three pages as `○`
  (Static); the prerendered HTML (`.next/server/app/{definitions,methodology,
  data-coverage}.html`) contained `<h1>… is unavailable</h1>` — confirmed baked
  error states.
- **F4 correction (supersedes the "resolved favorably" claim):** the original
  15.2 F4 verification was a FALSE POSITIVE. A leftover API server from a prior
  `pnpm test:e2e` run was still listening on :3001 during that build, so the
  build-time prerender fetch SUCCEEDED and baked real content. Local `next build`
  can also serve cached fetch data from `.next/cache`. **Any claim about
  build-time behavior requires a clean build (`rm -rf apps/web/.next`) with all
  servers stopped.** The CI `e2e` job is the authority on production-build
  behavior precisely because it always builds clean.
- **Fix (authorized):** added `export const dynamic = 'force-dynamic'` to
  `apps/web/app/{definitions,methodology,data-coverage}/page.tsx`. Chose
  force-dynamic over a no-store fetch because the pages were being statically
  prerendered regardless, and force-dynamic unambiguously forces per-request
  rendering. Rationale: the publication model separates deploys from data
  publication; these pages carry live published-run metadata (lastRefreshed,
  coverage dates) and must never be baked at build time. Updated the now-stale
  "no route-segment dynamic/revalidate override" comments in the methodology and
  data-coverage pages accordingly.
- **Audit (route table after fix):** `/definitions`, `/methodology`,
  `/data-coverage` now `ƒ` (Dynamic); `/charges/*` already dynamic via params.
  Remaining static routes (`/`, `/about`, `/admin`, `/_not-found`) make NO
  server-side API fetch (verified by grep), so static prerender is correct for
  them. No static route prerenders an API fetch.
- **Files touched:** `apps/web/app/definitions/page.tsx`,
  `apps/web/app/methodology/page.tsx`, `apps/web/app/data-coverage/page.tsx`,
  `tasks/worklog.md`.

## Task 15.3 — Sprint 3 exit demo + sprint close (human step, worklog only)

- **Date:** 2026-07-10
- **What happened:** Human exit demo run by Chops. All ten demo steps passed;
  Sprint 3 is closed. No code, config, copy, or test changes — bookkeeping only.
- **Exit demo — ten steps, all PASS:**
  1. Homepage charge search ("retail") → suggestions → charge-only result.
  2. Distributions as table + bars, counts + percentages together, sample size,
     date range, last refreshed.
  3. Thin-data charge (Criminal Trespass) renders "Based on a small sample."
  4. Judge-specific result beside Philadelphia baseline, separate sample sizes,
     neutral labels.
  5. Remove-filter action routes back to charge-only result.
  6. Judge-unavailable pair renders the pinned `@pca/shared` fallback message;
     W1 harassment judge-route state confirmed.
  7. Sentencing-unavailable charge: outcome persists, callout renders.
  8. `/definitions`, `/methodology`, `/data-coverage` render API content;
     2025-01-01 start date and seeded-data disclosure visible as served.
  9. Mobile viewport: pinned content order correct, no horizontal scroll.
  10. Full CI green on main including the e2e job.
- **Sprint 3 quality-gate yield (for the record):** the E2E gate caught three
  real defects before sprint close — (1) the W1 judge-route regression,
  (2) the homepage Level A color-only-meaning defect, and (3) the content-page
  build-time prerender baking (fixed via `force-dynamic`). The gate paid for
  itself: three production-visible defects surfaced and fixed pre-close.
- **Files touched:** `tasks/worklog.md`, `tasks/current-task.md` (cleared to a
  one-line "No active task" placeholder).
- **Deviations from plan:** none — no code changes.
- **Notes for next task:** Sprint 4 planning in progress; `current-task.md`
  holds the "No active task" placeholder until the next task is assigned.

---

## Task 16.1 — Helpers + Identity Port (Capstone → pipeline)

- **Date:** 2026-07-10
- **What was built:** Ported Capstone's `helpers.py` and `identity.py` into the
  `pipeline` package with behavior preserved exactly, severing the `config.py`
  dependency and all import-time side effects. Foundation layer for the
  Sprint 4 parser port.
  - `services/pipeline/src/pipeline/helpers.py`: `parse_date`, `to_days`,
    `GRADES`, `ParseError`, `_UNIT_DAYS` — verbatim (day=1/month=30/year=360;
    360-day-year documented, no 365 doc drift).
  - `services/pipeline/src/pipeline/identity.py`: `normalize_name`,
    `hash_defendant`, `_iter_values`, `assert_no_leak`, `RELATED_CASE_KEYS`,
    `assert_related_cases_clean`. Dropped `from src.config import ...`.
  - Tests: 13 ported helper/identity tests (`test_helpers.py`), 2 ported
    `assert_related_cases_clean` tests + new salt/allowlist tests
    (`test_identity.py`), and a fresh-import side-effect test
    (`test_import_side_effects.py`). Full pipeline suite: 55 passed. ruff lint
    and format clean.
  - `.env.example`: documented `DEFENDANT_HASH_SALT` (required, no default,
    stable across runs, never committed).
- **Behavioral differences from Capstone (exactly the two approved):**
  1. `hash_defendant` now takes salt as a **required keyword-only** parameter:
     `hash_defendant(name: str, birth_year: int, *, salt: str)`. Basis string
     `f"{salt}|{normalize_name(name)}|{birth_year}"` unchanged. Missing/None/
     empty salt raises `ValueError` naming `DEFENDANT_HASH_SALT` and the salt
     parameter; the message contains no name, birth year, or docket data.
     Capstone's silent `"change-me-in-env"` fallback is gone.
  2. No import-time side effects: modules read no env, load no dotenv, create
     no directories, touch no filesystem. Proven by a fresh-import test that
     evicts each module from `sys.modules` and re-imports under guards that
     raise on `os.getenv` / `Path.mkdir`.
- **Files touched:** `services/pipeline/src/pipeline/helpers.py` (new),
  `services/pipeline/src/pipeline/identity.py` (new),
  `services/pipeline/tests/test_helpers.py` (new),
  `services/pipeline/tests/test_identity.py` (new),
  `services/pipeline/tests/test_import_side_effects.py` (new),
  `.env.example`, `tasks/worklog.md`.
- **Deviations from plan:** none behavioral. Ruff format rewrapped a few long
  lines in the two modules and one test dict literal (cosmetic only).
- **Notes for next task (source-path discrepancy):** the task named the
  Capstone source at `~/court-data/capstone-src/`, which does not exist. The
  authoritative source was found at `~/Desktop/Capstone/` (`src/parse/helpers.py`,
  `src/identity.py`, `tests/test_helpers.py`, and the two
  `assert_related_cases_clean` tests inside `tests/test_mc_parser.py`).
  Future Sprint 4 port tasks should reference `~/Desktop/Capstone/`. No
  additional Capstone couplings or quirks surfaced beyond the config
  dependency already removed.

## Task 16.2 — Production Extraction Stage + Text Artifacts

- **Date:** 2026-07-10
- **What was built:** the real `extract-text` stage replacing the Sprint 1
  placeholder. PDF → ordered per-page text + one JSON artifact per source PDF
  written outside the repo, with low-text/image-only detection, the fixed
  status vocabulary, and no-raw-text logging discipline.
  - `services/pipeline/src/pipeline/extraction.py` (new): `extract(pdf_path,
    *, low_text_threshold=100) -> ExtractionResult` using
    `page.extract_text() or ""` with **default arguments** (fidelity to
    Capstone for the 17.1 seam — no parameter deviation). `compute_text_hash`
    (decision 7: sha256 of page texts joined by `\x0c`), `build_artifact`,
    `artifact_filename` (`<full-sha256>.json`), and the `run_extraction` run
    boundary (dir resolution/creation + git-worktree refusal here, never at
    import; counts-by-status to stdout; logs carry ids/counts/status/pages/
    durations only). Status/warning constants and provisional warning codes
    (`low_text_page`, `empty_page`) defined here with a docstring note that
    18.1 owns the unified vocabulary.
  - `services/pipeline/src/pipeline/paths.py` (new): neutral, dependency-free
    home for `inside_git_worktree`. Moved out of `evaluation/harness.py`;
    both the harness and `extraction.py` now import it from here (no
    duplicated copy — per plan-review fix #1).
  - `services/pipeline/src/pipeline/evaluation/harness.py`: dropped the local
    `inside_git_worktree`, imports it from `pipeline.paths`. The name is still
    re-exported through the harness namespace, so
    `test_evaluate_extractors`'s import is unaffected.
  - `services/pipeline/src/pipeline/cli.py`: `extract-text` gains a `path`
    positional (PDF or dir), `--output-dir` (default
    `~/court-data/extracted/`, resolved at the run boundary), and
    `--threshold`; dispatches to `run_extraction`. `PLACEHOLDER_COMMANDS` now
    derives from a new `IMPLEMENTED_COMMANDS` set (adds `extract-text`).
  - `services/pipeline/pyproject.toml` + `uv.lock`: pinned
    `pdfplumber==0.11.10` (lock already resolved 0.11.10; specifier updated to
    `==`). pymupdf/pypdf ranges unchanged (eval-harness-only, ADR 0001).
  - Tests: `tests/test_extraction.py` (new, 16 tests) — multi-page success
    (order/texts/counts/hash), empty-page + low-text warnings, partial and
    needs_ocr_or_review paths, `--threshold` override, threshold-compares-
    stripped-not-raw (plan-review fix #2), text-hash determinism + order
    sensitivity, unreadable→failed artifact with `text_hash: null` and no
    text/no raise (plan-review fix #3), artifact schema completeness,
    directory run + counts-by-status summary, git-worktree output refusal,
    no-raw-text-in-logs/console, and the static AST assertion that no
    production module (everything under `src/pipeline` except `evaluation/`)
    imports pymupdf/pypdf/fitz. `test_import_side_effects.py` adds
    `pipeline.extraction` to its fresh-import guard. Full suite: 70 passed;
    ruff lint + format clean. Verified end-to-end via a real CLI run into an
    out-of-repo dir (logs id-only, one artifact per file, version 0.11.10).
- **Plan-review fixes applied:** (1) worktree guard moved to shared
  `paths.py`, imported by both callers — no copy, no deferred unify;
  (2) status/warning decisions compare `len(text.strip())` while the artifact
  records raw `len(text)` as `per_page_chars` — split documented in the module
  docstring and covered by a dedicated test; (3) `failed` artifacts carry
  `text_hash: null` — stated in the module docstring and asserted in the
  unreadable-file test.
- **Threshold default:** 100 stripped chars per page, configurable via
  `--threshold`. Rationale: real docket pages run hundreds–thousands of chars;
  image-only/near-blank pages yield 0–a-few, so 100 sits far below content
  pages yet above OCR-needed noise.
- **Deviations from plan:** none behavioral. Ruff rewrapped a couple of long
  lines (cosmetic).
- **Notes for next task:** 17.1 will compare this stage's page text against
  Capstone reference text on the same PDFs — the extraction call is
  `page.extract_text() or ""`, default args, pdfplumber `==0.11.10`; re-pin
  there if the comparison forces it. 18.1 should absorb/align the provisional
  `low_text_page`/`empty_page`/`unreadable_pdf` codes into the unified
  vocabulary. `paths.inside_git_worktree` is now the shared output guard for
  any future stage that writes artifacts.

## Task 16.3 — Manual Import: Content Hashing, Dedupe, Metadata

- **Date:** 2026-07-10
- **What was built:** The real `import-manual` stage replacing the Sprint 1
  placeholder. `manual_import.py` flat-scans a directory, streams sha256
  hashes (1 MiB chunks — multi-MB PDFs never load whole), validates by
  extension + `%PDF-` magic bytes, dedupes by content hash across runs, and
  writes one hash-keyed `<sha256>.json` metadata record per file under a
  worktree-guarded root (default `~/court-data/imports/`), plus a counts-only
  `import-report.json` (overwritten each run). Records carry the full pinned
  field set (`id`, `original_filename`, `file_hash`, `file_size_bytes`,
  `imported_at`, `mode`, `docket_number_provenance`, `court_type`, `county`,
  `status`, `error_code`); `id` is the full sha256 (== `file_hash`).
  Provenance derives from the filename stem via the Philadelphia UJS pattern
  `^(CP|MC)-(\d{2})-[A-Z]{2}-\d{7}-\d{4}$` (court code + 2-digit county);
  non-matching stems degrade all three provenance fields to null — never
  guessed. `cli.py` wires the subcommand (positional input dir,
  `--metadata-root` override) and moves it into `IMPLEMENTED_COMMANDS`.
- **Files touched:** `services/pipeline/src/pipeline/manual_import.py` (new),
  `services/pipeline/src/pipeline/cli.py` (subcommand wiring),
  `services/pipeline/tests/test_manual_import.py` (new, 11 tests),
  `services/pipeline/tests/test_import_side_effects.py` (added
  `pipeline.manual_import` to the fresh-import guard), `tasks/worklog.md`.
  No `paths.py` change (existing `inside_git_worktree` sufficed); no new
  dependencies (stdlib only).
- **Status semantics:** exactly one of `imported` / `duplicate` / `invalid` /
  `failed` per file. Per-file flow: wrong extension → `invalid`, skipped, NO
  record; unreadable (OSError) → `failed`, counted only, no record (no hash to
  key by; sanitized to the OS error *class name* only); `.pdf` with bad magic
  bytes → `invalid` WITH a hash-keyed record; existing hash → `duplicate`
  (original record immutable, never overwritten); else → `imported`.
- **Deliberate invalid-content dedupe (approved adjustment):** a
  bad-magic-bytes file writes a hash-keyed record, so re-importing it counts as
  `duplicate` and the record retains status `invalid`. Documented in the module
  docstring and covered by a test (import → invalid; re-import → duplicate,
  record byte-identical).
- **Privacy:** console prints only the counts summary
  (`imported=N duplicate=N invalid=N failed=N`); logs (stderr JSON) carry
  counts/statuses only — never filenames, stems, paths, or content. Per-file
  detail (incl. `original_filename` and the provenance stem) lives only in the
  out-of-repo records. Proven by a sentinel-stem test asserting the name never
  reaches captured stdout/stderr/caplog across every status path.
- **Deviations from plan:** none. All four approved adjustments applied
  (wrong-extension no-record; single overwritten report; invalid-content
  dedupe documented + tested; unreadable test skips under `os.geteuid() == 0`
  since root ignores permission bits).
- **Verification:** full suite 81 passed; ruff clean. Exercised end-to-end via
  the installed `pipeline` console script into an out-of-repo dir:
  imported/invalid split correct, re-run all-duplicate (bad-magic PDF →
  duplicate, record-less `.txt` → invalid again), worktree guard exits 2 and
  creates nothing, logs id/status-only.
- **Notes for next task:** the parser stage takes `docket_number` as an
  explicit parameter — it should read it from the record's
  `docket_number_provenance` (or a caller override), never re-derive from a
  filename. The `wrong_extension` / `bad_magic_bytes` / `unreadable_file`
  codes are import-stage-local; 18.1's unified warning/error vocabulary may
  absorb them. `python -m pipeline.cli` is a no-op (no `__main__` block); use
  the `pipeline` console script or `pipeline.cli:main`.

## Task 17.1 — Extraction-Seam Equivalence Check

- **Date:** 2026-07-10
- **What was built:** A `seam-check` CLI command plus a `seam_check` comparator
  module that proves the Task 16.2 production extraction reproduces Capstone's
  pdfplumber reference text line-for-line. The comparator imports and calls the
  *same* production function (`pipeline.extraction.extract`) — no
  reimplementation. Per docket it runs the decision-4 order: (a) source-hash
  gate (mismatch → `failed`/`hash_mismatch`, no diff), (b) page-count equality
  (→ `divergent` with a `page_count` divergence), (c) per-page line-level exact
  compare (`split("\n")`, no normalization). Outcome vocabulary: exactly one of
  `equivalent` / `divergent` / `failed` / `missing_reference` per PDF, with
  `failed` reasons `hash_mismatch` / `malformed_reference` / `extraction_failed`
  / `exception`. Reference files are shape-validated (`source_file`, `sha256`,
  `pdfplumber_version`, `pages`); malformed ones are loud per-docket failures,
  not run-aborting. Both pdfplumber versions (ours from the installed package,
  Capstone's from the reference files) are captured in the report header with a
  `version_mismatch` flag. Two out-of-repo artifacts are written under
  `--report-dir`: `seam-report.json` (machine-readable, includes differing line
  content) and `seam-report.txt` (human summary, positions only). CI runs unit
  tests only; a `seam-check` invocation in a CI environment refuses loudly.
- **Files touched:** `services/pipeline/src/pipeline/seam_check.py` (new),
  `services/pipeline/src/pipeline/cli.py` (subcommand wiring + CI guard),
  `services/pipeline/tests/test_seam_check.py` (new, 14 tests),
  `services/pipeline/tests/test_import_side_effects.py` (added
  `pipeline.seam_check` to the fresh-import guard). No dependency changes; no
  `pyproject.toml`/`uv.lock` edit.
- **Privacy decision (approved amendment to task decision 7):** the spec's
  "docket stems allowed in console/log" wording was a defect — docket numbers
  are defendant-identifying. Console/logs carry only counts, statuses,
  hash-prefix ids, and page/line numbers (matching the `extraction.py` /
  `harness.py` precedent). Docket stems and divergence content live only in the
  out-of-repo report artifacts; `seam-report.txt` keeps stems (out-of-repo) with
  hash-prefix ids alongside for cross-referencing logs. Asserted by a test that
  a synthetic sentinel *and* the docket stem never reach stdout/stderr, while the
  sentinel does reach `seam-report.json` (and not `seam-report.txt`).
- **CI guard placement:** the guard lives in the CLI handler (the actual corpus
  run), not in `run_seam_check`, so unit tests that call `run_seam_check`
  directly on synthetic tmp dirs still pass under CI (`CI=true`). Detects `CI`
  or `GITHUB_ACTIONS`, read at the run boundary (never at import). A dedicated
  test drives `cli.main` with `CI=true` and asserts exit 2 with nothing written.
- **Deviations from plan:** none. CP/MC classification reuses the canonical
  `DOCKET_NUMBER_RE` from `manual_import` (single source of truth); non-matching
  stems bucket as `unknown`. Exit code is 0 on any completed run regardless of
  divergences (decision 9 — the tool reports, does not decide).
- **Verification:** all three pipeline gates green — `ruff check src tests`
  clean, `ruff format --check .` clean, `pytest -q` 100 passed (14 new). No real
  docket content, PDFs, or reference text in the repo; tests use synthetic
  pymupdf PDFs and hand-built reference JSON in `tmp_path` only.
- **Notes for next task (17.2 parser port):** the comparator's exit is a
  recorded outcome, not a decision — triage of any divergence class (accept /
  re-pin pdfplumber / adjust) is human work and, if the pin changes, lands in
  `uv` deps. The reference dir may contain a `_failures.txt` written by the
  reference-dump script; the per-PDF `{stem}.json` lookup never touches it, so
  its presence is harmless. If a corpus run reports zero divergences, the
  extraction seam is proven stable and 17.2 can port parser heuristics against
  16.2 output with confidence.
- **17.1 corpus run result (human-executed, 2026-07-10):** full corpus seam
  check over 1,596 fixtures (1,556 CP + 40 MC). Result: 1596 equivalent, 0
  divergent, 0 failed, 0 missing_reference. pdfplumber 0.11.10 on both sides;
  version_mismatch: False. Triage decision: zero divergences — accepted, no
  re-pin, no adjustment. The extraction seam is proven equivalent over the full
  working corpus; 17.3 divergences, if any, are attributable to parser logic
  only. Report artifacts at `~/court-data/seam-report/` (out-of-repo).

## Task 17.2 — Faithful Parser Port (`parse_docket_text` + `parse_docket`)

- **Date:** 2026-07-10
- **What was built:** A behavior-preserving port of Capstone's
  `src/parse/docket_parser.py` (626 LOC) into the pipeline package. The pure
  parsing surface — `parse_docket_text`, plus `is_statute_token`,
  `match_association_reason`, `parse_related_cases`, `detect_court_type`, and
  the module constants — lives in `pipeline.docket_parser` (stdlib only, no
  pdfplumber anywhere in its module path, per acceptance criterion 1). The
  PDF-opening wrapper `parse_docket` lives in `pipeline.docket_parser_pdf`.
  Every quirk ported UNCHANGED (defect inventory below). The parser imports the
  16.1 ported `pipeline.helpers` (GRADES, ParseError, parse_date, to_days) and
  `pipeline.identity` (hash_defendant, assert_no_leak,
  assert_related_cases_clean); it re-declares none of them.
- **Files touched:**
  - `services/pipeline/src/pipeline/docket_parser.py` (new, pure stdlib) —
    `parse_docket_text` + pure helpers + `parse_docket_checked` boundary.
  - `services/pipeline/src/pipeline/docket_parser_pdf.py` (new) — `parse_docket`
    with Capstone's plain pdfplumber loop.
  - `services/pipeline/tests/test_docket_parser.py` (new) — 8 ported tests + 3
    added (2 boundary, 1 ParseError-content).
  - `services/pipeline/tests/test_import_side_effects.py` — added
    `pipeline.docket_parser` and `pipeline.docket_parser_pdf` to the guard.
  - No dependency changes; no `pyproject.toml` / `uv.lock` edit.
- **Approved design decisions (from the plan):**
  - **Salt threading.** Capstone's `hash_defendant(name, birth_year)` read
    `DEFENDANT_HASH_SALT` from `config.py` at import; the 16.1 port severed that
    and made `salt` a required keyword-only parameter with no env read. So the
    port threads a caller-supplied keyword-only `salt` through both entry points
    (`parse_docket_text(docket_number, pages_text, *, salt)` and
    `parse_docket(pdf_path, docket_number, *, salt)`) straight to
    `hash_defendant`. The positional signature in criterion 1 is preserved. The
    parser does NO salt validation of its own — `hash_defendant`'s own
    required-salt check fires instead.
  - **`docket_number` is an explicit parameter** on `parse_docket`, never
    derived from `pdf_path.stem` (task decision 4). Filename provenance is the
    import stage's business.
  - **Module split.** `parse_docket` sits in its own module so
    `docket_parser.py` stays pdfplumber-free. `parse_docket` uses Capstone's
    plain `pdfplumber.open` → per-page `extract_text() or ""` loop and is
    deliberately NOT routed through `pipeline.extraction`: the 16.2 stage
    carries threshold/status logic Capstone never had, so fidelity means
    porting Capstone's own loop even though 17.1 proved the extraction seams
    equivalent. Both new modules are in the fresh-import side-effect guard.
  - **Sentinel boundary.** Capstone wires it in `scripts/parse_fixtures.py`
    (lines 26–29: `parse_docket` → `assert_no_leak` → `assert_related_cases_clean`
    → write), a script bound to config/db and outside this task's allowed files.
    Ported as `parse_docket_checked` in `docket_parser.py`: the same three
    calls minus IO. The assertions stay OUT of `parse_docket_text` so parse
    behavior is unchanged; `parse_docket_checked` is the seam a writer (17.3
    comparator, later loader) calls pre-persist.
- **Defect inventory — ported UNCHANGED, flagged for Phase 18 (line refs are
  in `pipeline/docket_parser.py`):**
  - Disposition truncation via offense/statute/grade prefix-strip
    (`parse_docket_text`, the `charge_match` block) → 18.2.
  - min-days filled from max/flat value with NO annotation (`save_current_sentence`,
    the `min_days is None` branches) → 18.3.
  - Judge capture accepts any name-shaped span with zero judge validation
    (the `expecting_judge_line` block) → 18.2 (junk-judge guard) / Sprint 5.
  - Held / non-terminal events → null disposition dates, no event-date capture
    → 18.3.
  - **KeyError crash** on one unsupported disposition layout: `disposition_raw`
    is guarded by `if seq in parsed_charges`, but the sentence-type branch does
    `charge = parsed_charges[current_charge_seq]` unconditionally, so a dispo
    section referencing an uncaptured charge sequence crashes. Ported as-is (task
    decision 8); per-docket exception capture is the 17.3 comparator's job.
  - `"Unknown Statute"` void-placeholder drop and leading-`IC` marker drop:
    preserved verbatim.
- **NOTE A — deliberate test duplication:** `test_privacy_guard_rejects_extra_field`
  and `test_privacy_guard_passes_clean_record` are byte-identical to two tests
  16.1 already ported into `test_identity.py`. Re-ported here per the task note
  because at parser level they belong to the parser's ported suite. A future
  cleanup must NOT "deduplicate" by deleting the `test_identity.py` copies (those
  assert the guard as a standalone identity unit). The through-the-parse-path
  exercise of the guard is the two new `parse_docket_checked` tests: a clean MC
  sheet passes; the rich MC sheet raises because its captured judge
  ("Example, Judge A.") shares the defendant surname, putting a sentinel into a
  record VALUE — a collision Capstone's `assert_no_leak` treats as a hard stop.
- **Capstone tests ported (8, all from `tests/test_mc_parser.py`, the sole
  parser test file):** `test_record_key_set_is_fixed_allowlist`,
  `test_court_type_detection_both_prefixes`,
  `test_mc_record_court_type_and_dc_number`,
  `test_cp_record_court_type_and_dc_number`, `test_related_cases_drops_caption`,
  `test_related_cases_parser_ignores_header_and_free_text`,
  `test_privacy_guard_rejects_extra_field`, `test_privacy_guard_passes_clean_record`.
  Adaptations: `src.*` imports → `pipeline.*`; `parse_docket_text(...)` calls
  gain `salt=TEST_SALT`; fixtures copied verbatim (already fictional). Tests
  deemed inapplicable: `test_helpers.py` (helpers/identity, ported in 16.1),
  `test_load_helpers.py` / `test_mc_loader.py` (DB loader, Sprint 5),
  `test_abort_guard.py` / `test_windows.py` (acquire stage, not this phase).
- **Lint adaptations (behavior-neutral, required by criterion 10):** B904 on the
  read-failure raise handled with `from exc` (matches the repo convention in
  `seam_check.py`); the two Capstone-verbatim dead assignments
  (`offense_date`, `otn_val`) and the unused `enumerate` index kept in place and
  suppressed with `# noqa: F841` / `# noqa: B007` (matches the `# noqa: BLE001`
  precedent in `extraction.py` / `seam_check.py`) rather than deleted, to keep
  the port byte-faithful. Two long lines wrapped and imports reordered by ruff;
  no tokens changed.
- **Couplings / surprises during the port:** the only real coupling was the
  severed-salt signature (above) — no other unported Capstone surface was
  reachable. `SKIP_SECTIONS` is ported as a constant but, as in Capstone, is
  never referenced in `parse_docket_text` (the section loop uses the `HEADERS`
  membership test directly); kept for fidelity and Phase-18 reference.
- **Deviations from plan:** none.
- **Verification (all three pipeline CI gates green):**
  - `.venv/bin/ruff check src tests` — All checks passed.
  - `.venv/bin/ruff format --check .` — 24 files already formatted.
  - `.venv/bin/python -m pytest -q` — 113 passed (11 new in
    `test_docket_parser.py`, 2 new guard params). No real docket text, PDFs, or
    Capstone raw data in the repo; all fixtures use fictional `Example` names and
    placeholder dockets.
- **Notes for next task (17.3 baseline equivalence):** diff the port's record
  against the regenerated Capstone baseline field-by-field, excluding
  `parsed_at` and `parser_version` (both are constant/timestamp, not parse
  output). `defendant_hash` IS compared, so 17.3 must supply the SAME salt
  Capstone used to regenerate the baseline. Per-docket exception capture belongs
  to the comparator: the one KeyError-crashing quarantined docket should crash
  identically and be recorded as a per-docket failure, not guarded. Feed the
  comparator 16.2 extraction output through `parse_docket_text` (seam proven
  equivalent in 17.1); use `parse_docket_checked` where the privacy assertions
  should gate a write.

## Task 17.3 — Baseline Equivalence Run (Port-Correctness Gate)

- **Date:** 2026-07-10
- **What was built:** A corpus comparator (`equivalence-check`) that runs the
  ported 16.2 extraction + 17.2 parser over the fixture corpus and diffs each
  parsed record field-by-field against the regenerated Capstone baseline JSON.
  New module `equivalence_check.py`: layout-robust baseline loader (`*.json`,
  single-record-object OR list-of-records, indexed by each record's
  `docket_number` field, never filename; loud `BaselineError` on a non-record
  root or unreadable JSON; refuses to run on zero records; flags duplicate
  docket numbers; records loaded/skipped counts in the header). Deep field diff
  (`diff_records`) producing dotted/bracketed paths (`charges[0].sentences[0].min_days`)
  with per-path divergence kinds (`value`, `key_missing_in_corpus/baseline`,
  `list_length`); list-length mismatches record surplus/missing elements *with
  values* in the JSON report (out-of-repo), paths+counts only in the TXT and
  console. Per-docket pipeline: `extraction.extract` → `parse_docket_checked`
  (parser + 16.1 privacy assertions), classifying each docket into exactly one
  of `equivalent`/`divergent`/`parse_failed`/`extraction_failed`/`baseline_missing`,
  plus `corpus_missing` for baseline records with no corpus PDF. Per-docket
  exception capture: extraction returns a failed result, the parse is wrapped
  (ParseError → `parse_error`; privacy-assertion RuntimeError → distinct
  `privacy_assertion` reason so a sentinel block is distinguishable; anything
  else → `unexpected_exception`), and an outer loop guard catches the rest — one
  bad docket never aborts the run. Reconciliation is *asserted*, not just
  reported: corpus statuses must sum to the corpus PDF count and matched +
  `corpus_missing` must equal the unique baseline docket count; on failure the
  run returns nonzero and `reconciled=false` in the header. Reports land under
  `--output-dir` (default `~/court-data/equivalence/`, refused inside a git
  worktree): machine-readable `equivalence-report.json` (per-docket statuses,
  field-path divergences with values, exception details) and human-readable
  `equivalence-report.txt` (per-court CP/MC totals, status breakdown, top
  divergent field paths, active exclusion list, gate verdict). CLI wiring in
  `cli.py`: `equivalence-check` subcommand (`--corpus-dir`, `--baseline-dir`,
  `--output-dir`, repeatable `--exclude-field`, `--salt-parity-confirmed`),
  reads `DEFENDANT_HASH_SALT` from the env at the run boundary (loud refusal if
  unset; value never printed/written), refuses to run under CI.
- **Salt parity mode:** default is parity-UNCONFIRMED → `case.defendant_hash`
  (verified as the sole hash path in the 17.2 record contract) is added to the
  exclusion set and the mode `hash_excluded_parity_unconfirmed` is stated in the
  JSON header, the TXT summary, and the console. `--salt-parity-confirmed`
  switches to `hash_compared` and drops the exclusion. The exclusion base is one
  documented constant `EXCLUDED_FIELDS = {parsed_at, parser_version}`.
- **Files touched:** `services/pipeline/src/pipeline/equivalence_check.py` (new),
  `services/pipeline/src/pipeline/cli.py` (subcommand wiring + salt-from-env),
  `services/pipeline/tests/test_equivalence_check.py` (new, 24 synthetic tests),
  `tasks/worklog.md`.
- **Deviations from plan:** none. Console/log privacy follows the 17.1
  hash-prefix precedent (CLAUDE.md hard rule overrides the task's "docket IDs"
  wording — docket numbers are defendant-identifying, so they stay in the
  out-of-repo report; stdout carries counts/statuses/salt-mode only, logs carry
  hash-prefix ids).
- **Verification (all three pipeline CI gates green):**
  - `.venv/bin/ruff check src tests` — All checks passed.
  - `.venv/bin/ruff format --check .` — 26 files already formatted.
  - `.venv/bin/python -m pytest -q` — 137 passed (24 new). Tests are synthetic
    only: extraction and parse are monkeypatched, no real PDF/docket/baseline is
    touched, all output goes to `tmp_path`.
- **Notes for next task:** the actual gate RUN over the real 1,596-docket corpus
  is a LOCAL human step (tier-2, never CI): with `DEFENDANT_HASH_SALT` set,
  `pipeline equivalence-check` (defaults point at `~/court-data/fixtures/` and
  `~/court-data/capstone-baseline/`, output to `~/court-data/equivalence/`). Pass
  `--salt-parity-confirmed` ONLY after human-verifying the baseline was
  regenerated with the same salt; otherwise the hash is excluded and the report
  says so. The summary counts and PASS/REVIEW verdict from that run — never
  docket content — are what closes the gate in the planning chat before Phase 18.
  Any divergence found is triaged there, not fixed here.
- 1,596/1,596 equivalent, CP 1,556 / MC 40, zero divergent/failed/missing, salt parity confirmed, hash compared, verdict PASS. 
## Task 18.1 — Warning Framework + review_needed + Parser Output Envelope

- **Date:** 2026-07-10
- **What was built:** The 18.1 observability layer over the proven-equivalent
  17.2 parser — a closed warning vocabulary, a derived `review_needed` boolean,
  and a per-document envelope wrapping the UNCHANGED record — plus per-docket
  failure capture and a `parse` CLI stage. Emission is observation-only; the
  parsed record is not touched (criterion 5).
  - **`warning_codes.py` (new, single source of truth):** the nine locked codes,
    the `SEVERITY` map (code → `review`/`info`), `WARNING_CODES` closed set,
    `make_warning(code, *, section, charge_sequence, page, field)` — the ONLY
    constructor, accepting solely those four optional structural fields so a
    text-carrying warning is unrepresentable by construction (decision 2), and
    `derive_review_needed(codes)` = any code with `review` severity. Severity map
    documented in the module docstring, including the MISSING_SENTENCE_DATE=info
    rationale (undated sentence facts are mechanically excluded by the Sprint 7
    date-range gate; review cannot recover a date the sheet never printed).
  - **`envelope.py` (new):** `parse_document(...)` → envelope with exactly the
    pinned fields (`source_sha256`, `parser_version`, `extraction_artifact`,
    `record`, `warnings`, `review_needed`, `status`, `created_at`, `error`); no
    numeric-confidence field anywhere. Embeds the parser's exact record object by
    reference (proven by a monkeypatch identity test). `observe(record, status)`
    derives the observation-only warnings from the record + extraction status
    only — never page text. `run_parse(...)` is the CLI driver: reads 16.2
    extraction artifacts, writes one `{source_sha256}.json` envelope per doc,
    refuses an output dir inside a git worktree, one bad artifact never aborts
    the run.
  - **`cli.py`:** new `parse` subcommand (`--artifacts-dir` default
    `~/court-data/extracted/`, `--output-dir` default `~/court-data/envelopes/`),
    salt read from `DEFENDANT_HASH_SALT` at the run boundary (loud refusal if
    unset; value never printed), refuses to run under CI — same convention as
    seam-check / equivalence-check.
- **NON_TERMINAL_CASE — path (a), record-derived (per reviewer preference).** The
  ported MC path records a charge's disposition (`disposition_raw` /
  `disposition_date` / `sentences`) ONLY inside an event its gating accepts as
  terminal (Final Disposition, or an event name containing "ard"); a held /
  "Not Final" event sets `in_valid_event=False` and writes nothing, and the
  parser writes no "held" text anywhere. So "no terminal event present" is
  faithfully visible in the record as: the record has charges and NONE exposes
  any disposition or sentence. Detection reads only the parsed record — no page
  text, no regex hoist, no parser change — so criterion 5 is trivially safe. The
  corrected predicate holds: a docket with interim non-final events plus a
  genuine final disposition has ≥1 disposed charge and does NOT flag (tested).
- **Exception mapping (per approved FIX 1):** ALL parse-time exceptions
  (ParseError, KeyError, anything) → `failed` envelope with
  `error.code = UNSUPPORTED_FORMAT` and structural context (`exception_class`
  only — no free-text message, no raw docket text). MISSING_CHARGE_SECTION is now
  the third defined-but-unemitted code, alongside SUSPECT_JUDGE_LINE and
  SUSPECTED_AMENDED_CHARGE; the closure test asserts the unemitted set is exactly
  those three. (The quarantined KeyError specimen and a name/DOB ParseError both
  verified to land as UNSUPPORTED_FORMAT failed envelopes.)
- **Two-version design (decision 4 + 7):** the ENVELOPE carries
  `parser_version = 2`; the wrapped record keeps its internal `parser_version = 1`
  untouched. Documented in the envelope module docstring.
- **Severity map:** implemented exactly as approved. review = LOW_TEXT_EXTRACTION,
  MISSING_CHARGE_SECTION, UNSUPPORTED_FORMAT, MISSING_DISPOSITION_DATE,
  SUSPECT_JUDGE_LINE, SUSPECTED_AMENDED_CHARGE; info = UNPARSEABLE_DURATION,
  MISSING_SENTENCE_DATE, NON_TERMINAL_CASE.
- **Files touched:** `services/pipeline/src/pipeline/warning_codes.py` (new),
  `services/pipeline/src/pipeline/envelope.py` (new),
  `services/pipeline/src/pipeline/cli.py` (subcommand wiring),
  `services/pipeline/tests/test_warning_codes.py` (new),
  `services/pipeline/tests/test_envelope.py` (new),
  `services/pipeline/tests/test_cli.py` (parse CI/salt guard tests),
  `tasks/worklog.md`. No `.env.example` change (salt already exists; output dir
  is a flag). No apps/packages/db touched.
- **Deviations from plan:** none beyond the two approved fixes (ParseError →
  UNSUPPORTED_FORMAT, MISSING_CHARGE_SECTION unemitted; NON_TERMINAL_CASE path a).
- **Verification (all three pipeline CI gates green):**
  - `.venv/bin/ruff check src tests` — All checks passed.
  - `.venv/bin/ruff format --check .` — 30 files already formatted.
  - `.venv/bin/python -m pytest -q` — 172 passed (35 new: warning_codes 11,
    envelope 22, cli 2). Synthetic fixtures only (fictional `Example` / placeholder
    docket); no real PDF/docket/baseline touched; envelope artifacts written to
    `tmp_path` in tests.
- **Notes for next task:** the record-shape-neutrality guarantee is by test
  (criterion 5); the actual 17.3 comparator RE-RUN over the real corpus to
  reconfirm zero divergences is the standing LOCAL human step (Chops). 18.2 wires
  the SUSPECT_JUDGE_LINE / SUSPECTED_AMENDED_CHARGE detectors and MISSING_CHARGE_SECTION;
  each becomes a golden delta then. The `parse` stage consumes 16.2 extraction
  artifacts (`~/court-data/extracted/`) and emits envelopes to
  `~/court-data/envelopes/`.
- **18.1 post-merge verification: equivalence rerun PASS 1596/1596 (hash field
excluded — salt rotated post-17.3; parity permanently unconfirmed vs frozen
baseline going forward). Real-corpus parse run: 1596 extracted (all
success), 1596 parsed, 0 failed. Warning distribution: UNPARSEABLE_DURATION
280 (known duration-null population), MISSING_DISPOSITION_DATE 211 across
67 review_needed dockets, NON_TERMINAL_CASE 104 = 91 CP pending + 13 MC
held-for-court — all accurate per definition, info severity, mechanically
excluded from aggregates (no disposition → no outcome fact). record
court_type is None across all 1596 (faithful-port inert field; Capstone
baseline identical per 17.3). Sprint 5 normalization note: docket-number
prefix is the authoritative court-type source; decide populate-vs-drop for
the record field there.
## Task 18.2 — Hardening: Charges, Dispositions, Judges

- **Date:** 2026-07-10
- **What was built:** The first three locked hardening items on the ported
  parser, each proven isolated and warning-surfaced. All three land in one
  commit. The parser now DELIBERATELY diverges in output VALUES from the
  Capstone baseline (schema/shape unchanged); the equivalence comparator's role
  flips from "prove identical" to "prove the diff set is exactly the intended
  delta set."
  - **Item 1 — junk judge guard:** `_is_junk_judge(value)` (single documented
    pattern set in `docket_parser.py`) rejects judge-slot captures matching
    sentence-component patterns — keywords `Confinement|Probation|IPP`, the
    `Min|Max of` slot, duration expressions (number + day/month/year unit), and
    currency (`$` or a `\d[\d,]*\.\d{2}` amount). NO name-shape/identity
    validation (Sprint 5). `ARD`/`No Further Penalty`/`Fines and Costs`
    deliberately excluded ("Ard" is a name-shaped surname). Applied at BOTH
    capture sites: assigned judge (`CASE INFORMATION`) and per-charge
    disposition judge (`DISPOSITION SENTENCING/PENALTIES`). On rejection ONLY
    the judge field is nulled — `disposition_date`/`filed_date` on the same line
    are still recorded and control flow is unchanged — so each rejected capture
    is exactly ONE field delta. Emits `SUSPECT_JUDGE_LINE` (structural context:
    section + charge_sequence).
  - **Item 2 — disposition line-wrap fix:** a pure-prose tail line (letters and
    spaces only, ≥1 letter) in the judge-expectation slot is appended to the
    current charge's `disposition_raw`, so a wrapped disposition
    ("Transferred to Another Jurisdiction") is captured in full. Root cause
    (hypothesis, to be confirmed on the corpus): the value wraps to a second
    physical line; the parser captured only the charge-line remainder and
    dropped the wrapped tail via the `expecting_judge_line` fall-through
    `continue`. Sentence-type and judge/date lines are matched BEFORE this
    check, so only disposition prose is appended.
  - **Item 3 — amended/downgraded/replaced signal:** `_matches_amended_charge`
    scans the already-parsed `disposition_raw` for `amended | downgraded |
    replaced by | charge changed` (case-insensitive). WARNING-ONLY: reads a
    parsed field, changes no field, never merges/re-keys charges. Pattern basis
    is explicitly labelled **SPECULATIVE-CONSERVATIVE** in the code (no cited
    CPCMS document, no agent-readable corpus observation) — the real per-pattern
    corpus hit counts (from the human rerun) are what turn the basis into data.
    Emits `SUSPECTED_AMENDED_CHARGE` (section `CHARGES` + charge_sequence).
- **Mechanism:** `parse_docket_text` now returns a 3-tuple
  `(record, sentinels, warnings)`; the record object shape is byte-unchanged
  (warnings live OUTSIDE it), so record↔baseline equivalence is untouched.
  `parse_docket_checked` and `docket_parser_pdf.parse_docket` forward the
  3-tuple; `envelope.parse_document` merges parser warnings after the `observe()`
  warnings; `equivalence_check.compare_one` ignores the warnings (it diffs
  records). No new warning codes — `SUSPECT_JUDGE_LINE`/`SUSPECTED_AMENDED_CHARGE`
  already existed at `review` severity in the 18.1 vocabulary.
- **parser_version (per approved reading):** envelope `ENVELOPE_PARSER_VERSION`
  bumped 2→3; the record's internal `parser_version` stays 1 (record-SCHEMA/shape
  axis — the shape is still Capstone-equivalent even though values diverge). The
  comparator excludes `parser_version` regardless, so the bump is delta-neutral.
  Envelope/parser docstrings relabelled from "Capstone-equivalent record" to
  schema/shape framing (values-diverge, schema-unchanged).
- **Emission-scope update:** `envelope.UNEMITTED_CODES` shrinks from three codes
  to `{MISSING_CHARGE_SECTION}` (its detector is future work, out of 18.2 scope).
- **Files touched:** `services/pipeline/src/pipeline/docket_parser.py`
  (guard + line-wrap fix + amended scan + 3-tuple + docstring),
  `docket_parser_pdf.py` (passthrough return/annotation),
  `envelope.py` (merge parser warnings, version 2→3, UNEMITTED_CODES,
  docstrings), `equivalence_check.py` (3-tuple unpack only),
  `tests/test_docket_parser.py`, `tests/test_envelope.py`,
  `tests/test_equivalence_check.py`, `tasks/worklog.md`. No `@pca/*`, apps, db,
  CI, or `docs/` changes. `warning_codes.py` untouched (no vocabulary change).
- **Test adjustments (named per convention):** (1) every `parse_docket_text` /
  `parse_docket_checked` call site updated for the 3-tuple return (mechanical
  unpack: `record, _` → `record, _, _`); (2) the two monkeypatch fakes
  (`test_envelope` embed-verbatim test, `test_equivalence_check._fake_parse`)
  return the extra warnings element; (3) `test_envelope` version assertion
  `== 2` → `== 3`; (4) `test_unemitted_set_...` rewritten to assert the single
  remaining unemitted code `{MISSING_CHARGE_SECTION}`. New tests: 19 across the
  three items (guard reject/pass at both sites, line-wrap-in-full + no-spurious-
  extension + Item 2→3 no-false-amended, amended positive/negative parametrized,
  envelope surfacing + review_needed for both new codes). All synthetic
  (fictional `Example`, placeholder zero-sequence dockets); no real PDF/docket/
  baseline touched.
- **Verification (all three pipeline CI gates green):**
  - `.venv/bin/ruff check src tests` — All checks passed.
  - `.venv/bin/ruff format --check .` — 30 files already formatted.
  - `.venv/bin/python -m pytest -q` — 191 passed (19 new).
- **STANDING LOCAL human step (Chops) — consolidated corpus rerun.** Corpus
  runs are out-of-repo (real dockets); ONE consolidated final rerun is
  sufficient because the three delta classes are field-disjoint. Commands:
  - `DEFENDANT_HASH_SALT=… pipeline equivalence-check` (defaults:
    `--corpus-dir ~/court-data/fixtures`, `--baseline-dir
    ~/court-data/capstone-baseline`, `--output-dir ~/court-data/equivalence`).
    Attributes Items 1 & 2 (both change the record).
  - `DEFENDANT_HASH_SALT=… pipeline parse` (defaults:
    `--artifacts-dir ~/court-data/extracted`, `--output-dir
    ~/court-data/envelopes`), then count `SUSPECTED_AMENDED_CHARGE` /
    `SUSPECT_JUDGE_LINE` across the envelopes. Item 3's corpus effect is
    warning-only (zero record diff) so it shows here, NOT in the comparator.
  - **Expected delta classes (each diff attributable to exactly one item):**
    - Item 1: `value` diffs on `case.assigned_judge_raw` and/or
      `charges[i].disposition_judge_raw`, baseline=sentence-fragment →
      corpus=null. Nothing else.
    - Item 2: `value` diffs on `charges[i].disposition_raw` ONLY, where the
      after-string is a PREFIX-EXTENSION of the before-string (appended
      disposition prose). STOP-AND-REPORT if: any after-string is not a
      prefix-extension of its before-string; any appended content is not
      disposition prose; or any Item-2 diff appears on a field other than
      `disposition_raw`. Enumerate the distinct before→after pairs in the report.
    - Item 3: ZERO record diffs; only new `SUSPECTED_AMENDED_CHARGE` warnings.
      Report the per-pattern hit counts; implausible hits (ordinary dockets
      flagged) are a STOP-AND-REPORT.
    - Any diff outside these three classes, or not attributable to exactly one
      item, is a STOP-AND-REPORT (not to be explained away).
  - An optional intermediate rerun after Item 2 (before Item 3) is available —
    Item 2 is self-contained and runnable on its own — given its
    hypothesis-driven nature.
- **Sprint 5 dependency (Item 2):** once the corpus rerun confirms
  "Transferred to Another Jurisdiction" is captured in full, Sprint 5 can DROP
  the disposition-map truncated-form workaround (a named Sprint 5 opening item).
  Evidence it needs: the Item 2 before→after pair enumeration from the rerun
  showing the truncated form no longer emitted.
- **Notes for next task (18.3):** held-case event dates, min_assumed
  annotation, third-party name guard, sentinel precision, and the 7 quarantined
  sentinel-block dockets remain 18.3. `MISSING_CHARGE_SECTION` is still the sole
  defined-but-unemitted code.

### Task 18.2 — Item 2 repair (post-corpus-rerun; supersedes the Item 2 sections above)

- **Date:** 2026-07-10
- **Why:** The consolidated corpus rerun (1,596 dockets) FAILED Item 2's stop
  condition. Item 1 validated (exactly 3 `disposition_judge_raw` fragments →
  null); Item 3 clean (zero record diffs). Item 2's pure-prose append gate
  produced ~535 divergent dockets whose appended tails were NOT disposition
  prose. Root cause from the data: the disposition section re-prints the charge
  description; the disposition column and the (re-printed) charge-description
  column wrap together and interleave with section-header furniture, so the
  continuation line cannot be distinguished from a disposition wrap. Even the
  32 Transferred true-positives were polluted (e.g. `Transferred to Another` →
  `Transferred to Another Manufacture or Deliver Jurisdiction`, or trailing
  `COMMONWEALTH INFORMATION ATTORNEY INFORMATION Office Private`). The Capstone
  fall-through drop was correct for those lines.
- **Repaired design (plan-approved, Approach B1 — deterministic repair, reads no
  continuation line):** reverted the append gate + continuation helpers (Capstone
  fall-through restored verbatim; Items 1 and 3 untouched). Added
  `_TRUNCATED_DISPOSITION_REPAIRS`, a corpus-evidenced single-entry table
  (`"Transferred to Another"` → `"Transferred to Another Jurisdiction"`). After
  the disposition loop, before the Item 3 scan, a charge whose `disposition_raw`
  is an EXACT-MATCH table key is rewritten to the full string. Each key is a
  complete, unambiguous disposition prefix with exactly one full form that is
  never itself a complete disposition, so the rewrite is unambiguous and — because
  no subsequent line is read — immune to charge-name wraps and section furniture
  by construction. Zero-false-positive-by-construction. Table grows only with the
  same corpus evidence and exact-match discipline; any other truncated
  disposition is left to the downstream map (deliberate false-negative bias).
- **Why the failure classes are now rejected:** `Guilty Plea - Negotiated`,
  `Guilty`, `ARD - County`, every charge-name wrap, and every section-furniture
  run are not table keys and no continuation line is read → all untouched. Only
  an exact `Transferred to Another` capture is rewritten; its polluted
  continuation is never read, so the clean full string is produced every time.
- **New expected corpus delta (Item 2):** `value` diffs on
  `charges[i].disposition_raw` ONLY, where before ∈ table keys and after = the
  exact table value; count ≈ 32 (the Transferred true-positive class). STOP-AND-
  REPORT if any `disposition_raw` diff has a before not in the table or an after
  not equal to the table value, or any Item-2 diff on any other field. Combined
  repaired delta = Item 1 (3 × `disposition_judge_raw`→null) + Item 2 (~32 ×
  exact `disposition_raw` repairs) + Item 3 (0 record diffs).
- **Fixtures (replacing the old Item 2 tests):** polluted-continuation positive
  (`Transferred to Another` + `Manufacture or Deliver Jurisdiction` → full clean
  string, no amended flag), charge-description-wrap negative (`Guilty Plea -
  Negotiated` + `Manufacture or Deliver` → unchanged), section-furniture negative
  (`COMMONWEALTH INFORMATION …` → unchanged), plus the retained single-line
  sentence-type negative. Item 2→3 no-`SUSPECTED_AMENDED_CHARGE` assertion stands.
- **Files touched (repair):** `services/pipeline/src/pipeline/docket_parser.py`,
  `services/pipeline/tests/test_docket_parser.py`, `tasks/worklog.md`. Items 1
  and 3 code and tests unchanged. `envelope.py` / `equivalence_check.py` /
  `docket_parser_pdf.py` unchanged from the first 18.2 pass.
- **Verification (all three pipeline CI gates green):**
  - `.venv/bin/ruff check src tests` — All checks passed.
  - `.venv/bin/ruff format --check .` — 30 files already formatted.
  - `.venv/bin/python -m pytest -q` — 193 passed.
- **STANDING LOCAL human step (Chops) — repeat the consolidated rerun.** Same
  commands as the first pass (`pipeline equivalence-check`, then `pipeline
  parse` + warning counts). Item 3 warning-count validation (deferred at the
  failed rerun) lands with this repeated run once envelopes are regenerated.

## Task 18.3 — Hardening: Dates, Sentencing, Privacy

- **Date:** 2026-07-10
- **What was built:** The three locked Sprint 4 hardening items plus the two
  banked quarantine design questions (Q1/Q2), all as declared, corpus-attributable
  delta classes.
  - **Item 1 — held-case event dates.** A non-terminal (Not Final, non-ARD) event
    records `event_date` (the event-header date) and `event_name` on the charge.
    **Placement rule (corrected after the Check-2 defect below): the keys survive
    ONLY on charges that END the parse undisposed** (`disposition_raw`,
    `disposition_date`, `disposition_judge_raw` all null); a charge listed under a
    non-terminal event but later disposed under a terminal event (the Preliminary
    Hearing → Trial progression) has the transient keys stripped by a placement
    sweep after the disposition loop. When a held charge appears under multiple
    non-terminal events, the LATEST event-header wins (assignment overwrites). Held
    cases keep `disposition_*` null and `sentences` `[]` (output stays honest);
    `NON_TERMINAL_CASE` is still emitted by the envelope observation layer
    (`event_date` does not affect `_charge_has_disposition`). Terminal output is
    byte-identical to the Capstone baseline. Cross-court capture unchanged (raw).
  - **Item 2 — `min_assumed` annotation.** A sentence records `min_assumed: true`
    exactly when `min_days` was FILLED from the maximum or from a flat value; it is
    absent (not `false`) when min was parsed directly (max may be filled from min)
    or when both bounds parsed. Parsed duration values are byte-identical to
    pre-task output — pure annotation, no warning, no `review_needed` impact.
    Added only when true, so unaffected sentences stay byte-identical.
  - **Q1 — sentinel matching precision.** `identity.assert_no_leak` now matches
    whole-token (boundary-anchored: `(?<![a-z0-9]) escaped-sentinel (?![a-z0-9])`,
    case-insensitive, min length 3) instead of raw substring. A whole-token match
    is a strict subset of a substring match, so the change can only *unblock*,
    never newly block — this discharges "zero previously-passing dockets may newly
    block" by construction. It recovers the 2 quarantine fragment false positives
    while the 5 real collisions still match. **Surrendered leak class (for the POC
    report):** a sentinel that appears only as a proper sub-span inside a larger
    alphanumeric token is no longer blocked; accepted because a fragment embedded
    in a larger word is not a retrievable identifier, and that benign class is
    exactly the 2 false positives removed. Full names and DOB strings remain
    exact-matched (internal punctuation via `re.escape`, outer edges anchored).
  - **Q2 / Item 3 — third-party name guard (`SENTINEL_COLLISION`, new code, plan-
    approved, severity `review`).** In the two known judge label contexts
    (`CASE INFORMATION` assigned-judge, `DISPOSITION` disposition-judge), a
    name-shaped capture that whole-token-collides with a sentinel is NULLED and
    flagged `SENTINEL_COLLISION` (structural context only: section, charge_sequence
    — never the colliding text). The colliding value never passes through as a
    judge name; `review_needed` derives to true automatically. `assert_no_leak`
    (now whole-token) is retained as the fail-closed backstop. The 18.2 junk-judge
    guard was NOT touched. Residual coverage gap (contexts outside the two judge
    slots; NER out of scope) is documented here for 20.1 to lift: the guard covers
    the assigned-judge and disposition-judge slots only; attorney/participant
    free-text contexts are not pattern-guarded and rely on the backstop plus
    upstream capture bounds. False-negative bias is deliberate.
  - **Versioning.** `ENVELOPE_PARSER_VERSION` 3 → 4; record internal
    `parser_version` 1 → 2 (first record-SCHEMA change since the port — the two
    conditional fields). `EXCLUDED_FIELDS` already excludes `parser_version`, so
    the record-version bump produces no comparator diff.
- **Declared delta classes for the corpus rerun (18.2 inversion discipline):**
  - **Main-corpus comparison (1,596 baseline records), CP/MC separate — every diff
    must be exactly one of:**
    - **Class A — event_date/event_name additions:** `key_missing_in_baseline` at
      `charges[i].event_date` and `charges[i].event_name`, on charges that END the
      parse undisposed only. **Post-fix actuals over the 1,603 corpus: 463 true-held
      event-key charges → 926 keys across 104 dockets (CP 91 / MC 13), all of which
      also carry `NON_TERMINAL_CASE`.**
      > **[Class A semantics amended by the 18.4 defect note below — these are
      > key-PRESENCE counts, and the VALUES they counted were wrong. See the
      > "18.4 defect note" appended to this entry for populated-value status and
      > the value gate that now enforces it. Do not act on these counts as
      > evidence of correct held-charge values.]**
    - **Class B — min_assumed additions:** `key_missing_in_baseline` at
      `charges[i].sentences[j].min_assumed`, value `true`, filled-min sentences
      only. **Post-fix actuals: 1,842 keys across 1,095 dockets, 0 with value ≠
      true (unchanged by the Check-2 fix — min_assumed was untouched).**
    - **Class C — sentinel-disposition changes:** **expected and VERIFIED ZERO in
      the main corpus.** All 1,596 pass (no live collision); whole-token only
      unblocks; the guard nulls nothing where nothing collides.
    - **Classes D/E — 18.2 carryover against the immutable Capstone baseline
      (adjudicated into the cumulative ledger; supersede per-task-only class
      declarations for all future runs against the Capstone baseline until the 19.2
      goldens become the regression reference).** Class D: `disposition_judge_raw`
      value→null with `SUSPECT_JUDGE_LINE` (18.2 Item 1) — **accepted count 3**.
      Class E: `disposition_raw` truncation repairs ('Transferred to Another' → full
      form) (18.2 Item 2) — **accepted count 16** (split 2/13/1 across
      CP-51-CR-0000981 / CP-51-CR-0000982 / MC-51-CR-0001053). Carryover identity
      proven byte-for-byte against the retained 18.2 acceptance report.
  - **STOP-AND-REPORT** (never fix in place, never explain away): any main-corpus
    status change; any `value` diff; any key diff outside Classes A/B; any *new*
    hard block on a previously-passing docket; any Class-C-shaped diff anywhere in
    the main corpus; any real leak.
- **Quarantine rerun report — STATUS-TRANSITION based (Fix 1; the 7 sentinel
  dockets have NO Capstone baseline, so there is nothing to diff against — this is
  NOT a baseline comparison):**
  - 2 fragment false positives: `privacy_assertion` block → **pass** (parse to a
    clean record).
  - 5 whole-token collisions: `privacy_assertion` block → **parsed-and-flagged**
    (judge field null, `SENTINEL_COLLISION`, `review_needed = true`).
  - 1 KeyError docket: **untouched, stays quarantined** (POC unsupported-format
    specimen; out of scope).
  Report emits docket ids, sections, counts, statuses ONLY — never the colliding
  capture or any docket text.
- **Amended standing invariant (Fix 2, worklog-bound):** after this task the 7
  recovered sentinel dockets move into `~/court-data/fixtures/` (human step, Chops).
  The invariant becomes **fixtures = baseline (1,596) ∪ recovered sentinel dockets
  (7)**. `equivalence_check.py` already expresses a fixture PDF with no baseline
  JSON as `STATUS_BASELINE_MISSING` — an explicit, reconciled, non-aborting,
  non-silent entry — so it satisfies "explicit no-baseline informational entry,
  never a failure, never a silent skip" without code change; the module was
  deliberately NOT modified (weakening its strict port-gate verdict would mask a
  genuinely-missing baseline, and the 7 expected entries cannot be auto-classified
  without embedding docket ids in repo code, which privacy forbids). At rerun the
  human confirms `baseline_missing` count == 7 (the recovered set).
- **Files touched:** `services/pipeline/src/pipeline/identity.py` (whole-token
  predicate `matches_as_token` + `collides_with_sentinels`; `assert_no_leak`
  switched to it), `services/pipeline/src/pipeline/warning_codes.py`
  (`SENTINEL_COLLISION`, severity `review`; vocabulary 9 → 10),
  `services/pipeline/src/pipeline/docket_parser.py` (event_date/event_name capture,
  min_assumed, third-party name guard in both judge contexts, record
  `parser_version` 2), `services/pipeline/src/pipeline/envelope.py`
  (`ENVELOPE_PARSER_VERSION = 4`; comments), tests
  (`test_identity.py`, `test_docket_parser.py`, `test_envelope.py`,
  `test_warning_codes.py`), `tasks/worklog.md`. `equivalence_check.py` NOT modified
  (see Fix 2 above).
- **Check-2 defect and fix (honest history, post-review).** The first
  implementation attached `event_date`/`event_name` at each non-terminal-event
  appearance keyed by charge sequence, but did NOT remove them when the same
  sequence was later disposed under a terminal event. The full-corpus placement
  re-check found **3,085 disposed charges across 1,472 dockets carrying event keys**
  — falsifying the "byte-identical terminal output" claim (every extra key was a
  legitimate Class A `key_missing_in_baseline` diff, so the comparator still
  reconciled and nothing leaked, but the placement was wrong). **Fix (directed, only
  authorized change):** a placement sweep after the disposition loop strips
  `event_date`/`event_name` from any charge that ends the parse disposed (chosen
  over never-setting because the non-terminal event precedes the terminal event in
  the source, so "ends undisposed" is only knowable once the whole disposition
  section is parsed). Latest-non-terminal-wins is preserved via loop overwrite. No
  other behavior changed; no version bumps (same task's record-schema change,
  corrected — `ENVELOPE_PARSER_VERSION` stays 4, record `parser_version` stays 2).
  Two regression tests added (progression: disposed-after-nonterminal → no event
  keys; multi-non-terminal: latest event-header wins).
- **Post-fix full-corpus rerun actuals (1,603 vs Capstone baseline, reconciled;
  CP/MC separate).** equivalent 392 (CP 369 / MC 23), divergent 1,204 (CP 1,187 /
  MC 17), parse_failed 0, extraction_failed 0, baseline_missing 7 (= exactly the
  recovered 7), corpus_missing 0. Every divergence classifies into exactly one
  ledger class: Class A 926 keys/104 dockets, Class B 1,842 keys/1,095 dockets,
  Class D 3, Class E 16; Class C 0; unclassified 0. Placement re-check: 463
  event-key charges, 0 violations. Warning totals unchanged from the pre-fix parse
  (UNPARSEABLE_DURATION 280, MISSING_DISPOSITION_DATE 211, NON_TERMINAL_CASE 104,
  SENTINEL_COLLISION 17 across the 5 recovered dockets, SUSPECT_JUDGE_LINE 5;
  review_needed true 76 / false 1,527) — the fix moves fields, not warnings.
  Quarantine spot-check unchanged: 2 pass / 5 flagged, SENTINEL_COLLISION confined
  to the recovered 5.
- **Deviations from plan:** (1) Quarantine report reframed status-transition based,
  not baseline-diff (Fix 1). (2) `event_name` added alongside `event_date` on
  non-terminal charges per approved answer (Decision 4's field list was not
  exhaustive); Class A covers both keys. (3) `equivalence_check.py` left unmodified
  with justification (Fix 2). (4) Item-1 placement corrected post-review (Check-2
  defect above). No other deviation.
- **Notes for next task:** The corpus/quarantine reruns are a STANDING LOCAL human
  step (Chops), same as 18.2 — fixtures live outside the repo. Real Class A/B
  counts and the quarantine per-docket outcomes land from that run; the expected
  shape and stop conditions are declared above. Sprint 5 judge normalization is the
  durable "is this value actually a judge" fix; the guard here only removes the
  leak. 20.1 lifts the residual-gap documentation above verbatim.
- **Verification (all three pipeline CI gates green):**
  - `.venv/bin/ruff check src tests` — All checks passed.
  - `.venv/bin/ruff format --check .` — 30 files already formatted.
  - `.venv/bin/python -m pytest -q` — 208 passed (206 + 2 Check-2 regression tests).
- **18.4 defect note (appended 2026-07-11 — do not rewrite history above).**
  A SECOND defect in the same held-case event capture was found after this entry
  was written, at the **20.2 exit demo**, and fixed in task 18.4. The 18.3 capture
  assumed a **two-line** event header (event-name line, then an anchor line with
  the date at **column 0**: `MM/DD/YYYY … Not Final`). Real CPCMS prints the
  header on **one line**: `<EventName> <MM/DD/YYYY> <Not Final|Final Disposition>`
  — a corpus scan found the date immediately left of the status token on
  **3,278/3,278** anchor lines and at line start on **zero**. On the authoritative
  v4 corpus run this left **`event_date` null on 463/463 held charges** and
  **`event_name` mis-sourced** (offense fragments off the wrong line) on 463/463.
  - **Ledger Class A semantics amended (key-presence → populated-value).** The
    Class A bullet above counts `key_missing_in_baseline` at
    `charges[i].event_date`/`event_name`. That diff is **value-blind**: it fires on
    key PRESENCE, so the 926-key / 104-docket / 463-charge (CP 91 / MC 13) counts
    were all green in 18.3 while the underlying values were wrong. After 18.4 the
    **paths and counts are unchanged** (comparator diffs stay
    `key_missing_in_baseline` on the same paths); what changed is that the VALUES
    are now correct and **a new fail-loud value gate enforces it** (see 18.4 item 4
    / the 18.4 entry below). Read the Class A counts as key-presence only; value
    correctness is attested by the value gate, not by these diffs.
  - **Verification-gap lesson:** key-presence diffs cannot certify a new capture
    field's values. Any future capture field requires a value gate, not just a
    key-presence class in the ledger. The 18.4 entry records the gate.

## Task COL-1 — Collection Baseline Run (Collector Port + One-Hour Weekend Baseline)

- **Date:** 2026-07-10
- **What was built:** The `pipeline collect` CLI subcommand and a new
  `pipeline.collector` package that ports Capstone's UJS-portal per-docket fetch
  path into a fully code-enforced pacing/stop regime. Enumerates
  `MC-51-CR-#######-2025` docket numbers, fetches each docket-sheet PDF into an
  intake dir, logs every attempt, and writes a JSONL attempt log + JSON run
  report. Tooling only — Chops runs the actual baseline manually.
- **Files touched:**
  - `services/pipeline/src/pipeline/collector/__init__.py` (new)
  - `services/pipeline/src/pipeline/collector/enumeration.py` (new — docket-range
    formatting, 7-digit zero-pad, MC-only)
  - `services/pipeline/src/pipeline/collector/classification.py` (new — pure
    `FetchSignal` → outcome; block-before-miss precedence)
  - `services/pipeline/src/pipeline/collector/guard.py` (new — block streak N=5
    and error streak N=5)
  - `services/pipeline/src/pipeline/collector/engine.py` (new — run loop; all
    caps/cooldowns/delays/reporting; injected transport/sleep/clock/jitter/abort)
  - `services/pipeline/src/pipeline/collector/transport.py` (new — Playwright
    adapter, lazy import, block detection; the only Playwright-touching module)
  - `services/pipeline/src/pipeline/collector/run.py` (new — run boundary: dir
    validation, SIGINT→graceful abort, real deps, transport lifecycle)
  - `services/pipeline/src/pipeline/cli.py` (collect subcommand + flags + CI guard)
  - `services/pipeline/pyproject.toml` + `uv.lock` (optional `collector` group,
    `playwright==1.61.0` exact)
  - `services/pipeline/README.md` (run-procedure section)
  - `services/pipeline/tests/test_collector_{enumeration,classification,guard,engine,cli}.py`
    (new) + `test_import_side_effects.py` (collector modules added, Playwright-free
    import test)
- **Capstone throttle-review findings:** Pacing lived largely in the SHELL
  wrapper `run_loop.sh` (`CHUNK=40`, `REST=180`s `sleep`, `while true`,
  operator Ctrl-C) — operator-attention pacing, now replaced by code. `collect.py`
  added only a per-fetch `polite_sleep` + `--limit` budget + a 150-fetch browser
  restart; **no wall-clock cap, no post-block cooldown, no bot-check detection**.
  `guard.py` (`AbortGuard`) ran two streaks (error@5, nopdf@8) that **conflated
  "no PDF" with "throttled"** and could not tell a genuine missing docket from a
  block. `fetch_fixtures.py`/`fetch_mc_fixtures.py` were standalone fixture
  fetchers with the same conflation. COL-1 replaces all of it with: 240-min hard
  ceiling, 2-min post-block cooldown, jittered 2–5s per-request delay, 40/batch +
  4-min inter-batch cooldown, explicit block/bot-check classification distinct
  from clean miss, block streak N=5 + error streak N=5, per-attempt outcome
  logging, resumable `already_present` skip, out-of-repo intake/report dirs.
- **Strategy divergence (confirmed proceed):** Capstone's `collect.py`
  deliberately *retired* docket-number enumeration in favor of a Date-Filed
  search harvest, precisely because enumeration wastes lookups on non-existent
  sequences and produced rate-limit false negatives under `AbortGuard`. COL-1
  re-adopts enumeration as a standing locked decision (it is the coverage
  denominator), and the new miss/block separation is the specific fix for the
  conflation that drove Capstone off enumeration. This changes the miss-rate
  profile Capstone saw — expected and intended.
- **Deviations from plan:** none. All six approved fixes incorporated
  (per-request jittered delay; consecutive-error stop; headful default; no
  screenshots/tracing/HAR/video + grep test; block-before-miss precedence;
  documented browser-restart drop). Playwright pin resolved to `1.61.0` at
  implement time; batch boundaries count real portal requests (both pre-approved).
- **Flagged for re-evaluation after the baseline run:** (1) browser-restart-every-
  150-fetches dropped (unnecessary for a ≤600-request hour); (2) block/bot-check
  DOM signatures in `transport.py` are best-effort (Capstone had none to port) and
  MUST be operator-confirmed on the headful run before extended collection.
- **Notes for next task:** Running the collection is the human step (Chops, a
  weekend). Collected PDFs are NEW INPUTS in `~/court-data/intake/`, not fixtures
  or baseline members; they enter the pipeline later via the 16.3 manual-import
  path after triage. Bot-check written confirmation remains an ADR 0002 open item
  gating extended/regular collection.
- **Verification (all three pipeline CI gates green):**
  - `.venv/bin/ruff check src tests` — All checks passed.
  - `.venv/bin/ruff format --check .` — 42 files already formatted.
  - `.venv/bin/python -m pytest -q` — 274 passed.

## Task COL-1a — Collector fixes from baseline run 1

- **Date:** 2026-07-11
- **Baseline run 1 record (good-faith, stated plainly):** run-20260711-034851 —
  129 attempted / 63 hits / 66 logged misses / 0 logged blocks; ended
  `operator_abort` at 29:30. The portal began serving an "unauthorized
  request"-style block page around sequence 0000122. The classifier, which was
  **fail-open** (any page lacking a docket-sheet link → `miss`), logged those
  block pages as misses — so blocks counted 0 for the whole run and attempts
  ~122–129 are misclassified blocks. Because they were not recognized as blocks,
  the **mandatory 2-minute post-block cooldown never fired** during that window.
  Fixed by this task. (The flagged "unverified DOM signatures" risk from COL-1 is
  thereby confirmed: block detection failed entirely.) Additionally, the Ctrl-C
  abort wrote the report correctly but then threw "Browser.close: Connection
  closed while reading from the driver" from `PlaywrightTransport.__exit__`.
- **What was built (5 fixes):**
  - **FIX 1 — fail-closed classification (core).** `miss` now REQUIRES positive
    identification of the portal's genuine no-results state (`FetchSignal.no_results`,
    set by the transport only when the search UI rendered with zero docket-sheet
    links and no block signature). Any response that is neither a successful PDF
    nor a positively-identified no-results page classifies as `blocked`. Unknown
    pages are blocks, never misses — robust to unseen block pages.
  - **FIX 2 — observed block signature.** Case-insensitive `unauthorized` /
    `not authorized` substrings recognized explicitly (either ⇒ blocked), on top
    of FIX 1's fail-closed default. Substring (not exact-phrase) matching chosen:
    operator recall is "unauthorized request" but is not screenshot-verified, and
    a false positive costs only a conservative cooldown.
  - **FIX 3 — graceful browser close.** `PlaywrightTransport.__exit__` now
    swallows/logs close()/stop() failures (SIGINT can kill the driver before we
    close); operator abort exits cleanly after the report is written.
  - **FIX 4 — operational flags.** Added `--batch-size` (default 40) and
    `--batch-cooldown-seconds` (default 240, enforced 60s floor). The
    counsel-locked 240-minute ceiling and 120s post-block cooldown stay hardcoded
    constants — no flags, unoverridable.
  - **FIX 5 — this worklog record.**
- **Files touched:** `collector/classification.py` (new `no_results`/`unauthorized`
  fields, fail-closed `classify`), `collector/transport.py` (positive no-results
  marker, unauthorized signature, graceful `__exit__`), `collector/engine.py`
  (batch flags via `CollectParams`; blocked detail incl. `unauthorized` /
  `unrecognized_page`), `collector/run.py` (batch args + floor enforcement),
  `cli.py` (two flags), `README.md` (fail-closed wording, flags, documented
  residual), `tests/test_collector_{classification,engine,cli}.py` (updated) +
  new `tests/test_collector_transport.py`.
- **Documented residual (README):** a block page that renders the *full* search
  UI with zero sheet links AND none of the recognized block text would still
  classify as `miss`. The observed block page is covered by its signature;
  interstitials without the search UI are covered by fail-closed. Operator
  confirms block-page appearance on the next headful run.
- **Deviations from plan:** none. Block signature uses the approved two-substring
  option (`unauthorized` OR `not authorized`).
- **Notes for next task:** the positive no-results marker and block signatures in
  `transport.py` are still live-unverified; the next headful run should confirm
  them. Fail-closed means a *wrong* no-results marker fails safe (over-blocks,
  triggering conservative cooldowns / an early `block_streak` stop) rather than
  leaking blocks as misses.
- **Verification (all four gates green):**
  - `.venv/bin/ruff check src tests` — All checks passed.
  - `.venv/bin/ruff format --check .` — 43 files already formatted.
  - `.venv/bin/python -m pytest -q` — 289 passed.
  - repo-root `pnpm format:check` — passed (MD/config touched).

## Task COL-1b — Persistent miss ledger (skip confirmed misses on rerun)

- **Date:** 2026-07-11
- **Run-2 note:** run-20260711-045230 deliberately re-confirmed run-1-era misses
  under the fixed fail-closed classifier. Those re-confirmations ARE valid ledger
  seeds. This task does **not** backfill the ledger from old logs (run-1 fail-open
  miss records must never seed it); the ledger populates naturally from
  fail-closed runs going forward, starting with run 2's confirmed misses.
- **Problem:** reruns re-attempted every previously-missed docket because
  resumability keys on PDF existence and a miss writes no file. At the observed
  ~40% miss rate in low MC-51-CR-2025 sequences, that wasted a large share of each
  rerun's portal budget re-confirming known answers.
- **What was built:**
  - **Miss ledger** — append-only JSONL per court+year at
    `<ledger-dir>/miss-ledger-<court>-<year>.jsonl`, `--ledger-dir` default
    `~/court-data/coverage/` (under the data root, outside the intake PDF dir and
    outside every git worktree — guard extended to cover it). One line per
    confirmed miss: `docket_number`, `run_id`, `timestamp`, `classifier_note`
    (`no_results`).
  - **Append only on a fail-closed miss** (positively-identified no-results).
    Blocks/hits/errors/skips never append.
  - **`known_miss` outcome** — on rerun, a docket in the ledger is skipped: no
    portal request, no per-request delay, no batch-boundary advance,
    streak-neutral (mirrors `already_present`), but still an enumerated resolved
    docket in counts and the coverage denominator.
  - **`--recheck-misses`** ignores the ledger and re-attempts everything;
    confirmed misses re-append (loader dedupes by docket number).
  - **FIX 1 (loud skips):** `load_miss_ledger` counts skipped lines and logs a
    WARNING with the count and ledger path when nonzero — a corrupted ledger
    can't silently shrink the skip set and burn budget.
  - **FIX 2 (court/year scoping):** the loader ignores entries whose docket
    number is not this run's court+year (prefix `MC-51-CR-`, suffix `-<year>`),
    folding them into the same skipped-line warning — a renamed/misdirected
    ledger can't suppress attempts in a different run.
- **Files touched:** `collector/engine.py` (ledger load/append, `known_miss`
  outcome + counts, `CollectParams.ledger_dir`/`recheck_misses`, report params,
  `validate_output_dirs` ledger arg), `collector/run.py` (plumbing + ledger dir
  guard/mkdir + summary), `cli.py` (`--ledger-dir`, `--recheck-misses`),
  `README.md` (ledger docs + current-year caveat), `tests/test_collector_engine.py`
  and `tests/test_collector_cli.py` (ledger + flag tests).
- **Deviations from plan:** none. Both approved loader fixes incorporated.
- **Notes for next task:** the ledger is sound for CLOSED years; for a year still
  accruing filings a miss can later become a hit, so `--recheck-misses` is the
  revalidation path (documented in the README).
- **Verification (all four gates green):**
  - `.venv/bin/ruff check src tests` — All checks passed.
  - `.venv/bin/ruff format --check .` — 44 files already formatted.
  - `.venv/bin/python -m pytest -q` — 299 passed.
  - repo-root `pnpm format:check` — passed (MD touched).

## Task 19.1 — Tier-1 Synthetic Fixture Corpus + Index + Goldens + Hygiene Test

- **Date:** 2026-07-11
- **Goal:** Committed, CI-safe regression corpus: synthetic TEXT fixtures over
  the full scenario matrix (CP/MC where layout differs), a fixture index,
  parser-generated golden JSONs (fixed public test salt), plus tests enforcing
  docket-number hygiene, index/golden consistency, and fixture↔golden
  regression. No parser behavior change.
- **What was built (all under `services/pipeline/tests/tier1/`):**
  - **32 fixtures** (`fixtures/*.txt`) covering every matrix scenario; CP+MC
    pairs where layout differs (single-charge, multiple-charge), MC-only where
    the section set differs (held/cross-court + related-cases, blank-judge,
    multi-non-terminal). Pages separated by a visible `=== PAGE BREAK ===` line
    (all current fixtures are single-page). Two invented MC renderings
    (`unverified_mc_trial_verdict`, `unverified_mc_amp_diversion`) marked
    `layout_unverified: true`.
  - **32 goldens** (`goldens/*.json`) — the deterministic PROJECTION of the
    parse pipeline: `status`, `record` (with non-deterministic `parsed_at`
    dropped), full `warnings`, derived `review_needed`, and (on failed parse)
    the structural `error` arm. Warnings/`review_needed` composed exactly as
    `envelope.parse_document` does (`observe()` + parser warnings, extraction
    status fixed at `STATUS_SUCCESS`). Parser-generated only, never hand-edited.
  - **`fixture-index.yaml`** — per-fixture filename, court_type, scenario,
    expected_charge_count, expected_warnings, layout_unverified, synthetic.
  - **`support.py`** — `TIER1_TEST_SALT = "tier1-fixture-salt"` (public; never
    the real salt), fixture/page loader, `build_golden` projection, golden IO,
    field-level diff. Contains no `test_*` functions.
  - **`generate_goldens.py`** — minimal deterministic generator; refuses to run
    without `--regenerate` (exits non-zero), not pytest-collectable.
  - **`test_regression.py`** — parses every fixture, compares to its golden with
    readable field-level diffs; offline; asserts no local-corpus reference.
  - **`test_index.py`** — 1:1 fixture↔index↔golden; expected_warnings ⊆
    EMITTED_CODES; MISSING_CHARGE_SECTION never expected; index consistent with
    goldens; explicit failed-parse convention (count 0 / null record / error arm).
  - **`test_hygiene.py`** — scans the ENTIRE tier1 tree; fails on any docket-shape
    token whose 7-digit sequence isn't the `000000\d` placeholder; reports
    location only, never the matched token.
- **Files touched:** `services/pipeline/tests/tier1/**` (fixtures, goldens,
  index, support, generator, 3 tests); `services/pipeline/pyproject.toml` +
  `uv.lock` (add dev-only `pyyaml`, approved); repo-root `.prettierignore` (one
  line excluding the generated goldens dir, approved); `tasks/worklog.md`.
- **Required-fix resolutions:** restitution folded into the Fines-and-Costs
  sentence program text (the ported parser recognizes only six sentence-type
  prefixes; restitution is not a distinct parsed component — a faithful
  limitation, not a parser change); dedicated `missing_disposition_date_mc`
  (disposition without a date) and `missing_sentence_date_mc` (sentence without
  a date) fixtures added; hygiene scans the whole tree; failed-fixture rule
  documented + asserted in `test_index.py`; generator gated + non-collectable.
- **CP/MC layout evidence:** the parser branches on court only via
  `detect_court_type` (prefix-only, `docket_parser.py:266`), the RELATED CASES
  section (MC-only, `docket_parser.py:851`), and the Cross Court Docket Nos line
  (`docket_parser.py:469`). CHARGES / DISPOSITION / STATUS / DEFENDANT parsing
  never reads court_type, so shared-path scenarios are court-agnostic and
  single-court coverage suffices; CP+MC pairs are provided where the section set
  differs.
- **Deviations from plan:** none beyond the approved required fixes.
- **Notes for next task (19.2):** the run-fixtures CLI builds on this loader +
  `build_golden` projection; regeneration discipline (explicit flag + this
  worklog note) is to be formalized there. Goldens are prettier-ignored (repo
  root) because they are generated artifacts; the YAML index stays prettier-checked.
- **Verification (all four gates green):**
  - `.venv/bin/ruff check src tests` — All checks passed.
  - `.venv/bin/ruff format --check .` — 48 files already formatted.
  - `.venv/bin/python -m pytest -q` — 337 passed.
  - repo-root `pnpm format:check` — passed (YAML/MD in play; goldens ignored).

## Task 19.2 — Golden tooling + `run-fixtures` CLI + fifth gate (2026-07-11)

- **What was built:** the `pipeline run-fixtures` subcommand — a two-tier golden
  comparator/regenerator sharing ONE projection path — plus the fifth mandatory
  verification gate in CLAUDE.md.
  - **Shared projection (pinned decision 3):** new
    `src/pipeline/run_fixtures.py::project_envelope` reduces a full
    `envelope.parse_document` envelope to the deterministic golden subset
    `{status, record, warnings, review_needed, error}`. BOTH tiers now build
    their projection by calling the real `parse_document` and projecting — no
    second serialization path. `build_golden` (tier 1) was re-implemented on top
    of `parse_document`; the retired inline `parse_docket_text`+`observe` path is
    gone. Regenerating all 32 tier-1 goldens through the new path produced a
    byte-identical result (`git diff` empty — see verification).
  - **Tier 1 (always runs):** compares the committed `tests/tier1/` corpus vs its
    goldens; readable field diffs (values safe — synthetic); every write gated by
    `--update-goldens` (committed-to-git files get NO unflagged write path — a
    missing golden without the flag is `missing`/refused, not silently created).
  - **Tier 2 (`--corpus-dir` only):** reuses the 16.2 `extraction.extract` + 18.1
    `envelope.parse_document` stages, per-docket exception capture (extraction
    failure, `failed` envelope, or any raise → `failed`, never aborts the run),
    goldens written OUTSIDE the repo as `{source_sha256}.json` (mirrors the
    `~/court-data/envelopes/` naming), default dir `~/court-data/goldens/`.
    Statuses: `match`/`diverged`/`updated`/`new`/`failed`. `new` writes without
    the flag (first creation); `diverged` needs the flag to overwrite (→
    `updated`, a distinct summary status, never folded into `match`); `failed`
    stays non-zero even WITH the flag. Console shows counts/statuses/hash-prefix
    ids/field PATHS only — the value-bearing diff goes to the out-of-repo report
    (`run-fixtures-tier2-report.json`). CI + missing-salt guards mirror `parse`.
  - **Retired:** `tests/tier1/generate_goldens.py` (folded into `run-fixtures
    --update-goldens`) and `tests/tier1/support.py` (folded into
    `pipeline.run_fixtures`); tier-1 tests now import from the src module.
  - **Fifth gate:** CLAUDE.md now requires `git status --short <paths>` +
    `git ls-files --others --exclude-standard <paths>` in every completion report
    for tasks adding committed files (the 19.1 gitignore incident).
- **Reuse decisions:** (a) `generate_goldens.py` RETIRED (one tier-1 write path).
  (b) Reused `equivalence_check.diff_records` (17.3 deep field-diff-with-
  exclusions) for tier-2, `extraction.extract` + `envelope.parse_document` for
  tier-2 envelopes (both already importable — no refactor), `seam_check.
  running_in_ci`, `paths.inside_git_worktree`, `equivalence_check.SALT_ENV_VAR`.
  Did NOT reuse `equivalence_check.compare_one`/`load_baseline` (baseline-shaped,
  wrong reference). (c) Tier-2 golden filename `{source_sha256}.json`, found in
  `envelope.run_parse` (the `~/court-data/envelopes/` convention). (d) NO
  `ci.yml` change — `tests/tier1/test_regression.py` (committed in 19.1) already
  runs the full 32-fixture regression under the existing pytest job.
- **Files touched:** `src/pipeline/run_fixtures.py` (new), `src/pipeline/cli.py`
  (run-fixtures wired: args + CI/salt guards + dispatch), `tests/test_run_fixtures.py`
  (new, synthetic-only), `tests/tier1/test_regression.py` + `test_index.py`
  (imports repointed), deleted `tests/tier1/generate_goldens.py` +
  `tests/tier1/support.py`, `CLAUDE.md` (fifth gate), `tasks/worklog.md`.
- **No parser/extraction/identity/helpers change.** No test reads/writes
  `~/court-data/`. No CI reference to `~/court-data/`.
- **Deviations from plan:** none. All three plan-review confirm-points
  implemented as approved (tier-1 fully gated incl. missing-golden refusal;
  `failed` non-zero even with the flag; `updated` a distinct status; support.py
  deleted outright).
- **Notes for next task:** tier-2 goldens are established by Chops's post-merge
  human run of `run-fixtures --corpus-dir ~/court-data/fixtures/` (feeds 20.2) —
  first run is all `new`; drift shows on later runs.
- **Verification (all five gates):**
  - `uv run ruff check src tests` — All checks passed.
  - `uv run ruff format --check .` — 48 files already formatted.
  - `uv run pytest -q` — 355 passed, 1 skipped.
  - repo-root `pnpm format:check` — passed (CLAUDE.md / worklog MD in play).
  - Staging completeness — `git status --short` / `git ls-files --others
    --exclude-standard` over the task paths show nothing untracked or ignored
    (output in the completion report).

### 19.2 fix (2026-07-11) — CI red: incomplete commit + sixth gate

- **Root cause:** the first 19.2 commit (`b36790b`) captured ONLY the two file
  deletions (`support.py`, `generate_goldens.py`). Those were staged early by the
  implementation-time `git rm` (which writes the index immediately); every OTHER
  change — `run_fixtures.py`, the `cli.py` wiring, the two test-import repoints,
  `test_run_fixtures.py`, the CLAUDE.md gate, this worklog — was only ever written
  to the working tree and never staged. The commit therefore deleted `support.py`
  while leaving `test_index.py`/`test_regression.py` still importing from it, and
  never added `pipeline.run_fixtures`. CI failed at collection
  (`ModuleNotFoundError: No module named 'support'`). The reported "355 passed"
  was genuine but run against the full working tree, not the staged/committed
  subset — precisely the gap the new sixth gate closes. The staging-completeness
  section of the original report even showed `run_fixtures.py`/`test_run_fixtures.py`
  as `??`; that signal was misread as "the git add will catch them."
- **Fix:** the follow-up commit stages the complete 19.2 change set (the prior
  commit's deletions stand). Imports already targeted `pipeline.run_fixtures` on
  disk; confirmed no remaining `from support import` anywhere (`git grep` clean).
- **Sixth gate added:** "Clean-environment gate timing" — the four functional
  gates must run LAST, after all edits are saved + staged and stale bytecode is
  cleared, and the report's gate output must come from that post-staging run.

## Task 20.1 — Parser Proof-of-Concept Report (2026-07-11)

- **What was built:** `agent-docs/parser-proof-of-concept.md`, the Sprint 4
  closing report assessing whether UJS CP/MC docket PDFs can reliably feed the
  product's charge-level analytics, with explicit per-court readiness verdicts
  for Sprint 5. Documentation only — no parser/pipeline/test/fixture/CI change.
  The report covers all twelve required sections: extraction approach (ADR
  0001), port summary, extraction-seam equivalence (17.1), baseline equivalence
  (17.3), the six hardening deltas with corpus-validated counts, the ten-code
  warning framework, the privacy classification, supported/unsupported
  patterns, major ambiguity cases, the OCR assessment, fixture-corpus coverage
  and gaps, and the per-court verdicts.
- **Cross-check performed (task requirement):** every pinned figure was
  reconciled against the worklog before writing. All reconciled with zero
  discrepancies: 17.1 seam 1,596/1,596 (CP 1,556 / MC 40, version_mismatch
  false); 17.3 baseline 100% equiv, CP 1,556/1,556, MC 40/40; Class D 3 nulls
  vs `SUSPECT_JUDGE_LINE` 5 (warnings-vs-diffs explained); Class E 16
  Transferred repairs; Item 3 zero diffs / zero specimens; Class A 926 keys /
  104 dockets held-case; Class B 1,842 min_assumed / 1,095 dockets; sentinel
  cost 7/1,603 ≈ 0.44%; quarantine 1; recovered 7 = 2 clean + 5 flagged;
  `ENVELOPE_PARSER_VERSION` 4 / record `parser_version` 2; court_type None
  corpus-wide; tier-1 32 fixtures with 2 `layout_unverified` MC; tier-2 1,603 =
  1,596 + 7. No STOP-AND-REPORT triggered.
- **Verdicts (evidence-led, per the PINNED requirement):** CP READY (1,556
  baseline, 100% equiv, all deltas classified); MC CORRECT-ON-EVIDENCE BUT
  UNDER-EVIDENCED (40 baseline records + 2 unverified layouts — parser correct
  on all available MC records but the evidence base is too thin to certify MC
  analytics; supplementation named as the path). "CP ready, MC needs more
  evidence."
- **Files touched:** `agent-docs/parser-proof-of-concept.md` (new),
  `CLAUDE.md` (workflow references repointed `docs/current-task.md` →
  `tasks/current-task.md`, 3 occurrences), `tasks/worklog.md` (this entry).
- **Deviations from plan / task scope (human-authorized):** two changes the
  task's Allowed-files list did not name, both explicitly approved by the human
  before implementation: (1) the report was written to `agent-docs/` rather
  than the task's stated `docs/parser-proof-of-concept.md`, resolving the
  conflict with CLAUDE.md's Documentation rule ("never create files in
  `docs/`"; agent-generated docs go to `agent-docs/`); (2) CLAUDE.md's workflow
  step 1 and two related references were repointed from `docs/current-task.md`
  to `tasks/current-task.md` (the actual live task-file location). No code,
  pipeline, or corpus change; no pinned decision reopened.
- **Notes for next task:** the six Sprint 5 handoff items are named (not
  planned) at the end of the report — judge normalization/validation,
  disposition-map cleanup, court_type populate-vs-drop, restitution taxonomy
  mapping, MC evidence deepening, and (Sprint 7) duration display units.

## Task 18.4 — Event-header capture fix (single-line) + value gate + record corrections (2026-07-11)

- **What was built:** the held-case event header is now captured as a **single
  line** (`<EventName> <MM/DD/YYYY> <Not Final|Final Disposition>`), replacing the
  18.3 two-line assumption (name line, then date at column 0). The 18.3 assumption
  left `event_date` null on 463/463 held charges and `event_name` mis-sourced on
  463/463 in the authoritative v4 corpus run — surfaced at the 20.2 exit demo,
  root-caused to the layout assumption, corpus-confirmed by a scan (date immediately
  left of the status token on 3,278/3,278 anchor lines; 0 at line start).
- **Parser fix** (`docket_parser.py`, disposition loop): the previous-line name
  lookahead is retired; a line ending in the status token is matched with the
  anchored `r"(\d{2}/\d{2}/\d{4})\s+(?:Final Disposition|Not Final)$"` —
  `event_date` = the date token immediately preceding the status token,
  `event_name` = the leading text before it on the same line. The placement sweep
  (event keys only on charges ending undisposed; latest non-terminal wins) and the
  `in_valid_event` routing (incl. the ARD `"ard" in event_name` special case) are
  unchanged in behavior. Two-line handling is not retained (no real specimen in
  3,278 anchors); it returns as its own task if a real specimen ever appears.
  **[18.5 pointer] This `"ard" in event_name` special case was the accidental
  ARD-routing mechanism, and correcting event_name off the case-status row here
  severed it (65+ charges lost ARD dispositions). Task 18.5 retires it and routes
  ARD from the charge-line token at EVENT grain — see the 18.5 entry.**
- **Version bump:** `ENVELOPE_PARSER_VERSION` **4 → 5** (behavior axis — same input,
  corrected values). Record `parser_version` **stays 2** (no schema change — same
  conditional keys, corrected values). `test_envelope.py`, the `run_fixtures.py`
  projection comment, and a `test_run_fixtures.py` sample were updated 4 → 5; no
  other hardcoded envelope-version-4 reference was found.
- **STOP-AND-REPORT during implementation — `ard_diversion_cp.txt` (honest
  history).** The plan asserted terminal fixtures were **inert** under the fix
  (terminal `event_name` is unused, date captured identically). Tier-1 report-mode
  run **falsified that for one fixture**: `ard_diversion_cp.txt` diverged. Root
  cause: ARD is a `Not Final` event routed as a **valid disposition** solely via
  `"ard" in current_event_name` — so ARD *does* consume `event_name`, and in the
  two-line fixture the name "ARD" sat on the orphaned line. This is a real
  terminal-golden drift; per the armed stop condition I halted and reported it
  rather than mass-editing or explaining it away. Chops authorized (Option 1)
  folding it to the corpus-canonical single-line `ARD 03/10/2025 Not Final`. I
  verified **in-memory, before writing**, that the single-line form reproduces the
  committed golden **byte-for-byte**; the on-disk correction then matched. A pinned
  unit test now covers ARD single-line routing (charge ends disposed, no event
  keys). No other fixture diverged — the full tier-1 run confirms only this one.
- **Fixtures (tier-1):** `held_cross_court_mc.txt` and `ard_diversion_cp.txt`
  folded to single-line (both goldens reproduced byte-for-byte);
  `multi_nonterminal_mc.txt` folded to single-line (latest-wins semantics
  unchanged); the two inline event regression tests + `mc_held_page()` +
  `HELD_FOR_COURT` folded likewise. New fixture **`held_multiword_event_cp.txt`**
  (+ golden, + index entry): a held CP docket whose multi-word event name
  ("Waiver of Preliminary Hearing") places the date token at **index 4 (≠ 2)**,
  guarding against a position-baked capture. `held_cross_court_mc`'s
  `layout_unverified: false` marking is **unchanged in value but now
  evidence-backed** — after correction it reflects the corpus-observed single-line
  layout (cite: the 3,278-anchor scan), where before it mismarked an invented
  two-line layout as verified.
- **Value-verification gate (closes the 18.3 verification gap):** unit tests assert
  held `event_date` is a real parseable date and `event_name` is a non-empty label
  (incl. the multi-word and trailing-whitespace cases). `equivalence_check.py` now
  computes a **fail-loud** held-charge value gate over the placement-sweep survivors
  (charges carrying event keys — the same set Class A counts): `event_date` non-null
  & date-parseable and `event_name` non-null on 100%, else the run returns exit 1
  and the report/console show `held_value_gate: FAIL`. The distinct `event_name`
  vocabulary **size** (expected ~26 case-normalized) is reported as an
  informational count — the event-name strings are never written (privacy).
- **Fixture-layout audit queued (Sprint 5 opening item).** `ard_diversion_cp` is the
  **second** confirmed specimen of the invented two-line layout (after
  `held_cross_court_mc`) — evidence the audit is necessary, not hypothetical. The
  remaining terminal fixtures still encode the two-line layout but parse inertly
  (goldens unchanged), so they were left untouched; their `layout_unverified: false`
  markings are not yet evidence-backed. **Follow-up:** verify every tier-1 fixture's
  event-header (and other section) layouts against corpus-observed formats and
  correct `layout_unverified` markings accordingly.
- **Record corrections (this PR):** 18.3 worklog entry carries an appended defect
  note + an inline pointer on its Class A bullet (history not rewritten); the POC
  report (`agent-docs/parser-proof-of-concept.md`) corrects every held-case
  event-date statement, adds the defect/fix and the verification-gap lesson, and
  updates the tier-1 count 32 → 33 and the envelope version 4 → 5; `fixture-index.yaml`
  gains the new fixture.
- **Files touched:** `src/pipeline/docket_parser.py`, `src/pipeline/envelope.py`,
  `src/pipeline/equivalence_check.py`, `src/pipeline/run_fixtures.py` (comment),
  `tests/test_docket_parser.py`, `tests/test_envelope.py`,
  `tests/test_equivalence_check.py`, `tests/test_run_fixtures.py`,
  `tests/tier1/fixtures/{held_cross_court_mc,ard_diversion_cp,multi_nonterminal_mc,held_multiword_event_cp}.txt`,
  `tests/tier1/goldens/held_multiword_event_cp.json`, `tests/tier1/fixture-index.yaml`,
  `agent-docs/parser-proof-of-concept.md`, `tasks/worklog.md`.
- **Deviations from plan:** one — the authorized in-scope extension to correct
  `ard_diversion_cp.txt` (the stop-report above). No other deviation; no pinned
  decision reopened.
- **FULL-CORPUS RERUN — standing local human step (Chops), NOT run in this task.**
  Fixtures live outside the repo. Provide the run its own NEW dated output dirs
  (never overwrite `full-corpus-18.3-fix`). Parse the corpus with the v5 parser,
  then run `equivalence-check` vs the immutable Capstone baseline. **Expected:**
  every divergence classifies into amended ledger classes A–E; Class A stays
  926 keys / 104 dockets (CP 91 / MC 13) on the same paths, now **populated**;
  `baseline_missing == 7` exactly; unclassified `== 0`; placement re-check 463
  event-key charges / 0 violations; **held_value_gate: PASS** with 100% populated
  and the distinct-vocabulary size (~26) reported. Quarantine/side sets are **not**
  rerun here (they get the v5 parser whenever next exercised). **ARD watch item:**
  any ARD-related divergence in the comparator rerun — disposition fields changing
  on ARD dockets, or ARD charges gaining/losing event keys — is **UNCLASSIFIED**
  under the current ledger and therefore **stop-and-report**, never folded into
  Class A. If real ARD dockets parse identically before/after, the rerun report
  should say so explicitly (count of ARD-routed events observed, zero divergence)
  — that is the confirmation the two-line lookahead's effect on ARD routing was
  fixture-only.
- **Notes for next task:** Sprint 5 opens with the fixture-layout audit above and
  the six 20.1 handoff items; the held-case value gate is the template for any
  future capture field (never certify values with a key-presence class alone).

## Task 18.5 (in progress) — Disposition-token scanner (RF1 evidence tooling) (2026-07-11)

- **Status:** first of five sequenced steps for 18.5 (supersedes the defective
  18.4 ARD routing; continues on the never-merged `task-18.4` branch). This
  commit lands ONLY the corpus token scanner. The parser routing redesign, the
  comparator UN-DISPOSAL check, the new `ard_progression_cp` fixture, and the
  record updates (deliverables 2–7) remain BLOCKED until Chops runs the scanner
  and the ARD_CLASS / NON_TERMINAL frozensets are finalized against its output.
- **What was built:** `services/pipeline/scripts/scan_disposition_tokens.py` —
  enumerates every distinct NON-EMPTY charge-line disposition token appearing
  under a Not-Final event across the extracted corpus, and cross-references each
  occurrence against the Capstone baseline (RF1). Per-token it reports corpus
  count, `disposed_under_event`, `held_under_event`, `raw_equals_token`, and a
  mechanical partition: `disposed_under_event == corpus_count` → ARD_CLASS;
  `disposed_under_event == 0 and raw_equals_token == 0` → NON_TERMINAL; else
  MIXED (a plan-level STOP). Exit code 1 whenever any MIXED token exists.
- **Why attribution, not final-state (the RF1 subtlety):** Capstone routed at
  the EVENT level (status-row "ard" fired for every charge under the event); the
  18.5 redesign routes at the CHARGE-LINE level. A charge held at "Held for
  Court" (Not Final) and later found guilty at a Final event is DISPOSED in its
  final baseline state, so a naive final-state split marks "Held for Court" both
  disposed (progressed charges) and held (held-forever charges) → a false MIXED
  on the commonest non-terminal. So an occurrence is `disposed_under_event` only
  when the disposition is ATTRIBUTABLE to this event: `baseline.disposition_raw
  == token`, OR `baseline.disposition_date` ∈ the event block's judge-line dates.
  `raw_equals_token` is the decisive signal for the wrapped revoked token — if
  any docket ENDS on a revoked event the baseline disposed it with the wrap
  token as raw, so it must be ARD_CLASS or the fix would itself un-dispose it;
  only the cross-reference sees this (the inspected progression docket cannot —
  its revoked write was masked by the terminal overwrite).
- **Placement decision (flagged):** committed under `services/pipeline/scripts/`
  rather than repo-root `scripts/` (the plan's literal path). CI lints Python via
  `uv run ruff check .` from `services/pipeline/`, so a repo-root `scripts/*.py`
  would escape every Python gate; under `services/pipeline/scripts/` it is
  ruff-checked and format-checked. Trivial to relocate if repo-root is preferred.
- **Privacy:** console prints CPCMS tokens + structural counts ONLY (no docket
  numbers, names, dates, or sequences); the detailed JSON artifact is written
  OUT-OF-REPO (default `~/court-data/scan-disposition-tokens/`) and keys dockets
  by source-hash prefix, never docket number (mirrors the tier-2 report). The
  scanner refuses to run in CI, refuses to write inside the git worktree, and
  requires `DEFENDANT_HASH_SALT` (never printed/written).
- **Validation (offline, synthetic):** a five-docket fictional corpus in the
  scratchpad exercised all three partitions — pure ARD → ARD_CLASS; held-forever
  AND held→Final-guilty both → NON_TERMINAL for "Held for Court" (proving
  attribution suppresses the false MIXED); ends-on-revoked + masked-by-terminal
  → MIXED/STOP for the wrap token. Zero docket-number/name leaks in the artifact.
  The synthetic corpus was deleted after the run.
- **Files touched:** `services/pipeline/scripts/scan_disposition_tokens.py`
  (new), `tasks/worklog.md` (this entry). No parser/comparator/fixture/CI change.
- **Next step:** Chops runs the scanner (command in the report), shares the
  token/count/baseline-partition output here; any MIXED token or any regressed
  charge whose baseline raw is not covered by ARD_CLASS ∪ the Final path is a
  STOP; then the frozensets are finalized and deliverables 2–7 implemented.

### 18.5 fix (2026-07-11) — scanner `artifacts_scanned=0` + Final-coverage attribution

- **Bug 1 (the reported defect): `artifacts_scanned=0`.** The scanner filtered
  each artifact on `status == "extracted"`, but 16.2 writes extraction status
  `success` (values are success/partial/needs_ocr_or_review/failed —
  `extraction.py:54-57`); the string `"extracted"` was a misread of a
  `run_extraction` log line. All 1,596 artifacts were skipped → empty table,
  exit 0. Discovery (`glob("*.json")`) was never at fault (1,596 top-level
  `{sha}.json`, no nesting). **Fix:** align to the 18.1 parse CLI's loading path
  — reuse `envelope._artifact_docket_number`, drop the status filter entirely
  (run_parse parses every artifact's `pages` regardless of status), and skip
  only empty-`pages` (`failed`) artifacts, which carry no disposition text.
- **Fail-loud guard (continuation item 3):** an empty table can no longer exit 0.
  `artifacts_scanned == 0` (dir empty, or all artifacts page-less) and a zero-token
  result both print an explicit stderr error and exit 2. Verified against an empty
  dir (exit 2).
- **Bug 2 (surfaced once real data flowed): attribution conflated Final-covered
  with must-route.** Real corpus shows terminal dispositions genuinely under
  Not-Final events (verified: "Quashed" under "Pretrial Bring Back … Not Final").
  Most are ALSO disposed under a Final event, which always routes, so the
  Not-Final token need not route. The old `disposed_under_event == corpus`
  partition wrongly flagged Guilty/Quashed/etc. as ARD_CLASS/MIXED. **Fix:** score
  each disposed occurrence as `not_final_only` (no Final event covers the seq —
  must route) vs `final_also_disposed` (Final path covers it); partition keys on
  `not_final_only`. Guilty→NON_TERMINAL (fcov 12/12), ARD - County→must_route
  94/97, the "Proceed to Court (ARD" wrap→NON_TERMINAL (0 disposed, 0 raw-match —
  answers RF1's ends-on-revoked worry: no docket ends on it in this corpus).
- **Display fix:** the token column no longer truncates at 40 chars (which had
  collapsed distinct `DUI: … 1st Off*` / `Permitting …` tokens into duplicate
  rows); full token printed, column width computed from the data.
- **Faithful-fragment finding (for adjudication, not fixed here):** the offense
  strip (mirrored verbatim from the parser) yields truncated tokens — "roceed to
  Court", "RD - County" — when the DISPOSITION section reprints a shorter offense
  than the CHARGES section and the divergence lands mid disposition-word (root
  example: CHARGES "Endangering Welfare of Children - Parent/…"; DISPOSITION
  "Endangering Welfare of Children - Proceed to Court" → strip eats "…- P" →
  "roceed to Court"). Harmless for Proceed-class (non-terminal), but "RD - County"
  is a must-route ARD fragment — a routing-mechanism design point for the plan.
- **Policy note:** per the 18.5 step-2 policy change, real `~/court-data/` is now
  agent-readable; the scan was run and root-caused directly here. Repo hygiene is
  unchanged — no real docket text/numbers in tree/commits; the committed console
  keeps token+count hygiene; the detailed artifact stays out-of-repo, hash-keyed.
- **Files touched:** `services/pipeline/scripts/scan_disposition_tokens.py`,
  `tasks/worklog.md`. No parser/comparator/fixture/CI change.
- **STOP:** table pasted in the report; partition finalization stays a
  plan-approval item (the ARD-County held/fcov edges, "Withdrawn" must_route=2,
  the "RD - County" fragment, and the 65↔95 charge-count reconciliation are the
  open adjudication points). No frozensets pinned; no parser work started.

## Task 18.5 — ARD routing decoupled from event_name (event grain) (2026-07-11)

- **What was built (deliverables 2–7):** ARD-class dispositions route again —
  restored on the never-merged task-18.4 branch — but now via the charge-line
  disposition TOKEN at EVENT grain, fully decoupled from event_name and the
  case-status row. Supersedes the defective 18.4 routing.
- **Mechanism (approved event grain).** A Not-Final event routes **iff its FIRST
  charge line's token is in `ARD_CLASS_DISPOSITIONS`**; a routed event disposes
  **ALL** its charge lines, each with its own token as `disposition_raw`. Final
  Disposition events route as always; latest-valid-event-wins unchanged. The
  retired `"ard" in event_name` special case is gone. Implemented as a tri-state
  `in_valid_event` (None = a Not-Final event whose first charge line — the
  decision point — has not yet been seen), resolved on that first line; corpus
  evidence shows the ARD line is first in 27/27 ARD-bearing events, so a forward
  state machine needs no buffering. `_charge_line_token` factors the offense/
  statute/grade strip so routing can read the token before deciding.
- **Two discoveries reframe the 18.3/18.4 defect history (records).** (1) The
  18.4 two-line lookahead had been capturing the CASE-STATUS ROW ("ARD - County
  Open", "Proceed to Court (ARD Revoked)"), not the event name — its `"ard"`
  substring is what accidentally routed ARD. (2) Capstone's routing was
  EVENT-grained: when that status-row `"ard"` fired, EVERY charge line under the
  event disposed (each with its own token), not just the ARD line. Together these
  explain both the regression (18.4 corrected event_name off the status row →
  severed routing) and why charge-line grain is insufficient (it would strand
  companion dispositions — see the Withdrawn specimen). The token is the TRIGGER
  for an event-level decision, not a per-line routing key.
- **Frozensets (pinned, corpus-evidenced from `scripts/scan_disposition_tokens.py`
  over 1,596 docs).** `ARD_CLASS_DISPOSITIONS = {"ARD - County", "RD - County"}`
  — the latter a corpus-evidenced strip fragment (the DISPOSITION section reprints
  a shorter offense than CHARGES, so the longest-prefix strip eats the leading
  "A"); kept as an exact fragment form (never a repair — the baseline carries the
  fragment too), 18.2 discipline. `NON_TERMINAL_DISPOSITIONS` = all 36 scanned
  NON_TERMINAL tokens VERBATIM (including the `ceed/oceed/roceed to Court` strip
  fragments, `Proceed to Court (ARD`, `Proceed to Ct (Nolle Prossed`, and the
  verbose un-stripped `DUI:*` / `Permitting*` tokens) so UNKNOWN warns only on
  genuinely novel vocabulary. `Withdrawn` and the wrap token stay OUT of ARD_CLASS
  permanently — they only ever dispose as COMPANION (non-first) lines under an
  already-routed ARD event, which event grain reproduces without their being
  triggers.
- **Warning vocabulary 10 → 11:** `UNKNOWN_NOT_FINAL_DISPOSITION` (review
  severity, sets review_needed). Fires when a Not-Final event's FIRST charge-line
  token is in neither frozenset (the routing decision point), OR when an ARD_CLASS
  token is stranded on a NON-FIRST line of an UNROUTED event (the non-ARD-first
  guard; corpus 0/27 today). Structural context only (section, sequence) — never
  the token text.
- **Comparator UN-DISPOSAL check (permanent, deliverable 6):** a named,
  always-fail category — charges disposed in the baseline but undisposed in the
  corpus parse — reported distinctly (`un_disposal` block + txt/console lines),
  never folded into generic divergence counts; the run returns non-zero if
  `charges > 0`. The 18.4 regression is the motivating specimen.
- **New tier-1 fixture `ard_progression_cp` (deliverable 5):** the observed
  progression + companion-withdrawal shape — status rows, a `Status` (Not-Final)
  event whose first line `ARD - County` routes it with judge + ARD sentence, a
  companion seq2 `Withdrawn` disposing under the same routed event, a wrapped
  `Proceed to Court (ARD` / `Revoked)` revoke event held, and a terminal
  `Waiver Trial` (Final) carrying NO judge/sentence line — so the golden shows
  seq1 `disposition_raw` "Nolle Prossed" from the terminal event but judge / date
  / sentence from the ARD event (RF3). Fictional throughout; zero-sequence docket;
  `layout_unverified: false` (evidence: this task's human inspection + the scan).
  All 33 prior tier-1 goldens are byte-identical (event grain leaves held/ARD
  fixtures unchanged: their first-line tokens are empty→held or `ARD - County`→
  routed exactly as before).
- **Pattern B (deliverable 3) confirmed same root cause:** on the real docket
  (hash-prefix `17d1d0d787d9`) the ARD `Status` event carries judge + sentence and
  the Final `Waiver Trial` carries only the disposition, so v5 (un-routed ARD)
  lost judge/sentence-date/sentence while the Final event supplied
  disposition_raw; the fix routes the ARD event and the Final overwrites raw only.
  The 2 shifted-sentence dockets (`1d40e633ab36`, `fef3d2dff345`) are the identical
  shape (sentences mis-attributed off the un-routed ARD event).
- **Restoration reconciliation (acceptance amendment, approved):** the true
  baseline-anchored restoration is **68 distinct charges / 19 dockets** — 66
  ARD-class (65 `ARD - County` + 1 `RD - County` fragment) + 2 `Withdrawn`
  companions on the discriminator docket (`7ed52b93628c`). The triage's 65
  undercounted by 3 (the fragment + the 2 companions); the scan's earlier "95/97"
  was occurrence-vs-charge double counting (94 `ARD - County` occurrences map to
  65 charges, since a charge recurs under multiple Not-Final events). Genuine held
  (Class A) is 463 charges / 926 keys / 104 dockets (CP 91 / MC 13) — unchanged;
  under event grain the 68 regression charges move held→disposed and post-fix held
  returns to exactly 463 (charge-line grain would strand the 2 Withdrawn → 465 +
  UN-DISPOSAL 2).
- **Files touched:** `src/pipeline/docket_parser.py` (frozensets, token helper,
  event-grain routing), `src/pipeline/warning_codes.py` (+ its test),
  `src/pipeline/equivalence_check.py` (UN-DISPOSAL check),
  `tests/test_docket_parser.py`, `tests/test_equivalence_check.py`,
  `tests/test_warning_codes.py`,
  `tests/tier1/fixtures/ard_progression_cp.txt`,
  `tests/tier1/goldens/ard_progression_cp.json`, `tests/tier1/fixture-index.yaml`,
  `tasks/worklog.md`. No change to single-line capture, placement sweep, value
  gate, version numbers (envelope stays 5, record parser_version stays 2),
  junk-judge, truncation repairs, min_assumed, or sentinel logic.
- **POC report update DEFERRED (out-of-scope state change — flagged, not done).**
  Deliverable 7 also names the POC report, but it is mid-move by the human:
  `agent-docs/parser-proof-of-concept.md` is deleted from the working tree and an
  untracked copy now sits at `docs/parser-proof-of-concept.md`, which CLAUDE.md
  forbids the agent from editing. I did not touch either. The case-status-row and
  event-grain reframing is recorded here in full; the POC edit awaits the human's
  decision (commit the move first, edit the docs/ copy as an approved exception,
  or self-update).
- **18.4 worklog entry:** carries an inline 18.5 pointer on its routing bullet.

## POC report corrections (docs-only) — §6 warning count + Sprint 5 handoff + §5 figure verify (2026-07-11)

- **Date:** 2026-07-11
- **Scope:** Three pre-sprint-close corrections to
  `agent-docs/parser-proof-of-concept.md`. Documentation only — no code,
  fixture, golden, or test change.
- **What changed:**
  - **§6 warning count:** "Ten stable codes" → "Eleven stable codes",
    naming the eleventh (`UNKNOWN_NOT_FINAL_DISPOSITION`, review severity,
    added in 18.5). Aligns §6 with the executive summary's already-correct
    "eleven-code warning framework". Structural-context and
    no-numeric-confidence bullets unchanged.
  - **Sprint 5 handoff list:** added item 6 — structured CP↔MC held-case
    linkage (deferred from 18.3; Sprint 4 captured raw cross-court held-case
    data only; structured attribution is the Sprint 5 landing task; §5 ref).
    The display-units item was retained, renumbered 6 → 7, still labeled
    Sprint 7.
  - **§5 reverted-design figure:** VERIFIED, no edit. The 18.2 worklog entry
    (this file) is the authority and reads verbatim "Item 2's pure-prose
    append gate produced ~535 divergent dockets whose appended tails were NOT
    disposition prose." The report already said "~535 dockets" — it matches
    the worklog. `538` appears nowhere in the worklog; the "538 standing
    record" was the erroneous source and is outside this file's scope. No
    change made.
- **Files touched:** `agent-docs/parser-proof-of-concept.md`, `tasks/worklog.md`.
- **Deviations from plan:** none.
- **Notes for next task:** the POC report now lives at
  `agent-docs/parser-proof-of-concept.md` (the 18.5-flagged docs/ move was
  not in play for this task). §6 and the executive summary are now consistent
  on the 11-code vocabulary; the Sprint 5 handoff list is items 1–7.

## Task 19.3 — `run-fixtures` Contract Hardening (Tier 2) (2026-07-11)

- **Scope:** Closed the two tier-2 `run-fixtures` contract gaps confirmed in the
  20.2 exit demo (silent generate-on-missing; report clobbering). Tier-1
  behavior, `equivalence_check.py`, parser modules, golden CONTENT, envelope/
  record versions (`ENVELOPE_PARSER_VERSION=5`, record `parser_version=2`), and
  the 11-code warning vocabulary are all unchanged.
- **Contract changes + chosen mechanisms:**
  - **GAP 1 — golden writes are always flag-gated (disjoint, least-privilege
    flags).** A tier-2 run with NO golden-writing flag now writes ZERO goldens
    under all conditions, including an empty goldens dir. A docket lacking a
    golden gets the new per-docket status `golden_missing` (added to the tier-2
    vocabulary and `_T2_ORDER`) and the run exits nonzero; present-golden
    dockets are still compared in the same run (per-docket isolation holds — one
    missing golden never aborts the corpus). Two disjoint flags replace the old
    silent first-creation path: `--init-goldens` writes ONLY absent goldens
    (first-time establishment) and NEVER overwrites a divergent existing golden;
    `--update-goldens` refreshes ONLY existing goldens that diverge (semantics
    unchanged) and NEVER creates an absent one. Passing both together is an
    explicit full-write mode (absent created, divergent refreshed). Rationale of
    record: least privilege — an establishment run must not be able to silently
    clobber an existing golden, and a refresh must not silently create a new
    baseline; overloading one flag re-opens the "tool self-adjudicates what's
    fine" failure shape. Help text for BOTH flags states the combined full-write
    behavior and that EVERY golden-writing invocation requires a
    `tasks/worklog.md` note.
  - **GAP 2 — dated, non-clobbering reports.** Each tier-2 run now writes its
    report to a run-unique path `<output-dir>/reports/tier2-report-<UTC
    timestamp>.json` (microsecond precision — `%Y%m%dT%H%M%S_%fZ`), matching the
    corpus-run "new dated artifact, never overwrite" convention and moving
    reports out of the goldens dir (goldens stays hash-named-files only). A
    single clock read per run (`_now_utc`, wrapped so tests can force the stamp)
    names both the file and the report's `generated_at`. Belt-and-suspenders: if
    the computed path already exists the run refuses (rc 2) rather than
    overwrite. Console prints the report path at end of run (path/counts/
    statuses only — hygiene preserved).
- **Retroactive golden-establishment note (owed from the 20.2 exit demo):** the
  tier-2 goldens on disk are the post-18.5 set — all 1,603, established
  2026-07-11, back-to-back verification 1,603 match / 0 diverged. This 19.3 task
  did NOT change golden content.
- **Superseded artifact:** the old fixed
  `~/court-data/goldens/run-fixtures-tier2-report.json` is no longer written; it
  remains on disk as a stale, superseded artifact (out-of-repo). New reports
  land under `~/court-data/goldens/reports/`.
- **Real-corpus verification run (verbatim tool output):**

  ```
  tier1: match=34 diverged=0 updated=0 new=0 missing=0
  tier2: match=1603 diverged=0 updated=0 new=0 golden_missing=0 failed=0
  tier2 report: ~/court-data/goldens/reports/tier2-report-20260711T213310_122609Z.json
  EXIT_CODE=0
  ```

  1,603 match / 0 diverged against the existing goldens; zero goldens written
  (dir still holds 1,603); report landed at the new run-unique path.
- **Files touched:** `services/pipeline/src/pipeline/run_fixtures.py`,
  `services/pipeline/src/pipeline/cli.py`,
  `services/pipeline/tests/test_run_fixtures.py`,
  `services/pipeline/README.md`, `tasks/worklog.md`.
- **Deviations from plan:** none. (README carried run-fixtures only as a stale
  "placeholder"; per FIX 4 the authoritative flag docs live in the CLI `--help`
  and a focused run-fixtures section was added to the README documenting the
  19.3 flag/report contract — no silent gap between `--help` and README.)
- **Notes for next task:** no new committed file tree is introduced — reports
  live out-of-repo under `~/court-data/goldens/reports/`. `golden_missing` is a
  dirty (nonzero-exit) tier-2 status. First-time tier-2 establishment now
  requires `--init-goldens` explicitly; a plain comparison run over a dir with
  any absent golden fails with `golden_missing` by design.

## Task 21.1 — `raw.source_documents` + `parsed.*` Table Migrations (2026-07-11)

- **What was built:** Two Kysely migrations creating the internal document
  layer and the parsed layer — the 21.3 loader's write target; nothing writes
  to them in this task. `db/migrations/20260711225105_create_raw_source_documents.ts`
  creates **`raw.source_documents`** (MUTABLE, pin 2): uuid PK
  `gen_random_uuid()`, `file_hash` (unique `source_documents_file_hash_key`),
  and the 16.3 manual-import metadata record mirrored exactly —
  `original_filename`, `file_size_bytes` (bigint), `imported_at`, `import_mode`
  (record `mode` → column `import_mode`, confirmed), `status`, `error_code`
  (null), and the `derive_provenance` triple `docket_number_provenance`/
  `court_type`/`county` (all nullable — null on docket-number no-match); plus
  `created_at`/`updated_at` reusing the shared `public.set_updated_at()`
  trigger (6.1-owned; NOT recreated). `court_type` here is the raw CP/MC
  filename code — deliberately distinct from `parsed.dockets.court_type_recorded`.
  `db/migrations/20260711225106_create_parsed_tables.ts` creates the five
  **`parsed.*`** tables (all IMMUTABLE load artifacts, pin 3 — `created_at`
  only, no `updated_at`, no trigger; `loaded_at` additionally on dockets):
  `parsed.dockets` (FK → `raw.source_documents` **RESTRICT**, unique
  `source_document_id`), `parsed.charges` (FK → dockets **CASCADE**, unique
  `(docket_id, sequence)`), `parsed.sentences` (FK → charges **CASCADE**),
  `parsed.warnings` (FK → dockets **CASCADE**), `parsed.related_cases` (FK →
  dockets **CASCADE**). `db/src/types.ts` gained six interfaces + `Database`
  keys: `RawSourceDocumentsTable` mutable (trigger-typed `updated_at`), all
  five parsed tables `Immutable<>` on every column (aggregate-row precedent).
  `db/tests/parsed-schema.test.ts` (6 checks, all inside rolled-back
  transactions, 6.1 precedent): duplicate `file_hash`; orphan
  `source_document_id`/`docket_id`/`charge_id` FK violations; duplicate
  `parsed.dockets.source_document_id`; duplicate `parsed.charges (docket_id,
  sequence)`. `db/tsconfig.json` include gained `"tests"` (trivially
  necessary). `db/README.md` gained a Migrations table (all five files) and the
  FK-index reading (pin 5 satisfied by leading unique indexes on
  `dockets.source_document_id` and `charges.docket_id`).
- **Reading of the committed shapes (per-table nullability, all derived from
  the committed 16.3 record / 17.2 parser record / 18.1 envelope):**
  - `raw.source_documents`: NOT NULL — `id`, `file_hash`, `original_filename`,
    `file_size_bytes`, `imported_at`, `import_mode`, `status`, `created_at`,
    `updated_at`; NULL — `error_code`, `docket_number_provenance`, `court_type`,
    `county` (the provenance triple is null on docket-number no-match).
  - `parsed.dockets`: NOT NULL — `id`, `source_document_id`, `docket_number`,
    `record_parser_version`, `envelope_parser_version`, `parsed_at`, `county`
    (record hardcodes "Philadelphia"), `defendant_hash` (always computed,
    docket_parser.py:508), `envelope_status`, `review_needed`, `created_at`;
    NULL — `court_type_recorded` (nullable per pin though detect_court_type
    always returns a value), `court_type_derived` (21.3 populates),
    `case_status`, `filed_date`, `otn`, `dc_number`, `cross_court_dockets`
    (jsonb), `assigned_judge_raw`, `loaded_at` (21.3 populates). All the NULL
    docket fields default to `None` in the parser (docket_parser.py:523-583,
    972).
  - `parsed.charges`: NOT NULL — `id`, `docket_id`, `sequence`, `created_at`;
    NULL — `statute`, `grade`, `offense`, `disposition_raw`, `disposition_date`,
    `disposition_judge_raw`, `event_name`, `event_date` (event_* are the
    conditional held-charge keys, SD 12).
  - `parsed.sentences`: NOT NULL — `id`, `charge_id`, `component_order` (load-
    assigned list position), `sentence_type`, `min_assumed` (default false),
    `raw_text`, `created_at`; NULL — `min_days`, `max_days`, `program`,
    `sentence_date`. `raw_text` NOT NULL verified against the parser:
    `raw_text_parts` always initializes to `[line_str]` (the non-empty
    sentence-type line, docket_parser.py:926) and `raw_text = ", ".join(...)`
    (:696) — no code path emits a sentence without `raw_text`, so the standing
    NOT NULL decision holds with no parser finding.
  - `parsed.warnings`: NOT NULL — `id`, `docket_id`, `code`, `created_at`;
    NULL — `section`, `charge_sequence`, `page`, `field` (exactly the
    make_warning optional structural fields, warning_codes.py:89-114).
  - `parsed.related_cases`: NOT NULL — `id`, `docket_id`, `docket_number`,
    `created_at`; NULL — `court`, `association_reason`.
- **Files touched:** `db/migrations/20260711225105_create_raw_source_documents.ts`
  (new), `db/migrations/20260711225106_create_parsed_tables.ts` (new),
  `db/src/types.ts`, `db/tests/parsed-schema.test.ts` (new), `db/tsconfig.json`,
  `db/README.md`, `tasks/worklog.md`.
- **Deviations from plan:** (1) `assigned_judge_raw text null` ADDED to
  `parsed.dockets` per human answer — confirmed spec gap; 23.1 judge
  attribution + 22.3 roster curation need the docket-level assigned judge
  alongside the charge-level disposition judge. (2) The always-empty record
  `notes` field is INTENTIONALLY not stored (no producer) — recorded per human
  instruction. (3) `created_at` added to ALL five parsed tables, not just
  dockets: the descriptive Tables list showed it only on dockets, but pin 3
  ("created_at ... only, NO updated_at") reads as authoritative over the shape
  sketch and every immutable aggregate table carries `created_at` (6.2
  precedent); flagged in the completion report rather than silently chosen.
- **Notes for next task (21.3 loader):** absence → NULL/false is the loader's
  job (SD 12): held-charge `event_name`/`event_date` and `min_assumed` are
  ABSENT in JSON when inapplicable; map to NULL / false explicitly. `mode` →
  `import_mode` and `file_size_bytes` mirror the 16.3 record names. `component_order`
  is NOT in the record — assign it from the sentence list position at load.
  `court_type_derived` and `loaded_at` are unpopulated (nullable) until the
  loader fills them; `court_type_recorded` takes `case.court_type` as-is. Parsed
  tables are `Immutable<>` — a docket reload is delete-and-reinsert (CASCADE
  clears the tree), never an UPDATE/upsert. `cross_court_dockets` is jsonb.

## Task 21.2 — `fact.*` + `review.queue_items` Table Migrations

- **Date:** 2026-07-11
- **What was built:** Two Kysely migrations, `db/src/types.ts` typing for the
  four tables, one Python vocabulary module + tests, and a `db/tests`
  constraint-violation suite.
  - `20260711230001_create_fact_tables.ts` — `fact.fact_build_runs` (MUTABLE:
    created_at + updated_at + reused `public.set_updated_at()` trigger),
    `fact.charge_outcomes` and `fact.charge_sentences` (IMMUTABLE facts,
    created_at only). Per-run natural keys `UNIQUE (build_run_id,
    parsed_charge_id)` and `UNIQUE (build_run_id, parsed_sentence_id)`. FK ON
    DELETE: CASCADE from the build run and from the parent outcome fact; RESTRICT
    into `parsed.*` and `ref.*`.
  - `20260711230002_create_review_queue_items.ts` — `review.queue_items`
    (MUTABLE, trigger). `dedup_key` NOT NULL UNIQUE. FK ON DELETE: RESTRICT (NOT
    NULL) to `raw.source_documents`; SET NULL (nullable) to the three `parsed.*`
    pointers. `raw_value` / `candidate_context` carry Postgres column comments
    marking them structural-only.
  - `services/pipeline/src/pipeline/fact_review_vocab.py` — the five closed
    vocabularies (12 review item types, 3 severities, 4 item statuses, 3
    fact-build-run statuses, 12 eligibility reason codes) + the documented
    `dedup_key` composition. `test_fact_review_vocab.py` asserts uniqueness,
    non-emptiness, and the severity anti-collision guards.
- **Verification (against local Postgres 5433):** `migrate:latest` → `down` ×2 →
  `latest` clean; a `pg_constraint`/`pg_indexes` dump confirmed every pinned FK
  ON DELETE (c/r/n), both natural-key UNIQUEs, the `dedup_key` UNIQUE, both
  `set_updated_at` triggers, and the FK-index rule (build_run_id fronts its
  UNIQUE on both fact tables and gets no standalone index; every other FK column
  does). Gates: `ruff check` clean, `ruff format --check` clean, `pytest -q`
  green, `pnpm format:check` clean, db `typecheck` clean, db `vitest` 18/18
  (6 new rolled-back constraint tests).
- **Pinned-decision mirroring recorded in the report:** `parser_version` and
  `envelope_parser_version` on `fact_build_runs` are `integer`, EXACTLY the 21.1
  `parsed.dockets.record_parser_version`/`envelope_parser_version` types (no
  cross-layer mismatch, per approval item 4). Severities are `high`/`medium`/
  `low`, renamed away from `blocking`/`warning` to avoid colliding with the
  `blocking_warning` eligibility code and the parser warning-code severity
  vocabulary (approval item 3). `min_days` AND `max_days` are both nullable,
  mirroring `parsed.sentences` (approval item 2).
- **Files touched:** `db/migrations/20260711230001_create_fact_tables.ts` (new),
  `db/migrations/20260711230002_create_review_queue_items.ts` (new),
  `db/src/types.ts`, `db/tests/fact-review-schema.test.ts` (new — allowed-files
  list extended to cover it per approval item 1), `db/README.md`,
  `services/pipeline/src/pipeline/fact_review_vocab.py` (new),
  `services/pipeline/tests/test_fact_review_vocab.py` (new), `tasks/worklog.md`.
- **Deviations from plan:** none — all six required fixes applied as approved;
  no scope beyond the approved file list.
- **Notes for next task:** Nothing writes to these tables yet. 22.1 implements
  the `dedup_key` builder (composition documented in `fact_review_vocab.py`) and
  the review-item construction helpers that enforce these vocabularies; the DB
  stores the results. The per-run UNIQUEs are the "one fact candidate per parsed
  charge/sentence per build run" guarantee — the 23.2/23.3 builders reinsert via
  the build-run FK CASCADE, never `ON CONFLICT DO UPDATE` (fact rows are
  `Immutable<>`). `counts` is nullable jsonb (null while `in_progress`).

 HEAD
## Task 21.3 — Python DB Access + `pipeline load` + Canonical Corpus Load (2026-07-11)

- **What was built:** psycopg 3 (sync) DB access for the pipeline and the
  `pipeline load` command, which reads per-docket envelope artifacts and writes
  them into the frozen 21.1 `raw.source_documents` + `parsed.*` tables. Executed
  the first canonical corpus load (all 1,603 envelopes) end-to-end against the
  local DB and reconciled it against the known warning tallies.
- **DB module (`db.py`):** owns connection construction only — no pool, no ORM.
  `DATABASE_URL` is read at the CLI boundary (`cli.py`) and passed in; the module
  never reads the environment and never auto-loads `.env`. Empty URL is a hard
  failure. psycopg pinned EXACT: `psycopg[binary]==3.3.4` (`[binary]` ships libpq
  so CI/local need no system libpq).
- **Loader (`load.py`):** one docket = one transaction (raw upsert + full parsed
  graph commit/roll back together); per-docket exception isolation. Idempotency
  keyed on source file hash + `(envelope_parser_version, record_parser_version)`
  tuple: same→skip after a re-SELECT canonical content re-check (zero writes),
  newer→transactional replace (DELETE docket row, CASCADE clears children,
  reinsert + UPDATE raw), older→refuse, equal-version-but-different-content→
  per-docket failure + stop-and-report. Accepted envelope version set = `{5}`
  (read from each envelope; anything else = per-docket failure). `component_order`
  = sentence list index; `min_assumed` absent→false; `event_name/event_date`
  absent→NULL; `cross_court_dockets` (str|null) → jsonb scalar via `Json()`.
- **Rulings applied (this task's plan review):**
  - **Q1** — failed-parse envelopes create NO `parsed.*` rows (fabricating
    NOT-NULL `defendant_hash` etc. is dishonest data). They upsert only the raw
    row with loader status `parse_failed` and the envelope's error code; review
    visibility is via `raw.source_documents`, fact exclusion is structural.
  - **Q1/Fix 1** — the minimal-row arm was DELETED: the loader never synthesizes
    a raw row from envelope fields. A missing 16.3 import record = broken
    provenance = per-docket failure with NO rows (recovery: re-run idempotent
    `import-manual`). There are NO sentinel/"unknown" column values anywhere in
    the loader.
  - **Q2** — `court_type_recorded` ← `record.case.court_type` AS-IS. Note it is
    itself derivation-sourced (`detect_court_type()` on the docket number), NOT
    an independently captured banner value — so it is populated for every docket
    (1,603), not near-empty; AC 8e amended to report actuals.
  - **Fix 2** — the loader test suite HARD-FAILS in CI when `DATABASE_URL` is
    unset (a wiring regression), and SKIPS locally with a visible skip count.
  - **Fix 3** — seven run-report categories, reconciling to the envelope count:
    `loaded / skipped_same_version / replaced_newer_version /
    refused_older_version / failed_envelope_loaded / failed_exception /
    missing_import_record`. Nonzero `failed_exception` or `missing_import_record`
    → nonzero exit (fail-loud).
  - Intentional non-loads (no target columns; listed in the README note, never
    silent): `record.notes`, and `extraction_artifact.text_hash`/
    `provenance_path` (artifact_id == source hash, stored as `file_hash`).
- **CI:** the Python job gains a Postgres 17.10 service; the repo Kysely
  migrations are applied via the real migrator (`pnpm db:migrate:latest`) before
  `uv run pytest` (no hand-maintained SQL, no drift). CI never references
  `~/court-data/`; the real `load` command refuses to run in CI.
- **ACCEPTANCE RUN (verbatim in the completion report):** boot (`pnpm generate`
  + `db:migrate:latest` = "No pending migrations"); full load =
  `loaded=1603 ... total=1603`; row counts source_documents 1603 / dockets 1603
  / charges 3625 / sentences 4162 / warnings 617 / related_cases 658; identical
  re-run = `loaded=0 skipped_same_version=1603` with `updated_at`/`loaded_at`
  max/min/count UNCHANGED (zero changed rows). Warning reconciliation ALL MATCH:
  UNPARSEABLE_DURATION 280, MISSING_DISPOSITION_DATE 211, NON_TERMINAL_CASE 104,
  SENTINEL_COLLISION 17, SUSPECT_JUDGE_LINE 3, UNKNOWN_NOT_FINAL_DISPOSITION 2;
  review_needed = 75 dockets. court_type actuals: recorded populated 1,603
  (Common Pleas 1,563 / Municipal Court 40), derived populated 1,603 (CP 1,563 /
  MC 40). Optional 8f (quarantine specimen) NOT RUN: no failed-status v5 envelope
  exists among accessible artifacts (canonical set has none; recovered quarantine
  specimens are older-format `status=success` records) — the failed arm is proven
  synthetically.
- **Files touched:** `services/pipeline/pyproject.toml`,
  `services/pipeline/uv.lock`, `services/pipeline/src/pipeline/db.py` (new),
  `services/pipeline/src/pipeline/load.py` (new),
  `services/pipeline/src/pipeline/cli.py`,
  `services/pipeline/tests/test_load.py` (new),
  `services/pipeline/README.md`, `.github/workflows/ci.yml`, `tasks/worklog.md`.
- **Deviations from plan:** none beyond the four rulings + three fixes applied as
  directed (minimal-row arm removed; imported_at STOP resolved by Option 3).
  Branch note: the session was checked out on `col-2-search-collector` (=
  `phase-21` + the COL-2 commit); 21.3 was landed on `phase-21` as instructed by
  reverting the local `cli.py` edit, switching, and re-applying only the load
  wiring so no COL-2 collector code was dragged in.
- **Notes for next task:** the parsed layer now holds the canonical 1,603-docket
  corpus (row counts above). Phase 22 (fact generation) reads `parsed.*` filtered
  by `envelope_status = 'parsed'`; failed envelopes never produced parsed rows so
  they are excluded structurally. `loaded_at` is set per docket; a reload is a
  DELETE+reinsert (new `parsed.dockets.id`), so downstream must not cache docket
  ids across a reload.

## Task 21.3-f1 — Loader tests fail closed on non-test databases (2026-07-11)

- **Why:** the loader suite TRUNCATEs tables against whatever DB the env pointed
  at; it previously read `DATABASE_URL` (the dev DB) and destroyed the canonical
  load when the pytest gate ran. Once fact/review data exists this is silent data
  destruction by CI/local gates.
- **Guard 1 (env isolation):** the suite now reads ONLY
  `PIPELINE_TEST_DATABASE_URL` and never `DATABASE_URL`, so it structurally cannot
  truncate the database the `load` command writes to. Unset → local skip (visible
  count) / CI hard failure (unchanged Fix-2 semantics).
- **Guard 2 (dbname pattern):** before any truncation the connected database name
  must contain "test"; any other name is a hard failure regardless of which var
  supplied the URL (belt-and-braces against env-var mixups). Verified live:
  pointing the var at the dev DB `pca` hard-fails BEFORE truncating.
- **Both guards are pure/testable:** `_classify_test_db_url` and `_is_test_dbname`
  are unit-tested (absent→skip local / fail CI; present→run; non-test name
  rejected, case-insensitive) — DB-free arms that run everywhere.
- **CI:** the Python job's service DB is renamed `pca_pipeline_test` (contains
  "test"); the migrator step (`DATABASE_URL`) and the pytest step
  (`PIPELINE_TEST_DATABASE_URL`) target that same URL.
- **Docs:** both guards documented in the pipeline README loader-semantics note.
- **Files touched:** `services/pipeline/tests/test_load.py`,
  `.github/workflows/ci.yml`, `services/pipeline/README.md`, `tasks/worklog.md`.
- **Deviations from plan:** none.
- **Post-fix ops:** local test DB `pca_pipeline_test` created + migrated; canonical
  load re-run against the dev DB to repopulate it for Phase 22 (see completion
  report), and confirmed the pytest gate (now bound to the test DB) leaves the
  dev DB's 1,603 dockets untouched.

## Task COL-2 — Search-Mode Discovery: Date-Filed Advanced Search Collector (2026-07-11)

- **Date:** 2026-07-11
- **Goal:** add a Date-Filed search discovery mode to the collector (ported from
  Capstone `collect.py`/`fetch_mc_fixtures.py`): one advanced search per calendar
  day (County=Philadelphia), classify the results grid, harvest CP/MC-51-CR
  docket numbers + sheet hrefs, fetch PDFs per `--court`. Enumeration mode
  retained byte-for-byte as audit mode.
- **Step 0 live-DOM recon (5 jittered searches, 0 fetches, headful) pinned:**
  docket-number cell = **column index 2** (`thead th[2]` label is "Docket
  Number"; every CP/MC-51-CR data row carries its number there; caption=4,
  participant=7, DOB=8 are never touched); sheet anchor = row-scoped
  `a[href*='CpDocketSheet']` (first CP-51-CR row and first MC-51-CR row both
  resolve to `CpDocketSheet`; `MdjDocketSheet` is MDJ-only and always skipped);
  truncation banner = presence of substring "Not all results are shown for
  Common Pleas and Magisterial" (absent at 1 day / 181–241 rows, present at 3
  days / 805 rows); grid_empty marker (Blocker-2/Option A, operator-approved) =
  served search UI + no block + zero rows (future date 2027-06-01 rendered the
  search form with NO results table and 0 rows — no bespoke "no records" node
  exists).
- **Two Step-0 STOP-report contract gaps, both operator-adjudicated:** (1) AC-10's
  "expected-empty Sunday 2025-06-01" is false — Philadelphia MC arraignment court
  files 7 days/week (2025-06-01 returned 181 rows / 38 MC-51-CR); smoke empty
  window reassigned to **2027-06-01** (Option A). (2) grid_empty has no dedicated
  DOM marker; the served-search-UI basis (same as COL-1a `no_results`) was
  accepted as the positive marker.
- **Module structure (parallel to enumeration; enumeration untouched, AC-9):**
  new `search_classification.py` (`SearchSignal` + `classify_search`: 4
  fail-closed states grid_complete/grid_truncated/grid_empty/blocked, `error`
  prior branch), `harvest.py` (`harvest_rows` — the PD-3 privacy invariant),
  `window.py` (`daily_windows` + append-only window ledger writer/loader mirroring
  COL-1b), `search_engine.py` (the pure run loop), `search_transport.py`
  (Playwright adapter, browser restart every 150 fetches). Reused unchanged:
  `RunGuard` streaks, `FetchSignal`/`classify`, and enumeration constants/helpers.
- **Required fixes folded in:** **F1** `--court` widened to {MC,CP,both}; enumerate
  mode still rejects non-MC via a mode-aware `parser.error` carrying "invalid
  choice" (existing `test_collect_rejects_non_mc_court` passes verbatim). Ledger
  override flag named **`--recheck-windows`** (not the spec's "--research-windows"
  typo). **F2** batch counter counts ALL real portal requests — searches AND
  fetches (skips excluded); inter-batch cooldown fires on the combined count;
  `parameters.batch_request_counting = "searches_and_fetches"` records it. **F3**
  a blocked search writes a ledger entry (`outcome=blocked`, retryable); a
  transport-level exception (error) writes NONE (window stays unsearched) — both
  tested. **F4** `_pdf_from_href` + block presence-checks are duplicated into
  `search_transport.py` with inline comments naming their `transport.py` source;
  "collector transport consolidation" is flagged here as a future landing
  candidate. **F6** grid_complete and grid_empty both reset block/error streaks
  (tested).
- **Pinned-decision behavior:** discovery unit = one calendar day, no
  splitting/weekly mode; truncation banner on any window → immediate stop
  (`stop_reason=window_truncated`); harvest records BOTH courts, `--court` gates
  fetching (default MC); `already_present` disk check precedes every fetch;
  report reconciles per court `harvested = fetched + already_present +
  fetch_failures` (`totals.reconciles`); attempts.jsonl gains `window_date` +
  `court`; coverage stated in date terms ("N of M windows complete in [D1..D2]").
- **`--max-fetches` (smoke tooling only):** caps live fetches and stops the run,
  but the in-flight window's ledger entry is still written so a single-window
  smoke run yields its entry. Because it can leave a grid_complete window with
  harvested > fetched (rows unfetched by design), `totals.reconciles` is
  intentionally `false` for a capped run. Production runs pass no `--max-fetches`
  and fetch every harvested in-scope row, so the identity holds; time-cap and
  abort are checked at window boundaries only (never mid-fetch), so a complete
  window is always fetched to completion in production.
- **Files touched:** `collector/search_classification.py` (new),
  `collector/harvest.py` (new), `collector/window.py` (new),
  `collector/search_engine.py` (new), `collector/search_transport.py` (new),
  `collector/run.py` (`run_collect_search` boundary), `cli.py` (`--mode`,
  widened `--court`, `--start-date`/`--end-date`/`--max-fetches`/
  `--recheck-windows`, mode-aware validation + dispatch),
  `tests/test_collector_search_classification.py`,
  `tests/test_collector_harvest.py`, `tests/test_collector_window_ledger.py`,
  `tests/test_collector_search_engine.py`, `tests/test_collector_search_cli.py`
  (all new).
- **Deviations from plan:** none beyond the two operator-adjudicated Step-0 gaps
  above; all of F1–F6 applied as approved.
- **AC-10 live smoke (isolated `--ledger-dir ~/court-data/coverage-smoke-col2`,
  real intake; nothing classified blocked/truncated):**
  - 2025-06-03 `--court MC --max-fetches 10`: `complete`, cp_harvested=**23**,
    mc_harvested=**25**, 10 MC fetched (cap), stop_reason `fetch_cap`,
    reconciles `false` (cap left 15 MC rows unfetched by design). 10 valid
    `%PDF` sheets landed in intake (806→816 MC).
  - 2027-06-01: `empty` classified live, `windows_exhausted`.
  - Both window-ledger entries verbatim:
    `{"date":"2025-06-03",...,"outcome":"complete","cp_harvested":23,"mc_harvested":25,"fetched":{"CP":0,"MC":10},"already_present":{"CP":0,"MC":0},"fetch_failures":{"CP":0,"MC":0},"skipped_rows":193}`
    and
    `{"date":"2027-06-01",...,"outcome":"empty","cp_harvested":0,"mc_harvested":0,...,"skipped_rows":0}`.
  - Isolation held: no `window-ledger-philadelphia.jsonl` in the production
    `~/court-data/coverage/`.
- **Per-day harvest counts for Run 4 sizing (requested):** 2025-06-03 single
  Philadelphia weekday = 23 CP-51-CR + 25 MC-51-CR criminal dockets out of 241
  total grid rows (193 skipped MDJ/traffic/misc); recon corroboration —
  2025-06-01 (Sun) 0 CP / 38 MC, 3-day 2025-06-02..04 window 102 CP / 106 MC
  (banner present). Single weekday fits well under the truncation cap.
- **Verification (all four gates green, run fresh post-staging):**
  - `.venv/bin/ruff check src tests` — All checks passed.
  - `.venv/bin/ruff format --check .` — 61 files already formatted.
  - `.venv/bin/python -m pytest -q` — 447 passed, 1 skipped.
  - repo-root `pnpm format:check` — passed.
- **Notes for next task:** search mode is the primary collection mechanism;
  enumeration is now audit-only. A production campaign runs
  `pipeline collect --mode search --court MC --start-date D1 --end-date D2` with
  NO `--max-fetches` and the default `~/court-data/coverage/` ledger. grid_empty
  is rare-to-never on real dates (7-day arraignment court). The F4 transport
  consolidation (shared `_pdf_from_href`/block-detection base for `transport.py`
  + `search_transport.py`) is the natural next cleanup.
 26d4f20 (task COL-2: Date-Filed search-mode collector)

## Task COL-2a — Collector Observability + Pacing Defaults + ADR 0002 Cooldown Amendment (2026-07-12)

- **What was built:** search-mode console observability (log lines only, no
  behavior/ledger/report-schema change), updated operational pacing defaults,
  and a counsel-governed post-block cooldown raise, with ADR 0002 amended to
  record the "minimum of 2 minutes" reading.
  - **AC-1 window line:** the `complete`-window log line gains `fetched`,
    `already_present`, `fetch_failures` as **flat integers summed over the
    run's FETCHED courts** (harvested stays per-court `cp_`/`mc_` because both
    courts are always harvested). A per-court map is the natural extension if a
    `--court both` run ever needs the split.
  - **AC-2 cooldown line:** all three cooldown sites gain `batch` and
    `requests_in_batch` (read at the trigger); the two `post_block` sites also
    carry `outcome="blocked"` and a content-free `detail`
    (`bot_check`/`rate_limited`/`unauthorized`/`unrecognized_page`) — blocked
    fetches reuse `engine._attempt_detail`; blocked searches use a new
    `_search_block_detail` mirroring that vocabulary from the `SearchSignal`.
  - **AC-3 progress line:** emitted every **N=5** fully-searched windows —
    `windows_complete`/`windows_remaining`, `total_requests`, `elapsed_minutes`,
    `cap_minutes` (the **effective** budget `min(max_minutes, 240)`), and a
    linear `projected_stop` of `time_cap` vs `windows_exhausted`. Projecting
    against the effective budget (not the raw 240 ceiling) keeps shorter/smoke
    runs correct; for a production `--max-minutes 240` run the two coincide.
  - **PD-2 defaults:** `BATCH_SIZE_DEFAULT` 40→100, `BATCH_COOLDOWN_DEFAULT_SECONDS`
    240→120 in `engine.py`; floor unchanged at 60 (still exit-2 below floor).
    Per the approved §7 resolution, `cli.py`'s two argparse `default=`s now
    reference the engine constants (single source of truth; kills future drift)
    and `SearchParams` literal defaults were aligned to 100/120.
  - **PD-3 / AC-5:** `POST_BLOCK_COOLDOWN_SECONDS` 120→300, still hardcoded and
    flag-proof, with a comment citing ADR 0002's minimum wording.
  - **AC-6 ADR amendment:** the non-disruption cooldown sentence now reads "a
    cooldown of at least 2 minutes"; a new `## Amendments` section (2026-07-12)
    records the minimum reading (basis: operator attestation of counsel's
    2026-07-11 written confirmation); the Consequences echo updated to
    "≥2-minute"; batch-pacing figures left untouched as operational parameters.
    The AC-6 STOP condition did NOT apply: the current ADR text was flat
    "2-minute" but an operator-attested clarification exists, so the amendment
    proceeds rather than stopping.
- **Files touched:** `services/pipeline/src/pipeline/collector/engine.py`
  (constants + comments), `.../collector/search_engine.py` (log lines +
  `SearchParams` defaults + `_search_block_detail`), `.../cli.py` (argparse
  defaults reference engine constants + help text),
  `services/pipeline/tests/test_collector_search_engine.py` (5 new observability
  tests), `tests/test_collector_engine.py` (post-block test renamed to
  `test_post_block_cooldown_meets_counsel_minimum`, asserts ≥120 and ==300),
  `tests/test_collector_cli.py` (defaults 40/240→100/120, POST_BLOCK 120→300),
  `agent-docs/decisions/0002-source-access.md`, `tasks/worklog.md`.
- **Scope note / approved deviation:** `cli.py` was NOT in the task's original
  ALLOWED FILES; it was added under the plan-review §7 Option-A approval because
  the effective CLI pacing defaults live in `cli.py`'s argparse literals, not
  the engine constants — changing the constants alone would not have met PD-2.
  `run.py` needed no change (kwargs pass through). Branched `col-2a` from `main`
  after COL-2 merged (origin/main tip `5d919fa`), per the revised branch-point
  instruction.
- **Existing tests updated (AC-8):** `test_post_block_cooldown_is_two_minutes`
  → `test_post_block_cooldown_meets_counsel_minimum` (engine); `test_collect_defaults_parse`
  batch_size/cooldown 40/240→100/120 (cli); `test_legal_conditions_are_not_flags_and_are_hardcoded`
  POST_BLOCK 120→300 (cli). Tests that reference the constants by name adapted
  automatically. Floor-rejection test unchanged.
- **Notes for next task:** the F4 transport consolidation remains the natural
  next cleanup; reconciles/fetch_capped reporting polish is still an open
  worklog candidate (explicitly out of scope here).

## Task 22.1 — Normalization Models + Vocabularies (2026-07-12)

- **Date:** 2026-07-12
- **Branch:** `phase-22`, created from `main` (this is its first commit; the PR
  loop runs once at phase end per the phase-branch workflow §6.2).
- **What was built:** the shared, pure-Python normalization surface that every
  Sprint 5 matcher (22.2 charge, 22.3 judge, 22.4 outcome/sentencing) and the
  money extractor consume. New package
  `services/pipeline/src/pipeline/normalization/`:
  - `vocab.py` — the two closed normalization vocabularies, each defined once:
    `MATCH_METHODS` (locked six: exact/alias/statute/pattern/unmatched/ambiguous)
    with the `MATCHED_METHODS` identity-carrying subset, and `NORM_WARNING_CODES`
    (locked five: `NORM_UNMATCHED`, `NORM_AMBIGUOUS`, `NORM_STATUTE_TEXT_CONFLICT`,
    `NORM_UNPARSEABLE_AMOUNT`, `NORM_EMPTY_INPUT`). The `review_needed` derivation
    is DATA — `_ALWAYS_REVIEW_METHODS = {unmatched, ambiguous}` and
    `NORM_BLOCKING_WARNINGS = {NORM_STATUTE_TEXT_CONFLICT}` — plus the thin
    `derive_review_needed(method, codes)`.
  - `models.py` — frozen dataclasses with construction-time validation making
    invalid states unrepresentable: `NormalizationCandidate`; a shared
    `_NormalizationResult` base and four thin subclasses
    (`Charge`/`Judge`/`Outcome`/`Sentencing` `NormalizationResult`) enforcing
    pinned decisions 2–4; and `MoneyExtractionResult` (integer cents only —
    float AND bool rejected, since bool is an int subclass).
  - `review_items.py` — the `review.queue_items` payload builder.
  - `__init__.py` — public re-exports.
- **No warning-vocabulary amendments:** the pinned five were accepted as-is
  (plan approval), so the set stays locked at five.
- **LOCKED FIELD NAMING (binding on 22.2/22.3/22.4):** the four
  `*NormalizationResult` models carry the raw input under `raw_value` (matches
  AC1's "raw value" wording and the `review.queue_items.raw_value` column the
  results feed); the money model carries `raw_text` (pinned verbatim by
  decision 7). This is the locked contract — result matchers use `raw_value`,
  the money extractor uses `raw_text`. (The approved plan had said `raw_text`
  for the results base; this `raw_value` naming was reviewed and locked at report
  review.)
- **REQUIRED FIX 1 (dedup-key single implementation) — STANDING FOR 22.2/22.3/22.4:**
  `review_items.py` is now the CANONICAL and ONLY implementation of dedup-key
  derivation project-wide. Future consumers MUST import `build_review_item`
  (or `build_dedup_key`) from `pipeline.normalization`; they must NOT re-derive
  a key. The `\x1f` separator is a single named module constant
  (`DEDUP_KEY_SEPARATOR`) and the derivation site cites the composition
  documented in `fact_review_vocab.py` (module docstring, lines 32–57).
  `fact_review_vocab.py` was consumed (vocabularies imported) and NOT edited.
- **REQUIRED FIX 2 (review_needed derived-by-default):** the base dataclass field
  is `review_needed: bool | None = None`; when omitted it is derived and set via
  `object.__setattr__`; when passed it must equal the derived value or
  construction raises. Matchers can omit it and inherit the single derivation.
- **REQUIRED FIX 3 (full vocabulary enforcement):** `build_review_item` validates
  EVERY vocabulary-typed `review.queue_items` field against its
  `fact_review_vocab` set — `item_type` → `REVIEW_ITEM_TYPES`, `severity` →
  `REVIEW_SEVERITIES`, `reason_code` → `ELIGIBILITY_REASON_CODES`, `status` →
  `REVIEW_ITEM_STATUSES` (default `open`). Each is test-proven in both
  directions. The payload mirrors the table's writable columns; parsed.* UUID
  pointers are stored columns, never part of the dedup key.
- **Contract nuance resolved at plan approval:** decision 8's "21.2 derivation
  function" does not exist — `fact_review_vocab.py` documents the composition and
  delegates the implementation to 22.1. Implemented here per that docstring,
  importing only the vocabularies.
- **Files touched (all new except worklog):**
  `services/pipeline/src/pipeline/normalization/{__init__,vocab,models,review_items}.py`,
  `services/pipeline/tests/{test_normalization_vocab,test_normalization_models,test_normalization_review_items}.py`,
  `tasks/worklog.md` (append). No deviations from the approved plan.
- **No DB access:** psycopg is imported in none of the new modules (test +
  grep-asserted).
- **Notes for next task:** 22.2/22.3/22.4 return the domain-specific
  `*NormalizationResult` subclasses, omit `review_needed` (let it derive), and
  emit review items ONLY via `build_review_item`. Warning-vocabulary or
  match-method additions require plan-level approval before use.

## Task 22.2 — Charge Roster + Charge Normalization (2026-07-12)

- **What was built:** the real charge roster (committed seed, public-statute
  sourced) plus the pure `ChargeMatcher` that normalizes
  `parsed.charges.statute`/`offense` against a roster snapshot and emits 22.1
  `ChargeNormalizationResult` objects + `build_review_item` review items for
  unmatched/ambiguous values. Committed, repeatable corpus-reporting tooling
  (distinct-value + coverage) accompanies it.
- **Approved coverage floor: N = 5** (roster gate). 95 distinct statutes appear
  ≥5× in the loaded corpus (94.5% of charges). Floor is binding and met.
- **Modules (all new):**
  - `services/pipeline/src/pipeline/normalization/charge_matcher.py` — pure, NO
    psycopg. Two canonicalization functions (`canonicalize_text`,
    `canonicalize_statute`), `RosterEntry`/`RosterSnapshot`, `ChargeMatcher.match`
    (seven arms, precedence exact→alias→statute w/ conflict detection, never
    emits `pattern`), and `build_charge_review_item` (delegates to 22.1
    `build_review_item`; locator `(str(charge_sequence),)`).
  - `services/pipeline/src/pipeline/normalization/charge_roster_loader.py` — thin
    DB loader over `ref.normalized_charges`+`ref.charge_aliases` via the 21.3 DB
    module; refuses in CI (`running_in_ci` guard).
  - `services/pipeline/src/pipeline/reports/{__init__,distinct_values,charge_coverage}.py`
    — committed tooling (Required Fix 1): field-parameterized distinct-value
    report (22.3 reuses for judge fields), and the coverage run. Both refuse in
    CI, read `DATABASE_URL` at the boundary only, keep console to counts/methods/
    statute-cites (never offense free-text; full detail only to
    `~/court-data/reports/`), and embed no corpus-derived data.
  - `db/seeds/charge-roster-data.ts` (data + `DEMO_ALIAS_ADDITIONS`),
    `db/seeds/charge-roster.ts` (idempotent upsert + fail-loud slug-collision
    assertion + additive demo-alias upsert), wired into `db/seeds/run.ts`.
  - Tests: `services/pipeline/tests/{test_charge_matcher,test_charge_roster_loader,test_reports_distinct_values}.py`
    and `db/seeds/charge-roster.test.ts`.
- **Statute canonicalization rule:** upper-case, keep only `[A-Z0-9.-]` — folds
  `§`/`§§`, subsection parens (`(a)(1)`↔`§§ A1`), spaces, and CPCMS decorations;
  preserves dots/hyphens (section identity).
- **Required Fix 3 — the `*` finding (RECORDED):** trailing asterisk(s) on
  Title 75 § 3802 DUI subsections (`§§ A1*`, `§§ D2***`) are dropped by
  `canonicalize_statute`. Determination: in CPCMS DUI dockets the asterisk marks
  the DUI **grading/sentencing tier** (prior-offense count / BAC level), NOT a
  distinct statutory offense — § 3802(a)(1) is one offense regardless of tier.
  The drop therefore collapses `A1*`→`A1` at correct offense-identity granularity
  and never merges different subsections (`D1`/`D2` stay distinct). Documented at
  the canonicalization site; if evidence emerges that `*` distinguishes offenses,
  that is a STOP report.
- **Titles reading (roster gate Decision 1):** pinned decision 6 named "Titles
  18/35/75" as the expected PRIMARY sources, not an exclusivity rule. The binding
  ≥5× floor also requires `23 § 6114(a)` (PFA contempt) and `62 § 1407(a)(1)`
  (Medical Assistance provider fraud); both are public Pa. C.S. and are included.
- **Demo-alias decision (roster gate Decision 4):** "demo rows untouched" means
  the `ref.normalized_charges` demo ROWS are never modified; ADDITIVE
  `ref.charge_aliases` rows FK'd to demo slugs are permitted and directed
  (consistent with the Sprint 7 promotion standing decision). `DEMO_ALIAS_ADDITIONS`
  attaches standardized-CPCMS descriptions to the demo `possession-controlled-
  substance` row ("Int Poss Contr Subst By Per Not Reg") and the demo
  `retail-theft` row ("Retail Theft-Take Mdse"). This resolved the bare-
  `35 § 780-113` possession class (28 charges: unmatched → clean alias) and let
  the retail-theft `[stmt-only]` workaround entry be removed (retail identity
  absorbed by the demo row). Only ref.charge_aliases is written; demo seed
  modules stay untouched; the alias upsert is idempotent (DO NOTHING).
- **Coexistence (SD 8):** no roster row duplicates a demo canonical statute code
  (TS + Python tests). The 4 remaining ambiguous pairs (10 charges) are demo-
  bare-code vs real-subsection `NORM_STATUTE_TEXT_CONFLICT`s on `18 § 3503` and
  `18 § 2709` — kept as review items per Decision 2 (correct conflict-arm
  behavior, not noise).
- **Alias sourcing basis (Decision 3):** every alias is public statute phrasing
  or a standardized CPCMS charge-description string (the Commonwealth's own charge
  dictionary, verifiable against public UJS references); never free text or
  docket-specific content. Header comment states this.
- **Final coverage headline (verbatim):** roster_entries=78, total_charges=3625,
  distinct pairs=314. Match-method (distinct/charges): exact 36/1033, alias
  74/2068, statute 71/328, ambiguous 4/10, unmatched 129/186, pattern 0/0.
  ≥5× floor: 95 statutes, covered=95, uncovered=0. Clean-match rate **94.6%**
  (3429/3625). Reports in `~/court-data/reports/` (never committed).
- **Deviations from plan:** N=5 (not the plan's recommended 10); demo rows gained
  additive aliases and the retail `[stmt-only]` entry was removed (Decision 4) —
  all directed at the roster gate. No other deviations.
- **Notes for next task (22.3):** the distinct-value tool is field-parameterized
  (`--table/--column`) — reuse it for the judge fields. The charge matcher's
  canonicalization + precedence pattern is the template; judge matcher returns
  `JudgeNormalizationResult` and emits items via `build_review_item`. Sprint 7
  sweep is fake judges + seeded aggregates ONLY; demo charge rows are PROMOTED to
  roster membership, never deleted (they are load-bearing here and Phase 23 facts
  FK to them).

## Task 22.3 — Judge Roster + Judge Normalization (2026-07-12)

- **What was built:** the real judge roster (committed seed, public FJD-directory
  sourced) plus the pure `JudgeMatcher` that normalizes
  `parsed.dockets.assigned_judge_raw` and `parsed.charges.disposition_judge_raw`
  against a roster snapshot and emits 22.1 `JudgeNormalizationResult` objects +
  `build_review_item` review items for unmatched/ambiguous values. The Sprint 4
  durable fix for judge validity, at the normalization layer (parser untouched).
- **Roster (reviewed + APPROVED at the roster gate): 76 judges.** Two groups,
  both independently confirmed against the public FJD criminal assignment chart /
  pacourts Municipal Court list (NOT a corpus echo): (1) 53 observed in-corpus AND
  directory-confirmed; (2) 23 directory-completeness additions (sitting
  CP-criminal + Municipal Court, plus recent-departed who could have sat in the
  2025 window) not observed in-corpus. Names transcribed verbatim from the
  approved verified curation list — none sourced or guessed by the agent. Display
  names are public natural order, unprefixed; the fake Sprint 2 rows keep their
  "Judge " prefix. One space-separated compound surname (Barbara S. Thomson
  Previdi) carries a comma-form alias "Thomson Previdi, Barbara S.".
- **Roster source references:** public Philadelphia First Judicial District (FJD)
  criminal assignment chart + Pennsylvania UJS / pacourts Municipal Court judge
  list. Scope is the criminal-relevant bench (CP civil/family-only judges who
  cannot appear on a CR docket are excluded). `Sharon Williams Losier` surname
  granularity and `Larry Farnese` nickname (Larry<->Lawrence) are left for
  first-live-appearance alias top-up, NOT pre-invented.
- **Sanctioned vocabulary addition (Answer 1):** `judge_not_normalized` added to
  `fact_review_vocab.ELIGIBILITY_REASON_CODES` (additive; the domain-qualified
  judge analog of `charge_not_normalized`). Reason_code set is now 13 members;
  the 21.2 membership test was updated 12->13. Review-item mapping:
  unmatched -> `unmapped_judge` / medium / `judge_not_normalized`;
  ambiguous -> `ambiguous_judge` / HIGH / `judge_not_normalized`.
- **Fake-judge exclusion mechanism (pinned decision 7):** a candidate-pool filter
  `exclude_fake_judges(entries)` in `judge_matcher.py` drops the frozen
  `FAKE_JUDGE_SLUGS` set (source of truth: `db/seeds/reference-data.ts`
  JUDGE_SEEDS) at load time — no `ref.*` column. Proven by test: a real-style
  value cannot resolve to a fabricated identity. The seed's real<->fake
  slug-collision assertion is the seed-time backstop.
- **Unmatched non-distinction (pinned decision 3):** the matcher structurally
  CANNOT distinguish an issuing-authority / non-judge value from a real judge
  missing from the roster — both resolve to `unmatched` + review, no fuzzy-accept
  ever. Demonstrated in tests. Null/blank judge fields are ABSENT (match returns
  None; no result, no review item — SENTINEL_COLLISION nulls are already
  review_needed at parse).
- **Canonicalization (approved at gate):** display-format-independent, comma-aware
  positional parse; honorific strip (bare "J." deliberately NOT a honorific — it
  collides with a real first initial); intra-name hyphens/apostrophes deleted so
  hyphenated surnames are single tokens matching in both orders (this superseded
  the Answer-3 comma-alias requirement for compounds — there are no
  space-separated compounds in-corpus; the comma-alias mechanism is retained +
  synthetic/live-tested for the Thomson Previdi case). Generational suffixes
  (Jr/Sr/II/III/IV) carried as a separate identity component: absent-suffix is a
  wildcard (parallel to middle initials — unique => exact, two differing only by
  suffix => ambiguous), two present suffixes must match. Middle-initial tolerance
  bridges initial<->full-name and treats an absent middle as a wildcard.
- **Role context (pinned decision 6):** carried in the caller + dedup locator, NOT
  by modifying the frozen 22.1 model. assigned -> ("judge","assigned");
  disposition -> ("judge","disposition",str(charge_sequence)). Assigned and
  disposition on one docket yield two distinct items, never merged.
- **Coverage headline (verbatim, counts only; independent-directory confirmation
  over the 76-entry roster):**
  - assigned_judge_raw (1603 rows): distinct 51; absent(null/blank) 2 distinct /
    49 rows; present 49 distinct / 1554 rows; exact 49/1554; alias 0; ambiguous 0;
    unmatched 0; statute 0; pattern 0. Unmatched tail 0, ambiguous 0.
  - disposition_judge_raw (3625 rows): distinct 47; absent(null) 1 distinct / 689
    rows; present 46 distinct / 2936 rows; exact 46/2936; alias 0; ambiguous 0;
    unmatched 0; statute 0; pattern 0. Unmatched tail 0, ambiguous 0.
- **Persistence posture:** mirrors 22.2 — the matcher produces results +
  in-memory review-item payload dicts via `build_review_item`; NO fact.* writes,
  NO review-item DB persistence (Phase 23).
- **Files touched:** new —
  `services/pipeline/src/pipeline/normalization/{judge_matcher,judge_roster_loader}.py`,
  `services/pipeline/src/pipeline/reports/judge_coverage.py`,
  `services/pipeline/tests/{test_judge_matcher,test_judge_roster_loader,test_reports_judge_coverage,test_reports_distinct_fields}.py`,
  `db/seeds/{judge-roster-data,judge-roster,judge-roster.test}.ts`; modified —
  `services/pipeline/src/pipeline/fact_review_vocab.py` (additive reason_code),
  `services/pipeline/src/pipeline/reports/distinct_values.py` (`--field`
  multi-table extension), `services/pipeline/tests/test_fact_review_vocab.py`
  (12->13), `db/seeds/run.ts` (wire seedJudgeRoster), `tasks/worklog.md`.
- **Deviations from the approved plan:** canonicalization refined from real-data
  formats (hyphen/apostrophe single-token folding superseding the Answer-3
  compound-alias-for-all requirement; suffix-as-identity incl. III; absent-suffix
  wildcard; dropped bare "J." honorific) — all reviewed and APPROVED at the roster
  gate. Roster extended from the 53 observed to the 76-entry verified directory
  set per pinned decision 2 (RC1/RC2 at the gate). No other deviations.
- **Notes for next task (22.4):** outcome/sentencing matchers get their own
  domain-qualified `_not_normalized` reason codes (the `judge_not_normalized`
  convention). The `distinct_values.py` `--field schema.table.column` extension
  spans tables in one report. `judge_coverage.py` counts nulls as a DISTINCT
  absent class from unmatched. Christopher Hall is in the roster pending Chops
  confirmation (keep unless told to hold).

## Task 22.4 — Outcome Mapping (Disposition → Taxonomy) (2026-07-12)

- **Date:** 2026-07-12
- **What was built:** The disposition→outcome-code mapping layer. A pure,
  DB-free `OutcomeMapper` (`services/pipeline/src/pipeline/normalization/outcome_mapper.py`)
  maps `parsed.charges.disposition_raw` to a public outcome taxonomy code via a
  corpus-evidenced EXACT-match table (`DISPOSITION_OUTCOME_MAP`, 19 keys → 7
  codes). Three arms: (a) **held carve-out** — `disposition_raw IS NULL` →
  `map()` returns `None`, NO fact and NO review item (the 18.1 terminality
  predicate `_charge_has_disposition` replicated verbatim as
  `charge_has_terminal_disposition`/`is_held_charge`, not imported — it is
  module-private in envelope); (b) **mapped** → the table's code, `public_eligible`
  per taxonomy, no review; (c) **unmapped** — a terminal value absent from the
  table → code `unknown` + one `disposition_not_mapped` review item (medium),
  never public-eligible. Purpose-built `OutcomeMappingResult` carries
  `taxonomy_version` (read from taxonomy.json, stamped on every result) and the
  unmapped→unknown+review state — 22.1's frozen `OutcomeNormalizationResult`
  can carry neither and is read-only (approved Q2). Review items go through the
  canonical 22.1 `build_review_item` only (`build_outcome_review_item`). A thin
  `load_taxonomy_snapshot()` reads the generated taxonomy.json at the boundary;
  the mapper is pure over the injected `TaxonomySnapshot`. New AC-8 acceptance-
  authority tool `reports/outcome_coverage.py` (mirrors judge_coverage.py) runs
  the mapper over the corpus and reports the mapped/unmapped/held split; CI-
  guarded, `DATABASE_URL` at the boundary only, console counts/codes/version only
  (raw values → report file). `disposition_not_mapped` added to
  `ELIGIBILITY_REASON_CODES` (13→14).
- **Corpus rerun (acceptance authority) — reproduced the approved split exactly:**
  total 3625 rows; held (null) 463 / no fact, no review; mapped 3155 / 19 distinct
  (guilty_plea 2315, guilty_verdict 467, dismissed 226, ard 65, other 61,
  acquittal 17, withdrawn 4); unmapped→unknown 7 rows / 6 distinct. The 7 unmapped
  rows are exactly the 6 malformed/garbage captures approved at the gate.
- **Full reason_code set (14) after the additive change:** disposition_date_missing,
  disposition_date_before_mvp_window, sentence_date_missing,
  sentence_date_before_mvp_window, charge_not_normalized, judge_not_normalized,
  disposition_not_mapped, outcome_category_not_public, sentencing_category_not_public,
  sentencing_component_not_normalized, review_needed, blocking_warning,
  judge_not_attributed, parent_outcome_ineligible.
- **AC-5 hygiene:** the table carries only the full "Transferred to Another
  Jurisdiction"; the truncated "Transferred to Another" key is absent (the 18.2
  Class E repair, 16 rows, rewrites it before mapping) — asserted by test.
- **Files touched:** `services/pipeline/src/pipeline/normalization/outcome_mapper.py`
  (new), `services/pipeline/src/pipeline/reports/outcome_coverage.py` (new),
  `services/pipeline/tests/test_outcome_mapper.py` (new),
  `services/pipeline/src/pipeline/fact_review_vocab.py` (add
  `disposition_not_mapped`, 13→14), `services/pipeline/tests/test_fact_review_vocab.py`
  (13→14 guard — trivially necessary accompanying change to the vocab's own test),
  `tasks/worklog.md`.
- **Deviations from the approved plan:** none. Two pre-code STOP reports (entrypoint
  + held-predicate) were withdrawn by planning ("you had it right"); implemented the
  original approach — `python -m pipeline.reports.*` entrypoint, envelope 18.1 held
  predicate replicated verbatim, no fix-3 reconciliation.
- **Notes for next task (22.5 / Phase 23):** "Dismissed - Rule 600 (Speedy" is a
  known UNREPAIRED mid-phrase parser truncation of "…(Speedy Trial)", mapped
  verbatim to `dismissed` here; the durable fix is a parser truncated-disposition
  repair-table entry (same class as the 18.2 Transferred repair) — a future
  parser-repair candidate, out of scope for 22.4. The held carve-out is at the
  disposition-value grain (`disposition_raw IS NULL`); Phase 23 owns reconciling
  map results to `fact.*` persistence and the eligibility reason codes. 22.5 owns
  sentencing mapping + money extraction.

## Task 23.1 — Judge Attribution Rules (Phase 23 opener) (2026-07-12)

- **Date:** 2026-07-12
- **What was built:** The conservative, pure judge-attribution resolver that 23.2
  (outcome facts) consumes and 23.3 (sentence facts) inherits unchanged. New
  `pipeline.facts` package (Phase-23 fact-building logic home) with one module,
  `facts/judge_attribution.py`:
  - `AttributionResult` (frozen; `__post_init__` invariants making invalid states
    unrepresentable): `(normalized_judge_id | None, method, review_descriptor |
    None)`, method ∈ `{disposition_judge, assigned_judge_rule, none}`. Attributed
    methods require an id and carry no descriptor; `none` carries no id; a
    descriptor rides only on the `none`/ambiguous case.
  - `DocketAttributionContext` (frozen) + `build_docket_context(docket, matcher)` —
    derives the docket-level decision ONCE per docket (assigned single-match +
    fallback-eligibility); `fallback_eligible` ⇒ non-null `assigned_judge_id`.
  - `resolve_charge(charge, context, matcher, *, source_document_id,
    parsed_docket_id=None, parsed_charge_id=None)` — per-charge decision order:
    (1) disposition single-match → `disposition_judge`; (2) disposition `ambiguous`
    → `none` + review descriptor (pinned #6); (3) disposition `unmatched` → `none`
    (no double-emit; that's 22.3/23.4's `unmapped_judge`); (4) disposition ABSENT
    but captured-then-nulled (DP1) → `none`, never fallback; (5) disposition ABSENT
    on a fallback-eligible docket → `assigned_judge_rule`; (6) else `none`. Pure; no
    DB, no I/O, no side effects.
  - APPROVED `assigned_judge_rule` (SD 1 #2, docket-scoped, single-path): a docket
    is fallback-eligible iff NO charge carries a roster-matched disposition judge
    AND `assigned_judge_raw` is a single unambiguous roster match; each ABSENT-
    disposition charge on such a docket is attributed to the assigned judge. Docket
    scope protects the 238/1417 (17%) dockets where disposition≠assigned and makes
    the pinned #6 disposition-vs-assigned conflict structurally impossible.
  - Ambiguous-attribution review descriptor via the 22.1 `build_review_item` helper:
    item_type `ambiguous_judge_attribution`, reason `judge_not_attributed`, HIGH,
    locator `("judge","attribution",<sequence>)` (distinct from 22.3's disposition
    locator). Dedup key = `source_document_id` + locator ONLY; parsed UUIDs ride as
    non-key context (asserted by test). NO `fact_review_vocab.py` edit — both vocab
    members already existed.
- **How to verify:** `.venv/bin/python -m pytest tests/test_judge_attribution.py -q`
  (16 tier-1 synthetic tests: disposition match; the approved fallback; no-match →
  none; present-but-unmatched suppression; ambiguous → review + none; sibling-charge
  fallback suppression; DP1 captured-then-nulled (SUSPECT_JUDGE_LINE +
  SENTINEL_COLLISION); result/context invariants; dedup-key parsed-UUID exclusion;
  inheritance reuse).
- **Files touched:** `services/pipeline/src/pipeline/facts/__init__.py` (new),
  `services/pipeline/src/pipeline/facts/judge_attribution.py` (new),
  `services/pipeline/tests/test_judge_attribution.py` (new), `tasks/worklog.md`.
- **Deviations from plan/gate:** one flagged implementation decision within the
  adjudicated DP1 branch-1 clause. DP1 named `SUSPECT_JUDGE_LINE` (the 3 Class-D
  junk-nulled charges, all of which the plain rule would fallback-ATTRIBUTE). I keyed
  the guardrail on the semantic class of charge-grain disposition-judge-nulling
  warnings — `{SUSPECT_JUDGE_LINE, SENTINEL_COLLISION}` — because both are the
  parser's two disposition-judge null branches (`_is_junk_judge` and
  `collides_with_sentinels`) and both mean "the charge captured its own judge, then
  it was nulled." parsed.* recon: 3 SUSPECT_JUDGE_LINE (all 3 land in fallback →
  now suppressed) and 12 charge-grain SENTINEL_COLLISION (0 currently land in
  fallback — 0-impact today, but latent as the corpus grows; included per the "must
  not receive fallback" principle and the "generalizes to every future junk-null"
  instruction).
- **Recon (parsed.* loaded corpus, counts only):** 1603 dockets / 3625 charges;
  disposition judge 2936 matched / 0 unmatched / 0 ambiguous / 689 absent; assigned
  1554 matched / 49 absent; max distinct matched disposition judges on ANY docket =
  1 (no multi-judge conflict); disposition≠assigned on 238/1417; fallback-eligible
  dockets = 137 (all 137 "no disposition judge present anywhere" after the DP1
  guardrail); the 5 SENTINEL_COLLISION recovered (assigned-nulled, review_needed)
  dockets = 0 in the fallback set (assigned null ⇒ ineligible).
- **Notes for next task (23.2/23.3):** the resolver's charge-record contract needs
  a `warning_codes` key per charge (that charge's charge-grain parser warning codes
  from `parsed.warnings`, joined by docket_id+sequence); absent/empty ⇒ no
  guardrail. `source_document_id` is a required kwarg (the `raw.*` UUID). 23.3 must
  NOT re-derive — it reuses the parent charge's `AttributionResult` for every
  sentence component (sentences carry no judge of their own). The
  `ambiguous_judge_attribution` descriptor path fires on ZERO real charges in-corpus
  today (0 ambiguous disposition judges) — built + tier-1 tested per pinned #6 by
  design, not a gap. `judge_specific_eligible` gating is 23.2/23.3's job, not the
  resolver's.

## Task 22.5 — Sentencing Mapping + Money Extraction (2026-07-12)

- **Date:** 2026-07-12
- **What was built:** The sentence-component→sentencing-category mapping layer plus
  the first real consumer of the 22.1 money model. Three new pure, DB-free modules:
  - `normalization/money_extractor.py` — `extract_amount(raw_text)` → 22.1
    `MoneyExtractionResult`. LOCKED `$`-REQUIRED regex `MONEY_TOKEN` (the ONE
    money-regex definition project-wide). Four-branch triage (option b): no `$` →
    amount unset, NO warning (legitimate absence); `$` present but 0 parseable →
    unset + `NORM_UNPARSEABLE_AMOUNT`; exactly one DISTINCT amount → set; ≥2 distinct
    → unset + `NORM_UNPARSEABLE_AMOUNT`. Distinct-by-value (same amount twice → one →
    SET); never sum, never max; integer cents only.
  - `normalization/sentencing_mapper.py` — `SentencingMapper.map(sentence_type,
    raw_text)` → purpose-built `SentencingComponentResult` (mirrors 22.4:
    `taxonomy_version` on every result; 22.1's frozen `SentencingNormalizationResult`
    is roster-shaped and unused, read-only). Base `SENTENCE_TYPE_CATEGORY_MAP`
    (verbatim `dict.get`, no fuzzy): Confinement→incarceration, Probation→probation,
    No Further Penalty→no_further_penalty, ARD→other, Fines and Costs→costs_fees,
    IPP→other (unreachable-but-kept, 0 corpus rows); absent → `unknown` +
    `unmapped_sentencing_component` review (`unknown` non-public, enforced at
    construction). Additive detection on `raw_text` (append, NEVER collapse):
    `\bRestitution\b` → +restitution; literal `\bCommunity Service\b` →
    +community_service; bare `\b\d+\s*hours?\b` alone → `ambiguous_sentencing_component`
    review, no silent add (conservative false-negative bias). Money runs only on a
    component carrying a monetary category (costs_fees base or restitution additive).
    `build_sentencing_review_items` (0+ items) + `build_duration_review_item` (helper
    only; caller passes the warning — the mapper never scans the envelope, so
    "durations consumed as parsed" holds; Phase 23 wires UNPARSEABLE_DURATION → this
    helper over the corpus). Locator `(charge_sequence, component_order)`;
    `parsed_sentence_id` payload-only, never in the dedup key.
  - `reports/sentencing_coverage.py` — recon (Part A, map-independent) + coverage
    (Part B, AC-8 authority) modes; `running_in_ci` guard, `DATABASE_URL` at the
    boundary only, console = counts + `sentence_type` vocab/codes only. Single-sources
    the money regex from `money_extractor` (keeps only the duration-contaminated
    candidate diagnostic locally).
  - `fact_review_vocab.py` — `money_amount_unparseable` + `sentence_duration_unparseable`
    added to `ELIGIBILITY_REASON_CODES` (14→16).
- **Part A recon finding (drove the gate):** the candidate `$`-OPTIONAL money regex
  was duration-contaminated — of components with a `.NN` decimal, ~all were duration
  figures ("11.00 months"; Probation 1811/1813, Confinement 1396/1397, ARD 98/100
  duration-adjacent), only ~5 corpus-wide were not. Gate LOCKED `$`-required. `Fines
  and Costs` (13/13) carry no discrete fine → `costs_fees`, no `fine` category.
- **Corpus rerun (coverage mode, acceptance authority) — reproduced the locked split
  EXACTLY:** total 4162 components. Base: probation 2059, incarceration 1550,
  no_further_penalty 440, other 100 (ARD; IPP 0), costs_fees 13, unmapped→unknown 0.
  Additive: +restitution 24, +community_service 9, ambiguous-CS→review 5. Money
  (monetary subset 37; `$`-required, rule b): amount SET 12, absent/no-item 18,
  money_unparseable (≥2 distinct) 7. Review items: unmapped 0, ambiguous 5, money 7.
  No deviation, no unattributable result.
- **Full reason_code set (16) after the additive change:** disposition_date_missing,
  disposition_date_before_mvp_window, sentence_date_missing,
  sentence_date_before_mvp_window, charge_not_normalized, judge_not_normalized,
  disposition_not_mapped, outcome_category_not_public, sentencing_category_not_public,
  sentencing_component_not_normalized, review_needed, blocking_warning,
  judge_not_attributed, parent_outcome_ineligible, money_amount_unparseable,
  sentence_duration_unparseable. 22.1–22.4 tests confirmed green after the additive
  change (test_fact_review_vocab bumped 14→16).
- **Files touched:** `services/pipeline/src/pipeline/normalization/money_extractor.py`
  (new), `services/pipeline/src/pipeline/normalization/sentencing_mapper.py` (new),
  `services/pipeline/src/pipeline/reports/sentencing_coverage.py` (new),
  `services/pipeline/src/pipeline/fact_review_vocab.py` (add 2 reason codes, 14→16),
  `services/pipeline/tests/test_money_extractor.py` (new),
  `services/pipeline/tests/test_sentencing_mapper.py` (new),
  `services/pipeline/tests/test_reports_sentencing_coverage.py` (new),
  `services/pipeline/tests/test_fact_review_vocab.py` (14→16 guard — trivially
  necessary accompanying change to the vocab's own test), `tasks/worklog.md`.
- **Deviations from the approved plan/gate:** none. Built against the locked
  artifacts exactly; recon-driven `$`-required regex and money triage (b) were the
  gate's locked decisions, not deviations.
- **Notes for next task (Phase 23 / fact build):** the money regex `$`-required
  `alt3` (`\$\d+`) is a fallback that would parse a malformed `$1,2` as `$1`
  (100 cents) — no such input in the corpus, noted for safety. `fine` taxonomy code
  is defined but intentionally UNPOPULATED (recon: corpus has no discrete fine).
  Money is a component-level reading (one amount per component, not allocated across
  multiple monetary categories). Phase 23 owns: `fact.*` persistence of categories +
  amount_cents, and wiring the parser UNPARSEABLE_DURATION warning →
  `build_duration_review_item` over the corpus (helper + reason code land here; the
  mapper never re-parses durations). Closes Phase 22 — its commit + the phase-close
  PR (phase-22 → main) close the phase.

## Task 23.2 — Outcome Fact Generation + Eligibility (2026-07-12)

- **Date:** 2026-07-12
- **What was built:** The first fact-writing consumer. `pipeline build-facts` reads
  the loaded `parsed.*` corpus, applies the 22.2 charge matcher / 22.4 outcome
  mapper / 23.1 judge resolver (all imported UNCHANGED), and writes one
  `fact.charge_outcomes` row per DISPOSED charge (`disposition_raw` non-null) under
  one new `fact.fact_build_runs` run. Two new modules under `pipeline.facts`:
  - `facts/outcome_facts.py` — pure, DB-free eligibility + row logic.
    `evaluate_outcome_eligibility(...)` returns the eligibility trio + fact
    `review_needed` + the all-applicable `ineligibility_reason_codes` array;
    `OutcomeFactEligibility` (frozen) enforces the invariant `reasons empty IFF
    judge_specific_eligible`. `build_outcome_fact_row(...)` assembles the full
    immutable column dict; `insert_outcome_facts(...)` is the single `executemany`
    writer (runs inside the caller's tx).
  - `facts/build_facts.py` — orchestration + `run_build_facts(database_url)`.
    Resolves the corpus provenance version BEFORE any write (single distinct
    `(record_parser_version, envelope_parser_version)`; mixed/empty → STOP, exit 2),
    creates the run (`in_progress`, committed), then in ONE tx bulk-inserts every
    fact and flips the run to `completed` with counts; on failure rolls back (zero
    facts) and marks the run `failed`.
  - `facts/__init__.py` re-exports the new surface; `cli.py` adds the `build-facts`
    subcommand (CI-refuses, reads `DATABASE_URL` at the boundary, NO salt — facts
    carry no defendant identity).
- **Eligibility (Sprint 5 plan Task 23.2 AC 2, VERBATIM — the current-task.md PDs
  PD1/PD3/PD4/PD6 were DISCARDED at the plan gate as inventing a vocabulary that
  contradicts the committed 21.2 schema + the sprint plan):**
  `mvp_eligible` = disposition_date present AND ≥ 2025-01-01; `public_eligible` =
  mvp AND charge match ∈ {exact, alias, statute} AND outcome category public AND
  fact `review_needed` false; `judge_specific_eligible` = public AND judge
  attributed (23.1). Fact `review_needed` is derived from the charge-grain PARSER
  warning severity via the locked 18.1 `warning_codes.derive_review_needed` — that
  map is the blocking set; no separate blocking list was invented.
  `ineligibility_reason_codes` carries EVERY applicable committed reason (empty ⇒
  judge_specific_eligible); `judge_not_attributed` is scoped to the
  public-eligible-but-unattributed case. Constant fills: `attribution_method` =
  `'charge_row'` (Task 21.2); `judge_attribution_method` = the 23.1 method verbatim;
  `charge_match_method` = matcher method; `outcome_match_method` = `exact`/`unmapped`;
  provenance stamped from the single distinct parser-version pair; `taxonomy_version`
  from taxonomy.json.
- **Acceptance corpus run (verbatim):** `charges_processed=3625 facts_written=3162
  held_skipped=463` (reconcile facts+held==charges: True). `mvp_eligible=437
  public_eligible=411 judge_specific_eligible=411 review_needed=226`. Outcome split:
  acquittal 17, ard 65, dismissed 226, guilty_plea 2315, guilty_verdict 467, other
  61, unknown 7, withdrawn 4. Ineligible-by-reason: disposition_date_before_mvp_window
  2514, review_needed 226, disposition_date_missing 211, charge_not_normalized 157,
  disposition_not_mapped 7, blocking_warning 1. The 22.4 outcome-coverage tool over
  the identical corpus reproduces the split EXACTLY (held 463; mapped 3155 by the
  same per-code counts; unmapped→unknown 7), so facts_written(3162)=mapped(3155)+
  unknown(7) and +held(463)=3625. blocking_warning=1 is the single statute/text-
  conflict charge, flagged additively alongside charge_not_normalized.
- **Tests:** `tests/test_facts_outcome_eligibility.py` (19 → DB-free tier-1 synthetic:
  every AC-8 scenario, all-applicable reason stacking, the eligibility invariants) and
  `tests/test_facts_build_facts.py` (DB integration via `PIPELINE_TEST_DATABASE_URL`,
  same guard pattern as the 21.3 loader suite: seeds a synthetic roster + docket with
  the AC-8 charge mix, asserts run lifecycle/counts, per-scenario fact rows, held →
  no fact, and failed-build → zero partial facts + run marked `failed`). Verified
  locally against a dedicated `pca_test` database (migrated to head): 19 passed.
- **Files touched:** `services/pipeline/src/pipeline/facts/outcome_facts.py` (new),
  `services/pipeline/src/pipeline/facts/build_facts.py` (new),
  `services/pipeline/src/pipeline/facts/__init__.py` (re-exports + docstring),
  `services/pipeline/src/pipeline/cli.py` (build-facts subcommand),
  `services/pipeline/tests/test_facts_outcome_eligibility.py` (new),
  `services/pipeline/tests/test_facts_build_facts.py` (new), `tasks/worklog.md`.
  No migrations, seeds, or TS/web touched; `fact_review_vocab.py` untouched (no new
  reason code needed — expected).
- **Deviations from the approved plan:** the human adjudicated the three plan-gate
  questions (date gate ON; review_needed gates public via the existing derivation;
  all-applicable reason array) and directed discarding current-task.md's eligibility
  PDs in favour of sprint-5-plan Task 23.2 AC 1–4 + the committed schema. Built to
  that. One in-flight correction: the initial `OutcomeFactEligibility` invariant
  ("public ⇒ no reasons") was wrong — a public-eligible-but-unattributed fact
  legitimately carries `judge_not_attributed`; fixed to "reasons empty IFF
  judge_specific_eligible". Acceptance numbers unchanged (all 411 public facts were
  also attributed).
- **Notes for next task (23.3 sentence facts):** the run is created + completed in
  `build_facts.build_facts(conn, url)`; 23.3 extends the SAME run by inserting
  sentence facts inside the completion tx (after `insert_outcome_facts`, before
  `_finish_run`) so one `build-facts` invocation remains one coherent fact-layer
  build — no second command, no second run concept. `attribution_method` constant
  for sentences is `'charge_component'` (Task 21.2). Runs are append-only (new run
  per invocation; NO active/published selection — Sprint 7). The local `pca_test`
  database was created + migrated to head to verify the DB suite; it is outside the
  repo and can be reused.

## Task 23.3 — Sentence Fact Generation + Eligibility (2026-07-12)

- **What was built:** `build-facts` now writes `fact.charge_sentences` inside the
  SAME run/transaction as outcome facts — one row per parsed sentence component on
  every disposed charge that received a 23.2 outcome fact (1:1, never collapsed,
  creation NOT gated by eligibility). Ordering: create run → insert outcome facts →
  read the `parsed_charge_id → charge_outcomes.id` map back inside the tx → build +
  insert sentence facts FK'd to the just-created parent → `_finish_run`. The 22.5
  sentencing mapper / money extractor, the 18.1 duration predicate, and the 23.2/23.1
  modules are all consumed UNCHANGED.
- **Eligibility (PD5):** `mvp_eligible` = sentence_date present ∧ ≥ 2025-01-01 (the
  same `MVP_WINDOW_START` imported from `outcome_facts`); `public_eligible` = parent
  outcome fact public_eligible ∧ mvp ∧ base sentencing category public ∧
  `component_match_method ∈ {exact}` ∧ ¬review_needed; `judge_specific_eligible` =
  public ∧ inherited judge attributed. Judge + `normalized_charge_id` fields are
  inherited verbatim from the parent (SD 1). `component_match_method` is derived from
  the 22.5 result onto the locked 22.1 vocab (`unmatched`/`ambiguous`/`exact`) — the
  mapper's base is an exact-table only, so `{exact}` is the clean set (mirrors 23.2).
- **review_needed (PD6):** `result.review_needed` (unmapped base ∨ ambiguous CS ∨
  money_unparseable) ∨ per-component `UNPARSEABLE_DURATION` (the imported envelope
  predicate `_is_unparseable_duration`, single source of truth — NOT re-inlined) ∨
  the silent-loss guard `len(result.categories) > 1` (an additive restitution/CS
  beyond base forces review so it surfaces to 23.4; base category still stored,
  amount_cents still populated). ZERO `review.queue_items` rows written (23.4's job).
- **Reason codes:** all sentence-grain codes already existed in the committed 21.2
  vocab — `fact_review_vocab.py` UNTOUCHED (no additions).
- **Corpus acceptance run (verbatim, hygiene-clean):** run `572ceb6c-0fa9-46`,
  status completed. Outcomes: charges_processed=3625, facts_written=3162,
  held_skipped=463 (reconciles). Sentence facts: 4162 written == 4162 components on
  disposed (reconciles); mvp=493, public=432, judge_specific=432, review_needed=317;
  amount coverage monetary=37 / amount_set=12 / money_unparseable=7 / money_absent=18;
  multi_category=33; duration facts=280 / envelope_warnings=280 / predicate_all=280
  (exact match). Sentence reason tallies: parent_outcome_ineligible=3670,
  sentence_date_before_mvp_window=3669, review_needed=317,
  sentence_duration_unparseable=280, money_amount_unparseable=7,
  sentencing_component_not_normalized=5.
- **SD-15 finding (Branch A, human-adjudicated):** 33 disposed-charge components
  have `sentence_date ≠ disposition_date` (all sentence_date EARLIER, 218–757 days,
  median 757; 29 straddle the 2025-01-01 MVP boundary). Root cause resolved in the
  planning chat: the parser has two `sentence_date` provenance paths —
  `docket_parser.py:738` (component-level captured value) and `:925` (copy of the
  charge disposition_date); the 21.3 loader carries the captured value verbatim, so
  a divergence is parser-origin and SOUND, not a defect. The SD-15 check is therefore
  a SOFT REPORT (logged: count + straddle + delta range), NOT a stop. PD5 keys
  `mvp_eligible` off `sentence_date`, so sub-window captured dates fall out via the
  existing `sentence_date_before_mvp_window` code — no vocab addition, no special
  casing. Held-charge (0) and duration==280 remain HARD stops (both pass).
- **AC8 parity (proven):** the new run's 3,162 outcome facts are byte-for-byte
  identical to the pre-existing 23.2 run — 0 mismatched rows across all 15 semantic
  columns, symmetric charge-key diff 0. Corpus integrity: orphan_sentence_facts=0,
  sentence_facts_on_held=0, judge_inheritance_mismatches=0, review_queue_items=0.
- **Files touched:** `services/pipeline/src/pipeline/facts/sentence_facts.py` (new),
  `services/pipeline/src/pipeline/facts/build_facts.py` (extended),
  `services/pipeline/tests/test_facts_sentence_eligibility.py` (new tier-1),
  `services/pipeline/tests/tier1/sentence_fact_goldens.json` (new committed golden),
  `services/pipeline/tests/test_facts_build_facts.py` (extended: sentence seed +
  linkage/scoring/held-STOP assertions), `tasks/worklog.md`. NO migrations, seeds,
  TS/web, or 22.x/23.1/23.2 module-body edits; `fact_review_vocab.py` untouched.
- **Deviations:** none from the (Branch-A-amended) approved plan. The corpus run
  first STOPPED on the SD-15 divergence exactly as designed; Branch A was adjudicated
  in the planning chat and the check was converted to a soft report per that ruling.
- **Notes for 23.4 (review-queue wiring):** sentence `review_needed` + the carried
  signals are recorded on each fact but NO `review.queue_items` are written yet. The
  22.5 `build_sentencing_review_items` / `build_duration_review_item` helpers already
  exist for the sentence-grain locator `(charge_sequence, component_order)`; the
  duration item is caller-wired (the build re-derives per component via the envelope
  predicate). Replace-on-rebuild (delete-and-reinsert) is still deferred to 24.1 —
  each `build-facts` invocation appends a new run (there are now two completed runs
  in the corpus DB).

## Task 23.4 — Review Item Generation + Dedup Wiring (2026-07-12)

- **What was built:** wired every Phase 22–23 normalization + attribution review
  path into `review.queue_items`, in the SAME `build-facts` pass, with DB-enforced
  dedup that is idempotent and STATUS-PRESERVING across rebuilds. Before 23.4 the
  build recorded `review_needed` on facts but wrote ZERO queue rows (deferred by
  design). 23.4 ROUTES existing signals — no new signals invented.
- **Seam (R2):** review items are built where the results already live in memory —
  `_collect_outcome_rows` (charge / disposition-judge / assigned-judge / outcome /
  23.1 ambiguous-attribution descriptor) and `_collect_sentence_rows` (22.5
  component items + duration + additive) — plus one read-only `parsed.warnings` scan
  (`_collect_warning_review_items`) for the two envelope-warning types. All 22.x /
  23.1 / 23.2 / 23.3 module BODIES consumed UNCHANGED; only the `build_facts.py`
  orchestrator (the plan-named integration path) was edited.
- **Helpers (R3):** consumed the shipped 22.1 `build_review_item` and the per-domain
  wrappers `build_charge_review_item` / `build_judge_review_item` (roles
  assigned+disposition) / `build_outcome_review_item` / `build_sentencing_review_items`
  / `build_duration_review_item` unchanged. The two envelope-warning types call the
  canonical `build_review_item` directly (no wrapper exists for them).
- **Vocabulary (plan-approved, the ONLY change):** added exactly ONE member,
  `additive_sentencing_category`, to `REVIEW_ITEM_TYPES` in `fact_review_vocab.py`.
  Its reason (`review_needed`) and severity (`low`) reuse EXISTING vocab members.
  Emission guard: emit only when `len(result.categories) > 1` AND
  `build_sentencing_review_items` produced no item for that component — never
  double-flags a money/ambiguous multi-category component. 23.4 alters NO fact flag
  (23.3 still owns the fact's `review_needed`).
- **Envelope-warning items (R4), existing vocab:** `MISSING_DISPOSITION_DATE` →
  `missing_disposition_date` / `disposition_date_missing` / medium; `SENTINEL_COLLISION`
  → `sentinel_collision` / `judge_not_normalized` / medium. Confirmed
  `MISSING_DISPOSITION_DATE` fires ONLY for a disposed charge with a null date
  (`envelope.py:146` guards on `disposition_raw is not None`), so held / event-key
  charges structurally never flood the queue — no exclusion needed. `SENTINEL_COLLISION`
  is emitted at TWO grains (docket-grain CASE INFORMATION with null `charge_sequence`,
  charge-grain DISPOSITION); the scan LEFT-JOINs charges and routes both — the
  docket-grain case uses an EMPTY locator, so its count tracks the LOADED tally (17),
  not the recovered-5 subset.
- **Dedup + status preservation (R5, AC2):** `insert_review_items` collapses payloads
  in memory by `dedup_key`, then inserts each with `ON CONFLICT (dedup_key) DO NOTHING`
  against the shipped 21.2 unique constraint. Items are NOT run-scoped (SD 6): no
  build-run id is stored on them. A pre-existing item is left untouched INCLUDING its
  `status` (the no-op insert fires no UPDATE, so the `set_updated_at` trigger never
  runs — proven: `updated_at` unchanged on re-run).
- **Run report (AC3):** `_print_summary` gains a hygiene-clean `--- review items ---`
  block — item TYPES + `generated / newly_inserted` counts only (no raw values, no
  docket numbers); `counts["review_items"]` (generated + newly_inserted, each by type)
  is persisted on the `fact_build_runs` row.
- **Corpus acceptance run (verbatim, hygiene-clean, real `pca` corpus):**
    - FIRST run — `review_items generated=710 newly_inserted=710`, by type:
      additive_sentencing_category 26 / ambiguous_charge 1 /
      ambiguous_sentencing_component 5 / duration_unparseable 280 /
      missing_disposition_date 211 / money_unparseable 7 / sentinel_collision 17 /
      unmapped_charge 156 / unmapped_disposition 7.
    - SECOND identical run — `generated=710 newly_inserted=0` (every type 0 newly
      inserted); queue total unchanged at 710; a status mutated to `resolved` between
      runs SURVIVED (by_status open 709 / resolved 1 post-rerun); reverted to leave
      the queue faithful (710 open).
  - Reconciliation vs the 23.3 signal baselines (item ≤ signal; dedup-collapse):
    charge_not_normalized 157 = unmapped_charge 156 + ambiguous_charge 1 ✓;
    disposition_not_mapped 7 = 7 ✓; sentencing_component_not_normalized 5 =
    ambiguous_sentencing_component 5 (all 5 were bare-hours ambiguous;
    unmapped_sentencing_component 0 — signal fully surfaced) ✓; money_amount_unparseable
    7 = 7 ✓; duration 280 = 280 ✓ (predicate_all=280, exact); missing_disposition_date
    211 = 211 ✓; sentinel_collision 17 (LOADED tally) = 17 ✓; additive 33 → 26 items +
    7 SUPPRESSED (read-only replay confirmed 26 additive + 7 suppressed == 33 multi,
    all 7 suppressed = money_unparseable, i.e. restitution-additive components already
    surfaced via money_unparseable — NO silent loss, the approved anti-double-flag
    guard). No item type is zero where its 23.3 signal exists → no stop-and-report.
- **Files touched:** `services/pipeline/src/pipeline/fact_review_vocab.py` (one
  approved type member), `services/pipeline/src/pipeline/facts/build_facts.py`
  (review-item wiring + `insert_review_items` + `_collect_warning_review_items` +
  report block; extended `_load_all_sentences` with docket/sequence/source ids),
  `services/pipeline/tests/test_review_item_wiring.py` (new tier-1 DB suite covering
  all 13 types + idempotency + status preservation), `services/pipeline/tests/
  test_fact_review_vocab.py` (13-member assertion), `services/pipeline/tests/
  test_facts_build_facts.py` (the now-obsolete `queue == 0` assertion updated to the
  4 items that seed produces), `tasks/worklog.md`. NO migrations, seeds, TS/web, or
  22.x/23.1/23.2/23.3 module-body edits.
- **Deviations:** none from the approved plan. During test authoring found the judge
  roster loader forbids two identities sharing a canonical name key, so judge
  ambiguity in the fixture is triggered via middle-name tolerance (a middle-less raw
  value matching two identities that differ only by middle) rather than duplicate
  display names — a fixture detail, no source-code impact.
- **Notes for 23.5 / 24.1:** the review queue is now populated (710 items on the
  canonical corpus, all `open`). Fact-build idempotency (delete-and-reinsert of
  facts) remains 24.1's job — 23.4 touched only review-queue idempotency; each
  `build-facts` still appends a new run.

## Task 23.5 — Structured CP↔MC Held-Case Linkage (2026-07-12)

- **What was built:** the 18.3 deferral landing — a new `parsed.docket_links` table
  and a linker that turns the held MC docket's `parsed.dockets.cross_court_dockets`
  capture into structured rows (source = MC held docket, target = the CP docket the
  case transfers to, link type `held_for_court`). In-corpus CP targets resolve to a
  `parsed.dockets` FK (resolved link); out-of-corpus targets record the target docket
  number with a null FK (unresolved link — a future-collection coverage signal);
  references the bounded §6.9 pattern cannot resolve route to `review.queue_items` via
  the existing 22.1/23.4 write path. Closes Phase 23.
- **INFORMATIONAL ONLY (AC4):** linkage does NOT change fact eligibility. The stage
  runs STRICTLY AFTER every outcome/sentence fact + its eligibility is computed and
  inserted; it only reads `parsed.dockets` and writes link rows + review items, and
  feeds nothing back. Boundary written as an explicit code comment at the seam
  (`build_facts.py`) and in `docket_links.py` / the migration. Attribution
  consequences are a Sprint 7 aggregation question, deferred.
- **Source seam (the ONE corrected decision, plan-approved after a STOP):** the linker
  keys off **MC dockets (`court_type_derived='MC'`) carrying a `cross_court_dockets`
  capture** — NOT presence of the field across all dockets. Recon R2's "22" sampled
  only the 40 `MC-*.json` files; the live corpus carries the field on **126** dockets
  (22 MC + 104 CP). The 104 CP dockets are other-county references (county codes ≠ 51,
  mostly `MD`), which §6.9 correctly rejects — a presence-based seam would have emitted
  104 false `malformed` review items and 126 links. The corrected MC-only seam yields
  exactly 22. Also: §6.7's null-disposition / event-key held model is a **CP-side**
  phenomenon (`NON_TERMINAL_CASE`); MC's held-for-court is a **disposed** charge
  (`disposition_raw` = a "Held for Court"-class value) carrying a cross-court reference
  — a distinct signal — so NO null-disposition filter is applied (it would exclude all
  22). This was adjudicated in planning chat, not self-resolved.
- **R3 (related_cases):** confirmed reserved evidence-source vocab member with ZERO
  held-for-court overlap in the corpus (it carries sibling / co-defendant MC
  associations); produces zero links this task. Every link stamps
  `evidence_source = cross_court_dockets`. Documented at `link_vocab.py` and the linker.
- **Lifecycle (RF1):** link rows are delete-and-reinserted per build (SD 6,
  current-state projection) — idempotent on content (proven by the rerun test: same
  tuples, count stable). Both FKs into `parsed.dockets` are `ON DELETE CASCADE`:
  `source_docket_id` (ownership) and the nullable `target_docket_id` (cross-reference —
  CASCADE self-heals under full rebuild; RESTRICT would block a legit CP reload and
  SET NULL would masquerade a resolved link as out-of-corpus). Review items travel the
  persistent, dedup-keyed, status-preserving 23.4 path instead — the two lifecycles
  coexist with no interaction.
- **Vocabulary (all plan-approved):** new module `link_vocab.py` with `LINK_TYPES`
  (`held_for_court`) and `LINK_EVIDENCE_SOURCES` (`cross_court_dockets`,
  `related_cases`); one member `unresolvable_cross_court_reference` added to
  `REVIEW_ITEM_TYPES` in `fact_review_vocab.py`. Its review items use `reason_code =
  review_needed` (generic) — linkage adds NO concept to `ELIGIBILITY_REASON_CODES`
  (AC4). Malformed vs ambiguous-target is carried in `candidate_context["subcase"]`,
  never a separate reason code (RF3).
- **Files touched:** new `db/migrations/20260712120000_create_parsed_docket_links.ts`
  (TypeScript DDL, SD 4; Python-only consumer) + `db/src/types.ts` (hand-authored
  `ParsedDocketLinksTable` + `Database` registration — there is no `pnpm generate`
  codegen; typecheck is the gate); new `services/pipeline/src/pipeline/link_vocab.py`;
  new `services/pipeline/src/pipeline/facts/docket_links.py` (linker); new
  `services/pipeline/tests/test_docket_links.py` (tier-1: bounded-parser unit + 5 DB
  tests — resolve / out-of-corpus / malformed / ambiguous-target / idempotent rerun);
  `services/pipeline/src/pipeline/fact_review_vocab.py` (one approved member) and its
  test `services/pipeline/tests/test_fact_review_vocab.py` (13→14, trivially
  necessary); `services/pipeline/src/pipeline/facts/build_facts.py` (in-tx linkage
  stage + summary block); `tasks/worklog.md`.
- **Ambiguous-target test (Tweak B):** two synthetic CP rows SHARE a `docket_number`
  (docket_number is not unique) as the resolution TARGETS, with an MC source
  referencing that number, so the target lookup returns 2 → review item, no link, no
  unresolved row.
- **Corpus acceptance run (verbatim, hygiene-clean, real `pca` corpus):**
    - `build-facts run=b5872703-e4de-40 status=completed`
    - linkage: `mc_source_dockets=22 links_total=22 resolved=0 unresolved=22`;
      `linkage_review_items malformed=0 ambiguous=0`.
    - DB after: `parsed.docket_links` = 22 (0 resolved / 22 unresolved; all
      `held_for_court` / `cross_court_dockets`; all 22 sources `court_type=MC`);
      `unresolvable_cross_court_reference` review items = 0.
  - **AC4 proof (per-run, Tweak A):** the 23.5 run's own fact rows are IDENTICAL to the
    23.4 baseline run — `facts_written=3162`, `sentence_facts_written=4162`,
    `charges_processed=3625` (baseline run 75ea1dd2: 3162 / 4162 / 3625); eligibility
    produced by the UNCHANGED 23.2/23.3 modules. `review_items generated=710
    newly_inserted=0` → `review.queue_items` total unchanged at 710. The only net-new
    linkage data is `parsed.docket_links` +22. Global fact totals rose by exactly one
    run's worth (12648→15810 outcome, 12486→16648 sentence) — normal append (`build-facts`
    is append-per-run; global fact idempotency is 24.1's job), NOT drift.
  - **RF4 reconciliation:** link count == 22 ✓; resolved == 0 / unresolved == 22 ✓
    (all 22 CP-51-CR targets out-of-corpus — a coverage finding, not a resolution
    failure; feeds future collection / COL 24.2 targeting); linkage review items == 0 ✓;
    malformed == 0 ✓; ambiguous == 0 ✓; no target lookup ≥2 on the real corpus ✓;
    no per-run fact/eligibility drift ✓; `review.queue_items` == 710 after the run ✓.
    No STOP condition triggered.
- **Deviations:** one, adjudicated in planning chat before coding — the source seam was
  corrected from the approved plan's presence-based keying to MC-only keying after the
  live DB revealed 126 (not 22) dockets carry `cross_court_dockets`. No other deviation.
- **Notes for 24.1 / 24.2:** the 22 unresolved held-for-court links are the corpus's
  MC→CP coverage gap — every referenced CP-51-CR docket is uncollected. This is a clean
  future-collection target list (AC3). `parsed.docket_links` is delete-and-reinserted
  each `build-facts`, so 24.1's full-corpus run repopulates it; the informational
  boundary means these links never enter the eligibility funnel (Sprint 7 aggregation).

## Task 24.1 — Full-Corpus Fact Build (Acceptance Authority) — 2026-07-12

- **What was built:** no source changes. Task 24.1 is an orchestrated end-to-end
  run over the loaded canonical corpus (1,603 dockets) using the already-merged
  21.x/22.x/23.x modules, plus a run-report artifact and this worklog entry. All
  R1–R5 recon items were resolved in the plan against the merged code + live DB
  before running.
- **Files touched (repo):** `tasks/worklog.md` only. Run report written OUTSIDE the
  repo at `~/court-data/reports/24.1-fact-build-run-aef44371.txt` (counts / fixed
  codes / run UUID only; no docket-derived data). `tasks/current-task.md` carries a
  pre-existing human edit — deliberately NOT staged.
- **R1 resolution (recorded):** fact builds are run-partitioned APPEND, confirmed
  empirically (global `fact.charge_outcomes` 15,810→18,972 = 6×3,162; `fact.charge_
  sentences` 16,648→20,810 = 5×4,162). SD 6's "delete-and-reinsert" wording is
  realized as append for the fact tables (literal delete-and-reinsert applies only
  to `parsed.docket_links`). Known, recorded divergence — not a bug, not a stop.
  Every reconciliation gate is scoped to the new `build_run_id`; the invariant is
  "one run's worth added" globally.
- **Corpus acceptance run (verbatim, hygiene-clean, real corpus):**
    - `build-facts run=aef44371-c09f-48 status=completed`
    - `charges_processed=3625 facts_written=3162 held_skipped=463`;
      `reconcile facts_written+held_skipped==charges_processed: True`.
    - outcome eligibility: `mvp_eligible=437 public_eligible=411
      judge_specific_eligible=411 review_needed=226`.
    - `sentence_facts_written=4162 components_on_disposed=4162`;
      `reconcile sentence_facts==components_on_disposed: True`; sentence eligibility
      `mvp_eligible=493 public_eligible=432 judge_specific_eligible=432
      review_needed=317`.
    - SD-15 (amended) soft report: divergence=33 straddle_mvp=29 delta_days=218..757;
      sentence eligibility keys off the captured `sentence_date`, not disposition_date.
    - linkage: `mc_source_dockets=22 links_total=22 resolved=0 unresolved=22`.
    - review: `generated=710 newly_inserted=0` (queue steady at 710 — idempotent).
- **Reconciliation gates (all PASS, per-run on build_run_id=aef44371):** disposed
  3,162 = outcome facts 3,162 + 0 exclusions; held charges with an outcome fact = 0;
  components-on-disposed 4,162 = sentence facts 4,162 + 0; NON_TERMINAL_CASE (104
  dockets) held charges → 0 outcome facts; recovered-5 SENTINEL_COLLISION (5 dockets,
  12 outcome facts on disposed charges) show disposition surviving with judge
  attribution empty (`judge_attribution_method=none`×12, `normalized_judge_id` NULL
  ×12); review_needed dockets = 75 consistent with envelope tallies; queue = 710 after.
- **Exclusion counts (AC2, explicit):** held-charge = 463; quarantine = 0 (all 1,603
  loaded `imported`; zero `parse_failed`).
- **Headline (Risk 2):** judge_specific_eligible / public_eligible = 411 / 411 =
  100%. Within the MVP public-eligible surface judge attribution is complete this
  run; judge data is NOT thinner than hoped for the judge-specific surface's first
  sizing. The 72 'none'-attribution outcome facts all fall outside the public-eligible
  set.
- **Deviations:** none. No STOP condition triggered; no anomaly required planning-chat
  adjudication.
- **Notes for 24.2 / 24.3:** the 22 unresolved held-for-court CP targets remain the
  MC→CP coverage gap (COL 24.2 targeting). 24.3 opens the court_type verify-then-decide
  step; this run touched no parser and no record schema. Global fact tables now carry 6
  outcome runs / 5 sentence runs of history (append) — Sprint 7 aggregation must select
  the latest completed `build_run_id`, never the global table count.

## Task 24.2 — COL Intake Protocol + First Intake — 2026-07-13

- **What was built:** the COL intake protocol (documented + executed once), growing
  the parsed corpus beyond the 1,603 invariant and materially deepening MC evidence.
  Orchestration over already-merged 16.3/16.2/18.1/19.2/21.3/24.1 tooling — NO new
  pipeline code, no module-body changes. One committed doc + this worklog entry.
- **Files touched (committed):** `agent-docs/intake/col-intake-protocol.md` (new);
  `tasks/worklog.md` (this entry). No source/schema/test/migration changes.
- **Out-of-repo artifacts (~/court-data/, per §6.8):** frozen snapshot
  `intake-snapshots/24.2-20260713T000946Z/` + `…​.MANIFEST.json`;
  `extracted-intake-20260713/`; `envelopes-intake-20260713/`; 3,166 new tier-2
  goldens under `goldens/`; run report `reports/24.2-intake-run-d591902f.txt`.
- **Rulings executed (planning chat):** (1) full frozen intake (complete snapshotted
  set); (2) exclude the 40 already-loaded MC docket numbers by FILTERING the input
  set — NOT a load/16.x guard (option (a); (c) rejected). Freeze added as a PERMANENT
  protocol step (collector appends continuously, so the staged set is a moving target
  and a fact build cannot reconcile against a mutating denominator).
- **Freeze + exclude (intake denominator):** staged-at-freeze 3,206 − 40 already-loaded
  MC = **3,166 included** (3,166 unique content hashes; 70 PDFs arrived between recon
  and freeze — exactly why the freeze exists). Content-hash dedupe alone caught 0 of
  the 40 (re-collected copies have different bytes → different `file_hash`); the
  docket-number exclusion is what prevents duplicate `parsed.dockets` rows.
- **Stage counts (AC2; raw output verbatim in the run report):** import-manual
  `imported=3166 duplicate=0 invalid=1 failed=0` (invalid=1 = the in-dir MANIFEST.json
  sidecar, since relocated); extract-text `success=3166 partial=0 needs_ocr_or_review=0
  failed=0`; parse `parsed=3166 failed=0` (**ZERO quarantine**); run-fixtures tier1
  `match=34`, tier2 `new=3166 diverged=0 failed=0 golden_missing=0`; load `loaded=3166`
  (all other categories 0). `--init-goldens` write recorded here per the 19.2 contract.
- **Quarantine (R6):** 0 isolated, 0 systematic. All 3,166 parsed clean; no shared-layout
  MC failure cluster → the parser is adequate on this MC class (MC-readiness evidence).
  The 15 filing-year-2024 PDFs loaded normally (window enforced at fact eligibility, not
  parse; they show as pre-window drops).
- **Corpus counts formally restated (AC3 — supersedes 1,603 by name):** loaded dockets
  **1,603 (1,563 CP + 40 MC) → 4,769 (1,563 CP + 3,206 MC)**; tier-2 goldens 1,604 →
  4,770; import records 1,604 → 4,770; envelope artifacts 1,603 canonical (immutable,
  `envelopes-2026-07-11-172514/`) + 3,166 intake = 4,769; `parsed.charges` 3,625 →
  13,334; `parsed.sentences` 4,162 → 4,733. Capstone baseline UNTOUCHED; comparator not
  run over new dockets (SD 14). CP side unchanged in every dimension — all growth is MC.
- **MC evidence position restated (AC4):** MC dockets **40 → 3,206**; MC public-eligible
  outcome facts **~0 → 319** (judge-specific 253); CP public-eligible 411 UNCHANGED;
  total public-eligible outcome facts 730 = 411 CP + 319 MC. The POC "correct but
  under-evidenced" verdict UPDATES to **materially evidenced for the terminal slice,
  with a defined coverage tail** — honest, not dressed as maturity. Two caveats:
  (a) most MC disposed-charge volume is **'Held for Court' bind-overs** (5,564 → outcome
  `other`; 844 `IGJ/HP - Held for Court` → `unknown`/review) plus 1,786 MC held
  (null-disposition) charges — NON-TERMINAL MC preliminary-hearing results, both
  categories NON-PUBLIC so nothing leaks; (b) MC normalization-coverage tail
  (`charge_not_normalized` 157 → 1,361; `unmapped_disposition` 7 → 928 — rosters curated
  against the CP-dominant corpus; new MC vocabulary routes to review per SD 9).
- **Corpus rerun (verbatim, hygiene-clean, real corpus; AC5):** `build-facts
  run=d591902f-8b2d-4c status=completed`; `charges_processed=13334 facts_written=11175
  held_skipped=2159`; `reconcile facts_written+held_skipped==charges_processed: True`;
  `sentence_facts_written=4733 components_on_disposed=4733`; `reconcile
  sentence_facts==components_on_disposed: True`. Higher per-run counts than 24.1
  (3,625/3,162/463/4,162), as expected — a new `build_run_id` partition (run-partitioned
  append; 24.1 retained). Outcome eligibility `mvp=1067 public=730 judge=664
  review=7695`; sentence `mvp=1064 public=733 judge=672 review=356`.
- **Reconciliation gates (all PASS, per-run on build_run_id=d591902f, grown corpus):**
  disposed 11,175 = outcome facts 11,175 + 0; facts+held 11,175+2,159 = 13,334; held
  charges with an outcome fact = 0; components-on-disposed 4,733 = sentence facts 4,733
  + 0; NON_TERMINAL_CASE (687 dockets) held → 0 outcome facts; recovered-5
  SENTINEL_COLLISION (original 5 dockets, 12 outcome facts) UNCHANGED
  (`judge_attribution_method=none`×12, `normalized_judge_id` NULL ×12); **duplicate
  docket_numbers = 0** (Decision-2 exclusion worked); review-item dedup holds — prior
  queue 710 preserved, every type's (generated − newly_inserted) equals its 24.1 count,
  new items only for new dockets (queue 710 → 10,369, all 'open').
- **Deviations:** none from the approved plan. STOP conditions (reconciliation mismatch /
  parse failures beyond quarantine / dedupe anomalies / unattributable surprise) — NONE
  triggered.
- **FLAGGED FOR PLANNING CHAT (not fixed — 24.2 is orchestration; surfacing ≠ fixing):**
  should MC **'Held for Court'** be modeled as NON-TERMINAL (no outcome fact, like held
  charges) rather than mapped to outcome `other`? Today it is contained (non-public,
  reconciles cleanly) but it dominates MC outcome-fact volume — a real taxonomy/
  eligibility-semantics decision for Sprint 6/7, tied to the CP↔MC linkage/coverage story
  (`mc_source_dockets=2,023 links=2,017 resolved=4 unresolved=2,013`; the 2,013
  out-of-corpus CP targets are the direct future-collection coverage signal).
- **Notes for 24.3 / Sprint 7:** 24.3 opens the `court_type` verify-then-decide step over
  this GROWN corpus (now 3,206 MC prefix-derivable dockets, not 40). Global fact tables
  now carry 7 outcome runs / 6 sentence runs of history (append) — Sprint 7 aggregation
  must select the latest completed `build_run_id`, never the global table count, and must
  decide MC 'Held for Court' semantics before publishing MC results. MC-dominance
  (3,206 MC vs 1,563 CP loaded) has no Sprint 5 consequence (no aggregates generated).

## Task 24.3 — `court_type` Populate-vs-Drop Decision (verify-and-worklog) — 2026-07-12

- **What was built:** nothing in code. 24.3 is verify-and-worklog: the sanctioned
  `court_type` parser touch was NOT exercised because R1 verification found no defect
  to fix. No parser change, no record-schema change, no `parser_version` bump (stays 2),
  no migration, no `db/src/types.ts` change, no tier-1/tier-2/baseline golden delta.
  Corpus untouched — no re-parse, no reload, no fact rebuild.
- **Files touched (committed):** `tasks/worklog.md` (this entry) only.
- **AC1 — verified finding (raw DB output over all 4,769 loaded dockets):**
  `parsed.dockets.court_type_recorded` is populated 100% — `Municipal Court`=3206,
  `Common Pleas`=1563; `rec_null`=0. It matches `court_type_derived` (`MC`/`CP`) on
  every row: consistent=4769, mismatched=0. Versions uniform: (record=2, envelope=5)
  across all 4769. `raw.source_documents.court_type` (16.3 import code) likewise
  populated: `MC`=3206, `CP`=1563. Re-verified on the GROWN corpus (4,769), not
  assumed to carry from the pre-intake 1,603.
- **AC1 reconciliation (SD 13 recon-vs-finding discrepancy resolved):** SD 13's
  "None everywhere" premise was a VERIFICATION ERROR, contradicted on every axis.
  (a) Code: the record's `case.court_type` is set from `detect_court_type(docket_number)`,
  which returns `"Municipal Court"` or `"Common Pleas"` and STRUCTURALLY cannot return
  None; this has held since the v1 parser port (17.2) through the v1→v2 bump (18.3).
  (b) Canonical envelopes store the populated string on disk. (c) The loader stores it
  as-is into `court_type_recorded`. The ONLY `court_type: None` in the tree is the
  `manual_import` fallback for a docket number that does not match the CP/MC prefix — a
  DIFFERENT, same-named field on the import record; every real docket matched the prefix,
  so even that column is fully populated. Best reconstruction: the earlier recon conflated
  that import-path None default with the parsed record field (or read a pre-load state).
- **Decision executed (planning-chat adjudicated):** KEEP AS-IS. R1 overrides the SD 13
  premise; because `court_type_recorded` is populated and 100% consistent with the
  prefix-derived value, there is no always-null field to drop and no missing value to
  populate — the sanctioned touch has no target. Both columns are kept;
  `court_type_derived` (docket-number prefix) remains authoritative by decision,
  unchanged. The AC2 fallback (keep + loader consistency check, mismatch → review item)
  was DECLINED in the planning chat as new behavior beyond the sanctioned scope and
  zero-yield today (0 mismatches across 4,769).
- **R2–R5:** not resolved — moot without a schema change (no drop/populate path taken).
- **Deviations from plan:** the task framed 24.3 as a decision-scoping / version-reload
  exercise premised on None-everywhere; R1 invalidated that premise, so per AC2 and the
  Process STOP rule ("court_type populated anywhere → STOP, never self-resolved") the
  direction was adjudicated in the planning chat to KEEP AS-IS. No unilateral scope change.
- **Notes for next task / Sprint 6–7:** SD 13 as written is superseded by this finding —
  `court_type_recorded` is populated and prefix-consistent corpus-wide; treat
  `court_type_derived` as the authoritative court-type source (decision, not defect).
  No court_type work remains. 24.3 closes Phase 24; the PR covers 24.1 + 24.2 + 24.3.

## Task 25.1 — Normalization and Attribution Report — 2026-07-12

- **What was built:** `agent-docs/normalization-attribution-report.md`, the committed
  aggregate-only summary of record for Sprint 5. Documentation only — no code, schema,
  parser, seed, or fact-build change. It sizes the Sprint 6 review queue and the Sprint 7
  eligible-fact volumes, carries explicit Sprint 6/7 readiness verdicts, and includes a
  methodology section written to be lifted into Sprint 7 public methodology copy.
- **Files touched (committed):** `agent-docs/normalization-attribution-report.md` (new);
  `tasks/worklog.md` (this entry). Nothing under `docs/`, no source/schema/test/migration.
- **File location (planning-chat resolved):** the sprint plan Task 25.1 names
  `docs/…` but the task GOAL names `agent-docs/…`; the task's SCOPE AUTHORITY subordinates
  the plan to §6, the CLAUDE.md documentation rule forbids agent-created files under
  `docs/`, and the 20.1 precedent (`agent-docs/parser-proof-of-concept.md`) landed under
  `agent-docs/`. Agent stopped-and-reported the conflict; human ruled **agent-docs/**.
- **Provenance discipline (honesty bar):** every figure carries a named source run or a
  read-only query scoped to the post-intake build. Pre-intake [24.1, `aef44371`] and
  post-intake [24.2, `d591902f`] figures are labelled and never blended. Read-only queries
  were run via the pipeline venv (psycopg) with `DATABASE_URL` sourced at the CLI boundary
  (salt never echoed); raw output is pasted verbatim in the 25.1 completion report.
- **RECON resolved (source run per figure class):** R1 post-intake corpus 4,769
  (1,563 CP + 3,206 MC), primary run `d591902f`; R2 pre/post reconciled (23.3's 4,162/432
  = [24.1] sentence facts/public; current 4,733/733); R3 judge-attributable fraction of
  public-eligible outcome facts = 664/730 = 91.0% (CP 411/411=100%, MC 253/319=79.3%);
  R4 linkage 2,023 source / 2,017 links / 4 resolved / 2,013 unresolved; R5 date-range
  day-by-day MC collection over filing/docketing dates 2025-01-01→2025-04-29 (window
  ledger).
- **Load-bearing corrections carried straight:** SD-15 (amended) — `sentence_date`
  captured at two parser sites, usually equal to disposition_date, can predate it,
  eligibility keys off the actual sentence_date; post-intake divergence CONFIRMED against
  the current corpus = 34 of 4,733 (always earlier, 29 straddle 2025-01-01, delta 218–757;
  CP baseline was 33). SD 13 (court_type, per 24.3) — populated 100%, 100% prefix-consistent;
  a one-liner, never "inert/None".
- **Read-only queries run (all scoped to `build_run_id=d591902f`, verbatim in completion
  report); every result reconciled with the 24.1/24.2 reports, NO STOP triggered:** fact
  counts (11,175 outcome / 4,733 sentence); charge/outcome/judge/component match-method
  distributions; sentencing-category split; money coverage (37/12/7/18); SD-15 divergence
  recompute (34); public-eligible + judge-specific by court_type (CP 411/411, MC 319/253);
  run-row `counts` jsonb (funnel, reason tallies, review-item by type, linkage).
- **Deviations from plan:** none, after the plan-review location fix. The one open item
  (docs/ vs agent-docs/) was stopped-and-reported per the task Process, not self-resolved.
- **Notes for 25.2 / Sprint 6–7:** 25.2 is a no-code human exit demo, so 25.1 is the only
  committed task on phase-25; the phase-25 PR fires after this commit (covers 25.1 alone)
  and merges on green, and the exit demo runs on merged main. The MC 'Held for Court'
  non-terminal-semantics question (raised in 24.2) is restated in the report as a Sprint
  6/7 adjudication item. Sprint 7 aggregation must select the latest completed
  `build_run_id` (append semantics), never the global fact-table count.

## Task 26.1 — Generator Command + Run Lifecycle + Charge-Only Outcome Aggregates (2026-07-13)

- **What was built:** `pipeline generate-aggregates` — a new console-script subcommand that
  opens an `analytics.aggregate_runs` row, aggregates `public_eligible` outcome facts from
  ONE fact build run into `analytics.charge_outcome_aggregates` (charge × outcome-category
  count / percentage / outcome sample size / eligible disposition-date range / thin-data
  flag), and prints a counts-only run report. Charge-only outcomes only (sentencing 26.2,
  judge-specific 27.x, validation 28.1, publish 28.2 remain unbuilt).
- **Files touched (committed):** `services/pipeline/src/pipeline/aggregates/__init__.py` (new);
  `services/pipeline/src/pipeline/aggregates/generate.py` (new); `services/pipeline/src/pipeline/cli.py`
  (register subcommand + args + CI-refuse/`DATABASE_URL`-boundary dispatch);
  `services/pipeline/tests/test_aggregates_generate.py` (new tier-1 suite);
  `tasks/worklog.md` (this entry). No `db/**`, no `apps/**`, no `docs/**`; `tasks/current-task.md`
  left uncommitted (human-managed, per the 24.3/25.1 commit precedent).
- **STOP-and-report resolved in the planning chat (status vocabulary):** the spec's lifecycle
  labels `generated`/`validated` are NOT `analytics.aggregate_runs.status` enum values — the
  CHECK permits only `in_progress|completed|failed`, and the publish CHECK ties `published_at`
  to `status='completed'`. Adjudicated mapping (no `analytics.*` migration this task, carried
  forward for 28.1/28.2): **"generated" (26.1) → `status='in_progress'`, `published_at`/
  `invalidated_at` NULL** (invisible to the §6.3 public-API predicate); **"validated" (28.1) →
  `completed`**; **"failed" → `failed`**; **"published" (28.2) → set `published_at`**. The
  mapping lives in the module docstring so later phases inherit it explicitly.
- **Secondary adjudications:** aggregate-run `--label` is report/log only (no column exists,
  not persisted); the thin-data reason `below_minimum_sample` is implied by the `is_thin_data`
  boolean (no reason column) and surfaced only in the run report.
- **Eligibility is READ, never recomputed (SD 1):** the generator selects `WHERE public_eligible`
  and groups; it re-applies no date/match/review rule. The excluded-by-reason tally is read
  straight off each excluded fact's `ineligibility_reason_codes`. No confidence threshold exists.
- **Lifecycle / idempotency (SD 4):** each invocation opens a NEW run; rows are written via
  delete-then-insert inside one transaction (aggregate rows are immutable → never ON CONFLICT
  UPDATE). Published/invalidated runs are never read for reuse and never mutated; a generation
  failure rolls the write back and marks the run `failed`. Confirmed on the real corpus: the
  seeded published run and the seeded in_progress decoy were untouched (active-published count
  stayed exactly 1).
- **Build-run selection (pinned decision 1 / check B):** default = latest completed
  (`WHERE status='completed' ORDER BY completed_at DESC LIMIT 1`); `--build-run <id>` overrides
  and must be completed. The real-corpus demo resolved the **default** build run
  `d591902f-8b2d-4c…` (latest completed) — reported `(default)` in the run output.
- **Defensive STOP (check A) kept:** a `public_eligible` fact with a null `normalized_charge_id`,
  a null `disposition_date`, or a pre-window date raises `FactIntegrityError` (exit 2, no run
  row) rather than silently skipping — `public_eligible` structurally guarantees all three.
- **Real-corpus demonstration (§6.10, verbatim in the completion report):** default build run
  `d591902f…`; facts_loaded=11175, facts_included=730, facts_excluded=10445; charges_with_aggregates=64,
  outcome_aggregates_generated=156, thin_data_charges=42; data_range 2025-01-01..2026-06-25.
  Post-run invariants over all 64 charges: `SUM(count)=sample_size` and `SUM(percentage)≈100`
  within tolerance; `is_thin_data == (sample_size<10)`; no `date_range_start` before 2025-01-01.
  (The 730 figure is this active run's yield, not the historically-cited number — reported as-is.)
- **Deviations from plan:** none. The status-vocabulary conflict was stopped-and-reported and
  adjudicated in the planning chat before implementation (never self-resolved).
- **Notes for 26.2 / 28.x:** 26.2 adds `analytics.charge_sentencing_aggregates` with an
  independent sentencing sample size (SD 5) — reuse `build_charge_outcome_aggregates`' grouping
  shape and `_write_aggregates`' delete-first path. 28.1 flips the working run to `completed`
  on a clean validation and `failed` otherwise; 28.2 sets `published_at` (CHECK already requires
  `completed`) and invalidates the seeded published run in the same transaction. The generator
  currently leaves each generated run as `in_progress`; 28.x selects the run to validate/publish
  explicitly (do not assume a single working run — the seed decoy is also `in_progress`).

## Task 26.2 — Charge-Only Sentencing Aggregates (closes Phase 26) (2026-07-13)

- **What was built:** extended `pipeline generate-aggregates` so the SAME invocation and the
  SAME write transaction that produces the 26.1 outcome rows now also produces
  `analytics.charge_sentencing_aggregates` under the SAME `aggregate_runs` run. No second run,
  no second subcommand, no restructure of the 26.1 outcome builder.
- **Recon (all three checks passed — no STOP):** (1) the 26.1 core already separates
  *read → pure build → single `_create_run` → one `with conn.transaction():` write block →
  summary*, so a sentencing pass drops into the existing transaction beside `_write_aggregates`
  with no restructure; (2) `analytics.charge_sentencing_aggregates` carries the full
  `AggregateRowBase` set plus `sentencing_sample_size` (types.ts) — no missing column, no
  migration; (3) `fact.charge_sentences` column names confirmed: `public_eligible` (eligibility),
  `sentencing_category_code` (category), `sentence_date` (date), `normalized_charge_id` (FK),
  `taxonomy_version`, `ineligibility_reason_codes` (text[]); multi-component sentences are 1:1
  rows, so grouping counts each component.
- **Files touched:** `services/pipeline/src/pipeline/aggregates/generate.py` (new
  `_load_sentence_facts`, `build_charge_sentencing_aggregates`, `_write_sentencing_aggregates`,
  `_SENTENCING_INSERT_COLUMNS`; `generate_aggregates` loads/builds both populations before any
  write and writes both in one transaction; `_print_summary` extended with the sentencing
  tallies + `charges_with_outcomes_no_sentencing`); `services/pipeline/tests/
  test_aggregates_generate.py` (7 pure sentencing tests + 2 DB integration tests + seeder
  `new_charge`/`sentenced_outcome` helpers, `fact()` gained an optional `charge_id`);
  `services/pipeline/src/pipeline/cli.py` (two user-facing help strings updated for accuracy —
  trivially-necessary in-surface touch).
- **Independent sentencing denominator (SD 5):** `sentencing_sample_size` = the charge's eligible
  *sentence* facts (one per component, never collapsed), never copied from the outcome count.
  Percentages are against that denominator; the thin flag uses the same
  `THIN_DATA_MIN_SAMPLE_SIZE` config applied to the sentencing sample.
- **Eligibility READ, never recomputed (SD 1) + STOP (adjudicated):** sentencing eligibility keys
  off the fact's own `public_eligible` and the actual `sentence_date` (SD 15). A `public_eligible`
  sentence fact with a null charge, a null `sentence_date`, or a `sentence_date` before the
  2025-01-01 floor raises `FactIntegrityError` (exit 2, no run row) — a fact-layer defect
  surfaced, never a silent filter.
- **Absence, not placeholder (SD 6):** a charge with eligible outcomes but no eligible sentence
  facts produces outcome rows and NO sentencing rows — no error, no placeholder. The run report
  counts these as `charges_with_outcomes_no_sentencing`, derived from the emitted rows so neither
  pure builder is touched to expose its grouping.
- **Run-level `data_range_end` (adjudicated in planning chat):** the run row's end is the UNION
  envelope — `max` over both eligible outcome disposition dates and eligible sentence dates — so
  the run covers everything it wrote; per-row ranges stay population-specific (outcome rows from
  `disposition_date`, sentence rows from `sentence_date`). Only ever extends the value; 26.1
  outcome-only tests are unaffected.
- **Real-corpus demonstration (§6.10, verbatim in the completion report):** default build run
  `d591902f-8b2d-4c…` (latest completed); aggregate run `2d4707ca-6bb4-4b…`. Sentencing yield:
  sentence_facts_loaded=4733, included=733, excluded=4000; charges_with_sentencing=58,
  sentencing_aggregates_generated=124, thin_data_sentencing_charges=36;
  charges_with_outcomes_no_sentencing=6. Outcome side unchanged from 26.1 (156 rows / 64 charges).
  Independence is visible: 733 included sentence facts vs 730 included outcome facts;
  64 − 58 = 6 = charges_with_outcomes_no_sentencing. (Reported as this run's yield, not a pinned
  figure.)
- **Deviations from plan:** none.
- **Notes for 27.x / 28.x:** 27.1/27.2 add judge-specific outcome/sentencing aggregates —
  reuse the grouping/write shapes here plus a judge id and the same-run baseline guarantee
  (SD 7). 28.1 validation must now check BOTH aggregate tables per run (sentencing rows:
  `SUM(count)=sentencing_sample_size`, percentages within tolerance, `date_range_start` ≥
  2025-01-01); 28.2 publish/invalidate is unchanged by this task. Local note: the fully-migrated
  pipeline test DB is `pca_test`; `pca_pipeline_test` is behind on unrelated migrations
  (docket_links / build_facts / review) and fails those suites — the aggregate suite passes on
  both.

## Task 27.1 — Judge-Specific Outcome Aggregates + Baseline (2026-07-13)

- **What was built:** a judge-specific outcome aggregation pass INSIDE the existing
  `pipeline generate-aggregates` invocation (Phase 26 shape preserved: read → pure build with all
  STOP checks pre-write → single `_create_run` → one write transaction → summary). New pure builder
  `build_judge_outcome_aggregates` groups `judge_specific_eligible` outcome facts by charge+judge
  pair, then by outcome category, and writes `analytics.judge_outcome_aggregates` rows under the
  SAME run and SAME transaction as the charge-only passes — no new `aggregate_runs` row, no new
  status, no restructure of the existing builders, no `analytics.*` migration (recon confirmed the
  Sprint 2 table matches: charge-only outcome shape + `judge_id`, unique on
  run+charge+judge+category).
- **Files touched:** `services/pipeline/src/pipeline/aggregates/generate.py` (loader gained
  `normalized_judge_id, judge_specific_eligible` — `judge_attribution_method` deliberately NOT
  selected, SD 1; new builder + `_write_judge_outcome_aggregates` delete-and-reinsert, SD 4; run
  report gained `judge_outcome_aggregates_generated`, `charge_judge_pairs_covered`, and an approved
  parity `thin_data_pairs` line; judge date-max joined the run-level union envelope — structurally
  a subset of the outcome envelope, included defensively); `services/pipeline/tests/
  test_aggregates_generate.py` (8 pure judge tests + 2 DB integration tests; seeder gained
  `new_judge`, `fact()` gained optional `judge_id`/`judge_specific_eligible`; fixture truncates
  `ref.normalized_judges`; sentencing STOP test also asserts zero judge rows leak).
- **Per-pair denominator (pinned):** each row's `sample_size` is the PAIR's eligible fact count,
  never the charge-wide count; percentages, thin flag (`THIN_DATA_MIN_SAMPLE_SIZE`, reason
  `below_minimum_sample`), and per-row date ranges are all pair-population-specific.
- **STOP guards extended:** a `judge_specific_eligible` fact with a null judge FK, null charge FK,
  null disposition date, or pre-2025-01-01 date raises `FactIntegrityError` (exit 2, no run row) —
  fact-layer defect surfaced pre-write, never silently filtered.
- **Baseline (SD 7):** test-asserted only (every judge aggregate's charge has a same-run
  charge-only outcome aggregate; NOT EXISTS query), no runtime enforcement — 28.1 re-validates
  independently. Never generated separately.
- **Housekeeping:** `pca_pipeline_test` brought current via `migrate:latest` — actual pending set
  was ONE migration (`20260712120000_create_parsed_docket_links`); the handoff note listing
  build_facts/review as pending was stale (they were applied 2026-07-12). Both test DBs now
  equivalent.
- **Real-corpus demonstration (§6.10, verbatim in the completion report):** default build run
  `d591902f-8b2d-4c…` (latest completed); aggregate run `51d27853-4788-42…`.
  judge_outcome_aggregates_generated=456, charge_judge_pairs_covered=395, thin_data_pairs=393.
  Judge coverage is SPARSE (393/395 pairs thin) — reported as a finding of this run's yield, not a
  failure and not a pinned figure. Charge-only side unchanged from 26.2 (156 outcome rows / 64
  charges; 124 sentencing rows / 58 charges). Baseline spot-verified on the real run: 0 judge rows
  without a same-run charge-only counterpart.
- **Deviations from plan:** none (thin_data_pairs report line and housekeeping-discrepancy
  handling were approved in planning before implementation).
- **Notes for 27.2 / 28.x:** 27.2 mirrors this pass over `fact.charge_sentences`
  (`judge_specific_eligible` + `normalized_judge_id` + independent per-pair sentencing denominator,
  baseline against the same-run charge-only SENTENCING aggregate). 28.1 validation must now cover
  THREE aggregate tables per run and re-validate the baseline itself. Phase-27 PR opens after 27.2
  (one commit per task, never squash).

## Task 27.2 — Judge-Specific Sentencing Aggregates + Baseline (2026-07-13)

- **What was built:** the fourth aggregation pass INSIDE `pipeline generate-aggregates`
  (27.1's shape preserved exactly: read → pure build with all STOP checks pre-write → single
  `_create_run` → one write transaction → summary). New pure builder
  `build_judge_sentencing_aggregates` groups `judge_specific_eligible` sentence facts by
  charge+judge pair, then by sentencing category, and writes
  `analytics.judge_sentencing_aggregates` rows under the SAME run and SAME transaction as the
  other three passes — no restructure of existing builders, no `analytics.*` migration (recon
  confirmed the Sprint 2 table: charge-only sentencing shape + `judge_id`, sample column
  `sentencing_sample_size`).
- **Files touched:** `services/pipeline/src/pipeline/aggregates/generate.py` (sentence loader
  gained `normalized_judge_id, judge_specific_eligible` — the same two-column extension 27.1
  made to the outcome loader; `judge_attribution_method` again deliberately NOT selected, SD 1;
  new builder + `_write_judge_sentencing_aggregates` delete-and-reinsert, SD 4; run report
  gained `judge_sentencing_aggregates_generated`, `charge_judge_sentencing_pairs_covered`, and
  the parity `thin_data_sentencing_pairs` line in 27.1's exact console format; judge-sentencing
  date-max joined the run-level union envelope); `services/pipeline/tests/
  test_aggregates_generate.py` (9 pure judge-sentencing tests incl. the independent-denominator
  check + 2 DB integration tests; `_sfact` gained the two judge keys mirroring the loader shape;
  seeder `sentenced_outcome` gained optional `judge_id`/`judge_specific_eligible`, stamping
  parent AND components with the sentence-fact invariant `judge_specific_eligible and
  public_eligible`).
- **Independent denominator (SD 5, pinned):** each row's `sentencing_sample_size` is the PAIR's
  eligible SENTENCE-fact count — never the pair's outcome sample, never charge-wide, never
  copied. Test-proven pure (3 outcome facts vs 1 sentence fact, same pair) and in the DB suite
  (pair outcome sample 2 vs sentencing sample 10).
- **STOP guards (SD 15):** a `judge_specific_eligible` sentence fact with a null judge FK, null
  charge FK, null `sentence_date`, or pre-2025-01-01 `sentence_date` raises
  `FactIntegrityError` pre-write (exit 2, no run row). Guards check `sentence_date` — the
  independently-captured sentencing date — never the parent disposition date.
- **Baseline (SD 7):** test-asserted only (NOT EXISTS against same-run
  `charge_sentencing_aggregates`), no runtime enforcement; 28.1 re-validates. Recon note: the
  guarantee is structural DIRECTLY on sentence facts — `sentence_facts.py` enforces
  `judge_specific_eligible implies public_eligible` as a dataclass invariant, so every
  judge-sentencing fact is itself in the charge-only sentencing denominator; the assertion
  guards regressions, it does not carry unique weight.
- **Real-corpus acceptance run (verbatim in the completion report):** default build run
  `d591902f-8b2d-4c…` (latest completed); aggregate run `65f4c65f-4691-48…`.
  judge_sentencing_aggregates_generated=423, charge_judge_sentencing_pairs_covered=344,
  thin_data_sentencing_pairs=339. FINDING (unanchored): coverage is NOT the near-zero the task
  anticipated — 344 pairs, 339/344 thin, consistent with the 27.1 judge-outcome sparsity
  pattern (395 pairs / 393 thin). Baseline spot-verified on the real run: 0 judge-sentencing
  rows without a same-run charge-only sentencing counterpart. Charge-only and judge-outcome
  passes unchanged (156/124/456 rows as in 27.1).
- **Deviations from plan:** none.
- **Notes for 28.x:** 28.1 validation must now cover FOUR aggregate tables per run
  (`SUM(count)=sentencing_sample_size` on both sentencing tables, percentages within tolerance,
  `date_range_start` ≥ 2025-01-01, baseline re-validation for BOTH judge tables — outcome
  against charge-only outcome, sentencing against charge-only sentencing). Phase 27 closes with
  this task's PR (one commit, never squash).

## Task 28.1 — Aggregate + Privacy Validation (2026-07-13)

- **What was built:** `pipeline validate-aggregates`, the separate validation step (SD 3) gating
  publish over a GENERATED (in_progress, unpublished) run. Three check families across ALL FOUR
  aggregate tables: per-group/row integrity (category counts sum to the group's one consistent
  sample size; percentage within ±0.005 inclusive `Decimal` tolerance of count/sample; sample
  size present; date range present, not inverted, start ≥ DATA_START_DATE; taxonomy version and
  run id present), SD-7 baseline (every judge-covered charge has a same-run charge-only
  counterpart, outcome↔outcome and sentencing↔sentencing), and privacy (every row, all columns
  JSON-shaped, through the forbidden-field scan). Verdict per the 26.1 status mapping — no new
  values, no migration: violations → `status='failed'` (terminal; the existing
  `aggregate_runs_published_at_check` CHECK structurally blocks publish); clean →
  `status='completed'` + `completed_at`. Default target: latest generated run; `--run` accepts
  in_progress or completed unpublished runs (re-validation idempotent), refuses failed/published.
- **Scanner mechanism (recon-adjudicated Option A):** `packages/shared` gained a `generate`
  script emitting gitignored `packages/shared/generated/forbidden-fields.json` (stems + value
  patterns as `{source, flags}`) from the TS constants — the taxonomy-artifact pattern; root
  `pnpm generate` and CI's existing pre-pytest `pnpm generate` step emit it with no workflow
  change. `pipeline/forbidden_scan.py` ports the ~30-line scan walk and loads the artifact
  (walk-up loader, `pnpm generate` hint; empty stems or unportable regex flags are hard load
  failures). Term parity is structural — no hand-copied Python list exists; the TS suite's
  poisoned fixtures are ported and run against the loaded artifact.
- **Files touched:** `packages/shared/src/generate.ts` (new), `packages/shared/package.json`
  (generate script; `tsx` + `@types/node` devDeps), `packages/shared/tsconfig.json`
  (`"types": ["node"]`, the taxonomy pairing) and `packages/shared/tsconfig.build.json`
  (excludes `src/generate.ts` — a build-time script, never dist runtime surface), `.gitignore`
  (`packages/shared/generated/`), `pnpm-lock.yaml`, `services/pipeline/src/pipeline/
  forbidden_scan.py` (new), `services/pipeline/src/pipeline/aggregates/validate.py` (new),
  `services/pipeline/src/pipeline/cli.py` (subcommand + CI refusal + DATABASE_URL boundary),
  `services/pipeline/tests/test_forbidden_scan.py` (new),
  `services/pipeline/tests/test_aggregates_validate.py` (new).
- **Failed-run interaction with SD-4 (planning-required confirmation):** a fresh
  `generate-aggregates` always INSERTs a NEW run row (`_create_run`), and every
  delete-and-reinsert targets only that new run's id — a failed run's row and aggregate rows
  are never reused, touched, or blocking. Failed runs are terminal history.
- **Console hygiene:** validation output is hash-prefix run id, per-table `rows_checked` /
  violation counts, and fixed check codes only; a privacy violation's offending value is never
  printed or logged (DB-test-asserted).
- **Deviations from plan:** `@types/node` devDep added alongside `tsx` in `packages/shared`
  (needed for the generate script's `node:fs` imports; same pairing taxonomy carries), plus the
  two `packages/shared` tsconfig touches above — the shared `build` gate otherwise failed on
  the new script's node globals. Both are trivially-necessary companions to the approved
  `generate.ts`; no other plan deviation.
- **Notes for 28.2:** publish must target a `completed` unpublished run (the CHECK already
  enforces it); validate-then-publish is two explicit steps. Re-validating a published run is
  refused here, so 28.2's invalidate path stays the only mutation of published history.

## Task 28.2 — Publish Swap + Coverage/Methodology Refresh + Exit Demo Prep — 2026-07-13

- **What was built:** `pipeline publish-aggregates` (NEW code — R1 recon found no
  reusable Sprint 2 publish/invalidate path to reuse; adjudicated in planning chat):
  one transaction sets `published_at` on a validated run and
  `invalidated_at`+`invalidated_reason` on the prior active published run
  (invalidate-before-publish ordering under the §6.3 partial unique index; prior run
  retained, never deleted). Idempotent explicit re-run; stale-guard on the bare form
  (below). Plus the real-run copy refresh: seeded-data disclosure removed from BOTH
  API spots (their "Sprint 7" marker condition — real aggregates replacing seeds —
  was met by this publish; leaving it would have made the API assert a falsehood),
  methodology updated for the cutdown MVP (SD-15 sentencing-date disclosure,
  judge-thinness honesty, ambiguous-excluded-structurally, no-manual-correction
  phrased without the route-forbidden internal vocabulary), data-coverage
  known-limitations refreshed (collection ongoing; MC coverage currently extends
  further than CP, stated qualitatively — no calendar dates or counts in copy).
- **Files touched (committed):** `services/pipeline/src/pipeline/aggregates/publish.py`
  (new), `services/pipeline/src/pipeline/cli.py`,
  `services/pipeline/tests/test_aggregates_publish.py` (new, 10 tests),
  `apps/api/src/content/methodology.ts`, `apps/api/src/content/data-coverage.ts`,
  `apps/api/src/routes/public/data-coverage.test.ts` (disclosure assertion inverted
  to assert ABSENCE), `agent-docs/decisions/0003-admin-review-post-deadline.md`
  (new — AC10), `tasks/worklog.md`. No API route/service/repository, web, schema,
  or parser change. `tasks/current-task.md` carries a human edit — NOT staged.
- **Adjudications executed (planning chat):** (1) publish is new code mirroring
  validate.py; (2) data-coverage contract FROZEN — eligible/excluded fact counts live
  in run reports/worklog/exit demo, never the endpoint; (3) disclosure removal NOW,
  both spots + markers; (4) intake race handled by snapshot (mtime >2 min guard), no
  collector pause; (5) step-6 judge verification prefers a real judge-specific result.
- **Intake (COL protocol, snapshot `28.2-20260713T180107Z`):** staged-at-freeze 5,082
  (mtime-guarded; 5,088 in dir at freeze instant); [0b] excluded 3,208 already-loaded
  docket numbers (hash dedupe alone would have missed re-collected copies); included
  1,874. Stages verbatim in run reports: import `imported=1874 duplicate=0 invalid=0
  failed=0`; extract `success=1874 partial=0 needs_ocr_or_review=0 failed=0`; parse
  `parsed=1871 failed=3 skipped=0` (all 3 UNSUPPORTED_FORMAT — isolated expected
  quarantine class, 0.16%, no systematic cluster; loaded as `parse_failed`, zero
  parsed rows, zero facts structurally); tier-2 `--init-goldens` totals `new=1871
  diverged=0 failed=3 golden_missing=0` (this entry is the mandatory golden-write
  note; verification rerun `match=1871 diverged=0`); load `loaded=1871
  failed_envelope_loaded=3 total=1874`.
- **Corpus counts formally restated (supersedes 4,769 by name):** loaded dockets
  **4,769 (1,563 CP + 3,206 MC) → 6,640 (2,931 CP + 3,709 MC)**;
  `raw.source_documents` 6,643 (6,640 imported + 3 parse_failed); `parsed.charges`
  13,334 → 19,156; `parsed.sentences` 4,733 → 7,340; duplicate docket numbers = 0.
  Capstone baseline untouched; comparator not run over new dockets (SD 14).
- **Fact build (rerun `8ded6328-b1d5-45`, status=completed):** `charges_processed=19156
  facts_written=15568 held_skipped=3588`, reconcile True; outcome eligibility
  `mvp=3410 public=2721 judge=2631 review=9793`; `sentence_facts_written=7340
  components_on_disposed=7340`, reconcile True; sentence eligibility `mvp=3671
  public=2839 judge=2762`; SD-15 divergence=34 straddle_mvp=29 delta_days=218..757.
  Gates all PASS scoped to the run: held-with-outcome-fact=0; sentinel-collision
  conservative behavior holds (56/56 facts on sentinel dockets have
  `judge_attribution_method='none'`, judge NULL — superset of 24.1's 12);
  review dedup holds (`newly_inserted=0` on this rerun); duplicate dockets 0.
  NOTE: an identical build (`3a29d048`) ran minutes earlier but its console report
  was only partially captured; it was rerun with full capture — append-only run
  partitions make this history, not a deviation of substance. Its rerun inserting 0
  new review items is itself the dedupe proof.
- **Aggregates:** generate run `84faecfc` then (post-incident, identical inputs)
  `286b0058` over build run `8ded6328`: `facts_loaded=15568 facts_included=2721
  facts_excluded=12847`; `charges_with_aggregates=76 outcome_aggregates_generated=247`
  `thin_data_charges=28`; `charges_with_sentencing=71 sentencing_aggregates=196
  thin=25`; `judge_outcome_aggregates=1179 pairs=885 thin_pairs=839`;
  `judge_sentencing_aggregates=1129 pairs=762 thin=702`; sentence facts included
  2,839 / excluded 4,501; `data_range: 2025-01-01..2026-07-10`. validate-aggregates:
  all four tables 0 violations, `run marked completed (validated)` (both runs).
- **PUBLISH INCIDENT (disclosed, fixed, regression-tested):** after publishing
  `84faecfc`, a bare `publish-aggregates` re-run (intended as the idempotency check)
  default-resolved to the LEFTOVER validated-unpublished 28.1-era run `65f4c65f` and
  published it, superseding the newer real run — the bare form was NOT idempotent
  when an older validated run lay around. Fix in the same task: default resolution
  now refuses a candidate validated BEFORE the active published run
  (`StaleValidatedRunError`, exit 2); explicit `--run` remains the operator override.
  Regression test `test_db_bare_rerun_never_publishes_a_stale_leftover_run`
  reproduces the incident. DB recovered via sanctioned commands only (fresh
  generate `286b0058` → validate → publish `--run`); no manual SQL, no history
  mutation. Final state: active run `286b0058`; `65f4c65f` and `84faecfc`
  invalidated history with accurate reasons; seeded run `5eedda7a-…0001` invalidated,
  retained (34 outcome rows intact) as rollback target.
- **Post-publish verification (zero API/UI code change):** charge search,
  charge-only result (sample 230, run id `286b0058…`), judge-specific result (a
  SOLID pair, n=56, thin=false, beside its baseline) and data-coverage (real counts
  76/71/885, dataEnd from the run, seeded disclosure GONE) all serve the published
  real run. Bare publish re-run now STOPs (`NoValidatedRunError` — nothing
  validated-unpublished left); explicit re-run is a no-op.
- **Local test environments (operational note for all future tasks):** after this
  swap, `pnpm --filter @pca/api test` must NEVER run against the real `pca` DB — the
  vitest global setup re-seeds and re-activates the seed run, which now collides
  with the real active run. Export `DATABASE_URL` pointing at `pca_test`
  (shell-exported vars beat the auto-loaded root `.env`). Pipeline DB tests use
  `PIPELINE_TEST_DATABASE_URL` → `pca_pipeline_test` as before.
- **Deviations from plan:** the stale-guard addition to publish.py (forced by the
  incident — required to actually meet the approved "idempotent / safe to re-run"
  AC) and the duplicate fact-build run for report capture. Both disclosed above;
  no other deviation. Numbers discipline held: superseded figures (730/432) appear
  nowhere; no count pinned in code, tests, or copy.
- **Notes for Sprint 7:** seed sweep may now DELETE the invalidated seeded run
  (this task only invalidated it). 'Held for Court' MC disposition mapping still
  banked. The two invalidated real runs (`84faecfc`, `65f4c65f`) are ordinary
  history — the sweep should target only seed-id runs.

## Task COL-3 — Court-Scoped Window Ledger + Concurrent MC/CP Collection (2026-07-13)

- **What was built:** the search-mode window ledger is now court-scoped
  (`window-ledger-philadelphia-<court>.jsonl`, one per FETCHED court), matching
  the enumeration-mode belt-and-braces: court in the filename AND a `court`
  field in every entry, validated on load (misdirected-ledger guard). A window
  is skipped only when EVERY fetched court completed it, so an MC completion
  can never suppress a CP search and vice versa. Completion is monotonic and
  order-independent across duplicate (date, court) entries: any
  `complete`/`empty` entry wins; a later `blocked`/`truncated` never revokes
  it; duplicates never error, warn, or distort (a `both` run re-searching a
  window only one court completed appends an expected duplicate). Concurrent
  MC+CP collection is the approved single interleaved process: `--court both`
  (already wired) is now correct under scoped ledgers — one search serves both
  courts' rows (strictly less portal load than two passes), one clock, one
  RunGuard, one cooldown, so the counsel caps / 300s post-block cooldown /
  block-streak stop are aggregate across courts by construction (tests prove
  streak does not reset on court switch, cooldown idles the whole run, one
  240-min budget). Live output labels courts distinctly: per-window and
  progress log lines now carry per-court fetched/already_present/
  fetch_failures (+ cumulative by_court on progress); counts only.
- **Files touched:** `services/pipeline/src/pipeline/collector/window.py`,
  `search_engine.py`, `run.py`, `src/pipeline/cli.py`;
  tests `test_collector_window_ledger.py`, `test_collector_search_engine.py`,
  `test_collector_search_cli.py`; this worklog. `engine.py` untouched
  (read-only model).
- **MIGRATION EXECUTED (one-time, idempotent, archived):**
  `pipeline migrate-window-ledger` over `~/court-data/coverage/` +
  `~/court-data/collection-runs/`: **215 shared-ledger entries → MC=122
  entries (121 dates), CP=93 entries (91 dates)**; shared file retired by
  rename to `window-ledger-philadelphia.jsonl.migrated-col3` (never deleted).
  Immediate re-run: `nothing to migrate`, exit 0, files unchanged.
  Attribution basis per run-id group (auditable): report-based — MC runs
  run-20260712-005852 (37), -025810 (7), -044124 (1), -072248 (22),
  -164622 (11), -235541 (20); CP runs run-20260713-030509 (27), -060332 (3),
  -170548 (29). Activity-inferred (no run-report.json; run died before
  writing one; fetch activity exclusively on one court) — MC:
  run-20260712-042549 (1), -044430 (13), -182732 (10); CP:
  run-20260713-124600 (34). The 93 CP entries are genuine workaround-era CP
  completions (written under `--recheck-windows`) — preserved and attributed
  to the CP-scoped ledger per pinned decision 6: CP starts CORRECT, not empty.
  No ambiguous attribution; the STOP condition never triggered.
- **`--recheck-windows` WORKAROUND RETIRED:** the flag remains as a
  diagnostic, but CP collection no longer needs it. Post-migration
  verification (raw output in the completion report): MC run over
  2025-01-01..03 skipped all 3 windows (`skipped_complete=3`, 0 searches, 0
  portal requests); CP run over MC-only-complete 2025-04-05 WITHOUT the flag
  searched it live (`searched=1, skipped_complete=0`, honest CP `complete`
  entry with 0 CP rows). Both smokes headful under the approved 1-2
  window / `--max-fetches 1` shape, counted against session budget.
- **Deviations from plan:** none.
- **For COL-4 / next tasks:** search-mode ledger loads REQUIRE the `court`
  field — pre-COL-3-format entries (no court) are skipped with a WARNING, so
  never hand-write ledger entries without it. The run report's
  `parameters.window_ledger_path` (string) is now `window_ledger_paths`
  (dict court→path); anything parsing old reports should tolerate both.
  Combined collection is `--court both` — do not run two per-court sessions.
  `~/court-data/coverage-smoke-col2/` still holds an old-format smoke ledger
  (untouched, unused by production runs).

## Task COL-4a — Docket Supersession in the Loader + prune-fact-runs (2026-07-13)

- **What was built:** the loader supersession arm — same `(docket_number,
  court_type_derived)` under a NEW source hash transactionally replaces the old
  parsed graph (delete + reinsert, one per-docket transaction), keeps the old
  `raw.source_documents` row as provenance with `status='parse_superseded'`
  (plan-approved status-value mechanism; NO migration), and closes out the old
  document's non-terminal review items (`open`/`in_review` →
  terminal `superseded`; `resolved`/`dismissed` untouched — triage state never
  transfers). Regression guard (flags, never blocks): charge-count shrink or
  disposition loss emits a hash-prefix warning + ONE `supersession_regression`
  review item (severity high, reason `review_needed`, anchored to the NEW source
  document, subcases in structural `candidate_context`). Plus the R3-adjudicated
  `pipeline prune-fact-runs` command: whole-run deletion of fact build runs
  (run row + facts via the gate-verified build_run_id CASCADE), explicit ids or
  `--all-completed`, dry-run by default with `--confirm` to execute, completed-
  only, one transaction per invocation, idempotent on absent ids, CI-refusing.
- **Files touched:** `services/pipeline/src/pipeline/load.py` (supersession +
  stale-skip arms, guard, AC-14 pre-check, two new report categories);
  `services/pipeline/src/pipeline/fact_review_vocab.py` (plan-approved
  `supersession_regression` item type + `superseded` status);
  `services/pipeline/src/pipeline/prune_fact_runs.py` (new);
  `services/pipeline/src/pipeline/cli.py` (prune-fact-runs wiring);
  `services/pipeline/tests/test_load.py`, `tests/test_prune_fact_runs.py` (new),
  `tests/test_fact_review_vocab.py` (closed-set pins extended for the two
  approved vocabulary additions — necessary companion touch, called out in the
  completion report); `tasks/worklog.md`.
- **Deviations from the approved plan (both surfaced + approved mid-task):**
  (1) THE PING-PONG FINDING: envelope artifacts accumulate one file per source
  hash, so after a supersession a full-dir re-load sees BOTH the losing and the
  winning envelope; without a guard they would supersede each other back and
  forth on every re-load (the loser's hash lookup misses — its parsed row is
  gone — so it falls into the new-hash/supersession path). Fix (approved): the
  stale-skip arm — an incoming envelope whose OWN raw row is already
  `parse_superseded` is skipped with zero writes (`skipped_stale_superseded`,
  healthy, ninth report category). COL-4b's refresh runbook DEPENDS on this:
  full-dir re-load is now proven safe (tier-1 test + the no-op invariant).
  (2) `_insert_parsed_graph` now returns the new docket id (the guard's review
  item needs it); uuid→str conversion at the review-item builder boundary.
- **R1 outcome (proven by test):** review.queue_items parsed FKs are SET NULL,
  anchor is the raw doc (RESTRICT, kept) — no crash at supersession; close-out
  semantics as above. Dedup keys incorporate `source_document_id`, so the next
  fact build regenerates the new document's items FRESH (open) under new keys;
  old items keep their history under the superseded doc.
- **R3 adjudication executed:** RESTRICT FKs stay; supersession pre-checks
  `fact.charge_outcomes` and rejects per-docket with reason
  `supersession_blocked_by_fact_rows`, warning names `pipeline prune-fact-runs`
  (AC-14). LATENT + BY DESIGN: the pre-existing `replaced_newer_version` arm
  does the same delete UNGUARDED and fails loudly on the raw FK violation if
  facts reference the graph — NOT separately fixed (adjudicated); prune-first
  ordering is the remedy for it too (code comment at the arm).
- **Acceptance runs (real corpus, verbatim in the completion report):** full
  canonical re-load of all three envelope dirs = no-op
  (`skipped_same_version=1603/3166/1871`, `failed_envelope_loaded=3` known
  failed-parse envelopes, everything else 0, exit 0 each; DB counts bit-identical
  to pre-task recon: 6,640 dockets / 19,156 charges / 13,624 review items /
  61,283 fact outcomes / 0 superseded docs). NO re-fetched specimen exists
  (envelope scan: 6,640 distinct dockets, 0 with multiple hashes), so per the
  approved AC-9 fallback the supersession proof is the tier-1 synthetic suite
  and the REAL-DATA supersession proof moves to COL-4b's first refresh run.
- **For COL-4b:** refresh ordering is prune → refresh → load → rebuild →
  aggregate → publish; `prune-fact-runs --all-completed --confirm` is the
  pre-refresh step (worklog each prune per the adjudication); the load step is
  now safe over the full envelopes dir (stale-skip); expect `superseded` +
  `skipped_stale_superseded` categories in refresh load reports; supersession
  keys on `(docket_number, court_type_derived)` and NEVER fires for failed-parse
  envelopes (they return in the failed arm before it).
- **Transcription incident (report reconciliation, post-completion):** the
  completion report's third acceptance-run block was RETYPED instead of pasted
  and corrupted in transcription (`skipped_stale_superseded` 3-for-0; categories
  summed 1877 ≠ total=1874). The loader's actual output was correct — its
  printed total is `sum()` over the same counts dict as the categories, so a
  non-reconciling line is unproducible by the code and always a transcription
  artifact. Adjudicated: dir re-run (idempotent), fresh line pasted verbatim
  (`skipped_same_version=1871 failed_envelope_loaded=3 total=1874`, all else 0,
  exit 0), DB counts unchanged (6,640 / 13,624 / 0 superseded). The CLAUDE.md
  verbatim rule is HARDENED in this same commit: acceptance-run lines must be
  copy-pasted from tool output, never retyped, and runs that write a report
  file under ~/court-data/ are referenced by filename alongside the pasted
  line.

## Task COL-4b — Pending-Docket Refresh Mode (2026-07-13)

- **What was built:** refresh collection mode (`pipeline collect --mode refresh`)
  — a third collector mode that re-fetches exactly the loaded corpus's
  non-terminal dockets. `collector/refresh_targets.py` derives the target list
  from the DB (charge-level predicate: any docket with a held charge,
  `parsed.charges.disposition_raw IS NULL`, joined to its current
  `raw.source_documents.file_hash`; deliberately NOT the NON_TERMINAL_CASE
  warning, which misses partially disposed dockets). `collector/refresh_engine.py`
  is the pure injected-dependency loop: fetches via the court-agnostic
  enumeration transport (CP and MC identically), reuses every counsel-locked
  constant (240-min ceiling, 300s post-block cooldown, jitter band, batch
  floor, RunGuard streaks, fail-closed classify), skips targets already in the
  cycle's refresh dir (`already_fetched`, streak-neutral), sha256-classifies
  every hit unchanged/changed/new against the loaded hash (PDF written in all
  hit cases), counts a positively-identified no-results on a loaded docket as
  a `failed` anomaly (`no_results_anomalies`) and NEVER writes window- or
  miss-ledger entries. Report carries target counts (count-only), all buckets,
  and two audit identities (attempted == attempt-log entries; fetched ==
  unchanged+changed+new). CLI: `--mode refresh`, new `--refresh-dir` (required),
  `--court` REQUIRED EXPLICITLY in refresh mode (argv-presence check — the
  parse-level MC default is unchanged for enumerate/search), DATABASE_URL read
  at the run boundary for refresh only; the DB connection closes before the
  browser session starts. Docs: `agent-docs/intake/refresh-runbook.md` (the
  prune → refresh → intake/load → build-facts → aggregate → publish cycle,
  pinned decision 7 confirmed: generate+validate+publish required
  same-session), a two-line [0b] exemption pointer in
  `agent-docs/intake/col-intake-protocol.md` (Chops-approved), and
  `agent-docs/collector-commands.md` (Chops-requested command/flag reference).
- **Files touched:** `services/pipeline/src/pipeline/collector/refresh_targets.py`
  (new), `collector/refresh_engine.py` (new), `collector/run.py`
  (run_collect_refresh), `cli.py` (mode/flags/validation/dispatch);
  `services/pipeline/tests/test_collector_refresh_targets.py` (new,
  Postgres-backed via PIPELINE_TEST_DATABASE_URL guards),
  `test_collector_refresh_engine.py` (new), `test_collector_refresh_cli.py`
  (new, incl. AC-11 pins that enumerate/search never touch refresh machinery
  or the DB layer); `agent-docs/intake/refresh-runbook.md` (new),
  `agent-docs/intake/col-intake-protocol.md` ([0b] pointer),
  `agent-docs/collector-commands.md` (new); `tasks/worklog.md`. No existing
  test file edited (AC-11). No loader/enumeration/window-ledger changes.
- **Deviations from the approved plan:** none in code. Sequencing directed by
  Chops in-task: (1) newly collected CP dockets were intaken FIRST via the
  standard protocol so refresh derivation would include them; (2) the refresh
  FETCH is deferred — Chops runs it personally; the refresh cycle restarts
  from runbook step 0 at that time; (3) because the fetch was deferred after
  the prune, an interim build-facts + generate + validate + publish ran on the
  grown corpus so the fact layer does not sit empty. **AC-7 (first refresh
  end-to-end, incl. the deferred COL-4a real-data supersession proof) and
  AC-8 (post-cycle restatement) carry to the future fetch.**
- **CP intake (standard protocol; snapshot `COL-4b-20260713T232717Z`, manifest
  beside it):** staged_at_freeze=5571, excluded_already_loaded=5080,
  included=491 (all CP; includes the 3 known parse_failed re-flows —
  hash-verified identical to the quarantine trio). Pipeline lines (verbatim):
  `imported=488 duplicate=3 invalid=0 failed=0`;
  `success=491 partial=0 needs_ocr_or_review=0 failed=0`;
  `parsed=488 failed=3 skipped=0`;
  goldens `tier2: match=0 diverged=0 updated=0 new=488 golden_missing=0
  failed=3` (report `tier2-report-20260713T233528_780560Z.json`; failures are
  the known parse_failed trio, matching the 28.2 precedent report exactly).
  **GOLDEN WRITE NOTE (required per protocol): `run-fixtures --init-goldens`
  wrote 488 absent tier-2 goldens for the new CP dockets; zero existing
  goldens touched; zero drift.** Load (exit 0, verbatim):
  `loaded=488 skipped_same_version=0 replaced_newer_version=0
  refused_older_version=0 superseded=0 skipped_stale_superseded=0
  failed_envelope_loaded=3 failed_exception=0 missing_import_record=0
  total=491`. Corpus: 6,640 → 7,128 dockets (+488 CP; 3,709 MC / 3,419 CP),
  charges 19,156 → 20,935, held charges 3,588 → 4,303. Zero duplicate docket
  numbers. No build-facts after this load (Chops-directed; covered by the
  interim rebuild below).
- **Refresh step-0 recon (post-intake):** refresh targets 1,118
  (686 MC / 432 CP) — supersedes the plan-time 1,012; point-in-time record
  only (window collection continues; derivation reruns fresh at fetch time).
  parse_failed=3 (out of refresh scope by design), parse_superseded=0.
- **PRUNE NOTE (step 1, worklogged per the COL-4a adjudication):**
  `prune-fact-runs --all-completed` dry run (verbatim):
  `would_prune=9 not_found=0 outcomes_deleted=0 sentences_deleted=0
  outcomes_selected=61283 sentences_selected=40223`; then `--confirm`
  (verbatim): `pruned=9 not_found=0 outcomes_deleted=61283
  sentences_deleted=40223 outcomes_selected=61283 sentences_selected=40223`.
  Published aggregate rows for run 286b0058… verified intact post-prune
  (247/196/1179/1129 rows). The pre-prune 61,283 was the SUM of nine retained
  run partitions, not one run's facts.
- **Interim rebuild + publish (Chops-directed after the fetch deferral):**
  build-facts run `b873298d-4faa-4d6c-8192-807aa91101b0` completed —
  facts_written=16,632, held_skipped=4,303, charges_processed=20,935
  (reconciles: 16,632+4,303==20,935, independently re-verified against
  parsed.charges); sentence_facts_written=8,230 == components_on_disposed;
  review items generated_total=14,094, newly_inserted_total=470 (dedup held —
  new items only for new dockets). generate-aggregates run
  `c82d8be2-48cf-4280-9b11-33a7d268008f` from build_run b873298d… (default):
  facts_loaded=16632 facts_included=3426; 261 outcome / 206 sentencing / 1354
  judge-outcome / 1276 judge-sentencing aggregates; data_range
  2025-01-01..2026-07-10. validate-aggregates: verdict=validated, violations=0
  on all four tables. publish-aggregates: run c82d8be2… published, prior
  286b0058… invalidated (superseded); exactly one active published run
  verified post-swap, serving 261 outcome-aggregate rows.
- **For the deferred refresh cycle (whenever Chops runs the fetch):** restart
  at runbook step 0 — fresh recon AND fresh target derivation (counts above
  will be stale), prune again per runbook, then Chops fetches into a fresh
  dated `--refresh-dir`; resume at step 3 (import). The 3 parse_failed sheets
  keep re-flowing through any intake that includes them (idempotent,
  expected). The first refresh's load step carries the deferred COL-4a
  real-data supersession proof; if zero sheets changed, state it and carry
  forward per AC-7.

## Operational intake — April 2025 window collection (2026-07-14)

Standard COL Intake Protocol run over the collector drop zone after window
collection reached 2025-05-01 (MC) / late April (CP). No code changes; all
artifacts under `~/court-data/`. Counts only below; all pipeline lines pasted
verbatim from tool output.

- **Step-0 recon (pre-intake baseline):** parsed.dockets=7,128
  (3,419 CP / 3,709 MC), parsed.charges=20,935, held=4,303,
  duplicate docket numbers=0; fact run `b873298d…` (16,632 outcomes);
  published aggregate run `c82d8be2…`.
- **[0] Freeze + [0b] exclusion (snapshot
  `apr2025-window-intake-20260714T032507Z`, manifest beside it):**
  `staged_at_freeze=6202`, `mtime_guard_dropped=0`,
  `excluded_already_loaded=5569`, `included=633` (618 CP / 15 MC; includes
  the 3 known parse_failed re-flows).
- **Import (verbatim):** `imported=630 duplicate=3 invalid=0 failed=0`
  (duplicates = the byte-identical parse_failed trio, as in prior intakes).
- **Extract (verbatim):** `success=633 partial=0 needs_ocr_or_review=0 failed=0`
  (dir `extracted-intake-apr2025-20260714/`).
- **Parse (verbatim):** `parsed=630 failed=3 skipped=0`
  (dir `envelopes-intake-apr2025-20260714/`; failures are the known trio).
- **GOLDEN WRITE NOTE (required per protocol):** `run-fixtures --init-goldens`
  wrote 630 absent tier-2 goldens for the new dockets; zero existing goldens
  touched; zero drift. Report `tier2-report-20260714T033225_272264Z.json`
  totals: `match=0 diverged=0 updated=0 new=630 golden_missing=0 failed=3`.
- **Load (exit 0, verbatim):** `loaded=630 skipped_same_version=0
  replaced_newer_version=0 refused_older_version=0 superseded=0
  skipped_stale_superseded=0 failed_envelope_loaded=3 failed_exception=0
  missing_import_record=0 total=633`. Reconciles with import/parse
  (630 + 3 == 633).
- **Corpus:** 7,128 → 7,758 dockets (+615 CP → 4,034; +15 MC → 3,724),
  charges 20,935 → 22,865, held 4,303 → 4,896. Zero duplicate docket numbers.
- **INCIDENT (operator, self-caused, remediated): build-facts ran twice.**
  The second invocation was issued only to re-display summary lines; each
  invocation writes a fresh run, so two identical partitions existed
  (`6204741e…` then `7e26b002…`, both completed, 17,969 outcomes / 9,240
  sentence facts each — deterministic over the same corpus). Review-item
  dedup held across the pair: first run `newly_inserted=712`, second run
  `generated_total=14806` / `newly_inserted_total=0`. Remediation: the
  redundant FIRST run was pruned with the sanctioned tool. Dry run
  (verbatim): `would_prune=1 not_found=0 outcomes_deleted=0
  sentences_deleted=0 outcomes_selected=17969 sentences_selected=9240`;
  confirm (verbatim): `pruned=1 not_found=0 outcomes_deleted=17969
  sentences_deleted=9240 outcomes_selected=17969 sentences_selected=9240`.
  Post-prune: 2 runs remain (`b873298d…` + `7e26b002…`), 34,601 outcomes
  total. Lesson recorded: never re-run a state-writing pipeline command to
  re-show its output; read the run row's `counts` jsonb instead.
- **Fact build (kept run `7e26b002-cb66-4712-bae2-361c7bc1466c`), counts from
  the run row:** `facts_written=17969 held_skipped=4896
  charges_processed=22865 reconciles=true` (17,969 + 4,896 == 22,865 ==
  parsed.charges, independently verified). Console (verbatim):
  `sentence_facts_written=9240 components_on_disposed=9240` and
  `reconcile sentence_facts==components_on_disposed: True`.
- **Aggregates:** generate-aggregates run
  `6ecf1fed-0b73-4cb8-bf50-2d8d213f1fa7` from build run `7e26b002…`
  (default=latest); console tail (verbatim): `data_range:
  2025-01-01..2026-07-13`. validate-aggregates (verbatim):
  `verdict=validated`; `charge_outcome_aggregates: rows_checked=274
  violations=0`; `charge_sentencing_aggregates: rows_checked=213
  violations=0`; `judge_outcome_aggregates: rows_checked=1510 violations=0`;
  `judge_sentencing_aggregates: rows_checked=1424 violations=0`.
  publish-aggregates (verbatim): `publish-aggregates run=6ecf1fed-0b73-4c
  published` / `prior published run c82d8be2-48cf-42 invalidated
  (superseded)`. Exactly one active published run verified post-swap.
- **Post-publish spot check:** public charge-results endpoint serves
  `aggregateRunId=6ecf1fed-0b73-4cb8-bf50-2d8d213f1fa7`,
  `lastRefreshed=2026-07-14T03:38:13.293Z`, dateRange end `2026-07-13`
  (sample: retail-theft outcomes sampleSize=145).
- **For the next cycle:** the 3 parse_failed sheets re-flowed idempotently
  again (expected; remedy remains parser work). The deferred COL-4b refresh
  cycle (AC-7/AC-8) is unaffected; held-charge count for fresh refresh
  derivation is now 4,896 at this build.

## Task 29.1 — Seed Sweep (2026-07-14)

**What was built.** Registry-driven sweep tooling for the live database:
`db/scripts/sweep-seed-rows.ts` (core: interlocks + deletes + report, one
transaction) and `db/scripts/sweep-seed-rows-cli.ts` (CLI: CI refusal before
any connection, mandatory explicit `--database <name>` matched against
`current_database()`, dry-run default with `--confirm` to execute). Targets
are imported from the `db/seeds/` registry — `JUDGE_SEEDS` slugs and both
run UUID constants (`SEED_PUBLISHED_RUN_ID`, `SEED_UNPUBLISHED_RUN_ID`) —
never name patterns. Per plan review D1 the unpublished decoy run is swept
along with the invalidated seeded published run. Demo charges and their
aliases are retained (no statement touches them); fake-judge aliases are
deleted explicitly so the count is reported rather than hidden in the FK
cascade. Dry run executes the same deletes and rolls back via a sentinel, so
would-delete counts are exact. Interlocks (any violation = abort + full
rollback): zero fact.* rows referencing fake judges; no judge-aggregate rows
outside the registry runs referencing fake judges; the seeded published run
must be invalidated; no registry run may be the active published run (F1).

**SD-3 resolution (plan review D2): refuse-via-guard.**
`db/scripts/seed-guard.ts` now runs before `seeds/run.ts` in the `db:seed`
package script and refuses (exit 2) when the target database contains real
corpus data (`raw.source_documents` or `fact.fact_build_runs` nonempty);
unmigrated targets get a run-migrations-first refusal (F2). The seed scripts
in `db/seeds/` are byte-identical — only invocation wiring changed. Without
the guard, `db:seed` against the post-sweep live DB would re-insert the
three fake judges (reference transaction commits first) and then fail on the
active-published unique index.

**Rollback-target surrender (Sprint 7 SD 2, stated per AC 3):** deleting the
invalidated seeded aggregate run `5eedda7a-0000-4000-8000-000000000001`
deliberately surrenders it as a rollback target. Once 29.3 republishes, real
runs are each other's rollback targets under the existing published-run
model.

**Files touched:** `db/scripts/sweep-seed-rows.ts`,
`db/scripts/sweep-seed-rows-cli.ts`, `db/scripts/seed-guard.ts`,
`db/tests/sweep-seed-rows.test.ts`, `db/package.json` (seed guard wiring +
`sweep:seeds` script), `db/tsconfig.json` (add `scripts/` to include),
`agent-docs/seed-sweep-runbook.md`, this worklog.

**Tests.** `db/tests/sweep-seed-rows.test.ts`: CLI CI refusal proven by
spawning the real CLI with `CI=1` and a bogus `DATABASE_URL` (refusal
precedes any connection); `--database` mismatch and missing-arg refusals;
guard verdicts for unmigrated / clean / real-corpus databases; F1 refusal
while the seeded run is still active-published; dry-run exactness;
confirmed-sweep deletion + retention (demo charges/aliases by before/after
snapshot, full judge roster, simulated active run); second-run no-op. The
behavior tests build a scratch database (`pca_sweep_test_<hex>` prefix per
F3c, force-dropped in afterAll) on the connected server, migrated
programmatically and seeded via the imported seed functions; they skip
LOUDLY when `DATABASE_URL` points at the live `pca` database (F3a).

**Deviations from plan:** none in scope. Two test-shape adjustments during
implementation: the simulated publish swap must invalidate the seeded run
BEFORE inserting the new published run (partial unique index allows one
active row), and demo-alias retention is asserted by before/after snapshot
because the 22.2 roster task adds `DEMO_ALIAS_ADDITIONS` to demo charges.

**For the next task (29.2, pinned recon input confirmed at plan review):**
db-package and API vitest configs auto-load the root `.env` — the 28.2
incident class. Separately, a PRE-EXISTING latent flake surfaced (not fixed,
out of scope): `db/seeds/reference.test.ts` asserts ref.* equals exactly the
Sprint-2 demo seeds, but the roster test files seed roster rows into the
same database in parallel vitest workers — on a fresh migrated DB this
machine reproduces the failure while 2-core CI runners win the race and stay
green. It fails against any long-lived DB (`pca_test`, live) regardless.

## Task 29.2 — Test-Database Guard (2026-07-14)

**What was built.** Structural test-dbname guard closing the 28.2 incident
class: both vitest global-setups now assert a test-database name BEFORE any
connection or write. New pure module `db/src/test-db-guard.ts`
(`isTestDbName`, `dbNameFromUrl`, `assertTestDatabaseUrl`), exported via the
new `@pca/db/test-db-guard` subpath (forbidden-scan precedent — off the main
runtime surface; conditional-exports triple in `db/package.json`, emit added
to `db/tsconfig.build.json`). Pattern per plan-review ruling: dbname contains
`test` (case-insensitive, the `PIPELINE_TEST_DATABASE_URL` convention) OR is
exactly `pca_ci`; fail-closed on a missing/unparseable dbname. Refusal
messages name the dbname ONLY — never the URL (credential hygiene, public CI
logs). Wired into `apps/api/vitest.global-setup.ts` ahead of the direct-call
seeding (the vector 29.1 left open) and into a NEW `db/vitest.global-setup.ts`
covering the seed/roster/sweep suites. A throwing globalSetup aborts the whole
run, so per-test writes are blocked at entry. Per-path coverage of every DB
test entry path recorded in `agent-docs/test-db-guard.md` (E2E → 29.1
data-shaped seed-guard; pipeline pytest → pre-existing guard; shared/web/
taxonomy/ui → no DB access).

**Deliberate-failure tests (AC 3).** `db/src/test-db-guard.test.ts` (pure):
live `pca` rejected; `pca_test`/`pca_pipeline_test`/`pca_ci`/
`pca_sweep_test_<hex>` pass; fail-closed cases; message-hygiene assertions
(no credentials/host/URL). `apps/api/vitest.global-setup.test.ts`: invokes
the REAL global-setup with a live-shaped dbname on a closed port — rejected
with the guard message (proving pre-connection blocking); `pca_ci` clears the
guard and proceeds to a connection error (CI-name pass proven locally).

**reference.test.ts race fix (D-A: FOLD IN).** `fileParallelism: false` in
`db/vitest.config.ts`. Mechanism: `seeds/reference.test.ts` asserts `ref.*`
equals exactly the demo seeds while the roster suites insert additional
`ref.*` rows into the SAME database; parallelism was the trigger because
vitest runs test files in separate concurrent workers sharing one database,
so roster inserts could land between the reference suite's seeding and its
exact-equality assertions. Reproduced pre-fix on this machine (fresh migrated
`pca_test`, `pnpm --filter @pca/db test`: 2 failed); post-fix same conditions:
all green. Residual pre-existing property, flagged for planning chat: the
suite remains file-ORDER-dependent on a fresh DB (vitest orders by size on a
cold cache, by prior duration warm; both currently run reference before the
roster suites).

**D-B (decision, not deferral):** no root-`.env` auto-load change, now or
later — the structural guard closes the incident class; a live-pointing root
`.env` now fails loudly at test entry.

**Files touched.** `db/src/test-db-guard.ts`, `db/src/test-db-guard.test.ts`,
`db/vitest.global-setup.ts`, `db/vitest.config.ts`, `db/package.json`,
`db/tsconfig.build.json`, `db/tsconfig.json` (include the new global-setup),
`apps/api/vitest.global-setup.ts`, `apps/api/vitest.global-setup.test.ts`,
`agent-docs/test-db-guard.md`, this worklog.

**Deviations from plan:** none in mechanism. Two trivially-necessary config
touches beyond the plan's file list, called out per CLAUDE.md:
`db/tsconfig.build.json` (emit the subpath module — part of the §6.6
exports-triple mechanics) and `db/tsconfig.json` (typecheck the new
global-setup, matching how `vitest.config.ts` is already listed).

**For the next task:** local test runs need a shell-exported test-DB URL
(root `.env` points at live `pca` and now fails loudly); `pca_test` on the
Docker Postgres (port 5433) is the working local target. CI is unaffected
(`pca_ci` passes by allowlist; E2E seeds through the 29.1-guarded
`pnpm db:seed`). Phase-close CI run confirms both 29.1 and 29.2 per D-C.

## Task 29.3 — "Held for Court" Fix, Phase A: code + tests + fixture (2026-07-14)

**What was built (Mechanism A, planning-chat pinned).** The five corpus-
evidenced held-for-court forms are now a non-terminal carve-out in the 22.4
outcome mapper: new byte-exact `HELD_FOR_COURT_DISPOSITIONS` frozenset in
`outcome_mapper.py` ("Held for Court", "IGJ - Held for Court", "HP - Held for
Court", "Held for Court IC", "GJ - Held for Court"); `OutcomeMapper.map()`
returns `None` for members exactly as for NULL (no fact, no review item); the
`"Held for Court": "other"` row is REMOVED from `DISPOSITION_OUTCOME_MAP`
("other" retains Transferred to Another Jurisdiction + Mistrial - Hung Jury).
No taxonomy change (1.0.0), no new eligibility reason codes, no parser or
envelope change (`charge_has_terminal_disposition` untouched). Fail-safe for
unseen future variants is documented at the carve-out site: an unlisted held
form arrives unmapped -> `unknown` (non-public) + `unmapped_disposition`
review item.

**Skip accounting (decision 6; F1 ruling).** The former single `held_skipped`
counter is RENAMED and split: `undisposed_skipped` (null disposition) +
`held_for_court_skipped` (bind-over forms). OLD->NEW key mapping for readers
of historical run reports: `held_skipped` -> `undisposed_skipped`; the
held-form population was previously invisible (counted inside
`facts_written`). Reconciliation identity extended and asserted:
`facts_written + undisposed_skipped + held_for_court_skipped ==
charges_processed`. F1 contingency grep found no code consumers of the old
key outside `build_facts.py` and its test (both updated here) plus the
`refresh_targets.py` docstring (amended per ruling R-a — comment-only; the
null-keyed refresh predicate is untouched and stays correct).

**Closure tooling (AC 10; separability proven in the approved plan).** New
`close_held_review_items.py` + `pipeline close-held-review-items` CLI (CI
refusal + DATABASE_URL boundary per the prune precedent). Key-scoped, never
ILIKE: candidate dedup keys are reconstructed via the canonical 22.1
`build_dedup_key` from current held-form charges — the form set is IMPORTED
from the mapper (F2: single authority, never re-listed). Scope: item types
`unmapped_disposition` + `unmapped_charge`, status `open` only;
`missing_disposition_date` is out of scope by construction (item_type is a
key segment). Closes as `superseded` (COL-4a precedent); dry-run default;
idempotent (post-confirm re-run selects zero).

**AC-3 decomposition (ruling R-c, stated explicitly).** The tier-1 fixture +
golden lock the PARSE-layer capture shape (parse behavior is intentionally
unchanged); the FACT-layer proof lives in the tests: `test_outcome_mapper.py`
locks all five forms -> `None` with no review item (the pinned
no-builder-guard regression lock, plus map-disjointness and the unlisted-
variant fail-safe test), and `test_facts_build_facts.py` seeds a held-form
charge (seq 8) beside terminal siblings and proves no fact for the held form,
siblings still facting, both counters, and the extended identity. New fixture
`held_for_court_disposed_mc.txt` (disposed MC bind-over under a Final
Disposition event, no date line, cross-court reference, terminal sibling) +
`fixture-index.yaml` entry; golden written via `pipeline run-fixtures
--update-goldens` (this note is the required golden-writing record):
`tier1: match=34 diverged=0 updated=0 new=1 missing=0`. Also added
`test_held_form_charge_sentence_is_stop`: a sentence on a held-form charge is
a structural in-transaction STOP (no parent fact) — live corpus carries zero
such sentences (recon).

**Files touched.** `services/pipeline/src/pipeline/normalization/
outcome_mapper.py`, `services/pipeline/src/pipeline/facts/build_facts.py`,
`services/pipeline/src/pipeline/close_held_review_items.py` (new),
`services/pipeline/src/pipeline/cli.py`, `services/pipeline/src/pipeline/
collector/refresh_targets.py` (docstring only, R-a),
`services/pipeline/tests/test_outcome_mapper.py`,
`services/pipeline/tests/test_facts_build_facts.py`,
`services/pipeline/tests/test_close_held_review_items.py` (new),
`services/pipeline/tests/tier1/fixtures/held_for_court_disposed_mc.txt`
(new), `services/pipeline/tests/tier1/goldens/held_for_court_disposed_mc.json`
(new), `services/pipeline/tests/tier1/fixture-index.yaml`,
`agent-docs/held-for-court-fix-runbook.md` (new),
`agent-docs/intake/col-intake-protocol.md` (reconciliation-gate line),
`agent-docs/intake/refresh-runbook.md` (step-8 identity), this worklog.

**Deviations from plan:** none in mechanism. All four required fixes applied
(F1 rename ruling, F2 import-not-relist, F3 pinned both review deltas in the
runbook, F4 protocol citations — `run-fixtures --init-goldens` confirmed a
committed protocol step, cited as such).

**GOLDEN WRITE NOTE (29.3 intake, 2026-07-14, required per protocol):**
`run-fixtures --init-goldens` over snapshot `29.3-intake-20260714T211046Z`
wrote 2,174 absent tier-2 goldens for the new dockets; zero existing goldens
touched; zero drift. Report `tier2-report-20260714T213043_253487Z.json`
totals: `match=0 diverged=0 updated=0 new=2174 golden_missing=0 failed=3`
(the known parse_failed trio).

**C2 ADJUDICATION + PHASE-A ADDENDUM (2026-07-14).** The intake scan gate
fired on a sixth held variant: "Held for Court - Hearsay" (2 charges, one MC
docket, disposed-with-no-date, zero sentence components). Planning chat ruled
Option 1: it joins `HELD_FOR_COURT_DISPOSITIONS` as the sixth corpus-evidenced
entry (sourcing comment extended at the site). Tests updated: the exact-set
lock is now six forms; the map-to-None parametrization covers all six; the
closure suite's F2 membership spot-check is six. No new fixture — parse
behavior is unchanged and the mapper test is the fact-layer lock (R-c
decomposition unchanged). F2 confirmed post-addendum: the closure tool's
scope followed automatically via the import; the form strings exist in no
code outside the mapper set, its content-lock test, and closure-suite seed
data (the parser's separate NON_TERMINAL_DISPOSITIONS event-routing
vocabulary is untouched by design — parser out of scope).

**Closure-count note for C3 (so nobody hunts for +2):** expected closure
scope stays 1,004 `unmapped_disposition` + 1,002 `unmapped_charge`. The two
hearsay charges have never been through a fact build (they entered the corpus
after rebuild 1 and are carved out before rebuild 2), so no open review items
exist for them and none will be generated post-addendum.

**Rebuild-2 expectations (restated per the AC-4 guard pattern, post-intake
corpus 9,932 dockets / 30,285 charges):** `undisposed_skipped=6538`,
`held_for_court_skipped=10955` (10,953 five-form + 2 hearsay),
`facts_written=12792` (30,285 − 6,538 − 10,955), reconcile `True`. Fresh
counts verified before the run; drift = STOP and restate.

**OPERATIONAL RECORD, PHASES B–E (2026-07-14; all pipeline invocations
Chops-run; agent steps read-only).**

- **Rebuild 1** (run `7dcb0789-2ae6-41fe-8553-34701396c87c`, recon corpus
  7,758 dockets): `charges_processed=22865 facts_written=10347
  undisposed_skipped=4896 held_for_court_skipped=7622`, reconcile True.
  Keyed comparison vs baseline `7e26b002…`: outcomes only_in_old=7622
  (exactly the five forms: 6618/522/478/2/2), only_in_new=0, content_diff=0;
  `other` retained 155, `unknown` 188; sentence facts 0/0/0; review
  generation deltas exactly `unmapped_disposition` −1004 and
  `unmapped_charge` −1002, all other types unchanged, newly_inserted=0
  (checkpoint C1, cleared).
- **Intake** (snapshot `29.3-intake-20260714T211046Z`): staged 8388 /
  mtime-dropped 12 / excluded 6199 / included 2177 → imported 2174 +
  3 duplicates (known trio) → extract 2177 success → parse 2174 + 3 failed →
  goldens new=2174, zero drift (noted above) → load 2174 loaded +
  3 failed_envelope_loaded, supersession family 0. Corpus 7,758 → 9,932
  dockets (4,724 CP / 5,208 MC), charges 22,865 → 30,285, zero duplicate
  docket numbers.
- **Scan gate + C2 adjudication:** sixth variant "Held for Court - Hearsay"
  (2 charges) → Option 1, Phase-A addendum (noted above); six-form re-scan:
  zero rows.
- **Rebuild 2** (run `cc71204b-8264-4a7f-91f1-3f447cb1bd8c`):
  `charges_processed=30285 facts_written=12792 undisposed_skipped=6538
  held_for_court_skipped=10955`, reconcile True — exactly the restated
  expectations. Structural-exclusion proof: 0 facts for the six held forms.
  Review dedup held: newly_inserted=5078, all intake-docket growth.
- **Publish:** generate run `d47dcd20-2059-46ad-92a9-6dfd3846dc23` from
  build run `cc71204b…` (default=latest), data_range 2025-01-01..2026-07-13;
  validate `verdict=validated` (284/227/1749/1608 rows, 0 violations);
  publish invalidated `6ecf1fed…` in the same transaction (rollback target,
  standing decision 2). Post-publish verification: sole published row is
  `d47dcd20…`; zero `other`/`unknown` rows in charge AND judge aggregates;
  `simple-assault` serves six terminal categories (sample 430) with the new
  run id; data-coverage serves the new run id + live counts dynamically
  (verified, not rebuilt).
- **Queue closure (AC 10):** dry `would_close=2006` (1004
  unmapped_disposition + 1002 unmapped_charge) → confirm `closed=2006` →
  re-run dry `would_close=0` (idempotent). Queue state after: exactly
  1004 + 1002 superseded; `missing_disposition_date` untouched (14,652 open,
  by design — parser still emits the warning); the +2 hearsay non-delta is
  explained in the closure-count note above.

**SD-14 FORMAL COUNT RESTATEMENT (AC 11).** The 29.3 intake grew the corpus:
dockets 7,758 → 9,932 (+2,174: CP 4,034 → 4,724, MC 3,724 → 5,208); charges
22,865 → 30,285; undisposed (null-disposition) 4,896 → 6,538; held-form
bind-overs 7,622 (five forms) → 10,955 (six forms). Fact layer on the grown
corpus: 12,792 outcome facts / 10,578 sentence facts under run `cc71204b…`.
Published aggregate run: `d47dcd20…` (77 charges with outcome aggregates,
73 with sentencing, 1,170 judge-charge pairs).

**AC-9 RESTATEMENT (exit-demo item 7 / DoD item 3).** Satisfied by
STRUCTURAL-EXCLUSION proof, not by a visible distribution change: held-form
facts are zero on the published run's build; no non-terminal category row
exists in any published aggregate table; the demo anchor `simple-assault`
(highest held concentration, 537 held facts at recon) serves only terminal
outcome categories, and its expected visible change is NONE — the 29.3
pollution was latent at the fact layer (recon finding, adjudicated framing).
31.1's demo script and 31.4 inherit this honest framing.

**For the operational phases (B–E).** The ordered Chops-run command sequence,
the keyed-comparison SQL, the held-variant scan gate, and the closure
sequence live in `agent-docs/held-for-court-fix-runbook.md`. Expected deltas
are pinned to the recon corpus (7,758 dockets, baseline run `7e26b002…`) with
the AC-4 fresh-count guard. Checkpoints C1 (post-rebuild-1 comparison), C2
(scan gate), C3 (final report) go to planning chat before proceeding.
Expected visible change to published distributions: NONE (structural-
exclusion framing per AC 9; the pollution was latent at the fact layer).

## Task H-30.0 — Phase-30 Hygiene: db-suite order independence + ESLint .venv ignore (2026-07-14)

**What was built.** Two pre-existing hygiene fixes, first commit on phase-30.
(1) `db/seeds/reference.test.ts` — the exact-equality suite now runs in its
own scratch database (`pca_ref_test_<12-hex>`, sweep-seed-rows precedent):
created off DATABASE_URL's server in `beforeAll` (120s timeout), migrated to
latest via Migrator/FileMigrationProvider, force-dropped in robust `afterAll`
(60s). Every assertion unchanged. `createDb()` import dropped; imports
(`pg`, `kysely/migration`, `node:crypto`) are existing @pca/db dependencies.
(2) `eslint.config.mjs` — `'**/.venv/'` added to the flat-config global
ignores. Also `db/vitest.config.ts` — comment-only rewording at
`fileParallelism: false` (setting untouched) so the rationale stays truthful
post-isolation and carries the never-casually-revert language (approved in
plan review).

**Root cause (recon, adjudicated reframing).** The named "file-order
dependence" is cross-invocation shared-state coupling: roster suites write
additive-only rows into the shared test DB's `ref.*` tables; the reference
suite asserted full-table exactness against that shared DB, so it failed
whenever a roster file preceded it in one run (vitest's cache-driven default
order decides who runs first) — and, stronger, failed in ANY order once
roster rows persisted from a previous invocation. Recon reproduced: as-found
isolation 3/6 failed; pristine-DB green suite then isolation 3/6 failed;
pristine-DB shuffle (charge-roster before reference) 2/6 failed with the
failure signature tracking exactly which roster file ran first. CI was green
by file-size coincidence (no cache → larger-first → reference before both
rosters). Local repo-root lint was red (15,511 problems, 36 finding-bearing
files, all under `services/pipeline/.venv`, 0 outside) — CI green only
because CI has no venv.

**Post-fix (all on the deliberately dirty pca_test, adjudicated order):**
default order 59/59 green; shuffle-seeded run with charge-roster printed
before reference 59/59 green; reference isolation LAST 6/6 green; zero
leaked scratch databases. Repo-root lint exit 0 in 4.88s real (was exit 1,
28.47s).

**Durable guardrail established (standing rule for all future db-suite
work):** no db-suite file may assert exactness against the shared test
database — exact-equality assertions get a scratch database
(sweep/reference pattern) — and every suite must tolerate a non-pristine
shared test DB. The shared test DB is expected to be polluted; passing on it
is the required posture, not an accident. The rule is also stated in the
reference.test.ts header comment.

**Files touched:** `db/seeds/reference.test.ts`, `db/vitest.config.ts`
(comment only), `eslint.config.mjs`, `tasks/worklog.md`.

**Deviations from plan:** none.

**For the next task:** vitest default file order is cache-driven
(`db/node_modules/.vite/vitest/…/results.json` — failed-first, then
slower-first; size-desc without cache) and must never be relied on. The
recon-stage pca_test resets were recon-only; no reset is needed to run the
db suite anymore, in any order. fileParallelism: false in db/vitest.config.ts
remains a deliberate race fix — never casually revert.

## Task 30.1 — Real-Data Verification Walkthrough + Defect Fixes (2026-07-14)

**What was done.** Systematic real-data verification walkthrough of every
public page against published run `d47dcd20-2059-46ad-92a9-6dfd3846dc23` on
production builds (build:packages → API build + `start` under plain node →
web `next build` + `next start`), live DB read-only throughout. Serving ports
3100 (web) / 3101 (API) — 3000/3001 were held by dev servers; deviation
adjudicated at checkpoint, pinned mechanism otherwise intact. Walkthrough
tooling: a TEMPORARY untracked Playwright config + specs under
`e2e/walkthrough*` reusing the committed machinery (axe WCAG 2.2 AA tag set,
`scanPublicCopy`, `scanForForbidden`, combobox driving, section testids,
horizontal-overflow checks) with soft-collected assertions for inventory;
deleted before commit (staging-completeness output proves absence). No term
list or scanning mechanism was created.

**What was checked** (every cell desktop 1280px AND mobile 390×844; per-cell
results recorded; slugs are live-run examples, never acceptance values):
homepage search on real rosters with open-listbox states gate-scanned;
high-sample `pwid-controlled-substance`; widest tail `simple-assault` (six
terminal outcome categories; 29.3 structural-exclusion framing intact — no
visible change expected and none observed); thin `voluntary-manslaughter`
(callout + badges, both distributions); thin + longest display name
`aggravated-assault-fear-sbi-designated` (85-char name wraps cleanly);
sentencing-unavailable `criminal-conspiracy-903c` (non-thin, callout
isolated, `§ 903(c)` renders); solid judge pair `pwid-controlled-substance` ×
`gibbs-monica` (real single-category 100% distribution) plus multi-row solid
pair × `shaffer-zachary-c`; thin pair `aggravated-assault-deadly-weapon` ×
`gibbs-monica` (four slots, real tails incl. ARD + sentencing Other);
judge-unavailable pair × `brumbach-marissa-j`; `/definitions` with anchor
existence proven for all 11 category codes served across the four most
tail-rich pages; `/methodology`; `/data-coverage` (live run id, window, and
counts served dynamically); `/about`; approved addendum `harassment` (sole
zero-aggregate charge — honest unavailable arm). AC 2 battery per figure:
counts + percentages + sample sizes + date ranges + last-refreshed,
table/bar equivalence (bars aria-hidden, table authoritative), per-row
Definition links. 320px spot set (adjudicated): home with each autocomplete
open (longest charge and judge names fully visible), the two long-name
result pages, plus supplemental zero-overflow probes on the four content
pages and `harassment`. Keyboard/screen-reader spot pass (AC 3):
keyboard-only combobox commit → submit → result; judge-filter commit →
navigation; tab-order sanity on charge/judge/content pages — focus ring
visible on every stop, no traps, logical order; heading outlines (one h1, no
skips) and table header scopes everywhere. Final automated state: 39/39
green; zero axe / copy-safety / privacy violations on every visited state.

**What was found / fixed.** ZERO UI/copy/formatting defects — no fix code,
no E2E assertion edits (checkpoint-confirmed empty fix list; the post-fix
re-verification requirement was vacuously satisfied). Three
walkthrough-harness artifact classes were fixed in the temp specs and are
recorded for future harness reuse: (1) link-count assertions must scope to
`main` (the header nav carries its own methodology link); (2) keyboard
typing must wait for hydration — server-rendered content is visible before
client handlers attach (framework-inherent; named post-launch queue item,
not a defect); (3) focus-trap detection must compare element identity, not
text signatures (distinct per-row "Definition" links share one).

**What was escalated** (stop-and-report per SD-6; checkpoint-adjudicated as
plausible-by-construction — independent denominators / per-component
sentence facts; verification queued as separate read-only diagnostic 30.1-D,
NOT investigated in-task): F1 — sentencing sample size exceeds outcome
sample size for the same scope, recurring: `pwid-controlled-substance` 685
vs 473; `voluntary-manslaughter` 5 vs 4; `pwid-controlled-substance` ×
`gibbs-monica` 178 vs 124; `aggravated-assault-deadly-weapon` ×
`gibbs-monica` 3 vs 1; the same charge's baseline 74 vs 59. Rendering is
correct and every figure carries its own honest sample size; the open
question is aggregates-layer.

**Verification.** E2E suite green on `pca_test` (primary path; scratch
fallback not needed): `15 passed (12.9s)`. Four gates + typecheck run
post-staging per the clean-environment gate (outputs in the completion
report). Live DB untouched: walkthrough traffic read-only; test suites
pointed at `pca_test` via shell-exported DATABASE_URL; the 29.2 guard was
never bypassed, weakened, or pointed at the live DB.

**Files touched:** `tasks/worklog.md` only (temp harness deleted before
commit).

**Deviations from plan:** serving ports 3100/3101 instead of 3000/3001
(checkpoint-adjudicated); two lingering `tsx watch` API dev watchers stopped
with explicit authorization before the E2E gate.

**For the next task:** 30.1-D (F1 diagnostic, read-only) is queued after
close. Post-launch queue: pre-hydration typing gap on combobox inputs. 30.3
inherits no copy changes from this task.

## Task 30.1-D — F1 Diagnostic: Sentencing-vs-Outcome Sample Semantics (2026-07-14)

**Verdict (subject to planning-chat adjudication, never self-adjudicated):
BY-CONSTRUCTION CONFIRMED, mechanism quantified.** Read-only diagnostic;
SELECT-only via `docker compose exec -T postgres psql -U pca -d pca`
(compose service is `postgres`, adjudicated in plan review). No code, copy,
schema, or data changes; no pipeline invocation. Detail artifact with every
query and raw output: `~/court-data/reports/30.1-D-f1-sentencing-vs-outcome.txt`.

**TRIANGULATION DEVIATION (adjudication item).** The 29.3 run report the
plan-review ruling pinned as the primary build-run record does not exist:
no 29.3-named file under `~/court-data/reports/` (directory last modified
2026-07-13, before the 29.3 publish) and neither run UUID appears anywhere
under `~/court-data/`. Substitute primary record used: this worklog's 29.3
operational record (rebuild-2 build run `cc71204b…`, publish `d47dcd20…`
from it, default=latest). The substitute agrees exactly with (b)
`generate.py::_resolve_build_run` (default = latest completed,
`ORDER BY completed_at DESC LIMIT 1`; live DB: `cc71204b…` completed
2026-07-14 21:43:50, publish 21:45:36, sole active published run
`d47dcd20…`) and (c) exact-match recomputation across all five anchors and
corpus-wide (all counts and per-category splits reconcile to the row). The
build run's `counts` jsonb also matches this worklog's 29.3 figures
verbatim (12,792 outcome / 10,578 sentence facts).

**Unit semantics from source (AC 1).** Outcome sample size counts
`public_eligible` outcome facts, one per disposed charge
(`aggregates/generate.py::build_charge_outcome_aggregates`,
`facts/outcome_facts.py` 23.2). Sentencing sample size counts
`public_eligible` sentence facts, one row per parsed sentence component,
1:1 never collapsed (`build_charge_sentencing_aggregates`,
`facts/sentence_facts.py` 23.3; unique `(build_run_id, parsed_sentence_id)`;
live check: 10,578 facts = 10,578 distinct parsed components). Judge scopes
group `judge_specific_eligible` facts per pair with independent per-pair
sentencing denominators (SD 5). Eligibility is read, never recomputed (SD 1).

**Multi-category components (AC 2).** From source: an additive
(pattern-added) restitution / community-service mapping materializes as ONE
sentence fact carrying the BASE category only; `multi_category` forces
`review_needed=True`, which makes the fact public-INeligible
(`sentence_facts.py::evaluate_sentence_eligibility` — the silent-loss
guard). Live build run: 64 multi-category components (42 restitution + 22
community-service, 0 both; SQL replica of the locked 22.5 regexes), exactly
matching the build run's recorded `multi_category_components: 64`; all 64
are review-excluded — 0 public_eligible. Implication: pattern-added
additional mappings do NOT inflate public sentencing sample sizes; they
remove their component from public aggregates entirely. Bare-`N hours`
ambiguous components: 33, matching `ambiguous_sentencing_component: 33`.

**Invariants (AC 3, AC 4 + plan-review required fixes 1–2), all zero
violations on build run `cc71204b…`:** eligible sentence facts with parent
missing / parent not public_eligible / parent in a DIFFERENT build run:
0 / 0 / 0 (judge variant likewise 0 / 0 / 0). Denormalized scope
consistency: child `normalized_charge_id` / `normalized_judge_id` vs parent
mismatches 0 across all 10,578 facts. Per-scope invariant: distinct parents
of eligible sentence facts ≤ outcome sample size in all 73 charge scopes
and all 1,007 pair scopes — 0 violations.

**Anchor decomposition (AC 5), all five exact:** published sample sizes =
recomputed fact counts = walkthrough anchors; per-category counts identical
row-for-row; category sums = sample sizes; 0 orphans. Components-per-parent:
`pwid-controlled-substance` 685 sentence facts over 454 sentenced parents
(hist 1×244, 2×192, 3×16, 4×1, 5×1) vs 473 outcomes; `voluntary-manslaughter`
5 over 4 (1×3, 2×1) vs 4; `pwid` × `gibbs-monica` 178 over 118 (1×65, 2×46,
3×7) vs 124; `aggravated-assault-deadly-weapon` × `gibbs-monica` 3 over 1
(3×1) vs 1; `aggravated-assault-deadly-weapon` 74 over 47 (1×22, 2×23, 3×2)
vs 59. Cross-run: the sole active published run is `d47dcd20…`; anchor rows
under other run ids belong to invalidated or unpublished (`in_progress`)
runs, invisible to the API predicate — by design, not cross-run leakage.

**Corpus shape (AC 6).** Charges: 33 of 73 sentencing scopes inverted
(6 equal, 34 smaller; max diff +212 = `pwid-controlled-substance`, median
inverted diff +5, max ratio 2.00, median 1.23). Pairs: 303 of 1,007
inverted (473 equal, 231 smaller; max diff +54, median +1, max ratio 4.00,
median 1.51). Full inverted-charge enumeration by slug in the detail
artifact. Corpus-wide eligible totals: 5,359 sentence facts vs 5,339
outcome facts.

**SD-15 recheck (AC 7).** All 10,578 facts: sentence_date earlier than
disposition_date 35 / equal 10,543 / later 0 / null 0; 2025-01-01
window-straddles 29 (sentence before window, disposition inside), reverse 0;
earlier-delta 1–757 days — matches the build run's recorded
`sd15_divergence: 35`, `sd15_straddle_mvp: 29`, deltas 1/757 exactly.
Public-eligible subset: 2 earlier, 0 straddles (straddling components are
mvp-ineligible by construction).

**Methodology hand-off (AC 8, no copy edits).** Served copy traced to the
REAL constants: `/methodology` = `apps/api/src/content/methodology.ts`
(`METHODOLOGY_CONTENT`, static per deploy; web page renders the API
response); `/definitions` = `apps/api/src/taxonomy.ts::PUBLIC_DEFINITIONS`
from `packages/taxonomy/seeds/*.json` definitions. Independent sentencing
denominators: EXPLAINED (sentencing section, incl. SD-15 date independence).
Component-counted samples: NOT explained ("charge dispositions or
sentencing events" — nothing says one sentencing event contributes one row
per component). Sentencing n exceeding outcome n: NOT explained — worse,
the copy asserts sentencing samples are "typically smaller than the outcome
sample size," contradicted at current corpus scale (33/73 charges,
303/1,007 pairs inverted, flagship charge 685 vs 473). Definitions copy
carries no sample-size semantics. → Named 30.3 rewrite items: fix
"typically smaller," explain per-component counting, state that sentencing
n can exceed outcome n.

**Verdict basis (AC 9).** Sentencing n = eligible sentence components over
sentenced eligible parents; every decomposition exact; zero unreconciled
residue. The inversion is exactly the by-construction mechanism the plans
describe (23.2/23.3, SD 5, 26.2): multi-component sentences under a subset
of sentenced parents. ANOMALY arm not triggered; verdict and the
triangulation substitution both go to planning chat for adjudication.

**Files touched:** `tasks/worklog.md` only. Detail artifact under
`~/court-data/reports/` (never committed).

**Deviations from plan:** the missing 29.3 run report (above) — worklog
substituted as primary record, flagged for adjudication rather than treated
as satisfied. Compose service name `postgres` (approved in plan review).

**For the next task:** 30.3 inherits the three copy rewrite items above.
The 29.3 publish/rebuild console outputs exist only in planning chat and
this worklog — if a durable run-report file is wanted, it must be
reconstructed from planning chat (never from memory) or accepted as
worklog-only. Two stale `in_progress` aggregate runs (`51d27853…`,
`2d4707ca…`, pre-publish history) sit unpublished in
`analytics.aggregate_runs`; harmless to the API predicate.

## Task 30.2 — Queued Contract Closures (2026-07-14)

**What was done.** Two documented closures, ZERO code changes (both
dispositions ruled at plan review; evidence replaces the diff).

**Part A — message-constant migration: CLOSED-BY-EVIDENCE (already
satisfied at 10.2, never marked closed).** Recon per the sprint-plan
stop-and-report preamble found the §5 queue item's premise stale:
`CHARGE_RESULT_UNAVAILABLE_MESSAGE` already lives in `@pca/shared` at
`packages/shared/src/public/charge-result.ts` alongside the other pinned
literals (`CHARGE_NOT_FOUND_MESSAGE`, `CHARGE_SENTENCING_UNAVAILABLE_MESSAGE`),
with doc-comment provenance "migrated from the 8.1 service in task 10.2."
Single definition: the literal occurs exactly once repo-wide, and is
additionally schema-pinned as a `Type.Literal` in the charge-unavailable
arm contract. All consumers import from `@pca/shared` — api
(`services/charge-result.ts`, `services/judge-result.ts`, route/service
tests, `public-copy-safety.test.ts`), web (`ChargeUnavailableView.tsx`,
`JudgeChargeUnavailableView.tsx`, component/state tests — never re-typed),
e2e (`unavailable-and-not-found.spec.ts`), shared-internal
(`error-messages.ts` references it in `PUBLIC_ERROR_MESSAGES`;
`test-support/fixtures.ts`). Scanner coverage at the @pca/shared home is
the 10.2 mechanism in `apps/api/src/public-copy-safety.test.ts`: the
constant is imported into `PINNED_PUBLIC_MESSAGES` and scanned at
definition, scanned again via the `PUBLIC_ERROR_MESSAGES` map, and scanned
live in rendered payloads via the probe-registry route scans (verbatim
suite output in the completion report). The in-package shuffle alternative
was rejected at plan review as manufactured motion.

**Part B — duration-display resolution: expected finding CONFIRMED, no
duration data on any public surface; the 360-day-year display question is
FORMALLY RETIRED for the MVP.** Method: source read + SELECT-only live-DB
checks via the sanctioned mechanism. Evidence: (1) live `analytics.*`
column inventory (verbatim psql in the completion report) — no duration
column in any of the five tables (`aggregate_runs` + four aggregate
tables; columns are category/count/percentage/sample-size/date-range/
thin-data/taxonomy bookkeeping only); (2) the single analytics migration
(`20260708223601`) defines that closed column set and no later migration
alters analytics tables; (3) `min_days`/`max_days`/`min_assumed` exist
only in `parsed.*` and `facts.*` (non-public layers); (4) grep for
duration identifiers across `packages/shared/src`, `apps/api/src`,
`apps/web/app` — zero hits; distribution entries carry only
categoryCode/displayName/count/percentage, all public schemas
`additionalProperties: false`, serialized against the union response
schemas. Clarity note: NONE, ruled at plan review — a units note for data
that never renders would mislead rather than clarify.

**Verification.** Copy-safety suite green with the constant scanned at its
@pca/shared home; E2E green on `pca_test` (shell-exported DATABASE_URL;
29.2 guard never bypassed); four gates + typecheck post-staging per the
clean-environment gate. Live DB read-only throughout (SELECT-only
inventory). Outputs verbatim in the completion report.

**Files touched:** `tasks/worklog.md` only.

**Deviations from plan:** none (the zero-diff shape IS the approved plan).

**For the next task (30.3 hand-off, ruled at plan review):** the 30.3 full
read should confirm no served copy promises sentence-length or duration
information in synonym terms the identifier grep would not catch
("sentence length", "how long", etc.) — expected clean. 30.3 also still
owns the three queued sentencing-sample rewording items from 30.1-D.

## Task 30.3 — Launch Copy + Date-Disclosure Pass (2026-07-15)

**What was done.** Full launch-framing read of ALL public copy as served
(17 surfaces, constants + serving trace + live-serve curl spot-checks under
the 30.1 agent-boot conditions); checkpoint-approved rewrites landed as
shared constants under existing scanner coverage; coverage block landed on
two surfaces per the checkpoint product decision. Phase 30 closes with this
task.

**Per-surface verdicts (AC 1).** Methodology `sentencing`: REWRITTEN
(confirmed items 1-3: "typically smaller" corpus-contingent claim removed;
per-component counting explained; sentencing n can exceed outcome n stated
with mechanism; SD-15 sentences preserved byte-identical). Methodology
`sampleSize`: REWRITTEN (sample-size units now name charge dispositions for
outcome figures and individual sentence components for sentencing figures).
Methodology `thinData`: RETAINED, flagged instance (see rationale below).
Methodology other seven sections: clean. Methodology page chrome: clean.
Data-coverage limitation "Coverage currently extends further for Municipal
Court...": REWRITTEN to construction form ("The covered records are a
growing subset of Philadelphia criminal cases..."), keeping the
/collection is ongoing/i pin. Data-coverage limitation "Most judge-specific
figures are thin at this stage": RETAINED, flagged instance. Data-coverage
other limitations, schema-pinned constants, page chrome: clean. Definitions
text (16 public categories): clean, NO edits, taxonomy version-bump
question never triggered. Definitions chrome: clean. Homepage: clean.
About page: REWRITTEN ("parsed, normalized, reviewed, and aggregated"
claimed a review step that does not exist in this version — ages
false-authoritative; now "parsed, normalized, and aggregated ... records
that cannot be read reliably are excluded automatically"). Layout/footer/
nav: clean, site-wide noindex intact. Result-display copy, formatter
labels, charge/judge result chrome, three unavailable arms, two not-found
messages, nine public error messages + fetch-failure message, search copy:
all clean; unavailable arms curl-verified serving pinned literals verbatim.

**Retention rationales (AC 3).** Both retained corpus-contingent instances
are the judge-thinness disclosures (methodology `thinData`; data-coverage
limitation 4): mandated honesty, explicitly time-scoped ("at this stage"),
currently true (published run: 1,050 of 1,170 judge-charge pairs thin,
89.7%), and they age FALSE-PESSIMISTIC (as coverage deepens the warning
overstates caution), which the checkpoint ruled tolerable. The SD-15 "the
two usually coincide" phrasing sits inside the protected SD-15 disclosure
(verify presence, don't rework) and was re-verified at scale by 30.1-D
(10,543/10,578 equal); retained untouched.

**Corpus-contingent sweep (AC 3).** Sweep of all served constants for the
class (typically/usually/most/currently/at this stage/often/generally/
tends/rarely/majority/norm): five instances found; two rewritten (type
specimen "typically smaller" + MC-vs-CP direction claim), two retained
with the rationale above, one inside the protected SD-15 text. Zero
unadjudicated instances remain.

**Duration-synonym check (AC 4): CLEAN.** Zero hits for "sentence length" /
"how long" / "duration" / "length of" / "term of" / months / years across
all served constants. Sentencing is described by category only.

**Unmapped-tail verdict (AC 4): HONEST AS SERVED.** Methodology limitations
states unclear outcome/judge-attribution records are excluded automatically
rather than resolved by hand; `unknown` categories are `public: false` and
never served; an unknown stored code raises INTERNAL_ERROR, never a
fabricated name. No rewrite needed.

**Coverage block (AC 5).** Absent as served (recon-confirmed; no
misdemeanor/felony/summary/pending language existed anywhere). Checkpoint
product decision: land BOTH a result-page note and a data-coverage bullet.
Result-page note landed as `RESULT_DISPLAY_COPY.coverageNote`, rendered in
the summary section of both result views directly adjacent to the
responsible-use notice (inside `section-summary`, NO new section testid, so
the pinned e2e section-order assertions needed no edits). Data-coverage
bullet landed as knownLimitations entry 2. The task-sketch "filed 2025+"
framing was ruled superseded at plan review (factually false; event-date
construction is served). The sketched "summary citations excluded" claim
was CONTRADICTED by the grade-S evidence check and reworded to honest form
per the checkpoint (summary-graded charges included when part of a criminal
case; standalone summary citations not collected).

**Grade-S evidence check (AC 5), SELECT-only via
`docker compose exec -T postgres psql -U pca -d pca`, verbatim.**
`ref.normalized_charges.grade` is NULL for all 78 loaded charges (served
`grade` field absent from payloads); grade lives in `parsed.charges`.

```
 grade | count
-------+-------
 F     |  1974
 F1    |  3233
 F2    |  2326
 F3    |  4086
 H1    |    49
 H2    |     6
 M     |  1070
 M1    |  4313
 M2    |  4227
 M3    |   482
 S     |   696
       |  7823
(12 rows)
```

Latest completed build run, grade-S outcome facts (count |
public_eligible): `S | 424 | 144`; grade-S sentence facts via parent
outcome join: `S | 232 | 133`. Served slugs carrying grade-S
public-eligible outcome facts:

```
                 slug                  | public_eligible_outcome_facts
---------------------------------------+-------------------------------
 harassment-physical-contact           |                            48
 disorderly-conduct-fighting           |                            28
 retail-theft                          |                            26
 criminal-mischief-damage-property     |                            22
 disorderly-conduct-hazardous          |                            14
 defiant-trespass-posted               |                             2
 criminal-conspiracy                   |                             2
 criminal-attempt                      |                             1
 defiant-trespass-actual-communication |                             1
(9 rows)
```

Supporting checks recorded at the checkpoint: judge-thinness currently true
(1,050 of 1,170 pairs thin); MC 5,208 vs CP 4,724 dockets (direction claim
true but marginal and closing — rewritten per ruling).

**Framing inheritances (AC 6).** Zero "demo"/"seeded"/"pollution" in served
copy (residue exists only in code comments referencing the removed Sprint-2
disclosure). SD-15 disclosure verified present in the live payload before
and after the edit and preserved byte-identical through the sentencing
rewrite. Judge-thinness honesty intact (retained, above).

**Scanner coverage + stop condition (AC 7).** Every proposed string was
pre-scanned before the checkpoint and again before landing (scanPublicCopy,
the methodology route's stricter regexes and internal-detail substrings,
the data-coverage route's term regexes and forbidden substrings, HARD-pin
compatibility). STOP CONDITION EXERCISED: the checkpoint-adjudicated
data-coverage coverage bullet contained "docket"/"dockets", which fails the
data-coverage route's forbidden-substring sweep; landing halted and the
failure returned to planning chat; Candidate A rewording (docket-free,
same claims) was adjudicated and landed. No new scanner mechanisms or term
lists. All landed strings are em-dash-free per planning-chat instruction
(punctuation swaps only, word-identical).

**Re-serve verification (checkpoint required fix 1).** After landing:
web production build rebuilt; API (tsx, port 3100) + web (`next start`,
port 3101, API_BASE_URL to 3100) booted read-only against the live DB;
re-curled all five changed surfaces. New strings serve on /methodology
(component counting + can-exceed), /data-coverage (new bullet + growing-
subset rewrite, zero MC-vs-CP occurrences), /about (excluded-automatically
sentence, zero "reviewed, and aggregated" occurrences), charge result and
judge result (coverageNote renders on both). HARD positive pins all present
in payloads: /January 1, 2025/, /not the filing date/i, /not a prediction/i,
/collection is ongoing/i, SD-15 "sentencing dates fall earlier"; "typically
smaller" zero occurrences. Servers torn down before any test suite ran.
Note: `next dev` (Turbopack) 404'd the nested judge route for unrelated
reasons; the production `next start` path (the CI-proven shape) serves it
correctly (200) and was used for verification.

**§5 responsible-use review item (plan AC 4): CLOSED.** The responsible-use
notice (four statements from RESULT_DISPLAY_COPY, rendered by
ResponsibleUseNotice on both result views and the About page) was read
against the controlled-launch framing and is honest and copy-safe as
served; this pass formalizes the 28.2 work for launch. The Sprint 9 queue
item is satisfied by this task.

**Verification.** E2E green on `pca_test` (shell-exported DATABASE_URL;
29.2 guard never bypassed; deterministic reseed before the run): 15 passed.
Four gates + typecheck run post-staging with caches cleared per the
clean-environment gate; outputs verbatim in the completion report, plus
staging completeness over task paths.

**Files touched:** `apps/api/src/content/methodology.ts`,
`apps/api/src/content/data-coverage.ts`, `apps/web/app/about/page.tsx`,
`apps/web/app/components/result-display-copy.ts`,
`apps/web/app/components/ChargeOnlyResultView.tsx`,
`apps/web/app/components/JudgeSpecificResultView.tsx`,
`apps/web/app/components/ChargeOnlyResultView.test.tsx`,
`apps/web/app/components/JudgeSpecificResultView.test.tsx`,
`tasks/worklog.md`. No e2e edits (the coverage note lives inside
`section-summary`; the checkpoint's conditional e2e edits were not
triggered).

**Deviations from plan:** the adjudicated coverage-bullet wording failed
pre-scan on the "docket" substring — stop condition exercised, reworded
wording (Candidate A) adjudicated in planning chat before landing. Em-dash
removal instruction applied to all landed strings as word-identical
punctuation swaps. No other deviations.

**For the next task:** Phase 30 closes here; the full PR loop runs at this
commit (push, PR, CI green, rebase-and-merge or merge commit, never
squash; CI also provides the deferred confirmation for the phase's
E2E/production-build claims). 31.1 (demo script) can now cite the coverage
note as a served surface. Post-launch queue unchanged: pre-hydration typing
gap on combobox inputs; two stale `in_progress` aggregate runs remain
unpublished and harmless.

## Task 31.1 — Demo Script + Demo Data Guardrails (2026-07-15)

**What was done.** Authored `agent-docs/demo-script.md`: the start-to-finish
demo path per pinned decision 1 (high-sample charge search → charge-only
result → thin-data example → judge filter → solid judge pair → thin judge
pair → judge-unavailable fallback → sentencing-unavailable charge →
remove-filter flow → methodology → data-coverage → mobile view at 390/320),
every step naming its slug and app path with expected on-screen outcomes in
copy-safe terms, a staleness-guardrails preamble (snapshot-of-a-published-run
framing, no pinned numbers anywhere, republish behavior, per-arm re-pick
criteria), the approved AC-3 re-verify walkthrough (/data-coverage metadata
check → anchor loads → re-pick criteria; no new tooling), and a
known-limitations section (judge thinness, MC/CP coverage shape,
sentencing-unavailable classes, ongoing collection). Held-for-court is
framed structurally only — non-terminal forms produce no outcome facts by
construction; no before/after framing anywhere. The sample-size moment
states the counting construction (outcome samples charge-counted; sentencing
samples component-counted under eligible parents; may differ in either
direction) and never asserts which is larger. Opens the phase-31 branch as
its first commit.

**Path supersession (recorded per planning-chat ruling).** Task 31.1 AC 1's
literal path `docs/demo-script.md` was superseded to
`agent-docs/demo-script.md` by planning-chat adjudication at plan approval —
the CLAUDE.md prohibition on agent-created files in `docs/` stands; nothing
under `docs/` was created or touched.

**Anchor re-verification (AC 6).** All eight candidate anchors verified
against the currently published run — ZERO substitutions; the midpoint
substitution checkpoint was not triggered. Method: production builds booted
read-only per the 30.1 mechanism (build:packages → API build + `start` under
plain node, PORT=3101 → web `next build` + `next start -p 3100`,
API_BASE_URL to 3101; 3100/3101 precedented), each anchor curled on the
public API and its arm shape confirmed (thin flags, unavailable arms,
display names, run id on every payload); sole published+non-invalidated run
confirmed SELECT-only via `docker compose exec -T postgres psql -U pca -d
pca` (one row). Search terms for every anchor confirmed resolving in the
charge/judge autocomplete endpoints. Raw outputs verbatim in the completion
report. Servers torn down and ports verified freed before any suite or gate
ran; live DB read-only throughout; no .env value echoed.

**Copy safety (AC 5 / pin 8).** One-off scanner invocation confirmed
feasible and run: `scanPublicCopy` from the built `@pca/shared` dist over
the whitespace-collapsed doc — CLEAN, 0 violations (output verbatim in the
completion report). Every quoted on-screen literal in the doc was re-copied
from source constants and mechanically re-checked against them (25/25
match). No permanent walker coverage of any doc tree was added.

**Files touched:** `agent-docs/demo-script.md` (new), `tasks/worklog.md`.
The three pre-existing untracked agent-docs files (v1col-data,
v1database-schema, v1pipeline-arch) were not touched or staged — their
disposition is a 31.2 adjudication.

**Deviations from plan:** deliverable path superseded to agent-docs/ by the
approval ruling (recorded above). None otherwise.

**For the next task:** 31.3 executes this script verbatim against the
deployed URL (impl AC 5) and 31.4 item 9 runs it as the exit demo. The
script's guardrails assume /data-coverage remains the live run-metadata
surface; if 31.3 changes that page's fields, the script's re-verify
walkthrough needs a same-task update. A republish before the demo requires
only the script's own re-verify walkthrough, not a doc rewrite.

## Task 31.2a — Documentation Tree Consolidation (2026-07-15)

**What was done.** Consolidated the two documentation trees into one:
`docs/` survives; `agent-docs/` is retired. Human-maintained planning
documents (README, architecture, brief, front-end-spec,
implementation-backlog, prd, roadmap, sprint-1..3 plans — 10 tracked
files) moved via `git mv` to the new protected subdirectory
`docs/planning/`. All 16 tracked agent docs moved via `git mv` to
`docs/` (11 flat files) with `decisions/` and `intake/` preserved as
`docs/decisions/` and `docs/intake/`. The flat-at-root shape was chosen
because it preserves every relative link with zero edits (`../apps/...`
in a11y-mobile-pass.md, `decisions/...`, `intake/...` sibling links).
CLAUDE.md's Documentation rules block replaced with the approved text
(protection narrows from all of `docs/` to `docs/planning/`; agent docs
go elsewhere under `docs/`), plus its two other path references updated
(Reference docs section; ADR 0002 pointer). The original rule (commit
4bd7231, task 2.2) existed for authorship separation — that rationale is
preserved by the `docs/planning/` boundary.

**v1 trio committed.** `v1col-data.md`, `v1database-schema.md`,
`v1pipeline-arch.md` moved to `docs/`, prettier-formatted (sanctioned
exception 1), all 17 machine-absolute `file:///` links converted to
repo-relative with identical targets (sanctioned exception 2, planning-
chat ruling 2, done before first `git add` so absolute local paths never
enter history), copy-scanned via the 31.1 one-off `scanPublicCopy`
mechanism — CLEAN, 0 violations — and committed.

**Reference updates (each file's only change).** `.prettierignore`
(`docs/` → `docs/planning/` — format coverage strictly grows),
`db/scripts/seed-guard.ts` + `db/tests/sweep-seed-rows.test.ts`
(seed-sweep-runbook path), `docs/held-for-court-fix-runbook.md` (intake
protocol path), `docs/tooling.md` (describes the .prettierignore
contents; ruling 3). Self-healed without edits: `.env.example` and
`db/README.md` referenced `docs/local-setup.md`, stale since task 2.2,
correct again now. Unchanged by design: `eslint.config.mjs` (`docs/`
ignore harmless in a markdown-only tree), root `README.md` layout row,
`docs/planning/architecture.md` repo diagram,
`tasks/current-task-template.md`.

**Demo script canonical path (supersedes the 31.1 note).** The demo
script now lives at `docs/demo-script.md`. 31.3 impl AC 5 and 31.4
item 9 execute it from there.

**Caveat retirement (new posture).** From this task's gates onward,
`pnpm format:check` green = fully clean; ANY warn line = stop. The
v1-trio warn-lines caveat is retired. Expected untracked posture:
`git ls-files --others --exclude-standard docs/` = exactly the four
sprint-4..7 plan files (physically moved to `docs/planning/`, staying
untracked per pin 6 / ruling 4; publication is a post-launch queue
item for 31.2's future-work doc). Any other untracked or warn entry =
stop.

**Files touched:** 26 tracked files `git mv`'d under `docs/` (no content
change — R100 renames); `docs/v1col-data.md`, `docs/v1database-schema.md`,
`docs/v1pipeline-arch.md` (new; formatting + link-form only); `CLAUDE.md`
(docs rule + two path references); `.prettierignore`;
`db/scripts/seed-guard.ts`; `db/tests/sweep-seed-rows.test.ts`;
`docs/held-for-court-fix-runbook.md`; `docs/tooling.md`;
`tasks/worklog.md`.

**Deviations from plan:** none — executed per the five planning-chat
rulings (structure as proposed; ALL file:/// links converted, not just
the two breaking ones; tooling.md update approved; sprint-4..7 plans
moved untracked; exception list = worklog + current-task + git history).
Human-directed pre-commit addition: one pre-existing machine-absolute
path in a historical entry (COL-era verbatim block) was redacted to the
~/court-data/ shorthand per the public-repo hygiene check; the report
filename is preserved. This 31.2a entry itself carried no absolute paths.

**For the next task.** 31.2 writes README pointers against this final
tree: planning set at `docs/planning/`, agent docs flat at `docs/` root,
ADRs at `docs/decisions/`, intake at `docs/intake/`. The untracked
`docs/planning/sprint-5-plan.md` contains one literal "agent-docs"
mention (line 653) — out of the repo; fix whenever the sprint plans are
published post-launch. The trio's remaining relative links point at real
source paths and were target-verified; content rewrites (including any
prose staleness in the v1 docs) remain 31.2+.

## Task 31.2 — Submission Package (2026-07-15)

**What was built.** `README.md` rewritten to the adjudicated outline: what
the product is and is not (guarded-phrase framing only); the launch MODEL
with no deployed claim (ruling 3a — the live-URL/status line is a named 31.3
gate item); a what-ships honesty section stating precisely what a fresh
local boot yields (ruling 3b); paragraph-level architecture; a
getting-started sequence proven by the dry run; workspace layout; testing;
a documentation map into the consolidated docs/ tree; limitations and
future-work links; privacy and responsible use.
`docs/known-limitations.md` (new): consolidation-ONLY launch-facing summary
drawn from the parser proof-of-concept report, the normalization/attribution
report, and the served methodology/data-coverage copy — every section names
its sources; construction statements only (no corpus counts, no run IDs
anywhere in the three docs); bluntness preserved (no NER-grade name
detection, OCR unimplemented, quarantined unsupported-format class,
exclusion-not-correction). `docs/future-work.md` (new): ten items, each with
its named landing/trigger — the six plan items plus the four Phase 30 queue
additions; the stale-run housekeeping item is described mechanically with no
run IDs; sprint-plan publication carries the consolidated-tree path-reference
note (the known stale `agent-docs` string in the untracked sprint-5 plan).

**§6.5 attachment shape (ruling 3b) confirmed at write time.** The aggregate
seed registry attaches every fabricated distribution to demo charge slugs
and to `judge-testina-placeholder` / `judge-samuel-seeddata` only;
`judge-fakename-example` deliberately carries zero aggregate rows; no real
roster judge appears. No violation to adjudicate.

**Screenshots (AC 5): SKIPPED per the Context ruling** — recorded here, not
implemented.

**Fresh-clone dry run (pins 6–7, rulings 1–2).** Pre-check found ports
3000/3001 occupied → STOP per required fix 1; the human freed them; re-check
clean before proceeding. Clone of committed phase-31 HEAD into a scratchpad
directory named `pca-freshclone` outside the repo (distinct Compose
project/volume namespace by directory basename — docker-compose.yml has no
`name:` key), with the rewritten README + both new docs overlaid (ruling 2).
Isolation overrides used and disclosed: `POSTGRES_PORT=5434` plus matching
`DATABASE_URL` port in the clone's `.env` — both documented knobs; a fresh
user on a clean machine needs neither. Documented path executed: `pnpm
install` → `cp .env.example .env` → `pnpm db:up` (clone container healthy on
5434) → `pnpm db:migrate:latest` (8 migrations) → `pnpm db:seed` (guard
allowed the empty DB; demo charges, fake seed judges, real rosters, and the
synthetic runs seeded — matching the README's fresh-boot description).
**Defect surfaced (doc-fix only; midpoint checkpoint not triggered):**
`pnpm dev` alone 500s on the web app on a fresh clone — `@pca/shared`
resolves to `dist/`, which does not exist until a build (the API boots fine;
its dev script runs from source via the `pca-source` condition). Fix:
`pnpm build:packages` added to the README boot sequence before `pnpm dev`,
and the Generated-artifacts paragraph corrected (root `test` runs generate
first; root `typecheck` starts with `build:packages`). Per ruling 2 the
corrected README was re-synced into the clone and the affected steps re-run
against the corrected text: `build:packages` → `pnpm dev` → API `/health`
ok, web `/` and `/methodology` 200, charge search serving roster + demo
charges, judge search serving the fake seed judge, charge result page 200.
Env audit: every env var each deployable reads is either in a committed
`.env.example` or optional-with-default (API `PORT` 3001 / `HOST` 127.0.0.1
/ `LOG_LEVEL` info in `apps/api/src/env.ts`; the web app ran with no `.env`
at all); `docs/local-setup.md` and `.env.example` needed NO changes.
Teardown per ruling 1: dev servers stopped and ports verified freed;
`docker compose down` in the clone (never `-v`); `docker volume ls` captured
showing both volumes as distinct entries; then
`docker volume rm pca-freshclone_postgres-data` by explicit name; the live
container and `pca_postgres-data` verified untouched. No dry-run step
touched the live database.

**Copy gate.** One-off `scanPublicCopy` invocation (31.1/31.2a mechanism:
built `@pca/shared` dist over whitespace-collapsed doc text) across
`README.md`, `docs/known-limitations.md`, `docs/future-work.md`: CLEAN, 0
violations (verbatim output in the completion report). No permanent doc
walker was added.

**Files touched:** `README.md` (rewrite), `docs/known-limitations.md` (new),
`docs/future-work.md` (new), `tasks/worklog.md`. `docs/local-setup.md` and
`.env.example` were in the allowed list but are untouched — the dry run
proved no defect in either.

**Deviations from plan:** none beyond the anticipated in-scope README fixes
above; the port-collision STOP and resume ran exactly per required fix 1.

**For the next task:** 31.3 owns the README's live-URL/status line (the
Launch model section states the model and makes no deployed claim). The
documented boot sequence now includes `pnpm build:packages`; any 31.3 change
to local boot must keep README/dry-run parity. Untracked posture unchanged:
`git ls-files --others --exclude-standard` over the repo = exactly the four
sprint-4..7 plan files under `docs/planning/`.

## Task 31.3 — Deployment Implementation: Guard, Rate Limiting, ADR, Runbooks (2026-07-15)

**What was built.** The pre-go-live implementation layer per the adjudicated
31.3 gate. (1) API_BASE_URL production guard:
`apps/web/app/lib/api-base-url.ts` now THROWS when
`NODE_ENV === 'production'` and the value is unset/empty; local-dev default
retained; next.config.ts evaluates it at config load, so misconfiguration
fails `next build`/`next start` loudly. Four new guard tests in
`api-base-url.test.ts`. (2) Live rate limiting: `@fastify/rate-limit@11.1.0`
(the task's one new dependency) registered INSIDE the public-routes
encapsulation scope (`apps/api/src/routes/public/index.ts`) — /health and
admin are structurally outside it. Constant-key global bucket per ruling 1
(recon: no reliable client identity reaches the private API — SSR fetches
carry none, the Next rewrite proxy adds only x-forwarded-host); per-IP
enforcement is the Cloudflare edge rule. Exceeded path:
`errorResponseBuilder` returns `publicError(RATE_LIMITED, <shared message>)`
and the plugin THROWS it (plugin index.js `throw
params.errorResponseBuilder(...)`), so the central handler shapes the 429 —
flat catalog shape with requestId, message from PUBLIC_ERROR_MESSAGES.
Thresholds env-tunable via loadEnv(): RATE_LIMIT_MAX (default 120) /
RATE_LIMIT_WINDOW_MS (default 60000), validated positive integers, always
registered, no disable path (ruling 2). Seven tests in
`apps/api/src/rate-limit.test.ts`: defaults, env reads, invalid-value
throws, 429 catalog shape (requestId presence proves central-handler
routing), two-IPs-one-bucket keying proof, /health 10-request burst all-200,
env-tuned threshold. (3) `docs/decisions/0004-deployment.md`: all ruled
decisions with rationale and one-line rejections, plus the six recorded
hazards including the per-instance in-memory bucket note (required addition
1). (4) Runbooks at docs/ root (ruling 5): `runbook-go-live.md` (domain,
DB creation, migrate, nine-table dump/restore with matched `pg_dump -Fc` /
`pg_restore --single-transaction` pair and explicit FK-ordered TOC per
required addition 2, private API + web services with CI-proven build
commands incl. `pnpm generate`, DNS/proxy, edge rate rule ~300/min on
/api/*, Bot Fight Mode OFF, UptimeRobot probes, three-surface noindex
verification — every step with a checkpoint), `runbook-verification.md`
(AGENT read-only half: endpoint sweep, noindex, forbidden-field scratch
scan per recon 5, one controlled 429 burst then stop; CHOPS half:
demo-script smoke), `runbook-rollback-republish.md` (Render rollback,
disposable-mirror data posture, edge point-away, TRUNCATE-then-restore
republish). Secret hygiene throughout: prod DATABASE_URL only via
`read -s`, never a file, never echoed.

**Files touched.** apps/web/app/lib/api-base-url.ts + .test.ts;
apps/api/src/env.ts, app.ts, routes/public/index.ts, rate-limit.test.ts
(new), package.json (+@fastify/rate-limit); pnpm-lock.yaml;
packages/shared/src/errors.ts (one line: stale "no middleware exists yet"
comment retired, ruling 4); .github/workflows/ci.yml (one enumerated edit:
API_BASE_URL env on the node-job Typecheck step — `next typegen` runs with
NODE_ENV=production); apps/web/.env.example (production-required note);
docs/local-setup.md (one enumerated edit, ruling 3b: apps/web/.env copy
step); docs/decisions/0004-deployment.md (new); docs/runbook-go-live.md,
docs/runbook-verification.md, docs/runbook-rollback-republish.md (new);
tasks/worklog.md.

**Deviations from plan.** None. app.ts was touched as anticipated
("may be untouched" resolved to a five-line register-options change).

**NEW STANDING LOCAL FACT (ruling 3c).** `pnpm typecheck`, web production
builds, and `pnpm test:e2e` now REQUIRE API_BASE_URL locally (Next defaults
NODE_ENV=production for every CLI command except `next dev`, and the guard
evaluates at config load). Set it via `apps/web/.env` (copy the example) or
a shell export. CI: the node job's Typecheck step carries it explicitly;
the e2e job already had it at job level.

**For the next task (31.4 / close-out).** Go-live is post-merge Chops work
from the three runbooks; ACs 3–6 of the plan verify there. Final authority
for build/E2E behavior claims is CI green at the phase PR (§6.2 exception).
The in-app limiter bucket is per-instance in-memory — recorded as ADR
hazard 5; revisit before any scale-out. Run-report file emission remains
deferred (named at 31.4). README live-URL line belongs to the close-out
branch, not here.

## Task 31.3b — Historical-Report Point-in-Time Framing (2026-07-15)

**What was built.** One dated point-in-time framing banner prepended to each
of the two historical reports, wording approved verbatim in planning chat
(2026-07-15) before commit: `docs/normalization-attribution-report.md`
(Sprint 5 / Task 25.1, written 2026-07-12 per the worklog heading — the
pin-4-sanctioned source; named builds `aef44371` pre-intake and `d591902f`
post-intake, both already carried by the doc's provenance key) and
`docs/parser-proof-of-concept.md` (Sprint 4 close / Task 20.1, written
2026-07-11 per the doc's own header). Both banners are blockquotes at line 1
above the H1 — true prepend, exactly one insertion hunk per file, zero body
deletions/modifications (diff-proven). The POC banner carries the pin-3
forward pointer: the Normalization and Attribution Report (§9, "MC evidence
base") subsequently updated the §12 per-court readiness verdicts; the
verdicts stand unedited as part of the record. Banners contain zero counts
and no run UUIDs beyond what each doc already carried; current coverage is
pointed at the live application's `/data-coverage` page, path only, no
hostname. No figure or body line changed in either report.

**Pin-5 sweep.** Four grep passes over the committed doc surface
(`git ls-files docs README.md`): the only in-class present-tense phrasing is
`docs/normalization-attribution-report.md:54` ("now stands at:"), inside the
banner-covered report — body untouched per pin 1, the banner's
"including any phrased in the present tense" clause covers it.
`docs/held-for-court-fix-runbook.md` lines 23/29/34/215/218 (corpus counts
7,758; 9,932/30,285) ruled NOT in class by planning chat: provenance-anchored
runbook counts pinned to named baseline runs with in-doc STOP-and-restate
guards, report-only, no edits, no follow-up task. All remaining "currently"
hits (README:134, demo-script:6, future-work:17/54, col-intake-protocol:42/79,
refresh-runbook:29, roadmap:5, test-db-guard:56, v1col-data:16) describe
code/config/process, not corpus counts. Zero fixes outside the two banners.

**Copy gate — ADJUDICATED KNOWN-GOOD FINDING (do not re-litigate silently).**
One-off `scanPublicCopy` (31.1/31.2a mechanism: built `@pca/shared` dist over
whitespace-collapsed doc text). POC report: CLEAN, 0 violations.
Normalization report: exactly two hits — `term=odds`, `term=predict stem` —
both at the doc's own pre-existing honesty-bar sentence ("No prediction,
ranking, odds, or legal-advice framing.", body line 19 post-banner),
adjudicated in planning chat 2026-07-15 as MENTION-NOT-USE in a frozen
record: the flagged sentence is the negated policy statement itself; the
mechanical gate did its designed job (flag stems for human framing review)
and the human gate passes this sentence. Banner-neutrality proven by the
identical scan over pre-banner HEAD: identical two hits, zero delta (index
shift 485/506 → 1087/1108 matches the banner's collapsed length —
corroborating evidence; the diff hunks are the prepend-only authority).
AC 4 was amended by planning chat to this exact expectation; any hit beyond
those two, or any delta from HEAD, is STOP. Rejected paths, recorded: body
edit (would falsify "preserved unchanged as recorded" in the same commit
that adds those words); guarded-disclaimer amendment in `copy-safety.ts`
(outside allowed files; landing trigger recorded in the planning-chat
post-launch queue, not this task — no reference to it in banners or docs).

**Files touched.** `docs/normalization-attribution-report.md` (prepend only),
`docs/parser-proof-of-concept.md` (prepend only), `tasks/worklog.md`.

**Deviations from plan.** Two required fixes applied at approval (approved
banner wording superseded the drafts — past-tense framing, no magnitude
claim; staging-completeness run repo-root unscoped). One mid-implementation
STOP (the scanner finding above), adjudicated in planning chat, resumed per
ruling. No other deviations.

**For the next task.** The normalization report's two scanner hits are
adjudicated known-good (mention-not-use); future scans of that file expect
exactly those two hits at the honesty-bar sentence and STOP on any delta.
The copy-safety guarded-disclaimer amendment lives in the planning-chat
post-launch queue. Republish of current-corpus figures reads from
`/data-coverage`, never from edits to these two frozen reports.

## Operational intake — aug2025 window collection (2026-07-15)

Standard COL Intake Protocol run over the collector drop zone after window
collection reached 2025-08-13 (both courts). No code changes; all artifacts
under `~/court-data/`; run report
`reports/aug2025-intake-run-20260715T201916Z.txt`. Counts only below; all
pipeline lines pasted verbatim from tool output.

- **Step-0 recon (pre-intake baseline, reconciled against the 29.3 entry):**
  parsed.dockets=9,932 (4,724 CP / 5,208 MC), parsed.charges=30,285,
  undisposed=6,538, duplicate docket numbers=0; fact run `cc71204b…`
  (12,792 outcomes); published aggregate run `d47dcd20…`.
- **[0] Freeze + [0b] exclusion (snapshot
  `aug2025-window-intake-20260715T201916Z`, manifest beside it; verbatim):**
  `staged_at_freeze=11664 mtime_guard_dropped=3 excluded_already_loaded=8376
  included=3285` (1,108 CP / 2,177 MC).
- **Import (verbatim):** `imported=3282 duplicate=3 invalid=0 failed=0`
  (duplicates = the byte-identical parse_failed trio, as in prior intakes).
- **Extract (verbatim):** `success=3285 partial=0 needs_ocr_or_review=0
  failed=0` (dir `extracted-intake-aug2025-20260715/`).
- **Parse (verbatim):** `parsed=3278 failed=7 skipped=0`
  (dir `envelopes-intake-aug2025-20260715/`).
- **STOP-AND-REPORT + ruling (planning chat, 2026-07-15):** 4 NEW parse
  failures beyond the known trio. Ruling: (1) MC ParseError cohort
  `a2779cd9…` / `f16bd8b4…` / `f9bcc008…` quarantined as SUSPECTED VARIANT,
  UNCONFIRMED — parked as a named post-launch investigation (first
  post-launch intake reports recurrence; structural characterization only;
  parser-support vs documented-permanent-class decided there; re-parse if
  support lands). (2) `e72bb960…` (CP) quarantined per the documented
  isolated KeyError class. (3) Restated quarantine count 3 → 7 CONFIRMED.
- **MC May–Aug 2025 denominator (ruling item 4, report-only, derived from
  snapshot manifest + intake envelopes):** 2,177 MC dockets in this intake;
  2,174 parsed clean (all with filed_date in 2025-05-01..2025-08-31); the 3
  quarantined MC sheets have no parsed record so their filed dates are
  underivable — window membership inferred from collection provenance.
- **GOLDEN WRITE NOTE (required per protocol):** `run-fixtures
  --init-goldens` wrote 3,278 absent tier-2 goldens for the new dockets;
  zero existing goldens touched; zero drift. Verbatim: tier1 `match=35
  diverged=0 updated=0 new=0 missing=0`; tier2 `match=0 diverged=0 updated=0
  new=3278 golden_missing=0 failed=7`. Report
  `tier2-report-20260715T212447_542393Z.json`. Exit 1 attributed to the
  documented dirty-on-failed semantics (failed > 0 always non-zero); the 7
  are the adjudicated quarantine set.
- **Load (exit 0, verbatim):** `loaded=3278 skipped_same_version=0
  replaced_newer_version=0 refused_older_version=0 superseded=0
  skipped_stale_superseded=0 failed_envelope_loaded=7 failed_exception=0
  missing_import_record=0 total=3285`. Reconciles with parse (3,278 + 7 ==
  3,285).
- **Corpus:** 9,932 → 13,210 dockets (+1,104 CP → 5,828; +2,174 MC → 7,382),
  charges 30,285 → 41,449, undisposed 6,538 → 9,219. Zero duplicate docket
  numbers; parse_failed documents restated 3 → 7.
- **Fact build (single invocation, run
  `50c7b88b-49fb-47…`, verbatim):** `charges_processed=41449
  facts_written=16511 undisposed_skipped=9219 held_for_court_skipped=15719`,
  `reconcile facts_written+undisposed_skipped+held_for_court_skipped==
  charges_processed: True`; `sentence_facts_written=12329
  components_on_disposed=12329`, `reconcile
  sentence_facts==components_on_disposed: True`. Review-item dedup held
  (new insertions only for new dockets).
- **Aggregates:** generate-aggregates run
  `dfbecb20-9230-4836-b4f9-654f616fcc88` from build run `50c7b88b…`
  (default=latest); console tail (verbatim): `data_range:
  2025-01-01..2026-07-14`. Post-generate `status=in_progress` verified as
  the documented 26.1 lifecycle (validate flips to completed).
  validate-aggregates (verbatim): `verdict=validated`;
  `charge_outcome_aggregates: rows_checked=296 violations=0`;
  `charge_sentencing_aggregates: rows_checked=237 violations=0`;
  `judge_outcome_aggregates: rows_checked=2056 violations=0`;
  `judge_sentencing_aggregates: rows_checked=1831 violations=0`; `run marked
  completed (validated)`. publish-aggregates (verbatim):
  `publish-aggregates run=dfbecb20-9230-48 published` / `prior published run
  d47dcd20-2059-46 invalidated (superseded)`. Exactly one active published
  run verified post-swap.
- **Post-publish spot check (local API against live DB, read-only):**
  charge-results endpoint serves
  `aggregateRunId=dfbecb20-9230-4836-b4f9-654f616fcc88`,
  `lastRefreshed=2026-07-15T21:32:47.268Z`, dateRange end `2026-07-14`
  (sample: theft-by-deception outcomes sampleSize=47).
- **For the next cycle:** quarantine set is now 7 (known trio + `e72bb960…`
  KeyError + the 3-sheet MC ParseError cohort). The cohort is a NAMED
  POST-LAUNCH INVESTIGATION — the first post-launch intake must report
  recurrence; it is NOT folded into expected quarantine. No parser edits
  were made in this cycle per the ruling.

## Task 31.3c — Migration-Runner TLS for External (Prod) Connections (2026-07-15)

**What was built.** Zero runtime code diff — recon proved the pinned driver
(`pg@8.22.0` / `pg-connection-string@2.14.0`) already honors TLS opt-in
end-to-end through the raw `DATABASE_URL` that `db/src/connection.ts` passes
to `pg.Pool` unmodified. Deliverables per the approved plan + planning-chat
rulings: (1) `docs/runbook-go-live.md` amended — Step 3 invocation now
appends `?sslmode=verify-full` (with the joiner assumption stated: `&` if
the external URL ever carries a query string), the Step 3 psql checkpoint
and every prod-touching libpq command in Step 4 (`pg_restore`, prod psql
count check) take a per-command `PGSSLMODE=verify-full PGSSLROOTCERT=system`
prefix (never exported), the Step 4 count-comparison loop was split into two
explicit invocations because the local docker iteration cannot take a
verify-full prefix, and the local-side `pg_dump` is annotated local/non-TLS;
(2) `db/tests/connection-tls.test.ts` — lock test pinning that a
parameter-free URL resolves ssl=false (local/CI opt-in absent) and
`?sslmode=verify-full` resolves to full verification (empty ssl object: no
rejectUnauthorized/checkServerIdentity weakening). The test fails on the
pre-announced pg v9 sslmode semantics change, forcing re-adjudication at
upgrade time.

**TLS chain probe (agent-executed per the amended division of labor;
operator supplied host+port only, never the credential-bearing URL).**
Capability verified first: system OpenSSL 3.6.3 supports `-starttls
postgres` (operator's earlier LibreSSL attempt did not; also zsh ate the
`<placeholder>` as a redirect). Verdict: PASS. Probe A (openssl, stderr
captured): chain `i:C=US, O=Let's Encrypt, CN=R12` → `i:C=US, O=Internet
Security Research Group, CN=ISRG Root X1`, `Verify return code: 0 (ok)`
against system roots. Probe A2: leaf SANs include the wildcard matching the
external host pattern — hostname verification (the verify-full half openssl
alone doesn't prove) holds. Probe B (exact pinned stack: `pg@8.22.0` via
tsx, `?sslmode=verify-full`, dummy user): `error.code=28P01
error.routine=auth_failed` — server-side auth rejection AFTER a completed,
verified handshake, the ruled pass signal. Two tooling false starts (CJS
top-level-await, unresolvable `pg` from scratchpad) are banked as-is and
were not TLS failures. Full verbatim evidence:
`~/court-data/reports/2026-07-15-31.3c-tls-probe.txt` (hostname appears
there only, never in committed artifacts). `sslmode=require` stays banned:
runtime security warning in the pinned version + v9 semantics change.

**Files touched.** `docs/runbook-go-live.md`, `db/tests/connection-tls.test.ts`
(new), `tasks/worklog.md`. `db/src/migrate.ts` and `db/src/connection.ts`
deliberately untouched (pinned decision 3, minimal remedy).

**Deviations from plan.** None from the approved plan as amended by the
execution relay (probe agent-executed; lock test in; strict libpq posture
in; URL-param spelling for Step 3). The Step 4 loop split was the approved
libpq ruling applied correctly rather than literally (a blanket prefix on
the loop would break the local iteration).

**For the next step.** Chops re-runs amended runbook Step 3 (fresh shell,
`read -s`, the `?sslmode=verify-full` invocation) — the psql checkpoint
stays held until Step 3 succeeds. Merge to main may trigger Render service
auto-deploys; expected, not a deviation. `tasks/current-task.md` local edit
belongs to the operator and is not part of this commit.

## Sprint 7 close-out (a) — Go-Live Execution Record (2026-07-15/16)

**Summary.** `docs/runbook-go-live.md` executed end to end against merged
main (Steps 1–10), followed by the post-deploy verification split
(`docs/runbook-verification.md`, agent half + operator-assisted checks).
The product is live at https://philacourtoutcomes.org under the
controlled-launch model: both DNS names proxied through Cloudflare,
encryption mode Full (strict) verified, noindex confirmed on all three
hostname surfaces, both UptimeRobot monitors up, edge rate rule Active,
and the live 429 shape confirmed with a single controlled burst. Render
hostnames and the internal API address appear only in the banked reports,
never here, per the hostname rule.

**STOPs and their rulings (by pointer):**

- **31.3c TLS** — migration-runner TLS for the external connection:
  `?sslmode=verify-full` on the URL for the Node runner; per-command
  `PGSSLMODE=verify-full PGSSLROOTCERT=system` for libpq tools;
  `sslmode=require` banned. See the 31.3c worklog entry above and
  ADR 0004 Addendum item 2; probe evidence banked
  (`2026-07-15-31.3c-tls-probe.txt`).
- **PG17 prerequisite** — local client tools predated PG17; ruled: install
  `postgresql@17` (Homebrew) and gate on the three `--version` checks
  (all reported 17.10). Runbook prerequisites now carry the executable
  gate; install + checkpoint banked verbatim.
- **Step 5 health check** — the health-check path field does not exist on
  Render private services; ruled: platform-default TCP probe, nothing
  health-check-related configured, deploy-green stated under TCP semantics
  only, internal address recorded verbatim as the web service's
  `API_BASE_URL`, `/health` verification moved to the verification
  runbook. See ADR 0004 Addendum item 5.
- **Step 7 sequencing** — ruled: encryption mode Full before any DNS
  records; both `@` and `www` CNAMEs to the web service's actual hostname
  created DNS-only (grey); wait for Render domain verification +
  certificate; flip both to Proxied; Full (strict) as the verified end
  state via the post-deploy one-shot. Zone was fresh, so the AAAA finding
  was moot as ruled. See ADR 0004 Addendum item 3.
- **Step 8 ratification** — ruled: 50 requests / 10 seconds per IP, action
  Block, minimum (10 s) mitigation timeout, Bot Fight Mode OFF — the
  ~300 req/min/IP decision under the plan's fixed counting window. See
  ADR 0004 Addendum item 4.

**Banked artifacts (verbatim console evidence lives there):**
`~/court-data/reports/2026-07-15-go-live-execution.txt`,
`~/court-data/reports/2026-07-15-verification.txt`,
`~/court-data/reports/2026-07-15-31.3c-tls-probe.txt`.

## Sprint 7 close-out (b) — Task 31.4 Exit Demo Record (2026-07-16)

Exit demo run by the operator against the DEPLOYED product per the
sprint-7 plan's twelve-item list; reviewed in the planning chat.

**Items 1–10 and 12: operator-attested**, with corroborating evidence
pointers into the banked reports:

- Item 1 (deployed URL loads; noindex) — three-surface noindex assertions
  banked verbatim (`2026-07-15-verification.txt`, Item 2).
- Items 2–7 (rosters, distributions, thin-data, judge-specific/fallback,
  sentencing-unavailable, held-for-court shape) — demo-script smoke over
  the live domain (C1) plus the read-only endpoint/page checks banked in
  `2026-07-15-verification.txt` (Item 1) and the go-live Step 6/7
  checkpoints.
- Item 8 (methodology + data-coverage honest window, current run
  metadata, no seeded framing) — live data-coverage body banked verbatim
  (go-live report, Step 6 checkpoint and Step 9 pre-check).
- Item 9 (demo script start-to-finish) and item 10 (submission package
  walkthrough) — operator-attested in planning chat.
- Item 12 (full CI green) — every phase-31 PR merged on green; final
  pre-close merge was PR #55 (2026-07-16).

**Item 11: evidenced verbatim** (banked addendum, copy-pasted from
`2026-07-15-verification.txt`):

```
=== Addendum (authorized) — test-database-guard deliberate-failure demonstration ===
$ cd db && DATABASE_URL=postgres://pca:pca_local_dev_password@localhost:5433/pca vitest run   # LOCAL non-test dbname, never prod
Error: db vitest globalSetup: refusing to run against database "pca" — the name does not match the test-database pattern (contains "test", or is the CI database pca_ci). DB-backed test runs seed reference data and delete-and-reinsert aggregate rows, and must never touch a live database. Point DATABASE_URL at a dedicated test database (e.g. pca_test).
 ❯ assertTestDatabaseUrl src/test-db-guard.ts:26:11
 ❯ Object.globalSetup [as setup] vitest.global-setup.ts:9:50
 ❯ TestProject._initializeGlobalSetup ...
exit-code=1 ; zero test files executed (abort at globalSetup, before any suite or DB write)
```

## Sprint 7 close-out (c) — Sprint-Close Record + Retroactive Items (2026-07-16)

**Sprint 7 is COMPLETE.** Exit demo closed in the planning chat; this
close-out branch is the sprint's final motion.

**Post-launch queue (opened at close):**

1. Collection cadence decision.
2. Indexing decision (whether/when to lift noindex).
3. Admin review tooling (ADR 0003 revisit).
4. Taxonomy-tables landing trigger.
5. MC defendant-block variant investigation — trigger: recurrence on the
   next intake (quarantined SUSPECTED VARIANT, UNCONFIRMED; quarantine
   count 7).
6. Copy-safety guarded-disclaimer rider.
7. Option B publish-to-target machinery (source/target split).
8. Run-report file emission (ADR 0004 Decision 12 deferral).
9. UptimeRobot ToS primary-source read (ADR 0004 Addendum item 8).
10. Raw-PDF retention (Sprint 9).
11. `.env` retention ruling RECORDED: retain — `PROD_DATABASE_URL` kept
    under its isolated name (never `DATABASE_URL`) in the local
    gitignored `.env` only; placeholder documented in `.env.example`.

**Retroactive record (item 8a) — the owed worklog-PR merge verification.**
Pulled via git/gh (verbatim):

```
PR #54 operational intake: aug2025 window collection — worklog restatement — state=MERGED mergedAt=2026-07-15T22:05:23Z mergeCommit=363cdf26cb655db5827f946e9a4325c43df3de7f head=intake-aug2025-window
363cdf2 IS ancestor of origin/main
```

**Retroactive record (item 8b) — the import-duplicates trio.** Question:
were the aug2025 intake's 3 import duplicates the known trio's previously
imported documents? **Answer: YES.** From the banked report
(`aug2025-intake-run-20260715T201916Z.txt`, verbatim line):

```
[1] import:   imported=3282 duplicate=3 invalid=0 failed=0
```

Corroboration (counts and hash-prefixes only): intersecting the included
file hashes of the three intake snapshot manifests (aug2025 ∩ apr2025 =
3; aug2025 ∩ COL-4b = 3; triple intersection = 3) isolates exactly three
documents — hash-prefixes `cb57fc53`, `de1eef8a`, `f5272c0f` — and the
local DB shows all three as `raw.source_documents` rows with
`status=parse_failed`, first imported 2026-07-13 (verbatim, SELECT-only):

```
cb57fc53|2026-07-13 18:02:21.362178+00|parse_failed
de1eef8a|2026-07-13 18:02:21.619103+00|parse_failed
f5272c0f|2026-07-13 18:02:21.544592+00|parse_failed
```

The 3 duplicates are the byte-identical parse_failed trio re-flowing (they
never load into `parsed`, so the freeze's already-loaded exclusion can
never drop them), consistent with every prior intake's attribution.

**Files touched by this close-out branch.** `README.md` (live-URL line),
`apps/web/next.config.ts` (comment-only stale "Sprint 9" fix),
`docs/runbook-go-live.md` (prerequisite version gate; storage/autoscaling
ruled values; Step 5 TCP semantics; Step 7 adjudicated sequencing; Step 8
ratified rule), `docs/runbook-verification.md` (C0 `/health` step with the
shell-guard rider, motivated by the item-4 wrong-shell miss),
`docs/decisions/0004-deployment.md` (Addendum — completes 31.3
implementation AC 8), `.env.example` (`PROD_DATABASE_URL` placeholder),
`tasks/worklog.md` (this record). Riding the branch with authorship noted
in its commit message: the operator's `docs/planning/roadmap.md` edit and
the operator's `docs/planning/sprint-4..7-plan.md` files (per the
operator's go: "include the sprints").

**For the next cycle.** The post-launch queue above is the backlog
opener; the first post-launch intake must report MC ParseError-cohort
recurrence (queue item 5). PR #55's remote branch
(`task-31.3c-migrate-tls`) was left undeleted at merge time — flagged for
cleanup with this branch's PR loop.

## Task filed-date-floor — Filed-Date Floor (Fact-Builder Eligibility Criterion) (2026-07-16)

**What was built.** A config-driven filed-date floor at the fact layer: a
fact is publicly eligible only if its parent docket's `filed_date` is on or
after the floor (default `2025-01-01`); null `filed_date` is fail-closed
ineligible. Applied DIRECTLY in both eligibility evaluators (outcome and
sentencing populations — pinned decision 1), gating `public_eligible` only
(`mvp_eligible` keeps its single event-date meaning; `judge_specific_eligible`
flips transitively as its subset — plan-review adjudication 2). Two new
plan-approved reason codes, mutually exclusive arms shared by both grains:
`filed_date_before_floor` and `filed_date_missing`. Vocabulary is
code-resident (`text[]`, no CHECK) — no migration. Config is
`FILED_DATE_FLOOR_DEFAULT` beside `MVP_WINDOW_START` (deliberately NOT
consolidated with the aggregation-time `DATA_START_DATE_DEFAULT` — the
event-date window is untouched, decision 5), overridable via a new
`build-facts --filed-date-floor` flag; the effective floor prints in the run
summary (`filed_date_floor=…`) and persists in the run's counts JSON. Facts
are still built for floored dockets — only the eligibility dimension flips.

**Files touched.** `services/pipeline/src/pipeline/fact_review_vocab.py`,
`facts/outcome_facts.py`, `facts/sentence_facts.py`, `facts/build_facts.py`,
`cli.py`; tests: `test_facts_outcome_eligibility.py` (evaluate-wrapper +
boundary/null/mutual-exclusivity/config-driven/stacking tests),
`test_facts_sentence_eligibility.py` (goldens pinned in-window, unchanged;
direct floor tests incl. floor+parent stacking), `test_facts_build_facts.py`
(seed gains in-window `filed_date` on docket 1 + a pre-floor docket seq 9 and
a null-filed docket seq 10), `test_fact_review_vocab.py` (vocabulary lock
16 → 18 — adjudicated as the mechanism working, not scope creep).

**Public-gate sufficiency (plan Addition A).** All four public aggregate
populations filter on the gated flags — `aggregates/generate.py:299`
(`public_eligible`, outcomes), `:393` (`judge_specific_eligible`), `:488`
(`public_eligible`, sentencing), `:592` (`judge_specific_eligible`); none
keys off `mvp_eligible`. Reason codes feed internal run-report tallies only
(`generate.py:302/491`); zero references in `apps/api/src` /
`packages/shared/src`.

**Verification rebuild (adjudicated ACCEPTED 2026-07-16).** New unpublished
fact run `eb7022ed-1f65-4701-81c9-1cafee577847` vs baseline `50c7b88b…`;
verbatim console + all six delta proofs banked at
`~/court-data/reports/filed-date-floor-rebuild-20260716T231545Z.txt`. Corpus
freeze held (no import/load; join orphans 0). Headline verbatim lines:

```
filed_date_floor=2025-01-01
charges_processed=41449 facts_written=16511 undisposed_skipped=9219 held_for_court_skipped=15719
mvp_eligible=8590 public_eligible=6578 judge_specific_eligible=6395 review_needed=5658
P2 public flips eligible->ineligible=399 reverse=0 flips_without_new_floor_code=0   (outcome)
P4 flip census by filed year x court: {('2023', 'CP'): 398, ('2024', 'CP'): 1}      (outcome)
P2 public flips eligible->ineligible=418 reverse=0 flips_without_new_floor_code=0   (sentence)
P4 flip census by filed year x court: {('2023', 'CP'): 416, ('2024', 'CP'): 2}      (sentence)
P5 mvp_eligible deltas=0 review_needed deltas=0                                      (both)
```

Outcome flips = 399 = the D4 snapshot expectation exactly (6,977 − 399 =
6,578 reconciles). Sentence-side `sentence_parent_code_additions=477` ruled
attributed-and-approved (transitive stacking; 418 flipped + 59 already
ineligible gaining codes without flipping); proof-6 wording amended for the
record to permit `parent_outcome_ineligible` on facts whose parent flipped
via the floor. Null-`filed_date` census: 0 dockets (fail-closed arm live,
tested, unexercised). Run `eb7022ed…` retained as evidence; published
aggregate run `dfbecb20…` untouched and active; no
generate/validate/publish executed.

**Gates (post-staging, caches cleared).** `ruff check` clean; `ruff format
--check` clean (127 files); `pytest -q` 1009 passed / 1 skipped
(pre-existing local fixture skip; DB-backed fact suites green against
`pca_pipeline_test`); repo-root `pnpm format:check` clean; `pnpm typecheck`
clean. Staging gate: all 9 files staged, no untracked/ignored files under
the task paths.

**Deviations from plan.** One: `test_fact_review_vocab.py` (the committed
vocabulary-lock test) was not on the plan's file list; updating it is
inherent to the approved vocabulary addition and was accepted at
adjudication.

**For the next task.** The next fact-build baseline for delta work is
`eb7022ed…` (adjudication, standing notes). Corpus freeze lifted at
adjudication, but intake stays held: the banked sequence runs the
map-addition task (own freeze) before intake → rebuild → republish (step-2
copy rides that window). Also banked from #55: remote branch
`task-31.3c-migrate-tls` was left undeleted — cleaned up (or reported)
with this branch's PR loop.
