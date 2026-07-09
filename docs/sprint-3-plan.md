# Sprint 3 Plan: Seeded Public UI

## Sprint 3 Goal

Build the first usable public website experience on top of the Sprint 2 seeded
public API.

By the end of Sprint 3, a user can:

- land on the homepage and search for a charge
- optionally add a judge
- view a Philadelphia-wide charge result
- view a judge-specific result beside the Philadelphia baseline
- see outcome and sentencing distributions as tables and bars
- see sample sizes, date ranges, and thin-data warnings on every figure
- hit the judge-unavailable and sentencing-unavailable fallbacks safely
- read definitions, methodology, and data coverage served from the API
- understand results are historical distributions, not predictions or legal
  advice

Sprint 3 consumes the seeded API only. No PDF parsing, no real aggregates.
Real data replaces the seeds in Sprint 7; everything built here is permanent.

---

## Locked Sprint 3 Scope

### In Scope

- Workspace package build/runtime fix (the broken `start` script — carried
  decision from Sprint 2 close)
- Next.js rewrites proxy for browser → API calls
- Typed public API client + shared error-message constants
- Tailwind v4 styling foundation (token migration from 4.1 globals)
- Shared frontend formatting utilities
- Homepage search experience
- Charge autocomplete; optional judge autocomplete; submission flows
- Charge-only result page
- Judge-specific result page with Philadelphia baseline
- Judge-unavailable and sentencing-unavailable UI states
- Outcome and sentencing distribution tables + HTML/CSS bar displays
- Sample size, date range, thin-data, and responsible-use components
- Definitions, methodology, and data-coverage pages consuming the Sprint 2
  endpoints (static placeholder copy dropped)
- About page
- Loading, empty, error, and no-result states (baked into each page task)
- Mobile-responsive layouts and accessibility pass
- Playwright E2E suite with axe-core assertions + dedicated CI E2E job
- Copy-guard coverage of all new public copy (automatic via `app/` placement)

### Out of Scope

- real UJS PDF ingestion or parsing
- admin review UI or admin authentication
- real aggregate generation
- production deployment
- product analytics
- SEO/indexing enablement (site-wide `noindex` stays; launch-readiness item)
- chart libraries (HTML/CSS bars this sprint; revisit at Sprint 8 staging
  review if richer visuals are wanted — table contract unchanged either way)
- CORS plugin on the API (rewrites proxy makes it unnecessary; revisit only
  if a non-proxy consumer appears)
- attorney referral features, legal advice workflows
- images/`sharp` (allowBuilds `sharp: false` stands; revisit only if a task
  actually introduces image processing — none planned)

---

## Sprint 3 Standing Decisions

These extend the Sprint 1/2 decisions and are locked:

1. **Workspace packages get a real runtime story.** Plain-node execution of
   built output (`pnpm --filter @pca/api start`) must work, and `apps/web`
   must be able to import `@pca/shared` in `app/` code. Task 11.1 states the
   goals; the agent proposes the mechanism (per-package `dist` builds +
   exports maps is the expected shape) for review before implementation.
   Production (Sprint 9) requires plain-node or bundled runtime regardless —
   `transpilePackages`-only is rejected as papering over web while leaving
   `start` broken.
2. **Styling: Tailwind v4**, CSS-first config. The 4.1 design tokens migrate
   into `@theme`. Semantic-HTML discipline from 4.1 is preserved — Tailwind
   styles it, it does not replace it. No component UI library.
3. **Charting: no library.** Distributions render as accessible HTML/CSS
   horizontal bars paired with the required tables. Bars use API-provided
   percentages only; the frontend never calculates core analytics.
4. **Data fetching split.** Server components fetch the API directly using a
   server-side base-URL env var. Browser-originated calls (autocomplete) go
   through Next.js rewrites (`/api/v1/public/*` → API), staying same-origin —
   no CORS, no API base URL in client bundles. No client data library.
5. **`/search` route dropped.** The homepage is the search surface. A
   dedicated search page, if ever wanted, is additive later.
6. **All web components and public copy live under `app/`** (e.g.
   `app/components/`, `app/lib/`), so the 4.1 copy-guard walker covers new
   copy automatically. Any file outside `app/` containing public copy must
   extend the walker in the same task — no silent gaps.
7. **Frontend user-facing message strings live in `@pca/shared`** and pass
   the copy-safety scanner. The judge-unavailable message renders the pinned
   `@pca/shared` literal — never re-typed in web code.
8. **Content pages consume the API.** `/methodology`, `/data-coverage`, and
   `/definitions` render the Sprint 2 endpoint responses and drop their
   static placeholder copy (9.2 worklog directive). The seeded-data
   disclosure exists in exactly two API content spots — the web must not
   create a third paraphrase.
9. **E2E: Playwright + axe-core**, one suite covering flows and rendered-page
   accessibility. Rendered-page copy/privacy assertions reuse
   `scanPublicCopy` (`@pca/shared`) and the 10.1 `ForbiddenViolation` checker
   — no new term lists anywhere.
10. **CI E2E job** runs `pnpm generate` → migrate → real `db:seed` (not the
    vitest globalSetup path) → boots API (fixed `start` path) and web via
    Playwright `webServer` → runs flows. Follows the 10.1 fail-loud-in-CI
    precedent; no hardcoded Postgres port (CI 5432 vs local 5433);
    `playwright install --with-deps` with browser caching.
11. **Loading/empty/error states belong to their page tasks**, not a separate
    phase. Per-component tests belong to their component tasks. Phase 15
    holds only cross-cutting work (a11y pass, E2E, exit demo).
12. **Site-wide `noindex` stays** through Sprint 3 (launch-readiness
    revisits).
13. **Phase numbering continues from Sprint 2**: Phases 11–15.

---

## MVP Data Range (restated)

MVP data coverage starts **January 1, 2025**. All rendered date ranges come
from API metadata; the frontend never invents or defaults date values. The
data-coverage page must display the 2025-01-01 start date as served.

---

## Technical Assumptions (carried)

| Area | Choice |
|---|---|
| Frontend | Next.js 16 App Router (hand-scaffolded shell from 4.1), React 19 |
| API source | Sprint 2 seeded public API, `/api/v1/public` |
| Ports | web 3000 / api 3001 (5.2b convention) |
| Shared contracts | `@pca/shared` (types, error codes, copy-safety scanner, pinned literals) |
| Styling | Tailwind v4 (this sprint's decision) |
| Component tests | Vitest (+ testing-library/jsdom added in Phase 13) |
| E2E | Playwright + axe-core (this sprint's decision) |
| Data | Seeded aggregates from the published run |

---

# Phase 11 — Frontend Foundation

## Task 11.1 — Workspace Package Build + Runtime Fix

Fixes the broken `start` script and unblocks web imports of `@pca/shared`.
Root cause (recon-confirmed): packages ship raw TS whose `.js`-extension
internal imports only resolve under tooling; plain node dies on the first
re-export.

The agent's implementation plan must propose the mechanism and cover:
`@pca/shared`, `@pca/taxonomy` (generated artifacts interplay), `@pca/db`.

Acceptance criteria:

- `pnpm --filter @pca/api build` then `pnpm --filter @pca/api start` serves
  requests under plain node — the recon repro is dead
- a trivial `app/` page (or the 11.2 client) importing `@pca/shared` passes
  `next build` — proven in this task or explicitly proven by 11.2, stated
  which in the plan
- fresh-clone ordering works: root scripts guarantee `generate` and any new
  package builds run before typecheck/test/build consumers
- `dev` workflows (tsx watch, next dev) unchanged
- CI updated for any new build steps; all gates green
- no behavior change to any package's public API surface

## Task 11.2 — Rewrites Proxy + Public API Client + Error Message Constants

Acceptance criteria:

- `next.config.ts` rewrites `/api/v1/public/*` to the API using a
  server-side env var (documented in `.env.example`); no API URL appears in
  client-delivered code
- typed client module under `app/lib/` with functions for: charge search,
  judge search, charge-only result, judge-specific result, definitions,
  methodology, data coverage — using `@pca/shared` response types; no admin
  functions
- client handles the flat error shape `{ statusCode, code, error, message,
  requestId }` and surfaces a typed result the UI can branch on
- user-facing message constants for all nine public error codes added to
  `@pca/shared`, passing the copy-safety scanner; web imports them — no
  inline user-facing strings
- messages avoid: parser/extraction/review internals, odds, prediction,
  likely sentence, legal advice
- tests: client success/error mapping, rewrite config presence, constants
  pass `scanPublicCopy`

## Task 11.3 — Tailwind v4 Styling Foundation

Acceptance criteria:

- Tailwind v4 installed and working with Next 16/Turbopack; any required
  allowBuilds entries handled deliberately (named in the plan)
- 4.1 design tokens migrated into `@theme`; `globals.css` reduced to tokens +
  base element styles; no visual regression to shell pages beyond intended
  restyling
- layout shell (header/nav/main/footer) restyled: calm civic tone, restrained
  palette, visible focus states preserved
- semantic HTML preserved; no class-soup replacing structure
- typecheck, lint, format, existing tests green

## Task 11.4 — Shared Frontend Formatting Utilities

Acceptance criteria:

- utilities under `app/lib/` for: count, percentage, sample size, date range,
  last-refreshed, result-type labels, thin-data reason labels
- percentages never rendered without counts available; date ranges
  human-readable; all values sourced from API metadata
- unit tests for each utility, including edge cases (zero counts, missing
  optional fields)

---

# Phase 12 — Search Experience

## Task 12.1 — Homepage Search Layout

Acceptance criteria:

- `/` presents charge search as the primary input; judge input visibly
  optional
- plain-language, historical-distribution framing; links to methodology and
  data coverage
- copy passes the guard (lives under `app/`); no prediction/odds/legal-advice
  /ranking language
- responsive on mobile and desktop; keyboard-reachable controls

## Task 12.2 — Charge Autocomplete

Acceptance criteria:

- `ChargeSearchInput` client component using the proxied search endpoint via
  the 11.2 client; debounced input
- loading, no-result, and error states; no-result copy suggests alternate
  spellings/common names and never asserts the charge doesn't exist
- full keyboard support: arrow navigation, Enter selects, Escape closes;
  visible focus; screen-reader accessible (labels + ARIA per combobox
  pattern)
- selection routes to `/charges/[chargeSlug]`
- component tests: loading, selection, no-result, keyboard selection

## Task 12.3 — Judge Autocomplete + Submission Flows

Acceptance criteria:

- `JudgeSearchInput` client component, clearly labeled optional; no-result
  state explains charge-only results remain available
- charge-only submission works with judge input empty; judge input never
  blocks submission
- charge + judge selection routes to `/charges/[chargeSlug]/judge/[judgeSlug]`
- same keyboard/a11y bar as 12.2
- component tests mirror 12.2 plus the optional-label and combined-flow cases

---

# Phase 13 — Result Pages

## Task 13.1 — Distribution + Metadata Display Components

Adds testing-library/jsdom to the web test setup (first component-render
tests).

Acceptance criteria:

- generic distribution table component (works for outcome and sentencing):
  category display name, definition access, count, percentage, applicable
  sample size; taxonomy sort order; count and percentage always together
- HTML/CSS horizontal bar display paired with the table; API percentages
  only; not color-only (labels/values on bars); accessible description; no
  chart library
- `SampleSizeLabel`, `DateRangeLabel`, `ThinDataBadge`, `ThinDataCallout`,
  `ResponsibleUseNotice` components; thin-data copy plain-English,
  non-ranking, non-predictive; responsible-use copy states historical
  aggregates, not legal advice, not predictions, individual cases vary
- all copy in these components ships as constants passing the guard
- component tests: table renders count+percentage+sample size, bars match
  percentages, thin-data renders from API metadata, responsible-use renders

## Task 13.2 — Charge-Only Result Page

`/charges/[chargeSlug]` (server component fetch).

Acceptance criteria:

- renders: charge name, Philadelphia-wide label, date range, last refreshed,
  outcome distribution (table + bars) with outcome sample size, sentencing
  distribution with separate sentencing sample size when available,
  per-distribution thin-data states, responsible-use notice, methodology and
  definitions links
- sentencing-unavailable state: outcome still renders; unavailable callout
  with methodology link; page never fails wholesale
- `CHARGE_NOT_FOUND` and `CHARGE_RESULT_UNAVAILABLE` render friendly states
  using the 11.2 shared messages
- optional judge-filter entry point routing to the judge-specific page,
  explaining availability isn't guaranteed for every pair
- loading state (route-level) with non-predictive copy
- mobile order: summary → responsible-use → thin-data → outcome → sentencing
  → links; no horizontal scroll
- tests: success render, thin-data charge, sentencing-unavailable charge,
  not-found state, metadata presence (sample size, date range, taxonomy-safe
  rendering)

## Task 13.3 — Judge-Specific Result Page

`/charges/[chargeSlug]/judge/[judgeSlug]` (server component fetch).

Acceptance criteria:

- renders: charge and judge names, judge-specific label, judge-specific
  outcome distribution, Philadelphia baseline outcome distribution,
  judge-specific and baseline sentencing where available, separate sample
  sizes for every group, date ranges, per-distribution thin-data,
  responsible-use notice
- neutral labels only — never better/worse, harsher/more lenient, best/worst,
  scores, rankings
- judge-unavailable fallback renders the pinned `@pca/shared` message
  verbatim with a link to the charge-only result; no internal reasons
- "View Philadelphia-wide result instead" removal action routes to
  `/charges/[chargeSlug]`
- missing charge/judge render friendly not-found states
- mobile order matches 13.2 with baseline comparison after sentencing
- tests: success with baseline, thin-data pair, unavailable-pair fallback
  (pinned literal asserted via import, not re-typed), removal action,
  metadata presence

---

# Phase 14 — Content Pages

## Task 14.1 — Definitions Page (API-backed)

Acceptance criteria:

- `/definitions` renders outcome and sentencing definitions from
  `GET /api/v1/public/definitions`; static placeholder copy removed
- taxonomy version displayed; taxonomy sort order respected
- result-page definition links/drawers target this content (anchor or
  in-page access pattern proposed by agent)
- mobile-friendly; loading and error states; tests

## Task 14.2 — Methodology + Data Coverage Pages (API-backed)

Acceptance criteria:

- `/methodology` renders the methodology endpoint response; static copy
  dropped (closes the 9.2 worklog directive)
- `/data-coverage` renders the data-coverage endpoint response including the
  2025-01-01 start date, data end, last refreshed, known limitations
  (including the seeded-data disclosure exactly as served — no paraphrase)
- no source-document, docket, defendant, or parser-internal content can be
  rendered (the API doesn't send it; the page must not add any)
- loading and error states; tests including "renders limitations as served"

## Task 14.3 — About Page

Acceptance criteria:

- `/about` explains site purpose, historical-aggregate focus, public-data
  source concept, responsible-use framing, no individual legal advice
- copy passes the guard; mobile-friendly

---

# Phase 15 — Quality Gate + Sprint Close

## Task 15.1 — Accessibility + Mobile Pass

Cross-cutting sweep after all pages exist.

Acceptance criteria:

- semantic heading hierarchy on all public pages; tables have proper headers;
  bars have text/table equivalents confirmed; thin-data warnings
  text-accessible; no hover-only or color-only meaning
- keyboard walkthrough of full flow (home → autocomplete → result → judge →
  removal → content pages) documented in the report; focus visible
  throughout; logical tab order; Escape/Enter behavior verified
- mobile viewport check of every public page; core content order per 13.2/
  13.3; no horizontal scrolling
- fixes applied where checks fail; findings worklogged

## Task 15.2 — Playwright E2E + axe-core + CI Job

Acceptance criteria:

- Playwright installed; suite covers: homepage load, charge search →
  charge-only result, add judge → judge-specific result with baseline,
  remove filter, judge-unavailable fallback, sentencing-unavailable render,
  definitions/methodology/data-coverage pages, mobile viewport result page
- axe-core assertions on every visited page; zero violations at the
  configured standard (WCAG 2.2 AA target)
- rendered-page copy assertions reuse `scanPublicCopy`; rendered-page
  privacy assertions reuse the 10.1 `ForbiddenViolation` checker — no new
  term lists
- Playwright `webServer` boots API via the fixed `start` path and web via
  production build
- dedicated CI E2E job: `pnpm generate` → migrate → `db:seed` → E2E; required
  check; fail-loud when CI env present; no hardcoded DB port; browser
  caching; 15-minute-budget conscious
- suite green locally and in CI

## Task 15.3 — Human Step: Exit Demo + Sprint Close

Chops runs the exit demo and reviews in the planning chat:

1. Homepage loads; search "retail" → suggestions → charge-only result
2. Distributions render as table + bars; sample size and date range visible
3. Thin-data warning appears on the seeded thin-data example
4. Add seeded fake judge → judge-specific result beside baseline
5. Remove filter → charge-only result
6. Trigger judge-unavailable pair → pinned fallback message
7. Sentencing-unavailable charge → outcome persists, callout renders
8. Definitions, methodology, data coverage load from API; 2025-01-01 visible
9. Mobile viewport walkthrough
10. Full CI green including the new E2E job

Sprint 3 closes here; Sprint 4 (Parser Proof of Concept) planning begins.

---

## Sprint 3 Definition of Done

1. `start` works under plain node; web imports `@pca/shared` in `app/` code.
2. Tailwind v4 foundation in place; tokens migrated; shell restyled.
3. Rewrites proxy live; typed client covers all seven endpoints; error
   messages are shared constants.
4. Homepage search works; charge autocomplete works; judge autocomplete works
   and is clearly optional; both submission flows route correctly.
5. Charge-only page shows all required metadata, distributions, thin-data,
   responsible-use, and handles sentencing-unavailable and not-found.
6. Judge-specific page shows baseline beside judge data with separate sample
   sizes and handles the unavailable pair via the pinned message.
7. Every figure shows its sample size; every result shows date range;
   sentencing sample size is separate from outcome sample size.
8. Definitions, methodology, and data-coverage pages render API content;
   static placeholder copy is gone; 2025-01-01 start date visible.
9. About page exists.
10. All new copy lives under `app/` and the copy guard passes; no
    prediction/odds/legal-advice/ranking language anywhere.
11. Accessibility and mobile passes complete; axe-core clean in E2E.
12. Playwright E2E suite passes locally and as a required CI job seeded via
    `db:seed`.
13. Site remains `noindex`.
14. Exit demo reviewed; sprint closed in the planning chat.

---

## Sprint 3 Risks (with mitigations locked)

1. **Package build rework destabilizes working dev flows** → 11.1 acceptance
   explicitly preserves tsx/next dev; plan-gated mechanism review before code.
2. **Frontend payload assumptions drift from API** → client uses `@pca/shared`
   types exclusively; no local mock shapes.
3. **UI accidentally sounds predictive** → all user-facing strings are shared
   constants under the scanner; guard covers `app/` automatically; E2E
   re-scans rendered pages.
4. **Judge-specific UI reads as ranking** → neutral labels enforced in 13.3
   acceptance; baseline framing only.
5. **Charts hide context** → tables are primary; sample size and date range
   render outside any hover state; bars are supplementary.
6. **Copy forks between API and web** → content pages render API responses;
   static copy deletion is an acceptance criterion; pinned literals imported.
7. **E2E flakiness in CI** → seeded deterministic data, Playwright webServer
   readiness checks, fail-loud precedent, browser caching.

## Handoff to Sprint 4

Sprint 4 (Parser Proof of Concept) begins when the exit demo passes: the
public UI works end-to-end against the seeded API, payload shapes are
validated by real consumption, and all unavailable states render safely.
Sprint 4 starts from the Capstone parser port-and-harden plan with the
fixture corpus staged outside the repo.