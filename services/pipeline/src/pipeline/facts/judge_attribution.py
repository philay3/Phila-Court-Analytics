"""Conservative judge-attribution resolver (Task 23.1, the genuine SD-1 problem).

Given a parsed docket + its charges and the 22.3 judge normalizer, decide — per
charge — WHICH judge (if any) the charge's outcome is attributed to. The resolver
is conservative BY CONSTRUCTION: false-negative bias, ambiguity routes to review,
it NEVER guesses and NEVER tie-breaks. It is PURE and DB-free (mirrors the 22.x
matcher/mapper split): it operates over in-memory records + an injected
:class:`JudgeMatcher`; a caller at the orchestration boundary loads the parsed
rows and hands them here.

Three attribution methods (pinned SD 1):

- ``disposition_judge`` (primary, pinned #1) — the charge's ``disposition_judge_raw``
  roster-matches to a single judge via 22.3. That judge, full stop.
- ``assigned_judge_rule`` (fallback, pinned #2; APPROVED rule below) — used ONLY
  under the narrow, docket-scoped rule, never probabilistically.
- ``none`` (pinned #3) — otherwise unattributed. Unattributed NEVER blocks a
  charge-only fact (pinned #5); it only gates ``judge_specific_eligible``, which
  23.2/23.3 enforce — NOT here.

The APPROVED ``assigned_judge_rule`` (evidence-backed by the parsed.* recon at the
23.1 plan gate) is DOCKET-SCOPED and single-path:

  A docket is *fallback-eligible* iff NO charge on it carries a roster-matched
  (single) disposition judge AND ``assigned_judge_raw`` roster-matches to a single
  unambiguous judge. On a fallback-eligible docket, a charge whose disposition
  judge is ABSENT is attributed to the assigned judge (``assigned_judge_rule``).

The docket scope is load-bearing: recon showed disposition judge != assigned judge
on 238/1417 dockets (17%), so the assigned judge is substituted ONLY when the
docket carries no disposition-judge signal at all — this structurally prevents the
pinned #6 disposition-vs-assigned conflict from ever producing a fallback
attribution.

Two per-charge guardrails keep the fallback honest (both = "the charge captured
its OWN disposition judge, so assigned-judge fallback would be a guess"):

- **present-but-unresolved** — ``disposition_judge_raw`` is present but 22.3 returns
  ``unmatched`` or ``ambiguous`` => ``method=none`` (never fallback).
- **captured-then-nulled** (23.1 plan-gate DP1) — the parser CAPTURED a disposition
  judge on this charge and NULLED it (18.2/18.3 hardening), recording a charge-grain
  warning in :data:`DISPOSITION_JUDGE_NULLED_WARNING_CODES`. The null erases the
  raw value, so absent the warning the charge is indistinguishable from a genuinely
  judge-less charge; the warning restores the "a disposition judge was here" signal,
  so such a charge is treated as present-but-unresolved => ``method=none``. This
  generalizes to every future junk-null as the corpus grows.

Ambiguity (pinned #6): an ``ambiguous`` disposition judge (one captured value
resolving to >= 2 roster identities) => ``method=none`` PLUS a review descriptor
built via the 22.1 :func:`build_review_item` helper (item_type
``ambiguous_judge_attribution``, reason ``judge_not_attributed``, HIGH). The
descriptor is emitted for THIS case ONLY; an ``unmatched``/absent disposition judge
carries the 22.3/23.4 ``unmapped_judge`` normalization signal, which 23.1 does not
double-emit.

Inheritance (pinned #4, AC 5): :func:`build_docket_context` derives the docket-level
decision ONCE per docket; :func:`resolve_charge` returns a reusable
:class:`AttributionResult` per charge. 23.3 calls the resolver once per PARENT
charge and reuses that result for every sentence component — sentence facts carry
no judge of their own, so there is no re-derivation path.

NO ``fact.*`` writes, NO ``fact_build_runs``, NO eligibility booleans here — 23.1
is pure attribution logic only. Raw judge values are permitted inside the review
descriptor payload (an internal-only table) but NEVER in console / log output.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pipeline.fact_review_vocab import (
    AMBIGUOUS_JUDGE_ATTRIBUTION,
    JUDGE_NOT_ATTRIBUTED,
    SEVERITY_HIGH,
)
from pipeline.normalization.judge_matcher import ENTITY_JUDGE, JudgeMatcher
from pipeline.normalization.review_items import build_review_item
from pipeline.normalization.vocab import MATCH_METHOD_AMBIGUOUS
from pipeline.warning_codes import SENTINEL_COLLISION, SUSPECT_JUDGE_LINE

# --- Attribution methods (pinned SD 1; the resolver's closed output vocabulary) -
METHOD_DISPOSITION_JUDGE = "disposition_judge"
METHOD_ASSIGNED_JUDGE_RULE = "assigned_judge_rule"
METHOD_NONE = "none"

ATTRIBUTION_METHODS: frozenset[str] = frozenset(
    {METHOD_DISPOSITION_JUDGE, METHOD_ASSIGNED_JUDGE_RULE, METHOD_NONE}
)

# Methods that carry an attributed judge identity (the two non-``none`` arms).
_ATTRIBUTED_METHODS: frozenset[str] = frozenset(
    {METHOD_DISPOSITION_JUDGE, METHOD_ASSIGNED_JUDGE_RULE}
)

# Charge-grain parser warnings that mean a disposition judge was CAPTURED on this
# charge and NULLED by 18.2/18.3 hardening (DP1). Both are the parser's two
# disposition-judge null branches (``_is_junk_judge`` -> SUSPECT_JUDGE_LINE;
# ``collides_with_sentinels`` -> SENTINEL_COLLISION), emitted with the charge
# sequence in the DISPOSITION section. A charge carrying either is treated as
# present-but-unresolved (never eligible for assigned-judge fallback). Keyed on the
# semantic class, not a single code, so it covers every future junk-null.
DISPOSITION_JUDGE_NULLED_WARNING_CODES: frozenset[str] = frozenset(
    {SUSPECT_JUDGE_LINE, SENTINEL_COLLISION}
)

# The charge-record key carrying that charge's charge-grain parser warning codes
# (from ``parsed.warnings`` for this docket + sequence). The caller populates it;
# absent / empty means "no charge-grain warnings". Kept as a documented soft key
# so the resolver stays a pure function over record mappings.
_CHARGE_WARNING_CODES_KEY = "warning_codes"


def _single_matched_id(matcher: JudgeMatcher, raw: object) -> str | None:
    """Return the single roster-matched normalized id for a raw judge value.

    ``None`` for absent (null/blank), ``unmatched``, or ``ambiguous`` — i.e. the
    id is present iff 22.3 resolves the value to exactly one roster identity
    (``normalized_id`` is set only on a matched method, per the 22.1 model
    invariant). A raw judge value is any string-or-``None``.
    """
    result = matcher.match(raw if raw is None else str(raw))
    if result is None:
        return None
    return result.normalized_id


def _charge_disposition_judge_nulled(charge: Mapping[str, object]) -> bool:
    """True iff this charge captured a disposition judge that was then nulled (DP1).

    Reads the charge's charge-grain parser warning codes and tests membership in
    :data:`DISPOSITION_JUDGE_NULLED_WARNING_CODES`. Missing / empty => False.
    """
    codes = charge.get(_CHARGE_WARNING_CODES_KEY, ())
    if not codes:
        return False
    return any(code in DISPOSITION_JUDGE_NULLED_WARNING_CODES for code in codes)


@dataclass(frozen=True)
class DocketAttributionContext:
    """The docket-level attribution decision, derived ONCE per docket (AC 5).

    - ``assigned_judge_id`` — the single unambiguous roster match for
      ``assigned_judge_raw``, or ``None`` (absent / unmatched / ambiguous).
    - ``fallback_eligible`` — True iff the APPROVED docket-scoped rule opens the
      assigned-judge fallback for this docket: NO charge carries a roster-matched
      disposition judge AND ``assigned_judge_id`` is present.

    Frozen and self-consistent: ``fallback_eligible`` implies a non-null
    ``assigned_judge_id``.
    """

    assigned_judge_id: str | None
    fallback_eligible: bool

    def __post_init__(self) -> None:
        if self.fallback_eligible and self.assigned_judge_id is None:
            raise ValueError("fallback_eligible requires a matched assigned_judge_id")


@dataclass(frozen=True)
class AttributionResult:
    """The per-charge attribution decision (AC 1 output triple).

    - ``normalized_judge_id`` — the attributed judge id, present iff ``method`` is
      an attributed method (``disposition_judge`` / ``assigned_judge_rule``).
    - ``method`` — one of :data:`ATTRIBUTION_METHODS`.
    - ``review_descriptor`` — a ``review.queue_items`` payload (from the 22.1
      helper) for the ambiguous-attribution case ONLY; ``None`` otherwise. Present
      only when ``method`` is ``none``.

    Reusable by 23.3 for every sentence component of the parent charge (pinned #4).
    Invariants are enforced at construction, making invalid states unrepresentable.
    """

    normalized_judge_id: str | None
    method: str
    review_descriptor: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if self.method not in ATTRIBUTION_METHODS:
            raise ValueError(f"unknown attribution method: {self.method!r}")
        if self.method in _ATTRIBUTED_METHODS:
            if self.normalized_judge_id is None:
                raise ValueError(f"{self.method!r} requires a normalized_judge_id")
            if self.review_descriptor is not None:
                raise ValueError(f"{self.method!r} must not carry a review descriptor")
        else:  # none
            if self.normalized_judge_id is not None:
                raise ValueError("method=none must not carry a normalized_judge_id")


def build_docket_context(
    docket: Mapping[str, object], matcher: JudgeMatcher
) -> DocketAttributionContext:
    """Derive the docket-level attribution context ONCE per docket (AC 5).

    ``docket`` is a parsed docket record with ``assigned_judge_raw`` and a
    ``charges`` sequence (each charge a mapping with ``disposition_judge_raw``).
    Computes the assigned-judge match and the APPROVED docket-scoped
    fallback-eligibility gate. Pure; no DB, no I/O.
    """
    assigned_id = _single_matched_id(matcher, docket.get("assigned_judge_raw"))

    charges: Sequence[Mapping[str, object]] = docket.get("charges", ())  # type: ignore[assignment]
    matched_disposition_ids: set[str] = set()
    for charge in charges:
        disp_id = _single_matched_id(matcher, charge.get("disposition_judge_raw"))
        if disp_id is not None:
            matched_disposition_ids.add(disp_id)

    fallback_eligible = not matched_disposition_ids and assigned_id is not None
    return DocketAttributionContext(
        assigned_judge_id=assigned_id, fallback_eligible=fallback_eligible
    )


def resolve_charge(
    charge: Mapping[str, object],
    context: DocketAttributionContext,
    matcher: JudgeMatcher,
    *,
    source_document_id: str,
    parsed_docket_id: str | None = None,
    parsed_charge_id: str | None = None,
) -> AttributionResult:
    """Resolve attribution for one charge (pinned SD 1). Pure; no DB, no I/O.

    Decision order:

    1. disposition matched (single) -> ``disposition_judge`` + that judge.
    2. disposition ``ambiguous`` -> ``none`` + review descriptor (pinned #6).
    3. disposition ``unmatched`` -> ``none`` (present-but-unresolved; the
       ``unmapped_judge`` signal is 22.3/23.4's, not double-emitted here).
    4. disposition ABSENT but captured-then-nulled (DP1) -> ``none`` (never
       fallback: the charge captured its own judge).
    5. disposition ABSENT on a fallback-eligible docket -> ``assigned_judge_rule``
       + the assigned judge (the APPROVED docket-scoped rule).
    6. otherwise -> ``none``.

    ``source_document_id`` (a ``raw.*`` UUID, stable across parsed reloads) anchors
    the review descriptor's dedup key; ``parsed_docket_id`` / ``parsed_charge_id``
    ride as non-key re-anchoring context ONLY (never enter the dedup key).
    """
    raw = charge.get("disposition_judge_raw")
    result = matcher.match(raw if raw is None else str(raw))

    if result is not None:
        if result.normalized_id is not None:
            # (1) single roster match -> primary attribution.
            return AttributionResult(
                normalized_judge_id=result.normalized_id,
                method=METHOD_DISPOSITION_JUDGE,
            )
        if result.match_method == MATCH_METHOD_AMBIGUOUS:
            # (2) ambiguous -> none + review descriptor (pinned #6). Never pick.
            descriptor = _build_attribution_review_item(
                result_candidates=result.candidates,
                raw_value=result.raw_value,
                source_document_id=source_document_id,
                charge_sequence=charge["sequence"],
                parsed_docket_id=parsed_docket_id,
                parsed_charge_id=parsed_charge_id,
            )
            return AttributionResult(
                normalized_judge_id=None,
                method=METHOD_NONE,
                review_descriptor=descriptor,
            )
        # (3) unmatched -> none, no attribution descriptor.
        return AttributionResult(normalized_judge_id=None, method=METHOD_NONE)

    # disposition judge ABSENT (null/blank) from here.
    if _charge_disposition_judge_nulled(charge):
        # (4) captured-then-nulled -> present-but-unresolved; never fallback (DP1).
        return AttributionResult(normalized_judge_id=None, method=METHOD_NONE)

    if context.fallback_eligible:
        # (5) the APPROVED docket-scoped assigned-judge fallback.
        return AttributionResult(
            normalized_judge_id=context.assigned_judge_id,
            method=METHOD_ASSIGNED_JUDGE_RULE,
        )

    # (6) unattributed.
    return AttributionResult(normalized_judge_id=None, method=METHOD_NONE)


def _build_attribution_review_item(
    *,
    result_candidates: Sequence[object],
    raw_value: str,
    source_document_id: str,
    charge_sequence: object,
    parsed_docket_id: str | None,
    parsed_charge_id: str | None,
) -> dict[str, object]:
    """Build the ambiguous-attribution review descriptor via the 22.1 helper.

    Pinned mapping (23.1 plan gate DP2): item_type ``ambiguous_judge_attribution``,
    reason ``judge_not_attributed`` (the accurate eligibility consequence — the
    judges DID normalize; attribution is what is ambiguous), severity HIGH (a
    wrong-judge attribution contaminates judge-specific aggregates, a public
    surface). The charge-grain locator ``("judge", "attribution", <sequence>)`` is
    distinct from 22.3's disposition locator so the two never collide. The dedup
    key is source_document_id + locator ONLY; the parsed pointers ride as non-key
    context.
    """
    candidate_context: Mapping[str, object] | None = None
    if result_candidates:
        candidate_context = {
            "candidates": [
                {"normalized_id": c.normalized_id, "display_name": c.display_name}  # type: ignore[attr-defined]
                for c in result_candidates
            ]
        }

    return build_review_item(
        source_document_id=source_document_id,
        item_type=AMBIGUOUS_JUDGE_ATTRIBUTION,
        severity=SEVERITY_HIGH,
        reason_code=JUDGE_NOT_ATTRIBUTED,
        locator=(ENTITY_JUDGE, "attribution", str(charge_sequence)),
        parsed_docket_id=parsed_docket_id,
        parsed_charge_id=parsed_charge_id,
        entity_type=ENTITY_JUDGE,
        raw_value=raw_value,
        candidate_context=candidate_context,
    )
