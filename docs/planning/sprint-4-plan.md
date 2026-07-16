# Sprint 4 Plan: Parser Proof of Concept (Capstone Port + Harden)

## Sprint 4 Goal

Port the proven Capstone (CP51) docket parser into the PCA pipeline, prove the
port faithful against a regenerated Capstone baseline, then harden its
documented failure modes — establishing whether UJS docket PDFs (CP **and**
MC) can reliably feed the product's charge-level analytics.

By the end of Sprint 4:

- the pipeline extracts text from docket PDFs with the locked pdfplumber
  approach and detects low-text/image-only documents
- manual import with content hashing and duplicate detection works
- the ported parser produces structured output for docket metadata, charges,
  judge fields, dispositions, and sentences — for both CP and MC dockets
- port fidelity is proven by field-level equivalence against Capstone's
  regenerated output over the full working corpus (1,258 CP + 40 MC)
- the documented failure modes are hardened, each with a visible before/after
  golden delta
- parser output carries stable warning codes and review-needed flags
- a committed synthetic fixture corpus drives regression tests in CI; the
  real corpus drives a local golden run
- a parser POC report assesses CP and MC readiness separately and states
  whether Sprint 5 can proceed

Sprint 4 does **not** produce public aggregates, load the database, or
normalize anything. It proves the parsing foundation.

---

## Locked Sprint 4 Scope

### In Scope

- Port of Capstone parser modules: `helpers`, `identity`, `docket_parser`
  (config.py explicitly NOT ported — severed)
- Production pdfplumber extraction stage (pinned version) + low-text /
  image-only detection + extracted-text artifacts
- Manual import command: content hashing, duplicate detection, import
  metadata (greenfield — Capstone has none)
- Extraction-seam equivalence check (our extraction vs Capstone's, same PDFs)
- Baseline equivalence run: ported parser vs regenerated Capstone baseline
  over the full working corpus — the port-correctness gate
- Warning-code + review-needed framework and parser output envelope
  (greenfield — no confidence concept exists in Capstone)
- Hardening of the locked failure-mode list (see Standing Decisions)
- Two-tier fixture strategy: committed synthetic text fixtures + golden
  outputs (CI), real corpus + goldens outside the repo (local)
- `run-fixtures` CLI and golden comparison tooling
- CI wiring for the tier-1 regression suite
- Parser POC report with per-court readiness assessment and honest
  limitations
- Both CP and MC dockets as first-class parse targets

### Out of Scope

- broad automated UJS ingestion — the Capstone Playwright collector stays
  PARKED pending source-access/compliance review; no collector work of any
  kind this sprint
- database loading (`parsed.*` tables stay empty; loader work is Sprint 5)
- charge/judge normalization, outcome/sentencing taxonomy mapping (Sprint 5)
- charge-level attribution rules (Sprint 5)
- structured CP↔MC de-novo case linkage (raw capture only this sprint;
  linkage is Sprint 5 attribution work)
- numeric parser confidence scoring (rejected — see Standing Decisions)
- OCR implementation (detect and flag only)
- external LLM/document-extraction services
- docket-number pseudonymization of tier-2 goldens (deferred to Sprint 8
  staging validation — goldens live outside all repos, so nothing is
  violated meanwhile)
- admin review UI
- production deployment

---

## Sprint 4 Standing Decisions

These extend the Sprint 1–3 decisions and are locked:

1. **Port-then-harden, in that order.** Phase 17 ports the Capstone parser
   faithfully — including its known quirks (disposition truncation,
   min-days fill, held-case null dates). Phase 18 hardens, one failure mode
   at a time, each change visible as a deliberate golden delta. No hardening
   lands before the 17.3 equivalence gate passes.
2. **Baseline equivalence is the port's acceptance test.** Chops regenerates
   Capstone's interim JSON over the working corpus and stages it at
   `~/court-data/capstone-baseline/`. The ported parser must produce
   field-equivalent output on the same inputs (metadata fields `parsed_at` /
   `parser_version` excluded from comparison). CP (1,258) and MC (40)
   subsets are reported separately; the MC pass is acknowledged as thin
   evidence, not proof.
3. **No numeric confidence.** Parser output carries stable warning codes and
   a derived `review_needed` boolean. A 0.00–1.00 score with no calibration
   behind it is false precision; the product rule ("ambiguous output is
   flagged, not silently accepted") is fully satisfied by structured
   warnings. If Sprint 5 attribution needs graded confidence, it is derived
   there from warning composition.
4. **Two-tier fixtures.** Tier 1: synthetic text fixtures + golden JSON
   outputs committed to the repo (fictional names, zero-sequence placeholder
   docket numbers only) — these drive the pytest regression suite and run in
   CI. Tier 2: the real PDF corpus and its goldens live under
   `~/court-data/` (corpus at `fixtures/`, goldens at `goldens/`, baseline
   at `capstone-baseline/`), outside all repos, exercised by a local
   `run-fixtures` invocation whose report is a human exit-demo artifact —
   never a CI dependency. CI must not reference `~/court-data/`.
5. **Committed fixture hygiene is machine-enforced.** A repo test asserts
   every tier-1 fixture and golden uses only placeholder docket-number
   patterns and contains no realistic docket numbers. Real docket text,
   PDFs, extracted text, and real-corpus goldens are never committed.
6. **`DEFENDANT_HASH_SALT` is required with no default.** Capstone's silent
   `"change-me-in-env"` fallback is not ported. The salt is an explicit
   required parameter; absence is a hard failure with a clear error. Salt
   lives in `.env`, documented in `.env.example`, never committed.
   `config.py` and its import-time side effects (dotenv load, directory
   creation) are not ported; env reading happens at the CLI boundary only.
7. **`docket_number` is supplied by the caller.** The parser API takes it as
   an explicit parameter. The import stage is responsible for determining it
   (filename stem is acceptable provenance for fixture PDFs but is data, not
   an API assumption).
8. **CP and MC are both in scope; MC is the less-validated path.** The
   Capstone MC support (Phase 7 delta) ports with everything else, but its
   evidence base is 40 records vs CP's 1,258. Consequences: per-court
   equivalence reporting (decision 2), per-court synthetic fixture variants
   wherever layout differs, per-court readiness assessment in the POC
   report, and a recommended (manual-only) MC corpus supplementation step.
9. **Locked hardening list** (each item = explicit deliverable with
   before/after golden delta):
   - junk judge rows — guard judge-line capture against sentence-fragment
     patterns
   - held-case event dates — capture the event-header date for non-terminal
     events into a new field; `disposition_date` stays null (held cases have
     no disposition — the output stays honest)
   - disposition truncation — fix "Transferred to Another Jurisdiction"
     capture at the parser (the disposition-map workaround was a patch)
   - `min_days` defaulting — value unchanged (CP-validated), plus a
     `min_assumed: true` annotation when the minimum was filled from the
     maximum or a flat value
   - amended/downgraded/replaced charge signal — conservative pattern
     flagging (warning + review-needed); charges are never merged
   - third-party name guard — pattern-based extension of the sentinel
     machinery where feasible; the residual limitation is documented
     honestly in the POC report. Full NER-grade detection is out of scope.
     **(Chops signed off on shipping this as a documented limitation.)**
10. **`year = 360` days is kept.** Consistently applied, validated against
    CP output, raw text always retained in `raw_text`. Our docs state 360
    (correcting Capstone's 365 doc drift). Display-unit questions belong to
    Sprint 7 aggregation.
11. **Extraction artifacts and parser outputs from real dockets are written
    outside the repo** (default output roots under `~/court-data/`),
    configurable per invocation. Nothing derived from real dockets lands
    inside the repo tree. Raw docket text is never printed to logs or
    console — ParseError messages and reports name sections/fields/counts
    only (Capstone convention, ported and kept).
12. **pdfplumber is pinned** in the pipeline's uv dependencies (exact
    version recorded; Capstone resolved 0.11.10). pymupdf/pypdf remain
    eval-harness-only per ADR 0001 and must not be imported by production
    pipeline stages.
13. **Warning codes are a stable vocabulary** defined in one module; the
    agent may propose additions but each addition requires plan-level
    approval. Warnings carry structural context only (section, charge
    sequence, page number) — never raw docket text.
14. **Phase numbering continues from Sprint 3: Phases 16–20.**

---

## MVP Data Range (restated)

MVP data coverage starts **January 1, 2025**. Sprint 4's job is to capture
the dates that later enforce this rule: disposition dates, sentence dates,
filing dates, and (new in 18.3) event-header dates for non-terminal events.
Parser fixtures may include pre-2025 dockets where needed for format
coverage; the range rule is enforced at aggregation (Sprint 7), not at parse.

---

## Technical Assumptions (carried + recon-confirmed)

| Area | Choice |
|---|---|
| Pipeline language | Python 3.12 (uv, ruff, pytest — 4.2 conventions) |
| Extraction | pdfplumber, pinned (ADR 0001); `page.extract_text()` only |
| Parser source | Capstone `docket_parser.py` (626 LOC) + `helpers.py` + `identity.py` |
| Parser input contract | ordered page-text strings; pure-stdlib core (`parse_docket_text`) |
| Parser output | JSON artifacts (envelope defined in 18.1); no DB writes |
| Privacy | salted defendant hash; sentinel leak assertion pre-write; salt required |
| Fixtures | tier 1 synthetic in-repo (CI) / tier 2 real corpus outside repo (local) |
| Baseline | regenerated Capstone interim JSON at `~/court-data/capstone-baseline/` |
| Tests | pytest; Capstone's 47-test suite ports where applicable |
| CI | tier-1 regression only; fail-loud; no `~/court-data/` access |

---

## Human Steps (Chops) — Sprint 4 Prerequisites

1. Set `DEFENDANT_HASH_SALT` in the monorepo `.env` (generate a strong random
   value; it must match across runs for stable hashes — record it in your
   password manager, never in git).
2. Create `~/court-data/goldens/`, `~/court-data/capstone-baseline/`, and
   `~/court-data/extracted/`.
3. Regenerate the Capstone baseline: run Capstone's parse over its raw corpus
   and copy the interim JSON (1,258 CP + 40 MC) into
   `~/court-data/capstone-baseline/`. Exact commands ship in the 17.3 task
   spec. Required before 17.1/17.3.
4. **Recommended:** manually supplement the MC corpus — download additional
   2025 MC dockets (and any CP dockets that fill scenario gaps) into
   `~/court-data/fixtures/`, prioritizing the two unverified MC renderings
   (a decided trial verdict; an AMP-specific diversion). Manual downloads
   only. The collector stays parked.

---

# Phase 16 — Port Foundation

## Task 16.1 — Helpers + Identity Port

Port `helpers.py` (parse_date, to_days, GRADES, ParseError) and `identity.py`
(hash_defendant, normalize_name, assert_no_leak, assert_related_cases_clean)
into the `pipeline` package.

Acceptance criteria:

- modules live under the pipeline src layout; no `config.py` port; no
  import-time side effects (no dotenv, no directory creation)
- salt is an explicit required parameter of `hash_defendant`; a missing/empty
  salt raises with a clear error; env reading happens only at the CLI
  boundary and `.env.example` documents `DEFENDANT_HASH_SALT`
- `to_days` behavior preserved exactly (unit map day=1/month=30/year=360,
  decimals, fraction forms, compound units, `None` for unparseable);
  the 360 convention documented in the docstring
- `assert_no_leak` semantics preserved: recursive value-only scan, sentinel
  ≥3 chars, key-allowlist proven by test; `assert_related_cases_clean`
  field-set check preserved
- Capstone's helper/identity tests (13) ported and passing; ruff clean;
  CI green

## Task 16.2 — Production Extraction Stage + Text Artifacts

Fills the Sprint 1 `extract-text` placeholder with the real pdfplumber stage.

Acceptance criteria:

- extraction module: PDF path → ordered page-text list via
  `page.extract_text()` only; pdfplumber pinned in uv with the exact version
  recorded; pymupdf/pypdf not imported anywhere in production stages
- low-text/image-only detection with a configurable threshold; artifact
  status is one of `success` / `partial` / `needs_ocr_or_review` / `failed`;
  OCR not implemented
- extracted-text artifacts written to a configurable output dir defaulting
  under `~/court-data/extracted/` — never inside the repo; artifact includes:
  source file hash, extractor name + version, page-level text, extraction
  timestamp, text hash, status, warnings
- no raw docket text printed to logs/console
- tests use synthetic PDFs only (5.1 precedent); cover success, empty-page,
  low-text flagging, unreadable-file failure

## Task 16.3 — Manual Import: Hashing, Dedupe, Metadata

Fills the Sprint 1 `import-manual` placeholder. Greenfield — Capstone
dedupes by docket-number presence, not content hash.

Acceptance criteria:

- CLI scans a local directory; accepts `.pdf` only; computes sha256 content
  hash; detects duplicates by hash
- per-file import metadata record (JSON, written under the local data root
  outside the repo): id (hash-derived), original filename, file hash, file
  size, import timestamp, mode `manual`, county/court type when derivable
  from the docket-number pattern, status, error code on failure
- metadata contains no defendant-identifying information; no raw text logged
- run report: imported / duplicate / invalid / failed counts
- tests: valid import, duplicate skip, invalid-file rejection, empty
  directory, unreadable file, metadata creation, no-raw-text-logging

---

# Phase 17 — Faithful Parser Port

## Task 17.1 — Extraction-Seam Equivalence Check

The parser's token heuristics are coupled to CPCMS line ordering. Before any
parser code ports, prove our extraction reproduces Capstone's.

Acceptance criteria:

- comparator tool: given the 20-PDF fixture set, compares our 16.2 per-page
  text output against Capstone-produced reference text on the same PDFs
  (reference generated by Chops from the Capstone venv — human step,
  commands in the task spec)
- per-page, line-level comparison; divergence report written to a local
  artifact outside the repo; console output contains counts and page/line
  positions only — never docket text
- outcome recorded: either zero divergences, or every divergence triaged for
  parser impact with an explicit decision (accept / pin pdfplumber to
  Capstone's exact version / adjust)
- the decision is appended to the worklog and, if the pin changes, to uv
  dependencies

## Task 17.2 — Parser Port (`parse_docket_text` + `parse_docket`)

Faithful port of `docket_parser.py`. Known quirks intentionally preserved
this task: disposition truncation, min-days fill (without annotation yet),
held-case null dates.

Acceptance criteria:

- `parse_docket_text(docket_number, pages_text)` ports pure-stdlib —
  no pdfplumber import in its module path; `parse_docket` takes an explicit
  `docket_number` parameter (never derives it from the filename)
- section state machine, charge parsing (sequence keying, grade/statute/
  offense tokenization, continuation handling, IC-marker and
  Unknown-Statute guards), judge capture (assigned + per-charge disposition
  judge), disposition event gating (Final Disposition / "ard"), sentence
  component parsing (Min of/Max of → to_days, raw_text always retained),
  related-cases and court-type detection all port with behavior unchanged
- sentinel generation + `assert_no_leak` + `assert_related_cases_clean` wired
  at the same boundary as Capstone (post-parse, pre-write)
- output record shape matches the Capstone contract; MC support (court-type
  detection, DCN, held-for-court rendering, caption drop) ports intact
- Capstone's parser tests (the 8 MC tests plus applicable synthetic-text
  tests) ported and passing; ParseError messages never quote docket text
- ruff clean; CI green

## Task 17.3 — Baseline Equivalence Run (Port-Correctness Gate)

**Human prerequisite:** the regenerated Capstone baseline is staged at
`~/court-data/capstone-baseline/` (Human Steps item 3).

Acceptance criteria:

- comparator runs the ported extraction + parser over the Capstone raw
  corpus and diffs field-by-field against the baseline, excluding
  `parsed_at` / `parser_version`
- equivalence report separates CP (1,258) and MC (40) subsets explicitly
- gate: 100% field equivalence, or every divergence individually explained
  and accepted in the report (e.g. a pdfplumber-version difference already
  triaged in 17.1)
- divergence artifacts and the full report stay local (outside repo);
  worklog records the summary (counts, verdict) — never docket content
- Phase 18 does not begin until this gate passes and Chops confirms in the
  planning chat

---

# Phase 18 — Warnings + Hardening

## Task 18.1 — Warning Framework + Output Envelope

Greenfield: Capstone's parser has no warnings, flags, or confidence.

Acceptance criteria:

- stable warning-code vocabulary defined in one module; initial set:
  `LOW_TEXT_EXTRACTION`, `MISSING_CHARGE_SECTION`, `UNPARSEABLE_DURATION`,
  `MISSING_DISPOSITION_DATE`, `MISSING_SENTENCE_DATE`,
  `SUSPECT_JUDGE_LINE`, `SUSPECTED_AMENDED_CHARGE`, `NON_TERMINAL_CASE`,
  `UNSUPPORTED_FORMAT` — additions require plan-level approval
- warnings carry structural context only (section, charge sequence, page);
  never raw docket text
- `review_needed: bool` derived from a documented warning→severity map
- parser output envelope per source document: source file hash, parser
  version (2), extraction artifact reference, parsed record, warnings,
  review_needed, parse status, created timestamp — no numeric confidence
  anywhere
- envelope integrates with 16.2/16.3 artifacts; tests cover derivation
  logic, envelope shape, and the no-text-in-warnings rule

## Task 18.2 — Hardening: Charges, Dispositions, Judges

Each change lands with a before/after golden delta on affected fixtures and
an equivalence-diff rerun proving unaffected output is unchanged.

Acceptance criteria:

- **junk judge guard:** judge-line capture rejects lines matching sentence-
  component patterns (Confinement/Probation/Min of/etc.); rejection emits
  `SUSPECT_JUDGE_LINE`; the Capstone artifact case (sentence fragment as
  judge name) is reproduced as a fixture and now guarded
- **disposition truncation fixed:** "Transferred to Another Jurisdiction"
  captured in full; delta documented so Sprint 5's disposition map drops the
  truncated-form workaround
- **amended/replaced signal:** conservative pattern flagging emits
  `SUSPECTED_AMENDED_CHARGE` + review_needed; charges are never merged or
  collapsed; false-negative bias is acceptable and documented
- tests per change; golden deltas committed for tier-1 fixtures; worklog
  entry names each delta

## Task 18.3 — Hardening: Dates, Sentencing, Privacy

Same delta discipline as 18.2.

Acceptance criteria:

- **held-case event dates:** non-terminal events capture the event-header
  date into a new `event_date` field with the event name;
  `disposition_date` stays null for held charges (no disposition happened);
  `NON_TERMINAL_CASE` warning set; cross-court docket capture stays raw —
  structured CP↔MC linkage explicitly deferred to Sprint 5 attribution
- **`min_assumed` annotation:** sentence components record
  `min_assumed: true` when min_days was filled from max or a flat value;
  parsed values unchanged (CP-validated behavior preserved)
- **third-party name guard:** sentinel machinery extended with pattern-based
  guards for known label contexts where feasible; what is and is not covered
  is documented precisely for the POC report — no overclaiming
- tests per change; golden deltas committed; worklog entry per delta

---

# Phase 19 — Fixtures + Regression

## Task 19.1 — Tier-1 Synthetic Fixture Corpus + Index

Acceptance criteria:

- committed synthetic **text** fixtures (not PDFs) under the pipeline test
  tree; fictional names, zero-sequence placeholder docket numbers only
- scenario matrix covered, with CP and MC variants wherever layout differs:
  single charge; multiple charges; dismissed; withdrawn; guilty plea; guilty
  verdict; acquittal; ARD/diversion; probation; incarceration;
  fine/costs/restitution; multiple sentence components; missing sentencing;
  multiple judges; junk judge line; held/non-terminal (MC) with cross-court
  reference; blank assigned judge (MC); amended/replaced pattern;
  unparseable duration ("Life"); min-assumed case; legacy/thin docket;
  low-text document
- the two unverified MC renderings (decided trial verdict; AMP diversion)
  included as synthetic fixtures marked `layout_unverified: true` in the
  index — invented layout is never presented as confirmed CPCMS output
- committed `fixture-index.yaml` (tier 1 only): filename, court type,
  scenario, expected charge count, expected warnings, layout_unverified,
  synthetic: true; the real-corpus index, if created, lives with the corpus
  outside the repo
- golden JSON outputs committed beside fixtures (synthetic → safe to commit)
- hygiene test enforces placeholder-only docket numbers across all committed
  fixtures and goldens (standing decision 5)

## Task 19.2 — Golden Tooling + `run-fixtures` + CI Wiring

Acceptance criteria:

- `run-fixtures` CLI: tier 1 (repo fixtures) always; tier 2 via an explicit
  `--corpus-dir` pointing under `~/court-data/` — local only
- golden comparison with readable field-level diffs; intentional golden
  updates require an explicit `--update-goldens` flag and a worklog note
- tier-2 run generates/refreshes real-corpus goldens under
  `~/court-data/goldens/` and reports pass/fail per docket; console output
  is counts/statuses/docket-ids only — never extracted text
- CI runs pytest + the full tier-1 regression; fail-loud per the 10.1
  precedent; CI never references `~/court-data/`
- attempting a tier-2 run in a CI environment errors loudly rather than
  silently skipping

---

# Phase 20 — POC Report + Sprint Close

## Task 20.1 — Parser POC Report + Limitations

File: `docs/parser-proof-of-concept.md`

Acceptance criteria:

- report covers: extraction approach (referencing ADR 0001 — no re-selection
  narrative), port summary, extraction-seam findings (17.1), baseline
  equivalence results with CP and MC reported separately (17.3), hardening
  changes with their golden deltas, warning framework summary, supported and
  unsupported docket patterns, major ambiguity cases, OCR need assessment,
  fixture-corpus coverage and gaps
- **per-court readiness:** an explicit CP verdict and an explicit MC verdict
  on whether Sprint 5 can proceed, with the MC evidence base (40-record
  baseline + synthetic coverage + any corpus supplementation) stated plainly
- limitations documented honestly: third-party name guard residual coverage,
  layout_unverified fixtures, MC thin baseline, legacy-docket variability,
  date-extraction limits, whether more fixtures are needed before real
  ingestion
- no overclaiming anywhere; copy review gate applies (this is an internal
  doc, but the honesty bar is the same)

## Task 20.2 — Human Step: Exit Demo + Sprint Close

Chops runs the exit demo and reviews in the planning chat:

1. Manual import over the fixture corpus: hash dedupe demonstrated
   (re-import → duplicates skipped)
2. Extraction artifact for one docket; synthetic low-text case flagged
   `needs_ocr_or_review`
3. 17.1 extraction-seam report summary
4. 17.3 baseline equivalence report: CP and MC verdicts
5. Parser output JSON: one CP multi-charge docket; one MC held-for-court
   docket (null disposition_date + captured event_date + cross-court raw)
6. Warning + review_needed example (junk judge line fixture)
7. One hardening before/after golden delta walked through
8. Tier-1 regression green in CI; tier-2 local run report
9. POC report walkthrough — per-court readiness verdicts
10. Full CI green

Sprint 4 closes here; Sprint 5 (Normalization and Attribution) planning
begins.

---

## Sprint 4 Definition of Done

1. helpers + identity ported; salt required, no default; config.py severed.
2. Production pdfplumber extraction works, pinned, with low-text detection
   and artifacts written outside the repo.
3. Manual import with content-hash dedupe and metadata works.
4. Extraction-seam equivalence checked and triaged (17.1).
5. Parser ported faithfully; Capstone tests pass; MC support intact.
6. Baseline equivalence gate passed: CP and MC subsets reported separately,
   all divergences explained and accepted.
7. Warning codes + review_needed + output envelope exist; no numeric
   confidence anywhere.
8. All six locked hardening items landed, each with before/after golden
   deltas and isolation proven by equivalence rerun.
9. Tier-1 synthetic corpus committed with per-court variants,
   layout_unverified marking, index, goldens, and the hygiene test.
10. `run-fixtures` works for both tiers; golden updates are explicit; CI
    runs tier 1 fail-loud and never touches `~/court-data/`.
11. POC report exists with honest limitations and separate CP/MC readiness
    verdicts.
12. No raw docket text in logs, console output, or the repo; no PDFs,
    extracted text, or real-corpus goldens committed; collector untouched.
13. Exit demo reviewed; sprint closed in the planning chat.

---

## Sprint 4 Risks (with mitigations locked)

1. **Extraction drift breaks token heuristics** → 17.1 proves the seam
   before parser work; pdfplumber pinned; pin-to-Capstone-version is the
   fallback lever.
2. **MC support is under-validated** → per-court equivalence reporting,
   per-court synthetic variants, per-court POC verdicts, recommended manual
   MC supplementation. The report is allowed to say "CP ready, MC needs
   more evidence" — that's a finding, not a failure.
3. **Hardening silently changes unrelated output** → port-then-harden order,
   per-change golden deltas, equivalence rerun after each hardening task.
4. **Real docket content leaks into repo/logs** → outside-repo artifact
   roots, ported no-text conventions, sentinel assertions pre-write, the
   committed-fixture hygiene test, and the extended third-party guard.
5. **Salt misconfiguration produces insecure hashes** → required parameter,
   hard fail, no default (kills Capstone's silent fallback).
6. **Baseline regeneration friction stalls 17.3** → it's a named human
   prerequisite with exact commands shipped in the task spec; 16.x and 17.1
   proceed without it.
7. **Synthetic fixtures mistaken for verified layouts** →
   `layout_unverified: true` marking is an index-schema field and a POC
   report disclosure, not a footnote.

## Handoff to Sprint 5

Sprint 5 (Normalization and Attribution) begins when the exit demo passes and
provides: the ported+hardened parser, per-court equivalence evidence, the
warning/review framework, both fixture tiers with goldens, captured
disposition/sentence/event dates, raw cross-court linkage data, and the POC
report's per-court readiness verdicts. Sprint 5 opens with the disposition-
map workaround cleanup (18.2 truncation fix), taxonomy mapping, charge/judge
normalization, charge-level attribution, and the structured CP↔MC held-case
linkage deferred from 18.3.