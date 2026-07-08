"""Evaluation harness comparing candidate PDF text extractors (Task 5.1).

Runs each selected extractor over a flat (non-recursive) directory of
fixture PDFs and writes comparison artifacts so a human can make the
Sprint 1 extractor decision.

Privacy rules (hard):

- Fixture filenames are real docket numbers. All artifacts and logs are
  keyed by a SHA-256 content-hash prefix; filenames appear only in
  ``file-index.json`` inside the output dir, never in logs or reports.
- Extracted text is never logged. It reaches disk only when ``dump_text``
  is set, and the output dir must live outside any git working tree.
"""

import hashlib
import json
import logging
import time
from collections.abc import Sequence
from pathlib import Path

from pipeline.evaluation.extractors import EXTRACTORS

logger = logging.getLogger("pipeline.evaluation")

SECTION_KEYWORDS = (
    "CASE INFORMATION",
    "STATUS INFORMATION",
    "CALENDAR EVENTS",
    "DEFENDANT INFORMATION",
    "CASE PARTICIPANTS",
    "CHARGES",
    "DISPOSITION SENTENCING/PENALTIES",
    "COMMONWEALTH INFORMATION",
    "ENTRIES",
)

HASH_PREFIX_LEN = 16
_ERROR_MESSAGE_MAX_LEN = 200

# Third-party PDF loggers can echo raw file bytes into their own log records
# (e.g. pypdf's "invalid pdf header: b'...'"), which would leak docket
# content through our root handler. Their diagnostics surface via the
# sanitized error records instead.
_LIBRARY_LOGGERS = ("pypdf", "pdfminer", "pdfplumber", "pymupdf", "fitz")


def _silence_library_loggers() -> None:
    for name in _LIBRARY_LOGGERS:
        logging.getLogger(name).propagate = False


def inside_git_worktree(path: Path) -> bool:
    """True if ``path`` or any ancestor contains a ``.git`` entry.

    ``.git`` may be a plain file rather than a directory (linked worktrees,
    submodules), so this checks for any filesystem entry, not just a dir.
    """
    resolved = path.resolve()
    return any(
        (candidate / ".git").exists() for candidate in (resolved, *resolved.parents)
    )


def _sanitize_error(exc: BaseException, path: Path) -> dict[str, str]:
    """Error record safe for reports: no extracted text, no fixture names.

    Library messages sometimes embed the file path (a real docket number),
    so any occurrence of the path, filename, or stem is redacted.
    """
    message = str(exc)
    for leak in (str(path), str(path.resolve()), path.name, path.stem):
        if leak:
            message = message.replace(leak, "<redacted>")
    if len(message) > _ERROR_MESSAGE_MAX_LEN:
        message = message[:_ERROR_MESSAGE_MAX_LEN] + "…"
    return {"type": type(exc).__name__, "message": message}


def _metrics_from_pages(pages: list[str], duration: float) -> dict[str, object]:
    lengths = [len(page) for page in pages]
    empty_indices = [i for i, page in enumerate(pages) if not page.strip()]
    upper = "\n".join(pages).upper()
    return {
        "page_count": len(pages),
        "total_chars": sum(lengths),
        "per_page_chars": lengths,
        "duration_seconds": duration,
        "empty_pages": {"count": len(empty_indices), "indices": empty_indices},
        "needs_ocr_or_review": len(empty_indices) == len(pages),
        "section_hits": {keyword: upper.count(keyword) for keyword in SECTION_KEYWORDS},
        "error": None,
    }


def _metrics_from_error(error: dict[str, str], duration: float) -> dict[str, object]:
    return {
        "page_count": None,
        "total_chars": None,
        "per_page_chars": None,
        "duration_seconds": duration,
        "empty_pages": None,
        "needs_ocr_or_review": True,
        "section_hits": None,
        "error": error,
    }


def _rollup(results: dict[str, dict[str, object]]) -> dict[str, object]:
    total = len(results)
    total_duration = sum(m["duration_seconds"] for m in results.values())
    succeeded = [m for m in results.values() if m["error"] is None]
    return {
        "total_files": total,
        "failures": total - len(succeeded),
        "total_duration_seconds": total_duration,
        "mean_duration_seconds": total_duration / total if total else 0.0,
        "needs_ocr_or_review": sum(
            1 for m in results.values() if m["needs_ocr_or_review"]
        ),
        "section_hit_rates": {
            keyword: (
                sum(1 for m in succeeded if m["section_hits"][keyword] > 0)
                / len(succeeded)
                if succeeded
                else 0.0
            )
            for keyword in SECTION_KEYWORDS
        },
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def run_evaluation(
    fixtures_dir: Path,
    output_dir: Path,
    extractor_names: Sequence[str],
    dump_text: bool = False,
) -> int:
    """Run the selected extractors over every PDF in ``fixtures_dir``.

    Returns a process exit code: 0 on completion (individual file failures
    are recorded, not fatal), 2 on invalid arguments.
    """
    if not fixtures_dir.is_dir():
        logger.error(
            "fixtures dir does not exist or is not a directory",
            extra={"fixtures_dir": str(fixtures_dir)},
        )
        return 2
    pdf_paths = sorted(
        p for p in fixtures_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"
    )
    if not pdf_paths:
        logger.error(
            "fixtures dir contains no PDF files (search is non-recursive)",
            extra={"fixtures_dir": str(fixtures_dir)},
        )
        return 2
    if inside_git_worktree(output_dir):
        logger.error(
            "output dir resolves to a path inside a git working tree; "
            "choose a location outside any repository",
            extra={"output_dir": str(output_dir)},
        )
        return 2

    unknown = [name for name in extractor_names if name not in EXTRACTORS]
    if unknown or not extractor_names:
        logger.error("unknown extractors requested", extra={"unknown": unknown})
        return 2

    _silence_library_loggers()
    output_dir.mkdir(parents=True, exist_ok=True)
    files = [
        (hashlib.sha256(path.read_bytes()).hexdigest()[:HASH_PREFIX_LEN], path)
        for path in pdf_paths
    ]
    logger.info(
        "starting extractor evaluation",
        extra={
            "fixtures_dir": str(fixtures_dir),
            "file_count": len(files),
            "extractors": list(extractor_names),
            "dump_text": dump_text,
        },
    )

    summary: dict[str, object] = {"extractors": {}}
    for name in extractor_names:
        extractor = EXTRACTORS[name]
        results: dict[str, dict[str, object]] = {}
        for digest, path in files:
            start = time.perf_counter()
            try:
                pages = [page or "" for page in extractor(path)]
            except Exception as exc:
                duration = time.perf_counter() - start
                error = _sanitize_error(exc, path)
                results[digest] = _metrics_from_error(error, duration)
                logger.warning(
                    "extraction failed",
                    extra={
                        "extractor": name,
                        "file": digest,
                        "error_type": error["type"],
                    },
                )
                continue
            duration = time.perf_counter() - start
            results[digest] = _metrics_from_pages(pages, duration)
            if dump_text:
                text_dir = output_dir / "text" / name
                text_dir.mkdir(parents=True, exist_ok=True)
                dump = "".join(
                    (f"\n\n--- page {i + 1} ---\n\n" if i else "") + page
                    for i, page in enumerate(pages)
                )
                (text_dir / f"{digest}.txt").write_text(dump)
            logger.info(
                "extracted",
                extra={
                    "extractor": name,
                    "file": digest,
                    "pages": len(pages),
                    "duration_seconds": duration,
                },
            )
        _write_json(
            output_dir / f"report-{name}.json",
            {"extractor": name, "file_count": len(files), "files": results},
        )
        summary["extractors"][name] = _rollup(results)

    _write_json(
        output_dir / "file-index.json",
        {digest: path.name for digest, path in files},
    )
    _write_json(output_dir / "summary.json", summary)
    logger.info(
        "evaluation complete",
        extra={"file_count": len(files), "extractors": list(extractor_names)},
    )
    return 0
