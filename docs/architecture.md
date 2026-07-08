# Fullstack Architecture: Philadelphia Court Outcomes Analytics

## Introduction

This document defines the fullstack architecture for Philadelphia Court Outcomes Analytics.

The system includes:

- public web app
- backend API
- UJS PDF ingestion pipeline
- parsing and normalization
- charge-level attribution
- aggregate generation
- admin review workflow
- deployment, security, testing, and monitoring

The core rule is that public users see aggregate historical distributions only. Raw docket-level data remains internal.

## High-Level Architecture

The system has five main layers:

1. Public Web App
2. Backend API
3. Data Pipeline
4. PostgreSQL Data Store
5. Admin Review and Audit Workflow

## Recommended Stack

| Area | Choice |
|---|---|
| Frontend | Next.js, React, TypeScript |
| Backend | Fastify, TypeScript |
| Database | PostgreSQL |
| Migration/query layer | Kysely + explicit SQL |
| Pipeline | Python |
| PDF extraction candidates | PyMuPDF, pdfplumber, pypdf |
| Object storage | private S3-compatible storage |
| Monorepo | pnpm workspaces / Turborepo |
| Testing | Vitest/Jest, Playwright, pytest |
| Monitoring | Sentry/provider logs/structured logs |

## Monorepo Structure

```text
philadelphia-court-outcomes/
├── apps/
│   ├── web/
│   └── api/
├── services/
│   └── pipeline/
├── packages/
│   ├── shared/
│   ├── taxonomy/
│   └── ui/
├── db/
├── docs/
├── infra/
├── scripts/
└── tests/
```

## Data Model Layers

### Raw Layer

Stores source metadata and private references to raw PDFs and extracted text.

Key models:

- `raw.import_batches`
- `raw.source_documents`
- `raw.extracted_text_artifacts`

### Parsed Layer

Stores parser outputs.

Key models:

- `parsed.dockets`
- `parsed.charges`
- `parsed.judge_events`
- `parsed.dispositions`
- `parsed.sentences`

### Reference Layer

Stores normalized domain entities and taxonomy.

Key models:

- `ref.normalized_charges`
- `ref.charge_aliases`
- `ref.normalized_judges`
- `ref.judge_aliases`
- `ref.outcome_categories`
- `ref.sentencing_categories`
- `ref.taxonomy_versions`

### Fact Layer

Stores charge-level analytics facts.

Key models:

- `fact.charge_outcomes`
- `fact.charge_sentences`

### Analytics Layer

Stores public aggregate outputs.

Key models:

- `analytics.aggregate_runs`
- `analytics.charge_outcome_aggregates`
- `analytics.charge_sentencing_aggregates`
- `analytics.judge_outcome_aggregates`
- `analytics.judge_sentencing_aggregates`

### Review and Audit Layers

Stores human review, corrections, exclusions, and audit events.

Key models:

- `review.queue_items`
- `review.admin_corrections`
- `audit.events`
- `audit.parser_versions`
- `auth.admin_users`

## Public API

Base path:

`/api/v1/public`

Endpoints:

- `GET /charges/search`
- `GET /judges/search`
- `GET /results/charge/{chargeId}`
- `GET /results/charge/{chargeId}/judge/{judgeId}`
- `GET /definitions`
- `GET /methodology`
- `GET /data-coverage`

Public API rules:

- aggregate-only
- no raw docket data
- no defendant names
- no docket numbers
- no source document IDs
- no storage keys
- no parser internals
- sample size included
- date range included
- thin-data status included
- taxonomy version included

## Admin API

Base path:

`/api/v1/admin`

Endpoint groups:

- import batches
- source documents
- review queue
- review item detail
- review actions
- normalization management
- aggregate runs
- audit events

Admin API rules:

- authenticated
- role-authorized
- admin writes audited
- raw context visible only to authorized admins
- raw source records never mutated by corrections

## Backend Architecture

The Fastify API should be organized into modules:

- public search
- public results
- public content
- data coverage
- admin auth
- admin review
- admin imports
- admin normalization
- aggregate runs
- audit

Recommended layering:

```text
route/controller
  -> validation
  -> service
  -> repository
  -> database
```

Public result repositories should query only:

- `analytics.*`
- selected `ref.*`

## Frontend Architecture

Next.js routes:

- `/`
- `/search`
- `/charges/[chargeSlug]`
- `/charges/[chargeSlug]/judge/[judgeSlug]`
- `/methodology`
- `/definitions`
- `/data-coverage`
- `/about`
- `/admin/*`

Frontend rules:

- charge search is primary
- judge is optional
- charts have table equivalents
- frontend does not calculate core analytics
- public result pages show sample size and date range
- result pages default to `noindex` until review
- admin routes protected

## Data Pipeline Architecture

Pipeline stages:

1. manual/source import
2. private PDF storage
3. text/layout extraction
4. docket parsing
5. charge parsing
6. judge parsing
7. disposition parsing
8. sentence parsing
9. normalization
10. charge-level outcome attribution
11. charge-level sentence attribution
12. confidence scoring
13. review queue generation
14. aggregate generation
15. aggregate validation/publication

Pipeline principles:

- manual import first
- automated import disabled until review
- deterministic parsing first
- OCR out of scope for Sprint 1
- parser outputs versioned
- taxonomy version recorded
- ambiguous data enters review
- public aggregates generated from eligible facts only

## Security and Privacy

Public data:

- aggregate counts and percentages
- sample sizes
- date ranges
- normalized charge/judge names
- taxonomy definitions
- methodology

Internal sensitive data:

- raw PDFs
- extracted text
- raw docket numbers
- parsed records
- charge-level facts
- sentence-level facts
- review records
- admin corrections
- object storage keys

Security requirements:

- private object storage
- admin auth
- admin audit
- least-privilege DB roles where practical
- public forbidden-field tests
- logging restrictions
- no raw docket content in monitoring

## Deployment Architecture

Deploy independently:

- web app
- API
- pipeline worker
- PostgreSQL
- object storage

Important rule:

Application deployment and data publication are separate. A code deploy should not automatically publish new parser output.

Aggregate publication should use explicit fields such as:

- `published_at`
- `invalidated_at`
- `invalidated_reason`

## Testing Strategy

Required test areas:

- frontend component tests
- public E2E flows
- accessibility tests
- API contract tests
- public forbidden-field tests
- admin auth/authorization tests
- parser fixture tests
- normalization tests
- attribution tests
- aggregate validation tests
- migration tests

Highest-risk tests:

- parser fixtures
- charge-level sentence attribution
- aggregate denominator checks
- public privacy-boundary tests

## Monitoring

Monitor:

- web uptime
- API latency and error rates
- search latency
- result endpoint latency
- admin auth failures
- import failures
- extraction failures
- parser failures
- low-confidence rates
- review backlog
- aggregate validation failures
- latest published aggregate age
- forbidden-field regressions

Logs must not include raw docket content or defendant-identifying information.

## Launch Gates

Public launch requires:

- parser proof of concept completed
- charge-level attribution validated
- sentencing attribution validated or limited
- public aggregate validation passing
- admin review workflow working
- public forbidden-field tests passing
- raw PDFs/extracted text private
- methodology and definitions complete
- responsible-use copy reviewed
- source-access/compliance review complete
- staging validation complete
- monitoring and rollback active

MVP data coverage starts on January 1, 2025. Outcome aggregates include eligible charge-level outcomes with disposition dates on or after January 1, 2025. Sentencing aggregates include eligible charge-level sentence facts with sentencing dates on or after January 1, 2025. Earlier-filed cases may be included if the relevant disposition or sentencing event occurred on or after January 1, 2025.