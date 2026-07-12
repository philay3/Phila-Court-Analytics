"""Tier-1 synthetic tests for the pure outcome mapper (Task 22.4, AC 2-7).

Covers every outcome category the approved exact-match table yields, the
unmapped -> ``unknown`` + review path, the held-charge carve-out (a held charge
yields no fact and no review item), the no-fuzzy-match rule, the AC-5 truncated-
form hygiene assertion, taxonomy-version stamping, the construction-time code /
public checks, dedup-key stability + parsed-UUID exclusion, and the real-taxonomy
loader. All fixtures are synthetic or standardized CPCMS disposition phrases; no
raw docket text, docket numbers, or defendant data.
"""

from __future__ import annotations

import pytest

from pipeline import fact_review_vocab as fv
from pipeline.normalization.outcome_mapper import (
    DISPOSITION_OUTCOME_MAP,
    ENTITY_DISPOSITION,
    OUTCOME_UNKNOWN,
    OutcomeMapper,
    OutcomeMappingResult,
    TaxonomySnapshot,
    build_outcome_review_item,
    charge_has_terminal_disposition,
    is_held_charge,
    load_taxonomy_snapshot,
)
from pipeline.normalization.review_items import DEDUP_KEY_SEPARATOR

# --- synthetic taxonomy (the 9 outcome codes; a test-only version string so the
# stamping tests prove the INJECTED version flows through, not a hardcoded one) --
SYNTH_VERSION = "9.9.9-test"
SYNTH_PUBLIC: dict[str, bool] = {
    "dismissed": True,
    "withdrawn": True,
    "guilty_plea": True,
    "guilty_verdict": True,
    "acquittal": True,
    "ard": True,
    "diversion": True,
    "other": True,
    "unknown": False,
}
SYNTH_TAXONOMY = TaxonomySnapshot(
    taxonomy_version=SYNTH_VERSION, public_by_code=SYNTH_PUBLIC
)

# The exact-match table yields precisely these seven categories.
EXPECTED_CATEGORIES = {
    "guilty_plea",
    "guilty_verdict",
    "dismissed",
    "acquittal",
    "ard",
    "withdrawn",
    "other",
}

# The six real corpus values that are NOT in the table (malformed/garbage
# captures) — each must route to unknown + one review item.
UNMAPPED_VALUES = [
    "DUI: High Rte of Alc (Bac.10 - <.16) 1st Off Guilty Plea - Negotiated M 75 § 3802 §§ B*",  # noqa: E501
    "26/2024",
    "DUI: Highest Rte of Alc (BAC .16+) 1st Off Guilty M 75 § 3802 §§ C*",
    "Nolo Contendere/Probation",
    "Permitting Violation - Accident Involving Damage Guilty S 75 § 3743 §§ A-P",
    "RD - County",
]


@pytest.fixture
def mapper() -> OutcomeMapper:
    return OutcomeMapper(SYNTH_TAXONOMY)


def make_charge(
    *, disposition_raw=None, disposition_date=None, sentences=()
) -> dict[str, object]:
    """A minimal parsed-charge dict with only the fields the held predicate reads."""
    return {
        "disposition_raw": disposition_raw,
        "disposition_date": disposition_date,
        "sentences": list(sentences),
    }


# --- mapped arm: every approved key -> its code (AC 2, AC 7) -------------------


@pytest.mark.parametrize(("raw", "code"), sorted(DISPOSITION_OUTCOME_MAP.items()))
def test_every_key_maps_to_its_approved_code(
    mapper: OutcomeMapper, raw: str, code: str
) -> None:
    result = mapper.map(raw)
    assert result is not None
    assert result.mapped is True
    assert result.review_needed is False
    assert result.outcome_code == code
    assert result.raw_value == raw
    assert result.taxonomy_version == SYNTH_VERSION
    assert result.public_eligible is True  # all seven mapped codes are public


def test_table_yields_exactly_the_expected_categories() -> None:
    assert set(DISPOSITION_OUTCOME_MAP.values()) == EXPECTED_CATEGORIES


def test_each_expected_category_is_reachable(mapper: OutcomeMapper) -> None:
    produced = set()
    for raw in DISPOSITION_OUTCOME_MAP:
        result = mapper.map(raw)
        assert result is not None
        produced.add(result.outcome_code)
    assert produced == EXPECTED_CATEGORIES


def test_mapped_result_builds_no_review_item(mapper: OutcomeMapper) -> None:
    result = mapper.map("Guilty Plea - Negotiated")
    assert (
        build_outcome_review_item(result, source_document_id="doc-1", charge_sequence=1)
        is None
    )


# --- unmapped arm: terminal value not in table -> unknown + review (AC 3) ------


def test_unmapped_terminal_returns_unknown_and_review(mapper: OutcomeMapper) -> None:
    result = mapper.map("Some Disposition Not In The Table")
    assert result is not None
    assert result.outcome_code == OUTCOME_UNKNOWN
    assert result.mapped is False
    assert result.review_needed is True
    assert result.public_eligible is False  # unknown is never public-eligible
    assert result.taxonomy_version == SYNTH_VERSION


@pytest.mark.parametrize("raw", UNMAPPED_VALUES)
def test_real_unmapped_corpus_values_route_to_unknown(
    mapper: OutcomeMapper, raw: str
) -> None:
    result = mapper.map(raw)
    assert result is not None
    assert result.outcome_code == OUTCOME_UNKNOWN
    assert result.review_needed is True
    assert result.public_eligible is False


def test_unmapped_builds_expected_review_item(mapper: OutcomeMapper) -> None:
    result = mapper.map("26/2024")
    item = build_outcome_review_item(
        result, source_document_id="doc-42", charge_sequence=3
    )
    assert item is not None
    assert item["item_type"] == fv.UNMAPPED_DISPOSITION
    assert item["reason_code"] == fv.DISPOSITION_NOT_MAPPED
    assert item["severity"] == fv.SEVERITY_MEDIUM
    assert item["status"] == fv.REVIEW_ITEM_STATUS_DEFAULT
    assert item["entity_type"] == ENTITY_DISPOSITION
    assert item["raw_value"] == "26/2024"
    assert item["source_document_id"] == "doc-42"
    assert item["dedup_key"] == DEDUP_KEY_SEPARATOR.join(
        ["doc-42", fv.UNMAPPED_DISPOSITION, "3"]
    )


def test_dedup_key_excludes_parsed_uuids(mapper: OutcomeMapper) -> None:
    result = mapper.map("RD - County")
    item = build_outcome_review_item(
        result,
        source_document_id="doc-7",
        charge_sequence=2,
        parsed_docket_id="parsed-docket-uuid",
        parsed_charge_id="parsed-charge-uuid",
    )
    assert item is not None
    assert "parsed-docket-uuid" not in item["dedup_key"]
    assert "parsed-charge-uuid" not in item["dedup_key"]
    assert item["dedup_key"] == DEDUP_KEY_SEPARATOR.join(
        ["doc-7", fv.UNMAPPED_DISPOSITION, "2"]
    )
    # ...but the parsed pointers are carried as re-anchoring payload columns.
    assert item["parsed_docket_id"] == "parsed-docket-uuid"
    assert item["parsed_charge_id"] == "parsed-charge-uuid"


# --- held carve-out: null disposition -> no fact, no review (AC 4, AC 7) -------


def test_null_disposition_maps_to_none(mapper: OutcomeMapper) -> None:
    assert mapper.map(None) is None


def test_held_charge_yields_no_fact_and_no_review(mapper: OutcomeMapper) -> None:
    charge = make_charge(disposition_raw=None, disposition_date=None, sentences=())
    assert is_held_charge(charge) is True
    # No fact: the mapper returns nothing for the held charge's null disposition.
    result = mapper.map(charge["disposition_raw"])  # type: ignore[arg-type]
    assert result is None
    # No review item either.
    assert (
        build_outcome_review_item(result, source_document_id="doc-1", charge_sequence=1)
        is None
    )


def test_held_predicate_true_only_when_all_terminal_fields_absent() -> None:
    held = make_charge(disposition_raw=None, disposition_date=None, sentences=())
    assert is_held_charge(held) is True
    assert charge_has_terminal_disposition(held) is False


@pytest.mark.parametrize(
    "charge",
    [
        make_charge(disposition_raw="Guilty"),
        make_charge(disposition_date="2024-01-02"),
        make_charge(sentences=[{"sentence_type": "probation"}]),
    ],
)
def test_terminal_charge_is_not_held(charge: dict[str, object]) -> None:
    assert charge_has_terminal_disposition(charge) is True
    assert is_held_charge(charge) is False


# --- no fuzzy matching: exact-match only (AC 2) --------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "guilty plea - negotiated",  # lower-cased
        "Guilty Plea - Negotiated ",  # trailing space
        " Guilty",  # leading space
        "Guilty Plea",  # substring of a longer key is itself a key -> mapped;
    ],
)
def test_near_miss_values_do_not_fuzzy_match(mapper: OutcomeMapper, raw: str) -> None:
    result = mapper.map(raw)
    assert result is not None
    if raw in DISPOSITION_OUTCOME_MAP:  # only the exact "Guilty Plea" is a real key
        assert result.mapped is True
    else:
        assert result.mapped is False
        assert result.outcome_code == OUTCOME_UNKNOWN


# --- AC 5: truncated-form hygiene ---------------------------------------------


def test_truncated_transferred_key_absent() -> None:
    # The 18.2 Class E repair rewrites "Transferred to Another" to its full form
    # before mapping, so the truncated key is unreachable and must NOT be present.
    assert "Transferred to Another" not in DISPOSITION_OUTCOME_MAP
    assert "Transferred to Another Jurisdiction" in DISPOSITION_OUTCOME_MAP
    assert DISPOSITION_OUTCOME_MAP["Transferred to Another Jurisdiction"] == "other"


def test_truncated_rule600_key_is_mapped_verbatim(mapper: OutcomeMapper) -> None:
    # A known UNREPAIRED parser truncation, mapped verbatim (future parser fix).
    result = mapper.map("Dismissed - Rule 600 (Speedy")
    assert result is not None
    assert result.outcome_code == "dismissed"


# --- taxonomy-version stamping (AC 2) -----------------------------------------


def test_taxonomy_version_stamped_on_mapped_and_unmapped(mapper: OutcomeMapper) -> None:
    mapped = mapper.map("Withdrawn")
    unmapped = mapper.map("nope")
    assert mapped is not None and unmapped is not None
    assert mapped.taxonomy_version == SYNTH_VERSION
    assert unmapped.taxonomy_version == SYNTH_VERSION


# --- construction-time checks -------------------------------------------------


def test_construction_rejects_map_code_absent_from_taxonomy() -> None:
    taxonomy = TaxonomySnapshot(
        taxonomy_version="1", public_by_code={"unknown": False, "dismissed": True}
    )
    with pytest.raises(ValueError, match="not in taxonomy"):
        OutcomeMapper(taxonomy)  # the real table uses guilty_plea etc.


def test_construction_rejects_public_unknown() -> None:
    public = dict(SYNTH_PUBLIC)
    public["unknown"] = True  # unknown must be non-public
    taxonomy = TaxonomySnapshot(taxonomy_version="1", public_by_code=public)
    with pytest.raises(ValueError, match="non-public"):
        OutcomeMapper(taxonomy)


def test_construction_rejects_bogus_code_in_custom_map() -> None:
    with pytest.raises(ValueError, match="not in taxonomy"):
        OutcomeMapper(SYNTH_TAXONOMY, {"Foo": "not_a_real_code"})


def test_result_rejects_contradictory_states() -> None:
    with pytest.raises(ValueError, match="must not need review"):
        OutcomeMappingResult(
            raw_value="x",
            outcome_code="dismissed",
            taxonomy_version="1",
            public_eligible=True,
            mapped=True,
            review_needed=True,
        )
    with pytest.raises(ValueError, match="carry the `unknown` code"):
        OutcomeMappingResult(
            raw_value="x",
            outcome_code="dismissed",
            taxonomy_version="1",
            public_eligible=True,
            mapped=False,
            review_needed=True,
        )


# --- real taxonomy loader (AC 2: codes + version come from taxonomy.json ONLY) --


def test_load_taxonomy_snapshot_reads_real_taxonomy() -> None:
    taxonomy = load_taxonomy_snapshot()
    assert taxonomy.taxonomy_version == "1.0.0"
    assert taxonomy.public_by_code["unknown"] is False
    # The nine outcome categories are all present.
    assert set(SYNTH_PUBLIC) <= set(taxonomy.public_by_code)


def test_every_table_code_is_a_real_taxonomy_code() -> None:
    real = load_taxonomy_snapshot().public_by_code
    for code in set(DISPOSITION_OUTCOME_MAP.values()) | {OUTCOME_UNKNOWN}:
        assert code in real


def test_mapper_constructs_and_maps_against_real_taxonomy() -> None:
    mapper = OutcomeMapper(load_taxonomy_snapshot())
    result = mapper.map("ARD - County")
    assert result is not None
    assert result.outcome_code == "ard"
    assert result.taxonomy_version == "1.0.0"
    assert result.public_eligible is True
