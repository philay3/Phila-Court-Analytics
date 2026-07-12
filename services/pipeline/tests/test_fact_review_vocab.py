"""Controlled vocabularies for the fact + review tables (Task 21.2).

Uniqueness (no two constants collapsing to one string) and non-emptiness for
each of the five vocabularies, plus the two anti-collision guards that motivated
the severity rename.
"""

from __future__ import annotations

from pipeline import fact_review_vocab as v

ALL_VOCABULARIES = (
    v.REVIEW_ITEM_TYPES,
    v.REVIEW_SEVERITIES,
    v.REVIEW_ITEM_STATUSES,
    v.FACT_BUILD_RUN_STATUSES,
    v.ELIGIBILITY_REASON_CODES,
)


def test_every_vocabulary_is_non_empty():
    for vocab in ALL_VOCABULARIES:
        assert len(vocab) > 0


def test_every_member_is_a_non_empty_lowercase_token():
    for vocab in ALL_VOCABULARIES:
        for member in vocab:
            assert isinstance(member, str)
            assert member != ""
            assert member == member.strip()
            assert member == member.lower()


def test_review_item_types_are_exactly_the_twelve_members():
    assert v.REVIEW_ITEM_TYPES == {
        "unmapped_charge",
        "ambiguous_charge",
        "unmapped_judge",
        "ambiguous_judge",
        "unmapped_disposition",
        "unmapped_sentencing_component",
        "ambiguous_sentencing_component",
        "money_unparseable",
        "duration_unparseable",
        "ambiguous_judge_attribution",
        "missing_disposition_date",
        "sentinel_collision",
    }
    assert len(v.REVIEW_ITEM_TYPES) == 12


def test_review_severities_are_exactly_high_medium_low():
    assert v.REVIEW_SEVERITIES == {"high", "medium", "low"}
    assert len(v.REVIEW_SEVERITIES) == 3


def test_review_item_statuses_and_default():
    assert v.REVIEW_ITEM_STATUSES == {"open", "in_review", "resolved", "dismissed"}
    assert len(v.REVIEW_ITEM_STATUSES) == 4
    assert v.REVIEW_ITEM_STATUS_DEFAULT == "open"
    assert v.REVIEW_ITEM_STATUS_DEFAULT in v.REVIEW_ITEM_STATUSES


def test_fact_build_run_statuses_are_exactly_three_members():
    assert v.FACT_BUILD_RUN_STATUSES == {"in_progress", "completed", "failed"}
    assert len(v.FACT_BUILD_RUN_STATUSES) == 3


def test_eligibility_reason_codes_are_exactly_the_sixteen_members():
    # judge_not_normalized added in Task 22.3 (sanctioned plan-level vocabulary
    # addition, Answer 1), the domain-qualified judge analog of
    # charge_not_normalized. disposition_not_mapped added in Task 22.4 (same
    # convention), the domain-qualified outcome-mapping analog. money_amount_unparseable
    # + sentence_duration_unparseable added in Task 22.5 (map-gate approved), the
    # domain-qualified sentencing money/duration analogs.
    assert v.ELIGIBILITY_REASON_CODES == {
        "disposition_date_missing",
        "disposition_date_before_mvp_window",
        "sentence_date_missing",
        "sentence_date_before_mvp_window",
        "charge_not_normalized",
        "judge_not_normalized",
        "disposition_not_mapped",
        "outcome_category_not_public",
        "sentencing_category_not_public",
        "sentencing_component_not_normalized",
        "review_needed",
        "blocking_warning",
        "judge_not_attributed",
        "parent_outcome_ineligible",
        "money_amount_unparseable",
        "sentence_duration_unparseable",
    }
    assert len(v.ELIGIBILITY_REASON_CODES) == 16


def test_severities_do_not_collide_with_the_colliding_vocabularies():
    # The rename rationale: severity tokens must not share words with the
    # eligibility reason codes ("blocking_warning") or the parser warning-code
    # severity vocabulary ("warning"/"info").
    assert "blocking" not in v.REVIEW_SEVERITIES
    assert "warning" not in v.REVIEW_SEVERITIES
    assert v.REVIEW_SEVERITIES.isdisjoint(v.ELIGIBILITY_REASON_CODES)


def test_named_constants_match_their_vocabulary_membership():
    # Guards against a typo making two constants equal (which would silently
    # shrink a frozenset without changing its declared literal above).
    assert v.REVIEW_ITEM_STATUS_DEFAULT == v.STATUS_OPEN
    assert v.SEVERITY_HIGH in v.REVIEW_SEVERITIES
    assert v.RUN_COMPLETED in v.FACT_BUILD_RUN_STATUSES
    assert v.BLOCKING_WARNING in v.ELIGIBILITY_REASON_CODES
    assert v.SENTINEL_COLLISION in v.REVIEW_ITEM_TYPES
