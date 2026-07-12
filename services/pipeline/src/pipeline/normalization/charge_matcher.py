"""Pure charge matcher + canonicalization (Task 22.2).

This module is PURE: it operates over an in-memory roster snapshot (roster
entries + aliases) with NO database access and NO psycopg import in its path
(pinned decision 1). A thin, separate loader (``charge_roster_loader.py``)
fetches the snapshot from ``ref.normalized_charges`` + ``ref.charge_aliases`` at
the orchestration/CLI boundary and hands it here. That split keeps the matcher
tier-1 synthetic-testable.

Two — and only two — canonicalization functions are defined here (pinned
decision 2). Every comparison of roster values and input values routes through
exactly one of them; there are no per-call-site variations:

- :func:`canonicalize_text` — case/punctuation/whitespace-insensitive folding
  of offense text, roster display names, and aliases.
- :func:`canonicalize_statute` — folding of statute codes across the observed
  CPCMS formatting variants of title/section/subsection.

Match precedence is exact -> alias -> statute with conflict detection (pinned
decision 3); the seven behavioral arms are documented on :meth:`ChargeMatcher.match`.
``pattern`` is never emitted by this matcher (it exists in the 22.1 vocabulary
for future matchers); a test asserts this.

Review items for unmatched/ambiguous results are built via the 22.1
:func:`build_review_item` helper only (:func:`build_charge_review_item`), with
21.2 vocabulary codes and the canonical dedup key. Raw charge text is permitted
inside results and review-item payloads (internal-only tables) but never in
console/log output.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pipeline.fact_review_vocab import (
    AMBIGUOUS_CHARGE,
    BLOCKING_WARNING,
    CHARGE_NOT_NORMALIZED,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    UNMAPPED_CHARGE,
)
from pipeline.normalization.models import (
    ChargeNormalizationResult,
    NormalizationCandidate,
)
from pipeline.normalization.review_items import build_review_item
from pipeline.normalization.vocab import (
    MATCH_METHOD_ALIAS,
    MATCH_METHOD_AMBIGUOUS,
    MATCH_METHOD_EXACT,
    MATCH_METHOD_STATUTE,
    MATCH_METHOD_UNMATCHED,
    NORM_AMBIGUOUS,
    NORM_EMPTY_INPUT,
    NORM_STATUTE_TEXT_CONFLICT,
    NORM_UNMATCHED,
)

# Non-alphanumeric run -> single space, for text folding.
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Characters kept by statute canonicalization after upper-casing: letters,
# digits, dot, hyphen. Everything else (spaces, the section glyphs `§`/`§§`,
# parentheses around subsection parts, and CPCMS decorations) is dropped.
_STATUTE_KEEP = re.compile(r"[^A-Z0-9.-]+")


def canonicalize_text(value: str | None) -> str:
    """Fold offense/display/alias text for comparison (pinned decision 2).

    Lower-cases, collapses every run of non-alphanumeric characters to a single
    space, and strips. This is the ONLY text normalization applied anywhere in
    the charge match path — ``"DUI: General Impairment"`` and
    ``"assault (simple)"`` fold to ``"dui general impairment"`` and
    ``"assault simple"``.
    """
    if value is None:
        return ""
    return _NON_ALNUM.sub(" ", value.lower()).strip()


def canonicalize_statute(value: str | None) -> str:
    """Fold a statute code across observed CPCMS formatting variants.

    Upper-cases, then keeps only ``[A-Z0-9.-]`` — dropping whitespace, the
    section glyphs (``§``/``§§``), the parentheses that wrap subsection parts in
    statute-reference phrasing (``(a)(1)`` -> ``A1``), and CPCMS display
    decorations. Dots and hyphens are preserved because they distinguish
    sections (``6110.1`` vs ``6110.2``; ``780-113``). Verified equalities:

    - ``"18 § 6106 §§ A1"``   == ``"18 § 6106(a)(1)"``   -> ``"186106A1"``
    - ``"35 § 780-113 §§ A30"`` == ``"35 § 780-113(a)(30)"`` -> ``"35780-113A30"``
    - ``"18 § 6301 §§ A1i"``  == ``"18 § 6301(a)(1)(i)"`` -> ``"186301A1I"``

    DELIBERATE LOSSY DROP (Required Fix 3): trailing asterisk decorations on
    Title 75 § 3802 DUI subsections (``§§ A1*``, ``§§ D2***``) are dropped. In
    CPCMS DUI dockets these asterisks mark the DUI GRADING/SENTENCING TIER
    (prior-offense count / BAC level), NOT a distinct statutory offense:
    § 3802(a)(1) is one offense regardless of tier, so collapsing ``A1*`` and
    ``A1`` to the same normalized charge is the correct offense-identity
    granularity (sentencing tier is a downstream concern). The drop never merges
    two different subsections — only ``*`` is removed, so ``D1`` and ``D2`` stay
    distinct. This is the only place the whole layer removes such decoration; if
    evidence emerges that ``*`` distinguishes offenses, that is a STOP report.
    """
    if value is None:
        return ""
    return _STATUTE_KEEP.sub("", value.upper())


@dataclass(frozen=True)
class RosterEntry:
    """One normalized-charge roster row, in the in-memory snapshot.

    ``normalized_id`` is the stable identity a matched result / candidate carries
    (the ``ref.normalized_charges`` id at the DB boundary; any stable string in
    synthetic tests). ``aliases`` are the roster's alias FORMS. NO raw docket
    data lives here — display names and aliases are public statute phrasing.
    """

    normalized_id: str
    slug: str
    display_name: str
    statute_code: str | None
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.normalized_id:
            raise ValueError("roster entry normalized_id must be non-empty")
        if not self.display_name:
            raise ValueError("roster entry display_name must be non-empty")


@dataclass(frozen=True)
class RosterSnapshot:
    """An immutable set of roster entries the matcher indexes over."""

    entries: tuple[RosterEntry, ...] = ()


def _candidate(entry: RosterEntry) -> NormalizationCandidate:
    return NormalizationCandidate(
        normalized_id=entry.normalized_id, display_name=entry.display_name
    )


def _candidates(entries: Sequence[RosterEntry]) -> tuple[NormalizationCandidate, ...]:
    """Structural candidate list, de-duplicated by id and ordered stably."""
    seen: dict[str, RosterEntry] = {}
    for entry in entries:
        seen.setdefault(entry.normalized_id, entry)
    ordered = sorted(seen.values(), key=lambda e: e.normalized_id)
    return tuple(_candidate(e) for e in ordered)


class ChargeMatcher:
    """Normalize a charge (statute + offense) against a roster snapshot.

    Pure and DB-free. Canonical lookup maps are built once at construction;
    :meth:`match` is a read-only decision tree over them.
    """

    def __init__(self, snapshot: RosterSnapshot) -> None:
        self._by_display: dict[str, list[RosterEntry]] = {}
        self._by_alias: dict[str, list[RosterEntry]] = {}
        self._by_statute: dict[str, list[RosterEntry]] = {}
        for entry in snapshot.entries:
            self._by_display.setdefault(
                canonicalize_text(entry.display_name), []
            ).append(entry)
            for alias in entry.aliases:
                self._by_alias.setdefault(canonicalize_text(alias), []).append(entry)
            if entry.statute_code is not None:
                code = canonicalize_statute(entry.statute_code)
                if code:
                    self._by_statute.setdefault(code, []).append(entry)

    def match(
        self, *, statute: str | None, offense: str | None
    ) -> ChargeNormalizationResult:
        """Normalize one charge; return a 22.1 ``ChargeNormalizationResult``.

        The seven behavioral arms (pinned decision 3):

        1. empty input   — both offense and statute blank -> ``unmatched`` +
           ``NORM_EMPTY_INPUT``.
        2. exact         — folded offense == a display name (single entry).
        3. alias         — folded offense == an alias (single entry), no exact.
        4. statute       — folded statute == a statute code (single entry), no
           text match.
        5. conflict      — a clean text match and a statute match resolve to
           DIFFERENT entries -> ``ambiguous`` + ``NORM_STATUTE_TEXT_CONFLICT``.
        6. same-tier ambiguity — >= 2 entries match on the resolved tier ->
           ``ambiguous`` + ``NORM_AMBIGUOUS``.
        7. unmatched     — nothing matches -> ``unmatched`` + ``NORM_UNMATCHED``.

        ``pattern`` is never returned. Precedence is text (exact then alias)
        over statute; a statute match alone is a clean ``statute`` match, and a
        statute that AGREES with the text match (same entry, or the text entry
        is among the statute matches) never fabricates a conflict.
        """
        text_canon = canonicalize_text(offense)
        statute_canon = canonicalize_statute(statute)
        raw_value = (offense or "").strip() or (statute or "").strip()

        if not text_canon and not statute_canon:
            return self._unmatched(raw_value, NORM_EMPTY_INPUT)

        # Resolve the text tier: exact first, else alias.
        text_method: str | None = None
        text_entries: list[RosterEntry] = []
        if text_canon:
            if text_canon in self._by_display:
                text_method = MATCH_METHOD_EXACT
                text_entries = self._by_display[text_canon]
            elif text_canon in self._by_alias:
                text_method = MATCH_METHOD_ALIAS
                text_entries = self._by_alias[text_canon]

        statute_entries = (
            self._by_statute.get(statute_canon, []) if statute_canon else []
        )

        # A text hit that is itself ambiguous (>= 2 distinct entries) cannot be
        # cleanly resolved regardless of statute.
        if text_method is not None:
            text_ids = {e.normalized_id for e in text_entries}
            if len(text_ids) >= 2:
                return self._ambiguous(raw_value, NORM_AMBIGUOUS, text_entries)

            (text_entry,) = ({e.normalized_id: e for e in text_entries}).values()
            statute_ids = {e.normalized_id for e in statute_entries}
            # Statute agrees when it is empty or includes the text entry.
            if not statute_ids or text_entry.normalized_id in statute_ids:
                return self._matched(text_method, raw_value, text_entry)
            # Statute points elsewhere entirely -> genuine conflict.
            return self._ambiguous(
                raw_value,
                NORM_STATUTE_TEXT_CONFLICT,
                [text_entry, *statute_entries],
            )

        # No text match: statute tier decides.
        statute_ids = {e.normalized_id for e in statute_entries}
        if not statute_ids:
            return self._unmatched(raw_value, NORM_UNMATCHED)
        if len(statute_ids) >= 2:
            return self._ambiguous(raw_value, NORM_AMBIGUOUS, statute_entries)
        (statute_entry,) = ({e.normalized_id: e for e in statute_entries}).values()
        return self._matched(MATCH_METHOD_STATUTE, raw_value, statute_entry)

    @staticmethod
    def _matched(
        method: str, raw_value: str, entry: RosterEntry
    ) -> ChargeNormalizationResult:
        return ChargeNormalizationResult(
            raw_value=raw_value,
            match_method=method,
            normalized_id=entry.normalized_id,
            display_name=entry.display_name,
        )

    @staticmethod
    def _unmatched(raw_value: str, warning: str) -> ChargeNormalizationResult:
        return ChargeNormalizationResult(
            raw_value=raw_value,
            match_method=MATCH_METHOD_UNMATCHED,
            warnings=(warning,),
        )

    @staticmethod
    def _ambiguous(
        raw_value: str, warning: str, entries: Sequence[RosterEntry]
    ) -> ChargeNormalizationResult:
        return ChargeNormalizationResult(
            raw_value=raw_value,
            match_method=MATCH_METHOD_AMBIGUOUS,
            warnings=(warning,),
            candidates=_candidates(entries),
        )


def build_charge_review_item(
    result: ChargeNormalizationResult,
    *,
    source_document_id: str,
    charge_sequence: int | str,
    parsed_docket_id: str | None = None,
    parsed_charge_id: str | None = None,
) -> dict[str, object] | None:
    """Build a ``review.queue_items`` payload for a charge result, or ``None``.

    Returns ``None`` when ``result.review_needed`` is False (a clean match with
    no blocking warning). Otherwise delegates to the 22.1 :func:`build_review_item`
    with the pinned 21.2 vocabulary (Answer 2):

    - unmatched / empty     -> unmapped_charge / charge_not_normalized / medium
    - same-tier ambiguous   -> ambiguous_charge / charge_not_normalized / medium
    - statute/text conflict -> ambiguous_charge / blocking_warning / high

    The dedup key is derived by :func:`build_review_item` from
    ``source_document_id``, ``item_type`` and the charge-grain locator
    ``(str(charge_sequence),)`` only. ``parsed_docket_id`` / ``parsed_charge_id``
    are carried as re-anchoring payload but by construction NEVER enter the key
    (Required Fix 2 test proves this).
    """
    if not result.review_needed:
        return None

    if NORM_STATUTE_TEXT_CONFLICT in result.warnings:
        item_type = AMBIGUOUS_CHARGE
        reason_code = BLOCKING_WARNING
        severity = SEVERITY_HIGH
    elif result.match_method == MATCH_METHOD_AMBIGUOUS:
        item_type = AMBIGUOUS_CHARGE
        reason_code = CHARGE_NOT_NORMALIZED
        severity = SEVERITY_MEDIUM
    else:  # unmatched (NORM_UNMATCHED or NORM_EMPTY_INPUT)
        item_type = UNMAPPED_CHARGE
        reason_code = CHARGE_NOT_NORMALIZED
        severity = SEVERITY_MEDIUM

    candidate_context: Mapping[str, object] | None = None
    if result.candidates:
        candidate_context = {
            "candidates": [
                {"normalized_id": c.normalized_id, "display_name": c.display_name}
                for c in result.candidates
            ]
        }

    return build_review_item(
        source_document_id=source_document_id,
        item_type=item_type,
        severity=severity,
        reason_code=reason_code,
        locator=(str(charge_sequence),),
        parsed_docket_id=parsed_docket_id,
        parsed_charge_id=parsed_charge_id,
        entity_type="charge",
        raw_value=result.raw_value,
        candidate_context=candidate_context,
    )
