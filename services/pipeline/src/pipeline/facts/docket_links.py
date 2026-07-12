"""Structured CP↔MC held-case linkage (Task 23.5) — the 18.3 deferral landing.

Reads the already-parsed ``parsed.dockets.cross_court_dockets`` capture on held MC
dockets and turns it into structured ``parsed.docket_links`` rows: source = the MC
held docket, target = the CP docket the case transfers to, link type
``held_for_court``. In-corpus CP targets resolve to a ``parsed.dockets`` FK
(resolved link); out-of-corpus targets are recorded with the target docket number
and a null FK (unresolved link — a future-collection signal, AC3). References the
linker cannot turn into a resolvable target route to ``review.queue_items`` via the
existing 22.1 / 23.4 write path, never a guess (AC2 / SD 9).

INFORMATIONAL ONLY (AC4). Linkage does NOT change fact eligibility. This module is a
normalization-stage READ of already-parsed data that writes its own link rows +
review items and feeds NOTHING back into the outcome/sentence fact path. The parser
is untouched and the 23.2/23.3 fact path is not entangled. Attribution consequences
of held-case linkage are a Sprint 7 aggregation question, explicitly deferred.

Source seam (23.5 corpus-verified decision): the linker keys off MC dockets
(``court_type_derived = 'MC'``) that carry a ``cross_court_dockets`` capture — NOT
off presence of the field across all dockets. On the loaded corpus 126 dockets carry
the field: 22 MC (the held-for-court set, all matching the §6.9 bounded pattern) and
104 CP (other-county references that §6.9 correctly rejects — out of scope here).
§6.7's null-disposition / event-key held model is a CP-side phenomenon; MC's
held-for-court is a DISPOSED charge carrying a cross-court reference, a distinct
signal — so no null-disposition filter is applied (it would exclude all 22).

Console/privacy hygiene (§6.5 / §6.8): docket numbers are internal-sensitive —
permitted inside ``parsed.*`` and ``review.*`` (internal by architecture) but NEVER
in console/logs. Callers print counts / statuses only; this module writes rows, it
does not print.

Lifecycle (SD 6, mirroring the fact rows): :func:`insert_docket_links` rebuilds the
whole ``parsed.docket_links`` table each build (delete-and-reinsert). Link rows are a
current-state projection of the corpus + linker logic, safe to rebuild; the
delete-and-reinsert makes a re-run on an unchanged corpus idempotent on link content
(same tuples, net zero change). Review items travel the persistent, dedup-keyed,
status-preserving 23.4 path instead — the two lifecycles coexist (a derived-state
table vs. an accumulating work queue) with no interaction.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

from pipeline.fact_review_vocab import (
    REVIEW_NEEDED,
    SEVERITY_MEDIUM,
    UNRESOLVABLE_CROSS_COURT_REFERENCE,
)
from pipeline.link_vocab import CROSS_COURT_DOCKETS, HELD_FOR_COURT
from pipeline.normalization.review_items import build_review_item

# The MC court type as recorded in parsed.dockets.court_type_derived (prefix-derived
# per SD 12). The held-for-court linkage source is MC only.
_MC_COURT_TYPE = "MC"

# §6.9 bounded UJS docket-number pattern. Intentionally NOT loose/greedy: a held MC
# docket's cross-court capture yields a Philadelphia (county 51) CR docket number, or
# it is unresolvable. Any non-matching fragment is a review item, never a guess (AC2).
_UJS_DOCKET_RE = re.compile(r"(?:CP|MC)-51-CR-\d{7}-\d{4}")

# candidate_context["subcase"] discriminators for the single review-item type
# (23.5 RF3 — distinguished by context, not by separate reason codes).
_SUBCASE_MALFORMED = "malformed"
_SUBCASE_AMBIGUOUS = "ambiguous_target"


def parse_cross_court_targets(raw: str) -> list[str]:
    """Extract bounded UJS target docket numbers from a cross-court string.

    Order-preserving and de-duplicated. An empty list means the string carried no
    §6.9-bounded docket number (the ``malformed`` case). In the loaded corpus every
    MC cross-court capture yields exactly one target.
    """
    return list(dict.fromkeys(_UJS_DOCKET_RE.findall(raw)))


def _resolve_target(conn: psycopg.Connection, target_docket_number: str) -> list[str]:
    """Resolve a target docket number to ``parsed.dockets`` id(s).

    ``parsed.dockets.docket_number`` has NO unique constraint (identity is per
    source document), so the lookup can return 0, 1, or ≥2 rows; the caller maps
    those to unresolved / resolved / ambiguous. Returns the id list.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM parsed.dockets WHERE docket_number = %s",
            (target_docket_number,),
        )
        return [str(row[0]) for row in cur.fetchall()]


def _load_mc_source_dockets(conn: psycopg.Connection) -> list[dict[str, object]]:
    """MC dockets carrying a cross-court capture — the held-for-court source set."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, source_document_id, cross_court_dockets FROM parsed.dockets "
            "WHERE court_type_derived = %s AND cross_court_dockets IS NOT NULL",
            (_MC_COURT_TYPE,),
        )
        return list(cur.fetchall())


def _link_row(
    *,
    source_docket_id: str,
    target_docket_number: str,
    target_docket_id: str | None,
) -> dict[str, object]:
    """A ``parsed.docket_links``-shaped row (held_for_court / cross_court_dockets)."""
    return {
        "source_docket_id": source_docket_id,
        "target_docket_number": target_docket_number,
        "target_docket_id": target_docket_id,
        "link_type": HELD_FOR_COURT,
        "evidence_source": CROSS_COURT_DOCKETS,
    }


def _unresolvable_review_item(
    *,
    source_document_id: str,
    parsed_docket_id: str,
    subcase: str,
    raw_value: str,
    match_count: int | None = None,
) -> dict[str, object]:
    """Build an ``unresolvable_cross_court_reference`` review item payload.

    Docket-grain (empty locator → one item per source docket), reason code the
    generic ``REVIEW_NEEDED`` (linkage is informational; AC4). The malformed vs
    ambiguous-target sub-case is carried in ``candidate_context`` (RF3), never as a
    separate reason code.
    """
    candidate_context: dict[str, object] = {"subcase": subcase}
    if match_count is not None:
        candidate_context["match_count"] = match_count
    return build_review_item(
        source_document_id=source_document_id,
        item_type=UNRESOLVABLE_CROSS_COURT_REFERENCE,
        severity=SEVERITY_MEDIUM,
        reason_code=REVIEW_NEEDED,
        locator=(),
        parsed_docket_id=parsed_docket_id,
        raw_value=raw_value,
        candidate_context=candidate_context,
    )


def collect_docket_links(
    conn: psycopg.Connection,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, int]]:
    """Read MC held dockets and build link rows + review items (no writes here).

    Returns ``(link_rows, review_items, counts)``:

    - ``link_rows``   — one per parsed target: resolved (target FK set) or unresolved
      (target FK null, out-of-corpus). Ambiguous / malformed targets produce NO link.
    - ``review_items`` — ``unresolvable_cross_court_reference`` payloads for malformed
      strings and ambiguous (≥2-match) targets.
    - ``counts``      — source docket + resolved / unresolved / review tallies for the
      run report and the RF4 reconciliation.
    """
    dockets = _load_mc_source_dockets(conn)

    link_rows: list[dict[str, object]] = []
    review_items: list[dict[str, object]] = []
    resolved = unresolved = review_malformed = review_ambiguous = 0

    for docket in dockets:
        source_docket_id = str(docket["id"])
        source_document_id = str(docket["source_document_id"])
        raw = docket["cross_court_dockets"]
        raw_str = raw if isinstance(raw, str) else str(raw)

        targets = parse_cross_court_targets(raw_str)
        if not targets:
            # Non-null capture with no §6.9-bounded docket number -> review, no link.
            review_malformed += 1
            review_items.append(
                _unresolvable_review_item(
                    source_document_id=source_document_id,
                    parsed_docket_id=source_docket_id,
                    subcase=_SUBCASE_MALFORMED,
                    raw_value=raw_str,
                )
            )
            continue

        for target_docket_number in targets:
            matches = _resolve_target(conn, target_docket_number)
            if len(matches) >= 2:
                # Ambiguous target lookup -> review, no link, no unresolved row
                # (unresolved is reserved for the 0-match / out-of-corpus case).
                review_ambiguous += 1
                review_items.append(
                    _unresolvable_review_item(
                        source_document_id=source_document_id,
                        parsed_docket_id=source_docket_id,
                        subcase=_SUBCASE_AMBIGUOUS,
                        raw_value=target_docket_number,
                        match_count=len(matches),
                    )
                )
                continue
            target_docket_id = matches[0] if matches else None
            if target_docket_id is None:
                unresolved += 1
            else:
                resolved += 1
            link_rows.append(
                _link_row(
                    source_docket_id=source_docket_id,
                    target_docket_number=target_docket_number,
                    target_docket_id=target_docket_id,
                )
            )

    counts = {
        "source_mc_dockets_with_ref": len(dockets),
        "links_total": len(link_rows),
        "resolved": resolved,
        "unresolved": unresolved,
        "review_malformed": review_malformed,
        "review_ambiguous": review_ambiguous,
    }
    return link_rows, review_items, counts


def insert_docket_links(
    conn: psycopg.Connection, link_rows: Sequence[Mapping[str, object]]
) -> None:
    """Rebuild ``parsed.docket_links`` (SD 6 delete-and-reinsert) in the caller's tx.

    The whole table is replaced each build so it always reflects the current corpus +
    linker logic; on an unchanged corpus the row set is identical (idempotent link
    content). Does not commit. The ``UNIQUE(source_docket_id, target_docket_number,
    link_type)`` constraint guards against an intra-build duplicate (a logic bug would
    surface as a violation, not a silent dup).
    """
    columns = (
        "source_docket_id",
        "target_docket_number",
        "target_docket_id",
        "link_type",
        "evidence_source",
    )
    placeholders = ", ".join(f"%({col})s" for col in columns)
    column_list = ", ".join(columns)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM parsed.docket_links")
        if not link_rows:
            return
        cur.executemany(
            f"INSERT INTO parsed.docket_links ({column_list}) VALUES ({placeholders})",  # noqa: S608 - columns are module constants, never input
            list(link_rows),
        )
