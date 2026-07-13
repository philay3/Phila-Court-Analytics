"""Tier-1 tests for aggregate + privacy validation (Task 28.1).

Two suites, mirroring the 26.x/27.x aggregate test layout:

- PURE tests over synthetic aggregate-row dicts (no DB; always run) for the
  three check families: per-table integrity (count sums, sample-size
  consistency, percentage/count alignment within the inclusive ±0.005
  tolerance, presence checks, the 2025-01-01 window floor, inverted ranges,
  run-id and taxonomy-version presence), the SD-7 baseline check, and the
  privacy scan (via an in-test term list — artifact parity lives in
  ``test_forbidden_scan.py``).

- ``validate_aggregates`` DB integration tests against a real Postgres TEST
  database (``PIPELINE_TEST_DATABASE_URL``), reusing the 26.1 suite's seeder
  and guards: a good generated run validates to ``completed`` (with
  ``completed_at``); a deliberately count-mismatched run fails to ``failed``
  and the ``published_at`` CHECK then structurally refuses publish; a
  privacy-violating row fails the run; a missing SD-7 baseline fails the
  run; run selection (default latest generated run; ``--run`` refusing
  failed runs; re-validation of a completed unpublished run) behaves as
  specified. DB guards mirror 26.1: reads ONLY ``PIPELINE_TEST_DATABASE_URL``
  (absent -> local skip / CI hard failure) via the imported ``_classify``,
  and the connected database name must contain "test" before any TRUNCATE.

Synthetic only: placeholder charge/judge slugs, fabricated category codes,
and the shared TS suite's fabricated docket-shaped poison strings. No figure
from any real run is pinned anywhere — every assertion is against rows this
suite seeds itself.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
import pytest
from psycopg import errors
from psycopg.rows import dict_row
from test_aggregates_generate import TEST_DB_URL_ENV_VAR, _classify, _Seeder

from pipeline.aggregates.generate import generate_aggregates
from pipeline.aggregates.validate import (
    CHECK_BASELINE_MISSING,
    CHECK_COUNT_SUM_MISMATCH,
    CHECK_DATE_RANGE_BEFORE_WINDOW,
    CHECK_DATE_RANGE_INVERTED,
    CHECK_DATE_RANGE_MISSING,
    CHECK_PERCENTAGE_MISALIGNED,
    CHECK_PRIVACY_VIOLATION,
    CHECK_RUN_ID_MISMATCH,
    CHECK_SAMPLE_SIZE_INCONSISTENT,
    CHECK_SAMPLE_SIZE_MISSING,
    CHECK_TAXONOMY_VERSION_MISSING,
    scannable_row,
    validate_aggregates,
    validate_baseline,
    validate_privacy,
    validate_table_rows,
)
from pipeline.forbidden_scan import ForbiddenTerms

TAXONOMY_VERSION = "test-taxonomy-1"
RUN_ID = "55555555-5555-5555-5555-555555555555"
OTHER_RUN_ID = "66666666-6666-6666-6666-666666666666"
CHARGE_A = "11111111-1111-1111-1111-111111111111"
CHARGE_B = "22222222-2222-2222-2222-222222222222"
JUDGE_X = "33333333-3333-3333-3333-333333333333"

WINDOW_START = date(2025, 1, 1)

# In-test scanner terms for the pure privacy tests: the shared docket value
# pattern plus one stem. Parity with the real artifact is proven in
# test_forbidden_scan.py; these tests exercise the validator's use of a scan.
_DOCKET_PATTERN = re.compile(r"\b(?:CP|MC)-\d{2}-[A-Za-z]{2}-\d{4,7}-\d{4}\b", re.I)
TERMS = ForbiddenTerms(field_stems=("docket",), value_patterns=(_DOCKET_PATTERN,))


def _row(
    *,
    count: int,
    percentage: str,
    sample_size: int | None,
    charge_id: str = CHARGE_A,
    judge_id: str | None = None,
    category: str = "cat_a",
    run_id: str | None = RUN_ID,
    start: date | None = date(2025, 2, 1),
    end: date | None = date(2025, 7, 1),
    taxonomy_version: str | None = TAXONOMY_VERSION,
) -> dict[str, object]:
    row: dict[str, object] = {
        "aggregate_run_id": run_id,
        "charge_id": charge_id,
        "category_code": category,
        "count": count,
        "percentage": Decimal(percentage),
        "sample_size": sample_size,
        "date_range_start": start,
        "date_range_end": end,
        "is_thin_data": False,
        "taxonomy_version": taxonomy_version,
    }
    if judge_id is not None:
        row["judge_id"] = judge_id
    return row


def _check(rows, *, has_judge: bool = False) -> Counter[str]:
    return validate_table_rows(
        rows,
        sample_field="sample_size",
        has_judge=has_judge,
        expected_run_id=RUN_ID,
        data_start_date=WINDOW_START,
    )


# --------------------------------------------------------------------------- #
# Pure: per-table integrity checks.                                          #
# --------------------------------------------------------------------------- #


def test_good_rows_produce_no_violations():
    rows = [
        _row(count=6, percentage="60.00", sample_size=10, category="cat_a"),
        _row(count=4, percentage="40.00", sample_size=10, category="cat_b"),
    ]
    assert _check(rows) == Counter()


def test_count_sum_mismatch_is_flagged_per_group():
    rows = [
        _row(count=6, percentage="60.00", sample_size=10, category="cat_a"),
        _row(count=3, percentage="30.00", sample_size=10, category="cat_b"),
    ]
    assert _check(rows)[CHECK_COUNT_SUM_MISMATCH] == 1


def test_inconsistent_sample_size_within_a_group_is_flagged():
    rows = [
        _row(count=6, percentage="60.00", sample_size=10, category="cat_a"),
        _row(count=4, percentage="40.00", sample_size=11, category="cat_b"),
    ]
    violations = _check(rows)
    assert violations[CHECK_SAMPLE_SIZE_INCONSISTENT] == 1
    # An inconsistent group is not additionally judged on its count sum.
    assert violations[CHECK_COUNT_SUM_MISMATCH] == 0


def test_percentage_within_inclusive_tolerance_passes():
    # 1/32 is exactly 3.125%: both 2-decimal roundings sit exactly 0.005
    # away — the inclusive boundary — and both must pass.
    for stored in ("3.13", "3.12"):
        rows = [
            _row(count=1, percentage=stored, sample_size=32, category="cat_a"),
            _row(count=31, percentage="96.88", sample_size=32, category="cat_b"),
        ]
        assert _check(rows)[CHECK_PERCENTAGE_MISALIGNED] == 0


def test_percentage_beyond_tolerance_is_flagged():
    rows = [
        _row(count=1, percentage="3.14", sample_size=32, category="cat_a"),
        _row(count=31, percentage="96.88", sample_size=32, category="cat_b"),
    ]
    assert _check(rows)[CHECK_PERCENTAGE_MISALIGNED] == 1


def test_missing_sample_size_is_flagged_and_skips_alignment():
    rows = [_row(count=5, percentage="50.00", sample_size=None)]
    violations = _check(rows)
    assert violations[CHECK_SAMPLE_SIZE_MISSING] == 1
    assert violations[CHECK_PERCENTAGE_MISALIGNED] == 0


def test_missing_date_range_is_flagged():
    rows = [_row(count=1, percentage="100.00", sample_size=1, start=None, end=None)]
    assert _check(rows)[CHECK_DATE_RANGE_MISSING] == 1


def test_date_range_start_before_window_is_flagged():
    rows = [
        _row(
            count=1,
            percentage="100.00",
            sample_size=1,
            start=date(2024, 12, 31),
            end=date(2025, 2, 1),
        )
    ]
    assert _check(rows)[CHECK_DATE_RANGE_BEFORE_WINDOW] == 1


def test_inverted_date_range_is_flagged():
    rows = [
        _row(
            count=1,
            percentage="100.00",
            sample_size=1,
            start=date(2025, 7, 1),
            end=date(2025, 2, 1),
        )
    ]
    assert _check(rows)[CHECK_DATE_RANGE_INVERTED] == 1


def test_missing_taxonomy_version_is_flagged():
    rows = [_row(count=1, percentage="100.00", sample_size=1, taxonomy_version=" ")]
    assert _check(rows)[CHECK_TAXONOMY_VERSION_MISSING] == 1


def test_foreign_or_missing_run_id_is_flagged():
    rows = [
        _row(count=1, percentage="100.00", sample_size=1, run_id=OTHER_RUN_ID),
        _row(
            count=1,
            percentage="100.00",
            sample_size=1,
            run_id=None,
            charge_id=CHARGE_B,
        ),
    ]
    assert _check(rows)[CHECK_RUN_ID_MISMATCH] == 2


def test_judge_tables_group_per_charge_judge_pair():
    # Same charge under two judges: independent groups, both clean.
    rows = [
        _row(count=2, percentage="100.00", sample_size=2, judge_id=JUDGE_X),
        _row(
            count=3,
            percentage="100.00",
            sample_size=3,
            judge_id="77777777-7777-7777-7777-777777777777",
        ),
    ]
    assert _check(rows, has_judge=True) == Counter()
    # Without judge grouping the same rows would collide into one bad group.
    assert _check(rows, has_judge=False) != Counter()


# --------------------------------------------------------------------------- #
# Pure: SD-7 baseline check.                                                 #
# --------------------------------------------------------------------------- #


def test_baseline_present_produces_no_violations():
    judge_rows = [_row(count=1, percentage="100.00", sample_size=1, judge_id=JUDGE_X)]
    baseline_rows = [_row(count=1, percentage="100.00", sample_size=1)]
    assert validate_baseline(judge_rows, baseline_rows) == Counter()


def test_missing_baseline_is_flagged_per_distinct_charge():
    judge_rows = [
        _row(count=1, percentage="100.00", sample_size=1, judge_id=JUDGE_X),
        _row(
            count=1,
            percentage="100.00",
            sample_size=1,
            judge_id=JUDGE_X,
            category="cat_b",
        ),
        _row(
            count=1,
            percentage="100.00",
            sample_size=1,
            judge_id=JUDGE_X,
            charge_id=CHARGE_B,
        ),
    ]
    baseline_rows = [
        _row(count=1, percentage="100.00", sample_size=1, charge_id=CHARGE_B)
    ]
    violations = validate_baseline(judge_rows, baseline_rows)
    assert violations[CHECK_BASELINE_MISSING] == 1


def test_empty_judge_population_needs_no_baseline():
    assert validate_baseline([], []) == Counter()


# --------------------------------------------------------------------------- #
# Pure: privacy scan over rows.                                              #
# --------------------------------------------------------------------------- #


def test_clean_rows_pass_the_privacy_scan():
    rows = [_row(count=1, percentage="100.00", sample_size=1)]
    assert validate_privacy(rows, TERMS) == Counter()


def test_docket_shaped_value_in_any_column_fails_the_privacy_scan():
    poisoned = _row(
        count=1,
        percentage="100.00",
        sample_size=1,
        category="CP-51-CR-0001234-2025",
    )
    violations = validate_privacy([poisoned], TERMS)
    assert violations[CHECK_PRIVACY_VIOLATION] == 1


def test_scannable_row_stringifies_driver_types_for_the_scan():
    row = {
        "id": UUID("9d3e7b1a-2c4f-4a8b-9e0d-6f5a3c2b1d0e"),
        "percentage": Decimal("33.33"),
        "date_range_start": date(2025, 2, 1),
        "created_at": datetime(2025, 7, 1, tzinfo=UTC),
        "count": 3,
        "is_thin_data": False,
        "category_code": "cat_a",
        "judge_id": None,
    }
    scannable = scannable_row(row)
    assert scannable["id"] == "9d3e7b1a-2c4f-4a8b-9e0d-6f5a3c2b1d0e"
    assert scannable["percentage"] == "33.33"
    assert scannable["date_range_start"] == "2025-02-01"
    assert isinstance(scannable["created_at"], str)
    assert scannable["count"] == 3
    assert scannable["is_thin_data"] is False
    assert scannable["judge_id"] is None


# --------------------------------------------------------------------------- #
# DB integration (real Postgres TEST database; guards imported from 26.1).   #
# --------------------------------------------------------------------------- #


@pytest.fixture
def agg_conn():
    from pipeline.seam_check import running_in_ci

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
            "refusing to run the validation suite against a database whose name "
            f"does not contain 'test'; point {TEST_DB_URL_ENV_VAR} at a test "
            "database."
        )
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE analytics.aggregate_runs CASCADE")
            cur.execute("TRUNCATE fact.fact_build_runs CASCADE")
            cur.execute("TRUNCATE raw.source_documents CASCADE")
            cur.execute("TRUNCATE ref.normalized_charges CASCADE")
            cur.execute("TRUNCATE ref.normalized_judges CASCADE")
        conn.commit()
        yield conn
    finally:
        conn.rollback()
        conn.close()


def _seed_and_generate(conn: psycopg.Connection) -> str:
    """Seed a four-population synthetic corpus, generate, return the run id."""
    seeder = _Seeder(conn)
    build_run_id = seeder.build_run()
    judge_id = seeder.new_judge("placeholder-judge-x", "Placeholder Judge X")
    for _ in range(6):
        seeder.fact(
            build_run_id,
            category="cat_guilty_plea",
            disposition_date=date(2025, 2, 1),
            public_eligible=True,
            judge_id=judge_id,
            judge_specific_eligible=True,
        )
    for _ in range(4):
        seeder.fact(
            build_run_id,
            category="cat_dismissed",
            disposition_date=date(2025, 7, 1),
            public_eligible=True,
        )
    for _ in range(2):
        seeder.sentenced_outcome(
            build_run_id,
            outcome_category="cat_guilty_plea",
            disposition_date=date(2025, 3, 1),
            components=[
                ("cat_probation", date(2025, 3, 1), True, ()),
                ("cat_fine", date(2025, 3, 1), True, ()),
            ],
            judge_id=judge_id,
            judge_specific_eligible=True,
        )
    rc = generate_aggregates(
        conn,
        build_run_id=None,
        data_start_date=WINDOW_START,
        thin_min_sample=10,
        label="unit-test",
    )
    assert rc == 0
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id FROM analytics.aggregate_runs ORDER BY started_at DESC LIMIT 1"
        )
        return str(cur.fetchone()["id"])


def _run_row(conn: psycopg.Connection, run_id: str) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM analytics.aggregate_runs WHERE id = %s", (run_id,))
        return cur.fetchone()


def _validate(conn: psycopg.Connection, run_id: str | None = None) -> int:
    return validate_aggregates(
        conn, run_id=run_id, data_start_date=WINDOW_START, terms=TERMS
    )


def test_db_good_run_validates_to_completed(agg_conn, capsys):
    run_id = _seed_and_generate(agg_conn)

    rc = _validate(agg_conn)
    assert rc == 0

    run = _run_row(agg_conn, run_id)
    assert run["status"] == "completed"
    assert run["completed_at"] is not None
    assert run["published_at"] is None

    out = capsys.readouterr().out
    assert "verdict=validated" in out
    for table in (
        "charge_outcome_aggregates",
        "charge_sentencing_aggregates",
        "judge_outcome_aggregates",
        "judge_sentencing_aggregates",
    ):
        assert f"{table}: rows_checked=" in out


def test_db_count_mismatched_run_fails_and_publish_is_blocked(agg_conn, capsys):
    run_id = _seed_and_generate(agg_conn)
    with agg_conn.cursor() as cur:
        cur.execute(
            "UPDATE analytics.charge_outcome_aggregates SET count = count + 1 "
            "WHERE id = (SELECT id FROM analytics.charge_outcome_aggregates "
            "WHERE aggregate_run_id = %s LIMIT 1)",
            (run_id,),
        )
    agg_conn.commit()

    rc = _validate(agg_conn)
    assert rc == 1
    assert _run_row(agg_conn, run_id)["status"] == "failed"
    out = capsys.readouterr().out
    assert "verdict=failed" in out
    assert f"charge_outcome_aggregates.{CHECK_COUNT_SUM_MISMATCH}" in out

    # The publish block is structural: the aggregate_runs published_at CHECK
    # refuses published_at on a non-completed run at the schema level.
    with pytest.raises(errors.CheckViolation):
        with agg_conn.cursor() as cur:
            cur.execute(
                "UPDATE analytics.aggregate_runs SET published_at = now() "
                "WHERE id = %s",
                (run_id,),
            )
    agg_conn.rollback()


def test_db_privacy_violating_row_fails_the_run(agg_conn, capsys):
    run_id = _seed_and_generate(agg_conn)
    # Poison one generated row with a fabricated docket-shaped string (the
    # shared TS suite's synthetic fixture style — no real docket data).
    with agg_conn.cursor() as cur:
        cur.execute(
            "UPDATE analytics.charge_sentencing_aggregates "
            "SET taxonomy_version = 'CP-51-CR-0001234-2025' "
            "WHERE id = (SELECT id FROM analytics.charge_sentencing_aggregates "
            "WHERE aggregate_run_id = %s LIMIT 1)",
            (run_id,),
        )
    agg_conn.commit()

    rc = _validate(agg_conn)
    assert rc == 1
    assert _run_row(agg_conn, run_id)["status"] == "failed"
    out = capsys.readouterr().out
    assert f"charge_sentencing_aggregates.{CHECK_PRIVACY_VIOLATION}" in out
    # Hygiene: the offending value never reaches console output.
    assert "CP-51-CR" not in out


def test_db_missing_baseline_fails_the_run(agg_conn, capsys):
    run_id = _seed_and_generate(agg_conn)
    with agg_conn.cursor() as cur:
        cur.execute(
            "DELETE FROM analytics.charge_outcome_aggregates "
            "WHERE aggregate_run_id = %s",
            (run_id,),
        )
    agg_conn.commit()

    rc = _validate(agg_conn)
    assert rc == 1
    assert _run_row(agg_conn, run_id)["status"] == "failed"
    out = capsys.readouterr().out
    assert f"judge_outcome_aggregates.{CHECK_BASELINE_MISSING}" in out


def test_db_run_selection_and_terminal_failed_runs(agg_conn, capsys):
    # No generated run at all -> STOP.
    assert _validate(agg_conn) == 2

    run_id = _seed_and_generate(agg_conn)

    # A clean pass marks the run completed; re-validating the same completed
    # unpublished run via --run is idempotent.
    assert _validate(agg_conn) == 0
    assert _validate(agg_conn, run_id=run_id) == 0
    assert _run_row(agg_conn, run_id)["status"] == "completed"

    # Once completed, it is no longer the default target (no in_progress run).
    assert _validate(agg_conn) == 2

    # A failed run is terminal: --run refuses it.
    with agg_conn.cursor() as cur:
        cur.execute(
            "UPDATE analytics.aggregate_runs SET status = 'failed' WHERE id = %s",
            (run_id,),
        )
    agg_conn.commit()
    assert _validate(agg_conn, run_id=run_id) == 2
