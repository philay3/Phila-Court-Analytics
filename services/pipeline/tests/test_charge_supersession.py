"""Charge supersession — the MC→CP double-count fix (Phase 36, 2026-07-25).

DB suite over a synthetic parsed graph (``PIPELINE_TEST_DATABASE_URL``; absent
-> local skip / CI hard failure via the shared ``_classify``). Exercises the
deterministic join exactly as ruled: case level (originating docket number +
OTN, both required), charge level (orig_seq + statute, both required), the
currently-held guard (the 22.4 mapper is the authority), latest-filed-wins on
multi-claim, whole-mapping replacement on apply, and the ON DELETE SET NULL
posture under a CP graph delete.

Synthetic only: placeholder docket numbers in the reserved 0000000 range,
placeholder statutes, no real court data anywhere.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime

import psycopg
import pytest
from psycopg.rows import dict_row
from test_aggregates_generate import TEST_DB_URL_ENV_VAR, _classify

from pipeline.facts.charge_supersession import (
    apply_supersessions,
    derive_supersessions,
)
from pipeline.normalization.outcome_mapper import OutcomeMapper, load_taxonomy_snapshot
from pipeline.seam_check import running_in_ci

# A real held form (the mapper maps it to None) and a real terminal form.
HELD_FORM = "Held for Court"
TERMINAL_FORM = "Guilty Plea"

MC_NUMBER = "MC-51-CR-0000001-2025"
MC_NUMBER_B = "MC-51-CR-0000002-2025"
CP_NUMBER = "CP-51-CR-0000001-2025"
CP_NUMBER_B = "CP-51-CR-0000002-2025"
OTN = "X 0000001-1"
OTHER_OTN = "X 0000002-2"
STATUTE = "18 § 9901 §§ A"
OTHER_STATUTE = "18 § 9902"


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
            "refusing to run the supersession suite against a database whose "
            f"name does not contain 'test'; point {TEST_DB_URL_ENV_VAR} at a "
            "test database."
        )
    try:
        with connection.cursor() as cur:
            cur.execute("TRUNCATE raw.source_documents CASCADE")
        connection.commit()
        yield connection
    finally:
        connection.rollback()
        connection.close()


@pytest.fixture(scope="module")
def mapper() -> OutcomeMapper:
    return OutcomeMapper(load_taxonomy_snapshot())


class _Graph:
    """Minimal parsed-graph seeder for supersession scenarios.

    One raw.source_documents row per docket (the schema's one-docket-per-
    document identity), each with a unique synthetic hash.
    """

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn
        self._doc_seq = 0

    def _source_document(self, cur) -> str:
        self._doc_seq += 1
        cur.execute(
            """
            INSERT INTO raw.source_documents
              (file_hash, original_filename, file_size_bytes, imported_at,
               import_mode, status)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (
                f"{self._doc_seq:064d}",
                f"synthetic-{self._doc_seq}.pdf",
                1,
                datetime.now(UTC),
                "manual",
                "imported",
            ),
        )
        return str(cur.fetchone()["id"])

    def docket(
        self,
        docket_number: str,
        court_type: str,
        *,
        otn: str | None = None,
        originating: str | None = None,
        filed: date | None = date(2025, 2, 1),
    ) -> str:
        with self.conn.cursor(row_factory=dict_row) as cur:
            source_document_id = self._source_document(cur)
            cur.execute(
                """
                INSERT INTO parsed.dockets
                  (source_document_id, docket_number, record_parser_version,
                   envelope_parser_version, parsed_at, county,
                   court_type_derived, filed_date, otn, originating_docket_no,
                   defendant_hash, envelope_status, review_needed)
                VALUES (%s, %s, 3, 8, %s, 'Philadelphia', %s, %s, %s, %s, %s,
                        'parsed', false)
                RETURNING id
                """,
                (
                    source_document_id,
                    docket_number,
                    datetime.now(UTC),
                    court_type,
                    filed,
                    otn,
                    originating,
                    "2" * 64,
                ),
            )
            docket_id = str(cur.fetchone()["id"])
        self.conn.commit()
        return docket_id

    def charge(
        self,
        docket_id: str,
        sequence: int,
        *,
        statute: str | None = STATUTE,
        disposition: str | None = None,
        orig_seq: int | None = None,
    ) -> str:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO parsed.charges
                  (docket_id, sequence, orig_seq, statute, offense,
                   disposition_raw)
                VALUES (%s, %s, %s, %s, 'Synthetic Offense', %s) RETURNING id
                """,
                (docket_id, sequence, orig_seq, statute, disposition),
            )
            charge_id = str(cur.fetchone()["id"])
        self.conn.commit()
        return charge_id

    def pointer(self, charge_id: str) -> str | None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT superseded_by_charge_id FROM parsed.charges WHERE id = %s",
                (charge_id,),
            )
            value = cur.fetchone()[0]
            return str(value) if value is not None else None


def _derive_and_apply(conn, mapper) -> tuple[dict[str, str], dict[str, int]]:
    mapping, counts = derive_supersessions(conn, mapper=mapper)
    with conn.transaction():
        apply_supersessions(conn, mapping)
    return mapping, counts


def test_happy_path_points_held_mc_charge_at_cp_twin(conn, mapper):
    graph = _Graph(conn)
    mc = graph.docket(MC_NUMBER, "MC", otn=OTN)
    mc_charge = graph.charge(mc, 1, disposition=HELD_FORM)
    cp = graph.docket(CP_NUMBER, "CP", otn=OTN, originating=MC_NUMBER)
    cp_charge = graph.charge(cp, 7, orig_seq=1)

    mapping, counts = _derive_and_apply(conn, mapper)

    assert mapping == {mc_charge: cp_charge}
    assert counts["superseded"] == 1
    assert graph.pointer(mc_charge) == cp_charge
    assert graph.pointer(cp_charge) is None

    # Idempotent: a second derivation over the unchanged corpus is identical.
    mapping_again, counts_again = _derive_and_apply(conn, mapper)
    assert mapping_again == mapping
    assert counts_again["superseded"] == 1


def test_all_case_and_charge_conditions_are_required(conn, mapper):
    graph = _Graph(conn)
    mc = graph.docket(MC_NUMBER, "MC", otn=OTN)
    graph.charge(mc, 1, disposition=HELD_FORM)
    graph.charge(mc, 2, disposition=HELD_FORM, statute=OTHER_STATUTE)

    # OTN mismatch: originating docket matches, OTN does not -> no case match.
    cp_wrong_otn = graph.docket(CP_NUMBER, "CP", otn=OTHER_OTN, originating=MC_NUMBER)
    graph.charge(cp_wrong_otn, 1, orig_seq=1)
    # orig_seq mismatch: case matches, no MC charge at that sequence.
    cp_wrong_seq = graph.docket(
        CP_NUMBER_B, "CP", otn=OTN, originating=MC_NUMBER, filed=date(2025, 3, 1)
    )
    graph.charge(cp_wrong_seq, 1, orig_seq=9)
    # statute mismatch: sequence matches, statute differs.
    graph.charge(cp_wrong_seq, 2, orig_seq=2)

    mapping, counts = _derive_and_apply(conn, mapper)

    assert mapping == {}
    assert counts["superseded"] == 0
    assert counts["no_case_match"] == 1
    assert counts["no_seq_match"] == 1
    assert counts["statute_mismatch"] == 1


def test_terminal_mc_outcomes_are_never_superseded(conn, mapper):
    """Withdrawn/dismissed-at-prelim (and remand-then-dismissed) charges keep
    their real MC outcomes: the CURRENT disposition governs, per the ruling."""
    graph = _Graph(conn)
    mc = graph.docket(MC_NUMBER, "MC", otn=OTN)
    mc_charge = graph.charge(mc, 1, disposition=TERMINAL_FORM)
    cp = graph.docket(CP_NUMBER, "CP", otn=OTN, originating=MC_NUMBER)
    graph.charge(cp, 1, orig_seq=1)

    mapping, counts = _derive_and_apply(conn, mapper)

    assert mapping == {}
    assert counts["mc_not_currently_held"] == 1
    assert graph.pointer(mc_charge) is None


def test_latest_filed_cp_case_wins_a_refile_second_round(conn, mapper):
    graph = _Graph(conn)
    mc = graph.docket(MC_NUMBER, "MC", otn=OTN)
    mc_charge = graph.charge(mc, 1, disposition=HELD_FORM)
    cp_round_one = graph.docket(
        CP_NUMBER, "CP", otn=OTN, originating=MC_NUMBER, filed=date(2025, 3, 1)
    )
    round_one_charge = graph.charge(cp_round_one, 1, orig_seq=1)
    cp_round_two = graph.docket(
        CP_NUMBER_B, "CP", otn=OTN, originating=MC_NUMBER, filed=date(2025, 9, 1)
    )
    round_two_charge = graph.charge(cp_round_two, 1, orig_seq=1)

    mapping, counts = _derive_and_apply(conn, mapper)

    assert mapping == {mc_charge: round_two_charge}
    assert counts["superseded"] == 1
    assert counts["later_claim_won"] == 1
    assert graph.pointer(mc_charge) == round_two_charge
    assert graph.pointer(round_one_charge) is None


def test_apply_replaces_the_whole_mapping(conn, mapper):
    """A stale pointer from an earlier derivation cannot survive an apply."""
    graph = _Graph(conn)
    mc = graph.docket(MC_NUMBER, "MC", otn=OTN)
    stale_holder = graph.charge(mc, 3, disposition=HELD_FORM)
    other = graph.docket(MC_NUMBER_B, "MC", otn=OTHER_OTN)
    stale_target = graph.charge(other, 1, disposition=None)
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE parsed.charges SET superseded_by_charge_id = %s WHERE id = %s",
            (stale_target, stale_holder),
        )
    conn.commit()
    assert graph.pointer(stale_holder) == stale_target

    mapping, _ = _derive_and_apply(conn, mapper)

    assert mapping == {}
    assert graph.pointer(stale_holder) is None


def test_cp_graph_delete_clears_pointers_via_set_null(conn, mapper):
    graph = _Graph(conn)
    mc = graph.docket(MC_NUMBER, "MC", otn=OTN)
    mc_charge = graph.charge(mc, 1, disposition=HELD_FORM)
    cp = graph.docket(CP_NUMBER, "CP", otn=OTN, originating=MC_NUMBER)
    graph.charge(cp, 1, orig_seq=1)
    _derive_and_apply(conn, mapper)
    assert graph.pointer(mc_charge) is not None

    with conn.cursor() as cur:
        cur.execute("DELETE FROM parsed.dockets WHERE id = %s", (cp,))
    conn.commit()

    assert graph.pointer(mc_charge) is None
