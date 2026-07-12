"""Tier-1 synthetic tests for sentence-fact eligibility (Task 23.3).

Pure, DB-free tests for the sentence-fact build layer —
:func:`evaluate_sentence_eligibility`, :func:`derive_component_match_method`, and
:func:`build_sentence_fact_row` — plus a committed golden of built fact rows
(fields + reason codes) over the AC10 scenario set. The 22.5 mapper is consumed
UNCHANGED (constructed from the real generated
taxonomy and called per component); the 18.1 duration predicate is imported and
applied verbatim. Synthetic inputs only (controlled CPCMS ``sentence_type`` vocab,
placeholder ids); no docket numbers, defendant data, or raw docket text.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pipeline.envelope import _is_unparseable_duration
from pipeline.fact_review_vocab import (
    JUDGE_NOT_ATTRIBUTED,
    MONEY_AMOUNT_UNPARSEABLE,
    PARENT_OUTCOME_INELIGIBLE,
    REVIEW_NEEDED,
    SENTENCE_DATE_BEFORE_MVP_WINDOW,
    SENTENCE_DATE_MISSING,
    SENTENCE_DURATION_UNPARSEABLE,
    SENTENCING_COMPONENT_NOT_NORMALIZED,
)
from pipeline.facts.judge_attribution import METHOD_DISPOSITION_JUDGE, METHOD_NONE
from pipeline.facts.sentence_facts import (
    ATTRIBUTION_METHOD_CHARGE_COMPONENT,
    build_sentence_fact_row,
    derive_component_match_method,
    evaluate_sentence_eligibility,
    parent_attributed,
)
from pipeline.normalization.sentencing_mapper import (
    SentencingMapper,
    load_sentencing_taxonomy,
)
from pipeline.normalization.vocab import (
    MATCH_METHOD_AMBIGUOUS,
    MATCH_METHOD_EXACT,
    MATCH_METHOD_UNMATCHED,
)

GOLDEN_PATH = Path(__file__).parent / "tier1" / "sentence_fact_goldens.json"

IN_WINDOW = "2025-06-01"
PRE_WINDOW = "2024-12-31"

# A clean, in-window, attributed parent (the common case) and an ineligible one.
_CLEAN_PARENT = {
    "public_eligible": True,
    "judge_attribution_method": METHOD_DISPOSITION_JUDGE,
    "normalized_charge_id": "charge-1111",
    "normalized_judge_id": "judge-2222",
}
_INELIGIBLE_PARENT = {
    "public_eligible": False,
    "judge_attribution_method": METHOD_NONE,
    "normalized_charge_id": None,
    "normalized_judge_id": None,
}


def _comp(sentence_type, raw_text, *, min_days=None, max_days=None, min_assumed=False):
    return {
        "sentence_type": sentence_type,
        "raw_text": raw_text,
        "min_days": min_days,
        "max_days": max_days,
        "min_assumed": min_assumed,
    }


# The AC10 scenario set. Each scenario is one parent + its ordered components; the
# builder emits one fact row per component (never collapsed).
SCENARIOS: list[dict] = [
    # probation + fine (multi-component, both clean/eligible)
    {
        "name": "probation_fine",
        "parent": _CLEAN_PARENT,
        "sentence_date": IN_WINDOW,
        "components": [
            _comp("Probation", "Probation, Min of 12.00 Months", min_days=365),
            _comp("Fines and Costs", "Fines and Costs, $500.00"),
        ],
    },
    # confinement + probation (multi-component, both clean/eligible)
    {
        "name": "confinement_probation",
        "parent": _CLEAN_PARENT,
        "sentence_date": IN_WINDOW,
        "components": [
            _comp(
                "Confinement",
                "Confinement, Min of 3.00 Months Max of 6.00 Months",
                min_days=90,
                max_days=180,
            ),
            _comp("Probation", "Probation, Min of 12.00 Months", min_days=365),
        ],
    },
    # a monetary component with a single parseable amount
    {
        "name": "monetary_parseable",
        "parent": _CLEAN_PARENT,
        "sentence_date": IN_WINDOW,
        "components": [_comp("Fines and Costs", "Fines and Costs, $1,234.56")],
    },
    # MONEY_UNPARSEABLE (two distinct amounts -> amount unset, category stands)
    {
        "name": "money_unparseable",
        "parent": _CLEAN_PARENT,
        "sentence_date": IN_WINDOW,
        "components": [
            _comp("Fines and Costs", "Fines and Costs, $500.00 and $250.00")
        ],
    },
    # UNPARSEABLE_DURATION (duration-bearing type, no parsed days, raw present)
    {
        "name": "unparseable_duration",
        "parent": _CLEAN_PARENT,
        "sentence_date": IN_WINDOW,
        "components": [_comp("Confinement", "Confinement, Life")],
    },
    # an unmapped sentencing component (sentence_type not in the 22.5 table);
    # parsed days present so the not-normalized signal is isolated
    {
        "name": "unmapped_component",
        "parent": _CLEAN_PARENT,
        "sentence_date": IN_WINDOW,
        "components": [
            _comp("Restorative Program", "Restorative Program details", min_days=90)
        ],
    },
    # an ambiguous sentencing component (bare "N hours", no "Community Service");
    # a probation term is present so the ambiguity signal is isolated
    {
        "name": "ambiguous_component",
        "parent": _CLEAN_PARENT,
        "sentence_date": IN_WINDOW,
        "components": [_comp("Probation", "Probation, 40 hours", min_days=365)],
    },
    # pre-2025 sentence_date -> mvp-ineligible
    {
        "name": "pre_2025",
        "parent": _CLEAN_PARENT,
        "sentence_date": PRE_WINDOW,
        "components": [
            _comp("Probation", "Probation, Min of 12.00 Months", min_days=365)
        ],
    },
    # missing sentence_date -> mvp-ineligible
    {
        "name": "sentence_date_missing",
        "parent": _CLEAN_PARENT,
        "sentence_date": None,
        "components": [
            _comp("Probation", "Probation, Min of 12.00 Months", min_days=365)
        ],
    },
    # parent-ineligible but otherwise clean (proves the transitive public gate)
    {
        "name": "parent_ineligible_clean",
        "parent": _INELIGIBLE_PARENT,
        "sentence_date": IN_WINDOW,
        "components": [
            _comp("Probation", "Probation, Min of 12.00 Months", min_days=365)
        ],
    },
    # additive restitution beyond the base (silent-loss guard: forced to review)
    {
        "name": "restitution_additive",
        "parent": _CLEAN_PARENT,
        "sentence_date": IN_WINDOW,
        "components": [
            _comp("Fines and Costs", "Fines and Costs; Restitution $300.00")
        ],
    },
]


def _mapper() -> SentencingMapper:
    return SentencingMapper(load_sentencing_taxonomy())


def _build_rows(scenario: dict, mapper: SentencingMapper, taxv: str) -> list[dict]:
    """Build the fact rows for one scenario exactly as the build orchestration does."""
    sentence_date = (
        date.fromisoformat(scenario["sentence_date"])
        if scenario["sentence_date"]
        else None
    )
    parent = scenario["parent"]
    rows: list[dict] = []
    for order, comp in enumerate(scenario["components"]):
        result = mapper.map(comp["sentence_type"], comp["raw_text"])
        match_method = derive_component_match_method(result)
        duration_unparseable = _is_unparseable_duration(
            {
                "sentence_type": comp["sentence_type"],
                "min_days": comp["min_days"],
                "max_days": comp["max_days"],
                "raw_text": comp["raw_text"],
            }
        )
        eligibility = evaluate_sentence_eligibility(
            sentence_date=sentence_date,
            result=result,
            component_match_method=match_method,
            duration_unparseable=duration_unparseable,
            parent_public_eligible=parent["public_eligible"],
            parent_attributed=parent_attributed(parent["judge_attribution_method"]),
        )
        rows.append(
            build_sentence_fact_row(
                build_run_id="run-00000000",
                charge_outcome_id=f"outcome-{scenario['name']}",
                parsed_sentence_id=f"sentence-{scenario['name']}-{order}",
                normalized_charge_id=parent["normalized_charge_id"],
                sentence_date=sentence_date,
                result=result,
                component_match_method=match_method,
                min_days=comp["min_days"],
                max_days=comp["max_days"],
                min_assumed=comp["min_assumed"],
                normalized_judge_id=parent["normalized_judge_id"],
                judge_attribution_method=parent["judge_attribution_method"],
                eligibility=eligibility,
                taxonomy_version=taxv,
            )
        )
    return rows


def _jsonable(row: dict) -> dict:
    out = dict(row)
    if isinstance(out.get("sentence_date"), date):
        out["sentence_date"] = out["sentence_date"].isoformat()
    return out


def build_all_goldens() -> dict[str, list[dict]]:
    """Regenerate the full golden mapping (used by the committed-golden writer)."""
    mapper = _mapper()
    taxv = load_sentencing_taxonomy().taxonomy_version
    return {
        sc["name"]: [_jsonable(r) for r in _build_rows(sc, mapper, taxv)]
        for sc in SCENARIOS
    }


# ---------------------------------------------------------------------------
# Golden regression
# ---------------------------------------------------------------------------


def test_sentence_fact_goldens_match_committed() -> None:
    golden = json.loads(GOLDEN_PATH.read_text())
    actual = build_all_goldens()
    assert set(golden) == {sc["name"] for sc in SCENARIOS}
    for name in golden:
        assert actual[name] == golden[name], name


# ---------------------------------------------------------------------------
# Explicit spec oracles (independent of the snapshot)
# ---------------------------------------------------------------------------


def _rows_for(name: str) -> list[dict]:
    mapper = _mapper()
    taxv = load_sentencing_taxonomy().taxonomy_version
    scenario = next(s for s in SCENARIOS if s["name"] == name)
    return _build_rows(scenario, mapper, taxv)


def test_multi_component_never_collapsed() -> None:
    rows = _rows_for("probation_fine")
    assert len(rows) == 2
    probation, fine = rows
    assert probation["sentencing_category_code"] == "probation"
    assert fine["sentencing_category_code"] == "costs_fees"
    assert fine["amount_cents"] == 50000
    # both clean/in-window/attributed -> fully eligible, empty reasons
    for row in rows:
        assert row["public_eligible"] is True
        assert row["judge_specific_eligible"] is True
        assert row["ineligibility_reason_codes"] == []
        assert row["attribution_method"] == ATTRIBUTION_METHOD_CHARGE_COMPONENT
        assert row["component_match_method"] == MATCH_METHOD_EXACT


def test_confinement_probation_two_facts() -> None:
    rows = _rows_for("confinement_probation")
    assert [r["sentencing_category_code"] for r in rows] == [
        "incarceration",
        "probation",
    ]
    assert rows[0]["min_days"] == 90 and rows[0]["max_days"] == 180
    assert all(r["judge_specific_eligible"] for r in rows)


def test_monetary_parseable_amount() -> None:
    (row,) = _rows_for("monetary_parseable")
    assert row["amount_cents"] == 123456
    assert row["review_needed"] is False
    assert row["public_eligible"] is True


def test_money_unparseable_routes_to_review() -> None:
    (row,) = _rows_for("money_unparseable")
    assert row["amount_cents"] is None
    assert row["review_needed"] is True
    assert row["public_eligible"] is False
    assert REVIEW_NEEDED in row["ineligibility_reason_codes"]
    assert MONEY_AMOUNT_UNPARSEABLE in row["ineligibility_reason_codes"]


def test_unparseable_duration_routes_to_review() -> None:
    (row,) = _rows_for("unparseable_duration")
    assert row["sentencing_category_code"] == "incarceration"
    assert row["min_days"] is None and row["max_days"] is None
    assert row["review_needed"] is True
    assert SENTENCE_DURATION_UNPARSEABLE in row["ineligibility_reason_codes"]
    assert REVIEW_NEEDED in row["ineligibility_reason_codes"]


def test_unmapped_component() -> None:
    (row,) = _rows_for("unmapped_component")
    assert row["component_match_method"] == MATCH_METHOD_UNMATCHED
    assert row["sentencing_category_code"] == "unknown"
    assert SENTENCING_COMPONENT_NOT_NORMALIZED in row["ineligibility_reason_codes"]
    assert row["public_eligible"] is False


def test_ambiguous_component() -> None:
    (row,) = _rows_for("ambiguous_component")
    assert row["component_match_method"] == MATCH_METHOD_AMBIGUOUS
    assert SENTENCING_COMPONENT_NOT_NORMALIZED in row["ineligibility_reason_codes"]
    assert row["review_needed"] is True


def test_pre_2025_mvp_ineligible() -> None:
    (row,) = _rows_for("pre_2025")
    assert row["mvp_eligible"] is False
    assert row["public_eligible"] is False
    assert SENTENCE_DATE_BEFORE_MVP_WINDOW in row["ineligibility_reason_codes"]


def test_sentence_date_missing() -> None:
    (row,) = _rows_for("sentence_date_missing")
    assert row["sentence_date"] is None
    assert row["mvp_eligible"] is False
    assert SENTENCE_DATE_MISSING in row["ineligibility_reason_codes"]


def test_parent_ineligible_transitive_gate() -> None:
    (row,) = _rows_for("parent_ineligible_clean")
    # otherwise clean and in-window, but the parent is not public-eligible
    assert row["mvp_eligible"] is True
    assert row["public_eligible"] is False
    assert row["ineligibility_reason_codes"] == [PARENT_OUTCOME_INELIGIBLE]


def test_restitution_additive_forces_review() -> None:
    (row,) = _rows_for("restitution_additive")
    # base category stored + amount populated, but the additive forces review so
    # it surfaces to 23.4 rather than being dropped to a base-only eligible fact
    assert row["sentencing_category_code"] == "costs_fees"
    assert row["amount_cents"] == 30000
    assert row["review_needed"] is True
    assert row["public_eligible"] is False
    assert REVIEW_NEEDED in row["ineligibility_reason_codes"]


# ---------------------------------------------------------------------------
# Unit-level oracles
# ---------------------------------------------------------------------------


def test_derive_component_match_method() -> None:
    mapper = _mapper()
    assert (
        derive_component_match_method(mapper.map("Probation", "Probation"))
        == MATCH_METHOD_EXACT
    )
    assert (
        derive_component_match_method(mapper.map("Nope", "Nope"))
        == MATCH_METHOD_UNMATCHED
    )
    assert (
        derive_component_match_method(mapper.map("Probation", "Probation, 8 hours"))
        == MATCH_METHOD_AMBIGUOUS
    )


def test_reasons_empty_iff_judge_specific() -> None:
    mapper = _mapper()
    taxv = load_sentencing_taxonomy().taxonomy_version
    for sc in SCENARIOS:
        for row in _build_rows(sc, mapper, taxv):
            assert (row["ineligibility_reason_codes"] == []) == row[
                "judge_specific_eligible"
            ]


def test_parent_attributed_helper() -> None:
    assert parent_attributed(METHOD_DISPOSITION_JUDGE) is True
    assert parent_attributed(METHOD_NONE) is False
    assert parent_attributed(None) is False


def test_public_eligible_only_when_attributed_promotes_to_judge_specific() -> None:
    # a clean, in-window, public component whose parent is public but UNATTRIBUTED
    # is public-eligible but NOT judge-specific, and carries judge_not_attributed
    mapper = _mapper()
    result = mapper.map("Probation", "Probation, Min of 12.00 Months")
    eligibility = evaluate_sentence_eligibility(
        sentence_date=date(2025, 6, 1),
        result=result,
        component_match_method=derive_component_match_method(result),
        duration_unparseable=False,
        parent_public_eligible=True,
        parent_attributed=False,
    )
    assert eligibility.public_eligible is True
    assert eligibility.judge_specific_eligible is False
    assert eligibility.ineligibility_reason_codes == (JUDGE_NOT_ATTRIBUTED,)
