# Task 7.2 — Charge Search Endpoint

## Standing rule
Respond with an implementation plan BEFORE writing any code. Wait for approval.

## Goal
Implement the first real public endpoint:

GET /api/v1/public/charges/search?q={query}&limit={limit}

Searches seeded normalized charges and their aliases (6.3 data) and returns
public-safe charge suggestions using the shared response envelope and the 7.1
error plumbing.

## Context
- ref.normalized_charges and ref.charge_aliases exist (6.1) and are seeded (6.3).
- Error catalog + central handler passthrough exist (7.1): endpoints throw
  errors carrying a catalog code; the handler shapes the response. Do NOT
  shape errors in the route.
- registerFormats() is already buildApp's first statement — do not move it.
- Ajv remains the request validator; do not switch validator compilers.

## Scope

### 1. Shared contracts (@pca/shared)
- TypeBox querystring schema: 
  - q: required string. Trimmed server-side; after trimming, length must be
    1–100. Empty/whitespace-only q → INVALID_REQUEST (400) via catalog throw.
  - limit: optional integer, default 10, min 1, max 25. Out-of-range or
    non-integer → INVALID_REQUEST (400).
  - additionalProperties: false.
- Response schema/type: { results: ChargeSearchResult[] } using the existing
  envelope convention. ChargeSearchResult fields (exactly these, camelCase):
  - id (uuid string)
  - slug
  - displayName
  - statuteCode (optional — omit or null per existing shared-type convention
    for optionals; be consistent with existing public types)
  - grade (optional, same convention)
  - matchedAlias (optional string)
- No counts, percentages, sample sizes, or aggregate fields of any kind.

### 2. Search behavior (apps/api)
- Repository layer reads ONLY ref.normalized_charges + ref.charge_aliases
  via Kysely. No analytics.*, no raw/parsed/fact/review/audit access.
- Only active charges are searchable (active-status column from 6.1).
- Matching: case-insensitive substring (ILIKE) against:
  a. normalized_charges.display_name
  b. charge_aliases alias text
  c. normalized_charges.statute_code (nullable — skip nulls)
- LIKE-wildcard escaping: escape %, _, and the escape character itself in
  user input before building the pattern (use an explicit ESCAPE clause).
  q="%" must NOT match everything; it matches only literal-% content
  (i.e., returns empty against seeded data).
- Ranking (deterministic):
  1. exact match (case-insensitive equality) on display name, alias, or
     statute code
  2. prefix match on any of the three
  3. substring match
  Tie-break: display_name ascending. Rank is computed across the best match
  the charge achieves via ANY of name/alias/statute.
- Deduplication: each charge appears at most once regardless of how many
  fields/aliases matched.
- matchedAlias: populated ONLY when the display name itself did not match
  (i.e., the result is present because of an alias). If multiple aliases
  matched, use the alphabetically first matching alias. Never populate it
  for statute-code-only matches.
- limit applied after ranking/dedup.
- No results is a SUCCESS: 200 with { results: [] }. Not an error, not 404.

### 3. Route wiring
- Route registered in the existing /api/v1/public namespace plugin.
- Request validation via the shared TypeBox schemas through Fastify's
  schema option (Ajv path).
- Layering per architecture: route → validation → service → repository.
  Keep it thin; no business logic in the route handler.

### 4. Tests (Vitest + fastify.inject, seeded local DB)
Required cases:
- exact display-name match returns the charge ranked first
- alias match returns the parent charge with matchedAlias populated
- substring match (e.g. "theft" → Retail Theft)
- case-insensitivity (upper/lower/mixed q)
- dedup: a charge whose name AND alias both match appears exactly once;
  matchedAlias absent (name matched)
- statute-code match returns the charge WITHOUT matchedAlias
- no match → 200 { results: [] }
- missing q → 400 INVALID_REQUEST (catalog shape: statusCode, code, error,
  message, requestId)
- whitespace-only q → 400 INVALID_REQUEST
- limit default (10) and max (25) enforced; limit=0 and limit=26 → 400
- q="%" and q="_" return empty (wildcard escaping proof)
- forbidden-content assertion: response JSON contains no counts,
  percentages, sampleSize, docket/defendant/source/parser/review fields
- inactive charge (insert one in test setup or via seed helper) is never
  returned

## Out of scope
- judge search (7.3)
- fuzzy/trigram search, pg_trgm, full-text search (comes due at Sprint 5
  normalization when the real charge corpus exists)
- pagination beyond limit
- rate limiting (RATE_LIMITED remains defined-only)
- any migration or seed changes (if seeds prove insufficient for a test
  case, say so in the plan — do not silently modify them)
- caching

## Files you may touch
- packages/shared/** (new schemas/types + exports only; no changes to the
  error catalog or format registration)
- apps/api/** (route, service, repository, tests)
- tasks/worklog.md (on completion)

Do NOT touch: db migrations, db/seeds, apps/web, services/pipeline,
CI workflow.

## Acceptance criteria
1. GET /api/v1/public/charges/search works against seeded data with the
   exact field list above — nothing more.
2. Validation, defaults, and limits enforced exactly as specified; all
   errors flow through the 7.1 catalog/handler (no per-endpoint shaping).
3. Matching, ranking, dedup, matchedAlias, and wildcard-escaping semantics
   as specified, with tests proving each.
4. Repository reads only ref.* tables; inactive charges excluded.
5. All listed tests pass; pnpm lint / typecheck / test green at root.
6. Worklog entry appended.