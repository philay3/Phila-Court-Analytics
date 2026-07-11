# pca-pipeline

Python data pipeline for Philadelphia Court Outcomes Analytics. The
`evaluate-extractors` command is implemented (Task 5.1); the other three CLI
commands are placeholders and real work (PDF import, extraction, parsing,
normalization, attribution, aggregation) arrives in later tasks.

Distribution name is `pca-pipeline` (matching the `@pca/*` convention on the
JS side); the import package and console script are both `pipeline`.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+ (uv will provision
a managed interpreter automatically if needed).

```sh
cd services/pipeline
uv sync
```

## Running the CLI

```sh
uv run pipeline --help
uv run pipeline import-manual        # placeholder
uv run pipeline extract-text         # placeholder
uv run pipeline evaluate-extractors  # implemented, see below
uv run pipeline run-fixtures         # placeholder
```

Placeholder commands log a structured "not implemented" message and exit 0.
Logs are JSON lines on **stderr**; stdout is reserved for future
machine-readable output.

## evaluate-extractors

Runs the three candidate PDF text extractors (PyMuPDF, pdfplumber, pypdf)
against a directory of local fixture docket PDFs and writes comparison
artifacts, so a human can make the Sprint 1 extractor decision (Task 5.3).
This is an evaluation harness only — `extract-text` remains the (stubbed)
production path, and no OCR is performed; image-only/empty pages are just
flagged.

```sh
uv run pipeline evaluate-extractors \
  --fixtures-dir ~/court-data/fixtures \
  --output-dir ~/court-data/eval-out \
  --dump-text
```

Options:

- `--fixtures-dir` (required): flat directory of fixture PDFs. The search is
  **non-recursive** — PDFs in subdirectories are ignored, so stage the whole
  corpus in one directory. Errors if the directory is missing or contains no
  PDFs.
- `--output-dir` (required): where artifacts are written (created if needed).
  The harness **refuses to run if this resolves to a path inside any git
  working tree** — pick a location outside every repository so reports and
  text dumps can never be committed.
- `--extractors` (optional): comma-separated subset, e.g.
  `--extractors pymupdf,pdfplumber`. Default: all three. `summary.json`
  covers only the extractors that ran.
- `--dump-text` (optional, off by default): also write each file's extracted
  text per extractor for side-by-side human review. **The Task 5.3
  evaluation requires this** — readability of charge tables and
  disposition/sentencing sections can only be judged from the text itself.

### Output artifacts

Everything is keyed by a 16-char SHA-256 prefix of the file bytes — never by
filename, since fixture filenames are real docket numbers.

- `report-<extractor>.json` — per-file metrics: page count, total and
  per-page character counts, wall-clock duration, empty pages (count +
  indices), `needs_ocr_or_review` (all pages empty or the file failed to
  open), case-insensitive occurrence counts for the UJS section keywords
  (CASE INFORMATION, CHARGES, ENTRIES, …), and sanitized error records.
- `file-index.json` — hash → original filename mapping so results can be
  traced back locally. It stays in the output dir with everything else.
- `summary.json` — per-extractor rollups: total files, failures, total/mean
  duration, `needs_ocr_or_review` count, and per-keyword hit rates (fraction
  of successfully processed files with at least one hit).
- `text/<extractor>/<hash>.txt` — extracted text dumps (only with
  `--dump-text`), pages separated by `--- page N ---` markers.

A file that fails to open is recorded and skipped; it never aborts the run.

### Privacy rules

- Fixture PDFs are real UJS docket sheets. They live **outside the repo**,
  are supplied at runtime via `--fixtures-dir`, and must never be committed
  or copied into the repo.
- The output dir (reports, file index, text dumps) also lives outside the
  repo — enforced by the git-working-tree guard above.
- Logs never contain extracted text, fixture filenames, or per-file paths —
  only hashes, counts, durations, and error types. Logging the fixtures
  _directory_ path once at startup is the only path that appears.

## collect (docket collection)

Automated collection command around the ported UJS-portal collector (Task
COL-1). It enumerates `MC-51-CR-#######-YYYY` docket numbers, fetches each
docket-sheet PDF into an intake directory, and enforces **all** pacing and
stop conditions in code — no operator-watched shell loop. Chops runs it
manually on a weekend; this is the tooling only.

Playwright is an **optional** dependency in the `collector` group. It is
**not** installed by default and **not** installed in CI, and `collect`
**refuses to run in a CI environment**. Install it only on the collection
machine:

```sh
uv sync --group collector
uv run playwright install chromium
```

### Run procedure (weekend baseline)

```sh
uv run pipeline collect \
  --court MC --year 2025 --start-seq 1 --count 600 --max-minutes 60
```

Defaults match the baseline run: court `MC`, year `2025`, start sequence `1`,
count `600` (the time cap ends the run before the range does), `--max-minutes
60`, intake dir `~/court-data/intake/`, report dir
`~/court-data/collection-runs/`. The browser runs **headful by default** (the
proven configuration and the honest posture); `--headless` exists but is off.

Watch the browser and the live console progress (JSON lines on stderr): each
attempt logs its docket number, outcome, batch number, and running
hits/misses/blocks counts; cooldowns log a notice. **Ctrl-C is graceful** — it
finishes the in-flight request, writes the report, and exits.

### Enforced legal conditions (counsel-locked, NOT overridable by any flag)

- **Hard 240-minute ceiling** on any run — `--max-minutes` can only shorten it.
- **2-minute cooldown** after any block/bot-check response, before the next
  request.
- Jittered **2.0–5.0s delay after every real portal request**.

### Operational parameters (tunable flags; defaults shown)

- **`--batch-size` (default 40)** and **`--batch-cooldown-seconds` (default 240)**
  — dockets per batch and the inter-batch cooldown. The cooldown has an
  **enforced 60s floor** (may be raised, never lowered below it). Batch
  boundaries count real portal requests, not already-present skips.
- **Consecutive-block streak** stop at **N=5** (`block_streak`): increments on a
  block/bot-check, resets on a hit or a positively-identified clean miss.
- **Consecutive-error streak** stop at **N=5** (`error_streak`): increments on
  transport errors, resets on any live response (hit/miss/blocked). Guards
  against a broken selector burning the whole range.

### Classification (fail-closed)

- A **bot check / captcha is always treated as a block** and is never solved,
  bypassed, or automated. The observed **"unauthorized" / "not authorized"**
  block page is recognized explicitly.
- A **clean miss** requires **positive identification** of the portal's genuine
  no-results state (the search UI rendered with zero docket-sheet links and no
  block signature). It is a successful request and a logged coverage data
  point — never a block or a failure.
- **Fail-closed default:** any page that is neither a successful PDF nor a
  positively-identified no-results page classifies as `blocked` — unknown or
  unrecognized shapes are blocks, never misses. (Run 1 proved the old fail-open
  polarity mislabeled an "unauthorized" block page as `miss`, so 0 blocks were
  logged and the post-block cooldown never fired; this is the fix.)
- **Documented residual:** a block page that renders the _full_ search UI with
  zero sheet links **and** none of the recognized block text would still
  classify as `miss`. The observed block page is covered by its signature, and
  interstitials without the search UI are covered by the fail-closed default;
  the operator confirms block-page appearance on the next headful run.
- **Resumable**: a docket whose `<docket>.pdf` is already in the intake dir is
  skipped and logged `already_present`; reruns over an overlapping range are
  safe.

### Outputs

- PDFs → `<intake-dir>/<docket>.pdf`.
- Per run → `<report-dir>/<run-id>/`:
  - `attempts.jsonl` — one line per attempted docket number (docket number,
    outcome, detail, batch, timestamp).
  - `run-report.json` — run id, timestamps, wall-clock duration (for ≤4h/≤8h
    session accounting), parameters used, counts, max block/error streaks, stop
    reason (`time_cap` / `range_exhausted` / `block_streak` / `error_streak` /
    `operator_abort`), cooldowns taken, and the coverage statement (`N hits of M
attempted in range X–Y`).

Both directories must be **outside every git working tree** (enforced) so
nothing derived from real dockets is committed. Docket numbers appear in logs
and reports (good-faith record); **page content, defendant names, and any text
beyond outcome classification appear nowhere**, and the collector captures **no
screenshots, tracing, HAR, or video** in any code path.

### Operational parameters flagged for re-evaluation

Two Capstone behaviors were intentionally changed and should be revisited after
the baseline run, alongside the batch/cooldown/N values:

- **Browser-restart-every-150-fetches was dropped.** Capstone restarted the
  browser periodically to guard memory. For a 60-minute baseline (≤ ~600
  requests) this is unnecessary; re-evaluate if extended collection lands.
- **Block/bot-check DOM signatures are best-effort.** Capstone had no block
  detection to port. Run 1 added the observed "unauthorized" signature and a
  fail-closed default (unknown pages → blocked), so the collector is now robust
  to unseen block pages, but the exact selectors/phrases in
  `collector/transport.py` — including the positive no-results marker — remain
  unverified against the live portal and must be confirmed on the next headful
  run.

## Tests

```sh
uv run pytest
```

Tests use tiny synthetic PDFs generated at test time — no real dockets ever
appear in the test suite, and a test asserts that run logs contain neither
extracted text nor fixture filenames.

## Lint / format

```sh
uv run ruff check .
uv run ruff format .          # or --check to verify without writing
```

## Logging rules

Structured logging lives in `src/pipeline/logging_utils.py`. Standing privacy
rule: raw docket text, defendant-identifying data, and file contents must
never be logged — only metadata (counts, durations, filenames-by-hash or
batch IDs, error types).
