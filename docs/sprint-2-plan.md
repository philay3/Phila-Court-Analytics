# Sprint 2 Plan: Seeded Public API

## Sprint 2 Goal

Build the first real public API layer using seeded aggregate data.

By the end of Sprint 2, the backend supports:

- charge search
- optional judge search
- charge-only Philadelphia-wide results
- judge-specific results with Philadelphia baseline
- seeded outcome distributions
- seeded sentencing distributions
- thin-data examples
- definitions and methodology content
- public data coverage metadata
- privacy-boundary and copy-safety tests

Sprint 2 does **not** require real docket PDF parsing. It uses seeded database
records that match the final public API shape. Real aggregates replace the
seeds in Sprint 7; everything else built here is permanent.

---

## Locked Sprint 2 Scope

### In Scope

- `ref.*` and `analytics.*` table migrations (tables do not exist yet — Sprint 1
  created schemas only)
- Seed runner infrastructure (idempotent, re-runnable)
- Seeded public charges + aliases
- Seeded public judges + aliases (fake names — see Standing Decisions)
- One published seeded aggregate run
- Seeded charge-only outcome and sentencing aggregates
- Seeded judge-specific outcome and sentencing aggregates
- Thin-data and judge-unavailable seed scenarios
- Public error code catalog extending the existing 1.3 error handler
- TypeBox FormatRegistry registration (carries the 3.2 worklog finding)
- Charge search endpoint
- Judge search endpoint
- Charge-only result endpoint (incl. sentencing-unavailable handling)
- Judge-specific result endpoint (incl. judge-unavailable response)
- Definitions endpoint (served from `@pca/taxonomy`)
- Methodology endpoint
- Data coverage endpoint
- Public forbidden-field test suite
- Public copy safety test suite (shared term constants moved to `@pca/shared`)

### Out of Scope

- real UJS PDF ingestion, extraction, or parsing
- real charge-level attribution
- real aggregate generation
- `ref.outcome_categories` / `ref.sentencing_categories` DB tables (taxonomy
  stays package-sourced this sprint; DB taxonomy tables deferred to Sprint 7)
- rate limiting implementation (`RATE_LIMITED` code is defined only)
- admin review UI or correction workflow
- automated UJS import
- production deployment

---

## Sprint 2 Standing Decisions

These extend the Sprint 1 decisions and are locked:

1. **Tables first.** Sprint 1's migration 2.3 created the eight schemas only.
   Sprint 2 opens with migrations for `ref.*` and `analytics.*` tables.
2. **Error shape.** Keep the flat error shape shipped in 1.3 —
   `{ statusCode, error, message, requestId }` — extended with a `code: string`
   field. The nested `{ error: { ... } }` envelope from earlier drafts is
   rejected to avoid churn in `@pca/shared` and existing tests.
3. **FormatRegistry.** Before any Sprint 2 endpoint ships, the API registers
   TypeBox string formats (at minimum `date`, `date-time`, `uuid`).
   Unregistered formats pass silently (3.2 worklog finding); registration is an
   acceptance criterion of task 7.1.
4. **Taxonomy is package-only this sprint.** The definitions endpoint serves
   directly from `@pca/taxonomy` generated artifacts. Aggregate tables store
   `taxonomy_version` as a plain string. DB taxonomy tables deferred.
5. **Seeded judges use obviously fake names.** Fabricated statistics must never
   be attached to real Philadelphia judges. Real judge names enter the system
   in Sprint 5 via normalization of real parsed data. Seeded charges use real
   statute names (statutes are not people).
6. **Seed mechanics.** TypeScript seed scripts in `db/seeds/`, executed through
   Kysely, idempotent via `ON CONFLICT` upserts keyed on slug/code. Root script
   `db:seed`. Re-running produces no duplicates and no errors.
7. **Copy-guard term constants move to `@pca/shared`.** Both `apps/web` (4.1
   guard) and the new API copy-safety tests import from the shared package.
8. **Per-endpoint tests live in their endpoint tasks.** Phase 10 contains only
   the cross-cutting suites (forbidden-field, copy safety).
9. **Phase numbering continues from Sprint 1**: Phases 6–10.

---

## MVP Data Range (restated)

MVP data coverage starts **January 1, 2025**.

- Outcome aggregates represent eligible charge-level outcomes with disposition
  dates ≥ 2025-01-01.
- Sentencing aggregates represent eligible charge-level sentence facts with
  sentencing dates ≥ 2025-01-01.
- Earlier-filed cases are included if the qualifying event occurred on/after
  that date.

All seeded aggregate metadata must include `dateRange.start = "2025-01-01"`, a
realistic `dateRange.end`, `lastRefreshed`, `taxonomyVersion`, and
`aggregateRunId`.

---

## Technical Assumptions (carried from Sprint 1)

| Area | Choice |
|---|---|
| Backend framework | Fastify (buildApp factory from 1.3) |
| Language | TypeScript strict, root-installed |
| Database | PostgreSQL 17.10 (Docker, port 5433) |
| Migration/query layer | Kysely |
| Validation | TypeBox (`@pca/shared` schemas, `additionalProperties: false`) |
| Public namespace | `/api/v1/public` (plugin exists, empty) |
| Shared contracts | `@pca/shared` |
| Taxonomy source | `@pca/taxonomy` generated artifacts |
| Tests | Vitest + `fastify.inject` |
| Data source | Seeded aggregate data |

---

# Phase 6 — Tables + Seed Data

## Task 6.1 — `ref.*` Table Migrations

Create migrations for:

- `ref.normalized_charges` — public ID, slug (unique), display name, optional
  statute code, optional grade, active status, timestamps
- `ref.charge_aliases` — alias text, FK to normalized charge
- `ref.normalized_judges` — public ID, slug (unique), display name, active
  status, timestamps
- `ref.judge_aliases` — alias text, FK to normalized judge

Acceptance criteria:

- migrations follow the established naming convention and run via the existing
  migration runner
- unique constraints on slugs; FKs enforced
- migration applies and rolls back cleanly against local Postgres
- no defendant-related columns anywhere in `ref.*`

## Task 6.2 — `analytics.*` Table Migrations

Create migrations for:

- `analytics.aggregate_runs` — id, status, `published_at`, `invalidated_at`,
  `invalidated_reason`, `started_at`, `completed_at`, parser version
  placeholder, taxonomy version, data range start/end
- `analytics.charge_outcome_aggregates`
- `analytics.charge_sentencing_aggregates`
- `analytics.judge_outcome_aggregates`
- `analytics.judge_sentencing_aggregates`

Aggregate tables support: charge ID (and judge ID where applicable), category
code, count, percentage, sample size (sentencing sample size stored separately
in sentencing tables), date range, thin-data flag, aggregate run ID, taxonomy
version.

Acceptance criteria:

- all five tables exist with FKs to `ref.*` and `aggregate_runs`
- publication model uses explicit `published_at` / `invalidated_at` fields
- migration applies and rolls back cleanly

## Task 6.3 — Seed Runner + Reference Seeds

(Collapses draft stories S2-001.1 – S2-001.4.)

Acceptance criteria:

- seed infrastructure in `db/seeds/`, TypeScript, run through Kysely, root
  script `db:seed`
- idempotent: re-running produces identical state, no duplicates
- ≥ 5 normalized charges seeded (e.g. Retail Theft, Simple Assault, DUI,
  Possession of a Controlled Substance, Criminal Trespass), each with ≥ 1 alias
- ≥ 3 normalized judges seeded with **obviously fake names**, each with ≥ 1
  alias
- aliases map back to their normalized records
- no defendant-identifying data, no raw docket rows

## Task 6.4 — Aggregate Seeds

(Collapses draft stories S2-002.1 – S2-002.6.)

Acceptance criteria:

- exactly one **published** seeded aggregate run; API logic must ignore
  unpublished/in-progress runs
- charge-only outcome aggregates for ≥ 3 charges; percentages consistent with
  counts and sample size
- charge-only sentencing aggregates for ≥ 3 charges; sentencing sample size
  separate from outcome sample size
- judge-specific outcome aggregates for ≥ 2 charge/judge pairs, each with a
  Philadelphia baseline available
- judge-specific sentencing aggregates for ≥ 2 charge/judge pairs
- at least one thin-data example in each of: charge-only outcomes,
  judge-specific outcomes
- at least one charge with sentencing data absent or partial
- at least one valid charge/judge pair with **no** judge-specific aggregate
  (the unavailable scenario)
- all rows carry run ID, taxonomy version, date range starting 2025-01-01

---

# Phase 7 — Public API Plumbing + Search

## Task 7.1 — Error Catalog + FormatRegistry

(Replaces draft S2-006.1/S2-006.2.)

Acceptance criteria:

- existing 1.3 error handler extended with `code: string`; shape is
  `{ statusCode, code, error, message, requestId }`
- error codes defined in `@pca/shared`: `INVALID_REQUEST`, `CHARGE_NOT_FOUND`,
  `JUDGE_NOT_FOUND`, `CHARGE_RESULT_UNAVAILABLE`,
  `JUDGE_SPECIFIC_RESULT_UNAVAILABLE`, `SENTENCING_RESULT_UNAVAILABLE`,
  `RATE_LIMITED` (defined only, not implemented), `INTERNAL_ERROR`
- TypeBox FormatRegistry registers `date`, `date-time`, `uuid` at app build;
  a test proves an unregistered-format schema now fails instead of passing
- public error messages never mention parser confidence, extraction, review
  status, raw records, odds, predictions, legal advice, or internal IDs
- 5xx responses keep the message-leak protection from 1.3

## Task 7.2 — Charge Search Endpoint

`GET /api/v1/public/charges/search?q={query}&limit={limit}`

Acceptance criteria:

- validates `q` and `limit` (sensible default, enforced maximum)
- searches normalized charges and aliases; results deduplicated
- returns only public-safe fields: charge ID, slug, display name, optional
  statute, optional grade, matched alias where useful
- uses the `{ results: [...] }` envelope from `@pca/shared`
- no aggregate statistics, no raw docket data
- tests: exact match, alias match, no result, invalid query, limit
  enforcement, no-stats assertion

## Task 7.3 — Judge Search Endpoint

`GET /api/v1/public/judges/search?q={query}&limit={limit}`

Acceptance criteria:

- same validation and envelope rules as 7.2
- searches normalized judges and aliases; deduplicated
- returns only: judge ID, slug, display name
- no aggregate statistics, no ranking, no score
- tests mirror 7.2

---

# Phase 8 — Result Endpoints

## Task 8.1 — Charge-Only Result Endpoint

`GET /api/v1/public/results/charge/{chargeIdOrSlug}`

(Includes draft S2-004.4 sentencing-unavailable handling — intrinsic to the
endpoint.)

Response includes: charge metadata; result type `charge_only`; geography
Philadelphia; date range; last refreshed; taxonomy version; public-safe
aggregate run reference; outcome distribution; sentencing distribution when
available; per-distribution thin-data status; responsible-use copy reference;
methodology and definitions links.

Distribution rows include: category code, display name, count, percentage, and
the applicable sample size (sentencing rows use sentencing sample size).

Acceptance criteria:

- reads only from the published aggregate run
- outcome distribution renders even when sentencing is unavailable; response
  includes public-safe sentencing-unavailable metadata rather than failing
- must NOT return: defendant names, docket numbers, source document IDs, raw or
  extracted text, parsed record IDs, fact IDs, review status, parser
  confidence, storage keys
- tests: success, thin-data charge, sentencing-unavailable charge, missing
  charge (`CHARGE_NOT_FOUND`), slug and ID lookup, metadata presence (sample
  size, date range ≥ 2025-01-01, taxonomy version)

## Task 8.2 — Judge-Specific Result Endpoint

`GET /api/v1/public/results/charge/{chargeIdOrSlug}/judge/{judgeIdOrSlug}`

(Includes draft S2-004.3 judge-unavailable response — same routing logic.)

Response includes: charge and judge metadata; result type `judge_specific`;
judge-specific outcome distribution; Philadelphia baseline outcome
distribution; judge-specific and baseline sentencing distributions where
available; separate sample sizes for judge-specific vs baseline and outcome vs
sentencing; date ranges; per-distribution thin-data statuses; taxonomy
version; last refreshed; methodology and definitions links.

When charge and judge both exist but no judge-specific aggregate exists:

- structured response with code `JUDGE_SPECIFIC_RESULT_UNAVAILABLE`
- safe public message (no internal reason, no parser/review mention), e.g.:
  "No judge-specific aggregate is available for this charge and judge yet.
  Philadelphia-wide historical data for this charge is still available."
- charge-only fallback route metadata plus charge and judge metadata

Acceptance criteria:

- baseline always present on successful judge-specific responses
- no ranking, prediction, legal-advice, or scoring language
- forbidden-field rules identical to 8.1
- tests: success, thin-data pair, unavailable pair fallback, sentencing
  unavailable, missing charge, missing judge, metadata presence

---

# Phase 9 — Content Endpoints

## Task 9.1 — Definitions Endpoint

`GET /api/v1/public/definitions`

Acceptance criteria:

- serves outcome and sentencing category definitions directly from
  `@pca/taxonomy` generated artifacts — no DB dependency
- returns taxonomy version
- returns only public-visible categories
- plain-English definitions, no legal advice
- tests included

## Task 9.2 — Methodology + Data Coverage Endpoints

`GET /api/v1/public/methodology`
`GET /api/v1/public/data-coverage`

Methodology returns: data source summary, 2025+ data range statement,
historical-aggregate explanation, not-legal-advice and not-prediction
statements, sample size explanation, thin-data explanation, charge-level
analytics statement, sentencing distribution statement, limitations summary.

Data coverage returns: jurisdiction Philadelphia, criminal court MVP scope,
data start `2025-01-01`, data end, last refreshed, public-safe aggregate run
metadata, high-level seeded count metadata, known limitations.

Acceptance criteria:

- data coverage excludes: source document lists, docket numbers, defendant
  data, parser internals, storage keys
- all copy passes the forbidden-term list
- tests included

---

# Phase 10 — Hardening + Sprint Close

## Task 10.1 — Public Forbidden-Field Test Suite

Acceptance criteria:

- a required suite runs every public endpoint response through a
  forbidden-field check that fails on: defendant name, docket number, raw
  docket number, source document ID, source URL, storage key, raw text,
  extracted text, parsed docket ID, parsed charge ID, charge outcome fact ID,
  charge sentence fact ID, review status, admin correction, parser confidence
- suite runs in CI and is required for merge discipline

## Task 10.2 — Copy Safety Test Suite + Shared Constants

Acceptance criteria:

- forbidden/approved term constants move from `apps/web` to `@pca/shared`;
  the 4.1 web copy guard imports from the new location with no behavior change
- API copy safety tests check all public messages, methodology, and data
  coverage copy for: odds, likely sentence, prediction (outside guarded
  disclaimer phrases), best judge, worst judge, judge score, win rate,
  guaranteed result
- both suites run in CI

## Task 10.3 — Human Step: Exit Demo + Sprint Close

Chops runs the exit demo and reviews results in the planning chat:

1. Charge search: "retail" → normalized charge result
2. Judge search: seeded fake judge → result
3. Charge-only result: distributions, sample size, date range
4. Judge-specific result: judge distribution beside Philadelphia baseline
5. Unavailable pair: fallback response
6. Data coverage: 2025-01-01 start date
7. Forbidden-field and copy safety suites passing

Sprint 2 closes here; Sprint 3 (Seeded Public UI) planning begins.

---

## Sprint 2 Definition of Done

1. `ref.*` and `analytics.*` tables exist via migrations.
2. `db:seed` is idempotent and populates charges, aliases, judges (fake
   names), and aliases.
3. One published seeded aggregate run exists; unpublished runs are ignored.
4. All four aggregate types are seeded, including thin-data examples, a
   sentencing-absent charge, and a judge-unavailable pair.
5. Error catalog with `code` field extends the 1.3 handler; FormatRegistry is
   registered and tested.
6. Charge and judge search endpoints work.
7. Charge-only and judge-specific result endpoints work, including both
   unavailable handlers.
8. Definitions, methodology, and data coverage endpoints work.
9. Every public result payload includes sample size, date range, thin-data
   status, and taxonomy version; data range begins 2025-01-01.
10. Forbidden-field and copy safety suites pass in CI.
11. No public endpoint exposes raw docket data, defendant-identifying data,
    source documents, parser internals, fact IDs, review data, or storage
    keys.
12. Exit demo reviewed; sprint closed in the planning chat.

---

## Sprint 2 Risks (carried, with mitigations locked)

1. **Seeded data diverges from future real data** → contracts already encode
   unavailable states, thin data, separate sentencing sample sizes, and
   baseline comparison; `@pca/shared` is the single source of truth.
2. **Frontend later needs different payloads** → metadata-rich responses now
   (sample size, date range, taxonomy version, result type, links).
3. **Public API leaks internal fields** → forbidden-field suite is a required
   CI check from this sprint onward.
4. **2025+ range not reflected early** → baked into seeds and data coverage.
5. **Fabricated stats attached to real people** → eliminated by the fake
   judge-name decision.

## Handoff to Sprint 3

Sprint 3 begins when the exit demo passes: stable responses for charge search,
judge search, charge-only result, judge-specific result, definitions,
methodology, data coverage, and both unavailable states.