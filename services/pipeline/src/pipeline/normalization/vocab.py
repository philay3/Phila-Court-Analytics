"""Normalization vocabularies + ``review_needed`` derivation (Task 22.1).

Two closed, single-source-of-truth vocabularies for the normalization layer,
plus the derived-boolean ``review_needed`` map. This is the analog of
``warning_codes.py`` for normalization: no other module defines these strings,
every matcher (22.2/22.3/22.4) and the money extractor import them from here,
and each set is closed. Additions require plan-level approval in the planning
chat — do not invent members in code.

Sprint 5 SD 2 (locked): there is NO numeric confidence anywhere in this layer.
Matching produces a CATEGORICAL ``match_method`` plus structured warning codes;
``review_needed`` is a DERIVED boolean off the documented map below, never a
0.00-1.00 score and never a threshold.

Two vocabularies are defined:

1. ``MATCH_METHODS`` — the six-value categorical outcome of a normalization
   match (pinned decision 2), locked at exactly these values.
   ``MATCHED_METHODS`` is the subset that carries a normalized identity
   (pinned decision 4).
2. ``NORM_WARNING_CODES`` — the closed normalization warning vocabulary (pinned
   decision 5). Distinct axis from the parser warning vocabulary
   (``warning_codes.py``); this task does NOT extend that one. Warnings on a
   result are a tuple of these codes only — structural context (docket, charge
   sequence, field) belongs to the review-item locator, not the per-value
   result.

``review_needed`` derivation (pinned decision 6) is DATA — the two constant sets
below — plus the thin :func:`derive_review_needed`. The arms:

- ``unmatched`` -> True (in ``_ALWAYS_REVIEW_METHODS``)
- ``ambiguous`` -> True (in ``_ALWAYS_REVIEW_METHODS``)
- a matched method (``exact``/``alias``/``statute``/``pattern``) -> True iff a
  warning from ``NORM_BLOCKING_WARNINGS`` is present, else False.
"""

from __future__ import annotations

from collections.abc import Iterable

# --- 1. Match methods (pinned decision 2; locked at exactly six values) ------
MATCH_METHOD_EXACT = "exact"
MATCH_METHOD_ALIAS = "alias"
MATCH_METHOD_STATUTE = "statute"
MATCH_METHOD_PATTERN = "pattern"
MATCH_METHOD_UNMATCHED = "unmatched"
MATCH_METHOD_AMBIGUOUS = "ambiguous"

MATCH_METHODS: frozenset[str] = frozenset(
    {
        MATCH_METHOD_EXACT,
        MATCH_METHOD_ALIAS,
        MATCH_METHOD_STATUTE,
        MATCH_METHOD_PATTERN,
        MATCH_METHOD_UNMATCHED,
        MATCH_METHOD_AMBIGUOUS,
    }
)

# The subset that carries a normalized identity (pinned decision 4): a result
# with one of these methods MUST have normalized_id + display_name; a result
# with ``unmatched`` or ``ambiguous`` MUST NOT.
MATCHED_METHODS: frozenset[str] = frozenset(
    {
        MATCH_METHOD_EXACT,
        MATCH_METHOD_ALIAS,
        MATCH_METHOD_STATUTE,
        MATCH_METHOD_PATTERN,
    }
)

# --- 2. Normalization warning codes (pinned decision 5; locked at five) ------
NORM_UNMATCHED = "NORM_UNMATCHED"
NORM_AMBIGUOUS = "NORM_AMBIGUOUS"
NORM_STATUTE_TEXT_CONFLICT = "NORM_STATUTE_TEXT_CONFLICT"
NORM_UNPARSEABLE_AMOUNT = "NORM_UNPARSEABLE_AMOUNT"
NORM_EMPTY_INPUT = "NORM_EMPTY_INPUT"

NORM_WARNING_CODES: frozenset[str] = frozenset(
    {
        NORM_UNMATCHED,
        NORM_AMBIGUOUS,
        NORM_STATUTE_TEXT_CONFLICT,
        NORM_UNPARSEABLE_AMOUNT,
        NORM_EMPTY_INPUT,
    }
)

# --- 3. review_needed derivation (pinned decision 6; data, not scattered) ----
# Methods that ALWAYS need review regardless of warnings: an unmatched value has
# no normalized identity, and an ambiguous value has more than one candidate — a
# human resolves both.
_ALWAYS_REVIEW_METHODS: frozenset[str] = frozenset(
    {MATCH_METHOD_UNMATCHED, MATCH_METHOD_AMBIGUOUS}
)

# The blocking-warning set: warnings whose presence flags an OTHERWISE-matched
# result for review. Only NORM_STATUTE_TEXT_CONFLICT can co-occur with a matched
# method and warrants review (a matched charge whose statute and text disagree).
# NORM_UNMATCHED / NORM_AMBIGUOUS / NORM_EMPTY_INPUT only accompany methods that
# are already always-review, and NORM_UNPARSEABLE_AMOUNT lives on the money path
# (which has no match_method), so none of them belong here.
NORM_BLOCKING_WARNINGS: frozenset[str] = frozenset({NORM_STATUTE_TEXT_CONFLICT})


def derive_review_needed(match_method: str, warning_codes: Iterable[str]) -> bool:
    """Derive ``review_needed`` from the documented map (pinned decision 6).

    ``unmatched``/``ambiguous`` -> True; a matched method -> True iff any code in
    ``warning_codes`` is a blocking warning, else False. An unknown method or an
    unknown warning code raises rather than being silently ignored.
    """
    if match_method not in MATCH_METHODS:
        raise ValueError(f"unknown match method: {match_method!r}")
    codes = tuple(warning_codes)
    for code in codes:
        if code not in NORM_WARNING_CODES:
            raise ValueError(f"unknown normalization warning code: {code!r}")
    if match_method in _ALWAYS_REVIEW_METHODS:
        return True
    return any(code in NORM_BLOCKING_WARNINGS for code in codes)
