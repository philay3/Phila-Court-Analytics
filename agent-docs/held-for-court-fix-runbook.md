# "Held for Court" Fix Runbook (Task 29.3, Stage 2)

_Status: single-use operational runbook for the 29.3 rebuild → intake →
republish → closure sequence. Mechanism A (the `HELD_FOR_COURT_DISPOSITIONS`
carve-out in `outcome_mapper.py`) is code-complete before step B1 runs._

Operational split (spec): **Chops personally runs every pipeline invocation and
every write-capable command against the live DB.** Agent steps are read-only
verification (SELECT-only, dbname `pca`) and are marked as such. Every
acceptance-relevant summary line is copy-pasted **verbatim** into the
checkpoint reports (never retyped — COL-4a transcription incident).

Environment for DB-touching steps, sourced at the shell boundary and never
echoed:

```
set -a; . <repo-root>/.env; set +a
```

pnpm gotcha: no trailing shell comments on forwarded commands.

Expected-delta guard (AC 4): the pinned numbers below hold ONLY against the
recon-time corpus — **7,758 loaded dockets, baseline fact run
`7e26b002-cb66-4712-bae2-361c7bc1466c`**. If step B0 shows a different loaded
count, STOP and restate expectations from a fresh count before rebuilding.

---

## Phase B — rebuild 1 (current corpus, delta proof)

**B0 (agent, read-only) — corpus guard:**

```sql
SELECT count(*) FROM parsed.dockets;  -- must be 7758, else STOP
```

**B1 (Chops) — rebuild 1:**

```
pipeline build-facts
```

Run report verbatim. Expect both skip counters printed and
`reconcile facts_written+undisposed_skipped+held_for_court_skipped==charges_processed: True`.
On the recon corpus: `held_for_court_skipped=7622`.

**B2 (agent, read-only) — keyed content comparison vs the baseline run.**
Fact IDs are per-run; the comparison keys on `parsed_charge_id`
(`parsed_sentence_id` for sentences). `<NEW>` = the B1 run id.

```sql
WITH old_f AS (SELECT * FROM fact.charge_outcomes
               WHERE build_run_id = '7e26b002-cb66-4712-bae2-361c7bc1466c'),
     new_f AS (SELECT * FROM fact.charge_outcomes WHERE build_run_id = '<NEW>')
SELECT
  count(*) FILTER (WHERE n.parsed_charge_id IS NULL) AS only_in_old,
  count(*) FILTER (WHERE o.parsed_charge_id IS NULL) AS only_in_new,
  count(*) FILTER (WHERE o.parsed_charge_id IS NOT NULL
                     AND n.parsed_charge_id IS NOT NULL
                     AND (o.normalized_charge_id    IS DISTINCT FROM n.normalized_charge_id
                       OR o.outcome_category_code   IS DISTINCT FROM n.outcome_category_code
                       OR o.disposition_date        IS DISTINCT FROM n.disposition_date
                       OR o.normalized_judge_id     IS DISTINCT FROM n.normalized_judge_id
                       OR o.judge_attribution_method IS DISTINCT FROM n.judge_attribution_method
                       OR o.attribution_method      IS DISTINCT FROM n.attribution_method
                       OR o.charge_match_method     IS DISTINCT FROM n.charge_match_method
                       OR o.outcome_match_method    IS DISTINCT FROM n.outcome_match_method
                       OR o.mvp_eligible            IS DISTINCT FROM n.mvp_eligible
                       OR o.public_eligible         IS DISTINCT FROM n.public_eligible
                       OR o.judge_specific_eligible IS DISTINCT FROM n.judge_specific_eligible
                       OR o.ineligibility_reason_codes IS DISTINCT FROM n.ineligibility_reason_codes
                       OR o.review_needed           IS DISTINCT FROM n.review_needed
                       OR o.taxonomy_version        IS DISTINCT FROM n.taxonomy_version))
    AS content_diff
FROM old_f o FULL OUTER JOIN new_f n ON o.parsed_charge_id = n.parsed_charge_id;
```

Attribution of `only_in_old` (must be exactly the five held forms):

```sql
SELECT c.disposition_raw, count(*)
FROM fact.charge_outcomes f JOIN parsed.charges c ON f.parsed_charge_id = c.id
WHERE f.build_run_id = '7e26b002-cb66-4712-bae2-361c7bc1466c'
  AND NOT EXISTS (SELECT 1 FROM fact.charge_outcomes n
                  WHERE n.build_run_id = '<NEW>'
                    AND n.parsed_charge_id = f.parsed_charge_id)
GROUP BY c.disposition_raw ORDER BY count(*) DESC;
```

Category retention in the new run:

```sql
SELECT outcome_category_code, count(*) FROM fact.charge_outcomes
WHERE build_run_id = '<NEW>' AND outcome_category_code IN ('other','unknown')
GROUP BY outcome_category_code;
```

Sentence facts (all three classes must be 0):

```sql
WITH old_s AS (SELECT * FROM fact.charge_sentences
               WHERE build_run_id = '7e26b002-cb66-4712-bae2-361c7bc1466c'),
     new_s AS (SELECT * FROM fact.charge_sentences WHERE build_run_id = '<NEW>')
SELECT
  count(*) FILTER (WHERE n.parsed_sentence_id IS NULL) AS only_in_old,
  count(*) FILTER (WHERE o.parsed_sentence_id IS NULL) AS only_in_new,
  count(*) FILTER (WHERE o.parsed_sentence_id IS NOT NULL
                     AND n.parsed_sentence_id IS NOT NULL
                     AND (o.sentencing_category_code IS DISTINCT FROM n.sentencing_category_code
                       OR o.sentence_date            IS DISTINCT FROM n.sentence_date
                       OR o.min_days                 IS DISTINCT FROM n.min_days
                       OR o.max_days                 IS DISTINCT FROM n.max_days
                       OR o.min_assumed              IS DISTINCT FROM n.min_assumed
                       OR o.amount_cents             IS DISTINCT FROM n.amount_cents
                       OR o.mvp_eligible             IS DISTINCT FROM n.mvp_eligible
                       OR o.public_eligible          IS DISTINCT FROM n.public_eligible
                       OR o.judge_specific_eligible  IS DISTINCT FROM n.judge_specific_eligible))
    AS content_diff
FROM old_s o FULL OUTER JOIN new_s n ON o.parsed_sentence_id = n.parsed_sentence_id;
```

**Pinned expectations (recon corpus only, AC 5):** outcomes `only_in_old` =
7,622 (Held for Court 6,618 / IGJ 522 / HP 478 / IC 2 / GJ 2), `only_in_new` =
0, `content_diff` = 0; `other` retains 155, `unknown` retains 188; sentence
diff all-zero; run-report review block shows `newly_inserted_total=0` with
generation deltas of exactly `unmapped_disposition` −1,004 and
`unmapped_charge` −1,002 vs the baseline run's report (F3: any other
review-type generation delta is unattributable → STOP). Anything
unattributable is stop-and-report (standing decision 4).

**→ CHECKPOINT C1: report B0–B2 verbatim to planning chat. Do not start
intake until cleared.**

## Phase C — intake backlog (per the committed COL Intake Protocol)

Each step cites the protocol section it implements
(`agent-docs/intake/col-intake-protocol.md`).

**C1 (Chops) — freeze (protocol "[0] Freeze", mtime-quiesced):** confirm the
staged set is quiescent (no file mtime newer than the quiesce window), then
copy the staged `*.pdf` set to `~/court-data/intake-snapshots/29.3-<UTC>/` and
write `MANIFEST.json` beside it (per-file sha256 + staged/excluded/included
counts). Apply the "[0b] Dedupe" already-loaded docket-number exclusion.

**C2 (Chops) — import (protocol "import-manual"; 16.3):**

```
pipeline import-manual ~/court-data/intake-snapshots/29.3-<UTC>/
```

**C3 (Chops) — extract (protocol "extract-text"; 16.2):**

```
pipeline extract-text ~/court-data/intake-snapshots/29.3-<UTC>/ --output-dir ~/court-data/extracted-intake-<date>/
```

**C4 (Chops) — parse (protocol "parse"; 18.1):**

```
pipeline parse --artifacts-dir ~/court-data/extracted-intake-<date>/ --output-dir ~/court-data/envelopes-intake-<date>/
```

**C5 (Chops) — tier-2 goldens (protocol "run-fixtures --init-goldens"; 19.2 —
a committed protocol step, F4-confirmed):**

```
pipeline run-fixtures --corpus-dir ~/court-data/intake-snapshots/29.3-<UTC>/ --init-goldens
```

Worklog note per golden-writing invocation (protocol requirement).

**C6 (Chops) — load (protocol "load"; 21.3):**

```
pipeline load --envelopes-dir ~/court-data/envelopes-intake-<date>/
```

Quarantine semantics per protocol ("Quarantine — isolated vs systematic");
systematic cluster = STOP.

**C7 (agent, read-only) — held-variant scan gate, BEFORE any aggregate work
(AC 6):**

```sql
SELECT disposition_raw, count(*) FROM parsed.charges
WHERE disposition_raw ILIKE '%held%'
  AND disposition_raw NOT IN
    ('Held for Court','IGJ - Held for Court','HP - Held for Court',
     'Held for Court IC','GJ - Held for Court','Held for Court - Hearsay')
GROUP BY disposition_raw;
```

(The six-form list mirrors `HELD_FOR_COURT_DISPOSITIONS`; "Held for Court -
Hearsay" joined at the C2 adjudication, 2026-07-14.)

Zero rows → proceed. Any row → **CHECKPOINT C2 reports forms + counts and
STOPs** for planning-chat adjudication (add-to-frozenset + re-rebuild vs
proceed with unknown/non-public) — never self-adjudicated. New NON-held
unmapped forms are expected intake growth: counts only, touch nothing
(decision 5).

**→ CHECKPOINT C2: report the scan-gate result either way.** (Fired on the
29.3 intake: "Held for Court - Hearsay" ×2; adjudicated Option 1 — sixth
frozenset entry, Phase-A addendum, expectations restated below.)

## Phase D — rebuild 2 + republish

**D1 (Chops) — rebuild 2 (protocol "Fact rebuild + reconciliation"):**

```
pipeline build-facts
```

All reconciliation gates; run report verbatim. Pinned expectations (C2
adjudication, against the post-intake corpus of 9,932 dockets / 30,285
charges; verify fresh counts first — drift = STOP and restate, AC-4 guard
pattern): `undisposed_skipped=6538`, `held_for_court_skipped=10955` (10,953
five-form + 2 hearsay), `facts_written=12792` (30,285 − 6,538 − 10,955),
reconcile line `True`.

**D2 (agent, read-only) — structural-exclusion proof (AC 7):**

```sql
SELECT count(*) FROM fact.charge_outcomes f
JOIN parsed.charges c ON f.parsed_charge_id = c.id
WHERE f.build_run_id = '<REBUILD2>' AND c.disposition_raw IN
  ('Held for Court','IGJ - Held for Court','HP - Held for Court',
   'Held for Court IC','GJ - Held for Court','Held for Court - Hearsay');
-- must be 0
```

**D3 (Chops) — generate → validate → publish (existing commands only; one
invocation, one run, one transaction; standing decision 5):**

```
pipeline generate-aggregates
pipeline validate-aggregates
pipeline publish-aggregates
```

Prior run `6ecf1fed-0b73-4cb8-bf50-2d8d213f1fa7` is invalidated in the same
transaction (StaleValidatedRunError guard intact) and becomes the rollback
target.

**D4 (agent, read-only) — post-publish verification (AC 8), verbatim:**
public endpoints serve the new run id; zero `other`/`unknown` rows in the
published aggregates; the demo anchor `simple-assault` serves only terminal
outcome categories (expected visible change: NONE — the honest structural
framing, AC 9); data-coverage metadata reflects the new run via existing
dynamic behavior (verified, not rebuilt; no hardcoded counts).

## Phase E — queue closure + close-out

**E1 (Chops) — key-scoped closure (AC 10; post-publish):**

```
pipeline close-held-review-items
pipeline close-held-review-items --confirm
pipeline close-held-review-items
```

Dry → confirm → dry-0 (idempotence), counts verbatim. Scope is structural:
open `unmapped_disposition` + `unmapped_charge` items whose dedup keys
reconstruct from current held-form charges via the mapper's
`HELD_FOR_COURT_DISPOSITIONS` (single authority; `missing_disposition_date`
is out of scope by item_type).

**E2 —** SD-14 formal count restatement (worklog + planning chat, AC 11) and
the AC-9 structural-exclusion restatement in the worklog.

**E3 —** phase close (AC 13): third commit on `phase-29` → push → PR → CI
green (deferred confirmation for 29.1 + 29.2) → rebase-and-merge or merge
commit (never squash) → delete branch → merge verification.

**→ CHECKPOINT C3: final completion report — all repo gates verbatim,
staging-completeness outputs, worklog restatements, closure counts.**
