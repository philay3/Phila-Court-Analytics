"""Tier-1 tests for the aggregate publish step (Task 28.2).

DB integration tests against a real Postgres TEST database
(``PIPELINE_TEST_DATABASE_URL``), reusing the 26.1 suite's seeder and guards
and the 28.1 suite's scanner terms; each test seeds one synthetic ref graph
and generates/validates real lifecycle runs through the 26.1/28.1 code paths:

- transactional swap: publishing a validated run sets ``published_at`` on it
  and ``invalidated_at`` + ``invalidated_reason`` on the previously active
  published run in the same transaction; exactly one run matches the §6.3
  active-published predicate afterward; the superseded run's row and
  aggregate rows survive (invalidated, never deleted);
- idempotency: re-publishing the active published run is a no-op success
  (``published_at`` unchanged, nothing newly invalidated);
- refusals: an unvalidated (``in_progress``) run, a ``failed`` run, an
  invalidated run, an unknown ``--run`` id, and an empty table are all STOPs
  (exit 2) that write nothing;
- default resolution: with no ``--run``, the latest validated (completed,
  unpublished, uninvalidated) run is the target.

DB guards mirror 26.1: reads ONLY ``PIPELINE_TEST_DATABASE_URL`` (absent ->
local skip / CI hard failure) via the imported ``_classify``, and the
connected database name must contain "test" before any TRUNCATE.

Synthetic only: every run under test is generated from this suite's
placeholder corpus. No figure from any real run is pinned anywhere.
"""

from __future__ import annotations

import os
from datetime import date

import psycopg
import pytest
from psycopg.rows import dict_row
from test_aggregates_generate import TEST_DB_URL_ENV_VAR, _classify, _Seeder
from test_aggregates_validate import TERMS, WINDOW_START

from pipeline.aggregates.generate import generate_aggregates
from pipeline.aggregates.publish import invalidation_reason, publish_aggregates
from pipeline.aggregates.validate import validate_aggregates

MISSING_RUN_ID = "99999999-9999-9999-9999-999999999999"


# --------------------------------------------------------------------------- #
# Pure: the invalidation reason written onto a superseded run.                #
# --------------------------------------------------------------------------- #


def test_invalidation_reason_names_the_superseding_run():
    assert invalidation_reason(MISSING_RUN_ID) == (
        f"superseded by publish of run {MISSING_RUN_ID}"
    )


# --------------------------------------------------------------------------- #
# DB integration (real Postgres TEST database; guards imported from 26.1).   #
# --------------------------------------------------------------------------- #


@pytest.fixture
def pub_conn():
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
            "refusing to run the publish suite against a database whose name "
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


@pytest.fixture
def seeder(pub_conn):
    """One synthetic ref/parsed graph per test; each run gets its own facts."""
    return _Seeder(pub_conn)


def _generated_run(conn: psycopg.Connection, seeder: _Seeder) -> str:
    """Seed a fresh build run with eligible facts and generate; return run id.

    The seeder's ref graph is shared across a test's runs (its slugs are
    unique-constrained), so each generated aggregate run gets its own build
    run and fact rows against the same placeholder charge.
    """
    build_run_id = seeder.build_run()
    for _ in range(6):
        seeder.fact(
            build_run_id,
            category="cat_guilty_plea",
            disposition_date=date(2025, 2, 1),
            public_eligible=True,
        )
    for _ in range(4):
        seeder.fact(
            build_run_id,
            category="cat_dismissed",
            disposition_date=date(2025, 7, 1),
            public_eligible=True,
        )
    rc = generate_aggregates(
        conn,
        build_run_id=build_run_id,
        data_start_date=WINDOW_START,
        thin_min_sample=10,
        label="publish-unit-test",
    )
    assert rc == 0
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id FROM analytics.aggregate_runs ORDER BY started_at DESC LIMIT 1"
        )
        return str(cur.fetchone()["id"])


def _validated_run(conn: psycopg.Connection, seeder: _Seeder) -> str:
    """Seed, generate, and validate one run; return its id (status completed)."""
    run_id = _generated_run(conn, seeder)
    rc = validate_aggregates(
        conn, run_id=run_id, data_start_date=WINDOW_START, terms=TERMS
    )
    assert rc == 0
    return run_id


def _run_row(conn: psycopg.Connection, run_id: str) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM analytics.aggregate_runs WHERE id = %s", (run_id,))
        return cur.fetchone()


def _active_run_ids(conn: psycopg.Connection) -> list[str]:
    """Every run matching the §6.3 active-published predicate."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id FROM analytics.aggregate_runs "
            "WHERE published_at IS NOT NULL AND invalidated_at IS NULL"
        )
        return [str(row["id"]) for row in cur.fetchall()]


def _publish(conn: psycopg.Connection, run_id: str | None = None) -> int:
    return publish_aggregates(conn, run_id=run_id)


def test_db_first_publish_activates_run_with_no_prior(pub_conn, seeder, capsys):
    run_id = _validated_run(pub_conn, seeder)

    rc = _publish(pub_conn, run_id)
    assert rc == 0

    run = _run_row(pub_conn, run_id)
    assert run["published_at"] is not None
    assert run["invalidated_at"] is None
    assert _active_run_ids(pub_conn) == [run_id]

    out = capsys.readouterr().out
    assert f"publish-aggregates run={run_id[:16]} published" in out
    assert "no prior published run to invalidate" in out


def test_db_publish_swaps_active_run_transactionally(pub_conn, seeder, capsys):
    old_id = _validated_run(pub_conn, seeder)
    assert _publish(pub_conn, old_id) == 0

    new_id = _validated_run(pub_conn, seeder)
    assert new_id != old_id
    capsys.readouterr()  # discard setup output

    rc = _publish(pub_conn, new_id)
    assert rc == 0

    new_run = _run_row(pub_conn, new_id)
    old_run = _run_row(pub_conn, old_id)
    assert new_run["published_at"] is not None
    assert new_run["invalidated_at"] is None
    # Superseded, never deleted: the prior run survives as a rollback target,
    # invalidated in the same transaction that published the new run.
    assert old_run["published_at"] is not None
    assert old_run["invalidated_at"] is not None
    assert old_run["invalidated_reason"] == invalidation_reason(new_id)
    assert old_run["invalidated_at"] == new_run["published_at"]
    assert _active_run_ids(pub_conn) == [new_id]
    # The superseded run's aggregate rows are retained.
    with pub_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM analytics.charge_outcome_aggregates "
            "WHERE aggregate_run_id = %s",
            (old_id,),
        )
        assert cur.fetchone()[0] > 0

    out = capsys.readouterr().out
    assert f"publish-aggregates run={new_id[:16]} published" in out
    assert f"prior published run {old_id[:16]} invalidated" in out


def test_db_republish_of_active_run_is_a_noop(pub_conn, seeder, capsys):
    run_id = _validated_run(pub_conn, seeder)
    assert _publish(pub_conn, run_id) == 0
    published_at = _run_row(pub_conn, run_id)["published_at"]
    capsys.readouterr()

    rc = _publish(pub_conn, run_id)
    assert rc == 0
    assert _run_row(pub_conn, run_id)["published_at"] == published_at
    assert _active_run_ids(pub_conn) == [run_id]
    assert "already published; no-op" in capsys.readouterr().out

    # The default (no --run) re-run is equally a STOP-free non-event: with no
    # validated unpublished run left, it refuses without touching the swap.
    assert _publish(pub_conn) == 2
    assert _active_run_ids(pub_conn) == [run_id]


def test_db_publish_refuses_unvalidated_run(pub_conn, seeder):
    run_id = _generated_run(pub_conn, seeder)  # in_progress, never validated

    assert _publish(pub_conn, run_id) == 2
    run = _run_row(pub_conn, run_id)
    assert run["status"] == "in_progress"
    assert run["published_at"] is None
    assert _active_run_ids(pub_conn) == []

    # Default resolution finds no completed run either.
    assert _publish(pub_conn) == 2


def test_db_publish_refuses_failed_run(pub_conn, seeder):
    run_id = _generated_run(pub_conn, seeder)
    with pub_conn.cursor() as cur:
        cur.execute(
            "UPDATE analytics.aggregate_runs SET status = 'failed' WHERE id = %s",
            (run_id,),
        )
    pub_conn.commit()

    assert _publish(pub_conn, run_id) == 2
    assert _run_row(pub_conn, run_id)["published_at"] is None


def test_db_publish_refuses_invalidated_run(pub_conn, seeder):
    old_id = _validated_run(pub_conn, seeder)
    assert _publish(pub_conn, old_id) == 0
    new_id = _validated_run(pub_conn, seeder)
    assert _publish(pub_conn, new_id) == 0
    # old_id is now published + invalidated; republishing it would resurrect
    # superseded data.
    assert _publish(pub_conn, old_id) == 2
    assert _active_run_ids(pub_conn) == [new_id]


def test_db_bare_rerun_never_publishes_a_stale_leftover_run(pub_conn, seeder):
    # Incident regression (28.2 execution): run A validated but never
    # published, run B validated later and published. A bare (no --run)
    # re-run must NOT resurrect leftover A over newer published B — that is
    # a STOP, and forcing A requires an explicit --run.
    stale_id = _validated_run(pub_conn, seeder)
    newer_id = _validated_run(pub_conn, seeder)
    assert _publish(pub_conn, newer_id) == 0

    assert _publish(pub_conn) == 2
    assert _active_run_ids(pub_conn) == [newer_id]
    assert _run_row(pub_conn, stale_id)["published_at"] is None

    # The explicit escape hatch still works: --run publishes the older run.
    assert _publish(pub_conn, stale_id) == 0
    assert _active_run_ids(pub_conn) == [stale_id]


def test_db_publish_refuses_unknown_run_and_empty_table(pub_conn):
    assert _publish(pub_conn, MISSING_RUN_ID) == 2
    assert _publish(pub_conn) == 2
    assert _active_run_ids(pub_conn) == []


def test_db_default_targets_latest_validated_run(pub_conn, seeder, capsys):
    older_id = _validated_run(pub_conn, seeder)
    newer_id = _validated_run(pub_conn, seeder)
    capsys.readouterr()

    rc = _publish(pub_conn)
    assert rc == 0
    assert _active_run_ids(pub_conn) == [newer_id]
    assert _run_row(pub_conn, older_id)["published_at"] is None
    assert f"publish-aggregates run={newer_id[:16]} published" in (
        capsys.readouterr().out
    )
