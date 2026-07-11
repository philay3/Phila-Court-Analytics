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
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

from pipeline.collector import engine
from pipeline.collector.engine import (
    PER_REQUEST_DELAY_MAX_SECONDS,
    PER_REQUEST_DELAY_MIN_SECONDS,
    CollectParams,
)

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
    headless: bool,
) -> int:
    """Validate inputs, run one collection, print a summary. Returns exit code.

    This is the CLI-facing entrypoint (the CI-environment guard runs one level
    up in ``cli.py``, mirroring parse/seam-check). Tests exercise the pure
    loop via :func:`engine.run` directly and never reach Playwright.
    """
    if max_minutes < 1 or start_seq < 1 or count < 1:
        logger.error(
            "invalid parameters",
            extra={
                "max_minutes": max_minutes,
                "start_seq": start_seq,
                "count": count,
            },
        )
        return 2

    dir_error = engine.validate_output_dirs(intake_dir, report_dir)
    if dir_error is not None:
        logger.error(
            "refusing to write inside a git working tree",
            extra={"error": dir_error},
        )
        return 2

    report_dir.mkdir(parents=True, exist_ok=True)

    params = CollectParams(
        court=court,
        year=year,
        start_seq=start_seq,
        count=count,
        max_minutes=max_minutes,
        intake_dir=intake_dir,
        report_dir=report_dir,
        headless=headless,
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
        f"already_present={counts['already_present']}; "
        f"duration={report['duration_hms']}; outputs under {report['output_dir']}"
    )
    return 0
