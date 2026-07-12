"""Judge-roster snapshot loader (Task 22.3).

The thin, DB-touching counterpart to the pure ``judge_matcher``: it fetches the
roster snapshot from ``ref.normalized_judges`` + ``ref.judge_aliases`` via the
21.3 DB module and hands an in-memory :class:`RosterSnapshot` to the matcher.
This is the ONLY module in the judge-normalization path that imports psycopg;
keeping it separate is what makes the matcher tier-1 synthetic-testable.

Both real and fake (Sprint 2 demo) rows live in ``ref.normalized_judges``. The
fabricated demo judges are stripped from the candidate pool here via
:func:`exclude_fake_judges` (pinned decision 7 — a candidate-pool filter, no
``ref.*`` column), so a real docket value can never resolve to a fake identity.

CI guard: this loader reads local court data and must never run in a CI
environment; it refuses via the existing ``running_in_ci`` guard (21.3 pattern).
``DATABASE_URL`` is read by the caller at the run boundary and passed in — never
read from the environment here, never logged.
"""

from __future__ import annotations

from pipeline.db import connect
from pipeline.normalization.judge_matcher import (
    RosterEntry,
    RosterSnapshot,
    exclude_fake_judges,
)
from pipeline.seam_check import running_in_ci


class CIExecutionError(RuntimeError):
    """Raised when the roster loader is invoked in a CI environment."""


def load_judge_roster(database_url: str) -> RosterSnapshot:
    """Load the judge roster (entries + aliases) into a :class:`RosterSnapshot`.

    Refuses to run in CI. One read-only transaction: every active
    ``ref.normalized_judges`` row (real + fake) with its aliases grouped in, then
    the fake Sprint 2 judges are excluded from the candidate pool before the
    snapshot is built.
    """
    if running_in_ci():
        raise CIExecutionError(
            "the judge-roster loader reads local court data and must never run "
            "in a CI environment; refusing"
        )

    with connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT j.id, j.slug, j.display_name,
                   COALESCE(
                       array_agg(a.alias_text) FILTER (WHERE a.alias_text IS NOT NULL),
                       '{}'
                   ) AS aliases
            FROM ref.normalized_judges j
            LEFT JOIN ref.judge_aliases a ON a.normalized_judge_id = j.id
            WHERE j.is_active
            GROUP BY j.id, j.slug, j.display_name
            ORDER BY j.slug
            """
        )
        entries = tuple(
            RosterEntry(
                normalized_id=str(row[0]),
                slug=row[1],
                display_name=row[2],
                aliases=tuple(row[3]),
            )
            for row in cur.fetchall()
        )
    return RosterSnapshot(entries=exclude_fake_judges(entries))
