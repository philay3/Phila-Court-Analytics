"""Envelope builder + observation layer tests (Task 18.1).

Synthetic fixtures only: fictional surname Example and docket
MC-51-CR-0000000-2025. No real names, captions, or docket content appears here.
"""

from __future__ import annotations

import json

from pipeline import envelope as env
from pipeline import warning_codes as wc
from pipeline.docket_parser import parse_docket_text
from pipeline.extraction import STATUS_PARTIAL, STATUS_SUCCESS

TEST_SALT = "test-salt"
DOCKET = "MC-51-CR-0000000-2025"
SOURCE_HASH = "a" * 64
TEXT_HASH = "b" * 64

BASE_HEAD = [
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


def build(*extra: str) -> str:
    return "\n".join(BASE_HEAD + list(extra))


# --- fixtures for each emission / status --------------------------------------

# Charges present, no disposition section: no terminal event -> NON_TERMINAL_CASE.
UNDISPOSED = build()

# A genuine Final Disposition with a judge date and a parseable sentence: clean,
# terminal, no warnings.
DISPOSED_CLEAN = build(
    "DISPOSITION SENTENCING/PENALTIES",
    "Trial",
    "01/15/2025 Final Disposition",
    "1 / Simple Assault Guilty",
    "Judge B. 01/15/2025",
    "Confinement",
    "Max of 12.00 Months",
)

# Interim non-final event PLUS a genuine final disposition: must NOT flag
# NON_TERMINAL_CASE (a terminal event is present).
NON_FINAL_THEN_FINAL = build(
    "DISPOSITION SENTENCING/PENALTIES",
    "Preliminary Hearing",
    "01/10/2025 Not Final",
    "Trial",
    "01/15/2025 Final Disposition",
    "1 / Simple Assault Guilty",
    "Judge B. 01/15/2025",
    "Confinement",
    "Max of 12.00 Months",
)

# "Life" sentence: to_days returns None on a present duration -> UNPARSEABLE_DURATION.
LIFE_DURATION = build(
    "DISPOSITION SENTENCING/PENALTIES",
    "Trial",
    "01/15/2025 Final Disposition",
    "1 / Simple Assault Guilty",
    "Judge B. 01/15/2025",
    "Confinement",
    "Min of Life Max of Life",
)

# Disposed charge with no judge/date line AND an unparseable event-line date
# (32.2 decision-7 failure mode: the event regex matches but parse_date fails),
# so disposition_date and sentence_date are both None ->
# MISSING_DISPOSITION_DATE + MISSING_SENTENCE_DATE. Pre-32.2 this specimen
# needed only the absent judge line; the event-line date now dates disposed
# rows, so the dateless shape requires the unparseable event date.
MISSING_DATES = build(
    "DISPOSITION SENTENCING/PENALTIES",
    "Trial",
    "99/99/2025 Final Disposition",
    "1 / Simple Assault Guilty",
    "Confinement",
    "Max of 12.00 Months",
)

# The quarantined KeyError specimen shape: a disposition references an uncaptured
# charge sequence (2), so the sentence-type branch does parsed_charges[2] -> KeyError.
KEYERROR_SPECIMEN = build(
    "DISPOSITION SENTENCING/PENALTIES",
    "Trial",
    "01/15/2025 Final Disposition",
    "2 / Aggravated Assault Guilty",
    "Confinement",
    "Max of 12.00 Months",
)

# 18.2 Item 1: a sentence fragment ending in a date lands in the disposition
# judge slot -> guard nulls the judge field and emits SUSPECT_JUDGE_LINE.
JUDGE_FRAGMENT = build(
    "DISPOSITION SENTENCING/PENALTIES",
    "Trial",
    "01/15/2025 Final Disposition",
    "1 / Simple Assault Guilty",
    "Confinement Min of 11.00 Months 01/15/2025",
)

# 18.2 Item 3: an amended-charge marker in disposition_raw -> SUSPECTED_AMENDED_CHARGE.
AMENDED_CHARGE = build(
    "DISPOSITION SENTENCING/PENALTIES",
    "Trial",
    "01/15/2025 Final Disposition",
    "1 / Simple Assault Amended",
    "Judge B. 01/15/2025",
)

# 18.3 Item 1: a held (Not Final) event -> charge carries event_date/event_name,
# disposition stays null, and NON_TERMINAL_CASE is emitted.
HELD_FOR_COURT = build(
    "DISPOSITION SENTENCING/PENALTIES",
    "Held for Court 06/15/2024 Not Final",
    "1 / Simple Assault",
)

# 18.3 Q2: a disposition judge whose surname equals the defendant's ->
# third-party name guard nulls the field and emits SENTINEL_COLLISION.
JUDGE_COLLISION = build(
    "DISPOSITION SENTENCING/PENALTIES",
    "Trial",
    "01/15/2025 Final Disposition",
    "1 / Simple Assault Guilty",
    "Example, Judge A. 01/15/2025",
)

# Name present, DOB absent: parse_docket_text raises ParseError.
PARSEERROR_SPECIMEN = "\n".join(
    [
        "MUNICIPAL COURT OF PHILADELPHIA COUNTY",
        "DEFENDANT INFORMATION",
        "CASE PARTICIPANTS",
        "Participant Type Name",
        "Defendant Example, Chris",
    ]
)


def make_envelope(page: str, *, extraction_status: str = STATUS_SUCCESS) -> dict:
    return env.parse_document(
        DOCKET,
        [page],
        source_sha256=SOURCE_HASH,
        text_hash=TEXT_HASH,
        provenance_path=None,
        extraction_status=extraction_status,
        salt=TEST_SALT,
    )


def codes_of(envelope: dict) -> set[str]:
    return env.collect_codes([envelope])


# --- criterion 3: envelope shape ----------------------------------------------

EXPECTED_ENVELOPE_KEYS = {
    "source_sha256",
    "parser_version",
    "extraction_artifact",
    "record",
    "warnings",
    "review_needed",
    "status",
    "created_at",
    "error",
}


def _all_keys(obj) -> set:
    keys: set = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= _all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            keys |= _all_keys(v)
    return keys


def test_envelope_shape_has_exactly_the_pinned_fields():
    envelope = make_envelope(DISPOSED_CLEAN)
    assert set(envelope) == EXPECTED_ENVELOPE_KEYS
    assert envelope["parser_version"] == env.ENVELOPE_PARSER_VERSION == 6
    assert set(envelope["extraction_artifact"]) == {
        "artifact_id",
        "text_hash",
        "provenance_path",
    }
    assert envelope["status"] == env.PARSE_STATUS_PARSED
    assert envelope["error"] is None


def test_envelope_has_no_numeric_confidence_field_anywhere():
    envelope = make_envelope(DISPOSED_CLEAN)
    keys = _all_keys(envelope)
    for forbidden in ("confidence", "score", "probability", "odds"):
        assert forbidden not in keys


def test_failed_envelope_shape_and_structural_error():
    envelope = make_envelope(KEYERROR_SPECIMEN)
    assert set(envelope) == EXPECTED_ENVELOPE_KEYS
    assert envelope["status"] == env.PARSE_STATUS_FAILED
    assert envelope["record"] is None
    assert envelope["error"] == {
        "code": wc.UNSUPPORTED_FORMAT,
        "exception_class": "KeyError",
    }
    assert envelope["review_needed"] is True


# --- criterion 5: record identity (the non-negotiable core) -------------------


def test_embedded_record_is_field_identical_to_direct_parse():
    record_direct, _, _ = parse_docket_text(DOCKET, [DISPOSED_CLEAN], salt=TEST_SALT)
    envelope = make_envelope(DISPOSED_CLEAN)
    embedded = envelope["record"]
    # parsed_at is the only per-run field (a timestamp), excluded exactly as 17.3
    # excludes it; everything else must be byte/field-identical.
    a = {k: v for k, v in embedded.items() if k != "parsed_at"}
    b = {k: v for k, v in record_direct.items() if k != "parsed_at"}
    assert a == b
    # No key anywhere in the record was added, removed, or renamed.
    assert _all_keys(embedded) == _all_keys(record_direct)


def test_envelope_embeds_the_parser_record_object_verbatim(monkeypatch):
    """The builder embeds the parser's returned object unchanged (by reference).

    Proven directly: patch the parser to return a sentinel record and assert the
    envelope's record IS that object — nothing wraps, copies, or reshapes it.
    """
    sentinel = {"charges": [], "marker": object()}
    monkeypatch.setattr(env, "parse_docket_text", lambda *a, **k: (sentinel, [], []))
    envelope = make_envelope(DISPOSED_CLEAN)
    assert envelope["record"] is sentinel


# --- criterion 4: warnings carry structural context only ----------------------


def test_warnings_carry_no_docket_text_names_or_raw_values():
    _, sentinels, _ = parse_docket_text(DOCKET, [LIFE_DURATION], salt=TEST_SALT)
    envelope = make_envelope(LIFE_DURATION)
    assert envelope["warnings"]  # this fixture must produce a warning
    blob = json.dumps(envelope["warnings"])
    # No identifying sentinel (name, name part, DOB) reached a warning payload.
    for sentinel in sentinels:
        if len(sentinel.strip()) >= 3:
            assert sentinel not in blob
    # No captured raw value ("Life") and no docket number leaked either.
    assert "Life" not in blob
    assert DOCKET not in blob


# --- criterion 7: one test per observation-only emission ----------------------


def test_emit_low_text_extraction_from_status():
    envelope = make_envelope(DISPOSED_CLEAN, extraction_status=STATUS_PARTIAL)
    assert wc.LOW_TEXT_EXTRACTION in codes_of(envelope)


def test_emit_unparseable_duration_on_life():
    envelope = make_envelope(LIFE_DURATION)
    assert codes_of(envelope) == {wc.UNPARSEABLE_DURATION}


def test_emit_missing_disposition_date():
    envelope = make_envelope(MISSING_DATES)
    assert wc.MISSING_DISPOSITION_DATE in codes_of(envelope)


def test_emit_missing_sentence_date():
    envelope = make_envelope(MISSING_DATES)
    assert wc.MISSING_SENTENCE_DATE in codes_of(envelope)


def test_emit_non_terminal_case_when_no_terminal_event():
    envelope = make_envelope(UNDISPOSED)
    assert wc.NON_TERMINAL_CASE in codes_of(envelope)


def test_emit_unsupported_format_on_exception():
    envelope = make_envelope(KEYERROR_SPECIMEN)
    assert envelope["error"]["code"] == wc.UNSUPPORTED_FORMAT


# --- NON_TERMINAL_CASE definition guards --------------------------------------


def test_non_terminal_not_flagged_when_final_disposition_present():
    assert wc.NON_TERMINAL_CASE not in codes_of(make_envelope(DISPOSED_CLEAN))


def test_non_terminal_not_flagged_with_interim_nonfinal_plus_final():
    assert wc.NON_TERMINAL_CASE not in codes_of(make_envelope(NON_FINAL_THEN_FINAL))


def test_clean_disposed_case_has_no_warnings_and_no_review():
    envelope = make_envelope(DISPOSED_CLEAN)
    assert envelope["warnings"] == []
    assert envelope["review_needed"] is False


# --- exception mapping: ParseError also maps to UNSUPPORTED_FORMAT -------------


def test_parse_error_maps_to_unsupported_format_not_missing_charge_section():
    envelope = make_envelope(PARSEERROR_SPECIMEN)
    assert envelope["status"] == env.PARSE_STATUS_FAILED
    assert envelope["error"]["code"] == wc.UNSUPPORTED_FORMAT
    assert envelope["error"]["exception_class"] == "ParseError"


# --- 18.2: parser warnings surface into the envelope and flag review ----------


def test_envelope_emits_suspect_judge_line_and_flags_review():
    envelope = make_envelope(JUDGE_FRAGMENT)
    assert wc.SUSPECT_JUDGE_LINE in codes_of(envelope)
    assert envelope["review_needed"] is True
    charge = envelope["record"]["charges"][0]
    # Only the judge field is nulled; the disposition_date is still captured.
    assert charge["disposition_judge_raw"] is None
    assert charge["disposition_date"] == "2025-01-15"


def test_envelope_emits_suspected_amended_charge_and_flags_review():
    envelope = make_envelope(AMENDED_CHARGE)
    assert wc.SUSPECTED_AMENDED_CHARGE in codes_of(envelope)
    assert envelope["review_needed"] is True
    # Warning-only: the parsed disposition_raw is unchanged.
    assert envelope["record"]["charges"][0]["disposition_raw"] == "Amended"


# --- 18.3: held-case event_date and the third-party name guard ----------------


def test_envelope_held_case_carries_event_date_and_flags_non_terminal():
    envelope = make_envelope(HELD_FOR_COURT)
    assert wc.NON_TERMINAL_CASE in codes_of(envelope)
    charge = envelope["record"]["charges"][0]
    assert charge["event_date"] == "2024-06-15"
    assert charge["event_name"] == "Held for Court"
    assert charge["disposition_date"] is None


def test_envelope_emits_sentinel_collision_and_flags_review():
    envelope = make_envelope(JUDGE_COLLISION)
    assert wc.SENTINEL_COLLISION in codes_of(envelope)
    assert envelope["review_needed"] is True
    charge = envelope["record"]["charges"][0]
    # The colliding value is nulled; the disposition_date is still captured.
    assert charge["disposition_judge_raw"] is None
    assert charge["disposition_date"] == "2025-01-15"
    # No colliding text anywhere in the envelope's warnings.
    assert "Example" not in json.dumps(envelope["warnings"])


# --- criterion 1: closed vocabulary; MISSING_CHARGE_SECTION defined-but-unemitted


def test_emitted_codes_are_a_subset_of_the_defined_vocabulary():
    assert env.EMITTED_CODES <= wc.WARNING_CODES


def test_unemitted_set_is_exactly_missing_charge_section():
    # 18.2 wired SUSPECT_JUDGE_LINE and SUSPECTED_AMENDED_CHARGE, leaving only
    # MISSING_CHARGE_SECTION defined-but-unemitted (its detector is future work).
    assert env.UNEMITTED_CODES == {wc.MISSING_CHARGE_SECTION}
    assert env.EMITTED_CODES == wc.WARNING_CODES - env.UNEMITTED_CODES


def test_no_fixture_emits_an_unemitted_code():
    envelopes = [
        make_envelope(UNDISPOSED),
        make_envelope(DISPOSED_CLEAN, extraction_status=STATUS_PARTIAL),
        make_envelope(LIFE_DURATION),
        make_envelope(MISSING_DATES),
        make_envelope(KEYERROR_SPECIMEN),
        make_envelope(PARSEERROR_SPECIMEN),
    ]
    seen = env.collect_codes(envelopes)
    assert seen <= env.EMITTED_CODES
    assert seen.isdisjoint(env.UNEMITTED_CODES)


# --- criterion 6: a raising docket does not abort a multi-file run -------------


def test_run_parse_continues_past_a_failing_docket(tmp_path, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    artifacts_dir = tmp_path / "extracted"
    artifacts_dir.mkdir()
    output_dir = tmp_path / "envelopes"

    def write_artifact(name: str, source_hash: str, page: str) -> None:
        (artifacts_dir / f"{source_hash}.json").write_text(
            json.dumps(
                {
                    "source_sha256": source_hash,
                    "text_hash": TEXT_HASH,
                    "original_filename": f"{name}.pdf",
                    "status": STATUS_SUCCESS,
                    "pages": [page],
                }
            )
        )

    good_hash = "c" * 64
    bad_hash = "d" * 64
    write_artifact("MC-51-CR-0000000-2025", good_hash, DISPOSED_CLEAN)
    write_artifact("MC-51-CR-0000001-2025", bad_hash, KEYERROR_SPECIMEN)

    rc = env.run_parse(artifacts_dir, output_dir, salt=TEST_SALT)
    assert rc == 0

    good = json.loads((output_dir / f"{good_hash}.json").read_text())
    bad = json.loads((output_dir / f"{bad_hash}.json").read_text())
    assert good["status"] == env.PARSE_STATUS_PARSED
    assert bad["status"] == env.PARSE_STATUS_FAILED
    assert bad["record"] is None
    assert bad["error"]["code"] == wc.UNSUPPORTED_FORMAT


def test_run_parse_refuses_output_inside_git_worktree(tmp_path):
    artifacts_dir = tmp_path / "extracted"
    artifacts_dir.mkdir()
    (artifacts_dir / "x.json").write_text(
        json.dumps(
            {
                "source_sha256": "e" * 64,
                "text_hash": TEXT_HASH,
                "original_filename": "MC-51-CR-0000000-2025.pdf",
                "status": STATUS_SUCCESS,
                "pages": [DISPOSED_CLEAN],
            }
        )
    )
    output_dir = tmp_path / "inside" / "envelopes"
    output_dir.parent.mkdir()
    (output_dir.parent / ".git").mkdir()
    assert env.run_parse(artifacts_dir, output_dir, salt=TEST_SALT) == 2
    assert not output_dir.exists()
