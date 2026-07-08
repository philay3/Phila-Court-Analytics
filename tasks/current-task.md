# Task 2.1 — Local Docker Compose + PostgreSQL

## Goal

Add a local PostgreSQL development environment via Docker Compose, with documented environment variables and local setup instructions. After this task, a developer can run one command and have a healthy, persistent local Postgres instance ready for the migration work in Task 2.2.

## Context

- Monorepo (1.1), TS base tooling (1.2), and the Fastify API shell (1.3) are complete.
- The API does NOT connect to the database in this task. Kysely, migrations, and schema creation are Tasks 2.2 and 2.3.
- Backlog reference: FDN-002.1 (Add Local Docker Compose).
- Standing stack: PostgreSQL, Kysely (later), Node 22, pnpm workspaces.
- Privacy posture: `.env.*` is already gitignored from 1.1. Only `.env.example` is committed, containing local-dev defaults and no real secrets.

## Scope

1. **`docker-compose.yml` at repo root** containing a single `postgres` service:
   - official `postgres` image pinned to a specific version tag (propose the pin in your plan — see open questions)
   - named volume for data persistence (survives `docker compose down`, cleared only by `down -v`)
   - healthcheck using `pg_isready`
   - port mapping to the host (propose default vs non-default host port in your plan)
   - database name, user, and password sourced from environment variables with sensible local defaults
2. **`.env.example` at repo root** (create or extend if one exists) with all DB variables:
   - discrete vars (host, port, db, user, password) AND a composed `DATABASE_URL`, so both styles are available to later tasks
   - placeholder/local-dev values only — nothing secret
3. **Root convenience scripts** in `package.json`:
   - `db:up` (detached), `db:down`, `db:logs` (or equivalent — propose names)
4. **Local setup documentation**: either a `docs/local-setup.md` section or README update covering:
   - prerequisite: Docker Desktop installed and running
   - copy `.env.example` → `.env`
   - start/stop/reset commands
   - how to verify the DB is healthy (e.g. `docker compose ps` showing healthy, or a `psql`/`pg_isready` one-liner)
5. **Object storage emulator**: NOT included. Add one sentence to the setup docs noting it is deferred until the pipeline needs it (per backlog FDN-002.1 "included or documented" — we choose documented).

## Acceptance criteria

- [ ] `docker compose up -d` (or the `db:up` script) starts PostgreSQL locally
- [ ] Postgres image is pinned to a specific version (no `latest`)
- [ ] Container reports healthy via its healthcheck
- [ ] Data persists across `docker compose down` + `up` (named volume)
- [ ] `.env.example` exists at root with all DB variables and a `DATABASE_URL`, local placeholder values only
- [ ] `.env` is gitignored (verify existing pattern covers it; do not weaken it)
- [ ] Root scripts `db:up` / `db:down` / `db:logs` (or agreed names) work
- [ ] Local setup docs cover prerequisites, first-run steps, start/stop/reset, and health verification
- [ ] Object storage emulator deferral is documented in one sentence
- [ ] `pnpm lint`, `pnpm typecheck`, and `pnpm test` still pass (nothing should break, but verify)
- [ ] No secrets, no production values, no credentials beyond local-dev placeholders committed

## Out of scope

- Kysely installation or configuration (Task 2.2)
- Migration runner or any migrations (Tasks 2.2 / 2.3)
- Creating any schemas or tables (Task 2.3)
- Connecting the Fastify API to the database (later task)
- Object storage emulator (documented deferral only)
- CI changes (Phase 5)
- Multiple compose profiles, prod compose files, or container orchestration beyond local dev

## Files the agent may touch

- `docker-compose.yml` (new, repo root)
- `.env.example` (new or extended, repo root)
- `package.json` (root — scripts only)
- `docs/local-setup.md` (new) or `README.md` (setup section) — state which in your plan
- `.gitignore` (only if a required ignore pattern is missing — call it out)
- `tasks/worklog.md` (append entry on completion)

## Notes / open questions for the agent's plan

- **Postgres version pin**: propose a specific tag (e.g. `postgres:17.x` vs `16.x`) and justify. We want a current major that Kysely and the analytics workload are happy with; no `latest`, no unversioned major-only tag unless you argue for it.
- **Host port**: propose 5432 vs a non-default port (e.g. 5433) to avoid collisions with any host-installed Postgres. State the tradeoff.
- **Env var naming**: propose the exact variable names (e.g. `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL`) and how compose consumes them (`env_file` vs `environment` with `${VAR:-default}` interpolation). Keep it compatible with what Kysely will need in 2.2.
- **Volume naming**: propose the named volume convention.
- Remember the standing rule: return your implementation plan before writing any code.

---

## Status

- Handed off: [date]
- Plan approved: pending
- Completed: pending