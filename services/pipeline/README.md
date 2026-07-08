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
  *directory* path once at startup is the only path that appears.

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
