"""Parser tests ported from Capstone's tests/test_mc_parser.py (Task 17.2),
exercised on synthetic text via parse_docket_text (no PDF needed). Fictional
surname Example and docket MC-51-CR-0000000-2025 only; no real names or
captions appear here.

Deliberate duplication: test_privacy_guard_rejects_extra_field /
test_privacy_guard_passes_clean_record are byte-identical to two tests 16.1
already ported into test_identity.py. They are re-ported here per the 17.2
task note because at this level they belong to the parser's ported test suite;
a future cleanup should NOT "deduplicate" by deleting the test_identity.py
copies (those assert the guard as a standalone identity unit). The full
parse-path exercise of the guard lives in the parse_docket_checked tests below.
"""

from __future__ import annotations

import pytest

from pipeline.docket_parser import (
    detect_court_type,
    parse_docket_checked,
    parse_docket_text,
    parse_related_cases,
)
from pipeline.helpers import ParseError
from pipeline.identity import assert_related_cases_clean

TEST_SALT = "test-salt"


def mc_page() -> str:
    """A minimal MC-shaped sheet with the four new sections. The related-cases
    row deliberately carries a fake caption so the test can prove it is
    dropped."""
    return "\n".join(
        [
            "MUNICIPAL COURT OF PHILADELPHIA COUNTY",
            "DOCKET",
            "Docket Number: MC-51-CR-0000000-2025",
            "CASE INFORMATION",
            "Judge Assigned: Date Filed: 01/06/2025",
            "OTN: X 1234567-8",
            "Case Local Number Type(s) Case Local Number(s)",
            "District Control Number 9988776655",
            "RELATED CASES",
            "Docket Number Court Caption Association Reason",
            "CP-51-CR-0000000-2025 Court of Common Pleas "
            "Commonwealth v. Example, Adam Refiled",
            "STATUS INFORMATION",
            "Case Status: Open",
            "DEFENDANT INFORMATION",
            "Date Of Birth: 01/01/1990",
            "CASE PARTICIPANTS",
            "Participant Type Name",
            "Defendant Example, Chris",
            "CHARGES",
            "Seq. Statute Grade Description",
            "1 1 18 § 2701 M1 Simple Assault 01/01/2025 X1234567",
        ]
    )


def mc_full_page() -> str:
    """An MC sheet exercising every section: CASE INFORMATION with a Cross
    Court Docket Nos line, RELATED CASES, a charge, and a disposition event
    that yields a sentence component. Used to prove the record's full recursive
    key set is a fixed allowlist (no key is derived from document text)."""
    return "\n".join(
        [
            "MUNICIPAL COURT OF PHILADELPHIA COUNTY",
            "DOCKET",
            "Docket Number: MC-51-CR-0000000-2025",
            "CASE INFORMATION",
            "Judge Assigned: Date Filed: 01/06/2025",
            "OTN: X 1234567-8",
            "Cross Court Docket Nos: CP-51-CR-0000000-2025",
            "Case Local Number Type(s) Case Local Number(s)",
            "District Control Number 9988776655",
            "RELATED CASES",
            "Docket Number Court Caption Association Reason",
            "CP-51-CR-0000000-2025 Court of Common Pleas "
            "Commonwealth v. Example, Adam Refiled",
            "STATUS INFORMATION",
            "Case Status: Open",
            "DEFENDANT INFORMATION",
            "Date Of Birth: 01/01/1990",
            "CASE PARTICIPANTS",
            "Participant Type Name",
            "Defendant Example, Chris",
            "CHARGES",
            "Seq. Statute Grade Description",
            "1 1 18 § 2701 M1 Simple Assault 01/01/2025 X1234567",
            "DISPOSITION SENTENCING/PENALTIES",
            "Preliminary Hearing",
            "01/15/2025 Final Disposition",
            "1 / Simple Assault Guilty Plea - Negotiated M1",
            "Example, Judge A. 01/15/2025",
            "Probation",
            "Max of 12.00 Months",
        ]
    )


ALLOWED_KEYS = {
    # top level
    "docket_number",
    "parser_version",
    "parsed_at",
    "case",
    "charges",
    "related_cases",
    "notes",
    # case
    "county",
    "court_type",
    "case_status",
    "filed_date",
    "otn",
    "assigned_judge_raw",
    "dc_number",
    "cross_court_dockets",
    "defendant_hash",
    # charges
    "sequence",
    "statute",
    "grade",
    "offense",
    "disposition_raw",
    "disposition_date",
    "disposition_judge_raw",
    "sentences",
    # sentences
    "sentence_type",
    "min_days",
    "max_days",
    "program",
    "sentence_date",
    "raw_text",
    # related_cases
    "court",
    "association_reason",
}


def _all_keys(obj) -> set:
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= _all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            keys |= _all_keys(v)
    return keys


def test_record_key_set_is_fixed_allowlist():
    """Every emitted key is a structural constant, never document text: the
    record's full recursive key set equals a fixed allowlist. This is the
    invariant the values-only leak scan relies on."""
    record, _ = parse_docket_text(
        "MC-51-CR-0000000-2025", [mc_full_page()], salt=TEST_SALT
    )
    # sanity: the rich fixture actually populated the optional nested sections
    assert record["charges"][0]["sentences"], "fixture must yield a sentence"
    assert record["related_cases"], "fixture must yield a related case"
    assert record["case"]["cross_court_dockets"] == "CP-51-CR-0000000-2025"
    assert _all_keys(record) == ALLOWED_KEYS


def cp_page() -> str:
    """A CP-shaped sheet with a Case Local Number(s) table and no related
    cases, to prove the delta leaves CP parsing intact."""
    return "\n".join(
        [
            "COURT OF COMMON PLEAS OF PHILADELPHIA COUNTY",
            "DOCKET",
            "Docket Number: CP-51-CR-0000000-2025",
            "CASE INFORMATION",
            "Judge Assigned: Example, Judge A. Date Filed: 02/03/2025",
            "OTN: X 7654321-1",
            "Case Local Number Type(s) Case Local Number(s)",
            "District Control Number 1122334455",
            "STATUS INFORMATION",
            "Case Status: Active",
            "DEFENDANT INFORMATION",
            "Date Of Birth: 05/05/1985",
            "CASE PARTICIPANTS",
            "Participant Type Name",
            "Defendant Example, Dana",
            "CHARGES",
            "Seq. Statute Grade Description",
            "1 1 18 § 3502 F1 Burglary 02/01/2025 X7654321",
        ]
    )


def test_court_type_detection_both_prefixes():
    assert detect_court_type("MC-51-CR-0000000-2025") == "Municipal Court"
    assert detect_court_type("CP-51-CR-0000000-2025") == "Common Pleas"


def test_mc_record_court_type_and_dc_number():
    record, _ = parse_docket_text("MC-51-CR-0000000-2025", [mc_page()], salt=TEST_SALT)
    assert record["case"]["court_type"] == "Municipal Court"
    assert record["case"]["dc_number"] == "9988776655"


def test_cp_record_court_type_and_dc_number():
    record, _ = parse_docket_text("CP-51-CR-0000000-2025", [cp_page()], salt=TEST_SALT)
    assert record["case"]["court_type"] == "Common Pleas"
    assert record["case"]["dc_number"] == "1122334455"
    assert record["related_cases"] == []


def test_related_cases_drops_caption():
    record, _ = parse_docket_text("MC-51-CR-0000000-2025", [mc_page()], salt=TEST_SALT)
    rc = record["related_cases"]
    assert len(rc) == 1
    entry = rc[0]
    assert entry == {
        "docket_number": "CP-51-CR-0000000-2025",
        "court": "Common Pleas",
        "association_reason": "Refiled",
    }
    # The fake caption name must appear nowhere in the record.
    import json

    blob = json.dumps(record)
    assert "Adam" not in blob


def test_related_cases_parser_ignores_header_and_free_text():
    lines = [
        "Docket Number Court Caption Association Reason",
        "MC-51-CR-0000001-2025 Municipal Court "
        "Commonwealth v. Example, Blake Consolidated",
        "some unrelated free text with no docket number",
    ]
    out = parse_related_cases(lines)
    assert out == [
        {
            "docket_number": "MC-51-CR-0000001-2025",
            "court": "Municipal Court",
            "association_reason": "Consolidated",
        }
    ]


def test_privacy_guard_rejects_extra_field():
    bad = {
        "related_cases": [
            {
                "docket_number": "MC-51-CR-0000000-2025",
                "court": "Municipal Court",
                "association_reason": "Refiled",
                "caption": "Example, Adam",
            }
        ]
    }
    with pytest.raises(RuntimeError):
        assert_related_cases_clean(bad)


def test_privacy_guard_passes_clean_record():
    good = {
        "related_cases": [
            {
                "docket_number": "MC-51-CR-0000000-2025",
                "court": "Municipal Court",
                "association_reason": "Refiled",
            }
        ]
    }
    assert assert_related_cases_clean(good) is None


# --- parse_docket_checked: the sentinel boundary exercised through the full
# parse path (Capstone parse_fixtures.py lines 26-29, minus IO). ---


def test_parse_docket_checked_passes_clean_record():
    """A clean MC sheet: no identifying string reaches a value, no related-case
    entry carries an extra field, so both assertions pass and the record is
    returned intact."""
    record, sentinels = parse_docket_checked(
        "MC-51-CR-0000000-2025", [mc_page()], salt=TEST_SALT
    )
    assert record["docket_number"] == "MC-51-CR-0000000-2025"
    assert sentinels  # sentinels were generated


def test_parse_docket_checked_raises_on_value_leak():
    """The rich MC sheet captures a judge ("Example, Judge A.") whose surname
    equals the defendant's; that collision puts a sentinel string into a record
    VALUE, so the post-parse assert_no_leak boundary raises. (Capstone treats
    such a defendant/judge surname collision as a hard stop by design.)"""
    with pytest.raises(RuntimeError):
        parse_docket_checked("MC-51-CR-0000000-2025", [mc_full_page()], salt=TEST_SALT)


# --- ParseError messages never quote docket text (acceptance criterion 8) ---


def test_parse_error_message_quotes_no_docket_text():
    """A sheet with a defendant name but no DOB raises ParseError; the message
    must name the field only, never the defendant value or docket number."""
    page = "\n".join(
        [
            "MUNICIPAL COURT OF PHILADELPHIA COUNTY",
            "DEFENDANT INFORMATION",
            "CASE PARTICIPANTS",
            "Participant Type Name",
            "Defendant Example, Chris",
        ]
    )
    with pytest.raises(ParseError) as excinfo:
        parse_docket_text("MC-51-CR-0000000-2025", [page], salt=TEST_SALT)
    msg = str(excinfo.value)
    assert "Example" not in msg
    assert "Chris" not in msg
    assert "MC-51-CR-0000000-2025" not in msg
