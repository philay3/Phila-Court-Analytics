# Task 7.3 — Judge Search Endpoint

## Standing rule
Respond with an implementation plan BEFORE writing any code. Wait for approval.

## Goal
Implement the public judge search endpoint:

GET /api/v1/public/judges/search?q={query}&limit={limit}

Searches seeded normalized judges and their aliases (6.3 data) and returns
public-safe judge suggestions. This is the near-mirror of the 7.2 charge
search endpoint and must reuse its conventions, helpers, and test patterns.

## Context
- ref.normalized_judges and ref.judge_aliases exist (6.1) and are seeded
  (6.3) with obviously fake judge names.
- 7.2 established: shared { results: [...] } envelope from @pca/shared,
  q/limit validation, LIKE-wildcard escaping, case-insensitive substring
  matching, exact → prefix → substring ranking with alphabetical tie-break,
  dedup across name/alias matches, and matchedAlias semantics.
- Judge search is optional in the product; nothing about this endpoint may
  imply judges are required or rankable.

## Design decisions (locked — mirror 7.2)
1. Matching: case-insensitive substring (ILIKE '%q%') against display_name
   and alias_text. Two match columns, not three — there is no statute
   equivalent for judges.
2. Ranking: exact match → prefix match → substring match, tie-broken
   alphabetically by display_name. Deterministic ordering is an acceptance
   criterion.
3. Dedup: a judge matching via both name and alias returns exactly once.
4. matchedAlias: populated ONLY when the display name itself did not match;
   if multiple aliases match, first alphabetically wins.
5. Only active judges (is_active = true) are returned, matching 7.2's
   behavior for charges.
6. Validation: identical q and limit rules as 7.2 (same min length, same
   default limit, same enforced maximum). Do not invent new values —
   reuse 7.2's constants; if they are inline in 7.2, extract them to a
   shared location both endpoints import.

## Scope
- New route in the public plugin: GET /api/v1/public/judges/search
- TypeBox request schema (q, limit) and response schema in @pca/shared,
  following the 7.2 pattern
- Response item fields — EXACTLY these, nothing more:
  - id (uuid)
  - slug
  - displayName
  - matchedAlias (optional, per rule 4)
- Repository/service layering consistent with 7.2's structure
- REUSE the 7.2 wildcard-escape helper and ranking logic where identical.
  Do not copy-paste the escape function. A generalized two-entity search
  abstraction is NOT required — propose one in the plan only if it
  simplifies rather than contorts; otherwise keep the queries separate.
- Errors flow through the 7.1 catalog passthrough (throw with catalog
  code; central handler shapes the response). INVALID_REQUEST for
  validation failures, consistent with 7.2.

## Acceptance criteria
1. Endpoint validates q and limit with the same rules as 7.2 (shared
   constants, not duplicated literals).
2. LIKE wildcards (% and _) in user input are escaped via the shared
   helper; q=% returns no spurious full-table match.
3. Searches normalized judges and aliases; results deduplicated; only
   is_active judges returned.
4. Ranking is deterministic: exact → prefix → substring, alphabetical
   tie-break; matchedAlias populated only on alias-only matches.
5. Response uses the { results: [...] } envelope; items contain ONLY
   id, slug, displayName, matchedAlias.
6. No aggregate statistics, counts, rankings, scores, or any numeric
   judge metadata appear anywhere in the response — including absence
   of fields like caseCount, resultCount, or sampleSize. An explicit
   test asserts the exact key set of a result item.
7. Tests mirror 7.2: exact match, prefix vs substring ordering, alias
   match (matchedAlias populated), name+alias dedup, no result (empty
   results array, 200), invalid query, limit default and max
   enforcement, wildcard-escape case, inactive judge excluded,
   exact-key-set assertion.
8. Typecheck, lint, format:check, and full test suite pass.
9. Worklog entry appended to tasks/worklog.md.

## Out of scope
- Result endpoints (8.1/8.2)
- Any judge statistics or aggregate lookups
- Fuzzy/trigram search (comes due in Sprint 5 with the real corpus,
  same as charges)
- Rate limiting
- Any changes to charge search behavior beyond extracting shared
  constants/helpers (extraction must be behavior-neutral; existing 7.2
  tests must pass unchanged)

## Files the agent may touch
- apps/api/src/** (public routes, services, repositories)
- packages/shared/src/** (judge search schemas, shared search constants)
- apps/api test files
- tasks/worklog.md