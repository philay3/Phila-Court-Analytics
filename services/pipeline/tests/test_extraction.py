"""Tests for the production extraction stage (Task 16.2).

No real dockets: tiny synthetic PDFs are generated at test time with PyMuPDF
(ADR 0001 permits pymupdf in tests — it restricts production modules only).
All output goes to pytest ``tmp_path``; nothing touches ``~/court-data/``.
"""

import ast
import json
from pathlib import Path

import pymupdf

from pipeline import cli
from pipeline.extraction import (
    DEFAULT_LOW_TEXT_THRESHOLD,
    ERROR_UNREADABLE_PDF,
    STATUS_FAILED,
    STATUS_NEEDS_OCR_OR_REVIEW,
    STATUS_PARTIAL,
    STATUS_SUCCESS,
    WARNING_EMPTY_PAGE,
    WARNING_LOW_TEXT_PAGE,
    _status_and_warnings,
    artifact_filename,
    build_artifact,
    compute_text_hash,
    extract,
    run_extraction,
)

# Body text distinctive enough to detect if it ever leaks into logs/console.
SENTINEL = "SYNTHETIC-DOCKET-BODY-TEXT-XYZZY"
# A page's worth of content that clears the 100-char threshold comfortably.
LONG = (
    "The Commonwealth of Pennsylvania case record spans several lines of "
    "docket text here, well past the low-text threshold for a real page. "
) * 2
SHORT = "Short page."
# ~50 stripped chars: below the default (100) but above a --threshold 20 run.
MID = "This mid-length docket line is about fifty chars."


def _write_pdf(path: Path, page_texts: list[str]) -> None:
    """Write a PDF with one page per string; empty string -> blank page."""
    doc = pymupdf.open()
    for text in page_texts:
        page = doc.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(36, 36, 560, 750), text, fontsize=11)
    doc.save(path)
    doc.close()


def _pdf(tmp_path: Path, name: str, page_texts: list[str]) -> Path:
    path = tmp_path / name
    _write_pdf(path, page_texts)
    return path


# --- extraction logic -------------------------------------------------------


def test_multi_page_success_order_texts_counts_hash(tmp_path):
    pages_in = [f"PAGE-MARKER-{i} {LONG}" for i in range(3)]
    pdf = _pdf(tmp_path, "doc.pdf", pages_in)

    result = extract(pdf)

    assert result.status == STATUS_SUCCESS
    assert result.warnings == []
    assert result.page_count == 3
    # Page order preserved.
    for i in range(3):
        assert f"PAGE-MARKER-{i}" in result.page_texts[i]
    # per_page_chars is the raw len(text) of each page.
    assert result.per_page_chars == [len(t) for t in result.page_texts]
    # text_hash matches the decision-7 construction over the page texts.
    assert result.text_hash == compute_text_hash(result.page_texts)


def test_empty_page_emits_warning(tmp_path):
    pdf = _pdf(tmp_path, "doc.pdf", [LONG, ""])

    result = extract(pdf)

    assert result.status == STATUS_PARTIAL
    assert {"code": WARNING_EMPTY_PAGE, "page": 2} in result.warnings


def test_low_text_partial_path(tmp_path):
    pdf = _pdf(tmp_path, "doc.pdf", [LONG, SHORT])

    result = extract(pdf)

    assert result.status == STATUS_PARTIAL
    codes = {(w["code"], w["page"]) for w in result.warnings}
    assert (WARNING_LOW_TEXT_PAGE, 2) in codes


def test_all_below_threshold_needs_ocr_or_review(tmp_path):
    pdf = _pdf(tmp_path, "doc.pdf", [SHORT, ""])

    result = extract(pdf)

    assert result.status == STATUS_NEEDS_OCR_OR_REVIEW


def test_threshold_override_honored(tmp_path):
    pdf = _pdf(tmp_path, "doc.pdf", [MID])

    # Default threshold (100): the single mid-length page is below it.
    assert extract(pdf).status == STATUS_NEEDS_OCR_OR_REVIEW
    # Lowering the threshold to 20 promotes the same page to success.
    promoted = extract(pdf, low_text_threshold=20)
    assert promoted.status == STATUS_SUCCESS
    assert promoted.warnings == []


def test_threshold_compares_stripped_not_raw_length():
    """Whitespace never counts as content: a whitespace-only page above 100
    raw chars is below-threshold, and a whitespace-padded page whose raw
    length exceeds the threshold is still flagged by its stripped length."""
    # 150 raw whitespace chars, zero content -> treated as an empty page.
    status, warnings = _status_and_warnings([" " * 150], DEFAULT_LOW_TEXT_THRESHOLD)
    assert status == STATUS_NEEDS_OCR_OR_REVIEW
    assert warnings == [{"code": WARNING_EMPTY_PAGE, "page": 1}]

    # 122 raw chars but only 2 of content -> low-text, char_count is stripped.
    status, warnings = _status_and_warnings([LONG, " " * 120 + "hi"], 100)
    assert status == STATUS_PARTIAL
    assert warnings == [{"code": WARNING_LOW_TEXT_PAGE, "page": 2, "char_count": 2}]


# --- text hash --------------------------------------------------------------


def test_text_hash_deterministic_and_order_sensitive():
    assert compute_text_hash(["alpha", "beta"]) == compute_text_hash(["alpha", "beta"])
    assert compute_text_hash(["alpha", "beta"]) != compute_text_hash(["beta", "alpha"])


def test_same_pdf_same_hash(tmp_path):
    pages_in = [f"PAGE-MARKER-{i} {LONG}" for i in range(2)]
    a = _pdf(tmp_path, "a.pdf", pages_in)
    b = _pdf(tmp_path, "b.pdf", pages_in)
    assert extract(a).text_hash == extract(b).text_hash


# --- failed path ------------------------------------------------------------


def test_unreadable_file_failed_artifact_no_text_no_raise(tmp_path):
    bad = tmp_path / "corrupt.pdf"
    bad.write_bytes(b"JUNKBYTES this is not a pdf at all")
    out = tmp_path / "out"

    # No exception escapes; exit code is 0 (a per-file failure is recorded).
    assert run_extraction(bad, out) == 0

    artifact = json.loads((out / artifact_filename(_sha256(bad))).read_text())
    assert artifact["status"] == STATUS_FAILED
    assert artifact["error"]["code"] == ERROR_UNREADABLE_PDF
    assert artifact["error"]["message"]
    assert artifact["pages"] == []
    assert artifact["per_page_chars"] == []
    assert artifact["page_count"] == 0
    # text_hash is pinned to null on a failed artifact.
    assert artifact["text_hash"] is None


def test_extract_does_not_raise_on_junk(tmp_path):
    bad = tmp_path / "corrupt.pdf"
    bad.write_bytes(b"not a pdf")
    result = extract(bad)
    assert result.status == STATUS_FAILED
    assert result.page_texts == []


# --- artifact schema --------------------------------------------------------


def test_artifact_schema_completeness(tmp_path):
    pdf = _pdf(tmp_path, "doc.pdf", [LONG, SHORT])
    result = extract(pdf)
    artifact = build_artifact(
        result, source_sha256="deadbeef", original_filename="doc.pdf"
    )

    assert set(artifact) == {
        "source_sha256",
        "original_filename",
        "extractor",
        "extracted_at",
        "status",
        "page_count",
        "pages",
        "per_page_chars",
        "text_hash",
        "warnings",
        "error",
    }
    assert artifact["extractor"]["name"] == "pdfplumber"
    # Version is read at runtime and matches the pinned pdfplumber.
    assert artifact["extractor"]["version"] == "0.11.10"
    assert artifact["source_sha256"] == "deadbeef"
    assert artifact["original_filename"] == "doc.pdf"
    assert artifact["error"] is None


# --- run boundary -----------------------------------------------------------


def test_run_extraction_directory_writes_one_artifact_per_file(tmp_path, capsys):
    src = tmp_path / "pdfs"
    src.mkdir()
    _write_pdf(src / "a.pdf", [LONG])
    _write_pdf(src / "b.pdf", [SHORT])
    out = tmp_path / "out"

    assert run_extraction(src, out) == 0

    artifacts = sorted(out.glob("*.json"))
    assert len(artifacts) == 2
    summary = capsys.readouterr().out.strip()
    # Counts-by-status only.
    assert summary == (
        f"{STATUS_SUCCESS}=1 {STATUS_PARTIAL}=0 "
        f"{STATUS_NEEDS_OCR_OR_REVIEW}=1 {STATUS_FAILED}=0"
    )


def test_run_extraction_refuses_output_inside_git_worktree(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    out = repo / "out"
    pdf = _pdf(tmp_path, "doc.pdf", [LONG])

    assert run_extraction(pdf, out) == 2
    assert not out.exists()


# --- no raw text in logs or console -----------------------------------------


def test_no_raw_docket_text_in_logs_or_console(tmp_path, capsys):
    src = tmp_path / "pdfs"
    src.mkdir()
    _write_pdf(src / "MC-51-CR-0001234-2024.pdf", [f"{LONG} {SENTINEL}"])
    out = tmp_path / "out"

    # Full CLI path so the real logging handler (stderr) is exercised.
    assert cli.main(["extract-text", str(src), "--output-dir", str(out)]) == 0

    captured = capsys.readouterr()
    assert SENTINEL not in captured.err  # logs
    assert SENTINEL not in captured.out  # run summary
    # The text does reach the artifact — proving extraction ran, and that the
    # only place raw text lands is the out-of-repo artifact.
    artifact_text = next(out.glob("*.json")).read_text()
    assert SENTINEL in artifact_text


# --- production import discipline (ADR 0001) --------------------------------

_PROD_ROOT = Path(__file__).resolve().parents[1] / "src" / "pipeline"
_FORBIDDEN = {"pymupdf", "pypdf", "fitz"}


def _production_module_files():
    for path in _PROD_ROOT.rglob("*.py"):
        # The evaluation harness is the sanctioned home for pymupdf/pypdf.
        if "evaluation" in path.relative_to(_PROD_ROOT).parts:
            continue
        yield path


def test_no_pymupdf_or_pypdf_in_production_modules():
    offenders = []
    for path in _production_module_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module.split(".")[0]] if node.module else []
            else:
                continue
            hits = _FORBIDDEN.intersection(names)
            if hits:
                offenders.append(f"{path.name}: {sorted(hits)}")
    assert not offenders, f"forbidden imports in production modules: {offenders}"


# --- helpers ----------------------------------------------------------------


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
