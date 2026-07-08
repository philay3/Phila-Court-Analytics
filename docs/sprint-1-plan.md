# Sprint 1 Plan

## Sprint Goal

Establish the runnable technical foundation and begin PDF extraction evaluation without committing to broad ingestion or parser architecture too early.

## Locked Stack Decisions

| Area | Sprint 1 Choice |
|---|---|
| Backend framework | Fastify |
| API language | TypeScript |
| Migration tool | Kysely Migrator |
| DB query layer | Kysely |
| Database | PostgreSQL |
| PDF extractor candidates | PyMuPDF, pdfplumber, pypdf |
| Likely primary extractor | PyMuPDF, pending fixture evaluation |
| Layout/table fallback candidate | pdfplumber |
| Metadata/simple baseline candidate | pypdf |
| OCR | Out of scope; detect and flag only |

## Why Fastify

Fastify is chosen because the API is focused, schema-heavy, and needs clear public/admin route separation with low framework overhead.

Sprint 1 needs:

- health endpoint
- route namespaces
- request validation
- response shaping
- standard errors
- request IDs
- structured logging

Fastify is a strong fit for that foundation.

## Why Kysely Migrator

The project needs explicit SQL for schemas, aggregate tables, views, indexes, and analytics-oriented queries.

Kysely is chosen for:

- type-safe query layer
- explicit migrations
- SQL readability
- compatibility with PostgreSQL analytics needs

## PDF Extraction Evaluation

Evaluate:

1. PyMuPDF
2. pdfplumber
3. pypdf

Sprint 1 does not choose the final parser engine. It builds the harness to compare these against representative fixtures.

Evaluation criteria:

- page-level text extraction quality
- text order
- charge table readability
- disposition section readability
- sentencing section readability
- extraction duration
- empty-page detection
- metadata usefulness
- failure modes

OCR is out of scope for Sprint 1. Empty or image-only PDFs should be flagged as `needs_ocr_or_review`.

## Sprint 1 Stories

### 1. Initialize Monorepo

Acceptance Criteria:

- monorepo structure exists
- pnpm workspace configured
- root scripts exist
- README includes setup
- no secrets or production data committed

### 2. Configure TypeScript and Fastify API Shell

Acceptance Criteria:

- Fastify API starts
- `/health` exists
- request ID middleware exists
- central error handler exists
- `/api/v1/public` namespace exists
- `/api/v1/admin` namespace exists
- strict TypeScript enabled

### 3. Configure Kysely and Migration System

Acceptance Criteria:

- Kysely installed
- migration runner exists
- initial migration creates schemas:
  - raw
  - parsed
  - ref
  - fact
  - analytics
  - review
  - audit
  - auth
- migration command runs locally
- migration naming convention documented

### 4. Create Local PostgreSQL Environment

Acceptance Criteria:

- local Docker Compose starts PostgreSQL
- local database URL documented
- `.env.example` includes DB variables
- API connects to local DB
- migrations apply successfully

### 5. Create Taxonomy Package

Acceptance Criteria:

- `packages/taxonomy` exists
- outcome seed file exists
- sentencing seed file exists
- thin-data seed file exists
- validation script exists
- generated TypeScript artifact exists
- generated JSON artifact exists

### 6. Create Shared API Types Package

Acceptance Criteria:

- `packages/shared` exists
- public response types exist
- result types require:
  - sample size
  - date range
  - thin-data status
  - taxonomy version
  - counts and percentages

### 7. Create Web App Shell

Acceptance Criteria:

- Next.js app starts
- routes exist:
  - `/`
  - `/methodology`
  - `/definitions`
  - `/data-coverage`
  - `/about`
- layout exists
- no prediction/legal-advice copy appears

### 8. Create Python Pipeline Shell

Acceptance Criteria:

- Python project exists
- CLI entrypoint exists
- pytest runs
- placeholder commands:
  - `import-manual`
  - `extract-text`
  - `evaluate-extractors`
  - `run-fixtures`
- structured logging helper exists

### 9. Add PDF Extraction Evaluation Harness

Acceptance Criteria:

- harness runs PyMuPDF, pdfplumber, and pypdf against fixture directory
- output artifacts are separated by extractor
- captures:
  - extracted text length
  - page count
  - extraction duration
  - empty pages
  - section keyword hits
  - errors
- does not log raw docket text to console
- saves internal artifacts for review

### 10. Add Basic CI

Acceptance Criteria:

CI runs:

- pnpm install
- lint
- typecheck
- tests
- taxonomy validation
- pytest for pipeline shell

## Sprint 1 Definition of Done

Sprint 1 is done when:

1. Monorepo runs locally.
2. Web app shell starts.
3. Fastify API shell starts.
4. `/health` works.
5. PostgreSQL starts locally.
6. Kysely migrations apply.
7. Initial schemas exist.
8. Taxonomy package validates.
9. Shared public API types exist.
10. Python pipeline shell runs tests.
11. PDF extraction evaluation harness runs against local fixtures.
12. CI runs baseline checks.
13. No secrets, raw production PDFs, extracted text, or defendant-identifying data are committed.
