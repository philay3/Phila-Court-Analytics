"""Tier-1 synthetic tests for the pure judge matcher (Task 22.3, AC 3-7).

Match-case fixtures use synthetic natural-order roster names; unmatched /
non-judge fixtures use fictional names; all docket identifiers are zero-sequence
placeholders. No real docket data. Covers every behavioral arm, the
comma/natural symmetry, middle-initial tolerance (incl. the initial<->full-name
bridge and the absent-middle wildcard in BOTH directions), the middle-initial
ambiguity arm, the fake-judge exclusion, role-context carry, dedup-key stability
+ UUID exclusion, and the statute/pattern-never-emitted rule.
"""

from __future__ import annotations

import pytest

from pipeline import fact_review_vocab as fv
from pipeline.normalization.judge_matcher import (
    ROLE_ASSIGNED,
    ROLE_DISPOSITION,
    CanonName,
    JudgeMatcher,
    RosterEntry,
    RosterSnapshot,
    build_judge_review_item,
    canonicalize_name,
    exclude_fake_judges,
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
    NORM_UNMATCHED,
)

# --- synthetic roster (natural-order display; fictional public-style names) ---

ROSTER = RosterSnapshot(
    entries=(
        RosterEntry("j1", "coyle-anne-marie", "Anne Marie Coyle"),
        RosterEntry("j2", "smith-john-quinn", "John Quinn Smith"),
        RosterEntry("j3", "smith-john-robert", "John Robert Smith"),
        RosterEntry("j4", "lopez-maria", "Maria Lopez"),
        # Compound surname: carries a comma-form alias so surname-first captured
        # values resolve (registering as `alias`, an accepted honest artifact).
        RosterEntry(
            "j5",
            "del-rio-anne-bianca",
            "Anne Bianca Del Rio",
            ("Del Rio, Anne Bianca",),
        ),
        RosterEntry("j6", "vaughn-robert-alan", "Robert Alan Vaughn", ("Bob Vaughn",)),
        # Hyphenated surname (single token after intra-punct deletion).
        RosterEntry("j7", "bryant-powell-crystal", "Crystal Bryant-Powell"),
        # Apostrophe surname + first-initial given ("J." must NOT be honorific).
        RosterEntry("j8", "okeefe-j-scott", "J. Scott O'Keefe"),
        # Generational suffix carried as a separate identity component.
        RosterEntry("j9", "sabatina-john-p-jr", "John P. Sabatina Jr."),
        # Two identities differing ONLY by generational suffix (Jr. vs Sr.).
        RosterEntry("j10", "vance-aaron-jr", "Aaron Vance Jr."),
        RosterEntry("j11", "vance-aaron-sr", "Aaron Vance Sr."),
    )
)


@pytest.fixture
def matcher() -> JudgeMatcher:
    return JudgeMatcher(ROSTER)


# --- canonicalization --------------------------------------------------------


def test_canonicalize_comma_and_natural_are_symmetric():
    assert canonicalize_name("Coyle, Anne Marie") == canonicalize_name(
        "Anne Marie Coyle"
    )
    assert canonicalize_name("Coyle, Anne Marie") == CanonName(
        ("coyle",), ("anne", "marie")
    )


def test_canonicalize_strips_honorifics_and_folds_case_punctuation():
    assert canonicalize_name("HON. COYLE, ANNE MARIE") == canonicalize_name(
        "Anne Marie Coyle"
    )
    assert canonicalize_name("The Honorable Judge Maria Lopez") == CanonName(
        ("lopez",), ("maria",)
    )
    assert canonicalize_name("  Lopez ,  Maria  ") == CanonName(("lopez",), ("maria",))


def test_canonicalize_absent_is_none():
    assert canonicalize_name(None) is None
    assert canonicalize_name("") is None
    assert canonicalize_name("   ") is None


# --- exact / alias / symmetry ------------------------------------------------


def test_exact_match_comma_form(matcher: JudgeMatcher):
    r = matcher.match("Coyle, Anne Marie")
    assert r is not None
    assert r.match_method == MATCH_METHOD_EXACT
    assert (r.normalized_id, r.display_name) == ("j1", "Anne Marie Coyle")
    assert r.review_needed is False
    assert r.warnings == ()


def test_exact_match_natural_and_comma_agree(matcher: JudgeMatcher):
    assert matcher.match("Vaughn, Robert Alan").normalized_id == "j6"
    assert matcher.match("Robert Alan Vaughn").normalized_id == "j6"


def test_alias_variant_match(matcher: JudgeMatcher):
    r = matcher.match("Bob Vaughn")
    assert r is not None
    assert r.match_method == MATCH_METHOD_ALIAS
    assert r.normalized_id == "j6"


def test_compound_surname_matches_via_comma_alias(matcher: JudgeMatcher):
    r = matcher.match("Del Rio, Anne Bianca")
    assert r is not None
    assert r.match_method == MATCH_METHOD_ALIAS
    assert r.normalized_id == "j5"


def test_honorific_stripped_exact(matcher: JudgeMatcher):
    assert matcher.match("Hon. Coyle, Anne Marie").normalized_id == "j1"


def test_hyphenated_surname_matches_both_orders(matcher: JudgeMatcher):
    comma = matcher.match("Bryant-Powell, Crystal")
    natural = matcher.match("Crystal Bryant-Powell")
    assert comma.normalized_id == natural.normalized_id == "j7"
    assert comma.match_method == MATCH_METHOD_EXACT


def test_apostrophe_surname_and_first_initial_are_preserved(matcher: JudgeMatcher):
    # "J." is a real first initial here, never stripped as a honorific.
    r = matcher.match("O'Keefe, J. Scott")
    assert r.match_method == MATCH_METHOD_EXACT
    assert r.normalized_id == "j8"
    assert matcher.match("J. Scott O'Keefe").normalized_id == "j8"


def test_generational_suffix_matches_and_distinguishes(matcher: JudgeMatcher):
    r = matcher.match("Sabatina, John P. Jr.")
    assert r.match_method == MATCH_METHOD_EXACT
    assert r.normalized_id == "j9"
    # A different PRESENT suffix does not collide with the Jr. identity.
    assert canonicalize_name("Sabatina, John P. Sr.") != canonicalize_name(
        "Sabatina, John P. Jr."
    )
    assert matcher.match("Sabatina, John P. Sr.").match_method == MATCH_METHOD_UNMATCHED


def test_absent_suffix_wildcard_unique_is_exact(matcher: JudgeMatcher):
    # Only j9 carries the (john, p) given under Sabatina; a lone-suffixed match is
    # covered above. Here: a captured value lacking a suffix against a UNIQUE
    # suffixed roster entry resolves exact (absent-suffix wildcard).
    snap = RosterSnapshot(
        entries=(RosterEntry("s1", "vance-aaron-jr", "Aaron Vance Jr."),)
    )
    r = JudgeMatcher(snap).match("Vance, Aaron")
    assert r.match_method == MATCH_METHOD_EXACT
    assert r.normalized_id == "s1"


def test_absent_suffix_two_identities_is_ambiguous(matcher: JudgeMatcher):
    # Captured value lacking a suffix, two roster identities differing ONLY by
    # Jr/Sr -> ambiguous + candidates, no silent pick (parallel to middle-initial).
    r = matcher.match("Vance, Aaron")
    assert r.match_method == MATCH_METHOD_AMBIGUOUS
    assert r.warnings == (NORM_AMBIGUOUS,)
    assert {c.normalized_id for c in r.candidates} == {"j10", "j11"}
    assert r.review_needed is True


def test_present_suffix_disambiguates(matcher: JudgeMatcher):
    assert matcher.match("Vance, Aaron Jr.").normalized_id == "j10"
    assert matcher.match("Vance, Aaron Sr.").normalized_id == "j11"


def test_roman_numeral_suffix_iii_is_identity():
    # The suffix-identity set includes III (e.g. Pittman III / Lewandowski III),
    # not only Jr/Sr.
    snap = RosterSnapshot(
        entries=(RosterEntry("p1", "pittman-joffie-c-iii", "Joffie C. Pittman III"),)
    )
    m = JudgeMatcher(snap)
    assert m.match("Pittman, Joffie C. III").match_method == MATCH_METHOD_EXACT
    assert m.match("Pittman, Joffie C. III").normalized_id == "p1"
    # Absent suffix -> unique III entry -> exact (wildcard).
    assert m.match("Pittman, Joffie C.").normalized_id == "p1"
    # A different PRESENT suffix does not collide with the III identity.
    assert m.match("Pittman, Joffie C. Jr.").match_method == MATCH_METHOD_UNMATCHED


def test_space_compound_surname_uses_comma_alias():
    # Barbara S. Thomson Previdi is a real space-separated compound surname: the
    # comma-form alias is load-bearing (natural-order parsing cannot recover the
    # compound). This is the live-roster path, beyond the synthetic Del Rio case.
    entry = RosterEntry(
        "tp",
        "thomson-previdi-barbara-s",
        "Barbara S. Thomson Previdi",
        ("Thomson Previdi, Barbara S.",),
    )
    m = JudgeMatcher(RosterSnapshot(entries=(entry,)))
    r = m.match("Thomson Previdi, Barbara S.")
    assert r.match_method == MATCH_METHOD_ALIAS
    assert r.normalized_id == "tp"
    # Without the alias, the compound surname is unrecoverable -> unmatched.
    no_alias = JudgeMatcher(
        RosterSnapshot(entries=(RosterEntry("tp", "x", "Barbara S. Thomson Previdi"),))
    )
    assert (
        no_alias.match("Thomson Previdi, Barbara S.").match_method
        == MATCH_METHOD_UNMATCHED
    )


# --- middle-initial tolerance (pinned decision 4) ----------------------------


def test_middle_initial_tolerant_is_exact(matcher: JudgeMatcher):
    # "M" bridges to full "Marie"; only one Coyle -> exact (tolerant).
    r = matcher.match("Coyle, Anne M")
    assert r is not None
    assert r.match_method == MATCH_METHOD_EXACT
    assert r.normalized_id == "j1"


def test_absent_middle_wildcard_unique_is_exact(matcher: JudgeMatcher):
    # Absent middle -> exactly one roster middle present -> exact.
    r = matcher.match("Coyle, Anne")
    assert r is not None
    assert r.match_method == MATCH_METHOD_EXACT
    assert r.normalized_id == "j1"


def test_absent_middle_wildcard_two_identities_is_ambiguous(matcher: JudgeMatcher):
    # Absent middle -> two identities differing only by middle -> ambiguous,
    # never a silent pick.
    r = matcher.match("Smith, John")
    assert r is not None
    assert r.match_method == MATCH_METHOD_AMBIGUOUS
    assert r.warnings == (NORM_AMBIGUOUS,)
    assert {c.normalized_id for c in r.candidates} == {"j2", "j3"}
    assert r.review_needed is True


def test_present_middle_initial_disambiguates(matcher: JudgeMatcher):
    assert matcher.match("Smith, John Q").normalized_id == "j2"
    assert matcher.match("Smith, John R").normalized_id == "j3"


# --- unmatched + non-distinction (pinned decision 3) -------------------------


def test_unmatched_non_judge_value(matcher: JudgeMatcher):
    r = matcher.match("Zzyzx, Quorra")  # fictional, name-shaped non-judge
    assert r is not None
    assert r.match_method == MATCH_METHOD_UNMATCHED
    assert r.warnings == (NORM_UNMATCHED,)
    assert r.normalized_id is None
    assert r.review_needed is True


def test_unmatched_roster_gap_is_same_arm(matcher: JudgeMatcher):
    # A genuine roster gap resolves to the IDENTICAL arm as a non-judge value:
    # the matcher structurally cannot distinguish the two.
    non_judge = matcher.match("Zzyzx, Quorra")
    roster_gap = matcher.match("Fairbanks, Gregory")  # fictional real-shaped judge
    assert roster_gap is not None and non_judge is not None
    assert roster_gap.match_method == non_judge.match_method == MATCH_METHOD_UNMATCHED


@pytest.mark.parametrize("value", [None, "", "   "])
def test_absent_input_returns_none(matcher: JudgeMatcher, value):
    assert matcher.match(value) is None


# --- statute / pattern never emitted (pinned decision 1) ---------------------


def test_statute_and_pattern_never_emitted(matcher: JudgeMatcher):
    inputs = [
        "Coyle, Anne Marie",
        "Coyle, Anne M",
        "Coyle, Anne",
        "Smith, John",
        "Smith, John Q",
        "Bob Vaughn",
        "Del Rio, Anne Bianca",
        "Zzyzx, Quorra",
        "Hon. Maria Lopez",
    ]
    for value in inputs:
        result = matcher.match(value)
        assert result is not None
        assert result.match_method not in {MATCH_METHOD_STATUTE, MATCH_METHOD_PATTERN}


# --- roster integrity guard --------------------------------------------------


def test_identical_canonical_key_fails_loud():
    dup = RosterSnapshot(
        entries=(
            RosterEntry("a1", "one", "Anne Marie Coyle"),
            RosterEntry("a2", "two", "Coyle, Anne Marie"),  # same canonical identity
        )
    )
    with pytest.raises(ValueError, match="canonical name key"):
        JudgeMatcher(dup)


# --- fake-judge exclusion (pinned decision 7, AC 5) --------------------------


def test_exclude_fake_judges_drops_fake_slugs():
    entries = (
        RosterEntry("r1", "coyle-anne-marie", "Anne Marie Coyle"),
        RosterEntry("f1", "judge-fakename-example", "Example, Fakename Realish"),
    )
    kept = exclude_fake_judges(entries)
    assert {e.slug for e in kept} == {"coyle-anne-marie"}


def test_real_value_cannot_resolve_to_fabricated_judge():
    # A fake seed whose display name is a real-docket-style value: after the
    # candidate-pool filter it is gone, so the matcher returns unmatched — never
    # the fabricated identity.
    with_fake = (
        RosterEntry("r1", "coyle-anne-marie", "Anne Marie Coyle"),
        RosterEntry("f1", "judge-fakename-example", "Fakename Realish Example"),
    )
    unfiltered = JudgeMatcher(RosterSnapshot(entries=with_fake))
    assert unfiltered.match("Example, Fakename Realish").normalized_id == "f1"

    filtered = JudgeMatcher(RosterSnapshot(entries=exclude_fake_judges(with_fake)))
    assert (
        filtered.match("Example, Fakename Realish").match_method
        == MATCH_METHOD_UNMATCHED
    )


# --- role-context carry + review items (pinned decisions 6, 9; AC 4, 6) ------


def test_clean_match_emits_no_review_item(matcher: JudgeMatcher):
    r = matcher.match("Coyle, Anne Marie")
    assert (
        build_judge_review_item(r, source_document_id="src-1", role=ROLE_ASSIGNED)
        is None
    )


def test_absent_result_emits_no_review_item():
    assert (
        build_judge_review_item(None, source_document_id="src-1", role=ROLE_ASSIGNED)
        is None
    )


def test_unmatched_assigned_emits_unmapped_judge_item(matcher: JudgeMatcher):
    r = matcher.match("Zzyzx, Quorra")
    item = build_judge_review_item(r, source_document_id="src-1", role=ROLE_ASSIGNED)
    assert item is not None
    assert item["item_type"] == fv.UNMAPPED_JUDGE
    assert item["reason_code"] == fv.JUDGE_NOT_NORMALIZED
    assert item["severity"] == fv.SEVERITY_MEDIUM
    assert item["entity_type"] == "judge"


def test_ambiguous_emits_high_severity_ambiguous_judge_item(matcher: JudgeMatcher):
    r = matcher.match("Smith, John")
    item = build_judge_review_item(r, source_document_id="src-1", role=ROLE_ASSIGNED)
    assert item is not None
    assert item["item_type"] == fv.AMBIGUOUS_JUDGE
    assert item["reason_code"] == fv.JUDGE_NOT_NORMALIZED
    assert item["severity"] == fv.SEVERITY_HIGH
    assert item["candidate_context"] == {
        "candidates": [
            {"normalized_id": "j2", "display_name": "John Quinn Smith"},
            {"normalized_id": "j3", "display_name": "John Robert Smith"},
        ]
    }


def test_assigned_and_disposition_on_one_docket_are_distinct(matcher: JudgeMatcher):
    # Pinned decision 6: two roles on one source document -> two distinct items,
    # never merged. The role lives in the dedup locator.
    r = matcher.match("Zzyzx, Quorra")
    assigned = build_judge_review_item(
        r, source_document_id="src-1", role=ROLE_ASSIGNED
    )
    disposition = build_judge_review_item(
        r, source_document_id="src-1", role=ROLE_DISPOSITION, charge_sequence=2
    )
    assert assigned is not None and disposition is not None
    assert assigned["dedup_key"] != disposition["dedup_key"]
    assert assigned["dedup_key"] == DEDUP_KEY_SEPARATOR.join(
        ["src-1", fv.UNMAPPED_JUDGE, "judge", "assigned"]
    )
    assert disposition["dedup_key"] == DEDUP_KEY_SEPARATOR.join(
        ["src-1", fv.UNMAPPED_JUDGE, "judge", "disposition", "2"]
    )


def test_disposition_item_requires_charge_sequence(matcher: JudgeMatcher):
    r = matcher.match("Zzyzx, Quorra")
    with pytest.raises(ValueError, match="charge_sequence"):
        build_judge_review_item(r, source_document_id="src-1", role=ROLE_DISPOSITION)


def test_unknown_role_raises(matcher: JudgeMatcher):
    r = matcher.match("Zzyzx, Quorra")
    with pytest.raises(ValueError, match="role"):
        build_judge_review_item(r, source_document_id="src-1", role="presiding")


def test_dedup_key_excludes_parsed_uuids_and_is_stable(matcher: JudgeMatcher):
    r = matcher.match("Zzyzx, Quorra")
    without = build_judge_review_item(
        r, source_document_id="src-1", role=ROLE_DISPOSITION, charge_sequence=5
    )
    with_ids = build_judge_review_item(
        r,
        source_document_id="src-1",
        role=ROLE_DISPOSITION,
        charge_sequence=5,
        parsed_docket_id="parsed-docket-abc",
        parsed_charge_id="parsed-charge-xyz",
    )
    assert without is not None and with_ids is not None
    assert without["dedup_key"] == with_ids["dedup_key"]
    assert with_ids["parsed_docket_id"] == "parsed-docket-abc"
    assert with_ids["parsed_charge_id"] == "parsed-charge-xyz"


def test_dedup_key_changes_with_source_or_locator(matcher: JudgeMatcher):
    r = matcher.match("Zzyzx, Quorra")
    base = build_judge_review_item(
        r, source_document_id="src-1", role=ROLE_DISPOSITION, charge_sequence=5
    )
    other_doc = build_judge_review_item(
        r, source_document_id="src-2", role=ROLE_DISPOSITION, charge_sequence=5
    )
    other_seq = build_judge_review_item(
        r, source_document_id="src-1", role=ROLE_DISPOSITION, charge_sequence=6
    )
    other_role = build_judge_review_item(
        r, source_document_id="src-1", role=ROLE_ASSIGNED
    )
    keys = {
        item["dedup_key"]
        for item in (base, other_doc, other_seq, other_role)
        if item is not None
    }
    assert len(keys) == 4
