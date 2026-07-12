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
