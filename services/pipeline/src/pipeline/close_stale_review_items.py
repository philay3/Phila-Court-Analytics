"""Generic stale-closure of review items whose generating condition is gone.

The 29.3 closure tool (``close_held_review_items``) swept exactly one stale
class: items the held-for-court mapper carve-out stopped generating. This is
the adjudicated generalization (review-queue closure package, 2026-07-25,
ruling R2): an ``open`` item of an in-scope type is STALE iff its ``dedup_key``
is NOT in the REGENERATION SET — the set of dedup keys the current fact
build's review paths would emit over the current corpus. Whatever fixed the
condition (a roster expansion, a mapper-table addition, a held-variant
adjudication, an extinct raw string), the item stops regenerating and this
tool is the one conscious closure operation for it. An item whose key IS
regenerated is LIVE and is never touched — under the dedup design a closed
row occupies its UNIQUE key permanently (inserts are ``ON CONFLICT DO
NOTHING``), so false-positive closure never self-heals and is THE failure
mode this predicate is designed against (process ruling PR-6).

The predicate IS the build, by import (single-authority rule; never SQL text
matching): the walk over ``parsed.charges`` mirrors the ``build_facts``
charge loop's decision sequence exactly, using the same canonical functions —

- ``OutcomeMapper.map`` — the held/undisposed arm (``None``) skips the charge
  before ANY charge-grain review path runs, exactly as the build loop does;
- ``build_charge_review_item`` over ``ChargeMatcher.match`` — the
  ``unmapped_charge`` emission decision and its dedup key;
- ``build_outcome_review_item`` — the ``unmapped_disposition`` emission
  decision and its dedup key.

``build_facts`` itself only SEQUENCES these calls; every emission decision
and the key composition (22.1 ``build_dedup_key``) live in the imported
functions, so a future matcher / mapper / held-set change widens or narrows
the regeneration set here automatically.

Scope discipline (pinned at adjudication, never widened here):

- ONLY item types ``unmapped_charge`` and ``unmapped_disposition``. Every
  other type is out of scope (``missing_disposition_date`` keeps regenerating
  by design and is the standing expected-open floor).
- ONLY ``open`` items — a human-touched ``in_review`` item is never
  bulk-closed.
- Close target is ``superseded`` (the COL-4a/29.3 precedent for mechanical
  closure), never ``dismissed``.

Dry run by default; ``--confirm`` to execute. One transaction with a rowcount
assert; idempotent (a closed item is no longer ``open``, so a re-run selects
zero). Console prints counts by type plus a by-``raw_value`` top list —
CPCMS state vocabulary is printable; dedup keys and UUIDs are not.
"""

from __future__ import annotations

import logging
from collections import Counter

import psycopg

from pipeline.fact_review_vocab import (
    STATUS_OPEN,
    STATUS_SUPERSEDED,
    UNMAPPED_CHARGE,
    UNMAPPED_DISPOSITION,
)
from pipeline.normalization.charge_matcher import (
    ChargeMatcher,
    build_charge_review_item,
)
from pipeline.normalization.charge_roster_loader import load_charge_roster
from pipeline.normalization.outcome_mapper import (
    OutcomeMapper,
    build_outcome_review_item,
    load_taxonomy_snapshot,
)

logger = logging.getLogger("pipeline.close_stale_review_items")

# The two item types in scope (adjudicated; never widened in code).
CLOSABLE_ITEM_TYPES: tuple[str, ...] = (UNMAPPED_CHARGE, UNMAPPED_DISPOSITION)

# How many distinct raw_value lines the console report shows.
_TOP_RAW_VALUES = 15


def _regeneration_keys(
    conn: psycopg.Connection,
    *,
    charge_matcher: ChargeMatcher,
    mapper: OutcomeMapper,
) -> set[str]:
    """Every in-scope dedup key the current build would emit over the corpus.

    Mirrors the ``build_facts`` charge loop's decision sequence with the same
    imported functions: the mapper's held/undisposed arm skips the charge
    entirely; otherwise the charge path may emit an ``unmapped_charge`` key
    (an ``ambiguous_charge`` item from the same builder is out of scope and
    dropped) and the outcome path may emit an ``unmapped_disposition`` key.
    """
    keys: set[str] = set()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT d.source_document_id, c.sequence, c.statute, c.offense, "
            "c.disposition_raw "
            "FROM parsed.charges c JOIN parsed.dockets d ON c.docket_id = d.id"
        )
        for sdid, sequence, statute, offense, disposition_raw in cur:
            outcome_result = mapper.map(disposition_raw)
            if outcome_result is None:
                # Held / undisposed arm: the build loop skips the charge before
                # any charge-grain review path runs — no keys of either type.
                continue
            source_document_id = str(sdid)
            charge_item = build_charge_review_item(
                charge_matcher.match(statute=statute, offense=offense),
                source_document_id=source_document_id,
                charge_sequence=int(sequence),
            )
            if charge_item is not None and charge_item["item_type"] == UNMAPPED_CHARGE:
                keys.add(str(charge_item["dedup_key"]))
            outcome_item = build_outcome_review_item(
                outcome_result,
                source_document_id=source_document_id,
                charge_sequence=int(sequence),
            )
            if outcome_item is not None:
                keys.add(str(outcome_item["dedup_key"]))
    return keys


def close_stale_review_items(
    conn: psycopg.Connection,
    *,
    charge_matcher: ChargeMatcher,
    mapper: OutcomeMapper,
    confirm: bool,
) -> int:
    """Close the stale in-scope open items; return the exit code.

    Without ``confirm``: dry run — print the selection, write nothing. With
    it: flip exactly the selected rows ``open`` -> ``superseded`` in ONE
    transaction (row count asserted against the selection).
    """
    with conn.transaction():
        regeneration_keys = _regeneration_keys(
            conn, charge_matcher=charge_matcher, mapper=mapper
        )

        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, item_type, raw_value, dedup_key FROM review.queue_items "
                "WHERE item_type = ANY(%(types)s) AND status = %(open)s",
                {"types": list(CLOSABLE_ITEM_TYPES), "open": STATUS_OPEN},
            )
            open_rows = cur.fetchall()

        stale = [
            (str(item_id), str(item_type), raw_value)
            for item_id, item_type, raw_value, dedup_key in open_rows
            if str(dedup_key) not in regeneration_keys
        ]

        if confirm and stale:
            stale_ids = [item_id for item_id, _, _ in stale]
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE review.queue_items SET status = %(superseded)s "
                    "WHERE id = ANY(%(ids)s) AND status = %(open)s",
                    {
                        "superseded": STATUS_SUPERSEDED,
                        "ids": stale_ids,
                        "open": STATUS_OPEN,
                    },
                )
                assert cur.rowcount == len(stale_ids)

    by_type = Counter(item_type for _, item_type, _ in stale)
    by_raw: Counter[tuple[str, str]] = Counter(
        (item_type, raw_value if raw_value is not None else "<null>")
        for _, item_type, raw_value in stale
    )

    mode = "closed" if confirm else "would_close"
    print(
        f"regeneration_keys={len(regeneration_keys)} "
        f"open_in_scope={len(open_rows)} {mode}={len(stale)}"
    )
    print(f"{mode}_by_type:")
    for item_type in CLOSABLE_ITEM_TYPES:
        print(f"  {item_type:24} {by_type.get(item_type, 0)}")
    print(f"{mode}_by_raw_value (top {_TOP_RAW_VALUES} of {len(by_raw)} distinct):")
    for (item_type, raw_value), n in by_raw.most_common(_TOP_RAW_VALUES):
        print(f"  {n:6}  {item_type:20} {raw_value}")
    remaining = len(by_raw) - min(len(by_raw), _TOP_RAW_VALUES)
    if remaining:
        print(f"  ... and {remaining} more distinct values")
    if not confirm:
        logger.info("dry run: nothing closed; pass --confirm to execute")
    return 0


def run_close_stale_review_items(
    conn: psycopg.Connection, database_url: str, *, confirm: bool
) -> int:
    """CLI entry: load the canonical matcher + mapper and run the closure.

    Loads exactly what ``build_facts`` loads for the two in-scope review paths
    — the active charge roster and the committed taxonomy — so the predicate
    tracks the build's own authorities.
    """
    charge_matcher = ChargeMatcher(load_charge_roster(database_url))
    mapper = OutcomeMapper(load_taxonomy_snapshot())
    return close_stale_review_items(
        conn, charge_matcher=charge_matcher, mapper=mapper, confirm=confirm
    )
