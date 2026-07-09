# Task 10.2 — Copy Safety Suite + Shared Constants Migration

## Goal

Make `@pca/shared` the single source of truth for public copy-safety rules
(forbidden terms, guarded disclaimer phrases, and the scanner itself), migrate
the existing web copy guard to consume it with no behavior change, and add an
API copy-safety test suite covering all public prose — static content sources
and live endpoint responses.

## Context

- The 4.1 web copy guard currently owns its own forbidden-term constants in
  `apps/web`.
- Task 9.2 exported `GUARDED_DISCLAIMER_PHRASES` as a named constant
  specifically so this task could migrate it mechanically.
- The 10.1 forbidden-field suite already inventories every public endpoint and
  walks responses; reuse its endpoint inventory pattern (do not duplicate a
  second hand-maintained endpoint list if the 10.1 inventory can be shared —
  extract it to a test helper both suites import).
- `CHARGE_RESULT_UNAVAILABLE_MESSAGE` and other pinned public message literals
  also migrate to `@pca/shared` as part of this task.

## Pinned design decisions (do not re-litigate)

1. New module: `packages/shared/src/public/copy-safety.ts`, exporting:
   - `FORBIDDEN_PUBLIC_TERMS` — the canonical term definitions (see list below),
     each with a case-insensitive, word-boundary-aware pattern
   - `GUARDED_DISCLAIMER_PHRASES` — migrated from its 9.2 location
   - `scanPublicCopy(text: string)` — returns structured violations
     (term matched, index/context); empty array = clean
2. Scanner algorithm is mask-then-scan: remove every guarded-phrase occurrence
   (case-insensitive) first, then scan the remainder with the forbidden-term
   patterns. No other exemption mechanism.
3. Forbidden terms (locked list):
   - `odds`
   - `predict` stem — matches predict, predicts, predicted, predicting,
     prediction(s), predictive
   - `likely sentence`
   - `best judge`
   - `worst judge`
   - `judge score`
   - `win rate`
   - `guaranteed`
   - `harsher`
   - `more lenient`
   `better` / `worse` are intentionally NOT in the mechanical list.
4. Word-boundary discipline: `odds` must not match inside other words;
   multi-word terms match across single spaces; matching is case-insensitive.
5. All consumers import from `@pca/shared` — no local copies, no inline
   forbidden-term literals anywhere in web or api after this task.

## Scope

### A. Shared package

- Create `copy-safety.ts` module as pinned above; export via the package's
  public entry point.
- Migrate `GUARDED_DISCLAIMER_PHRASES` and `CHARGE_RESULT_UNAVAILABLE_MESSAGE`
  (and any sibling pinned public message literals not yet in shared) into
  `@pca/shared`; update all existing imports.
- Unit tests for the scanner in `packages/shared`, including deliberate-failure
  probes:
  - bare `prediction` → violation
  - `not a prediction` (exact guarded phrase) → clean
  - text containing a guarded phrase AND a separate bare `predictive` →
    violation (masking one phrase must not launder the rest of the text)
  - `odds` inside a longer word → clean (word boundary)
  - `Win Rate` mixed case → violation
  - every entry in `GUARDED_DISCLAIMER_PHRASES` individually scans clean
  - every entry in `FORBIDDEN_PUBLIC_TERMS` individually produces a violation

### B. Web guard migration

- The 4.1 web copy guard deletes its local term constants and imports the
  shared module (constants and, if its check logic is replaceable one-for-one,
  the shared `scanPublicCopy`).
- Behavior change: none. Existing web guard tests pass with at most
  import-path edits.
- If the web guard's current local term list differs in ANY way from the
  locked list above, STOP and report the diff in your implementation plan —
  do not silently reconcile in either direction.

### C. API copy-safety suite

- New Vitest suite in `apps/api` that scans:
  1. Static sources: methodology content, data-coverage content, every message
     in the public error catalog, all pinned unavailable-message literals, and
     all public-visible taxonomy definitions from `@pca/taxonomy` artifacts.
  2. Live responses: `fastify.inject` against every public endpoint (success
     and unavailable/error variants), recursively collecting every string
     value in each JSON payload and asserting `scanPublicCopy` returns clean.
- Reuse/extract the 10.1 endpoint inventory so 10.1 and 10.2 cannot drift to
  different endpoint lists.
- Deliberate-failure probe: a test that injects a poisoned string through the
  scanner path used by the suite and asserts the suite mechanism actually
  fails on it (guards against a scanner that silently returns clean).

### D. CI

- Confirm both suites execute under the existing required test commands for
  their packages. No new workflow jobs. If anything does NOT run under an
  existing required command, report it in the plan before implementing.

## Acceptance criteria

1. `@pca/shared` exports `FORBIDDEN_PUBLIC_TERMS`, `GUARDED_DISCLAIMER_PHRASES`,
   and `scanPublicCopy`; no other package defines copy-safety terms.
2. Mask-then-scan behavior proven by the shared unit tests, including all
   listed probes.
3. Web guard imports from `@pca/shared`; zero behavior change; web tests green.
4. API suite scans both static sources and live responses for every public
   endpoint variant; all green.
5. `CHARGE_RESULT_UNAVAILABLE_MESSAGE` and `GUARDED_DISCLAIMER_PHRASES` are
   imported from `@pca/shared` everywhere they are used — grep confirms no
   duplicate literals remain in `apps/web` or `apps/api`.
6. Endpoint inventory is shared between the 10.1 and 10.2 suites (single
   definition).
7. All gates green: lint, format:check, typecheck, full test suites (shared,
   api, db, taxonomy, web), taxonomy validation, pytest.
8. One task, one commit (pre-existing format violations, if any, go in a
   separate prior chore commit).
9. Worklog entry appended, including any copy violations discovered.

## If the scan finds a real violation in existing copy

Do NOT rewrite the copy yourself. Stop, list every violation (file, term,
surrounding sentence) in your report, and wait for direction. Public copy
changes require planning-chat review.

## Out of scope

- Any rewording of methodology/data-coverage/definitions content
- Rate limiting
- Web UI changes beyond the guard's import migration
- DB taxonomy tables
- New CI workflow jobs

## Files you may touch

- `packages/shared/src/**` (new copy-safety module, entry point, tests)
- `apps/web` guard file(s) + their tests (import migration only)
- `apps/api` test files (new suite, shared endpoint-inventory helper) and
  import-path updates where migrated constants are consumed
- `tasks/worklog.md`

## First step

Submit your implementation plan for review before writing any code. The plan
must include: the current location and exact contents of the web guard's term
list (so we can verify it matches the locked list), the current location of
`GUARDED_DISCLAIMER_PHRASES` and `CHARGE_RESULT_UNAVAILABLE_MESSAGE`, and how
you will share the endpoint inventory with the 10.1 suite.