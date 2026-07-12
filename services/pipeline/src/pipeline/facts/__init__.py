"""Fact-building logic for Phase 23 (pure; no DB, no fact tables here).

Phase 23 turns normalized parsed records into fact rows. Task 23.1 opens the
phase with the conservative judge-attribution resolver — pure logic that the
23.2 outcome-fact builder consumes and 23.3 inherits unchanged for sentence
facts. NO ``fact.*`` persistence, NO ``fact_build_runs``, and NO eligibility
booleans live here; those are 23.2/23.3/23.4.

The public surface is re-exported from this package root so consumers import
from ``pipeline.facts`` rather than reaching into submodules.
"""

from __future__ import annotations

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
]
