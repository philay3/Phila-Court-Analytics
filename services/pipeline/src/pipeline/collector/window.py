"""Daily-window iteration and the search-mode window ledger (COL-2 PD-5, COL-3).

Discovery unit is ONE CALENDAR DAY (PD-1): no weekly mode, no adaptive
splitting. ``daily_windows`` enumerates every inclusive day in ``[start, end]``;
Sundays and holidays are searched like any other day (PD-9).

The window ledger is COURT-SCOPED (COL-3): an append-only JSONL per court at
``<ledger-dir>/window-ledger-philadelphia-<court>.jsonl`` (never in-repo),
mirroring the enumeration-mode miss ledger's court scoping belt-and-braces:
court in the filename AND a ``court`` field in every entry, validated on load,
so a renamed/misdirected ledger can never mark another court's windows
complete. One entry per searched window per fetched court records: ``date``,
``court``, ``run_id``, ``searched_at``, ``outcome``
(``complete``/``truncated``/``empty``/``blocked``), ``cp_harvested``,
``mc_harvested``, per-court ``fetched``/``already_present``/``fetch_failures``
counts, and ``skipped_rows``.

The loader mirrors COL-1b discipline (``engine.load_miss_ledger``): it dedupes,
warns loudly on malformed or misdirected lines, and yields the set of dates
that a prior run positively COMPLETED for this court — only ``complete`` and
``empty`` mark a window complete (PD-2). Completion is MONOTONIC across
duplicate entries for the same (date, court): any completing entry wins,
regardless of position in the file, and a later ``truncated``/``blocked``
entry (e.g. a recheck re-search of an already-complete window) never revokes
it. ``truncated`` and ``blocked`` windows that never completed are retried on
rerun; ``--recheck-windows`` ignores the ledger entirely.

``migrate_shared_ledger`` is the one-time COL-3 migration of the pre-COL-3
shared (court-blind) ledger into the court-scoped files; see its docstring.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger("pipeline.collector")

# Courts a window ledger can be scoped to (fetch courts; "both" is a run
# parameter, never a ledger scope).
WINDOW_LEDGER_COURTS = ("CP", "MC")

# The pre-COL-3 shared, court-blind ledger filename — exists only as the
# source of the one-time migration; nothing writes or loads it anymore.
SHARED_WINDOW_LEDGER_FILENAME = "window-ledger-philadelphia.jsonl"

# The retired shared ledger is archived under this suffix, never deleted.
MIGRATED_ARCHIVE_SUFFIX = ".migrated-col3"

# Ledger outcome vocabulary (PD-5).
OUTCOME_COMPLETE = "complete"
OUTCOME_TRUNCATED = "truncated"
OUTCOME_EMPTY = "empty"
OUTCOME_BLOCKED = "blocked"

# Only these positively-searched outcomes mark a window complete for rerun-skip.
COMPLETE_OUTCOMES = frozenset({OUTCOME_COMPLETE, OUTCOME_EMPTY})


class LedgerMigrationError(Exception):
    """A condition that must abort the shared-ledger migration untouched."""


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


def _require_court(court: str) -> None:
    if court not in WINDOW_LEDGER_COURTS:
        raise ValueError(
            f"window ledger court must be one of {WINDOW_LEDGER_COURTS}, got {court!r}"
        )


def window_ledger_path(ledger_dir: Path, court: str) -> Path:
    """Path to the court-scoped Philadelphia window ledger (COL-3)."""
    _require_court(court)
    return ledger_dir / f"window-ledger-philadelphia-{court}.jsonl"


def load_complete_windows(path: Path, court: str) -> set[str]:
    """Load the ISO dates a prior run positively completed FOR THIS COURT.

    Append-only JSONL, one searched window per line. Robust to a corrupt or
    misdirected ledger (mirrors ``engine.load_miss_ledger``): a line that does
    not parse, lacks a string ``date``/``outcome``/``court``, or whose
    ``court`` is not THIS ledger's court (a renamed/misdirected ledger must
    never suppress another court's windows) is skipped and counted; a nonzero
    skip count logs a WARNING (a silently shrinking skip set would re-search —
    and re-fetch — completed windows with no visible signal).

    Duplicate entries for one (date, court) are expected (a ``both`` run
    re-searches a window only one of its courts completed) and completion is
    monotonic: any ``complete``/``empty`` entry marks the date complete
    regardless of position; later ``truncated``/``blocked`` entries never
    revoke it, and duplicates never error or distort the returned set.
    """
    _require_court(court)
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
            entry_court = entry["court"]
        except (json.JSONDecodeError, KeyError, TypeError):
            skipped += 1
            continue
        if (
            not isinstance(day, str)
            or not isinstance(outcome, str)
            or not isinstance(entry_court, str)
        ):
            skipped += 1
            continue
        if entry_court != court:
            skipped += 1
            continue
        if outcome in COMPLETE_OUTCOMES:
            complete.add(day)
    if skipped:
        logger.warning(
            "window ledger: skipped unreadable or out-of-scope entries",
            extra={"skipped": skipped, "court": court, "ledger_path": str(path)},
        )
    return complete


def append_window_entry(path: Path, entry: dict) -> None:
    """Append one searched-window entry (append-only; creates parent)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(entry) + "\n")


# --- One-time COL-3 migration of the shared (court-blind) ledger ------------


def _attribute_run(run_id: str, entries: list[dict], runs_dir: Path) -> tuple[str, str]:
    """Attribute one run's shared-ledger entries to a court.

    Returns ``(court, basis)`` where court is ``"CP"``/``"MC"``/``"both"`` and
    basis is ``"report"`` (the run's run-report.json names its ``--court``) or
    ``"activity"`` (no report — the run died before writing one — so the court
    is inferred from which court has ALL of the run's fetch activity). A run
    with activity on both courts or on neither, and no report, is ambiguous —
    a literal STOP condition, adjudicated by aborting the whole migration.
    """
    report_path = runs_dir / run_id / "run-report.json"
    if report_path.exists():
        try:
            court = json.loads(report_path.read_text())["parameters"]["court"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise LedgerMigrationError(
                f"run report for {run_id} is unreadable: {type(exc).__name__}"
            ) from exc
        if court not in (*WINDOW_LEDGER_COURTS, "both"):
            raise LedgerMigrationError(
                f"run report for {run_id} names unknown court {court!r}"
            )
        return court, "report"

    def _activity(c: str) -> int:
        return sum(
            e.get(k, {}).get(c, 0)
            for e in entries
            for k in ("fetched", "already_present", "fetch_failures")
        )

    active = [c for c in WINDOW_LEDGER_COURTS if _activity(c) > 0]
    if len(active) != 1:
        raise LedgerMigrationError(
            f"run {run_id} has no run report and its fetch activity does not "
            f"single out one court (active: {active or 'none'}); attribution "
            "is ambiguous — migration aborted, nothing migrated"
        )
    return active[0], "activity"


def migrate_shared_ledger(ledger_dir: Path, runs_dir: Path) -> dict:
    """One-time COL-3 migration: split the shared ledger into court scopes.

    Every entry of ``window-ledger-philadelphia.jsonl`` is attributed to the
    court of the run that wrote it (per-run ``run-report.json`` first,
    fetch-activity inference for report-less runs — see ``_attribute_run``),
    rewritten with a ``court`` field into the court-scoped file(s), preserving
    file order; a ``both``-run entry goes to both courts. The shared file is
    then retired by rename to ``*.jsonl.migrated-col3`` (archived, never
    deleted).

    Idempotent by construction: a re-run finds no shared file and returns
    ``{"status": "nothing_to_migrate"}`` without touching anything. If the
    shared file AND a court-scoped target both exist (double migration, or a
    crash between write and rename), it refuses via
    :class:`LedgerMigrationError`; any unparseable or unattributable line
    likewise aborts the migration with the shared ledger untouched.

    Returns a summary dict with per-court entry/date counts and the per-run
    attribution basis (auditable evidence for the worklog).
    """
    shared = ledger_dir / SHARED_WINDOW_LEDGER_FILENAME
    if not shared.exists():
        return {"status": "nothing_to_migrate", "shared_path": str(shared)}
    targets = {c: window_ledger_path(ledger_dir, c) for c in WINDOW_LEDGER_COURTS}
    for target in targets.values():
        if target.exists():
            raise LedgerMigrationError(
                f"court-scoped ledger already exists alongside the shared "
                f"ledger ({target.name}); refusing to migrate twice"
            )

    entries: list[dict] = []
    for lineno, line in enumerate(shared.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if not (
                isinstance(entry, dict)
                and isinstance(entry.get("date"), str)
                and isinstance(entry.get("outcome"), str)
                and isinstance(entry.get("run_id"), str)
            ):
                raise TypeError("missing/invalid date, outcome, or run_id")
        except (json.JSONDecodeError, TypeError) as exc:
            raise LedgerMigrationError(
                f"shared ledger line {lineno} is unreadable "
                f"({type(exc).__name__}); migration aborted, nothing migrated"
            ) from exc
        entries.append(entry)

    by_run: dict[str, list[dict]] = {}
    for entry in entries:
        by_run.setdefault(entry["run_id"], []).append(entry)
    attribution = {
        run_id: _attribute_run(run_id, run_entries, runs_dir)
        for run_id, run_entries in by_run.items()
    }

    out_lines: dict[str, list[str]] = {c: [] for c in WINDOW_LEDGER_COURTS}
    counts: dict[str, int] = {c: 0 for c in WINDOW_LEDGER_COURTS}
    dates: dict[str, set[str]] = {c: set() for c in WINDOW_LEDGER_COURTS}
    for entry in entries:
        court, _basis = attribution[entry["run_id"]]
        scopes = WINDOW_LEDGER_COURTS if court == "both" else (court,)
        for scope in scopes:
            out_lines[scope].append(json.dumps({**entry, "court": scope}) + "\n")
            counts[scope] += 1
            dates[scope].add(entry["date"])

    for court in WINDOW_LEDGER_COURTS:
        if out_lines[court]:
            targets[court].write_text("".join(out_lines[court]))
    archived = shared.with_name(shared.name + MIGRATED_ARCHIVE_SUFFIX)
    shared.rename(archived)

    summary = {
        "status": "migrated",
        "shared_path": str(shared),
        "archived_to": str(archived),
        "total_entries": len(entries),
        "entries": counts,
        "dates": {c: len(dates[c]) for c in WINDOW_LEDGER_COURTS},
        "runs": [
            {
                "run_id": run_id,
                "court": attribution[run_id][0],
                "basis": attribution[run_id][1],
                "entries": len(by_run[run_id]),
            }
            for run_id in sorted(by_run)
        ],
    }
    logger.info(
        "window ledger migration complete",
        extra={k: v for k, v in summary.items() if k != "runs"},
    )
    return summary
