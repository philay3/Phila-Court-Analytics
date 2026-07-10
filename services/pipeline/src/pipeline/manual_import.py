"""Manual import stage (Task 16.3).

Directory of docket PDFs in -> one hash-keyed JSON metadata record per file
written OUTSIDE the repo, with duplicate detection across runs and a
counts-only run report. This is the real ``import-manual`` path; it does not
extract or parse (16.2 owns extraction) and performs no database writes.

Dedupe model: each imported file yields exactly one record named
``<sha256>.json`` under the metadata root. "Duplicate" means "a record with
this content hash already exists" — no separate index, works across runs.

Invalid-content dedupe is deliberate: a file with a ``.pdf`` extension whose
bytes are not ``%PDF-`` still gets a hash-keyed record with status
``invalid``. Re-importing that same file therefore counts as a ``duplicate``
and the original record (retaining status ``invalid``) is left untouched.
Wrong-*extension* files are different: they are never docket candidates, so
they are counted ``invalid`` and skipped with NO record written.

Provenance rule: the import stage records the filename stem as
``docket_number_provenance`` only when it matches the Philadelphia UJS
docket-number pattern; court type and county are derived from that pattern or
left null. Nothing is guessed. The parser (later stage) takes the docket
number as an explicit parameter and never derives it from a filename.

Privacy rules (hard):

- Console and log output carry counts and statuses ONLY — never filenames,
  docket numbers, stems, paths, or file content. Per-file detail lives in the
  metadata records (which live outside the repo).
- Error values carry a structured code and, for read failures, the OS error
  *class name* only — never file content.
- The metadata root is resolved/created at the run boundary, never at import,
  and a location inside a git working tree is refused.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pipeline.paths import inside_git_worktree

logger = logging.getLogger("pipeline.manual_import")

MODE = "manual"

# Status vocabulary: exactly one of these per file.
STATUS_IMPORTED = "imported"
STATUS_DUPLICATE = "duplicate"
STATUS_INVALID = "invalid"
STATUS_FAILED = "failed"

# Structured error codes. ``invalid`` codes describe validation outcomes;
# ``failed`` codes describe read failures. Error values never contain content.
ERROR_WRONG_EXTENSION = "wrong_extension"
ERROR_BAD_MAGIC_BYTES = "bad_magic_bytes"
ERROR_UNREADABLE_FILE = "unreadable_file"

PDF_MAGIC = b"%PDF-"
_HASH_CHUNK_SIZE = 1024 * 1024  # 1 MiB; PDFs stream rather than load whole.

# Philadelphia UJS docket-number pattern, e.g. CP-51-CR-0001234-2020 /
# MC-51-CR-0001234-2020: court (CP|MC) - county(2) - type(2 alpha) -
# sequence(7) - year(4). Matched against the filename stem only.
DOCKET_NUMBER_RE = re.compile(r"^(CP|MC)-(\d{2})-[A-Z]{2}-\d{7}-\d{4}$")

RUN_REPORT_FILENAME = "import-report.json"

# Statuses reported in the run summary, in a stable display order.
_SUMMARY_ORDER = (STATUS_IMPORTED, STATUS_DUPLICATE, STATUS_INVALID, STATUS_FAILED)


@dataclass
class FileOutcome:
    """Result of processing one candidate file.

    ``record`` is the metadata dict to persist, or None when no record is
    written (wrong extension, unreadable file, or a duplicate hash whose
    record already exists). ``file_hash`` is the record key when present.
    """

    status: str
    record: dict[str, object] | None = None
    file_hash: str | None = None


def derive_provenance(stem: str) -> dict[str, str | None]:
    """Docket-number provenance fields from a filename stem.

    On a pattern match, returns the stem as provenance plus the literal court
    code (CP/MC) and 2-digit county code. On no match, all three are null —
    never guessed.
    """
    match = DOCKET_NUMBER_RE.match(stem)
    if match is None:
        return {
            "docket_number_provenance": None,
            "court_type": None,
            "county": None,
        }
    return {
        "docket_number_provenance": stem,
        "court_type": match.group(1),
        "county": match.group(2),
    }


def _build_record(
    *,
    file_hash: str,
    original_filename: str,
    file_size_bytes: int,
    stem: str,
    status: str,
    error_code: str | None,
) -> dict[str, object]:
    """Assemble the full pinned metadata record. Every field always present."""
    record: dict[str, object] = {
        "id": file_hash,
        "original_filename": original_filename,
        "file_hash": file_hash,
        "file_size_bytes": file_size_bytes,
        "imported_at": datetime.now(UTC).isoformat(),
        "mode": MODE,
        "status": status,
        "error_code": error_code,
    }
    record.update(derive_provenance(stem))
    return record


def _hash_and_head(path: Path) -> tuple[str, bytes]:
    """Streamed sha256 plus the file's first bytes (for the magic check).

    Reads in 1 MiB chunks so multi-MB PDFs never load whole. Returns the full
    hex digest and up to ``len(PDF_MAGIC)`` leading bytes. Raises OSError to
    the caller on any read/permission failure.
    """
    digest = hashlib.sha256()
    head = b""
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_SIZE):
            if not head:
                head = chunk[: len(PDF_MAGIC)]
            digest.update(chunk)
    return digest.hexdigest(), head


def process_file(path: Path, metadata_root: Path) -> FileOutcome:
    """Classify and (when applicable) build the record for one file.

    Does not write anything; the caller persists ``outcome.record`` unless the
    hash already exists (duplicate). Ordering: extension -> read/hash ->
    magic-bytes -> dedupe -> imported.
    """
    if path.suffix.lower() != ".pdf":
        # Not a docket candidate: counted invalid, skipped, no record.
        return FileOutcome(status=STATUS_INVALID)

    try:
        file_hash, head = _hash_and_head(path)
    except OSError as exc:
        # No hash means no record to key by; counted in the run report only.
        logger.warning(
            "unreadable file skipped",
            extra={
                "status": STATUS_FAILED,
                "error_code": ERROR_UNREADABLE_FILE,
                "os_error": type(exc).__name__,
            },
        )
        return FileOutcome(status=STATUS_FAILED)

    stat = path.stat()
    error_code = None if head.startswith(PDF_MAGIC) else ERROR_BAD_MAGIC_BYTES
    status = STATUS_INVALID if error_code else STATUS_IMPORTED

    record = _build_record(
        file_hash=file_hash,
        original_filename=path.name,
        file_size_bytes=stat.st_size,
        stem=path.stem,
        status=status,
        error_code=error_code,
    )

    # Dedupe: an existing record (imported OR invalid) makes this a duplicate.
    if (metadata_root / f"{file_hash}.json").exists():
        return FileOutcome(status=STATUS_DUPLICATE, file_hash=file_hash)

    return FileOutcome(status=status, record=record, file_hash=file_hash)


def _scan(directory: Path) -> list[Path]:
    """Flat (non-recursive) list of the directory's files, sorted."""
    return sorted(p for p in directory.iterdir() if p.is_file())


def run_manual_import(input_dir: Path, metadata_root: Path) -> int:
    """Import every file in ``input_dir`` (flat) and write hash-keyed records.

    Resolves and creates ``metadata_root`` here (run boundary, never at
    import), refusing any location inside a git working tree. Writes one
    ``<sha256>.json`` per newly imported/invalid-content file, never
    overwriting an existing record. Prints counts-by-status to stdout and
    writes a counts-only run report; logs carry counts/statuses only. Returns
    a process exit code.
    """
    if not input_dir.exists() or not input_dir.is_dir():
        logger.error("input path is not a directory", extra={"path": str(input_dir)})
        return 2

    if inside_git_worktree(metadata_root):
        logger.error(
            "metadata root resolves to a path inside a git working tree; "
            "choose a location outside any repository",
            extra={"metadata_root": str(metadata_root)},
        )
        return 2

    metadata_root.mkdir(parents=True, exist_ok=True)
    files = _scan(input_dir)
    logger.info("starting manual import", extra={"file_count": len(files)})

    counts = {status: 0 for status in _SUMMARY_ORDER}
    for path in files:
        outcome = process_file(path, metadata_root)
        if outcome.record is not None and outcome.file_hash is not None:
            out_path = metadata_root / f"{outcome.file_hash}.json"
            out_path.write_text(
                json.dumps(outcome.record, indent=2, sort_keys=True) + "\n"
            )
        counts[outcome.status] += 1
        logger.info("processed", extra={"status": outcome.status})

    _write_run_report(metadata_root, counts)
    summary = " ".join(f"{status}={counts[status]}" for status in _SUMMARY_ORDER)
    print(summary)
    logger.info("manual import complete", extra={"file_count": len(files)})
    return 0


def _write_run_report(metadata_root: Path, counts: dict[str, int]) -> None:
    """Write the counts-only run report, overwriting any prior report."""
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "counts": {status: counts[status] for status in _SUMMARY_ORDER},
    }
    (metadata_root / RUN_REPORT_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
