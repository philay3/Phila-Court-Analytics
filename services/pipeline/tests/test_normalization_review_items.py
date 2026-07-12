"""review.queue_items builder + dedup-key derivation (Task 22.1).

Vocabulary enforcement in both directions for every vocabulary-typed field
(item_type, severity, reason_code, status), dedup-key determinism, and the
proof that no parsed.* UUID enters the key composition.
"""

from __future__ import annotations

import pytest

from pipeline import fact_review_vocab as fv
from pipeline.normalization import DEDUP_KEY_SEPARATOR, build_review_item
from pipeline.normalization.review_items import build_dedup_key

VALID = {
    "source_document_id": "src-doc-1",
    "item_type": fv.UNMAPPED_CHARGE,
    "severity": fv.SEVERITY_HIGH,
    "reason_code": fv.CHARGE_NOT_NORMALIZED,
}


def test_valid_payload_has_every_writable_column():
    item = build_review_item(**VALID, locator=("7",))
    assert set(item) == {
        "item_type",
        "severity",
        "source_document_id",
        "parsed_docket_id",
        "parsed_charge_id",
        "parsed_sentence_id",
        "entity_type",
        "raw_value",
        "candidate_context",
        "reason_code",
        "status",
        "dedup_key",
    }
    # status defaults to the fact_review_vocab default.
    assert item["status"] == fv.REVIEW_ITEM_STATUS_DEFAULT


# --- REQUIRED FIX 3: every vocabulary-typed field validated, both directions -


def test_item_type_accepts_valid_and_rejects_invalid():
    assert build_review_item(**VALID)["item_type"] == fv.UNMAPPED_CHARGE
    with pytest.raises(ValueError):
        build_review_item(**{**VALID, "item_type": "not_a_type"})


def test_severity_accepts_valid_and_rejects_invalid():
    for sev in (fv.SEVERITY_HIGH, fv.SEVERITY_MEDIUM, fv.SEVERITY_LOW):
        assert build_review_item(**{**VALID, "severity": sev})["severity"] == sev
    with pytest.raises(ValueError):
        build_review_item(**{**VALID, "severity": "blocking"})


def test_reason_code_accepts_valid_and_rejects_invalid():
    assert build_review_item(**VALID)["reason_code"] == fv.CHARGE_NOT_NORMALIZED
    with pytest.raises(ValueError):
        build_review_item(**{**VALID, "reason_code": "made_up_reason"})


def test_status_accepts_valid_and_rejects_invalid():
    assert (
        build_review_item(**VALID, status=fv.STATUS_IN_REVIEW)["status"]
        == fv.STATUS_IN_REVIEW
    )
    with pytest.raises(ValueError):
        build_review_item(**VALID, status="archived")


# --- dedup-key determinism (acceptance criterion 5) -------------------------


def test_dedup_key_is_deterministic_across_calls():
    a = build_review_item(**VALID, locator=("7",))["dedup_key"]
    b = build_review_item(**VALID, locator=("7",))["dedup_key"]
    assert a == b


def test_dedup_key_composition_is_source_type_locator():
    key = build_dedup_key("src-doc-1", fv.UNMAPPED_CHARGE, ("7", "2"))
    assert key == DEDUP_KEY_SEPARATOR.join(["src-doc-1", fv.UNMAPPED_CHARGE, "7", "2"])


def test_dedup_key_changes_with_locator_and_type():
    base = build_dedup_key("src-doc-1", fv.UNMAPPED_CHARGE, ("7",))
    assert base != build_dedup_key("src-doc-1", fv.UNMAPPED_CHARGE, ("8",))
    assert base != build_dedup_key("src-doc-1", fv.AMBIGUOUS_CHARGE, ("7",))
    assert base != build_dedup_key("src-doc-2", fv.UNMAPPED_CHARGE, ("7",))


def test_dedup_key_excludes_parsed_uuids():
    # Two items differing ONLY in their parsed.* pointers must share a key: the
    # parsed UUIDs are demonstrably absent from the key composition.
    parsed_uuid = "11111111-2222-3333-4444-555555555555"
    with_parsed = build_review_item(
        **VALID,
        locator=("7",),
        parsed_docket_id=parsed_uuid,
        parsed_charge_id=parsed_uuid,
        parsed_sentence_id=parsed_uuid,
    )
    without_parsed = build_review_item(**VALID, locator=("7",))
    assert with_parsed["dedup_key"] == without_parsed["dedup_key"]
    assert parsed_uuid not in with_parsed["dedup_key"]


def test_dedup_key_rejects_empty_and_separator_parts():
    with pytest.raises(ValueError):
        build_dedup_key("", fv.UNMAPPED_CHARGE, ())
    with pytest.raises(ValueError):
        build_dedup_key("src", fv.UNMAPPED_CHARGE, ("",))
    with pytest.raises(ValueError):
        build_dedup_key("src", fv.UNMAPPED_CHARGE, (f"a{DEDUP_KEY_SEPARATOR}b",))


def test_parsed_pointers_are_stored_columns_not_keyed():
    parsed_uuid = "aaaa"
    item = build_review_item(
        **VALID,
        locator=("7",),
        parsed_docket_id=parsed_uuid,
        entity_type="judge",
        raw_value="18-2701",
    )
    assert item["parsed_docket_id"] == parsed_uuid
    assert item["entity_type"] == "judge"
    assert item["raw_value"] == "18-2701"
