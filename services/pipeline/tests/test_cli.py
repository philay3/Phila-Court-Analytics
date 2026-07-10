import json

import pytest

from pipeline import cli

SUBCOMMAND_NAMES = [name for name, _ in cli.SUBCOMMANDS]
# evaluate-extractors is implemented (Task 5.1) and covered by its own tests.
PLACEHOLDER_NAMES = [
    name for name in SUBCOMMAND_NAMES if name in cli.PLACEHOLDER_COMMANDS
]


@pytest.mark.parametrize("command", PLACEHOLDER_NAMES)
def test_subcommand_exits_zero_and_logs_json(command, capsys):
    assert cli.main([command]) == 0
    err = capsys.readouterr().err
    entry = json.loads(err.strip().splitlines()[-1])
    assert entry["message"] == "command not implemented"
    assert entry["command"] == command
    assert entry["level"] == "INFO"


def test_no_subcommand_exits_nonzero(capsys):
    assert cli.main([]) != 0
    assert "usage:" in capsys.readouterr().err


def test_top_level_help(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "usage: pipeline" in out
    for name in SUBCOMMAND_NAMES:
        assert name in out


@pytest.mark.parametrize("command", SUBCOMMAND_NAMES)
def test_subcommand_help(command, capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main([command, "--help"])
    assert excinfo.value.code == 0
    assert command in capsys.readouterr().out


def test_parse_refuses_in_ci(monkeypatch, capsys):
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("DEFENDANT_HASH_SALT", "test-salt")
    assert cli.main(["parse", "--artifacts-dir", "/nonexistent"]) == 2
    entry = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert entry["command"] == "parse"
    assert "CI" in entry["message"]


def test_parse_requires_salt(monkeypatch, capsys):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("DEFENDANT_HASH_SALT", raising=False)
    assert cli.main(["parse", "--artifacts-dir", "/nonexistent"]) == 2
    entry = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert entry["command"] == "parse"
    assert "DEFENDANT_HASH_SALT" in entry["message"]
