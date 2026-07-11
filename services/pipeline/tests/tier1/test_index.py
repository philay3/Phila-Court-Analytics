"""Tier-1 fixture-index validation (Task 19.1).

Enforces the index invariants:

* 1:1 correspondence — every fixture ``*.txt`` has exactly one index entry and
  one golden ``*.json``, and every index entry names an existing fixture + golden.
* Vocabulary — each entry's ``expected_warnings`` is a subset of the pipeline's
  EMITTED_CODES, and MISSING_CHARGE_SECTION (the sole UNEMITTED code) is never
  expected anywhere.
* Consistency — each entry's ``expected_warnings`` and ``expected_charge_count``
  match its committed golden exactly, so the human-authored index cannot drift
  from the parser-generated goldens.
* Failed-fixture convention (explicit rule, applied not skipped) — a fixture
  whose golden status is ``failed`` MUST have ``expected_charge_count == 0``, a
  null golden record, and an ``error`` arm carrying ``code`` + ``exception_class``.

Field types (``layout_unverified`` bool, ``synthetic`` always true) are checked too.
"""

from __future__ import annotations

import yaml

from pipeline.envelope import EMITTED_CODES
from pipeline.run_fixtures import (
    FIXTURES_DIR,
    GOLDENS_DIR,
    INDEX_PATH,
    golden_filename,
    load_golden,
)
from pipeline.warning_codes import MISSING_CHARGE_SECTION

_INDEX = yaml.safe_load(INDEX_PATH.read_text())
_ENTRIES = _INDEX["fixtures"]


def test_one_to_one_fixture_index_golden():
    index_files = sorted(e["filename"] for e in _ENTRIES)
    assert len(index_files) == len(set(index_files)), "duplicate index filenames"

    fixture_files = sorted(p.name for p in FIXTURES_DIR.glob("*.txt"))
    golden_files = sorted(p.name for p in GOLDENS_DIR.glob("*.json"))

    assert index_files == fixture_files, "index<->fixture mismatch"
    assert sorted(golden_filename(f) for f in index_files) == golden_files, (
        "index<->golden mismatch"
    )


def test_expected_warnings_are_emitted_vocabulary():
    for entry in _ENTRIES:
        for code in entry["expected_warnings"]:
            assert code in EMITTED_CODES, (
                f"{entry['filename']}: {code} not in EMITTED_CODES"
            )
            assert code != MISSING_CHARGE_SECTION, (
                f"{entry['filename']}: MISSING_CHARGE_SECTION must never be expected"
            )


def test_index_field_types():
    for entry in _ENTRIES:
        assert isinstance(entry["layout_unverified"], bool), entry["filename"]
        assert entry["synthetic"] is True, entry["filename"]
        assert isinstance(entry["expected_charge_count"], int), entry["filename"]
        assert isinstance(entry["expected_warnings"], list), entry["filename"]
        assert entry["court_type"] in ("Common Pleas", "Municipal Court")


def test_index_consistent_with_goldens():
    for entry in _ENTRIES:
        golden = load_golden(entry["filename"])
        golden_codes = sorted(w["code"] for w in golden["warnings"])
        assert sorted(entry["expected_warnings"]) == golden_codes, (
            f"{entry['filename']}: expected_warnings {entry['expected_warnings']} "
            f"!= golden {golden_codes}"
        )

        record = golden["record"]
        # Failed-parse convention (explicit rule, applied to every fixture — the
        # degenerate/low-text fixture takes the `failed` branch, never skipped):
        # count 0, null record, structural error arm with code + exception_class.
        if golden["status"] == "failed":
            assert entry["expected_charge_count"] == 0, entry["filename"]
            assert record is None, entry["filename"]
            assert golden["error"] is not None, entry["filename"]
            assert set(golden["error"]) == {"code", "exception_class"}, entry[
                "filename"
            ]
        else:
            assert golden["error"] is None, entry["filename"]
            assert entry["expected_charge_count"] == len(record["charges"]), entry[
                "filename"
            ]
