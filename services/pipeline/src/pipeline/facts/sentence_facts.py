"""Sentence-fact eligibility + row construction (Task 23.3).

The sibling of :mod:`pipeline.facts.outcome_facts`: the pure, DB-free decision
that turns one 22.5 :class:`SentencingComponentResult` — plus the parent outcome
fact it hangs off and the parsed sentence row it mirrors — into a
``fact.charge_sentences`` row. One row per parsed sentence component on every
disposed charge that received a 23.2 outcome fact; creation is NEVER gated by
eligibility (create-all-mark-eligibility, exactly the 23.2 pattern), and
components are NEVER collapsed or merged (1:1).

Eligibility trio (Sprint 5 plan Task 23.3 PD5; SD 15 ties the date gate to the
parent's):

- ``mvp_eligible`` = ``sentence_date`` present AND >= 2025-01-01 (the SAME
  :data:`~pipeline.facts.outcome_facts.MVP_WINDOW_START`, imported unchanged).
- ``public_eligible`` = parent outcome fact ``public_eligible`` AND
  ``mvp_eligible`` AND the base sentencing category is public AND the component
  match method is a clean single-identity match (:data:`PUBLIC_COMPONENT_MATCH_METHODS`
  = ``{exact}``) AND the fact's ``review_needed`` is False. The docket/charge
  blocking-warning gate is inherited TRANSITIVELY via "parent must be
  public_eligible" — never re-implemented here.
- ``judge_specific_eligible`` = ``public_eligible`` AND the inherited judge
  attribution is present.

There are NO numeric thresholds. ``ineligibility_reason_codes`` carries every
applicable member of the committed 21.2 ``ELIGIBILITY_REASON_CODES`` vocabulary
(an eligible fact carries the empty tuple); NO vocabulary is invented here — the
sentence-grain codes were provisioned in 21.2/22.5.

The 22.5 mapper is consumed UNCHANGED: it emits no ``match_method`` field (its
base is an exact-match table only), so :func:`derive_component_match_method`
projects its ``base.mapped`` / ``ambiguous_community_service`` verdict onto the
locked 22.1 ``MATCH_METHODS`` vocabulary — ``unmatched`` for an unmapped base,
``ambiguous`` for a bare-``N hours`` component, else ``exact``. Only ``exact``
is public-eligible-clean, mirroring the 23.2 charge rule.

Judge fields are INHERITED verbatim from the parent outcome fact (SD 1 / 23.1
AC2): sentences carry no judge of their own. Durations
(``min_days``/``max_days``/``min_assumed``) are carried AS PARSED — this module
never reads or re-parses them.

Pure and DB-free except :func:`insert_sentence_facts`, the single ``executemany``
write helper, so the eligibility decision is tier-1 synthetic-testable with no
database. Returns structured rows and never prints.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import psycopg

from pipeline.fact_review_vocab import (
    JUDGE_NOT_ATTRIBUTED,
    MONEY_AMOUNT_UNPARSEABLE,
    PARENT_OUTCOME_INELIGIBLE,
    REVIEW_NEEDED,
    SENTENCE_DATE_BEFORE_MVP_WINDOW,
    SENTENCE_DATE_MISSING,
    SENTENCE_DURATION_UNPARSEABLE,
    SENTENCING_CATEGORY_NOT_PUBLIC,
    SENTENCING_COMPONENT_NOT_NORMALIZED,
)
from pipeline.facts.judge_attribution import METHOD_NONE
from pipeline.facts.outcome_facts import MVP_WINDOW_START
from pipeline.normalization.sentencing_mapper import SentencingComponentResult
from pipeline.normalization.vocab import (
    MATCH_METHOD_AMBIGUOUS,
    MATCH_METHOD_EXACT,
    MATCH_METHOD_UNMATCHED,
)

# The fact-grain attribution-method constant for a sentence fact (Task 21.2:
# ``charge_component``). It labels the fact's GRAIN — one row per parsed sentence
# component — and is distinct from ``judge_attribution_method`` (the parent's
# 23.1 verdict, inherited verbatim).
ATTRIBUTION_METHOD_CHARGE_COMPONENT = "charge_component"

# The component match methods that count as a public-eligible normalization: a
# clean single-identity exact-table hit. The 22.5 mapper's base is an exact-match
# table ONLY, so ``alias`` / ``statute`` / ``pattern`` are unreachable and
# ``unmatched`` / ``ambiguous`` are excluded by construction (mirrors the 23.2
# charge rule PUBLIC_CHARGE_MATCH_METHODS, narrowed to the single method the
# sentencing mapper can emit).
PUBLIC_COMPONENT_MATCH_METHODS: frozenset[str] = frozenset({MATCH_METHOD_EXACT})


def derive_component_match_method(result: SentencingComponentResult) -> str:
    """Project a 22.5 component result onto the locked 22.1 ``MATCH_METHODS``.

    The 22.5 mapper emits no ``match_method`` of its own; this reads its verdict:
    an unmapped base -> ``unmatched``; a bare ``N hours`` (ambiguous
    community-service) -> ``ambiguous``; otherwise a clean exact-table hit ->
    ``exact``. Pure; the mapper is consumed unchanged.
    """
    if not result.base.mapped:
        return MATCH_METHOD_UNMATCHED
    if result.ambiguous_community_service:
        return MATCH_METHOD_AMBIGUOUS
    return MATCH_METHOD_EXACT


@dataclass(frozen=True)
class SentenceFactEligibility:
    """The eligibility verdict for one sentence component's fact.

    ``ineligibility_reason_codes`` carries every applicable member of the 21.2
    ``ELIGIBILITY_REASON_CODES`` vocabulary; a fully-eligible fact carries the
    empty tuple. Invariants (asserted at construction, mirroring the outcome
    fact): a judge-specific-eligible fact is public-eligible, a public-eligible
    fact is mvp-eligible, and the reason array is empty IFF the fact is
    judge-specific-eligible (the top of the chain — a public-eligible-but-
    unattributed fact still carries the ``judge_not_attributed`` reason).
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


def evaluate_sentence_eligibility(
    *,
    sentence_date: date | None,
    result: SentencingComponentResult,
    component_match_method: str,
    duration_unparseable: bool,
    parent_public_eligible: bool,
    parent_attributed: bool,
) -> SentenceFactEligibility:
    """Decide the eligibility trio + reason codes for one sentence component (PD5).

    Pure: given the 22.5 component result (consumed unchanged), the derived
    ``component_match_method``, the per-component ``duration_unparseable`` signal
    (the 18.1 predicate, applied by the caller to the parsed sentence row), and
    the parent outcome fact's ``public_eligible`` / attribution state, returns the
    :class:`SentenceFactEligibility`.

    ``review_needed`` derives (PD6) from the component's own signals — an unmapped
    or ambiguous sentencing category, ``money_unparseable`` (all via
    ``result.review_needed``), or an ``UNPARSEABLE_DURATION`` component — PLUS the
    silent-loss guard: a component carrying an ADDITIVE category beyond the base
    (``len(result.categories) > 1``) is forced to review so the additive surfaces
    to the 23.4 queue rather than being dropped to a base-only eligible fact (the
    base category is still stored and ``amount_cents`` still populated).
    """
    multi_category = len(result.categories) > 1
    review_needed = result.review_needed or duration_unparseable or multi_category

    mvp_eligible = sentence_date is not None and sentence_date >= MVP_WINDOW_START
    clean_match = component_match_method in PUBLIC_COMPONENT_MATCH_METHODS
    # The 22.5 base mapping's ``public_eligible`` is the taxonomy ``public`` flag
    # for the base category (always False for the unmapped -> ``unknown`` sink).
    category_public = result.base.public_eligible

    public_eligible = (
        parent_public_eligible
        and mvp_eligible
        and clean_match
        and category_public
        and not review_needed
    )
    judge_specific_eligible = public_eligible and parent_attributed

    reasons: list[str] = []

    # Sentence-date reasons (mutually exclusive; drive mvp-ineligibility). SD 15
    # ties this to the parent's disposition-date gate; a nonzero divergence is a
    # STOP handled by the build orchestration, so here the date is trusted.
    if sentence_date is None:
        reasons.append(SENTENCE_DATE_MISSING)
    elif sentence_date < MVP_WINDOW_START:
        reasons.append(SENTENCE_DATE_BEFORE_MVP_WINDOW)

    # Transitive parent gate (the docket/charge blocking-warning set is inherited
    # here, never re-implemented for sentences).
    if not parent_public_eligible:
        reasons.append(PARENT_OUTCOME_INELIGIBLE)

    # Component-normalization reasons.
    if not clean_match:
        reasons.append(SENTENCING_COMPONENT_NOT_NORMALIZED)
    # A mapped-but-non-public base category (e.g. ARD/IPP -> ``other``); the
    # unmapped -> ``unknown`` case is already covered by not-normalized above.
    if result.base.mapped and not category_public:
        reasons.append(SENTENCING_CATEGORY_NOT_PUBLIC)

    # Review-signal reasons (each its own machine-readable code).
    if review_needed:
        reasons.append(REVIEW_NEEDED)
    if result.money_unparseable:
        reasons.append(MONEY_AMOUNT_UNPARSEABLE)
    if duration_unparseable:
        reasons.append(SENTENCE_DURATION_UNPARSEABLE)

    # Judge attribution is the SPECIFIC gate on judge_specific_eligible: a reason
    # only when the fact is otherwise public-eligible but unattributed.
    if public_eligible and not parent_attributed:
        reasons.append(JUDGE_NOT_ATTRIBUTED)

    return SentenceFactEligibility(
        mvp_eligible=mvp_eligible,
        public_eligible=public_eligible,
        judge_specific_eligible=judge_specific_eligible,
        review_needed=review_needed,
        ineligibility_reason_codes=tuple(reasons),
    )


def build_sentence_fact_row(
    *,
    build_run_id: str,
    charge_outcome_id: str,
    parsed_sentence_id: str,
    normalized_charge_id: str | None,
    sentence_date: date | None,
    result: SentencingComponentResult,
    component_match_method: str,
    min_days: int | None,
    max_days: int | None,
    min_assumed: bool,
    normalized_judge_id: str | None,
    judge_attribution_method: str | None,
    eligibility: SentenceFactEligibility,
    taxonomy_version: str,
) -> dict[str, object]:
    """Assemble the full ``fact.charge_sentences`` column dict for one component.

    Pure. ``sentencing_category_code`` is the BASE category (the 1:1 single-column
    schema stores one code per component; additive restitution / community-service
    mappings drive ``amount_cents`` and ``review_needed`` instead — the silent-loss
    guard in :func:`evaluate_sentence_eligibility`). ``normalized_charge_id`` and
    both judge fields are INHERITED verbatim from the parent outcome fact; duration
    fields + ``sentence_date`` are carried as parsed; ``amount_cents`` is the 22.5
    money extraction (``None`` unless exactly one amount was read).
    """
    return {
        "build_run_id": build_run_id,
        "charge_outcome_id": charge_outcome_id,
        "parsed_sentence_id": parsed_sentence_id,
        "normalized_charge_id": normalized_charge_id,
        "sentencing_category_code": result.base.category_code,
        "sentence_date": sentence_date,
        "min_days": min_days,
        "max_days": max_days,
        "min_assumed": min_assumed,
        "amount_cents": result.amount_cents,
        "normalized_judge_id": normalized_judge_id,
        "judge_attribution_method": judge_attribution_method,
        "attribution_method": ATTRIBUTION_METHOD_CHARGE_COMPONENT,
        "component_match_method": component_match_method,
        "mvp_eligible": eligibility.mvp_eligible,
        "public_eligible": eligibility.public_eligible,
        "judge_specific_eligible": eligibility.judge_specific_eligible,
        "ineligibility_reason_codes": list(eligibility.ineligibility_reason_codes),
        "review_needed": eligibility.review_needed,
        "taxonomy_version": taxonomy_version,
    }


def parent_attributed(judge_attribution_method: str | None) -> bool:
    """True iff the parent outcome fact carries an attributed judge (23.1).

    The inherited ``judge_attribution_method`` is ``disposition_judge`` /
    ``assigned_judge_rule`` when attributed and ``none`` (:data:`METHOD_NONE`)
    when not; NULL never occurs on an outcome fact but is treated as unattributed.
    """
    return (
        judge_attribution_method is not None and judge_attribution_method != METHOD_NONE
    )


# The immutable column order for the INSERT (id + created_at are DB defaults).
_INSERT_COLUMNS = (
    "build_run_id",
    "charge_outcome_id",
    "parsed_sentence_id",
    "normalized_charge_id",
    "sentencing_category_code",
    "sentence_date",
    "min_days",
    "max_days",
    "min_assumed",
    "amount_cents",
    "normalized_judge_id",
    "judge_attribution_method",
    "attribution_method",
    "component_match_method",
    "mvp_eligible",
    "public_eligible",
    "judge_specific_eligible",
    "ineligibility_reason_codes",
    "review_needed",
    "taxonomy_version",
)


def insert_sentence_facts(
    conn: psycopg.Connection, rows: Sequence[Mapping[str, object]]
) -> int:
    """Insert sentence-fact rows in one ``executemany``; return the count.

    Runs inside the caller's transaction (the run-lifecycle tx, AFTER the parent
    outcome facts). Insert-only — the fact table is immutable (a rebuild is
    delete-and-reinsert under a new run). Does not commit; the caller owns the
    transaction boundary.
    """
    if not rows:
        return 0
    placeholders = ", ".join(f"%({col})s" for col in _INSERT_COLUMNS)
    columns = ", ".join(_INSERT_COLUMNS)
    with conn.cursor() as cur:
        cur.executemany(
            f"INSERT INTO fact.charge_sentences ({columns}) VALUES ({placeholders})",  # noqa: S608 - columns are module constants, never input
            list(rows),
        )
    return len(rows)
