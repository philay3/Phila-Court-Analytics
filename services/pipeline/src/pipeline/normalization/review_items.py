"""``review.queue_items`` payload builder + dedup-key derivation (Task 22.1).

This module is the CANONICAL and ONLY implementation of dedup-key derivation
project-wide, from this task forward (REQUIRED FIX 1). Every future consumer
(22.2 charge, 22.3 judge, 22.4 outcome/sentencing) imports :func:`build_review_item`
from here rather than re-deriving a key. ``fact_review_vocab.py`` DOCUMENTS the
composition (its module docstring, lines 32-57) and delegates the implementation
to the 22.1 helpers; this is that implementation. ``fact_review_vocab`` is
consumed (its vocabularies imported), never edited.

Every vocabulary-typed field on a ``review.queue_items`` row is validated
against its ``fact_review_vocab`` set at construction (REQUIRED FIX 3) — invalid
raises, in both directions:

- ``item_type``   -> ``REVIEW_ITEM_TYPES``
- ``severity``    -> ``REVIEW_SEVERITIES``
- ``reason_code`` -> ``ELIGIBILITY_REASON_CODES``
- ``status``      -> ``REVIEW_ITEM_STATUSES`` (defaults to the ``open`` default)

The dedup key is composed from STABLE identifiers only — ``source_document_id``
(a ``raw.*`` UUID that survives parsed reloads), ``item_type``, and a structural
``locator`` — and incorporates NO ``parsed.*`` UUID by construction (those
reloads re-mint). The parsed pointers (``parsed_docket_id`` etc.) are stored as
row columns for re-anchoring but are deliberately NOT part of the key.

NO DB access, NO psycopg: this builds an in-memory payload dict only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pipeline.fact_review_vocab import (
    ELIGIBILITY_REASON_CODES,
    REVIEW_ITEM_STATUS_DEFAULT,
    REVIEW_ITEM_STATUSES,
    REVIEW_ITEM_TYPES,
    REVIEW_SEVERITIES,
)

# The dedup-key part separator: the ASCII unit separator (\x1f), defined here
# exactly once (REQUIRED FIX 1b). It cannot appear in any structural part, so
# the join is unambiguous. See the composition documented in
# fact_review_vocab.py (module docstring, lines 32-57).
DEDUP_KEY_SEPARATOR = "\x1f"


def build_dedup_key(
    source_document_id: str,
    item_type: str,
    locator: Sequence[str] = (),
) -> str:
    """Derive a ``review.queue_items.dedup_key`` (canonical implementation).

    Composition (per fact_review_vocab.py docstring, lines 32-57)::

        dedup_key = DEDUP_KEY_SEPARATOR.join(
            [source_document_id, item_type, *locator]
        )

    ``source_document_id`` is the one UUID stable across parsed reloads;
    ``item_type`` is a review item type; ``locator`` is zero or more structural
    locator parts. NO ``parsed.*`` UUID enters the key by construction. Every
    part must be a non-empty string with no embedded separator.
    """
    parts = [source_document_id, item_type, *locator]
    for part in parts:
        if not isinstance(part, str) or part == "":
            raise ValueError("dedup-key parts must be non-empty strings")
        if DEDUP_KEY_SEPARATOR in part:
            raise ValueError("dedup-key parts must not contain the separator")
    return DEDUP_KEY_SEPARATOR.join(parts)


def build_review_item(
    *,
    source_document_id: str,
    item_type: str,
    severity: str,
    reason_code: str,
    locator: Sequence[str] = (),
    status: str = REVIEW_ITEM_STATUS_DEFAULT,
    parsed_docket_id: str | None = None,
    parsed_charge_id: str | None = None,
    parsed_sentence_id: str | None = None,
    entity_type: str | None = None,
    raw_value: str | None = None,
    candidate_context: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build a ``review.queue_items``-shaped payload (pinned decision 8).

    Validates every vocabulary-typed field against its ``fact_review_vocab`` set
    (invalid raises) and derives ``dedup_key`` via :func:`build_dedup_key` — no
    ``parsed.*`` UUID enters the key. The returned dict mirrors the writable
    columns of ``review.queue_items``; DB-generated columns (``id``,
    ``created_at``, ``updated_at``) are not included.

    ``raw_value`` and ``candidate_context`` are structural-only per the table's
    column comments — never defendant-identifying content; this builder does not
    inspect them but callers must honor that posture.
    """
    if item_type not in REVIEW_ITEM_TYPES:
        raise ValueError(f"unknown review item_type: {item_type!r}")
    if severity not in REVIEW_SEVERITIES:
        raise ValueError(f"unknown review severity: {severity!r}")
    if reason_code not in ELIGIBILITY_REASON_CODES:
        raise ValueError(f"unknown review reason_code: {reason_code!r}")
    if status not in REVIEW_ITEM_STATUSES:
        raise ValueError(f"unknown review status: {status!r}")

    dedup_key = build_dedup_key(source_document_id, item_type, locator)

    return {
        "item_type": item_type,
        "severity": severity,
        "source_document_id": source_document_id,
        "parsed_docket_id": parsed_docket_id,
        "parsed_charge_id": parsed_charge_id,
        "parsed_sentence_id": parsed_sentence_id,
        "entity_type": entity_type,
        "raw_value": raw_value,
        "candidate_context": candidate_context,
        "reason_code": reason_code,
        "status": status,
        "dedup_key": dedup_key,
    }
