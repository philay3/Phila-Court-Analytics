# Task 5.2 — GitHub Actions CI

## Goal

Add a baseline CI workflow that runs on every pull request and on pushes to `main`, covering both the Node/TypeScript monorepo and the Python pipeline. CI must fail on lint, format, typecheck, test, taxonomy validation, or migration errors. Also fix the deferred sequential `pnpm dev` issue from task 4.1.

## Context

- Monorepo: pnpm workspaces, Node 22 LTS, TypeScript strict, ESLint 9 flat config + Prettier, Vitest.
- Workspaces: `apps/api` (Fastify), `apps/web` (Next.js), `packages/taxonomy`, `packages/shared`, `services/pipeline` (Python, uv-managed).
- Taxonomy `generated/` artifacts are gitignored — a fresh clone must run the root generate step before typecheck/test can pass. CI is the first true fresh-clone consumer; use the existing root generate mechanism established in 3.1/3.2.
- Python pipeline uses uv (`uv.lock` committed), ruff for lint + format, pytest. Harness tests use synthetic PDFs generated at test time — CI needs no fixture files.
- Local Postgres is pinned to `postgres:17.10` (standing decision: CI must use a 17.x service container). Local host port 5433 is a host-conflict convention only; inside the CI runner use the default 5432.
- Kysely migration runner exists with a root migration script (from 2.2/2.3); use the existing script name.

Before writing any code, respond with an implementation plan per CLAUDE.md.

## Scope

### 1. Workflow file

`.github/workflows/ci.yml`:

- Triggers: `pull_request` (all branches) and `push` to `main`.
- Concurrency group keyed on workflow + ref, `cancel-in-progress: true`, so superseded pushes don't waste runner minutes.
- Pin all GitHub Actions to major version tags (e.g. `actions/checkout@v4`). Document the chosen versions in the plan.
- No repository secrets may be required or referenced. Postgres service credentials are throwaway dummy values defined inline in the workflow — that is acceptable and not a secrets violation.

### 2. Node job

Runs on `ubuntu-latest` with a `postgres:17.10` service container (dummy user/password/db, health check via `pg_isready` options, exposed on 5432).

Steps, in order:

1. Checkout.
2. Set up pnpm — derive the version from the repo's `packageManager` field (corepack or `pnpm/action-setup`), not a hardcoded duplicate.
3. Set up Node 22 with pnpm store caching.
4. `pnpm install --frozen-lockfile`.
5. Root taxonomy generate step (existing mechanism).
6. Lint (`pnpm lint`).
7. Format check (`pnpm format:check`).
8. Typecheck (`pnpm typecheck`).
9. Taxonomy validation (existing validation script).
10. Tests (`pnpm test`).
11. Apply migrations against the service container (existing migration script, `DATABASE_URL` pointing at the service). This proves migrations apply cleanly on a fresh database.

If the repo's existing root scripts differ in name from the above, use the existing names — do not rename root scripts in this task.

### 3. Python job

Runs in parallel with the Node job, working directory `services/pipeline`:

1. Checkout.
2. Set up uv (official `astral-sh/setup-uv` action) with caching, Python version from `.python-version`.
3. `uv sync` with frozen/locked resolution.
4. `uv run ruff check .`
5. `uv run ruff format --check .`
6. `uv run pytest`

### 4. Fix sequential `pnpm dev` (deferred from 4.1)

Update the root `dev` script so workspace dev servers run in parallel (e.g. `pnpm -r --parallel dev` or equivalent). Verify locally that `pnpm dev` starts both the API and web dev servers concurrently and that Ctrl+C cleanly stops both.

### 5. Documentation

- Add a CI status badge to the root README.
- Add a short `docs/ci.md` (or a section in an existing tooling doc — agent's choice, state it in the plan): what CI runs, in what order, why the taxonomy generate step precedes typecheck, and the Postgres service container convention (17.x pin, 5432 in CI vs 5433 locally).

### 6. Worklog

Append `tasks/worklog.md` entry on completion (after human confirmation, per standing workflow).

## Acceptance criteria

- CI workflow triggers on pull requests and on pushes to `main`.
- Node job: install (frozen lockfile), taxonomy generate, lint, format:check, typecheck, taxonomy validation, tests, and migration apply against a `postgres:17.10` service container — all pass on a green run.
- Python job: uv sync (locked), ruff check, ruff format check, and pytest — all pass on a green run.
- CI fails when any of the above fail (demonstrate reasoning in the plan; no need to push a deliberately broken commit).
- Jobs run in parallel; superseded runs on the same ref are cancelled.
- No secrets referenced or required; no fixture PDFs, extracted text, or docket data needed or touched by CI.
- pnpm version in CI comes from the repo's `packageManager` field (single source of truth).
- `pnpm dev` runs API and web dev servers in parallel.
- README has a CI badge; CI documentation exists.
- Worklog entry appended after confirmation.

## Out of scope

- Deployment or release workflows of any kind
- Docker image builds
- Coverage reporting/upload
- Dependabot/Renovate configuration
- Branch protection rules (GitHub settings — human task)
- E2E/Playwright tests
- Running the extraction harness against real fixtures (that is 5.3, human-run, and real fixtures never enter CI)
- Renaming or restructuring existing root scripts
- Caching Next.js build output

## Files the agent may touch

- `.github/workflows/**` (new)
- Root `package.json` (only: the `dev` script fix)
- Root `README.md` (badge only)
- `docs/**` (CI documentation)
- `tasks/worklog.md` (append, after confirmation)
- Nothing else