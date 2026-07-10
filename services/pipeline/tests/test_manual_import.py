"""Tests for the manual import stage (Task 16.3).

No real dockets: tiny synthetic byte files stand in for PDFs (import does not
parse, so valid content is just ``%PDF-`` magic bytes plus filler). All output
goes to pytest ``tmp_path``; nothing touches ``~/court-data/``.
"""

import json
import logging
import os
from pathlib import Path

import pytest

from pipeline.manual_import import (
    ERROR_BAD_MAGIC_BYTES,
    RUN_REPORT_FILENAME,
    STATUS_DUPLICATE,
    STATUS_IMPORTED,
    STATUS_INVALID,
    derive_provenance,
    run_manual_import,
)

# Distinctive stem: if the filename ever leaks into logs/console we detect it.
SENTINEL_STEM = "CP-51-CR-0009999-2026"
PDF_BYTES = b"%PDF-1.7\n" + b"synthetic filler bytes\n" * 8
NOT_PDF_BYTES = b"this is plainly not a pdf at all\n"


def _write(directory: Path, name: str, data: bytes = PDF_BYTES) -> Path:
    path = directory / name
    path.write_bytes(data)
    return path


def _records(metadata_root: Path) -> list[Path]:
    """Hash-keyed metadata records (excludes the run report)."""
    return sorted(
        p
        for p in metadata_root.iterdir()
        if p.suffix == ".json" and p.name != RUN_REPORT_FILENAME
    )


def test_valid_import_writes_hash_keyed_record(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _write(src, "CP-51-CR-0001234-2020.pdf")
    root = tmp_path / "out"

    assert run_manual_import(src, root) == 0

    records = _records(root)
    assert len(records) == 1
    record = json.loads(records[0].read_text())
    # Filename is <sha256>.json and the hash keys the record.
    assert records[0].stem == record["file_hash"]
    assert record["status"] == STATUS_IMPORTED
    assert record["error_code"] is None


def test_metadata_field_completeness(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _write(src, "CP-51-CR-0001234-2020.pdf")
    root = tmp_path / "out"
    run_manual_import(src, root)

    record = json.loads(_records(root)[0].read_text())
    assert set(record) == {
        "id",
        "original_filename",
        "file_hash",
        "file_size_bytes",
        "imported_at",
        "mode",
        "docket_number_provenance",
        "court_type",
        "county",
        "status",
        "error_code",
    }
    assert record["id"] == record["file_hash"]
    assert record["mode"] == "manual"
    assert record["original_filename"] == "CP-51-CR-0001234-2020.pdf"
    assert record["file_size_bytes"] == len(PDF_BYTES)


def test_provenance_from_matching_stem(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _write(src, "MC-51-CR-0007777-2019.pdf")
    root = tmp_path / "out"
    run_manual_import(src, root)

    record = json.loads(_records(root)[0].read_text())
    assert record["docket_number_provenance"] == "MC-51-CR-0007777-2019"
    assert record["court_type"] == "MC"
    assert record["county"] == "51"


def test_provenance_null_degradation(tmp_path):
    # A non-matching stem never guesses: all three provenance fields are null.
    assert derive_provenance("random-file-name") == {
        "docket_number_provenance": None,
        "court_type": None,
        "county": None,
    }

    src = tmp_path / "src"
    src.mkdir()
    _write(src, "not-a-docket-number.pdf")
    root = tmp_path / "out"
    run_manual_import(src, root)

    record = json.loads(_records(root)[0].read_text())
    assert record["docket_number_provenance"] is None
    assert record["court_type"] is None
    assert record["county"] is None


def test_duplicate_skip_on_rerun(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _write(src, "CP-51-CR-0001234-2020.pdf")
    root = tmp_path / "out"

    run_manual_import(src, root)
    record_path = _records(root)[0]
    first = record_path.read_text()

    # Second run over the same all-valid directory: everything duplicate, the
    # original record untouched, zero errors.
    run_manual_import(src, root)
    assert len(_records(root)) == 1
    assert record_path.read_text() == first
    report = json.loads((root / RUN_REPORT_FILENAME).read_text())
    assert report["counts"][STATUS_DUPLICATE] == 1
    assert report["counts"]["failed"] == 0


def test_wrong_extension_skipped_no_record(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _write(src, "CP-51-CR-0001234-2020.txt")
    root = tmp_path / "out"
    run_manual_import(src, root)

    assert _records(root) == []
    report = json.loads((root / RUN_REPORT_FILENAME).read_text())
    assert report["counts"][STATUS_INVALID] == 1


def test_bad_magic_bytes_invalid_then_duplicate(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _write(src, "CP-51-CR-0001234-2020.pdf", data=NOT_PDF_BYTES)
    root = tmp_path / "out"

    # First import: a .pdf whose bytes are not %PDF- is invalid, but still
    # gets a hash-keyed record.
    run_manual_import(src, root)
    records = _records(root)
    assert len(records) == 1
    record = json.loads(records[0].read_text())
    assert record["status"] == STATUS_INVALID
    assert record["error_code"] == ERROR_BAD_MAGIC_BYTES
    first = records[0].read_text()

    # Re-import: the existing hash makes it a duplicate; record untouched and
    # still carries status "invalid".
    run_manual_import(src, root)
    assert records[0].read_text() == first
    report = json.loads((root / RUN_REPORT_FILENAME).read_text())
    assert report["counts"][STATUS_DUPLICATE] == 1
    assert report["counts"][STATUS_INVALID] == 0


def test_empty_directory(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    root = tmp_path / "out"

    assert run_manual_import(src, root) == 0
    assert _records(root) == []
    report = json.loads((root / RUN_REPORT_FILENAME).read_text())
    assert report["counts"] == {
        STATUS_IMPORTED: 0,
        STATUS_DUPLICATE: 0,
        STATUS_INVALID: 0,
        "failed": 0,
    }


def test_unreadable_file_counted_failed(tmp_path):
    if os.geteuid() == 0:
        pytest.skip(
            "running as root: permission bits are ignored, cannot test IO failure"
        )
    src = tmp_path / "src"
    src.mkdir()
    unreadable = _write(src, "CP-51-CR-0001234-2020.pdf")
    unreadable.chmod(0o000)
    root = tmp_path / "out"
    try:
        assert run_manual_import(src, root) == 0
    finally:
        unreadable.chmod(0o644)

    # No hash means no record; counted in the run report only.
    assert _records(root) == []
    report = json.loads((root / RUN_REPORT_FILENAME).read_text())
    assert report["counts"]["failed"] == 1


def test_run_report_and_console_counts(tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    _write(src, "CP-51-CR-0001234-2020.pdf")
    _write(src, "CP-51-CR-0005678-2021.pdf", data=NOT_PDF_BYTES)
    _write(src, "notes.txt")
    root = tmp_path / "out"
    run_manual_import(src, root)

    out = capsys.readouterr().out
    assert "imported=1" in out
    assert "invalid=2" in out  # bad-magic pdf + wrong-extension txt
    report = json.loads((root / RUN_REPORT_FILENAME).read_text())
    assert report["counts"][STATUS_IMPORTED] == 1
    assert report["counts"][STATUS_INVALID] == 2


def test_no_raw_content_in_logs_or_console(tmp_path, capsys, caplog):
    src = tmp_path / "src"
    src.mkdir()
    # Every status path exercised, all with the sentinel stem in the filename.
    _write(src, f"{SENTINEL_STEM}.pdf")
    _write(src, f"{SENTINEL_STEM}-bad.pdf", data=NOT_PDF_BYTES)
    _write(src, f"{SENTINEL_STEM}.txt")
    root = tmp_path / "out"

    with caplog.at_level(logging.DEBUG, logger="pipeline.manual_import"):
        run_manual_import(src, root)

    captured = capsys.readouterr()
    assert SENTINEL_STEM not in captured.out
    assert SENTINEL_STEM not in captured.err
    assert SENTINEL_STEM not in caplog.text
