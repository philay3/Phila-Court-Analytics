"""CLI tests for search mode (COL-2): --mode / --court widening with the
mode-aware parser.error (F1), date-range requirement, and dispatch. The
existing enumerate-mode CLI tests (test_collector_cli.py) must remain green
unchanged (AC-9)."""

import json
from datetime import date

from pipeline import cli


def test_mode_defaults_to_enumerate():
    args = cli.build_parser().parse_args(["collect"])
    assert args.mode == "enumerate"


def test_court_choices_widened_to_cp_and_both():
    parser = cli.build_parser()
    for court in ("MC", "CP", "both"):
        args = parser.parse_args(["collect", "--court", court])
        assert args.court == court


def test_enumerate_rejects_cp_with_invalid_choice_message(capsys):
    # F1 / Decision A: enumerate mode still rejects non-MC as an invalid choice,
    # exit code 2 — the argparse-style contract the existing test relies on.
    try:
        cli.main(["collect", "--court", "CP"])
    except SystemExit as exc:
        assert exc.code == 2
    err = capsys.readouterr().err
    assert "invalid choice" in err


def test_enumerate_rejects_both(capsys):
    try:
        cli.main(["collect", "--court", "both"])
    except SystemExit as exc:
        assert exc.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_search_mode_accepts_cp_and_both(monkeypatch):
    # With a valid date range, search mode accepts CP/both without erroring.
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr("pipeline.collector.run.run_collect_search", fake_run)
    rc = cli.main(
        [
            "collect",
            "--mode",
            "search",
            "--court",
            "both",
            "--start-date",
            "2025-06-03",
            "--end-date",
            "2025-06-04",
        ]
    )
    assert rc == 0
    assert captured["court"] == "both"
    assert captured["start_date"] == date(2025, 6, 3)
    assert captured["end_date"] == date(2025, 6, 4)


def test_search_mode_requires_start_and_end_date(capsys):
    try:
        cli.main(["collect", "--mode", "search", "--court", "MC"])
    except SystemExit as exc:
        assert exc.code == 2
    assert "requires --start-date and --end-date" in capsys.readouterr().err


def test_search_mode_requires_end_date(capsys):
    try:
        cli.main(["collect", "--mode", "search", "--start-date", "2025-06-03"])
    except SystemExit as exc:
        assert exc.code == 2
    assert "requires --start-date and --end-date" in capsys.readouterr().err


def test_search_flags_parse():
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "collect",
            "--mode",
            "search",
            "--start-date",
            "2025-06-03",
            "--end-date",
            "2025-06-05",
            "--max-fetches",
            "10",
            "--recheck-windows",
        ]
    )
    assert args.mode == "search"
    assert args.start_date == date(2025, 6, 3)
    assert args.end_date == date(2025, 6, 5)
    assert args.max_fetches == 10
    assert args.recheck_windows is True


def test_search_help_lists_new_flags(capsys):
    try:
        cli.main(["collect", "--help"])
    except SystemExit:
        pass
    out = capsys.readouterr().out
    for flag in (
        "--mode",
        "--start-date",
        "--end-date",
        "--max-fetches",
        "--recheck-windows",
    ):
        assert flag in out


def test_search_mode_refuses_in_ci(monkeypatch, capsys):
    monkeypatch.setenv("CI", "true")
    rc = cli.main(
        [
            "collect",
            "--mode",
            "search",
            "--start-date",
            "2025-06-03",
            "--end-date",
            "2025-06-03",
        ]
    )
    assert rc == 2
    entry = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert entry["command"] == "collect"
    assert "CI" in entry["message"]


def test_search_dispatch_passes_all_args(monkeypatch):
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr("pipeline.collector.run.run_collect_search", fake_run)
    cli.main(
        [
            "collect",
            "--mode",
            "search",
            "--court",
            "MC",
            "--start-date",
            "2025-06-03",
            "--end-date",
            "2025-06-03",
            "--max-fetches",
            "10",
        ]
    )
    assert captured["court"] == "MC"
    assert captured["max_fetches"] == 10
    assert captured["recheck_windows"] is False
    assert "start_date" in captured and "end_date" in captured


# --- COL-3: migrate-window-ledger subcommand --------------------------------


def test_migrate_ledger_dispatch_passes_dirs(monkeypatch, tmp_path):
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr("pipeline.collector.run.run_migrate_window_ledger", fake_run)
    rc = cli.main(
        [
            "migrate-window-ledger",
            "--ledger-dir",
            str(tmp_path / "coverage"),
            "--runs-dir",
            str(tmp_path / "runs"),
        ]
    )
    assert rc == 0
    assert captured["ledger_dir"] == tmp_path / "coverage"
    assert captured["runs_dir"] == tmp_path / "runs"


def test_migrate_ledger_defaults_point_at_court_data(monkeypatch):
    parser = cli.build_parser()
    args = parser.parse_args(["migrate-window-ledger"])
    assert args.ledger_dir.name == "coverage"
    assert args.runs_dir.name == "collection-runs"
    assert args.ledger_dir.parent.name == "court-data"


def test_migrate_ledger_refuses_in_ci(monkeypatch, capsys):
    monkeypatch.setenv("CI", "true")
    rc = cli.main(["migrate-window-ledger"])
    assert rc == 2
    entry = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert entry["command"] == "migrate-window-ledger"
    assert "CI" in entry["message"]


def test_migrate_ledger_has_no_pacing_or_collection_flags(capsys):
    # AC-8: no flag introduced for COL-3 reaches any pacing or counsel-locked
    # parameter — the subcommand rejects them all outright.
    for flag, value in (
        ("--batch-size", "5"),
        ("--batch-cooldown-seconds", "1"),
        ("--max-minutes", "999"),
        ("--max-fetches", "1"),
        ("--court", "MC"),
        ("--recheck-windows", None),
    ):
        argv = ["migrate-window-ledger", flag] + ([value] if value else [])
        try:
            cli.main(argv)
            raise AssertionError(f"{flag} unexpectedly accepted")
        except SystemExit as exc:
            assert exc.code == 2
        assert "unrecognized arguments" in capsys.readouterr().err


def test_migrate_ledger_end_to_end(monkeypatch, tmp_path, capsys):
    # Full path CLI -> run -> window with real files: migrates, prints counts
    # and per-run attribution basis (auditable evidence), exits 0; rerun is a
    # no-op exit 0.
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    ledger_dir, runs_dir = tmp_path / "coverage", tmp_path / "runs"
    ledger_dir.mkdir()
    entry = {
        "date": "2025-01-01",
        "run_id": "run-a",
        "searched_at": "2026-07-12T00:00:00+00:00",
        "outcome": "complete",
        "cp_harvested": 0,
        "mc_harvested": 1,
        "fetched": {"CP": 0, "MC": 1},
        "already_present": {"CP": 0, "MC": 0},
        "fetch_failures": {"CP": 0, "MC": 0},
        "skipped_rows": 0,
    }
    (ledger_dir / "window-ledger-philadelphia.jsonl").write_text(
        json.dumps(entry) + "\n"
    )
    (runs_dir / "run-a").mkdir(parents=True)
    (runs_dir / "run-a" / "run-report.json").write_text(
        json.dumps({"parameters": {"court": "MC"}})
    )
    argv = [
        "migrate-window-ledger",
        "--ledger-dir",
        str(ledger_dir),
        "--runs-dir",
        str(runs_dir),
    ]

    rc = cli.main(argv)
    out = capsys.readouterr().out
    assert rc == 0
    assert "migrated 1 entries" in out
    assert "MC=1 entries (1 dates)" in out
    assert "run-a: court=MC entries=1 attribution=report" in out
    assert (ledger_dir / "window-ledger-philadelphia-MC.jsonl").exists()
    assert (ledger_dir / "window-ledger-philadelphia.jsonl.migrated-col3").exists()
    assert not (ledger_dir / "window-ledger-philadelphia.jsonl").exists()

    rc2 = cli.main(argv)
    assert rc2 == 0
    assert "nothing to migrate" in capsys.readouterr().out
