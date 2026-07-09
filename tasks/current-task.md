# Task 8.2 — Judge-Specific Result Endpoint

## Goal

Implement `GET /api/v1/public/results/charge/{chargeIdOrSlug}/judge/{judgeIdOrSlug}`
— the judge-specific result with mandatory Philadelphia baseline, and the
structured judge-unavailable response.

Return an implementation plan BEFORE writing any code. The plan must cover:
how 8.1's repository/service machinery is reused for the baseline, the
top-level response union, the globalSetup seeding refactor, and the test
list. Wait for approval before implementing.

## Context

- Task 8.1 is complete and is the template: published-run resolution,
  UUID/slug disambiguation, taxonomy-sourced display names and ordering,
  sample-size uniformity checks, the sentencing tagged union, numeric(5,2)
  string→number conversion, response-schema stripping, catalog-code throws
  only.
- This task adds the two judge aggregate tables to `PublicApiDatabase`:
  `analytics.judge_outcome_aggregates`, `analytics.judge_sentencing_aggregates`.
- Seeds provide: judge-specific outcome + sentencing aggregates for ≥ 2
  charge/judge pairs (each with baseline available), ≥ 1 thin-data
  judge-specific example, and ≥ 1 valid charge/judge pair with NO
  judge-specific aggregate (the unavailable scenario).

## Pinned design decisions

### Entity resolution

- Same UUID/slug disambiguation rule as 8.1, applied independently to both
  path params. No fallthrough in either.
- Resolution order: charge, then judge, then run. Missing/inactive charge →
  404 `CHARGE_NOT_FOUND`. Missing/inactive judge → 404 `JUDGE_NOT_FOUND`.
  Entity 404s are independent of publication state.

### Availability decision tree (in order)

1. No active published run → throw `CHARGE_RESULT_UNAVAILABLE` (404).
   Identical to 8.1; operational state is not distinguishable publicly.
2. Run exists, but the charge has zero charge-only outcome rows (no
   baseline) → throw `CHARGE_RESULT_UNAVAILABLE` (404). The unavailable
   variant's fallback promise must never point at a dead end.
3. Run + baseline exist, zero judge-specific outcome rows for the pair →
   **HTTP 200** with the unavailable variant (below). This is an answer,
   not an error — same reasoning as 8.1's sentencing union — and it is the
   only way to carry the required charge/judge/fallback metadata without
   violating the flat error contract and the no-per-endpoint-error-shaping
   rule.
4. Judge-specific outcome rows exist but baseline rows are absent →
   throw `INTERNAL_ERROR` (500). Aggregation must always produce the
   baseline superset; this state is an integrity failure.
5. Otherwise → success response.

The catalog status default for `JUDGE_SPECIFIC_RESULT_UNAVAILABLE` is
unused by this endpoint (defaults are not invariants, per standing
decision). Do not change the catalog.

### Response contract (top-level tagged union in @pca/shared)

Success arm:

- `resultType`: literal `"judge_specific"`
- `charge`: same summary shape as 8.1
- `judge`: `{ id, slug, displayName }`
- `geography`: literal `"philadelphia"`
- `dateRange`, `lastRefreshed`, `taxonomyVersion`, `aggregateRunId`, `links`
  — identical semantics and sourcing to 8.1 (from the run)
- `judgeSpecific`: `{ outcomes: { sampleSize, thinData, rows },
  sentencing: <same tagged union as 8.1, judge-scoped sample size> }`
- `baseline`: `{ outcomes: { sampleSize, thinData, rows },
  sentencing: <same tagged union as 8.1> }`
- Row shape identical to 8.1. All four sample sizes are independent.
  Baseline is REQUIRED on every success response.

Unavailable arm (HTTP 200):

- `resultType`: literal `"judge_specific_unavailable"`
- `code`: literal `"JUDGE_SPECIFIC_RESULT_UNAVAILABLE"`
- `message`: literal pinned to a new exported constant
  `JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE`: "No judge-specific aggregate is
  available for this charge and judge yet. Philadelphia-wide historical
  data for this charge is still available." (No internal reason, no
  parser/review wording.)
- `charge` and `judge`: same summary shapes as the success arm
- `fallback`: `{ chargeOnlyResultPath }` — the public API path
  `/api/v1/public/results/charge/{slug}` built from the charge slug
- No distributions, no sample sizes, no run metadata in this arm.

Union members are structurally disjoint via the `resultType` literals;
route response schema is `{ 200: <union> }` so serialization stripping
covers both arms. `additionalProperties: false` throughout.

### Reuse (mandatory)

- Baseline outcome/sentencing reads use 8.1's existing repository
  functions; judge-scoped reads mirror them against the judge tables.
- The distribution builder (taxonomy ordering, display-name mapping,
  uniformity check, any-row thinData, percentage conversion, sentencing
  union assembly) is extracted from the 8.1 service into a shared helper
  and used by BOTH endpoints. 8.1's behavior must not change — its test
  suite is the regression lock.
- Integrity rules apply to all four distributions: unknown/non-public
  category code → `INTERNAL_ERROR`; intra-distribution sample-size
  mismatch → `INTERNAL_ERROR`.

### Test seeding refactor (in scope)

- Add a Vitest globalSetup to `apps/api` that runs `seedReference` +
  `seedAggregates` once when `DATABASE_URL` is set, before any suite.
- Existing DB-backed suites (search, 8.1 results) drop their self-seeding
  `beforeAll` calls. Per-suite skip guards and per-suite cleanup prefixes
  (`zz-test-`, `zz-result-`, and this task's new prefix) are unchanged.
- This removes the concurrent delete-and-reinsert race between
  aggregate-seeding suites.

## Scope

1. `@pca/shared`: judge-specific result union schema + types, the
   `JUDGE_SPECIFIC_UNAVAILABLE_MESSAGE` constant, judge summary schema.
   Delete the stale task-3.2 `judgeSpecificResultSchema` from `results.ts`
   and repoint/remove its consumers (same treatment approved for the
   charge schema in 8.1; `results.ts` may be deleted entirely if empty).
2. `apps/api`: route registration, service, judge-table repository
   functions, extraction of the shared distribution builder,
   `PublicApiDatabase` widened by exactly the two judge tables,
   globalSetup seeding refactor.
3. Tests (Vitest + `fastify.inject` + stubbed-repo unit tests), minimum:
   - success by slugs: both arms of metadata present; judgeSpecific AND
     baseline both rendered; four independent sample sizes asserted
     against seeded values; rows in taxonomy order
   - success by UUIDs for the same pair; body identical to slug lookup
   - mixed param modes (slug charge + UUID judge) resolve identically
   - thin-data pair: judge-specific thinData true where seeded
   - unavailable pair (seeded scenario): HTTP 200, unavailable arm,
     literal code + message, correct fallback path, charge and judge
     summaries present, no distributions
   - unknown charge → 404 CHARGE_NOT_FOUND; unknown judge → 404
     JUDGE_NOT_FOUND (both with the flat catalog shape)
   - no-fallthrough probe for the judge param (UUID-shaped judge slug,
     same technique as 8.1)
   - unit tests (stubbed repo): decision-tree branches incl.
     no-baseline-with-judge-rows → INTERNAL_ERROR, no-run and no-baseline
     → CHARGE_RESULT_UNAVAILABLE, uniformity mismatch on a judge
     distribution → INTERNAL_ERROR
   - forbidden-content + allowed-key guards on every response in the
     suite (endpoint-local, per 8.1 pattern)
   - 8.1's suite still passes untouched (regression lock on the
     extraction)
   - a judge-sentencing-unavailable case: if seeds don't contain a pair
     with outcome rows but no sentencing rows, cover it at the unit level
     with a stubbed repository — do NOT modify seeds

## Out of scope

- Definitions/methodology/data-coverage endpoints (Phase 9)
- Cross-cutting forbidden-field and copy-safety suites (Phase 10)
- Caching, rate limiting, pagination
- Any DB migrations or seed changes — if seeds prove insufficient, STOP
  and report (unit-level stubbing is the sanctioned workaround for
  missing scenarios)
- Any changes to the error catalog or its status defaults
- Any web UI work

## Files the agent may touch

- `packages/shared/src/**`
- `apps/api/src/**`
- `apps/api/vitest.config.ts` and test setup files (globalSetup refactor)
- `apps/api/package.json` only if strictly needed (none expected)
- `tasks/worklog.md` (append entry on completion)

Do not touch: `db/**` (no exception this time — seedAggregates is already
exported), `packages/taxonomy/**`, `apps/web/**`, `services/pipeline/**`,
CI workflows.

## Acceptance criteria

- Baseline present on every success response; four independent sample
  sizes; judge and baseline sentencing unions independent
- Unavailable pair returns HTTP 200 with the pinned literal code, message,
  charge/judge summaries, and a truthful fallback path
- No-run and no-baseline cases return 404 CHARGE_RESULT_UNAVAILABLE; the
  unavailable variant is never emitted when the fallback would dead-end
- Slug/UUID/mixed lookups identical; no fallthrough on either param
- Shared distribution builder extracted; 8.1 suite passes unchanged
- globalSetup seeding in place; no suite self-seeds aggregates
- No ranking, prediction, or scoring language anywhere in new copy
- No forbidden fields in any response (spot-checked in tests)
- All error paths use the central handler + catalog codes
- Lint, typecheck, and full test suite pass