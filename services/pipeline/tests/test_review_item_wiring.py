"""DB integration tests for review-item generation + dedup wiring (Task 23.4).

Exercises ``build_facts`` end-to-end against a real Postgres TEST database
(``PIPELINE_TEST_DATABASE_URL``), the same harness as the 23.2 fact suite: seeds a
synthetic ``ref.*`` roster + ``parsed.*`` graph engineered to fire EVERY routed
review path exactly once (the charge-grain sentinel + docket-grain sentinel make
``sentinel_collision`` fire twice), runs the build, and asserts:

- AC2(a): each of the 13 item types is created from the synthetic fixture, with the
  exact per-type counts (dedup-collapsed);
- AC2(b): a second identical build adds ZERO duplicate rows (idempotent queue);
- AC2(c): an item whose ``status`` is mutated to a non-default value survives a
  re-run byte-identical (status-preserving), and its ``updated_at`` is untouched.

DB guards mirror the 21.3 / 23.2 suites: reads ONLY ``PIPELINE_TEST_DATABASE_URL``
(absent -> local skip / CI hard failure), and the connected database name must
contain "test" before any TRUNCATE. Hygiene: no raw docket text is asserted here;
the fixture uses fictional names and a zero-sequence placeholder docket number.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime

import psycopg
import pytest
from psycopg.rows import dict_row

from pipeline.facts.build_facts import build_facts
from pipeline.normalization import charge_roster_loader, judge_roster_loader
from pipeline.seam_check import running_in_ci
from pipeline.warning_codes import (
    MISSING_DISPOSITION_DATE,
    SENTINEL_COLLISION,
    UNPARSEABLE_DURATION,
)

TEST_DB_URL_ENV_VAR = "PIPELINE_TEST_DATABASE_URL"


def _classify(url: str | None, *, in_ci: bool) -> tuple[str, str]:
    if url and url.strip():
        return ("run", url)
    if in_ci:
        return (
            "fail",
            f"{TEST_DB_URL_ENV_VAR} must be set for the review suite in CI.",
        )
    return ("skip", f"{TEST_DB_URL_ENV_VAR} not set; skipping review DB suite (local).")


@pytest.fixture
def build_conn():
    action, payload = _classify(
        os.environ.get(TEST_DB_URL_ENV_VAR), in_ci=running_in_ci()
    )
    if action == "fail":
        pytest.fail(payload)
    if action == "skip":
        pytest.skip(payload)

    conn = psycopg.connect(payload)
    if "test" not in conn.info.dbname.lower():
        conn.close()
        pytest.fail(
            "refusing to run the review suite against a database whose name does "
            f"not contain 'test'; point {TEST_DB_URL_ENV_VAR} at a test database."
        )
    try:
        with conn.cursor() as cur:
            # raw.source_documents CASCADE clears parsed.*, fact.*, and (via the FK)
            # review.queue_items — a clean slate every test.
            cur.execute("TRUNCATE fact.fact_build_runs CASCADE")
            cur.execute("TRUNCATE raw.source_documents CASCADE")
            cur.execute("TRUNCATE ref.normalized_charges CASCADE")
            cur.execute("TRUNCATE ref.normalized_judges CASCADE")
        conn.commit()
        yield conn, payload
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture(autouse=True)
def _allow_roster_loaders(monkeypatch):
    # Dedicated TEST database: neutralize the roster loaders' CI guard.
    monkeypatch.setattr(charge_roster_loader, "running_in_ci", lambda: False)
    monkeypatch.setattr(judge_roster_loader, "running_in_ci", lambda: False)


# Roster: a clean singleton, and same-display pairs that make a raw value ambiguous
# across two identities (>= 2 candidates -> ambiguous, never a silent pick).
_CLEAN_STATUTE = "18 § 1000"
_CLEAN_OFFENSE = "Clean Offense"
_AMBIGUOUS_OFFENSE = "Ambiguous Offense"
_CLEAN_JUDGE = "Clean Judge"
# Two roster identities that differ ONLY by middle name -> distinct canonical keys
# (the judge loader forbids two identities sharing a key), yet a raw value lacking a
# middle tolerance-matches BOTH (absent-middle wildcard) -> ambiguous, never a pick.
_AMBIGUOUS_JUDGE_A = "Pat Alpha Ambiguous"
_AMBIGUOUS_JUDGE_B = "Pat Beta Ambiguous"
_AMBIGUOUS_JUDGE_RAW = "Pat Ambiguous"


def _seed(conn: psycopg.Connection) -> None:
    """Seed a roster + one docket engineered to fire every routed review path."""
    with conn.cursor(row_factory=dict_row) as cur:
        for slug, name, statute in (
            ("clean-charge", _CLEAN_OFFENSE, _CLEAN_STATUTE),
            ("ambig-charge-a", _AMBIGUOUS_OFFENSE, "18 § 3000"),
            ("ambig-charge-b", _AMBIGUOUS_OFFENSE, "18 § 4000"),
        ):
            cur.execute(
                "INSERT INTO ref.normalized_charges (slug, display_name, statute_code) "
                "VALUES (%s, %s, %s)",
                (slug, name, statute),
            )
        for slug, name in (
            ("judge-clean", _CLEAN_JUDGE),
            ("judge-ambig-a", _AMBIGUOUS_JUDGE_A),
            ("judge-ambig-b", _AMBIGUOUS_JUDGE_B),
        ):
            cur.execute(
                "INSERT INTO ref.normalized_judges (slug, display_name) "
                "VALUES (%s, %s)",
                (slug, name),
            )

        cur.execute(
            """
            INSERT INTO raw.source_documents
              (file_hash, original_filename, file_size_bytes, imported_at,
               import_mode, status)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            """,
            ("0" * 64, "synthetic.pdf", 1, datetime.now(UTC), "manual", "imported"),
        )
        source_document_id = cur.fetchone()["id"]

        cur.execute(
            """
            INSERT INTO parsed.dockets
              (source_document_id, docket_number, record_parser_version,
               envelope_parser_version, parsed_at, county, defendant_hash,
               assigned_judge_raw, envelope_status, review_needed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (
                source_document_id,
                "CP-51-CR-0000000-2025",
                2,
                5,
                datetime.now(UTC),
                "Philadelphia",
                "0" * 64,
                _CLEAN_JUDGE,  # matched -> no assigned-judge item, no fallback
                "parsed",
                False,
            ),
        )
        docket_id = cur.fetchone()["id"]

        d = date(2025, 6, 1)
        # (sequence, statute, offense, disposition_raw, disposition_date, disp_judge)
        charges = [
            (1, "99 § 9999", "Nomatch Offense", "Guilty Plea", d, _CLEAN_JUDGE),
            (2, "18 § 5000", _AMBIGUOUS_OFFENSE, "Guilty Plea", d, _CLEAN_JUDGE),
            (
                3,
                _CLEAN_STATUTE,
                _CLEAN_OFFENSE,
                "Zzz Nomatch Disposition",
                d,
                _CLEAN_JUDGE,
            ),
            (4, _CLEAN_STATUTE, _CLEAN_OFFENSE, "Guilty Plea", d, "Nobody Notinroster"),
            (5, _CLEAN_STATUTE, _CLEAN_OFFENSE, "Guilty Plea", d, _AMBIGUOUS_JUDGE_RAW),
            (6, _CLEAN_STATUTE, _CLEAN_OFFENSE, "Guilty Plea", None, _CLEAN_JUDGE),
            (7, _CLEAN_STATUTE, _CLEAN_OFFENSE, "Guilty Plea", d, None),
            (8, _CLEAN_STATUTE, _CLEAN_OFFENSE, "Guilty Plea", d, _CLEAN_JUDGE),
        ]
        charge_ids: dict[int, str] = {}
        for seq, statute, offense, disp, ddate, judge in charges:
            cur.execute(
                """
                INSERT INTO parsed.charges
                  (docket_id, sequence, statute, offense, disposition_raw,
                   disposition_date, disposition_judge_raw)
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (docket_id, seq, statute, offense, disp, ddate, judge),
            )
            charge_ids[seq] = cur.fetchone()["id"]

        # Sentence components (all on the clean seq 8; sentence_date == disposition
        # date per SD 15). Non-duration components carry parsed days so ONLY the
        # "Confinement, Life" component trips the 18.1 predicate.
        components = [
            (
                1,
                "Zzz Unknown Sentence",
                30,
                60,
                "Zzz Unknown Sentence, Min of 1.00 Months",
            ),
            (2, "Probation", 365, None, "Probation, 40 hours"),
            (3, "Fines and Costs", None, None, "Fines and Costs, $500.00 and $250.00"),
            (4, "Confinement", None, None, "Confinement, Life"),
            (5, "Probation", 365, None, "Probation, Community Service 40 hours"),
        ]
        for order, stype, min_days, max_days, raw_text in components:
            cur.execute(
                """
                INSERT INTO parsed.sentences
                  (charge_id, component_order, sentence_type, min_days, max_days,
                   min_assumed, sentence_date, raw_text)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (charge_ids[8], order, stype, min_days, max_days, False, d, raw_text),
            )

        # Envelope warnings routed to the queue at fact build:
        warnings = [
            (MISSING_DISPOSITION_DATE, 6),  # disposed charge, null date
            (SENTINEL_COLLISION, 7),  # charge-grain (DISPOSITION section)
            (
                SENTINEL_COLLISION,
                None,
            ),  # docket-grain (CASE INFORMATION), empty locator
            (UNPARSEABLE_DURATION, 8),  # matches the seq-8 "Life" component (recon)
        ]
        for code, seq in warnings:
            cur.execute(
                "INSERT INTO parsed.warnings (docket_id, code, charge_sequence) "
                "VALUES (%s, %s, %s)",
                (docket_id, code, seq),
            )
    conn.commit()


# The engineered per-type item counts (dedup-collapsed). sentinel_collision fires
# twice: the charge-grain seq-7 warning and the docket-grain (null-sequence) warning.
_EXPECTED_BY_TYPE = {
    "unmapped_charge": 1,
    "ambiguous_charge": 1,
    "unmapped_disposition": 1,
    "unmapped_judge": 1,
    "ambiguous_judge": 1,
    "ambiguous_judge_attribution": 1,
    "missing_disposition_date": 1,
    "sentinel_collision": 2,
    "unmapped_sentencing_component": 1,
    "ambiguous_sentencing_component": 1,
    "money_unparseable": 1,
    "duration_unparseable": 1,
    "additive_sentencing_category": 1,
}
_EXPECTED_TOTAL = sum(_EXPECTED_BY_TYPE.values())


def _queue_by_type(conn: psycopg.Connection) -> dict[str, int]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT item_type, count(*) AS n FROM review.queue_items GROUP BY item_type"
        )
        return {r["item_type"]: r["n"] for r in cur.fetchall()}


def _latest_run_review_counts(conn: psycopg.Connection) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT counts FROM fact.fact_build_runs "
            "WHERE status = 'completed' ORDER BY completed_at DESC LIMIT 1"
        )
        return cur.fetchone()["counts"]["review_items"]


def test_every_item_type_is_created(build_conn):
    """AC2(a): each of the 13 routed item types lands with its expected count."""
    conn, url = build_conn
    _seed(conn)

    assert build_facts(conn, url) == 0

    assert _queue_by_type(conn) == _EXPECTED_BY_TYPE
    # AC1: the queue covers the full AC1 vocabulary (every routed type present).
    assert set(_queue_by_type(conn)) == set(_EXPECTED_BY_TYPE)

    # AC3: per-type counts are reported on the run row; first run inserts them all.
    review_counts = _latest_run_review_counts(conn)
    assert review_counts["generated_by_type"] == _EXPECTED_BY_TYPE
    assert review_counts["generated_total"] == _EXPECTED_TOTAL
    assert review_counts["newly_inserted_total"] == _EXPECTED_TOTAL


def test_rerun_is_idempotent_on_the_queue(build_conn):
    """AC2(b): a second identical build adds zero duplicate rows."""
    conn, url = build_conn
    _seed(conn)

    assert build_facts(conn, url) == 0
    first = _queue_by_type(conn)
    assert sum(first.values()) == _EXPECTED_TOTAL

    # Second identical build: same dedup keys -> ON CONFLICT DO NOTHING.
    assert build_facts(conn, url) == 0
    assert _queue_by_type(conn) == first
    assert sum(_queue_by_type(conn).values()) == _EXPECTED_TOTAL

    review_counts = _latest_run_review_counts(conn)
    assert review_counts["generated_total"] == _EXPECTED_TOTAL  # still generated
    assert review_counts["newly_inserted_total"] == 0  # but none newly inserted


def test_rerun_preserves_mutated_status(build_conn):
    """AC2(c): an item's mutated status survives a re-run byte-identical."""
    conn, url = build_conn
    _seed(conn)

    assert build_facts(conn, url) == 0

    # Mutate one item's triage status to a non-default value (Sprint 6's job),
    # capturing its identity and updated_at.
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "UPDATE review.queue_items SET status = 'resolved' "
            "WHERE item_type = 'unmapped_charge' "
            "RETURNING id, dedup_key, updated_at"
        )
        mutated = cur.fetchone()
    conn.commit()
    assert mutated is not None

    # Re-run the whole build; the conflicting insert must touch nothing.
    assert build_facts(conn, url) == 0

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, status, updated_at FROM review.queue_items "
            "WHERE dedup_key = %s",
            (mutated["dedup_key"],),
        )
        after = cur.fetchone()

    assert after["id"] == mutated["id"]  # same row, not re-created
    assert after["status"] == "resolved"  # status untouched
    assert after["updated_at"] == mutated["updated_at"]  # no-op insert fired no trigger
    assert sum(_queue_by_type(conn).values()) == _EXPECTED_TOTAL  # no duplicates
