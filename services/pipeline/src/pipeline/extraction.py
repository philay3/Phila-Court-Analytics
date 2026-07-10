"""Production PDF text-extraction stage (Task 16.2).

PDF in -> ordered per-page text plus a JSON artifact written outside the
repo. This is the real ``extract-text`` path; OCR is out of scope, so
image-only / low-text pages are detected and flagged, never processed.

Fidelity rule (Task 17.1 will compare this stage's output line-by-line
against Capstone reference text): the extraction call is
``page.extract_text() or ""`` with **default arguments** — no layout,
tolerance, or keep_blank_chars parameters. Do not add any.

Extractor policy (ADR 0001): pdfplumber only. pymupdf / pypdf must never be
imported by a production pipeline module; they remain eval-harness-only.

Privacy rules (hard):

- Raw docket text never reaches logs, console, or error messages. Console
  and log output carry only ids, counts, statuses, page numbers, durations.
- Artifacts live OUTSIDE the repo (default ``~/court-data/extracted/``).
  Output-dir resolution and creation happen at the run boundary, never at
  import; a dir inside a git working tree is refused.

Threshold semantics (deliberate split):

- **Status / warning decisions compare ``len(text.strip())``** against the
  low-text threshold, so a whitespace-only page counts as empty/below and
  never inflates to "content".
- **The artifact's ``per_page_chars`` records raw ``len(text)``** as the
  literal per-page character count. These two numbers can differ for a page
  padded with whitespace; that is intended.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import pdfplumber

from pipeline.paths import inside_git_worktree

logger = logging.getLogger("pipeline.extraction")

EXTRACTOR_NAME = "pdfplumber"
PAGE_SEPARATOR = "\x0c"  # form feed; joins page texts for the text hash

# Status vocabulary (Task 16.2 decision 5): exactly one of these.
STATUS_SUCCESS = "success"
STATUS_PARTIAL = "partial"
STATUS_NEEDS_OCR_OR_REVIEW = "needs_ocr_or_review"
STATUS_FAILED = "failed"

# Provisional warning codes. Task 18.1 owns the unified warning-code
# vocabulary and will absorb or align these. Warnings carry structural
# context only (page numbers, counts) — never extracted text.
WARNING_LOW_TEXT_PAGE = "low_text_page"
WARNING_EMPTY_PAGE = "empty_page"

# Per-page character threshold (compared against stripped length). A genuine
# UJS docket page runs many hundreds to thousands of characters; an
# image-only / near-blank page yields 0 to a few. 100 sits far below any real
# content page (no false "partial") yet well above OCR-needed noise.
DEFAULT_LOW_TEXT_THRESHOLD = 100

# Error code recorded on a failed artifact. Provisional, like the warnings.
ERROR_UNREADABLE_PDF = "unreadable_pdf"

_ERROR_MESSAGE_MAX_LEN = 200


@dataclass
class ExtractionResult:
    """Outcome of extracting one PDF.

    On ``failed``, ``page_texts``/``per_page_chars`` are empty, ``page_count``
    is 0, ``text_hash`` is None, and ``error`` carries a sanitized
    ``{code, message}``. Otherwise ``error`` is None.
    """

    status: str
    page_texts: list[str] = field(default_factory=list)
    page_count: int = 0
    per_page_chars: list[int] = field(default_factory=list)
    warnings: list[dict[str, object]] = field(default_factory=list)
    text_hash: str | None = None
    error: dict[str, str] | None = None


def compute_text_hash(page_texts: list[str]) -> str:
    """sha256 of page texts joined by form feed, per decision 7.

    Empty pages contribute empty strings; join order is page order.
    """
    joined = PAGE_SEPARATOR.join(page_texts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _sanitize_error(exc: BaseException, path: Path) -> dict[str, str]:
    """Error record safe to persist: no file content, no filename.

    pdfplumber / pdfminer messages sometimes embed the file path (a real
    docket number) or byte fragments, so any occurrence of the path, name, or
    stem is redacted and the message is length-capped.
    """
    message = str(exc)
    for leak in (str(path), str(path.resolve()), path.name, path.stem):
        if leak:
            message = message.replace(leak, "<redacted>")
    if len(message) > _ERROR_MESSAGE_MAX_LEN:
        message = message[:_ERROR_MESSAGE_MAX_LEN] + "…"
    return {"code": ERROR_UNREADABLE_PDF, "message": message}


def _status_and_warnings(
    page_texts: list[str], low_text_threshold: int
) -> tuple[str, list[dict[str, object]]]:
    """Derive status and warnings from page texts.

    Content is measured as ``len(text.strip())`` so whitespace never counts;
    warnings use 1-based page numbers and carry structural context only.
    """
    warnings: list[dict[str, object]] = []
    below_count = 0
    for index, text in enumerate(page_texts):
        stripped_len = len(text.strip())
        if stripped_len == 0:
            below_count += 1
            warnings.append({"code": WARNING_EMPTY_PAGE, "page": index + 1})
        elif stripped_len < low_text_threshold:
            below_count += 1
            warnings.append(
                {
                    "code": WARNING_LOW_TEXT_PAGE,
                    "page": index + 1,
                    "char_count": stripped_len,
                }
            )

    if below_count == 0 and page_texts:
        status = STATUS_SUCCESS
    elif below_count == len(page_texts):
        # All pages below threshold, including a zero-page document.
        status = STATUS_NEEDS_OCR_OR_REVIEW
    else:
        status = STATUS_PARTIAL
    return status, warnings


def extract(
    pdf_path: Path, *, low_text_threshold: int = DEFAULT_LOW_TEXT_THRESHOLD
) -> ExtractionResult:
    """Extract ordered page text from one PDF.

    Uses ``page.extract_text() or ""`` with default arguments (fidelity
    requirement — do not add parameters). Any open/parse failure is captured
    as a ``failed`` result with a sanitized error; no exception escapes.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page_texts = [page.extract_text() or "" for page in pdf.pages]
    except Exception as exc:  # noqa: BLE001 - any failure becomes a failed artifact
        return ExtractionResult(
            status=STATUS_FAILED,
            error=_sanitize_error(exc, pdf_path),
        )

    per_page_chars = [len(text) for text in page_texts]
    status, warnings = _status_and_warnings(page_texts, low_text_threshold)
    return ExtractionResult(
        status=status,
        page_texts=page_texts,
        page_count=len(page_texts),
        per_page_chars=per_page_chars,
        warnings=warnings,
        text_hash=compute_text_hash(page_texts),
    )


def _extractor_version() -> str:
    """pdfplumber version read at runtime (recorded in every artifact)."""
    return version("pdfplumber")


def build_artifact(
    result: ExtractionResult, *, source_sha256: str, original_filename: str
) -> dict[str, object]:
    """Assemble the JSON artifact for one source PDF.

    Every field is always present. On ``failed``, ``pages``/``per_page_chars``
    are empty, ``page_count`` is 0, ``text_hash`` is null, and ``error``
    carries the sanitized code/message; otherwise ``error`` is null.
    """
    return {
        "source_sha256": source_sha256,
        "original_filename": original_filename,
        "extractor": {"name": EXTRACTOR_NAME, "version": _extractor_version()},
        "extracted_at": datetime.now(UTC).isoformat(),
        "status": result.status,
        "page_count": result.page_count,
        "pages": result.page_texts,
        "per_page_chars": result.per_page_chars,
        "text_hash": result.text_hash,
        "warnings": result.warnings,
        "error": result.error,
    }


def artifact_filename(source_sha256: str) -> str:
    """Deterministic artifact name derived from the source file hash."""
    return f"{source_sha256}.json"


# Statuses reported in the run summary, in a stable display order.
_SUMMARY_ORDER = (
    STATUS_SUCCESS,
    STATUS_PARTIAL,
    STATUS_NEEDS_OCR_OR_REVIEW,
    STATUS_FAILED,
)


def _pdf_paths(path: Path) -> list[Path]:
    """PDFs to process: a single file, or every ``*.pdf`` in a directory.

    Directory search is non-recursive (matches the evaluate-extractors
    convention); results are sorted for deterministic processing order.
    """
    if path.is_file():
        return [path]
    return sorted(
        p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"
    )


def run_extraction(
    path: Path,
    output_dir: Path,
    *,
    low_text_threshold: int = DEFAULT_LOW_TEXT_THRESHOLD,
) -> int:
    """Extract every PDF under ``path`` and write one artifact per file.

    Resolves and creates ``output_dir`` here (run boundary, never at import),
    refusing any location inside a git working tree. Individual file failures
    are recorded as ``failed`` artifacts, not fatal. Prints counts-by-status
    to stdout; logs carry only ids, counts, statuses, page numbers, and
    durations — never extracted text. Returns a process exit code.
    """
    if not path.exists():
        logger.error("input path does not exist", extra={"path": str(path)})
        return 2
    if path.is_dir():
        pdf_paths = _pdf_paths(path)
        if not pdf_paths:
            logger.error(
                "input directory contains no PDF files (search is non-recursive)",
                extra={"path": str(path)},
            )
            return 2
    elif path.suffix.lower() != ".pdf":
        logger.error("input file is not a PDF", extra={"path": str(path)})
        return 2
    else:
        pdf_paths = [path]

    if inside_git_worktree(output_dir):
        logger.error(
            "output dir resolves to a path inside a git working tree; "
            "choose a location outside any repository",
            extra={"output_dir": str(output_dir)},
        )
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "starting extraction",
        extra={"file_count": len(pdf_paths), "output_dir": str(output_dir)},
    )

    counts = {status: 0 for status in _SUMMARY_ORDER}
    for pdf_path in pdf_paths:
        source_sha256 = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        start = time.perf_counter()
        result = extract(pdf_path, low_text_threshold=low_text_threshold)
        duration = time.perf_counter() - start
        artifact = build_artifact(
            result,
            source_sha256=source_sha256,
            original_filename=pdf_path.name,
        )
        out_path = output_dir / artifact_filename(source_sha256)
        out_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
        counts[result.status] += 1
        logger.info(
            "extracted",
            extra={
                "file": source_sha256[:16],
                "status": result.status,
                "pages": result.page_count,
                "duration_seconds": duration,
            },
        )

    summary = " ".join(f"{status}={counts[status]}" for status in _SUMMARY_ORDER)
    print(summary)
    logger.info("extraction complete", extra={"file_count": len(pdf_paths)})
    return 0
