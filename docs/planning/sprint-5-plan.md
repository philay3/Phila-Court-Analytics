# Sprint 5 Plan: Normalization and Attribution

## Sprint 5 Goal

Turn the canonical Sprint 4 parser output (1,603 envelopes) into structured,
reviewable, charge-level facts in PostgreSQL — the internal fact layer that
Sprint 6 reviews and Sprint 7 aggregates and publishes.

By the end of Sprint 5:

- `raw.*`, `parsed.*`, `fact.*`, and `review.*` tables exist and are loaded
- the full canonical envelope set is loaded into the parsed layer
- real charge and judge reference rosters exist alongside the Sprint 2 seeds
- parsed charges normalize to `ref.normalized_charges` (exact / alias /
  statute matching)
- parsed judge captures normalize to `ref.normalized_judges` — the durable
  fix for "is this value actually a judge," resolving the 5 recovered
  SENTINEL_COLLISION dockets and the junk-judge class
- raw dispositions map to outcome taxonomy categories; sentence components
  map to sentencing taxonomy categories
- monetary amounts and any residual durations are extracted at the
  normalization stage (parser untouched)
- charge-level outcome and sentence fact candidates exist with explicit
  eligibility status and reason codes
- judge attribution is conservative and separately gated from charge-only
  eligibility
- structured CP↔MC held-case linkage exists
- ambiguous or unmapped records generate deduplicated review items in
  `review.queue_items` — the input Sprint 6's admin UI consumes
- COL-collected dockets enter the corpus deliberately via a defined intake
  protocol, deepening MC evidence
- a normalization/attribution report states whether Sprint 6 and Sprint 7
  can proceed

Sprint 5 does **not** produce public aggregates, change any public API or
UI, or build admin review screens.

---

## Locked Sprint 5 Scope

### In Scope

- `raw.source_documents`, `parsed.*`, `fact.*`, `review.queue_items` table
  migrations (Kysely; schemas exist since Sprint 1, all six data schemas
  beyond ref/analytics are currently empty)
- Python DB access layer (psycopg, pinned via uv) + `pipeline load`
  subcommand: envelopes → parsed layer, idempotent, keyed on source hash
- Full canonical corpus load (1,603 envelopes) as the loader's acceptance
  run
- Real charge roster and real judge roster (curation protocol below) +
  seeded/real coexistence rules
- Charge normalization: exact, alias, statute matching; ambiguity handling
- Judge normalization: exact, alias/variant matching with honorific/initial
  handling; role context preserved (assigned vs disposition judge);
  resolution path for the recovered-7 flagged dockets
- Outcome mapping: `disposition_raw` → outcome taxonomy (the disposition
  map is built fresh; the Capstone truncated-form workaround entry is
  excluded from birth — the Sprint 5 opening cleanup, evidence banked by
  the 18.2 corpus rerun)
- Sentencing mapping: `sentence_type` → sentencing taxonomy, plus
  pattern-based detection of restitution / community service inside
  component text (the 20.2 restitution flag lands here)
- Normalization-stage monetary extraction from sentence `raw_text`/`program`
  (amount in cents where parseable; parser output untouched)
- Judge attribution to outcome and sentence facts (conservative,
  role-based)
- Charge-level outcome and sentence fact candidate generation into `fact.*`
- Eligibility rules: MVP date window (≥ 2025-01-01), category
  public-eligibility, review_needed, blocking warnings; judge-specific
  eligibility separated from charge-only eligibility
- Structured CP↔MC held-case linkage from `cross_court_dockets` +
  `related_cases`
- Review item generation with dedup into `review.queue_items`
- `record.court_type` populate-vs-drop decision (opens by verifying actual
  corpus-wide behavior — see Standing Decision 13)
- COL intake protocol: collected PDFs → 16.3 import → extract → parse →
  `--init-goldens` → load; deliberate corpus growth beyond the 1,603
  invariant; MC evidence deepening
- Full-corpus normalization/attribution run as the sprint's acceptance
  authority
- Normalization and attribution report + methodology implications

### Out of Scope

- public aggregate generation (Sprint 7)
- public API or UI changes of any kind
- admin review UI, admin auth, correction workflow (Sprint 6)
- DB taxonomy tables (`ref.outcome_categories` etc. — Sprint 7; taxonomy
  stays package-sourced, `taxonomy_version` stored as a string)
- **numeric confidence scores of any kind** — rejected in Sprint 4 and the
  rejection stands (see Standing Decision 2)
- parser behavior changes (one narrow exception: if the court_type decision
  in 24.3 lands on "populate," that is a scoped, golden-delta'd change with
  its own corpus rerun; nothing else touches the parser)
- OCR, ML/LLM extraction, external document services
- docket-number pseudonymization of tier-2 goldens (Sprint 8)
- raw-PDF retention decision (Sprint 9)
- branch protection revisit (second contributor or Sprint 8)
- production deployment

---

## Sprint 5 Standing Decisions

These extend the Sprint 1–4 decisions and are locked:

1. **The parse already attributes.** Recon confirmed dispositions
   (`disposition_raw` / `disposition_date` / `disposition_judge_raw`) live
   ON the charge object and sentence components are a nested list ON the
   charge. There is no detached disposition or sentence collection.
   Consequently bglad's sequence-linking and docket-level-fallback
   attribution machinery (draft S5-007.2–007.4, S5-008.1–008.3) is not
   built. Charge-level attribution method is `charge_row` for outcomes and
   `charge_component` for sentences — recorded on every fact for
   methodology transparency, but there is exactly one attribution path
   each. The genuine attribution work this sprint is judge attribution and
   CP↔MC linkage.
2. **No numeric confidence, anywhere (reaffirmed).** All draft "confidence
   score" fields are replaced by: a categorical `match_method` vocabulary
   (`exact` / `alias` / `statute` / `pattern` / `unmatched` / `ambiguous`),
   structured warning codes, and derived `review_needed`. Eligibility gates
   on explicit boolean conditions and blocking-warning sets — never on
   thresholds. If a future sprint needs graded confidence, it derives from
   warning composition there.
3. **Facts live in the database, not fixture files.** The pipeline loads
   parsed envelopes into `parsed.*`, then normalization/attribution reads
   `parsed.*` + `ref.*` and writes `fact.*` + `review.queue_items`. Draft
   S5-011's repo-tree artifact directories
   (`services/pipeline/tests/fixtures/actual_*`) are rejected — real-corpus
   output in the repo tree is a privacy violation. Tier-1 synthetic
   fixtures drive committed golden tests for the normalization/attribution
   stages, same two-tier discipline as Sprint 4; real-corpus run reports
   land under `~/court-data/reports/`.
4. **Schema ownership stays split.** Kysely migrations (TypeScript) own all
   DDL, including tables only Python writes. Python gets a read/write data
   path via psycopg (pinned in uv), connection string from `DATABASE_URL`
   sourced at the CLI boundary (never auto-loaded — `set -a; source .env;
   set +a` convention holds). No Python-side migration tool.
5. **Loader idempotency and versioning.** `pipeline load` upserts keyed on
   envelope `source_sha256`; re-loading the same envelope set is a no-op;
   loading a newer `parser_version` for an existing source replaces that
   docket's parsed rows in one transaction. Loader console output follows
   corpus-tool hygiene: counts, statuses, hash-prefix ids only. Docket
   numbers are internal-sensitive data — permitted in the private DB
   (`parsed.*` is internal by architecture), never in console/logs/repo.
6. **Fact builds are delete-and-reinsert per run.** A
   `fact.fact_build_runs` row records parser_version, taxonomy_version,
   roster state, started/completed timestamps, and counts; facts and
   review items generated by a run carry its id; re-running replaces the
   prior run's facts transactionally (the Sprint 2 aggregate-seed pattern,
   promoted). Review items survive across runs via the dedup key, not via
   run scoping (Sprint 6 must not lose triage state to a rebuild).
7. **Rosters: public sources committed, corpus checks local.** Committed
   reference seeds for real charges source from public statute references
   (Titles 18/35/75), and for real judges from public judicial directories
   (First Judicial District). Corpus-derived artifacts — distinct-value
   frequency reports, coverage checks — are curation inputs that live under
   `~/court-data/` only. This keeps the letter of the repo-tree rule while
   making rosters reproducible. Roster contents require plan-level review
   before commit (they are public-facing names).
8. **Seeded/real coexistence.** Sprint 2's fake-judge and demo-charge seeds
   stay until the Sprint 7 sweep. Real and seeded rows share `ref.*`
   tables; seeded rows are identified by the slug registry in `db/seeds/`
   (already the upsert key); the Sprint 7 sweep deletes by that registry.
   Real-roster inserts assert no slug collision with the seed registry.
   Fabricated statistics never attach to real judges — structurally
   guaranteed this sprint because no new aggregates are generated at all.
9. **Unmatched is a state, not a failure.** Unmatched/ambiguous charges,
   judges, dispositions, and sentence components produce review items and
   ineligible facts — never crashes, never silent acceptance, never public
   eligibility. Ambiguous results carry their candidate set in review-item
   context (structural references + the raw matched value; raw values are
   internal-sensitive and permitted in `review.*`, which is admin-only by
   architecture).
10. **Money and residual-duration parsing happen at normalization.** The
    parser is not reopened for monetary extraction. A normalization-stage
    extractor reads sentence `raw_text`/`program`, emits amount-in-cents
    where parseable plus a `MONEY_UNPARSEABLE` review path where a monetary
    category is asserted but no amount parses. Duration fields (min_days /
    max_days / min_assumed) are consumed as parsed; the 280
    UNPARSEABLE_DURATION envelope warnings route to review items, not to
    re-parsing.
11. **Sentence-type mapping table is locked at plan level.** The
    `sentence_type` → sentencing-category map (including the IPP and ARD
    component decisions, restitution/community-service pattern detection,
    and what falls to `other` vs review) ships as an explicit table in the
    22.5 task spec and requires planning-chat approval before
    implementation — same discipline as warning-code additions.
12. **Conditional keys are presence-checked.** `event_name`/`event_date`
    (held charges only) and `min_assumed` (True only) are ABSENT, not
    null, when inapplicable. Loader and normalizer use presence checks;
    DB columns are nullable and absence maps to NULL/false explicitly.
13. **court_type: verify, then decide.** Recon read the code path as
    populating `case.court_type` via `detect_court_type`; the verified
    corpus-wide finding is None everywhere. Task 24.3 opens by
    establishing actual behavior on the canonical envelope set before the
    populate-vs-drop decision. The docket-number prefix remains the
    authoritative court-type source regardless; the loader stores the
    record value as-is and separately derives prefix-based court type at
    load time (reconciling the 16.3 CP/MC code vs the record's expanded
    string).
14. **Corpus growth is protocol-governed.** The 1,603-fixtures invariant is
    superseded the moment COL intake lands (24.2): new dockets have NO
    Capstone-baseline entry (the baseline is immutable and remains the
    port anchor only); they enter goldens via `--init-goldens` with a
    worklog note; corpus counts are restated in the worklog and in this
    plan's status log at intake. Growth is deliberate, counted, and
    reconciled — never incidental.
15. **Sentence dates are disposition dates.** Recon confirmed
    `sentence_date` is copied from the charge's `disposition_date`.
    Sentencing MVP eligibility therefore keys off the same date as outcome
    eligibility; the methodology report must state this honestly rather
    than implying independent sentencing-date capture.
16. **Phase numbering continues from Sprint 4: Phases 21–25.**

---

## MVP Data Range (restated)

MVP data coverage starts **January 1, 2025**, enforced at fact eligibility
this sprint (and again at aggregation in Sprint 7):

- Outcome facts are MVP-eligible only if `disposition_date` ≥ 2025-01-01.
- Sentence facts are MVP-eligible only if `sentence_date` ≥ 2025-01-01
  (which per Standing Decision 15 equals the disposition date).
- Earlier-filed cases qualify if the event date qualifies.
- Missing dates → ineligible with a reason code (and MISSING_* warnings
  already flow to review via envelope warnings); never silent inclusion.

---

## Technical Assumptions (carried + recon-confirmed)

| Area | Choice |
|---|---|
| Parser output | Envelope v5 / record schema v2; charge-keyed dispositions and sentences; 11-code warning vocabulary; conditional keys per SD 12 |
| Canonical input | 1,603 envelopes at `~/court-data/envelopes-2026-07-11-172514/` (the only set) |
| Pipeline language | Python 3.12, uv, ruff, pytest (4.2 conventions) |
| DB | PostgreSQL 17.10, Docker port 5433; Kysely migrations own DDL |
| Python DB driver | psycopg 3, pinned in uv |
| Taxonomy | `@pca/taxonomy` artifacts (`taxonomy.json` for Python), TAXONOMY_VERSION "1.0.0", package-only until Sprint 7 |
| Reference data | `ref.*` tables (Sprint 2 shapes confirmed by recon) |
| Tests | pytest + tier-1 synthetic fixtures/goldens in CI; Vitest for any TS-side work |
| Real-data access | Agent runs corpus operations end-to-end per §6.10 (sources salt + DATABASE_URL, never echoes) |
| CI | Tier-1 only; never references `~/court-data/`; six CLAUDE.md gates + staging-completeness gate on every completion report |

---

## Human Steps (Chops) — Sprint 5 Prerequisites

1. Confirm `DATABASE_URL` is present in the monorepo `.env` and documented
   in `.env.example` (the local Postgres on port 5433).
2. Decide COL Run cadence for the sprint window (the intake task consumes
   whatever the collector has landed in `~/court-data/intake/`; more runs =
   more MC evidence). Per-operator caps and ADR 0002 conditions apply.
3. Roster review (mid-sprint, planning chat): approve the curated charge
   and judge rosters before they are committed (Standing Decision 7).
4. Git/PR mechanics per task, as always.

---

# Phase 21 — Fact-Layer Foundation

## Task 21.1 — `raw.source_documents` + `parsed.*` Table Migrations

Creates the internal document and parsed layers. Kysely migrations +
`db/src/types.ts` typing.

Tables:

- `raw.source_documents` — id (uuid), file hash (unique), original
  filename, file size, imported_at, import mode, docket-number provenance
  fields from the 16.3 record (including the raw CP/MC code and county
  code), status, error code, timestamps
- `parsed.dockets` — id, FK to source document, docket_number, record
  parser_version, envelope parser_version, parsed_at, case fields (county,
  court_type as recorded, prefix-derived court type, case_status,
  filed_date, otn, dc_number, cross_court_dockets raw, defendant_hash),
  envelope status, review_needed, loaded_at
- `parsed.charges` — id, FK to docket, sequence, statute, grade, offense,
  disposition_raw, disposition_date, disposition_judge_raw, event_name,
  event_date (nullable; presence-mapped per SD 12)
- `parsed.sentences` — id, FK to charge, component order, sentence_type,
  min_days, max_days, min_assumed (bool, default false), program,
  sentence_date, raw_text
- `parsed.warnings` — id, FK to docket, code, section, charge_sequence,
  page, field (the envelope's structural warning objects, queryable)
- `parsed.related_cases` — id, FK to docket, related docket_number, court,
  association_reason

Acceptance criteria:

1. Migrations follow naming conventions, apply and roll back cleanly; one
   migration file for the FK-related `parsed.*` family, one for `raw.*`.
2. UUID PKs via `gen_random_uuid()`; `updated_at` triggers attached where
   the column exists; unique constraint on `raw.source_documents.file_hash`
   and on `(docket_id, sequence)` in `parsed.charges`.
3. `db/src/types.ts` gains the new tables with correct nullability;
   `pnpm generate` / typecheck green.
4. No defendant-name column anywhere (defendant_hash only — the parser
   never emits names and the schema must not invite them).
5. Migration docs updated; all repo gates green.

## Task 21.2 — `fact.*` + `review.queue_items` Table Migrations

Tables:

- `fact.fact_build_runs` — id, status, parser_version, envelope version,
  taxonomy_version, roster snapshot note, started/completed, counts JSON
- `fact.charge_outcomes` — id, build run FK, parsed charge FK, parsed
  docket FK, normalized_charge_id FK, outcome category code (string),
  disposition_date, normalized_judge_id FK (nullable), judge attribution
  method, attribution method (`charge_row`), match methods (charge,
  outcome), mvp_eligible bool, public_eligible bool, judge_specific_eligible
  bool, ineligibility reason codes (text[]), review_needed, taxonomy_version,
  created_at
- `fact.charge_sentences` — id, build run FK, parent outcome fact FK,
  parsed sentence FK, normalized_charge_id, sentencing category code,
  sentence_date, min_days, max_days, min_assumed, amount_cents (nullable),
  normalized_judge_id (nullable), judge attribution method, attribution
  method (`charge_component`), match methods, eligibility trio + reason
  codes, review_needed, taxonomy_version, created_at
- `review.queue_items` — id, item type (controlled vocabulary), severity,
  source document FK, parsed docket FK, parsed charge FK (nullable),
  parsed sentence FK (nullable), entity type, raw value, candidate context
  (jsonb, structural), reason code, status (default `open`), created_at,
  dedup key (unique)

Acceptance criteria:

1. All tables exist with enforced FKs; fact rows are immutable by
   convention (created_at only, update-never typing — Sprint 2 precedent).
2. Review-item dedup key is a DB unique constraint (not app-only):
   deterministic over (source document, parsed record reference, item
   type).
3. Review item type and reason-code vocabularies are defined in one Python
   module (mirroring the warning-code pattern); the migration stores them
   as text — vocabulary lives in code, additions need plan-level approval.
4. Eligibility reason codes are a controlled vocabulary in the same module.
5. Migrations apply/roll back cleanly; types generated; gates green.

## Task 21.3 — Python DB Access + `pipeline load` + Canonical Corpus Load

Fills the loader gap (Capstone's SQLite loader was never ported —
`parse_docket_checked` is the anticipated seam).

Acceptance criteria:

1. psycopg 3 pinned in uv; a thin DB module reads `DATABASE_URL` at the CLI
   boundary only; no auto-loaded `.env`; refuses to run in CI.
2. `pipeline load --envelopes-dir <path>`: reads envelope JSONs, validates
   envelope version, upserts `raw.source_documents` (joining 16.3 import
   metadata where present) and inserts the docket/charges/sentences/
   warnings/related-cases graph transactionally per docket.
3. Idempotent per SD 5: full re-run of the same set = 0 changed rows,
   reported as skips; newer parser_version replaces per-docket
   transactionally; per-docket exception isolation (one bad envelope never
   kills the run — per-docket failure status, Sprint 4 comparator
   precedent).
4. `failed`-status envelopes (the quarantine class) load as
   `parsed.dockets` rows with null record fields and their error preserved
   — visible to Sprint 6 review, excluded from all fact generation.
5. Console/log hygiene: counts, statuses, hash-prefix ids only.
6. Acceptance run (agent-executed, raw output verbatim): full canonical
   load of 1,603 envelopes; report row counts per table; warning-count
   reconciliation against the known envelope tallies (UNPARSEABLE_DURATION
   280, MISSING_DISPOSITION_DATE 211, NON_TERMINAL_CASE 104,
   SENTINEL_COLLISION 17, SUSPECT_JUDGE_LINE 3,
   UNKNOWN_NOT_FINAL_DISPOSITION 2; review_needed = 75 dockets). Any
   mismatch is stop-and-report.
7. Tier-1 synthetic-envelope loader tests in CI (loading into a test
   database via the existing CI Postgres service); all gates green.

---

# Phase 22 — Rosters + Normalization

## Task 22.1 — Normalization Models + Vocabularies

Greenfield module(s) defining the shared shapes every matcher uses. No
numeric confidence (SD 2).

Acceptance criteria:

1. Result models for charge, judge, outcome, and sentencing normalization:
   raw value, normalized id/code (if matched), display name (if matched),
   `match_method` from the locked vocabulary (`exact` / `alias` /
   `statute` / `pattern` / `unmatched` / `ambiguous`), warning codes,
   review_needed, candidate list (ambiguous only).
2. Money extraction result model: raw text, amount_cents | None, warning
   codes.
3. Review-item construction helpers enforce the 21.2 vocabularies and the
   dedup-key derivation; raw values permitted (internal-only tables),
   structural context otherwise.
4. Unit tests over model construction, method vocabulary enforcement, and
   dedup-key determinism; gates green.

## Task 22.2 — Charge Roster + Charge Normalization

Roster (SD 7): curated real-charge seed sourced from public statute
references, coverage-validated against the corpus locally.

Acceptance criteria:

1. Local (never committed) distinct-value report over
   `parsed.charges.statute`/`offense` from the loaded corpus: distinct
   values + frequencies, written under `~/court-data/reports/` — curation
   input.
2. Committed charge-roster seed extends `db/seeds/` (upsert on slug):
   display names + statute codes from public references covering at
   minimum every statute appearing ≥ N times in the corpus (N proposed in
   the agent plan, approved in planning chat); aliases for observed text
   variants sourced as public statute phrasing, not verbatim corpus rows.
   **Roster reviewed in planning chat before commit** (Human Step 3).
3. Matcher: exact (case/punctuation/whitespace-insensitive) → alias →
   statute-code match; statute match may override weak text match;
   conflicting statute/text = `ambiguous` + review item; multiple plausible
   candidates = `ambiguous` + candidates; unmatched = review item.
4. Seeded demo charges are matchable but the coexistence rules (SD 8)
   hold; no slug collisions.
5. Tier-1 synthetic tests: exact, alias, statute, conflict, ambiguous,
   unmatched; gates green.

## Task 22.3 — Judge Roster + Judge Normalization (Durable Fix)

The Sprint 4-designated durable fix for judge validity. Parser heuristics
stay as shipped; validation happens here against a real roster.

Acceptance criteria:

1. Local distinct-value report over `assigned_judge_raw` +
   `disposition_judge_raw` (frequencies; hash-prefix docket ids only in
   any per-docket detail), under `~/court-data/reports/`.
2. Committed judge-roster seed from public judicial directories (FJD
   Common Pleas + Municipal Court), obviously-fake Sprint 2 seeds
   untouched; slug-collision assertion; **roster reviewed in planning chat
   before commit**.
3. Matcher: exact → alias/variant with honorific stripping, middle-initial
   tolerance, punctuation/case insensitivity; match methods recorded;
   name-shaped-but-not-a-judge values (the issuing-authority class from
   the sentinel root-cause finding) resolve to `unmatched` + review item —
   never silently accepted, never guessed.
4. Role context preserved: results carry the source field (assigned vs
   disposition judge); roles are never upgraded or merged.
5. Recovered-7 resolution path: the 5 SENTINEL_COLLISION dockets' nulled
   judge fields flow through as unmatched/absent with their existing
   review flags; the acceptance run shows their disposition data survives
   into normalization while judge attribution stays conservatively empty.
6. Tier-1 tests: exact, variant, honorific, initial, unmatched,
   issuing-authority-shaped value; gates green.

## Task 22.4 — Outcome Mapping (Disposition → Taxonomy)

The disposition map is built fresh for PCA. Opening cleanup honored: the
Capstone truncated-form workaround entry ("Transferred to Another…") is
excluded — the 18.2 parser repair made it unreachable (16 repairs,
truncated form no longer emitted), and a hygiene test proves the map
contains no truncated-form key.

Acceptance criteria:

1. Local distinct-value report over `disposition_raw` (frequencies) —
   curation input for the map.
2. Mapping module: `disposition_raw` → outcome category code
   (`dismissed` / `withdrawn` / `guilty_plea` / `guilty_verdict` /
   `acquittal` / `ard` / `diversion` / `other` / `unknown`), taxonomy
   loaded from `@pca/taxonomy` `taxonomy.json`, taxonomy_version recorded
   on every result; map entries are corpus-evidenced exact matches
   (the 18.2 repair-table principle, applied to mapping) — no fuzzy
   disposition matching.
3. Unmapped disposition → `unknown` + review item; `unknown` is never
   public-eligible; null disposition on a held charge is NOT an unmapped
   outcome (held charges produce no outcome fact at all).
4. Truncated-form hygiene test per above.
5. The full map table ships in the task spec for planning-chat approval
   before implementation (SD 11 discipline applies here too).
6. Tier-1 tests over every category + unmapped; gates green.

## Task 22.5 — Sentencing Mapping + Money Extraction

Acceptance criteria:

1. `sentence_type` → sentencing-category map per the locked table
   (SD 11; ships in the task spec, approved in planning chat before
   implementation — includes the IPP and ARD-component decisions).
2. Pattern-based detection of restitution and community service inside
   component `raw_text`/`program` (the 20.2 restitution flag): detected
   patterns produce ADDITIONAL category mappings on the same component
   where the taxonomy requires it, or route to review when ambiguous —
   components are never collapsed; conservative false-negative bias,
   documented.
3. Money extractor per SD 10: amount_cents from `raw_text`/`program` for
   monetary categories (fine, costs_fees, restitution) — handles commas,
   decimals, multiple amounts (policy for multiples locked in the task
   spec); monetary category asserted with no parseable amount →
   `MONEY_UNPARSEABLE` review item, category mapping still stands.
4. Durations consumed as parsed (min_days/max_days/min_assumed);
   UNPARSEABLE_DURATION envelope warnings produce review items at fact
   build; no re-parsing.
5. Unmapped/ambiguous components → review items; `unknown` never
   public-eligible.
6. Tier-1 tests: every sentence_type, restitution pattern, community
   service pattern, money success/multi/failure, unmapped; gates green.

---

# Phase 23 — Attribution + Facts

## Task 23.1 — Judge Attribution Rules

The genuine attribution problem (SD 1). Conservative by construction.

Acceptance criteria:

1. Outcome facts: judge attribution uses `disposition_judge_raw`
   (normalized via 22.3) when matched; else `assigned_judge_raw` ONLY
   under an explicit, documented rule set proposed in the agent plan and
   approved in planning chat (e.g., single-judge dockets where assigned
   judge is roster-matched); else unattributed. Attribution method
   recorded (`disposition_judge` / `assigned_judge_rule` / `none`).
2. Sentence facts inherit the parent outcome fact's judge attribution
   (sentence components carry no judge of their own — recon-confirmed;
   the methodology report states this).
3. Unattributed or ambiguous judge never blocks charge-only facts; it
   only gates judge_specific_eligible (23.2/23.3).
4. Ambiguous attribution (e.g., roster-matched disposition judge
   conflicting with roster-matched assigned judge under the rule set) →
   review item.
5. Tier-1 tests: disposition-judge match, assigned-only rule case,
   unmatched, conflict; gates green.

## Task 23.2 — Outcome Fact Generation + Eligibility

Acceptance criteria:

1. Fact builder reads `parsed.*` + rosters + maps, writes
   `fact.charge_outcomes` under a `fact_build_runs` run (delete-and-
   reinsert per SD 6). One fact candidate per disposed charge; held
   charges (event-key presence, null disposition) produce NO outcome fact
   and are counted in the run report.
2. Eligibility (all explicit booleans + reason codes, no thresholds):
   `mvp_eligible` = disposition_date present and ≥ 2025-01-01;
   `public_eligible` = mvp_eligible AND charge match ∈ {exact, alias,
   statute} AND outcome category public AND review_needed false AND no
   blocking warning on the docket/charge (blocking set locked in the task
   spec from the 11-code vocabulary); `judge_specific_eligible` =
   public_eligible AND judge attributed via 23.1.
3. Every ineligible fact carries machine-readable reason codes; every
   fact carries attribution method, match methods, parser/taxonomy
   versions.
4. Quarantine-class dockets (failed envelopes) produce zero facts.
5. Tier-1 golden tests over synthetic fixtures (fact outputs + reason
   codes, committed goldens); gates green.

## Task 23.3 — Sentence Fact Generation + Eligibility

Acceptance criteria:

1. Builder writes `fact.charge_sentences` linked to parent outcome facts;
   multiple components preserved 1:1 (never collapsed); duration and
   amount fields carried where present.
2. Eligibility mirrors 23.2 with: parent outcome fact must exist and be
   public_eligible for the sentence fact to be public_eligible;
   sentence_date rule per SD 15; sentencing category public; component
   match method valid; reason codes on every ineligible fact.
3. Sentencing sample independence is structurally real: outcome facts
   without sentence facts are normal; the run report counts both
   populations separately.
4. Tier-1 golden tests including probation+fine and confinement+probation
   multi-component cases; gates green.

## Task 23.4 — Review Item Generation + Dedup Wiring

Cross-cutting task that makes 22.x/23.x review paths land in
`review.queue_items` uniformly.

Acceptance criteria:

1. All normalization and attribution review paths write through the 22.1
   helpers into `review.queue_items`; item types cover: unmapped/ambiguous
   charge, unmapped/ambiguous judge, unmapped disposition,
   unmapped/ambiguous sentencing component, money unparseable, duration
   unparseable, ambiguous judge attribution, missing disposition date
   (from envelope warnings at fact build), sentinel collision carry-over.
2. Dedup is DB-enforced (21.2 unique key); re-running the fact build is
   idempotent on the review queue (existing items untouched, including
   their status); tests prove repeated processing adds zero duplicates.
3. Item counts by type are part of every fact-build run report.
4. Gates green.

## Task 23.5 — Structured CP↔MC Held-Case Linkage

The 18.3 deferral lands. Raw inputs: `case.cross_court_dockets` (raw
string) + `related_cases` (structured, association-reason vocabulary).

Acceptance criteria:

1. Link model + table (`parsed.docket_links` or equivalent, migration in
   this task): source docket, target docket number (and target parsed
   docket FK when the target is in-corpus), link type (controlled
   vocabulary; at minimum `held_for_court`), evidence source
   (cross_court_dockets / related_cases), created_at.
2. Linker parses docket numbers from the raw cross-court string with the
   bounded UJS pattern; unresolvable fragments → review item, never a
   guess.
3. MC held dockets linking to in-corpus CP dockets are reported as
   resolved pairs (counts; hash-prefix ids in any detail artifact);
   out-of-corpus targets recorded as unresolved links (future collection
   targets — feeds the coverage story).
4. Linkage is informational this sprint: it does not change fact
   eligibility (attribution consequences are a Sprint 7 aggregation
   question, stated in the report); this boundary is explicit in code
   comments and the report.
5. Tier-1 tests: held MC fixture with cross-court reference resolves;
   malformed string → review item; gates green.

---

# Phase 24 — Corpus Run + Intake + Decisions

## Task 24.1 — Full-Corpus Fact Build (Acceptance Authority)

The corpus run, not the unit suite, is the acceptance authority (6.8).

Acceptance criteria:

1. Agent executes end-to-end on the loaded canonical corpus: normalization
   + attribution + fact build + review generation; raw output verbatim in
   the completion report.
2. Run report (under `~/court-data/reports/`, run-unique filename):
   normalization match-method distributions per entity type; outcome and
   sentencing category distributions; fact counts (outcome, sentence);
   eligibility funnel (total → mvp_eligible → public_eligible →
   judge_specific_eligible) with reason-code tallies; review items by
   type; held-charge and quarantine exclusion counts; linkage resolution
   counts.
3. Reconciliation gates (stop-and-report on any mismatch): disposed-charge
   count = outcome-fact count + explained exclusions; sentence-component
   count = sentence-fact count + explained exclusions; the 104
   NON_TERMINAL_CASE dockets produce zero outcome facts for their held
   charges; the recovered-5 show conservative judge behavior per 22.3;
   review_needed docket count consistent with envelope tallies.
4. Unexplained anomalies are stop-and-report, adjudicated in planning
   chat — never self-adjudicated.

## Task 24.2 — COL Intake Protocol + First Intake

Deliberate corpus growth (SD 14) + MC evidence deepening.

Acceptance criteria:

1. Documented intake protocol (agent-docs): collected PDFs from
   `~/court-data/intake/` → 16.3 import (content-hash dedupe reconciles
   any multi-operator overlap) → 16.2 extraction → parse → tier-2
   `--init-goldens` (worklog note) → `pipeline load`. The Capstone
   baseline is untouched (immutable port anchor; new dockets have no
   baseline entry, and the equivalence comparator is not run over them).
2. First intake executed over whatever COL runs have landed by this task:
   run report with counts at every stage (imported / duplicate / invalid;
   extracted; parsed clean / flagged / failed; goldens initialized;
   loaded).
3. Corpus counts formally restated post-intake (worklog + planning chat):
   fixtures, goldens, envelopes, loaded dockets — the new invariant
   supersedes 1,603 by name.
4. MC evidence position restated: MC docket count before/after, with the
   POC report's "correct-but-under-evidenced" verdict updated or
   explicitly left standing.
5. New-docket facts flow through a fact-build rerun (24.1 tooling);
   anomalies stop-and-report.

## Task 24.3 — `record.court_type` Populate-vs-Drop Decision

Acceptance criteria:

1. Verify actual behavior first (SD 13): query the loaded corpus for
   `court_type` distribution; reconcile the recon reading
   (detect_court_type populates) against the ledger finding (None
   corpus-wide); the verified answer is worklogged.
2. Decision executed per outcome, decided in planning chat:
   - If genuinely None corpus-wide → drop the record field in favor of the
     loader's prefix-derived column (a record-schema change:
     parser_version bump, golden update with `--update-goldens` + worklog,
     corpus rerun proving the diff set is exactly the removed key), OR
     populate from prefix at parse (same discipline).
   - If populated → keep, and the loader's prefix-derived column becomes a
     consistency check (mismatch → review item).
3. Either path: goldens, tier-2 drift check, and the delta discipline from
   Sprint 4 apply in full; this is the sprint's only sanctioned parser
   touch.

---

# Phase 25 — Report + Sprint Close

## Task 25.1 — Normalization and Attribution Report

File: `docs/normalization-attribution-report.md` (committed — counts and
rates only, nothing docket-derived beyond aggregates).

Acceptance criteria:

1. Covers: corpus position (post-intake counts); normalization match
   rates per entity type with method breakdowns; outcome/sentencing
   category distributions; eligibility funnel with reason-code analysis;
   review-item volume by type (the Sprint 6 workload preview); judge
   attribution coverage (what fraction of public-eligible outcome facts
   are judge-attributable — the judge-specific product surface's first
   real sizing); linkage resolution rates; recovered-7 disposition;
   known limitations (money-extraction coverage, sentence-date =
   disposition-date, MC evidence base, unmatched-roster tails).
2. Methodology implications section (draft S5-012.2 preserved): how
   attribution works (one path each + judge rules), when facts are
   excluded, why sentencing sample size differs, how the 2025-01-01 rule
   applies, what "sentence date" actually is — written to be liftable
   into Sprint 7's public methodology copy, honesty bar identical to the
   POC report.
3. Explicit verdicts: Sprint 6 readiness (is the review queue real and
   triageable) and Sprint 7 readiness (are eligible-fact volumes
   sufficient to aggregate, with thin-data expectations previewed).
4. No overclaiming; copy review gate applies.

## Task 25.2 — Human Step: Exit Demo + Sprint Close

Chops runs the exit demo and reviews in the planning chat:

1. `parsed.*` row counts for the loaded corpus; one docket's full graph
   (hash-prefix id) walked from source document to sentences
2. Charge normalization: an exact, an alias, a statute, and an unmatched
   case from the run report
3. Judge normalization: a roster match and an issuing-authority-shaped
   unmatched; a recovered-5 docket showing conservative judge handling
4. Outcome + sentencing mapping distributions; a restitution pattern
   detection; a money extraction with amount_cents
5. An outcome fact and its sentence facts in `fact.*`, with eligibility
   booleans and reason codes; a charge-only-eligible /
   judge-specific-ineligible example
6. The 2025-01-01 eligibility boundary demonstrated (pre/post examples)
7. Review queue counts by type; dedup demonstrated (rerun adds nothing)
8. A resolved CP↔MC held-case link pair
9. Intake outcome: corpus counts before/after; MC evidence position
10. court_type verdict and its executed consequence
11. Tier-1 suites green in CI; full CI green
12. Report walkthrough — Sprint 6 and Sprint 7 readiness verdicts

Sprint 5 closes here; Sprint 6 (Admin Review MVP) planning begins.

---

## Sprint 5 Definition of Done

1. `raw.source_documents`, `parsed.*`, `fact.*`, `review.queue_items`, and
   the linkage table exist via migrations; types generated.
2. `pipeline load` is idempotent, per-docket-isolated, hygiene-compliant;
   the canonical corpus is loaded and reconciled against envelope tallies.
3. Real charge and judge rosters are committed from public sources,
   planning-chat approved, coexisting with Sprint 2 seeds per the
   registry rule.
4. Charge, judge, outcome, and sentencing normalization work with
   categorical match methods; no numeric confidence exists anywhere.
5. The disposition map contains no truncated-form workaround (hygiene
   test).
6. Money extraction and restitution/community-service detection work at
   the normalization stage; the parser is untouched (24.3 excepted).
7. Judge attribution is conservative, rule-documented, and never blocks
   charge-only facts.
8. Outcome and sentence facts exist in `fact.*` with the eligibility trio,
   reason codes, and delete-and-reinsert run semantics; held charges and
   quarantine dockets produce no facts.
9. Review items generate with DB-enforced dedup; rerunning adds zero
   duplicates and preserves triage status.
10. Structured CP↔MC linkage exists; unresolved targets are recorded, not
    guessed.
11. The full-corpus fact build passed its reconciliation gates; all
    anomalies were adjudicated in planning chat.
12. COL intake protocol is documented and executed once; corpus counts
    restated; MC evidence position updated.
13. court_type is verified and decided, with full delta discipline on
    whichever path.
14. Tier-1 synthetic tests + goldens cover normalization, facts, and the
    loader in CI; CI never touches `~/court-data/`.
15. The report exists with Sprint 6 and Sprint 7 readiness verdicts.
16. No raw docket text in logs, console, or the repo; nothing
    corpus-derived committed beyond aggregate counts in the report;
    fabricated statistics attach to no real judge.
17. Exit demo reviewed; sprint closed in the planning chat.

---

## Sprint 5 Risks (with mitigations locked)

1. **Roster tails fragment the data** (charges/judges that never match) →
   frequency-driven curation with an approved coverage threshold;
   unmatched routes to review, feeding alias growth; the report sizes the
   tail honestly.
2. **Judge attribution is too weak to power judge-specific results** →
   charge-only eligibility is independent by construction; the report's
   attribution-coverage number is the honest early warning, and "judge
   data is thinner than hoped" is a finding, not a failure.
3. **Review volume swamps Sprint 6** → DB-enforced dedup, per-type counts
   in every run report, and roster/alias iteration this sprint before the
   admin UI exists.
4. **Money extraction underperforms** → category mapping never depends on
   amount parsing; MONEY_UNPARSEABLE routes to review; coverage reported,
   with Sprint 7 deciding whether amount-based views ship at all.
5. **Fact rebuilds destabilize the review queue** → run-scoped facts but
   dedup-keyed review items with preserved status; idempotency is tested,
   not assumed.
6. **Intake breaks corpus invariants silently** → SD 14 protocol: counted,
   worklogged, goldens via --init-goldens, baseline untouched, restated
   invariant by name.
7. **2025+ window makes eligible data thin** → the eligibility funnel and
   reason-code tallies quantify exactly what the window costs; thin-data
   handling exists downstream; architecture unchanged.
8. **Loader/DB coupling breaks CI** → tier-1 loader tests use the CI
   Postgres service; all real-corpus operations refuse CI; the six gates +
   staging-completeness gate apply to every task.

## Handoff to Sprint 6

Sprint 6 (Admin Review MVP) begins when the exit demo passes and provides:
a populated `review.queue_items` table with typed, deduplicated,
status-carrying items; loaded `parsed.*` context for review detail views;
`fact.*` candidates with eligibility reason codes; the report's review-
volume-by-type workload preview; and the normalization rosters whose
alias growth the admin correction workflow will drive. Sprint 6 focuses
on admin auth, the review queue UI/API, item detail with safe raw
context, approve/correct/exclude actions, audit events, and applying
corrections to subsequent fact-build runs.