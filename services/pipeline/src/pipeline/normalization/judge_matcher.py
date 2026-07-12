"""Pure judge matcher + name canonicalization (Task 22.3).

This module is PURE: it operates over an in-memory roster snapshot (roster
entries + aliases) with NO database access and NO psycopg import in its path
(mirrors the 22.2 charge matcher). A thin, separate loader
(``judge_roster_loader.py``) fetches the snapshot from ``ref.normalized_judges``
+ ``ref.judge_aliases`` at the orchestration/CLI boundary and hands it here. That
split keeps the matcher tier-1 synthetic-testable.

The Sprint 4 durable fix (settled §6.7): both judge-capture paths accept any
name-shaped span with zero judge validation. Validation happens HERE — a raw
judge value is normalized against the real roster or it does not resolve. The
matcher structurally CANNOT distinguish an issuing-authority / non-judge value
from a real judge missing from the roster: both are ``unmatched`` (pinned
decision 3). There is no fuzzy-accept and no nearest-neighbor fallback, ever.

Canonicalization (pinned decisions 1, 4) is applied symmetrically to both the
roster names and the captured values, and is display-format-INDEPENDENT: it
parses the captured CPCMS surname-first comma form (``"Surname, Given Middle"``)
and the natural-order roster form (``"Given Middle Surname"``) into the same
structured ``(surname, given)`` identity. Rules:

- honorific stripping (``Hon.`` / ``Honorable`` / ``Judge`` / ``Justice``);
- case / punctuation / whitespace insensitivity, with intra-name hyphens and
  apostrophes deleted so hyphenated surnames (``Bryant-Powell``) are single
  tokens that match in both orders, and generational suffixes (``Jr.`` / ``Sr.``)
  carried as a separate identity component (so ``Jr`` never merges with ``Sr``);
- middle-initial tolerance, INCLUDING the initial<->full-name bridge (captured
  ``"M"`` matches directory ``"Marie"``) and the absent-middle wildcard (a raw
  value lacking a middle is compatible with any single roster middle) — applied
  only when it resolves to exactly ONE roster identity; two roster identities
  differing only by middle yield ``ambiguous`` + candidates, never a silent pick.

Match precedence: exact(full) -> alias(full) -> middle-initial-tolerant(exact) ->
ambiguous / unmatched. ``statute`` and ``pattern`` are NEVER emitted (a test
asserts both, as 22.2 asserted pattern-never-emitted for charges). A null / blank
field is ABSENT input (pinned decision 8): :meth:`JudgeMatcher.match` returns
``None`` — no result, no review item, nothing reconstructed.

Review items for unmatched / ambiguous results are built via the 22.1
:func:`build_review_item` helper only (:func:`build_judge_review_item`), with the
21.2 vocabulary and the canonical dedup key. Raw judge values are permitted
inside results and review-item payloads (internal-only tables) but NEVER in
console / log output (pinned decision 5).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pipeline.fact_review_vocab import (
    AMBIGUOUS_JUDGE,
    JUDGE_NOT_NORMALIZED,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    UNMAPPED_JUDGE,
)
from pipeline.normalization.models import (
    JudgeNormalizationResult,
    NormalizationCandidate,
)
from pipeline.normalization.review_items import build_review_item
from pipeline.normalization.vocab import (
    MATCH_METHOD_ALIAS,
    MATCH_METHOD_AMBIGUOUS,
    MATCH_METHOD_EXACT,
    MATCH_METHOD_UNMATCHED,
    NORM_AMBIGUOUS,
    NORM_UNMATCHED,
)

# Source-role tags (pinned decision 6): each raw field is matched independently
# and its result is tagged with its source role by the CALLER (the frozen 22.1
# JudgeNormalizationResult is not modified). The role is carried into the review
# item's dedup locator so assigned and disposition captures on one docket stay
# distinct (two results, never merged).
ENTITY_JUDGE = "judge"
ROLE_ASSIGNED = "assigned"
ROLE_DISPOSITION = "disposition"

# Obviously-fake Sprint 2 seed judges (pinned decision 7). SOURCE OF TRUTH is
# db/seeds/reference-data.ts (JUDGE_SEEDS); this set MIRRORS those slugs and is
# FROZEN — the fake judges are never grown, and the Sprint 7 sweep deletes them.
# The seed's real<->fake slug-collision assertion is the seed-time backstop; this
# constant is the match-time backstop, so a real docket value can NEVER resolve
# to a fabricated judge identity even if one reached the snapshot.
FAKE_JUDGE_SLUGS: frozenset[str] = frozenset(
    {
        "judge-testina-placeholder",
        "judge-samuel-seeddata",
        "judge-fakename-example",
    }
)

# Leading honorific(s) to strip before parsing. Matched repeatedly from the
# start so "The Honorable Judge ..." folds fully. None appear in the loaded
# corpus (0/95 distinct values) — this is defensive robustness across sources.
# NOTE: a bare "J." is deliberately NOT a honorific here — it collides with a
# legitimate first initial (e.g. "J. Scott O'Keefe").
_HONORIFIC = re.compile(
    r"^(?:the\s+)?(?:hon(?:ora(?:ble|ur)?)?\.?|honou?rable|judge|justice)\s+",
    re.IGNORECASE,
)

# Intra-name punctuation deleted (joined, not spaced) so a hyphenated or
# apostrophe surname is a SINGLE token in both the comma form and natural order:
# "Bryant-Powell" -> "bryantpowell", "O'Keefe" -> "okeefe". This makes hyphenated
# surnames match symmetrically without a comma-form alias (there are no
# space-separated compound surnames in the corpus). Curly apostrophe included.
_INTRA_PUNCT = re.compile(r"['’\-]")

# Non-alphanumeric run -> single space, for token folding.
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Generational suffix tokens, carried as a SEPARATE identity component so the
# natural-order surname stays the last NON-suffix token and Jr. never merges with
# Sr. (they compare unequal). Present in the corpus on several judges.
_SUFFIX_TOKENS: frozenset[str] = frozenset({"jr", "sr", "ii", "iii", "iv"})


def _fold(value: str) -> str:
    """Lower-case, drop intra-name punctuation, fold to single-spaced tokens."""
    return _NON_ALNUM.sub(" ", _INTRA_PUNCT.sub("", value.lower())).strip()


def _strip_honorifics(value: str) -> str:
    prev: str | None = None
    current = value.strip()
    while prev != current:
        prev = current
        current = _HONORIFIC.sub("", current).strip()
    return current


@dataclass(frozen=True)
class CanonName:
    """A structured, folded name identity: ``(surname, given, suffix)``.

    ``given`` is first name followed by any middle tokens; ``suffix`` is a
    generational suffix (``jr`` / ``sr`` / ...) held separately so it never
    pollutes the surname or a middle slot. Surname is identified POSITIONALLY —
    from the comma on the captured / comma-form side, and as the last non-suffix
    token on the natural-order roster side — so the two formats compare
    symmetrically and surname/given can never be silently swapped.
    """

    surname: tuple[str, ...]
    given: tuple[str, ...]
    suffix: tuple[str, ...] = ()

    @property
    def exact_key(self) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        return (self.surname, self.given, self.suffix)

    @property
    def first(self) -> str | None:
        return self.given[0] if self.given else None

    @property
    def middles(self) -> tuple[str, ...]:
        return self.given[1:]


def canonicalize_name(value: str | None) -> CanonName | None:
    """Parse a raw or roster name into a :class:`CanonName`, or ``None``.

    ``None`` / blank / whitespace-only -> ``None`` (absent input, pinned decision
    8). Otherwise: strip honorifics, then split on the FIRST comma when present
    (surname before, given after — the CPCMS captured form); with no comma, treat
    the value as natural order and take the last NON-suffix token as the surname
    (the roster form). Intra-name hyphens / apostrophes are deleted by
    :func:`_fold`, so hyphenated surnames are single tokens that match in both
    orders without an alias. Generational suffixes (``Jr.`` / ``Sr.`` / ...) are
    pulled into their own component so the natural-order surname is correct and
    ``Jr`` never merges with ``Sr``.
    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    stripped = _strip_honorifics(stripped)
    if "," in stripped:
        surname_part, _, given_part = stripped.partition(",")
        surname = tuple(_fold(surname_part).split())
        given = list(_fold(given_part).split())
    else:
        tokens = _fold(stripped).split()
        # Pull trailing suffixes first so the surname is the last NON-suffix token.
        tail_suffix: list[str] = []
        while tokens and tokens[-1] in _SUFFIX_TOKENS:
            tail_suffix.insert(0, tokens.pop())
        if not tokens:
            return None
        surname = (tokens[-1],)
        given = tokens[:-1] + tail_suffix
    # Extract the trailing suffix from the given tail (unifies both forms).
    suffix: list[str] = []
    while given and given[-1] in _SUFFIX_TOKENS:
        suffix.insert(0, given.pop())
    if not surname and not given and not suffix:
        return None
    return CanonName(surname=surname, given=tuple(given), suffix=tuple(suffix))


def _middles_compatible(
    raw_middles: tuple[str, ...], entry_middles: tuple[str, ...]
) -> bool:
    """Middle-token compatibility for the tolerance tier (pinned decision 4).

    - Absent-middle wildcard: if EITHER side has no middle tokens, they are
      compatible (a raw value lacking a middle matches a roster middle; test both
      directions). This is what makes a raw value ambiguous across two roster
      identities that differ only by middle initial.
    - Otherwise same count, and each position matches exactly OR one side is a
      single-letter initial equal to the first letter of the other (bridges the
      captured ``"M"`` <-> directory ``"Marie"`` case).
    """
    if not raw_middles or not entry_middles:
        return True
    if len(raw_middles) != len(entry_middles):
        return False
    for a, b in zip(raw_middles, entry_middles, strict=True):
        if a == b:
            continue
        if len(a) == 1 and a == b[0]:
            continue
        if len(b) == 1 and b == a[0]:
            continue
        return False
    return True


def _suffix_compatible(
    raw_suffix: tuple[str, ...], cand_suffix: tuple[str, ...]
) -> bool:
    """Generational-suffix compatibility, parallel to the middle-initial rule.

    Absent-suffix wildcard: a captured value lacking a suffix is compatible with
    a suffixed roster entry (so it is ``exact`` against a unique suffixed judge,
    and ``ambiguous`` across two entries differing only by ``Jr``/``Sr``). But two
    PRESENT suffixes must match exactly — ``Jr`` never resolves to ``Sr``.
    """
    if not raw_suffix or not cand_suffix:
        return True
    return raw_suffix == cand_suffix


def _tolerant_match(raw: CanonName, cand: CanonName) -> bool:
    """True iff ``raw`` matches ``cand`` under middle-initial / suffix tolerance.

    Requires an identical surname and an identical FIRST given token on both
    sides (a bare surname with no first name never tolerance-matches), then
    suffix compatibility (absent-suffix wildcard; two present suffixes must be
    equal) and middle compatibility. Exact and alias tiers run first, so tolerance
    only resolves genuine middle-initial / absent-suffix variance.
    """
    if raw.surname != cand.surname:
        return False
    if not _suffix_compatible(raw.suffix, cand.suffix):
        return False
    if raw.first is None or cand.first is None or raw.first != cand.first:
        return False
    return _middles_compatible(raw.middles, cand.middles)


@dataclass(frozen=True)
class RosterEntry:
    """One normalized-judge roster row, in the in-memory snapshot.

    ``normalized_id`` is the stable identity a matched result / candidate carries
    (the ``ref.normalized_judges`` id at the DB boundary; any stable string in
    synthetic tests). ``display_name`` is the public natural-order string; the
    matcher parses it positionally. ``aliases`` are alternate FORMS (name
    variants, and a comma-form alias for any SPACE-separated compound surname,
    which natural-order parsing cannot recover). NO raw docket data lives here —
    names come from public judicial directories.
    """

    normalized_id: str
    slug: str
    display_name: str
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.normalized_id:
            raise ValueError("roster entry normalized_id must be non-empty")
        if not self.slug:
            raise ValueError("roster entry slug must be non-empty")
        if not self.display_name:
            raise ValueError("roster entry display_name must be non-empty")


@dataclass(frozen=True)
class RosterSnapshot:
    """An immutable set of roster entries the matcher indexes over."""

    entries: tuple[RosterEntry, ...] = ()


def exclude_fake_judges(entries: Sequence[RosterEntry]) -> tuple[RosterEntry, ...]:
    """Drop the fabricated Sprint 2 seed judges from a candidate pool.

    The candidate-pool filter of pinned decision 7 (preferred over a ``ref.*``
    column). Applied by the loader after fetch so the matcher can never resolve a
    real docket value to a fake identity. Pure over :class:`RosterEntry`, so it
    is tier-1 testable without a database.
    """
    return tuple(e for e in entries if e.slug not in FAKE_JUDGE_SLUGS)


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


class JudgeMatcher:
    """Normalize a raw judge name against a roster snapshot.

    Pure and DB-free. Canonical lookup maps are built once at construction;
    :meth:`match` is a read-only decision tree over them. The candidate pool is
    the REAL roster; callers exclude the fake judges (via
    :func:`exclude_fake_judges`) before constructing the matcher.
    """

    def __init__(self, snapshot: RosterSnapshot) -> None:
        self._exact: dict[tuple, list[RosterEntry]] = {}
        self._alias: dict[tuple, list[RosterEntry]] = {}
        # Tolerance pool: (canonical name, entry, is_display). Display identities
        # yield `exact` on a tolerant hit (pinned decision 1); alias-origin
        # identities yield `alias` (compound-surname comma forms register as
        # alias, per the roster-gate answer).
        self._identities: list[tuple[CanonName, RosterEntry, bool]] = []
        # Identical-canonical-key fail-loud guard: two distinct roster identities
        # may not share a display canonical key, else exact matching would be
        # order-unsafe.
        display_key_owner: dict[tuple, str] = {}
        for entry in snapshot.entries:
            cn = canonicalize_name(entry.display_name)
            if cn is None:
                raise ValueError(
                    f"roster display_name does not parse: slug={entry.slug!r}"
                )
            owner = display_key_owner.get(cn.exact_key)
            if owner is not None and owner != entry.normalized_id:
                raise ValueError(
                    "roster integrity error: two identities share a canonical "
                    f"name key (slug={entry.slug!r})"
                )
            display_key_owner.setdefault(cn.exact_key, entry.normalized_id)
            self._exact.setdefault(cn.exact_key, []).append(entry)
            self._identities.append((cn, entry, True))
            for alias in entry.aliases:
                acn = canonicalize_name(alias)
                if acn is None:
                    continue
                self._alias.setdefault(acn.exact_key, []).append(entry)
                self._identities.append((acn, entry, False))

    def match(self, value: str | None) -> JudgeNormalizationResult | None:
        """Normalize one raw judge value; return a result or ``None`` (absent).

        Arms:

        1. absent  — null / blank -> ``None`` (pinned decision 8; no result).
        2. exact   — folded name == a display identity (single entry).
        3. alias   — folded name == an alias form (single entry), no exact.
        4. exact (tolerant) — middle-initial-tolerant hit on a display identity
           resolving to a single entry.
        5. alias (tolerant) — tolerant hit resolving to a single entry only via
           an alias form (e.g. a compound-surname comma alias).
        6. ambiguous — a tolerant hit resolving to >= 2 distinct identities, or a
           display / alias key shared by >= 2 identities -> ``ambiguous`` +
           candidates (never a silent pick).
        7. unmatched — nothing matches -> ``unmatched`` + ``NORM_UNMATCHED``.
        """
        cn = canonicalize_name(value)
        if cn is None:
            return None
        raw_value = value.strip()  # type: ignore[union-attr]  # cn None-guards blanks

        exact_entries = self._exact.get(cn.exact_key, [])
        if exact_entries:
            ids = {e.normalized_id for e in exact_entries}
            if len(ids) == 1:
                return self._matched(MATCH_METHOD_EXACT, raw_value, exact_entries[0])
            return self._ambiguous(raw_value, exact_entries)

        alias_entries = self._alias.get(cn.exact_key, [])
        if alias_entries:
            ids = {e.normalized_id for e in alias_entries}
            if len(ids) == 1:
                return self._matched(MATCH_METHOD_ALIAS, raw_value, alias_entries[0])
            return self._ambiguous(raw_value, alias_entries)

        # Tolerance tier: gather every identity compatible under middle-initial
        # tolerance, tracking whether each id was reached via a display form.
        tol: dict[str, tuple[RosterEntry, bool]] = {}
        for cand_cn, entry, is_display in self._identities:
            if _tolerant_match(cn, cand_cn):
                existing = tol.get(entry.normalized_id)
                reached_via_display = is_display or (
                    existing is not None and existing[1]
                )
                tol[entry.normalized_id] = (entry, reached_via_display)
        if not tol:
            return self._unmatched(raw_value)
        if len(tol) == 1:
            entry, via_display = next(iter(tol.values()))
            method = MATCH_METHOD_EXACT if via_display else MATCH_METHOD_ALIAS
            return self._matched(method, raw_value, entry)
        return self._ambiguous(raw_value, [e for e, _ in tol.values()])

    @staticmethod
    def _matched(
        method: str, raw_value: str, entry: RosterEntry
    ) -> JudgeNormalizationResult:
        return JudgeNormalizationResult(
            raw_value=raw_value,
            match_method=method,
            normalized_id=entry.normalized_id,
            display_name=entry.display_name,
        )

    @staticmethod
    def _unmatched(raw_value: str) -> JudgeNormalizationResult:
        return JudgeNormalizationResult(
            raw_value=raw_value,
            match_method=MATCH_METHOD_UNMATCHED,
            warnings=(NORM_UNMATCHED,),
        )

    @staticmethod
    def _ambiguous(
        raw_value: str, entries: Sequence[RosterEntry]
    ) -> JudgeNormalizationResult:
        return JudgeNormalizationResult(
            raw_value=raw_value,
            match_method=MATCH_METHOD_AMBIGUOUS,
            warnings=(NORM_AMBIGUOUS,),
            candidates=_candidates(entries),
        )


def build_judge_review_item(
    result: JudgeNormalizationResult | None,
    *,
    source_document_id: str,
    role: str,
    charge_sequence: int | str | None = None,
    parsed_docket_id: str | None = None,
    parsed_charge_id: str | None = None,
) -> dict[str, object] | None:
    """Build a ``review.queue_items`` payload for a judge result, or ``None``.

    Returns ``None`` for an absent input (``result is None``) or a clean match
    (``review_needed`` False). Otherwise delegates to the 22.1
    :func:`build_review_item` with the pinned mapping (Answer 1):

    - unmatched -> ``unmapped_judge`` / ``judge_not_normalized`` / medium
    - ambiguous -> ``ambiguous_judge`` / ``judge_not_normalized`` / HIGH

    Ambiguous is higher severity: a wrong-judge attribution contaminates
    judge-specific aggregates, a core public surface (pinned decision 9).

    Role context (pinned decision 6) is carried in the dedup locator so assigned
    and disposition captures never collide on one docket:

    - assigned (docket grain)    -> ``("judge", "assigned")``
    - disposition (charge grain) -> ``("judge", "disposition", str(charge_sequence))``

    ``parsed_docket_id`` / ``parsed_charge_id`` are carried as re-anchoring
    payload but by construction NEVER enter the dedup key.
    """
    if result is None or not result.review_needed:
        return None

    if role == ROLE_ASSIGNED:
        locator: tuple[str, ...] = (ENTITY_JUDGE, ROLE_ASSIGNED)
    elif role == ROLE_DISPOSITION:
        if charge_sequence is None:
            raise ValueError(
                "disposition judge review item requires a charge_sequence locator"
            )
        locator = (ENTITY_JUDGE, ROLE_DISPOSITION, str(charge_sequence))
    else:
        raise ValueError(f"unknown judge source role: {role!r}")

    if result.match_method == MATCH_METHOD_AMBIGUOUS:
        item_type = AMBIGUOUS_JUDGE
        severity = SEVERITY_HIGH
    else:  # unmatched
        item_type = UNMAPPED_JUDGE
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
        reason_code=JUDGE_NOT_NORMALIZED,
        locator=locator,
        parsed_docket_id=parsed_docket_id,
        parsed_charge_id=parsed_charge_id,
        entity_type=ENTITY_JUDGE,
        raw_value=result.raw_value,
        candidate_context=candidate_context,
    )
