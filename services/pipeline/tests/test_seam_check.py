"""Tests for the extraction-seam equivalence check (Task 17.1).

Synthetic data only: tiny PDFs are generated at test time with PyMuPDF (ADR
0001 permits pymupdf in tests) and reference JSON is hand-built from our own
extractor's output, so we exercise the comparator's logic — not real dockets.
All output goes to pytest ``tmp_path``; nothing touches ``~/court-data/``.
"""

import ast
import json
from pathlib import Path

import pymupdf

from pipeline import cli, extraction, seam_check
from pipeline.seam_check import (
    DIVERGENCE_LINE,
    DIVERGENCE_PAGE_COUNT,
    REASON_EXCEPTION,
    REASON_EXTRACTION_FAILED,
    REASON_HASH_MISMATCH,
    REASON_MALFORMED_REFERENCE,
    STATUS_DIVERGENT,
    STATUS_EQUIVALENT,
    STATUS_FAILED,
    STATUS_MISSING_REFERENCE,
    run_seam_check,
)

# Distinctive body text: if it ever reaches stdout/stderr the privacy test fails.
SENTINEL = "SYNTHETIC-DOCKET-BODY-TEXT-XYZZY"
LONG = (
    "The Commonwealth of Pennsylvania case record spans several lines of "
    "docket text here, well past any low-text threshold for a real page. "
) * 2

_PROD_ROOT = Path(__file__).resolve().parents[1] / "src" / "pipeline"


def _write_pdf(path: Path, page_texts: list[str]) -> None:
    doc = pymupdf.open()
    for text in page_texts:
        page = doc.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(36, 36, 560, 750), text, fontsize=11)
    doc.save(path)
    doc.close()


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reference_for(
    pdf_path: Path,
    *,
    pages: list[str] | None = None,
    sha256: str | None = None,
    version: str = "0.11.10",
) -> dict:
    """A well-formed reference dict; defaults to matching our extractor."""
    if pages is None:
        pages = extraction.extract(pdf_path).page_texts
    return {
        "source_file": pdf_path.name,
        "sha256": sha256 if sha256 is not None else _sha256(pdf_path),
        "pdfplumber_version": version,
        "pages": pages,
    }


def _write_reference(reference_dir: Path, stem: str, reference: object) -> None:
    reference_dir.mkdir(parents=True, exist_ok=True)
    (reference_dir / f"{stem}.json").write_text(json.dumps(reference))


class _Corpus:
    """Builds a corpus dir + reference dir + report dir under tmp_path."""

    def __init__(self, tmp_path: Path):
        self.corpus = tmp_path / "corpus"
        self.reference = tmp_path / "reference"
        self.report = tmp_path / "report"
        self.corpus.mkdir()
        self.reference.mkdir()

    def add(
        self, stem: str, page_texts: list[str], *, reference: object | None = None
    ) -> Path:
        pdf = self.corpus / f"{stem}.pdf"
        _write_pdf(pdf, page_texts)
        if reference is None:
            reference = _reference_for(pdf)
        if reference is not _NO_REFERENCE:
            _write_reference(self.reference, stem, reference)
        return pdf

    def run(self) -> int:
        return run_seam_check(self.corpus, self.reference, self.report)

    def json_report(self) -> dict:
        return json.loads((self.report / "seam-report.json").read_text())


_NO_REFERENCE = object()


def _docket(report: dict, stem: str) -> dict:
    return next(d for d in report["dockets"] if d["docket"] == stem)


# --- comparison outcomes ----------------------------------------------------


def test_equivalent_pair(tmp_path):
    corpus = _Corpus(tmp_path)
    corpus.add("CP-51-CR-0000001-2024", [f"{LONG} alpha", f"{LONG} beta"])

    assert corpus.run() == 0
    report = corpus.json_report()
    assert report["totals"]["equivalent"] == 1
    assert report["totals"]["divergent"] == 0
    # Equivalent dockets carry no per-docket triage entry.
    assert report["dockets"] == []


def test_line_divergence_records_exact_position(tmp_path):
    corpus = _Corpus(tmp_path)
    pdf = corpus.corpus / "CP-51-CR-0000002-2024.pdf"
    _write_pdf(pdf, [f"{LONG} alpha"])
    ours = extraction.extract(pdf).page_texts
    # Flip the last line of page 1 so exactly one line diverges.
    diverged = ours[0].split("\n")
    target_line = len(diverged)  # 1-based line number of the last line
    diverged[-1] = diverged[-1] + "-DIVERGED"
    reference = _reference_for(pdf, pages=["\n".join(diverged)])
    _write_reference(corpus.reference, "CP-51-CR-0000002-2024", reference)

    assert corpus.run() == 0
    report = corpus.json_report()
    assert report["totals"]["divergent"] == 1
    entry = _docket(report, "CP-51-CR-0000002-2024")
    (divergence,) = entry["divergences"]
    assert divergence["type"] == DIVERGENCE_LINE
    assert divergence["page"] == 1
    assert divergence["line"] == target_line


def test_page_count_divergence(tmp_path):
    corpus = _Corpus(tmp_path)
    pdf = corpus.corpus / "CP-51-CR-0000003-2024.pdf"
    _write_pdf(pdf, [f"{LONG} a", f"{LONG} b"])
    # Reference has one page; we extract two.
    reference = _reference_for(pdf, pages=[extraction.extract(pdf).page_texts[0]])
    _write_reference(corpus.reference, "CP-51-CR-0000003-2024", reference)

    assert corpus.run() == 0
    report = corpus.json_report()
    entry = _docket(report, "CP-51-CR-0000003-2024")
    assert entry["status"] == STATUS_DIVERGENT
    (divergence,) = entry["divergences"]
    assert divergence == {"type": DIVERGENCE_PAGE_COUNT, "ours": 2, "reference": 1}


def test_hash_mismatch_is_failure_not_diff(tmp_path):
    corpus = _Corpus(tmp_path)
    pdf = corpus.corpus / "CP-51-CR-0000004-2024.pdf"
    _write_pdf(pdf, [f"{LONG} a"])
    # Correct pages, wrong sha256 -> comparator must not diff.
    reference = _reference_for(pdf, sha256="0" * 64)
    _write_reference(corpus.reference, "CP-51-CR-0000004-2024", reference)

    assert corpus.run() == 0
    report = corpus.json_report()
    entry = _docket(report, "CP-51-CR-0000004-2024")
    assert entry["status"] == STATUS_FAILED
    assert entry["reason"] == REASON_HASH_MISMATCH
    assert "divergences" not in entry


def test_missing_reference(tmp_path):
    corpus = _Corpus(tmp_path)
    corpus.add("CP-51-CR-0000005-2024", [f"{LONG} a"], reference=_NO_REFERENCE)

    assert corpus.run() == 0
    report = corpus.json_report()
    assert report["totals"]["missing_reference"] == 1
    entry = _docket(report, "CP-51-CR-0000005-2024")
    assert entry["status"] == STATUS_MISSING_REFERENCE


def test_malformed_reference_is_loud_per_docket_failure(tmp_path):
    corpus = _Corpus(tmp_path)
    # Missing the required 'pages' key.
    corpus.add(
        "CP-51-CR-0000006-2024",
        [f"{LONG} a"],
        reference={"source_file": "x.pdf", "sha256": "0", "pdfplumber_version": "0"},
    )

    assert corpus.run() == 0
    report = corpus.json_report()
    entry = _docket(report, "CP-51-CR-0000006-2024")
    assert entry["status"] == STATUS_FAILED
    assert entry["reason"] == REASON_MALFORMED_REFERENCE


def test_extraction_failure_recorded(tmp_path):
    corpus = _Corpus(tmp_path)
    # A file whose bytes are a valid sha match but not a real PDF: our
    # extractor returns a failed result, recorded as extraction_failed.
    pdf = corpus.corpus / "CP-51-CR-0000007-2024.pdf"
    pdf.write_bytes(b"JUNKBYTES not a pdf")
    reference = _reference_for(pdf, pages=[])
    _write_reference(corpus.reference, "CP-51-CR-0000007-2024", reference)

    assert corpus.run() == 0
    entry = _docket(corpus.json_report(), "CP-51-CR-0000007-2024")
    assert entry["status"] == STATUS_FAILED
    assert entry["reason"] == REASON_EXTRACTION_FAILED


def test_per_docket_exception_does_not_abort_run(tmp_path, monkeypatch):
    corpus = _Corpus(tmp_path)
    poison = "CP-51-CR-0000008-2024"
    good = "CP-51-CR-0000009-2024"
    corpus.add(poison, [f"{LONG} a"])
    corpus.add(good, [f"{LONG} b"])

    real_extract = extraction.extract

    def _explode(pdf_path):
        if pdf_path.stem == poison:
            raise RuntimeError("boom")
        return real_extract(pdf_path)

    # Patch the name the comparator actually calls.
    monkeypatch.setattr(seam_check, "extract", _explode)

    assert corpus.run() == 0
    report = corpus.json_report()
    assert _docket(report, poison)["reason"] == REASON_EXCEPTION
    # The good docket after the poisoned one still processed to completion.
    assert report["totals"]["equivalent"] == 1


# --- privacy ----------------------------------------------------------------


def test_no_docket_text_or_stem_in_console(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    corpus = _Corpus(tmp_path)
    stem = "MC-51-CR-0009999-2024"
    pdf = corpus.corpus / f"{stem}.pdf"
    _write_pdf(pdf, [f"{LONG} {SENTINEL}"])
    ours = extraction.extract(pdf).page_texts
    # Force a divergence so the sentinel-bearing line lands in the report.
    diverged = ours[0].split("\n")
    diverged[-1] = diverged[-1] + "-DIVERGED"
    _write_reference(
        corpus.reference, stem, _reference_for(pdf, pages=["\n".join(diverged)])
    )

    # Full CLI path so the real stderr logging handler is exercised.
    assert (
        cli.main(
            [
                "seam-check",
                "--corpus-dir",
                str(corpus.corpus),
                "--reference-dir",
                str(corpus.reference),
                "--report-dir",
                str(corpus.report),
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    for stream in (captured.out, captured.err):
        assert SENTINEL not in stream  # docket text never leaves the report
        assert stem not in stream  # docket stem never reaches console/logs
    # The differing content does reach the out-of-repo JSON report.
    assert SENTINEL in (corpus.report / "seam-report.json").read_text()
    # ...but the human-readable summary carries positions only, no content.
    assert SENTINEL not in (corpus.report / "seam-report.txt").read_text()


# --- version capture --------------------------------------------------------


def test_version_capture_and_mismatch_flag(tmp_path):
    corpus = _Corpus(tmp_path)
    pdf = corpus.corpus / "CP-51-CR-0000010-2024.pdf"
    _write_pdf(pdf, [f"{LONG} a"])
    _write_reference(
        corpus.reference,
        "CP-51-CR-0000010-2024",
        _reference_for(pdf, version="0.0.1-fake"),
    )

    assert corpus.run() == 0
    header = corpus.json_report()["header"]
    assert header["ours_pdfplumber_version"] == "0.11.10"
    assert header["capstone_pdfplumber_versions"] == ["0.0.1-fake"]
    assert header["version_mismatch"] is True


def test_matching_version_not_flagged(tmp_path):
    corpus = _Corpus(tmp_path)
    corpus.add("CP-51-CR-0000011-2024", [f"{LONG} a"])
    assert corpus.run() == 0
    assert corpus.json_report()["header"]["version_mismatch"] is False


# --- report shape / breakdown -----------------------------------------------


def test_report_totals_and_court_breakdown(tmp_path):
    corpus = _Corpus(tmp_path)
    corpus.add("CP-51-CR-0000012-2024", [f"{LONG} a"])  # equivalent CP
    # Divergent MC.
    mc_stem = "MC-51-CR-0000013-2024"
    mc_pdf = corpus.corpus / f"{mc_stem}.pdf"
    _write_pdf(mc_pdf, [f"{LONG} b"])
    _write_reference(corpus.reference, mc_stem, _reference_for(mc_pdf, pages=["x"]))
    # Non-docket stem -> classified 'unknown'.
    corpus.add("not-a-docket", [f"{LONG} c"])

    assert corpus.run() == 0
    report = corpus.json_report()
    assert report["totals"] == {
        "corpus_pdfs": 3,
        "compared": 3,
        "equivalent": 2,
        "divergent": 1,
        "failed": 0,
        "missing_reference": 0,
    }
    assert report["by_court"]["CP"][STATUS_EQUIVALENT] == 1
    assert report["by_court"]["MC"][STATUS_DIVERGENT] == 1
    assert report["by_court"]["unknown"][STATUS_EQUIVALENT] == 1


# --- run-boundary guards ----------------------------------------------------


def test_report_dir_inside_git_worktree_rejected(tmp_path):
    corpus = _Corpus(tmp_path)
    corpus.add("CP-51-CR-0000014-2024", [f"{LONG} a"])
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    report_dir = repo / "out"

    assert run_seam_check(corpus.corpus, corpus.reference, report_dir) == 2
    assert not report_dir.exists()


def test_ci_environment_refuses_run(tmp_path, monkeypatch):
    monkeypatch.setenv("CI", "true")
    corpus = _Corpus(tmp_path)
    corpus.add("CP-51-CR-0000015-2024", [f"{LONG} a"])

    assert (
        cli.main(
            [
                "seam-check",
                "--corpus-dir",
                str(corpus.corpus),
                "--reference-dir",
                str(corpus.reference),
                "--report-dir",
                str(corpus.report),
            ]
        )
        == 2
    )
    # It refused before writing anything.
    assert not corpus.report.exists()


def test_cli_defaults_under_court_data():
    parser = cli.build_parser()
    args = parser.parse_args(["seam-check"])
    home = Path.home()
    assert args.corpus_dir == home / "court-data" / "fixtures"
    assert args.reference_dir == home / "court-data" / "capstone-reference-text"
    assert args.report_dir == home / "court-data" / "seam-report"


# --- extraction-reuse proof (decision 2 / AC2) ------------------------------


def test_comparator_calls_production_extraction_identity():
    # The comparator's ``extract`` IS the production extraction function.
    assert seam_check.extract is extraction.extract


def test_seam_check_imports_extract_from_pipeline_extraction():
    tree = ast.parse((_PROD_ROOT / "seam_check.py").read_text())
    imported = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "pipeline.extraction"
        and any(alias.name == "extract" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert imported
