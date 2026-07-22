"""Refresh-target derivation tests (Task COL-4b) — synthetic rows only.

Exercises ``derive_refresh_targets`` against a REAL Postgres with the repo
migrations applied, mirroring the loader-suite guards exactly (test_load.py):
the suite reads ONLY ``PIPELINE_TEST_DATABASE_URL`` (never ``DATABASE_URL``),
skips locally when unset, HARD-FAILS in CI when unset, and refuses any
database whose name does not contain "test" before truncating. CI never
touches ~/court-data/ or the real DB (AC-9).

Every docket number, hash, and value inserted here is FABRICATED (UJS-shaped
numbers over impossible 9xxxxxx sequences; constant hex fillers).
"""

from __future__ import annotations

import os

import psycopg
import pytest

from pipeline.collector.refresh_targets import (
    RefreshTarget,
    count_by_court,
    derive_refresh_targets,
)
from pipeline.seam_check import running_in_ci

TEST_DB_URL_ENV_VAR = "PIPELINE_TEST_DATABASE_URL"

_FAKE_DEFENDANT_HASH = "0" * 64


def _classify_test_db_url(url: str | None, *, in_ci: bool) -> tuple[str, str]:
    """Pure guard-1 decision: ('run', url) | ('skip', reason) | ('fail', reason)."""
    if url and url.strip():
        return ("run", url)
    if in_ci:
        return (
            "fail",
            f"{TEST_DB_URL_ENV_VAR} must be set for the refresh-targets suite in "
            "CI; an unset value is a wiring regression, not a reason to skip.",
        )
    return (
        "skip",
        f"{TEST_DB_URL_ENV_VAR} not set; skipping refresh-targets DB suite (local).",
    )


@pytest.fixture
def refresh_conn():
    action, payload = _classify_test_db_url(
        os.environ.get(TEST_DB_URL_ENV_VAR), in_ci=running_in_ci()
    )
    if action == "fail":
        pytest.fail(payload)
    if action == "skip":
        pytest.skip(payload)

    conn = psycopg.connect(payload)
    dbname = conn.info.dbname
    if "test" not in dbname.lower():
        conn.close()
        pytest.fail(
            "refusing to run the refresh-targets suite against a database whose "
            "name does not contain 'test' — the suite TRUNCATEs tables and must "
            f"never touch a dev/prod database. Point {TEST_DB_URL_ENV_VAR} at a "
            "dedicated test database."
        )
    try:
        with conn.cursor() as cur:
            # CASCADE clears the whole raw -> parsed tree between tests.
            cur.execute("TRUNCATE raw.source_documents CASCADE")
        conn.commit()
        yield conn
    finally:
        conn.rollback()
        conn.close()


def seed_docket(
    conn: psycopg.Connection,
    docket_number: str,
    file_hash: str,
    dispositions: list[str | None],
    filed_date: str | None = None,
) -> None:
    """Insert one fabricated source doc + parsed docket + its charges.

    ``dispositions`` holds one ``disposition_raw`` per charge (None = held);
    an empty list seeds a zero-charge docket. ``filed_date`` is nullable in
    the schema and defaults to NULL here so existing tests exercise the
    NULLS LAST + docket-number-tiebreak tail of the ordering.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw.source_documents
              (file_hash, original_filename, file_size_bytes, imported_at,
               import_mode, status)
            VALUES (%(hash)s, 'fabricated.pdf', 1000, now(), 'manual', 'imported')
            RETURNING id
            """,
            {"hash": file_hash},
        )
        source_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO parsed.dockets
              (source_document_id, docket_number, record_parser_version,
               envelope_parser_version, parsed_at, county, defendant_hash,
               envelope_status, review_needed, filed_date)
            VALUES (%(source_id)s, %(docket)s, 2, 5, now(), 'Philadelphia',
                    %(defendant_hash)s, 'success', false, %(filed_date)s)
            RETURNING id
            """,
            {
                "source_id": source_id,
                "docket": docket_number,
                "defendant_hash": _FAKE_DEFENDANT_HASH,
                "filed_date": filed_date,
            },
        )
        docket_id = cur.fetchone()[0]
        for sequence, disposition_raw in enumerate(dispositions, start=1):
            cur.execute(
                """
                INSERT INTO parsed.charges (docket_id, sequence, disposition_raw)
                VALUES (%(docket_id)s, %(sequence)s, %(disposition)s)
                """,
                {
                    "docket_id": docket_id,
                    "sequence": sequence,
                    "disposition": disposition_raw,
                },
            )
    conn.commit()


def test_held_docket_selected_disposed_docket_not(refresh_conn):
    seed_docket(refresh_conn, "MC-51-CR-9000001-2025", "a" * 64, [None, None])
    seed_docket(refresh_conn, "MC-51-CR-9000002-2025", "b" * 64, ["Guilty Plea"])
    targets = derive_refresh_targets(refresh_conn, "both")
    assert targets == [
        RefreshTarget(docket_number="MC-51-CR-9000001-2025", source_hash="a" * 64)
    ]


def test_partially_disposed_docket_is_a_target(refresh_conn):
    # One disposed charge + one held charge: the NON_TERMINAL_CASE warning
    # would MISS this docket (it fires only when no charge is disposed); the
    # charge-level predicate must select it — the pinned-decision-1 rationale.
    seed_docket(refresh_conn, "CP-51-CR-9000003-2025", "c" * 64, ["Guilty Plea", None])
    targets = derive_refresh_targets(refresh_conn, "both")
    assert [t.docket_number for t in targets] == ["CP-51-CR-9000003-2025"]


def test_zero_charge_docket_is_not_a_target(refresh_conn):
    seed_docket(refresh_conn, "MC-51-CR-9000004-2025", "d" * 64, [])
    assert derive_refresh_targets(refresh_conn, "both") == []


def test_court_filter_and_ordering(refresh_conn):
    seed_docket(refresh_conn, "MC-51-CR-9000006-2025", "e" * 64, [None])
    seed_docket(refresh_conn, "CP-51-CR-9000005-2025", "f" * 64, [None])
    seed_docket(refresh_conn, "MC-51-CR-9000005-2025", "1" * 64, [None])
    seed_docket(refresh_conn, "CP-51-CR-9000009-2025", "2" * 64, ["Dismissed"])

    both = derive_refresh_targets(refresh_conn, "both")
    assert [t.docket_number for t in both] == [
        "CP-51-CR-9000005-2025",
        "MC-51-CR-9000005-2025",
        "MC-51-CR-9000006-2025",
    ]
    mc = derive_refresh_targets(refresh_conn, "MC")
    assert [t.docket_number for t in mc] == [
        "MC-51-CR-9000005-2025",
        "MC-51-CR-9000006-2025",
    ]
    cp = derive_refresh_targets(refresh_conn, "CP")
    assert [t.docket_number for t in cp] == ["CP-51-CR-9000005-2025"]
    assert count_by_court(both) == {"MC": 2, "CP": 1}


def test_ordering_oldest_first_nulls_last_docket_tiebreak(refresh_conn):
    # Docket-number order alone over-samples the young cohort (right-censoring:
    # undisposed-heavy = young-heavy), so the derivation must walk oldest
    # filings first; NULL filed_dates sort last, docket number breaks ties.
    seed_docket(
        refresh_conn,
        "MC-51-CR-9000011-2026",
        "a1" * 32,
        [None],
        filed_date="2026-02-01",
    )
    seed_docket(
        refresh_conn,
        "CP-51-CR-9000012-2025",
        "b1" * 32,
        [None],
        filed_date="2025-03-09",
    )
    seed_docket(refresh_conn, "CP-51-CR-9000013-2025", "c1" * 32, [None])
    seed_docket(
        refresh_conn,
        "MC-51-CR-9000010-2025",
        "d1" * 32,
        [None],
        filed_date="2025-03-09",
    )
    targets = derive_refresh_targets(refresh_conn, "both")
    assert [t.docket_number for t in targets] == [
        "CP-51-CR-9000012-2025",  # 2025-03-09 (docket-number tiebreak: CP < MC)
        "MC-51-CR-9000010-2025",  # 2025-03-09
        "MC-51-CR-9000011-2026",  # 2026-02-01 — young docket sorts AFTER old ones
        "CP-51-CR-9000013-2025",  # NULL filed_date sorts last
    ]


def test_target_carries_current_source_hash(refresh_conn):
    seed_docket(refresh_conn, "MC-51-CR-9000007-2025", "3" * 64, [None])
    (target,) = derive_refresh_targets(refresh_conn, "MC")
    assert target.source_hash == "3" * 64


def test_unknown_court_raises(refresh_conn):
    with pytest.raises(ValueError, match="unsupported court"):
        derive_refresh_targets(refresh_conn, "XX")
