"""Outcome-fact eligibility + row construction (Task 23.2).

This module owns the pure, DB-free decision that turns the three live
matcher/mapper/resolver results for one DISPOSED charge into a
``fact.charge_outcomes`` row: the eligibility trio (``mvp_eligible`` /
``public_eligible`` / ``judge_specific_eligible``), the fact's ``review_needed``
boolean, and the ``ineligibility_reason_codes`` array. Eligibility is defined
VERBATIM by Sprint 5 plan Task 23.2 AC 2:

- ``mvp_eligible`` = ``disposition_date`` present AND >= 2025-01-01.
- ``public_eligible`` = ``mvp_eligible`` AND the parent docket's ``filed_date``
  is present AND >= the configured filed-date floor (task filed-date-floor;
  default 2025-01-01, null fail-closed) AND the charge match method is one of
  ``{exact, alias, statute}`` AND the outcome category is public AND the fact's
  ``review_needed`` is False.
- ``judge_specific_eligible`` = ``public_eligible`` AND the judge is attributed
  (23.1 method ``disposition_judge`` / ``assigned_judge_rule``).

There are NO numeric thresholds and NO invented "blocking-warning" list: the
fact's ``review_needed`` is DERIVED from the parser's own charge-grain warning
severity via the locked 18.1 ``warning_codes.derive_review_needed`` map — that map
IS the blocking set. The ``ineligibility_reason_codes`` array carries EVERY
applicable member of the committed 21.2 ``ELIGIBILITY_REASON_CODES`` vocabulary
(an eligible fact carries the empty array); no vocabulary is invented here.

The three upstream results are consumed UNCHANGED (imported, never reimplemented):
the 22.2 ``ChargeNormalizationResult``, the 22.4 ``OutcomeMappingResult``, and the
23.1 ``AttributionResult``. This module adds NO judge/charge/outcome logic of its
own; it only combines their verdicts into the fact row. Pure and DB-free except
:func:`insert_outcome_facts`, the single ``executemany`` write helper, so the
eligibility decision is tier-1 synthetic-testable with no database.

Console/log hygiene: this module returns structured rows and never prints; the
build orchestration prints counts + fixed codes only (never raw docket text).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import psycopg

from pipeline.fact_review_vocab import (
    BLOCKING_WARNING,
    CHARGE_NOT_NORMALIZED,
    DISPOSITION_DATE_BEFORE_MVP_WINDOW,
    DISPOSITION_DATE_MISSING,
    DISPOSITION_NOT_MAPPED,
    FILED_DATE_BEFORE_FLOOR,
    FILED_DATE_MISSING,
    JUDGE_NOT_ATTRIBUTED,
    OUTCOME_CATEGORY_NOT_PUBLIC,
    REVIEW_NEEDED,
)
from pipeline.facts.judge_attribution import METHOD_NONE, AttributionResult
from pipeline.normalization.models import ChargeNormalizationResult
from pipeline.normalization.outcome_mapper import OutcomeMappingResult
from pipeline.normalization.vocab import (
    MATCH_METHOD_ALIAS,
    MATCH_METHOD_EXACT,
    MATCH_METHOD_STATUTE,
    NORM_STATUTE_TEXT_CONFLICT,
)
from pipeline.warning_codes import derive_review_needed

# --- Locked constants (Sprint 5 plan Task 23.2 AC 2 + Task 21.2 schema) ------
# The MVP coverage window opens 2025-01-01 (Sprint 5 plan). A disposition on or
# after this date is in-window; the window gates ``mvp_eligible`` only — a
# pre-window charge is STILL written as a fact with its real date, just marked
# ``mvp_eligible = False`` (the date is never dropped; aggregation enforces the
# window downstream in Sprint 7).
MVP_WINDOW_START = date(2025, 1, 1)

# The filed-date floor (task filed-date-floor, plan-approved 2026-07-16): a fact
# is publicly eligible only if its parent docket's ``filed_date`` is on or after
# this floor (null -> ineligible, fail-closed). Gates ``public_eligible`` ONLY —
# ``mvp_eligible`` keeps its single event-date meaning. This is the named
# configuration default the ``--filed-date-floor`` CLI flag overrides; the
# evaluators read the threaded value and carry no date literal. DELIBERATELY a
# parallel constant to the aggregation-time ``DATA_START_DATE_DEFAULT``
# (aggregates/generate.py): the event-date window there is untouched and NOT
# consolidated with this filed-date floor — the floor is additive at the fact
# layer, and sharing the constant would couple the fact layer to the aggregates
# module.
FILED_DATE_FLOOR_DEFAULT = date(2025, 1, 1)

# The charge match methods that count as a public-eligible normalization (AC 2):
# a clean single-identity match. ``pattern`` (never emitted by the 22.2 matcher)
# and ``unmatched`` / ``ambiguous`` are excluded by construction.
PUBLIC_CHARGE_MATCH_METHODS: frozenset[str] = frozenset(
    {MATCH_METHOD_EXACT, MATCH_METHOD_ALIAS, MATCH_METHOD_STATUTE}
)

# The fact-grain attribution-method constant for an outcome fact (Task 21.2:
# ``charge_row``). It labels the fact's GRAIN — one row per parsed charge — and
# is distinct from ``judge_attribution_method`` (the 23.1 per-charge verdict).
ATTRIBUTION_METHOD_CHARGE_ROW = "charge_row"

# ``outcome_match_method`` values. The 22.4 mapper is a single exact-match table
# (never fuzzy), so a mapped result is an ``exact`` table hit and the unmapped ->
# ``unknown`` sink is ``unmapped``.
OUTCOME_MATCH_METHOD_EXACT = "exact"
OUTCOME_MATCH_METHOD_UNMAPPED = "unmapped"


@dataclass(frozen=True)
class OutcomeFactEligibility:
    """The eligibility verdict for one disposed charge's outcome fact.

    ``ineligibility_reason_codes`` carries every applicable member of the 21.2
    ``ELIGIBILITY_REASON_CODES`` vocabulary; a fully-eligible fact carries the
    empty tuple. Invariants (asserted at construction): a judge-specific-eligible
    fact is public-eligible, a public-eligible fact is mvp-eligible, and the
    reason array is empty IFF the fact is judge-specific-eligible (the top of the
    eligibility chain — a public-eligible-but-unattributed fact still carries the
    ``judge_not_attributed`` reason).
    """

    mvp_eligible: bool
    public_eligible: bool
    judge_specific_eligible: bool
    review_needed: bool
    ineligibility_reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.judge_specific_eligible and not self.public_eligible:
            raise ValueError("judge_specific_eligible implies public_eligible")
        if self.public_eligible and not self.mvp_eligible:
            raise ValueError("public_eligible implies mvp_eligible")
        if self.judge_specific_eligible == bool(self.ineligibility_reason_codes):
            raise ValueError(
                "reason codes are empty iff the fact is judge_specific_eligible"
            )


def evaluate_outcome_eligibility(
    *,
    disposition_date: date | None,
    filed_date: date | None,
    filed_date_floor: date,
    charge_result: ChargeNormalizationResult,
    outcome_result: OutcomeMappingResult,
    attribution: AttributionResult,
    charge_warning_codes: Sequence[str] = (),
) -> OutcomeFactEligibility:
    """Decide the eligibility trio + reason codes for one disposed charge (AC 2).

    Pure: given the three upstream verdicts (all consumed UNCHANGED), the
    disposition date, the parent docket's filed date + the configured filed-date
    floor, and the charge's charge-grain PARSER warning codes, it returns the
    :class:`OutcomeFactEligibility`. ``charge_warning_codes`` are the
    ``parsed.warnings`` codes for this charge (from the 11-code parser
    vocabulary); their review severity drives the fact's ``review_needed`` via the
    locked 18.1 map — no separate blocking list exists.
    """
    # review_needed: True iff any charge-grain parser warning is review-severity
    # (the locked 18.1 severity map; that map is the blocking set — AC 2).
    review_needed = derive_review_needed(charge_warning_codes)

    mvp_eligible = disposition_date is not None and disposition_date >= MVP_WINDOW_START
    # Filed-date floor: gates public_eligible ONLY (mvp_eligible keeps its single
    # event-date meaning). Null filed_date is fail-closed ineligible.
    filed_ok = filed_date is not None and filed_date >= filed_date_floor
    charge_public_match = charge_result.match_method in PUBLIC_CHARGE_MATCH_METHODS
    # The 22.4 result's ``public_eligible`` is the taxonomy ``public`` flag for the
    # mapped code (always False for the unmapped -> ``unknown`` sink).
    category_public = outcome_result.public_eligible

    public_eligible = (
        mvp_eligible
        and filed_ok
        and charge_public_match
        and category_public
        and not review_needed
    )
    attributed = attribution.method != METHOD_NONE
    judge_specific_eligible = public_eligible and attributed

    reasons: list[str] = []

    # Date-window reasons (mutually exclusive; drive mvp-ineligibility).
    if disposition_date is None:
        reasons.append(DISPOSITION_DATE_MISSING)
    elif disposition_date < MVP_WINDOW_START:
        reasons.append(DISPOSITION_DATE_BEFORE_MVP_WINDOW)

    # Filed-date-floor reasons (mutually exclusive arms; drive public-
    # ineligibility only — never mvp).
    if filed_date is None:
        reasons.append(FILED_DATE_MISSING)
    elif filed_date < filed_date_floor:
        reasons.append(FILED_DATE_BEFORE_FLOOR)

    # Charge-normalization reasons.
    if not charge_public_match:
        reasons.append(CHARGE_NOT_NORMALIZED)
    if NORM_STATUTE_TEXT_CONFLICT in charge_result.warnings:
        # The statute/text-conflict subclass (22.2). Additive to
        # charge_not_normalized (the conflict also yields an ambiguous match).
        reasons.append(BLOCKING_WARNING)

    # Outcome-mapping reasons (mutually exclusive).
    if not outcome_result.mapped:
        reasons.append(DISPOSITION_NOT_MAPPED)
    elif not category_public:
        reasons.append(OUTCOME_CATEGORY_NOT_PUBLIC)

    # A review-severity parser warning is its own machine-readable reason.
    if review_needed:
        reasons.append(REVIEW_NEEDED)

    # Judge attribution is the SPECIFIC gate on judge_specific_eligible: it is a
    # reason only when the fact is otherwise public-eligible but unattributed
    # (when the fact is already public-ineligible, the public reasons explain it).
    if public_eligible and not attributed:
        reasons.append(JUDGE_NOT_ATTRIBUTED)

    return OutcomeFactEligibility(
        mvp_eligible=mvp_eligible,
        public_eligible=public_eligible,
        judge_specific_eligible=judge_specific_eligible,
        review_needed=review_needed,
        ineligibility_reason_codes=tuple(reasons),
    )


def build_outcome_fact_row(
    *,
    build_run_id: str,
    parsed_charge_id: str,
    parsed_docket_id: str,
    disposition_date: date | None,
    charge_result: ChargeNormalizationResult,
    outcome_result: OutcomeMappingResult,
    attribution: AttributionResult,
    eligibility: OutcomeFactEligibility,
    taxonomy_version: str,
) -> dict[str, object]:
    """Assemble the full ``fact.charge_outcomes`` column dict for one charge.

    Pure. Every column of the immutable fact row is populated here (``id`` and
    ``created_at`` are DB defaults). ``normalized_charge_id`` / ``normalized_judge_id``
    are NULL on an unmatched charge / unattributed judge (both are legitimate
    ineligible-fact states). ``judge_attribution_method`` carries the 23.1 verdict
    verbatim (``disposition_judge`` / ``assigned_judge_rule`` / ``none``).
    """
    return {
        "build_run_id": build_run_id,
        "parsed_charge_id": parsed_charge_id,
        "parsed_docket_id": parsed_docket_id,
        "normalized_charge_id": charge_result.normalized_id,
        "outcome_category_code": outcome_result.outcome_code,
        "disposition_date": disposition_date,
        "normalized_judge_id": attribution.normalized_judge_id,
        "judge_attribution_method": attribution.method,
        "attribution_method": ATTRIBUTION_METHOD_CHARGE_ROW,
        "charge_match_method": charge_result.match_method,
        "outcome_match_method": (
            OUTCOME_MATCH_METHOD_EXACT
            if outcome_result.mapped
            else OUTCOME_MATCH_METHOD_UNMAPPED
        ),
        "mvp_eligible": eligibility.mvp_eligible,
        "public_eligible": eligibility.public_eligible,
        "judge_specific_eligible": eligibility.judge_specific_eligible,
        "ineligibility_reason_codes": list(eligibility.ineligibility_reason_codes),
        "review_needed": eligibility.review_needed,
        "taxonomy_version": taxonomy_version,
    }


# The immutable column order for the INSERT (id + created_at are DB defaults).
_INSERT_COLUMNS = (
    "build_run_id",
    "parsed_charge_id",
    "parsed_docket_id",
    "normalized_charge_id",
    "outcome_category_code",
    "disposition_date",
    "normalized_judge_id",
    "judge_attribution_method",
    "attribution_method",
    "charge_match_method",
    "outcome_match_method",
    "mvp_eligible",
    "public_eligible",
    "judge_specific_eligible",
    "ineligibility_reason_codes",
    "review_needed",
    "taxonomy_version",
)


def insert_outcome_facts(
    conn: psycopg.Connection, rows: Sequence[Mapping[str, object]]
) -> int:
    """Insert outcome-fact rows in one ``executemany``; return the count.

    Runs inside the caller's transaction (the run-lifecycle tx). Insert-only —
    the fact table is immutable (a rebuild is delete-and-reinsert under a new
    run). Does not commit; the caller owns the transaction boundary.
    """
    if not rows:
        return 0
    placeholders = ", ".join(f"%({col})s" for col in _INSERT_COLUMNS)
    columns = ", ".join(_INSERT_COLUMNS)
    with conn.cursor() as cur:
        cur.executemany(
            f"INSERT INTO fact.charge_outcomes ({columns}) VALUES ({placeholders})",  # noqa: S608 - columns are module constants, never input
            list(rows),
        )
    return len(rows)
