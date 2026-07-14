# Refresh Cycle Runbook (COL-4b)

_Status: active (established Task COL-4b, Sprint 7). Governs every pending-docket refresh cycle._

A **refresh cycle** re-fetches the loaded corpus's non-terminal dockets so their later
dispositions enter the corpus, closing the frozen-pending bias (slow cases — trials — are
systematically under-counted vs fast pleas when pending dockets never get a second look). It is
the sanctioned path for re-collecting **already-loaded** dockets: changed sheets supersede at load
(COL-4a); unchanged sheets die as duplicates at import.

This runbook varies the [COL Intake Protocol](col-intake-protocol.md) in exactly one place: the
**[0b] docket-number exclusion does not apply to refresh targets**. That exclusion exists to stop
_incidental_ re-collection from double-loading a docket; a refresh cycle re-collects loaded
dockets **by design**, and loader supersession (COL-4a) now replaces the old parsed graph instead
of duplicating it. Everything else in the intake protocol — per-stage counting, quarantine
semantics, reconciliation gates, console hygiene — applies unchanged.

Nothing here contains docket-derived content. All per-run artifacts live outside the repo under
`~/court-data/`; only aggregate counts are restated in `tasks/worklog.md`.

---

## What a refresh cycle is NOT (honesty bar)

- It does **not** discover new dockets. Window coverage (search mode) owns discovery; refresh only
  re-fetches dockets the corpus already holds.
- It does **not** target `parse_failed` documents. They have no `parsed.*` rows, so they carry no
  parsed state to be non-terminal about; their remedy is parser work. (3 such documents at
  runbook adoption — restate the current count each cycle.)
- It does **not** guarantee dispositions. A still-pending docket re-fetches byte-identical
  (`unchanged`) and yields zero loader writes. What refresh captures is bounded by how much has
  actually happened on the target dockets since the last fetch — cadence-dependent, decided per
  run by the operator (pinned decision 5); nothing about cadence is automated or hardcoded.
- A refresh run is **not** window coverage: it writes no window-ledger entries and no miss-ledger
  entries, ever.

## Counsel conditions (ADR 0002 — apply in full)

Refresh fetches are collection actions under all counsel conditions. Enforced **in code** (shared
with enumeration, flag-proof): the 240-minute session ceiling, the 300s post-block cooldown, the
jittered 2.0–5.0s per-request delay, inter-batch cooldowns (60s floor), and the block/error
streak stops (5) over fail-closed classification. Enforced **by this runbook** (operator
discipline): **≤ 8 hours of collection per day**, a real break between sessions, and weekends as
the default collection posture (weekday sessions are within conditions but not the default).

## Target set

Derived at run time from the loaded corpus (never a static list): every `parsed.dockets` row with
at least one held charge (`parsed.charges.disposition_raw IS NULL`), joined to its current source
hash. `--court both` is the canonical full refresh; refresh mode requires `--court` explicitly so
a default can never silently shrink a cycle to one court.

---

## The cycle

Run steps in order. Every acceptance-relevant summary line is **copy-pasted verbatim** into the
completion record (never retyped — see the COL-4a transcription incident), alongside the report
filename where the step writes one under `~/court-data/`.

Environment for DB-touching steps, sourced at the shell boundary and never echoed:

```
set -a; . <repo-root>/.env; set +a
```

### 0. Pre-cycle recon (record the baseline)

Record (counts only): `parsed.dockets` / `parsed.charges` / held-charge counts, fact-run id +
`fact.charge_outcomes` count, the active published aggregate run id, and the refresh target count
by court. These are the "before" numbers the post-cycle restatement reconciles against.

**Failure behavior:** none (read-only). A surprising baseline (e.g. duplicate docket numbers ≠ 0)
is a STOP before anything is pruned.

### 1. Prune fact runs

```
pipeline prune-fact-runs --all-completed            # dry run — review the selection
pipeline prune-fact-runs --all-completed --confirm  # delete (worklog the prune)
```

Whole-run deletion (run rows + facts via CASCADE) so supersessions cannot hit the fail-loud fact
FKs. **From this point until step 9 completes, the fact layer is empty/rebuilding. Published
public aggregates are unaffected throughout: `analytics.*` rows are standalone and the published
run keeps serving — COL-4a gate-verified.**

**Failure behavior:** refuses whole if any selected run is non-completed; absent ids are
idempotent success. A refusal is a STOP (adjudicate in planning chat).

### 2. Refresh fetch session(s)

```
pipeline collect --mode refresh --court both \
  --refresh-dir ~/court-data/refresh-intake-<UTC-date>/ \
  --max-minutes 240
```

One **fresh, dated** refresh dir per cycle; the **same** dir for every session of that cycle
(already-fetched targets skip locally, so interrupted cycles resume by re-running the identical
command). Repeat sessions — within the daily cap, with breaks — until the run ends
`targets_exhausted` and the remainder is only `already_fetched`.

**Failure behavior:** block/error streaks stop the run in code (cooldown posture; resume in a
later session). `no_results_anomalies > 0` (a loaded docket returning no results) is a
STOP-and-report. A truncated cycle (time cap mid-list) is normal — resume, don't restate.

### 3. Import

```
pipeline import-manual ~/court-data/refresh-intake-<date>/
```

Cross-check against the final refresh run-report: `duplicate ≈ unchanged_hash`,
`imported ≈ changed_hash` (exact once all sessions completed and nothing else touched the dir).

**Failure behavior:** `invalid`/`failed` counts > 0, or a cross-check mismatch: STOP-and-report.

### 4. Extract

```
pipeline extract-text ~/court-data/refresh-intake-<date>/ \
  --output-dir ~/court-data/extracted-refresh-<date>/
```

Cycle-scoped output dir (keeps canonical extraction sets immutable, per the intake protocol).

**Failure behavior:** per-document quarantine is counted, never silently dropped; a systematic
failure cluster is a STOP.

### 5. Parse

```
pipeline parse --artifacts-dir ~/court-data/extracted-refresh-<date>/ \
  --output-dir ~/court-data/envelopes-refresh-<date>/
```

**Failure behavior:** failed envelopes are quarantine (isolated = expected, counted; systematic
cluster = STOP). A refreshed sheet that now fails to parse where its predecessor parsed is an
anomaly — STOP-and-report.

### 6. Goldens (where new)

```
pipeline run-fixtures --corpus-dir ~/court-data/refresh-intake-<date>/ --init-goldens
```

Changed sheets carry new hashes → new goldens (`--init-goldens` writes absent goldens only);
unchanged sheets match their existing hash-named goldens. Superseded hashes' goldens remain on
disk as historical record. **Every golden-writing invocation gets its `tasks/worklog.md` note.**
Refreshed dockets are never equivalence-checked (post-Capstone fetches; the baseline has no entry).

**Failure behavior:** reported drift on an existing golden is a STOP (a refreshed PDF must never
silently rewrite an established golden).

### 7. Load (supersessions happen here)

```
pipeline load --envelopes-dir ~/court-data/envelopes-refresh-<date>/
```

Expected categories: `superseded == changed_hash`, `skipped_same_version == unchanged_hash`,
`loaded == 0` (a refresh adds no new dockets), `failed_envelope_loaded` = the step-5 quarantine
count, everything else 0. Supersession keeps the old raw row as `parse_superseded` provenance and
may emit `supersession_regression` review items (flags, never blocks) — count them for step 10.

**Failure behavior:** `supersession_blocked_by_fact_rows` is **impossible after step 1** — its
appearance means the prune didn't cover the corpus and is a STOP. `failed_exception` /
`missing_import_record` > 0: STOP. `loaded > 0`: a non-refresh PDF entered the cycle dir — STOP.

### 8. Rebuild facts

```
pipeline build-facts
```

New `build_run_id` over the full corpus. All intake-protocol reconciliation gates apply
(`facts_written + held_skipped == charges_processed`, held charges produce zero facts, review-item
dedup holds, zero duplicate docket numbers). Expect `held_skipped` to **drop or hold** vs step 0;
a rise is an anomaly — STOP.

**Failure behavior:** any reconciliation mismatch is STOP-AND-REPORT, adjudicated in planning
chat, never self-resolved.

### 9. Aggregate + publish (required, same operational session)

```
pipeline generate-aggregates
pipeline validate-aggregates
pipeline publish-aggregates
```

**Pinned decision 7 (confirmed): a refresh cycle ends with generate + validate + publish in the
same operational session** — public data never sits long on a pruned-and-rebuilt fact layer. This
step is required, not optional; a cycle that cannot publish same-session is an incident to
adjudicate, not a pause point.

**Failure behavior:** validation failure blocks publish (fail-loud) — STOP; the previously
published run keeps serving throughout.

### 10. Post-publish spot check + restatement

- Spot-check the public endpoints serve the NEW aggregate run (run id + a count or two — counts
  only, no docket-derived content).
- Restate in `tasks/worklog.md` **and** planning chat: targets by court; attempted / fetched /
  unchanged / changed / new; blocked / failed / anomalies; import counts; load categories
  (supersession count explicitly); fact counts + held delta; `supersession_regression` items if
  any; the published aggregate run id. Verbatim-paste rule applies to every line.

---

## STOP conditions (literal, adjudicated in planning chat — never by the agent)

1. Any step suggesting a loader change (COL-4a is complete; refresh never edits the loader).
2. `no_results_anomalies > 0`, `loaded > 0` at step 7, `supersession_blocked_by_fact_rows`, a
   golden-drift report, a systematic quarantine cluster, or any reconciliation mismatch.
3. Any ambiguity about whether an action is within the counsel conditions.
4. Any other unexplained anomaly in a first-of-kind cycle.
