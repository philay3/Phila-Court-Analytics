# Demo Script — Philadelphia Court Outcomes

This is the start-to-finish demo path for the product. It is executed
verbatim at the production smoke walkthrough (Task 31.3) and the exit
demo (Task 31.4). Every step names its real slug and app path from the
currently published aggregate run and describes the expected on-screen
outcome in copy-safe terms. URLs are app paths only; prepend the
serving host.

Quoted strings in this script are the exact literals the app serves.
If a quoted string does not match what you see on screen, stop and
investigate — either the deployment is stale or the copy changed after
this script was written.

## Staleness guardrails — read first

This script is a snapshot taken against a published run. It pins **no
numbers**: collection is ongoing, and a republish during the demo
window is possible. A republish may shift sample sizes, percentages,
thin-data flags, category tails, and which charge–judge pairs have
judge-specific aggregates. The anchors below were verified against the
run published at the time of writing; they are expected to keep
working, but each one's role must be re-verified after any republish.

**Re-verify walkthrough** (run once before any demo, and again after
any republish — no tooling required, just a browser):

1. Open `/data-coverage`. Note the values beside "Aggregate run" and
   "Last refreshed". If they differ from your previous demo run, the
   run has been republished — continue with the remaining steps rather
   than assuming the anchors still hold.
2. Load each anchor URL listed in the steps below and confirm the
   expected arm still renders, using the role criteria under each
   step: the badge/callout states for the thin anchors, the
   sentencing-unavailable callout on its anchor, the
   judge-unavailable fallback on its pair, and both distributions with
   no thin-data badge on the high-sample anchor.
3. If an anchor no longer fits its role, re-pick a replacement that
   meets the same criteria (each step states its criteria) via the
   home-page search, and note the substitution wherever the demo is
   being tracked.

## The demo path

### 1. Search for a high-sample charge

- Open `/`. The page heading is "Philadelphia Court Outcomes"; under
  "Search court outcomes" there is a "Charge" combobox (placeholder
  "Search by charge") and a "Judge (optional)" combobox (placeholder
  "Add a judge").
- Type `PWID` in the charge box and select **Manufacture, Delivery, or
  Possession With Intent (PWID)** from the listbox. Leave the judge
  box empty. Submit.
- You land on `/charges/pwid-controlled-substance`.

Anchor role: a charge with large samples in both distributions.
Criteria if re-picking: both the outcome and sentencing distributions
render and neither carries the thin-data badge.

### 2. The charge-only result — the core of the product

On `/charges/pwid-controlled-substance`, direct attention to, in
order:

- **The two distributions.** "Historical outcome distribution" and
  "Historical sentencing distribution", each rendered as a bar
  visualization backed by an authoritative table with "Count" and
  "Percentage" columns and a per-row "Definition" link into
  `/definitions`.
- **Sample sizes.** Each distribution carries its own "Sample size:"
  line. Point out the construction: the outcome sample counts charges;
  the sentencing sample counts sentence components under eligible
  parent charges. Because the two are constructed differently, they
  can differ in either direction for the same scope — a mismatch
  between them is expected, not an error.
- **The date range.** The range starts at January 1, 2025 (the planned
  data start) and ends at the published run's data-window end.
- **The responsible-use notice**, four statements served verbatim:
  "These figures are historical aggregates." / "They are not legal
  advice." / "They are not a prediction of any current or future
  case." / "Individual cases vary, and past patterns do not determine
  any specific outcome."
- **The coverage note**, beginning "These figures summarize criminal
  cases from Philadelphia's Municipal Court and Court of Common Pleas
  with disposition or sentencing events on or after January 1, 2025."
  — it states that only charges with a recorded final outcome are
  included and that collection is ongoing.

Structural point worth making here: the outcome distribution contains
only terminal outcomes. Interim procedural results — for example a
preliminary-hearing "held for court" — are non-terminal forms and
produce no outcome facts by construction, so they never appear in any
distribution.

Optional second charge-only anchor, if the audience wants to see a
wider outcome tail: `/charges/simple-assault` serves more outcome
categories on this run (including ARD), which makes the per-row
"Definition" links and the category vocabulary easier to show.

### 3. A thin-data example

- Navigate to `/charges/voluntary-manslaughter` (or search
  `manslaughter` from `/` and select **Voluntary Manslaughter**).
- Expected: both distributions render, and both carry the thin-data
  badge "Based on a small sample." plus the callout: "These figures
  come from a small number of records. With so little data behind
  them, the percentages can shift noticeably as more records are
  added, so read them as a rough summary rather than a settled
  pattern."
- The point to land: the product labels thin data instead of hiding it
  or drawing conclusions from it.

Criteria if re-picking: a charge whose outcome AND sentencing
distributions both carry the thin-data badge.

### 4. Add a judge filter

- Return to `/charges/pwid-controlled-substance`. Below the result,
  show the judge-filter entry: heading "View this charge for a
  specific judge", combobox labeled "Judge (optional)", help text
  "Add a judge to view historical outcomes for this charge and that
  judge. Judge-specific data is not available for every charge and
  judge."
- Type `Gibbs` and select **Monica Gibbs**.

### 5. Judge-specific result beside baseline — solid pair

- You land on `/charges/pwid-controlled-substance/judge/gibbs-monica`.
- Expected: two sections — "Judge-specific result" and
  "Philadelphia-wide baseline" — each with its own outcome and
  sentencing distributions and its own "Sample size:" lines. On this
  pair, the judge-specific distributions render without the thin-data
  badge.
- The point to land: the judge-specific figures never replace the
  baseline; they render beside it, and every figure carries its own
  sample size.

Criteria if re-picking: a pair whose judge-specific distributions
render without the thin-data badge.

### 6. Judge-specific result — thin pair

- Navigate to
  `/charges/aggravated-assault-deadly-weapon/judge/gibbs-monica`
  (searchable from `/` as `aggravated assault` + `Gibbs`).
- Expected: the same two-section layout, but the judge-specific
  distributions carry the thin-data badge "Based on a small sample."
  and the thin-data callout, while the Philadelphia-wide baseline
  below renders without them.
- The point to land: thinness is flagged per figure — a thin
  judge-specific result sits beside a non-thin baseline on the same
  page.

Criteria if re-picking: a pair whose judge-specific distributions
carry the thin-data badge while the same charge's baseline does not.

### 7. Judge-unavailable pair — the honest fallback

- Navigate to
  `/charges/pwid-controlled-substance/judge/brumbach-marissa-j`
  (searchable as `PWID` + `Brumbach`).
- Expected: no judge-specific distributions. Instead the pinned
  message: "No judge-specific aggregate is available for this charge
  and judge yet. Philadelphia-wide historical data for this charge is
  still available." with the link "View Philadelphia-wide result
  instead".
- The point to land: when a pair has no aggregate, the product says so
  and routes to what does exist — it never fabricates or extrapolates.

Criteria if re-picking: any charge–judge pair that serves the
unavailable message above (pick a judge from the roster autocomplete
that has no aggregate for the chosen charge).

### 8. Sentencing-unavailable charge

- Navigate to `/charges/criminal-conspiracy-903c` (searchable as
  `conspiracy`; the display name renders the statute reference
  "§ 903(c)").
- Expected: the outcome distribution renders in full; in place of the
  sentencing distribution stands the callout "Historical sentencing
  data is not available for this charge yet." with the "Read the
  methodology" link. The page never fails wholesale.

Criteria if re-picking: a charge whose outcome distribution renders
while the sentencing arm serves the callout above.

### 9. Remove the filter

- Return to `/charges/pwid-controlled-substance/judge/gibbs-monica`
  and click "View Philadelphia-wide result instead".
- Expected: you land back on `/charges/pwid-controlled-substance`,
  the charge-only view from step 2.

### 10. Methodology

- Navigate to `/methodology`.
- Walk the section list as served: "Where the data comes from", "What
  time period is covered", "What the results mean", "Not a
  prediction", "Not legal advice", "Sample size", "Thin data",
  "Charge-level figures", "Sentencing figures", "Known limitations".
- The point to land: every construction shown during the demo (sample
  sizes, thin-data labeling, charge-level scope, sentencing
  eligibility) is documented on a public page.

### 11. Data coverage — where the run metadata reads live

- Navigate to `/data-coverage`.
- Expected under "Current coverage": "Covered data window" (its start
  renders as January 1, 2025), "Last refreshed", "Aggregate run" (the
  published run's identifier — this is the live source of truth for
  which run is being served), "Taxonomy version", and the three count
  fields. The "Planned data start" field also renders January 1, 2025.
- Expected below: the "Known limitations" list, served by the API.
- The point to land: run metadata is public and live — this page is
  what the staleness guardrails at the top of this script key off.

### 12. Mobile view

- Set the viewport to 390×844 (the standard mobile pass; 320 px is the
  narrow spot-check width).
- Open `/` and, in the charge box, search `aggravated assault`; select
  **Aggravated Assault — Fear of Imminent Serious Bodily Injury to
  Designated Individuals** (the longest display name on the roster) —
  the open listbox and the committed value must be fully visible with
  no horizontal overflow.
- Land on `/charges/aggravated-assault-fear-sbi-designated`: the long
  charge name wraps cleanly, distributions stack, tables remain
  readable, and nothing scrolls horizontally. This anchor is also thin
  on this run, so the badge and callout from step 3 appear here too.

Criteria if re-picking: the charge with the longest display name in
the autocomplete.

## Known limitations to disclose in a live demo

- **Judge thinness.** Judge-specific samples subset the
  Philadelphia-wide samples for the same charge, so they are smaller
  by construction and more often carry the thin-data badge. Expect
  thin badges and unavailable pairs to be common on judge-filtered
  views.
- **MC/CP coverage shape.** Coverage spans Philadelphia's Municipal
  Court and Court of Common Pleas. A case can begin in Municipal Court
  and continue in the Court of Common Pleas; only charges with a
  recorded final outcome contribute facts, and non-terminal forms
  (such as held-for-court) produce no outcome facts by construction.
  The court-level composition behind any given charge therefore varies
  and is not shown per court.
- **Sentencing-unavailable classes.** Some charges serve an outcome
  distribution but no sentencing distribution (step 8's callout arm).
  This is a structural property of sentencing eligibility, not a data
  error, and the set of affected charges can change on republish.
- **Ongoing collection.** The figures reflect records collected so
  far, not every Philadelphia criminal case, and they change as newly
  collected records are aggregated. Never quote a number from a
  previous demo run as current.
