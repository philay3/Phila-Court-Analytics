"""Outcome classification for a single docket fetch (Task COL-1).

Pure, transport-free, and fully unit-testable offline: the Playwright adapter
observes the portal and produces a :class:`FetchSignal`; this module turns that
signal into exactly one outcome. Separating observation from classification is
the fix for Capstone's ``AbortGuard``, which conflated "no PDF returned" with
"throttled" and so could not tell a genuine missing docket (a coverage data
point) from a block (a stop signal).

Outcome vocabulary (one per attempt):

- ``hit``     — a docket-sheet PDF was retrieved.
- ``miss``    — the docket number does not exist on the portal (clean miss).
                A successful request and a logged coverage data point.
- ``blocked`` — a rate-limit / block / bot-check response. A bot check is
                ALWAYS a block; it is never solved, bypassed, or automated.
- ``error``   — a transport exception (timeout, DOM/selector failure, etc.).

Precedence (decision, FIX 5): block signals are evaluated BEFORE the
empty-results ⇒ miss branch, because a soft-block page and an empty-results
page can look alike. A page carrying both block indicators and zero rows is
``blocked``, never ``miss``.
"""

from __future__ import annotations

from dataclasses import dataclass

OUTCOME_HIT = "hit"
OUTCOME_MISS = "miss"
OUTCOME_BLOCKED = "blocked"
OUTCOME_ERROR = "error"


@dataclass(frozen=True)
class FetchSignal:
    """What the transport observed for one fetch — booleans and counts only.

    Never carries page text, captions, or defendant-identifying content.
    ``pdf_bytes`` holds the retrieved sheet on a hit (written to intake, never
    logged); ``error_type`` holds an exception *class name* only.
    """

    pdf_ok: bool = False
    result_rows: int = 0
    bot_check: bool = False
    rate_limited: bool = False
    error: bool = False
    error_type: str | None = None
    pdf_bytes: bytes | None = None


def classify(signal: FetchSignal) -> str:
    """Map one :class:`FetchSignal` to a single outcome string.

    Order matters: ``error`` (a hard transport failure with no page to
    inspect), then block signals (FIX 5: before the miss branch), then a
    successful PDF, then a clean miss.
    """
    if signal.error:
        return OUTCOME_ERROR
    if signal.bot_check or signal.rate_limited:
        return OUTCOME_BLOCKED
    if signal.pdf_ok:
        return OUTCOME_HIT
    return OUTCOME_MISS
