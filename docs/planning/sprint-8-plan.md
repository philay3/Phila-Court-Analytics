# Sprint 8 Plan: The Data Becomes True

**Adjudicated in planning chat 2026-07-17.** Authored mid-phase-32 with
32.1 complete and 32.2 in flight; statuses are marked inline. This plan
supersedes any draft Sprint 8 material written without visibility into
the launch, the date audit, or the 32.1 recon.

## Sprint 8 Goal

Fix the parser date-source defect and let the site's numbers become
true. The audit (§6.13 of the project instructions) proved every
disposition date exists on the sheets on the Final Disposition event
line while the parser reads only the judge line — dateless dismissals,
withdrawals, acquittals, and transfers are a parser artifact, and dated
rows carry the sentencing date instead of the disposition date. Sprint 8
corrects the date source, drops the seq-99,999 placeholder pollution,
lands the already-ruled map additions, republishes once, re-tunes the
copy that described the old skew, and then reorders charge pages to lead
with sentencing (stage one of the endorsed promotion program).

By the end of Sprint 8:

- disposition dates come from the Final Disposition event line;
  sentence dates keep the judge-line (Sentence Date column) source,
  byte-identical to today
- the dateless-disposed class (8,591 floored at the audit snapshot)
  carries true dates; the wrong-date class on dated rows is corrected
  and measured
- seq-99,999 placeholder rows no longer pollute the last real charge's
  offense field; the suppressed normalization matches recover
- the ruled map additions land (dismissal-family kin, nolo/mistrial, IC
  variants per the 2026-07-16 directional rulings), recovering volume
  now that their rows carry dates
- one rebuild → validate → publish cycle puts the corrected data live;
  counts are formally restated; the dismissal disclosure and any
  affected copy are re-tuned in the same window; the demo staleness
  walkthrough is re-run
- charge pages lead with the sentencing block under explicitly
  conditional headers, outcome mix demoted below (stage one — existing
  served data only)

**Operator constraint (set by Chops, governs the whole sprint):**
nothing that risks the live site or runs long. One rebuild/republish
cycle. Anything not required for the above defers to Sprint 9.

Sprint 8 does **not** build the conviction-denominated sentencing index
(stage two), the volume index / funnel display, any Sprint 9 parser
guard, admin review, or indexing enablement.

---

## Current State (what this sprint builds on)

Live at philacourtoutcomes.org serving floored aggregate run
`a0738c1f…`; corpus 17,610 dockets at the last intake; filed-date floor
in force (PR #57); launch copy pass live (PR #58). Collection continues
(Chops-run) toward the full 2025→present filing span; intake landed
before 32.4 may ride the sprint's publish cycle at operator discretion —
the aggregator is re-runnable.

Ground-truth audit round 1, session 1 delivered the verdict and the
defect ledger (project instructions §6.13). The 32.1 fix recon confirmed
the mechanism at code level, cleared extraction (8/8 markers intact),
ruled C4 as bundled damage, and selected sentencing-invariance Option B.
Code freeze lifted at sprint open.

**Numbers discipline (SD-14, applies sprint-wide):** no figure is pinned
in code, tests, or copy. Every count is a snapshot; counts quoted in
this plan describe the state at planning time and are never acceptance
values. The §6.13 defect ledger is the expected-delta reference for
32.2/32.4, restated at publish.

---

## Locked Sprint 8 Scope

### In Scope

- Parser date-source fix + 99,999 CHARGES-section guard (32.2, in
  flight): full delta discipline, corpus rerun as acceptance authority
- Map additions per the 2026-07-16 directional rulings (32.3), table
  approved in planning chat before code
- One rebuild → validate → publish cycle with copy re-tune and demo
  staleness re-walk (32.4)
- Sentencing promotion stage one: page reorder with conditional
  headers, existing served data only (Phase 33)
- Worklog entries: audit verdict (summary-level) + per-task entries

### Out of Scope

- Sentencing stage two (conviction-denominated index) — Sprint 9
- Volume index / per-charge funnel display — Sprint 9
- Rule 600 truncation repair, fragment-leakage guard,
  column-concatenation guard, MC missing-caption parser support — all
  Sprint 9 (ruled at 32.1; zero touch-set overlap)
- Pending-docket refresh (COL-4b) — Sprint 9 ops track
- Build-run-id persistence, audit round-1 continuation — Sprint 9
- Any schema change; any extraction change; any new warning code
  (plan-level approval required if one surfaces)
- Design restyle (any Claude Design direction returns to planning
  before any spec); noindex lift; admin review; taxonomy tables;
  product analytics
- `db:reset` / volume wipes — PROHIBITED (real corpus on the volume)

---

## Sprint 8 Standing Decisions

1. **Date semantics (SD-15 amendment, lands with 32.2):**
   `disposition_date` = the governing Final Disposition block's
   event-line date; `sentence_date` = the judge-line date (the sheet's
   Sentence Date column), independently retained. **Governing-block
   principle:** a charge re-disposed by a later Final block takes that
   block's string AND date together — including ARD-progression rows
   (STOP ruling 2026-07-17); rows whose governing block is the ARD
   block keep judge-line dating unchanged.
2. **Sentencing invariance is Option B and hard-zero:** every sentence
   row byte-identical through the fix; any nonzero is a STOP.
3. **Delta discipline:** the corpus rerun attributes every diff to
   D-A (dateless→dated), D-B (judge-line→event-line shifts, ARD
   subclass enumerated separately), D-C (sentencing, hard zero), D-D
   (offense cleanup, exactly the leak rows), D-E (nothing else — incl.
   invariants: dated held rows 0, date-without-string rows 0,
   quarantine membership unchanged, baseline-missing exactly 7).
   Two-instrument authority: `run-fixtures` tier-2 drift is the delta
   authority; `equivalence-check` carries the invariants (19.2 tooling
   governs; extraction byte-equivalent per the 17.1 seam proof).
4. **Versions:** `ENVELOPE_PARSER_VERSION` 6; `ACCEPTED_ENVELOPE_VERSIONS`
   = {6}; record `parser_version` stays 2. The loader's newer-version
   arm performs the transactional replace at 32.4.
5. **Map discipline (32.3):** the concrete form→category table is
   approved in planning chat before any code; byte-exact keys only; no
   new truncated keys (the existing Rule 600 truncated key stays until
   the Sprint 9 repair + 22.4 reconciliation); additive aliases only;
   demo `ref.normalized_charges` rows never modified; no taxonomy
   version bump expected (no new categories — a new-category need is a
   STOP).
6. **One publish cycle (32.4):** existing runbook'd machinery only,
   agent-run per the Phase 31 division-of-labor amendment; counts
   formally restated (worklog + planning chat); copy changes ride the
   same window through both gates; demo staleness re-walk is mandatory
   because the mixes transform.
7. **Stage one is display-only (Phase 33):** existing served data,
   no new aggregates, no funnel counts, all strings in `@pca/shared`
   through scanner + human framing review.

---

## Phase 32 — Parser Date Fix + Data Cycle

### Task 32.1 — Fix Recon **[COMPLETE 2026-07-17]**

Delivered R1–R7; all eight ACs met. Adjudications banked: mechanism
approved; held vocabulary imported from `outcome_mapper` (cycle-check
passed); ARD carve-out approved (later restated by the STOP ruling's
governing-block principle); C4 ruled DAMAGE → guard bundled; Option B;
riders declined (all Sprint 9); versions 6/{6}.

### Task 32.2 — Parser Date-Source Fix + 99,999 Guard **[IN FLIGHT]**

Governing documents: the issued task spec, the plan approval (Q1–Q5
rulings + required fixes 1–2), and the ARD-progression STOP ruling.
Status at plan time: mechanism, versions, SD-15 reframe, tests (961
passed), and tier-1 fixtures/goldens staged on `phase-32`; corpus rerun
+ equivalence check running; delta classifier ready.

Acceptance criteria (plan-level restatement):

1. Mechanism per standing decisions 1–4 above; eight tier-1 fixture
   behaviors with flag-gated goldens; unit tests per changed branch.
2. Corpus rerun completes with every diff attributed to D-A…D-E; D-C
   zero; D-A exceptions enumerated individually; D-B's ARD subclass
   enumerated separately.
3. Delta report adjudicated in planning chat BEFORE the commit; single
   task commit on `phase-32` carrying the audit-verdict + 32.2 worklog
   entries; tier-2 goldens refreshed post-adjudication; all five gates
   verbatim; no PR until phase close.

### Task 32.3 — Map Additions (table-approval gate)

Scope: the unmapped forms ruled in on 2026-07-16 — dismissal-family kin
(Dismissed - LOP, Rule 1013, Abatement, Rule 546, De Minimis),
nolo contendere and mistrial placements, IC-suffix variants, and the
contaminated-string handling — per the directional rulings, finalized at
table approval.

Acceptance criteria:

1. The agent's proposal presents the complete form→category table with
   per-form row counts (fresh snapshots) and cites each directional
   ruling; approved in planning chat before any code.
2. Byte-exact map keys only; no truncated or pattern keys; additive
   changes only; expected-delta lines per form stated at approval (they
   verify at the 32.4 rebuild, where `unknown`-category counts drop by
   the mapped totals).
3. Tier-1/unit coverage for the new mappings; no taxonomy version bump
   (new-category need = STOP); all gates verbatim; single task commit
   on `phase-32`.

### Task 32.4 — Rebuild → Validate → Publish + Copy + Demo Re-Walk

One cycle, agent-run under the committed runbooks.

Acceptance criteria:

1. Load (envelope-6 transactional replace) → build-facts → generate →
   validate → publish through existing commands; publish swap atomic;
   run lines verbatim; post-publish verification per runbook.
2. Fact-level reconciliation attributes the rebuild's changes to the
   expected classes: D-A/D-B/D-D materialization, map deltas per the
   32.3 approval, the C4 re-match recovery (55–163 band at the R4
   snapshot), and the SD-15 lag report in its reframed expected state.
   Anything unattributable is stop-and-report.
3. Counts formally restated (worklog + planning chat) per SD-14.
4. Copy revision rides the same window through both gates: the
   dismissal disclosure re-tuned (the missing-date mechanism is dead;
   right-censoring remains and stays disclosed), plus any
   coverage/known-limitations/methodology line the new date semantics
   touches. No predictive language; corpus-contingent-claims principle
   holds.
5. Demo staleness re-walk executed against the new run (mandatory —
   outcome mixes transform); anchors re-verified or substituted per
   the script's protocol.
6. Phase-32 PR opened at phase close (rebase-and-merge or merge
   commit, never squash); merge verification run.

## Phase 33 — Sentencing Promotion, Stage One

Reorder charge-only and judge-specific result pages to lead with the
sentencing block already served, under an explicitly conditional header
(final wording through the gates; working shape: "when cases like this
ended in conviction"); outcome mix demoted below it. Existing served
data ONLY.

Acceptance criteria:

1. Recon confirms the shared page componentry and the exact strings
   affected; all new/changed strings live in `@pca/shared` and pass the
   scanner; human framing review passes (no likely-sentence framing —
   the conditional header is the honesty device AND the reassurance).
2. Charge pages and judge-specific pages lead with sentencing where
   sentencing data exists; the sentencing-unavailable arm renders
   outcome-first with its existing callout — no layout dead-ends on
   any tagged-union arm.
3. No new aggregates, no funnel counts, no API change; frontend
   calculates nothing (bars render API percentages only; table
   contract unchanged).
4. Heading hierarchy and a11y verified for the new order; E2E copy and
   privacy assertions updated and green; all gates verbatim.
5. Judged against the post-32.4 pages in a planning-chat review with
   Chops; single task commit; phase-33 PR at close.

---

## Sprint 8 Definition of Done

1. Disposition dates sourced from Final Disposition event lines are
   live; sentence dates byte-identical to pre-fix; every rerun and
   rebuild diff attributed; no unadjudicated STOPs.
2. The 99,999 guard is live; suppressed normalization matches
   recovered and measured.
3. The ruled map additions are live; `unknown` shrinks by the approved
   per-form expectations.
4. One publish cycle completed with counts restated; copy re-tuned
   through both gates; demo staleness re-walk passed.
5. Charge pages lead with sentencing under conditional headers; both
   copy gates passed; a11y/E2E green.
6. Worklog carries the audit verdict and every task; PRs merged per
   the phase model; CI green throughout; no real-docket content in the
   repo tree.
7. Sprint closed in the planning chat.

---

## Sprint 8 Risks (with mitigations)

1. **Parser change blast radius** → full delta discipline; two-
   instrument rerun; hard-zero sentencing invariant; STOP on anything
   unattributable (already exercised once — the ARD-progression STOP).
2. **The republish transforms public numbers dramatically** → that is
   the point, and it is managed: copy re-tune rides the same window,
   counts are restated, the demo re-walk is mandatory, and the prior
   run remains the rollback target under the published-run model.
3. **Map additions interact with new dates** → single rebuild carries
   both; expected deltas per form stated at table approval; rebuild
   reconciliation attributes them separately from D-classes.
4. **Scope creep against the operator constraint** → everything not in
   scope is named in Sprint 9's plan with a landing; riders were ruled
   out at 32.1 on touch-set evidence.
5. **Ongoing collection shifts counts mid-sprint** → SD-14; intake
   rides 32.4 at operator discretion; staleness protocol covers the
   demo.

---

## Handoff to Sprint 9

Sprint 9 opens on the post-32.4 data: stage-two design inputs (wedge,
grade mix, retention) are measured fresh, the hardening batch has its
own corpus-rerun cycle, and the volume index + funnel display carry the
noindex-lift decision. The Sprint 9 plan document holds the queue.