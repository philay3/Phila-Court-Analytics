# Task 10.1 — Public Forbidden-Field Test Suite

## Goal

Add a required test suite in `apps/api` that scans EVERY public endpoint
response for forbidden fields and forbidden value patterns, with endpoint
coverage enforced by route-table discovery rather than a manually maintained
list. This suite is a permanent privacy gate: it must be structurally
impossible to add a public endpoint that escapes it.

## Context

- All Sprint 2 public endpoints exist: charges/search, judges/search,
  results/charge/{chargeIdOrSlug}, results/charge/.../judge/{judgeIdOrSlug},
  definitions, methodology, data-coverage.
- The public API is aggregate-only. Forbidden content includes: defendant
  names, docket numbers, raw docket numbers, source document IDs, source
  URLs, storage keys, raw text, extracted text, parsed docket IDs, parsed
  charge IDs, charge outcome fact IDs, charge sentence fact IDs, review
  status, admin corrections, parser confidence.
- `@pca/shared` is the single source of truth for public API contracts.
  Forbidden-field constants belong there (this is deliberate: it avoids a
  later migration and lets future consumers — e.g. web E2E tests — import
  the same list).
- DB-backed suites seed via Vitest globalSetup only (standing decision).
  Never self-seed.
- The central error handler shapes all error responses; error and
  200-unavailable arms must be scanned, not just success arms.

## Pinned design (do not re-litigate; raise concerns in your plan if any
are unworkable)

1. **Discovery**: collect routes via an `onRoute` hook on the test app
   instance (buildApp), filter to method GET + URL prefix `/api/v1/public`.
   Non-public routes (`/health`, admin namespace) are excluded by the
   prefix filter.
2. **Probe registry**: a typed map from Fastify route pattern (the exact
   `url` as registered, e.g. `/api/v1/public/results/charge/:chargeIdOrSlug`)
   to an array of concrete probe requests (path + query) built against
   seeded data. The suite fails with an explicit message naming the route
   if any discovered route has zero probes. It must also fail if a
   registry entry references a route that no longer exists (stale probe
   detection — both directions are checked).
3. **Arm coverage**: probes per route must include, where the route
   supports them: success, thin-data case, 200-unavailable arm
   (sentencing-unavailable for 8.1, judge-unavailable for 8.2), and at
   least one 404 (CHARGE_NOT_FOUND or JUDGE_NOT_FOUND). Every probe
   response body is scanned regardless of status code.
4. **Constants in `@pca/shared`**: new module `src/public/forbidden-fields.ts`
   exporting:
   - `FORBIDDEN_FIELD_STEMS: readonly string[]` — normalized stems:
     `defendant`, `docket`, `sourcedocument`, `sourceurl`, `storagekey`,
     `rawtext`, `extractedtext`, `parseddocket`, `parsedcharge`, `factid`,
     `reviewstatus`, `admincorrection`, `confidence`
   - `FORBIDDEN_VALUE_PATTERNS: readonly RegExp[]` — at minimum a UJS
     docket-number pattern (e.g. `CP-51-CR-0001234-2025` and `MC-` variants).
     Propose the exact regex(es) in your plan.
   Exported from the package entry point alongside existing public
   contract exports.
5. **Checker semantics**:
   - Deep-recursive walk of the parsed JSON body (objects + arrays).
   - Key check: normalize each key (lowercase, strip `_`, `-`) and fail if
     the normalized key CONTAINS any forbidden stem.
   - Value check: every string value tested against every forbidden value
     pattern.
   - On failure, the error must identify the route, probe, JSON path to
     the offending key/value, and which stem/pattern matched.
6. **Checker self-tests (required)**: unit tests that feed the checker
   poisoned objects — at least one per forbidden stem, one per value
   pattern, one deeply nested (≥3 levels, inside an array), and one
   camelCase + one snake_case variant of the same stem — and assert each
   is caught. Also one clean fixture (a realistic charge-only result
   payload) asserting no false positive.
7. **Seeding**: reuse the existing globalSetup-seeded data for probe
   targets (seeded slugs/IDs). Do not insert or delete rows in this suite.

## Scope

- `packages/shared`: add `forbidden-fields.ts` module + its unit tests;
  export from entry point.
- `apps/api`: new test file(s) for the suite (e.g.
  `test/public-forbidden-fields.test.ts`), plus a small test helper for
  route discovery and the deep-walk checker (checker may live in a test
  helper within apps/api; only the CONSTANTS live in @pca/shared).
- Update `tasks/worklog.md` on completion.

## Out of scope

- Copy-safety constant migration and copy-term scanning (Task 10.2 —
  this suite checks structure and identifiers, not prose terms).
- Admin endpoints (none are public; prefix filter excludes them).
- Any change to endpoint implementations, schemas, or seeds. If the suite
  finds a real leak, STOP and report it — do not fix endpoint code inside
  this task.
- Rate limiting, web app tests, CI workflow changes (the suite runs inside
  the existing `apps/api` Vitest run, which CI already executes).

## Acceptance criteria

1. Suite discovers public GET routes via onRoute hook; a route-count
   assertion documents the currently expected number (7) with a comment
   explaining it exists to make silent discovery breakage visible.
2. Unmapped-route failure proven by a deliberate-failure probe: a test
   registers a throwaway public route on a local app instance and asserts
   the suite's coverage check reports it as unprobed.
3. Stale-probe detection proven symmetrically (registry entry for a
   nonexistent route fails with a clear message).
4. All seven routes have probes covering the arms listed in pinned
   decision 3; every probe body passes the checker.
5. Checker self-tests pass: every stem, every value pattern, nested case,
   case-variant cases, and the clean-fixture no-false-positive case.
6. `FORBIDDEN_FIELD_STEMS` and `FORBIDDEN_VALUE_PATTERNS` exported from
   `@pca/shared`; suite imports them — no inline literals in apps/api.
7. No endpoint/schema/seed code modified.
8. All existing gates stay green: shared, api, db, taxonomy, web tests;
   lint, typecheck, format:check.
9. Worklog entry appended (deviations, findings, forward notes).

## Process

Submit an implementation plan BEFORE writing code. The plan must include:
the exact route-discovery mechanism, the probe registry shape, the
proposed docket-number regex(es), where the checker helper lives, and the
list of probes per route.