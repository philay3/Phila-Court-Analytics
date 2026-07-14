"""Tier-1 synthetic close-held-review-items tests (Task 29.3, AC 10).

Every row seeded here is FABRICATED — synthetic UUID-keyed rows over the same
fabricated docket-number/hash conventions as ``test_load.py``; disposition
strings are standardized CPCMS vocabulary (committable). The suite exercises
``pipeline.close_held_review_items`` against a REAL Postgres with the repo
migrations applied, reusing the 21.3 fail-closed guards:
``PIPELINE_TEST_DATABASE_URL`` only (never ``DATABASE_URL``), and the connected
database name must contain "test" before any truncation.

What AC 10 requires proven: closure is KEY-scoped (canonical dedup-key
reconstruction from the mapper's ``HELD_FOR_COURT_DISPOSITIONS`` authority set,
never ILIKE), type-scoped (``unmapped_disposition`` + ``unmapped_charge`` only;
``missing_disposition_date`` untouched), status-scoped (``open`` only), closes
as ``superseded``, is idempotent (re-run selects zero), and the dry-run /
``--confirm`` split holds. The CLI seam (CI refusal) is covered at the
``cli.main`` level without a DB.
"""

from __future__ import annotations

import os

import psycopg
import pytest

from pipeline import cli
from pipeline.close_held_review_items import (
    CLOSABLE_ITEM_TYPES,
    run_close_held_review_items,
)
from pipeline.fact_review_vocab import (
    MISSING_DISPOSITION_DATE,
    SEVERITY_MEDIUM,
    STATUS_IN_REVIEW,
    STATUS_OPEN,
    STATUS_SUPERSEDED,
    UNMAPPED_CHARGE,
    UNMAPPED_DISPOSITION,
)
from pipeline.normalization.outcome_mapper import HELD_FOR_COURT_DISPOSITIONS
from pipeline.normalization.review_items import build_dedup_key
from pipeline.seam_check import running_in_ci

TEST_DB_URL_ENV_VAR = "PIPELINE_TEST_DATABASE_URL"

_FAKE_HASH = "d" + "a" * 63


@pytest.fixture
def close_conn():
    url = os.environ.get(TEST_DB_URL_ENV_VAR)
    if not (url and url.strip()):
        if running_in_ci():
            pytest.fail(
                f"{TEST_DB_URL_ENV_VAR} must be set for the closure suite in CI; "
                "an unset value is a wiring regression, not a reason to skip."
            )
        pytest.skip(
            f"{TEST_DB_URL_ENV_VAR} not set; skipping closure DB suite (local)."
        )

    conn = psycopg.connect(url)
    if "test" not in conn.info.dbname.lower():
        conn.close()
        pytest.fail(
            "refusing to run the closure suite against a database whose name does "
            "not contain 'test' — the suite TRUNCATEs tables and must never touch "
            f"a dev/prod database. Point {TEST_DB_URL_ENV_VAR} at a dedicated "
            "test database."
        )
    try:
        with conn.cursor() as cur:
            # raw CASCADE clears parsed/review via the FK chain.
            cur.execute("TRUNCATE raw.source_documents CASCADE")
        conn.commit()
        yield conn
    finally:
        conn.rollback()
        conn.close()


def _seed_docket(conn: psycopg.Connection) -> tuple[str, str]:
    """One synthetic raw doc + parsed docket; returns (doc_id, docket_id)."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO raw.source_documents
                 (file_hash, original_filename, file_size_bytes, imported_at,
                  import_mode, status)
               VALUES (%(hash)s, 'synthetic.pdf', 1, now(), 'manual', 'imported')
               RETURNING id""",
            {"hash": _FAKE_HASH},
        )
        doc_id = str(cur.fetchone()[0])
        cur.execute(
            """INSERT INTO parsed.dockets
                 (source_document_id, docket_number, record_parser_version,
                  envelope_parser_version, parsed_at, county, defendant_hash,
                  envelope_status, review_needed)
               VALUES (%(doc)s, 'MC-51-CR-0000001-2020', 2, 5, now(),
                       'Philadelphia', %(dh)s, 'parsed', false)
               RETURNING id""",
            {"doc": doc_id, "dh": "0" * 64},
        )
        docket_id = str(cur.fetchone()[0])
    return doc_id, docket_id


def _seed_charge(
    conn: psycopg.Connection, docket_id: str, sequence: int, disposition_raw: str | None
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO parsed.charges (docket_id, sequence, disposition_raw)
               VALUES (%(docket)s, %(seq)s, %(disp)s) RETURNING id""",
            {"docket": docket_id, "seq": sequence, "disp": disposition_raw},
        )
        return str(cur.fetchone()[0])


def _seed_item(
    conn: psycopg.Connection,
    *,
    source_document_id: str,
    item_type: str,
    charge_sequence: int,
    status: str = STATUS_OPEN,
) -> str:
    """One queue item with the canonical charge-grain dedup key; returns dedup_key."""
    dedup_key = build_dedup_key(source_document_id, item_type, (str(charge_sequence),))
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO review.queue_items
                 (item_type, severity, source_document_id, entity_type,
                  raw_value, reason_code, status, dedup_key)
               VALUES (%(item_type)s, %(severity)s, %(doc)s, 'disposition',
                       'synthetic', 'review_needed', %(status)s, %(key)s)""",
            {
                "item_type": item_type,
                "severity": SEVERITY_MEDIUM,
                "doc": source_document_id,
                "status": status,
                "key": dedup_key,
            },
        )
    return dedup_key


def _statuses(conn: psycopg.Connection) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute("SELECT dedup_key, status FROM review.queue_items")
        return {str(k): str(s) for k, s in cur.fetchall()}


def test_closable_types_are_the_pinned_pair() -> None:
    assert set(CLOSABLE_ITEM_TYPES) == {UNMAPPED_DISPOSITION, UNMAPPED_CHARGE}


def test_closure_is_key_type_and_status_scoped(close_conn, capsys) -> None:
    conn = close_conn
    doc_id, docket_id = _seed_docket(conn)
    # seq 1: held form -> its open scoped items close.
    _seed_charge(conn, docket_id, 1, "IGJ - Held for Court")
    key_disp = _seed_item(
        conn,
        source_document_id=doc_id,
        item_type=UNMAPPED_DISPOSITION,
        charge_sequence=1,
    )
    key_charge = _seed_item(
        conn,
        source_document_id=doc_id,
        item_type=UNMAPPED_CHARGE,
        charge_sequence=1,
    )
    # Same held charge, OUT-of-scope type -> untouched.
    key_mdd = _seed_item(
        conn,
        source_document_id=doc_id,
        item_type=MISSING_DISPOSITION_DATE,
        charge_sequence=1,
    )
    # seq 2: held form but item already human-touched (in_review) -> untouched.
    _seed_charge(conn, docket_id, 2, "Held for Court")
    key_in_review = _seed_item(
        conn,
        source_document_id=doc_id,
        item_type=UNMAPPED_DISPOSITION,
        charge_sequence=2,
        status=STATUS_IN_REVIEW,
    )
    # seq 3: NON-held unmapped disposition -> untouched (key-scoped, not
    # type-wide).
    _seed_charge(conn, docket_id, 3, "Dismissed - LOP")
    key_nonheld = _seed_item(
        conn,
        source_document_id=doc_id,
        item_type=UNMAPPED_DISPOSITION,
        charge_sequence=3,
    )
    # seq 4: undisposed (null) charge with a stray scoped-type item -> untouched
    # (a null disposition is not a held FORM; closure follows the mapper set).
    _seed_charge(conn, docket_id, 4, None)
    key_null = _seed_item(
        conn,
        source_document_id=doc_id,
        item_type=UNMAPPED_CHARGE,
        charge_sequence=4,
    )
    conn.commit()

    assert run_close_held_review_items(conn, confirm=True) == 0
    out = capsys.readouterr().out
    assert "closed=2" in out

    statuses = _statuses(conn)
    assert statuses[key_disp] == STATUS_SUPERSEDED
    assert statuses[key_charge] == STATUS_SUPERSEDED
    assert statuses[key_mdd] == STATUS_OPEN
    assert statuses[key_in_review] == STATUS_IN_REVIEW
    assert statuses[key_nonheld] == STATUS_OPEN
    assert statuses[key_null] == STATUS_OPEN


def test_dry_run_writes_nothing_and_reports(close_conn, capsys) -> None:
    conn = close_conn
    doc_id, docket_id = _seed_docket(conn)
    _seed_charge(conn, docket_id, 1, "Held for Court")
    key = _seed_item(
        conn,
        source_document_id=doc_id,
        item_type=UNMAPPED_DISPOSITION,
        charge_sequence=1,
    )
    conn.commit()

    assert run_close_held_review_items(conn, confirm=False) == 0
    out = capsys.readouterr().out
    assert "would_close=1" in out
    assert _statuses(conn)[key] == STATUS_OPEN


def test_confirm_then_rerun_is_idempotent_zero(close_conn, capsys) -> None:
    conn = close_conn
    doc_id, docket_id = _seed_docket(conn)
    _seed_charge(conn, docket_id, 1, "HP - Held for Court")
    key = _seed_item(
        conn,
        source_document_id=doc_id,
        item_type=UNMAPPED_CHARGE,
        charge_sequence=1,
    )
    conn.commit()

    assert run_close_held_review_items(conn, confirm=True) == 0
    assert "closed=1" in capsys.readouterr().out
    assert _statuses(conn)[key] == STATUS_SUPERSEDED

    # Re-run (confirm and dry): the item is no longer open -> selects zero.
    assert run_close_held_review_items(conn, confirm=True) == 0
    assert "closed=0" in capsys.readouterr().out
    assert run_close_held_review_items(conn, confirm=False) == 0
    assert "would_close=0" in capsys.readouterr().out
    assert _statuses(conn)[key] == STATUS_SUPERSEDED


def test_scope_follows_the_mapper_authority_set() -> None:
    # F2: the tool must consume the mapper's set, never re-list the forms. A
    # membership spot-check pins the import seam (the full six-form content
    # lock lives in test_outcome_mapper.py).
    assert "Held for Court" in HELD_FOR_COURT_DISPOSITIONS
    assert len(HELD_FOR_COURT_DISPOSITIONS) == 6


def test_cli_refuses_in_ci(monkeypatch):
    monkeypatch.setenv("CI", "true")
    assert cli.main(["close-held-review-items", "--confirm"]) == 2
