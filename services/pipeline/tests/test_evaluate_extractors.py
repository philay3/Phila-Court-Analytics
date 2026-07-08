"""Tests for the evaluate-extractors harness.

No real dockets: tiny synthetic PDFs are generated at test time with
PyMuPDF. Fixture names deliberately mimic docket-number filenames so the
no-filename-leak assertions are meaningful.
"""

import json
import re

import pymupdf
import pytest

from pipeline import cli
from pipeline.evaluation.harness import SECTION_KEYWORDS, inside_git_worktree

# Distinctive body text that must never appear in logs or reports.
SENTINEL = "SYNTHETIC-DOCKET-BODY-TEXT-XYZZY"
# Distinctive junk-file bytes: pypdf's logger echoes the file header
# ("invalid pdf header: b'...'"), so raw bytes must not leak either.
JUNK_BYTES = b"JUNKBYTES this is not a pdf at all"
TEXT_PDF_NAME = "MC-51-CR-0001234-2024.pdf"
BLANK_PDF_NAME = "CP-51-CR-0005678-2024.pdf"
JUNK_PDF_NAME = "MC-51-CR-0009999-2024.pdf"
FIXTURE_NAMES = (TEXT_PDF_NAME, BLANK_PDF_NAME, JUNK_PDF_NAME)
TEXT_PDF_PAGES = 3
HASH_KEY_RE = re.compile(r"^[0-9a-f]{16}$")


@pytest.fixture
def fixtures_dir(tmp_path):
    fixtures = tmp_path / "pdfs"
    fixtures.mkdir()

    doc = pymupdf.open()
    for i in range(TEXT_PDF_PAGES):
        page = doc.new_page()
        page.insert_text((72, 72), f"CASE INFORMATION for page {i + 1}")
        page.insert_text((72, 144), f"CHARGES {SENTINEL}")
    doc.save(fixtures / TEXT_PDF_NAME)
    doc.close()

    doc = pymupdf.open()
    doc.new_page()
    doc.new_page()
    doc.save(fixtures / BLANK_PDF_NAME)
    doc.close()

    (fixtures / JUNK_PDF_NAME).write_bytes(JUNK_BYTES)
    return fixtures


@pytest.fixture
def output_dir(tmp_path):
    return tmp_path / "out"


def run_cli(fixtures_dir, output_dir, *extra):
    return cli.main(
        [
            "evaluate-extractors",
            "--fixtures-dir",
            str(fixtures_dir),
            "--output-dir",
            str(output_dir),
            *extra,
        ]
    )


def load_report(output_dir, extractor):
    return json.loads((output_dir / f"report-{extractor}.json").read_text())


def hash_for(output_dir, filename):
    index = json.loads((output_dir / "file-index.json").read_text())
    return next(digest for digest, name in index.items() if name == filename)


@pytest.fixture
def completed_run(fixtures_dir, output_dir, capsys):
    assert run_cli(fixtures_dir, output_dir) == 0
    return capsys.readouterr().err


@pytest.mark.parametrize("extractor", ["pymupdf", "pdfplumber", "pypdf"])
def test_text_pdf_metrics(completed_run, output_dir, extractor):
    report = load_report(output_dir, extractor)
    metrics = report["files"][hash_for(output_dir, TEXT_PDF_NAME)]
    assert metrics["error"] is None
    assert metrics["page_count"] == TEXT_PDF_PAGES
    assert metrics["total_chars"] > 0
    assert len(metrics["per_page_chars"]) == TEXT_PDF_PAGES
    assert all(length > 0 for length in metrics["per_page_chars"])
    assert metrics["empty_pages"] == {"count": 0, "indices": []}
    assert metrics["needs_ocr_or_review"] is False
    assert metrics["section_hits"]["CASE INFORMATION"] == TEXT_PDF_PAGES
    assert metrics["section_hits"]["CHARGES"] == TEXT_PDF_PAGES
    assert metrics["section_hits"]["ENTRIES"] == 0
    assert metrics["duration_seconds"] >= 0


@pytest.mark.parametrize("extractor", ["pymupdf", "pdfplumber", "pypdf"])
def test_blank_pdf_flagged_for_ocr(completed_run, output_dir, extractor):
    report = load_report(output_dir, extractor)
    metrics = report["files"][hash_for(output_dir, BLANK_PDF_NAME)]
    assert metrics["needs_ocr_or_review"] is True
    assert metrics["empty_pages"] == {"count": 2, "indices": [0, 1]}


@pytest.mark.parametrize("extractor", ["pymupdf", "pdfplumber", "pypdf"])
def test_junk_file_error_recorded_run_continues(completed_run, output_dir, extractor):
    report = load_report(output_dir, extractor)
    metrics = report["files"][hash_for(output_dir, JUNK_PDF_NAME)]
    assert metrics["error"] is not None
    assert metrics["error"]["type"]
    assert metrics["needs_ocr_or_review"] is True
    # The failure did not abort the run: all three files have records.
    assert len(report["files"]) == len(FIXTURE_NAMES)


def test_artifact_structure(completed_run, output_dir):
    index = json.loads((output_dir / "file-index.json").read_text())
    assert sorted(index.values()) == sorted(FIXTURE_NAMES)
    assert all(HASH_KEY_RE.match(digest) for digest in index)

    summary = json.loads((output_dir / "summary.json").read_text())
    assert set(summary["extractors"]) == {"pymupdf", "pdfplumber", "pypdf"}
    for rollup in summary["extractors"].values():
        assert rollup["total_files"] == len(FIXTURE_NAMES)
        assert rollup["failures"] == 1
        assert rollup["needs_ocr_or_review"] == 2  # blank + junk
        assert rollup["total_duration_seconds"] >= 0
        assert rollup["mean_duration_seconds"] >= 0
        assert set(rollup["section_hit_rates"]) == set(SECTION_KEYWORDS)
        assert rollup["section_hit_rates"]["CASE INFORMATION"] == 0.5  # 1 of 2

    for extractor in ("pymupdf", "pdfplumber", "pypdf"):
        report = load_report(output_dir, extractor)
        assert report["extractor"] == extractor
        assert report["file_count"] == len(FIXTURE_NAMES)
        assert all(HASH_KEY_RE.match(digest) for digest in report["files"])


def test_no_text_or_filenames_in_logs_or_reports(completed_run, output_dir):
    assert SENTINEL not in completed_run
    # pypdf's logger echoes the first 5 header bytes; check that prefix.
    assert "JUNKB" not in completed_run
    for name in FIXTURE_NAMES:
        assert name not in completed_run
        assert name.removesuffix(".pdf") not in completed_run

    for extractor in ("pymupdf", "pdfplumber", "pypdf"):
        dumped = json.dumps(load_report(output_dir, extractor))
        assert SENTINEL not in dumped
        for name in FIXTURE_NAMES:
            assert name.removesuffix(".pdf") not in dumped


def test_missing_fixtures_dir_errors(tmp_path, output_dir, capsys):
    assert run_cli(tmp_path / "nope", output_dir) == 2
    assert "fixtures dir" in capsys.readouterr().err


def test_empty_fixtures_dir_errors(tmp_path, output_dir, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert run_cli(empty, output_dir) == 2
    assert "no PDF files" in capsys.readouterr().err


@pytest.mark.parametrize("git_entry_kind", ["dir", "file"])
def test_output_dir_inside_git_worktree_refused(
    fixtures_dir, tmp_path, git_entry_kind, capsys
):
    repo = tmp_path / "repo"
    repo.mkdir()
    if git_entry_kind == "dir":
        (repo / ".git").mkdir()
    else:
        # Linked worktrees and submodules use a plain .git file.
        (repo / ".git").write_text("gitdir: /somewhere/else\n")
    assert inside_git_worktree(repo / "out") is True
    assert run_cli(fixtures_dir, repo / "deep" / "out") == 2
    assert "git working tree" in capsys.readouterr().err


def test_extractor_subset_runs_only_selected(fixtures_dir, output_dir):
    assert run_cli(fixtures_dir, output_dir, "--extractors", "pymupdf") == 0
    assert (output_dir / "report-pymupdf.json").exists()
    assert not (output_dir / "report-pdfplumber.json").exists()
    assert not (output_dir / "report-pypdf.json").exists()
    summary = json.loads((output_dir / "summary.json").read_text())
    assert set(summary["extractors"]) == {"pymupdf"}


def test_unknown_extractor_rejected(fixtures_dir, output_dir, capsys):
    with pytest.raises(SystemExit) as excinfo:
        run_cli(fixtures_dir, output_dir, "--extractors", "tesseract")
    assert excinfo.value.code == 2
    assert "unknown extractor" in capsys.readouterr().err


def test_dump_text_off_by_default(completed_run, output_dir):
    assert not (output_dir / "text").exists()


def test_dump_text_writes_extracted_text(fixtures_dir, output_dir):
    assert run_cli(fixtures_dir, output_dir, "--dump-text") == 0
    digest = hash_for(output_dir, TEXT_PDF_NAME)
    for extractor in ("pymupdf", "pdfplumber", "pypdf"):
        dump = (output_dir / "text" / extractor / f"{digest}.txt").read_text()
        assert SENTINEL in dump
        assert "--- page 2 ---" in dump
