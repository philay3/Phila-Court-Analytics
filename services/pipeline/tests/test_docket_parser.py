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
    ARD_CLASS_DISPOSITIONS,
    NON_TERMINAL_DISPOSITIONS,
    detect_court_type,
    parse_docket_checked,
    parse_docket_text,
    parse_related_cases,
)
from pipeline.envelope import _charge_has_disposition
from pipeline.helpers import ParseError
from pipeline.identity import assert_related_cases_clean
from pipeline.normalization.outcome_mapper import (
    DISPOSITION_OUTCOME_MAP,
    HELD_FOR_COURT_DISPOSITIONS,
)
from pipeline.warning_codes import (
    SENTINEL_COLLISION,
    SUSPECT_DISPOSITION_TOKEN,
    SUSPECT_JUDGE_LINE,
    SUSPECTED_AMENDED_CHARGE,
    UNKNOWN_NOT_FINAL_DISPOSITION,
)

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


def mc_held_page() -> str:
    """An MC sheet held for court: a non-terminal (Not Final) event whose charge
    carries no disposition. Exercises the 18.3 event_date/event_name capture on a
    non-terminal charge (disposition stays null; NON_TERMINAL_CASE is an envelope
    observation, not asserted here)."""
    return "\n".join(
        [
            "MUNICIPAL COURT OF PHILADELPHIA COUNTY",
            "DOCKET",
            "Docket Number: MC-51-CR-0000000-2025",
            "CASE INFORMATION",
            "Judge Assigned: Date Filed: 01/06/2025",
            "OTN: X 1234567-8",
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
            "Held for Court 06/15/2024 Not Final",
            "1 / Simple Assault",
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
    # charges: 18.3 non-terminal (held) charges only
    "event_date",
    "event_name",
    # sentences
    "sentence_type",
    "min_days",
    "max_days",
    "program",
    "sentence_date",
    "raw_text",
    # sentences: 18.3 annotation, present only when min was filled
    "min_assumed",
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
    invariant the values-only leak scan relies on.

    18.3: some keys are conditionally present (event_date/event_name on
    non-terminal charges; min_assumed on filled sentences), so the invariant is
    asserted over the UNION of a terminal fixture (mc_full_page: sentence +
    min_assumed) and a held fixture (mc_held_page: event_date/event_name). The
    union must equal the allowlist EXACTLY — an unexpected key still fails loudly."""
    terminal, _, _ = parse_docket_text(
        "MC-51-CR-0000000-2025", [mc_full_page()], salt=TEST_SALT
    )
    held, _, _ = parse_docket_text(
        "MC-51-CR-0000000-2025", [mc_held_page()], salt=TEST_SALT
    )
    # sanity: the fixtures actually populate the optional nested/conditional keys
    assert terminal["charges"][0]["sentences"], "fixture must yield a sentence"
    assert terminal["charges"][0]["sentences"][0].get("min_assumed") is True
    assert terminal["related_cases"], "fixture must yield a related case"
    assert terminal["case"]["cross_court_dockets"] == "CP-51-CR-0000000-2025"
    assert held["charges"][0]["event_date"] == "2024-06-15"
    assert held["charges"][0]["event_name"] == "Held for Court"
    assert (_all_keys(terminal) | _all_keys(held)) == ALLOWED_KEYS


def cp_page() -> str:
    """A CP-shaped sheet with a Case Local Number(s) table and no related
    cases, to prove the delta leaves CP parsing intact."""
    return "\n".join(
        [
            "COURT OF COMMON PLEAS OF PHILADELPHIA COUNTY",
            "DOCKET",
            "Docket Number: CP-51-CR-0000000-2025",
            "CASE INFORMATION",
            "Judge Assigned: Torres, Judge A. Date Filed: 02/03/2025",
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


def test_parse_docket_checked_nulls_colliding_judge_and_passes():
    """The rich MC sheet captures a disposition judge ("Example, Judge A.") whose
    surname equals the defendant's. 18.3 Q2: the parse-time third-party name guard
    nulls that field and flags SENTINEL_COLLISION, so the colliding value never
    reaches a record VALUE and the post-parse assert_no_leak backstop no longer
    fires — the record is returned, flagged for human adjudication."""
    record, _, warnings = parse_docket_checked(
        "MC-51-CR-0000000-2025", [mc_full_page()], salt=TEST_SALT
    )
    charge = record["charges"][0]
    assert charge["disposition_judge_raw"] is None
    # The disposition_date on the same line is still captured.
    assert charge["disposition_date"] == "2025-01-15"
    collision = [w for w in warnings if w["code"] == SENTINEL_COLLISION]
    assert len(collision) == 1
    assert collision[0]["section"] == "DISPOSITION SENTENCING/PENALTIES"
    assert collision[0]["charge_sequence"] == 1
    # Structural context only: the colliding capture never enters the warning.
    assert "Example" not in json.dumps(warnings)


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
    """A name-shaped assigned judge that does not collide with a sentinel is kept
    and emits no warning."""
    record, _, warnings = parse_docket_text(DOCKET_CP, [cp_page()], salt=TEST_SALT)
    assert record["case"]["assigned_judge_raw"] == "Torres, Judge A."
    assert not any(w["code"] == SUSPECT_JUDGE_LINE for w in warnings)
    assert not any(w["code"] == SENTINEL_COLLISION for w in warnings)


# --- Item 2: known-truncated disposition repair -----------------------------
# The 18.2 corpus rerun proved the continuation line cannot be read safely (it
# interleaves disposition tails, charge-description wraps, and section-header
# furniture). Item 2 instead repairs an EXACT-MATCH truncated capture to its
# known full string and reads no continuation line — so a polluted continuation
# cannot leak in, and non-truncated dispositions are never touched.


def test_truncated_disposition_repaired_ignoring_polluted_continuation():
    """The Transferred capture ("Transferred to Another") is repaired to the full
    string. The continuation line is deliberately polluted with a charge-name
    wrap; because the repair reads no continuation line, the pollution never
    leaks, the following judge line is still read, and the repaired string does
    not trigger the amended signal (Item 2 -> Item 3 interaction)."""
    page = build_mc(
        "Trial",
        "01/15/2025 Final Disposition",
        "1 / Simple Assault Transferred to Another",
        "Manufacture or Deliver Jurisdiction",
        "Smith, Judge A. 01/15/2025",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] == "Transferred to Another Jurisdiction"
    assert charge["disposition_judge_raw"] == "Smith, Judge A."
    assert charge["disposition_date"] == "2025-01-15"
    assert not any(w["code"] == SUSPECTED_AMENDED_CHARGE for w in warnings)


def test_truncated_rule600_disposition_repaired():
    """The Rule 600 wrap capture ("Dismissed - Rule 600 (Speedy") is repaired to
    the full string (Task 34.1, same Item-2 class as Transferred). The
    continuation line carrying the tail is polluted with a charge-name wrap;
    the repair reads no continuation line, so the pollution never leaks, the
    judge line is still read, and the event-line date is kept."""
    page = build_mc(
        "Trial",
        "01/15/2025 Final Disposition",
        "1 / Simple Assault Dismissed - Rule 600 (Speedy",
        "Manufacture or Deliver Trial)",
        "Smith, Judge A. 01/15/2025",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] == "Dismissed - Rule 600 (Speedy Trial)"
    assert charge["disposition_judge_raw"] == "Smith, Judge A."
    assert charge["disposition_date"] == "2025-01-15"
    assert warnings == []


def test_charge_description_wrap_not_appended():
    """A charge-description wrap after an ordinary disposition is NOT appended;
    the ordinary disposition (not a repair-table key) is left untouched."""
    page = build_mc(
        "Trial",
        "01/15/2025 Final Disposition",
        "1 / Simple Assault Guilty Plea - Negotiated",
        "Manufacture or Deliver",
        "Smith, Judge A. 01/15/2025",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    assert record["charges"][0]["disposition_raw"] == "Guilty Plea - Negotiated"


def test_section_furniture_run_not_appended():
    """A section-header furniture run after a disposition is NOT appended."""
    page = build_mc(
        "Trial",
        "01/15/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        "COMMONWEALTH INFORMATION ATTORNEY INFORMATION Office Private",
        "Smith, Judge A. 01/15/2025",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    assert record["charges"][0]["disposition_raw"] == "Guilty"


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


# ===========================================================================
# Task 18.3 hardening: held-case event_date/event_name, min_assumed annotation,
# third-party name guard (SENTINEL_COLLISION). Synthetic text only (fictional
# surname Example / placeholder docket).
# ===========================================================================


# --- Item 1: held-case event_date / event_name ------------------------------


def test_held_charge_captures_event_date_and_name_disposition_stays_null():
    """A non-terminal (Not Final) event records event_date and event_name on the
    charge; disposition_raw/disposition_date/disposition_judge_raw stay null and
    sentences stays empty (held cases have no disposition)."""
    record, _, _ = parse_docket_text(DOCKET_MC, [mc_held_page()], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["event_date"] == "2024-06-15"
    assert charge["event_name"] == "Held for Court"
    assert charge["disposition_raw"] is None
    assert charge["disposition_date"] is None
    assert charge["disposition_judge_raw"] is None
    assert charge["sentences"] == []


def test_terminal_charge_has_no_event_fields():
    """A terminal charge carries no event_date/event_name keys — the fields are
    conditional (non-terminal only), so terminal output stays byte-identical to
    the Capstone baseline."""
    page = build_mc(
        "Trial",
        "01/15/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        "Torres, Judge A. 01/15/2025",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert "event_date" not in charge
    assert "event_name" not in charge


def test_progression_charge_disposed_after_nonterminal_has_no_event_keys():
    """Check-2 regression: a charge listed under a non-terminal event and then
    disposed under a terminal event on the same docket must end with NO event
    keys and a populated disposition (the placement sweep strips the transient
    event keys once the charge is disposed)."""
    page = build_mc(
        "Preliminary Hearing 06/15/2024 Not Final",
        "1 / Simple Assault",
        "Trial 01/15/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        "Torres, Judge A. 01/15/2025",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert "event_date" not in charge
    assert "event_name" not in charge
    assert charge["disposition_raw"] == "Guilty"
    assert charge["disposition_date"] == "2025-01-15"
    assert charge["disposition_judge_raw"] == "Torres, Judge A."


def test_held_charge_under_multiple_nonterminal_events_latest_wins():
    """Pinned semantic: a held charge listed under two non-terminal events keeps
    the LATEST event-header's date and name (assignment overwrites); disposition
    stays null."""
    page = build_mc(
        "Preliminary Hearing 06/15/2024 Not Final",
        "1 / Simple Assault",
        "Continued Hearing 09/20/2024 Not Final",
        "1 / Simple Assault",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["event_name"] == "Continued Hearing"
    assert charge["event_date"] == "2024-09-20"
    assert charge["disposition_raw"] is None
    assert charge["disposition_date"] is None
    assert charge["disposition_judge_raw"] is None
    assert charge["sentences"] == []


def test_held_event_header_single_line_tolerates_trailing_whitespace():
    """18.4 Required Fix 1: the single-line event-header capture is anchored with
    ``$``; extracted lines are ``.strip()``ed before matching, so a header line
    carrying trailing whitespace still parses to a populated event_date/name."""
    page = build_mc(
        "Held for Court 06/15/2024 Not Final   ",
        "1 / Simple Assault",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["event_date"] == "2024-06-15"
    assert charge["event_name"] == "Held for Court"


def test_held_multiword_event_name_captured_and_date_parseable():
    """18.4 value-verification (unit): a multi-word event name whose date token is
    NOT at index 2 is captured whole (leading text before the date), and
    event_date is a real, parseable ISO date — not an offense fragment or null."""
    from datetime import date

    page = build_mc(
        "Waiver of Preliminary Hearing 07/03/2024 Not Final",
        "1 / Simple Assault",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["event_name"] == "Waiver of Preliminary Hearing"
    assert date.fromisoformat(charge["event_date"]) == date(2024, 7, 3)


# --- 18.5: event-grain disposition routing ----------------------------------
# A Not-Final event routes iff its FIRST charge line's token is in ARD_CLASS;
# a routed event disposes ALL its charge lines (each with its own token);
# routing is decoupled from event_name and the case-status row.


def _mc_two_charge_head() -> list[str]:
    """An MC head whose CHARGES section carries two sequences (for companion
    tests). Fictional; placeholder docket number; no real docket data."""
    return [
        "MUNICIPAL COURT OF PHILADELPHIA COUNTY",
        "DOCKET",
        f"Docket Number: {DOCKET_MC}",
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
        "2 1 18 § 3921 M1 Theft By Unlawful Taking 01/01/2025 X1234567",
        "DISPOSITION SENTENCING/PENALTIES",
    ]


def test_ard_event_routes_via_charge_line_token_not_event_name():
    """18.5 event grain: a Not-Final event routes iff its FIRST charge line's token
    is in ARD_CLASS_DISPOSITIONS — decoupled from event_name (the 18.4 regression
    came from the retired ``'ard' in event_name`` check). event_name here is
    "Status" (no 'ard'), yet the "ARD - County" charge-line token routes the event,
    so the charge ends DISPOSED with judge + sentence, not held."""
    page = build_mc(
        "Status 03/10/2025 Not Final",
        "1 / Simple Assault ARD - County",
        "Torres, Judge A. 03/10/2025",
        "ARD",
        "Max of 12.00 Months",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] == "ARD - County"
    assert charge["disposition_date"] == "2025-03-10"
    assert charge["disposition_judge_raw"] == "Torres, Judge A."
    assert charge["sentences"][0]["sentence_type"] == "ARD"
    assert "event_date" not in charge
    assert "event_name" not in charge


def test_non_terminal_first_line_token_leaves_event_held_silently():
    """A first-line NON_TERMINAL token (here "Held for Court") does not route: the
    charge stays held (event keys recorded, no disposition), and no warning fires
    — it is known vocabulary."""
    page = build_mc(
        "Preliminary Hearing 06/15/2024 Not Final",
        "1 / Simple Assault Held for Court",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] is None
    assert charge["event_name"] == "Preliminary Hearing"
    assert charge["event_date"] == "2024-06-15"
    assert not any(w["code"] == UNKNOWN_NOT_FINAL_DISPOSITION for w in warnings)


def test_wrap_token_proceed_to_court_ard_stays_non_terminal():
    """The wrapped revoked token "Proceed to Court (ARD" (first line of a line-wrap)
    is NON_TERMINAL — it never routes, and warns nothing (corpus-evidenced)."""
    page = build_mc(
        "Violation of Probation 05/01/2025 Not Final",
        "1 / Simple Assault Proceed to Court (ARD",
        "Revoked)",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] is None
    assert charge["event_name"] == "Violation of Probation"
    assert not any(w["code"] == UNKNOWN_NOT_FINAL_DISPOSITION for w in warnings)


def test_rule600_token_routing_unchanged():
    """Routing consumes PRE-repair stream tokens, so the truncated Rule 600 wrap
    token stays in NON_TERMINAL_DISPOSITIONS despite the Task 34.1 repair: a
    first-line "Dismissed - Rule 600 (Speedy" under a Not-Final event does not
    route (charge stays held) and warns nothing — known vocabulary."""
    page = build_mc(
        "Status 03/10/2025 Not Final",
        "1 / Simple Assault Dismissed - Rule 600 (Speedy",
        "Trial)",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] is None
    assert charge["event_name"] == "Status"
    assert not any(w["code"] == UNKNOWN_NOT_FINAL_DISPOSITION for w in warnings)


def test_unknown_first_line_token_warns_review_and_holds():
    """A non-empty first-line token in NEITHER frozenset is novel vocabulary at the
    routing decision point: the event stays held and UNKNOWN_NOT_FINAL_DISPOSITION
    (review severity) fires with structural context only — never the token text."""
    page = build_mc(
        "Status 03/10/2025 Not Final",
        "1 / Simple Assault Frobnicated Beyond Recognition",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] is None  # not routed
    hits = [w for w in warnings if w["code"] == UNKNOWN_NOT_FINAL_DISPOSITION]
    assert len(hits) == 1
    assert hits[0]["charge_sequence"] == 1
    assert hits[0]["section"] == "DISPOSITION SENTENCING/PENALTIES"
    assert "Frobnicated" not in json.dumps(warnings)


def test_event_grain_disposes_companion_line_with_its_own_token():
    """The discriminator shape (docket 7ed52b93628c): a routed ARD event whose
    FIRST line is "ARD - County" disposes its COMPANION line with the companion's
    own token ("Withdrawn"), even though "Withdrawn" is not in any frozenset —
    event grain, Capstone-faithful. No warning (companion is a non-first line)."""
    page = "\n".join(
        [
            *_mc_two_charge_head(),
            "Status 03/10/2025 Not Final",
            "1 / Simple Assault ARD - County",
            "Torres, Judge A. 03/10/2025",
            "ARD",
            "2 / Theft By Unlawful Taking Withdrawn",
        ]
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    by_seq = {c["sequence"]: c for c in record["charges"]}
    assert by_seq[1]["disposition_raw"] == "ARD - County"
    assert by_seq[2]["disposition_raw"] == "Withdrawn"  # companion disposed
    assert "event_name" not in by_seq[2]
    assert not any(w["code"] == UNKNOWN_NOT_FINAL_DISPOSITION for w in warnings)


def test_non_ard_first_guard_warns_on_stranded_ard_token():
    """The non-ARD-first guard: an ARD_CLASS token on a NON-FIRST line of an
    UNROUTED Not-Final event (first line NON_TERMINAL) is a potentially un-routed
    genuine ARD disposition — it does not route (event grain decides on the first
    line) but fires UNKNOWN_NOT_FINAL_DISPOSITION so it cannot vanish silently."""
    page = "\n".join(
        [
            *_mc_two_charge_head(),
            "Status 03/10/2025 Not Final",
            "1 / Simple Assault Held for Court",
            "2 / Theft By Unlawful Taking ARD - County",
        ]
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    by_seq = {c["sequence"]: c for c in record["charges"]}
    assert by_seq[1]["disposition_raw"] is None  # event did not route
    assert by_seq[2]["disposition_raw"] is None  # stranded ARD stays held
    hits = [w for w in warnings if w["code"] == UNKNOWN_NOT_FINAL_DISPOSITION]
    assert len(hits) == 1
    assert hits[0]["charge_sequence"] == 2


def test_ard_progression_final_overwrites_raw_keeps_judge_and_sentence():
    """Pattern B / progression: an ARD "Status" event supplies judge + sentence;
    a later Final event carrying ONLY the disposition (no judge/sentence lines)
    overwrites disposition_raw and (32.2 STOP ruling, option a) supplies its
    OWN event-line disposition date — string and date come from the same
    governing block. Judge and the ARD sentence (with its judge-line sentence
    date) stay from the ARD event."""
    page = build_mc(
        "Status 03/10/2025 Not Final",
        "1 / Simple Assault ARD - County",
        "Conroy, David H. 03/10/2025",
        "ARD",
        "Max of 6.00 Months",
        "Waiver Trial 07/01/2025 Final Disposition",
        "1 / Simple Assault Nolle Prossed",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] == "Nolle Prossed"  # from the Final event
    assert charge["disposition_date"] == "2025-07-01"  # the Final event's own date
    assert charge["disposition_judge_raw"] == "Conroy, David H."  # from the ARD event
    assert len(charge["sentences"]) == 1  # the ARD sentence, not overwritten
    assert charge["sentences"][0]["sentence_type"] == "ARD"
    assert charge["sentences"][0]["sentence_date"] == "2025-03-10"  # ARD judge line


# --- Item 2: min_assumed annotation -----------------------------------------


def test_min_assumed_true_when_min_filled_from_max():
    page = build_mc(
        "Trial",
        "01/15/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        "Torres, Judge A. 01/15/2025",
        "Confinement",
        "Max of 12.00 Months",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    sentence = record["charges"][0]["sentences"][0]
    assert sentence["min_assumed"] is True
    assert sentence["min_days"] == sentence["max_days"] == 360


def test_min_assumed_true_when_filled_from_flat_value():
    page = build_mc(
        "Trial",
        "01/15/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        "Torres, Judge A. 01/15/2025",
        "Confinement",
        "11.00 Months",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    sentence = record["charges"][0]["sentences"][0]
    assert sentence["min_assumed"] is True
    assert sentence["min_days"] == sentence["max_days"] == 330


def test_min_assumed_absent_when_min_parsed_directly():
    """Min parsed directly (max filled from min): min_assumed is absent, not
    False — the key appears only when min was actually assumed."""
    page = build_mc(
        "Trial",
        "01/15/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        "Torres, Judge A. 01/15/2025",
        "Confinement",
        "Min of 11.00 Months",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    sentence = record["charges"][0]["sentences"][0]
    assert "min_assumed" not in sentence
    assert sentence["min_days"] == 330


def test_min_assumed_absent_when_both_bounds_parsed():
    page = build_mc(
        "Trial",
        "01/15/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        "Torres, Judge A. 01/15/2025",
        "Confinement",
        "Min of 11.00 Months Max of 23.00 Months",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    sentence = record["charges"][0]["sentences"][0]
    assert "min_assumed" not in sentence
    assert sentence["min_days"] == 330
    assert sentence["max_days"] == 690


# --- Item 3 / Q2: third-party name guard (SENTINEL_COLLISION) ----------------


def _cp_with_assigned_judge(judge: str) -> str:
    """A CP sheet whose assigned-judge slot carries ``judge``. Defendant surname
    is the fictional Example so a judge surnamed Example is a real collision."""
    return "\n".join(
        [
            "COURT OF COMMON PLEAS OF PHILADELPHIA COUNTY",
            "DOCKET",
            "Docket Number: CP-51-CR-0000000-2025",
            "CASE INFORMATION",
            f"Judge Assigned: {judge} Date Filed: 02/03/2025",
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
    )


def test_assigned_judge_collision_nulled_and_flagged():
    """A name-shaped assigned judge whose surname whole-token-collides with the
    defendant's is nulled and flagged SENTINEL_COLLISION; Date Filed on the same
    line is still parsed and no collision text leaks into the warning."""
    page = _cp_with_assigned_judge("Example, Judge A.")
    record, _, warnings = parse_docket_text(DOCKET_CP, [page], salt=TEST_SALT)
    assert record["case"]["assigned_judge_raw"] is None
    assert record["case"]["filed_date"] == "2025-02-03"
    collision = [w for w in warnings if w["code"] == SENTINEL_COLLISION]
    assert len(collision) == 1
    assert collision[0]["section"] == "CASE INFORMATION"
    assert "Example" not in json.dumps(warnings)


def test_assigned_judge_fragment_substring_does_not_collide():
    """A judge surname that merely CONTAINS a name part as a sub-span
    ("Exampleton" contains "Example") is not a whole-token collision and passes
    untouched — the 18.3 Q1 fragment recovery, at the guard label context."""
    page = _cp_with_assigned_judge("Exampleton, Judge A.")
    record, _, warnings = parse_docket_text(DOCKET_CP, [page], salt=TEST_SALT)
    assert record["case"]["assigned_judge_raw"] == "Exampleton, Judge A."
    assert not any(w["code"] == SENTINEL_COLLISION for w in warnings)


# --- 32.2: event-line disposition dates + seq-99,999 charge guard ------------


def build_mc_with_charges(charge_rows: list[str], disposition_body: list[str]) -> str:
    """An MC sheet with custom CHARGES rows plus a DISPOSITION section body."""
    return "\n".join(
        [
            *_MC_HEAD[:-1],  # fixed head up to the column-header line
            *charge_rows,
            "DISPOSITION SENTENCING/PENALTIES",
            *disposition_body,
        ]
    )


def test_final_block_dates_rows_without_judge_lines():
    """The core 32.2 fix: disposed rows under a dated Final Disposition event
    carry the EVENT-line date even when no judge line prints (the formerly
    dateless disposed class)."""
    page = build_mc(
        "Waiver Trial 06/09/2026 Final Disposition",
        "1 / Simple Assault Nolle Prossed",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] == "Nolle Prossed"
    assert charge["disposition_date"] == "2026-06-09"
    assert charge["disposition_judge_raw"] is None
    assert charge["sentences"] == []


def test_latest_final_block_wins_string_and_date_together():
    """N1-07 pattern: a later Final block re-disposes the charge; string AND
    date both come from the later block (same governing block)."""
    page = build_mc(
        "Waiver Trial 05/01/2025 Final Disposition",
        "1 / Simple Assault Nolle Prossed",
        "Status 05/15/2025 Final Disposition",
        "1 / Simple Assault Guilty",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] == "Guilty"
    assert charge["disposition_date"] == "2025-05-15"


def test_not_final_dated_block_contributes_no_date():
    """S5-04 pattern: an earlier Not-Final block with a disposition token and a
    dated line is excluded; the later Final block supplies string and date."""
    page = build_mc(
        "Preliminary Hearing 12/12/2025 Not Final",
        "1 / Simple Assault Dismissed - LOE",
        "Reyes, Judge M. 12/12/2025",
        "ARC Status 03/30/2026 Final Disposition",
        "1 / Simple Assault Guilty Plea - Negotiated",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] == "Guilty Plea - Negotiated"
    assert charge["disposition_date"] == "2026-03-30"
    assert charge["disposition_judge_raw"] is None
    # Disposed charge carries no held-event keys (placement sweep unchanged).
    assert "event_date" not in charge and "event_name" not in charge


@pytest.mark.parametrize("held_form", sorted(HELD_FOR_COURT_DISPOSITIONS))
def test_held_form_stays_dateless_inside_dated_final_block(held_form):
    """Requirement 4 / N2-S6-02 pattern: a held-for-court row inside a dated
    Final block keeps its recorded form but NEVER takes the event date
    (Mechanism A preserved; vocabulary imported, never re-listed)."""
    page = build_mc(
        "Preliminary Hearing 09/11/2025 Final Disposition",
        f"1 / Simple Assault {held_form}",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] == held_form
    assert charge["disposition_date"] is None


def test_held_sibling_dateless_while_terminal_sibling_dated():
    """S6-02 shape: held row and terminal row in the SAME dated Final block —
    only the terminal row takes the event date."""
    page = build_mc_with_charges(
        [
            "1 1 18 § 2701 M1 Simple Assault 01/01/2025 X1234567",
            "2 1 18 § 2702 F1 Aggravated Assault 01/01/2025 X1234567",
        ],
        [
            "Preliminary Hearing 09/11/2025 Final Disposition",
            "1 / Simple Assault Held for Court",
            "2 / Aggravated Assault Dismissed - LOE",
        ],
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    held, terminal = record["charges"]
    assert held["disposition_raw"] == "Held for Court"
    assert held["disposition_date"] is None
    assert terminal["disposition_raw"] == "Dismissed - LOE"
    assert terminal["disposition_date"] == "2025-09-11"


def test_ard_governing_block_keeps_judge_line_dating():
    """Decision 4 (as restated by the STOP ruling): a charge whose GOVERNING
    block is the ARD-routed Not-Final event keeps judge-line dating unchanged —
    even when the judge-line date differs from the event-line date."""
    page = build_mc(
        "Status 03/10/2025 Not Final",
        "1 / Simple Assault ARD - County",
        "Conroy, David H. 04/15/2025",
        "ARD",
        "Max of 6.00 Months",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] == "ARD - County"
    assert charge["disposition_date"] == "2025-04-15"  # judge line, NOT event line
    assert charge["sentences"][0]["sentence_date"] == "2025-04-15"


def test_unparseable_final_event_date_leaves_row_dateless():
    """Decision 7 failure mode: the event regex matches but the date fails
    parse_date -> the row stays dateless (surfaced downstream by the existing
    MISSING_DISPOSITION_DATE envelope warning); no new warning code."""
    page = build_mc(
        "Waiver Trial 99/99/2025 Final Disposition",
        "1 / Simple Assault Guilty",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] == "Guilty"
    assert charge["disposition_date"] is None


def test_empty_token_row_takes_no_event_date():
    """Q5 guard: a charge line with no disposition token stays string-less AND
    dateless — the date-without-string row shape must never exist."""
    page = build_mc(
        "Waiver Trial 05/01/2025 Final Disposition",
        "1 / Simple Assault",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] is None
    assert charge["disposition_date"] is None


def test_deferred_sentencing_divergence_dates_split():
    """S5-03 pattern: event date != judge-line date -> disposition_date is the
    event-line date, sentence_date is the judge-line (Sentence Date column)
    date, on the same charge."""
    page = build_mc(
        "Pretrial Bring Back 01/29/2026 Final Disposition",
        "1 / Simple Assault Guilty",
        "Conroy, David H. 05/21/2026",
        "Confinement",
        "Min of 3.00 Months Max of 12.00 Months",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_date"] == "2026-01-29"
    assert charge["disposition_judge_raw"] == "Conroy, David H."
    assert charge["sentences"][0]["sentence_date"] == "2026-05-21"


def test_sentence_dates_ride_their_own_blocks_judge_line():
    """D-C parity shape (the 35-row divergent class): a re-disposed charge
    keeps each sentence component's date from ITS block's judge line, exactly
    as pre-32.2."""
    page = build_mc(
        "Trial 02/01/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        "Reyes, Judge M. 02/01/2025",
        "Confinement",
        "Min of 1.00 Months Max of 2.00 Months",
        "Status 04/01/2025 Final Disposition",
        "1 / Simple Assault Guilty Plea - Negotiated",
        "Conroy, David H. 04/05/2025",
        "Probation",
        "Max of 12.00 Months",
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] == "Guilty Plea - Negotiated"
    assert charge["disposition_date"] == "2025-04-01"  # later Final event line
    dates = [s["sentence_date"] for s in charge["sentences"]]
    assert dates == ["2025-02-01", "2025-04-05"]  # each block's own judge line


def test_charges_placeholder_rows_and_wrap_dropped():
    """C4 guard: a seq-99,999 placeholder row AND its wrapped continuation line
    are dropped — the last real charge's offense/statute/grade stay clean."""
    page = build_mc_with_charges(
        [
            "1 1 18 § 2701 M1 Simple Assault 01/01/2025 X1234567",
            "99,999 1 0 § 0 Disposed at Lower Court 02/13/2020",
            "wrapped placeholder continuation text",
        ],
        [
            "Waiver Trial 06/09/2026 Final Disposition",
            "1 / Simple Assault Nolle Prossed",
        ],
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    assert len(record["charges"]) == 1
    charge = record["charges"][0]
    assert charge["offense"] == "Simple Assault"
    assert charge["statute"] == "18 § 2701 M1"


def test_placeholder_state_resets_at_next_real_charge_row():
    """Required fix 2: a real charge row after a placeholder block resets the
    wrap state and parses normally — nothing is dropped beyond the placeholder
    block itself."""
    page = build_mc_with_charges(
        [
            "1 1 18 § 2701 M1 Simple Assault 01/01/2025 X1234567",
            "99,999 1 0 § 0 Disposed at Lower Court 02/13/2020",
            "wrapped placeholder continuation text",
            "2 1 18 § 2702 F1 Aggravated Assault 01/01/2025 X1234567",
        ],
        [
            "Waiver Trial 06/09/2026 Final Disposition",
            "1 / Simple Assault Nolle Prossed",
            "2 / Aggravated Assault Nolle Prossed",
        ],
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    assert [c["sequence"] for c in record["charges"]] == [1, 2]
    first, second = record["charges"]
    assert first["offense"] == "Simple Assault"
    assert second["offense"] == "Aggravated Assault"
    assert second["statute"] == "18 § 2702 F1"
    assert second["disposition_date"] == "2026-06-09"


def test_disposition_section_placeholder_lines_stay_inert():
    """Regression lock: seq-99,999 lines in the DISPOSITION section are NOT
    guarded (proven inert on the audit sheets) — the parse is byte-identical
    with or without them."""
    body = [
        "Waiver Trial 06/09/2026 Final Disposition",
        "1 / Simple Assault Guilty",
        "Reyes, Judge M. 06/09/2026",
        "Confinement",
        "Min of 1.00 Months Max of 2.00 Months",
    ]
    placeholder_lines = [
        "99,999 Disposed at Lower Court 02/13/2020 Withdrawn",
        "99,999 Disposed at Lower Court 02/13/2020 Withdrawn",
    ]
    with_lines, _, _ = parse_docket_text(
        DOCKET_MC, [build_mc(*body, *placeholder_lines)], salt=TEST_SALT
    )
    without_lines, _, _ = parse_docket_text(
        DOCKET_MC, [build_mc(*body)], salt=TEST_SALT
    )
    with_lines.pop("parsed_at")
    without_lines.pop("parsed_at")
    assert with_lines == without_lines


# ===========================================================================
# Task 34.2: sentence-condition fragment guard. A condition line beginning
# with a slash-date also matches the disposition charge-line regex (month
# digit = sequence); pre-guard it overwrote a real capture (fragment-victim
# class) or left a phantom current_charge_seq that KeyError'd at the
# component save (the quarantined CP KeyError class). The guard rejects the
# match on the structural date-head shape; the line follows the natural
# non-charge-line flow, silently. Synthetic text only.
# ===========================================================================

_MC_HEAD_TWO_CHARGES = [
    *_MC_HEAD[:-1],
    "1 1 18 § 2701 M1 Simple Assault 01/01/2025 X1234567",
    "2 2 18 § 3921 M2 Theft 01/01/2025 X1234567",
]


def build_mc_two_charges(*disposition_body: str) -> str:
    """An MC sheet with two charges plus a DISPOSITION section body."""
    return "\n".join(
        [*_MC_HEAD_TWO_CHARGES, "DISPOSITION SENTENCING/PENALTIES", *disposition_body]
    )


def test_fragment_guard_rejects_slash_date_line_preserves_disposition():
    """The victim shape: a slash-date condition line whose month digit equals
    an existing sequence no longer overwrites that charge's real disposition,
    re-dates it, or joins the component raw_text. Silent — no warning."""
    page = build_mc(
        "Trial 01/15/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        "Reyes, Judge M. 01/15/2025",
        "Probation",
        "Min of 6.00 Months Max of 12.00 Months",
        "1/20/25 Report to courtroom 402",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    assert len(record["charges"]) == 1
    charge = record["charges"][0]
    assert charge["disposition_raw"] == "Guilty"
    assert charge["disposition_date"] == "2025-01-15"
    assert charge["disposition_judge_raw"] == "Reyes, Judge M."
    [sentence] = charge["sentences"]
    assert "courtroom" not in sentence["raw_text"]
    assert warnings == []


@pytest.mark.parametrize(
    "fragment_line",
    [
        "1/20/25 Report to courtroom 402",
        "1/20/2025 Surrender by noon",
        "1/20/25",
        "1/20/25, then report",
    ],
)
def test_fragment_shapes_rejected_at_charge_match(fragment_line):
    """Rejection boundary: D/DD/YY and D/DD/YYYY heads, bare fragments, and
    non-digit boundaries after the year (recon-exact ``(?!\\d)``) all reject.
    Month digit 1 = the real sequence, so any miss would overwrite Guilty."""
    page = build_mc(
        "Trial 01/15/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        "Reyes, Judge M. 01/15/2025",
        fragment_line,
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] == "Guilty"
    assert charge["disposition_date"] == "2025-01-15"
    assert warnings == []


@pytest.mark.parametrize(
    ("charge_line", "expected_disposition"),
    [
        ("1 / Simple Assault Guilty", "Guilty"),
        ("1/Simple Assault Guilty", "Guilty"),
        ("1/15 Grams Possession Guilty", "15 Grams Possession Guilty"),
        ("1/15/20261 Count Guilty", "15/20261 Count Guilty"),
    ],
)
def test_genuine_charge_lines_still_match(charge_line, expected_disposition):
    """The false-positive lock: canonical spaced columns, tight spacing, a
    numeric two-segment head (no second slash), and a 5-digit run after the
    second slash (not a year) all still match as charge lines."""
    page = build_mc(
        "Trial 01/15/2025 Final Disposition",
        charge_line,
    )
    record, _, _ = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] == expected_disposition


def test_fragment_guard_preserves_component_attachment():
    """The cross-sequence steal (F-C class): a component line after the
    fragment stays with the true owner (charge 2), not the month-digit
    charge (charge 1)."""
    page = build_mc_two_charges(
        "Trial 01/15/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        "Reyes, Judge M. 01/15/2025",
        "2 / Theft Guilty",
        "Reyes, Judge M. 01/15/2025",
        "Probation",
        "Min of 6.00 Months Max of 12.00 Months",
        "1/20/25 Report to courtroom 402",
        "Fines and Costs",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    first, second = record["charges"]
    assert first["disposition_raw"] == "Guilty"
    assert first["sentences"] == []
    assert [s["sentence_type"] for s in second["sentences"]] == [
        "Probation",
        "Fines and Costs",
    ]
    assert warnings == []


def test_fragment_guard_phantom_sequence_with_component_line_parses():
    """The crash class (F-Q): a fragment whose month digit matches NO charge,
    followed by a component block. Pre-guard this KeyError'd at the component
    save (phantom current_charge_seq); post-guard it parses and the component
    attaches to the real current charge."""
    page = build_mc(
        "Trial 01/15/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        "Reyes, Judge M. 01/15/2025",
        "9/20/25 Report to courtroom 402",
        "Probation",
        "Min of 6.00 Months Max of 12.00 Months",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] == "Guilty"
    [sentence] = charge["sentences"]
    assert sentence["sentence_type"] == "Probation"
    assert warnings == []


def test_rejected_fragment_with_duration_units_joins_component_raw_text():
    """The natural non-charge-line flow, duration arm: a rejected fragment
    carrying duration units joins the OPEN component's raw_text via the
    existing continuation heuristic — the pinned raw_text delta arm."""
    page = build_mc(
        "Trial 01/15/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        "Reyes, Judge M. 01/15/2025",
        "Probation",
        "Min of 6.00 Months Max of 12.00 Months",
        "1/20/25 surrender within 10 days",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] == "Guilty"
    [sentence] = charge["sentences"]
    assert "surrender within 10 days" in sentence["raw_text"]
    assert warnings == []


def test_rejected_fragment_in_judge_slot_leaves_judge_capture_intact():
    """The natural non-charge-line flow, judge-slot arm: a fragment between
    the charge line and its judge line is skipped with the slot still open —
    the judge is captured from the next line as before."""
    page = build_mc(
        "Trial 01/15/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        "1/20/25 Report to courtroom 402",
        "Reyes, Judge M. 01/15/2025",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] == "Guilty"
    assert charge["disposition_judge_raw"] == "Reyes, Judge M."
    assert warnings == []


# ===========================================================================
# Task 34.3: column-concatenation guard. A boundary-lost disposition row hands
# the charge-line strip a token that still CONTAINS its statute (offense
# re-print + disposition phrase + statute + trailing columns concatenated by
# column loss); pre-guard the whole row became disposition_raw and took the
# event date. The gate rejects the capture at the routed-event assignment —
# raw left unassigned, date never reached, SUSPECT_DISPOSITION_TOKEN emitted.
# Placement is load-bearing: the legitimate §-bearing NON_TERMINAL vocabulary
# is consulted only under unrouted Not-Final events and stays unreachable.
# Synthetic text only (fictional offenses/statutes, placeholder docket).
# ===========================================================================


def test_concat_token_rejected_undisposed_with_warning():
    """The C-U arm: the defect row's charge ends undisposed and dateless with
    the structural warning; the healthy sibling in the same event is untouched
    (containment)."""
    page = build_mc_two_charges(
        "Trial 01/15/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        "2 / Thft By Unlwf Tkg Dismissed M2 18 § 3921 §§ A Trial Div",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    healthy, rejected = record["charges"]
    assert healthy["disposition_raw"] == "Guilty"
    assert healthy["disposition_date"] == "2025-01-15"
    assert rejected["disposition_raw"] is None
    assert rejected["disposition_date"] is None
    [warning] = warnings
    assert warning["code"] == SUSPECT_DISPOSITION_TOKEN
    assert warning["charge_sequence"] == 2


def test_concat_held_embedding_rejected_dateless_held_arm():
    """The C-H arm: a rejected token EMBEDDING a held form ends exactly where
    a held charge ends — null disposition, dateless, not disposed in the
    envelope's eyes (the existing null-disposition non-terminal path; no held
    machinery is modified, the row simply reaches it)."""
    page = build_mc(
        "Preliminary Hearing 09/11/2025 Final Disposition",
        "1 / Smpl Aslt Held for Court M1 18 § 2701 §§ A Trial Div",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] is None
    assert charge["disposition_date"] is None
    assert not _charge_has_disposition(charge)
    [warning] = warnings
    assert warning["code"] == SUSPECT_DISPOSITION_TOKEN


def test_concat_guard_never_overwrites_earlier_disposition():
    """The C-U-P unmask shape: a rejected line never masks a genuine earlier
    writer — raw is left UNASSIGNED on rejection (not forced None), so the
    earlier valid block's string AND date both survive (contrast
    test_latest_final_block_wins_string_and_date_together)."""
    page = build_mc(
        "Waiver Trial 05/01/2025 Final Disposition",
        "1 / Simple Assault Guilty",
        "Status 05/15/2025 Final Disposition",
        "1 / Smpl Aslt Nolle Prossed M1 18 § 2701 §§ A Trial Div",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] == "Guilty"
    assert charge["disposition_date"] == "2025-05-01"
    [warning] = warnings
    assert warning["code"] == SUSPECT_DISPOSITION_TOKEN


def test_disposition_vocabulary_never_contains_statute_cue():
    """The false-positive boundary: no member of any vocabulary the gate can
    see as an ACCEPTED disposition carries '§' — so no legitimate capture can
    ever satisfy the predicate. The six §-bearing NON_TERMINAL members exist
    (premise of the placement argument) but are routing-suppression
    vocabulary, unreachable by the post-routing gate."""
    for vocab in (
        DISPOSITION_OUTCOME_MAP.keys(),
        HELD_FOR_COURT_DISPOSITIONS,
        ARD_CLASS_DISPOSITIONS,
    ):
        assert not [v for v in vocab if "§" in v]
    assert [v for v in NON_TERMINAL_DISPOSITIONS if "§" in v]


@pytest.mark.parametrize(
    "member",
    sorted(v for v in NON_TERMINAL_DISPOSITIONS if "§" in v),
)
def test_nonterminal_statute_tokens_unaffected_at_routing(member):
    """Placement lock: a legitimate §-bearing NON_TERMINAL token as the FIRST
    charge line of a Not-Final event behaves exactly as before the guard —
    the event stays held SILENTLY (no UNKNOWN_NOT_FINAL_DISPOSITION, no
    SUSPECT_DISPOSITION_TOKEN) and the charge keeps its held-event keys."""
    page = build_mc(
        "Preliminary Hearing 09/11/2025 Not Final",
        f"1 / {member}",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] is None
    assert charge["disposition_date"] is None
    assert charge["event_name"] == "Preliminary Hearing"
    assert warnings == []


def test_rejected_charge_keeps_nonterminal_event_keys():
    """18.3 event-key placement on a C-U row: a charge that ends the parse
    undisposed because its Final-block capture was rejected KEEPS the event
    keys recorded by an earlier non-terminal event (the placement sweep only
    strips them from disposed charges)."""
    page = build_mc(
        "Preliminary Hearing 03/10/2025 Not Final",
        "1 / Simple Assault Held for Court",
        "Trial 05/15/2025 Final Disposition",
        "1 / Smpl Aslt Dismissed M1 18 § 2701 §§ A Trial Div",
    )
    record, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    charge = record["charges"][0]
    assert charge["disposition_raw"] is None
    assert charge["event_name"] == "Preliminary Hearing"
    assert charge["event_date"] == "2025-03-10"
    [warning] = warnings
    assert warning["code"] == SUSPECT_DISPOSITION_TOKEN


def test_concat_warning_payload_structural_only():
    """The warning carries structural context ONLY: code, section, charge
    sequence — never text, never a captured span."""
    page = build_mc(
        "Trial 01/15/2025 Final Disposition",
        "1 / Smpl Aslt Dismissed M1 18 § 2701 §§ A Trial Div",
    )
    _, _, warnings = parse_docket_text(DOCKET_MC, [page], salt=TEST_SALT)
    [warning] = warnings
    assert set(warning) == {"code", "section", "charge_sequence"}
    assert warning["code"] == SUSPECT_DISPOSITION_TOKEN
    assert warning["section"] == "DISPOSITION SENTENCING/PENALTIES"
    assert warning["charge_sequence"] == 1
