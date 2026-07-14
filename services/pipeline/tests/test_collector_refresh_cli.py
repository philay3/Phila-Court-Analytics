"""CLI tests for refresh mode (Task COL-4b) — plus the AC-11 regression pins
that the existing enumerate/search paths ignore the refresh machinery
entirely (no refresh flags consumed, no DATABASE_URL read, no DB layer
touched).

The existing enumerate-mode (test_collector_cli.py) and search-mode
(test_collector_search_cli.py) suites are deliberately untouched by COL-4b;
this file only ADDS pins.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pipeline import cli


def _no_ci(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)


def _poison_db_connect(monkeypatch):
    def poisoned(*_a, **_k):  # pragma: no cover - failure path
        raise AssertionError(
            "pipeline.db.connect must never be reached by this collect mode"
        )

    monkeypatch.setattr("pipeline.db.connect", poisoned)


# --- Parse + validation ------------------------------------------------------


def test_refresh_flags_parse():
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "collect",
            "--mode",
            "refresh",
            "--court",
            "both",
            "--refresh-dir",
            "/tmp/refresh-cycle",
            "--max-fetches",
            "3",
        ]
    )
    assert args.mode == "refresh"
    assert args.court == "both"
    assert args.refresh_dir == Path("/tmp/refresh-cycle")
    assert args.max_fetches == 3


def test_refresh_requires_refresh_dir(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["collect", "--mode", "refresh", "--court", "both"])
    assert exc.value.code == 2
    assert "requires --refresh-dir" in capsys.readouterr().err


def test_refresh_requires_explicit_court(capsys):
    # The parse-level default (MC) exists, but refresh refuses to use it: an
    # accidental default-MC run would silently half-refresh the corpus.
    with pytest.raises(SystemExit) as exc:
        cli.main(["collect", "--mode", "refresh", "--refresh-dir", "/tmp/x"])
    assert exc.value.code == 2
    assert "explicit --court" in capsys.readouterr().err


def test_refresh_accepts_court_equals_form(monkeypatch):
    _no_ci(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake/fake")
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("pipeline.collector.run.run_collect_refresh", fake_run)
    rc = cli.main(
        ["collect", "--mode", "refresh", "--court=CP", "--refresh-dir", "/tmp/x"]
    )
    assert rc == 0
    assert captured["court"] == "CP"


def test_refresh_requires_database_url(monkeypatch):
    _no_ci(monkeypatch)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    def must_not_run(**_kwargs):  # pragma: no cover - failure path
        raise AssertionError("run_collect_refresh must not be reached")

    monkeypatch.setattr("pipeline.collector.run.run_collect_refresh", must_not_run)
    rc = cli.main(
        ["collect", "--mode", "refresh", "--court", "both", "--refresh-dir", "/tmp/x"]
    )
    # Exit 2 with run_collect_refresh never reached (the poisoned fake would
    # have raised): the boundary guard refused before any work.
    assert rc == 2


def test_refresh_wiring_passes_flags_through(monkeypatch, tmp_path):
    _no_ci(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake/fake")
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("pipeline.collector.run.run_collect_refresh", fake_run)
    rc = cli.main(
        [
            "collect",
            "--mode",
            "refresh",
            "--court",
            "both",
            "--refresh-dir",
            str(tmp_path / "refresh"),
            "--max-minutes",
            "240",
            "--batch-size",
            "50",
            "--batch-cooldown-seconds",
            "180",
            "--max-fetches",
            "2",
        ]
    )
    assert rc == 0
    assert captured["database_url"] == "postgresql://fake/fake"
    assert captured["court"] == "both"
    assert captured["refresh_dir"] == tmp_path / "refresh"
    assert captured["max_minutes"] == 240
    assert captured["batch_size"] == 50
    assert captured["batch_cooldown_seconds"] == 180
    assert captured["max_fetches"] == 2
    assert captured["headless"] is False


def test_refresh_refused_in_ci_before_any_import(monkeypatch):
    monkeypatch.setenv("CI", "true")
    sys.modules.pop("playwright", None)

    def must_not_run(**_kwargs):  # pragma: no cover - failure path
        raise AssertionError("run_collect_refresh must not be reached in CI")

    monkeypatch.setattr("pipeline.collector.run.run_collect_refresh", must_not_run)
    rc = cli.main(
        ["collect", "--mode", "refresh", "--court", "both", "--refresh-dir", "/tmp/x"]
    )
    assert rc == 2
    assert "playwright" not in sys.modules


# --- AC-11: existing modes ignore the refresh machinery entirely -------------


def test_enumerate_mode_ignores_refresh_machinery(monkeypatch, tmp_path):
    _no_ci(monkeypatch)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    _poison_db_connect(monkeypatch)
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("pipeline.collector.run.run_collect", fake_run)
    rc = cli.main(["collect", "--intake-dir", str(tmp_path / "intake")])
    assert rc == 0
    # Routed with the pre-COL-4b signature: no refresh kwargs, no DB touch,
    # and no DATABASE_URL needed.
    assert "refresh_dir" not in captured
    assert "database_url" not in captured
    assert captured["court"] == "MC"
    assert captured["recheck_misses"] is False


def test_search_mode_ignores_refresh_machinery(monkeypatch, tmp_path):
    _no_ci(monkeypatch)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    _poison_db_connect(monkeypatch)
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return 0

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
            "--intake-dir",
            str(tmp_path / "intake"),
        ]
    )
    assert rc == 0
    assert "refresh_dir" not in captured
    assert "database_url" not in captured
    assert captured["court"] == "both"


def test_refresh_dir_defaults_to_none_outside_refresh_mode():
    parser = cli.build_parser()
    args = parser.parse_args(["collect"])
    assert args.refresh_dir is None
