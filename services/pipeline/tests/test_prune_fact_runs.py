"""Tier-1 synthetic prune-fact-runs tests (Task COL-4a, AC-13).

Every row seeded here is FABRICATED — synthetic UUID-keyed rows over the same
fabricated docket-number/hash conventions as ``test_load.py``; no real docket
data. The suite exercises ``pipeline.prune_fact_runs`` against a REAL Postgres
with the repo migrations applied (CI provides one; locally, a dedicated test
database), reusing the 21.3 fail-closed guards: ``PIPELINE_TEST_DATABASE_URL``
only (never ``DATABASE_URL``), and the connected database name must contain
"test" before any truncation.

What AC-13 requires proven: selected runs are deleted WHOLE via the build-run
CASCADE (never partially), published aggregates and review items are
demonstrably unaffected, absent ids are idempotent success, and the dry-run /
--confirm split plus the completed-only rule hold. The CLI seam (CI refusal,
selection-form validation) is covered at the ``cli.main`` level without a DB.
"""

from __future__ import annotations

import os

import psycopg
import pytest

from pipeline import cli
from pipeline.prune_fact_runs import run_prune_fact_runs
from pipeline.seam_check import running_in_ci

TEST_DB_URL_ENV_VAR = "PIPELINE_TEST_DATABASE_URL"

_FAKE_HASH_1 = "e" + "a" * 63
_FAKE_HASH_2 = "f" + "a" * 63


@pytest.fixture
def prune_conn():
    url = os.environ.get(TEST_DB_URL_ENV_VAR)
    if not (url and url.strip()):
        if running_in_ci():
            pytest.fail(
                f"{TEST_DB_URL_ENV_VAR} must be set for the prune suite in CI; an "
                "unset value is a wiring regression, not a reason to skip."
            )
        pytest.skip(f"{TEST_DB_URL_ENV_VAR} not set; skipping prune DB suite (local).")

    conn = psycopg.connect(url)
    if "test" not in conn.info.dbname.lower():
        conn.close()
        pytest.fail(
            "refusing to run the prune suite against a database whose name does "
            "not contain 'test' — the suite TRUNCATEs tables and must never touch "
            f"a dev/prod database. Point {TEST_DB_URL_ENV_VAR} at a dedicated "
            "test database."
        )
    try:
        with conn.cursor() as cur:
            # raw CASCADE clears parsed/fact-facts/review/links; the run and
            # analytics bookkeeping tables are not in that FK chain.
            cur.execute("TRUNCATE raw.source_documents CASCADE")
            cur.execute("TRUNCATE fact.fact_build_runs CASCADE")
            cur.execute("TRUNCATE analytics.aggregate_runs CASCADE")
            cur.execute("TRUNCATE ref.normalized_charges CASCADE")
        conn.commit()
        yield conn
    finally:
        conn.rollback()
        conn.close()


def _seed_parsed_docket(conn: psycopg.Connection, file_hash: str) -> tuple[str, str]:
    """One synthetic raw doc + parsed docket + charge; returns (docket, charge)."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO raw.source_documents
                 (file_hash, original_filename, file_size_bytes, imported_at,
                  import_mode, status)
               VALUES (%(hash)s, 'synthetic.pdf', 1, now(), 'manual', 'imported')
               RETURNING id""",
            {"hash": file_hash},
        )
        doc_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO parsed.dockets
                 (source_document_id, docket_number, record_parser_version,
                  envelope_parser_version, parsed_at, county, defendant_hash,
                  envelope_status, review_needed)
               VALUES (%(doc)s, 'CP-51-CR-0000001-2020', 2, 5, now(),
                       'Philadelphia', %(dh)s, 'parsed', false)
               RETURNING id""",
            {"doc": doc_id, "dh": "0" * 64},
        )
        docket_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO parsed.charges (docket_id, sequence)
               VALUES (%(docket)s, 1) RETURNING id""",
            {"docket": docket_id},
        )
        charge_id = cur.fetchone()[0]
    return docket_id, charge_id


def _seed_fact_run(
    conn: psycopg.Connection, docket_id: str, charge_id: str, *, status: str
) -> str:
    """One fact build run with one outcome fact (when completed); returns id."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO fact.fact_build_runs
                 (status, parser_version, envelope_parser_version,
                  taxonomy_version, started_at)
               VALUES (%(status)s, 2, 5, 'test', now()) RETURNING id""",
            {"status": status},
        )
        run_id = cur.fetchone()[0]
        if status == "completed":
            cur.execute(
                """INSERT INTO fact.charge_outcomes
                     (build_run_id, parsed_charge_id, parsed_docket_id,
                      outcome_category_code, attribution_method,
                      charge_match_method, outcome_match_method, mvp_eligible,
                      public_eligible, judge_specific_eligible, review_needed,
                      taxonomy_version)
                   VALUES (%(run)s, %(charge)s, %(docket)s, 'conviction',
                           'direct', 'exact', 'exact', true, true, true, false,
                           'test')""",
                {"run": run_id, "charge": charge_id, "docket": docket_id},
            )
    conn.commit()
    return str(run_id)


def _seed_published_aggregate_and_review_item(
    conn: psycopg.Connection, docket_id: str
) -> None:
    """A published analytics row + an open review item that must survive prunes."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO ref.normalized_charges (slug, display_name)
               VALUES ('synthetic-charge', 'Synthetic Charge') RETURNING id"""
        )
        ref_charge = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO analytics.aggregate_runs
                 (status, started_at, completed_at, published_at,
                  taxonomy_version, data_range_start, data_range_end)
               VALUES ('completed', now(), now(), now(), 'test',
                       '2025-01-01', '2025-12-31') RETURNING id"""
        )
        agg_run = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO analytics.charge_outcome_aggregates
                 (aggregate_run_id, charge_id, category_code, count, percentage,
                  sample_size, date_range_start, date_range_end, is_thin_data,
                  taxonomy_version)
               VALUES (%(run)s, %(charge)s, 'conviction', 5, 50.00, 10,
                       '2025-01-01', '2025-12-31', false, 'test')""",
            {"run": agg_run, "charge": ref_charge},
        )
        cur.execute(
            """SELECT id FROM raw.source_documents LIMIT 1""",
        )
        doc_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO review.queue_items
                 (item_type, severity, source_document_id, reason_code, status,
                  dedup_key)
               VALUES ('unmapped_charge', 'low', %(doc)s, 'review_needed',
                       'open', 'colfoura-prune-item')""",
            {"doc": doc_id},
        )
        _ = docket_id  # anchoring is via the raw doc; parsed ptr not needed
    conn.commit()


def _count(conn: psycopg.Connection, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {table}")  # noqa: S608 - test-owned literals
        return cur.fetchone()[0]


def test_prune_deletes_selected_run_whole_and_spares_everything_else(
    prune_conn, capsys
):
    docket_id, charge_id = _seed_parsed_docket(prune_conn, _FAKE_HASH_1)
    run_a = _seed_fact_run(prune_conn, docket_id, charge_id, status="completed")
    run_b = _seed_fact_run(prune_conn, docket_id, charge_id, status="completed")
    _seed_published_aggregate_and_review_item(prune_conn, docket_id)

    rc = run_prune_fact_runs(
        prune_conn, run_ids=[run_a], all_completed=False, confirm=True
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "pruned=1" in out and "not_found=0" in out
    assert "outcomes_deleted=1" in out

    # Whole-run delete: run A and its facts are gone, run B is intact.
    with prune_conn.cursor() as cur:
        cur.execute("SELECT id::text, status FROM fact.fact_build_runs")
        remaining = cur.fetchall()
    assert [(run_b, "completed")] == [(r[0], r[1]) for r in remaining]
    assert _count(prune_conn, "fact.charge_outcomes") == 1  # run B's fact only

    # Demonstrably unaffected: parsed graph, published aggregates, review item.
    assert _count(prune_conn, "parsed.dockets") == 1
    assert _count(prune_conn, "analytics.aggregate_runs") == 1
    assert _count(prune_conn, "analytics.charge_outcome_aggregates") == 1
    assert _count(prune_conn, "review.queue_items") == 1


def test_dry_run_without_confirm_writes_nothing(prune_conn, capsys):
    docket_id, charge_id = _seed_parsed_docket(prune_conn, _FAKE_HASH_1)
    run_a = _seed_fact_run(prune_conn, docket_id, charge_id, status="completed")

    rc = run_prune_fact_runs(
        prune_conn, run_ids=[run_a], all_completed=False, confirm=False
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "would_prune=1" in out and "outcomes_deleted=0" in out
    assert "outcomes_selected=1" in out
    assert _count(prune_conn, "fact.fact_build_runs") == 1
    assert _count(prune_conn, "fact.charge_outcomes") == 1


def test_prune_is_idempotent_on_already_pruned_ids(prune_conn, capsys):
    docket_id, charge_id = _seed_parsed_docket(prune_conn, _FAKE_HASH_1)
    run_a = _seed_fact_run(prune_conn, docket_id, charge_id, status="completed")

    assert (
        run_prune_fact_runs(
            prune_conn, run_ids=[run_a], all_completed=False, confirm=True
        )
        == 0
    )
    capsys.readouterr()

    rc = run_prune_fact_runs(
        prune_conn, run_ids=[run_a], all_completed=False, confirm=True
    )
    out = capsys.readouterr().out
    assert rc == 0  # already-pruned = goal state reached, not an error
    assert "pruned=0" in out and "not_found=1" in out


def test_prune_refuses_non_completed_runs_whole_invocation(prune_conn, capsys):
    docket_id, charge_id = _seed_parsed_docket(prune_conn, _FAKE_HASH_1)
    run_done = _seed_fact_run(prune_conn, docket_id, charge_id, status="completed")
    run_live = _seed_fact_run(prune_conn, docket_id, charge_id, status="in_progress")

    rc = run_prune_fact_runs(
        prune_conn,
        run_ids=[run_done, run_live],
        all_completed=False,
        confirm=True,
    )
    assert rc == 1
    # Nothing deleted — not even the completed run named alongside the live one.
    assert _count(prune_conn, "fact.fact_build_runs") == 2
    assert _count(prune_conn, "fact.charge_outcomes") == 1


def test_all_completed_selects_only_completed_runs(prune_conn, capsys):
    docket_id, charge_id = _seed_parsed_docket(prune_conn, _FAKE_HASH_1)
    _seed_fact_run(prune_conn, docket_id, charge_id, status="completed")
    _seed_fact_run(prune_conn, docket_id, charge_id, status="completed")
    _seed_fact_run(prune_conn, docket_id, charge_id, status="in_progress")
    _seed_fact_run(prune_conn, docket_id, charge_id, status="failed")

    rc = run_prune_fact_runs(prune_conn, run_ids=[], all_completed=True, confirm=True)
    out = capsys.readouterr().out
    assert rc == 0
    assert "pruned=2" in out
    with prune_conn.cursor() as cur:
        cur.execute("SELECT status FROM fact.fact_build_runs ORDER BY status")
        assert [r[0] for r in cur.fetchall()] == ["failed", "in_progress"]
    assert _count(prune_conn, "fact.charge_outcomes") == 0


# --------------------------------------------------------------------------- #
# CLI seam (no DB): CI refusal and selection-form validation                   #
# --------------------------------------------------------------------------- #
def test_cli_refuses_in_ci(monkeypatch):
    monkeypatch.setenv("CI", "true")
    assert cli.main(["prune-fact-runs", "--all-completed", "--confirm"]) == 2


def test_cli_requires_exactly_one_selection_form(monkeypatch):
    for var in ("CI", "GITHUB_ACTIONS"):
        monkeypatch.delenv(var, raising=False)
    # Neither ids nor --all-completed.
    assert cli.main(["prune-fact-runs"]) == 2
    # Both at once.
    assert (
        cli.main(
            [
                "prune-fact-runs",
                "00000000-0000-0000-0000-000000000000",
                "--all-completed",
            ]
        )
        == 2
    )
