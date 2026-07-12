"""Fact-building logic for Phase 23 (pure; no DB, no fact tables here).

Phase 23 turns normalized parsed records into fact rows. Task 23.1 opens the
phase with the conservative judge-attribution resolver (``judge_attribution``) —
pure logic that the 23.2 outcome-fact builder consumes and 23.3 inherits
unchanged for sentence facts. Task 23.2 adds the outcome-fact layer: the pure
eligibility + row logic (``outcome_facts``) and the ``pipeline build-facts``
orchestration that writes ``fact.charge_outcomes`` under one ``fact_build_runs``
run (``build_facts``).

The public surface is re-exported from this package root so consumers import
from ``pipeline.facts`` rather than reaching into submodules.
"""

from __future__ import annotations

from pipeline.facts.build_facts import run_build_facts
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
from pipeline.facts.outcome_facts import (
    OutcomeFactEligibility,
    build_outcome_fact_row,
    evaluate_outcome_eligibility,
    insert_outcome_facts,
)

__all__ = [
    "METHOD_DISPOSITION_JUDGE",
    "METHOD_ASSIGNED_JUDGE_RULE",
    "METHOD_NONE",
    "ATTRIBUTION_METHODS",
    "DISPOSITION_JUDGE_NULLED_WARNING_CODES",
    "AttributionResult",
    "DocketAttributionContext",
    "build_docket_context",
    "resolve_charge",
    "OutcomeFactEligibility",
    "evaluate_outcome_eligibility",
    "build_outcome_fact_row",
    "insert_outcome_facts",
    "run_build_facts",
]
