# pca-pipeline

Python data pipeline for Philadelphia Court Outcomes Analytics. This is the
project shell only — the four CLI commands are placeholders and real work
(PDF import, extraction, parsing, normalization, attribution, aggregation)
arrives in later tasks.

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
uv run pipeline import-manual
uv run pipeline extract-text
uv run pipeline evaluate-extractors
uv run pipeline run-fixtures
```

Each command currently logs a structured "not implemented" message and exits 0.
Logs are JSON lines on **stderr**; stdout is reserved for future
machine-readable output.

## Tests

```sh
uv run pytest
```

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
