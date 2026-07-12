"""Tier-1 synthetic tests for the pure charge matcher (Task 22.2, AC 4/7).

All fixtures are fictional charge text (or public statute phrasing) with
zero-sequence placeholder identifiers — no real docket data. Covers every
behavioral arm, canonicalization edge cases, the pattern-never-emitted rule, and
review-item construction + dedup-key stability (including Required Fix 2).
"""

from __future__ import annotations

import pytest

from pipeline import fact_review_vocab as fv
from pipeline.normalization.charge_matcher import (
    ChargeMatcher,
    RosterEntry,
    RosterSnapshot,
    build_charge_review_item,
    canonicalize_statute,
    canonicalize_text,
)
from pipeline.normalization.review_items import DEDUP_KEY_SEPARATOR
from pipeline.normalization.vocab import (
    MATCH_METHOD_ALIAS,
    MATCH_METHOD_AMBIGUOUS,
    MATCH_METHOD_EXACT,
    MATCH_METHOD_PATTERN,
    MATCH_METHOD_STATUTE,
    MATCH_METHOD_UNMATCHED,
    NORM_AMBIGUOUS,
    NORM_EMPTY_INPUT,
    NORM_STATUTE_TEXT_CONFLICT,
    NORM_UNMATCHED,
)

# --- synthetic roster --------------------------------------------------------

ROSTER = RosterSnapshot(
    entries=(
        RosterEntry(
            "c1", "alpha-theft", "Alpha Theft", "18 § 9001", ("alpha shoplifting",)
        ),
        RosterEntry(
            "c2", "beta-assault", "Beta Assault", "18 § 9002 §§ A1", ("beta battery",)
        ),
        RosterEntry("c3", "gamma-first", "Gamma Offense", "18 § 9003", ()),
        RosterEntry("c4", "gamma-second", "Gamma Offense", "18 § 9004", ()),
        RosterEntry(
            "c5",
            "delta-drug",
            "Delta Substance",
            "35 § 780-113(a)(30)",
            ("delta delivery",),
        ),
        RosterEntry("c6", "epsilon-fraud", "Epsilon Fraud", "18 § 9006", ()),
        RosterEntry("c7", "dui-alpha", "Alpha DUI", "75 § 3802(a)(1)", ()),
    )
)


@pytest.fixture
def matcher() -> ChargeMatcher:
    return ChargeMatcher(ROSTER)


# --- canonicalization (pinned decision 2) ------------------------------------


def test_canonicalize_text_folds_case_punctuation_whitespace():
    assert canonicalize_text("DUI: General Impairment") == "dui general impairment"
    assert canonicalize_text("assault (simple)") == "assault simple"
    assert canonicalize_text("  Alpha   Theft! ") == "alpha theft"
    assert canonicalize_text(None) == ""
    assert canonicalize_text("   ") == ""


def test_canonicalize_statute_folds_observed_variants():
    assert canonicalize_statute("18 § 6106 §§ A1") == canonicalize_statute(
        "18 § 6106(a)(1)"
    )
    assert canonicalize_statute("18 § 6106 §§ A1") == "186106A1"
    assert canonicalize_statute("35 § 780-113 §§ A30") == "35780-113A30"
    assert canonicalize_statute("35 § 780-113(a)(30)") == "35780-113A30"
    assert canonicalize_statute("18 § 6301 §§ A1i") == "186301A1I"
    assert canonicalize_statute("18 § 6301(a)(1)(i)") == "186301A1I"
    assert canonicalize_statute(None) == ""


def test_canonicalize_statute_drops_dui_grading_asterisks():
    # Required Fix 3: trailing DUI grading-tier asterisks collapse to the same
    # subsection; different subsections stay distinct.
    assert canonicalize_statute("75 § 3802 §§ A1*") == canonicalize_statute(
        "75 § 3802 §§ A1"
    )
    assert canonicalize_statute("75 § 3802 §§ A1***") == "753802A1"
    assert canonicalize_statute("75 § 3802 §§ D1*") != canonicalize_statute(
        "75 § 3802 §§ D2****"
    )


# --- the seven behavioral arms (pinned decision 3) ---------------------------


def test_exact_match(matcher: ChargeMatcher):
    r = matcher.match(statute=None, offense="Alpha Theft")
    assert r.match_method == MATCH_METHOD_EXACT
    assert (r.normalized_id, r.display_name) == ("c1", "Alpha Theft")
    assert r.review_needed is False
    assert r.warnings == ()


def test_exact_match_is_case_and_punctuation_insensitive(matcher: ChargeMatcher):
    r = matcher.match(statute=None, offense="  alpha   THEFT! ")
    assert r.match_method == MATCH_METHOD_EXACT
    assert r.normalized_id == "c1"


def test_alias_match(matcher: ChargeMatcher):
    r = matcher.match(statute=None, offense="Alpha Shoplifting")
    assert r.match_method == MATCH_METHOD_ALIAS
    assert r.normalized_id == "c1"


def test_statute_match_when_text_unmatched(matcher: ChargeMatcher):
    r = matcher.match(statute="18 § 9006", offense="some unrecognized wording")
    assert r.match_method == MATCH_METHOD_STATUTE
    assert r.normalized_id == "c6"


def test_statute_match_across_formatting_variant(matcher: ChargeMatcher):
    r = matcher.match(statute="35 § 780-113 §§ A30", offense=None)
    assert r.match_method == MATCH_METHOD_STATUTE
    assert r.normalized_id == "c5"


def test_statute_match_with_dui_asterisk(matcher: ChargeMatcher):
    r = matcher.match(statute="75 § 3802 §§ A1*", offense=None)
    assert r.match_method == MATCH_METHOD_STATUTE
    assert r.normalized_id == "c7"


def test_agreeing_statute_does_not_fabricate_conflict(matcher: ChargeMatcher):
    # Text picks c1, statute also resolves to c1 -> clean exact, no conflict.
    r = matcher.match(statute="18 § 9001", offense="Alpha Theft")
    assert r.match_method == MATCH_METHOD_EXACT
    assert r.normalized_id == "c1"
    assert r.warnings == ()


def test_statute_text_conflict_is_ambiguous_and_blocks(matcher: ChargeMatcher):
    # Text -> c1, statute -> c6 (different entry): conflict.
    r = matcher.match(statute="18 § 9006", offense="Alpha Theft")
    assert r.match_method == MATCH_METHOD_AMBIGUOUS
    assert r.warnings == (NORM_STATUTE_TEXT_CONFLICT,)
    assert r.review_needed is True
    ids = {c.normalized_id for c in r.candidates}
    assert ids == {"c1", "c6"}


def test_same_tier_text_ambiguity(matcher: ChargeMatcher):
    r = matcher.match(statute=None, offense="Gamma Offense")
    assert r.match_method == MATCH_METHOD_AMBIGUOUS
    assert r.warnings == (NORM_AMBIGUOUS,)
    assert {c.normalized_id for c in r.candidates} == {"c3", "c4"}
    assert r.review_needed is True


def test_same_tier_statute_ambiguity():
    snap = RosterSnapshot(
        entries=(
            RosterEntry("x1", "x-one", "X One", "18 § 1234", ()),
            RosterEntry("x2", "x-two", "X Two", "18 § 1234", ()),
        )
    )
    r = ChargeMatcher(snap).match(statute="18 § 1234", offense=None)
    assert r.match_method == MATCH_METHOD_AMBIGUOUS
    assert r.warnings == (NORM_AMBIGUOUS,)
    assert {c.normalized_id for c in r.candidates} == {"x1", "x2"}


def test_unmatched(matcher: ChargeMatcher):
    r = matcher.match(statute="99 § 0000", offense="entirely unknown wording")
    assert r.match_method == MATCH_METHOD_UNMATCHED
    assert r.warnings == (NORM_UNMATCHED,)
    assert r.normalized_id is None
    assert r.review_needed is True


@pytest.mark.parametrize(
    ("statute", "offense"),
    [(None, None), ("   ", ""), ("", "   "), (None, "")],
)
def test_empty_input(matcher: ChargeMatcher, statute, offense):
    r = matcher.match(statute=statute, offense=offense)
    assert r.match_method == MATCH_METHOD_UNMATCHED
    assert r.warnings == (NORM_EMPTY_INPUT,)


def test_pattern_is_never_emitted(matcher: ChargeMatcher):
    inputs = [
        (None, "Alpha Theft"),
        (None, "Alpha Shoplifting"),
        ("18 § 9006", "zzz"),
        ("18 § 9006", "Alpha Theft"),
        (None, "Gamma Offense"),
        ("99 § 0000", "unknown"),
        (None, None),
        ("35 § 780-113 §§ A30", None),
    ]
    for statute, offense in inputs:
        assert (
            matcher.match(statute=statute, offense=offense).match_method
            != MATCH_METHOD_PATTERN
        )


# --- review-item construction (AC 4) + dedup stability (AC 7 / Fix 2) --------


def test_clean_match_emits_no_review_item(matcher: ChargeMatcher):
    r = matcher.match(statute=None, offense="Alpha Theft")
    assert (
        build_charge_review_item(r, source_document_id="src-1", charge_sequence=1)
        is None
    )


def test_unmatched_emits_unmapped_charge_item(matcher: ChargeMatcher):
    r = matcher.match(statute="99 § 0000", offense="unknown")
    item = build_charge_review_item(r, source_document_id="src-1", charge_sequence=2)
    assert item is not None
    assert item["item_type"] == fv.UNMAPPED_CHARGE
    assert item["reason_code"] == fv.CHARGE_NOT_NORMALIZED
    assert item["severity"] == fv.SEVERITY_MEDIUM
    assert item["entity_type"] == "charge"


def test_conflict_emits_high_severity_blocking_item(matcher: ChargeMatcher):
    r = matcher.match(statute="18 § 9006", offense="Alpha Theft")
    item = build_charge_review_item(r, source_document_id="src-1", charge_sequence=3)
    assert item is not None
    assert item["item_type"] == fv.AMBIGUOUS_CHARGE
    assert item["reason_code"] == fv.BLOCKING_WARNING
    assert item["severity"] == fv.SEVERITY_HIGH
    assert item["candidate_context"] == {
        "candidates": [
            {"normalized_id": "c1", "display_name": "Alpha Theft"},
            {"normalized_id": "c6", "display_name": "Epsilon Fraud"},
        ]
    }


def test_ambiguous_emits_medium_ambiguous_item(matcher: ChargeMatcher):
    r = matcher.match(statute=None, offense="Gamma Offense")
    item = build_charge_review_item(r, source_document_id="src-1", charge_sequence=4)
    assert item is not None
    assert item["item_type"] == fv.AMBIGUOUS_CHARGE
    assert item["reason_code"] == fv.CHARGE_NOT_NORMALIZED
    assert item["severity"] == fv.SEVERITY_MEDIUM


def test_dedup_key_excludes_parsed_uuids_and_is_stable(matcher: ChargeMatcher):
    # Required Fix 2: the parsed.* UUIDs never enter the dedup key.
    r = matcher.match(statute="99 § 0000", offense="unknown")
    without = build_charge_review_item(r, source_document_id="src-1", charge_sequence=7)
    with_ids = build_charge_review_item(
        r,
        source_document_id="src-1",
        charge_sequence=7,
        parsed_docket_id="parsed-docket-abc",
        parsed_charge_id="parsed-charge-xyz",
    )
    assert without is not None and with_ids is not None
    assert without["dedup_key"] == with_ids["dedup_key"]
    # The parsed ids are still carried as re-anchoring payload.
    assert with_ids["parsed_docket_id"] == "parsed-docket-abc"
    assert with_ids["parsed_charge_id"] == "parsed-charge-xyz"
    # Composition is exactly source_document_id | item_type | charge_sequence.
    assert without["dedup_key"] == DEDUP_KEY_SEPARATOR.join(
        ["src-1", fv.UNMAPPED_CHARGE, "7"]
    )


def test_dedup_key_changes_with_source_document_or_sequence(matcher: ChargeMatcher):
    r = matcher.match(statute="99 § 0000", offense="unknown")
    base = build_charge_review_item(r, source_document_id="src-1", charge_sequence=7)
    other_doc = build_charge_review_item(
        r, source_document_id="src-2", charge_sequence=7
    )
    other_seq = build_charge_review_item(
        r, source_document_id="src-1", charge_sequence=8
    )
    assert base is not None and other_doc is not None and other_seq is not None
    assert base["dedup_key"] != other_doc["dedup_key"]
    assert base["dedup_key"] != other_seq["dedup_key"]


# --- coexistence invariant (SD 8): no statute-canonical collision -----------


def test_demo_plus_real_roster_has_unique_canonical_statutes():
    # The coexistence design requires that no two roster rows (demo + real)
    # share a canonical statute code, else statute-tier matching turns spuriously
    # ambiguous. This mirrors the invariant the real seed must uphold; the six
    # values below are the public demo statute codes plus real subsection codes.
    codes = [
        "18 § 3929",  # demo retail theft (section-level)
        "18 § 2701",  # demo simple assault
        "75 § 3802(a)(1)",  # demo DUI
        "35 § 780-113(a)(16)",  # demo drug possession
        "18 § 3503",  # demo criminal trespass
        "18 § 2709",  # demo harassment
        "18 § 3929 §§ A1",  # real: distinct subsection of retail theft
        "35 § 780-113(a)(30)",  # real: distinct drug-act subsection
    ]
    canon = [canonicalize_statute(c) for c in codes]
    assert len(set(canon)) == len(canon)
