"""Normalization result models (Task 22.1).

Valid construction plus every invalid arm of pinned decisions 2-4 (method
vocabulary, matched-field consistency, candidate-list rule), the derived-by-
default / passed-value review_needed behaviour, the warning-vocabulary
closedness, and the money model float/bool prohibition (pinned decision 7).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from pipeline.normalization import (
    ChargeNormalizationResult,
    JudgeNormalizationResult,
    MoneyExtractionResult,
    NormalizationCandidate,
    OutcomeNormalizationResult,
    SentencingNormalizationResult,
)

ALL_RESULT_MODELS = (
    ChargeNormalizationResult,
    JudgeNormalizationResult,
    OutcomeNormalizationResult,
    SentencingNormalizationResult,
)


def _candidates(n: int = 2) -> tuple[NormalizationCandidate, ...]:
    return tuple(
        NormalizationCandidate(normalized_id=f"id-{i}", display_name=f"Name {i}")
        for i in range(n)
    )


# --- valid construction across all four models ------------------------------


@pytest.mark.parametrize("model", ALL_RESULT_MODELS)
def test_valid_matched_result(model):
    r = model(
        raw_value="raw",
        match_method="exact",
        normalized_id="norm-1",
        display_name="Norm One",
    )
    assert r.normalized_id == "norm-1"
    assert r.display_name == "Norm One"
    assert r.review_needed is False  # matched, no blocking warning


@pytest.mark.parametrize("model", ALL_RESULT_MODELS)
def test_valid_unmatched_result(model):
    r = model(raw_value="raw", match_method="unmatched")
    assert r.normalized_id is None
    assert r.display_name is None
    assert r.candidates == ()
    assert r.review_needed is True


@pytest.mark.parametrize("model", ALL_RESULT_MODELS)
def test_valid_ambiguous_result(model):
    r = model(
        raw_value="raw",
        match_method="ambiguous",
        candidates=_candidates(2),
    )
    assert len(r.candidates) == 2
    assert r.normalized_id is None
    assert r.review_needed is True


# --- pinned decision 2: method vocabulary is closed -------------------------


@pytest.mark.parametrize("model", ALL_RESULT_MODELS)
def test_unknown_match_method_raises(model):
    with pytest.raises(ValueError):
        model(raw_value="raw", match_method="fuzzy")


# --- pinned decision 4: matched-field consistency ---------------------------


@pytest.mark.parametrize("model", ALL_RESULT_MODELS)
def test_matched_method_without_identity_raises(model):
    with pytest.raises(ValueError):
        model(raw_value="raw", match_method="exact")  # missing id + name


@pytest.mark.parametrize("model", ALL_RESULT_MODELS)
def test_matched_method_missing_display_name_raises(model):
    with pytest.raises(ValueError):
        model(raw_value="raw", match_method="alias", normalized_id="x")


@pytest.mark.parametrize("model", ALL_RESULT_MODELS)
def test_unmatched_with_identity_raises(model):
    with pytest.raises(ValueError):
        model(
            raw_value="raw",
            match_method="unmatched",
            normalized_id="x",
            display_name="X",
        )


@pytest.mark.parametrize("model", ALL_RESULT_MODELS)
def test_ambiguous_with_identity_raises(model):
    with pytest.raises(ValueError):
        model(
            raw_value="raw",
            match_method="ambiguous",
            normalized_id="x",
            display_name="X",
            candidates=_candidates(2),
        )


# --- pinned decision 3: candidate-list rule ---------------------------------


@pytest.mark.parametrize("model", ALL_RESULT_MODELS)
def test_ambiguous_with_one_candidate_raises(model):
    with pytest.raises(ValueError):
        model(
            raw_value="raw",
            match_method="ambiguous",
            candidates=_candidates(1),
        )


@pytest.mark.parametrize("model", ALL_RESULT_MODELS)
def test_ambiguous_with_zero_candidates_raises(model):
    with pytest.raises(ValueError):
        model(raw_value="raw", match_method="ambiguous")


@pytest.mark.parametrize("model", ALL_RESULT_MODELS)
def test_matched_with_candidates_raises(model):
    with pytest.raises(ValueError):
        model(
            raw_value="raw",
            match_method="exact",
            normalized_id="x",
            display_name="X",
            candidates=_candidates(2),
        )


@pytest.mark.parametrize("model", ALL_RESULT_MODELS)
def test_unmatched_with_candidates_raises(model):
    with pytest.raises(ValueError):
        model(
            raw_value="raw",
            match_method="unmatched",
            candidates=_candidates(2),
        )


# --- acceptance criterion 4: warning vocabulary is closed -------------------


@pytest.mark.parametrize("model", ALL_RESULT_MODELS)
def test_unknown_warning_code_raises(model):
    with pytest.raises(ValueError):
        model(
            raw_value="raw",
            match_method="unmatched",
            warnings=("NOT_A_REAL_CODE",),
        )


@pytest.mark.parametrize("model", ALL_RESULT_MODELS)
def test_known_warning_code_accepted(model):
    r = model(
        raw_value="raw",
        match_method="unmatched",
        warnings=("NORM_UNMATCHED",),
    )
    assert r.warnings == ("NORM_UNMATCHED",)


# --- pinned decision 6: review_needed derived-by-default vs passed -----------


def test_review_needed_omitted_is_derived():
    # Matched + blocking warning -> derived True even though omitted.
    r = ChargeNormalizationResult(
        raw_value="raw",
        match_method="statute",
        normalized_id="x",
        display_name="X",
        warnings=("NORM_STATUTE_TEXT_CONFLICT",),
    )
    assert r.review_needed is True

    # Matched, no blocking warning -> derived False.
    r2 = ChargeNormalizationResult(
        raw_value="raw",
        match_method="exact",
        normalized_id="x",
        display_name="X",
    )
    assert r2.review_needed is False


def test_review_needed_passed_and_correct_is_accepted():
    r = ChargeNormalizationResult(
        raw_value="raw",
        match_method="unmatched",
        review_needed=True,
    )
    assert r.review_needed is True


def test_review_needed_passed_and_wrong_raises():
    # unmatched always derives True; passing False must raise.
    with pytest.raises(ValueError):
        ChargeNormalizationResult(
            raw_value="raw",
            match_method="unmatched",
            review_needed=False,
        )
    # matched-no-warning derives False; passing True must raise.
    with pytest.raises(ValueError):
        ChargeNormalizationResult(
            raw_value="raw",
            match_method="exact",
            normalized_id="x",
            display_name="X",
            review_needed=True,
        )


# --- NormalizationCandidate validation --------------------------------------


def test_candidate_requires_non_empty_fields():
    with pytest.raises(ValueError):
        NormalizationCandidate(normalized_id="", display_name="X")
    with pytest.raises(ValueError):
        NormalizationCandidate(normalized_id="x", display_name="")


# --- frozen / immutable -----------------------------------------------------


def test_results_are_frozen():
    r = ChargeNormalizationResult(raw_value="raw", match_method="unmatched")
    with pytest.raises(FrozenInstanceError):
        r.match_method = "exact"  # type: ignore[misc]


# --- pinned decision 7: money model, integer cents only ---------------------


def test_money_accepts_int_cents_and_none():
    assert MoneyExtractionResult(raw_text="$1.00", amount_cents=100).amount_cents == 100
    assert MoneyExtractionResult(raw_text="", amount_cents=None).amount_cents is None
    assert MoneyExtractionResult(raw_text="$0", amount_cents=0).amount_cents == 0


def test_money_rejects_float():
    with pytest.raises(ValueError):
        MoneyExtractionResult(raw_text="$1.00", amount_cents=100.0)  # type: ignore[arg-type]


def test_money_rejects_bool():
    # bool is an int subclass; it must not sneak through as cents.
    with pytest.raises(ValueError):
        MoneyExtractionResult(raw_text="$1", amount_cents=True)  # type: ignore[arg-type]


def test_money_rejects_unknown_warning_code():
    with pytest.raises(ValueError):
        MoneyExtractionResult(raw_text="x", warnings=("NOPE",))


def test_money_accepts_known_warning_code():
    r = MoneyExtractionResult(
        raw_text="x", amount_cents=None, warnings=("NORM_UNPARSEABLE_AMOUNT",)
    )
    assert r.warnings == ("NORM_UNPARSEABLE_AMOUNT",)


def test_money_is_frozen():
    r = MoneyExtractionResult(raw_text="x", amount_cents=1)
    with pytest.raises(FrozenInstanceError):
        r.amount_cents = 2  # type: ignore[misc]
