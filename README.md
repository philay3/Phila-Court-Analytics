# Philadelphia Court Outcomes Analytics

[![CI](https://github.com/philay3/Phila-Court-Analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/philay3/Phila-Court-Analytics/actions/workflows/ci.yml)

Historical, aggregate outcome distributions for criminal charges in the
Philadelphia courts, built from public docket sheets published on the
Pennsylvania Unified Judicial System (UJS) portal.

## What this is (and is not)

The product answers one kind of question: across past Philadelphia criminal
cases, how were charges of a given type resolved, and what sentence types were
recorded — as a distribution over groups of past cases, optionally broken down
by judge. Every figure is a historical aggregate with its sample size shown;
small samples are labeled as thin data rather than hidden.

It is deliberately narrow about what it is not:

- **Not a prediction.** Figures are historical summaries. Past distributions
  do not predict what a court will decide in any current or future case.
- **Not legal advice.** This site does not provide legal advice. Nothing here
  is a substitute for consulting a licensed attorney about a specific
  situation.
- **Not a judge comparison or scoring product.** Results describe groups of
  past cases as a whole, never any individual case, and the product draws no
  conclusions about any judge or court.

The same statements are served to users in the application itself (the
methodology page), enforced by automated copy-safety gates over every public
surface.

## Launch model

The product is built for a controlled launch: site-wide `noindex` (search
engines are deliberately not invited), no promotion, and honest disclosures on
every result surface. Collection is ongoing — coverage begins January 1, 2025,
anchored to disposition and sentencing event dates rather than filing dates,
and figures grow as newly collected records are aggregated. Known limitations
are documented rather than smoothed over: see
[docs/known-limitations.md](docs/known-limitations.md).

## What ships in this repository

Code, migrations, seeds, tests, and documentation — **no court data**. Nothing
derived from real dockets is committed: no docket PDFs, no extracted docket
text, no docket numbers, no defendant-identifying data. Source documents and
pipeline artifacts live outside the repository on the operator's machine and
are referenced only through gitignored, configurable paths.

A fresh clone therefore boots against **deterministic synthetic demo data**,
not real figures. The seed step inserts:

- a small set of demo charges (carrying real Pennsylvania statute names by
  design) and the real public charge and judge rosters — public reference
  information only, with no case data attached;
- a set of obviously fake seed judges (placeholder names that cannot be
  mistaken for real people);
- hand-constructed demo aggregate distributions that attach **only** to the
  demo charges and the fake seed judges. Fabricated statistics are never
  attached to a real judge's name.

Real figures exist only where the collection and aggregation pipeline has been
run over collected court records, which does not happen on a clone. The seed
step is also guarded: it refuses to run against any database that already
contains real corpus data.

## Architecture

A Python pipeline turns collected public docket PDFs into aggregate
statistics: text extraction (pdfplumber), parsing into structured per-docket
records with a closed warning vocabulary, normalization of charges, outcomes,
and judges against curated rosters, and a fact build that decides public
eligibility through explicit boolean gates with machine-readable reason codes
— no confidence scores anywhere. Unmatched or unclear records are excluded and
routed to a review queue; they never reach public data.

Facts are aggregated into immutable, versioned **aggregate runs** in
PostgreSQL (layered schemas: `raw` → `parsed` → `fact`, with `ref` rosters and
`analytics` aggregates). At most one run is published and active at a time;
figures change only by publishing a new run, which is also the rollback model.

A Fastify + TypeScript API serves **only** the aggregate and reference layers
— the public API is aggregate-only by construction, and automated gates scan
every public route for forbidden fields and unsafe copy. A Next.js (App
Router) web application renders the results with the same copy and privacy
gates applied end to end (unit, integration, and Playwright E2E).

## Getting started

Prerequisites:

- Node 22 LTS
- [pnpm](https://pnpm.io/) (repo pins the version via the `packageManager` field)
- Docker Desktop (for local PostgreSQL)
- Python 3.12 — only needed for pipeline development
  ([services/pipeline/README.md](services/pipeline/README.md)); the web app,
  API, and database run without it

Boot the app from a fresh clone:

```sh
git clone https://github.com/philay3/Phila-Court-Analytics.git
cd Phila-Court-Analytics
pnpm install
cp .env.example .env      # local-dev defaults work as-is
pnpm db:up                # PostgreSQL via Docker Compose (host port 5433)
pnpm db:migrate:latest    # apply migrations
pnpm db:seed              # deterministic synthetic demo data (see above)
pnpm build:packages       # build the shared workspace packages once
pnpm dev                  # web on :3000, API on :3001
```

Then open <http://localhost:3000> (web) — the API health check is at
<http://localhost:3001/health>. See [docs/local-setup.md](docs/local-setup.md)
for database details (start/stop/reset, health checks, port overrides).

### Environment files

Each deployable documents its environment in a committed `.env.example`;
local-dev defaults are chosen so a fresh clone runs with a copied root `.env`
and nothing else:

- Root [`.env.example`](.env.example): local Postgres credentials /
  `DATABASE_URL`, plus `DEFENDANT_HASH_SALT` (required by the **pipeline
  only** — the web app, API, and database tooling never read it).
- Web app ([apps/web/.env.example](apps/web/.env.example)): `API_BASE_URL`,
  optional — defaults to `http://localhost:3001`.
- API: no `.env` needed locally; it reads `DATABASE_URL` from the root `.env`
  (via the dev script) and `PORT`/`HOST`/`LOG_LEVEL` are optional with
  defaults.

### Generated artifacts

Some packages emit generated artifacts that other packages import (currently
`@pca/taxonomy`, whose artifacts `@pca/shared` builds its schemas from).
Artifacts are gitignored and rebuilt on demand: `pnpm generate`. Root `test`
runs it first, and root `typecheck` starts by building the workspace packages
(which regenerates taxonomy artifacts), so on a fresh clone the root scripts
work in any order after `pnpm install`. `packages/taxonomy/` is the single source
of truth for outcome and sentencing categories — see
[packages/taxonomy/README.md](packages/taxonomy/README.md).

## Workspace layout

| Path                 | Purpose                                            |
| -------------------- | -------------------------------------------------- |
| `apps/web/`          | Next.js (App Router) public web application        |
| `apps/api/`          | Fastify + TypeScript public API (aggregate-only)   |
| `services/pipeline/` | Python 3.12 docket-processing pipeline             |
| `packages/shared/`   | Shared TypeScript types, schemas, and copy gates   |
| `packages/taxonomy/` | Offense and outcome taxonomy definitions           |
| `packages/ui/`       | Shared React UI components                         |
| `db/`                | PostgreSQL migrations, seeds, and database tooling |
| `e2e/`               | Playwright end-to-end + accessibility suite        |
| `docs/`              | Documentation (see the map below)                  |
| `infra/`             | Infrastructure configuration                       |
| `scripts/`           | Repo maintenance and development scripts           |
| `tests/`             | Cross-package integration and end-to-end tests     |

## Testing

Root scripts run recursively across the workspace: `pnpm lint`,
`pnpm typecheck`, `pnpm test`, `pnpm format:check`. The Python pipeline has
its own three gates (`ruff check`, `ruff format --check`, `pytest`) — see
[services/pipeline/README.md](services/pipeline/README.md).

`e2e/` is a Playwright suite that walks every public flow against a real
seeded database, the API booted from built output, and a production web
build; on every visited page it asserts accessibility (WCAG 2.2 AA), copy
safety, and privacy (forbidden-field scans). It does not provision the
database — run the database steps from Getting started first, then
`pnpm test:e2e`. First run only:
`pnpm --filter @pca/e2e exec playwright install chromium`. See
[e2e/README.md](e2e/README.md).

## Documentation map

- [docs/planning/](docs/planning/) — human-maintained planning documents
  (roadmap, PRD, architecture, sprint plans). Everything else under `docs/`
  is generated or maintained alongside the code.
- [docs/decisions/](docs/decisions/) — architecture decision records (PDF
  extractor selection, source access, admin-review deferral).
- [docs/intake/](docs/intake/) — corpus intake protocol and refresh runbook.
- [docs/local-setup.md](docs/local-setup.md) — local database setup and
  operations.
- [docs/known-limitations.md](docs/known-limitations.md) — the consolidated,
  launch-facing summary of what the data does and does not cover.
- [docs/future-work.md](docs/future-work.md) — named future work with landing
  triggers.
- [docs/demo-script.md](docs/demo-script.md) — the walkthrough script for
  demoing the product.
- [docs/parser-proof-of-concept.md](docs/parser-proof-of-concept.md) and
  [docs/normalization-attribution-report.md](docs/normalization-attribution-report.md)
  — the engineering reports behind the parser and normalization layers, with
  their full disclosures.
- [docs/v1pipeline-arch.md](docs/v1pipeline-arch.md),
  [docs/v1database-schema.md](docs/v1database-schema.md),
  [docs/v1col-data.md](docs/v1col-data.md) — v1 architecture references.

The user-facing methodology is served by the application itself (the
`/methodology` page), so it can never drift from what the product actually
does.

## Known limitations and future work

The honest one-stop summaries: [docs/known-limitations.md](docs/known-limitations.md)
consolidates every disclosure already made in the engineering reports and the
served methodology; [docs/future-work.md](docs/future-work.md) names what is
deliberately not built yet and what would trigger building it.

## Privacy and responsible use

This project handles public court records with strict privacy discipline:

- Raw docket PDFs, extracted docket text, and fixture PDFs are **never
  committed**. Fixtures live outside the repo and are referenced via a
  configurable, gitignored path.
- No defendant names, docket numbers, or other production court data appear
  in the repo, logs, tests, or CI output. Defendant identity exists in the
  pipeline only as a salted hash.
- Secrets and `.env` files with real values are never committed
  (`.env.example` files carry placeholder values only).
- The public API is aggregate-only: raw, parsed, fact, review, and
  source-document data are never exposed, enforced by automated
  forbidden-field scans over every public route.
- User-facing copy never frames results as forecasts of future outcomes,
  never advises on any case, and draws no conclusions about judges — enforced
  by an automated copy-safety scanner over every public surface, including
  this repository's public documents.
