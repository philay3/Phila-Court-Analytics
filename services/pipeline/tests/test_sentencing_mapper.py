"""Tier-1 synthetic tests for the pure sentencing mapper (Task 22.5, AC 1-7).

Covers every ``sentence_type`` in the approved base table, the unmapped ->
``unknown`` + review path, the no-fuzzy-match rule, additive restitution /
community-service detection (components never collapsed), the ambiguous
hours-only path, the money single/multiple/zero branches on monetary components
(and money NOT read on non-monetary ones), taxonomy-version stamping, the
construction-time code / public checks, dedup-key stability + parsed-UUID
exclusion, the Phase-23 duration helper, and the real-taxonomy loader. All inputs
are synthetic or CPCMS sentence-type vocabulary; no raw docket text.
"""

from __future__ import annotations

import pytest

from pipeline import fact_review_vocab as fv
from pipeline.normalization.review_items import DEDUP_KEY_SEPARATOR
from pipeline.normalization.sentencing_mapper import (
    CATEGORY_COMMUNITY_SERVICE,
    CATEGORY_RESTITUTION,
    ENTITY_SENTENCING,
    SENTENCE_TYPE_CATEGORY_MAP,
    SENTENCING_UNKNOWN,
    SOURCE_COMMUNITY_SERVICE,
    SOURCE_RESTITUTION,
    SOURCE_SENTENCE_TYPE,
    SentencingCategoryMapping,
    SentencingMapper,
    SentencingTaxonomy,
    build_duration_review_item,
    build_sentencing_review_items,
    load_sentencing_taxonomy,
)

# --- synthetic taxonomy (the 9 sentencing codes; a test-only version so the
# stamping tests prove the INJECTED version flows through, not a hardcoded one) --
SYNTH_VERSION = "9.9.9-test"
SYNTH_PUBLIC: dict[str, bool] = {
    "probation": True,
    "incarceration": True,
    "fine": True,
    "restitution": True,
    "community_service": True,
    "no_further_penalty": True,
    "costs_fees": True,
    "other": True,
    "unknown": False,
}
SYNTH_TAXONOMY = SentencingTaxonomy(
    taxonomy_version=SYNTH_VERSION, public_by_code=SYNTH_PUBLIC
)


@pytest.fixture
def mapper() -> SentencingMapper:
    return SentencingMapper(SYNTH_TAXONOMY)


# --- base exact-match table (AC 1) -------------------------------------------
@pytest.mark.parametrize(
    ("sentence_type", "expected_code"),
    [
        ("Confinement", "incarceration"),
        ("Probation", "probation"),
        ("No Further Penalty", "no_further_penalty"),
        ("ARD", "other"),
        ("Fines and Costs", "costs_fees"),
        ("IPP", "other"),
    ],
)
def test_base_map_every_sentence_type(mapper, sentence_type, expected_code):
    result = mapper.map(sentence_type, "")
    base = result.base
    assert base.category_code == expected_code
    assert base.source == SOURCE_SENTENCE_TYPE
    assert base.mapped is True
    assert base.public_eligible is True
    assert result.taxonomy_version == SYNTH_VERSION
    assert result.review_needed is False


def test_base_map_matches_locked_keys():
    assert set(SENTENCE_TYPE_CATEGORY_MAP) == {
        "Confinement",
        "Probation",
        "No Further Penalty",
        "ARD",
        "Fines and Costs",
        "IPP",
    }


# --- unmapped -> unknown + review (AC 5) -------------------------------------
def test_unmapped_sentence_type_is_unknown_and_needs_review(mapper):
    result = mapper.map("Some New Disposition Type", "")
    base = result.base
    assert base.category_code == SENTENCING_UNKNOWN
    assert base.mapped is False
    assert base.public_eligible is False
    assert result.review_needed is True


def test_no_fuzzy_matching(mapper):
    # Exact-match only: casing/whitespace variants do NOT match the table.
    assert mapper.map("confinement", "").base.category_code == SENTENCING_UNKNOWN
    assert mapper.map("Confinement ", "").base.category_code == SENTENCING_UNKNOWN
    assert mapper.map("Probation (County)", "").base.category_code == SENTENCING_UNKNOWN


def test_unknown_is_never_public_eligible(mapper):
    # Enforced at construction against the taxonomy AND on the result.
    result = mapper.map("garbage", "")
    assert result.base.public_eligible is False
    assert SYNTH_PUBLIC["unknown"] is False


# --- additive detection, never collapsed (AC 2) ------------------------------
def test_restitution_adds_category_on_same_component(mapper):
    result = mapper.map("Probation", "Probation, Restitution $500.00")
    codes = [(c.category_code, c.source) for c in result.categories]
    assert codes == [
        ("probation", SOURCE_SENTENCE_TYPE),
        (CATEGORY_RESTITUTION, SOURCE_RESTITUTION),
    ]
    # additive is a SECOND mapping on the same component — base is untouched.
    assert result.base.category_code == "probation"


def test_community_service_literal_adds_category(mapper):
    result = mapper.map("Probation", "Probation Community Service 40 hours")
    sources = {c.source for c in result.categories}
    assert SOURCE_COMMUNITY_SERVICE in sources
    cs = next(c for c in result.categories if c.source == SOURCE_COMMUNITY_SERVICE)
    assert cs.category_code == CATEGORY_COMMUNITY_SERVICE
    # literal "Community Service" present -> NOT ambiguous.
    assert result.ambiguous_community_service is False


def test_hours_only_is_ambiguous_not_a_silent_add(mapper):
    result = mapper.map("Confinement", "Confinement 40 hours")
    # No community_service category added (conservative false-negative bias)...
    assert all(c.category_code != CATEGORY_COMMUNITY_SERVICE for c in result.categories)
    # ...but flagged for review.
    assert result.ambiguous_community_service is True
    assert result.review_needed is True


def test_restitution_and_community_service_both_added(mapper):
    result = mapper.map(
        "Probation", "Probation Restitution $50.00 Community Service 10 hours"
    )
    codes = {c.category_code for c in result.categories}
    assert codes == {"probation", CATEGORY_RESTITUTION, CATEGORY_COMMUNITY_SERVICE}


# --- money branches (AC 3) ---------------------------------------------------
def test_money_single_amount_set_on_monetary_component(mapper):
    result = mapper.map("Fines and Costs", "Fines and Costs Restitution $500.00")
    assert result.amount_cents == 50000
    assert result.money_unparseable is False
    assert result.review_needed is False


def test_money_multiple_distinct_unset_with_item_category_intact(mapper):
    result = mapper.map("ARD", "ARD Restitution $100.00 plus $250.00")
    assert result.amount_cents is None
    assert result.money_unparseable is True
    # category mapping STANDS (base + restitution both present).
    assert result.base.category_code == "other"
    assert any(c.category_code == CATEGORY_RESTITUTION for c in result.categories)


def test_money_absent_no_item_on_costs_fees(mapper):
    # Bare "Fines and Costs" (no `$`): amount unset, NO money item (branch 1).
    result = mapper.map("Fines and Costs", "Fines and Costs")
    assert result.money is not None  # it IS a monetary component
    assert result.amount_cents is None
    assert result.money_unparseable is False
    assert result.review_needed is False


def test_money_not_read_on_non_monetary_component(mapper):
    # Confinement (incarceration) with a stray `$` and no restitution -> money
    # is not extracted at all.
    result = mapper.map("Confinement", "Confinement 6 months $500.00")
    assert result.money is None
    assert result.amount_cents is None
    assert result.review_needed is False


def test_same_amount_twice_is_single_set(mapper):
    result = mapper.map("Confinement", "Confinement Restitution $500.00 $500.00")
    assert result.amount_cents == 50000
    assert result.money_unparseable is False


# --- durations consumed as parsed (AC 4) -------------------------------------
def test_durations_are_not_read_or_reparsed(mapper):
    # min/max duration figures never become money and never trigger review here.
    result = mapper.map("Confinement", "Confinement Min of 11.00 Max of 23.00 months")
    assert result.money is None
    assert result.amount_cents is None
    assert result.review_needed is False


# --- review items (AC 5) -----------------------------------------------------
def test_unmapped_review_item_shape(mapper):
    result = mapper.map("garbage", "")
    items = build_sentencing_review_items(
        result,
        source_document_id="doc-1",
        charge_sequence=3,
        component_order=2,
    )
    assert len(items) == 1
    item = items[0]
    assert item["item_type"] == fv.UNMAPPED_SENTENCING_COMPONENT
    assert item["reason_code"] == fv.SENTENCING_COMPONENT_NOT_NORMALIZED
    assert item["severity"] == fv.SEVERITY_MEDIUM
    assert item["entity_type"] == ENTITY_SENTENCING


def test_ambiguous_and_money_items(mapper):
    ambiguous = mapper.map("Confinement", "Confinement 40 hours")
    (item,) = build_sentencing_review_items(
        ambiguous, source_document_id="d", charge_sequence=1, component_order=1
    )
    assert item["item_type"] == fv.AMBIGUOUS_SENTENCING_COMPONENT
    assert item["reason_code"] == fv.SENTENCING_COMPONENT_NOT_NORMALIZED
    assert item["severity"] == fv.SEVERITY_MEDIUM

    money = mapper.map("ARD", "ARD Restitution $1.00 and $2.00")
    (mitem,) = build_sentencing_review_items(
        money, source_document_id="d", charge_sequence=1, component_order=1
    )
    assert mitem["item_type"] == fv.MONEY_UNPARSEABLE
    assert mitem["reason_code"] == fv.MONEY_AMOUNT_UNPARSEABLE
    assert mitem["severity"] == fv.SEVERITY_LOW


def test_clean_component_yields_no_review_items(mapper):
    result = mapper.map("Probation", "Probation, Restitution $500.00")
    items = build_sentencing_review_items(
        result, source_document_id="d", charge_sequence=1, component_order=1
    )
    assert items == []


def test_dedup_key_is_stable_and_excludes_parsed_uuids(mapper):
    result = mapper.map("garbage", "")
    (item,) = build_sentencing_review_items(
        result,
        source_document_id="src-uuid",
        charge_sequence=4,
        component_order=1,
        parsed_docket_id="PARSED-DOCKET",
        parsed_charge_id="PARSED-CHARGE",
        parsed_sentence_id="PARSED-SENTENCE",
    )
    # Key = source_document_id + item_type + (charge_sequence, component_order).
    assert item["dedup_key"] == DEDUP_KEY_SEPARATOR.join(
        ["src-uuid", fv.UNMAPPED_SENTENCING_COMPONENT, "4", "1"]
    )
    # Parsed UUIDs are carried as payload but NEVER enter the key.
    for parsed in ("PARSED-DOCKET", "PARSED-CHARGE", "PARSED-SENTENCE"):
        assert parsed not in item["dedup_key"]
    assert item["parsed_sentence_id"] == "PARSED-SENTENCE"


def test_multiple_items_have_distinct_keys(mapper):
    # An unmapped base with a restitution money multiple -> two items, two keys.
    result = mapper.map("garbage", "Restitution $1.00 and $2.00")
    items = build_sentencing_review_items(
        result, source_document_id="d", charge_sequence=1, component_order=1
    )
    item_types = {i["item_type"] for i in items}
    assert item_types == {fv.UNMAPPED_SENTENCING_COMPONENT, fv.MONEY_UNPARSEABLE}
    assert len({i["dedup_key"] for i in items}) == 2


# --- duration helper (AC 4/6; Phase-23-wired) --------------------------------
def test_build_duration_review_item():
    item = build_duration_review_item(
        source_document_id="src",
        charge_sequence=2,
        component_order=1,
        parsed_sentence_id="PARSED",
        raw_value="Confinement",
    )
    assert item["item_type"] == fv.DURATION_UNPARSEABLE
    assert item["reason_code"] == fv.SENTENCE_DURATION_UNPARSEABLE
    assert item["severity"] == fv.SEVERITY_LOW
    assert item["dedup_key"] == DEDUP_KEY_SEPARATOR.join(
        ["src", fv.DURATION_UNPARSEABLE, "2", "1"]
    )
    assert "PARSED" not in item["dedup_key"]


# --- construction-time checks (AC 1/5) ---------------------------------------
def test_construction_rejects_code_absent_from_taxonomy():
    bad_map = {"Confinement": "not_a_real_code"}
    with pytest.raises(ValueError, match="not in taxonomy"):
        SentencingMapper(SYNTH_TAXONOMY, bad_map)


def test_construction_rejects_public_unknown():
    bad_taxonomy = SentencingTaxonomy(
        taxonomy_version="x",
        public_by_code={**SYNTH_PUBLIC, "unknown": True},
    )
    with pytest.raises(ValueError, match="non-public"):
        SentencingMapper(bad_taxonomy)


def test_category_mapping_rejects_public_unknown():
    with pytest.raises(ValueError, match="public"):
        SentencingCategoryMapping(
            category_code=SENTENCING_UNKNOWN,
            source=SOURCE_SENTENCE_TYPE,
            public_eligible=True,
            mapped=False,
        )


def test_category_mapping_rejects_unmapped_non_unknown():
    with pytest.raises(ValueError, match="unknown"):
        SentencingCategoryMapping(
            category_code="probation",
            source=SOURCE_SENTENCE_TYPE,
            public_eligible=True,
            mapped=False,
        )


# --- real taxonomy loader (AC 1) ---------------------------------------------
def test_real_loader_reads_sentencing_categories():
    taxonomy = load_sentencing_taxonomy()
    assert taxonomy.taxonomy_version
    # `unknown` must be present and non-public; the mapper must construct on it.
    assert taxonomy.public_by_code[SENTENCING_UNKNOWN] is False
    for code in SENTENCE_TYPE_CATEGORY_MAP.values():
        assert code in taxonomy.public_by_code
    SentencingMapper(taxonomy)  # constructs without raising
