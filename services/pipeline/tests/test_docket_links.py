"""Tier-1 tests for CP<->MC held-case linkage (Task 23.5).

A pure-unit test for the §6.9 bounded parser plus a DB-integration suite (the same
``PIPELINE_TEST_DATABASE_URL`` harness as the 23.2/23.4 fact suites) that exercises
``collect_docket_links`` + ``insert_docket_links`` against a real ``parsed.dockets``
graph, covering AC2/AC3/AC5:

- in-corpus target resolves (target FK set), no review item;
- out-of-corpus target -> unresolved link (target FK null), NO review item;
- malformed reference (non-null capture, no bounded match) -> review item, no link;
- ambiguous target (two synthetic CP rows SHARING a docket_number, as the resolution
  TARGETS, with an MC source referencing that number) -> review item, no link;
- delete-and-reinsert re-run is idempotent on link content (same tuples, count stable).

Hygiene: synthetic docket numbers only (fictional 51-CR sequences); no real data.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Json

from pipeline.facts.docket_links import (
    collect_docket_links,
    insert_docket_links,
    parse_cross_court_targets,
)
from pipeline.seam_check import running_in_ci

TEST_DB_URL_ENV_VAR = "PIPELINE_TEST_DATABASE_URL"


def _classify(url: str | None, *, in_ci: bool) -> tuple[str, str]:
    if url and url.strip():
        return ("run", url)
    if in_ci:
        return (
            "fail",
            f"{TEST_DB_URL_ENV_VAR} must be set for the linkage suite in CI.",
        )
    return (
        "skip",
        f"{TEST_DB_URL_ENV_VAR} not set; skipping linkage DB suite (local).",
    )


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
            "refusing to run the linkage suite against a database whose name does "
            f"not contain 'test'; point {TEST_DB_URL_ENV_VAR} at a test database."
        )
    try:
        with connection.cursor() as cur:
            # raw.source_documents CASCADE clears parsed.* (and parsed.docket_links via
            # its FK) plus fact.* / review.queue_items — a clean slate every test.
            cur.execute("TRUNCATE raw.source_documents CASCADE")
        connection.commit()
        yield connection
    finally:
        connection.rollback()
        connection.close()


def _insert_source_docket(
    connection: psycopg.Connection,
    *,
    idx: int,
    court_type: str,
    docket_number: str,
    cross_court: str | None,
) -> str:
    """Insert one raw.source_documents + parsed.dockets pair; return the docket id."""
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "INSERT INTO raw.source_documents "
            "(file_hash, original_filename, file_size_bytes, imported_at, "
            "import_mode, status) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (
                f"{idx:064x}",
                "synthetic.pdf",
                1,
                datetime.now(UTC),
                "manual",
                "imported",
            ),
        )
        source_document_id = cur.fetchone()["id"]
        cur.execute(
            "INSERT INTO parsed.dockets "
            "(source_document_id, docket_number, record_parser_version, "
            "envelope_parser_version, parsed_at, county, court_type_derived, "
            "cross_court_dockets, defendant_hash, envelope_status, review_needed) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                source_document_id,
                docket_number,
                2,
                5,
                datetime.now(UTC),
                "Philadelphia",
                court_type,
                None if cross_court is None else Json(cross_court),
                "0" * 64,
                "parsed",
                False,
            ),
        )
        return str(cur.fetchone()["id"])


def _links(connection: psycopg.Connection) -> list[dict[str, object]]:
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT source_docket_id::text, target_docket_number, "
            "target_docket_id::text, link_type, evidence_source "
            "FROM parsed.docket_links ORDER BY target_docket_number"
        )
        return list(cur.fetchall())


def _link_tupleset(connection: psycopg.Connection) -> set[tuple[object, ...]]:
    return {
        (
            r["source_docket_id"],
            r["target_docket_number"],
            r["target_docket_id"],
            r["link_type"],
            r["evidence_source"],
        )
        for r in _links(connection)
    }


# --- pure-unit: the §6.9 bounded parser (no DB) -----------------------------
def test_parse_cross_court_targets_is_bounded():
    # single Philadelphia CR docket number -> one target
    assert parse_cross_court_targets("CP-51-CR-0000001-2020") == [
        "CP-51-CR-0000001-2020"
    ]
    # non-null capture with no bounded docket number -> malformed (empty list)
    assert parse_cross_court_targets("see companion file") == []
    # other-county / non-CR references are rejected (the 104-CP-docket case)
    assert parse_cross_court_targets("CP-09-MD-0000001-2020") == []
    # multiple bounded numbers preserved in order; both CP and MC prefixes matched
    assert parse_cross_court_targets(
        "MC-51-CR-1234567-2019 then CP-51-CR-7654321-2021"
    ) == ["MC-51-CR-1234567-2019", "CP-51-CR-7654321-2021"]
    # de-duplicated
    assert parse_cross_court_targets(
        "CP-51-CR-0000001-2020 / CP-51-CR-0000001-2020"
    ) == ["CP-51-CR-0000001-2020"]


# --- DB integration ---------------------------------------------------------
def test_in_corpus_target_resolves(conn):
    """AC2/AC3: an MC held docket whose CP target is in-corpus -> resolved link."""
    target_id = _insert_source_docket(
        conn,
        idx=1,
        court_type="CP",
        docket_number="CP-51-CR-0000001-2020",
        cross_court=None,
    )
    source_id = _insert_source_docket(
        conn,
        idx=2,
        court_type="MC",
        docket_number="MC-51-CR-0000010-2020",
        cross_court="CP-51-CR-0000001-2020",
    )

    link_rows, review_items, counts = collect_docket_links(conn)
    insert_docket_links(conn, link_rows)
    conn.commit()

    assert counts == {
        "source_mc_dockets_with_ref": 1,
        "links_total": 1,
        "resolved": 1,
        "unresolved": 0,
        "review_malformed": 0,
        "review_ambiguous": 0,
    }
    assert review_items == []
    (link,) = _links(conn)
    assert link["source_docket_id"] == source_id
    assert link["target_docket_id"] == target_id
    assert link["target_docket_number"] == "CP-51-CR-0000001-2020"
    assert link["link_type"] == "held_for_court"
    assert link["evidence_source"] == "cross_court_dockets"


def test_out_of_corpus_target_is_unresolved_no_review(conn):
    """AC3: bounded match, 0 rows -> unresolved link (FK null), NO review item."""
    _insert_source_docket(
        conn,
        idx=1,
        court_type="MC",
        docket_number="MC-51-CR-0000010-2020",
        cross_court="CP-51-CR-0000099-2020",
    )

    link_rows, review_items, counts = collect_docket_links(conn)
    insert_docket_links(conn, link_rows)
    conn.commit()

    assert counts["links_total"] == 1
    assert counts["unresolved"] == 1
    assert counts["resolved"] == 0
    assert review_items == []
    (link,) = _links(conn)
    assert link["target_docket_id"] is None
    assert link["target_docket_number"] == "CP-51-CR-0000099-2020"


def test_malformed_reference_routes_to_review(conn):
    """AC2/AC5: non-null capture, no bounded docket number -> review item, no link."""
    _insert_source_docket(
        conn,
        idx=1,
        court_type="MC",
        docket_number="MC-51-CR-0000010-2020",
        cross_court="see companion file",
    )

    link_rows, review_items, counts = collect_docket_links(conn)
    insert_docket_links(conn, link_rows)
    conn.commit()

    assert counts["links_total"] == 0
    assert counts["review_malformed"] == 1
    assert _links(conn) == []
    (item,) = review_items
    assert item["item_type"] == "unresolvable_cross_court_reference"
    assert item["reason_code"] == "review_needed"
    assert item["candidate_context"] == {"subcase": "malformed"}


def test_ambiguous_target_routes_to_review(conn):
    """AC2/RF3 (Tweak B): the resolution TARGET is ambiguous — two synthetic CP rows
    SHARE a docket_number (docket_number is not unique) and an MC source references it
    -> the target lookup returns 2 rows -> review item, no link, no unresolved row."""
    shared = "CP-51-CR-0000003-2020"
    _insert_source_docket(
        conn, idx=1, court_type="CP", docket_number=shared, cross_court=None
    )
    _insert_source_docket(
        conn, idx=2, court_type="CP", docket_number=shared, cross_court=None
    )
    _insert_source_docket(
        conn,
        idx=3,
        court_type="MC",
        docket_number="MC-51-CR-0000010-2020",
        cross_court=shared,
    )

    link_rows, review_items, counts = collect_docket_links(conn)
    insert_docket_links(conn, link_rows)
    conn.commit()

    assert counts["links_total"] == 0
    assert counts["resolved"] == 0
    assert counts["unresolved"] == 0
    assert counts["review_ambiguous"] == 1
    assert _links(conn) == []
    (item,) = review_items
    assert item["item_type"] == "unresolvable_cross_court_reference"
    assert item["reason_code"] == "review_needed"
    assert item["candidate_context"] == {
        "subcase": "ambiguous_target",
        "match_count": 2,
    }


def test_rerun_is_idempotent_on_links(conn):
    """AC1 lifecycle: delete-and-reinsert on an unchanged corpus -> identical link set,
    count stable (net zero change)."""
    _insert_source_docket(
        conn,
        idx=1,
        court_type="CP",
        docket_number="CP-51-CR-0000001-2020",
        cross_court=None,
    )
    _insert_source_docket(
        conn,
        idx=2,
        court_type="MC",
        docket_number="MC-51-CR-0000010-2020",
        cross_court="CP-51-CR-0000001-2020",
    )
    _insert_source_docket(
        conn,
        idx=3,
        court_type="MC",
        docket_number="MC-51-CR-0000011-2020",
        cross_court="CP-51-CR-0000099-2020",
    )

    rows1, _, counts1 = collect_docket_links(conn)
    insert_docket_links(conn, rows1)
    conn.commit()
    first = _link_tupleset(conn)

    rows2, _, counts2 = collect_docket_links(conn)
    insert_docket_links(conn, rows2)
    conn.commit()
    second = _link_tupleset(conn)

    assert counts1 == counts2
    assert first == second
    assert len(second) == 2  # one resolved + one unresolved; no growth on re-run
