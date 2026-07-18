"""Pure disposition -> outcome-code mapper (Task 22.4).

Maps a parsed ``disposition_raw`` string to a public outcome taxonomy code via a
deterministic, corpus-evidenced EXACT-match table (:data:`DISPOSITION_OUTCOME_MAP`).
This mirrors the 18.2 repair-table principle: exact-match on captured state,
never fuzzy / normalized / partial matching, never adjacent-line reading. There
is exactly one lookup — ``dict.get`` on the verbatim raw string — and no text
folding anywhere in this module (contrast the 22.2 charge matcher, which folds).

Three arms:

- **held carve-out (AC 4; extended by Task 29.3)** — ``disposition_raw`` IS NULL
  *or* is one of the :data:`HELD_FOR_COURT_DISPOSITIONS` forms: the charge ended
  the parse undisposed (the 18.1 terminality predicate,
  :func:`charge_has_terminal_disposition`, is False), or it is a non-terminal MC
  bind-over recorded as a disposition value (Task 29.3 Mechanism A).
  :meth:`OutcomeMapper.map` returns ``None`` — NO outcome fact and NO review
  item. A held charge is NOT "unmapped"; routing a null disposition or a
  bind-over to review as a false ``unmapped`` is the quiet-bug spot these tasks
  guard against.
- **mapped** — a terminal ``disposition_raw`` present in the table -> its outcome
  code, ``public_eligible`` per taxonomy, ``review_needed`` False.
- **unmapped (AC 3)** — a terminal ``disposition_raw`` NOT in the table -> code
  ``unknown`` + one ``disposition_not_mapped`` review item (medium). ``unknown``
  is never public-eligible (enforced against the taxonomy at construction).

Codes come from ``@pca/taxonomy`` taxonomy.json ONLY, and ``taxonomy_version`` is
read from that file and stamped on every result. 22.1's frozen
``OutcomeNormalizationResult`` cannot carry ``taxonomy_version`` nor represent the
unmapped -> ``unknown`` + review state (a matched method forbids review; an
unmatched method forbids carrying a code), and 22.1 is read-only, so this module
returns its own purpose-built :class:`OutcomeMappingResult` (approved at plan
review, Q2). Phase 23 owns reconciling this to ``fact.*`` persistence.

The mapper is PURE and DB-free (mirrors 22.2/22.3): it operates over an injected
:class:`TaxonomySnapshot`. A thin loader (:func:`load_taxonomy_snapshot`) reads the
committed-at-build taxonomy.json at the CLI/orchestration boundary and hands the
snapshot here, keeping the mapper tier-1 synthetic-testable. Review items are
built via the canonical 22.1 :func:`build_review_item` only. Raw disposition
values are permitted inside results and review-item payloads (internal-only
tables) but NEVER in console / log output.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pipeline.fact_review_vocab import (
    DISPOSITION_NOT_MAPPED,
    SEVERITY_MEDIUM,
    UNMAPPED_DISPOSITION,
)
from pipeline.normalization.review_items import build_review_item

# The taxonomy `unknown` outcome code (non-public). Not a member of the exact-
# match table: it is the sink for a terminal disposition that maps to nothing.
OUTCOME_UNKNOWN = "unknown"

# Entity tag carried on the review item (parallel to 22.2 "charge" / 22.3 "judge").
ENTITY_DISPOSITION = "disposition"

# --- Held-for-court carve-out (Task 29.3, Mechanism A — planning-chat pinned) --
# A "Held for Court" disposition is a non-terminal MC bind-over — the case
# continues on a CP docket — so it is NOT an outcome. These charges take the
# held arm (`map()` returns None: no fact, no review item), exactly like a null
# disposition. Keys are BYTE-EXACT to the corpus-evidenced variant scan (recon
# 29.3 stage 1; the 18.2/22.4 repair-table precedent: exact-match on captured
# state, never pattern matching). This set is the SINGLE authority on which
# disposition values are held forms — the fact builder and the review-queue
# closure tool consume it; nothing re-lists the five forms.
#
# Fail-safe for unseen future variants (DESIGNED behavior, not a gap): a held
# form not listed here arrives as a terminal unmapped value -> `unknown`
# (never public-eligible) + one `unmapped_disposition` review item. It cannot
# reach public aggregates; adding it here is a planning-chat adjudication.
#
# "Held for Court - Hearsay" is the sixth corpus-evidenced entry, surfaced by
# the 29.3 intake scan gate (2 charges, one MC docket, disposed-with-no-date,
# zero sentence components — structurally identical to the original five) and
# adjudicated in planning chat (C2, Option 1) exactly per that process.
HELD_FOR_COURT_DISPOSITIONS: frozenset[str] = frozenset(
    {
        "Held for Court",
        "IGJ - Held for Court",
        "HP - Held for Court",
        "Held for Court IC",
        "GJ - Held for Court",
        "Held for Court - Hearsay",
    }
)

# --- The APPROVED exact-match table (Task 22.4 map-approval gate) -------------
# disposition_raw string -> outcome taxonomy code. Keys are BYTE-EXACT to the
# Part A distinct-value report over the corpus; every value is a real taxonomy
# outcome code (verified at construction against the injected TaxonomySnapshot).
# Task 32.3 added 17 keys (dismissal-family kin, Nolo Contendere/Probation,
# Mistrial, IC-suffix variants, Charge Changed (Lower Court)) per the
# 2026-07-16 directional rulings, table approved in planning chat 2026-07-17;
# keys byte-exact to the 32.3 Stage-1 sweep. Contaminated/mangled strings
# (leading-char-loss, offense-text bleed, scheduling bleed, status-suffix) are
# NEVER map keys — they route to the Sprint 9 parser hardening batch.
# "Proceed to Court" is deliberately unmapped: non-terminal continuation shape,
# deferred to Sprint 9 (no-fact design question); the unmapped fail-safe keeps
# it non-public.
# These keys are standardized CPCMS disposition phrases — public state
# vocabulary, non-identifying (same class as the committed charge-description
# vocabulary); no raw docket text, docket numbers, or defendant data.
#
# AC-5 hygiene: the table carries ONLY the full "Transferred to Another
# Jurisdiction"; the truncated capture "Transferred to Another" is absent —
# the 18.2 Class E repair (16 rows) rewrites the truncated form to its full
# string before mapping, so a truncated key would be unreachable. A test asserts
# the truncated key's absence.
#
# NOTE (future parser-repair candidate, NOT this task): "Dismissed - Rule 600
# (Speedy" is a known mid-phrase parser truncation of "...(Speedy Trial)". It is
# mapped verbatim to `dismissed` here; the durable fix belongs in the parser's
# truncated-disposition repair table (same class as the 18.2 Transferred repair)
# and is logged to the worklog — the parser is out of scope for 22.4.
DISPOSITION_OUTCOME_MAP: dict[str, str] = {
    # guilty_plea — plea of guilty / no contest resulting in a conviction
    "Guilty Plea - Negotiated": "guilty_plea",
    "Guilty Plea - Non-Negotiated": "guilty_plea",
    "Guilty Plea - Negotiated IC": "guilty_plea",
    "Guilty Plea": "guilty_plea",
    "Nolo Contendere": "guilty_plea",
    "Guilty Plea - Non-Negotiated IC": "guilty_plea",
    "Guilty Plea IC": "guilty_plea",
    "Nolo Contendere/Probation": "guilty_plea",
    # guilty_verdict — found guilty after trial
    "Guilty": "guilty_verdict",
    "Guilty IC": "guilty_verdict",
    # dismissed — court ended the charge without a conviction
    "Nolle Prossed": "dismissed",
    "Quashed": "dismissed",
    "Dismissed - LOE": "dismissed",
    "Dismissed - Rule 600 (Speedy": "dismissed",
    "Dismissed": "dismissed",
    "Dismissed - LOP": "dismissed",
    "Dismissed - Rule 1013": "dismissed",
    "Dismissed - Rule 586": "dismissed",
    "Dismissed - Rule 546": "dismissed",
    "Dismissed - Abatement": "dismissed",
    "Dismissed - De Minimis": "dismissed",
    "Nolle Prossed IC": "dismissed",
    "Quashed IC": "dismissed",
    "Dismissed - Abatement IC": "dismissed",
    # acquittal — found not guilty after trial
    "Not Guilty": "acquittal",
    "Judgment of Acquittal": "acquittal",
    "Judgment of Acquittal IC": "acquittal",
    "Not Guilty IC": "acquittal",
    # ard — Accelerated Rehabilitative Disposition
    "ARD - County": "ard",
    # withdrawn — prosecution withdrew the charge
    "Withdrawn": "withdrawn",
    "Withdrawn IC": "withdrawn",
    # other — recorded disposition outside the defined categories. NOTE (Task
    # 29.3): "Held for Court" is deliberately ABSENT — a bind-over is not an
    # outcome; it takes the held arm via HELD_FOR_COURT_DISPOSITIONS above.
    # "Charge Changed (Lower Court)" is terminal-without-independent-outcome
    # (the Transferred shape), ruled into `other` at the 32.3 table gate.
    "Transferred to Another Jurisdiction": "other",
    "Mistrial - Hung Jury": "other",
    "Mistrial": "other",
    "Charge Changed (Lower Court)": "other",
}


# --- Taxonomy snapshot + loader (the DB/file boundary, kept off the mapper) ---
# taxonomy.json lives at this repo-relative path. It is a generated artifact
# (gitignored); `pnpm generate` builds it, and CI's Python job regenerates it
# before pytest, so it is present wherever the loader runs.
_TAXONOMY_RELPATH = ("packages", "taxonomy", "generated", "taxonomy.json")


@dataclass(frozen=True)
class TaxonomySnapshot:
    """An immutable view of the outcome taxonomy the mapper needs.

    ``taxonomy_version`` is stamped on every mapping result; ``public_by_code``
    maps each outcome code to its ``public`` flag (drives ``public_eligible`` and
    the construction-time code-membership check). Structural only — no raw data.
    """

    taxonomy_version: str
    public_by_code: Mapping[str, bool]

    def __post_init__(self) -> None:
        if not self.taxonomy_version:
            raise ValueError("taxonomy_version must be non-empty")
        if not self.public_by_code:
            raise ValueError("public_by_code must be non-empty")


def load_taxonomy_snapshot(path: Path | None = None) -> TaxonomySnapshot:
    """Load the outcome taxonomy from taxonomy.json (the file boundary).

    With ``path`` omitted, walks up from this module to find
    ``packages/taxonomy/generated/taxonomy.json``. Reads ``taxonomyVersion`` and
    the ``outcomeCategories`` ``code`` -> ``public`` map. Raises
    ``FileNotFoundError`` with a `pnpm generate` hint if the artifact is missing.
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
        for category in data["outcomeCategories"]
    }
    return TaxonomySnapshot(
        taxonomy_version=str(data["taxonomyVersion"]),
        public_by_code=public_by_code,
    )


# --- Held predicate (18.1, replicated verbatim — never treated as unmapped) ---
def charge_has_terminal_disposition(charge: Mapping[str, object]) -> bool:
    """Terminality predicate — replicates ``envelope._charge_has_disposition``.

    Introduced in Task 18.1: a charge carries a terminal outcome iff it has a
    ``disposition_raw``, a ``disposition_date``, or any sentence — the parser
    records those ONLY inside an event it gated as terminal (Final Disposition /
    ARD). Replicated here VERBATIM (that function is module-private) rather than
    imported across modules, so the mapper and coverage tool share one definition
    with no cross-module private coupling. A charge is HELD — no outcome fact, no
    review item (AC 4) — exactly when this returns False.
    """
    return (
        charge["disposition_raw"] is not None
        or charge["disposition_date"] is not None
        or bool(charge["sentences"])
    )


def is_held_charge(charge: Mapping[str, object]) -> bool:
    """True iff the charge ended the parse undisposed (the AC-4 held carve-out)."""
    return not charge_has_terminal_disposition(charge)


@dataclass(frozen=True)
class OutcomeMappingResult:
    """The result of mapping one terminal ``disposition_raw`` value.

    Purpose-built (not the frozen 22.1 ``OutcomeNormalizationResult``) so it can
    carry ``taxonomy_version`` and the unmapped -> ``unknown`` + review state:

    - ``raw_value`` — the disposition string that was mapped.
    - ``outcome_code`` — a real taxonomy outcome code (``unknown`` when unmapped).
    - ``taxonomy_version`` — stamped from taxonomy.json on EVERY result (AC 2).
    - ``public_eligible`` — the taxonomy ``public`` flag for ``outcome_code``
      (always False for ``unknown``).
    - ``mapped`` — True iff ``outcome_code`` came from the exact-match table;
      False for the unmapped -> ``unknown`` path.
    - ``review_needed`` — True iff unmapped (a ``disposition_not_mapped`` review
      item is warranted); False for a clean mapped result.

    The held carve-out produces NO result at all (:meth:`OutcomeMapper.map`
    returns ``None``), so a held charge never constructs one of these.
    """

    raw_value: str
    outcome_code: str
    taxonomy_version: str
    public_eligible: bool
    mapped: bool
    review_needed: bool

    def __post_init__(self) -> None:
        if not self.outcome_code:
            raise ValueError("outcome_code must be non-empty")
        if not self.taxonomy_version:
            raise ValueError("taxonomy_version must be non-empty")
        # An unmapped result is `unknown` + review; a mapped result is neither.
        if self.mapped and self.review_needed:
            raise ValueError("a mapped result must not need review")
        if not self.mapped and self.outcome_code != OUTCOME_UNKNOWN:
            raise ValueError("an unmapped result must carry the `unknown` code")


class OutcomeMapper:
    """Map ``disposition_raw`` -> outcome code against the exact-match table.

    Pure and DB-free. The lookup table and taxonomy are fixed at construction;
    :meth:`map` is a read-only exact-match decision over them.
    """

    def __init__(
        self,
        taxonomy: TaxonomySnapshot,
        mapping: Mapping[str, str] = DISPOSITION_OUTCOME_MAP,
    ) -> None:
        # Construction-time check: every mapped code (and the `unknown` sink) is a
        # real taxonomy outcome code, and `unknown` is non-public so it can never
        # be public-eligible. Codes come from the taxonomy ONLY.
        used_codes = set(mapping.values()) | {OUTCOME_UNKNOWN}
        for code in sorted(used_codes):
            if code not in taxonomy.public_by_code:
                raise ValueError(f"outcome code not in taxonomy: {code!r}")
        if taxonomy.public_by_code.get(OUTCOME_UNKNOWN) is not False:
            raise ValueError(
                "taxonomy must define `unknown` as non-public (never public-eligible)"
            )
        self._version = taxonomy.taxonomy_version
        self._public = dict(taxonomy.public_by_code)
        self._map = dict(mapping)

    def map(self, disposition_raw: str | None) -> OutcomeMappingResult | None:
        """Map one ``disposition_raw`` value; return a result or ``None`` (held).

        Arms:

        1. held    — ``disposition_raw`` IS NULL (AC 4; the 18.1 held carve-out
           at the disposition grain) OR a byte-exact
           ``HELD_FOR_COURT_DISPOSITIONS`` member (Task 29.3: a non-terminal MC
           bind-over is not an outcome) -> ``None``; no fact, no review.
        2. mapped  — exact-match hit in the table -> its outcome code.
        3. unmapped — a terminal value not in the table -> ``unknown`` + review.

        Exact-match only: the raw string is looked up verbatim, never folded.
        """
        # AC 4 held carve-out: a null disposition is an undisposed (held) charge —
        # no terminal disposition to map, so no fact and no review item. Guarding
        # on `is None` (not truthiness) mirrors the 18.1 predicate, which keys on
        # `disposition_raw is not None`.
        if disposition_raw is None:
            return None

        # Task 29.3 held-for-court carve-out: a recorded bind-over form is
        # non-terminal — same held arm as NULL (no fact, no review item).
        # Byte-exact membership only; an unlisted future variant deliberately
        # falls through to the unmapped -> `unknown` + review fail-safe below.
        if disposition_raw in HELD_FOR_COURT_DISPOSITIONS:
            return None

        code = self._map.get(disposition_raw)
        if code is not None:
            return OutcomeMappingResult(
                raw_value=disposition_raw,
                outcome_code=code,
                taxonomy_version=self._version,
                public_eligible=self._public[code],
                mapped=True,
                review_needed=False,
            )

        # Unmapped terminal disposition -> unknown + review (AC 3). `unknown` is
        # non-public, so public_eligible is False by taxonomy.
        return OutcomeMappingResult(
            raw_value=disposition_raw,
            outcome_code=OUTCOME_UNKNOWN,
            taxonomy_version=self._version,
            public_eligible=self._public[OUTCOME_UNKNOWN],
            mapped=False,
            review_needed=True,
        )


def build_outcome_review_item(
    result: OutcomeMappingResult | None,
    *,
    source_document_id: str,
    charge_sequence: int | str,
    parsed_docket_id: str | None = None,
    parsed_charge_id: str | None = None,
) -> dict[str, object] | None:
    """Build a ``review.queue_items`` payload for an outcome result, or ``None``.

    Returns ``None`` for a held charge (``result is None``) and for a clean mapped
    result (``review_needed`` False) — only the unmapped -> ``unknown`` path
    produces a review item. Otherwise delegates to the 22.1
    :func:`build_review_item` with the pinned mapping:

    - ``item_type``  = ``unmapped_disposition``
    - ``reason_code`` = ``disposition_not_mapped``
    - ``severity``   = ``medium``

    The dedup key is derived from ``source_document_id``, ``item_type`` and the
    charge-grain locator ``(str(charge_sequence),)`` only; ``parsed_docket_id`` /
    ``parsed_charge_id`` are carried as re-anchoring payload but by construction
    NEVER enter the key.
    """
    if result is None or not result.review_needed:
        return None

    return build_review_item(
        source_document_id=source_document_id,
        item_type=UNMAPPED_DISPOSITION,
        severity=SEVERITY_MEDIUM,
        reason_code=DISPOSITION_NOT_MAPPED,
        locator=(str(charge_sequence),),
        parsed_docket_id=parsed_docket_id,
        parsed_charge_id=parsed_charge_id,
        entity_type=ENTITY_DISPOSITION,
        raw_value=result.raw_value,
    )
