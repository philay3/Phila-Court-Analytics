# Implementation Backlog

## Backlog Scope

This backlog covers the first three implementation milestones:

1. Foundation
2. Seeded Public UI/API
3. Parser Proof of Concept

## Milestone 1: Foundation

### Epic FDN-001: Repository and Monorepo Setup

#### FDN-001.1 Initialize Monorepo

Acceptance Criteria:

- repository includes `apps/web`, `apps/api`, `services/pipeline`, `packages/shared`, `packages/taxonomy`, `db`, `docs`, `infra`, and `scripts`
- `pnpm-workspace.yaml` exists
- root scripts exist for dev, build, lint, typecheck, and test
- README includes local setup
- no secrets or production data committed

#### FDN-001.2 Configure TypeScript Base Tooling

Acceptance Criteria:

- `tsconfig.base.json` exists
- strict TypeScript mode enabled
- app/package configs extend base config
- linting and formatting configured

#### FDN-001.3 Add Basic CI Workflow

Acceptance Criteria:

- CI runs on pull requests
- CI runs install, lint, typecheck, tests, and taxonomy validation
- CI fails on typecheck or lint errors

### Epic FDN-002: Local Development Environment

#### FDN-002.1 Add Local Docker Compose

Acceptance Criteria:

- local PostgreSQL starts
- optional object storage emulator included or documented
- `.env.example` files exist
- local setup documented

#### FDN-002.2 Add Database Migration System

Acceptance Criteria:

- Kysely Migrator configured
- initial migration creates schemas: raw, parsed, ref, fact, analytics, review, audit, auth
- migration command runs locally
- migration docs added

#### FDN-002.3 Add Initial Database Tables

Acceptance Criteria:

- initial reference and aggregate tables exist
- aggregate tables support sample size, date range, thin-data flag, taxonomy version, and aggregate run ID

### Epic FDN-003: Taxonomy Foundation

#### FDN-003.1 Create Taxonomy Package

Acceptance Criteria:

- `packages/taxonomy` exists
- outcome, sentencing, thin-data seed files exist
- validation script exists
- generated TypeScript and JSON artifacts exist

#### FDN-003.2 Seed Outcome Categories

Acceptance Criteria:

- dismissed, withdrawn, guilty plea, guilty verdict, acquittal, ARD, diversion, other, and unknown categories exist
- categories have stable code, display name, definition, sort order, and public flag

#### FDN-003.3 Seed Sentencing Categories

Acceptance Criteria:

- probation, incarceration, fine, restitution, community service, no further penalty, costs/fees, other, and unknown categories exist
- categories have stable code, display name, definition, sort order, and public flag

### Epic FDN-004: Shared API Contracts

#### FDN-004.1 Create Shared Types Package

Acceptance Criteria:

- `packages/shared` exists
- public API response types exist
- public result types require sample size, date range, thin-data status, taxonomy version, counts, and percentages

#### FDN-004.2 Add Runtime Validation Schemas

Acceptance Criteria:

- validation library selected
- public schemas exist
- API imports schemas
- frontend imports shared types

### Epic FDN-005: Application Shells

#### FDN-005.1 Create Web App Shell

Acceptance Criteria:

- Next.js app starts locally
- public informational routes exist
- admin placeholder route exists
- no predictive/legal-advice language appears

#### FDN-005.2 Create API Shell

Acceptance Criteria:

- Fastify API starts locally
- `/health` exists
- request ID middleware exists
- central error handler exists
- public/admin route namespaces exist

#### FDN-005.3 Create Python Pipeline Shell

Acceptance Criteria:

- Python project exists
- CLI entrypoint exists
- pytest runs
- placeholder commands exist for import, extraction, parse, and fixtures

## Milestone 2: Seeded Public UI/API

### Epic PUB-001: Seeded Public Data

#### PUB-001.1 Create Seeded Aggregate Dataset

Acceptance Criteria:

- at least three charges
- at least two judges
- aliases
- charge-only aggregates
- judge-specific aggregates
- sentencing aggregates
- thin-data example
- unavailable judge-specific scenario

#### PUB-001.2 Seed Definitions and Methodology Content

Acceptance Criteria:

- outcome definitions available
- sentencing definitions available
- methodology summary exists
- responsible-use copy exists
- copy avoids prediction, odds, legal advice, and ranking language

### Epic PUB-002: Public Search API

#### PUB-002.1 Implement Charge Search

Endpoint:

`GET /api/v1/public/charges/search`

Acceptance Criteria:

- searches normalized charges and aliases
- returns public charge suggestions
- no raw data
- validates query and limit
- tests included

#### PUB-002.2 Implement Judge Search

Endpoint:

`GET /api/v1/public/judges/search`

Acceptance Criteria:

- searches normalized judges and aliases
- returns public judge suggestions
- judge remains optional
- no raw data
- tests included

### Epic PUB-003: Public Result API

#### PUB-003.1 Implement Charge-Only Result

Endpoint:

`GET /api/v1/public/results/charge/{chargeId}`

Acceptance Criteria:

- returns Philadelphia-wide outcome and sentencing distributions
- includes sample size, date range, thin-data status, taxonomy version, last refreshed date
- counts and percentages returned together
- no raw, parsed, fact, review, audit, or source data exposed

#### PUB-003.2 Implement Judge-Specific Result

Endpoint:

`GET /api/v1/public/results/charge/{chargeId}/judge/{judgeId}`

Acceptance Criteria:

- returns judge-specific result
- returns Philadelphia baseline
- includes separate sentencing sample size
- no ranking/predictive labels
- tests included

#### PUB-003.3 Implement Judge-Specific Unavailable Response

Acceptance Criteria:

- structured unavailable response
- charge-only fallback
- safe public message
- tests included

### Epic PUB-004: Public Search Flow

Stories:

- homepage search
- charge autocomplete
- optional judge autocomplete

Core acceptance:

- charge primary
- judge optional
- keyboard accessible
- no predictive language

### Epic PUB-005: Public Result Pages

Stories:

- charge-only result page
- judge-specific result page
- unavailable states

Core acceptance:

- sample size visible
- date range visible
- thin-data state visible
- responsible-use copy visible
- mobile-friendly
- no legal advice/prediction framing

### Epic PUB-006: Result Display Components

Stories:

- outcome distribution section
- sentencing distribution section
- baseline comparison section
- sample size and thin-data components

Core acceptance:

- charts paired with tables
- counts and percentages visible
- sample sizes visible
- no color-only meaning

### Epic PUB-007: Public Content Pages

Stories:

- definitions page
- methodology page
- data coverage page

### Epic PUB-008: Public Privacy and Contract Tests

Stories:

- public API forbidden-field tests
- public copy guard tests

## Milestone 3: Parser Proof of Concept

### Epic POC-001: Parser Fixture Corpus

Stories:

- collect representative PDF fixtures
- define golden output format

### Epic POC-002: Manual Import and Storage

Stories:

- implement manual PDF import
- add import tests

### Epic POC-003: Text and Layout Extraction

Stories:

- implement text extraction
- evaluate PyMuPDF, pdfplumber, and pypdf

### Epic POC-004: Docket and Charge Parsing

Stories:

- parse docket metadata
- parse charge rows

### Epic POC-005: Judge, Disposition, and Sentence Parsing

Stories:

- parse judge events
- parse dispositions
- parse sentencing text

### Epic POC-006: Normalization Proof of Concept

Stories:

- normalize charges
- normalize judges
- normalize outcomes and sentencing categories

### Epic POC-007: Charge-Level Attribution Proof of Concept

Stories:

- attribute outcomes to charges
- attribute sentences to charges

### Epic POC-008: Review Queue Generation

Story:

- generate review items from low-confidence records

### Epic POC-009: Fixture Aggregate Generation

Stories:

- generate fixture aggregates
- validate aggregate outputs

## Cross-Milestone Release Blockers

- public forbidden-field tests pass
- public copy avoids prediction/legal-advice/judge-ranking language
- sample size appears on every figure
- thin-data state is visible
- judge-specific result has Philadelphia baseline
- sentencing distribution uses separate sentencing sample size
- raw PDFs and extracted text remain private
- parser proof of concept validates launch scope
- source-access/compliance review complete before broad ingestion

MVP data coverage starts on January 1, 2025. Outcome aggregates include eligible charge-level outcomes with disposition dates on or after January 1, 2025. Sentencing aggregates include eligible charge-level sentence facts with sentencing dates on or after January 1, 2025. Earlier-filed cases may be included if the relevant disposition or sentencing event occurred on or after January 1, 2025.