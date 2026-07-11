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
        "--batch-size",
        "--batch-cooldown-seconds",
        "--ledger-dir",
        "--recheck-misses",
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
    assert args.batch_size == 40
    assert args.batch_cooldown_seconds == 240
    assert args.ledger_dir.name == "coverage"
    assert args.recheck_misses is False


def test_collect_batch_flags_parse():
    parser = cli.build_parser()
    args = parser.parse_args(
        ["collect", "--batch-size", "10", "--batch-cooldown-seconds", "120"]
    )
    assert args.batch_size == 10
    assert args.batch_cooldown_seconds == 120


def test_collect_ledger_flags_parse(tmp_path):
    parser = cli.build_parser()
    args = parser.parse_args(
        ["collect", "--ledger-dir", str(tmp_path / "cov"), "--recheck-misses"]
    )
    assert args.ledger_dir == tmp_path / "cov"
    assert args.recheck_misses is True


def test_collect_rejects_cooldown_below_floor(monkeypatch, capsys):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    # 59 < the 60s floor -> exit 2, loud log, no browser launched.
    assert cli.main(["collect", "--batch-cooldown-seconds", "59"]) == 2
    entry = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert entry["floor_seconds"] == 60
    assert "floor" in entry["message"]


def test_legal_conditions_are_not_flags_and_are_hardcoded():
    from pipeline.collector import engine

    parser = cli.build_parser()
    # No flag exists to change the counsel-locked ceilings.
    for bad in ("--hard-ceiling-minutes", "--post-block-cooldown-seconds"):
        try:
            parser.parse_args(["collect", bad, "10"])
        except SystemExit as exc:
            assert exc.code == 2
        else:  # pragma: no cover - would mean the flag leaked in
            raise AssertionError(f"{bad} should not be a recognized flag")
    assert engine.HARD_CEILING_MINUTES == 240
    assert engine.POST_BLOCK_COOLDOWN_SECONDS == 120


def test_collect_rejects_non_mc_court(capsys):
    try:
        cli.main(["collect", "--court", "CP"])
    except SystemExit as exc:
        assert exc.code == 2
    assert "invalid choice" in capsys.readouterr().err
