# @pca/e2e — end-to-end suite (task 15.2; static since STATIC-2b)

Playwright (chromium) walks every public flow against the **static export** —
built from a **real seeded test database** by the API-reading build script —
served with Cloudflare Pages semantics by **`wrangler pages dev`**. No API
server and no `next start` run during the suite. On every visited page/state
it asserts:

- **accessibility** — axe-core, zero violations at WCAG 2.2 AA
  (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`);
- **copy safety** — `scanPublicCopy` from `@pca/shared` over the rendered text;
- **privacy** — `scanForForbidden` from `@pca/shared/forbidden-scan` (the
  relocated task-10.1 checker) over the rendered text.

Pinned user-facing messages are asserted via `@pca/shared` imports, never
re-typed. Seed slugs live in [`support/constants.ts`](support/constants.ts) and
are read off `db/seeds/` — the deterministic seed set.

## Prerequisites — this suite does NOT provision the database

`pnpm test:e2e` builds the export and serves it. It does **not** create,
migrate, or seed the database. Before running it locally you must, once, with
`DATABASE_URL` pointing at a **test** database on the local Docker Postgres
(port 5433) — for example the database `pca_test`:

```bash
pnpm db:up                 # start local Docker Postgres (port 5433)
pnpm db:migrate:latest     # apply migrations (DATABASE_URL → the test database)
pnpm db:seed               # load the deterministic seed data (same DATABASE_URL)
```

The export is built in `--mode ci`, whose guard accepts only a test-shaped
database name (one containing `test`, or the CI service's `pca_ci`) and
refuses the local canonical database by design. No database port is hardcoded
anywhere in the E2E path; the connection always comes from the environment
(local at 5433, CI job env at 5432).

## Running locally

From the repo root, with `DATABASE_URL` set to the seeded test database:

```bash
E2E_WEB_PORT=8788 pnpm test:e2e
```

That runs `pnpm build:static -- --mode ci` (workspace packages, then the
export to `apps/web/out` with its data files under `out/data/`), then
Playwright. Playwright's `webServer` starts
`wrangler pages dev ../apps/web/out` bound to 127.0.0.1 on `E2E_WEB_PORT`
(default 3000); it honors `_headers`, `_redirects`, and serves the root
`404.html` with a real 404 status, as production does.

`reuseExistingServer` is on locally (off in CI), so point `E2E_WEB_PORT` at a
free port — a dev server already holding 3000 would otherwise be reused as the
target.

## First run only

Install the chromium browser Playwright drives:

```bash
pnpm --filter @pca/e2e exec playwright install chromium
```

CI installs it with `--with-deps` and caches it.
