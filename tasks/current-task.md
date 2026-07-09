# Task 8.1 — Charge-Only Result Endpoint

## Goal

Implement `GET /api/v1/public/results/charge/{chargeIdOrSlug}` — the first
public result endpoint. It reads the seeded `analytics.*` data through the
published-run model and returns Philadelphia-wide outcome and sentencing
distributions for one charge, with full public metadata.

Return an implementation plan BEFORE writing any code. The plan must cover:
repository query strategy (including the published-run query), the shared
schema additions, the sentencing-unavailable union handling, and the test
list. Wait for approval before implementing.

## Context

- Phases 6 and 7 are complete: `ref.*` and `analytics.*` tables exist,
  seeds are in place (including one published aggregate run, thin-data
  examples, and at least one charge with sentencing absent), the error
  catalog + FormatRegistry ship in the central handler, and both search
  endpoints are live.
- This endpoint is the first consumer of `analytics.charge_outcome_aggregates`
  and `analytics.charge_sentencing_aggregates`.
- Layering is route → validation → service → repository. Public result
  repositories query only `analytics.*` and selected `ref.*`.
- Errors are emitted by throwing errors carrying a catalog code; the central
  handler shapes the response. No per-endpoint error shaping.
- `registerFormats()` is already buildApp's first statement; do not re-register.

## Pinned design decisions

### Published-run resolution

- The repository resolves the single active published run:
  `published_at IS NOT NULL AND invalidated_at IS NULL`. The partial unique
  index from 6.2 guarantees at most one; the query must still be written
  defensively (LIMIT 1, deterministic).
- All aggregate reads for this request are scoped to that run's ID.
- If no active published run exists → throw `CHARGE_RESULT_UNAVAILABLE`.
- If the charge resolves but has zero outcome aggregate rows in the active
  run → throw `CHARGE_RESULT_UNAVAILABLE`.
- The two cases above are indistinguishable in the public response by design.

### Path param disambiguation

- If `chargeIdOrSlug` matches the canonical UUID v4-compatible regex
  (case-insensitive 8-4-4-4-12 hex), look up `ref.normalized_charges` by `id`.
- Otherwise look up by `slug`.
- No fallthrough between the two. Misses in either mode → `CHARGE_NOT_FOUND`.
- Only active charges resolve; inactive → `CHARGE_NOT_FOUND`.

### HTTP statuses

- `CHARGE_NOT_FOUND` → 404
- `CHARGE_RESULT_UNAVAILABLE` → 404
- Set/confirm these as the catalog defaults in `@pca/shared`
  (`PUBLIC_ERROR_CODE_STATUS`); the per-response `statusCode` field remains
  authoritative.

### Response shape (add TypeBox schemas to @pca/shared)

Success (200):

- `charge`: `{ id, slug, displayName, statuteCode?, grade? }`
- `resultType`: literal `"charge_only"`
- `geography`: literal `"philadelphia"`
- `dateRange`: `{ start, end }` (ISO dates, from the aggregate run;
  start must be ≥ 2025-01-01 in practice)
- `lastRefreshed`: ISO date-time — the run's `published_at`
- `taxonomyVersion`: string (from the run)
- `aggregateRunId`: UUID (public-safe run reference; no other run fields)
- `outcomes`: `{ sampleSize, thinData, rows }`
- `sentencing`: tagged union —
  - `{ available: true, sampleSize, thinData, rows }` — note
    `sampleSize` here is the SENTENCING sample size, independent of
    outcomes
  - `{ available: false, message }` — `message` is a public-safe constant,
    e.g. "Historical sentencing data is not available for this charge yet."
    No parser/review/extraction/internal wording.
- `links`: `{ methodology, definitions }` — public paths (`/methodology`,
  `/definitions`)
- Row shape (both distributions): `{ categoryCode, displayName, count,
  percentage }`. Sample size is NOT duplicated per row.

Schemas use `additionalProperties: false` throughout, consistent with
existing `@pca/shared` conventions.

### Taxonomy usage

- Aggregate rows store category codes only. `displayName` and row ordering
  come from `@pca/taxonomy` generated artifacts (taxonomy sort order).
- Add `@pca/taxonomy` as a dependency of `apps/api` if not already present.
- If an aggregate row carries a category code unknown to the taxonomy
  artifact, that is an internal integrity failure: throw `INTERNAL_ERROR`
  (500). Never render an unknown code with a fabricated display name, and
  never leak the offending code in the public message.

### Distribution semantics

- Percentages and counts are served exactly as stored — no recomputation.
- `thinData` (per distribution): true if ANY row in that distribution for
  this charge/run carries the thin-data flag; expected seeded state is
  uniform per distribution, but the any-row rule is the defensive contract.
- Outcomes and sentencing carry independent `sampleSize` and `thinData`.

## Scope

1. `@pca/shared`: charge-only result response schema + types, the
   sentencing union, the public-safe sentencing-unavailable message
   constant, and status defaults for the two error codes above.
2. `apps/api`: route registration under `/api/v1/public`, param validation,
   service, repository (published-run query + charge resolution + both
   distribution reads), taxonomy-artifact wiring for display names/order.
3. Tests (Vitest + `fastify.inject`), minimum:
   - success by slug: full metadata present (sampleSize, dateRange with
     start ≥ 2025-01-01, taxonomyVersion, lastRefreshed, aggregateRunId)
   - success by UUID for the same charge; body identical to slug lookup
   - counts/percentages match seeded values; rows in taxonomy sort order
   - thin-data charge: `outcomes.thinData === true`
   - sentencing-unavailable charge: `available: false`, message constant,
     outcomes still fully rendered
   - unknown slug → 404 `CHARGE_NOT_FOUND`
   - UUID-shaped param not in DB → 404 `CHARGE_NOT_FOUND` (proves no
     slug fallthrough)
   - forbidden-key spot assertions on every response body in this suite:
     no defendant name, docket number, source document ID, storage key,
     raw/extracted text, parsed/fact IDs, review status, parser confidence
     (the exhaustive suite is Task 10.1; these are endpoint-local guards)
   - error responses use the flat catalog shape
     `{ statusCode, code, error, message, requestId }`

## Out of scope

- Judge-specific result endpoint (Task 8.2)
- Definitions/methodology/data-coverage endpoints (Phase 9)
- Cross-cutting forbidden-field and copy-safety suites (Phase 10)
- Caching, rate limiting, pagination
- Any DB migrations or seed changes — if seeds prove insufficient for a
  required test scenario, STOP and report back instead of modifying seeds
- Any web UI work

## Files the agent may touch

- `packages/shared/src/**` (new public result schema module + error status
  additions)
- `apps/api/src/**` (route, service, repository, taxonomy wiring)
- `apps/api/test/**` (or the established test location)
- `apps/api/package.json` (only to add `@pca/taxonomy` if needed)
- `tasks/worklog.md` (append entry on completion)

Do not touch: `db/**`, `packages/taxonomy/src/**` seeds, `apps/web/**`,
`services/pipeline/**`, CI workflows.

## Acceptance criteria

- Endpoint reads only from the active published aggregate run; unpublished
  and invalidated runs are provably ignored (covered by existing seed state)
- Slug and UUID lookup both work with identical bodies; no fallthrough
- Outcome distribution renders even when sentencing is unavailable
- Sentencing sample size is separate from outcome sample size
- Every success response includes: sample size(s), date range starting
  2025-01-01, thin-data statuses, taxonomy version, lastRefreshed,
  aggregateRunId
- No forbidden fields in any response (spot-checked in tests)
- All error paths use the central handler + catalog codes; no per-endpoint
  error shaping
- Lint, typecheck, and full test suite pass