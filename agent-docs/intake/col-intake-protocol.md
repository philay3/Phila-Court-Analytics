# COL Intake Protocol

_Status: active (established Task 24.2, Sprint 5). Governs every deliberate
growth of the parsed corpus beyond the frozen Capstone-derived set._

This document defines the **only** sanctioned path by which collector-gathered
(COL) docket PDFs enter the corpus. Corpus growth is protocol-governed
(Standing Decision 14): deliberate, counted, reconciled — never incidental.

Nothing here contains docket-derived content. All per-run counts and artifacts
live **outside the repo** under `~/court-data/`; only aggregate counts are
restated in `tasks/worklog.md`.

---

## The intake path

```
~/court-data/intake/ (collector drop zone, continuously appended)
  → [0] FREEZE: snapshot the exact staged file set at run start (manifest)
  → [0b] EXCLUDE: drop docket numbers already loaded (see "Dedupe", below)
  → import-manual  (16.3; content-hash dedupe; hash-keyed metadata records)
  → extract-text   (16.2; per-page text extraction; status per document)
  → parse          (18.1; extraction artifacts → per-docket envelopes)
  → run-fixtures --init-goldens  (19.2; tier-2 goldens for new dockets)
  → load           (21.3; envelopes → raw.* + parsed.* ; idempotent upsert)
  → build-facts    (23.2/24.1; full-corpus fact rebuild, new build_run_id)
```

Each stage writes its artifacts under `~/court-data/` (outside any git tree):
`imports/`, `extracted-intake-<date>/`, `envelopes-intake-<date>/`,
`goldens/` (+ `goldens/reports/`), and a run report under `reports/`.
Intake-scoped `extracted-*`/`envelopes-*` directories keep the canonical
envelope set (`envelopes-2026-07-11-172514/`) **immutable** and scope `load`
to only the new dockets.

---

## [0] Freeze — permanent, mandatory first step

The collector continuously appends PDFs to `~/court-data/intake/`, so
"everything currently staged" is a **moving target**. A fact build cannot
reconcile against an input set that mutated mid-run. Therefore, at run start:

1. **Snapshot** the exact set of `*.pdf` files staged at that instant into a
   dedicated, immutable snapshot directory
   (`~/court-data/intake-snapshots/<task>-<UTC>/`), by **copying** the files
   (a copy is immune to concurrent additions/removals; a symlink is not).
2. **Write a manifest** (`MANIFEST.json`, kept beside the snapshot dir, not
   inside it) recording, per included file, its `sha256` content hash — plus
   the staged-at-freeze count, the excluded count, and the included count.

The snapshot is the **intake denominator** for the run report and the restated
corpus counts. Anything dropped into `~/court-data/intake/` after the freeze is
**excluded from this run** and belongs to the next intake. The freeze is a
permanent part of the protocol, not a one-run convenience.

---

## Dedupe — two distinct kinds of overlap

**Content-hash dedupe (automatic, 16.3).** `import-manual` keys one metadata
record per file by its `sha256`. A byte-identical re-drop of an already-imported
PDF is a `duplicate` (no new record) — this reconciles multi-operator overlap
where two operators fetched the _same bytes_.

**Docket-number overlap (manual exclusion at [0b]).** A docket already loaded
into `parsed.*` can be re-collected later as a **different-byte** PDF (portals
re-render sheets). Content-hash dedupe cannot catch this: different bytes →
different `sha256` → different `raw.source_documents.file_hash`. Because
`parsed.dockets` is keyed on `source_document_id` (not `docket_number`), loading
such a copy would create a **second parsed row for the same docket number**,
double-counting its facts in the rebuild.

The loader is **not** modified to guard against this (out of scope; the loader's
idempotency contract is source-hash based by design). Instead the **input set is
filtered**: at [0b], docket numbers already present in `parsed.dockets` are
excluded from the snapshot. A re-collected copy of an already-loaded docket
carries **zero new information** for the current corpus, so exclusion loses
nothing. (Whether a later re-pull of a docket is _more complete_ than the loaded
copy is a separate freshness-refresh policy question — deferred, not solved
here.)

**Refresh cycles (COL-4b):** the [0b] exclusion does **not** apply to refresh
targets — see the [Refresh Cycle Runbook](refresh-runbook.md); loader supersession (COL-4a) is the sanctioned path there.

The run report states both the **snapshot count** and the **post-exclusion
(included) count**.

---

## Quarantine — isolated vs systematic

Per-docket exception isolation holds at every stage: one bad docket never kills
the run; it is **counted and reported, never silently dropped**.

- **Extraction** classifies each document `success` / `partial` /
  `needs_ocr_or_review` / `failed`.
- **Parse** failures produce a `failed` envelope (no record).
- **Load** writes a `raw.source_documents` row for a `failed` envelope
  (`parse_failed` status + error code) but **no `parsed.*` rows** — so a
  quarantined docket is Sprint-6-visible yet contributes **zero** charges and
  therefore zero facts, structurally.

Two readings of quarantine, and they are **not** the same:

- **Isolated** unsupported-format / `KeyError`-class quarantines are **expected**
  and reported — they are evidence for the readiness verdict.
- A **systematic cluster** (many dockets failing on a shared layout) is
  **STOP-AND-REPORT**: it means the parser is inadequate on that document class
  and the readiness verdict stays "not ready." A systematic cluster is never
  folded into "expected quarantine."

---

## Load idempotency on growth

`load` processes only the envelopes in its `--envelopes-dir`. Pointed at an
intake-scoped envelopes directory, it **adds** the new dockets and never
disturbs the existing corpus (their source hashes are absent from the set).
Upsert identity is the source file hash; version is
`(record_parser_version, envelope_parser_version)` compared as a tuple —
same version re-load is a no-op after a content re-check; a newer version
replaces transactionally.

---

## Fact rebuild + reconciliation

`build-facts` reads the **full grown corpus** and writes a **new `build_run_id`
partition** (run-partitioned append; prior runs' facts are retained). Per-run
counts are **higher** than the prior run's — that is the point of intake. The
corpus must carry a **single** `(record, envelope)` version pair; a mixed-version
corpus is a STOP.

Reconciliation gates (per-run, scoped to the new `build_run_id`, reframed to the
grown corpus) — **any mismatch is STOP-AND-REPORT**, adjudicated in the planning
chat, never self-resolved:

- disposed-charge count = outcome-fact count + explained exclusions;
- sentence-component count (on disposed) = sentence-fact count + explained
  exclusions;
- held charges produce **zero** outcome facts;
- the original recovered SENTINEL_COLLISION dockets show **unchanged**
  conservative judge behavior;
- review-item dedup holds: pre-existing items are **not** multiplied; new items
  appear **only** for new dockets;
- **zero** duplicate docket numbers in `parsed.dockets` (the [0b] exclusion
  working).

---

## The Capstone baseline is untouched

The Capstone baseline (`~/court-data/capstone-baseline/`) is an **immutable port
anchor** (SD 14). New dockets:

- have **no** baseline entry (the baseline is never regenerated);
- enter goldens via `--init-goldens` (goldens **initialized**, never compared
  against a nonexistent baseline), with a mandatory `tasks/worklog.md` note per
  golden-writing invocation;
- are **never** run through the equivalence comparator (it diffs against the
  Capstone baseline, which has no entry for them).

---

## Console & artifact hygiene

Console/log output carries **counts, statuses, and hash-prefix ids only** — never
docket numbers, raw text, paths, or `DATABASE_URL` / `DEFENDANT_HASH_SALT`
(both sourced at the CLI boundary, never echoed). The run report and goldens live
under `~/court-data/` (outside the repo). This committed protocol document, and
any worklog entry it produces, contain **zero** docket-derived content.
