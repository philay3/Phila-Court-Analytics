"""The code-enforced collection run loop (Task COL-1).

All pacing and stop conditions live here, enforced in code — never in a shell
wrapper and never dependent on operator attention:

Legal conditions (counsel-locked, NOT overridable by any flag):
  - a hard 240-minute absolute ceiling on any run;
  - a 2-minute cooldown after ANY block response, before the next request.

Operational parameters (ours; re-evaluated after the baseline run):
  - a jittered 2.0–5.0s delay after every real portal request (FIX 1);
  - 40 dockets per batch, 4-minute inter-batch cooldown;
  - consecutive-block streak stop N=5 (block_streak);
  - consecutive-error streak stop N=5 (error_streak, FIX 2).

The loop is pure and offline-testable: the Playwright transport, the sleep
function, the monotonic clock, the wall-clock ``now``, the per-request jitter
source, and the graceful-abort signal are all injected. Tests drive the whole
regime with a scripted fake transport and a recording fake sleep — zero
network, zero Playwright.

Privacy (hard): docket numbers are permitted in logs and reports (good-faith
record); page content, defendant names, and any text beyond outcome
classification are logged NOWHERE. No screenshot, tracing, HAR, or video is
captured in any code path (FIX 4).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Event

from pipeline.collector.classification import (
    OUTCOME_BLOCKED,
    OUTCOME_ERROR,
    OUTCOME_HIT,
    FetchSignal,
    classify,
)
from pipeline.collector.enumeration import docket_range
from pipeline.collector.guard import (
    BLOCK_STREAK_STOP,
    ERROR_STREAK_STOP,
    RunGuard,
)
from pipeline.paths import inside_git_worktree

logger = logging.getLogger("pipeline.collector")

# --- Counsel-locked ceilings (NOT overridable by any flag) -----------------
HARD_CEILING_MINUTES = 240
POST_BLOCK_COOLDOWN_SECONDS = 120

# --- Operational parameters (ours; batch values are flag-tunable) ----------
# Defaults for the tunable batch flags (COL-1a, FIX 4). The batch cooldown has
# an enforced FLOOR — it may be raised but never dropped below it.
BATCH_SIZE_DEFAULT = 40
BATCH_COOLDOWN_DEFAULT_SECONDS = 240
BATCH_COOLDOWN_FLOOR_SECONDS = 60
# The per-request jitter band is unoverridable (COL-1, FIX 1).
PER_REQUEST_DELAY_MIN_SECONDS = 2.0
PER_REQUEST_DELAY_MAX_SECONDS = 5.0

# --- Stop reasons ----------------------------------------------------------
STOP_TIME_CAP = "time_cap"
STOP_RANGE_EXHAUSTED = "range_exhausted"
STOP_OPERATOR_ABORT = "operator_abort"
# (block_streak / error_streak stop reasons come from RunGuard.)

# Attempt outcomes as they appear in the log/report. ``already_present`` is a
# local intake skip (no portal request); the rest come from classify().
OUTCOME_ALREADY_PRESENT = "already_present"

ATTEMPT_LOG_FILENAME = "attempts.jsonl"
RUN_REPORT_FILENAME = "run-report.json"

# Count keys in the run report, in a stable display order.
_COUNT_KEYS = ("hits", "misses", "already_present", "blocks", "errors")
_OUTCOME_TO_COUNT = {
    OUTCOME_HIT: "hits",
    "miss": "misses",
    OUTCOME_ALREADY_PRESENT: "already_present",
    OUTCOME_BLOCKED: "blocks",
    OUTCOME_ERROR: "errors",
}


@dataclass
class CollectParams:
    """Parameters for one collection run (recorded verbatim in the report)."""

    court: str
    year: int
    start_seq: int
    count: int
    max_minutes: int
    intake_dir: Path
    report_dir: Path
    headless: bool = False
    batch_size: int = BATCH_SIZE_DEFAULT
    batch_cooldown_seconds: int = BATCH_COOLDOWN_DEFAULT_SECONDS


class Transport:
    """Structural contract for a fetch transport (documentation only).

    Implementations must never raise out of :meth:`fetch`; a transport failure
    is returned as ``FetchSignal(error=True, error_type=...)``.
    """

    def fetch(self, docket: str) -> FetchSignal:  # pragma: no cover - protocol
        raise NotImplementedError


def validate_output_dirs(intake_dir: Path, report_dir: Path) -> str | None:
    """Return an error message if either output dir is inside a git worktree.

    PDFs land only under the intake dir and reports only under the report dir;
    both must sit outside every repository so nothing derived from real
    dockets can be committed. Returns ``None`` when both are safe.
    """
    for label, path in (("intake-dir", intake_dir), ("report-dir", report_dir)):
        if inside_git_worktree(path):
            return (
                f"{label} resolves to a path inside a git working tree; choose "
                "a location outside any repository"
            )
    return None


def _format_hms(seconds: float) -> str:
    """Format a duration as ``H:MM:SS`` for session-length accounting."""
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def _attempt_detail(outcome: str, signal: FetchSignal | None) -> str | None:
    """A privacy-safe, content-free detail string for the attempt log."""
    if signal is None:
        return None
    if outcome == OUTCOME_BLOCKED:
        if signal.bot_check:
            return "bot_check"
        if signal.unauthorized:
            return "unauthorized"
        if signal.rate_limited:
            return "rate_limited"
        # Classified blocked by the fail-closed default: no positive marker.
        return "unrecognized_page"
    if outcome == OUTCOME_ERROR:
        return signal.error_type
    return None


def run(
    params: CollectParams,
    transport: Transport,
    *,
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
    now: Callable[[], datetime],
    jitter: Callable[[], float],
    abort_event: Event,
) -> dict:
    """Execute one collection run; write the attempt log + report; return it.

    Enumerates the requested docket range, fetches each number through
    ``transport``, enforces every cap/cooldown/streak in code, writes
    ``attempts.jsonl`` and ``run-report.json`` under ``report_dir/<run-id>/``,
    and saves each hit's PDF to ``intake_dir/<docket>.pdf``. Returns the run
    report dict.
    """
    started_at = now()
    start_mono = monotonic()
    run_id = "run-" + started_at.strftime("%Y%m%d-%H%M%S")
    run_dir = params.report_dir / run_id

    params.intake_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    # The 240-minute ceiling clamps the wall-clock budget: no flag can exceed
    # it (FIX / legal condition). --max-minutes only ever shortens the run.
    budget_seconds = min(params.max_minutes, HARD_CEILING_MINUTES) * 60

    dockets = docket_range(params.court, params.year, params.start_seq, params.count)
    guard = RunGuard()

    attempts: list[dict] = []
    counts = dict.fromkeys(_COUNT_KEYS, 0)
    cooldowns_taken = {"post_block": 0, "inter_batch": 0}
    delays_taken = 0
    max_block_streak = 0
    max_error_streak = 0
    requests_in_batch = 0
    batch_number = 1
    stop_reason: str | None = None

    logger.info(
        "collection run starting",
        extra={
            "run_id": run_id,
            "court": params.court,
            "year": params.year,
            "start_seq": params.start_seq,
            "count": params.count,
            "max_minutes": params.max_minutes,
            "hard_ceiling_minutes": HARD_CEILING_MINUTES,
            "headful": not params.headless,
        },
    )

    def _elapsed() -> float:
        return monotonic() - start_mono

    def _record(docket: str, outcome: str, signal: FetchSignal | None) -> None:
        attempts.append(
            {
                "docket_number": docket,
                "outcome": outcome,
                "detail": _attempt_detail(outcome, signal),
                "batch": batch_number,
                "timestamp": now().isoformat(),
            }
        )
        counts[_OUTCOME_TO_COUNT[outcome]] += 1

    for docket in dockets:
        if abort_event.is_set():
            stop_reason = STOP_OPERATOR_ABORT
            break
        if _elapsed() >= budget_seconds:
            stop_reason = STOP_TIME_CAP
            break

        # Resumability: an intake PDF already on disk is skipped (no portal
        # request, no batch advance, no delay). Neutral to both streaks.
        if (params.intake_dir / f"{docket}.pdf").exists():
            _record(docket, OUTCOME_ALREADY_PRESENT, None)
            guard.record(OUTCOME_ALREADY_PRESENT)
            logger.info(
                "attempt",
                extra={
                    "docket_number": docket,
                    "outcome": OUTCOME_ALREADY_PRESENT,
                    "batch": batch_number,
                    "attempted": len(attempts),
                },
            )
            continue

        # Inter-batch cooldown fires before the first real request of a new
        # batch — i.e. once a full batch of real requests has completed.
        if requests_in_batch == params.batch_size:
            logger.info(
                "cooldown",
                extra={
                    "kind": "inter_batch",
                    "seconds": params.batch_cooldown_seconds,
                },
            )
            sleep(params.batch_cooldown_seconds)
            cooldowns_taken["inter_batch"] += 1
            requests_in_batch = 0
            batch_number += 1
            if abort_event.is_set():
                stop_reason = STOP_OPERATOR_ABORT
                break
            if _elapsed() >= budget_seconds:
                stop_reason = STOP_TIME_CAP
                break

        signal = transport.fetch(docket)
        outcome = classify(signal)
        _record(docket, outcome, signal)
        requests_in_batch += 1

        if outcome == OUTCOME_HIT and signal.pdf_bytes is not None:
            (params.intake_dir / f"{docket}.pdf").write_bytes(signal.pdf_bytes)

        # Jittered per-request delay after EVERY real portal request (FIX 1).
        delay = jitter()
        sleep(delay)
        delays_taken += 1

        # Post-block cooldown: 2 minutes after ANY block, before the next
        # request (counsel-locked, on top of the per-request delay).
        if outcome == OUTCOME_BLOCKED:
            logger.info(
                "cooldown",
                extra={"kind": "post_block", "seconds": POST_BLOCK_COOLDOWN_SECONDS},
            )
            sleep(POST_BLOCK_COOLDOWN_SECONDS)
            cooldowns_taken["post_block"] += 1

        stop = guard.record(outcome)
        max_block_streak = max(max_block_streak, guard.block_streak)
        max_error_streak = max(max_error_streak, guard.error_streak)

        logger.info(
            "attempt",
            extra={
                "docket_number": docket,
                "outcome": outcome,
                "batch": batch_number,
                "attempted": len(attempts),
                "hits": counts["hits"],
                "misses": counts["misses"],
                "blocks": counts["blocks"],
                "errors": counts["errors"],
            },
        )

        if stop is not None:
            stop_reason = stop
            break
    else:
        stop_reason = STOP_RANGE_EXHAUSTED

    ended_at = now()
    duration_seconds = round(_elapsed(), 3)

    report = _build_report(
        run_id=run_id,
        run_dir=run_dir,
        params=params,
        dockets=dockets,
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=duration_seconds,
        counts=counts,
        attempts=attempts,
        cooldowns_taken=cooldowns_taken,
        delays_taken=delays_taken,
        max_block_streak=max_block_streak,
        max_error_streak=max_error_streak,
        stop_reason=stop_reason or STOP_RANGE_EXHAUSTED,
    )

    _write_outputs(run_dir, attempts, report)

    logger.info(
        "collection run complete",
        extra={
            "run_id": run_id,
            "stop_reason": report["stop_reason"],
            "attempted": counts_total(counts),
            "hits": counts["hits"],
            "duration_hms": report["duration_hms"],
        },
    )
    return report


def counts_total(counts: dict[str, int]) -> int:
    """Total attempted = every logged outcome (portal requests + skips)."""
    return sum(counts[key] for key in _COUNT_KEYS)


def _coverage_statement(counts: dict[str, int], attempts: list[dict]) -> str:
    """The pinned coverage statement: ``N hits of M attempted in range X–Y``."""
    attempted = counts_total(counts)
    if attempted == 0:
        return "0 hits of 0 attempted (no dockets attempted)"
    first = attempts[0]["docket_number"]
    last = attempts[-1]["docket_number"]
    return f"{counts['hits']} hits of {attempted} attempted in range {first}–{last}"


def _build_report(
    *,
    run_id: str,
    run_dir: Path,
    params: CollectParams,
    dockets: list[str],
    started_at: datetime,
    ended_at: datetime,
    duration_seconds: float,
    counts: dict[str, int],
    attempts: list[dict],
    cooldowns_taken: dict[str, int],
    delays_taken: int,
    max_block_streak: int,
    max_error_streak: int,
    stop_reason: str,
) -> dict:
    """Assemble the pinned run-report dict (all fields always present)."""
    return {
        "run_id": run_id,
        "output_dir": str(run_dir),
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "duration_seconds": duration_seconds,
        "duration_hms": _format_hms(duration_seconds),
        "parameters": {
            "court": params.court,
            "year": params.year,
            "start_seq": params.start_seq,
            "count": params.count,
            "range_first": dockets[0],
            "range_last": dockets[-1],
            "batch_size": params.batch_size,
            "inter_batch_cooldown_seconds": params.batch_cooldown_seconds,
            "post_block_cooldown_seconds": POST_BLOCK_COOLDOWN_SECONDS,
            "per_request_delay_seconds": [
                PER_REQUEST_DELAY_MIN_SECONDS,
                PER_REQUEST_DELAY_MAX_SECONDS,
            ],
            "block_streak_stop": BLOCK_STREAK_STOP,
            "error_streak_stop": ERROR_STREAK_STOP,
            "max_minutes": params.max_minutes,
            "hard_ceiling_minutes": HARD_CEILING_MINUTES,
            "headful": not params.headless,
        },
        "counts": {
            "attempted": counts_total(counts),
            **{key: counts[key] for key in _COUNT_KEYS},
        },
        "max_block_streak": max_block_streak,
        "max_error_streak": max_error_streak,
        "stop_reason": stop_reason,
        "cooldowns_taken": dict(cooldowns_taken),
        "per_request_delays_taken": delays_taken,
        "coverage_statement": _coverage_statement(counts, attempts),
    }


def _write_outputs(run_dir: Path, attempts: list[dict], report: dict) -> None:
    """Write the JSONL attempt log and the JSON run report."""
    lines = "".join(json.dumps(a) + "\n" for a in attempts)
    (run_dir / ATTEMPT_LOG_FILENAME).write_text(lines)
    (run_dir / RUN_REPORT_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )


__all__ = [
    "CollectParams",
    "Transport",
    "run",
    "validate_output_dirs",
]
