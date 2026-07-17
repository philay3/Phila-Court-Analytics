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
    FILED_DATE_BEFORE_FLOOR,
    FILED_DATE_MISSING,
    JUDGE_NOT_ATTRIBUTED,
    PARENT_OUTCOME_INELIGIBLE,
    REVIEW_NEEDED,
    RUN_COMPLETED,
    RUN_FAILED,
    SENTENCE_DATE_BEFORE_MVP_WINDOW,
    SENTENCE_DURATION_UNPARSEABLE,
)
from pipeline.facts.build_facts import build_facts
from pipeline.facts.sentence_facts import ATTRIBUTION_METHOD_CHARGE_COMPONENT
from pipeline.normalization import charge_roster_loader, judge_roster_loader
from pipeline.seam_check import running_in_ci
from pipeline.warning_codes import SUSPECTED_AMENDED_CHARGE, UNPARSEABLE_DURATION

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
               assigned_judge_raw, envelope_status, review_needed, filed_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
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
                date(2025, 2, 1),  # filed in-window: the floor never gates docket 1
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
            (
                8,
                ROSTER_STATUTE,
                ROSTER_OFFENSE,
                "Held for Court",
                None,
                None,
            ),  # 29.3 held-form bind-over -> no fact, no review item
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
        # A charge-grain review-severity parser warning on seq 7.
        cur.execute(
            "INSERT INTO parsed.warnings (docket_id, code, charge_sequence) "
            "VALUES (%s, %s, %s)",
            (docket_id, SUSPECTED_AMENDED_CHARGE, 7),
        )
        _seed_sentences(cur, charge_ids, docket_id)

        # Filed-date-floor dockets (task filed-date-floor): each carries ONE
        # otherwise fully eligible charge + one clean probation component, so
        # the floor is the only ineligibility signal. Distinct sequences (9,
        # 10) keep the sequence-keyed assertion maps collision-free. Every
        # normalization path is clean (roster charge/judge, mapped
        # disposition), so these dockets add NO review items.
        _seed_floor_docket(
            cur,
            file_hash="1" * 64,
            docket_number="CP-51-CR-0000001-2023",
            filed_date=date(2023, 5, 1),  # pre-floor
            seq=9,
        )
        _seed_floor_docket(
            cur,
            file_hash="2" * 64,
            docket_number="CP-51-CR-0000002-2024",
            filed_date=None,  # null filed_date: the fail-closed arm
            seq=10,
        )
    conn.commit()


def _seed_floor_docket(cur, *, file_hash, docket_number, filed_date, seq) -> None:
    cur.execute(
        """
        INSERT INTO raw.source_documents
          (file_hash, original_filename, file_size_bytes, imported_at,
           import_mode, status)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """,
        (file_hash, "synthetic.pdf", 1, datetime.now(UTC), "manual", "imported"),
    )
    source_document_id = cur.fetchone()["id"]
    cur.execute(
        """
        INSERT INTO parsed.dockets
          (source_document_id, docket_number, record_parser_version,
           envelope_parser_version, parsed_at, county, defendant_hash,
           assigned_judge_raw, envelope_status, review_needed, filed_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """,
        (
            source_document_id,
            docket_number,
            2,
            5,
            datetime.now(UTC),
            "Philadelphia",
            "0" * 64,
            JUDGE_NAME,  # clean assigned-judge match: no review item
            "parsed",
            False,
            filed_date,
        ),
    )
    docket_id = cur.fetchone()["id"]
    cur.execute(
        """
        INSERT INTO parsed.charges
          (docket_id, sequence, statute, offense, disposition_raw,
           disposition_date, disposition_judge_raw)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """,
        (
            docket_id,
            seq,
            ROSTER_STATUTE,
            ROSTER_OFFENSE,
            "Guilty Plea",
            date(2025, 6, 1),
            JUDGE_NAME,
        ),
    )
    charge_id = cur.fetchone()["id"]
    cur.execute(
        """
        INSERT INTO parsed.sentences
          (charge_id, component_order, sentence_type, min_days, max_days,
           min_assumed, sentence_date, raw_text)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            charge_id,
            1,
            "Probation",
            365,
            None,
            False,
            date(2025, 6, 1),
            "Probation, Min of 12.00 Months",
        ),
    )


# Sentence components per DISPOSED charge (never on the held seq 5). Each
# ``sentence_date`` equals its charge's disposition_date (SD 15). The seq-4
# "Confinement, Life" carries no parsed days and a matching UNPARSEABLE_DURATION
# warning so the duration reconciliation is exercised too.
#   seq -> [(component_order, sentence_type, min_days, max_days, raw_text, date)]
_SENTENCES: dict[int, list[tuple]] = {
    1: [
        (
            1,
            "Confinement",
            90,
            180,
            "Confinement, Min of 3.00 Months Max of 6.00 Months",
            date(2025, 6, 1),
        ),
        (
            2,
            "Fines and Costs",
            None,
            None,
            "Fines and Costs, $500.00",
            date(2025, 6, 1),
        ),
    ],
    4: [(1, "Confinement", None, None, "Confinement, Life", date(2025, 6, 1))],
    6: [
        (1, "Probation", 365, None, "Probation, Min of 12.00 Months", date(2024, 6, 1))
    ],
    7: [
        (1, "Probation", 365, None, "Probation, Min of 12.00 Months", date(2025, 6, 1))
    ],
}


def _seed_sentences(cur, charge_ids: dict[int, str], docket_id: str) -> None:
    for seq, components in _SENTENCES.items():
        for order, stype, min_days, max_days, raw_text, sdate in components:
            cur.execute(
                """
                INSERT INTO parsed.sentences
                  (charge_id, component_order, sentence_type, min_days, max_days,
                   min_assumed, sentence_date, raw_text)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    charge_ids[seq],
                    order,
                    stype,
                    min_days,
                    max_days,
                    False,
                    sdate,
                    raw_text,
                ),
            )
    # The envelope-grain UNPARSEABLE_DURATION warning matching the seq-4 "Life"
    # component (charge grain; info severity — does not touch outcome eligibility).
    cur.execute(
        "INSERT INTO parsed.warnings (docket_id, code, charge_sequence) "
        "VALUES (%s, %s, %s)",
        (docket_id, UNPARSEABLE_DURATION, 4),
    )


def _sentence_facts(conn: psycopg.Connection) -> dict[tuple[int, int], dict]:
    """Sentence facts keyed by ``(charge_sequence, component_order)``."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT c.sequence AS seq, s.component_order AS ord, f.*
            FROM fact.charge_sentences f
            JOIN parsed.sentences s ON s.id = f.parsed_sentence_id
            JOIN parsed.charges c ON c.id = s.charge_id
            """
        )
        return {(row["seq"], row["ord"]): row for row in cur.fetchall()}


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
    assert run["parser_version"] == 2 and run["envelope_parser_version"] == 6
    assert run["taxonomy_version"]
    counts = run["counts"]
    assert counts["charges_processed"] == 10
    assert counts["facts_written"] == 8  # seq 5 undisposed, seq 8 held-form
    assert counts["undisposed_skipped"] == 1  # seq 5 (null disposition)
    assert counts["held_for_court_skipped"] == 1  # seq 8 (29.3 bind-over form)
    # The effective filed-date floor is persisted on the run row (config
    # visibility) and tallied per floor arm in the reason counts.
    assert counts["filed_date_floor"] == "2025-01-01"
    assert counts["ineligible_by_reason"][FILED_DATE_BEFORE_FLOOR] == 1  # seq 9
    assert counts["ineligible_by_reason"][FILED_DATE_MISSING] == 1  # seq 10
    assert (
        counts["facts_written"]
        + counts["undisposed_skipped"]
        + counts["held_for_court_skipped"]
        == counts["charges_processed"]
    )

    facts = _facts_by_sequence(conn)
    # seq 5 (undisposed) and seq 8 (held-form) produced no fact; their terminal
    # siblings on the same docket all did (the AC-3 fact-layer proof). The
    # floored dockets (seq 9, 10) still produce facts — the floor flips only
    # the eligibility dimension, never fact creation.
    assert set(facts) == {1, 2, 3, 4, 6, 7, 9, 10}

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

    # seq 9 — pre-floor filed_date: fact built, mvp keeps its event-date
    # meaning, public gated by the floor alone.
    f9 = facts[9]
    assert f9["mvp_eligible"] and not f9["public_eligible"]
    assert f9["ineligibility_reason_codes"] == [FILED_DATE_BEFORE_FLOOR]

    # seq 10 — null filed_date: fail-closed under filed_date_missing ONLY
    # (the arms are mutually exclusive).
    f10 = facts[10]
    assert f10["mvp_eligible"] and not f10["public_eligible"]
    assert f10["ineligibility_reason_codes"] == [FILED_DATE_MISSING]


def test_sentence_facts_built_linked_and_scored(build_conn):
    conn, url = build_conn
    _seed(conn)

    assert build_facts(conn, url) == 0

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT counts FROM fact.fact_build_runs")
        counts = cur.fetchone()["counts"]
    sc = counts["sentences"]
    # 2 (seq1) + 1 each (seq4, 6, 7, 9, 10) = 7 components on disposed charges.
    assert sc["sentence_facts_written"] == 7
    assert sc["components_on_disposed"] == 7
    assert sc["duration_unparseable_facts"] == 1
    assert sc["duration_warning_count"] == 1
    assert sc["duration_predicate_all"] == 1
    assert sc["monetary_components"] == 1 and sc["amount_set"] == 1

    outcomes = _facts_by_sequence(conn)
    sentences = _sentence_facts(conn)
    # Exactly the disposed-charge components; the held seq 5 contributes none.
    assert set(sentences) == {(1, 1), (1, 2), (4, 1), (6, 1), (7, 1), (9, 1), (10, 1)}

    # seq1 — two components, both fully eligible, FK'd to the seq1 outcome fact,
    # judge + normalized-charge fields inherited verbatim from the parent.
    parent1 = outcomes[1]
    confinement = sentences[(1, 1)]
    fine = sentences[(1, 2)]
    for row in (confinement, fine):
        assert row["charge_outcome_id"] == parent1["id"]
        assert row["normalized_charge_id"] == parent1["normalized_charge_id"]
        assert row["normalized_judge_id"] == parent1["normalized_judge_id"]
        assert row["judge_attribution_method"] == parent1["judge_attribution_method"]
        assert row["attribution_method"] == ATTRIBUTION_METHOD_CHARGE_COMPONENT
        assert row["public_eligible"] and row["judge_specific_eligible"]
        assert row["ineligibility_reason_codes"] == []
    assert confinement["sentencing_category_code"] == "incarceration"
    assert confinement["min_days"] == 90 and confinement["max_days"] == 180
    assert fine["sentencing_category_code"] == "costs_fees"
    assert fine["amount_cents"] == 50000

    # seq4 — "Confinement, Life": duration-unparseable -> review; parent seq4 is
    # public (so NOT parent-ineligible), but the sentence is review-gated.
    life = sentences[(4, 1)]
    assert life["charge_outcome_id"] == outcomes[4]["id"]
    assert life["min_days"] is None and life["max_days"] is None
    assert life["review_needed"] and not life["public_eligible"]
    assert SENTENCE_DURATION_UNPARSEABLE in life["ineligibility_reason_codes"]
    assert PARENT_OUTCOME_INELIGIBLE not in life["ineligibility_reason_codes"]

    # seq6 — pre-window sentence_date -> mvp-ineligible (parent also ineligible).
    pre = sentences[(6, 1)]
    assert not pre["mvp_eligible"]
    assert pre["sentence_date"] == date(2024, 6, 1)
    assert SENTENCE_DATE_BEFORE_MVP_WINDOW in pre["ineligibility_reason_codes"]

    # seq7 — parent gated by a review-severity warning: transitive parent gate.
    seven = sentences[(7, 1)]
    assert not seven["public_eligible"]
    assert PARENT_OUTCOME_INELIGIBLE in seven["ineligibility_reason_codes"]

    # seq9 — pre-floor filed_date: the sentence fact carries BOTH the direct
    # floor code (pinned decision 1: every population) and the transitive
    # parent code ("every applicable reason").
    floored = sentences[(9, 1)]
    assert not floored["public_eligible"]
    assert FILED_DATE_BEFORE_FLOOR in floored["ineligibility_reason_codes"]
    assert PARENT_OUTCOME_INELIGIBLE in floored["ineligibility_reason_codes"]

    # seq10 — null filed_date: fail-closed missing arm only, plus the parent.
    nulled = sentences[(10, 1)]
    assert not nulled["public_eligible"]
    assert FILED_DATE_MISSING in nulled["ineligibility_reason_codes"]
    assert FILED_DATE_BEFORE_FLOOR not in nulled["ineligibility_reason_codes"]

    # Task 23.4 now wires review items into the queue: this seed yields exactly one
    # item per real normalization/attribution signal it carries (dedup-collapsed).
    # (Exhaustive per-type coverage lives in test_review_item_wiring.py.)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT item_type, count(*) AS n FROM review.queue_items GROUP BY item_type"
        )
        by_type = {r["item_type"]: r["n"] for r in cur.fetchall()}
    assert by_type == {
        "unmapped_charge": 1,  # seq 3: unlisted statute/offense
        "unmapped_disposition": 1,  # seq 2: unmapped disposition_raw
        "unmapped_judge": 1,  # assigned "Beta Nomatch"
        "duration_unparseable": 1,  # seq 4: "Confinement, Life"
    }


def test_held_charge_sentence_is_stop(build_conn):
    conn, url = build_conn
    _seed(conn)
    # Attach a sentence component to the HELD charge (seq 5) -> orphan risk -> STOP.
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id FROM parsed.charges WHERE sequence = 5 AND docket_id IN "
            "(SELECT id FROM parsed.dockets)"
        )
        held_charge_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO parsed.sentences
              (charge_id, component_order, sentence_type, sentence_date, raw_text)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (held_charge_id, 1, "Probation", None, "Probation"),
        )
    conn.commit()

    # Read-only pre-write STOP: returns 2 and creates NO run and NO facts.
    assert build_facts(conn, url) == 2
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) AS n FROM fact.fact_build_runs")
        assert cur.fetchone()["n"] == 0
        cur.execute("SELECT count(*) AS n FROM fact.charge_outcomes")
        assert cur.fetchone()["n"] == 0
        cur.execute("SELECT count(*) AS n FROM fact.charge_sentences")
        assert cur.fetchone()["n"] == 0


def test_held_form_charge_sentence_is_stop(build_conn):
    conn, url = build_conn
    _seed(conn)
    # Attach a sentence component to the held-FORM charge (seq 8). Its charge is
    # "disposed" to the sentence layer (non-null disposition_raw) but produces
    # no outcome fact under the 29.3 carve-out, so the sentence has no parent
    # fact -> SentenceIntegrityError inside the build tx -> failed run, zero
    # facts persisted. (The live corpus carries zero such sentences — recon —
    # so this guard is a structural lock, not an expected path.) The component
    # is duration-CLEAN (parsed days) so the pre-write duration-drift STOP does
    # not fire first — the no-parent-fact stop is the one under test.
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id FROM parsed.charges WHERE sequence = 8 AND docket_id IN "
            "(SELECT id FROM parsed.dockets)"
        )
        held_form_charge_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO parsed.sentences
              (charge_id, component_order, sentence_type, min_days, max_days,
               min_assumed, sentence_date, raw_text)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                held_form_charge_id,
                1,
                "Probation",
                365,
                None,
                False,
                date(2025, 6, 1),
                "Probation, Min of 12.00 Months",
            ),
        )
    conn.commit()

    # In-transaction STOP: the run row survives as failed; no facts persist.
    assert build_facts(conn, url) == 1
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT status FROM fact.fact_build_runs")
        rows = cur.fetchall()
        assert len(rows) == 1 and rows[0]["status"] == RUN_FAILED
        cur.execute("SELECT count(*) AS n FROM fact.charge_outcomes")
        assert cur.fetchone()["n"] == 0
        cur.execute("SELECT count(*) AS n FROM fact.charge_sentences")
        assert cur.fetchone()["n"] == 0


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
