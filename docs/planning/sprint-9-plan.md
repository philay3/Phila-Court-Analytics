# Sprint 9 Plan: Depth, Guards, and the Index

**Adjudicated as direction 2026-07-17; task-level detail is confirmed at
Sprint 9 open.** Written deliberately before its inputs exist: several
design rulings depend on post-32.4 measurements, so this plan names
scope, sequencing, gates, and landings — not pinned task specs. Pre-fix
numbers quoted anywhere are obsolete on arrival (SD-14).

## Sprint 9 Goal

Make the promoted sentencing story as good as the reference class
(stage two), put the denominator on the page (volume index + funnel),
and clear the named parser/pipeline defect tail behind one hardening
cycle. Close with the noindex-lift decision against its criterion.

By the end of Sprint 9:

- the conviction-denominated sentencing index is live: % of convictions
  with confinement / probation / fine, median where imposed, under the
  five design rulings
- every charge page shows its funnel: charges seen, held for court,
  still pending, N with recorded outcomes — the percentage is visibly
  conditional
- the defect tail is fixed: Rule 600 truncation (+ map-key
  reconciliation), sentence-condition fragment leakage, column
  concatenation, MC missing-caption support (quarantined docs
  auto-reflow)
- the ops track has run: pending-docket refresh, build-run-id
  persistence, audit round-1 continuation
- the noindex-lift decision is made against the pinned criterion: the
  worst-case page reads honestly at a glance — funnel visible,
  undercounts flagged, trustworthy content leading

---

## Current State Assumed at Open

Sprint 8 closed: event-line dates live, maps landed, one republish
done, sentencing-first stage-one layout shipped, copy re-tuned.
Collection at or near the full 2025→present filing span. The §6.13
defect ledger's remaining items are exactly this sprint's targets.

**Numbers discipline (SD-14):** all stage-two design inputs — the
unsentenced-conviction wedge, retail-theft grade mix, per-stage
retention — are measured POST-32.4 in a fresh read-only diagnostics
session before the design gate. Nothing from pre-fix diagnostics is
citable for these rulings.

---

## Locked Sprint 9 Scope (direction level)

### In Scope

- Phase 34 — pipeline hardening batch (one corpus-rerun cycle)
- Phase 35 — sentencing stage two: design gate + build
- Phase 36 — volume index + per-charge funnel display + noindex
  decision gate
- Data-operations track (parallel): COL-4b pending-docket refresh,
  build-run-id persistence, audit round-1 continuation, collection
  cadence / republish rhythm decision, raw-PDF retention decision
- Publish cycles ride at operator cadence — the phases above name the
  natural groupings, not a mandated single cycle

### Out of Scope

- Admin review tooling (ADR 0003 stands; Chops remains the human
  reviewer) unless explicitly promoted at sprint open
- DB taxonomy tables (trigger unchanged: first taxonomy version bump
  or second taxonomy writer)
- Design restyle (any chosen visual direction returns to planning
  before any spec; restyle rides the token system)
- Prediction, forecasting, judge-ranking anything — never
- `db:reset` / volume wipes — PROHIBITED

---

## Phase 34 — Pipeline Hardening Batch

The named parser-defect tail from the audit, batched behind ONE corpus
rerun with per-change delta classes (the Sprint 4 hardening pattern).

- **Rule 600 truncation repair + map-key reconciliation:** parser
  captures the full form ("Dismissed - Rule 600 (Speedy Trial)",
  sheet-confirmed); the truncated map key is retired per the 22.4
  fresh-map principle in the same change; delta class = exactly the
  truncation-class rows (76 corpus at the audit snapshot).
- **Sentence-condition fragment guard:** conservative pattern rejection
  in the continuation heuristic, false-negative bias; optional
  18.2-style exact-match repair of the known victims (mapped
  pleas/nolle misrouted to `unknown`), corpus-evidenced table only.
- **Column-concatenation guard:** the N6-class whole-row
  `disposition_raw` shape rejected or repaired per recon; sheets are
  normal — this is boundary-loss handling.
- **MC missing-caption parser support:** the CONFIRMED layout variant
  parses; quarantined documents auto-reflow through the standing
  quarantine machinery; the auto-quarantine tripwires stay in force
  for any NEW signature.

Each change: recon → mechanism approved in planning chat → tier-1
fixtures/goldens → the batch's corpus rerun attributes every diff to
its change's class. Rebuild/republish rides the operator cadence.

## Phase 35 — Sentencing Stage Two: Conviction-Denominated Index

Opens with a **design gate in planning chat** (no code before it), fed
by the post-32.4 diagnostics session. The five rulings:

1. **Unsentenced-conviction wedge rule** — how convictions with zero
   sentencing facts count (exclude-with-disclosure vs. count-as-none);
   the fresh wedge measurement sizes the stakes.
2. **Grade blending** — pooled rates mix M and F grades on one charge
   page; ruling on grade splits vs. a grade-mix line (retail theft is
   the type specimen).
3. **PA min–max median convention** — which median (min, max, or the
   pair), the 360-day-year display convention, and `min_assumed`
   handling. This DELIBERATELY reopens the 30.2 duration-display
   retirement — a named decision, not drift.
4. **Coverage fallback** — what thin/no-sentencing charges show.
5. **Header copy** — through both gates; no likely-sentence framing.

Build after the gate: a NEW aggregate population denominated in
convictions (today's sentencing sample counts components), with
schema/generator/validation additions through existing run-lifecycle
machinery, API payload additions, and the stage-one page slots
upgraded to index rates with the fuller breakdown below.

## Phase 36 — Volume Index + Funnel Display + Noindex Gate

- **Volume index:** filed-universe machinery — per-charge counts of
  charges seen, held for court, still pending, with recorded outcomes.
  New data machinery (the fix for universe framing beyond the copy
  block), through the same run-lifecycle discipline.
- **Funnel display:** all four numbers on the result page so the
  percentage is visibly conditional; copy through both gates;
  "records" noun discipline holds.
- **Noindex-lift decision gate (planning chat):** judged against the
  pinned criterion — the worst-case page (retail theft) reads honestly
  at a glance: funnel visible, undercounts flagged, trustworthy
  content leading. Lift, partial-lift, or hold are all legitimate
  outcomes; the decision is recorded either way.

## Data-Operations Track (parallel, operator cadence)

- **Build-run-id persistence on `aggregate_runs`** — small
  migration + generator write + validation assert; FIRST in the track
  (audit drill-down provenance stands on it; today's linkage is
  inferential).
- **COL-4b pending-docket refresh** — restart from step 0 with fresh
  target derivation; post-32.2 its value is true right-censoring
  recovery (capturing endings that happened after collection).
- **Audit round-1 continuation** — remaining strata (9M-band MC
  docket, truncation-repaired, junk-judge/sentinel-collision,
  min_assumed, SD-15 straddlers), the freshness pass, and the
  derivation drill-down (which uses the persisted build-run id).
- **Collection cadence + republish rhythm** — a scheduling decision,
  not a build.
- **Raw-PDF retention decision** — the last ADR 0002-era open item;
  a decision record, kept offline with the compliance materials.

---

## Sprint 9 Definition of Done (direction level)

1. Hardening batch live with every diff attributed; quarantine reflow
   proven; no unadjudicated STOPs.
2. Stage-two index live under the five recorded rulings; stage-one
   slots upgraded; both copy gates passed.
3. Funnel numbers on the page; volume index reconciles against the
   corpus.
4. Noindex decision made and recorded against the criterion.
5. Ops track items run or explicitly re-queued with named landings —
   no "for now" deferrals.
6. Counts restated at every publish; CI green; repo-tree privacy
   intact; sprint closed in planning chat.

---

## Sprint 9 Risks (with mitigations)

1. **Stage-two rulings made on stale intuitions** → hard gate: the
   post-32.4 diagnostics session runs first; pre-fix numbers are
   inadmissible.
2. **New aggregate population destabilizes the publish path** →
   existing run-lifecycle machinery only; validation extended, not
   bypassed; published-run rollback model unchanged.
3. **Hardening batch delta soup** → per-change delta classes, one
   rerun, the Sprint 4 pattern; anything unattributable is
   stop-and-report.
4. **Funnel/volume numbers contradict served percentages** → they are
   built to be conditional context for the same run; validation
   asserts internal consistency before publish.
5. **Noindex pressure outruns the criterion** → the criterion is
   pinned in writing; the gate is a planning-chat decision with the
   worst-case page on screen.