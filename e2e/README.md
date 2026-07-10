# @pca/e2e — end-to-end suite (task 15.2)

Playwright (chromium) walks every public flow against a **real seeded
database**, the **API booted from built output under plain node**, and the
**web app booted from a production build**. On every visited page/state it
asserts:

- **accessibility** — axe-core, zero violations at WCAG 2.2 AA
  (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`);
- **copy safety** — `scanPublicCopy` from `@pca/shared` over the rendered text;
- **privacy** — `scanForForbidden` from `@pca/shared/forbidden-scan` (the
  relocated task-10.1 checker) over the rendered text.

Pinned user-facing messages are asserted via `@pca/shared` imports, never
re-typed. Seed slugs live in [`support/constants.ts`](support/constants.ts) and
are read off `db/seeds/` — the deterministic seed set.

## Prerequisites — this suite does NOT provision the database

`pnpm test:e2e` only **builds and starts** the servers. It does **not** create,
migrate, or seed the database. Before running it locally you must, once:

```bash
pnpm db:up                 # start local Docker Postgres (port 5433)
pnpm db:migrate:latest     # apply migrations
pnpm db:seed               # load the deterministic seed data
```

Your local `DATABASE_URL` (root `.env`, pointing at port **5433**) must be in
place — the API reads it via its `--env-file-if-exists` start path. No database
port is hardcoded anywhere in the E2E path; the connection always comes from the
environment (local `.env` at 5433, CI job env at 5432).

## Running locally

From the repo root:

```bash
pnpm test:e2e
```

That builds the workspace packages, the API, and the web production build, then
runs Playwright. Playwright's `webServer` starts:

- **API** — `pnpm --filter @pca/api run start` (plain node, built `dist`), port
  **3001**, readiness `GET /health`;
- **web** — `pnpm --filter @pca/web run start` (`next start`), port **3000**,
  with `API_BASE_URL=http://127.0.0.1:3001` set explicitly.

`reuseExistingServer` is on locally (off in CI), so an already-running dev
server on those ports is reused.

## First run only

Install the chromium browser Playwright drives:

```bash
pnpm --filter @pca/e2e exec playwright install chromium
```

CI installs it with `--with-deps` and caches it.
