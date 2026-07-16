# Sprint 6 Plan: Real Aggregate Generation

## Sprint 6 Goal

Turn the charge-level facts produced in Sprint 5 into real public aggregate
data, and swap the seeded aggregate run for the real one so the existing
public app serves real Philadelphia criminal-court distributions.

By the end of Sprint 6:

- one command reads eligible `fact.*` rows and writes `analytics.*` aggregate
  rows under a single aggregate run
- charge-only outcome and sentencing distributions exist for every charge with
  eligible facts
- judge-specific outcome and sentencing distributions exist only where the
  data is solid, each with a matching Philadelphia-wide baseline
- every distribution carries its own sample size, date range, and thin-data
  flag; sentencing sample size is computed separately from outcome sample size
- the real run is validated and published, invalidating the seeded run in the
  same transaction — the public API and UI switch to real data with no API or
  UI code change
- the run is re-runnable at any time: it aggregates whatever eligible facts
  exist at the moment it runs, so ongoing collection just makes the next run
  richer

Sprint 6 does **not** build admin review, change the public API contract, or
touch the public UI. The generator is the whole sprint.

**Admin review is deferred to post-deadline future work** (documented in
Sprint 6, not built). Ambiguous or ineligible records are excluded from
aggregates automatically — the eligibility decision already lives on the facts
from Sprint 5; the aggregator does not re-judge it.

---

## Locked Sprint 6 Scope

### In Scope

- `pipeline generate-aggregates` command (console-script entrypoint)
- Aggregate run lifecycle: open run → write rows → validate → publish
  (publish invalidates the prior published run in one transaction)
- Charge-only outcome aggregates
- Charge-only sentencing aggregates (separate sentencing sample size)
- Judge-specific outcome aggregates (only where judge attribution is solid)
- Judge-specific sentencing aggregates (only where solid)
- Philadelphia-wide baseline wiring for every judge-specific aggregate
- Per-distribution sample size, date range, thin-data flag
- 2025-01-01 MVP window enforcement at aggregation
- Aggregate validation (counts sum to sample size, percentages align, date
  range valid, metadata present)
- Privacy validation (forbidden-field scan of generated rows)
- Data-coverage and methodology metadata refresh
- Publish swap verification: the existing public API serves the real run

### Out of Scope

- admin review UI, admin auth, correction workflow, audit dashboard (deferred
  to post-deadline future work)
- JSON output mode — the app is already `analytics.*`-backed; DB rows only
- **numeric confidence thresholds of any kind** — rejected since Sprint 4;
  eligibility gates on the categorical `match_method` + boolean trio already
  written onto the facts (see Standing Decision 1)
- public API contract changes or new endpoints (the run-swap needs none)
- public UI changes (Sprint 7 hardening)
- automated UJS ingestion, OCR, external services
- the Sprint 7 seed sweep (fake judges + seeded aggregates are invalidated by
  the publish swap this sprint, deleted by the sweep later)
- production deployment / launch-readiness gates (Sprint 8)

---

## Sprint 6 Standing Decisions

These extend the Sprint 1–5 decisions and are locked:

1. **The aggregator reads eligibility; it never re-computes it.** Sprint 5
   already wrote `public_eligible` / `judge_specific_eligible` (and their
   reason codes) onto every fact. The generator selects `WHERE public_eligible`
   (and `WHERE judge_specific_eligible` for judge rows) and groups — it does
   not re-apply date rules, match-method checks, or review flags. This keeps a
   single source of eligibility truth and satisfies bglad's "exclude ambiguous
   records" rule structurally, without any confidence threshold.
2. **DB rows, one published run.** Output is `analytics.*` rows, not JSON. The
   published-run model from §6.3 governs: active published ⟺ `published_at IS
   NOT NULL AND invalidated_at IS NULL`; at most one; publishing the real run
   invalidates the seeded run in the same transaction. The seeded run stays in
   the table as an invalidated rollback target — not deleted this sprint.
3. **Generation and publication are separate steps.** The command writes rows
   under a run with status `generated`, runs validation, and only publishes on
   an explicit publish step/flag once validation passes. A broken aggregate set
   never reaches the public API. Mirrors the architecture rule that a code
   change should not auto-publish data.
4. **Delete-and-reinsert per run.** Re-running generation replaces the prior
   *generated-but-unpublished* run's rows transactionally (Sprint 2
   aggregate-seed pattern, reused). Published runs are immutable; a new run is
   a new row that invalidates the old on publish.
5. **Sentencing sample size is independent.** Outcome sample size = eligible
   outcome facts in the charge's denominator; sentencing sample size = eligible
   *sentence* facts in the charge's denominator. Never copied from the outcome
   count. A charge can have outcome aggregates and no sentencing aggregates —
   that is the normal sentencing-unavailable case.
6. **Unavailable states are absence, not rows.** The public API already returns
   the judge-specific-unavailable and sentencing-unavailable arms (Sprint 2
   tasks 8.1/8.2) when no matching aggregate row exists. The generator writes
   no "unavailable" rows and builds no unavailable machinery — it simply omits
   empty groups, and the existing API logic does the rest.
7. **Baseline is the same-run charge-only aggregate.** Every judge-specific
   aggregate must have a corresponding charge-only aggregate for the same
   charge in the same run (structurally guaranteed, since a
   judge-specific-eligible fact is also public-eligible). Validation asserts
   this; it is not separately generated data.
8. **Thin-data is a flag, not a filter.** `THIN_DATA_MIN_SAMPLE_SIZE` (default
   10, config) sets the flag; thin results are shown with a warning, never
   hidden. Reason code `below_minimum_sample` when flagged.
9. **Full 2025-forward window.** No upper date cap for launch. The
   `DATA_START_DATE = 2025-01-01` floor is the only date filter; the facts
   already carry it via `mvp_eligible`, so the aggregator inherits it through
   the eligibility select. (A date-capped slice, if ever wanted, is a config
   add — not a design change.)
10. **Phase numbering continues from Sprint 5: Phases 26–28.**

---

## Recon required before implementation (Claude has no repo access)

The agent's implementation plan must confirm these from the actual code before
writing the generator — the plan does not assume them:

- exact `fact.charge_outcomes` / `fact.charge_sentences` column names for the
  eligibility flags, the category codes, the date fields, the normalized-charge
  and normalized-judge FKs, and `taxonomy_version`
- exact `analytics.*` aggregate table columns (built in Sprint 2 task 6.2;
  read `db/src/types.ts`) and the `aggregate_runs` lifecycle columns
- how the public API currently selects the active run (expected: the §6.3
  published-run predicate) and the Sprint 2 seed runner's publish/invalidate
  code path, to reuse rather than reinvent
- the taxonomy source for category display names / public-visibility / sort
  order (`@pca/taxonomy` artifacts, per §6.3)

Any mismatch between recon and this plan is stop-and-report, adjudicated in the
planning chat.

---

## MVP Data Range (restated)

MVP coverage starts **2025-01-01**, inherited through fact eligibility:

- outcome aggregates: eligible outcome facts with `disposition_date` ≥
  2025-01-01
- sentencing aggregates: eligible sentence facts with `sentence_date` ≥
  2025-01-01 (per SD-15, `sentence_date` is independently captured and can
  predate the disposition date; eligibility keys off the actual sentence date)
- no aggregate group's date-range start may be earlier than 2025-01-01

---

# Phase 26 — Charge-Only Aggregates

## Task 26.1 — Generator Command + Run Lifecycle + Charge-Only Outcomes

Acceptance criteria:

1. `pipeline generate-aggregates` exists as a subcommand of the `pipeline`
   console script (no `python -m` path); reads `DATABASE_URL` at the CLI
   boundary only; refuses to run in CI.
2. Config surface: `DATA_START_DATE` (default 2025-01-01),
   `THIN_DATA_MIN_SAMPLE_SIZE` (default 10), aggregate-run label. No confidence
   thresholds anywhere.
3. Run lifecycle: opens an `aggregate_runs` row with status `generated`,
   parser/taxonomy versions, data start/end, timestamps; all aggregate rows
   carry that run id; delete-and-reinsert semantics for a re-run of an
   unpublished generated run (SD 4).
4. Charge-only outcome aggregates: for each normalized charge, group eligible
   (`public_eligible`) outcome facts by outcome category. Each row carries
   charge id, category code, count, percentage (category_count ÷ total eligible
   outcome facts for that charge), outcome sample size, date-range start/end
   (from eligible disposition dates, never before 2025-01-01), thin-data flag +
   reason, run id, taxonomy version.
5. Groups with zero eligible facts produce no rows (SD 6).
6. Console/log hygiene: counts and statuses only — no docket numbers, no raw
   text, no defendant data.
7. Run report: facts loaded, facts included, facts excluded (with the fact
   layer's own reason-code tallies), outcome aggregates generated.
8. Tier-1 tests over synthetic facts: multi-category charge, single-category
   charge, thin-data charge, 2025-boundary exclusion, empty group. All repo
   gates green.

## Task 26.2 — Charge-Only Sentencing Aggregates

Acceptance criteria:

1. For each normalized charge, group eligible sentence facts by sentencing
   category into `analytics.charge_sentencing_aggregates`.
2. Sentencing sample size computed independently (SD 5); date range from
   eligible sentence dates; percentages against the sentencing denominator.
3. A charge with eligible outcomes but no eligible sentence facts produces
   outcome rows and no sentencing rows — no error, no placeholder.
4. Run report extends with sentencing aggregates generated and the count of
   charges with outcomes-but-no-sentencing.
5. Tier-1 tests: charge with both, charge with outcomes only, thin sentencing,
   multi-component sentence facts counted correctly. Gates green.

---

# Phase 27 — Judge-Specific Aggregates + Baselines

## Task 27.1 — Judge-Specific Outcome Aggregates + Baseline

Acceptance criteria:

1. For each charge+judge pair, group `judge_specific_eligible` outcome facts by
   category into `analytics.judge_outcome_aggregates`; same metadata shape as
   26.1 plus judge id.
2. A pair with no eligible judge-specific facts produces no rows (the API
   returns the unavailable arm — SD 6).
3. Baseline guarantee (SD 7): every judge-specific outcome aggregate has a
   charge-only outcome aggregate for the same charge in the same run.
4. Run report extends with judge-specific outcome aggregates generated and
   distinct charge+judge pairs covered.
5. Tier-1 tests: solid pair, thin pair, pair with no eligible judge facts,
   baseline-present assertion. Gates green.

## Task 27.2 — Judge-Specific Sentencing Aggregates + Baseline

Acceptance criteria:

1. For each charge+judge pair, group eligible judge-specific sentence facts
   into `analytics.judge_sentencing_aggregates`; independent sentencing sample
   size; same baseline guarantee against the charge-only sentencing aggregate.
2. Where judge-specific sentencing has no eligible facts but judge-specific
   outcomes exist, sentencing is simply absent — the API's sentencing-
   unavailable arm covers it.
3. Run report extends with judge-specific sentencing aggregates generated.
4. Tier-1 tests mirror 27.1 for sentencing. Gates green.

---

# Phase 28 — Validation, Publish, Close

## Task 28.1 — Aggregate + Privacy Validation

Acceptance criteria:

1. Validation pass over a generated (unpublished) run verifies, per aggregate:
   category counts sum to the stored sample size; percentages align with counts
   within rounding tolerance; sample size present; date range present and start
   ≥ 2025-01-01; taxonomy version and run id present.
2. Baseline validation: every judge-specific outcome/sentencing aggregate has
   its same-run charge-only baseline; a missing baseline blocks that
   judge-specific result (fails validation).
3. Privacy validation: every generated row passes the `@pca/shared`
   forbidden-field scanner — no defendant name, docket number, source id,
   storage key, raw/extracted text, parsed/fact id, review status, or parser
   internal appears in any aggregate field.
4. Validation failure sets run status `failed` and blocks publish; a clean pass
   sets `validated`.
5. Tests cover a good run, a deliberately count-mismatched run, and a
   privacy-violating row. Gates green.

## Task 28.2 — Publish Swap + Coverage/Methodology + Exit Demo

Acceptance criteria:

1. Publish step sets `published_at` on the validated run and invalidates the
   prior published (seeded) run in the same transaction (§6.3). Idempotent /
   safe to re-run.
2. Post-publish verification (agent-run, raw output verbatim): the public
   charge search, charge-only result, judge-specific result, and data-coverage
   endpoints now return real-run data; the seeded run is invalidated, not
   deleted.
3. Data-coverage metadata reflects the real run: jurisdiction, criminal-court
   MVP scope, data start 2025-01-01, data end, last generated, charges-with-
   aggregates count, judges-with-aggregates count, eligible outcome/sentence
   fact counts, excluded count, known limitations.
4. Methodology copy updated for the cutdown MVP: 2025+ window, disposition-date
   outcomes, sentence-date sentencing, ambiguous records excluded, no admin
   review in this version, thin data may shift as records are added, historical
   distributions — not legal advice, not predictions. Copy passes the scanner +
   human framing review.
5. Admin review documented as post-deadline future work.
6. Exit demo (planning chat): generator run + include/exclude summary; a
   charge-only outcome + sentencing result on the real run; a thin-data flag; a
   judge-specific result beside its baseline; a judge-unavailable pair; a
   sentencing-unavailable charge; data-coverage showing 2025-01-01; validation
   + privacy pass; full CI green.

Sprint 6 closes here; Sprint 7 (Public Demo Hardening) planning begins.

---

## Sprint 6 Definition of Done

1. `pipeline generate-aggregates` generates charge-only outcome and sentencing
   aggregates from eligible facts.
2. Judge-specific outcome and sentencing aggregates generate only where facts
   are solid, each with a same-run Philadelphia baseline.
3. Sample sizes (outcome and sentencing, independent), date ranges, and
   thin-data flags are computed per distribution.
4. 2025-01-01 window is enforced via fact eligibility; no aggregate starts
   earlier.
5. Ambiguous/ineligible facts are excluded structurally — no confidence
   threshold exists anywhere.
6. Aggregate and privacy validation pass; a failing run cannot publish.
7. The real run is published and invalidates the seeded run in one transaction;
   the existing public API and UI serve real data with no code change.
8. The generator is idempotent and re-runnable against whatever facts exist at
   run time.
9. Data-coverage and methodology reflect the real run and the cutdown MVP;
   admin review is documented as future work.
10. Tier-1 tests cover the generator and validation in CI; CI never touches
    `~/court-data/`.
11. No public/aggregate output exposes raw docket text, defendant data, source
    documents, parser internals, fact ids, or review data.
12. Exit demo reviewed; sprint closed in the planning chat.

---

## Sprint 6 Risks (with mitigations)

1. **Eligible facts are thin** → acceptable for the demo; thin-data flags and
   honest coverage copy carry it; ongoing collection + re-run fattens the next
   published run without code change.
2. **Judge-specific data is sparse** → judge results appear only where solid;
   the unavailable arm covers every other pair; charge-only stays first-class.
3. **Sentencing sparser than outcomes** → independent sentencing sample size +
   the sentencing-unavailable arm; sentencing is never forced.
4. **Aggregate counts wrong** → validation asserts counts↔sample-size↔
   percentages before publish; a failing run cannot go public.
5. **Internal data leaks into aggregates** → forbidden-field scan of generated
   rows is a publish-blocking validation step.
6. **Publish swap surprises the live app** → generation and publish are
   separate; publish is transactional invalidate-old/activate-new; the seeded
   run remains as an invalidated rollback target.

---

## Handoff to Sprint 7

Sprint 7 (Public Demo Hardening) begins when the exit demo passes and the
public app is serving a real, validated, published aggregate run: charge
search, charge-only results, judge-specific-where-available results, all
unavailable states, and coverage/methodology all reading real data. Sprint 7
focuses on making that experience feel complete and stable — page states,
mobile, thin-data warnings, copy clarity — no new data machinery.