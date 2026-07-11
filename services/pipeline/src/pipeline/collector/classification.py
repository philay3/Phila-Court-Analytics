"""Outcome classification for a single docket fetch (Task COL-1 / COL-1a).

Pure, transport-free, and fully unit-testable offline: the Playwright adapter
observes the portal and produces a :class:`FetchSignal`; this module turns that
signal into exactly one outcome. Separating observation from classification is
the fix for Capstone's ``AbortGuard``, which conflated "no PDF returned" with
"throttled" and so could not tell a genuine missing docket (a coverage data
point) from a block (a stop signal).

Outcome vocabulary (one per attempt):

- ``hit``     — a docket-sheet PDF was retrieved.
- ``miss``    — the docket number does not exist on the portal (clean miss),
                POSITIVELY identified by the portal's genuine no-results state.
                A successful request and a logged coverage data point.
- ``blocked`` — a rate-limit / block / bot-check / unauthorized response OR any
                page shape we do not positively recognize. A bot check is
                ALWAYS a block; it is never solved, bypassed, or automated.
- ``error``   — a transport exception (timeout, DOM/selector failure, etc.).

Fail-closed polarity (COL-1a, FIX 1 — the core fix). ``miss`` REQUIRES the
positively-identified no-results state (``no_results``). Anything that is
neither a successful PDF nor a positively-identified no-results page classifies
as ``blocked`` — unknown/unrecognized pages are blocks, never misses. This is
robust to block pages we have not seen yet. Run 1 (run-20260711-034851) proved
the old fail-open polarity misclassified an "unauthorized request" block page as
``miss``, so 0 blocks were logged and the mandatory post-block cooldown never
fired.

Precedence: ``error`` first (a hard transport failure has no page to inspect),
then block signals (before the miss branch, since a soft-block page and an
empty-results page can look alike), then a successful PDF, then a positively
identified no-results miss, and finally the fail-closed default (blocked).
"""

from __future__ import annotations

from dataclasses import dataclass

OUTCOME_HIT = "hit"
OUTCOME_MISS = "miss"
OUTCOME_BLOCKED = "blocked"
OUTCOME_ERROR = "error"


@dataclass(frozen=True)
class FetchSignal:
    """What the transport observed for one fetch — booleans only.

    Never carries page text, captions, or defendant-identifying content.
    ``pdf_bytes`` holds the retrieved sheet on a hit (written to intake, never
    logged); ``error_type`` holds an exception *class name* only.

    Positive markers (COL-1a): ``pdf_ok`` and ``no_results`` are the ONLY two
    states that avoid a block classification. ``no_results`` must be set only
    when the portal's genuine empty-results state is positively identified — an
    absent/unknown page must leave it False so classification fails closed.
    """

    pdf_ok: bool = False
    no_results: bool = False
    bot_check: bool = False
    rate_limited: bool = False
    unauthorized: bool = False
    error: bool = False
    error_type: str | None = None
    pdf_bytes: bytes | None = None


def is_block_signal(signal: FetchSignal) -> bool:
    """True if any recognized block/bot-check/unauthorized marker is set."""
    return signal.bot_check or signal.rate_limited or signal.unauthorized


def classify(signal: FetchSignal) -> str:
    """Map one :class:`FetchSignal` to a single outcome string (fail-closed)."""
    if signal.error:
        return OUTCOME_ERROR
    if is_block_signal(signal):
        return OUTCOME_BLOCKED
    if signal.pdf_ok:
        return OUTCOME_HIT
    if signal.no_results:
        return OUTCOME_MISS
    # Fail-closed default: neither a PDF nor a positively-identified no-results
    # page. Unknown shapes are blocks, never misses (COL-1a, FIX 1).
    return OUTCOME_BLOCKED
