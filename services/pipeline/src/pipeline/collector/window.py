"""Daily-window iteration and the search-mode window ledger (Task COL-2, PD-5).

Discovery unit is ONE CALENDAR DAY (PD-1): no weekly mode, no adaptive
splitting. ``daily_windows`` enumerates every inclusive day in ``[start, end]``;
Sundays and holidays are searched like any other day (PD-9).

The window ledger is an append-only JSONL at
``<ledger-dir>/window-ledger-philadelphia.jsonl`` (never in-repo). One entry per
searched window records: ``date``, ``run_id``, ``searched_at``, ``outcome``
(``complete``/``truncated``/``empty``/``blocked``), ``cp_harvested``,
``mc_harvested``, per-court ``fetched``/``already_present``/``fetch_failures``
counts, and ``skipped_rows``.

The loader mirrors COL-1b discipline (``engine.load_miss_ledger``): it dedupes,
warns loudly on malformed lines, and yields the set of dates that a prior run
positively COMPLETED — only ``complete`` and ``empty`` mark a window complete
(PD-2). ``truncated`` and ``blocked`` windows are NOT complete and are retried
on rerun; ``--recheck-windows`` ignores the ledger entirely.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger("pipeline.collector")

WINDOW_LEDGER_FILENAME = "window-ledger-philadelphia.jsonl"

# Ledger outcome vocabulary (PD-5).
OUTCOME_COMPLETE = "complete"
OUTCOME_TRUNCATED = "truncated"
OUTCOME_EMPTY = "empty"
OUTCOME_BLOCKED = "blocked"

# Only these positively-searched outcomes mark a window complete for rerun-skip.
COMPLETE_OUTCOMES = frozenset({OUTCOME_COMPLETE, OUTCOME_EMPTY})


def daily_windows(start: date, end: date) -> list[date]:
    """Every inclusive calendar day in ``[start, end]`` (PD-1)."""
    if end < start:
        raise ValueError(
            f"end date {end.isoformat()} precedes start {start.isoformat()}"
        )
    out: list[date] = []
    day = start
    while day <= end:
        out.append(day)
        day += timedelta(days=1)
    return out


def window_ledger_path(ledger_dir: Path) -> Path:
    """Path to the Philadelphia window ledger under the ledger dir."""
    return ledger_dir / WINDOW_LEDGER_FILENAME


def load_complete_windows(path: Path) -> set[str]:
    """Load the ISO date strings that a prior run positively completed.

    Append-only JSONL, one searched window per line. Robust to a corrupt ledger
    (mirrors ``engine.load_miss_ledger``): a line that does not parse, lacks a
    string ``date``/``outcome``, is skipped and counted; a nonzero skip count
    logs a WARNING (a silently shrinking skip set would re-search — and re-fetch
    — completed windows with no visible signal). Only ``complete``/``empty``
    outcomes contribute; ``truncated``/``blocked`` are intentionally retryable.
    """
    if not path.exists():
        return set()
    complete: set[str] = set()
    skipped = 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            day = entry["date"]
            outcome = entry["outcome"]
        except (json.JSONDecodeError, KeyError, TypeError):
            skipped += 1
            continue
        if not isinstance(day, str) or not isinstance(outcome, str):
            skipped += 1
            continue
        if outcome in COMPLETE_OUTCOMES:
            complete.add(day)
    if skipped:
        logger.warning(
            "window ledger: skipped unreadable entries",
            extra={"skipped": skipped, "ledger_path": str(path)},
        )
    return complete


def append_window_entry(path: Path, entry: dict) -> None:
    """Append one searched-window entry (append-only; creates parent)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(entry) + "\n")
