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

import json

import pytest

from pipeline.docket_parser import (
    detect_court_type,
    parse_docket_checked,
    parse_docket_text,
    parse_related_cases,
)
from pipeline.helpers import ParseError
from pipeline.identity import assert_related_cases_clean
from pipeline.warning_codes import SUSPECT_JUDGE_LINE, SUSPECTED_AMENDED_CHARGE

TEST_SALT = "test-salt"
DOCKET_MC = "MC-51-CR-0000000-2025"
DOCKET_CP = "CP-51-CR-0000000-2025"


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
    record, _, _ = parse_docket_text(
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
    record, _, _ = parse_docket_text(
        "MC-51-CR-0000000-2025", [mc_page()], salt=TEST_SALT
    )
    assert record["case"]["court_type"] == "Municipal Court"
    assert record["case"]["dc_number"] == "9988776655"


def test_cp_record_court_type_and_dc_number():
    record, _, _ = parse_docket_text(
        "CP-51-CR-0000000-2025", [cp_page()], salt=TEST_SALT
    )
    assert record["case"]["court_type"] == "Common Pleas"
    assert record["case"]["dc_number"] == "1122334455"
    assert record["related_cases"] == []


def test_related_cases_drops_caption():
    record, _, _ = parse_docket_text(
        "MC-51-CR-0000000-2025", [mc_page()], salt=TEST_SALT
    )
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
    record, sentinels, _ = parse_docket_checked(
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


# ===========================================================================
# Task 18.2 hardening: junk judge guard, disposition line-wrap fix, amended
# charge signal. Synthetic text only (fictional surname Example / placeholder
# docket). Each item is exercised through parse_docket_text so the emitted
# structural warnings (third return element) can be asserted directly.
# ===========================================================================

_MC_HEAD = [
    "MUNICIPAL COURT OF PHILADELPHIA COUNTY",
    "DOCKET",
    "Docket Number: MC-51-CR-0000000-2025",
    "CASE INFORMATION",
    "Judge Assigned: Date Filed: 01/06/2025",
    "OTN: X 1234567-8",
    "STATUS INFORMATION",
    "Case Status: Closed",
    "DEFENDANT INFORMATION",
    "Date Of Birth: 01/01/1990",
    "CASE PARTICIPANTS",
    "Participant Type Name",
    "Defendant Example, Chris",
    "CHARGES",
    "Seq. Statute Grade Description",
    "1 1 18 § 2701 M1 Simple Assault 01/01/2025 X1234567",
]


def build_mc(*disposition_body: str) -> str:
    """An MC sheet with the fixed head above plus a DISPOSITION section body."""
    return "\n".join([*_MC_HEAD, "DISPOSITION SENTENCING/PENALTIES", *disposition_body])


# --- Item 1: junk judge guard -----------------------------------------------


def test_junk_judge_guard_rejects_sentence_fragment_in_disposition_slot():
    """The Capstone artifact: a sentence fragment ending in a date lands in the
    disposition judge slot. The guard nulls the judge field and emits
    SUSPECT_JUDGE_LINE; only the judge field is affected — the disposition_date
    on the same line is still captured."""
    page = build_mc(
        "Trial",
        "01/15/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        "Confinement Min of 11.00 Months 01/15/2025",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_judge_raw"] is None
    assert charge["disposition_date"] == "2025-01-15"
    suspect = [w for w in warnings if w["code"] == SUSPECT_JUDGE_LINE]
    assert len(suspect) == 1
    assert suspect[0]["charge_sequence"] == 1
    assert suspect[0]["section"] == "DISPOSITION SENTENCING/PENALTIES"
    # Structural context only: no fragment text leaked into the warning payload.
    assert "Confinement" not in json.dumps(warnings)


@pytest.mark.parametrize(
    "judge_line,expected_judge",
    [
        ("Smith, Judge A. 01/15/2025", "Smith, Judge A."),
        ("Nguyen, T. 01/15/2025", "Nguyen, T."),
        ("O'Brien, Mary J. 01/15/2025", "O'Brien, Mary J."),
        ("Doe, J. 01/15/2025", "Doe, J."),
    ],
)
def test_junk_judge_guard_passes_name_shaped_values(judge_line, expected_judge):
    """Comma-formatted and initialed name-shaped judge values pass untouched."""
    page = build_mc(
        "Trial",
        "01/15/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        judge_line,
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    assert record["charges"][0]["disposition_judge_raw"] == expected_judge
    assert not any(w["code"] == SUSPECT_JUDGE_LINE for w in warnings)


def test_junk_judge_guard_rejects_fragment_in_assigned_judge_slot():
    """A sentence fragment in the assigned-judge slot is rejected too; the
    field is nulled and Date Filed on the same line is still parsed."""
    lines = [
        "COURT OF COMMON PLEAS OF PHILADELPHIA COUNTY",
        "DOCKET",
        "Docket Number: CP-51-CR-0000000-2025",
        "CASE INFORMATION",
        "Judge Assigned: Confinement 11 Months Date Filed: 02/03/2025",
        "OTN: X 7654321-1",
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
    record, _, warnings = parse_docket_text(
        DOCKET_CP, ["\n".join(lines)], salt=TEST_SALT
    )
    assert record["case"]["assigned_judge_raw"] is None
    assert record["case"]["filed_date"] == "2025-02-03"
    assert any(
        w["code"] == SUSPECT_JUDGE_LINE and w.get("section") == "CASE INFORMATION"
        for w in warnings
    )


def test_assigned_judge_name_shaped_value_preserved():
    """A name-shaped assigned judge is kept and emits no warning."""
    record, _, warnings = parse_docket_text(DOCKET_CP, [cp_page()], salt=TEST_SALT)
    assert record["case"]["assigned_judge_raw"] == "Example, Judge A."
    assert not any(w["code"] == SUSPECT_JUDGE_LINE for w in warnings)


# --- Item 2: disposition line-wrap capture ----------------------------------


def test_disposition_line_wrap_captured_in_full():
    """A disposition that wraps to a second physical line is captured in full
    ("Transferred to Another Jurisdiction"), the following judge line is still
    read, and the extended string does not spuriously trigger the amended
    signal (Item 2 -> Item 3 interaction)."""
    page = build_mc(
        "Trial",
        "01/15/2025 Final Disposition",
        "1 / Simple Assault Transferred to Another",
        "Jurisdiction",
        "Smith, Judge A. 01/15/2025",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] == "Transferred to Another Jurisdiction"
    assert charge["disposition_judge_raw"] == "Smith, Judge A."
    assert charge["disposition_date"] == "2025-01-15"
    assert not any(w["code"] == SUSPECTED_AMENDED_CHARGE for w in warnings)


def test_disposition_not_extended_by_sentence_type_line():
    """A sentence-type line ("Confinement") after the disposition is NOT a wrap;
    disposition_raw stays exactly the charge-line value."""
    page = build_mc(
        "Trial",
        "01/15/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        "Confinement",
        "Max of 12.00 Months",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    assert record["charges"][0]["disposition_raw"] == "Guilty"


# --- Item 3: amended/downgraded/replaced charge signal ----------------------


@pytest.mark.parametrize(
    "disposition_tail",
    ["Amended", "Downgraded", "Replaced By", "Charge Changed"],
)
def test_amended_charge_signal_emitted(disposition_tail):
    """Each conservative marker in disposition_raw emits SUSPECTED_AMENDED_CHARGE
    with structural context; the parsed disposition_raw is unchanged (warning-
    only, zero field change)."""
    page = build_mc(
        "Trial",
        "01/15/2025 Final Disposition",
        f"1 / Simple Assault {disposition_tail}",
        "Smith, Judge A. 01/15/2025",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    assert record["charges"][0]["disposition_raw"] == disposition_tail
    amended = [w for w in warnings if w["code"] == SUSPECTED_AMENDED_CHARGE]
    assert len(amended) == 1
    assert amended[0]["charge_sequence"] == 1
    assert amended[0]["section"] == "CHARGES"


@pytest.mark.parametrize(
    "disposition_tail",
    ["Guilty", "Guilty Plea - Negotiated", "Nolle Prossed", "Not Guilty"],
)
def test_ordinary_disposition_does_not_flag_amended(disposition_tail):
    """Ordinary disposition renderings never trigger the amended signal."""
    page = build_mc(
        "Trial",
        "01/15/2025 Final Disposition",
        f"1 / Simple Assault {disposition_tail}",
        "Smith, Judge A. 01/15/2025",
    )
    _, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    assert not any(w["code"] == SUSPECTED_AMENDED_CHARGE for w in warnings)
