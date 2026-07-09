# Task 9.2 — Methodology + Data Coverage Endpoints

## Goal

Implement the final two Sprint 2 public endpoints:

- GET /api/v1/public/methodology
- GET /api/v1/public/data-coverage

Methodology serves structured static copy explaining what the product
is and is not. Data coverage reports what data the published aggregates
actually represent, derived from the active published aggregate run.

## Context

- 9.1 established the static-content pattern: content module in
  apps/api, schema in @pca/shared, poison-proxy test proving
  DB-independence. Methodology follows it exactly.
- 8.1/8.2 established published-run resolution: a run is active
  published iff published_at IS NOT NULL AND invalidated_at IS NULL,
  and at most one exists. Data coverage reuses the existing run
  resolution — do not write a second resolver.
- Phase 8 standing decision: "data slice absent" is an HTTP-200
  tagged-union response, not an error. Data coverage with no published
  run follows this pattern.
- Errors, if any, go through the central handler via catalog-coded
  throws. No per-endpoint error shaping.

## Endpoint 1: GET /api/v1/public/methodology

Static, DB-independent, versioned only by deploy.

Response is STRUCTURED — keyed sections, not one text blob — so the
Sprint 3 frontend can render sections independently and copy tests can
target fields. Required sections (each a { heading, body } object or
similar shape of the agent's design, consistent across sections):

- dataSource: public docket sheets from the Pennsylvania UJS portal,
  Philadelphia criminal court scope
- dataRange: coverage begins 2025-01-01, anchored to
  disposition/sentencing event dates, not filing dates; earlier-filed
  cases included if the qualifying event is on/after that date
- whatResultsMean: historical aggregate distributions
- notPrediction: explicit not-a-prediction statement
- notLegalAdvice: explicit not-legal-advice statement
- sampleSize: what sample size means and why it is shown on every
  figure
- thinData: what thin data means and how it is surfaced
- chargeLevelAnalytics: outcomes and sentences are attributed at the
  charge level, not the docket level
- sentencing: sentencing distributions use a separate sentencing
  sample size and may be unavailable for some charges
- limitations: plain-English summary of known limitations

All copy is plain-English, neutral, and must not contain any
forbidden term (odds, likely sentence, predict/prediction outside the
guarded disclaimer phrasing, best judge, worst judge, judge score,
win rate, guaranteed result), and must not mention parser confidence,
extraction, review workflow, or any internal system detail.

## Endpoint 2: GET /api/v1/public/data-coverage

Reads the active published aggregate run. Response has two arms as a
tagged union:

Common fields (always present, both arms):
- jurisdiction: Philadelphia
- courtScope: criminal court (MVP scope statement)
- plannedDataStart: "2025-01-01"
- knownLimitations: high-level, public-safe list

Available arm (active published run exists):
- coverage.available: true
- coverage.dataStart / coverage.dataEnd: from the run's data range
- coverage.lastRefreshed: from the run's published_at
- coverage.taxonomyVersion
- coverage.aggregateRunId (public-safe reference, consistent with how
  8.1/8.2 expose the run reference)
- coverage.counts: high-level counts derived from the active run's
  aggregate tables — number of charges with charge-only outcome
  aggregates, number of charges with sentencing aggregates, number of
  charge/judge pairs with judge-specific aggregates. Counts only;
  no names, no lists, no row-level data.

Unavailable arm (no active published run):
- coverage.available: false
- a safe public message (no internal reason, no run states, no parser
  or review mention)
- no run-derived fields

MUST NOT return (either arm): source document lists or IDs, docket
numbers, defendant data, raw or extracted text, storage keys, parser
version, parser confidence, review status, internal run states,
invalidation reasons.

## Schemas

- Both response schemas live in @pca/shared under the established
  public schema conventions (additionalProperties: false), exported
  alongside the existing public schemas.
- Follow the tagged-union modeling precedent from the 8.x unavailable
  arms.

## Acceptance criteria

1. Both endpoints exist under /api/v1/public and validate against
   their @pca/shared schemas.
2. Methodology contains all ten required sections with non-empty copy;
   a test asserts section presence.
3. Methodology is DB-independent: poison-proxy test (9.1 pattern)
   proves the endpoint succeeds with the DB unreachable.
4. Data coverage resolves the active published run via the existing
   run-resolution logic (no duplicate resolver).
5. Data coverage available arm returns correct dataStart (2025-01-01
   for the seeded run), dataEnd, lastRefreshed, taxonomyVersion, run
   reference, and counts consistent with the seeded data from 6.4.
6. Data coverage with no active published run returns HTTP 200 with
   coverage.available: false, the safe message, and all common fields.
   Test this by invalidating/absenting the run within a transaction or
   isolated test setup — do not mutate the shared seeded state used by
   other suites (respect the globalSetup seeding contract from 8.2).
7. Counts queries touch only analytics.* (and ref.* if needed for
   joins) — verified by the @pca/db Pick-narrowed repository interface.
8. Per-endpoint forbidden-term tests: methodology copy and data
   coverage messages pass the word-boundary forbidden-term regexes
   (9.1 pattern). Full cross-cutting suite remains 10.2's job.
9. Per-endpoint forbidden-field assertions: responses contain none of
   the MUST NOT fields above.
10. All gates green: lint, format:check, typecheck, tests. Worklog
    entry appended on completion.

## Conditional item — CI format:check

If the answer to the 9.1 follow-up question is that the GitHub Actions
workflow does NOT run format:check: add a format:check step to the CI
job in this task (two-line change), note it in the worklog. If CI
already runs it, do nothing here.

## Out of scope

- Any change to the static /methodology page in apps/web (Sprint 3
  refactors it to consume this endpoint)
- Moving copy-guard constants to @pca/shared (task 10.2)
- Cross-cutting forbidden-field and copy-safety suites (10.1/10.2)
- Rate limiting
- DB taxonomy tables
- Any admin or non-public endpoint

## Files the agent may touch

- packages/shared/src/public/** (new methodology/data-coverage schemas
  + exports)
- apps/api/src/** (routes, content module, repositories for coverage
  counts)
- apps/api test files
- .github/workflows/** (ONLY if the conditional CI item applies)
- tasks/worklog.md

## Plan-first rule

Respond with an implementation plan before writing any code. The plan
must state: (a) the response shape for both endpoints including the
tagged-union modeling for coverage, (b) where methodology copy lives
and how the poison-proxy test is wired, (c) how the no-published-run
test isolates itself from the shared seeded state, (d) whether CI
currently runs format:check and therefore whether the conditional item
applies.