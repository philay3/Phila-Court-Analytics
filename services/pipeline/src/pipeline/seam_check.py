"""Extraction-seam equivalence check (Task 17.1).

Proves the production extraction stage (Task 16.2) reproduces Capstone's
pdfplumber reference text line-for-line, before any parser code ports. The
comparator imports and calls the *same* extraction code path production uses
(``pipeline.extraction.extract``) — no reimplementation — and diffs its
output against one reference JSON file per PDF.

Reference-file contract (decision 3)::

    {"source_file": str, "sha256": str, "pdfplumber_version": str,
     "pages": [str, ...]}

Comparison order per docket (decision 4): (a) source-hash gate — a mismatch is
a reported *failure*, not a diff; (b) page-count equality; (c) per-page,
line-level exact string comparison (split on ``\\n``, no normalization). Any
normalization judgment is human triage, not the tool's.

Privacy rules (hard):

- Console/log output carries ONLY counts, statuses, hash-prefix ids, page
  numbers, and line numbers — never docket stems, never docket text. (The
  task's decision 7 said "docket stems"; that wording was a defect. Docket
  numbers are defendant-identifying, so the CLAUDE.md hard rule and the
  ``extraction.py`` / ``harness.py`` hash-prefix precedent govern.)
- Docket stems and divergence content are confined to the out-of-repo report
  artifacts under ``report_dir`` (default ``~/court-data/seam-report/``). A
  ``report_dir`` inside a git working tree is refused.
- Per-docket exception capture (decision 6): any failure on a single PDF —
  including a malformed reference file — is caught, recorded loudly as a
  ``failed`` outcome, and the run continues. One bad docket never aborts the
  corpus run.

The tool reports; it does not decide (decision 9). A completed run returns 0
regardless of divergences; triage is human work recorded in the worklog.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from pipeline.extraction import STATUS_FAILED as EXTRACTION_STATUS_FAILED
from pipeline.extraction import extract
from pipeline.manual_import import DOCKET_NUMBER_RE
from pipeline.paths import inside_git_worktree

logger = logging.getLogger("pipeline.seam_check")

EXTRACTOR_NAME = "pdfplumber"
HASH_PREFIX_LEN = 16

# Per-docket outcome vocabulary: exactly one of these per PDF.
STATUS_EQUIVALENT = "equivalent"
STATUS_DIVERGENT = "divergent"
STATUS_FAILED = "failed"
STATUS_MISSING_REFERENCE = "missing_reference"

# Stable display order for the summary and per-court breakdown.
_SUMMARY_ORDER = (
    STATUS_EQUIVALENT,
    STATUS_DIVERGENT,
    STATUS_FAILED,
    STATUS_MISSING_REFERENCE,
)

# Reasons attached to a ``failed`` outcome.
REASON_HASH_MISMATCH = "hash_mismatch"
REASON_MALFORMED_REFERENCE = "malformed_reference"
REASON_EXTRACTION_FAILED = "extraction_failed"
REASON_EXCEPTION = "exception"

# Divergence kinds attached to a ``divergent`` outcome.
DIVERGENCE_PAGE_COUNT = "page_count"
DIVERGENCE_LINE = "line"

# GitHub Actions sets both; either presence means "do not run over local
# court data" (Task 19.2 precedent). Read at the run boundary, never at import.
_CI_ENV_VARS = ("CI", "GITHUB_ACTIONS")


class MalformedReferenceError(Exception):
    """Raised when a reference JSON file does not match the required shape.

    Carries only structural context (key names, type names) — never file
    content — so it is safe to surface in a report entry.
    """


@dataclass
class DocketResult:
    """Outcome of comparing one PDF against its reference file.

    ``divergences`` and the page counts carry the full detail (including
    differing line content) that lands ONLY in the out-of-repo report.
    """

    stem: str
    source_hash: str | None
    status: str
    reason: str | None = None
    divergences: list[dict[str, object]] = field(default_factory=list)
    our_page_count: int | None = None
    reference_page_count: int | None = None


def running_in_ci() -> bool:
    """True if a CI environment variable is set (read at call time)."""
    return any(os.getenv(name) for name in _CI_ENV_VARS)


def load_reference(path: Path) -> dict[str, object]:
    """Read and shape-validate one reference JSON file (decision 3).

    Raises ``MalformedReferenceError`` on any structural problem. The error
    message names the offending key/type only — never file content.
    """
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise MalformedReferenceError(
            f"reference file is not readable JSON: {type(exc).__name__}"
        ) from exc
    if not isinstance(raw, dict):
        raise MalformedReferenceError("reference root is not a JSON object")
    required: dict[str, type] = {
        "source_file": str,
        "sha256": str,
        "pdfplumber_version": str,
        "pages": list,
    }
    for key, expected_type in required.items():
        if key not in raw:
            raise MalformedReferenceError(f"reference missing required key: {key}")
        if not isinstance(raw[key], expected_type):
            raise MalformedReferenceError(
                f"reference key '{key}' is not of type {expected_type.__name__}"
            )
    if not all(isinstance(page, str) for page in raw["pages"]):
        raise MalformedReferenceError("reference 'pages' entries must all be strings")
    return raw


def compare_docket(
    pdf_path: Path, reference: dict[str, object], source_hash: str | None
) -> DocketResult:
    """Compare one PDF against its reference in the decision-4 order.

    (a) source-hash gate; (b) page-count equality; (c) line-level exact
    compare. A hash mismatch short-circuits to a ``failed`` outcome and never
    runs extraction or a diff.
    """
    stem = pdf_path.stem

    # (a) source-hash gate — a mismatch means we and Capstone read different
    # bytes, so a line diff would be meaningless.
    if source_hash != reference["sha256"]:
        return DocketResult(
            stem=stem,
            source_hash=source_hash,
            status=STATUS_FAILED,
            reason=REASON_HASH_MISMATCH,
        )

    # Production code path — the same call extraction production uses.
    result = extract(pdf_path)
    if result.status == EXTRACTION_STATUS_FAILED:
        return DocketResult(
            stem=stem,
            source_hash=source_hash,
            status=STATUS_FAILED,
            reason=REASON_EXTRACTION_FAILED,
        )

    our_pages = result.page_texts
    reference_pages = [str(page) for page in reference["pages"]]

    # (b) page-count equality gate.
    if len(our_pages) != len(reference_pages):
        return DocketResult(
            stem=stem,
            source_hash=source_hash,
            status=STATUS_DIVERGENT,
            our_page_count=len(our_pages),
            reference_page_count=len(reference_pages),
            divergences=[
                {
                    "type": DIVERGENCE_PAGE_COUNT,
                    "ours": len(our_pages),
                    "reference": len(reference_pages),
                }
            ],
        )

    # (c) per-page, line-level exact compare. No normalization, no whitespace
    # forgiveness — any judgment about acceptable differences is human triage.
    divergences: list[dict[str, object]] = []
    for page_index, (our_text, reference_text) in enumerate(
        zip(our_pages, reference_pages, strict=True)
    ):
        our_lines = our_text.split("\n")
        reference_lines = reference_text.split("\n")
        for line_index in range(max(len(our_lines), len(reference_lines))):
            our_line = our_lines[line_index] if line_index < len(our_lines) else None
            reference_line = (
                reference_lines[line_index]
                if line_index < len(reference_lines)
                else None
            )
            if our_line != reference_line:
                divergences.append(
                    {
                        "type": DIVERGENCE_LINE,
                        "page": page_index + 1,
                        "line": line_index + 1,
                        "ours": our_line,
                        "reference": reference_line,
                    }
                )

    return DocketResult(
        stem=stem,
        source_hash=source_hash,
        status=STATUS_DIVERGENT if divergences else STATUS_EQUIVALENT,
        divergences=divergences,
        our_page_count=len(our_pages),
        reference_page_count=len(reference_pages),
    )


def _check_one(pdf_path: Path, reference_dir: Path) -> tuple[DocketResult, str | None]:
    """Resolve, load, and compare one PDF. Never raises.

    Returns the outcome plus the reference's recorded pdfplumber version (or
    ``None`` when unavailable). Any exception — a malformed reference or an
    unexpected failure — becomes a ``failed`` outcome so the run continues.
    """
    stem = pdf_path.stem
    try:
        source_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    except OSError:
        source_hash = None

    reference_path = reference_dir / f"{stem}.json"
    if not reference_path.exists():
        return (
            DocketResult(
                stem=stem, source_hash=source_hash, status=STATUS_MISSING_REFERENCE
            ),
            None,
        )

    try:
        reference = load_reference(reference_path)
    except MalformedReferenceError:
        return (
            DocketResult(
                stem=stem,
                source_hash=source_hash,
                status=STATUS_FAILED,
                reason=REASON_MALFORMED_REFERENCE,
            ),
            None,
        )

    reference_version = str(reference["pdfplumber_version"])
    try:
        return compare_docket(pdf_path, reference, source_hash), reference_version
    except Exception:  # noqa: BLE001 - one bad docket must not abort the run
        return (
            DocketResult(
                stem=stem,
                source_hash=source_hash,
                status=STATUS_FAILED,
                reason=REASON_EXCEPTION,
            ),
            reference_version,
        )


def _court_of(stem: str) -> str:
    """CP / MC by the canonical UJS docket-number pattern; else 'unknown'."""
    match = DOCKET_NUMBER_RE.match(stem)
    return match.group(1) if match else "unknown"


def _hash_prefix(source_hash: str | None) -> str:
    return (source_hash or "unknown")[:HASH_PREFIX_LEN]


def _docket_entry(result: DocketResult) -> dict[str, object]:
    """Full per-docket report entry (out-of-repo only — may carry stem/text)."""
    entry: dict[str, object] = {
        "docket": result.stem,
        "hash_prefix": _hash_prefix(result.source_hash),
        "court": _court_of(result.stem),
        "status": result.status,
    }
    if result.reason is not None:
        entry["reason"] = result.reason
    if result.divergences:
        entry["divergences"] = result.divergences
    if result.our_page_count is not None:
        entry["our_page_count"] = result.our_page_count
    if result.reference_page_count is not None:
        entry["reference_page_count"] = result.reference_page_count
    return entry


def _render_summary(report: dict[str, object]) -> str:
    """Human-readable summary: positions only, no divergence content.

    Lives out-of-repo so it keeps docket stems (with hash-prefix ids alongside
    for cross-referencing logs), but the differing line *content* stays in the
    JSON report exclusively.
    """
    header = report["header"]
    totals = report["totals"]
    by_court = report["by_court"]
    lines: list[str] = ["Extraction-Seam Equivalence Check (Task 17.1)", ""]
    lines.append(f"generated_at: {header['generated_at']}")
    lines.append(f"our pdfplumber: {header['ours_pdfplumber_version']}")
    capstone = ", ".join(header["capstone_pdfplumber_versions"]) or "(none)"
    lines.append(f"capstone pdfplumber: {capstone}")
    lines.append(f"version_mismatch: {header['version_mismatch']}")
    lines.append("")
    lines.append("Totals:")
    for key in (
        "corpus_pdfs",
        "compared",
        "equivalent",
        "divergent",
        "failed",
        "missing_reference",
    ):
        lines.append(f"  {key}: {totals[key]}")
    lines.append("")
    lines.append("By court:")
    for court in sorted(by_court):
        counts = by_court[court]
        rendered = " ".join(f"{status}={counts[status]}" for status in _SUMMARY_ORDER)
        lines.append(f"  {court}: {rendered}")
    lines.append("")
    lines.append(
        "Dockets needing triage (positions only; content in seam-report.json):"
    )
    for docket in report["dockets"]:
        reason = f" reason={docket['reason']}" if docket.get("reason") else ""
        lines.append(
            f"  [{docket['hash_prefix']}] {docket['docket']} "
            f"({docket['court']}) {docket['status']}{reason}"
        )
        for divergence in docket.get("divergences", []):
            if divergence["type"] == DIVERGENCE_LINE:
                lines.append(
                    f"      page {divergence['page']} line {divergence['line']}"
                )
            elif divergence["type"] == DIVERGENCE_PAGE_COUNT:
                lines.append(
                    f"      page_count ours={divergence['ours']} "
                    f"reference={divergence['reference']}"
                )
    return "\n".join(lines) + "\n"


def run_seam_check(corpus_dir: Path, reference_dir: Path, report_dir: Path) -> int:
    """Compare every PDF in ``corpus_dir`` against its reference file.

    Writes a machine-readable ``seam-report.json`` and a human-readable
    ``seam-report.txt`` under ``report_dir`` (refused if inside a git working
    tree). Prints counts-by-status to stdout; logs carry only hash-prefix ids,
    statuses, and counts. Returns a process exit code: 0 on a completed run
    (divergences are recorded, not fatal), 2 on invalid arguments.
    """
    if not corpus_dir.is_dir():
        logger.error(
            "corpus dir does not exist or is not a directory",
            extra={"corpus_dir": str(corpus_dir)},
        )
        return 2
    if not reference_dir.is_dir():
        logger.error(
            "reference dir does not exist or is not a directory",
            extra={"reference_dir": str(reference_dir)},
        )
        return 2
    if inside_git_worktree(report_dir):
        logger.error(
            "report dir resolves to a path inside a git working tree; "
            "choose a location outside any repository",
            extra={"report_dir": str(report_dir)},
        )
        return 2

    pdf_paths = sorted(
        p for p in corpus_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"
    )
    if not pdf_paths:
        logger.error(
            "corpus dir contains no PDF files (search is non-recursive)",
            extra={"corpus_dir": str(corpus_dir)},
        )
        return 2

    report_dir.mkdir(parents=True, exist_ok=True)
    ours_version = version("pdfplumber")
    logger.info(
        "starting seam check",
        extra={"corpus_dir": str(corpus_dir), "file_count": len(pdf_paths)},
    )

    docket_results: list[DocketResult] = []
    reference_versions: set[str] = set()
    for pdf_path in pdf_paths:
        result, reference_version = _check_one(pdf_path, reference_dir)
        docket_results.append(result)
        if reference_version is not None:
            reference_versions.add(reference_version)
        logger.info(
            "checked",
            extra={
                "file": _hash_prefix(result.source_hash),
                "status": result.status,
                "reason": result.reason or "",
                "divergences": len(result.divergences),
            },
        )

    counts = {status: 0 for status in _SUMMARY_ORDER}
    by_court: dict[str, dict[str, int]] = {}
    for result in docket_results:
        counts[result.status] += 1
        bucket = by_court.setdefault(
            _court_of(result.stem), {status: 0 for status in _SUMMARY_ORDER}
        )
        bucket[result.status] += 1

    compared = (
        counts[STATUS_EQUIVALENT] + counts[STATUS_DIVERGENT] + counts[STATUS_FAILED]
    )
    capstone_versions = sorted(reference_versions)
    version_mismatch = bool(reference_versions) and (
        len(reference_versions) > 1 or ours_version not in reference_versions
    )
    if version_mismatch:
        logger.warning(
            "pdfplumber version mismatch: our extractor differs from Capstone "
            "references (first suspect for any divergence)",
            extra={"ours": ours_version, "capstone": capstone_versions},
        )

    report: dict[str, object] = {
        "header": {
            "ours_pdfplumber_version": ours_version,
            "capstone_pdfplumber_versions": capstone_versions,
            "version_mismatch": version_mismatch,
            "corpus_dir": str(corpus_dir),
            "reference_dir": str(reference_dir),
            "generated_at": datetime.now(UTC).isoformat(),
        },
        "totals": {
            "corpus_pdfs": len(pdf_paths),
            "compared": compared,
            "equivalent": counts[STATUS_EQUIVALENT],
            "divergent": counts[STATUS_DIVERGENT],
            "failed": counts[STATUS_FAILED],
            "missing_reference": counts[STATUS_MISSING_REFERENCE],
        },
        "by_court": by_court,
        "dockets": [
            _docket_entry(result)
            for result in docket_results
            if result.status != STATUS_EQUIVALENT
        ],
    }

    (report_dir / "seam-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    (report_dir / "seam-report.txt").write_text(_render_summary(report))

    summary = " ".join(f"{status}={counts[status]}" for status in _SUMMARY_ORDER)
    print(summary)
    logger.info("seam check complete", extra={"file_count": len(pdf_paths)})
    return 0
