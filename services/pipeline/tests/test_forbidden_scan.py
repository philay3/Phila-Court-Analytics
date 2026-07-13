"""Tier-1 tests for the Python forbidden-field scanner port (Task 28.1).

Two suites:

- Artifact-backed scan tests porting the ``@pca/shared`` checker self-tests
  (``packages/shared/src/forbidden-scan.test.ts``) fixture-for-fixture:
  every shared stem caught via a poisoned key (through casing/separator
  variants, nesting, and arrays), every shared value pattern caught via a
  poisoned value, and a realistic clean payload producing zero violations.
  Running the SAME adversarial fixtures against the artifact the Python
  scanner actually loads is the parity check: a stem or pattern added in
  ``forbidden-fields.ts`` without a matching poisoned fixture here fails the
  coverage assertions. The artifact is a build product (root
  ``pnpm generate``): absent locally -> skip; absent in CI -> hard failure
  (CI generates it before pytest).

- Pure loader tests over ``tmp_path`` artifacts: missing file, empty stem
  list, and unportable regex flags all fail loudly — a degenerate artifact
  must never scan as "clean".

Synthetic only: the poisoned docket-shaped strings are the same fabricated
``...-0001234-...`` style fixtures the shared TS suite commits; no real
docket data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.forbidden_scan import (
    ForbiddenTerms,
    ForbiddenViolation,
    load_forbidden_terms,
    scan_for_forbidden,
)
from pipeline.seam_check import running_in_ci

# One representative poisoned KEY per shared stem, ported byte-for-byte from
# forbidden-scan.test.ts. Keys embed the stem inside longer names (the check
# is CONTAINS on the normalized key), mixing casing/separator styles.
POISONED_KEY_BY_STEM = {
    "defendant": "defendantName",
    "docket": "docketNumber",
    "sourcedocument": "source_document_id",
    "sourceid": "sourceId",
    "sourceurl": "source-url",
    "storagekey": "storageKey",
    "rawtext": "raw_text",
    "extractedtext": "extractedText",
    "parseddocket": "parsed_docket_id",
    "parsedcharge": "parsedChargeId",
    "factid": "chargeOutcomeFactId",
    "reviewstatus": "review_status",
    "admincorrection": "adminCorrectionNote",
    "confidence": "parserConfidence",
}

# One poisoned string VALUE per shared value pattern, index-aligned with the
# artifact's valuePatterns list (ported from forbidden-scan.test.ts).
POISONED_VALUE_BY_PATTERN = ["Case CP-51-CR-0001234-2025 continued"]

# The TS suite's realistic clean charge-only result payload (8.1 contract
# shape) — the no-false-positive fixture.
CLEAN_CHARGE_ONLY_RESULT = {
    "charge": {
        "id": "3f0a2f9e-7f52-4e6b-8a53-0d5f4bfb0f6c",
        "slug": "retail-theft",
        "displayName": "Retail theft",
        "statuteCode": "18 § 3929",
        "grade": "M1",
    },
    "resultType": "charge_only",
    "geography": "philadelphia",
    "dateRange": {"start": "2020-01-01", "end": "2024-12-31"},
    "lastRefreshed": "2025-01-15T00:00:00.000Z",
    "taxonomyVersion": "1.0.0",
    "aggregateRunId": "9d3e7b1a-2c4f-4a8b-9e0d-6f5a3c2b1d0e",
    "outcomes": {
        "sampleSize": 1200,
        "thinData": False,
        "rows": [
            {
                "categoryCode": "dismissed",
                "displayName": "Dismissed",
                "count": 264,
                "percentage": 22,
            },
            {
                "categoryCode": "guilty_plea",
                "displayName": "Guilty plea",
                "count": 540,
                "percentage": 45,
            },
        ],
    },
    "sentencing": {
        "available": True,
        "sampleSize": 700,
        "thinData": False,
        "rows": [
            {
                "categoryCode": "probation",
                "displayName": "Probation",
                "count": 245,
                "percentage": 35,
            }
        ],
    },
}


@pytest.fixture(scope="module")
def terms() -> ForbiddenTerms:
    try:
        return load_forbidden_terms()
    except FileNotFoundError:
        if running_in_ci():
            pytest.fail(
                "forbidden-fields.json must exist in CI; the workflow runs "
                "`pnpm generate` before pytest."
            )
        pytest.skip("forbidden-fields.json not generated locally; run `pnpm generate`.")


# --------------------------------------------------------------------------- #
# Artifact-backed scan tests (ported TS checker self-tests).                 #
# --------------------------------------------------------------------------- #


def test_poisoned_key_fixtures_cover_every_artifact_stem(terms):
    assert sorted(POISONED_KEY_BY_STEM) == sorted(terms.field_stems)


def test_every_stem_caught_via_its_poisoned_key(terms):
    for stem, poisoned_key in POISONED_KEY_BY_STEM.items():
        violations = scan_for_forbidden({poisoned_key: "x"}, terms)
        # Membership, not equality: overlapping stems legitimately produce
        # extra violations (e.g. parsed_docket_id matches parseddocket AND
        # docket) — same posture as the TS suite's toContainEqual.
        assert (
            ForbiddenViolation(
                json_path=f"$.{poisoned_key}",
                kind="key",
                offender=poisoned_key,
                matched=stem,
            )
            in violations
        )


def test_camel_and_snake_case_variants_of_one_stem_both_caught(terms):
    for key in ("docketNumber", "docket_number"):
        violations = scan_for_forbidden({key: "x"}, terms)
        assert len(violations) == 1
        assert violations[0].kind == "key"
        assert violations[0].offender == key
        assert violations[0].matched == "docket"


def test_poisoned_key_nested_three_levels_deep_inside_an_array(terms):
    violations = scan_for_forbidden(
        {
            "outcomes": {
                "rows": [
                    {"categoryCode": "dismissed"},
                    {"nested": {"defendantName": "leak"}},
                ]
            }
        },
        terms,
    )
    assert violations == [
        ForbiddenViolation(
            json_path="$.outcomes.rows[1].nested.defendantName",
            kind="key",
            offender="defendantName",
            matched="defendant",
        )
    ]


def test_poisoned_value_fixtures_cover_every_artifact_pattern(terms):
    assert len(POISONED_VALUE_BY_PATTERN) == len(terms.value_patterns)
    for index, poisoned in enumerate(POISONED_VALUE_BY_PATTERN):
        violations = scan_for_forbidden({"note": poisoned}, terms)
        assert violations == [
            ForbiddenViolation(
                json_path="$.note",
                kind="value",
                offender=poisoned,
                matched=terms.value_patterns[index].pattern,
            )
        ]


def test_docket_shaped_value_inside_a_nested_array_element(terms):
    violations = scan_for_forbidden(
        {"results": [{"ok": "fine"}, {"rows": ["clean", "MC-51-CR-0007654-2024"]}]},
        terms,
    )
    assert violations == [
        ForbiddenViolation(
            json_path="$.results[1].rows[1]",
            kind="value",
            offender="MC-51-CR-0007654-2024",
            matched=terms.value_patterns[0].pattern,
        )
    ]


def test_value_pattern_is_case_insensitive_like_the_ts_scanner(terms):
    violations = scan_for_forbidden({"note": "cp-51-cr-0001234-2025"}, terms)
    assert [v.kind for v in violations] == ["value"]


def test_clean_realistic_payload_produces_zero_violations(terms):
    assert scan_for_forbidden(CLEAN_CHARGE_ONLY_RESULT, terms) == []


def test_non_dict_bodies_produce_zero_violations(terms):
    assert scan_for_forbidden(None, terms) == []
    assert scan_for_forbidden(42, terms) == []
    assert scan_for_forbidden("Retail theft", terms) == []


# --------------------------------------------------------------------------- #
# Loader tests (tmp_path artifacts; no build product needed).                #
# --------------------------------------------------------------------------- #


def _write_artifact(path: Path, field_stems, value_patterns) -> Path:
    artifact = path / "forbidden-fields.json"
    artifact.write_text(
        json.dumps({"fieldStems": field_stems, "valuePatterns": value_patterns})
    )
    return artifact


def test_loader_reads_stems_and_compiles_patterns(tmp_path):
    artifact = _write_artifact(
        tmp_path,
        ["docket"],
        [{"source": r"\bCP-\d{2}\b", "flags": "i"}],
    )
    loaded = load_forbidden_terms(artifact)
    assert loaded.field_stems == ("docket",)
    assert loaded.value_patterns[0].search("cp-51")


def test_loader_missing_artifact_is_a_hard_failure(tmp_path):
    with pytest.raises((FileNotFoundError, OSError)):
        load_forbidden_terms(tmp_path / "absent.json")


def test_loader_refuses_an_empty_stem_list(tmp_path):
    artifact = _write_artifact(tmp_path, [], [])
    with pytest.raises(ValueError):
        load_forbidden_terms(artifact)


def test_loader_refuses_an_unportable_regex_flag(tmp_path):
    artifact = _write_artifact(tmp_path, ["docket"], [{"source": "x", "flags": "g"}])
    with pytest.raises(ValueError):
        load_forbidden_terms(artifact)
