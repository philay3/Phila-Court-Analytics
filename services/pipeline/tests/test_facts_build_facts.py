"""DB integration tests for the outcome-fact build (Task 23.2).

Exercises ``build_facts`` end-to-end against a real Postgres TEST database
(``PIPELINE_TEST_DATABASE_URL``): seeds a synthetic ``ref.*`` roster + ``parsed.*``
graph (fictional names, zero-sequence placeholder docket number), runs the build,
and asserts the run lifecycle, the AC-8 per-scenario fact rows, the held-charge
skip, and the failure invariant (a failed build leaves no partial facts).

DB guards mirror the 21.3 loader suite: reads ONLY ``PIPELINE_TEST_DATABASE_URL``
(absent -> local skip / CI hard failure), and the connected database name must
contain "test" before any TRUNCATE. The roster loaders' CI guard is neutralized
here because the target is explicitly a dedicated TEST database.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime

import psycopg
import pytest
from psycopg.rows import dict_row

import pipeline.facts.build_facts as build_facts_mod
from pipeline.fact_review_vocab import (
    CHARGE_NOT_NORMALIZED,
    DISPOSITION_DATE_BEFORE_MVP_WINDOW,
    DISPOSITION_NOT_MAPPED,
    JUDGE_NOT_ATTRIBUTED,
    REVIEW_NEEDED,
    RUN_COMPLETED,
    RUN_FAILED,
)
from pipeline.facts.build_facts import build_facts
from pipeline.normalization import charge_roster_loader, judge_roster_loader
from pipeline.seam_check import running_in_ci
from pipeline.warning_codes import SUSPECTED_AMENDED_CHARGE

TEST_DB_URL_ENV_VAR = "PIPELINE_TEST_DATABASE_URL"


def _classify(url: str | None, *, in_ci: bool) -> tuple[str, str]:
    if url and url.strip():
        return ("run", url)
    if in_ci:
        return ("fail", f"{TEST_DB_URL_ENV_VAR} must be set for the fact suite in CI.")
    return ("skip", f"{TEST_DB_URL_ENV_VAR} not set; skipping fact DB suite (local).")


@pytest.fixture
def build_conn():
    action, payload = _classify(
        os.environ.get(TEST_DB_URL_ENV_VAR), in_ci=running_in_ci()
    )
    if action == "fail":
        pytest.fail(payload)
    if action == "skip":
        pytest.skip(payload)

    # Tuple-default connection, matching what ``pipeline.db.connect`` hands the
    # production build; assertions below use explicit dict cursors.
    conn = psycopg.connect(payload)
    if "test" not in conn.info.dbname.lower():
        conn.close()
        pytest.fail(
            "refusing to run the fact suite against a database whose name does "
            f"not contain 'test'; point {TEST_DB_URL_ENV_VAR} at a test database."
        )
    try:
        with conn.cursor() as cur:
            # Clear the whole fact + raw/parsed tree between tests.
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
    # The target is a dedicated TEST database; neutralize the roster loaders'
    # CI guard so the build can read the seeded roster.
    monkeypatch.setattr(charge_roster_loader, "running_in_ci", lambda: False)
    monkeypatch.setattr(judge_roster_loader, "running_in_ci", lambda: False)


JUDGE_NAME = "Alpha Testjudge"
ROSTER_STATUTE = "18 § 9999"
ROSTER_OFFENSE = "Fictional Theft Offense"


def _seed(conn: psycopg.Connection) -> None:
    """Seed a synthetic roster + one docket with the AC-8 charge mix."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "INSERT INTO ref.normalized_charges (slug, display_name, statute_code) "
            "VALUES (%s, %s, %s) RETURNING id",
            ("fictional-theft", ROSTER_OFFENSE, ROSTER_STATUTE),
        )
        cur.fetchone()
        cur.execute(
            "INSERT INTO ref.normalized_judges (slug, display_name) "
            "VALUES (%s, %s) RETURNING id",
            ("judge-testjudge-alpha", JUDGE_NAME),
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
                "Beta Nomatch",  # assigned judge unmatched -> no fallback anyway
                "parsed",
                False,
            ),
        )
        docket_id = cur.fetchone()["id"]

        # (sequence, statute, offense, disposition_raw, disposition_date,
        #  disposition_judge_raw)
        charges = [
            (
                1,
                ROSTER_STATUTE,
                ROSTER_OFFENSE,
                "Guilty Plea",
                date(2025, 6, 1),
                JUDGE_NAME,
            ),  # fully eligible
            (
                2,
                ROSTER_STATUTE,
                ROSTER_OFFENSE,
                "Zzz Unmapped Disposition",
                date(2025, 6, 1),
                JUDGE_NAME,
            ),  # disposition_not_mapped
            (
                3,
                "77 § 0000",
                "Unlisted Offense XYZ",
                "Guilty Plea",
                date(2025, 6, 1),
                JUDGE_NAME,
            ),  # charge_not_normalized
            (
                4,
                ROSTER_STATUTE,
                ROSTER_OFFENSE,
                "Guilty Plea",
                date(2025, 6, 1),
                None,
            ),  # judge_not_attributed
            (5, ROSTER_STATUTE, ROSTER_OFFENSE, None, None, None),  # held -> no fact
            (
                6,
                ROSTER_STATUTE,
                ROSTER_OFFENSE,
                "Guilty Plea",
                date(2024, 6, 1),
                JUDGE_NAME,
            ),  # pre-window
            (
                7,
                ROSTER_STATUTE,
                ROSTER_OFFENSE,
                "Guilty Plea",
                date(2025, 6, 1),
                JUDGE_NAME,
            ),  # review_needed via warning
        ]
        for seq, statute, offense, disp, ddate, judge in charges:
            cur.execute(
                """
                INSERT INTO parsed.charges
                  (docket_id, sequence, statute, offense, disposition_raw,
                   disposition_date, disposition_judge_raw)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (docket_id, seq, statute, offense, disp, ddate, judge),
            )
        # A charge-grain review-severity parser warning on seq 7.
        cur.execute(
            "INSERT INTO parsed.warnings (docket_id, code, charge_sequence) "
            "VALUES (%s, %s, %s)",
            (docket_id, SUSPECTED_AMENDED_CHARGE, 7),
        )
    conn.commit()


def _facts_by_sequence(conn: psycopg.Connection) -> dict[int, dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT c.sequence AS seq, f.*
            FROM fact.charge_outcomes f
            JOIN parsed.charges c ON c.id = f.parsed_charge_id
            """
        )
        return {row["seq"]: row for row in cur.fetchall()}


def test_build_lifecycle_and_scenarios(build_conn):
    conn, url = build_conn
    _seed(conn)

    assert build_facts(conn, url) == 0

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM fact.fact_build_runs")
        runs = cur.fetchall()
    assert len(runs) == 1
    run = runs[0]
    assert run["status"] == RUN_COMPLETED
    assert run["completed_at"] is not None
    assert run["parser_version"] == 2 and run["envelope_parser_version"] == 5
    assert run["taxonomy_version"]
    counts = run["counts"]
    assert counts["charges_processed"] == 7
    assert counts["facts_written"] == 6  # seq 5 is held
    assert counts["held_skipped"] == 1
    assert (
        counts["facts_written"] + counts["held_skipped"] == counts["charges_processed"]
    )

    facts = _facts_by_sequence(conn)
    # seq 5 (held) produced no fact.
    assert set(facts) == {1, 2, 3, 4, 6, 7}

    # seq 1 — fully eligible.
    f1 = facts[1]
    assert (
        f1["mvp_eligible"] and f1["public_eligible"] and f1["judge_specific_eligible"]
    )
    assert f1["ineligibility_reason_codes"] == []
    assert f1["normalized_charge_id"] is not None
    assert f1["normalized_judge_id"] is not None
    assert f1["attribution_method"] == "charge_row"

    # seq 2 — unmapped disposition.
    f2 = facts[2]
    assert not f2["public_eligible"]
    assert DISPOSITION_NOT_MAPPED in f2["ineligibility_reason_codes"]
    assert f2["outcome_category_code"] == "unknown"

    # seq 3 — charge not normalized.
    f3 = facts[3]
    assert not f3["public_eligible"]
    assert f3["normalized_charge_id"] is None
    assert CHARGE_NOT_NORMALIZED in f3["ineligibility_reason_codes"]

    # seq 4 — public-eligible but judge unattributed.
    f4 = facts[4]
    assert f4["public_eligible"] and not f4["judge_specific_eligible"]
    assert f4["normalized_judge_id"] is None
    assert f4["judge_attribution_method"] == "none"
    assert f4["ineligibility_reason_codes"] == [JUDGE_NOT_ATTRIBUTED]

    # seq 6 — pre-window date, fact still written with its real date.
    f6 = facts[6]
    assert not f6["mvp_eligible"]
    assert f6["disposition_date"] == date(2024, 6, 1)
    assert DISPOSITION_DATE_BEFORE_MVP_WINDOW in f6["ineligibility_reason_codes"]

    # seq 7 — review-severity parser warning gates public via review_needed.
    f7 = facts[7]
    assert f7["mvp_eligible"] and f7["review_needed"] and not f7["public_eligible"]
    assert REVIEW_NEEDED in f7["ineligibility_reason_codes"]


def test_failed_build_leaves_no_partial_facts(build_conn, monkeypatch):
    conn, url = build_conn
    _seed(conn)

    # Force the insert to blow up mid-build.
    def _boom(*_args, **_kwargs):
        raise RuntimeError("synthetic insert failure")

    monkeypatch.setattr(build_facts_mod, "insert_outcome_facts", _boom)

    assert build_facts(conn, url) == 1

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) AS n FROM fact.charge_outcomes")
        assert cur.fetchone()["n"] == 0
        cur.execute("SELECT status FROM fact.fact_build_runs")
        rows = cur.fetchall()
    # The run row survives (append-only history) and is marked failed.
    assert len(rows) == 1 and rows[0]["status"] == RUN_FAILED
