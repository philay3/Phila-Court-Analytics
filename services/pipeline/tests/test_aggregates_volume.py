"""Phase 36 charge-volume generation — pure builder tests + DB end-to-end.

Pure suite: synthetic corpus dicts through :func:`build_charge_volume_rows` —
the filed universe (floor + NULL fail-closed), the four bucket arms, the
superseded fold (a traced held row is counted once, on its CP side), the
non-held-superseded anomaly (fail-open to visible counting), roster
invisibility of unmatched rows, and the closure identity.

DB suite (``PIPELINE_TEST_DATABASE_URL``): a coherent mini-corpus (MC held
charge pointed at its CP twin, CP twin publicly disposed, matching fact rows)
through ``generate_aggregates`` + ``validate_aggregates`` — proving the volume
rows persist under the run, the funnel-vs-percentages identity holds, the
fact-side sum holds, and the whole run validates clean end to end.

Synthetic only: placeholder slugs, statutes, and docket numbers.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime

import psycopg
import pytest
from psycopg.rows import dict_row
from test_aggregates_generate import TEST_DB_URL_ENV_VAR, _classify

from pipeline.aggregates.generate import generate_aggregates
from pipeline.aggregates.validate import validate_aggregates
from pipeline.aggregates.volume import build_charge_volume_rows
from pipeline.forbidden_scan import ForbiddenTerms
from pipeline.normalization.charge_matcher import (
    ChargeMatcher,
    RosterEntry,
    RosterSnapshot,
)
from pipeline.normalization.outcome_mapper import OutcomeMapper, load_taxonomy_snapshot
from pipeline.seam_check import running_in_ci

CHARGE_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
STATUTE = "18 § 9901 §§ A"
OFFENSE = "Placeholder Volume Offense"
HELD_FORM = "Held for Court"
TERMINAL_FORM = "Guilty Plea"
FLOOR = date(2025, 1, 1)

ROSTER = RosterSnapshot(
    entries=(
        RosterEntry(
            normalized_id=CHARGE_ID,
            slug="placeholder-volume-charge",
            display_name=OFFENSE,
            statute_code=STATUTE,
            aliases=(),
        ),
    )
)


@pytest.fixture(scope="module")
def matcher() -> ChargeMatcher:
    return ChargeMatcher(ROSTER)


@pytest.fixture(scope="module")
def mapper() -> OutcomeMapper:
    return OutcomeMapper(load_taxonomy_snapshot())


def _row(
    *,
    filed: date | None = date(2025, 2, 1),
    statute: str | None = STATUTE,
    offense: str | None = OFFENSE,
    disposition: str | None = None,
    disposition_date: date | None = None,
    superseded: bool = False,
    docket_id: str = "docket-1",
    sequence: int = 1,
) -> dict[str, object]:
    return {
        "id": f"{docket_id}-{sequence}",
        "docket_id": docket_id,
        "sequence": sequence,
        "statute": statute,
        "offense": offense,
        "disposition_raw": disposition,
        "disposition_date": disposition_date,
        "superseded": superseded,
        "filed_date": filed,
    }


def _build(rows, matcher, mapper):
    return build_charge_volume_rows(
        rows, {}, matcher=matcher, mapper=mapper, taxonomy_version="test-tax"
    )


def test_universe_excludes_pre_floor_and_null_filed(matcher, mapper):
    rows = [
        _row(filed=date(2024, 12, 31), disposition=None, sequence=1),
        _row(filed=None, disposition=None, sequence=2),
        _row(filed=FLOOR, disposition=None, sequence=3),
    ]
    volume_rows, report = _build(rows, matcher, mapper)

    assert report["rows_pre_floor"] == 2
    assert report["rows_in_universe"] == 1
    assert len(volume_rows) == 1
    assert volume_rows[0]["charges_seen"] == 1
    assert volume_rows[0]["still_pending"] == 1


def test_bucket_arms_and_closure(matcher, mapper):
    rows = [
        # (a) public-eligible outcome: in-window terminal disposition.
        _row(disposition=TERMINAL_FORM, disposition_date=date(2025, 3, 1), sequence=1),
        # (b) held, untraced.
        _row(disposition=HELD_FORM, sequence=2),
        # (c) pending.
        _row(disposition=None, sequence=3),
        # (d) disposed but excluded: pre-window disposition date.
        _row(disposition=TERMINAL_FORM, disposition_date=date(2024, 6, 1), sequence=4),
    ]
    volume_rows, report = _build(rows, matcher, mapper)

    assert len(volume_rows) == 1
    row = volume_rows[0]
    assert row["charge_id"] == CHARGE_ID
    assert row["charges_seen"] == 4
    assert row["outcomes_recorded"] == 1
    assert row["held_for_court"] == 1
    assert row["still_pending"] == 1
    assert row["disposed_excluded"] == 1
    assert row["held_superseded"] == 0
    assert report["outcomes_total"] == 1
    assert report["held_total"] == 1


def test_superseded_held_row_folds_into_its_cp_journey(matcher, mapper):
    rows = [
        # The MC held row, traced to a CP twin: folded, counted once (below).
        _row(disposition=HELD_FORM, superseded=True, docket_id="mc-1", sequence=1),
        # The CP continuation, publicly disposed.
        _row(
            disposition=TERMINAL_FORM,
            disposition_date=date(2025, 4, 1),
            docket_id="cp-1",
            sequence=1,
        ),
    ]
    volume_rows, report = _build(rows, matcher, mapper)

    assert report["superseded_folded"] == 1
    assert len(volume_rows) == 1
    row = volume_rows[0]
    assert row["charges_seen"] == 1  # ONE journey, never two
    assert row["outcomes_recorded"] == 1
    assert row["held_for_court"] == 0
    assert row["held_superseded"] == 1


def test_superseded_non_held_row_counts_and_flags_anomaly(matcher, mapper):
    rows = [
        _row(
            disposition=TERMINAL_FORM,
            disposition_date=date(2025, 3, 1),
            superseded=True,
        ),
    ]
    volume_rows, report = _build(rows, matcher, mapper)

    assert report["superseded_not_held_anomaly"] == 1
    assert report["superseded_folded"] == 0
    assert len(volume_rows) == 1
    assert volume_rows[0]["charges_seen"] == 1
    assert volume_rows[0]["outcomes_recorded"] == 1


def test_unmatched_rows_are_invisible_to_pages_but_tallied(matcher, mapper):
    rows = [
        _row(statute="99 § 0000", offense="No Such Offense", disposition=None),
    ]
    volume_rows, report = _build(rows, matcher, mapper)

    assert volume_rows == []
    assert report["unmatched_rows"] == 1
    assert report["pending_total"] == 1
    assert report["identities_with_journeys"] == 0


def test_fully_superseded_identity_produces_no_row(matcher, mapper):
    rows = [
        _row(disposition=HELD_FORM, superseded=True),
    ]
    volume_rows, report = _build(rows, matcher, mapper)

    assert volume_rows == []
    assert report["superseded_folded"] == 1
    assert report["identities_fully_superseded"] == 1


# --- DB end-to-end -----------------------------------------------------------


@pytest.fixture
def conn():
    action, payload = _classify(
        os.environ.get(TEST_DB_URL_ENV_VAR), in_ci=running_in_ci()
    )
    if action == "fail":
        pytest.fail(payload)
    if action == "skip":
        pytest.skip(payload)

    connection = psycopg.connect(payload)
    if "test" not in connection.info.dbname.lower():
        connection.close()
        pytest.fail(
            "refusing to run the volume suite against a database whose name "
            f"does not contain 'test'; point {TEST_DB_URL_ENV_VAR} at a test "
            "database."
        )
    try:
        with connection.cursor() as cur:
            cur.execute("TRUNCATE analytics.aggregate_runs CASCADE")
            cur.execute("TRUNCATE fact.fact_build_runs CASCADE")
            cur.execute("TRUNCATE raw.source_documents CASCADE")
            cur.execute("TRUNCATE ref.normalized_charges CASCADE")
            cur.execute("TRUNCATE ref.normalized_judges CASCADE")
        connection.commit()
        yield connection
    finally:
        connection.rollback()
        connection.close()


def test_db_end_to_end_volume_rows_generate_and_validate(conn):
    """Coherent mini-corpus: generate writes the volume row, validation passes.

    MC held charge pointed at its CP twin; CP twin publicly disposed with a
    matching public-eligible fact. Expected volume row: seen=1 (the journey),
    outcomes=1, held=0, superseded=1 — and the funnel-vs-percentages and
    fact-side identities hold, so the run validates to completed.
    """
    taxonomy_version = "test-tax-1"
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "INSERT INTO ref.normalized_charges (slug, display_name, statute_code) "
            "VALUES (%s, %s, %s) RETURNING id",
            ("placeholder-volume-charge", OFFENSE, STATUTE),
        )
        charge_ref_id = str(cur.fetchone()["id"])

        def docket(number: str, court: str) -> str:
            # One source document per docket (the schema's identity rule).
            cur.execute(
                """
                INSERT INTO raw.source_documents
                  (file_hash, original_filename, file_size_bytes, imported_at,
                   import_mode, status)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (
                    # Unique, deterministic synthetic hash: the docket number
                    # itself (court prefix included), padded — never Python's
                    # salted hash().
                    number.replace("-", "").lower().ljust(64, "0"),
                    f"synthetic-{number[-9:]}.pdf",
                    1,
                    datetime.now(UTC),
                    "manual",
                    "imported",
                ),
            )
            source_document_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO parsed.dockets
                  (source_document_id, docket_number, record_parser_version,
                   envelope_parser_version, parsed_at, county,
                   court_type_derived, filed_date, defendant_hash,
                   envelope_status, review_needed)
                VALUES (%s, %s, 3, 8, %s, 'Philadelphia', %s, %s, %s,
                        'parsed', false)
                RETURNING id
                """,
                (
                    source_document_id,
                    number,
                    datetime.now(UTC),
                    court,
                    date(2025, 2, 1),
                    "4" * 64,
                ),
            )
            return str(cur.fetchone()["id"])

        mc_docket = docket("MC-51-CR-0000003-2025", "MC")
        cp_docket = docket("CP-51-CR-0000003-2025", "CP")

        def charge(
            docket_id: str, disposition: str | None, disposition_date: date | None
        ) -> str:
            cur.execute(
                """
                INSERT INTO parsed.charges
                  (docket_id, sequence, statute, offense, disposition_raw,
                   disposition_date)
                VALUES (%s, 1, %s, %s, %s, %s) RETURNING id
                """,
                (docket_id, STATUTE, OFFENSE, disposition, disposition_date),
            )
            return str(cur.fetchone()["id"])

        mc_charge = charge(mc_docket, HELD_FORM, None)
        cp_charge = charge(cp_docket, TERMINAL_FORM, date(2025, 4, 1))
        cur.execute(
            "UPDATE parsed.charges SET superseded_by_charge_id = %s WHERE id = %s",
            (cp_charge, mc_charge),
        )

        cur.execute(
            """
            INSERT INTO fact.fact_build_runs
              (status, parser_version, envelope_parser_version, taxonomy_version,
               started_at, completed_at)
            VALUES ('completed', 3, 8, %s, %s, %s) RETURNING id
            """,
            (taxonomy_version, datetime.now(UTC), datetime.now(UTC)),
        )
        build_run_id = str(cur.fetchone()["id"])
        cur.execute(
            """
            INSERT INTO fact.charge_outcomes
              (build_run_id, parsed_charge_id, parsed_docket_id,
               normalized_charge_id, outcome_category_code, disposition_date,
               attribution_method, charge_match_method, outcome_match_method,
               mvp_eligible, public_eligible, judge_specific_eligible,
               review_needed, taxonomy_version)
            VALUES (%s, %s, %s, %s, 'cat_guilty_plea', %s,
                    'charge_row', 'statute', 'exact',
                    true, true, false, false, %s)
            """,
            (
                build_run_id,
                cp_charge,
                cp_docket,
                charge_ref_id,
                date(2025, 4, 1),
                taxonomy_version,
            ),
        )
    conn.commit()

    rc = generate_aggregates(
        conn,
        build_run_id=None,
        data_start_date=FLOOR,
        thin_min_sample=10,
        label="volume-e2e",
    )
    assert rc == 0

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id FROM analytics.aggregate_runs ORDER BY started_at DESC LIMIT 1"
        )
        run_id = str(cur.fetchone()["id"])
        cur.execute(
            "SELECT * FROM analytics.charge_volume_aggregates "
            "WHERE aggregate_run_id = %s",
            (run_id,),
        )
        volume_rows = cur.fetchall()

    assert len(volume_rows) == 1
    row = volume_rows[0]
    assert str(row["charge_id"]) == charge_ref_id
    assert row["charges_seen"] == 1
    assert row["outcomes_recorded"] == 1
    assert row["held_for_court"] == 0
    assert row["still_pending"] == 0
    assert row["disposed_excluded"] == 0
    assert row["held_superseded"] == 1

    rc = validate_aggregates(
        conn,
        run_id=run_id,
        data_start_date=FLOOR,
        terms=ForbiddenTerms(field_stems=(), value_patterns=()),
    )
    assert rc == 0
