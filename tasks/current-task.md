# Task 9.1 — Public Definitions Endpoint

## Goal

Implement `GET /api/v1/public/definitions`, serving outcome and
sentencing category definitions directly from `@pca/taxonomy`
generated artifacts. No database dependency.

## Context

- Phase 9 of Sprint 2. Phases 6–8 are complete: ref.* and analytics.*
  tables, seeds, error catalog + FormatRegistry, charge/judge search,
  and both result endpoints exist.
- Standing decision: taxonomy is package-only through Sprint 2. The
  definitions endpoint reads the generated artifacts from
  `@pca/taxonomy` — it does NOT read `ref.*` or `analytics.*` tables,
  and it does NOT resolve an aggregate run. DB taxonomy tables are
  deferred to Sprint 7.
- apps/api already has a taxonomy module that filters categories to
  public-visible ones (used by the result endpoints for display
  names). REUSE that module and its public filter. Do not re-derive
  public filtering logic in the route/service.
- This endpoint is static per deploy: same response for every request
  until the taxonomy package version changes and the API is
  redeployed.

## Scope

1. Route: `GET /api/v1/public/definitions` in the existing public
   namespace plugin.
2. Response shape (add TypeBox schema + types to @pca/shared under
   src/public/, consistent with existing public contracts):
   - `taxonomyVersion: string` — from the @pca/taxonomy artifact
   - `outcomes: DefinitionEntry[]`
   - `sentencing: DefinitionEntry[]`
   - DefinitionEntry: `{ code: string, displayName: string,
     definition: string, sortOrder: number }`
3. Filtering: only categories with `public: true` appear. The
   `public` flag itself is NOT included in the response (it's
   internal metadata).
4. Ordering: entries sorted by `sortOrder` ascending in the response.
5. Response validation: attach the response schema to the route like
   the other public endpoints (Ajv serialization guard).
6. Error behavior: no new error codes. This endpoint has no not-found
   or unavailable state. Unexpected failures fall through to the
   existing central handler (INTERNAL_ERROR).

## Acceptance Criteria

- `GET /api/v1/public/definitions` returns 200 with taxonomyVersion,
  outcomes, and sentencing arrays.
- Every entry has code, displayName, definition, sortOrder — and
  nothing else. No `public` flag, no internal fields.
- Non-public categories (if any exist in seeds) are absent from the
  response; the filter comes from the existing apps/api taxonomy
  module, not new logic.
- Entries are ordered by sortOrder ascending.
- taxonomyVersion matches the @pca/taxonomy generated artifact
  version exactly.
- The handler chain performs NO database access. A test proves the
  endpoint succeeds via fastify.inject against an app instance whose
  DB is unavailable/not connected (or equivalent proof that no
  query executes).
- Definitions text is plain-English and contains no legal advice,
  prediction, odds, or ranking language (it comes from the taxonomy
  package, but assert the forbidden terms against the actual
  response body in this task's tests as a belt-and-braces check).
- Tests (Vitest + fastify.inject): success shape, public-only
  filtering, ordering, taxonomyVersion presence, no-DB proof,
  forbidden-term check on response text.
- Existing tests, lint, typecheck, format:check all pass.
- Worklog entry appended to tasks/worklog.md.

## Out of Scope

- Methodology and data coverage endpoints (Task 9.2).
- Any ref.outcome_categories / ref.sentencing_categories DB tables
  (deferred to Sprint 7).
- Caching headers / ETag / CDN concerns (revisit at launch readiness).
- Changes to taxonomy seed content or the taxonomy package's
  generation pipeline.
- The cross-cutting forbidden-field and copy safety suites (Phase 10).

## Files You May Touch

- apps/api/src/routes/public/** (new definitions route)
- apps/api/src/services/** or the existing taxonomy module location
  (wiring only — reuse, don't rewrite)
- apps/api/test/** (new test file)
- packages/shared/src/public/** (definitions schema + types, exports)
- packages/shared/test/** (schema tests if the package has them)
- tasks/worklog.md

Do not touch: db/**, services/pipeline/**, apps/web/**, migrations,
seeds, CI workflow.

## Process

Respond with an implementation plan BEFORE writing any code. The plan
will be reviewed and approved in the planning chat.