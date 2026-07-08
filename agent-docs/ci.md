# CI

The CI workflow lives at `.github/workflows/ci.yml`. It runs on every pull request and
on pushes to `main`. Two jobs run in parallel; a failure in either fails the run.
Superseded runs on the same ref are cancelled (`concurrency` with
`cancel-in-progress: true`).

No repository secrets are required or referenced. CI never touches fixture PDFs,
extracted docket text, or any court data — the pipeline tests generate synthetic PDFs
at test time.

## Node job

Runs on `ubuntu-latest` with a Postgres service container, `timeout-minutes: 15`.

Steps, in order:

1. Checkout.
2. pnpm setup — `pnpm/action-setup@v4` with no version input, so the pnpm version comes
   from the root `packageManager` field (single source of truth).
3. Node 22 with pnpm store caching.
4. `pnpm install --frozen-lockfile`
5. `pnpm generate`
6. `pnpm lint`
7. `pnpm format:check`
8. `pnpm typecheck`
9. `pnpm taxonomy:validate`
10. `pnpm test`
11. `pnpm db:migrate:latest` against the service container
    (`DATABASE_URL=postgresql://ci:ci@localhost:5432/pca_ci`).

### Why generate precedes typecheck

The taxonomy package's `generated/` artifacts are gitignored. CI checks out a fresh
clone, so those artifacts do not exist until the root generate step runs; typecheck and
test would fail on missing modules without it. (`typecheck` and `test` also invoke
`generate` internally — the explicit step exists for clear failure attribution, and the
re-runs are idempotent.)

## Python job

Runs in `services/pipeline`, `timeout-minutes: 15`:

1. Checkout.
2. `astral-sh/setup-uv@v6` with caching keyed on `services/pipeline/uv.lock`. The Python
   version is resolved by uv from `services/pipeline/.python-version` — no duplicated
   version string in the workflow.
3. `uv sync --locked` — fails if `uv.lock` is missing or out of date with
   `pyproject.toml`.
4. `uv run ruff check .`
5. `uv run ruff format --check .`
6. `uv run pytest`

## Postgres service container convention

- Image is pinned to `postgres:17.10` (standing decision: CI uses a 17.x pin matching
  local `docker-compose.yml`).
- Credentials are throwaway dummy literals defined inline in the workflow
  (`ci` / `ci` / `pca_ci`). They protect nothing and are not secrets.
- Inside the CI runner Postgres listens on the default **5432**. The local convention of
  host port **5433** exists only to avoid conflicts with other Postgres instances on a
  developer's machine; it does not apply in CI.
- The container has a `pg_isready` health check, so the job's steps only start once the
  database accepts connections.

## Note for future deploy workflows

`cancel-in-progress: true` also cancels in-flight runs on `main` when a newer push
lands. That is fine while CI is checks-only, but if a deploy workflow ever hangs off
this workflow (or reuses the concurrency group), cancelling a half-finished `main` run
becomes a footgun — revisit the concurrency settings at that point.
