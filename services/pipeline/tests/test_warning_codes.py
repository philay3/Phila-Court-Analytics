"""Warning vocabulary, severity map, and review_needed derivation (Task 18.1)."""

from __future__ import annotations

import pytest

from pipeline import warning_codes as wc

EXPECTED_CODES = {
    "LOW_TEXT_EXTRACTION",
    "MISSING_CHARGE_SECTION",
    "UNPARSEABLE_DURATION",
    "MISSING_DISPOSITION_DATE",
    "MISSING_SENTENCE_DATE",
    "SUSPECT_JUDGE_LINE",
    "SUSPECTED_AMENDED_CHARGE",
    "NON_TERMINAL_CASE",
    "UNSUPPORTED_FORMAT",
    "SENTINEL_COLLISION",
    "UNKNOWN_NOT_FINAL_DISPOSITION",
    "SUSPECT_DISPOSITION_TOKEN",
}


def test_vocabulary_is_exactly_the_twelve_codes():
    assert wc.WARNING_CODES == EXPECTED_CODES
    assert len(wc.WARNING_CODES) == 12


def test_severity_map_covers_every_code_with_valid_levels():
    assert set(wc.SEVERITY) == wc.WARNING_CODES
    assert set(wc.SEVERITY.values()) <= {wc.SEVERITY_REVIEW, wc.SEVERITY_INFO}


def test_severity_map_matches_approved_table():
    review = {c for c, s in wc.SEVERITY.items() if s == wc.SEVERITY_REVIEW}
    info = {c for c, s in wc.SEVERITY.items() if s == wc.SEVERITY_INFO}
    assert review == {
        wc.LOW_TEXT_EXTRACTION,
        wc.MISSING_CHARGE_SECTION,
        wc.UNSUPPORTED_FORMAT,
        wc.MISSING_DISPOSITION_DATE,
        wc.SUSPECT_JUDGE_LINE,
        wc.SUSPECTED_AMENDED_CHARGE,
        wc.SENTINEL_COLLISION,
        wc.UNKNOWN_NOT_FINAL_DISPOSITION,
        wc.SUSPECT_DISPOSITION_TOKEN,
    }
    assert info == {
        wc.UNPARSEABLE_DURATION,
        wc.MISSING_SENTENCE_DATE,
        wc.NON_TERMINAL_CASE,
    }


def test_make_warning_rejects_unknown_code():
    with pytest.raises(ValueError):
        wc.make_warning("NOT_A_CODE")


def test_make_warning_is_structural_only_and_drops_none_fields():
    w = wc.make_warning(wc.UNPARSEABLE_DURATION, charge_sequence=3)
    assert w == {"code": wc.UNPARSEABLE_DURATION, "charge_sequence": 3}
    # Only the code plus the supplied structural field — nothing else.
    assert set(w) <= {"code", "section", "charge_sequence", "page", "field"}


def test_make_warning_accepts_all_structural_fields():
    w = wc.make_warning(
        wc.MISSING_SENTENCE_DATE,
        section="DISPOSITION",
        charge_sequence=2,
        page=4,
        field="sentence_date",
    )
    assert w == {
        "code": wc.MISSING_SENTENCE_DATE,
        "section": "DISPOSITION",
        "charge_sequence": 2,
        "page": 4,
        "field": "sentence_date",
    }


def test_derive_review_needed_no_warnings_is_false():
    assert wc.derive_review_needed([]) is False


def test_derive_review_needed_single_info_is_false():
    assert wc.derive_review_needed([wc.NON_TERMINAL_CASE]) is False


def test_derive_review_needed_single_review_is_true():
    assert wc.derive_review_needed([wc.LOW_TEXT_EXTRACTION]) is True


def test_derive_review_needed_mixed_is_true():
    assert (
        wc.derive_review_needed([wc.NON_TERMINAL_CASE, wc.MISSING_DISPOSITION_DATE])
        is True
    )


def test_derive_review_needed_rejects_unknown_code():
    with pytest.raises(ValueError):
        wc.derive_review_needed(["NOT_A_CODE"])
