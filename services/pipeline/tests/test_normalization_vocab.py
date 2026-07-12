"""Normalization vocabularies + review_needed derivation (Task 22.1).

Locks the two closed vocabularies (match methods, warning codes), the
MATCHED_METHODS subset, the blocking-warning set, and every arm of the
review_needed map.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.normalization import vocab as v


def test_no_psycopg_import_in_normalization_package():
    # Acceptance criterion 6: no DB access — psycopg is imported nowhere in the
    # new package's source (models, vocab, review_items, __init__).
    pkg = Path(v.__file__).parent
    sources = sorted(pkg.glob("*.py"))
    assert sources, "expected normalization package sources to exist"
    for path in sources:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            assert not stripped.startswith(("import psycopg", "from psycopg")), (
                f"psycopg imported in {path.name}"
            )


def test_match_methods_are_exactly_the_locked_six():
    assert v.MATCH_METHODS == {
        "exact",
        "alias",
        "statute",
        "pattern",
        "unmatched",
        "ambiguous",
    }
    assert len(v.MATCH_METHODS) == 6


def test_matched_methods_are_the_four_identity_carrying_methods():
    assert v.MATCHED_METHODS == {"exact", "alias", "statute", "pattern"}
    # The non-matched methods are exactly unmatched + ambiguous.
    assert v.MATCH_METHODS - v.MATCHED_METHODS == {"unmatched", "ambiguous"}


def test_warning_codes_are_exactly_the_locked_five():
    assert v.NORM_WARNING_CODES == {
        "NORM_UNMATCHED",
        "NORM_AMBIGUOUS",
        "NORM_STATUTE_TEXT_CONFLICT",
        "NORM_UNPARSEABLE_AMOUNT",
        "NORM_EMPTY_INPUT",
    }
    assert len(v.NORM_WARNING_CODES) == 5


def test_named_constants_match_membership():
    for method in (
        v.MATCH_METHOD_EXACT,
        v.MATCH_METHOD_ALIAS,
        v.MATCH_METHOD_STATUTE,
        v.MATCH_METHOD_PATTERN,
        v.MATCH_METHOD_UNMATCHED,
        v.MATCH_METHOD_AMBIGUOUS,
    ):
        assert method in v.MATCH_METHODS
    for code in (
        v.NORM_UNMATCHED,
        v.NORM_AMBIGUOUS,
        v.NORM_STATUTE_TEXT_CONFLICT,
        v.NORM_UNPARSEABLE_AMOUNT,
        v.NORM_EMPTY_INPUT,
    ):
        assert code in v.NORM_WARNING_CODES


def test_blocking_warnings_is_exactly_statute_text_conflict():
    assert v.NORM_BLOCKING_WARNINGS == {"NORM_STATUTE_TEXT_CONFLICT"}
    assert v.NORM_BLOCKING_WARNINGS <= v.NORM_WARNING_CODES


# --- review_needed map: all three arms (acceptance criterion 3) -------------


def test_review_needed_unmatched_arm_is_true():
    assert v.derive_review_needed("unmatched", ()) is True
    # True regardless of warnings.
    assert v.derive_review_needed("unmatched", ("NORM_UNMATCHED",)) is True


def test_review_needed_ambiguous_arm_is_true():
    assert v.derive_review_needed("ambiguous", ()) is True
    assert v.derive_review_needed("ambiguous", ("NORM_AMBIGUOUS",)) is True


def test_review_needed_matched_without_blocking_warning_is_false():
    assert v.derive_review_needed("exact", ()) is False
    assert v.derive_review_needed("alias", ()) is False
    assert v.derive_review_needed("statute", ()) is False
    assert v.derive_review_needed("pattern", ()) is False


def test_review_needed_matched_with_blocking_warning_is_true():
    assert v.derive_review_needed("statute", ("NORM_STATUTE_TEXT_CONFLICT",)) is True
    # Mixed: a blocking warning anywhere in the list flips it True.
    assert (
        v.derive_review_needed(
            "exact", ("NORM_EMPTY_INPUT", "NORM_STATUTE_TEXT_CONFLICT")
        )
        is True
    )


def test_review_needed_matched_with_non_blocking_warning_is_false():
    # A warning that is NOT in the blocking set does not flip a matched result.
    assert v.derive_review_needed("exact", ("NORM_UNPARSEABLE_AMOUNT",)) is False


def test_derive_review_needed_rejects_unknown_method():
    with pytest.raises(ValueError):
        v.derive_review_needed("fuzzy", ())


def test_derive_review_needed_rejects_unknown_warning_code():
    with pytest.raises(ValueError):
        v.derive_review_needed("exact", ("NOPE",))
