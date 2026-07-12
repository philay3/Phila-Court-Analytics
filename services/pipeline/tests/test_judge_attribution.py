"""Tier-1 synthetic tests for the pure judge-attribution resolver (Task 23.1).

Synthetic roster (fictional public-style names), zero-sequence placeholder docket
numbers, synthetic ``source_document_id`` UUID-shaped strings. No real docket
data. Covers every behavioral arm of pinned SD 1 and the 23.1 plan gates:
disposition-judge match; the APPROVED docket-scoped assigned-judge fallback;
no-match => none; ambiguous disposition => review + none (pinned #6); sibling-charge
fallback suppression (a matched disposition judge disqualifies the whole docket);
the DP1 captured-then-nulled guardrail (SUSPECT_JUDGE_LINE / SENTINEL_COLLISION);
present-but-unmatched suppression; the AttributionResult invariants; and the
descriptor's dedup-key stability + parsed-UUID exclusion.
"""

from __future__ import annotations

import pytest

from pipeline import fact_review_vocab as fv
from pipeline.facts.judge_attribution import (
    ATTRIBUTION_METHODS,
    DISPOSITION_JUDGE_NULLED_WARNING_CODES,
    METHOD_ASSIGNED_JUDGE_RULE,
    METHOD_DISPOSITION_JUDGE,
    METHOD_NONE,
    AttributionResult,
    DocketAttributionContext,
    build_docket_context,
    resolve_charge,
)
from pipeline.normalization.judge_matcher import (
    JudgeMatcher,
    RosterEntry,
    RosterSnapshot,
)
from pipeline.normalization.review_items import DEDUP_KEY_SEPARATOR
from pipeline.warning_codes import SUSPECT_JUDGE_LINE

# --- synthetic roster (natural-order display; fictional public-style names) ---
# j2/j3 differ ONLY by middle name, so a middle-less captured value is ambiguous
# across them (drives the pinned #6 ambiguous-attribution path).
ROSTER = RosterSnapshot(
    entries=(
        RosterEntry("j1", "coyle-anne-marie", "Anne Marie Coyle"),
        RosterEntry("j2", "reyes-john-quinn", "John Quinn Reyes"),
        RosterEntry("j3", "reyes-john-robert", "John Robert Reyes"),
        RosterEntry("j4", "okafor-maria", "Maria Okafor"),
    )
)
MATCHER = JudgeMatcher(ROSTER)

SRC = "00000000-0000-4000-8000-000000000001"  # synthetic source_document_id


def _charge(sequence, disposition_judge_raw=None, warning_codes=()):
    return {
        "sequence": sequence,
        "disposition_judge_raw": disposition_judge_raw,
        "warning_codes": tuple(warning_codes),
    }


def _docket(assigned_judge_raw, charges):
    return {"assigned_judge_raw": assigned_judge_raw, "charges": list(charges)}


# --- AC 6: disposition-judge match (primary path, pinned #1) ------------------
def test_disposition_judge_match_attributes_that_judge():
    docket = _docket("Anne Marie Coyle", [_charge(1, "Coyle, Anne Marie")])
    ctx = build_docket_context(docket, MATCHER)
    result = resolve_charge(docket["charges"][0], ctx, MATCHER, source_document_id=SRC)
    assert result.method == METHOD_DISPOSITION_JUDGE
    assert result.normalized_judge_id == "j1"
    assert result.review_descriptor is None
    # Disposition signal present -> docket NOT fallback-eligible even though the
    # assigned judge is also matched.
    assert ctx.fallback_eligible is False


# --- AC 6: the APPROVED assigned-judge fallback (pinned #2) -------------------
def test_assigned_only_fallback_rule():
    # No charge has a roster-matched disposition judge; assigned matches -> the
    # absent-disposition charge is attributed to the assigned judge.
    docket = _docket("Maria Okafor", [_charge(1, None)])
    ctx = build_docket_context(docket, MATCHER)
    assert ctx.fallback_eligible is True
    assert ctx.assigned_judge_id == "j4"
    result = resolve_charge(docket["charges"][0], ctx, MATCHER, source_document_id=SRC)
    assert result.method == METHOD_ASSIGNED_JUDGE_RULE
    assert result.normalized_judge_id == "j4"
    assert result.review_descriptor is None


# --- AC 6: no match => method=none -------------------------------------------
def test_no_match_is_none_when_assigned_absent():
    docket = _docket(None, [_charge(1, None)])
    ctx = build_docket_context(docket, MATCHER)
    assert ctx.fallback_eligible is False
    result = resolve_charge(docket["charges"][0], ctx, MATCHER, source_document_id=SRC)
    assert result.method == METHOD_NONE
    assert result.normalized_judge_id is None
    assert result.review_descriptor is None


def test_no_match_is_none_when_assigned_unmatched():
    docket = _docket("Nonexistent Offbench Person", [_charge(1, None)])
    ctx = build_docket_context(docket, MATCHER)
    assert ctx.assigned_judge_id is None
    assert ctx.fallback_eligible is False
    result = resolve_charge(docket["charges"][0], ctx, MATCHER, source_document_id=SRC)
    assert result.method == METHOD_NONE


# --- present-but-unmatched disposition => none, never fallback ---------------
def test_present_but_unmatched_disposition_never_falls_back():
    # Disposition judge present but off-roster; assigned matches. The charge
    # captured its own (unresolved) judge -> none, not assigned_judge_rule.
    docket = _docket("Maria Okafor", [_charge(1, "Unknown Offbench Name")])
    ctx = build_docket_context(docket, MATCHER)
    # An unmatched disposition contributes no matched id, so the docket is still
    # fallback-eligible in the aggregate...
    assert ctx.fallback_eligible is True
    result = resolve_charge(docket["charges"][0], ctx, MATCHER, source_document_id=SRC)
    # ...but THIS charge is present-but-unresolved, so it does not fall back.
    assert result.method == METHOD_NONE
    assert result.review_descriptor is None


# --- AC 6 / pinned #6: ambiguous disposition => review + none ----------------
def test_ambiguous_disposition_routes_to_review_and_none():
    # "John Reyes" is ambiguous across j2 (John Quinn) and j3 (John Robert).
    charge = _charge(3, "Reyes, John")
    docket = _docket("Maria Okafor", [charge])
    ctx = build_docket_context(docket, MATCHER)
    result = resolve_charge(charge, ctx, MATCHER, source_document_id=SRC)
    assert result.method == METHOD_NONE
    assert result.normalized_judge_id is None
    desc = result.review_descriptor
    assert desc is not None
    assert desc["item_type"] == fv.AMBIGUOUS_JUDGE_ATTRIBUTION
    assert desc["reason_code"] == fv.JUDGE_NOT_ATTRIBUTED
    assert desc["severity"] == fv.SEVERITY_HIGH
    assert desc["entity_type"] == "judge"
    # Two candidate identities are carried structurally (never a silent pick).
    candidates = desc["candidate_context"]["candidates"]
    assert {c["normalized_id"] for c in candidates} == {"j2", "j3"}


def test_ambiguous_disposition_does_not_create_docket_signal():
    # An ambiguous disposition is NOT a roster-matched disposition judge, so it
    # does not disqualify the docket from fallback for a sibling absent charge.
    ambiguous = _charge(1, "Reyes, John")
    absent = _charge(2, None)
    docket = _docket("Maria Okafor", [ambiguous, absent])
    ctx = build_docket_context(docket, MATCHER)
    assert ctx.fallback_eligible is True
    r_amb = resolve_charge(ambiguous, ctx, MATCHER, source_document_id=SRC)
    r_abs = resolve_charge(absent, ctx, MATCHER, source_document_id=SRC)
    assert r_amb.method == METHOD_NONE and r_amb.review_descriptor is not None
    assert r_abs.method == METHOD_ASSIGNED_JUDGE_RULE
    assert r_abs.normalized_judge_id == "j4"


# --- AC 6: multi-charge docket where only the disposition judge matches -------
def test_sibling_charge_fallback_suppression():
    # Charge 1 has a matched disposition judge -> the docket carries disposition
    # signal, so sibling charge 2 (absent) does NOT fall back to assigned.
    disp = _charge(1, "Coyle, Anne Marie")
    sibling = _charge(2, None)
    docket = _docket("Maria Okafor", [disp, sibling])
    ctx = build_docket_context(docket, MATCHER)
    assert ctx.fallback_eligible is False  # docket carries disposition signal
    r_disp = resolve_charge(disp, ctx, MATCHER, source_document_id=SRC)
    r_sib = resolve_charge(sibling, ctx, MATCHER, source_document_id=SRC)
    assert r_disp.method == METHOD_DISPOSITION_JUDGE
    assert r_disp.normalized_judge_id == "j1"
    assert r_sib.method == METHOD_NONE
    assert r_sib.normalized_judge_id is None


# --- DP1: captured-then-nulled disposition judge => none, never fallback ------
@pytest.mark.parametrize("code", sorted(DISPOSITION_JUDGE_NULLED_WARNING_CODES))
def test_captured_then_nulled_charge_never_falls_back(code):
    # Disposition judge is absent (nulled) BUT the charge carries the captured-
    # then-nulled warning; assigned matches. It must NOT fall back (DP1).
    charge = _charge(1, None, warning_codes=(code,))
    docket = _docket("Maria Okafor", [charge])
    ctx = build_docket_context(docket, MATCHER)
    assert ctx.fallback_eligible is True  # docket-level gate is open...
    result = resolve_charge(charge, ctx, MATCHER, source_document_id=SRC)
    # ...but the per-charge nulled guardrail suppresses this charge.
    assert result.method == METHOD_NONE
    assert result.normalized_judge_id is None
    assert result.review_descriptor is None


def test_nulled_charge_and_absent_sibling_only_sibling_falls_back():
    # A junk-nulled charge (1) is suppressed; a genuinely judge-less sibling (2)
    # on the same fallback-eligible docket still gets the assigned judge.
    nulled = _charge(1, None, warning_codes=(SUSPECT_JUDGE_LINE,))
    absent = _charge(2, None)
    docket = _docket("Maria Okafor", [nulled, absent])
    ctx = build_docket_context(docket, MATCHER)
    assert ctx.fallback_eligible is True
    r_nulled = resolve_charge(nulled, ctx, MATCHER, source_document_id=SRC)
    assert r_nulled.method == METHOD_NONE
    r_abs = resolve_charge(absent, ctx, MATCHER, source_document_id=SRC)
    assert r_abs.method == METHOD_ASSIGNED_JUDGE_RULE
    assert r_abs.normalized_judge_id == "j4"


def test_unrelated_warning_code_does_not_suppress_fallback():
    # A non-nulling warning code must not trip the DP1 guardrail.
    charge = _charge(1, None, warning_codes=("MISSING_DISPOSITION_DATE",))
    docket = _docket("Maria Okafor", [charge])
    ctx = build_docket_context(docket, MATCHER)
    result = resolve_charge(charge, ctx, MATCHER, source_document_id=SRC)
    assert result.method == METHOD_ASSIGNED_JUDGE_RULE
    assert result.normalized_judge_id == "j4"


# --- Directive 1: dedup key = source_document_id + locator only ---------------
def test_descriptor_dedup_key_excludes_parsed_uuids():
    charge = _charge(7, "Reyes, John")
    docket = _docket("Maria Okafor", [charge])
    ctx = build_docket_context(docket, MATCHER)
    a = resolve_charge(
        charge,
        ctx,
        MATCHER,
        source_document_id=SRC,
        parsed_docket_id="pd-AAAA",
        parsed_charge_id="pc-AAAA",
    ).review_descriptor
    b = resolve_charge(
        charge,
        ctx,
        MATCHER,
        source_document_id=SRC,
        parsed_docket_id="pd-ZZZZ",
        parsed_charge_id="pc-ZZZZ",
    ).review_descriptor
    # Same source_document_id + locator => identical dedup key despite different
    # parsed UUIDs (which ride as non-key context only).
    assert a["dedup_key"] == b["dedup_key"]
    assert a["parsed_docket_id"] != b["parsed_docket_id"]
    expected = DEDUP_KEY_SEPARATOR.join(
        [SRC, fv.AMBIGUOUS_JUDGE_ATTRIBUTION, "judge", "attribution", "7"]
    )
    assert a["dedup_key"] == expected
    assert "pd-AAAA" not in a["dedup_key"]


# --- AttributionResult invariants (unrepresentable invalid states) -----------
def test_attribution_result_invariants():
    with pytest.raises(ValueError):
        AttributionResult(normalized_judge_id=None, method="bogus")
    with pytest.raises(ValueError):
        # attributed method requires an id
        AttributionResult(normalized_judge_id=None, method=METHOD_DISPOSITION_JUDGE)
    with pytest.raises(ValueError):
        # method=none must not carry an id
        AttributionResult(normalized_judge_id="j1", method=METHOD_NONE)
    with pytest.raises(ValueError):
        # attributed method must not carry a descriptor
        AttributionResult(
            normalized_judge_id="j1",
            method=METHOD_ASSIGNED_JUDGE_RULE,
            review_descriptor={"x": 1},
        )
    # Valid constructions do not raise.
    ok = AttributionResult("j1", METHOD_DISPOSITION_JUDGE)
    assert ok.method in ATTRIBUTION_METHODS
    assert AttributionResult(None, METHOD_NONE).normalized_judge_id is None


def test_docket_context_invariant():
    with pytest.raises(ValueError):
        DocketAttributionContext(assigned_judge_id=None, fallback_eligible=True)
    # ambiguous assigned judge yields no id and no eligibility.
    docket = _docket("Reyes, John", [_charge(1, None)])
    ctx = build_docket_context(docket, MATCHER)
    assert ctx.assigned_judge_id is None
    assert ctx.fallback_eligible is False


# --- Inheritance-readiness (AC 5): context once, result reused ---------------
def test_result_is_reusable_for_inheritance():
    # 23.3 inherits the parent charge's result verbatim; the result is a plain
    # reusable value (a matched charge attribution reused across N components).
    charge = _charge(1, "Okafor, Maria")
    docket = _docket("Anne Marie Coyle", [charge])
    ctx = build_docket_context(docket, MATCHER)
    parent = resolve_charge(charge, ctx, MATCHER, source_document_id=SRC)
    assert parent.method == METHOD_DISPOSITION_JUDGE
    inherited = [parent for _ in range(3)]  # sentence components inherit the same
    assert all(r.normalized_judge_id == "j4" for r in inherited)
