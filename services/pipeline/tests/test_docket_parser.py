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
from pipeline.warning_codes import (
    SENTINEL_COLLISION,
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
    overwrites disposition_raw but leaves judge/date/sentences intact (latest-
    valid-event-wins). Reproduces the Capstone-faithful shape."""
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
    assert charge["disposition_date"] == "2025-03-10"  # from the ARD event
    assert charge["disposition_judge_raw"] == "Conroy, David H."  # from the ARD event
    assert len(charge["sentences"]) == 1  # the ARD sentence, not overwritten
    assert charge["sentences"][0]["sentence_type"] == "ARD"


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
