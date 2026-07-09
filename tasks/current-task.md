# Task 11.2 — Rewrites Proxy + Public API Client + Error Message Constants

## Goal

Give apps/web its data layer: a Next.js rewrites proxy so browser calls stay
same-origin, a typed client module covering all seven public endpoints, and
user-facing error-message constants in @pca/shared for all nine public error
codes. Delete the 11.1 import-proof page.

## Context

- Sprint 3, Phase 11 (frontend foundation). 11.1 landed per-package dist
  builds with conditional exports (`pca-source` source condition). next dev /
  next build resolve @pca/* to dist — run `pnpm run build:packages` before
  web work and after any @pca/shared edits in this task.
- The public API (Sprint 2) serves /api/v1/public/* on port 3001 (web on
  3000). Error responses use the flat shape
  `{ statusCode, code, error, message, requestId }` with the nine-code
  catalog in @pca/shared.
- The judge-unavailable message is a pinned literal in @pca/shared (8.2).
- Copy-safety terms/phrases/scanner live solely in @pca/shared; the 10.2
  suite scans shared public copy.

## Pinned design decisions (do not re-litigate; plan must conform)

1. Client functions return a tagged union:
   `{ ok: true, data: T } | { ok: false, error: PublicApiFailure }`.
   They never throw for expected outcomes.
2. `PublicApiFailure` is a discriminated union:
   - `{ kind: 'api_error', statusCode, code, error, message, requestId }`
     — any well-formed API error response
   - `{ kind: 'fetch_failed' }` — network failure, non-JSON body, or
     malformed error payload
   The nine-code public catalog is NOT extended. Transport failures are a
   client-side kind, not a fake API code.
3. @pca/shared exports `PUBLIC_ERROR_MESSAGES: Record<PublicErrorCode,
   string>` (all nine codes) plus a fetch-failure message constant. The
   JUDGE_SPECIFIC_RESULT_UNAVAILABLE entry references the existing pinned
   literal — the string is not re-typed anywhere.
4. Base URL: server-side fetches use env var `API_BASE_URL` (server-only,
   no NEXT_PUBLIC_ prefix); browser fetches use the relative
   /api/v1/public/* path via the rewrite. One client module handles both.
   No API URL in any client-delivered bundle.
5. The client trusts @pca/shared response types. No runtime revalidation of
   API responses in the web app.
6. If a new @pca/shared export subpath is needed, it extends the
   `pca-source` conditional-exports triple exactly as in 11.1.

## Scope

1. **Rewrites proxy**: `next.config.ts` rewrites `/api/v1/public/:path*` to
   the API using `API_BASE_URL`. Document the var in `apps/web/.env.example`
   (create if absent) with the local default `http://localhost:3001`.
2. **Message constants** in @pca/shared: `PUBLIC_ERROR_MESSAGES` covering
   all nine codes (INVALID_REQUEST, CHARGE_NOT_FOUND, JUDGE_NOT_FOUND,
   CHARGE_RESULT_UNAVAILABLE, JUDGE_SPECIFIC_RESULT_UNAVAILABLE,
   SENTENCING_RESULT_UNAVAILABLE, RATE_LIMITED, INTERNAL_ERROR, NOT_FOUND)
   plus the fetch-failure message. Plain-English, user-facing, no internal
   detail.
3. **Typed client** under `apps/web/app/lib/` with functions for: charge
   search, judge search, charge-only result, judge-specific result,
   definitions, methodology, data coverage. Uses @pca/shared response types
   and the tagged-union failure shape. No admin functions.
4. **Delete the 11.1 import-proof page** and its test if one exists.

## Acceptance criteria

- [ ] `next.config.ts` rewrite maps `/api/v1/public/:path*` to
      `${API_BASE_URL}/api/v1/public/:path*`; var documented in
      `apps/web/.env.example`; no NEXT_PUBLIC_ API URL anywhere; a grep/test
      asserts no API base URL string appears under `.next/static` output or,
      minimally, that no NEXT_PUBLIC_ API var is referenced in app/ code
- [ ] Client module exports typed functions for all seven endpoints; each
      returns the pinned tagged union; no function throws on an API error
      response or network failure (proven by tests)
- [ ] Well-formed API errors surface as `kind: 'api_error'` with all five
      flat-shape fields preserved (requestId retained for support use)
- [ ] Network failure, non-JSON response, and malformed error body each
      surface as `kind: 'fetch_failed'` (three distinct tests)
- [ ] `PUBLIC_ERROR_MESSAGES` covers exactly the nine catalog codes —
      a test asserts key set equality with the catalog so adding a tenth
      code later fails loudly until a message is added
- [ ] JUDGE_SPECIFIC_RESULT_UNAVAILABLE message is the pinned 8.2 literal
      by reference (test asserts identity via import, not a re-typed string)
- [ ] All new message constants pass `scanPublicCopy`, and the 10.2
      copy-safety suite demonstrably covers the file they live in (if the
      suite enumerates files/exports, extend it in this task)
- [ ] Messages contain no parser/extraction/review internals, odds,
      prediction, likely-sentence, ranking, or legal-advice language
- [ ] Server-side and browser-side base-URL resolution both proven by unit
      tests (env-var path and relative path)
- [ ] Import-proof page from 11.1 deleted; `next build` still green
- [ ] All gates green: lint, format:check, typecheck, tests (all packages),
      `next build`, CI config updated if any new step is required

## Out of scope

- Any page or component consuming the client (Phases 12–14)
- Tailwind/styling work (11.3), formatting utilities (11.4)
- CORS plugin on the API (rewrites make it unnecessary — standing decision)
- Client-side data libraries (SWR/React Query) — rejected, standing decision
- Runtime revalidation of API responses
- Rate-limiting implementation (RATE_LIMITED message only)
- Retry logic, caching policy tuning, request deduplication

## Files the agent may touch

- `apps/web/next.config.ts`
- `apps/web/.env.example`
- `apps/web/app/lib/**` (new client module + tests)
- `apps/web/app/**` (only to delete the import-proof page/test)
- `packages/shared/src/public/**` (message constants + tests)
- `packages/shared/package.json` (only if a new export subpath is required)
- 10.2 copy-safety suite files (only if coverage must be extended to the
  new constants file)
- Root/CI config only if a new build step is genuinely required (state why)

## Process

Respond with an implementation plan BEFORE writing code. The plan must state:
(a) whether a new @pca/shared export subpath is added or existing entries
suffice, (b) how the client detects server vs browser context, (c) how the
no-API-URL-in-client-bundle criterion will be verified, (d) exact message
text for all nine codes plus the fetch-failure message, for copy review.
After implementation, append a worklog entry to tasks/worklog.md and report
back with results against each acceptance criterion.