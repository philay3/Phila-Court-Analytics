"""Key-scoped closure of held-sourced review items (Task 29.3, AC 10).

Mechanism A (the ``HELD_FOR_COURT_DISPOSITIONS`` carve-out in the 22.4 outcome
mapper) stops GENERATING two review-item populations: the ``unmapped_disposition``
items for the four unmapped bind-over variant forms and the charge-grain
``unmapped_charge`` items on held-form charges (the fact-build loop skips a held
charge before any charge-grain review path runs). The queue is persistent and
status-preserving (SD 6), so the already-inserted rows stay ``open`` forever
unless consciously closed — this command is that conscious operation, ruled
conditional-on-separability at stage-2 adjudication (separability PROVEN in the
approved plan) and run by the operator post-publish.

Scope discipline (adjudicated, never widened here):

- ONLY item types ``unmapped_disposition`` and ``unmapped_charge``;
  ``missing_disposition_date`` is explicitly OUT of scope (the parser still
  emits its warning; those items keep regenerating by design).
- ONLY ``open`` items (a human-touched ``in_review`` item is never bulk-closed).
- KEY-scoped, never ILIKE-scoped: candidate ``dedup_key`` values are
  reconstructed from stable identifiers over the CURRENT corpus via the
  canonical 22.1 :func:`build_dedup_key` — held-form charges are selected by
  byte-exact membership in ``HELD_FOR_COURT_DISPOSITIONS``, imported from the
  outcome mapper (single authority; the five forms are never re-listed, so a
  future sixth-variant adjudication widens closure scope automatically).

Items close as ``superseded`` — the COL-4a precedent for "mechanically closed
because the generating condition no longer exists," distinct from human
``dismissed``. Idempotent: a closed item is no longer ``open``, so a re-run
selects zero. Destruction of triage state requires ``--confirm``; without it
the command is a DRY RUN printing the selection counts. One transaction.

Console/log hygiene: counts, item types, and statuses only — never raw values,
docket numbers, or key contents (keys embed source-document UUIDs; UUIDs are
synthetic, but keys are still not printed — counts suffice).
"""

from __future__ import annotations

import logging

import psycopg

from pipeline.fact_review_vocab import (
    STATUS_OPEN,
    STATUS_SUPERSEDED,
    UNMAPPED_CHARGE,
    UNMAPPED_DISPOSITION,
)
from pipeline.normalization.outcome_mapper import HELD_FOR_COURT_DISPOSITIONS
from pipeline.normalization.review_items import build_dedup_key

logger = logging.getLogger("pipeline.close_held_review_items")

# The two item types Mechanism A stops generating (AC 10 pinned scope).
CLOSABLE_ITEM_TYPES: tuple[str, ...] = (UNMAPPED_DISPOSITION, UNMAPPED_CHARGE)


def _held_charge_anchors(conn: psycopg.Connection) -> list[tuple[str, int]]:
    """``(source_document_id, charge_sequence)`` for every held-form charge.

    Byte-exact membership against the mapper's authority set — the same
    predicate that decides fact-skip, so closure scope tracks it exactly.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT d.source_document_id, c.sequence "
            "FROM parsed.charges c JOIN parsed.dockets d ON c.docket_id = d.id "
            "WHERE c.disposition_raw = ANY(%(held_forms)s)",
            {"held_forms": sorted(HELD_FOR_COURT_DISPOSITIONS)},
        )
        return [(str(sdid), int(seq)) for sdid, seq in cur.fetchall()]


def _candidate_keys(anchors: list[tuple[str, int]]) -> list[str]:
    """Every dedup key Mechanism A stops generating, via the canonical builder.

    Charge-grain composition: ``source_document_id / item_type /
    [charge_sequence]`` (fact_review_vocab's documented grain), one key per
    (held charge, closable type) pair.
    """
    return [
        build_dedup_key(sdid, item_type, (str(seq),))
        for sdid, seq in anchors
        for item_type in CLOSABLE_ITEM_TYPES
    ]


def run_close_held_review_items(conn: psycopg.Connection, *, confirm: bool) -> int:
    """Close the key-scoped held-sourced open items; return the exit code.

    Without ``--confirm``: dry run — print the selection counts by item type,
    write nothing. With it: flip exactly the selected rows ``open`` ->
    ``superseded`` in ONE transaction (the row count is asserted against the
    selection). Re-running after a confirm selects zero (idempotent).
    """
    with conn.transaction():
        anchors = _held_charge_anchors(conn)
        keys = _candidate_keys(anchors)

        by_type: dict[str, int] = dict.fromkeys(CLOSABLE_ITEM_TYPES, 0)
        selected_ids: list[str] = []
        if keys:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, item_type FROM review.queue_items "
                    "WHERE dedup_key = ANY(%(keys)s) AND status = %(open)s",
                    {"keys": keys, "open": STATUS_OPEN},
                )
                for item_id, item_type in cur.fetchall():
                    selected_ids.append(str(item_id))
                    by_type[item_type] += 1

        if confirm and selected_ids:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE review.queue_items SET status = %(superseded)s "
                    "WHERE id = ANY(%(ids)s) AND status = %(open)s",
                    {
                        "superseded": STATUS_SUPERSEDED,
                        "ids": selected_ids,
                        "open": STATUS_OPEN,
                    },
                )
                assert cur.rowcount == len(selected_ids)

    mode = "closed" if confirm else "would_close"
    print(
        f"held_form_charges={len(anchors)} candidate_keys={len(keys)} "
        f"{mode}={len(selected_ids)}"
    )
    print(f"{mode}_by_type:")
    for item_type in CLOSABLE_ITEM_TYPES:
        print(f"  {item_type:24} {by_type[item_type]}")
    if not confirm:
        logger.info("dry run: nothing closed; pass --confirm to execute")
    return 0
