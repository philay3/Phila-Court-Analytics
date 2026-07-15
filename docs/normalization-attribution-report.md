# Normalization and Attribution Report — Sprint 5

**Status:** committed summary of record for Sprint 5 (Task 25.1).
**Content class:** aggregate counts and rates only. No docket text, docket numbers,
defendant-identifying data, or per-item detail appears anywhere in this document.
**Honesty bar:** every figure traces to a named source run or a read-only query
scoped to the post-intake build. Nothing is restated from memory; pre-intake and
post-intake figures are never blended. No prediction, ranking, odds, or
legal-advice framing.

This report sizes the Sprint 6 review queue and the Sprint 7 eligible-fact volumes,
and its methodology section (§10) is written to be lifted into Sprint 7 public
methodology copy.

---

## Provenance key

Every figure below is tagged with one of:

- **[24.1]** — `~/court-data/reports/24.1-fact-build-run-aef44371.txt`, the
  pre-intake full-corpus fact build, `build_run_id aef44371`, 1,603-docket
  CP-anchored corpus. Used only as the pre-intake baseline for pre/post contrast.
- **[24.2]** — `~/court-data/reports/24.2-intake-run-d591902f.txt`, the post-intake
  fact build over the grown corpus, `build_run_id d591902f`.
- **[Q:d591902f]** — a read-only query run against the live post-intake fact
  partition (`build_run_id d591902f-8b2d-4ce7-bc09-58b5130e74e5`); raw output is
  pasted verbatim in the Task 25.1 completion report. Includes figures read from
  the run row's persisted `fact.fact_build_runs.counts` jsonb (the run's own
  recorded tabulation).
- **[24.3]** — Task 24.3 worklog entry (court_type verify-and-worklog).
- **[ledger]** — `~/court-data/coverage/window-ledger-philadelphia.jsonl`
  (collection coverage window).

**The report's spine is the post-intake corpus.** Where a figure exists only at the
CP baseline it is labelled [24.1] and presented as pre-intake context, never as the
current number.

---

## 1. Corpus position (post-intake)

The 1,603-docket invariant was superseded by name at COL intake [24.2]. The corpus
now stands at:

| Dimension          | Pre-intake [24.1]            | Post-intake [24.2]                               |
| ------------------ | ---------------------------- | ------------------------------------------------ |
| loaded dockets     | 1,603 (1,563 CP + 40 MC)     | **4,769 (1,563 CP + 3,206 MC)**                  |
| tier-2 goldens     | 1,604                        | 4,770                                            |
| import records     | 1,604                        | 4,770                                            |
| envelope artifacts | 1,603 (canonical, immutable) | 4,769 (1,603 canonical immutable + 3,166 intake) |
| `parsed.charges`   | 3,625                        | 13,334                                           |
| `parsed.sentences` | 4,162                        | 4,733                                            |

The CP side is unchanged in every dimension; **all growth is MC**. The Capstone
baseline is untouched (immutable port anchor); new dockets have no baseline entry
and the equivalence comparator was not run over them [24.2].

Fact counts for the post-intake build [24.2 / Q:d591902f]:

- charges processed: **13,334** (= facts written 11,175 + held-skipped 2,159)
- outcome facts written: **11,175** (one per disposed charge)
- held-charge exclusions: **2,159** (null disposition → no outcome fact)
- sentence facts written: **4,733** (one per component on a disposed charge)
- quarantine exclusions: **0** (all 3,166 intake dockets parsed clean; no
  `parse_failed`)

---

## 2. Normalization match rates per entity type (post-intake)

All distributions are over the post-intake build [Q:d591902f]. The CP baseline
[24.1] row is provided for pre/post contrast only.

### Charge (over 11,175 outcome facts)

| method    | count | share |
| --------- | ----- | ----- |
| alias     | 5,659 | 50.6% |
| exact     | 3,210 | 28.7% |
| statute   | 945   | 8.5%  |
| ambiguous | 6     | 0.1%  |
| unmatched | 1,355 | 12.1% |

Normalized (exact \| alias \| statute) = **9,814 (87.8%)**; not-normalized
(unmatched + ambiguous) = **1,361 (12.2%)**, which is the `charge_not_normalized`
ineligibility reason count. CP baseline [24.1], over 3,162: exact 927 / alias 1,805
/ statute 273 / ambiguous 1 / unmatched 156 (not-normalized 157).

### Outcome (over 11,175 outcome facts)

| method   | count  | share |
| -------- | ------ | ----- |
| exact    | 10,247 | 91.7% |
| unmapped | 928    | 8.3%  |

Unmapped dispositions map to outcome category `unknown` and are never
public-eligible. CP baseline [24.1]: exact 3,155 / unmapped 7.

### Judge attribution (over 11,175 outcome facts)

| method              | count |
| ------------------- | ----- |
| disposition_judge   | 3,468 |
| assigned_judge_rule | 154   |
| none                | 7,553 |

The large `none` count is dominated by pre-window and otherwise-ineligible facts;
within the public-eligible surface, judge attribution is near-complete (see §6).
Only 66 `none` facts fall on otherwise-eligible facts (the `judge_not_attributed`
reason, §4). CP baseline [24.1]: disposition_judge 2,936 / assigned_judge_rule 154
/ none 72.

### Sentencing component (over 4,733 sentence facts)

| method    | count | share |
| --------- | ----- | ----- |
| exact     | 4,718 | 99.7% |
| ambiguous | 15    | 0.3%  |

Sentence-fact judge attribution is inherited from the parent outcome fact
[Q:d591902f]: disposition_judge 4,622 / none 111. CP baseline [24.1]: exact 4,157 /
ambiguous 5.

---

## 3. Outcome and sentencing category distributions (post-intake)

### Outcome categories (over 11,175, [24.2 / Q:d591902f])

| category    | count |     | category       | count |
| ----------- | ----- | --- | -------------- | ----- |
| other       | 5,703 |     | ard            | 190   |
| guilty_plea | 2,599 |     | acquittal      | 29    |
| unknown     | 928   |     | withdrawn      | 393   |
| dismissed   | 742   |     | guilty_verdict | 591   |

`other` (5,703) and `unknown` (928) together = 6,631, dominated by MC "Held for
Court" bind-overs (§9 limitations). Both categories are **non-public** — none of
this reaches public data. CP baseline [24.1]: guilty_plea 2,315 / guilty_verdict
467 / dismissed 226 / ard 65 / other 61 / acquittal 17 / unknown 7 / withdrawn 4.

### Sentencing categories (base category stored; over 4,733, [Q:d591902f])

| category           | count |
| ------------------ | ----- |
| probation          | 2,393 |
| incarceration      | 1,601 |
| no_further_penalty | 496   |
| other              | 230   |
| costs_fees         | 13    |

`multi_category_components` = 34 (base stored; additive detections route to review,
never collapsed). CP baseline [24.1]: probation 2,059 / incarceration 1,550 /
no_further_penalty 440 / other 100 / costs_fees 13 / multi 33.

---

## 4. Eligibility funnel with reason-code analysis (post-intake)

Eligibility is decided by explicit boolean conditions and reason-code sets, never by
thresholds; no numeric confidence exists anywhere in the pipeline (Standing
Decision 2).

### Outcome facts [24.2 / Q:d591902f]

```
total disposed              11,175
 -> mvp_eligible             1,067   (disposition_date present AND >= 2025-01-01)
 -> public_eligible            730   (411 CP + 319 MC)
 -> judge_specific_eligible    664
review_needed (flagged)      7,695
```

Ineligibility reason tallies (codes co-occur, over 11,175):

| reason                             | count |
| ---------------------------------- | ----- |
| review_needed                      | 7,695 |
| disposition_date_missing           | 7,594 |
| disposition_date_before_mvp_window | 2,514 |
| charge_not_normalized              | 1,361 |
| disposition_not_mapped             | 928   |
| judge_not_attributed               | 66    |
| blocking_warning                   | 6     |

### Sentence facts [24.2 / Q:d591902f]

```
total                        4,733
 -> mvp_eligible             1,064   (sentence_date present AND >= 2025-01-01)
 -> public_eligible            733
 -> judge_specific_eligible    672
review_needed (flagged)        356
```

Ineligibility reason tallies (over 4,733):

| reason                              | count |
| ----------------------------------- | ----- |
| parent_outcome_ineligible           | 3,921 |
| sentence_date_before_mvp_window     | 3,669 |
| review_needed                       | 356   |
| sentence_duration_unparseable       | 315   |
| sentencing_component_not_normalized | 15    |
| money_amount_unparseable            | 7     |

The 2025-01-01 window is the dominant funnel cost on both surfaces (see §10). CP
baseline [24.1] — outcome: 3,162 → 437 → 411 → 411 (review 226); sentence: 4,162 →
493 → 432 → 432 (review 317). The pre-intake "432 public-eligible sentence facts"
figure from Task 23.3 is the [24.1] sentence `public_eligible`; the current figure
is **733**.

---

## 5. Review-item volume by type — Sprint 6 workload preview (post-intake)

The review queue is dedup-persistent (not run-scoped): a DB-enforced dedup key means
re-running the fact build adds zero duplicates and preserves triage status. Queue
total after intake: **10,369** items (all `open`) = 710 prior [24.1] preserved +
9,659 new [24.2 / Q:d591902f].

| item type                          | generated | newly inserted | prior (= [24.1] count) |
| ---------------------------------- | --------- | -------------- | ---------------------- |
| missing_disposition_date           | 7,594     | 7,383          | 211                    |
| unmapped_charge                    | 1,355     | 1,199          | 156                    |
| unmapped_disposition               | 928       | 921            | 7                      |
| duration_unparseable               | 315       | 35             | 280                    |
| unmapped_judge                     | 87        | 87             | new type               |
| sentinel_collision                 | 28        | 11             | 17                     |
| additive_sentencing_category       | 27        | 1              | 26                     |
| ambiguous_sentencing_component     | 15        | 10             | 5                      |
| money_unparseable                  | 7         | 0              | 7                      |
| unresolvable_cross_court_reference | 7         | 7              | new type               |
| ambiguous_charge                   | 6         | 5              | 1                      |

For every pre-existing type, `generated − newly_inserted` equals that type's [24.1]
count; the prior 710 survived untouched (dedup verified). New items were created
only for new dockets.

---

## 6. Judge attribution coverage (post-intake)

The judge-specific product surface's first real sizing — the fraction of
public-eligible outcome facts that carry a roster-matched judge [Q:d591902f]:

| court     | public-eligible | judge-attributable | coverage  |
| --------- | --------------- | ------------------ | --------- |
| CP        | 411             | 411                | 100.0%    |
| MC        | 319             | 253                | 79.3%     |
| **total** | **730**         | **664**            | **91.0%** |

Judge attribution is complete on CP and materially present on MC, with a ~21% MC
tail that is not yet roster-attributable. This is an honest thin-data preview for
Sprint 7 (Risk 2): the MC tail is a finding to size, not a failure — the CP surface
is fully attributable and charge-only eligibility is independent by construction. CP
baseline [24.1] was 411/411 = 100% (MC was ~0 public-eligible at 40 dockets).

---

## 7. CP↔MC linkage resolution (post-intake, informational)

Structured held-case linkage is informational this sprint — it does not change fact
eligibility (that is a Sprint 7 aggregation question) [24.2 / Q:d591902f]:

```
mc_source_dockets   2,023
links_total         2,017
resolved                4
unresolved          2,013
review (malformed)      7   (ambiguous 0)
```

The 2,013 unresolved links are MC bind-overs whose Common Pleas case is not yet
collected. This is the coverage story, not a defect: a case held in MC is disposed
in CP, so the unresolved tail is a direct future-collection signal and the reason CP
collection is the priority. It is the structural counterpart of the MC "Held for
Court" non-terminal dominance (§9). CP baseline [24.1]: 22 source / 22 links / 0
resolved / 22 unresolved.

---

## 8. Recovered-7 disposition

The 7 dockets recovered from quarantine = **2 clean + 5 flagged**
SENTINEL_COLLISION [worklog cross-check; 24.1/24.2 reconciliation gates]. The 5
flagged dockets carry 12 outcome facts on their disposed charges; across both the
pre-intake and post-intake builds their behavior is unchanged and conservative:
`judge_attribution_method = none` (×12) and `normalized_judge_id` NULL (×12), while
their disposition data survives into normalization. Judge attribution stays
conservatively empty rather than guessed — the durable fix behaving as designed.

---

## 9. Known limitations

Every figure here carries provenance, on the same bar as the headline numbers.

**Money-extraction coverage** [Q:d591902f, run `counts`]. Monetary components 37;
amount parsed (`amount_set`) 12; `money_unparseable` 7; `money_absent` 18. Money
coverage is unchanged from the CP baseline [24.1] because monetary components are
CP-dominant and intake was MC. The extractor is conservatively false-negative
biased; a monetary category asserted with no parseable amount still maps the
category and routes a `money_unparseable` review item — category mapping never
depends on amount parsing.

**Sentence-date behavior (amended Standing Decision 15)** [Q:d591902f + run
`counts`]. `sentence_date` is captured at two parser sites: a component-level
captured value, and — absent that — a fallback copy of the charge's
`disposition_date`. The two usually coincide but can diverge when a component
carries its own earlier date. Post-intake divergence: **34 of 4,733** sentence
facts, sentence_date **always earlier**, 29 straddling the 2025-01-01 MVP boundary,
delta 218–757 days. CP baseline [24.1] was 33. Eligibility keys off the **actual
sentence_date**, not the parent disposition_date. This report does not state
"sentence_date = disposition_date"; that framing is superseded.

**MC evidence base** [24.2]. MC grew 40 → 3,206 dockets; MC public-eligible outcome
facts ~0 → 319. The POC "correct but under-evidenced" MC verdict is updated to
**materially evidenced for the terminal slice, with a defined coverage tail** — with
two honest caveats:

- _(a) Non-terminal dominance._ Most MC disposed-charge volume is "Held for Court"
  bind-overs: 5,564 charges → outcome `other`, 844 "IGJ/HP - Held for Court"
  variants → `unknown`/review, plus 1,786 MC held (null-disposition) charges. Both
  `other` and `unknown` are non-public, so none leaks into public data. This is MC
  behaving as the lower court — the CP-coverage story, not an MC-outcome story.
  **Open question flagged for planning-chat adjudication (Sprint 6/7):** whether MC
  "Held for Court" should be modelled as non-terminal (no outcome fact, like held
  charges) rather than mapped to `other`. Today it is contained (non-public) and
  reconciles cleanly; it is a taxonomy/eligibility-semantics decision, not a defect.
- _(b) MC normalization-coverage tail._ `charge_not_normalized` rose 157 → 1,361 and
  `unmapped_disposition` 7 → 928 [24.2 / Q:d591902f]; the charge and disposition
  rosters were curated against the CP-dominant 1,603 corpus. New MC vocabulary routes
  to review (unmatched is a state, not a failure), never to public results. Closing
  this tail is roster/map curation work.

**Unmatched-roster tails (current, post-intake)** [Q:d591902f]. Charge
unmatched+ambiguous **1,361** (12.2% of outcome facts); disposition unmapped **928**
(8.3%); judge `unmapped_judge` review items **87**; sentencing component ambiguous
**15**. All route to review and to ineligible facts; none reaches public data.

**court_type** [24.3]. `parsed.dockets.court_type_recorded` is populated on 100% of
the corpus (Municipal Court 3,206 / Common Pleas 1,563; null 0) and 100% consistent
with the prefix-derived `court_type_derived` (consistent 4,769, mismatched 0). The
earlier "None corpus-wide" reading was a verification error, corrected in 24.3.
`court_type_derived` (docket-number prefix) is the authoritative court-type source by
decision. This is not a normalization surface.

---

## 10. Methodology implications (liftable to Sprint 7 public methodology)

_Written to the same honesty bar as the parser POC report; intended to be lifted,
with editing, into public-facing methodology copy._

**How attribution works — one path each.** Each disposition lives on its charge, and
each sentence component lives on its charge; there is no detached disposition or
sentence collection. Consequently there is exactly one attribution path per fact:
outcomes are attributed at the charge row; sentences are attributed at the charge
component. Sentence components carry no judge of their own, so a sentence fact
inherits its parent outcome fact's judge attribution.

**Judge attribution rules (conservative).** An outcome fact's judge is taken from the
disposition-judge value (normalized against a real roster) when it matches; otherwise
from the assigned-judge value only under a documented single-judge, roster-matched
rule; otherwise the fact is left unattributed. Name-shaped values that are not judges
(e.g. issuing authorities) resolve to unmatched and route to review — never guessed.
Unattributed judges never block charge-only facts; they only gate the
judge-specific surface.

**When facts are excluded.** A charge with no disposition (held for court) produces no
outcome fact at all. Quarantined/failed documents produce no facts. Beyond that,
eligibility is a set of explicit boolean gates with machine-readable reason codes: a
fact is public-eligible only when it is within the data window, its charge normalized
to a real roster entry, its outcome category is a public category, it carries no
blocking warning, and it is not flagged for review. There are no confidence scores;
"unmatched" is a recorded state that produces a review item and an ineligible fact.

**Why the sentencing sample differs from the outcome sample.** Not every disposed
charge carries sentence components, so sentence facts (4,733) are a distinct, smaller
population than outcome facts (11,175), counted separately. A charge with an outcome
but no sentence component is normal, not an error.

**How the 2025-01-01 rule applies.** An outcome fact is within the MVP window when its
disposition date is present and on or after 2025-01-01; a sentence fact when its
sentence date is present and on or after 2025-01-01. A missing date is ineligible with
a reason code, never a silent inclusion. This single rule is the dominant reason the
eligible sample is far smaller than the collected corpus (§4): the corpus is collected
by filing/docketing date, but eligibility is decided by disposition/sentence date, so
"collected" and "eligible" differ by disposition timing, not by error. MC collection
covers filing/docketing dates 2025-01-01 through 2025-04-29 [ledger]; a docket
collected in that window is eligible only once it reaches a qualifying disposition.

**What "sentence date" actually is.** The sentence date is usually the same as the
disposition date, but it is captured independently at the sentence-component level and
can predate the disposition date when a component records its own earlier date.
Eligibility uses the actual sentence date. A small divergent tail exists and is
disclosed (§9); the sentence date is not merely a copy of the disposition date.

---

## 11. Verdicts

### Sprint 6 readiness — READY

The review queue is real and triageable. It holds **10,369** typed, deduplicated,
status-carrying items across 11 item types [24.2 / Q:d591902f], with DB-enforced
dedup proven idempotent (a rebuild preserves the prior queue and its statuses and
adds items only for new dockets). Per-type counts give Sprint 6 a concrete workload
shape — the dominant classes are `missing_disposition_date` (7,594),
`unmapped_charge` (1,355), `unmapped_disposition` (928), and `duration_unparseable`
(315). This is exactly the input Sprint 6's admin review UI consumes.

### Sprint 7 readiness — READY, with thin-data expectations previewed

Public-eligible volumes are sufficient to aggregate at the charge level: **730**
public-eligible outcome facts (411 CP + 319 MC) and **733** public-eligible sentence
facts, of which **664 (91.0%)** are judge-attributable [24.2 / Q:d591902f]. Thin-data
expectations to carry into Sprint 7:

- **Judge-specific MC tail.** MC judge attribution is 79.3% vs CP's 100% — the
  judge-specific surface is thinner on MC and should be sized honestly per charge/
  judge cell, not presented as uniform.
- **The data window is the dominant cost.** The 2025-01-01 rule
  (`disposition_date_before_mvp_window` 2,514 + `disposition_date_missing` 7,594)
  removes most of the corpus from the eligible set; this is expected and is handled
  downstream, but it means eligible cells will be small.
- **MC terminal volume is thin because MC is the lower court.** MC's disposed-charge
  volume is dominated by non-terminal "Held for Court" bind-overs (non-public); the
  terminal MC slice is materially evidenced but modest. The "Held for Court"
  taxonomy-semantics question (§9a) is flagged for Sprint 6/7 adjudication.
- **Money-based views are optional.** Amount coverage is low (12 amounts parsed
  across 37 monetary components); whether amount-based views ship at all is a
  Sprint 7 decision, and category mapping never depends on amount parsing.

Both surfaces are ready to proceed; the thin spots above are sized here so Sprint 7
plans around them rather than discovering them.
