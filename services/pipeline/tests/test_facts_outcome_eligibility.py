"""Tier-1 synthetic tests for outcome-fact eligibility (Task 23.2).

Pure, DB-free unit tests for :func:`evaluate_outcome_eligibility` and
:func:`build_outcome_fact_row` — the eligibility trio, ``review_needed``, and the
all-applicable ``ineligibility_reason_codes`` array, exactly per Sprint 5 plan
Task 23.2 AC 2/3. Synthetic inputs only (fictional charge/judge strings); the
three upstream result types are constructed directly, never re-derived.
"""

from __future__ import annotations

from datetime import date

import pytest

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
from pipeline.facts.judge_attribution import (
    METHOD_ASSIGNED_JUDGE_RULE,
    METHOD_DISPOSITION_JUDGE,
    METHOD_NONE,
    AttributionResult,
)
from pipeline.facts.outcome_facts import (
    ATTRIBUTION_METHOD_CHARGE_ROW,
    FILED_DATE_FLOOR_DEFAULT,
    OUTCOME_MATCH_METHOD_EXACT,
    OUTCOME_MATCH_METHOD_UNMAPPED,
    OutcomeFactEligibility,
    build_outcome_fact_row,
    evaluate_outcome_eligibility,
)
from pipeline.normalization.models import (
    ChargeNormalizationResult,
    NormalizationCandidate,
)
from pipeline.normalization.outcome_mapper import OUTCOME_UNKNOWN, OutcomeMappingResult
from pipeline.normalization.vocab import (
    MATCH_METHOD_ALIAS,
    MATCH_METHOD_AMBIGUOUS,
    MATCH_METHOD_EXACT,
    MATCH_METHOD_UNMATCHED,
    NORM_AMBIGUOUS,
    NORM_STATUTE_TEXT_CONFLICT,
    NORM_UNMATCHED,
)
from pipeline.warning_codes import MISSING_DISPOSITION_DATE, SUSPECTED_AMENDED_CHARGE

IN_WINDOW = date(2025, 6, 1)
PRE_WINDOW = date(2024, 12, 31)
FILED_IN_WINDOW = date(2025, 3, 1)
FILED_PRE_FLOOR = date(2024, 12, 31)
TAXV = "1.0.0"


def evaluate(**kwargs):
    """``evaluate_outcome_eligibility`` with an in-window filed-date default.

    The filed-date floor (task filed-date-floor) is orthogonal to the pre-floor
    scenarios below, so this wrapper pins ``filed_date`` in-window and the floor
    to the committed default; each test states only the signal it exercises.
    The floor tests at the bottom override both explicitly.
    """
    kwargs.setdefault("filed_date", FILED_IN_WINDOW)
    kwargs.setdefault("filed_date_floor", FILED_DATE_FLOOR_DEFAULT)
    return evaluate_outcome_eligibility(**kwargs)


# --- builders for the three upstream results (all synthetic) ----------------
def matched_charge(method: str = MATCH_METHOD_EXACT) -> ChargeNormalizationResult:
    return ChargeNormalizationResult(
        raw_value="Fictional Offense",
        match_method=method,
        normalized_id="charge-uuid-1",
        display_name="Fictional Offense",
    )


def unmatched_charge() -> ChargeNormalizationResult:
    return ChargeNormalizationResult(
        raw_value="Nonsense Offense",
        match_method=MATCH_METHOD_UNMATCHED,
        warnings=(NORM_UNMATCHED,),
    )


def conflicted_charge() -> ChargeNormalizationResult:
    return ChargeNormalizationResult(
        raw_value="Conflicted Offense",
        match_method=MATCH_METHOD_AMBIGUOUS,
        warnings=(NORM_STATUTE_TEXT_CONFLICT,),
        candidates=(
            NormalizationCandidate(normalized_id="a", display_name="A"),
            NormalizationCandidate(normalized_id="b", display_name="B"),
        ),
    )


def mapped_public_outcome() -> OutcomeMappingResult:
    return OutcomeMappingResult(
        raw_value="Guilty Plea",
        outcome_code="guilty_plea",
        taxonomy_version=TAXV,
        public_eligible=True,
        mapped=True,
        review_needed=False,
    )


def mapped_nonpublic_outcome() -> OutcomeMappingResult:
    return OutcomeMappingResult(
        raw_value="Some Sealed Disposition",
        outcome_code="other",
        taxonomy_version=TAXV,
        public_eligible=False,
        mapped=True,
        review_needed=False,
    )


def unmapped_outcome() -> OutcomeMappingResult:
    return OutcomeMappingResult(
        raw_value="Totally Unknown Disposition",
        outcome_code=OUTCOME_UNKNOWN,
        taxonomy_version=TAXV,
        public_eligible=False,
        mapped=False,
        review_needed=True,
    )


def attributed(method: str = METHOD_DISPOSITION_JUDGE) -> AttributionResult:
    return AttributionResult(normalized_judge_id="judge-uuid-1", method=method)


def unattributed() -> AttributionResult:
    return AttributionResult(normalized_judge_id=None, method=METHOD_NONE)


# --- the AC 8 scenarios -----------------------------------------------------
def test_fully_eligible_fact():
    e = evaluate(
        disposition_date=IN_WINDOW,
        charge_result=matched_charge(),
        outcome_result=mapped_public_outcome(),
        attribution=attributed(),
    )
    assert e.mvp_eligible and e.public_eligible and e.judge_specific_eligible
    assert not e.review_needed
    assert e.ineligibility_reason_codes == ()


def test_assigned_judge_rule_is_attributed():
    e = evaluate(
        disposition_date=IN_WINDOW,
        charge_result=matched_charge(MATCH_METHOD_ALIAS),
        outcome_result=mapped_public_outcome(),
        attribution=attributed(METHOD_ASSIGNED_JUDGE_RULE),
    )
    assert e.judge_specific_eligible
    assert e.ineligibility_reason_codes == ()


def test_unknown_outcome_ineligible_disposition_not_mapped():
    e = evaluate(
        disposition_date=IN_WINDOW,
        charge_result=matched_charge(),
        outcome_result=unmapped_outcome(),
        attribution=attributed(),
    )
    assert e.mvp_eligible
    assert not e.public_eligible and not e.judge_specific_eligible
    assert DISPOSITION_NOT_MAPPED in e.ineligibility_reason_codes
    # public-ineligible -> judge is NOT the specific gate, so no judge reason.
    assert JUDGE_NOT_ATTRIBUTED not in e.ineligibility_reason_codes


def test_unnormalized_charge_ineligible_charge_not_normalized():
    e = evaluate(
        disposition_date=IN_WINDOW,
        charge_result=unmatched_charge(),
        outcome_result=mapped_public_outcome(),
        attribution=attributed(),
    )
    assert e.mvp_eligible
    assert not e.public_eligible
    assert CHARGE_NOT_NORMALIZED in e.ineligibility_reason_codes


def test_ambiguous_charge_is_not_public_normalized():
    e = evaluate(
        disposition_date=IN_WINDOW,
        charge_result=ChargeNormalizationResult(
            raw_value="Ambiguous Offense",
            match_method=MATCH_METHOD_AMBIGUOUS,
            warnings=(NORM_AMBIGUOUS,),
            candidates=(
                NormalizationCandidate(normalized_id="a", display_name="A"),
                NormalizationCandidate(normalized_id="b", display_name="B"),
            ),
        ),
        outcome_result=mapped_public_outcome(),
        attribution=attributed(),
    )
    assert not e.public_eligible
    assert CHARGE_NOT_NORMALIZED in e.ineligibility_reason_codes


def test_public_eligible_but_judge_unattributed():
    e = evaluate(
        disposition_date=IN_WINDOW,
        charge_result=matched_charge(),
        outcome_result=mapped_public_outcome(),
        attribution=unattributed(),
    )
    assert e.public_eligible
    assert not e.judge_specific_eligible
    assert e.ineligibility_reason_codes == (JUDGE_NOT_ATTRIBUTED,)


def test_pre_window_date_not_mvp_eligible():
    e = evaluate(
        disposition_date=PRE_WINDOW,
        charge_result=matched_charge(),
        outcome_result=mapped_public_outcome(),
        attribution=attributed(),
    )
    assert not e.mvp_eligible and not e.public_eligible
    assert DISPOSITION_DATE_BEFORE_MVP_WINDOW in e.ineligibility_reason_codes


def test_null_date_not_mvp_eligible():
    e = evaluate(
        disposition_date=None,
        charge_result=matched_charge(),
        outcome_result=mapped_public_outcome(),
        attribution=attributed(),
    )
    assert not e.mvp_eligible
    assert DISPOSITION_DATE_MISSING in e.ineligibility_reason_codes


def test_review_severity_parser_warning_gates_public_via_review_needed():
    e = evaluate(
        disposition_date=IN_WINDOW,
        charge_result=matched_charge(),
        outcome_result=mapped_public_outcome(),
        attribution=attributed(),
        charge_warning_codes=[SUSPECTED_AMENDED_CHARGE],
    )
    assert e.mvp_eligible
    assert e.review_needed
    assert not e.public_eligible
    assert REVIEW_NEEDED in e.ineligibility_reason_codes


def test_missing_disposition_date_warning_and_null_date_stack():
    # A null-date charge carrying the charge-grain MISSING_DISPOSITION_DATE
    # warning: both the date reason and review_needed apply (all applicable).
    e = evaluate(
        disposition_date=None,
        charge_result=matched_charge(),
        outcome_result=mapped_public_outcome(),
        attribution=attributed(),
        charge_warning_codes=[MISSING_DISPOSITION_DATE],
    )
    assert e.review_needed
    assert DISPOSITION_DATE_MISSING in e.ineligibility_reason_codes
    assert REVIEW_NEEDED in e.ineligibility_reason_codes


def test_mapped_nonpublic_category_reason():
    e = evaluate(
        disposition_date=IN_WINDOW,
        charge_result=matched_charge(),
        outcome_result=mapped_nonpublic_outcome(),
        attribution=attributed(),
    )
    assert not e.public_eligible
    assert OUTCOME_CATEGORY_NOT_PUBLIC in e.ineligibility_reason_codes
    assert DISPOSITION_NOT_MAPPED not in e.ineligibility_reason_codes


def test_statute_text_conflict_adds_blocking_warning_additively():
    e = evaluate(
        disposition_date=IN_WINDOW,
        charge_result=conflicted_charge(),
        outcome_result=mapped_public_outcome(),
        attribution=attributed(),
    )
    assert not e.public_eligible
    # A conflict is both an ambiguous (unnormalized) match AND the blocking
    # subclass -> both reasons present.
    assert CHARGE_NOT_NORMALIZED in e.ineligibility_reason_codes
    assert BLOCKING_WARNING in e.ineligibility_reason_codes


def test_all_applicable_reasons_stack():
    # A pre-window, unmatched charge carries BOTH its date reason and its
    # normalization reason (the all-applicable array, not a single code).
    e = evaluate(
        disposition_date=PRE_WINDOW,
        charge_result=unmatched_charge(),
        outcome_result=mapped_public_outcome(),
        attribution=unattributed(),
    )
    assert set(e.ineligibility_reason_codes) == {
        DISPOSITION_DATE_BEFORE_MVP_WINDOW,
        CHARGE_NOT_NORMALIZED,
    }
    # Not judge_not_attributed: the fact is already public-ineligible.
    assert JUDGE_NOT_ATTRIBUTED not in e.ineligibility_reason_codes


# --- invariants + row construction ------------------------------------------
def test_eligibility_invariants_enforced():
    with pytest.raises(ValueError):
        OutcomeFactEligibility(
            mvp_eligible=False,
            public_eligible=True,  # public without mvp
            judge_specific_eligible=False,
            review_needed=False,
            ineligibility_reason_codes=(),
        )
    with pytest.raises(ValueError):
        OutcomeFactEligibility(
            mvp_eligible=True,
            public_eligible=True,
            judge_specific_eligible=True,  # fully eligible but carries a reason
            review_needed=False,
            ineligibility_reason_codes=(CHARGE_NOT_NORMALIZED,),
        )


def test_public_eligible_may_carry_judge_reason():
    # A public-eligible-but-unattributed fact legitimately carries exactly the
    # judge_not_attributed reason (empty array is reserved for judge_specific).
    OutcomeFactEligibility(
        mvp_eligible=True,
        public_eligible=True,
        judge_specific_eligible=False,
        review_needed=False,
        ineligibility_reason_codes=(JUDGE_NOT_ATTRIBUTED,),
    )


def test_build_outcome_fact_row_columns():
    charge_result = matched_charge()
    outcome_result = mapped_public_outcome()
    attribution = attributed()
    eligibility = evaluate(
        disposition_date=IN_WINDOW,
        charge_result=charge_result,
        outcome_result=outcome_result,
        attribution=attribution,
    )
    row = build_outcome_fact_row(
        build_run_id="run-1",
        parsed_charge_id="pc-1",
        parsed_docket_id="pd-1",
        disposition_date=IN_WINDOW,
        charge_result=charge_result,
        outcome_result=outcome_result,
        attribution=attribution,
        eligibility=eligibility,
        taxonomy_version=TAXV,
    )
    assert row["attribution_method"] == ATTRIBUTION_METHOD_CHARGE_ROW
    assert row["outcome_match_method"] == OUTCOME_MATCH_METHOD_EXACT
    assert row["normalized_charge_id"] == "charge-uuid-1"
    assert row["normalized_judge_id"] == "judge-uuid-1"
    assert row["judge_attribution_method"] == METHOD_DISPOSITION_JUDGE
    assert row["outcome_category_code"] == "guilty_plea"
    assert row["ineligibility_reason_codes"] == []


def test_build_row_unmapped_outcome_match_method():
    charge_result = matched_charge()
    outcome_result = unmapped_outcome()
    attribution = unattributed()
    eligibility = evaluate(
        disposition_date=IN_WINDOW,
        charge_result=charge_result,
        outcome_result=outcome_result,
        attribution=attribution,
    )
    row = build_outcome_fact_row(
        build_run_id="run-1",
        parsed_charge_id="pc-2",
        parsed_docket_id="pd-1",
        disposition_date=IN_WINDOW,
        charge_result=charge_result,
        outcome_result=outcome_result,
        attribution=attribution,
        eligibility=eligibility,
        taxonomy_version=TAXV,
    )
    assert row["outcome_match_method"] == OUTCOME_MATCH_METHOD_UNMAPPED
    assert row["normalized_judge_id"] is None
    assert row["outcome_category_code"] == OUTCOME_UNKNOWN


# --- filed-date floor (task filed-date-floor) --------------------------------
def test_filed_day_before_floor_public_ineligible():
    # Boundary: 2024-12-31 is below the default 2025-01-01 floor. The floor
    # gates public_eligible ONLY — mvp_eligible keeps its event-date meaning.
    e = evaluate(
        disposition_date=IN_WINDOW,
        filed_date=FILED_PRE_FLOOR,
        charge_result=matched_charge(),
        outcome_result=mapped_public_outcome(),
        attribution=attributed(),
    )
    assert e.mvp_eligible
    assert not e.public_eligible and not e.judge_specific_eligible
    assert e.ineligibility_reason_codes == (FILED_DATE_BEFORE_FLOOR,)


def test_filed_on_floor_eligible():
    # Boundary: exactly 2025-01-01 is on the floor -> eligible, no floor code.
    e = evaluate(
        disposition_date=IN_WINDOW,
        filed_date=date(2025, 1, 1),
        charge_result=matched_charge(),
        outcome_result=mapped_public_outcome(),
        attribution=attributed(),
    )
    assert e.public_eligible and e.judge_specific_eligible
    assert e.ineligibility_reason_codes == ()


def test_filed_null_fail_closed_missing_code_only():
    # Fail-closed: a null filed_date is ineligible and carries
    # filed_date_missing ONLY — the arms are mutually exclusive.
    e = evaluate(
        disposition_date=IN_WINDOW,
        filed_date=None,
        charge_result=matched_charge(),
        outcome_result=mapped_public_outcome(),
        attribution=attributed(),
    )
    assert e.mvp_eligible and not e.public_eligible
    assert e.ineligibility_reason_codes == (FILED_DATE_MISSING,)
    assert FILED_DATE_BEFORE_FLOOR not in e.ineligibility_reason_codes


def test_filed_floor_is_config_driven():
    # The evaluator reads the threaded floor, not a hardcoded date: the same
    # filed_date is eligible under an earlier floor and ineligible under the
    # committed default.
    kwargs = dict(
        disposition_date=IN_WINDOW,
        filed_date=date(2024, 6, 1),
        charge_result=matched_charge(),
        outcome_result=mapped_public_outcome(),
        attribution=attributed(),
    )
    assert evaluate(**kwargs, filed_date_floor=date(2024, 1, 1)).public_eligible
    assert not evaluate(**kwargs).public_eligible


def test_filed_floor_default_constant():
    assert FILED_DATE_FLOOR_DEFAULT == date(2025, 1, 1)


def test_filed_floor_reason_stacks_with_other_reasons():
    # A floored fact with other defects carries every applicable code.
    e = evaluate(
        disposition_date=PRE_WINDOW,
        filed_date=None,
        charge_result=unmatched_charge(),
        outcome_result=mapped_public_outcome(),
        attribution=unattributed(),
    )
    assert not e.mvp_eligible and not e.public_eligible
    assert DISPOSITION_DATE_BEFORE_MVP_WINDOW in e.ineligibility_reason_codes
    assert FILED_DATE_MISSING in e.ineligibility_reason_codes
    assert CHARGE_NOT_NORMALIZED in e.ineligibility_reason_codes
