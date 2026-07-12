"""Window ledger + daily-window tests (AC-5), mirroring COL-1b discipline:
dedupe, malformed-line warning, complete-window skip, truncated/blocked retry.
The override flag (--recheck-windows) is exercised at the engine level."""

import json
import logging
from datetime import date

from pipeline.collector import window


def test_daily_windows_inclusive():
    days = window.daily_windows(date(2025, 6, 1), date(2025, 6, 3))
    assert [d.isoformat() for d in days] == ["2025-06-01", "2025-06-02", "2025-06-03"]


def test_daily_windows_single_day():
    days = window.daily_windows(date(2025, 6, 3), date(2025, 6, 3))
    assert days == [date(2025, 6, 3)]


def test_daily_windows_rejects_reversed_range():
    import pytest

    with pytest.raises(ValueError, match="precedes"):
        window.daily_windows(date(2025, 6, 3), date(2025, 6, 1))


def _write(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))


def test_load_only_complete_and_empty_mark_windows_complete(tmp_path):
    path = window.window_ledger_path(tmp_path)
    _write(
        path,
        [
            {"date": "2025-06-01", "outcome": "complete"},
            {"date": "2025-06-02", "outcome": "empty"},
            {"date": "2025-06-03", "outcome": "truncated"},  # retryable
            {"date": "2025-06-04", "outcome": "blocked"},  # retryable
        ],
    )
    assert window.load_complete_windows(path) == {"2025-06-01", "2025-06-02"}


def test_loader_dedupes_duplicate_lines(tmp_path):
    path = window.window_ledger_path(tmp_path)
    _write(
        path,
        [
            {"date": "2025-06-03", "outcome": "complete"},
            {"date": "2025-06-03", "outcome": "complete"},
            {"date": "2025-06-03", "outcome": "complete"},
        ],
    )
    assert window.load_complete_windows(path) == {"2025-06-03"}


def test_loader_missing_file_is_empty(tmp_path):
    assert window.load_complete_windows(window.window_ledger_path(tmp_path)) == set()


def test_loader_skips_malformed_line_loudly(tmp_path, caplog):
    path = window.window_ledger_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    good = json.dumps({"date": "2025-06-03", "outcome": "complete"})
    path.write_text(good + "\n" + "{not valid json\n")
    with caplog.at_level(logging.WARNING, logger="pipeline.collector"):
        known = window.load_complete_windows(path)
    assert known == {"2025-06-03"}
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].skipped == 1
    assert warnings[0].ledger_path == str(path)


def test_loader_skips_missing_keys_and_wrong_types(tmp_path, caplog):
    path = window.window_ledger_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"date": "2025-06-03", "outcome": "complete"}),  # good
        json.dumps({"outcome": "complete"}),  # no date
        json.dumps({"date": "2025-06-05"}),  # no outcome
        json.dumps({"date": 20250606, "outcome": "complete"}),  # date not a str
    ]
    path.write_text("\n".join(lines) + "\n")
    with caplog.at_level(logging.WARNING, logger="pipeline.collector"):
        known = window.load_complete_windows(path)
    assert known == {"2025-06-03"}
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].skipped == 3


def test_append_window_entry_is_append_only(tmp_path):
    path = window.window_ledger_path(tmp_path)
    window.append_window_entry(path, {"date": "2025-06-01", "outcome": "empty"})
    window.append_window_entry(path, {"date": "2025-06-02", "outcome": "complete"})
    lines = [json.loads(x) for x in path.read_text().splitlines()]
    assert [e["date"] for e in lines] == ["2025-06-01", "2025-06-02"]
