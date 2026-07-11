import json
import sys

from pipeline import cli


def test_collect_is_a_registered_subcommand():
    names = [name for name, _ in cli.SUBCOMMANDS]
    assert "collect" in names
    assert "collect" in cli.IMPLEMENTED_COMMANDS
    assert "collect" not in cli.PLACEHOLDER_COMMANDS


def test_collect_refuses_in_ci(monkeypatch, capsys):
    monkeypatch.setenv("CI", "true")
    assert cli.main(["collect"]) == 2
    entry = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert entry["command"] == "collect"
    assert "CI" in entry["message"]


def test_collect_ci_guard_does_not_import_playwright(monkeypatch):
    # The CI guard returns before the lazy transport import, so a CI run never
    # needs the optional collector group.
    monkeypatch.setenv("CI", "true")
    sys.modules.pop("playwright", None)
    cli.main(["collect"])
    assert "playwright" not in sys.modules


def test_collect_help_lists_flags(capsys):
    try:
        cli.main(["collect", "--help"])
    except SystemExit:
        pass
    out = capsys.readouterr().out
    for flag in (
        "--court",
        "--year",
        "--start-seq",
        "--count",
        "--max-minutes",
        "--intake-dir",
        "--report-dir",
        "--headless",
    ):
        assert flag in out


def test_collect_defaults_parse():
    parser = cli.build_parser()
    args = parser.parse_args(["collect"])
    assert args.command == "collect"
    assert args.court == "MC"
    assert args.year == 2025
    assert args.start_seq == 1
    assert args.count == 600
    assert args.max_minutes == 60
    assert args.headless is False  # headful by default (FIX 3)


def test_collect_rejects_non_mc_court(capsys):
    try:
        cli.main(["collect", "--court", "CP"])
    except SystemExit as exc:
        assert exc.code == 2
    assert "invalid choice" in capsys.readouterr().err
