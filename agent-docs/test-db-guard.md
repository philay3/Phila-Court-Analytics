# Test-Database Guard (task 29.2)

Structural enforcement that DB-backed **test** runs only ever target a test
database. Closes the 28.2 incident class: with the root `.env` pointing at
the live database, `pnpm --filter @pca/api test` or `pnpm --filter @pca/db
test` would silently re-seed reference data and delete-and-reinsert
`analytics.aggregate_runs` rows via the vitest global-setups, which seed by
direct function calls and therefore bypass the 29.1 `db:seed` seed-guard.

## Mechanism

`@pca/db/test-db-guard` (subpath export; `db/src/test-db-guard.ts`) exposes a
pure, name-shaped, pre-connection check:

- a database name passes iff it contains `test` (case-insensitive — the
  established `PIPELINE_TEST_DATABASE_URL` convention) **or** is exactly
  `pca_ci` (the CI service database);
- fail-closed: a URL whose database name cannot be determined is rejected;
- refusal messages name the offending **dbname only** — never the URL, which
  can carry credentials.

Wired into both vitest global-setups, which abort the entire run before any
suite executes:

- `apps/api/vitest.global-setup.ts` — before the direct-call seeding;
- `db/vitest.global-setup.ts` (new) — ahead of the seed suites and the sweep
  scratch-database suite.

## Per-path coverage

| Test entry path                                 | Coverage                                                                                                  |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| API suite (`pnpm --filter @pca/api test`)       | guard in `vitest.global-setup.ts` before seeding; a throw aborts the run before any suite writes          |
| db package suite (`pnpm --filter @pca/db test`) | guard in new `db/vitest.global-setup.ts`; scratch DBs (`pca_sweep_test_<hex>`) match the pattern          |
| E2E job (CI and local `test:e2e`)               | seeds only via real `pnpm db:seed` → 29.1 data-shaped seed-guard; the Playwright suite does not provision |
| Pipeline pytest                                 | pre-existing: reads only `PIPELINE_TEST_DATABASE_URL`; hard-fails unless the dbname contains `test`       |
| shared / web / taxonomy / ui suites             | no database access                                                                                        |

## Local workflow implication

No env-var expectations change. What changes: a `DATABASE_URL` naming a
non-test database (e.g. the live DB auto-loaded from the root `.env`) now
fails the db/API test runs loudly at entry instead of silently seeding.
Export a test-database URL in the shell (shell values take precedence over
the root-`.env` auto-load), e.g. a local `pca_test` created with
`pnpm db:up` + `pnpm db:migrate:latest`.

## Race fix folded in (D-A ruling)

`db/vitest.config.ts` sets `fileParallelism: false`: the reference suite
asserts `ref.*` equals exactly the demo seeds while the roster suites insert
additional `ref.*` rows into the same database, so parallel workers raced.
Sequential execution removes the race. Residual (pre-existing) property worth
knowing: the suite is still file-order-dependent on a fresh database — vitest
orders files by size (cold cache) or prior duration (warm cache), and both
currently run `seeds/reference.test.ts` before the roster suites; an edit
that flips those orderings would surface the same exact-equality failure
deterministically. Flagged at 29.2 completion for planning-chat disposition.
