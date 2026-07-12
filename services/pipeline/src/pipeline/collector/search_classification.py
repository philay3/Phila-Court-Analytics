"""Search-result classification for one Date-Filed window (Task COL-2).

Pure, transport-free, offline-testable — the analog of ``classification.py`` for
search mode. The Playwright adapter observes the results page and produces a
:class:`SearchSignal`; this module maps that signal to exactly one outcome.

Four positive states (PD-2), fail-closed:

- ``grid_complete``  — the results grid rendered and the truncation banner is
                       ABSENT (the window fits under the portal's display cap).
- ``grid_truncated`` — the truncation banner is PRESENT ("Not all results are
                       shown for Common Pleas and Magisterial ..."). A real stop
                       signal: the window overflowed the cap.
- ``grid_empty``     — a positively-identified no-results state. Per the
                       COL-2 Blocker-2 adjudication (Option A): the search UI
                       was served (positive "the portal answered us" marker),
                       no block signature is present, and there are zero result
                       rows — accepting BOTH observed empty forms (no results
                       table at all, or a results table with zero rows). This is
                       the same positive-marker basis COL-1a uses for the
                       enumeration ``no_results`` outcome; it is NOT inferred
                       from absence, because the served search UI is required.
- ``blocked``        — a recognized block/bot-check/unauthorized signature, a
                       page that did NOT serve the search UI, or anything else
                       not positively recognized (the fail-closed default).

``error`` is a prior branch (a transport exception has no page to inspect),
mirroring ``classification.classify``'s precedence: error first, then block
signals, then the positive states, then the fail-closed default. ``error`` and
``blocked`` drive the existing block/error streak guard; the four positive
states are what the window ledger records.
"""

from __future__ import annotations

from dataclasses import dataclass

OUTCOME_GRID_COMPLETE = "grid_complete"
OUTCOME_GRID_TRUNCATED = "grid_truncated"
OUTCOME_GRID_EMPTY = "grid_empty"
OUTCOME_SEARCH_BLOCKED = "blocked"
OUTCOME_SEARCH_ERROR = "error"

# The four positive states that a served search page can classify as.
POSITIVE_STATES = frozenset(
    {
        OUTCOME_GRID_COMPLETE,
        OUTCOME_GRID_TRUNCATED,
        OUTCOME_GRID_EMPTY,
        OUTCOME_SEARCH_BLOCKED,
    }
)


@dataclass(frozen=True)
class SearchSignal:
    """What the transport observed for one window search — booleans/counts only.

    Never carries row text, captions, participant names, or DOB content.

    Positive markers (Blocker-2 / Option A): ``search_ui_present`` is the
    positive "the portal served the search page" marker; a block interstitial
    lacks it and so fails closed. ``banner_present`` is the pinned truncation
    signal. ``results_table_present``/``row_count`` distinguish complete from
    empty once the page is positively served.
    """

    search_ui_present: bool = False
    results_table_present: bool = False
    row_count: int = 0
    banner_present: bool = False
    bot_check: bool = False
    rate_limited: bool = False
    unauthorized: bool = False
    error: bool = False
    error_type: str | None = None


def is_block_signal(signal: SearchSignal) -> bool:
    """True if any recognized block/bot-check/unauthorized marker is set."""
    return signal.bot_check or signal.rate_limited or signal.unauthorized


def classify_search(signal: SearchSignal) -> str:
    """Map one :class:`SearchSignal` to a single outcome string (fail-closed)."""
    if signal.error:
        return OUTCOME_SEARCH_ERROR
    if is_block_signal(signal):
        return OUTCOME_SEARCH_BLOCKED
    # Fail-closed: without the positively-served search UI, we do not trust the
    # page — an unrecognized/interstitial page is a block, never empty.
    if not signal.search_ui_present:
        return OUTCOME_SEARCH_BLOCKED
    if signal.banner_present:
        return OUTCOME_GRID_TRUNCATED
    if signal.results_table_present and signal.row_count >= 1:
        return OUTCOME_GRID_COMPLETE
    # Served search UI, no block, no banner, and zero result rows: the
    # positively-identified empty state (Blocker-2 / Option A). Accepts both
    # observed forms — no results table, or a table with zero rows.
    if signal.row_count == 0:
        return OUTCOME_GRID_EMPTY
    # Fail-closed default: anything not positively recognized (e.g. rows claimed
    # without a rendered table) is blocked, never guessed.
    return OUTCOME_SEARCH_BLOCKED
