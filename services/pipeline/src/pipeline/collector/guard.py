"""Consecutive-failure stop logic (Task COL-1).

Two independent streak counters, both enforced in code (not operator
attention), each ending the run gracefully with a report when it trips:

- **block streak** (counsel-informed operational parameter, N=5):
  increments on ``blocked``; resets on ``hit`` and on ``miss`` (a clean miss
  is a successful request); an ``error`` is NEUTRAL (an error is not a block,
  so it neither increments nor resets this counter); ``already_present`` is a
  local skip with no portal request and is neutral. Trips → ``block_streak``.

- **error streak** (our operational parameter, N=5, FIX 2): increments on
  ``error``; resets on ``hit``, ``miss``, AND ``blocked`` (any of those is a
  live response from the portal, proving the transport path still works);
  ``already_present`` is neutral. Trips → ``error_streak``. Without this, a
  broken selector or a portal DOM change would burn the entire range as
  errors with nothing to stop it.

Kept portal-free so it unit-tests offline (no Playwright, no network).
"""

from __future__ import annotations

from pipeline.collector.classification import (
    OUTCOME_BLOCKED,
    OUTCOME_ERROR,
    OUTCOME_HIT,
    OUTCOME_MISS,
)

BLOCK_STREAK_STOP = 5
ERROR_STREAK_STOP = 5

STOP_BLOCK_STREAK = "block_streak"
STOP_ERROR_STREAK = "error_streak"

# hit / miss reset BOTH streaks (a real response from the portal). A block
# resets only the error streak (handled inline, since a block also advances
# the block streak in the same step).
_HIT_OR_MISS = frozenset({OUTCOME_HIT, OUTCOME_MISS})


class RunGuard:
    """Track both streaks; :meth:`record` returns a stop reason or ``None``."""

    def __init__(
        self,
        block_stop: int = BLOCK_STREAK_STOP,
        error_stop: int = ERROR_STREAK_STOP,
    ) -> None:
        self.block_stop = block_stop
        self.error_stop = error_stop
        self.block_streak = 0
        self.error_streak = 0

    def record(self, outcome: str) -> str | None:
        """Record one attempt outcome; return a stop reason if a streak trips.

        ``outcome`` is one of ``hit``/``miss``/``blocked``/``error``/
        ``already_present``.
        """
        if outcome == OUTCOME_BLOCKED:
            # A block resets the error streak, then advances the block streak.
            self.error_streak = 0
            self.block_streak += 1
            if self.block_streak >= self.block_stop:
                return STOP_BLOCK_STREAK
            return None
        if outcome == OUTCOME_ERROR:
            # Neutral to the block streak; advances the error streak.
            self.error_streak += 1
            if self.error_streak >= self.error_stop:
                return STOP_ERROR_STREAK
            return None
        if outcome in _HIT_OR_MISS:  # hit / miss: a live, real response
            self.block_streak = 0
            self.error_streak = 0
            return None
        # already_present (or anything else non-portal): neutral to both.
        return None
