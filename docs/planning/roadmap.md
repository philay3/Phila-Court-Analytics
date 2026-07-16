# Project Roadmap / Build Order

This is the clearest “what happens next?” document for the project.

Deployed under controlled launch at philacourtoutcomes.org, 2026-07-16

## Current Status

Completed planning docs:

1. Project brief
2. Product requirements
3. Front-end / UX specification
4. Fullstack architecture
5. Implementation backlog
6. Sprint 1 plan and stack decisions

Not yet built:

- actual repository
- Next.js web app
- Fastify API
- PostgreSQL migrations
- Python PDF parser
- admin review tools
- real aggregate generation

## Recommended Build Order

```text
Planning Docs
  → Sprint 1: Foundation
  → Sprint 2: Seeded Public API
  → Sprint 3: Seeded Public UI
  → Sprint 4: Parser Proof of Concept
  → Sprint 5: Normalization and Attribution
  → Sprint 6: Admin Review MVP
  → Sprint 7: Real Aggregate Generation
  → Sprint 8: Staging Validation
  → Sprint 9: Launch Readiness
```

## Sprint 1: Foundation

Goal: create the runnable technical foundation.

Build:

- monorepo
- Next.js web shell
- Fastify API shell
- PostgreSQL local environment
- Kysely migrations
- taxonomy package
- shared API types
- Python pipeline shell
- PDF extraction evaluation harness
- baseline CI

Primary docs:

- `sprint-1-plan.md`
- `implementation-backlog.md`

## Sprint 2: Seeded Public API

Goal: build the first real API using seeded/fake aggregate data.

Build:

- charge search endpoint
- judge search endpoint
- charge-only result endpoint
- judge-specific result endpoint
- definitions/methodology/data coverage endpoints
- seeded outcome and sentencing aggregate data
- public privacy-boundary tests

Primary doc:

- `implementation-backlog.md`, Milestone 2

## Sprint 3: Seeded Public UI

Goal: build the public website against the seeded API.

Build:

- homepage search
- charge autocomplete
- optional judge autocomplete
- charge-only result page
- judge-specific result page
- outcome distribution chart/table
- sentencing distribution chart/table
- thin-data warnings
- sample-size/date-range labels
- methodology and definitions pages

Primary docs:

- `front-end-spec.md`
- `implementation-backlog.md`, Milestone 2

## Sprint 4: Parser Proof of Concept

Goal: prove that UJS docket PDFs can be parsed reliably enough.

Build:

- representative PDF fixture corpus
- manual PDF import
- PDF text extraction comparison
- charge parsing
- judge parsing
- disposition parsing
- sentencing parsing
- golden parser outputs
- parser regression tests

Primary doc:

- `implementation-backlog.md`, Milestone 3

## Sprint 5: Normalization and Attribution

Goal: turn parsed docket records into charge-level analytics-ready facts.

Build:

- charge normalization
- judge normalization
- outcome category mapping
- sentencing category mapping
- charge-level outcome attribution
- charge-level sentence attribution
- confidence scoring
- review-needed flags

Primary docs:

- `architecture.md`
- `implementation-backlog.md`, Milestone 3 and follow-on work

## Sprint 6: Admin Review MVP

Goal: let humans review uncertain parser output before it becomes public aggregate data.

Build:

- admin login
- review queue
- review item detail
- approve/correct/exclude/needs-more-review actions
- audit events
- aggregate run dashboard

Primary doc:

- `architecture.md`, Admin Review / Backend / Security sections

## Sprint 7: Real Aggregate Generation

Goal: replace seeded data with validated aggregate output from reviewed charge-level facts.

Build:

- charge-only outcome aggregates
- charge-only sentencing aggregates
- judge-specific outcome aggregates
- judge-specific sentencing aggregates
- Philadelphia baseline aggregates
- thin-data flags
- aggregate validation
- aggregate publication and rollback

Primary docs:

- `architecture.md`
- `implementation-backlog.md`

## Sprint 8: Staging Validation

Goal: test the full system before public launch.

Validate:

- public flows
- admin flows
- parser quality
- aggregate sanity
- privacy boundaries
- accessibility
- monitoring
- rollback

Primary docs:

- `architecture.md`
- `front-end-spec.md`

## Sprint 9: Launch Readiness

Goal: complete final production, compliance, and public launch checks.

Complete:

- source-access/compliance review
- raw PDF retention decision
- public indexing decision
- responsible-use/disclaimer review
- production deployment
- production smoke tests
- monitoring alerts
- aggregate rollback readiness

Primary docs:

- `architecture.md`
- `prd.md`

## Where the Order Lives in the Docs

Use these files in this order:

1. `roadmap.md`
   - the plain-English build order

2. `sprint-1-plan.md`
   - exactly what to build first

3. `implementation-backlog.md`
   - epics/stories/acceptance criteria for the first three milestones

4. `architecture.md`
   - technical details behind each system area

5. `front-end-spec.md`
   - UI behavior and page/component details

6. `prd.md`
   - product requirements and scope

7. `brief.md`
   - high-level project summary

## Immediate Next Step

Start Sprint 1 with:

1. Initialize monorepo
2. Configure TypeScript
3. Create Fastify API shell
4. Create local PostgreSQL + Kysely migrations
5. Create taxonomy package
6. Create shared API types
7. Create Next.js web shell
8. Create Python pipeline shell
9. Add PDF extraction evaluation harness
10. Add basic CI

MVP data coverage starts on January 1, 2025. Outcome aggregates include eligible charge-level outcomes with disposition dates on or after January 1, 2025. Sentencing aggregates include eligible charge-level sentence facts with sentencing dates on or after January 1, 2025. Earlier-filed cases may be included if the relevant disposition or sentencing event occurred on or after January 1, 2025.