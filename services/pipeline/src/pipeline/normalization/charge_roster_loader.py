"""Charge-roster snapshot loader (Task 22.2).

The thin, DB-touching counterpart to the pure ``charge_matcher``: it fetches the
roster snapshot from ``ref.normalized_charges`` + ``ref.charge_aliases`` via the
21.3 DB module and hands an in-memory :class:`RosterSnapshot` to the matcher.
This is the ONLY module in the charge-normalization path that imports psycopg;
keeping it separate is what makes the matcher tier-1 synthetic-testable
(pinned decision 1).

Both real and seeded rows live in ``ref.*`` (Sprint 5 SD 8), so the snapshot
naturally carries the Sprint 2 demo charges alongside the real roster with no
special-casing (AC 6).

CI guard (AC 5): this loader reads local court data and must never run in a CI
environment; it refuses via the existing ``running_in_ci`` guard (21.3 pattern).
``DATABASE_URL`` is read by the caller at the run boundary and passed in — never
read from the environment here, never logged.
"""

from __future__ import annotations

from pipeline.db import connect
from pipeline.normalization.charge_matcher import RosterEntry, RosterSnapshot
from pipeline.seam_check import running_in_ci


class CIExecutionError(RuntimeError):
    """Raised when the roster loader is invoked in a CI environment."""


def load_charge_roster(database_url: str) -> RosterSnapshot:
    """Load the charge roster (entries + aliases) into a :class:`RosterSnapshot`.

    Refuses to run in CI. One read-only transaction: every ``ref.normalized_charges``
    row (real + seeded) with its aliases grouped in. ``statute_code`` may be NULL
    for a roster row; the matcher simply indexes such a row on text only.
    """
    if running_in_ci():
        raise CIExecutionError(
            "the charge-roster loader reads local court data and must never run "
            "in a CI environment; refusing"
        )

    with connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.id, c.slug, c.display_name, c.statute_code,
                   COALESCE(
                       array_agg(a.alias_text) FILTER (WHERE a.alias_text IS NOT NULL),
                       '{}'
                   ) AS aliases
            FROM ref.normalized_charges c
            LEFT JOIN ref.charge_aliases a ON a.normalized_charge_id = c.id
            WHERE c.is_active
            GROUP BY c.id, c.slug, c.display_name, c.statute_code
            ORDER BY c.slug
            """
        )
        entries = tuple(
            RosterEntry(
                normalized_id=str(row[0]),
                slug=row[1],
                display_name=row[2],
                statute_code=row[3],
                aliases=tuple(row[4]),
            )
            for row in cur.fetchall()
        )
    return RosterSnapshot(entries=entries)
