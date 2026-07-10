# Philadelphia Court Outcomes Analytics

[![CI](https://github.com/philay3/Phila-Court-Analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/philay3/Phila-Court-Analytics/actions/workflows/ci.yml)

Aggregate analytics on Philadelphia court case outcomes, built from public docket records.

## Prerequisites

- Node 22 LTS
- [pnpm](https://pnpm.io/) (repo pins the version via the `packageManager` field)
- Python 3.12
- Docker Desktop

## Setup

```sh
git clone <repo-url>
cd philadelphia-court-outcomes
pnpm install
```

Root scripts (recursive across all workspace packages; no-ops until packages define them):

```sh
pnpm dev
pnpm build
pnpm lint
pnpm typecheck
pnpm test
```

### Environment files

Each app documents its own environment in a committed `.env.example`. For local
development the defaults are chosen so a fresh clone runs without any `.env`:

- Database / Docker Compose: see the root [`.env.example`](.env.example) — copy
  to `.env` (`cp .env.example .env`) for the local Postgres credentials.
- Web app (`apps/web`): `API_BASE_URL` is **optional** and defaults to
  `http://localhost:3001`; copy `apps/web/.env.example` to `apps/web/.env` only
  to point the web app at an API on a different host/port. See
  [apps/web/README.md](apps/web/README.md).

## Workspace layout

| Path                 | Purpose                                          |
| -------------------- | ------------------------------------------------ |
| `apps/web/`          | Next.js (App Router) public web application      |
| `apps/api/`          | Fastify + TypeScript public API (aggregate-only) |
| `services/pipeline/` | Python 3.12 docket-processing pipeline           |
| `packages/shared/`   | Shared TypeScript types and utilities            |
| `packages/taxonomy/` | Offense and outcome taxonomy definitions         |
| `packages/ui/`       | Shared React UI components                       |
| `db/`                | PostgreSQL migrations and database tooling       |
| `e2e/`               | Playwright end-to-end + accessibility suite      |
| `docs/`              | Planning and reference documentation             |
| `infra/`             | Infrastructure configuration                     |
| `scripts/`           | Repo maintenance and development scripts         |
| `tests/`             | Cross-package integration and end-to-end tests   |

## Taxonomy

`packages/taxonomy/` (`@pca/taxonomy`) is the single source of truth for outcome
categories, sentencing categories, and thin-data configuration. Seed data lives
in JSON under `packages/taxonomy/seeds/`; generated artifacts are gitignored and
rebuilt on demand:

```sh
pnpm taxonomy:validate   # check seed invariants
pnpm taxonomy:generate   # emit generated/taxonomy.json and generated/index.ts
```

See [packages/taxonomy/README.md](packages/taxonomy/README.md) for details.

## Generated artifacts

Some packages emit generated artifacts that other packages import (currently
`@pca/taxonomy`, whose artifacts `@pca/shared` builds its schemas from). Artifacts are
gitignored and rebuilt on demand:

```sh
pnpm generate   # runs every package's generate script
```

Root `typecheck` and `test` run `pnpm generate` first, so on a fresh clone the root
scripts work in any order after `pnpm install`. When running package-scoped commands
(e.g. `pnpm --filter @pca/shared test`), run `pnpm generate` at the root first.

## End-to-end tests

`e2e/` (`@pca/e2e`) is a Playwright (chromium) suite that walks every public
flow against a **real seeded database**, the **API booted from built output
under plain node**, and the **web app booted from a production build**. On every
visited page it asserts accessibility (axe-core, WCAG 2.2 AA), copy safety
(`scanPublicCopy`), and privacy (`scanForForbidden`).

The suite **does not provision the database**. Set up the local database once
before running it:

```sh
pnpm db:up               # local Docker Postgres (port 5433)
pnpm db:migrate:latest   # apply migrations
pnpm db:seed             # deterministic seed data
```

Your local `DATABASE_URL` (root `.env`, port 5433) must be in place — no DB port
is hardcoded in the E2E path; the connection comes from the environment (CI uses
5432). Then, from the repo root:

```sh
pnpm test:e2e            # builds packages + API + web, then runs Playwright
```

First run only, install the browser: `pnpm --filter @pca/e2e exec playwright
install chromium`. See [e2e/README.md](e2e/README.md) for details.

## Privacy rules

This project handles public court records with strict privacy discipline:

- Fixture PDFs, raw docket PDFs, and extracted docket text are **never committed**. Fixtures live outside the repo and are referenced via a configurable, gitignored path.
- Secrets and `.env` files with real values are never committed (`.env.example` is the only committable env file).
- No defendant names, docket numbers, or other production court data in the repo, logs, tests, or CI output.
