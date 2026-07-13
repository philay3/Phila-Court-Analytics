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
    build_charge_sentencing_aggregates,
    generate_aggregates,
)
from pipeline.fact_review_vocab import (
    DISPOSITION_DATE_BEFORE_MVP_WINDOW,
    DISPOSITION_NOT_MAPPED,
    SENTENCING_CATEGORY_NOT_PUBLIC,
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
# Pure sentencing aggregation core (no DB) — Task 26.2.                       #
# --------------------------------------------------------------------------- #


def _sfact(
    *,
    charge_id: str | None,
    category: str,
    sentence_date: date | None,
    public_eligible: bool,
    reason_codes: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "normalized_charge_id": charge_id,
        "sentencing_category_code": category,
        "sentence_date": sentence_date,
        "public_eligible": public_eligible,
        "ineligibility_reason_codes": list(reason_codes),
    }


def _sbuild(facts, *, thin_min_sample: int = 10):
    return build_charge_sentencing_aggregates(
        facts,
        data_start_date=date(2025, 1, 1),
        thin_min_sample=thin_min_sample,
        taxonomy_version=TAXONOMY_VERSION,
    )


def test_sentencing_multi_component_counted_independently():
    # 12 eligible sentence-component facts across three categories: 6 / 3 / 3.
    # Each component is its own fact (multi-component sentences are never collapsed),
    # so the sentencing denominator is 12 components, computed independently of any
    # outcome count (SD 5). -> 50 / 25 / 25.
    facts = []
    facts += [
        _sfact(
            charge_id=CHARGE_A,
            category="confinement",
            sentence_date=date(2025, 2, 1),
            public_eligible=True,
        )
        for _ in range(6)
    ]
    facts += [
        _sfact(
            charge_id=CHARGE_A,
            category="probation",
            sentence_date=date(2025, 5, 1),
            public_eligible=True,
        )
        for _ in range(3)
    ]
    facts += [
        _sfact(
            charge_id=CHARGE_A,
            category="fine",
            sentence_date=date(2025, 8, 1),
            public_eligible=True,
        )
        for _ in range(3)
    ]
    rows, report = _sbuild(facts)

    by_cat = {r["category_code"]: r for r in rows}
    assert set(by_cat) == {"confinement", "probation", "fine"}
    assert by_cat["confinement"]["count"] == 6
    assert by_cat["confinement"]["percentage"] == "50.00"
    assert by_cat["probation"]["percentage"] == "25.00"
    assert by_cat["fine"]["percentage"] == "25.00"
    for r in rows:
        # Independent sentencing denominator carried on every row; no outcome coupling.
        assert r["sentencing_sample_size"] == 12
        assert "sample_size" not in r
        assert r["is_thin_data"] is False
        assert r["date_range_start"] == date(2025, 2, 1)
        assert r["date_range_end"] == date(2025, 8, 1)
        assert r["taxonomy_version"] == TAXONOMY_VERSION
    assert sum(r["count"] for r in rows) == 12
    assert report["sentence_facts_loaded"] == 12
    assert report["sentence_facts_included"] == 12
    assert report["charges_with_sentencing"] == 1
    assert report["sentencing_aggregates_generated"] == 3
    assert report["thin_data_sentencing_charges"] == 0


def test_sentencing_thin_flag_fires_at_the_boundary():
    at_boundary = [
        _sfact(
            charge_id=CHARGE_A,
            category="probation",
            sentence_date=date(2025, 3, 1),
            public_eligible=True,
        )
        for _ in range(10)
    ]
    rows, report = _sbuild(at_boundary)
    assert rows[0]["is_thin_data"] is False
    assert report["thin_data_sentencing_charges"] == 0

    rows, report = _sbuild(at_boundary[:9])
    assert rows[0]["is_thin_data"] is True
    assert report["thin_data_sentencing_charges"] == 1


def test_sentencing_empty_group_produces_no_rows():
    # A charge whose sentence facts are all ineligible produces no sentencing rows
    # (SD 6) — the excluded facts are tallied by their own reason codes, never
    # recomputed.
    facts = [
        _sfact(
            charge_id=CHARGE_A,
            category="confinement",
            sentence_date=date(2025, 4, 1),
            public_eligible=False,
            reason_codes=(SENTENCING_CATEGORY_NOT_PUBLIC,),
        )
        for _ in range(3)
    ]
    rows, report = _sbuild(facts)
    assert rows == []
    assert report["charges_with_sentencing"] == 0
    assert report["sentencing_aggregates_generated"] == 0
    assert report["sentence_facts_included"] == 0
    assert report["sentence_facts_excluded"] == 3
    assert report["sentencing_excluded_by_reason"] == {
        SENTENCING_CATEGORY_NOT_PUBLIC: 3
    }


def test_sentencing_two_charges_have_independent_denominators():
    facts = [
        _sfact(
            charge_id=CHARGE_A,
            category="confinement",
            sentence_date=date(2025, 4, 1),
            public_eligible=True,
        ),
        _sfact(
            charge_id=CHARGE_B,
            category="probation",
            sentence_date=date(2025, 4, 2),
            public_eligible=True,
        ),
    ]
    rows, report = _sbuild(facts)
    assert report["charges_with_sentencing"] == 2
    assert {r["charge_id"] for r in rows} == {CHARGE_A, CHARGE_B}
    for r in rows:
        assert r["sentencing_sample_size"] == 1
        assert r["is_thin_data"] is True


def test_sentencing_integrity_stop_on_eligible_fact_with_null_charge():
    facts = [
        _sfact(
            charge_id=None,
            category="probation",
            sentence_date=date(2025, 4, 1),
            public_eligible=True,
        )
    ]
    with pytest.raises(FactIntegrityError):
        _sbuild(facts)


def test_sentencing_integrity_stop_on_eligible_fact_with_null_date():
    facts = [
        _sfact(
            charge_id=CHARGE_A,
            category="probation",
            sentence_date=None,
            public_eligible=True,
        )
    ]
    with pytest.raises(FactIntegrityError):
        _sbuild(facts)


def test_sentencing_integrity_stop_on_eligible_fact_before_window():
    # An eligible sentence fact dated before the 2025-01-01 floor is a fact-layer
    # defect surfaced as a STOP (SD 1: read eligibility, never silently filter).
    facts = [
        _sfact(
            charge_id=CHARGE_A,
            category="probation",
            sentence_date=date(2024, 12, 31),
            public_eligible=True,
        )
    ]
    with pytest.raises(FactIntegrityError):
        _sbuild(facts)


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

    def new_charge(self, slug: str, display_name: str) -> str:
        """Insert an additional normalized charge and return its id."""
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "INSERT INTO ref.normalized_charges (slug, display_name) "
                "VALUES (%s, %s) RETURNING id",
                (slug, display_name),
            )
            charge_id = str(cur.fetchone()["id"])
        self.conn.commit()
        return charge_id

    def fact(
        self,
        build_run_id: str,
        *,
        category: str,
        disposition_date: date | None,
        public_eligible: bool,
        reason_codes: tuple[str, ...] = (),
        charge_id: str | None = None,
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
                    charge_id or self.charge_id,
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

    def sentenced_outcome(
        self,
        build_run_id: str,
        *,
        outcome_category: str,
        disposition_date: date | None,
        components: list[tuple[str, date | None, bool, tuple[str, ...]]],
        charge_id: str | None = None,
    ) -> None:
        """Seed one eligible parent outcome fact and its 1:1 sentence-component facts.

        Each component is ``(sentencing_category_code, sentence_date, public_eligible,
        reason_codes)`` and becomes its own ``fact.charge_sentences`` row under a shared
        parent ``fact.charge_outcomes`` — mirroring the real, never-collapsed
        multi-component shape. The parent outcome is public-eligible, so it also counts
        in the charge's outcome denominator (every sentenced charge has an outcome).
        """
        target_charge = charge_id or self.charge_id
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
                        true, true, false, %s, false, %s)
                RETURNING id
                """,
                (
                    build_run_id,
                    parsed_charge_id,
                    self.docket_id,
                    target_charge,
                    outcome_category,
                    disposition_date,
                    [],
                    TAXONOMY_VERSION,
                ),
            )
            outcome_id = str(cur.fetchone()["id"])
            for order, (
                category,
                sentence_date,
                public_eligible,
                reason_codes,
            ) in enumerate(components, start=1):
                cur.execute(
                    """
                    INSERT INTO parsed.sentences
                      (charge_id, component_order, sentence_type, raw_text,
                       sentence_date)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id
                    """,
                    (parsed_charge_id, order, "synthetic", "synthetic", sentence_date),
                )
                parsed_sentence_id = str(cur.fetchone()["id"])
                cur.execute(
                    """
                    INSERT INTO fact.charge_sentences
                      (build_run_id, charge_outcome_id, parsed_sentence_id,
                       normalized_charge_id, sentencing_category_code, sentence_date,
                       attribution_method, component_match_method, mvp_eligible,
                       public_eligible, judge_specific_eligible,
                       ineligibility_reason_codes, review_needed, taxonomy_version)
                    VALUES (%s, %s, %s, %s, %s, %s, 'charge_row', 'exact',
                            %s, %s, false, %s, false, %s)
                    """,
                    (
                        build_run_id,
                        outcome_id,
                        parsed_sentence_id,
                        target_charge,
                        category,
                        sentence_date,
                        public_eligible,
                        public_eligible,
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


def _sent_rows(conn: psycopg.Connection, run_id: str) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM analytics.charge_sentencing_aggregates "
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


def test_db_outcome_and_sentencing_share_one_run(agg_conn, capsys):
    # Two charges: one with both outcomes and sentencing (incl. a multi-component
    # sentence), one with an eligible outcome but NO sentence facts (SD 6).
    seeder = _Seeder(agg_conn)
    charge_both = seeder.charge_id
    charge_outcomes_only = seeder.new_charge(
        "placeholder-charge-b", "Placeholder Charge B"
    )
    build_run_id = seeder.build_run()

    # charge_both, sentenced outcome #1: three components (confinement+probation+fine)
    # under a single outcome — the named multi-component case (never collapsed).
    seeder.sentenced_outcome(
        build_run_id,
        charge_id=charge_both,
        outcome_category="guilty",
        disposition_date=date(2025, 3, 1),
        components=[
            ("confinement", date(2025, 3, 15), True, ()),
            ("probation", date(2025, 3, 15), True, ()),
            ("fine", date(2025, 3, 15), True, ()),
        ],
    )
    # #2 and #3: single-component sentences.
    seeder.sentenced_outcome(
        build_run_id,
        charge_id=charge_both,
        outcome_category="guilty_plea",
        disposition_date=date(2025, 4, 1),
        components=[("probation", date(2025, 4, 2), True, ())],
    )
    seeder.sentenced_outcome(
        build_run_id,
        charge_id=charge_both,
        outcome_category="guilty_plea",
        disposition_date=date(2025, 5, 1),
        components=[("fine", date(2025, 5, 3), True, ())],
    )
    # charge_outcomes_only: an eligible outcome fact, no sentence facts at all.
    seeder.fact(
        build_run_id,
        charge_id=charge_outcomes_only,
        category="dismissed",
        disposition_date=date(2025, 6, 1),
        public_eligible=True,
    )

    rc = generate_aggregates(
        agg_conn,
        build_run_id=None,
        data_start_date=date(2025, 1, 1),
        thin_min_sample=10,
        label="unit-test",
    )
    assert rc == 0

    with agg_conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM analytics.aggregate_runs")
        run_ids = [str(r["id"]) for r in cur.fetchall()]
    assert len(run_ids) == 1
    run_id = run_ids[0]

    # Run-level range: start at the floor; end is the UNION envelope of outcome
    # dispositions (max 2025-06-01) and sentence dates (max 2025-05-03).
    run = _run_row(agg_conn, run_id)
    assert run["data_range_start"] == date(2025, 1, 1)
    assert run["data_range_end"] == date(2025, 6, 1)

    # Outcome aggregates: both charges present.
    outcome_rows = _agg_rows(agg_conn, run_id)
    outcome_by_charge = {}
    for r in outcome_rows:
        outcome_by_charge.setdefault(str(r["charge_id"]), []).append(r)
    assert set(outcome_by_charge) == {charge_both, charge_outcomes_only}

    # Sentencing aggregates: ONLY charge_both; independent denominator of 5 components
    # (confinement 1, probation 2, fine 2), thin (5 < 10), sentence-date range.
    sent_rows = _sent_rows(agg_conn, run_id)
    assert {str(r["charge_id"]) for r in sent_rows} == {charge_both}
    sent_by_cat = {r["category_code"]: r for r in sent_rows}
    assert sent_by_cat["confinement"]["count"] == 1
    assert sent_by_cat["probation"]["count"] == 2
    assert sent_by_cat["fine"]["count"] == 2
    for r in sent_rows:
        assert r["sentencing_sample_size"] == 5
        assert r["is_thin_data"] is True
        assert r["date_range_start"] == date(2025, 3, 15)
        assert r["date_range_end"] == date(2025, 5, 3)
    assert {str(r["percentage"]) for r in sent_rows} == {"20.00", "40.00"}

    # charge_outcomes_only has no sentencing rows (absence, not a placeholder).
    assert all(str(r["charge_id"]) != charge_outcomes_only for r in sent_rows)

    # Run report extends with sentencing tallies + the outcomes-but-no-sentencing count.
    out = capsys.readouterr().out
    assert "sentence_facts_loaded=5" in out
    assert "sentence_facts_included=5" in out
    assert "sentencing_aggregates_generated=3" in out
    assert "charges_with_sentencing=1" in out
    assert "charges_with_outcomes_no_sentencing=1" in out
    assert "thin_data_sentencing_charges=1" in out


def test_db_sentencing_before_window_stops_leaving_no_run(agg_conn):
    # An eligible sentence fact dated before the floor is a fact-integrity STOP: both
    # pure builds run before any write, so no aggregate run row is created and no
    # outcome rows leak either.
    seeder = _Seeder(agg_conn)
    build_run_id = seeder.build_run()
    seeder.sentenced_outcome(
        build_run_id,
        outcome_category="guilty",
        disposition_date=date(2025, 3, 1),
        components=[("probation", date(2024, 12, 1), True, ())],
    )

    rc = generate_aggregates(
        agg_conn,
        build_run_id=None,
        data_start_date=date(2025, 1, 1),
        thin_min_sample=10,
        label="stop",
    )
    assert rc == 2
    with agg_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM analytics.aggregate_runs")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM analytics.charge_outcome_aggregates")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM analytics.charge_sentencing_aggregates")
        assert cur.fetchone()[0] == 0
