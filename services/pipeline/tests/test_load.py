"""Tier-1 synthetic-envelope loader tests (Task 21.3).

Every envelope, import record, docket number, and hash in this file is
FABRICATED — no real docket data. Docket numbers use the UJS shape over
impossible sequences; ``defendant_hash``/``source_sha256`` are constant hex
fillers. The suite exercises ``pipeline.load`` against a REAL Postgres with the
repo migrations applied (CI provides one; locally, a dedicated test database).

Fail-closed on a non-test database (Fix 21.3-f1): the suite reads ONLY
``PIPELINE_TEST_DATABASE_URL`` (never ``DATABASE_URL``, so it can never truncate
the dev/prod DB) and, before truncating, asserts the connected database name
contains "test". An unset var SKIPS locally (visible skip count) but HARD-FAILS
in CI (Fix 2 semantics); a non-test database name is a hard failure regardless.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import psycopg
import pytest

from pipeline.load import STATUS_PARSE_FAILED, run_load
from pipeline.seam_check import running_in_ci

# The UJS docket-number shape, as a SUBSTRING probe for the hygiene assertion.
_DOCKET_RE = re.compile(r"(CP|MC)-\d{2}-[A-Z]{2}-\d{7}-\d{4}")

_FAKE_HASH = "a" * 64  # any 64-hex stand-in; per-test hashes vary the first char.
_FAKE_DEFENDANT_HASH = "0" * 64


# --------------------------------------------------------------------------- #
# Fabricated envelope / import-record builders                                #
# --------------------------------------------------------------------------- #
def make_sentence(**overrides: object) -> dict:
    sentence = {
        "sentence_type": "Confinement",
        "min_days": 90,
        "max_days": 180,
        "program": None,
        "sentence_date": "2021-03-01",
        "raw_text": "90 to 180 days confinement",
    }
    sentence.update(overrides)
    return sentence


def make_charge(sequence: int = 1, **overrides: object) -> dict:
    charge = {
        "sequence": sequence,
        "statute": "18 § 2701",
        "grade": "M1",
        "offense": "Simple Assault",
        "disposition_raw": "Guilty Plea",
        "disposition_date": "2021-03-01",
        "disposition_judge_raw": "SMITH, J",
        "event_name": "Final Disposition",
        "event_date": "2021-03-01",
        "sentences": [make_sentence()],
    }
    charge.update(overrides)
    return charge


def make_record(
    docket_number: str = "CP-51-CR-0000001-2020",
    *,
    court_type: str = "Common Pleas",
    parser_version: int = 2,
    charges: list | None = None,
    related_cases: list | None = None,
    **case_overrides: object,
) -> dict:
    case = {
        "county": "Philadelphia",
        "court_type": court_type,
        "case_status": "Closed",
        "filed_date": "2020-01-15",
        "otn": "T1234567",
        "assigned_judge_raw": "SMITH, J",
        "dc_number": None,
        "cross_court_dockets": None,
        "defendant_hash": _FAKE_DEFENDANT_HASH,
    }
    case.update(case_overrides)
    return {
        "docket_number": docket_number,
        "parser_version": parser_version,
        "parsed_at": "2026-07-11T12:00:00",
        "case": case,
        "charges": [make_charge()] if charges is None else charges,
        "related_cases": [] if related_cases is None else related_cases,
        "notes": [],
    }


def make_envelope(
    source_sha256: str,
    *,
    record: dict | None = None,
    status: str = "parsed",
    warnings: list | None = None,
    review_needed: bool = False,
    parser_version: int = 5,
    error: dict | None = None,
) -> dict:
    return {
        "source_sha256": source_sha256,
        "parser_version": parser_version,
        "extraction_artifact": {
            "artifact_id": source_sha256,
            "text_hash": "b" * 64,
            "provenance_path": "/nonexistent/artifact.json",
        },
        "record": make_record() if record is None else record,
        "warnings": [] if warnings is None else warnings,
        "review_needed": review_needed,
        "status": status,
        "created_at": "2026-07-11T12:00:00+00:00",
        "error": error,
    }


def make_import_record(source_sha256: str, **overrides: object) -> dict:
    record = {
        "id": source_sha256,
        "original_filename": "CP-51-CR-0000001-2020.pdf",
        "file_hash": source_sha256,
        "file_size_bytes": 12345,
        "imported_at": "2026-07-10T09:00:00+00:00",
        "mode": "manual",
        "status": "imported",
        "error_code": None,
        "docket_number_provenance": "CP-51-CR-0000001-2020",
        "court_type": "CP",
        "county": "51",
    }
    record.update(overrides)
    return record


def write_pair(
    env_dir: Path,
    imp_dir: Path,
    envelope: dict,
    *,
    import_record: dict | None = None,
    write_import: bool = True,
) -> None:
    """Write an envelope (and, unless suppressed, its 16.3 import record)."""
    sha = envelope["source_sha256"]
    (env_dir / f"{sha}.json").write_text(json.dumps(envelope))
    if write_import:
        record = import_record if import_record is not None else make_import_record(sha)
        (imp_dir / f"{sha}.json").write_text(json.dumps(record))


# --------------------------------------------------------------------------- #
# DB fixture — fail-closed on a non-test database (Fix 21.3-f1)               #
#                                                                             #
# The suite TRUNCATEs tables, so it must never touch the dev/prod database.   #
# Two independent guards:                                                     #
#   1. It reads ONLY ``PIPELINE_TEST_DATABASE_URL`` (never ``DATABASE_URL``); #
#      absent -> local skip / CI hard failure (the existing Fix-2 semantics). #
#   2. Before any truncation, the connected database name must contain        #
#      "test"; a mismatch is a hard failure regardless of which var supplied  #
#      the URL (belt and braces against env-var mixups).                      #
# --------------------------------------------------------------------------- #
TEST_DB_URL_ENV_VAR = "PIPELINE_TEST_DATABASE_URL"


def _classify_test_db_url(url: str | None, *, in_ci: bool) -> tuple[str, str]:
    """Pure guard-1 decision: ('run', url) | ('skip', reason) | ('fail', reason)."""
    if url and url.strip():
        return ("run", url)
    if in_ci:
        return (
            "fail",
            f"{TEST_DB_URL_ENV_VAR} must be set for the loader suite in CI; an "
            "unset value is a wiring regression, not a reason to skip.",
        )
    return (
        "skip",
        f"{TEST_DB_URL_ENV_VAR} not set; skipping loader DB suite (local).",
    )


def _is_test_dbname(dbname: str) -> bool:
    """Pure guard-2 predicate: the target database is positively a test DB."""
    return "test" in dbname.lower()


@pytest.fixture
def loader_conn():
    action, payload = _classify_test_db_url(
        os.environ.get(TEST_DB_URL_ENV_VAR), in_ci=running_in_ci()
    )
    if action == "fail":
        pytest.fail(payload)
    if action == "skip":
        pytest.skip(payload)

    conn = psycopg.connect(payload)
    dbname = conn.info.dbname
    if not _is_test_dbname(dbname):
        conn.close()
        pytest.fail(
            "refusing to run the loader suite against a database whose name does "
            "not contain 'test' — the suite TRUNCATEs tables and must never touch "
            f"a dev/prod database (guard 2). Point {TEST_DB_URL_ENV_VAR} at a "
            "dedicated test database."
        )
    try:
        with conn.cursor() as cur:
            # CASCADE clears the whole raw -> parsed tree between tests.
            cur.execute("TRUNCATE raw.source_documents CASCADE")
        conn.commit()
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[Path, Path]:
    env_dir = tmp_path / "envelopes"
    imp_dir = tmp_path / "imports"
    env_dir.mkdir()
    imp_dir.mkdir()
    return env_dir, imp_dir


# --------------------------------------------------------------------------- #
# Small query helpers                                                         #
# --------------------------------------------------------------------------- #
def _count(conn: psycopg.Connection, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {table}")
        return cur.fetchone()[0]


def _one(conn: psycopg.Connection, sql: str, params: dict | None = None):
    with conn.cursor() as cur:
        cur.execute(sql, params or {})
        return cur.fetchone()


# --------------------------------------------------------------------------- #
# AC2 + AC5: happy-path load + court_type mapping                             #
# --------------------------------------------------------------------------- #
def test_loads_full_parsed_graph(loader_conn, dirs, capsys):
    env_dir, imp_dir = dirs
    sha = "1" + _FAKE_HASH[1:]
    record = make_record(
        charges=[
            make_charge(1, sentences=[make_sentence(), make_sentence(min_days=1)]),
            make_charge(2, offense="Theft"),
        ],
        related_cases=[
            {
                "docket_number": "MC-51-CR-0009999-2020",
                "court": "MC",
                "association_reason": "Originating",
            }
        ],
        cross_court_dockets="CP-51-CR-0000002-2020",
    )
    write_pair(
        env_dir,
        imp_dir,
        make_envelope(
            sha,
            record=record,
            warnings=[{"code": "UNPARSEABLE_DURATION", "charge_sequence": 1}],
        ),
    )

    rc = run_load(env_dir, imp_dir, loader_conn)
    assert rc == 0

    out = capsys.readouterr().out
    assert "loaded=1" in out and "total=1" in out

    assert _count(loader_conn, "raw.source_documents") == 1
    assert _count(loader_conn, "parsed.dockets") == 1
    assert _count(loader_conn, "parsed.charges") == 2
    assert (
        _count(loader_conn, "parsed.sentences") == 3
    )  # 2 on charge 1 + 1 default on charge 2
    assert _count(loader_conn, "parsed.warnings") == 1
    assert _count(loader_conn, "parsed.related_cases") == 1

    row = _one(
        loader_conn,
        """SELECT court_type_recorded, court_type_derived, envelope_status,
                  review_needed, loaded_at, cross_court_dockets
           FROM parsed.dockets""",
    )
    assert row[0] == "Common Pleas"  # Q2: recorded = record value as-is
    assert row[1] == "CP"  # derived from docket-number prefix
    assert row[2] == "parsed"
    assert row[3] is False
    assert row[4] is not None  # loaded_at set by the loader
    assert row[5] == "CP-51-CR-0000002-2020"  # jsonb scalar round-trips to str

    orders = _one(
        loader_conn,
        """SELECT array_agg(component_order ORDER BY component_order)
           FROM parsed.sentences s
           JOIN parsed.charges c ON c.id = s.charge_id
           WHERE c.sequence = 1""",
    )
    assert orders[0] == [0, 1]  # component_order = list index


def test_court_type_derived_mc(loader_conn, dirs):
    env_dir, imp_dir = dirs
    sha = "2" + _FAKE_HASH[1:]
    record = make_record("MC-51-CR-0000001-2020", court_type="Municipal Court")
    write_pair(env_dir, imp_dir, make_envelope(sha, record=record))
    assert run_load(env_dir, imp_dir, loader_conn) == 0
    row = _one(
        loader_conn,
        "SELECT court_type_recorded, court_type_derived FROM parsed.dockets",
    )
    assert row == ("Municipal Court", "MC")


def test_court_type_derived_null_for_non_cp_mc_prefix(loader_conn, dirs):
    env_dir, imp_dir = dirs
    sha = "3" + _FAKE_HASH[1:]
    # Fabricated non-CP/MC prefix: derived must be NULL (recorded still as-is).
    record = make_record("XX-51-CR-0000001-2020", court_type="Common Pleas")
    write_pair(env_dir, imp_dir, make_envelope(sha, record=record))
    assert run_load(env_dir, imp_dir, loader_conn) == 0
    row = _one(
        loader_conn,
        "SELECT court_type_recorded, court_type_derived FROM parsed.dockets",
    )
    assert row == ("Common Pleas", None)


def test_min_assumed_absent_false_and_event_absent_null(loader_conn, dirs):
    env_dir, imp_dir = dirs
    sha = "4" + _FAKE_HASH[1:]
    charge = make_charge(1, sentences=[make_sentence()])
    del charge["event_name"]
    del charge["event_date"]
    charge["sentences"][0].pop("min_assumed", None)  # absent -> False
    record = make_record(charges=[charge])
    write_pair(env_dir, imp_dir, make_envelope(sha, record=record))
    assert run_load(env_dir, imp_dir, loader_conn) == 0
    charge_row = _one(loader_conn, "SELECT event_name, event_date FROM parsed.charges")
    assert charge_row == (None, None)
    assert _one(loader_conn, "SELECT min_assumed FROM parsed.sentences")[0] is False


# --------------------------------------------------------------------------- #
# AC3: idempotency (four arms) + per-docket isolation                        #
# --------------------------------------------------------------------------- #
def test_idempotency_skip_same_version_zero_changes(loader_conn, dirs, capsys):
    env_dir, imp_dir = dirs
    sha = "5" + _FAKE_HASH[1:]
    write_pair(env_dir, imp_dir, make_envelope(sha))
    assert run_load(env_dir, imp_dir, loader_conn) == 0
    capsys.readouterr()

    before = _one(
        loader_conn,
        """SELECT d.id, d.loaded_at, s.updated_at
           FROM parsed.dockets d JOIN raw.source_documents s
           ON s.id = d.source_document_id""",
    )
    assert run_load(env_dir, imp_dir, loader_conn) == 0
    out = capsys.readouterr().out
    assert "skipped_same_version=1" in out and "loaded=0" in out

    after = _one(
        loader_conn,
        """SELECT d.id, d.loaded_at, s.updated_at
           FROM parsed.dockets d JOIN raw.source_documents s
           ON s.id = d.source_document_id""",
    )
    assert before == after  # zero changed rows on identical re-run
    assert _count(loader_conn, "parsed.dockets") == 1


def test_idempotency_replace_newer_version(loader_conn, dirs, capsys):
    env_dir, imp_dir = dirs
    sha = "6" + _FAKE_HASH[1:]
    write_pair(env_dir, imp_dir, make_envelope(sha))
    assert run_load(env_dir, imp_dir, loader_conn) == 0
    old_id = _one(loader_conn, "SELECT id FROM parsed.dockets")[0]
    capsys.readouterr()

    newer = make_envelope(
        sha,
        record=make_record(
            parser_version=3, charges=[make_charge(1, offense="Robbery")]
        ),
    )
    write_pair(env_dir, imp_dir, newer)
    assert run_load(env_dir, imp_dir, loader_conn) == 0
    assert "replaced_newer_version=1" in capsys.readouterr().out

    row = _one(loader_conn, "SELECT id, record_parser_version FROM parsed.dockets")
    assert row[1] == 3
    assert row[0] != old_id  # docket row was deleted + reinserted
    assert _count(loader_conn, "parsed.dockets") == 1
    assert _one(loader_conn, "SELECT offense FROM parsed.charges")[0] == "Robbery"


def test_idempotency_refuse_older_version_zero_writes(loader_conn, dirs, capsys):
    env_dir, imp_dir = dirs
    sha = "7" + _FAKE_HASH[1:]
    write_pair(
        env_dir, imp_dir, make_envelope(sha, record=make_record(parser_version=2))
    )
    assert run_load(env_dir, imp_dir, loader_conn) == 0
    capsys.readouterr()

    older = make_envelope(
        sha,
        record=make_record(
            parser_version=1, charges=[make_charge(1, offense="Downgrade")]
        ),
    )
    write_pair(env_dir, imp_dir, older)
    assert run_load(env_dir, imp_dir, loader_conn) == 0
    assert "refused_older_version=1" in capsys.readouterr().out
    # Never downgraded: still the v2 content.
    assert _one(loader_conn, "SELECT record_parser_version FROM parsed.dockets")[0] == 2
    assert (
        _one(loader_conn, "SELECT offense FROM parsed.charges")[0] == "Simple Assault"
    )


def test_idempotency_equal_version_content_mismatch_rejected(loader_conn, dirs, capsys):
    env_dir, imp_dir = dirs
    sha = "8" + _FAKE_HASH[1:]
    write_pair(env_dir, imp_dir, make_envelope(sha))
    assert run_load(env_dir, imp_dir, loader_conn) == 0
    capsys.readouterr()

    # Same hash + same versions, DIFFERENT content -> reject, never overwrite.
    mutated = make_envelope(
        sha, record=make_record(charges=[make_charge(1, offense="Different")])
    )
    write_pair(env_dir, imp_dir, mutated)
    rc = run_load(env_dir, imp_dir, loader_conn)
    assert rc == 1  # fail-loud
    assert "failed_exception=1" in capsys.readouterr().out
    assert (
        _one(loader_conn, "SELECT offense FROM parsed.charges")[0] == "Simple Assault"
    )


def test_per_docket_exception_isolation(loader_conn, dirs, capsys):
    env_dir, imp_dir = dirs
    good = "9" + _FAKE_HASH[1:]
    bad = "a" + _FAKE_HASH[1:]
    write_pair(env_dir, imp_dir, make_envelope(good))
    # Missing case.defendant_hash -> KeyError mid-insert -> rolled back, isolated.
    broken_record = make_record()
    del broken_record["case"]["defendant_hash"]
    write_pair(env_dir, imp_dir, make_envelope(bad, record=broken_record))

    rc = run_load(env_dir, imp_dir, loader_conn)
    assert rc == 1
    out = capsys.readouterr().out
    assert "loaded=1" in out and "failed_exception=1" in out and "total=2" in out
    # The good docket committed; the bad one wrote nothing.
    assert _count(loader_conn, "parsed.dockets") == 1
    assert (
        _one(
            loader_conn,
            "SELECT count(*) FROM raw.source_documents WHERE file_hash = %(h)s",
            {"h": bad},
        )[0]
        == 0
    )


# --------------------------------------------------------------------------- #
# AC4 (Q1 ruling): failed envelope + missing import record                   #
# --------------------------------------------------------------------------- #
def test_failed_envelope_upserts_raw_only(loader_conn, dirs, capsys):
    env_dir, imp_dir = dirs
    sha = "b" + _FAKE_HASH[1:]
    envelope = make_envelope(
        sha,
        record=None,
        status="failed",
        error={"code": "UNSUPPORTED_FORMAT", "exception_class": "KeyError"},
    )
    write_pair(env_dir, imp_dir, envelope)

    rc = run_load(env_dir, imp_dir, loader_conn)
    assert rc == 0
    assert "failed_envelope_loaded=1" in capsys.readouterr().out

    row = _one(loader_conn, "SELECT status, error_code FROM raw.source_documents")
    assert row == (STATUS_PARSE_FAILED, "UNSUPPORTED_FORMAT")
    assert _count(loader_conn, "parsed.dockets") == 0  # no fabricated parsed rows


def test_missing_import_record_writes_nothing_and_continues(loader_conn, dirs, capsys):
    env_dir, imp_dir = dirs
    orphan = "c" + _FAKE_HASH[1:]
    good = "d" + _FAKE_HASH[1:]
    write_pair(
        env_dir, imp_dir, make_envelope(orphan), write_import=False
    )  # no 16.3 record
    write_pair(env_dir, imp_dir, make_envelope(good))

    rc = run_load(env_dir, imp_dir, loader_conn)
    assert rc == 1  # fail-loud on broken provenance
    out = capsys.readouterr().out
    assert "missing_import_record=1" in out and "loaded=1" in out and "total=2" in out
    assert _count(loader_conn, "raw.source_documents") == 1  # only the good one
    assert _count(loader_conn, "parsed.dockets") == 1


def test_unknown_envelope_version_is_per_docket_failure(loader_conn, dirs, capsys):
    env_dir, imp_dir = dirs
    bad = "e" + _FAKE_HASH[1:]
    good = "f" + _FAKE_HASH[1:]
    write_pair(env_dir, imp_dir, make_envelope(bad, parser_version=99))
    write_pair(env_dir, imp_dir, make_envelope(good))

    rc = run_load(env_dir, imp_dir, loader_conn)
    assert rc == 1
    out = capsys.readouterr().out
    assert "failed_exception=1" in out and "loaded=1" in out
    assert _count(loader_conn, "raw.source_documents") == 1


# --------------------------------------------------------------------------- #
# AC6: console/report hygiene                                                 #
# --------------------------------------------------------------------------- #
def test_console_output_has_no_docket_numbers(loader_conn, dirs, capsys, caplog):
    env_dir, imp_dir = dirs
    sha = "1" + "b" * 63
    record = make_record(
        "CP-51-CR-0000123-2020",
        related_cases=[
            {
                "docket_number": "MC-51-CR-0000456-2020",
                "court": "MC",
                "association_reason": "x",
            }
        ],
    )
    write_pair(env_dir, imp_dir, make_envelope(sha, record=record))

    with caplog.at_level("INFO"):
        run_load(env_dir, imp_dir, loader_conn)

    blob = capsys.readouterr().out + capsys.readouterr().err + caplog.text
    assert not _DOCKET_RE.search(blob), "docket-number-shaped string leaked into output"


# --------------------------------------------------------------------------- #
# Fix 21.3-f1: fail-closed guard arms (pure, no DB required)                  #
# --------------------------------------------------------------------------- #
def test_guard1_absent_url_skips_locally():
    action, _ = _classify_test_db_url("", in_ci=False)
    assert action == "skip"
    action_none, _ = _classify_test_db_url(None, in_ci=False)
    assert action_none == "skip"


def test_guard1_absent_url_hard_fails_in_ci():
    action, reason = _classify_test_db_url(None, in_ci=True)
    assert action == "fail"
    assert TEST_DB_URL_ENV_VAR in reason


def test_guard1_present_url_runs():
    action, payload = _classify_test_db_url(
        "postgresql://u:p@localhost:5432/pca_test", in_ci=True
    )
    assert action == "run"
    assert payload.endswith("/pca_test")


def test_guard2_rejects_non_test_dbname():
    # A dev/prod-shaped name is refused; only a name containing "test" passes.
    assert _is_test_dbname("pca") is False
    assert _is_test_dbname("pca_prod") is False
    assert _is_test_dbname("pca_test") is True
    assert _is_test_dbname("PCA_TEST") is True  # case-insensitive
    assert _is_test_dbname("pipeline_test_db") is True
