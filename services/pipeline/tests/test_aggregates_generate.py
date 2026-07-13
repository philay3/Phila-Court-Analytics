"""Tier-1 tests for charge-only outcome aggregate generation (Task 26.1).

Two suites:

- ``build_charge_outcome_aggregates`` PURE tests over synthetic fact dicts (no DB;
  always run). They cover the AC-8 scenarios directly on the aggregation core:
  multi-category charge, single-category charge, thin-data charge, the thin-flag
  boundary, 2025-window exclusion (read from the fact's own eligibility flag, never
  recomputed), empty group, percentage/sample-size reconciliation, and the
  fact-integrity STOP guards.

- ``generate_aggregates`` DB integration tests against a real Postgres TEST database
  (``PIPELINE_TEST_DATABASE_URL``): the full run lifecycle (a "generated" run opened as
  status ``in_progress`` and left unpublished), the written aggregate rows, re-run
  independence (SD 4), and the no-completed-build-run refusal. DB guards mirror the
  23.2 fact suite: reads ONLY ``PIPELINE_TEST_DATABASE_URL`` (absent -> local skip / CI
  hard failure), and the connected database name must contain "test" before any
  TRUNCATE.

Synthetic only: placeholder charge slugs and fabricated outcome codes; no docket
numbers, no defendant data.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime

import psycopg
import pytest
from psycopg.rows import dict_row

from pipeline.aggregates.generate import (
    FactIntegrityError,
    build_charge_outcome_aggregates,
    generate_aggregates,
)
from pipeline.fact_review_vocab import (
    DISPOSITION_DATE_BEFORE_MVP_WINDOW,
    DISPOSITION_NOT_MAPPED,
)
from pipeline.seam_check import running_in_ci

TAXONOMY_VERSION = "test-taxonomy-1"
CHARGE_A = "11111111-1111-1111-1111-111111111111"
CHARGE_B = "22222222-2222-2222-2222-222222222222"


def _fact(
    *,
    charge_id: str | None,
    category: str,
    disposition_date: date | None,
    public_eligible: bool,
    reason_codes: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "normalized_charge_id": charge_id,
        "outcome_category_code": category,
        "disposition_date": disposition_date,
        "public_eligible": public_eligible,
        "ineligibility_reason_codes": list(reason_codes),
    }


def _build(facts, *, thin_min_sample: int = 10):
    return build_charge_outcome_aggregates(
        facts,
        data_start_date=date(2025, 1, 1),
        thin_min_sample=thin_min_sample,
        taxonomy_version=TAXONOMY_VERSION,
    )


# --------------------------------------------------------------------------- #
# Pure aggregation core (no DB).                                              #
# --------------------------------------------------------------------------- #


def test_multi_category_charge_percentages_and_sample_size():
    # 12 eligible facts across three categories: 6 / 3 / 3 -> 50 / 25 / 25.
    facts = []
    facts += [
        _fact(
            charge_id=CHARGE_A,
            category="guilty_plea",
            disposition_date=date(2025, 2, 1),
            public_eligible=True,
        )
        for _ in range(6)
    ]
    facts += [
        _fact(
            charge_id=CHARGE_A,
            category="dismissed",
            disposition_date=date(2025, 5, 1),
            public_eligible=True,
        )
        for _ in range(3)
    ]
    facts += [
        _fact(
            charge_id=CHARGE_A,
            category="guilty",
            disposition_date=date(2025, 8, 1),
            public_eligible=True,
        )
        for _ in range(3)
    ]
    rows, report = _build(facts)

    assert {r["category_code"] for r in rows} == {"guilty_plea", "dismissed", "guilty"}
    by_cat = {r["category_code"]: r for r in rows}
    assert by_cat["guilty_plea"]["count"] == 6
    assert by_cat["guilty_plea"]["percentage"] == "50.00"
    assert by_cat["dismissed"]["percentage"] == "25.00"
    assert by_cat["guilty"]["percentage"] == "25.00"
    # Every row carries the charge's sample size (its eligible-fact denominator) and
    # the charge's eligible disposition-date span; none is thin (12 >= 10).
    for r in rows:
        assert r["sample_size"] == 12
        assert r["is_thin_data"] is False
        assert r["date_range_start"] == date(2025, 2, 1)
        assert r["date_range_end"] == date(2025, 8, 1)
        assert r["taxonomy_version"] == TAXONOMY_VERSION

    # Counts reconcile to the sample size exactly; percentages to 100 within tolerance.
    assert sum(r["count"] for r in rows) == 12
    assert abs(sum(float(r["percentage"]) for r in rows) - 100.0) <= 0.5
    assert report["facts_loaded"] == 12
    assert report["facts_included"] == 12
    assert report["facts_excluded"] == 0
    assert report["charges_with_aggregates"] == 1
    assert report["outcome_aggregates_generated"] == 3
    assert report["thin_data_charges"] == 0


def test_single_category_charge_is_one_hundred_percent():
    facts = [
        _fact(
            charge_id=CHARGE_A,
            category="guilty_plea",
            disposition_date=date(2025, 3, 1),
            public_eligible=True,
        )
        for _ in range(10)
    ]
    rows, _ = _build(facts)
    assert len(rows) == 1
    assert rows[0]["count"] == 10
    assert rows[0]["percentage"] == "100.00"


def test_thin_flag_fires_at_the_boundary():
    # Exactly at THIN_DATA_MIN_SAMPLE_SIZE (10) -> not thin.
    at_boundary = [
        _fact(
            charge_id=CHARGE_A,
            category="guilty_plea",
            disposition_date=date(2025, 3, 1),
            public_eligible=True,
        )
        for _ in range(10)
    ]
    rows, report = _build(at_boundary)
    assert rows[0]["is_thin_data"] is False
    assert report["thin_data_charges"] == 0

    # One below the threshold (9) -> thin.
    below = at_boundary[:9]
    rows, report = _build(below)
    assert rows[0]["is_thin_data"] is True
    assert report["thin_data_charges"] == 1


def test_2025_window_exclusion_reads_the_fact_flag():
    # Pre-window facts already carry public_eligible=False + the reason code (Sprint 5);
    # they are excluded from the denominator and tallied by reason, never recomputed.
    facts = [
        _fact(
            charge_id=CHARGE_A,
            category="guilty_plea",
            disposition_date=date(2025, 6, 1),
            public_eligible=True,
        )
        for _ in range(4)
    ] + [
        _fact(
            charge_id=CHARGE_A,
            category="guilty_plea",
            disposition_date=date(2024, 12, 1),
            public_eligible=False,
            reason_codes=(DISPOSITION_DATE_BEFORE_MVP_WINDOW,),
        )
        for _ in range(3)
    ]
    rows, report = _build(facts)
    assert len(rows) == 1
    # Denominator counts only the eligible facts, not the excluded pre-window ones.
    assert rows[0]["sample_size"] == 4
    assert rows[0]["count"] == 4
    assert rows[0]["date_range_start"] == date(2025, 6, 1)
    assert report["facts_included"] == 4
    assert report["facts_excluded"] == 3
    assert report["excluded_by_reason"] == {DISPOSITION_DATE_BEFORE_MVP_WINDOW: 3}


def test_empty_group_produces_no_rows():
    # A charge whose facts are all ineligible produces no aggregate rows (SD 6).
    facts = [
        _fact(
            charge_id=CHARGE_A,
            category="unknown",
            disposition_date=None,
            public_eligible=False,
            reason_codes=(DISPOSITION_NOT_MAPPED,),
        )
        for _ in range(3)
    ]
    rows, report = _build(facts)
    assert rows == []
    assert report["charges_with_aggregates"] == 0
    assert report["outcome_aggregates_generated"] == 0
    assert report["facts_included"] == 0
    assert report["facts_excluded"] == 3
    assert report["excluded_by_reason"] == {DISPOSITION_NOT_MAPPED: 3}


def test_two_charges_group_independently():
    facts = [
        _fact(
            charge_id=CHARGE_A,
            category="guilty_plea",
            disposition_date=date(2025, 4, 1),
            public_eligible=True,
        ),
        _fact(
            charge_id=CHARGE_B,
            category="dismissed",
            disposition_date=date(2025, 4, 2),
            public_eligible=True,
        ),
    ]
    rows, report = _build(facts)
    assert report["charges_with_aggregates"] == 2
    assert {r["charge_id"] for r in rows} == {CHARGE_A, CHARGE_B}
    for r in rows:
        assert r["sample_size"] == 1
        assert r["is_thin_data"] is True


def test_integrity_stop_on_eligible_fact_with_null_charge():
    facts = [
        _fact(
            charge_id=None,
            category="guilty_plea",
            disposition_date=date(2025, 4, 1),
            public_eligible=True,
        )
    ]
    with pytest.raises(FactIntegrityError):
        _build(facts)


def test_integrity_stop_on_eligible_fact_with_null_date():
    facts = [
        _fact(
            charge_id=CHARGE_A,
            category="guilty_plea",
            disposition_date=None,
            public_eligible=True,
        )
    ]
    with pytest.raises(FactIntegrityError):
        _build(facts)


def test_integrity_stop_on_eligible_fact_before_window():
    facts = [
        _fact(
            charge_id=CHARGE_A,
            category="guilty_plea",
            disposition_date=date(2024, 12, 31),
            public_eligible=True,
        )
    ]
    with pytest.raises(FactIntegrityError):
        _build(facts)


# --------------------------------------------------------------------------- #
# DB integration (real Postgres TEST database).                              #
# --------------------------------------------------------------------------- #

TEST_DB_URL_ENV_VAR = "PIPELINE_TEST_DATABASE_URL"


def _classify(url: str | None, *, in_ci: bool) -> tuple[str, str]:
    if url and url.strip():
        return ("run", url)
    if in_ci:
        return (
            "fail",
            f"{TEST_DB_URL_ENV_VAR} must be set for the aggregate suite in CI.",
        )
    return (
        "skip",
        f"{TEST_DB_URL_ENV_VAR} not set; skipping aggregate DB suite (local).",
    )


@pytest.fixture
def agg_conn():
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
            "refusing to run the aggregate suite against a database whose name does "
            f"not contain 'test'; point {TEST_DB_URL_ENV_VAR} at a test database."
        )
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE analytics.aggregate_runs CASCADE")
            cur.execute("TRUNCATE fact.fact_build_runs CASCADE")
            cur.execute("TRUNCATE raw.source_documents CASCADE")
            cur.execute("TRUNCATE ref.normalized_charges CASCADE")
        conn.commit()
        yield conn
    finally:
        conn.rollback()
        conn.close()


class _Seeder:
    """Seeds a synthetic ref/parsed/fact graph and hands out fact rows to aggregate."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn
        self._seq = 0
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "INSERT INTO ref.normalized_charges (slug, display_name) "
                "VALUES (%s, %s) RETURNING id",
                ("placeholder-charge-a", "Placeholder Charge A"),
            )
            self.charge_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO raw.source_documents
                  (file_hash, original_filename, file_size_bytes, imported_at,
                   import_mode, status)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                """,
                ("0" * 64, "synthetic.pdf", 1, datetime.now(UTC), "manual", "imported"),
            )
            self.source_document_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO parsed.dockets
                  (source_document_id, docket_number, record_parser_version,
                   envelope_parser_version, parsed_at, county, defendant_hash,
                   envelope_status, review_needed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (
                    self.source_document_id,
                    "CP-51-CR-0000000-2025",
                    2,
                    5,
                    datetime.now(UTC),
                    "Philadelphia",
                    "0" * 64,
                    "parsed",
                    False,
                ),
            )
            self.docket_id = str(cur.fetchone()["id"])
        conn.commit()

    def build_run(self) -> str:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO fact.fact_build_runs
                  (status, parser_version, envelope_parser_version, taxonomy_version,
                   started_at, completed_at)
                VALUES ('completed', %s, %s, %s, %s, %s) RETURNING id
                """,
                (2, 5, TAXONOMY_VERSION, datetime.now(UTC), datetime.now(UTC)),
            )
            run_id = str(cur.fetchone()["id"])
        self.conn.commit()
        return run_id

    def _parsed_charge(self, cur) -> str:
        self._seq += 1
        cur.execute(
            "INSERT INTO parsed.charges (docket_id, sequence) VALUES (%s, %s) "
            "RETURNING id",
            (self.docket_id, self._seq),
        )
        return str(cur.fetchone()["id"])

    def fact(
        self,
        build_run_id: str,
        *,
        category: str,
        disposition_date: date | None,
        public_eligible: bool,
        reason_codes: tuple[str, ...] = (),
    ) -> None:
        with self.conn.cursor(row_factory=dict_row) as cur:
            parsed_charge_id = self._parsed_charge(cur)
            cur.execute(
                """
                INSERT INTO fact.charge_outcomes
                  (build_run_id, parsed_charge_id, parsed_docket_id,
                   normalized_charge_id, outcome_category_code, disposition_date,
                   attribution_method, charge_match_method, outcome_match_method,
                   mvp_eligible, public_eligible, judge_specific_eligible,
                   ineligibility_reason_codes, review_needed, taxonomy_version)
                VALUES (%s, %s, %s, %s, %s, %s, 'charge_row', 'exact', 'exact',
                        %s, %s, %s, %s, false, %s)
                """,
                (
                    build_run_id,
                    parsed_charge_id,
                    self.docket_id,
                    self.charge_id,
                    category,
                    disposition_date,
                    public_eligible,
                    public_eligible,
                    False,
                    list(reason_codes),
                    TAXONOMY_VERSION,
                ),
            )
        self.conn.commit()


def _run_row(conn: psycopg.Connection, run_id: str) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM analytics.aggregate_runs WHERE id = %s", (run_id,))
        return cur.fetchone()


def _agg_rows(conn: psycopg.Connection, run_id: str) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM analytics.charge_outcome_aggregates "
            "WHERE aggregate_run_id = %s ORDER BY category_code",
            (run_id,),
        )
        return list(cur.fetchall())


def test_db_full_run_lifecycle_and_written_rows(agg_conn, capsys):
    seeder = _Seeder(agg_conn)
    build_run_id = seeder.build_run()
    for _ in range(6):
        seeder.fact(
            build_run_id,
            category="guilty_plea",
            disposition_date=date(2025, 2, 1),
            public_eligible=True,
        )
    for _ in range(4):
        seeder.fact(
            build_run_id,
            category="dismissed",
            disposition_date=date(2025, 7, 1),
            public_eligible=True,
        )
    # An excluded pre-window fact: it must not inflate the denominator, but is tallied.
    seeder.fact(
        build_run_id,
        category="guilty_plea",
        disposition_date=date(2024, 12, 1),
        public_eligible=False,
        reason_codes=(DISPOSITION_DATE_BEFORE_MVP_WINDOW,),
    )

    rc = generate_aggregates(
        agg_conn,
        build_run_id=None,
        data_start_date=date(2025, 1, 1),
        thin_min_sample=10,
        label="unit-test",
    )
    assert rc == 0

    # Exactly one aggregate run, opened "generated" == in_progress and unpublished.
    with agg_conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM analytics.aggregate_runs")
        run_ids = [str(r["id"]) for r in cur.fetchall()]
    assert len(run_ids) == 1
    run = _run_row(agg_conn, run_ids[0])
    assert run["status"] == "in_progress"
    assert run["published_at"] is None
    assert run["invalidated_at"] is None
    assert run["taxonomy_version"] == TAXONOMY_VERSION
    assert run["data_range_start"] == date(2025, 1, 1)
    assert run["data_range_end"] == date(2025, 7, 1)

    rows = _agg_rows(agg_conn, run_ids[0])
    assert [(r["category_code"], r["count"]) for r in rows] == [
        ("dismissed", 4),
        ("guilty_plea", 6),
    ]
    for r in rows:
        assert str(r["aggregate_run_id"]) == run_ids[0]
        assert str(r["charge_id"]) == seeder.charge_id
        assert r["sample_size"] == 10
        assert r["is_thin_data"] is False
        assert r["date_range_start"] == date(2025, 2, 1)
        assert r["date_range_end"] == date(2025, 7, 1)
    assert {str(r["percentage"]) for r in rows} == {"40.00", "60.00"}

    # Run report (counts only; hygiene) includes the excluded pre-window fact.
    out = capsys.readouterr().out
    assert "facts_loaded=11" in out
    assert "facts_included=10" in out
    assert "facts_excluded=1" in out
    assert "outcome_aggregates_generated=2" in out
    assert "(default)" in out


def test_db_rerun_is_independent_and_leaves_first_run_untouched(agg_conn):
    seeder = _Seeder(agg_conn)
    build_run_id = seeder.build_run()
    for _ in range(3):
        seeder.fact(
            build_run_id,
            category="guilty_plea",
            disposition_date=date(2025, 2, 1),
            public_eligible=True,
        )

    assert (
        generate_aggregates(
            agg_conn,
            build_run_id=build_run_id,
            data_start_date=date(2025, 1, 1),
            thin_min_sample=10,
            label="run-1",
        )
        == 0
    )
    assert (
        generate_aggregates(
            agg_conn,
            build_run_id=build_run_id,
            data_start_date=date(2025, 1, 1),
            thin_min_sample=10,
            label="run-2",
        )
        == 0
    )

    with agg_conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM analytics.aggregate_runs ORDER BY started_at")
        run_ids = [str(r["id"]) for r in cur.fetchall()]
    # Two independent generated runs; each carries its own single thin-data row.
    assert len(run_ids) == 2
    for run_id in run_ids:
        rows = _agg_rows(agg_conn, run_id)
        assert len(rows) == 1
        assert rows[0]["count"] == 3
        assert rows[0]["is_thin_data"] is True


def test_db_no_completed_build_run_refuses(agg_conn):
    # No fact build run at all -> refuse (exit 2), and no aggregate run row created.
    rc = generate_aggregates(
        agg_conn,
        build_run_id=None,
        data_start_date=date(2025, 1, 1),
        thin_min_sample=10,
        label="none",
    )
    assert rc == 2
    with agg_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM analytics.aggregate_runs")
        assert cur.fetchone()[0] == 0


def test_db_bad_build_run_id_refuses(agg_conn):
    _Seeder(agg_conn)  # graph exists, but no completed run with this id
    rc = generate_aggregates(
        agg_conn,
        build_run_id="99999999-9999-9999-9999-999999999999",
        data_start_date=date(2025, 1, 1),
        thin_min_sample=10,
        label="bad",
    )
    assert rc == 2
    with agg_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM analytics.aggregate_runs")
        assert cur.fetchone()[0] == 0
