# Board — Philadelphia Court Outcomes

**Compiled 2026-07-25.** Every figure below was read on 2026-07-25 from a named
file on disk or from command output run on 2026-07-25. Each figure carries its
source inline. Nothing here is restated from conversation, memory, or planning
chat — anything not verifiable on disk today is written as
`unknown — confirm with operator`.

## Provenance note — the live-query request could not be honored

The task asked for read-only queries against local canonical `pca`. **They did
not run.** This session reaches the machine through a file bridge only; the
local Postgres is not reachable from it:

```
FAIL localhost:5433        -> ConnectionRefusedError
FAIL 127.0.0.1:5433        -> ConnectionRefusedError
FAIL host.docker.internal  -> name resolution failure
FAIL 192.168.65.2:5433     -> Network is unreachable
```
_(python socket probe, run 2026-07-25; `psql`, `pg_isready` and `docker` are all
absent from the bridge environment — `which` returned nothing for each.)_

Every DB-derived count below is therefore **report-sourced**, taken from the two
newest read-only reports on disk, both of which print their SQL adjacent to
their output and both of which ran under `default_transaction_read_only=on`:

- `~/court-data/reports/recon-36.0-20260724T235427Z.md` — session dated
  **2026-07-24**, file mtime 2026-07-24 23:59.
- `~/court-data/reports/operator-numbers-report-20260722T233446Z.md` — session
  dated **2026-07-22**.

These are snapshots at their own dates, not live values for 2026-07-25. The
recon report's own corpus census opened and closed identically
(37,369 dockets / 136,389 charges at both ends) and states that nothing has been
loaded since the Stage D publish — so corpus-grain figures are expected to still
hold, but that expectation is not a query. **Re-run the counts before treating
any number here as acceptance-grade.**

---

## 1. Live state

_As of 2026-07-25._

**Deployment**

| Fact | Value | Source |
|---|---|---|
| Live URL | https://philacourtoutcomes.org | `README.md:8` |
| Launch posture | controlled launch; site-wide `noindex`, no promotion | `README.md` "Data coverage & honesty"; `recon-36.0` R8 (`apps/web/app/layout.tsx:35-37` robots block) |
| Hosting | Render (private API service + web service), Cloudflare proxy, UptimeRobot monitors | `README.md` tech stack; worklog "Sprint 7 close-out (a)" |
| Edge rate rule | 50 requests / 10 s per IP, action Block | worklog "Sprint 7 close-out (a)" |
| In-app rate limit | 120 / 60 000 ms defaults | worklog Task 31.3 |

**Repository**

| Fact | Value | Source |
|---|---|---|
| HEAD | `ebc1ae9a3196dee5805b3b6fc73bc49e19d692f5` | `git log -1`, run 2026-07-25 |
| HEAD date / subject | 2026-07-23 19:45:28 −0400 — "Merge pull request #75 from philay3/readme-1-product-readme" | same |
| Branch | `main` | `git rev-parse --abbrev-ref HEAD`, run 2026-07-25 |
| Working tree | clean (`git status --short` produced no output) | run 2026-07-25 |
| Last 5 merges | #75 README-1, #74 video-v3 B2, #73 prerecord-2, #72 data-cycle close, #71 republish runbook FK amendment | `git log --oneline -40`, run 2026-07-25 |
| Stale local branches | `col-4` (2026-07-13), `phase-26` (2026-07-13), `phase-29` (2026-07-14), `phase-31` (2026-07-15), `video-v3-capture-relayout` (2026-07-22) | `git branch`, run 2026-07-25 |
| Migrations on disk | 10 | `ls db/migrations/`, run 2026-07-25 |

**Published data**

| Fact | Value | Source |
|---|---|---|
| Published aggregate run | `9b870800-7ee1-42af-920d-b6ce63b56ab4` | `recon-36.0` R4; `operator-numbers-report` header |
| Its fact build run | `ddb0fbd9-364d-444f-a342-ac6e6978c309` (the single completed fact build) | `recon-36.0` R4 |
| Build completed | 2026-07-22 22:47:34 UTC | `operator-numbers-report` §10 |
| Aggregate data_range | 2025-01-01 .. 2026-07-21 | worklog "Phase-2 Data Cycle 1", Stage D |
| Prior run | `82b6cc99` invalidated (superseded) at that publish | worklog Stage D |
| Prod sync | per-table counts identical local vs prod across all 14 tables at last republish | worklog Stage D STOP 2 |

**Corpus** _(all from `operator-numbers-report`, snapshot 2026-07-22; corpus
census re-confirmed identical in `recon-36.0`, snapshot 2026-07-24)_

| Metric | Count |
|---|---|
| Dockets | 37,369 (CP 12,617 / MC 24,752) |
| Charges | 136,389 |
| Version pair | single pair (record 2, envelope 8) across all 37,369 |
| Duplicate docket numbers | 0 |
| Quarantined source documents | 0 |
| Source documents | `imported` 37,369 + `parse_superseded` 1,121 |
| Dockets flagged `review_needed` | 12,803 |

**Charge partition (the reconciliation identity, `identity_holds = t`)**

| Bucket | Count |
|---|---|
| Outcome-fact-producing | 42,983 |
| Undisposed (null disposition) | 51,608 |
| Held for court (six bind-over forms) | 41,798 |
| **Total** | **136,389** |

**Fact and served volumes**

| Metric | Count | Source |
|---|---|---|
| Outcome facts | 42,983 | worklog Stage D D5; `operator-numbers-report` §2 |
| Public-eligible outcome facts | 32,942 | worklog D5; `recon-36.0` R2 |
| Sentence facts | 17,765 | worklog D5; `operator-numbers-report` §10 |
| Public-eligible sentence facts | 10,649 | worklog D5; `operator-numbers-report` §10 |
| Roster slugs with matched charges | 78 | `recon-36.0` R3 |
| …of those with zero public-eligible outcomes (dead-end arm today) | 1 | `recon-36.0` R3 |

Citywide public-eligible outcome mix (worklog Stage D D5): dismissed 13,932
(42.3%), withdrawn 7,952 (24.1%), guilty_plea 7,779 (23.6%), guilty_verdict
1,605 (4.9%), acquittal 894 (2.7%), ard 754 (2.3%), other 26 (0.1%).

**Current task file on disk** — `tasks/current-task.md` holds **Task 36.0 —
Phase 36 Recon (Read-Only)**. Its deliverable exists:
`~/court-data/reports/recon-36.0-20260724T235427Z.md`, written 2026-07-24 23:59.
That task is done; the amended **36.0-A** spec is staged at
`~/court-data/recon-36.0-A/36.0-A-amended-spec.md` and has not yet been pasted
into the task file as of 2026-07-25.

**Process rulings** — `docs/process-rulings.md` (added 2026-07-25, **untracked
pending your commit**) is the durable landing for planning-chat process rulings.
It records PR-1 (worklog waived for read-only recons — an intended `CLAUDE.md`
step-6 deviation), PR-2 (rulings are recorded on disk), PR-3 (F3 census at both
ends), PR-4 (charge-text hygiene with the class-(iii) carve-out), and PR-5 (DB
sessions run in Claude Code). It exists because the 36.0 Q1 ruling was real but
unverifiable from disk. Note for the staging gate: this file changes the
expected-untracked posture until it is committed.

---

## 2. Canonical product state

_As of 2026-07-25. Sources: `README.md`, `CLAUDE.md`, `recon-36.0`, worklog._

**What the product is.** Search a Philadelphia criminal charge and see how past
cases with that charge resolved — outcomes and sentences, citywide or by judge
where available. Built first for people facing charges, second for attorneys and
researchers. Every figure is a historical aggregate with its sample size shown;
small samples are labeled thin rather than hidden. Explicitly not a prediction,
not legal advice, not a judge comparison or scoring product. (`README.md`)

**Pipeline.** UJS docket PDFs → pdfplumber text extraction → deterministic
parsing under a closed warning vocabulary → roster normalization (charges,
outcomes, judges) → eligibility-gated fact build with machine-readable reason
codes → immutable versioned aggregate runs in PostgreSQL → aggregate-only API →
Next.js frontend that computes nothing. At most one aggregate run is published
and active at a time; figures change only by publishing a new run. (`README.md`,
"How it works")

**Stack.** Two records, and they are not identical — the locked list is narrower
than what actually ships.

*Locked by `CLAUDE.md` §"Stack (locked — do not substitute)":* pnpm workspaces
monorepo (no Turborepo yet); Fastify + TypeScript strict + TypeBox; PostgreSQL
with Kysely + Kysely Migrator (no version pinned); Next.js App Router + React +
TypeScript (**Tailwind is not named**); Python 3.12 + pytest with extractor
*candidates* PyMuPDF / pdfplumber / pypdf (pdfplumber is not locked there, and
psycopg3 and uv are not named); Node 22 LTS; GitHub Actions.

*As described in `README.md` §"Tech stack":* the same plus Tailwind CSS v4,
PostgreSQL 17, pdfplumber + psycopg3 + uv as the chosen pipeline tools, Vitest,
Playwright + axe-core, ruff, and the Render / Cloudflare / UptimeRobot infra
line.

**Served surfaces.** Homepage search, `/charges` directory, charge result page,
judge-specific result page, `/definitions`, `/methodology`, `/data-coverage`,
`/about`.

**Public API.** Six route modules under `apps/api/src/routes/public/` —
`charges.ts`, `judges.ts`, `results.ts`, `definitions.ts`, `methodology.ts`,
`data-coverage.ts` (`ls`, run 2026-07-25). The worklog records seven registered
public routes through Task 10.1 and the eighth, `GET /api/v1/public/charges`,
landing at DP-4.1 — eight total. The endpoint count was not re-verified against
the route registry in this pass. Charge result is a
discriminated union: `charge_only` success arm and `charge_only_unavailable`
arm; the unavailable arm carries `additionalProperties: false` and no run
metadata by design. (`recon-36.0` R6)

**Canonical result-page order** (prerecord-2, 2026-07-22 worklog entry): outcome
mix first → sentencing detail → sentencing index rates (or its zero-sentenced
fallback line) — at every render site and arm. Outcome rows carry visual-only
group headings ("Dismissed or withdrawn", "Guilty plea or verdict"); the
frontend derives no figures.

**Version and vocabulary state**

| Axis | Value | Source |
|---|---|---|
| Envelope parser version | 8 | `operator-numbers-report` §1 version-pair census |
| Record parser version | 2 | same |
| Warning vocabulary | 14 codes, `LOW_TEXT_EXTRACTION` … `ORPHANED_SENTENCE_SUPPRESSED` | `services/pipeline/src/pipeline/warning_codes.py`, read 2026-07-25 |
| Taxonomy version | 1.0.0 | `operator-numbers-report` §10 build-run row |
| Charge roster active entries | 78 | `recon-36.0` R1 census header |
| Thin-data threshold | pipeline default 10 (the taxonomy artifact's provisional 30 was deleted at 35.3) | worklog Task 35.3 |
| Filed-date floor / MVP window start | 2025-01-01 (deliberately unconsolidated constants) | `recon-36.0` R1/R2 |

**Aggregate layer.** `analytics.aggregate_runs.status` takes exactly three
values under its CHECK — `in_progress`, `completed`, `failed`. Validation over a
generated run flips it to `completed` on a clean pass and to `failed` on any
violation, which structurally blocks publish via
`aggregate_runs_published_at_check`. `published_at` and `invalidated_at` are
timestamp columns, not statuses: the live published run `9b870800` carries
`status = completed`. A partial unique index permits at most one active
published run. (`recon-36.0` R5; `operator-numbers-report` §7)

**Nine aggregate tables** are FK'd to `aggregate_runs` — four Sprint-6 tables
plus five from Task 35.1 — for ten `analytics.*` tables in total counting
`aggregate_runs` itself. Corroborated three ways: the operator-numbers report's
table enumeration (4 `ref` + 10 `analytics`, the latter including
`aggregate_runs`); the worklog's 35.1 entry ("five conviction-grain
sentencing-index tables", "validation extended over all nine tables"); and the
Stage D publish record ("all nine populations violations=0"). **Flag for the
operator:** `recon-36.0` R5 states "ten aggregate tables … four Sprint-6 tables
+ six Task-35.1 index tables" but then names only five 35.1 tables — an internal
inconsistency in that report, not a disagreement between sources.

**Standing rules that constrain any change** (`CLAUDE.md`, read 2026-07-25):
plan-then-implement with explicit approval; strict scope discipline; six
mandatory gates (ruff check, ruff format --check, pytest with
`PIPELINE_TEST_DATABASE_URL` pinned, `pnpm format:check`, staging completeness,
clean-environment gate timing — the functional four run last, post-staging);
branch + PR + merge-on-green, never a direct commit to main; nothing derived
from real dockets enters the repo tree; acceptance-relevant run output pasted
verbatim, never retyped.

---

## 3. Roadmap — unordered draft

**Operator will reorder.** These are items named in on-disk records with no
sequencing implied by their position here. Each carries its source; several are
named-with-trigger rather than scheduled.

- **Phase 36 — volume index + funnel display + noindex gate.** Recon complete
  (`recon-36.0`, 2026-07-24), design gate pending in planning chat. Proposed
  shape: new `analytics.charge_volume_aggregates` table, one row per (run,
  charge), with a closure CHECK on the wedge-identity precedent; funnel counts
  computed in one generator pass; closure asserted at validation over persisted
  rows only.
- **R7a — charge not-found serves 200.** Diagnosed: the route-level
  `loading.tsx` Suspense boundary flushes a 200 shell before `notFound()` can
  land. Defect is mode-independent (dev and production build both 200); the
  banked "under `next start`" qualifier understated it. Proposed mechanism:
  delete `apps/web/app/charges/[chargeSlug]/loading.tsx`.
- **R7b — judge-route soft-404.** Deliberate in-page not-found render so two
  distinct pinned messages can show; the code comment defers the real-404
  question to this gate. Proposed mechanism: call `notFound()` + add
  `judge/[judgeSlug]/not-found.tsx`, trading the message distinction for the
  correct status. Blocked on R7a's boundary removal.
- **Noindex lift / partial-lift / hold verdict** — a planning-chat gate with the
  worst-case page on screen. `recon-36.0` R8 assembles the inputs; no verdict on
  disk.
- **Next data cycle** — opens with the out-of-cycle refresh arrivals ruled
  NEXT-cycle material at the last cycle close.
- **Committed full-corpus reload runbook** — two executions now live only in
  worklog and dispatch text.
- **Collector run-report emission on interrupted sessions** — second confirmed
  instance (refresh session 2 wrote no run artifacts).
- **Stale never-published aggregate run `24184d68` housekeeping.**
- **Legacy capstone golden set (1,500)** — named Sprint-9 item.
- **"Proceed to Court" disposition mapping** — deferred from 32.3; stays
  unmapped under the designed fail-safe (non-public `unknown` + review item).
- **Contaminated-string census** — banked at 32.3: leading-char-loss 11 rows,
  offense-text ~28, scheduling bleed 4, status-suffix 1.
- **Intake-dir residue policy** — queued to the Sprint 9 ops track.
- **Site-wide label reconciliation** (result pages, methodology definition,
  sentencing-unit noun) — named Sprint 9 copy item.
- **README copy-gate coverage** — root README is world-visible and covered by no
  mechanical copy gate; extending the scanner is a queued Sprint 9 ops
  candidate. Until it lands, any README edit needs a manual `scanPublicCopy`
  pass.
- **Raw-PDF retention decision** (post-launch queue item 10).
- **Collection cadence / republish rhythm decision** (post-launch queue item 1).
- **Admin review tooling** — ADR 0003 revisit (post-launch queue item 3).
- **Taxonomy-tables landing trigger** (post-launch queue item 4).
- **Option B publish-to-target machinery** (source/target split, post-launch
  queue item 7).
- **UptimeRobot ToS primary-source read** (post-launch queue item 9).
- **S6 collector-arrival golden-coverage policy** — Phase-2-cycle decision,
  explicitly not invented at 34.5.
- **Named affordances with triggers, not scheduled:** golden-set re-scope
  (trigger: a second wrong-corpus run); `apps/api` dev/start unguarded remote-DB
  exposure (trigger: any incident, or remote URLs becoming routine in local
  `.env`); dismissal-disclosure retirement (trigger: dismissal coverage
  settling).
- **Stale local branch cleanup** — five merged-era local branches still present
  (see Live state).
- **Demo video final capture** — gated on G1–G3 (relayout deploy live, new
  publish serving, staleness re-walk); had not run as of the last worklog entry
  touching it.

Anything not listed above and not evidenced on disk: *unknown — confirm with
operator.*

---

## 4. Fix ledger, with counts

Counts are report-sourced at the dates shown, not live. Where a class was
resolved, the resolution is stated.

### 4.1 Open defects in served behavior

| ID | Defect | Count / scope | Status | Source |
|---|---|---|---|---|
| R7a | Charge not-found serves HTTP 200 instead of 404 | all unknown charge slugs; reproduced dev **and** production build | diagnosed, mechanism proposed, not built | `recon-36.0` R7a (2026-07-24) |
| R7b | Judge-route soft-404 (unknown judge, and unknown charge on the judge route) | both routes, dev and prod | diagnosed, by design, mechanism proposed, not built | `recon-36.0` R7b |
| — | Charge with nonzero volume but zero recorded outcomes returns the dead-end unavailable arm | **1** of 78 matched roster slugs today; every newly rostered charge starts there | confirmed, in Phase 36 scope | `recon-36.0` R6 |

### 4.2 Exclusion tail — why 103,447 charges are not in the served percentages

Full-population funnel, computed 2026-07-24 by the real matcher over all 136,389
parsed charges (`recon-36.0` R2). **Closes exactly, zero residual.**

| Bucket | Count | Share of corpus † |
|---|---|---|
| (a) Recorded outcomes (public-eligible) | 32,942 | 24.2% |
| (b) Held for court | 41,798 | 30.6% |
| (c) Pending / undisposed | 51,608 | 37.8% |
| (d) Disposed but not fact-eligible | 10,041 | 7.4% |
| **Total** | **136,389** | 100% |

† Share column is arithmetic performed here on the four disk-sourced counts, not
a figure read from any report. The section heading's 103,447 is likewise derived
(136,389 − 32,942).

Bucket (d) by reason code — non-exclusive tally (a charge can carry several):

| Reason code | Count |
|---|---|
| `charge_not_normalized` | **6,191** |
| `filed_date_before_floor` | 3,086 |
| `disposition_date_before_mvp_window` | 2,745 |
| `review_needed` | 1,018 |
| `disposition_not_mapped` | **68** |
| `blocking_warning` | 33 |
| `disposition_date_missing` | **0** (mechanism extinct post-envelope-6 rebuild) |

Exclusive reason-combination tally (sums to 10,041): `charge_not_normalized`
alone 5,854; `disposition_date_before_mvp_window + filed_date_before_floor`
2,607; `review_needed` alone 882; `filed_date_before_floor` alone 321; thirteen
further combinations at 123 and below (123, 120, 39, 31, 27, 19, 11, 2, and five
at 1).

**Charge-normalization tail.** Over the full parsed population the matcher
returns: alias 64,482 / exact 40,700 / unmatched **19,079** / statute 10,043 /
ambiguous **2,085**. Clean-match rate 84.48% full-population, 83.97% over the
non-fact subset. The 19,079 unmatched (14.0% of all parsed charges) are
structurally invisible to any charge-keyed index regardless of the population
ruling. Ambiguous is concentrated in the undisposed subset — 2,052 of 2,085.
(`recon-36.0` R1)

**Population boundary candidates** (`recon-36.0` R3, all at charge grain): all
parsed charges 136,389 · post-filed-date-floor 132,944, with 3,445 charges on
pre-floor dockets dropping and **0 charges** on dockets with NULL filed_date
(fail-closed under the floor; the partition closes: 132,944 + 3,445 + 0 =
136,389) · disposed inside the MVP event window 40,238. The recon makes no
statement about how many *dockets* carry a NULL filed_date. Boundary ruling is
planning-chat's; not on disk.

### 4.3 Review queue

Snapshot 2026-07-22 (`operator-numbers-report` §9). **Not re-queried 2026-07-25.**

| Metric | Count |
|---|---|
| Review items total | 61,751 |
| **Open** | **59,733** |
| Superseded | 2,018 |
| Generated by the ddb0fbd9 build | 50,193 |
| Newly inserted by that build | 23,307 |

Newly-inserted by type: `missing_disposition_date` 19,880 · `unmapped_charge`
2,846 · `unmapped_judge` 272 · `duration_unparseable` 141 ·
**`unmapped_disposition` 51** · `additive_sentencing_category` 50 ·
`sentinel_collision` 38 · `ambiguous_sentencing_component` 10 ·
`money_unparseable` 8 · `unresolvable_cross_court_reference` 6 ·
`ambiguous_charge` 5.

The queue is persistent and status-preserving — `build_facts` inserts via
`ON CONFLICT (dedup_key) DO NOTHING` and **nothing auto-closes**. The 32 open
`unmapped_disposition` items from the 34.x guard classes stopped regenerating at
the last rebuild; their closure to `superseded` is a conscious key-scoped
operation, and the 29.3 closure tool's pinned scope covers held-form populations
only — an adjudicated extension or an analogous pass is still needed. (worklog
34.5 intake-cycle verification ledger)

### 4.4 Parser warning census

Snapshot 2026-07-22 (`operator-numbers-report` §10), corpus-wide over
`parsed.warnings`:

| Code | Count |
|---|---|
| `MISSING_DISPOSITION_DATE` | 41,798 |
| `NON_TERMINAL_CASE` | 13,295 |
| `UNKNOWN_NOT_FINAL_DISPOSITION` | 2,477 |
| `UNPARSEABLE_DURATION` | 1,109 |
| `SENTINEL_COLLISION` | 169 |
| `SUSPECT_DISPOSITION_TOKEN` | 57 |
| `BLANK_DOB_CAPTION` | 15 |
| `ORPHANED_SENTENCE_SUPPRESSED` | 15 |
| `SUSPECT_JUDGE_LINE` | 10 |
| `SUSPECTED_AMENDED_CHARGE` | 5 |

### 4.5 Closed / resolved, kept for the record

| Class | Was | Now | Source |
|---|---|---|---|
| Parse quarantine | 9 documents | **0** — the 34.5-banked deferred reflow landed doc-for-doc at Stage A | worklog Phase-2 Cycle 1, Stage A |
| Sentences on held charges (post-suppression invariant) | 18 rows on 15 charges | **0** | worklog Stage D STOP 1; `operator-numbers-report` §10 |
| Republish runbook FK refusal | 14-table TRUNCATE refused by 4 FK edges from 2 tables | amended TRUNCATE set + nonzero=STOP empty-precondition (PR #71) | worklog Stage D STOP 2 |
| Refresh-target ordering | docket-number ordered | `filed_date ASC NULLS LAST` + docket tiebreak (PR #69) | worklog ordering-fix rider |
| Duplicate docket numbers | — | 0 | `operator-numbers-report` §1 |

### 4.6 Structural risks named but not defects

- **Fact-build → volume-generate drift.** Buckets (b)(c)(d) exist only in
  `parsed.*`, which has no run identity; a volume generator's non-fact counts
  are a snapshot at generate time. No skew on current state (the identities
  reconcile exactly), but nothing structural prevents it. Proposed guard: a
  validation assert plus the same-session build+generate convention.
  (`recon-36.0` R4)
- **Window-constant coupling.** `public_eligible` embeds disposition_date ≥
  2025-01-01 and the aggregates' event window is `DATA_START_DATE` = 2025-01-01
  — currently the same date by parallel, deliberately unconsolidated constants.
  Any funnel-vs-facts assert must compare like-for-like or it breaks the day one
  constant moves. (`recon-36.0` R5)
- **Rate-limit bucket is per-instance in-memory** (ADR 0004 hazard 5) — revisit
  before any scale-out. (worklog Task 31.3)
- **`apps/api` dev/start auto-load the root `.env` and connect unguarded** —
  accepted named exposure, read-path; the local-DB guard covers migrate and seed
  only. (worklog Task 34.6 R-1)

---

## 5. In flight

_As of 2026-07-25._

**Operator pending-docket refresh pass (COL-4b) — running now.**
`~/court-data/refresh-intake-2026-07-22/` holds **7,083 files** and was last
modified **2026-07-25 00:23** (`find` + `ls -lt`, run 2026-07-25) — the
directory is actively growing. For scale: the worklog records this directory at
"953+ and growing" at the last cycle close (2026-07-23), and `recon-36.0`
(2026-07-24) states the pass "is at the fetch/extract stage; nothing has been
loaded since the Stage D publish." `tasks/current-task.md` describes it as
"operator-run, roughly half complete."

Derivation scale from the last cycle: `refresh_targets_total = 13,331` (CP 5,033
/ MC 8,298), filed 2023-01-03..2026-06-30, ordering monotone oldest-first;
cycle 1 hauled 1,121 of those 13,331 (worklog Stage B / Stage C1). Whether the
current pass is against the same target set or a fresh derivation:
*unknown — confirm with operator.*

**Nothing loaded since the publish.** The corpus census in `recon-36.0` opened
and closed identically on 2026-07-24 (37,369 / 136,389), and
`raw.source_documents` shows only `imported` + `parse_superseded` — no
`quarantined` rows. So the refresh haul on disk has **not** entered the database
yet; the served run `9b870800` is unaffected by it.

**Phase 36 design gate — pending in planning chat.** The recon that feeds it is
complete and on disk (2026-07-24); no verdict, no boundary ruling, and no
adjudication of the R6 payload shape (extend the unavailable arm vs. a third
union arm) exists on disk. Its first build task is pre-named: the R7a/R7b 404
fixes, mechanism to be adjudicated at the same gate.

**No successor task spec.** `tasks/current-task.md` still holds the completed
Task 36.0 recon. The file is untracked and gitignored by design (Task 34.6 R-2),
so its contents are the only signal of what is queued next — and today it
signals nothing new.

**Repo state is quiet.** Clean tree, on `main`, HEAD is the README-1 merge from
2026-07-23. No open work is staged or in progress in the working tree.

**Not verifiable from here:** whether the last merge has deployed; current
production health; whether the demo video capture G1–G3 gates have passed; any
planning-chat decision made after 2026-07-24. *unknown — confirm with operator.*
