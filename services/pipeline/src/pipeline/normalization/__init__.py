"""Normalization result models + controlled vocabularies (Task 22.1).

Pure-Python, greenfield: the shared result models, the closed normalization
warning vocabulary, the ``review_needed`` derivation map, and the
``review.queue_items`` payload builder that every Sprint 5 normalization matcher
(22.2 charge, 22.3 judge, 22.4 outcome/sentencing) and the money extractor
consume. No matchers, no parsing logic, and NO DB access live here.

The public surface is re-exported from this package root so consumers import
from ``pipeline.normalization`` rather than reaching into submodules.
"""

from __future__ import annotations

from pipeline.normalization.models import (
    ChargeNormalizationResult,
    JudgeNormalizationResult,
    MoneyExtractionResult,
    NormalizationCandidate,
    OutcomeNormalizationResult,
    SentencingNormalizationResult,
)
from pipeline.normalization.review_items import DEDUP_KEY_SEPARATOR, build_review_item
from pipeline.normalization.vocab import (
    MATCH_METHOD_ALIAS,
    MATCH_METHOD_AMBIGUOUS,
    MATCH_METHOD_EXACT,
    MATCH_METHOD_PATTERN,
    MATCH_METHOD_STATUTE,
    MATCH_METHOD_UNMATCHED,
    MATCH_METHODS,
    MATCHED_METHODS,
    NORM_AMBIGUOUS,
    NORM_BLOCKING_WARNINGS,
    NORM_EMPTY_INPUT,
    NORM_STATUTE_TEXT_CONFLICT,
    NORM_UNMATCHED,
    NORM_UNPARSEABLE_AMOUNT,
    NORM_WARNING_CODES,
    derive_review_needed,
)

__all__ = [
    # vocab — match methods
    "MATCH_METHODS",
    "MATCHED_METHODS",
    "MATCH_METHOD_EXACT",
    "MATCH_METHOD_ALIAS",
    "MATCH_METHOD_STATUTE",
    "MATCH_METHOD_PATTERN",
    "MATCH_METHOD_UNMATCHED",
    "MATCH_METHOD_AMBIGUOUS",
    # vocab — warnings + review_needed
    "NORM_WARNING_CODES",
    "NORM_BLOCKING_WARNINGS",
    "NORM_UNMATCHED",
    "NORM_AMBIGUOUS",
    "NORM_STATUTE_TEXT_CONFLICT",
    "NORM_UNPARSEABLE_AMOUNT",
    "NORM_EMPTY_INPUT",
    "derive_review_needed",
    # models
    "NormalizationCandidate",
    "ChargeNormalizationResult",
    "JudgeNormalizationResult",
    "OutcomeNormalizationResult",
    "SentencingNormalizationResult",
    "MoneyExtractionResult",
    # review-item builder
    "build_review_item",
    "DEDUP_KEY_SEPARATOR",
]
