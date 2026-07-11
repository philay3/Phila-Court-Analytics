# Parser Proof-of-Concept Report (Sprint 4 Close)

- **Task:** 20.1
- **Date:** 2026-07-11
- **Scope:** Assessment of whether UJS docket PDFs (CP and MC) can reliably
  feed the product's charge-level analytics, with explicit per-court
  readiness verdicts for Sprint 5.
- **Status:** Internal engineering report. Documentation only — no parser,
  pipeline, test, fixture, or CI change accompanies it.

Every figure below is corpus-validated and recorded in `tasks/worklog.md`
(tasks 16.1–19.2) and the local, out-of-repo comparator artifacts. This
report contains no docket numbers, defendant-identifying data, raw docket
text, or hash values — only counts, statuses, section names, and field
names describing real-corpus findings.

---

## Executive summary

Phases 16–19 ported the Capstone parser faithfully, proved it equivalent to
the regenerated baseline, landed six hardening items as classified golden
deltas, stood up an eleven-code warning framework (the eleventh,
`UNKNOWN_NOT_FINAL_DISPOSITION`, added in 18.5 — see the event-grain correction
below), and built a two-tier fixture system with CI-enforced tier-1 regression
and local tier-2 real-corpus runs.

The parser is **correct on the evidence available**: 100% field equivalence
against the baseline, every post-hardening divergence attributable to exactly
one intended delta class, zero unclassified diffs, and zero silent privacy
leaks. The gating question for Sprint 5 is not parser correctness but
**evidence depth per court**:

- **CP — READY.** 1,556 baseline records, 100% field-equivalent, all deltas
  classified.
- **MC — CORRECT BUT UNDER-EVIDENCED.** 40 baseline records. The parser is
  equivalent on all 40, but 40 records is not proof of coverage. Sprint 5 MC
  analytics should not be certified on this base without supplementation.

Full verdicts with evidence in §12.

---

## 1. Extraction approach

Extraction is **pdfplumber, pinned `==0.11.10`**, using `page.extract_text()`
only (default arguments, pages joined in order). The library selection was
made in Sprint 1 and is not re-litigated here — see
[ADR 0001](decisions/0001-pdf-extractor.md) for the pymupdf/pdfplumber/pypdf
evaluation and the readability, licensing (MIT vs AGPL), and Capstone-
incumbency rationale.

`pymupdf` and `pypdf` remain dependencies of the **evaluation harness only**;
a static AST test forbids any production pipeline module (everything under
`src/pipeline` except `evaluation/`) from importing `pymupdf`, `pypdf`, or
`fitz`.

## 2. Port summary

The Capstone parser was ported behavior-preserving across three tasks:

- **Modules ported:** `helpers` and `identity` (16.1), then `docket_parser`
  (17.2) — the pure parsing surface (`parse_docket_text` plus pure helpers)
  in `pipeline.docket_parser` (stdlib only, no pdfplumber on its import path),
  and the PDF-opening wrapper `parse_docket` in `pipeline.docket_parser_pdf`.
- **`config.py` severed.** No import-time env reads, dotenv loads, directory
  creation, or filesystem touches; proven by a fresh-import side-effect test.
- **Salt required, no default.** `hash_defendant(name, birth_year, *, salt)`
  takes salt as a required keyword-only parameter; missing/empty salt raises
  `ValueError` naming `DEFENDANT_HASH_SALT`, with no name/birth-year/docket
  data in the message. Capstone's silent `"change-me-in-env"` fallback is
  gone.
- **`docket_number` is caller-supplied**, never derived from the PDF filename
  stem — filename provenance is the import stage's responsibility.
- **Quirks preserved through the port**, then addressed as separately named
  hardening changes in Phase 18 (§5). The port itself changed no parse
  behavior.

Current versions: **`ENVELOPE_PARSER_VERSION = 5`**, **record
`parser_version = 2`**. (The envelope version tracks the observability
wrapper / parse behavior — bumped to 5 in 18.4 for the single-line
event-header capture fix; the record version tracks record-schema changes —
bumped to 2 in 18.3 for the two conditional held-case fields and unchanged by
18.4, which corrected held-charge values without a schema change.)

## 3. Extraction-seam findings (17.1)

Before porting any parser logic, the production extraction stage (16.2) was
proven to reproduce Capstone's pdfplumber reference text line-for-line over
the full working corpus:

- **1,596 / 1,596 dockets equivalent** (1,556 CP + 40 MC); 0 divergent,
  0 failed, 0 missing-reference.
- pdfplumber **0.11.10 on both sides**; `version_mismatch: false`.
- **Zero divergences.**

Consequence: any divergence found downstream in 17.3 is attributable to
parser logic alone, not to the extraction seam.

## 4. Baseline equivalence (17.3)

The ported extraction + parser were run over the corpus and diffed
field-by-field against the regenerated Capstone baseline (excluding only
`parsed_at` and `parser_version`), with salt parity confirmed so
`defendant_hash` was compared, not excluded.

- **100% field equivalence.** Verdict: PASS.
- **CP: 1,556 / 1,556** equivalent.
- **MC: 40 / 40** equivalent.

**The MC pass is thin evidence, not proof.** Forty records exercise the MC
path but cannot establish MC layout coverage. This limitation propagates to
the MC readiness verdict (§12) and the fixture-gap discussion (§11).

## 5. Hardening changes with golden deltas

Six hardening items landed in Phase 18. After hardening, the equivalence
comparator's role inverted from "prove identical" to "prove the diff set is
exactly the intended delta set." Every divergence in the final rerun
classifies into exactly one class below; **zero unclassified diffs**. Class
letters (A/B/D/E) are the cumulative delta-ledger labels against the immutable
Capstone baseline.

### Junk judge guard (18.2, Class D)

Rejects judge-slot captures matching sentence-component patterns (confinement/
probation/IPP keywords, min/max-of slots, duration expressions, currency); no
name-shape or identity validation (that is Sprint 5). On rejection **only the
judge field is nulled** — same-line dates and control flow are untouched — so
each rejection is exactly one field delta.

- **Record delta: 3 sentence-fragment captures nulled**
  (`disposition_judge_raw` → null).
- **`SUSPECT_JUDGE_LINE` warnings: 5 occurrences across 4 dockets** = the 3
  guard nulls + 2 transient captures caught-and-overwritten on a single
  docket.

The warning count (5) and the diff count (3) legitimately differ because they
measure different things: **warnings count suspect parse-time events; diffs
count final-value changes.** A capture that is flagged and then overwritten by
a later valid capture on the same docket raises a warning but produces no
final-value delta.

### Disposition truncation repair (18.2 Item 2, repaired, Class E)

The first append-based design failed its corpus stop condition (~535 dockets
whose appended tails were charge-name re-prints and section furniture, not
disposition prose) and was reverted to the Capstone fall-through. The shipped
design is a **corpus-evidenced exact-match repair table** (single entry:
`"Transferred to Another"` → `"Transferred to Another Jurisdiction"`), applied
after the disposition loop, reading no continuation line — zero-false-positive
by construction.

- **Record delta: 16 exact-match repairs** of `disposition_raw`
  ("Transferred to Another" → full form), Class E.

This enables a named Sprint 5 cleanup: once the full form is captured
directly, Sprint 5 can drop the disposition-map truncated-form workaround.

### Amended/replaced signal (18.2 Item 3)

Warning-only scan of the already-parsed `disposition_raw` for amended/
downgraded/replaced-by/charge-changed language. Reads a parsed field, changes
no field, never merges or re-keys charges.

- **Zero record diffs. Zero corpus specimens.**
- Pattern basis is labeled **speculative-conservative** in the code — no cited
  CPCMS document and no corpus observation back it yet; it stays speculative
  until real hits arrive.

### Held-case event dates (18.3 Item 1 / corrected in 18.4, Class A)

Records `event_date` (event-header date) and `event_name` on charges — but
**only on charges that end the parse undisposed** (`disposition_raw`,
`disposition_date`, `disposition_judge_raw` all null). A charge listed under a
non-terminal event but later disposed under a terminal event has the transient
keys stripped by a placement sweep after the disposition loop; when a held
charge appears under multiple non-terminal events, the latest event-header
wins. **`disposition_date` stays null for held charges** and terminal output
is byte-identical to the baseline.

- **Record delta: 926 keys (event_date + event_name) across 104 dockets**
  (CP 91 / MC 13), from 463 true-held event-key charges; **all also carry
  `NON_TERMINAL_CASE`.** As of 18.4 these keys are **populated with correct
  values**; the 18.3 run had the keys present but their values wrong (see
  below).

**Placement rule and its acceptance authority:** the initial 18.3
implementation attached the event keys at each non-terminal appearance but did
not strip them when the same charge was later disposed — a placement defect
that **206 green unit tests did not catch**. The full-corpus rerun found 3,085
disposed charges wrongly carrying event keys, and the placement sweep was added
in response. The lesson is recorded here deliberately: **corpus verification,
not the unit suite, is the acceptance authority for this parser.**

**18.4 correction — single-line event header (a second, deeper defect of the
same field).** The 18.3 capture assumed a _two-line_ event header: an event-name
line, then an anchor line carrying the date at column 0
(`MM/DD/YYYY … Not Final`). Real CPCMS prints the header on **one line**:
`<EventName> <MM/DD/YYYY> <Not Final|Final Disposition>` — a corpus scan found
the date immediately left of the status token on **3,278/3,278** anchor lines
and at line start on **zero** of them. Consequence on the authoritative v4
corpus run: **`event_date` was null on 463/463 held charges and `event_name`
was mis-sourced** (offense fragments captured off the wrong line), not the
event labels. 18.4 replaces the capture with a single-line anchored read
(`event_date` = the date token immediately preceding the status token;
`event_name` = the leading text before it) and bumps `ENVELOPE_PARSER_VERSION`
4 → 5 (record `parser_version` stays 2 — same keys, corrected values). Two-line
handling is retired; no real specimen exists to support it.

**Why the key-presence diff hid it — the verification-gap lesson.** The
comparator classifies these as `key_missing_in_baseline` (Class A) because the
Capstone baseline has no such keys. That diff is **value-blind**: it fires on
the _presence_ of a key, so a corpus where 100% of held charges carry
`event_date`/`event_name` keys reconciles cleanly even when every one of those
values is null or wrong. Class-A key-presence counts were green through 18.3
precisely because they never inspected the values. **Going forward, any new
capture field requires a value gate, not just a key-presence diff.** 18.4 adds
one: the equivalence/corpus tooling now asserts, fail-loud, that **100% of held
charges (the placement-sweep survivors — exactly the charges carrying event
keys) have a non-null, date-parseable `event_date` and a non-null `event_name`**,
and reports the distinct `event_name` vocabulary size (**10** case-normalized
held-survivor values corpus-wide as of the 18.5 rerun; the 18.4 "~26" was an
over-estimate the run corrected) as an informational line. This defect was
surfaced by the 20.2 exit demo and root-caused to the two-line assumption; it is
recorded here, not smoothed over (Check-2 precedent).

### 18.5 correction — ARD routing decoupled from `event_name` (event grain)

The 18.4 single-line fix was correct but surfaced a **third, deeper layer of the
same defect** that reframes the whole 18.3/18.4 narrative above. Two discoveries:

1. **The two-line lookahead had been capturing the CASE-STATUS ROW, not the
   event name.** Real CPCMS prints a case-status row _above_ the event header
   (e.g. `ARD - County Open`, `Proceed to Court (ARD Revoked)`). The 18.3/pre-18.4
   parser's previous-line lookahead captured _that_ row as the "event_name". Its
   `ard` substring is what — accidentally — routed ARD dispositions: an
   `in_valid_event` special case (`"ard" in event_name`) fired on the status row.
   So "18.3 mis-sourced event_name" (above) was more precisely "captured the
   status row," and that mis-capture was load-bearing for ARD routing.
2. **Capstone's routing was EVENT-grained.** When the status-row `ard` fired,
   EVERY charge line under that event disposed — each with its own charge-line
   token as `disposition_raw`, not just the ARD line. The token was the _trigger_
   for an event-level decision, never a per-line routing key.

**The regression 18.4 introduced.** Correcting `event_name` off the status row to
the true single-line label (`Status`, `Violation of Probation` — no `ard`
substring) severed the accidental routing. On the v5 corpus run this un-disposed
**68 charges across 19 dockets** (66 ARD-class = 65 `ARD - County` + 1 corpus
strip-fragment `RD - County`, plus 2 `Withdrawn` companions), inflating the
held-survivor set 463 → 531 and producing a Pattern-B specimen (an un-routed ARD
event losing judge/sentence-date/sentence while a later Final event still
supplied `disposition_raw`) and two shifted-sentence dockets.

**The 18.5 fix — event grain, decoupled from `event_name` and the status row.**
A Not-Final event routes **iff its FIRST charge line's disposition token is in
`ARD_CLASS_DISPOSITIONS`** (`{ARD - County, RD - County}`, corpus-evidenced, 18.2
exact-match discipline); a routed event disposes **all** its charge lines, each
with its own token; Final Disposition events route as always; latest-valid-event
-wins is unchanged. `NON_TERMINAL_DISPOSITIONS` pins the 36 other scanned tokens
verbatim so a new eleventh warning, **`UNKNOWN_NOT_FINAL_DISPOSITION`** (review),
fires only on genuinely novel first-line vocabulary (or an ARD token stranded on
a non-first line of an unrouted event). The comparator gains a permanent,
always-fail **UN-DISPOSAL** check (a charge disposed in the baseline but
undisposed by the corpus parse — its own report category, never folded into
generic divergences). `ENVELOPE_PARSER_VERSION` stays 5 (same behaviour-change
lineage, never shipped); record `parser_version` stays 2.

**Corpus rerun (v5-with-event-grain vs baseline).** `reconciled: True`,
`baseline_missing 7`, `held_value_gate PASS 463/463` (100% populated),
`un_disposal PASS 0/0`. The 1,204 divergences decompose with **zero
unclassified**: Class A 926 keys / 463 charges / 104 dockets (CP 91 / MC 13),
Class B 1,842 `min_assumed` / 1,095 dockets (the pinned v4 figure — restoring the
ARD sentences restores their annotation), Class C 0, Class D 3 junk-judge nulls,
Class E 16 Transferred repairs (one docket carries B+D; all others single-class).
The 19 ARD dockets, the Pattern-B docket, and the 2 shifted-sentence dockets each
reproduce their baseline record with zero routing divergence (Class-B
`min_assumed` only). Held-survivor `event_name` vocabulary settled 11 → 10 as the
now-ARD-routed `Violation of Probation` events left the held set. The mechanism
choice (event grain over charge-line grain) is corpus-forced: charge-line grain
would strand the 2 `Withdrawn` companions (held 465, UN-DISPOSAL 2); event grain
lands held exactly at the pinned 463. A new tier-1 fixture, `ard_progression_cp`,
encodes the shape end-to-end.

### `min_assumed` annotation (18.3 Item 2, Class B)

A sentence records `min_assumed: true` exactly when `min_days` was filled from
the maximum or from a flat value; the key is absent (not `false`) otherwise.
Pure annotation — **parsed duration values are byte-identical** to pre-task
output, no warning, no `review_needed` impact.

- **Record delta: 1,842 annotations across 1,095 dockets**, all value `true`.

### Whole-token sentinel matching + `SENTINEL_COLLISION` (18.3)

Covered in the privacy section (§7).

## 6. Warning framework

The observability layer (18.1, extended in 18.3) wraps the unchanged parsed
record in a per-document envelope carrying warnings and a derived
`review_needed` boolean. It is observation-only: emission never mutates the
record.

- **Eleven stable codes**, a closed vocabulary with a single constructor (the
  eleventh, `UNKNOWN_NOT_FINAL_DISPOSITION`, review severity, added in 18.5).
- **Structural context only** — a warning carries at most `section`,
  `charge_sequence`, `page`, and `field`. A text-carrying warning is
  unrepresentable by construction; raw docket text can never enter a warning.
- **`review_needed` is derived** from a documented severity map (any code of
  `review` severity → true), not set ad hoc.
- **No numeric confidence anywhere.** A confidence score was rejected as false
  precision. If graded confidence is ever needed, it derives in Sprint 5 from
  warning composition, not from a fabricated number in the parser.

## 7. Privacy classification

- **Fail-closed on real data.** The sentinel machinery (`assert_no_leak` plus
  the pattern guards) was validated against the real corpus with **zero silent
  leaks**. A sentinel reaching a record value is a hard stop, not a warning.

- **Quarantine = 1 docket.** A single unsupported-format specimen crashes with
  a `KeyError` (its disposition section references a charge sequence never
  captured). It stays quarantined and its docket id lives only in local,
  out-of-repo artifacts — this report references it descriptively and never by
  docket number or hash.

- **The 7 historically sentinel-blocked dockets are RECOVERED post-18.3.**
  After whole-token matching replaced substring matching:
  - **2 parse clean** — they were fragment-substring false positives.
  - **5 parse flagged** — judge fields nulled, `SENTINEL_COLLISION` emitted,
    `review_needed = true` — pending Sprint 5 judge normalization.

- **Historical sentinel data cost ≈ 0.44%** (7 of 1,603), with the
  precision-improvement path identified and shipped (whole-token matching).

- **Surrendered leak class, documented.** Whole-token matching no longer
  blocks a sentinel that appears only as a proper sub-span inside a larger
  alphanumeric token. Accepted rationale: a fragment embedded in a larger
  token is not a retrievable identifier. **Full names and DOB strings remain
  matched** (internal punctuation escaped, outer edges anchored). The benign
  class removed is exactly the 2 false positives above.

- **Third-party name guard ships as a documented limitation.** The guard
  covers the two known judge-label contexts only — the `CASE INFORMATION`
  assigned-judge slot and the `DISPOSITION` disposition-judge slot — nulling a
  name-shaped capture that whole-token-collides with a sentinel and emitting
  `SENTINEL_COLLISION`. **Not covered:** attorney/participant free-text
  contexts, and any detection beyond pattern matching — there is **no
  NER-grade name detection**. Those contexts rely on the fail-closed
  `assert_no_leak` backstop and upstream capture bounds. This is a
  pattern-based extension only, stated without overclaim; Chops signed off on
  shipping it as a documented limitation.

## 8. Supported and unsupported docket patterns

- **Supported:** the scenarios enumerated in the tier-1 matrix (§11) —
  single- and multiple-charge CP and MC dockets, held/cross-court and
  related-cases MC dockets, blank-judge, multi-non-terminal, and the
  missing-date variants.
- **Unsupported:** the `KeyError` format class — a disposition section that
  references a charge sequence never captured (§7 quarantine). This is the one
  known unsupported pattern.
- **Court-type field:** `record.court_type` is **None corpus-wide** — a
  faithful-port inert field (the Capstone baseline is identical). The
  **docket-number prefix (`CP`/`MC`) is the authoritative court-type source.**
  Sprint 5 decides whether to populate the record field from the prefix or
  drop it.

## 9. Major ambiguity cases

- **Judge-slot values with zero judge validation.** The parser accepts any
  name-shaped span in a judge slot; the 18.2 guard removes obvious
  sentence-fragment non-judges, but genuine name-shaped non-judge captures
  survive. The durable fix is **Sprint 5 judge normalization/validation**
  ("is this value actually a judge"), not another parser heuristic. The
  hardening guards remove the leak, not the ambiguity.

- **Restitution finding (19.1).** Restitution is **not a distinct parsed
  sentence component** — the ported parser recognizes only six sentence-type
  prefixes, and restitution is not one of them. It survives only inside the
  `raw_text` of Fines-and-Costs lines. This is a faithful limitation, not a
  parser defect, and is named here as a **Sprint 5 taxonomy-mapping input**.

- **Duration convention.** A year is **360 days** (day = 1, month = 30,
  year = 360), CP-validated, with no 365-day doc drift. `raw_text` is always
  retained, so no source information is lost even when a duration is
  normalized. **Display units are a Sprint 7 question**, not a parser one.

## 10. OCR assessment

There are **no scanned dockets** in the 1,596-docket corpus — all are
text-native. The extraction stage's low-text detection flags such a page
`needs_ocr_or_review` (default threshold 100 stripped chars/page), but that
path has been exercised only by synthetic tests. **OCR is unimplemented.** The
decision is revisited if and when a scanned docket appears (consistent with
ADR 0001's known limitation).

## 11. Fixture-corpus coverage and gaps

**Tier-1 (committed, CI-enforced):** 34 synthetic TEXT fixtures over the full
scenario matrix, with CP+MC pairs where layout differs and MC-only fixtures
where the section set differs. Each has a parser-generated golden and an index
entry; a hygiene test scans the entire tier-1 tree and fails on any
docket-shaped token that is not the `000000\d` placeholder. The tier-1
regression runs in CI under the existing pytest job. 18.5 added
`ard_progression_cp` — the event-grain progression + companion-withdrawal shape
(ARD `Status` event routes on its first-line `ARD - County` token with judge +
sentence, a companion seq2 `Withdrawn` disposes under the same routed event, a
wrapped `Proceed to Court (ARD` / `Revoked)` revoke event stays held, and a
terminal Final event carrying no judge/sentence overwrites `disposition_raw`
only) — and all 33 prior goldens stayed byte-identical under event grain. 18.4
corrected the event-header layout of the held (`held_cross_court_mc`) and ARD
(`ard_diversion_cp`) fixtures to the corpus-canonical single-line form (both
goldens reproduced byte-for-byte) and added `held_multiword_event_cp` — a held
fixture whose multi-word event name places the date token at index 4, guarding
against a position-baked capture.

- **Disclosed gap — two `layout_unverified` MC fixtures:** the decided-trial-
  verdict and AMP-diversion renderings are **invented layouts, never confirmed
  against real CPCMS output.** They are marked `layout_unverified: true` in the
  index and should be validated against a real MC docket of each kind before
  being trusted as coverage.

- **Disclosed gap — broader fixture-layout audit needed (Sprint 5).** 18.4
  found _two_ committed fixtures encoding an invented two-line event header
  (`held_cross_court_mc`, then `ard_diversion_cp`) that does not exist in real
  CPCMS. The remaining terminal fixtures still encode the same two-line layout;
  they parse inertly under the single-line capture (terminal `event_name` is
  unused and the date is captured identically), so their goldens are unchanged
  and they were left untouched — but their `layout_unverified: false` markings
  are not yet evidence-backed against corpus-observed formats. A Sprint 5
  opening item verifies every tier-1 fixture's event-header (and other section)
  layouts against real formats and corrects the markings accordingly.

**Tier-2 (local, out-of-repo):** **1,603 fixtures = 1,596 baseline + 7
recovered sentinel dockets.** The 7 recovered dockets have no Capstone
baseline, so the comparator reports them as `STATUS_BASELINE_MISSING` — an
explicit, reconciled, informational entry (not a failure, not a silent skip).
At rerun the human confirms the `baseline_missing` count is exactly 7.

- **Disclosed gap — MC evidence base remains thin:** 40 baseline MC records.
  The named mitigation path is **manual import / collector supplementation** of
  additional real MC dockets before MC analytics are certified.

## 12. Per-court readiness verdicts

The verdicts follow the evidence, not the schedule.

### CP — READY for Sprint 5

Evidence base:

- Extraction seam: **1,556 / 1,556 equivalent**, zero divergences (§3).
- Baseline equivalence: **1,556 / 1,556, 100% field-equivalent** (§4).
- All post-hardening divergences classified into intended delta classes with
  **zero unclassified diffs** (§5).
- Held-case, min_assumed, and sentinel behaviors validated at CP scale
  (CP 91 held dockets; the bulk of the 1,842 min_assumed annotations). Held-case
  event **values** are correct as of the 18.4 single-line fix and are now
  enforced by a fail-loud corpus value gate, not key-presence alone (§5).

CP charge-level data can proceed into Sprint 5 normalization/taxonomy work.
The open items are Sprint 5 work by design (judge validation, disposition-map
cleanup, court_type populate-vs-drop, restitution taxonomy mapping), not CP
parser gaps.

### MC — CORRECT ON EVIDENCE, BUT UNDER-EVIDENCED

Evidence base:

- Extraction seam: **40 / 40 equivalent** (§3).
- Baseline equivalence: **40 / 40, 100% field-equivalent** (§4) — but **40
  records is thin evidence, not proof** of MC layout coverage.
- Two of the MC layout fixtures are `layout_unverified` — invented, not
  confirmed against real CPCMS output (§11).

The MC parser is **correct on every MC record available**, and nothing in the
evidence suggests an MC-specific defect. But the evidence base is too shallow
to certify MC coverage. **Recommendation:** Sprint 5 may build MC handling
against the current parser, but **MC analytics should not be certified for
release** until the MC evidence base is deepened — via manual/collector
supplementation of real MC dockets and confirmation of the two
`layout_unverified` fixtures against real output. "CP ready, MC needs more
evidence" is the honest reading of the corpus.

---

## Sprint 5 handoff items named in this report

These are named only (no Sprint 5 planning content is authored here):

1. Judge normalization/validation — the durable fix for judge-slot ambiguity
   and the residual third-party-name coverage gap (§7, §9).
2. Disposition-map truncated-form workaround cleanup, enabled by the Item 2
   repair (§5).
3. `court_type` populate-vs-drop decision, using the docket-number prefix
   (§8).
4. Restitution taxonomy mapping from Fines-and-Costs `raw_text` (§9).
5. MC evidence deepening — manual/collector supplementation and confirmation
   of the two `layout_unverified` fixtures (§11, §12).
6. Structured CP↔MC held-case linkage — deferred from 18.3; Sprint 4 captured
   raw cross-court held-case data only, with structured attribution the
   Sprint 5 landing task (§5).
7. Display-unit handling for durations — deferred to Sprint 7 (§9).
