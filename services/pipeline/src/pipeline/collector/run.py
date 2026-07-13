"""Run-boundary orchestration for ``pipeline collect`` (Task COL-1).

Resolves and validates output directories, wires the real injected
dependencies (wall clock, monotonic clock, ``time.sleep``, the jittered
per-request delay, and a ``SIGINT`` handler that requests a graceful abort),
builds the Playwright transport, and calls the pure :func:`engine.run` loop.

Graceful Ctrl-C: the ``SIGINT`` handler only *sets* an abort flag; the engine
checks it at the top of each iteration, so the in-flight request finishes, the
report is written, and the process exits (stop reason ``operator_abort``).
"""

from __future__ import annotations

import logging
import random
import signal
import time
from datetime import UTC, date, datetime
from pathlib import Path
from threading import Event

from pipeline.collector import engine, search_engine
from pipeline.collector.engine import (
    PER_REQUEST_DELAY_MAX_SECONDS,
    PER_REQUEST_DELAY_MIN_SECONDS,
    CollectParams,
)
from pipeline.collector.search_engine import SearchParams
from pipeline.collector.window import LedgerMigrationError, migrate_shared_ledger
from pipeline.paths import inside_git_worktree

logger = logging.getLogger("pipeline.collector")


def _jitter() -> float:
    """A fresh jittered per-request delay in the enforced 2.0–5.0s band."""
    return random.uniform(PER_REQUEST_DELAY_MIN_SECONDS, PER_REQUEST_DELAY_MAX_SECONDS)


def run_collect(
    *,
    court: str,
    year: int,
    start_seq: int,
    count: int,
    max_minutes: int,
    intake_dir: Path,
    report_dir: Path,
    ledger_dir: Path,
    headless: bool,
    batch_size: int,
    batch_cooldown_seconds: int,
    recheck_misses: bool,
) -> int:
    """Validate inputs, run one collection, print a summary. Returns exit code.

    This is the CLI-facing entrypoint (the CI-environment guard runs one level
    up in ``cli.py``, mirroring parse/seam-check). Tests exercise the pure
    loop via :func:`engine.run` directly and never reach Playwright.
    """
    if max_minutes < 1 or start_seq < 1 or count < 1 or batch_size < 1:
        logger.error(
            "invalid parameters",
            extra={
                "max_minutes": max_minutes,
                "start_seq": start_seq,
                "count": count,
                "batch_size": batch_size,
            },
        )
        return 2

    # Enforced floor on the operational batch cooldown (COL-1a, FIX 4): it may
    # be raised but never dropped below the floor.
    if batch_cooldown_seconds < engine.BATCH_COOLDOWN_FLOOR_SECONDS:
        logger.error(
            "batch-cooldown-seconds is below the enforced floor",
            extra={
                "batch_cooldown_seconds": batch_cooldown_seconds,
                "floor_seconds": engine.BATCH_COOLDOWN_FLOOR_SECONDS,
            },
        )
        return 2

    dir_error = engine.validate_output_dirs(intake_dir, report_dir, ledger_dir)
    if dir_error is not None:
        logger.error(
            "refusing to write inside a git working tree",
            extra={"error": dir_error},
        )
        return 2

    report_dir.mkdir(parents=True, exist_ok=True)
    ledger_dir.mkdir(parents=True, exist_ok=True)

    params = CollectParams(
        court=court,
        year=year,
        start_seq=start_seq,
        count=count,
        max_minutes=max_minutes,
        intake_dir=intake_dir,
        report_dir=report_dir,
        ledger_dir=ledger_dir,
        headless=headless,
        batch_size=batch_size,
        batch_cooldown_seconds=batch_cooldown_seconds,
        recheck_misses=recheck_misses,
    )

    abort_event = Event()
    previous_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, lambda *_a: abort_event.set())

    # Import here (not at module top) so the module stays Playwright-free to
    # import; the optional group is only required at actual run time.
    from pipeline.collector.transport import PlaywrightTransport

    try:
        with PlaywrightTransport(headless=headless) as transport:
            report = engine.run(
                params,
                transport,
                sleep=time.sleep,
                monotonic=time.monotonic,
                now=lambda: datetime.now(UTC),
                jitter=_jitter,
                abort_event=abort_event,
            )
    finally:
        signal.signal(signal.SIGINT, previous_handler)

    counts = report["counts"]
    print(
        f"collect: {report['stop_reason']} — {report['coverage_statement']}; "
        f"blocks={counts['blocks']} errors={counts['errors']} "
        f"already_present={counts['already_present']} "
        f"known_miss={counts['known_miss']}; "
        f"duration={report['duration_hms']}; outputs under {report['output_dir']}"
    )
    return 0


def run_collect_search(
    *,
    court: str,
    start_date: date,
    end_date: date,
    max_minutes: int,
    intake_dir: Path,
    report_dir: Path,
    ledger_dir: Path,
    headless: bool,
    batch_size: int,
    batch_cooldown_seconds: int,
    max_fetches: int | None,
    recheck_windows: bool,
) -> int:
    """Validate inputs, run one search-mode collection, print a summary.

    Returns an exit code. Like :func:`run_collect`, tests exercise the pure
    :func:`search_engine.run` loop directly and never reach Playwright.
    """
    if max_minutes < 1 or batch_size < 1:
        logger.error(
            "invalid parameters",
            extra={"max_minutes": max_minutes, "batch_size": batch_size},
        )
        return 2
    if end_date < start_date:
        logger.error(
            "end-date precedes start-date",
            extra={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        )
        return 2
    if max_fetches is not None and max_fetches < 1:
        logger.error("max-fetches must be >= 1", extra={"max_fetches": max_fetches})
        return 2

    # Same enforced floor on the operational batch cooldown as enumeration mode.
    if batch_cooldown_seconds < engine.BATCH_COOLDOWN_FLOOR_SECONDS:
        logger.error(
            "batch-cooldown-seconds is below the enforced floor",
            extra={
                "batch_cooldown_seconds": batch_cooldown_seconds,
                "floor_seconds": engine.BATCH_COOLDOWN_FLOOR_SECONDS,
            },
        )
        return 2

    dir_error = engine.validate_output_dirs(intake_dir, report_dir, ledger_dir)
    if dir_error is not None:
        logger.error(
            "refusing to write inside a git working tree",
            extra={"error": dir_error},
        )
        return 2

    report_dir.mkdir(parents=True, exist_ok=True)
    ledger_dir.mkdir(parents=True, exist_ok=True)

    params = SearchParams(
        court=court,
        start_date=start_date,
        end_date=end_date,
        max_minutes=max_minutes,
        intake_dir=intake_dir,
        report_dir=report_dir,
        ledger_dir=ledger_dir,
        headless=headless,
        batch_size=batch_size,
        batch_cooldown_seconds=batch_cooldown_seconds,
        max_fetches=max_fetches,
        recheck_windows=recheck_windows,
    )

    abort_event = Event()
    previous_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, lambda *_a: abort_event.set())

    # Imported here (not at module top) so the module stays Playwright-free to
    # import; the optional group is only required at actual run time.
    from pipeline.collector.search_transport import PlaywrightSearchTransport

    try:
        with PlaywrightSearchTransport(headless=headless) as transport:
            report = search_engine.run(
                params,
                transport,
                sleep=time.sleep,
                monotonic=time.monotonic,
                now=lambda: datetime.now(UTC),
                jitter=_jitter,
                abort_event=abort_event,
            )
    finally:
        signal.signal(signal.SIGINT, previous_handler)

    by_court = report["totals"]["by_court"]
    per_court = " ".join(
        f"{c}(h={by_court[c]['harvested']},f={by_court[c]['fetched']},"
        f"ap={by_court[c]['already_present']},ff={by_court[c]['fetch_failures']})"
        for c in ("CP", "MC")
    )
    print(
        f"collect(search): {report['stop_reason']} — "
        f"{report['coverage_statement']}; {per_court}; "
        f"skipped_rows={report['totals']['skipped_rows']}; "
        f"duration={report['duration_hms']}; outputs under {report['output_dir']}"
    )
    return 0


def run_migrate_window_ledger(*, ledger_dir: Path, runs_dir: Path) -> int:
    """One-time COL-3 migration of the shared window ledger. Returns exit code.

    Offline (no portal access): reads run reports under ``runs_dir`` to
    attribute each shared-ledger entry to its court, writes the court-scoped
    ledgers, and archives the shared file. Console output is counts, run ids,
    statuses, and paths only (hygiene).
    """
    for label, path in (("ledger-dir", ledger_dir), ("runs-dir", runs_dir)):
        if inside_git_worktree(path):
            logger.error(
                "refusing to operate inside a git working tree",
                extra={"dir": label},
            )
            return 2

    try:
        summary = migrate_shared_ledger(ledger_dir, runs_dir)
    except LedgerMigrationError as exc:
        logger.error("window ledger migration refused", extra={"reason": str(exc)})
        return 2

    if summary["status"] == "nothing_to_migrate":
        print(
            "migrate-window-ledger: nothing to migrate "
            f"(no shared ledger at {summary['shared_path']})"
        )
        return 0

    print(
        "migrate-window-ledger: migrated "
        f"{summary['total_entries']} entries -> "
        f"MC={summary['entries']['MC']} entries ({summary['dates']['MC']} dates), "
        f"CP={summary['entries']['CP']} entries ({summary['dates']['CP']} dates); "
        f"shared ledger archived to {summary['archived_to']}"
    )
    for run in summary["runs"]:
        print(
            f"  {run['run_id']}: court={run['court']} "
            f"entries={run['entries']} attribution={run['basis']}"
        )
    return 0
