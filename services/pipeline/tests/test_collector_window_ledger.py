"""Window ledger + daily-window tests, mirroring COL-1b discipline: dedupe,
malformed-line warning, complete-window skip, truncated/blocked retry — plus
COL-3: court-scoped files, the entry-level court guard (misdirected ledgers),
duplicate tolerance, and the one-time shared-ledger migration. The override
flag (--recheck-windows) is exercised at the engine level."""

import json
import logging
from datetime import date

import pytest

from pipeline.collector import window


def test_daily_windows_inclusive():
    days = window.daily_windows(date(2025, 6, 1), date(2025, 6, 3))
    assert [d.isoformat() for d in days] == ["2025-06-01", "2025-06-02", "2025-06-03"]


def test_daily_windows_single_day():
    days = window.daily_windows(date(2025, 6, 3), date(2025, 6, 3))
    assert days == [date(2025, 6, 3)]


def test_daily_windows_rejects_reversed_range():
    with pytest.raises(ValueError, match="precedes"):
        window.daily_windows(date(2025, 6, 3), date(2025, 6, 1))


def _write(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))


def _entry(day, outcome, court="MC", **extra):
    return {"date": day, "court": court, "outcome": outcome, **extra}


# --- COL-3: court-scoped path -----------------------------------------------


def test_ledger_path_is_court_scoped(tmp_path):
    assert window.window_ledger_path(tmp_path, "MC").name == (
        "window-ledger-philadelphia-MC.jsonl"
    )
    assert window.window_ledger_path(tmp_path, "CP").name == (
        "window-ledger-philadelphia-CP.jsonl"
    )


def test_ledger_path_rejects_unknown_court(tmp_path):
    with pytest.raises(ValueError, match="court"):
        window.window_ledger_path(tmp_path, "both")
    with pytest.raises(ValueError, match="court"):
        window.window_ledger_path(tmp_path, "philadelphia")


def test_loader_rejects_unknown_court(tmp_path):
    with pytest.raises(ValueError, match="court"):
        window.load_complete_windows(tmp_path / "x.jsonl", "both")


# --- loader: completion vocabulary + robustness ------------------------------


def test_load_only_complete_and_empty_mark_windows_complete(tmp_path):
    path = window.window_ledger_path(tmp_path, "MC")
    _write(
        path,
        [
            _entry("2025-06-01", "complete"),
            _entry("2025-06-02", "empty"),
            _entry("2025-06-03", "truncated"),  # retryable
            _entry("2025-06-04", "blocked"),  # retryable
        ],
    )
    assert window.load_complete_windows(path, "MC") == {"2025-06-01", "2025-06-02"}


def test_loader_dedupes_duplicate_lines(tmp_path):
    path = window.window_ledger_path(tmp_path, "MC")
    _write(
        path,
        [
            _entry("2025-06-03", "complete"),
            _entry("2025-06-03", "complete"),
            _entry("2025-06-03", "complete"),
        ],
    )
    assert window.load_complete_windows(path, "MC") == {"2025-06-03"}


def test_duplicate_completion_is_monotonic_any_completing_entry_wins(tmp_path):
    # COL-3 fix A: duplicates for one (date, court) are expected (a both run
    # re-searches a window only one court completed). Completion is monotonic
    # and ORDER-INDEPENDENT: any complete/empty entry wins; a later blocked/
    # truncated entry never revokes it — and no duplicate errors, warns, or
    # distorts the set.
    mc = window.window_ledger_path(tmp_path, "MC")
    # complete THEN blocked (a recheck re-search got blocked later).
    _write(mc, [_entry("2025-06-01", "complete"), _entry("2025-06-01", "blocked")])
    assert window.load_complete_windows(mc, "MC") == {"2025-06-01"}
    # blocked THEN complete (normal retry) — same result, order-independent.
    _write(mc, [_entry("2025-06-02", "blocked"), _entry("2025-06-02", "complete")])
    assert window.load_complete_windows(mc, "MC") == {"2025-06-02"}


def test_duplicates_do_not_warn(tmp_path, caplog):
    path = window.window_ledger_path(tmp_path, "MC")
    _write(path, [_entry("2025-06-01", "complete")] * 3)
    with caplog.at_level(logging.WARNING, logger="pipeline.collector"):
        window.load_complete_windows(path, "MC")
    assert not [r for r in caplog.records if r.levelno == logging.WARNING]


def test_loader_missing_file_is_empty(tmp_path):
    path = window.window_ledger_path(tmp_path, "MC")
    assert window.load_complete_windows(path, "MC") == set()


def test_loader_skips_malformed_line_loudly(tmp_path, caplog):
    path = window.window_ledger_path(tmp_path, "MC")
    path.parent.mkdir(parents=True, exist_ok=True)
    good = json.dumps(_entry("2025-06-03", "complete"))
    path.write_text(good + "\n" + "{not valid json\n")
    with caplog.at_level(logging.WARNING, logger="pipeline.collector"):
        known = window.load_complete_windows(path, "MC")
    assert known == {"2025-06-03"}
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].skipped == 1
    assert warnings[0].ledger_path == str(path)


def test_loader_skips_missing_keys_and_wrong_types(tmp_path, caplog):
    path = window.window_ledger_path(tmp_path, "MC")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(_entry("2025-06-03", "complete")),  # good
        json.dumps({"court": "MC", "outcome": "complete"}),  # no date
        json.dumps({"date": "2025-06-05", "court": "MC"}),  # no outcome
        json.dumps({"date": "2025-06-06", "outcome": "complete"}),  # no court
        json.dumps(_entry(20250607, "complete")),  # date not a str
        json.dumps({"date": "2025-06-08", "court": 51, "outcome": "complete"}),
    ]
    path.write_text("\n".join(lines) + "\n")
    with caplog.at_level(logging.WARNING, logger="pipeline.collector"):
        known = window.load_complete_windows(path, "MC")
    assert known == {"2025-06-03"}
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].skipped == 5


def test_loader_skips_misdirected_court_entries_loudly(tmp_path, caplog):
    # AC-2: the misdirected-ledger guard, matching the enumeration precedent —
    # a CP entry in (or a CP file renamed to) the MC ledger never marks MC
    # windows complete.
    path = window.window_ledger_path(tmp_path, "MC")
    _write(
        path,
        [
            _entry("2025-06-01", "complete", court="MC"),
            _entry("2025-06-02", "complete", court="CP"),  # misdirected
        ],
    )
    with caplog.at_level(logging.WARNING, logger="pipeline.collector"):
        known = window.load_complete_windows(path, "MC")
    assert known == {"2025-06-01"}
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].skipped == 1
    assert warnings[0].court == "MC"


def test_append_window_entry_is_append_only(tmp_path):
    path = window.window_ledger_path(tmp_path, "MC")
    window.append_window_entry(path, _entry("2025-06-01", "empty"))
    window.append_window_entry(path, _entry("2025-06-02", "complete"))
    lines = [json.loads(x) for x in path.read_text().splitlines()]
    assert [e["date"] for e in lines] == ["2025-06-01", "2025-06-02"]


# --- COL-3: one-time shared-ledger migration ---------------------------------


def _shared_entry(day, run_id, cp=0, mc=0):
    """A pre-COL-3 shared-ledger entry (no court field; PD-5 schema)."""
    return {
        "date": day,
        "run_id": run_id,
        "searched_at": "2026-07-12T00:00:00+00:00",
        "outcome": "complete",
        "cp_harvested": cp,
        "mc_harvested": mc,
        "fetched": {"CP": cp, "MC": mc},
        "already_present": {"CP": 0, "MC": 0},
        "fetch_failures": {"CP": 0, "MC": 0},
        "skipped_rows": 0,
    }


def _write_shared(ledger_dir, entries):
    shared = ledger_dir / window.SHARED_WINDOW_LEDGER_FILENAME
    _write(shared, entries)
    return shared


def _write_run_report(runs_dir, run_id, court):
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run-report.json").write_text(
        json.dumps({"run_id": run_id, "parameters": {"court": court}})
    )


def test_migration_attributes_by_run_report(tmp_path):
    ledger_dir, runs_dir = tmp_path / "coverage", tmp_path / "runs"
    _write_shared(
        ledger_dir,
        [
            _shared_entry("2025-01-01", "run-a", mc=3),
            _shared_entry("2025-01-02", "run-b", cp=2),
            _shared_entry("2025-01-01", "run-b", cp=1),
        ],
    )
    _write_run_report(runs_dir, "run-a", "MC")
    _write_run_report(runs_dir, "run-b", "CP")

    summary = window.migrate_shared_ledger(ledger_dir, runs_dir)

    assert summary["status"] == "migrated"
    assert summary["total_entries"] == 3
    assert summary["entries"] == {"CP": 2, "MC": 1}
    assert summary["dates"] == {"CP": 2, "MC": 1}
    assert summary["runs"] == [
        {"run_id": "run-a", "court": "MC", "basis": "report", "entries": 1},
        {"run_id": "run-b", "court": "CP", "basis": "report", "entries": 2},
    ]
    mc = window.load_complete_windows(window.window_ledger_path(ledger_dir, "MC"), "MC")
    cp = window.load_complete_windows(window.window_ledger_path(ledger_dir, "CP"), "CP")
    assert mc == {"2025-01-01"}
    assert cp == {"2025-01-01", "2025-01-02"}
    # Original fields preserved; court field added.
    first_cp = json.loads(
        window.window_ledger_path(ledger_dir, "CP").read_text().splitlines()[0]
    )
    assert first_cp["court"] == "CP"
    assert first_cp["run_id"] == "run-b"
    assert first_cp["fetched"] == {"CP": 2, "MC": 0}


def test_migration_archives_shared_file_never_deletes(tmp_path):
    ledger_dir, runs_dir = tmp_path / "coverage", tmp_path / "runs"
    shared = _write_shared(ledger_dir, [_shared_entry("2025-01-01", "run-a", mc=1)])
    _write_run_report(runs_dir, "run-a", "MC")
    original_text = shared.read_text()

    summary = window.migrate_shared_ledger(ledger_dir, runs_dir)

    assert not shared.exists()
    archived = ledger_dir / (
        window.SHARED_WINDOW_LEDGER_FILENAME + window.MIGRATED_ARCHIVE_SUFFIX
    )
    assert summary["archived_to"] == str(archived)
    assert archived.read_text() == original_text  # archived byte-for-byte


def test_migration_infers_court_from_activity_when_report_missing(tmp_path):
    # A run that died before writing run-report.json is attributed by which
    # court has ALL of its fetch activity.
    ledger_dir, runs_dir = tmp_path / "coverage", tmp_path / "runs"
    runs_dir.mkdir(parents=True)
    _write_shared(
        ledger_dir,
        [
            _shared_entry("2025-01-01", "run-x", mc=4),
            _shared_entry("2025-01-02", "run-x", mc=0),  # zero-activity entry
        ],
    )
    summary = window.migrate_shared_ledger(ledger_dir, runs_dir)
    assert summary["runs"] == [
        {"run_id": "run-x", "court": "MC", "basis": "activity", "entries": 2},
    ]
    # The zero-activity entry inherits its run's attribution.
    mc = window.load_complete_windows(window.window_ledger_path(ledger_dir, "MC"), "MC")
    assert mc == {"2025-01-01", "2025-01-02"}
    assert not window.window_ledger_path(ledger_dir, "CP").exists()


def test_migration_both_run_entries_land_in_both_ledgers(tmp_path):
    ledger_dir, runs_dir = tmp_path / "coverage", tmp_path / "runs"
    _write_shared(ledger_dir, [_shared_entry("2025-01-01", "run-a", cp=1, mc=1)])
    _write_run_report(runs_dir, "run-a", "both")
    summary = window.migrate_shared_ledger(ledger_dir, runs_dir)
    assert summary["entries"] == {"CP": 1, "MC": 1}
    for court in ("CP", "MC"):
        entries = [
            json.loads(x)
            for x in window.window_ledger_path(ledger_dir, court)
            .read_text()
            .splitlines()
        ]
        assert [(e["date"], e["court"]) for e in entries] == [("2025-01-01", court)]


def test_migration_ambiguous_activity_aborts_untouched(tmp_path):
    # STOP condition: no report and activity on both courts (or neither run
    # entry shows any) — refuse, migrating nothing.
    ledger_dir, runs_dir = tmp_path / "coverage", tmp_path / "runs"
    runs_dir.mkdir(parents=True)
    shared = _write_shared(
        ledger_dir, [_shared_entry("2025-01-01", "run-x", cp=1, mc=1)]
    )
    with pytest.raises(window.LedgerMigrationError, match="ambiguous"):
        window.migrate_shared_ledger(ledger_dir, runs_dir)
    assert shared.exists()  # untouched
    assert not window.window_ledger_path(ledger_dir, "MC").exists()
    assert not window.window_ledger_path(ledger_dir, "CP").exists()


def test_migration_zero_activity_run_is_ambiguous(tmp_path):
    ledger_dir, runs_dir = tmp_path / "coverage", tmp_path / "runs"
    runs_dir.mkdir(parents=True)
    _write_shared(ledger_dir, [_shared_entry("2025-01-01", "run-x")])
    with pytest.raises(window.LedgerMigrationError, match="ambiguous"):
        window.migrate_shared_ledger(ledger_dir, runs_dir)


def test_migration_unreadable_line_aborts_untouched(tmp_path):
    ledger_dir, runs_dir = tmp_path / "coverage", tmp_path / "runs"
    runs_dir.mkdir(parents=True)
    shared = _write_shared(ledger_dir, [_shared_entry("2025-01-01", "run-a", mc=1)])
    with shared.open("a") as handle:
        handle.write("{broken\n")
    with pytest.raises(window.LedgerMigrationError, match="line 2"):
        window.migrate_shared_ledger(ledger_dir, runs_dir)
    assert shared.exists()
    assert not window.window_ledger_path(ledger_dir, "MC").exists()


def test_migration_unreadable_run_report_aborts(tmp_path):
    ledger_dir, runs_dir = tmp_path / "coverage", tmp_path / "runs"
    _write_shared(ledger_dir, [_shared_entry("2025-01-01", "run-a", mc=1)])
    run_dir = runs_dir / "run-a"
    run_dir.mkdir(parents=True)
    (run_dir / "run-report.json").write_text("{broken")
    with pytest.raises(window.LedgerMigrationError, match="unreadable"):
        window.migrate_shared_ledger(ledger_dir, runs_dir)


def test_migration_unknown_report_court_aborts(tmp_path):
    ledger_dir, runs_dir = tmp_path / "coverage", tmp_path / "runs"
    _write_shared(ledger_dir, [_shared_entry("2025-01-01", "run-a", mc=1)])
    _write_run_report(runs_dir, "run-a", "philadelphia")
    with pytest.raises(window.LedgerMigrationError, match="unknown court"):
        window.migrate_shared_ledger(ledger_dir, runs_dir)


def test_migration_refuses_when_target_already_exists(tmp_path):
    ledger_dir, runs_dir = tmp_path / "coverage", tmp_path / "runs"
    _write_shared(ledger_dir, [_shared_entry("2025-01-01", "run-a", mc=1)])
    _write_run_report(runs_dir, "run-a", "MC")
    _write(window.window_ledger_path(ledger_dir, "MC"), [_entry("2025-06-01", "empty")])
    with pytest.raises(window.LedgerMigrationError, match="refusing to migrate twice"):
        window.migrate_shared_ledger(ledger_dir, runs_dir)


def test_migration_is_idempotent_rerun_migrates_nothing_errors_on_nothing(tmp_path):
    # AC-10: re-running migrates nothing and errors on nothing.
    ledger_dir, runs_dir = tmp_path / "coverage", tmp_path / "runs"
    _write_shared(ledger_dir, [_shared_entry("2025-01-01", "run-a", mc=1)])
    _write_run_report(runs_dir, "run-a", "MC")

    first = window.migrate_shared_ledger(ledger_dir, runs_dir)
    assert first["status"] == "migrated"
    mc_after_first = window.window_ledger_path(ledger_dir, "MC").read_text()

    second = window.migrate_shared_ledger(ledger_dir, runs_dir)
    assert second["status"] == "nothing_to_migrate"
    # Nothing changed on the second run.
    assert window.window_ledger_path(ledger_dir, "MC").read_text() == mc_after_first


def test_migration_nothing_to_migrate_when_no_shared_file(tmp_path):
    summary = window.migrate_shared_ledger(tmp_path / "coverage", tmp_path / "runs")
    assert summary["status"] == "nothing_to_migrate"
