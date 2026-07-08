# Task 7.1 — Public Error Catalog + Format Registration

## Goal

Extend the existing error handling from task 1.3 with a stable public
error `code` field, define the public error code catalog in
`@pca/shared`, and make TypeBox string formats (`date`, `date-time`,
`uuid`) actually enforced in schema validation — closing the 3.2
worklog finding that unregistered formats pass silently.

## Context

- Sprint 2, Phase 7. Endpoints 7.2+ depend on this plumbing.
- The 1.3 error handler ships a flat shape:
  `{ statusCode, error, message, requestId }`. This shape is KEPT and
  extended with `code: string`. The nested `{ error: { ... } }`
  envelope is explicitly rejected (standing decision).
- The 3.2 worklog recorded that TypeBox schemas using
  `format: 'date'` etc. pass validation silently when the format is
  unregistered. This task must make malformed format values fail in
  the real request validation path.
- 5xx responses currently have message-leak protection (internal error
  messages are not echoed to clients). That protection must survive
  unchanged.

## Deliverables

### 1. Error code catalog in `@pca/shared`

- New module (e.g. `packages/shared/src/errors.ts`) exporting:
  - a const object of public error codes:
    `INVALID_REQUEST`, `CHARGE_NOT_FOUND`, `JUDGE_NOT_FOUND`,
    `CHARGE_RESULT_UNAVAILABLE`, `JUDGE_SPECIFIC_RESULT_UNAVAILABLE`,
    `SENTENCING_RESULT_UNAVAILABLE`, `RATE_LIMITED`, `INTERNAL_ERROR`
  - a derived union type (e.g. `PublicErrorCode`)
  - a TypeBox schema for the public error response shape:
    `{ statusCode, code, error, message, requestId }`
- `RATE_LIMITED` is defined only. No rate limiting middleware or
  implementation of any kind.
- Each code maps to a default HTTP status (documented in the module):
  INVALID_REQUEST→400, *_NOT_FOUND→404, *_UNAVAILABLE→404 (final
  status per code may be proposed in the plan; unavailable-state
  semantics are consumed by 8.1/8.2), RATE_LIMITED→429,
  INTERNAL_ERROR→500.

### 2. Error handler extension in `apps/api`

- Central error handler emits
  `{ statusCode, code, error, message, requestId }` for all error
  responses.
- Validation failures map to `INVALID_REQUEST` (400).
- Unmapped/unexpected errors map to `INTERNAL_ERROR` (500) with the
  existing message-leak protection intact: internal error messages
  never reach the client on 5xx.
- 404 for unknown routes carries an appropriate code (propose in plan;
  `INVALID_REQUEST` vs a generic not-found — do not invent new public
  codes beyond the catalog without flagging it).

### 3. Format registration

- `registerFormats()` exported from `@pca/shared` registering `date`,
  `date-time`, `uuid`. Idempotent.
- `buildApp` calls `registerFormats()` before any route/schema
  registration. No app instance can exist without formats registered.
- CRITICAL: the implementation plan must state which compiler actually
  validates incoming requests (Fastify's Ajv vs TypeBox TypeCompiler)
  and wire format enforcement into that real path. TypeBox
  FormatRegistry registration alone is insufficient if Ajv performs
  route validation.
- If `@pca/shared` schema tests compile schemas directly, a Vitest
  setup file calls `registerFormats()` there too.

## Acceptance criteria

1. Error responses from the API have exactly the shape
   `{ statusCode, code, error, message, requestId }`.
2. All eight codes exist in `@pca/shared` with a derived union type;
   API imports them from `@pca/shared` (no local re-definition).
3. A test proves a request with a malformed `format: 'date'` (or
   `uuid`) value is rejected with 400 + `INVALID_REQUEST` through the
   real request path (`fastify.inject`), where the same schema
   previously passed silently.
4. A test proves `registerFormats()` is idempotent (calling twice does
   not throw or change behavior).
5. A test proves 5xx responses do not leak internal error messages
   (existing protection retained, now with `code: INTERNAL_ERROR`).
6. No public error message mentions: parser confidence, extraction,
   review status, raw records, odket/docket internals, odds,
   predictions, legal advice, or internal IDs.
7. Existing 1.3 tests updated, not deleted; full suite green;
   lint/typecheck/format pass.

## Out of scope

- Any public endpoint (7.2 onward)
- Rate limiting implementation (code defined only)
- Copy-guard/forbidden-term test suites (10.1/10.2)
- Moving copy-guard constants to `@pca/shared` (10.2)
- Any `ref.*`/`analytics.*` queries or DB access changes

## Files the agent may touch

- `packages/shared/src/**` (new errors + formats modules, tests, index exports)
- `apps/api/src/**` (error handler, buildApp wiring, tests)
- Vitest setup/config files in those two workspaces only

## Process

Return an implementation plan BEFORE writing code. The plan must
explicitly answer: (a) which validator compiles request schemas today
and how formats reach it; (b) proposed status-code mapping for the
unavailable-state codes; (c) how idempotency of registerFormats() is
achieved. Append a worklog entry to tasks/worklog.md on completion.