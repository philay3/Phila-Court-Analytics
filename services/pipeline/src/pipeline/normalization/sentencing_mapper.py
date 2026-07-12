"""Pure sentence-component -> sentencing-category mapper (Task 22.5).

Maps a parsed sentence component to public sentencing taxonomy codes and extracts a
monetary amount for monetary components. Mirrors the 22.4 outcome mapper: a
deterministic EXACT-match table over the captured ``sentence_type`` (the 18.2
repair-table principle — verbatim ``dict.get``, never fuzzy/folded/partial), a
purpose-built result type carrying ``taxonomy_version`` (the frozen 22.1
``SentencingNormalizationResult`` is roster-match-shaped and cannot), and a thin
loader at the file boundary keeping the mapper tier-1 synthetic-testable.

Three layers per component (LOCKED at the 22.5 map gate):

- **Base mapping** — :data:`SENTENCE_TYPE_CATEGORY_MAP` exact-matches
  ``sentence_type`` -> one sentencing code; an absent value -> ``unknown`` +
  ``unmapped_sentencing_component`` review. ``unknown`` is never public-eligible
  (enforced at construction against the taxonomy).
- **Additive detection** (the SUSPECTED_AMENDED_CHARGE philosophy, add/flag never
  collapse) — a whole-token ``Restitution`` or literal ``Community Service`` in
  ``raw_text`` ADDS a category mapping on the SAME component (components are NEVER
  collapsed). A bare ``N hours`` with no "Community Service" is AMBIGUOUS ->
  ``ambiguous_sentencing_component`` review, never a silent add. Conservative
  false-negative bias: an unmatched signal is left out (flagged), not guessed in.
- **Money** — for a component carrying any monetary category (``costs_fees`` base
  or ``restitution`` additive), the money extractor reads a single amount from
  ``raw_text`` per the locked four-branch triage; a zero/multiple/unreadable
  amount leaves ``amount_cents`` unset (with a
  ``money_unparseable`` item where a ``$`` was present) but the category stands.

Durations (``min_days``/``max_days``/``min_assumed``) are consumed AS PARSED — this
module never reads or re-parses them. A parser ``UNPARSEABLE_DURATION`` warning maps
to a review item via :func:`build_duration_review_item`, which the CALLER invokes
(Phase 23 wires the envelope warning to it); the mapper never scans the envelope.

Pure and DB-free (mirrors 22.2/22.3/22.4). Codes come from ``@pca/taxonomy``
taxonomy.json ONLY and ``taxonomy_version`` is stamped on every result. NO DB, NO
``fact.*`` writes (Phase 23). Raw values are permitted inside results / review-item
payloads (internal-only) but NEVER in console / log output.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pipeline.fact_review_vocab import (
    AMBIGUOUS_SENTENCING_COMPONENT,
    DURATION_UNPARSEABLE,
    MONEY_AMOUNT_UNPARSEABLE,
    MONEY_UNPARSEABLE,
    SENTENCE_DURATION_UNPARSEABLE,
    SENTENCING_COMPONENT_NOT_NORMALIZED,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    UNMAPPED_SENTENCING_COMPONENT,
)
from pipeline.normalization.models import MoneyExtractionResult
from pipeline.normalization.money_extractor import extract_amount
from pipeline.normalization.review_items import build_review_item
from pipeline.normalization.vocab import NORM_UNPARSEABLE_AMOUNT

# The taxonomy `unknown` sentencing code (non-public) — the sink for a
# ``sentence_type`` that maps to nothing. Not a member of the exact-match table.
SENTENCING_UNKNOWN = "unknown"

# Monetary sentencing categories — a component carrying any of these gets money
# extraction (`fine` is defined but, per the 22.5 recon, never populated: the
# corpus has no discrete fine; `Fines and Costs` -> `costs_fees`).
MONETARY_CATEGORIES: frozenset[str] = frozenset({"fine", "costs_fees", "restitution"})

# Additive category codes.
CATEGORY_RESTITUTION = "restitution"
CATEGORY_COMMUNITY_SERVICE = "community_service"

# Entity tag carried on review items (parallel to 22.4 "disposition").
ENTITY_SENTENCING = "sentencing"

# Where a category mapping came from.
SOURCE_SENTENCE_TYPE = "sentence_type"
SOURCE_RESTITUTION = "restitution_detection"
SOURCE_COMMUNITY_SERVICE = "community_service_detection"
SENTENCING_SOURCES: frozenset[str] = frozenset(
    {SOURCE_SENTENCE_TYPE, SOURCE_RESTITUTION, SOURCE_COMMUNITY_SERVICE}
)

# --- The APPROVED exact-match base table (Task 22.5 map-approval gate) ---------
# sentence_type string -> sentencing taxonomy code. Keys are BYTE-EXACT to the
# parser's controlled sentence-type vocabulary (Confinement / Probation / ARD /
# IPP / No Further Penalty / Fines and Costs); every value is a real taxonomy code
# (verified at construction). These are CPCMS sentencing vocabulary — non-
# identifying, same class as the committed charge-description vocabulary; no raw
# docket text, docket numbers, or defendant data.
#
# `Fines and Costs` -> `costs_fees`: recon-confirmed (13/13 corpus components carry
# no discrete fine amount), so a discrete `fine` category is not populated.
# `IPP` -> `other`: absent from the corpus (0 rows) — an unreachable-but-kept entry
# for safety, matching the 22.4 precedent of retaining dead-but-safe map rows.
SENTENCE_TYPE_CATEGORY_MAP: dict[str, str] = {
    "Confinement": "incarceration",
    "Probation": "probation",
    "No Further Penalty": "no_further_penalty",
    "ARD": "other",
    "Fines and Costs": "costs_fees",
    "IPP": "other",
}

# --- Additive-detection patterns (LOCKED, 22.5 map gate) ----------------------
# Whole-token / literal, case-insensitive. Conservative: `Community Service` must
# be literal to ADD the category; a bare `N hours` alone is ambiguous (-> review).
_RESTITUTION = re.compile(r"\bRestitution\b", re.IGNORECASE)
_COMMUNITY_SERVICE = re.compile(r"\bCommunity Service\b", re.IGNORECASE)
_HOURS = re.compile(r"\b\d+\s*hours?\b", re.IGNORECASE)

# taxonomy.json (generated, gitignored; `pnpm generate` builds it; CI regenerates
# before pytest) at this repo-relative path.
_TAXONOMY_RELPATH = ("packages", "taxonomy", "generated", "taxonomy.json")


@dataclass(frozen=True)
class SentencingTaxonomy:
    """An immutable view of the sentencing taxonomy the mapper needs.

    ``taxonomy_version`` is stamped on every result; ``public_by_code`` maps each
    sentencing code to its ``public`` flag (drives ``public_eligible`` and the
    construction-time membership check). Structural only — no raw data.
    """

    taxonomy_version: str
    public_by_code: Mapping[str, bool]

    def __post_init__(self) -> None:
        if not self.taxonomy_version:
            raise ValueError("taxonomy_version must be non-empty")
        if not self.public_by_code:
            raise ValueError("public_by_code must be non-empty")


def load_sentencing_taxonomy(path: Path | None = None) -> SentencingTaxonomy:
    """Load the SENTENCING taxonomy from taxonomy.json (the file boundary).

    With ``path`` omitted, walks up from this module to find
    ``packages/taxonomy/generated/taxonomy.json``. Reads ``taxonomyVersion`` and the
    ``sentencingCategories`` ``code`` -> ``public`` map (contrast the 22.4 loader,
    which reads ``outcomeCategories``). Raises ``FileNotFoundError`` with a
    `pnpm generate` hint if the artifact is missing.
    """
    if path is None:
        here = Path(__file__).resolve()
        for candidate in here.parents:
            probe = candidate.joinpath(*_TAXONOMY_RELPATH)
            if probe.is_file():
                path = probe
                break
        if path is None:
            raise FileNotFoundError(
                "taxonomy.json not found; run `pnpm generate` to build "
                "packages/taxonomy/generated/taxonomy.json"
            )
    data = json.loads(path.read_text())
    public_by_code = {
        category["code"]: bool(category["public"])
        for category in data["sentencingCategories"]
    }
    return SentencingTaxonomy(
        taxonomy_version=str(data["taxonomyVersion"]),
        public_by_code=public_by_code,
    )


@dataclass(frozen=True)
class SentencingCategoryMapping:
    """One category mapping on a component — a base mapping OR an additive one.

    A component may carry several (base first, then additive), which is how
    "components are never collapsed" is represented: restitution / community-service
    detection APPENDS a mapping rather than replacing or merging the base.

    - ``category_code`` — a real taxonomy code (``unknown`` only for an unmapped
      base).
    - ``source`` — one of :data:`SENTENCING_SOURCES`.
    - ``public_eligible`` — the taxonomy ``public`` flag (always False for
      ``unknown``).
    - ``mapped`` — True from the table / an additive detection; False only for the
      unmapped base -> ``unknown`` sink.
    """

    category_code: str
    source: str
    public_eligible: bool
    mapped: bool

    def __post_init__(self) -> None:
        if not self.category_code:
            raise ValueError("category_code must be non-empty")
        if self.source not in SENTENCING_SOURCES:
            raise ValueError(f"unknown mapping source: {self.source!r}")
        if not self.mapped and self.category_code != SENTENCING_UNKNOWN:
            raise ValueError("an unmapped mapping must carry the `unknown` code")
        if self.category_code == SENTENCING_UNKNOWN and self.public_eligible:
            raise ValueError("`unknown` is never public-eligible")


@dataclass(frozen=True)
class SentencingComponentResult:
    """The result of mapping ONE parsed sentence component.

    - ``raw_sentence_type`` — the ``sentence_type`` that was mapped.
    - ``taxonomy_version`` — stamped from taxonomy.json on EVERY result.
    - ``categories`` — >= 1 mappings, base (``sentence_type`` source) FIRST, then
      any additive restitution / community-service mappings.
    - ``money`` — the money-extraction result for a monetary component, else
      ``None`` (money is not read for a non-monetary component).
    - ``ambiguous_community_service`` — a bare ``N hours`` with no "Community
      Service" literal was seen (-> review, no category added).

    The convenience properties derive the review state; the authoritative review
    payloads come from :func:`build_sentencing_review_items`.
    """

    raw_sentence_type: str
    taxonomy_version: str
    categories: tuple[SentencingCategoryMapping, ...]
    money: MoneyExtractionResult | None
    ambiguous_community_service: bool

    def __post_init__(self) -> None:
        if not self.taxonomy_version:
            raise ValueError("taxonomy_version must be non-empty")
        if not self.categories:
            raise ValueError("a component result carries >= 1 category mapping")
        if self.categories[0].source != SOURCE_SENTENCE_TYPE:
            raise ValueError("the first category mapping must be the base mapping")

    @property
    def base(self) -> SentencingCategoryMapping:
        """The base (``sentence_type``) mapping — always ``categories[0]``."""
        return self.categories[0]

    @property
    def amount_cents(self) -> int | None:
        """The extracted amount (set only for the exactly-one-amount branch)."""
        return self.money.amount_cents if self.money is not None else None

    @property
    def money_unparseable(self) -> bool:
        """True iff a monetary component's amount was present-but-unresolvable."""
        return self.money is not None and NORM_UNPARSEABLE_AMOUNT in self.money.warnings

    @property
    def review_needed(self) -> bool:
        """True iff this component warrants any review item."""
        return (
            not self.base.mapped
            or self.ambiguous_community_service
            or self.money_unparseable
        )


class SentencingMapper:
    """Map a sentence component -> sentencing categories against the exact table.

    Pure and DB-free. The table and taxonomy are fixed at construction; :meth:`map`
    is a read-only exact-match + additive-detection decision over them.
    """

    def __init__(
        self,
        taxonomy: SentencingTaxonomy,
        mapping: Mapping[str, str] = SENTENCE_TYPE_CATEGORY_MAP,
    ) -> None:
        # Construction-time check: every base code, both additive codes, the
        # monetary codes, and the `unknown` sink are real taxonomy codes, and
        # `unknown` is non-public so it can never be public-eligible.
        used_codes = (
            set(mapping.values())
            | {SENTENCING_UNKNOWN, CATEGORY_RESTITUTION, CATEGORY_COMMUNITY_SERVICE}
            | set(MONETARY_CATEGORIES)
        )
        for code in sorted(used_codes):
            if code not in taxonomy.public_by_code:
                raise ValueError(f"sentencing code not in taxonomy: {code!r}")
        if taxonomy.public_by_code.get(SENTENCING_UNKNOWN) is not False:
            raise ValueError(
                "taxonomy must define `unknown` as non-public (never public-eligible)"
            )
        self._version = taxonomy.taxonomy_version
        self._public = dict(taxonomy.public_by_code)
        self._map = dict(mapping)

    def _mapping(
        self, code: str, source: str, *, mapped: bool
    ) -> SentencingCategoryMapping:
        return SentencingCategoryMapping(
            category_code=code,
            source=source,
            public_eligible=self._public[code] if mapped else False,
            mapped=mapped,
        )

    def map(self, sentence_type: str, raw_text: str) -> SentencingComponentResult:
        """Map one sentence component (``sentence_type`` + ``raw_text``).

        Layers: (1) base exact-match (verbatim ``dict.get``, never folded);
        (2) additive restitution / community-service detection on ``raw_text``
        (append, never collapse; a bare ``N hours`` -> ambiguous, no add);
        (3) money extraction iff any monetary category is present.
        """
        text = raw_text or ""
        categories: list[SentencingCategoryMapping] = []

        # (1) base — exact-match on the verbatim sentence_type.
        base_code = self._map.get(sentence_type)
        if base_code is None:
            categories.append(
                self._mapping(SENTENCING_UNKNOWN, SOURCE_SENTENCE_TYPE, mapped=False)
            )
        else:
            categories.append(
                self._mapping(base_code, SOURCE_SENTENCE_TYPE, mapped=True)
            )

        # (2) additive detection on raw_text (or sentence_type) — never collapse.
        if _RESTITUTION.search(text) or _RESTITUTION.search(sentence_type):
            categories.append(
                self._mapping(CATEGORY_RESTITUTION, SOURCE_RESTITUTION, mapped=True)
            )
        ambiguous_cs = False
        if _COMMUNITY_SERVICE.search(text):
            categories.append(
                self._mapping(
                    CATEGORY_COMMUNITY_SERVICE, SOURCE_COMMUNITY_SERVICE, mapped=True
                )
            )
        elif _HOURS.search(text):
            # bare "N hours" with no "Community Service" literal -> ambiguous:
            # flag for review, do NOT silently add the category.
            ambiguous_cs = True

        # (3) money — only for a component carrying a monetary category.
        money = None
        if any(c.category_code in MONETARY_CATEGORIES for c in categories):
            money = extract_amount(text)

        return SentencingComponentResult(
            raw_sentence_type=sentence_type,
            taxonomy_version=self._version,
            categories=tuple(categories),
            money=money,
            ambiguous_community_service=ambiguous_cs,
        )


def build_sentencing_review_items(
    result: SentencingComponentResult,
    *,
    source_document_id: str,
    charge_sequence: int | str,
    component_order: int | str,
    parsed_docket_id: str | None = None,
    parsed_charge_id: str | None = None,
    parsed_sentence_id: str | None = None,
) -> list[dict[str, object]]:
    """Build the ``review.queue_items`` payloads for one component (0 or more).

    Emits, per the LOCKED table, at most one of each:

    - unmapped base    -> ``unmapped_sentencing_component`` /
      ``sentencing_component_not_normalized`` / medium
    - ambiguous CS     -> ``ambiguous_sentencing_component`` /
      ``sentencing_component_not_normalized`` / medium
    - money unparseable -> ``money_unparseable`` / ``money_amount_unparseable`` / low

    The sentence-grain locator is ``(str(charge_sequence), str(component_order))``;
    ``parsed_*`` pointers are re-anchoring payload and by construction NEVER enter
    the dedup key. Distinct ``item_type`` per condition keeps the three keys
    collision-free within one component.
    """
    locator = (str(charge_sequence), str(component_order))
    common = {
        "source_document_id": source_document_id,
        "locator": locator,
        "parsed_docket_id": parsed_docket_id,
        "parsed_charge_id": parsed_charge_id,
        "parsed_sentence_id": parsed_sentence_id,
        "entity_type": ENTITY_SENTENCING,
        "raw_value": result.raw_sentence_type,
    }
    items: list[dict[str, object]] = []

    if not result.base.mapped:
        items.append(
            build_review_item(
                item_type=UNMAPPED_SENTENCING_COMPONENT,
                severity=SEVERITY_MEDIUM,
                reason_code=SENTENCING_COMPONENT_NOT_NORMALIZED,
                **common,
            )
        )
    if result.ambiguous_community_service:
        items.append(
            build_review_item(
                item_type=AMBIGUOUS_SENTENCING_COMPONENT,
                severity=SEVERITY_MEDIUM,
                reason_code=SENTENCING_COMPONENT_NOT_NORMALIZED,
                **common,
            )
        )
    if result.money_unparseable:
        items.append(
            build_review_item(
                item_type=MONEY_UNPARSEABLE,
                severity=SEVERITY_LOW,
                reason_code=MONEY_AMOUNT_UNPARSEABLE,
                **common,
            )
        )
    return items


def build_duration_review_item(
    *,
    source_document_id: str,
    charge_sequence: int | str,
    component_order: int | str,
    parsed_docket_id: str | None = None,
    parsed_charge_id: str | None = None,
    parsed_sentence_id: str | None = None,
    raw_value: str | None = None,
) -> dict[str, object]:
    """Build a ``duration_unparseable`` review item (helper only; Phase-23-wired).

    The CALLER decides when to invoke this — i.e., when the parser emitted an
    ``UNPARSEABLE_DURATION`` warning for the component. The mapper never scans the
    envelope and never re-parses a duration, so "durations consumed as parsed"
    holds; Phase 23 (fact build) wires the envelope warning to this helper over the
    corpus. Mapping: ``duration_unparseable`` / ``sentence_duration_unparseable`` /
    low, same sentence-grain locator and payload-only ``parsed_*`` pointers.
    """
    return build_review_item(
        source_document_id=source_document_id,
        item_type=DURATION_UNPARSEABLE,
        severity=SEVERITY_LOW,
        reason_code=SENTENCE_DURATION_UNPARSEABLE,
        locator=(str(charge_sequence), str(component_order)),
        parsed_docket_id=parsed_docket_id,
        parsed_charge_id=parsed_charge_id,
        parsed_sentence_id=parsed_sentence_id,
        entity_type=ENTITY_SENTENCING,
        raw_value=raw_value,
    )
