"""Tier-1 synthetic close-stale-review-items tests (closure package R2).

Every row seeded here is FABRICATED — synthetic UUID-keyed rows over the same
fabricated docket-number/hash conventions as ``test_load.py``; disposition and
offense strings are standardized CPCMS/statute vocabulary (committable). The
suite exercises ``pipeline.close_stale_review_items`` against a REAL Postgres
with the repo migrations applied, reusing the 21.3 fail-closed guards:
``PIPELINE_TEST_DATABASE_URL`` only (never ``DATABASE_URL``), and the connected
database name must contain "test" before any truncation.

What R2 requires proven: the predicate is the canonical build path by import
(an open item closes iff the current matcher/mapper walk would NOT re-emit its
dedup key), type-scoped (the pinned pair only; ``missing_disposition_date``
untouched), status-scoped (``open`` only; ``in_review`` never bulk-closed),
closes as ``superseded``, is idempotent, holds the dry-run / ``--confirm``
split, and — the load-bearing negative — a LIVE-condition item (key still in
the regeneration set) is never touched. The CLI seam (CI refusal) is covered
at the ``cli.main`` level without a DB.
"""

from __future__ import annotations

import os

import psycopg
import pytest

from pipeline import cli
from pipeline.close_stale_review_items import (
    CLOSABLE_ITEM_TYPES,
    close_stale_review_items,
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
from pipeline.normalization.charge_matcher import (
    ChargeMatcher,
    RosterEntry,
    RosterSnapshot,
)
from pipeline.normalization.outcome_mapper import OutcomeMapper, TaxonomySnapshot
from pipeline.normalization.review_items import build_dedup_key
from pipeline.seam_check import running_in_ci

TEST_DB_URL_ENV_VAR = "PIPELINE_TEST_DATABASE_URL"

_FAKE_HASH = "e" + "b" * 63


def _matcher() -> ChargeMatcher:
    """One-entry synthetic roster: 'Theft' matches exact, everything else doesn't."""
    return ChargeMatcher(
        RosterSnapshot(
            entries=(
                RosterEntry(
                    normalized_id="norm-theft",
                    slug="theft",
                    display_name="Theft",
                    statute_code=None,
                ),
            )
        )
    )


def _mapper() -> OutcomeMapper:
    """The real DISPOSITION_OUTCOME_MAP over a synthetic taxonomy snapshot."""
    return OutcomeMapper(
        TaxonomySnapshot(
            taxonomy_version="0.0.0-test",
            public_by_code={
                "guilty_plea": True,
                "guilty_verdict": True,
                "dismissed": True,
                "acquittal": True,
                "ard": True,
                "withdrawn": True,
                "other": False,
                "unknown": False,
            },
        )
    )


def _run(conn: psycopg.Connection, *, confirm: bool) -> int:
    return close_stale_review_items(
        conn, charge_matcher=_matcher(), mapper=_mapper(), confirm=confirm
    )


@pytest.fixture
def stale_conn():
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
               VALUES (%(doc)s, 'MC-51-CR-0000002-2020', 2, 5, now(),
                       'Philadelphia', %(dh)s, 'parsed', false)
               RETURNING id""",
            {"doc": doc_id, "dh": "1" * 64},
        )
        docket_id = str(cur.fetchone()[0])
    return doc_id, docket_id


def _seed_charge(
    conn: psycopg.Connection,
    docket_id: str,
    sequence: int,
    disposition_raw: str | None,
    offense: str | None = None,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO parsed.charges (docket_id, sequence, disposition_raw,
                                           offense)
               VALUES (%(docket)s, %(seq)s, %(disp)s, %(offense)s) RETURNING id""",
            {
                "docket": docket_id,
                "seq": sequence,
                "disp": disposition_raw,
                "offense": offense,
            },
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
    assert set(CLOSABLE_ITEM_TYPES) == {UNMAPPED_CHARGE, UNMAPPED_DISPOSITION}


def test_stale_close_and_live_carve_out(stale_conn, capsys) -> None:
    conn = stale_conn
    doc_id, docket_id = _seed_docket(conn)

    # seq 1: condition FIXED both ways — disposition now mapped
    # ('Dismissed - LOP' is in the real table) and offense now roster-matched
    # ('Theft', exact). Neither key regenerates -> both items are stale.
    _seed_charge(conn, docket_id, 1, "Dismissed - LOP", offense="Theft")
    key_stale_disp = _seed_item(
        conn,
        source_document_id=doc_id,
        item_type=UNMAPPED_DISPOSITION,
        charge_sequence=1,
    )
    key_stale_charge = _seed_item(
        conn,
        source_document_id=doc_id,
        item_type=UNMAPPED_CHARGE,
        charge_sequence=1,
    )
    # seq 2: held form — the mapper's held arm skips the charge before any
    # review path runs, so a lingering item is stale (the 29.3 sweep, now by
    # the generic predicate).
    _seed_charge(conn, docket_id, 2, "Held for Court")
    key_stale_held = _seed_item(
        conn,
        source_document_id=doc_id,
        item_type=UNMAPPED_DISPOSITION,
        charge_sequence=2,
    )
    # seq 3: condition LIVE both ways — an unmapped terminal disposition and an
    # unmatched offense both still regenerate their keys -> NEVER closed (the
    # load-bearing negative: closure is per-key permanent).
    _seed_charge(
        conn, docket_id, 3, "Proceed to Court", offense="Some Unrostered Offense"
    )
    key_live_disp = _seed_item(
        conn,
        source_document_id=doc_id,
        item_type=UNMAPPED_DISPOSITION,
        charge_sequence=3,
    )
    key_live_charge = _seed_item(
        conn,
        source_document_id=doc_id,
        item_type=UNMAPPED_CHARGE,
        charge_sequence=3,
    )
    # seq 1 again, OUT-of-scope type on a stale-condition charge -> untouched.
    key_mdd = _seed_item(
        conn,
        source_document_id=doc_id,
        item_type=MISSING_DISPOSITION_DATE,
        charge_sequence=1,
    )
    # seq 4: stale condition but human-touched (in_review) -> untouched.
    _seed_charge(conn, docket_id, 4, "Withdrawn", offense="Theft")
    key_in_review = _seed_item(
        conn,
        source_document_id=doc_id,
        item_type=UNMAPPED_DISPOSITION,
        charge_sequence=4,
        status=STATUS_IN_REVIEW,
    )
    conn.commit()

    assert _run(conn, confirm=True) == 0
    out = capsys.readouterr().out
    assert "closed=3" in out

    statuses = _statuses(conn)
    assert statuses[key_stale_disp] == STATUS_SUPERSEDED
    assert statuses[key_stale_charge] == STATUS_SUPERSEDED
    assert statuses[key_stale_held] == STATUS_SUPERSEDED
    assert statuses[key_live_disp] == STATUS_OPEN
    assert statuses[key_live_charge] == STATUS_OPEN
    assert statuses[key_mdd] == STATUS_OPEN
    assert statuses[key_in_review] == STATUS_IN_REVIEW


def test_ambiguous_rematch_retires_the_unmapped_key(stale_conn, capsys) -> None:
    # A charge whose offense now matches AMBIGUOUSLY regenerates an
    # ambiguous_charge key (out of scope), NOT the old unmapped_charge key —
    # the unmapped item is stale and closes; the next build mints the
    # ambiguous item fresh under its own key.
    conn = stale_conn
    doc_id, docket_id = _seed_docket(conn)
    _seed_charge(conn, docket_id, 1, "Withdrawn", offense="Theft")
    key_unmapped = _seed_item(
        conn,
        source_document_id=doc_id,
        item_type=UNMAPPED_CHARGE,
        charge_sequence=1,
    )
    conn.commit()

    ambiguous_matcher = ChargeMatcher(
        RosterSnapshot(
            entries=(
                RosterEntry(
                    normalized_id="norm-theft-a",
                    slug="theft-a",
                    display_name="Theft",
                    statute_code=None,
                ),
                RosterEntry(
                    normalized_id="norm-theft-b",
                    slug="theft-b",
                    display_name="Theft",
                    statute_code=None,
                ),
            )
        )
    )
    assert (
        close_stale_review_items(
            conn, charge_matcher=ambiguous_matcher, mapper=_mapper(), confirm=True
        )
        == 0
    )
    assert "closed=1" in capsys.readouterr().out
    assert _statuses(conn)[key_unmapped] == STATUS_SUPERSEDED


def test_dry_run_writes_nothing_and_reports(stale_conn, capsys) -> None:
    conn = stale_conn
    doc_id, docket_id = _seed_docket(conn)
    _seed_charge(conn, docket_id, 1, "Nolle Prossed", offense="Theft")
    key = _seed_item(
        conn,
        source_document_id=doc_id,
        item_type=UNMAPPED_DISPOSITION,
        charge_sequence=1,
    )
    conn.commit()

    assert _run(conn, confirm=False) == 0
    out = capsys.readouterr().out
    assert "would_close=1" in out
    assert _statuses(conn)[key] == STATUS_OPEN


def test_confirm_then_rerun_is_idempotent_zero(stale_conn, capsys) -> None:
    conn = stale_conn
    doc_id, docket_id = _seed_docket(conn)
    _seed_charge(conn, docket_id, 1, "Guilty Plea", offense="Theft")
    key = _seed_item(
        conn,
        source_document_id=doc_id,
        item_type=UNMAPPED_CHARGE,
        charge_sequence=1,
    )
    conn.commit()

    assert _run(conn, confirm=True) == 0
    assert "closed=1" in capsys.readouterr().out
    assert _statuses(conn)[key] == STATUS_SUPERSEDED

    # Re-run (confirm and dry): the item is no longer open -> selects zero.
    assert _run(conn, confirm=True) == 0
    assert "closed=0" in capsys.readouterr().out
    assert _run(conn, confirm=False) == 0
    assert "would_close=0" in capsys.readouterr().out
    assert _statuses(conn)[key] == STATUS_SUPERSEDED


def test_cli_refuses_in_ci(monkeypatch):
    monkeypatch.setenv("CI", "true")
    assert cli.main(["close-stale-review-items", "--confirm"]) == 2
