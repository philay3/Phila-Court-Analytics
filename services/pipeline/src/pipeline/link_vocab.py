"""Controlled vocabularies for ``parsed.docket_links`` (Task 23.5).

The single source of truth for the two ``parsed.docket_links`` controlled
vocabularies. It is deliberately separate from ``fact_review_vocab.py`` (whose
documented scope is the ``fact.*`` and ``review.queue_items`` tables): a link row
is a parsed-layer artifact, not a fact/review row, so its vocabularies live with
the table they belong to. Each set is closed; additions require plan-level
approval (the ``warning_codes.py`` / ``fact_review_vocab.py`` precedent) — do not
invent members in code.

The DB stores each vocabulary as ``text`` (no FK, no enum type), exactly like the
parser/record vocabularies and the ``fact_review_vocab`` sets: membership lives
here, immutability/nullability/defaults live in the migration.

Two vocabularies are defined:

1. ``LINK_TYPES`` — the kind of cross-court relationship a ``parsed.docket_links``
   row records. This sprint the sole member is ``held_for_court`` (Sprint 5 plan
   23.5 AC1 minimum): an MC held-for-court docket referencing the CP docket the
   case transfers to. NOTE on the held signal: §6.7's null-disposition / event-key
   held model is a CP-side phenomenon (``NON_TERMINAL_CASE``). MC's held-for-court
   is a DISTINCT signal — a DISPOSED charge (``disposition_raw`` = a
   "Held for Court"-class value) that carries a cross-court reference. The linker
   therefore keys off MC dockets carrying a ``cross_court_dockets`` capture, NOT
   off a null-disposition filter (which would exclude every MC held docket).
2. ``LINK_EVIDENCE_SOURCES`` — which already-parsed field the link was read from.
   ``cross_court_dockets`` is the ``parsed.dockets.cross_court_dockets`` capture
   and is the SOLE carrier of held-for-court linkage in the loaded corpus.
   ``related_cases`` is a RESERVED member (AC1 names both evidence sources) with
   ZERO held-for-court overlap in the corpus — ``parsed.related_cases`` carries
   sibling / co-defendant MC associations, and across all MC dockets with a
   cross-court CP reference that CP docket appears in ``related_cases`` zero times
   (23.5 recon R3). It therefore produces ZERO links this task; every link written
   stamps ``evidence_source = cross_court_dockets``.
"""

from __future__ import annotations

# --- 1. Link types (Sprint 5 plan 23.5 AC1; additions need approval) --------
HELD_FOR_COURT = "held_for_court"

LINK_TYPES: frozenset[str] = frozenset({HELD_FOR_COURT})

# --- 2. Link evidence sources (Sprint 5 plan 23.5 AC1) ----------------------
# cross_court_dockets: the sole carrier of held-for-court linkage this sprint.
CROSS_COURT_DOCKETS = "cross_court_dockets"
# related_cases: reserved vocab member, zero held-for-court overlap in the corpus
# (23.5 recon R3) — produces no links this task; kept because AC1 names it.
RELATED_CASES = "related_cases"

LINK_EVIDENCE_SOURCES: frozenset[str] = frozenset({CROSS_COURT_DOCKETS, RELATED_CASES})
