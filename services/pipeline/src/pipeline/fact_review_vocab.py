"""Controlled vocabularies for the fact + review tables (Task 21.2).

This is the SINGLE source of truth for every controlled vocabulary that the
``fact.*`` and ``review.queue_items`` tables store as plain text. No other
module defines these strings; the 22.x/23.x writers import them from here. Each
set is closed, and additions require plan-level approval — do not invent members
in code (the warning-code precedent, ``warning_codes.py``).

The DB stores each vocabulary as ``text`` (no FK, no enum type): the taxonomy
and these vocabularies are package-only through the current sprint, exactly like
the Sprint 2 analytics tables. Immutability, nullability, and defaults live in
the migrations; membership lives here.

Five vocabularies are defined:

1. ``REVIEW_ITEM_TYPES`` — the kind of thing a ``review.queue_items`` row flags
   (Sprint 5 plan 23.4). One member per review path the 22.x/23.x work emits.
2. ``REVIEW_SEVERITIES`` — triage priority for a review item: ``high`` /
   ``medium`` / ``low``. Deliberately NOT ``blocking`` / ``warning`` / ``info``:
   ``blocking`` would collide with the ``blocking_warning`` eligibility reason
   code below, and ``warning`` would collide with the parser warning-code
   severity vocabulary (``warning_codes.SEVERITY``). Triage priority must not
   share words with either vocabulary, so a neutral high/medium/low scale is
   used.
3. ``REVIEW_ITEM_STATUSES`` — the triage lifecycle Sprint 6 drives; new items
   default to ``open`` (``REVIEW_ITEM_STATUS_DEFAULT``).
4. ``FACT_BUILD_RUN_STATUSES`` — the ``fact.fact_build_runs`` lifecycle,
   mirroring the analytics ``aggregate_runs`` status set.
5. ``ELIGIBILITY_REASON_CODES`` — machine-readable reasons a fact is ineligible,
   stored in ``fact.*.ineligibility_reason_codes`` (Sprint 5 plan 23.2/23.3).

Dedup-key composition (documented here; implemented by the 22.1 helpers)
------------------------------------------------------------------------
``review.queue_items.dedup_key`` is a NOT NULL text column with a DB UNIQUE
constraint. It is composed deterministically from STABLE identifiers only, so
that re-running the fact build is idempotent on the review queue even across
parsed reloads (which re-mint every ``parsed.*`` UUID). The composition is::

    dedup_key = "\\x1f".join([source_document_id, item_type, *locator])

where the parts are:

- ``source_document_id`` — the ``raw.source_documents`` UUID. This is the one
  UUID that is stable across parsed reloads (review items are FK-anchored to the
  source document, not to parsed rows), so it is the safe anchor.
- ``item_type`` — one of ``REVIEW_ITEM_TYPES``.
- ``locator`` — zero or more structural locator parts drawn ONLY from stable
  structural identifiers, chosen by the item's grain:
    * charge-scoped items  -> [charge_sequence]
    * sentence-scoped items -> [charge_sequence, sentence_component_order]
    * judge / entity items -> [entity_type] (and field where applicable)
    * docket-scoped items  -> [] (empty locator)

The separator is the ASCII unit separator (``\\x1f``), which cannot appear in
any of the structural parts. The key incorporates NO ``parsed.*`` UUID by
construction. ``\\x1f`` and the composition itself are documented here only; the
22.1 review-item helpers implement the builder and the DB stores the result.
"""

from __future__ import annotations

# --- 1. Review item types (Sprint 5 plan 23.4; additions need approval) -----
UNMAPPED_CHARGE = "unmapped_charge"
AMBIGUOUS_CHARGE = "ambiguous_charge"
UNMAPPED_JUDGE = "unmapped_judge"
AMBIGUOUS_JUDGE = "ambiguous_judge"
UNMAPPED_DISPOSITION = "unmapped_disposition"
UNMAPPED_SENTENCING_COMPONENT = "unmapped_sentencing_component"
AMBIGUOUS_SENTENCING_COMPONENT = "ambiguous_sentencing_component"
MONEY_UNPARSEABLE = "money_unparseable"
DURATION_UNPARSEABLE = "duration_unparseable"
AMBIGUOUS_JUDGE_ATTRIBUTION = "ambiguous_judge_attribution"
MISSING_DISPOSITION_DATE = "missing_disposition_date"
SENTINEL_COLLISION = "sentinel_collision"
# Task 23.4 addition (plan-approved): a sentence component that carries an ADDITIVE
# restitution / community-service category beyond its base (``len(categories) > 1``).
# The 1:1 ``fact.charge_sentences`` schema stores only the base category, so the
# additive would be silently lost; 23.3 forces the fact's ``review_needed`` and 23.4
# surfaces the additive to the queue under this type. It is neither unmapped nor
# ambiguous (both mappings are valid) — reusing those types would corrupt Sprint 6
# triage counts, so it gets its own member (the ONLY 23.4 vocabulary change).
ADDITIVE_SENTENCING_CATEGORY = "additive_sentencing_category"
# Task 23.5 addition (plan-approved): a held MC docket's cross-court reference that
# the linker could not turn into a resolvable target — either the
# ``cross_court_dockets`` string yields no bounded UJS docket number (``malformed``),
# or the parsed target docket number matches >=2 ``parsed.dockets`` rows so the
# target lookup is ambiguous (``ambiguous_target``). Both sub-cases share this one
# type and are distinguished by ``candidate_context["subcase"]`` (23.5 RF3), never by
# separate reason codes. Its ``reason_code`` is the generic ``REVIEW_NEEDED``:
# linkage is informational (AC4) and MUST NOT introduce a concept into
# ``ELIGIBILITY_REASON_CODES``, which would soften the eligibility boundary.
UNRESOLVABLE_CROSS_COURT_REFERENCE = "unresolvable_cross_court_reference"
# Task COL-4a addition (plan-approved): a superseding parse (same docket number +
# court, new source hash) that regressed against the parse it replaced — fewer
# charges, or a previously disposed charge now undisposed/absent. The parse itself
# is valid (nothing is unmapped or ambiguous), so no existing type fits. The two
# sub-cases (charge shrink / disposition loss) share this one type and are
# distinguished by ``candidate_context`` (the 23.5 sub-case precedent). Its
# ``reason_code`` is the generic ``REVIEW_NEEDED`` (also the 23.5 precedent):
# the guard flags, never blocks, and MUST NOT introduce a concept into
# ``ELIGIBILITY_REASON_CODES``. Anchored to the NEW source document (the
# actionable object is the new parse), docket-scoped (empty locator).
SUPERSESSION_REGRESSION = "supersession_regression"

REVIEW_ITEM_TYPES: frozenset[str] = frozenset(
    {
        UNMAPPED_CHARGE,
        AMBIGUOUS_CHARGE,
        UNMAPPED_JUDGE,
        AMBIGUOUS_JUDGE,
        UNMAPPED_DISPOSITION,
        UNMAPPED_SENTENCING_COMPONENT,
        AMBIGUOUS_SENTENCING_COMPONENT,
        MONEY_UNPARSEABLE,
        DURATION_UNPARSEABLE,
        AMBIGUOUS_JUDGE_ATTRIBUTION,
        MISSING_DISPOSITION_DATE,
        SENTINEL_COLLISION,
        ADDITIVE_SENTENCING_CATEGORY,
        UNRESOLVABLE_CROSS_COURT_REFERENCE,
        SUPERSESSION_REGRESSION,
    }
)

# --- 2. Review severities (triage priority; neutral high/medium/low) --------
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

REVIEW_SEVERITIES: frozenset[str] = frozenset(
    {SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW}
)

# --- 3. Review item statuses (Sprint 6 triage lifecycle; default open) ------
STATUS_OPEN = "open"
STATUS_IN_REVIEW = "in_review"
STATUS_RESOLVED = "resolved"
STATUS_DISMISSED = "dismissed"
# Task COL-4a addition (plan-approved): terminal close-out for items whose parsed
# graph was replaced by a docket supersession (COL-4a loader arm). Distinct from
# ``dismissed`` so mechanical closure is never conflated with human dismissal;
# triage state never transfers to the superseding document's items (its next fact
# build regenerates them fresh under new dedup keys). Set by the loader on every
# NON-terminal item (open / in_review) anchored to the superseded source document;
# resolved / dismissed items are already terminal and stay untouched.
STATUS_SUPERSEDED = "superseded"

REVIEW_ITEM_STATUSES: frozenset[str] = frozenset(
    {
        STATUS_OPEN,
        STATUS_IN_REVIEW,
        STATUS_RESOLVED,
        STATUS_DISMISSED,
        STATUS_SUPERSEDED,
    }
)

# The DB default for review.queue_items.status.
REVIEW_ITEM_STATUS_DEFAULT = STATUS_OPEN

# --- 4. Fact-build-run statuses (mirrors analytics aggregate_runs) ----------
RUN_IN_PROGRESS = "in_progress"
RUN_COMPLETED = "completed"
RUN_FAILED = "failed"

FACT_BUILD_RUN_STATUSES: frozenset[str] = frozenset(
    {RUN_IN_PROGRESS, RUN_COMPLETED, RUN_FAILED}
)

# --- 5. Eligibility reason codes (Sprint 5 plan 23.2/23.3) ------------------
DISPOSITION_DATE_MISSING = "disposition_date_missing"
DISPOSITION_DATE_BEFORE_MVP_WINDOW = "disposition_date_before_mvp_window"
SENTENCE_DATE_MISSING = "sentence_date_missing"
SENTENCE_DATE_BEFORE_MVP_WINDOW = "sentence_date_before_mvp_window"
CHARGE_NOT_NORMALIZED = "charge_not_normalized"
JUDGE_NOT_NORMALIZED = "judge_not_normalized"
DISPOSITION_NOT_MAPPED = "disposition_not_mapped"
OUTCOME_CATEGORY_NOT_PUBLIC = "outcome_category_not_public"
SENTENCING_CATEGORY_NOT_PUBLIC = "sentencing_category_not_public"
SENTENCING_COMPONENT_NOT_NORMALIZED = "sentencing_component_not_normalized"
REVIEW_NEEDED = "review_needed"
BLOCKING_WARNING = "blocking_warning"
JUDGE_NOT_ATTRIBUTED = "judge_not_attributed"
PARENT_OUTCOME_INELIGIBLE = "parent_outcome_ineligible"
# Task 22.5 additions: a monetary sentencing component whose amount is present but
# unresolvable (zero-parseable-with-currency, or >=2 distinct amounts — the money
# is unreadable, but the category mapping still stands); and a sentence-duration
# figure the parser flagged UNPARSEABLE_DURATION (helper lands here; Phase 23 wires
# the envelope warning to it — the mapper never re-parses durations).
MONEY_AMOUNT_UNPARSEABLE = "money_amount_unparseable"
SENTENCE_DURATION_UNPARSEABLE = "sentence_duration_unparseable"

ELIGIBILITY_REASON_CODES: frozenset[str] = frozenset(
    {
        DISPOSITION_DATE_MISSING,
        DISPOSITION_DATE_BEFORE_MVP_WINDOW,
        SENTENCE_DATE_MISSING,
        SENTENCE_DATE_BEFORE_MVP_WINDOW,
        CHARGE_NOT_NORMALIZED,
        JUDGE_NOT_NORMALIZED,
        DISPOSITION_NOT_MAPPED,
        OUTCOME_CATEGORY_NOT_PUBLIC,
        SENTENCING_CATEGORY_NOT_PUBLIC,
        SENTENCING_COMPONENT_NOT_NORMALIZED,
        REVIEW_NEEDED,
        BLOCKING_WARNING,
        JUDGE_NOT_ATTRIBUTED,
        PARENT_OUTCOME_INELIGIBLE,
        MONEY_AMOUNT_UNPARSEABLE,
        SENTENCE_DURATION_UNPARSEABLE,
    }
)
