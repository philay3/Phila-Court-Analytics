# Accessibility + Mobile Pass — Task 15.1

Static (code) audit of every public page, state, and shared component against
the task 15.1 checklist (target standard: WCAG 2.2 AA). This document records the
**agent code audit** (half 1) and reserves a section for the **human interactive
walkthrough** (half 2). Task 15.2 layers automated E2E + axe-core on top of this
pass — see "Forward notes for 15.2".

Method: static analysis of markup, component structure, Tailwind classes, ARIA
wiring, copy modules, and DOM source order. Repo-wide greps were used to prove
negatives (no `outline-none`, no positive `tabindex`, no `hover:`-gated meaning,
no `title=` tooltips, no fixed pixel widths). No runtime tooling was installed
(Playwright/axe-core are 15.2).

## Surface audited

Pages: `/` ([page.tsx](../apps/web/app/page.tsx)), charge result
([ChargeOnlyResultView](../apps/web/app/components/ChargeOnlyResultView.tsx)),
judge result
([JudgeSpecificResultView](../apps/web/app/components/JudgeSpecificResultView.tsx)),
`/definitions`, `/methodology`, `/data-coverage`, `/about`. Admin is out of scope.

States: charge `loading` / `error` / `not-found` / `unavailable`; judge
`loading` / `error` / in-page `not-found` / `unavailable`; content-page
`loading` and inline error states.

Shared components: layout shell, `DistributionSection`, `ThinDataBadge`,
`ThinDataCallout`, `ResponsibleUseNotice`, `SampleSizeLabel`, `DateRangeLabel`,
`SentencingUnavailableNotice`, the combobox hook (`combobox-search`),
`ChargeSearchInput`, `JudgeSearchInput`, `SearchForm`, `JudgeFilterEntry`.

## Findings summary

**Agent code audit — 1 finding, fixed.** Two terminal not-found states rendered no
page heading (`<h1>`), while every other state (error, unavailable) already carries
one. All other checklist sections passed clean; details below.

**Human walkthrough — a11y/mobile clean; 3 functional findings, fixed.** The
keyboard + 320px/390px mobile passes found no accessibility issues beyond the
`h1` fix. Three functional findings surfaced and were fixed in this task: a
missing judge-route mapping for `CHARGE_RESULT_UNAVAILABLE` (a designed state
rendering as a generic error), an `API_BASE_URL` fallback inconsistency between
the two fetch paths, and an `apps/web` env setup-doc gap. See "Human interactive
walkthrough findings" below.

---

## Checklist results

### Structure

- **One `h1` per page; headings descend without skips** — **FINDING (fixed).**
  Every page and terminal state carries exactly one `<h1>` **except** the two
  not-found views, which rendered only a `<p>` + link:
  - [charges/[chargeSlug]/not-found.tsx](../apps/web/app/charges/[chargeSlug]/not-found.tsx)
  - [components/ResultNotFoundView.tsx](../apps/web/app/components/ResultNotFoundView.tsx)
    (the judge route's in-page soft-404 for missing charge / missing judge)

  A screen-reader user navigating by heading landed on a page with no heading.
  **Fix:** added an `<h1>` to both, sourced from a new
  `CHARGE_RESULT_COPY.notFoundHeading` constant (`"Result not found"`), mirroring
  the error state's heading-plus-body pattern. Heading assertions added to both
  test suites to guard against regression. Copy change called out below.

  Elsewhere heading order is clean: home `h1 → h2` (sr-only search heading);
  content pages `h1 → h2` per section (definitions add `h3` per entry, no skip);
  result pages `h1 → h2` (judge/baseline sections, judge-filter). Distribution
  titles are `<caption>` elements, not headings, so they do not affect the
  heading tree.

- **Landmark structure** — **PASS.** The 11.3 shell
  ([layout.tsx](../apps/web/app/layout.tsx)) provides `header` > `nav[aria-label]`,
  `main`, and `footer`; all page content renders inside `main`. Result pages use
  `<aside>` (responsible-use) and `role="note"` (thin-data / sentencing-
  unavailable) appropriately. No content sits outside a landmark.

- **Distribution tables use `<th>` with correct `scope`** — **PASS.**
  [DistributionSection.tsx](../apps/web/app/components/DistributionSection.tsx)
  uses `<th scope="col">` for the three column headers and `<th scope="row">` for
  each category row header, with a `<caption>` naming the distribution and the
  `<section>` labelled by the caption id.

- **Definition access not hover-only** — **PASS.** Per-row definition access is a
  real `<a>` link with visible text ("Definition") and an explicit
  `aria-label` ("Definition of <category>"); on the definitions page each entry
  is a `<dt>`/`<dd>` pair. No hover/tooltip mechanism anywhere.

### Charts / bars

- **Every bar display has its paired table present AND visible** — **PASS**
  (per the 13.1 standing decision confirmed for this task: the table is the
  primary display, bars are supplementary). In `DistributionSection` the semantic
  `<table>` renders first and fully visible; the bar block is
  `aria-hidden="true"` and is the supplement — not the reverse. No paired table
  is `sr-only`.

- **Bars carry text labels/values** — **PASS.** Each bar row renders the category
  `displayName` and `count · percentage` as visible text; meaning never depends
  on bar length or the `bg-accent` fill color alone.

- **Bar percentages from API via 11.4 formatters** — **PASS.** Fill width is
  `style={{ width: `${row.percentage}%` }}` straight from the API value; visible
  figures use `formatCount` / `formatPercentage`. No client-side analytics; no
  regression from counts.

### Thin data / warnings

- **Thin-data badge + callout are real, announced text** — **PASS.**
  [ThinDataBadge](../apps/web/app/components/ThinDataBadge.tsx) renders the pinned
  `formatThinDataLabel` text inside a bordered `<span>`;
  [ThinDataCallout](../apps/web/app/components/ThinDataCallout.tsx) renders
  `role="note"` with plain-text body. Both are text in the DOM, not icon-only or
  color-only, and are rendered from API thin-data flags only.

### Keyboard / focus (static)

- **Native elements or correct role + handlers** — **PASS.** All actionable
  elements are native `<button>` / `<a>` / `<input>`, except the two autocomplete
  comboboxes, which implement the WAI-ARIA combobox pattern (see below).

- **No positive `tabindex`; DOM order matches reading order** — **PASS.** Grep for
  `tabIndex` across `apps/web/app` returns nothing; layouts are single-column DOM
  source order with no CSS `order`.

- **Focus visible on every interactive element** — **PASS.** Grep for
  `outline-none` returns nothing, so no focus suppression exists. Links get the
  global `a:focus-visible` outline (globals.css) plus explicit
  `focus-visible:outline-*` utilities; buttons carry explicit
  `focus-visible:outline-2 outline-offset-2 outline-accent`; text inputs retain
  the user-agent focus ring (never removed). _Note for 15.2:_ inputs rely on the
  UA default ring — worth an axe/visual confirmation but not a failure.

- **Autocomplete: arrow / Enter / Escape + ARIA** — **PASS.** The shared
  [combobox-search](../apps/web/app/components/combobox-search.ts) hook handles
  ArrowUp/Down (wrapping, reopen-on-arrow), Enter (selects the active option or
  falls through to submit when the list is closed), Escape (first closes, second
  clears), and Tab (closes without trapping). ARIA is correct on the input
  (`role="combobox"`, `aria-autocomplete="list"`, `aria-expanded`,
  `aria-controls`, `aria-activedescendant`, `aria-describedby`) and the list
  (`role="listbox"`, `role="option"`, `aria-selected`), with collision-proof
  `useId` wiring and an `sr-only` instructions node and a `role="status"`
  live region.

### Mobile (static)

- **Result-page DOM order matches 13.2/13.3 priority** — **PASS.** Verified by
  `data-testid` source order. Charge-only: summary → responsible-use →
  thin-data → outcome → sentencing → links (→ judge-filter). Judge: summary →
  responsible-use → thin-data → judge outcome → judge sentencing → baseline
  outcome → baseline sentencing → links (baseline after judge sentencing).

- **No fixed widths forcing horizontal scroll at 320px** — **PASS.** Grep for
  `w-[…]` / `min-w-[…]` / `min-w-*` returns nothing; widths are `w-full` /
  `max-w-content` / flex-wrap.

- **Tables have an overflow strategy that preserves header association** —
  **PASS.** Each `DistributionSection` is wrapped in `overflow-x-auto`, so the
  whole table scrolls as a unit — `<th>`/`scope` associations are intact and no
  data is hidden.

### Copy / meaning

- **No hover-only critical information** — **PASS.** Grep finds no `title=`,
  no `group-hover`, and no `hover:` class beyond `hover:underline` /
  `hover:opacity` (pure visual affordances). All meaning is present without hover.

- **No color-only meaning** — **PASS.** Thin data is text; the active combobox
  option is conveyed by `aria-selected` + `aria-activedescendant` (not only the
  `bg-canvas` highlight); bars are `aria-hidden` with a full text/table
  equivalent.

### States without an `h1` — intentional pass

Route-level `loading.tsx` placeholders (all sections) render a single
`role="status"` paragraph with neutral copy and **no** `h1`. This is intentional
and accepted: they are transient, announced via the live region, and replaced by
the full content (which carries the `h1`). Adding a heading that immediately
unmounts would be worse for AT. Documented here rather than "fixed".

---

## Fixes applied

| #   | Finding                                     | Files                                                                                                                                                                                                                                                                                                                                                                                             | Notes                                                                                                        |
| --- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| 1   | Two terminal not-found states had no `<h1>` | [charge-result-copy.ts](../apps/web/app/components/charge-result-copy.ts), [not-found.tsx](../apps/web/app/charges/[chargeSlug]/not-found.tsx), [ResultNotFoundView.tsx](../apps/web/app/components/ResultNotFoundView.tsx), [not-found.test.tsx](../apps/web/app/charges/[chargeSlug]/not-found.test.tsx), [ResultNotFoundView.test.tsx](../apps/web/app/components/ResultNotFoundView.test.tsx) | Added `<h1>` sourced from new `CHARGE_RESULT_COPY.notFoundHeading`; heading assertions added to both suites. |

### Copy-safety call-out

One copy constant was added: `CHARGE_RESULT_COPY.notFoundHeading = "Result not
found"` in `apps/web/app/components/charge-result-copy.ts`. This is app-level copy
(not a `@pca/shared` change); it is covered by the app/-walking copy guard and
directly scanned by `charge-result-copy.test.ts` via `scanPublicCopy`. The value
is neutral, non-comparative, and contains no prediction / odds / legal-advice /
judge-ranking vocabulary — it passes the copy-safety scanner.

---

## Human interactive walkthrough findings

Chops ran the keyboard + real-device (320px / 390px) mobile walkthrough against
the checkpoint build. **Accessibility and mobile passes were clean** — no a11y
findings beyond the agent-audit `h1` fix. The walkthrough surfaced **three
functional findings**, all fixed within this task.

### Confirmed clean (walkthrough)

- Homepage tab order; footer has no focusable elements (correct non-stop).
- Charge autocomplete full keyboard pattern incl. Escape and open-list Tab; judge
  autocomplete; both result pages' tab order and focus visibility.
- "View Philadelphia-wide result instead" keyboard activation; judge-unavailable
  pair renders the pinned fallback (possession-controlled-substance +
  judge-fakename-example).
- Definition anchor links land near the correct definition; content pages
  tab-through (definitions page correctly has no tab stops — static content);
  `2025-01-01` visible on data coverage.
- Mobile clean at 320px and 390px: result-page content order, table overflow,
  autocomplete tap targets, and unavailable states.

### Finding W1 — judge route had no mapping for `CHARGE_RESULT_UNAVAILABLE` (highest severity)

**Repro:** `/charges/harassment/judge/{any-judge-slug}`. Harassment is seeded with
no aggregates, so the judge endpoint correctly returns **HTTP 404** with code
`CHARGE_RESULT_UNAVAILABLE` and the pinned message "Results are not available for
this charge yet." (verified via curl; requestId `1ca95609`). The judge page had no
mapping for this code, fell through to the deliberate generic throw
([page.tsx](../apps/web/app/charges/[chargeSlug]/judge/[judgeSlug]/page.tsx) line
55), and rendered the generic "Something went wrong" boundary. A designed state
rendered as a generic error.

**Root cause / asymmetry:** the same "charge resolves but has no publishable
aggregate" semantic is delivered as **two different shapes per route** — a 200
tagged-union arm (`resultType: charge_only_unavailable`, carrying charge identity

- `links`) on the charge route, but a **404 error envelope** (message only, no
  identity) on the judge route. The charge route was unaffected; `/charges/harassment`
  renders its designed friendly state correctly.

**Fix:** added a `charge-unavailable` state to the judge route's pure resolver and
a designed friendly view, placed **before** the generic throw (which stays for
genuinely unexpected responses):

- [judge-result-state.ts](../apps/web/app/charges/[chargeSlug]/judge/[judgeSlug]/judge-result-state.ts)
  — new `{ kind: 'charge-unavailable' }` state; maps the `CHARGE_RESULT_UNAVAILABLE`
  api_error code to it.
- [JudgeChargeUnavailableView.tsx](../apps/web/app/components/JudgeChargeUnavailableView.tsx)
  (new) — adapts the 13.2 charge-unavailable **pattern** (h1 + message +
  methodology/definitions links). Because the 404 envelope carries no charge
  identity or `links` object, it cannot reuse `ChargeUnavailableView` directly
  (that view is bound to the 200-arm `data.charge` / `data.links` shape); it
  renders the pinned `CHARGE_RESULT_UNAVAILABLE_MESSAGE` (@pca/shared constant,
  never re-typed), a generic `chargeUnavailableHeading`, and the standing static
  `/methodology` + `/definitions` hrefs.
- [page.tsx](../apps/web/app/charges/[chargeSlug]/judge/[judgeSlug]/page.tsx) —
  renders the new view for the `charge-unavailable` state.
- Tests: new resolver case (404 `CHARGE_RESULT_UNAVAILABLE` → `charge-unavailable`)
  and a new `JudgeChargeUnavailableView` render test (h1 + pinned message + both
  link hrefs).

**Full code-to-state mapping audit (both result routes).** Verified every
`PUBLIC_ERROR_CODES` catalog entry is handled; `CHARGE_RESULT_UNAVAILABLE` on the
judge route was the only unmapped designed-state gap.

Charge route — `resolveChargeResultState`
([charge-result-state.ts](../apps/web/app/charges/[chargeSlug]/charge-result-state.ts)):

| API result                                                                                          | State                                         |
| --------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| 200 `charge_only`                                                                                   | success (result view)                         |
| 200 `charge_only_unavailable` (this is how `CHARGE_RESULT_UNAVAILABLE` arrives here)                | unavailable (in-page `ChargeUnavailableView`) |
| api_error `CHARGE_NOT_FOUND`                                                                        | not-found (`notFound()` → not-found.tsx)      |
| api_error `JUDGE_NOT_FOUND` / `JUDGE_SPECIFIC_RESULT_UNAVAILABLE` / `SENTENCING_RESULT_UNAVAILABLE` | n/a for this endpoint                         |
| api_error `INVALID_REQUEST` / `NOT_FOUND` / `RATE_LIMITED` / `INTERNAL_ERROR`, or fetch_failed      | error (throw → error.tsx)                     |

Judge route — `resolveJudgeResultState`
([judge-result-state.ts](../apps/web/app/charges/[chargeSlug]/judge/[judgeSlug]/judge-result-state.ts)):

| API result                                                                                      | State                                                                          |
| ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| 200 `judge_specific`                                                                            | success (result view)                                                          |
| 200 `judge_specific_unavailable` (this is how `JUDGE_SPECIFIC_RESULT_UNAVAILABLE` arrives here) | unavailable (in-page `JudgeUnavailableView`)                                   |
| api_error `CHARGE_NOT_FOUND`                                                                    | not-found (reason `charge`)                                                    |
| api_error `JUDGE_NOT_FOUND`                                                                     | not-found (reason `judge`)                                                     |
| **api_error `CHARGE_RESULT_UNAVAILABLE`**                                                       | **charge-unavailable (in-page `JudgeChargeUnavailableView`) — the W1 fix**     |
| `SENTENCING_RESULT_UNAVAILABLE`                                                                 | handled in-payload (`sentencing.available === false`), never a top-level error |
| api_error `INVALID_REQUEST` / `NOT_FOUND` / `RATE_LIMITED` / `INTERNAL_ERROR`, or fetch_failed  | error (throw → error.tsx)                                                      |

Nothing else falls through to a generic error for a designed state.

### Finding W2 — `API_BASE_URL` fallback inconsistency between the two fetch paths

**Repro:** with `API_BASE_URL` absent from `apps/web/.env`, browser-originated
calls through the rewrites proxy worked (autocomplete succeeded) but
server-component fetches failed (result pages rendered the generic error until the
var was added). The `next.config.ts` rewrite carried a `localhost:3001` default;
the server-side client
([public-api-client.ts](../apps/web/app/lib/public-api-client.ts)) threw on a
missing base (→ `fetch_failed` → generic error) with no default and no indication
the cause was configuration.

**Fix — chosen resolution: a single shared local-dev default (not fail-fast).**
Introduced [api-base-url.ts](../apps/web/app/lib/api-base-url.ts) as the one source
of truth (`resolveApiBaseUrl`, default `http://localhost:3001`). Both paths now use
it: `next.config.ts` (rewrite) and the server-side client (`fetchPublic` resolves
the base through it, server-side only, so the client path is unchanged and no env
read reaches the browser bundle).

**Why shared-default over fail-fast:** the rewrite already defaulted (a browser
path cannot fail-fast without breaking CI's `next build`), and `.env.example` + CI
already sanction `localhost:3001` as the local default — so making the server path
consistent with the already-working browser path is the minimal change that
removes the half-working state. Failing fast on the server while the browser
defaulted would keep the two paths inconsistent in the opposite direction and
break the existing CI-build assumption. Production hardening (requiring the var in
prod / removing the default) is already earmarked as Sprint 9 launch-readiness
scope by the standing `next.config.ts` and `.env.example` notes, so it is
deliberately **not** introduced here. Added `resolveApiBaseUrl` unit tests
(default applied, explicit value respected, env read).

### Finding W3 — setup documentation gap for `apps/web` env

The web setup path never told a developer how `API_BASE_URL` is configured. With
W2 making the var **optional** in local dev, the docs now state that (rather than
an unconditional "copy `.env.example` to `.env`"):

- [apps/web/README.md](../apps/web/README.md) — new "Local development" +
  "Environment" section: `API_BASE_URL` is optional, defaults to
  `http://localhost:3001`, copy `.env.example` to `.env` only to override.
- [apps/web/.env.example](../apps/web/.env.example) — comment updated to note the
  variable is optional and how the default is resolved.
- root [README.md](../README.md) — Setup gains an "Environment files" note
  pointing at the per-app `.env.example` files and the optional web var.

### Copy-safety call-out (walkthrough fixes)

One additional app-level copy constant was added for W1:
`CHARGE_RESULT_COPY.chargeUnavailableHeading = "Results not available"` in
`apps/web/app/components/charge-result-copy.ts`. Not a `@pca/shared` change; scanned
by `charge-result-copy.test.ts` via `scanPublicCopy`; neutral and non-comparative,
no restricted vocabulary — passes the scanner. No `@pca/shared` copy was touched by
any walkthrough fix.

### Scope note

W1–W3 are functional rather than strictly-accessibility items and reach beyond the
task's original "Files you may touch" list (config: `next.config.ts`,
`apps/web/.env.example`; docs: root + `apps/web` README). They are fixed here under
the task's two-halves structure at Chops's explicit direction as walkthrough
findings. Called out as authorized deviations.

---

## Forward notes for 15.2 (automated E2E + axe-core)

- **axe-core should confirm:** one `h1` per page/state (the not-found fix is the
  only heading change this pass); no color-contrast regressions on `text-muted`
  over `bg-surface`; combobox ARIA (`aria-expanded`/`aria-activedescendant`
  toggling) during live interaction.
- **Input focus ring:** confirm the UA default focus ring on the search/filter
  `<input>`s is visible in both themes — this pass verified only that it is never
  suppressed.
- **Loading states:** axe will see the transient `role="status"` placeholders with
  no `h1` — this is intentional (documented above), not a violation to flag.
- **Table scroll:** exercise `overflow-x-auto` on the distribution tables at 320px
  to confirm no data clipping and intact header association at runtime.
- **Judge-route charge-unavailable (W1):** add an E2E that visits a charge with no
  aggregates under a judge (e.g. `/charges/harassment/judge/{slug}`) and asserts
  the friendly `JudgeChargeUnavailableView` (h1 + pinned message + links) renders —
  not the "Something went wrong" boundary. This is a 404-envelope path, distinct
  from the charge route's 200-arm unavailable state.
- **API base URL (W2):** the unified default lives in `app/lib/api-base-url.ts`;
  E2E/build runs still rely on the `localhost:3001` local-dev default (no
  `API_BASE_URL` needed to render result pages). Production wiring remains Sprint 9.
