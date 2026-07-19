"""The search-mode collection run loop (Task COL-2).

The parallel of ``engine.run`` for Date-Filed search discovery. Enumeration mode
(``engine.run``) is left byte-for-byte unchanged (AC-9); this module reuses its
policy-locked constants, the ``RunGuard`` streak logic, and the per-fetch
``FetchSignal``/``classify`` path rather than re-deriving any of them.

Per calendar-day window (PD-1): one advanced search → ``classify_search`` →
(if complete) harvest CP/MC-51-CR rows → fetch the ``--court``-selected rows
in-session → append one window-ledger entry per FETCHED court to that court's
ledger (COL-3: ledgers are court-scoped; a window is skipped only when every
fetched court has completed it, so an MC completion can never suppress a CP
search, and vice versa). One search serves both courts' rows, so a
``--court both`` run collects MC and CP concurrently at strictly less portal
load than two per-court passes, under ONE clock, ONE ``RunGuard``, and ONE
cooldown — the locked caps, block cooldown, and streak stops are aggregate
across courts by construction. All pacing/stop conditions are enforced in
code and reused from enumeration:

  - policy-locked 240-minute ceiling and 300s post-block cooldown;
  - jittered 2.0-5.0s delay after EVERY portal request — searches AND fetches;
  - batch accounting counts ALL real portal requests, searches and fetches
    alike (skips excluded); the inter-batch cooldown fires on that combined
    count (F2);
  - block/error streak stops via the shared ``RunGuard`` (AC-7b); a truncation
    banner on any window stops the run immediately (AC-7a).

Purity/testability match ``engine.run``: the transport, sleep, clocks, jitter,
and abort signal are injected; the whole regime unit-tests offline with a
scripted fake transport — zero network, zero Playwright.

Privacy (hard): only docket numbers, counts, dates, states, and hash-safe
detail strings ever reach logs/reports. Row text, captions, participants, and
DOB are never read here (the harvester enforces that) and never emitted.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from threading import Event

from pipeline.collector.classification import (
    OUTCOME_BLOCKED,
    OUTCOME_ERROR,
    OUTCOME_HIT,
    OUTCOME_MISS,
    FetchSignal,
    classify,
)
from pipeline.collector.engine import (
    ATTEMPT_LOG_FILENAME,
    HARD_CEILING_MINUTES,
    OUTCOME_ALREADY_PRESENT,
    PER_REQUEST_DELAY_MAX_SECONDS,
    PER_REQUEST_DELAY_MIN_SECONDS,
    POST_BLOCK_COOLDOWN_SECONDS,
    RUN_REPORT_FILENAME,
    STOP_OPERATOR_ABORT,
    STOP_TIME_CAP,
    _attempt_detail,
    _format_hms,
)
from pipeline.collector.guard import BLOCK_STREAK_STOP, ERROR_STREAK_STOP, RunGuard
from pipeline.collector.harvest import HarvestResult
from pipeline.collector.search_classification import (
    OUTCOME_GRID_EMPTY,
    OUTCOME_GRID_TRUNCATED,
    OUTCOME_SEARCH_BLOCKED,
    OUTCOME_SEARCH_ERROR,
    SearchSignal,
    classify_search,
)
from pipeline.collector.window import (
    OUTCOME_BLOCKED as LEDGER_BLOCKED,
)
from pipeline.collector.window import (
    OUTCOME_COMPLETE as LEDGER_COMPLETE,
)
from pipeline.collector.window import (
    OUTCOME_EMPTY as LEDGER_EMPTY,
)
from pipeline.collector.window import (
    OUTCOME_TRUNCATED as LEDGER_TRUNCATED,
)
from pipeline.collector.window import (
    append_window_entry,
    daily_windows,
    load_complete_windows,
    window_ledger_path,
)

logger = logging.getLogger("pipeline.collector")

# --- Search-mode stop reasons (enumeration reasons are reused as imported) --
STOP_WINDOWS_EXHAUSTED = "windows_exhausted"
STOP_WINDOW_TRUNCATED = "window_truncated"
STOP_FETCH_CAP = "fetch_cap"

# Emit a progress+projection log line once every N fully-searched windows.
PROGRESS_INTERVAL_WINDOWS = 5

# --court -> the court prefixes that are FETCHED. Both are always HARVESTED.
FETCH_COURTS = {"MC": ("MC",), "CP": ("CP",), "both": ("CP", "MC")}
_COURTS = ("CP", "MC")

# Per-fetch attempt-log outcome vocabulary (search mode).
ATTEMPT_HIT = "hit"
ATTEMPT_ALREADY_PRESENT = OUTCOME_ALREADY_PRESENT
ATTEMPT_FETCH_FAILED = "fetch_failed"
DETAIL_NO_SHEET_LINK = "no_sheet_link"


@dataclass
class SearchParams:
    """Parameters for one search-mode run (recorded verbatim in the report)."""

    court: str  # "MC" | "CP" | "both"
    start_date: date
    end_date: date
    max_minutes: int
    intake_dir: Path
    report_dir: Path
    ledger_dir: Path
    headless: bool = False
    batch_size: int = 100
    batch_cooldown_seconds: int = 120
    max_fetches: int | None = None
    recheck_windows: bool = False


class SearchTransport:
    """Structural contract for a search transport (documentation only).

    ``search`` drives one window's advanced search and returns a content-free
    :class:`SearchSignal`; ``harvest`` reads the current results page into a
    :class:`HarvestResult`; ``fetch`` retrieves one docket-sheet PDF from a
    harvested href. None may raise: a failure is returned as an error signal.
    """

    def search(self, window: date) -> SearchSignal:  # pragma: no cover - protocol
        raise NotImplementedError

    def harvest(self) -> HarvestResult:  # pragma: no cover - protocol
        raise NotImplementedError

    def fetch(self, href: str) -> FetchSignal:  # pragma: no cover - protocol
        raise NotImplementedError


def _empty_court_counts() -> dict[str, dict[str, int]]:
    return {
        court: {"harvested": 0, "fetched": 0, "already_present": 0, "fetch_failures": 0}
        for court in _COURTS
    }


def _search_block_detail(signal: SearchSignal) -> str:
    """Content-free block detail for a blocked SEARCH (AC-2), mirroring the
    fetch-side ``_attempt_detail`` block vocabulary. Fail-closed default (no
    positive marker, search UI not served) is ``unrecognized_page``."""
    if signal.bot_check:
        return "bot_check"
    if signal.unauthorized:
        return "unauthorized"
    if signal.rate_limited:
        return "rate_limited"
    return "unrecognized_page"


def run(
    params: SearchParams,
    transport: SearchTransport,
    *,
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
    now: Callable[[], datetime],
    jitter: Callable[[], float],
    abort_event: Event,
) -> dict:
    """Execute one search-mode run; write the attempt log + report; return it."""
    started_at = now()
    start_mono = monotonic()
    run_id = "run-" + started_at.strftime("%Y%m%d-%H%M%S")
    run_dir = params.report_dir / run_id
    params.intake_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    budget_seconds = min(params.max_minutes, HARD_CEILING_MINUTES) * 60
    windows = daily_windows(params.start_date, params.end_date)
    fetch_courts = FETCH_COURTS[params.court]
    # COL-3: one court-scoped ledger per FETCHED court. A window is skipped
    # only when every fetched court completed it, so cross-court completions
    # can never suppress a search.
    ledger_paths = {c: window_ledger_path(params.ledger_dir, c) for c in fetch_courts}
    complete_by_court: dict[str, set[str]] = {
        c: (
            set()
            if params.recheck_windows
            else load_complete_windows(ledger_paths[c], c)
        )
        for c in fetch_courts
    }
    guard = RunGuard()

    attempts: list[dict] = []
    totals = _empty_court_counts()
    total_skipped_rows = 0
    total_fetches = 0
    window_summaries: list[dict] = []
    window_outcomes = {
        LEDGER_COMPLETE: 0,
        LEDGER_TRUNCATED: 0,
        LEDGER_EMPTY: 0,
        LEDGER_BLOCKED: 0,
        "error": 0,
    }
    skipped_complete = 0
    cooldowns_taken = {"post_block": 0, "inter_batch": 0}
    delays_taken = 0
    requests_in_batch = 0
    batch_number = 1
    windows_processed = 0
    max_block_streak = 0
    max_error_streak = 0
    stop_reason: str | None = None

    logger.info(
        "search-mode collection run starting",
        extra={
            "run_id": run_id,
            "court": params.court,
            "start_date": params.start_date.isoformat(),
            "end_date": params.end_date.isoformat(),
            "windows": len(windows),
            "max_minutes": params.max_minutes,
            "hard_ceiling_minutes": HARD_CEILING_MINUTES,
            "max_fetches": params.max_fetches,
            "headful": not params.headless,
        },
    )

    def _elapsed() -> float:
        return monotonic() - start_mono

    def _record_guard(outcome: str) -> str | None:
        nonlocal max_block_streak, max_error_streak
        stop = guard.record(outcome)
        max_block_streak = max(max_block_streak, guard.block_streak)
        max_error_streak = max(max_error_streak, guard.error_streak)
        return stop

    def _log_cooldown(
        kind: str,
        seconds: int,
        *,
        outcome: str | None = None,
        detail: str | None = None,
    ) -> None:
        """One cooldown log line with batch context (AC-2). ``requests_in_batch``
        and ``batch_number`` are read at the moment of the trigger; post_block
        lines additionally carry the triggering ``outcome`` and ``detail``."""
        extra: dict = {
            "kind": kind,
            "seconds": seconds,
            "batch": batch_number,
            "requests_in_batch": requests_in_batch,
        }
        if outcome is not None:
            extra["outcome"] = outcome
        if detail is not None:
            extra["detail"] = detail
        logger.info("cooldown", extra=extra)

    def _maybe_emit_progress() -> None:
        """Every ``PROGRESS_INTERVAL_WINDOWS`` fully-searched windows, log a
        progress line (AC-3): windows complete/remaining, total portal requests
        so far, elapsed vs. the effective time budget, and a linear projection
        of whether the run ends in ``time_cap`` or ``windows_exhausted``."""
        if windows_processed % PROGRESS_INTERVAL_WINDOWS != 0:
            return
        complete = skipped_complete + windows_processed
        remaining = len(windows) - complete
        elapsed = _elapsed()
        per_window = elapsed / windows_processed if windows_processed else 0.0
        projected_total = elapsed + per_window * remaining
        projected_stop = (
            STOP_TIME_CAP
            if projected_total > budget_seconds
            else STOP_WINDOWS_EXHAUSTED
        )
        logger.info(
            "progress",
            extra={
                "windows_complete": complete,
                "windows_remaining": remaining,
                "total_requests": delays_taken,
                "elapsed_minutes": round(elapsed / 60, 1),
                "cap_minutes": round(budget_seconds / 60, 1),
                "projected_stop": projected_stop,
                # AC-7 (COL-3): cumulative per-court activity, labeled per
                # court, so a combined MC+CP run's progress is distinguishable
                # live. Counts only — console hygiene.
                "by_court": {
                    c: {
                        "harvested": totals[c]["harvested"],
                        "fetched": totals[c]["fetched"],
                        "already_present": totals[c]["already_present"],
                        "fetch_failures": totals[c]["fetch_failures"],
                    }
                    for c in fetch_courts
                },
            },
        )

    def _maybe_inter_batch_cooldown() -> str | None:
        """Fire the inter-batch cooldown before a real request if a full batch
        of combined search+fetch requests has completed (F2). Returns a
        boundary stop reason (abort/time) if one trips during the cooldown."""
        nonlocal requests_in_batch, batch_number
        if requests_in_batch == params.batch_size:
            _log_cooldown("inter_batch", params.batch_cooldown_seconds)
            sleep(params.batch_cooldown_seconds)
            cooldowns_taken["inter_batch"] += 1
            requests_in_batch = 0
            batch_number += 1
            if abort_event.is_set():
                return STOP_OPERATOR_ABORT
            if _elapsed() >= budget_seconds:
                return STOP_TIME_CAP
        return None

    for window in windows:
        # Window-boundary stop checks: time cap and abort are honored between
        # windows only, never mid-fetch, so a grid_complete window is always
        # fetched to completion before the clock/abort ends the run (a window is
        # a small, bounded unit of work — the enumeration analogue of finishing
        # the in-flight request).
        if abort_event.is_set():
            stop_reason = STOP_OPERATOR_ABORT
            break
        if _elapsed() >= budget_seconds:
            stop_reason = STOP_TIME_CAP
            break

        wkey = window.isoformat()
        if all(wkey in complete_by_court[c] for c in fetch_courts):
            skipped_complete += 1
            continue

        boundary_stop = _maybe_inter_batch_cooldown()
        if boundary_stop is not None:
            stop_reason = boundary_stop
            break

        signal = transport.search(window)
        s_outcome = classify_search(signal)
        requests_in_batch += 1
        windows_processed += 1  # one searched window (drives the progress line)
        sleep(jitter())  # jitter after EVERY portal request (search)
        delays_taken += 1

        win_counts = _empty_court_counts()
        win_skipped = 0

        if s_outcome == OUTCOME_SEARCH_ERROR:
            # F3: a transport-level exception writes NO ledger entry — the
            # window stays unsearched and is retried on rerun.
            window_outcomes["error"] += 1
            window_summaries.append(
                _window_summary(wkey, "error", win_counts, win_skipped, fetch_courts)
            )
            logger.info("window", extra={"window_date": wkey, "outcome": "error"})
            stop = _record_guard(OUTCOME_ERROR)
            if stop is not None:
                stop_reason = stop
                break
            _maybe_emit_progress()
            continue

        if s_outcome == OUTCOME_SEARCH_BLOCKED:
            # F3: a blocked search DOES write a ledger entry (retryable on
            # rerun). Post-block cooldown then the block streak.
            window_outcomes[LEDGER_BLOCKED] += 1
            _write_ledger(
                ledger_paths, wkey, run_id, now, LEDGER_BLOCKED, win_counts, win_skipped
            )
            window_summaries.append(
                _window_summary(
                    wkey, LEDGER_BLOCKED, win_counts, win_skipped, fetch_courts
                )
            )
            logger.info(
                "window", extra={"window_date": wkey, "outcome": LEDGER_BLOCKED}
            )
            _log_cooldown(
                "post_block",
                POST_BLOCK_COOLDOWN_SECONDS,
                outcome=LEDGER_BLOCKED,
                detail=_search_block_detail(signal),
            )
            sleep(POST_BLOCK_COOLDOWN_SECONDS)
            cooldowns_taken["post_block"] += 1
            stop = _record_guard(OUTCOME_BLOCKED)
            if stop is not None:
                stop_reason = stop
                break
            _maybe_emit_progress()
            continue

        if s_outcome == OUTCOME_GRID_TRUNCATED:
            # AC-7a: a truncation banner on any daily window is a literal stop.
            window_outcomes[LEDGER_TRUNCATED] += 1
            _write_ledger(
                ledger_paths,
                wkey,
                run_id,
                now,
                LEDGER_TRUNCATED,
                win_counts,
                win_skipped,
            )
            window_summaries.append(
                _window_summary(
                    wkey, LEDGER_TRUNCATED, win_counts, win_skipped, fetch_courts
                )
            )
            logger.info(
                "window", extra={"window_date": wkey, "outcome": LEDGER_TRUNCATED}
            )
            _record_guard(OUTCOME_HIT)  # a live response; reset streaks (F6-parity)
            stop_reason = STOP_WINDOW_TRUNCATED
            break

        if s_outcome == OUTCOME_GRID_EMPTY:
            # F6: grid_empty is positive proof the portal served us — reset both
            # streaks. Marks the window complete for rerun-skip.
            window_outcomes[LEDGER_EMPTY] += 1
            _write_ledger(
                ledger_paths, wkey, run_id, now, LEDGER_EMPTY, win_counts, win_skipped
            )
            window_summaries.append(
                _window_summary(
                    wkey, LEDGER_EMPTY, win_counts, win_skipped, fetch_courts
                )
            )
            logger.info("window", extra={"window_date": wkey, "outcome": LEDGER_EMPTY})
            _record_guard(OUTCOME_MISS)
            _maybe_emit_progress()
            continue

        # --- grid_complete: harvest + fetch ---------------------------------
        # F6: grid_complete resets both streaks (positive proof of service).
        _record_guard(OUTCOME_HIT)
        harvest = transport.harvest()
        win_skipped = harvest.skipped_rows
        total_skipped_rows += harvest.skipped_rows
        for hrow in harvest.rows:
            win_counts[hrow.court]["harvested"] += 1
            totals[hrow.court]["harvested"] += 1

        interrupted = False
        for hrow in harvest.rows:
            if hrow.court not in fetch_courts:
                continue  # harvested + recorded, but --court excludes fetching

            # --max-fetches (smoke tooling): cap live PDF fetches. On reaching
            # it we stop the run but STILL write this window's ledger entry
            # below, so a single-window smoke run always produces its entry.
            if params.max_fetches is not None and total_fetches >= params.max_fetches:
                stop_reason = STOP_FETCH_CAP
                interrupted = True
                break

            docket = hrow.docket
            pdf_path = params.intake_dir / f"{docket}.pdf"

            # already_present precedes every fetch (PD-6): zero portal cost.
            if pdf_path.exists():
                win_counts[hrow.court]["already_present"] += 1
                totals[hrow.court]["already_present"] += 1
                attempts.append(
                    _attempt(docket, ATTEMPT_ALREADY_PRESENT, None, wkey, hrow.court)
                )
                continue

            if hrow.href is None:
                # A harvested row with no docket-sheet anchor cannot be fetched:
                # a fetch failure, but no portal request (guard-neutral).
                win_counts[hrow.court]["fetch_failures"] += 1
                totals[hrow.court]["fetch_failures"] += 1
                attempts.append(
                    _attempt(
                        docket,
                        ATTEMPT_FETCH_FAILED,
                        DETAIL_NO_SHEET_LINK,
                        wkey,
                        hrow.court,
                    )
                )
                continue

            boundary_stop = _maybe_inter_batch_cooldown()
            if boundary_stop is not None:
                stop_reason = boundary_stop
                interrupted = True
                break

            fsignal = transport.fetch(hrow.href)
            f_outcome = classify(fsignal)
            requests_in_batch += 1
            total_fetches += 1

            if f_outcome == OUTCOME_HIT and fsignal.pdf_bytes is not None:
                pdf_path.write_bytes(fsignal.pdf_bytes)
                win_counts[hrow.court]["fetched"] += 1
                totals[hrow.court]["fetched"] += 1
                attempts.append(_attempt(docket, ATTEMPT_HIT, None, wkey, hrow.court))
            else:
                # blocked or error: a fetch failure. Detail is content-free
                # (block marker or exception class name), reused from engine.
                win_counts[hrow.court]["fetch_failures"] += 1
                totals[hrow.court]["fetch_failures"] += 1
                attempts.append(
                    _attempt(
                        docket,
                        ATTEMPT_FETCH_FAILED,
                        _attempt_detail(f_outcome, fsignal),
                        wkey,
                        hrow.court,
                    )
                )

            sleep(jitter())  # jitter after EVERY portal request (fetch)
            delays_taken += 1
            if f_outcome == OUTCOME_BLOCKED:
                _log_cooldown(
                    "post_block",
                    POST_BLOCK_COOLDOWN_SECONDS,
                    outcome=OUTCOME_BLOCKED,
                    detail=_attempt_detail(f_outcome, fsignal),
                )
                sleep(POST_BLOCK_COOLDOWN_SECONDS)
                cooldowns_taken["post_block"] += 1

            stop = _record_guard(f_outcome)
            if stop is not None:
                stop_reason = stop
                interrupted = True
                break

        # Uniform rule: the window was search-complete, so it records a
        # ``complete`` ledger entry with whatever fetch counts were achieved
        # (a mid-fetch interruption from a streak/cap/time stop still writes it,
        # so "one entry per searched window" holds and a single-window smoke
        # run always yields its entry).
        window_outcomes[LEDGER_COMPLETE] += 1
        _write_ledger(
            ledger_paths, wkey, run_id, now, LEDGER_COMPLETE, win_counts, win_skipped
        )
        window_summaries.append(
            _window_summary(
                wkey, LEDGER_COMPLETE, win_counts, win_skipped, fetch_courts
            )
        )
        logger.info(
            "window",
            extra={
                "window_date": wkey,
                "outcome": LEDGER_COMPLETE,
                "cp_harvested": win_counts["CP"]["harvested"],
                "mc_harvested": win_counts["MC"]["harvested"],
                # AC-7 (COL-3): fetch accounting labeled per fetched court so
                # a combined MC+CP run's window activity is distinguishable
                # live (was flat sums over fetch courts pre-COL-3).
                "fetched": {c: win_counts[c]["fetched"] for c in fetch_courts},
                "already_present": {
                    c: win_counts[c]["already_present"] for c in fetch_courts
                },
                "fetch_failures": {
                    c: win_counts[c]["fetch_failures"] for c in fetch_courts
                },
                "skipped_rows": win_skipped,
            },
        )
        if interrupted:
            break
        _maybe_emit_progress()
    else:
        stop_reason = STOP_WINDOWS_EXHAUSTED

    ended_at = now()
    duration_seconds = round(_elapsed(), 3)

    report = _build_report(
        run_id=run_id,
        run_dir=run_dir,
        params=params,
        windows=windows,
        ledger_paths=ledger_paths,
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=duration_seconds,
        totals=totals,
        total_skipped_rows=total_skipped_rows,
        total_fetches=total_fetches,
        window_summaries=window_summaries,
        window_outcomes=window_outcomes,
        skipped_complete=skipped_complete,
        cooldowns_taken=cooldowns_taken,
        delays_taken=delays_taken,
        max_block_streak=max_block_streak,
        max_error_streak=max_error_streak,
        stop_reason=stop_reason or STOP_WINDOWS_EXHAUSTED,
    )
    _write_outputs(run_dir, attempts, report)

    logger.info(
        "search-mode collection run complete",
        extra={
            "run_id": run_id,
            "stop_reason": report["stop_reason"],
            "coverage_statement": report["coverage_statement"],
            "duration_hms": report["duration_hms"],
        },
    )
    return report


def _attempt(
    docket: str, outcome: str, detail: str | None, window_date: str, court: str
) -> dict:
    """A privacy-safe per-fetch attempt-log entry (search mode: + window_date)."""
    return {
        "docket_number": docket,
        "outcome": outcome,
        "detail": detail,
        "window_date": window_date,
        "court": court,
    }


def _write_ledger(
    paths: dict[str, Path],
    wkey: str,
    run_id: str,
    now: Callable[[], datetime],
    outcome: str,
    win_counts: dict[str, dict[str, int]],
    skipped_rows: int,
) -> None:
    """Append one searched-window entry per fetched court (PD-5 schema + COL-3
    ``court`` scope field) to that court's ledger."""
    searched_at = now().isoformat()
    for court, path in paths.items():
        append_window_entry(
            path,
            {
                "date": wkey,
                "court": court,
                "run_id": run_id,
                "searched_at": searched_at,
                "outcome": outcome,
                "cp_harvested": win_counts["CP"]["harvested"],
                "mc_harvested": win_counts["MC"]["harvested"],
                "fetched": {c: win_counts[c]["fetched"] for c in _COURTS},
                "already_present": {
                    c: win_counts[c]["already_present"] for c in _COURTS
                },
                "fetch_failures": {c: win_counts[c]["fetch_failures"] for c in _COURTS},
                "skipped_rows": skipped_rows,
            },
        )


def _window_summary(
    wkey: str,
    outcome: str,
    win_counts: dict[str, dict[str, int]],
    skipped_rows: int,
    fetch_courts: tuple[str, ...],
) -> dict:
    """One per-window summary block for the run report (AC-8)."""
    return {
        "date": wkey,
        "outcome": outcome,
        "by_court": {c: dict(win_counts[c]) for c in _COURTS},
        "skipped_rows": skipped_rows,
        "fetched_courts": list(fetch_courts),
    }


def _coverage_statement(
    windows: list[date], skipped_complete: int, window_outcomes: dict[str, int]
) -> str:
    """The pinned date-terms coverage statement (AC-8)."""
    total = len(windows)
    now_complete = window_outcomes["complete"] + window_outcomes["empty"]
    complete = skipped_complete + now_complete
    span = f"[{windows[0].isoformat()}..{windows[-1].isoformat()}]" if windows else "[]"
    return f"{complete} of {total} windows complete in {span}"


def _reconciles(
    totals: dict[str, dict[str, int]], fetch_courts: tuple[str, ...]
) -> bool:
    """AC-6: per fetched court, harvested == fetched + already_present +
    fetch_failures. (Only asserted for fetched courts and only when no window
    was cut short by --max-fetches; the run report exposes the buckets so the
    identity is auditable in every case.)"""
    return all(
        totals[c]["harvested"]
        == totals[c]["fetched"]
        + totals[c]["already_present"]
        + totals[c]["fetch_failures"]
        for c in fetch_courts
    )


def _build_report(
    *,
    run_id: str,
    run_dir: Path,
    params: SearchParams,
    windows: list[date],
    ledger_paths: dict[str, Path],
    started_at: datetime,
    ended_at: datetime,
    duration_seconds: float,
    totals: dict[str, dict[str, int]],
    total_skipped_rows: int,
    total_fetches: int,
    window_summaries: list[dict],
    window_outcomes: dict[str, int],
    skipped_complete: int,
    cooldowns_taken: dict[str, int],
    delays_taken: int,
    max_block_streak: int,
    max_error_streak: int,
    stop_reason: str,
) -> dict:
    """Assemble the pinned search-mode run-report dict (all fields present)."""
    fetch_courts = FETCH_COURTS[params.court]
    return {
        "run_id": run_id,
        "output_dir": str(run_dir),
        "mode": "search",
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "duration_seconds": duration_seconds,
        "duration_hms": _format_hms(duration_seconds),
        "parameters": {
            "court": params.court,
            "fetched_courts": list(fetch_courts),
            "start_date": params.start_date.isoformat(),
            "end_date": params.end_date.isoformat(),
            "batch_size": params.batch_size,
            "inter_batch_cooldown_seconds": params.batch_cooldown_seconds,
            "post_block_cooldown_seconds": POST_BLOCK_COOLDOWN_SECONDS,
            "per_request_delay_seconds": [
                PER_REQUEST_DELAY_MIN_SECONDS,
                PER_REQUEST_DELAY_MAX_SECONDS,
            ],
            "batch_request_counting": "searches_and_fetches",  # F2 auditability
            "block_streak_stop": BLOCK_STREAK_STOP,
            "error_streak_stop": ERROR_STREAK_STOP,
            "max_minutes": params.max_minutes,
            "hard_ceiling_minutes": HARD_CEILING_MINUTES,
            "max_fetches": params.max_fetches,
            "recheck_windows": params.recheck_windows,
            "headful": not params.headless,
            "window_ledger_paths": {c: str(p) for c, p in ledger_paths.items()},
        },
        "date_range": {
            "start": params.start_date.isoformat(),
            "end": params.end_date.isoformat(),
            "total_windows": len(windows),
            "searched": len(window_summaries),
            "skipped_complete": skipped_complete,
        },
        "windows": window_summaries,
        "totals": {
            "by_court": {c: dict(totals[c]) for c in _COURTS},
            "skipped_rows": total_skipped_rows,
            "fetches": total_fetches,
            "window_outcomes": dict(window_outcomes),
            "reconciles": _reconciles(totals, fetch_courts),
        },
        "max_block_streak": max_block_streak,
        "max_error_streak": max_error_streak,
        "stop_reason": stop_reason,
        "cooldowns_taken": dict(cooldowns_taken),
        "per_request_delays_taken": delays_taken,
        "coverage_statement": _coverage_statement(
            windows, skipped_complete, window_outcomes
        ),
    }


def _write_outputs(run_dir: Path, attempts: list[dict], report: dict) -> None:
    """Write the JSONL attempt log and the JSON run report."""
    lines = "".join(json.dumps(a) + "\n" for a in attempts)
    (run_dir / ATTEMPT_LOG_FILENAME).write_text(lines)
    (run_dir / RUN_REPORT_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )


__all__ = ["SearchParams", "SearchTransport", "run"]
