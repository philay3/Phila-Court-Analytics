"""The pending-docket refresh run loop (Task COL-4b).

Re-fetches exactly the DB-derived refresh target list (refresh_targets.py) —
the loaded corpus's non-terminal dockets — through the SAME per-docket
DocketNumber-search transport enumeration uses (``PlaywrightTransport.fetch``
is court-agnostic; only enumeration's range FORMATTING is MC-only), so CP and
MC targets fetch identically. Fetched sheets land in a cycle-scoped refresh
directory and enter the corpus via the standard intake protocol; a changed
sheet supersedes at load (COL-4a), an unchanged sheet is a normal duplicate at
import (pinned decision 8).

Bypass scoping (pinned decision 3 / AC-2): the already-present skip that
freezes pending dockets lives in the enumerate/search engines and checks the
MAIN intake dir. This engine never consults that dir — its entire fetch
universe IS the target list, so the bypass is scoped to targets BY
CONSTRUCTION: nothing outside the list is ever attempted (tests pin
``attempted == targets``), and the other modes' skip semantics are untouched.
Resumability WITHIN a cycle is the same presence-skip pattern applied to the
cycle's refresh dir instead: a target whose PDF is already there was fetched by
an earlier session of this cycle and is skipped locally (``already_fetched``,
no portal request, streak-neutral).

All counsel conditions are REUSED from enumeration, never re-derived (pinned
decision 2): the flag-proof 240-minute ceiling and 300s post-block cooldown,
the jittered 2.0-5.0s delay after EVERY portal request, inter-batch cooldowns
on real requests only, and the shared ``RunGuard`` block/error streak stops
over the fail-closed ``classify`` path.

A refresh is not window coverage and not enumeration coverage: this module
writes NO window-ledger entries and NO miss-ledger entries (pinned decision 3
/ AC-3). A positively-identified no-results state on a LOADED docket is an
anomaly — counted under ``failed`` with detail ``no_results`` and totaled as
``no_results_anomalies`` in the report (a first-cycle STOP-and-report signal),
never recorded as a coverage miss.

Hash classification (pinned decision 8): every hit's bytes are sha256'd
against the target's current loaded hash — ``unchanged`` (still pending,
sheet identical) or ``changed`` (supersession candidate). ``new`` means no
prior hash was available for comparison; the derivation JOIN guarantees one,
so the bucket is defensive and expected 0. The PDF is written in ALL hit
cases: unchanged sheets then die as duplicates at import, which gives the
runbook its cross-check identity (import ``duplicate`` ≈ report ``unchanged``).

Purity/testability match ``engine.run``: transport, sleep, clocks, jitter, and
abort signal are injected; the whole regime unit-tests offline with a scripted
fake transport — zero network, zero Playwright, zero database.

Privacy (hard): docket numbers appear only in the attempt log and logger lines
(the good-faith record, written under ~/court-data/); the run report and
console summaries carry counts, statuses, and hash classes only.
"""

from __future__ import annotations

import hashlib
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
    OUTCOME_MISS,
    classify,
)
from pipeline.collector.engine import (
    ATTEMPT_LOG_FILENAME,
    HARD_CEILING_MINUTES,
    PER_REQUEST_DELAY_MAX_SECONDS,
    PER_REQUEST_DELAY_MIN_SECONDS,
    POST_BLOCK_COOLDOWN_SECONDS,
    RUN_REPORT_FILENAME,
    STOP_OPERATOR_ABORT,
    STOP_TIME_CAP,
    Transport,
    _attempt_detail,
    _format_hms,
)
from pipeline.collector.guard import BLOCK_STREAK_STOP, ERROR_STREAK_STOP, RunGuard
from pipeline.collector.refresh_targets import RefreshTarget, count_by_court
from pipeline.collector.search_engine import STOP_FETCH_CAP

logger = logging.getLogger("pipeline.collector")

# --- Refresh-mode stop reason (shared reasons are reused as imported) -------
STOP_TARGETS_EXHAUSTED = "targets_exhausted"

# Hash classes for a fetched sheet vs. the target's current loaded hash.
HASH_UNCHANGED = "unchanged"
HASH_CHANGED = "changed"
HASH_NEW = "new"

# Per-attempt outcome vocabulary (refresh mode). ``already_fetched`` is the
# cycle-local resume skip (refresh dir, THIS cycle) — deliberately distinct
# from enumeration's ``already_present`` (main intake dir), which refresh
# bypasses by construction. Unknown to RunGuard -> streak-neutral, like every
# non-portal skip.
ATTEMPT_HIT = "hit"
ATTEMPT_ALREADY_FETCHED = "already_fetched"
ATTEMPT_FETCH_FAILED = "fetch_failed"
DETAIL_NO_RESULTS = "no_results"
DETAIL_NO_PDF_BYTES = "no_pdf_bytes"

# Count keys in the run report, in a stable display order. ``attempted`` is
# derived; ``no_results_anomalies`` is a labeled subset of ``failed``.
_COUNT_KEYS = (
    "fetched",
    "unchanged_hash",
    "changed_hash",
    "new_hash",
    "already_fetched",
    "blocked",
    "failed",
    "no_results_anomalies",
)


@dataclass
class RefreshParams:
    """Parameters for one refresh run (recorded verbatim in the report)."""

    court: str  # "MC" | "CP" | "both" — the filter the target list was derived under
    max_minutes: int
    refresh_dir: Path
    report_dir: Path
    headless: bool = False
    batch_size: int = 100
    batch_cooldown_seconds: int = 120
    max_fetches: int | None = None


def run(
    params: RefreshParams,
    targets: list[RefreshTarget],
    transport: Transport,
    *,
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
    now: Callable[[], datetime],
    jitter: Callable[[], float],
    abort_event: Event,
) -> dict:
    """Execute one refresh run; write the attempt log + report; return it."""
    started_at = now()
    start_mono = monotonic()
    run_id = "run-" + started_at.strftime("%Y%m%d-%H%M%S")
    run_dir = params.report_dir / run_id

    params.refresh_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    # The 240-minute ceiling clamps the wall-clock budget: no flag can exceed
    # it (counsel-locked). --max-minutes only ever shortens the run.
    budget_seconds = min(params.max_minutes, HARD_CEILING_MINUTES) * 60

    guard = RunGuard()

    attempts: list[dict] = []
    counts = dict.fromkeys(_COUNT_KEYS, 0)
    cooldowns_taken = {"post_block": 0, "inter_batch": 0}
    delays_taken = 0
    total_fetches = 0
    max_block_streak = 0
    max_error_streak = 0
    requests_in_batch = 0
    batch_number = 1
    stop_reason: str | None = None

    by_court = count_by_court(targets)
    logger.info(
        "refresh run starting",
        extra={
            "run_id": run_id,
            "court": params.court,
            "targets": len(targets),
            "targets_mc": by_court["MC"],
            "targets_cp": by_court["CP"],
            "max_minutes": params.max_minutes,
            "hard_ceiling_minutes": HARD_CEILING_MINUTES,
            "max_fetches": params.max_fetches,
            "headful": not params.headless,
        },
    )

    def _elapsed() -> float:
        return monotonic() - start_mono

    def _record(
        docket: str, outcome: str, detail: str | None, hash_class: str | None
    ) -> None:
        attempts.append(
            {
                "docket_number": docket,
                "outcome": outcome,
                "detail": detail,
                "hash_class": hash_class,
                "batch": batch_number,
                "timestamp": now().isoformat(),
            }
        )

    for target in targets:
        if abort_event.is_set():
            stop_reason = STOP_OPERATOR_ABORT
            break
        if _elapsed() >= budget_seconds:
            stop_reason = STOP_TIME_CAP
            break

        # --max-fetches (smoke tooling): cap live portal fetches, mirroring
        # search mode — checked before any work on the next target.
        if params.max_fetches is not None and total_fetches >= params.max_fetches:
            stop_reason = STOP_FETCH_CAP
            break

        docket = target.docket_number
        pdf_path = params.refresh_dir / f"{docket}.pdf"

        # Cycle-local resume skip: fetched by an earlier session of THIS cycle
        # (no portal request, no batch advance, no delay; streak-neutral). The
        # MAIN intake dir is never consulted — that skip is what refresh
        # bypasses, and the bypass is scoped to targets by construction.
        if pdf_path.exists():
            counts["already_fetched"] += 1
            _record(docket, ATTEMPT_ALREADY_FETCHED, None, None)
            guard.record(ATTEMPT_ALREADY_FETCHED)
            logger.info(
                "attempt",
                extra={
                    "docket_number": docket,
                    "outcome": ATTEMPT_ALREADY_FETCHED,
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
        requests_in_batch += 1
        total_fetches += 1

        if outcome == OUTCOME_HIT and signal.pdf_bytes is not None:
            digest = hashlib.sha256(signal.pdf_bytes).hexdigest()
            if not target.source_hash:
                hash_class = HASH_NEW  # defensive: derivation guarantees a hash
            elif digest == target.source_hash:
                hash_class = HASH_UNCHANGED
            else:
                hash_class = HASH_CHANGED
            pdf_path.write_bytes(signal.pdf_bytes)
            counts["fetched"] += 1
            counts[f"{hash_class}_hash"] += 1
            _record(docket, ATTEMPT_HIT, None, hash_class)
        elif outcome == OUTCOME_HIT:
            # pdf_ok without bytes cannot be hash-classified or imported: a
            # fetch failure for refresh accounting (fail-closed bookkeeping).
            counts["failed"] += 1
            _record(docket, ATTEMPT_FETCH_FAILED, DETAIL_NO_PDF_BYTES, None)
        elif outcome == OUTCOME_MISS:
            # ANOMALY: a positively-identified no-results state for a docket
            # the corpus has loaded. Counted + surfaced, never written to the
            # enumeration miss ledger (a refresh is not coverage).
            counts["failed"] += 1
            counts["no_results_anomalies"] += 1
            _record(docket, ATTEMPT_FETCH_FAILED, DETAIL_NO_RESULTS, None)
        elif outcome == OUTCOME_BLOCKED:
            counts["blocked"] += 1
            _record(docket, OUTCOME_BLOCKED, _attempt_detail(outcome, signal), None)
        elif outcome == OUTCOME_ERROR:
            counts["failed"] += 1
            _record(
                docket, ATTEMPT_FETCH_FAILED, _attempt_detail(outcome, signal), None
            )

        # Jittered per-request delay after EVERY real portal request.
        sleep(jitter())
        delays_taken += 1

        # Post-block cooldown: 300s (≥2-minute counsel minimum) after ANY
        # block, before the next request (on top of the per-request delay).
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
                "outcome": attempts[-1]["outcome"],
                "detail": attempts[-1]["detail"],
                "hash_class": attempts[-1]["hash_class"],
                "batch": batch_number,
                "attempted": len(attempts),
                "fetched": counts["fetched"],
                "blocked": counts["blocked"],
                "failed": counts["failed"],
            },
        )

        if stop is not None:
            stop_reason = stop
            break
    else:
        stop_reason = STOP_TARGETS_EXHAUSTED

    ended_at = now()
    duration_seconds = round(_elapsed(), 3)

    report = _build_report(
        run_id=run_id,
        run_dir=run_dir,
        params=params,
        targets_total=len(targets),
        targets_by_court=by_court,
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=duration_seconds,
        counts=counts,
        attempts_logged=len(attempts),
        cooldowns_taken=cooldowns_taken,
        delays_taken=delays_taken,
        max_block_streak=max_block_streak,
        max_error_streak=max_error_streak,
        stop_reason=stop_reason or STOP_TARGETS_EXHAUSTED,
    )
    _write_outputs(run_dir, attempts, report)

    logger.info(
        "refresh run complete",
        extra={
            "run_id": run_id,
            "stop_reason": report["stop_reason"],
            "coverage_statement": report["coverage_statement"],
            "duration_hms": report["duration_hms"],
        },
    )
    return report


def attempted_total(counts: dict[str, int]) -> int:
    """Total attempted = every processed target: fetches, failures, and skips.

    ``unchanged/changed/new`` are hash classes WITHIN ``fetched`` and
    ``no_results_anomalies`` is a labeled subset of ``failed``; neither adds to
    the attempted total.
    """
    return (
        counts["fetched"]
        + counts["blocked"]
        + counts["failed"]
        + counts["already_fetched"]
    )


def _reconciles(counts: dict[str, int], attempts_logged: int) -> dict[str, bool]:
    """The two accounting identities, exposed for audit in every report.

    The first cross-checks the derived ``attempted`` total against the attempt
    log (every processed target appends exactly one entry — an independent
    accumulator, so a bookkeeping slip cannot hide). The second pins the hash
    classes as a partition of ``fetched``.
    """
    return {
        "attempted_eq_attempt_log_entries": attempted_total(counts) == attempts_logged,
        "fetched_eq_unchanged_changed_new": counts["fetched"]
        == counts["unchanged_hash"] + counts["changed_hash"] + counts["new_hash"],
    }


def _coverage_statement(counts: dict[str, int], targets_total: int) -> str:
    """The refresh coverage statement (counts only, no docket numbers)."""
    return (
        f"{counts['fetched']} fetched of {targets_total} targets "
        f"({counts['unchanged_hash']} unchanged, {counts['changed_hash']} changed, "
        f"{counts['new_hash']} new); "
        f"{counts['already_fetched']} already fetched this cycle"
    )


def _build_report(
    *,
    run_id: str,
    run_dir: Path,
    params: RefreshParams,
    targets_total: int,
    targets_by_court: dict[str, int],
    started_at: datetime,
    ended_at: datetime,
    duration_seconds: float,
    counts: dict[str, int],
    attempts_logged: int,
    cooldowns_taken: dict[str, int],
    delays_taken: int,
    max_block_streak: int,
    max_error_streak: int,
    stop_reason: str,
) -> dict:
    """Assemble the pinned refresh run-report dict (all fields always present)."""
    return {
        "run_id": run_id,
        "output_dir": str(run_dir),
        "mode": "refresh",
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "duration_seconds": duration_seconds,
        "duration_hms": _format_hms(duration_seconds),
        "parameters": {
            "court": params.court,
            "refresh_dir": str(params.refresh_dir),
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
            "max_fetches": params.max_fetches,
            "headful": not params.headless,
        },
        # AC-1: target-list derivation is reported as counts only.
        "targets": {
            "derived_total": targets_total,
            "by_court": dict(targets_by_court),
        },
        "counts": {
            "attempted": attempted_total(counts),
            **{key: counts[key] for key in _COUNT_KEYS},
        },
        "reconciles": _reconciles(counts, attempts_logged),
        "max_block_streak": max_block_streak,
        "max_error_streak": max_error_streak,
        "stop_reason": stop_reason,
        "cooldowns_taken": dict(cooldowns_taken),
        "per_request_delays_taken": delays_taken,
        "coverage_statement": _coverage_statement(counts, targets_total),
    }


def _write_outputs(run_dir: Path, attempts: list[dict], report: dict) -> None:
    """Write the JSONL attempt log and the JSON run report."""
    lines = "".join(json.dumps(a) + "\n" for a in attempts)
    (run_dir / ATTEMPT_LOG_FILENAME).write_text(lines)
    (run_dir / RUN_REPORT_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )


__all__ = ["RefreshParams", "run"]
