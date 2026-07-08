# Philadelphia Court Outcomes Analytics

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

## Privacy rules

This project handles public court records with strict privacy discipline:

- Fixture PDFs, raw docket PDFs, and extracted docket text are **never committed**. Fixtures live outside the repo and are referenced via a configurable, gitignored path.
- Secrets and `.env` files with real values are never committed (`.env.example` is the only committable env file).
- No defendant names, docket numbers, or other production court data in the repo, logs, tests, or CI output.
