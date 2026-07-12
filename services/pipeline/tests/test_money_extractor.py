"""Tier-1 tests for the money extractor (Task 22.5, AC 3).

Covers integer-cents conversion, distinct-by-value amount collection, and the
locked four-branch triage (option b): no-`$` absence (no warning), `$`-present-
but-unreadable, exactly-one-amount SET, and multiple-distinct unset. Also asserts
the `$`-required regex excludes sentence-duration figures ("11.00 months"), the
recon-driven reason the `$`-optional candidate was rejected. All inputs are
synthetic; no raw docket text.
"""

from __future__ import annotations

from pipeline.normalization.money_extractor import (
    distinct_amounts,
    extract_amount,
    token_to_cents,
)
from pipeline.normalization.vocab import NORM_UNPARSEABLE_AMOUNT


def test_token_to_cents_shapes():
    assert token_to_cents("$500") == 50000
    assert token_to_cents("$500.00") == 50000
    assert token_to_cents("$1,234.56") == 123456
    assert token_to_cents("$1,234") == 123400
    assert token_to_cents("$12,345,678.00") == 1234567800
    assert token_to_cents("$1234.56") == 123456  # 4+ digits, no comma
    assert token_to_cents("$1234") == 123400


def test_distinct_amounts_dedupes_by_value():
    # Same amount written twice is ONE distinct amount (the held gate test case).
    assert distinct_amounts("Restitution $500.00 $500.00") == {50000}
    # Two different amounts are two.
    assert distinct_amounts("$100.00 plus $250.00") == {10000, 25000}
    # No `$` -> no amounts.
    assert distinct_amounts("Confinement Min of 11.00 Max of 23.00 months") == set()


def test_branch3_exactly_one_amount_sets_cents_no_warning():
    r = extract_amount("Fines and Costs Restitution $500.00")
    assert r.amount_cents == 50000
    assert r.warnings == ()


def test_same_amount_twice_is_single_set():
    # Distinct-by-value -> one amount -> SET, never sum (would be 100000).
    r = extract_amount("Restitution $500.00 and $500.00")
    assert r.amount_cents == 50000
    assert r.warnings == ()


def test_branch1_no_dollar_is_absent_no_warning():
    # A monetary component that simply states no amount: unset, NO warning ->
    # the caller emits no money item (amount legitimately absent).
    r = extract_amount("Fines and Costs")
    assert r.amount_cents is None
    assert r.warnings == ()


def test_branch2_dollar_present_but_unparseable_warns():
    # A `$` with nothing parseable after it -> present-but-unreadable.
    r = extract_amount("Fines and Costs $")
    assert r.amount_cents is None
    assert r.warnings == (NORM_UNPARSEABLE_AMOUNT,)


def test_branch4_multiple_distinct_amounts_unset_and_warns():
    r = extract_amount("Restitution $100.00 plus costs $250.00")
    assert r.amount_cents is None
    assert r.warnings == (NORM_UNPARSEABLE_AMOUNT,)


def test_duration_figures_are_not_money():
    # `$`-required: "11.00 months" / "23.00 months" carry no `$` -> not money,
    # no warning (this is the whole point of the recon-locked regex).
    r = extract_amount("Confinement Min of 11.00 Max of 23.00 months")
    assert r.amount_cents is None
    assert r.warnings == ()


def test_extracted_amount_is_integer_cents():
    r = extract_amount("$1,234.56")
    assert isinstance(r.amount_cents, int)
    assert not isinstance(r.amount_cents, bool)
    assert r.amount_cents == 123456
