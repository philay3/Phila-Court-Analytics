"""Refresh-target derivation from the loaded corpus (Task COL-4b).

Pinned decision 1: the refresh target set is derived from the loaded corpus —
every ``parsed.dockets`` row with at least one held charge
(``parsed.charges.disposition_raw IS NULL``). This is the charge-level
predicate, deliberately NOT the ``NON_TERMINAL_CASE`` warning: the warning
fires only when NO charge is disposed (envelope.py), so it misses a partially
disposed docket — exactly the kind a refresh must not freeze. The null-keyed
predicate is aligned with the fact layer's ``undisposed_skipped`` population;
held-FORM MC charges (Task 29.3 ``HELD_FOR_COURT_DISPOSITIONS``) are disposed
at MC and deliberately NOT refresh targets — their continuation arrives via CP
collection, not MC refresh.

Each target carries the sha256 of its CURRENT loaded sheet
(``raw.source_documents.file_hash`` via the docket's ``source_document_id``),
which is what the refresh engine compares fetched bytes against to classify a
re-fetched sheet unchanged/changed. Supersession (COL-4a) keeps that pointer
current, so the comparison stays correct across refresh cycles.

Out of the predicate BY DESIGN: ``parse_failed`` source documents have no
``parsed.*`` rows (loader Q1 ruling), so they carry no parsed state and are not
refresh targets; their remedy is parser work, not re-fetching.

Privacy: docket numbers and hashes stay in returned values (good-faith record,
written only under ~/court-data/); nothing here logs or prints them.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg

# --court -> docket-number prefix filter; "both" applies no filter. The court
# of a docket is its number's prefix — the same labeling the collector fetches
# and reports by (search-mode FETCH_COURTS precedent).
_COURT_PREFIX_FILTERS = {"MC": "MC-%", "CP": "CP-%"}
VALID_COURTS = ("MC", "CP", "both")

_TARGETS_SQL = """
    SELECT d.docket_number, s.file_hash
    FROM parsed.dockets d
    JOIN raw.source_documents s ON s.id = d.source_document_id
    WHERE EXISTS (
        SELECT 1 FROM parsed.charges c
        WHERE c.docket_id = d.id AND c.disposition_raw IS NULL
    )
"""
_ORDER_SQL = " ORDER BY d.docket_number"


@dataclass(frozen=True)
class RefreshTarget:
    """One refresh target: a loaded non-terminal docket and its current hash."""

    docket_number: str
    source_hash: str


def derive_refresh_targets(conn: psycopg.Connection, court: str) -> list[RefreshTarget]:
    """Return the ordered refresh target list for ``court`` (MC/CP/both).

    Deterministic (ordered by docket number) so an interrupted cycle's resumed
    sessions walk the same sequence. Raises ``ValueError`` on an unknown court
    rather than silently returning an empty (or unfiltered) set.
    """
    if court not in VALID_COURTS:
        valid = ", ".join(VALID_COURTS)
        raise ValueError(f"unsupported court {court!r}; supported: {valid}")
    sql = _TARGETS_SQL
    params: dict[str, str] = {}
    if court != "both":
        sql += " AND d.docket_number LIKE %(prefix)s"
        params["prefix"] = _COURT_PREFIX_FILTERS[court]
    sql += _ORDER_SQL
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [RefreshTarget(docket_number=row[0], source_hash=row[1]) for row in rows]


def count_by_court(targets: list[RefreshTarget]) -> dict[str, int]:
    """Target counts keyed by court prefix (report/log material: counts only)."""
    counts = {"MC": 0, "CP": 0}
    for target in targets:
        for court in counts:
            if target.docket_number.startswith(f"{court}-"):
                counts[court] += 1
    return counts


__all__ = [
    "RefreshTarget",
    "VALID_COURTS",
    "count_by_court",
    "derive_refresh_targets",
]
