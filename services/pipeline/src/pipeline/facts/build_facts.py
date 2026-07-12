"""Outcome-fact build orchestration + ``pipeline build-facts`` (Task 23.2).

The first consumer that lands facts in the database. Reads the loaded ``parsed.*``
corpus, applies the 22.2 charge matcher, the 22.4 outcome mapper, and the 23.1
judge-attribution resolver (all imported UNCHANGED), and writes one
``fact.charge_outcomes`` row per DISPOSED charge (``disposition_raw`` non-null)
under a single new ``fact.fact_build_runs`` run. Held charges (null
``disposition_raw``) produce NO fact and are counted; failed-parse (quarantine)
envelopes contribute zero charges structurally (the 21.3 loader writes no
``parsed.*`` rows for them), so they produce zero facts.

Run lifecycle (append-only history; a completed run is a full consistent set; a
failed build leaves no partial facts):

  1. Resolve the corpus provenance version BEFORE any write — the single distinct
     ``(record_parser_version, envelope_parser_version)`` across ``parsed.dockets``.
     A mixed-version corpus (or an empty one) is a STOP, not a guess.
  2. Insert the run row (``in_progress``) and commit it — the run exists in
     history regardless of what follows.
  3. In ONE transaction: bulk-insert every outcome fact, then flip the run to
     ``completed`` with its counts. Commit atomically.
  4. On any failure in step 3: roll back (zero facts persist), then mark the run
     ``failed`` in its own transaction.

Facts carry NO defendant identity (``fact.charge_outcomes`` has no defendant
column; ``defendant_hash`` is ``parsed.*`` only), so this build needs
``DATABASE_URL`` but NEVER ``DEFENDANT_HASH_SALT``. ``DATABASE_URL`` is read at the
CLI boundary only (21.3 pattern) and never printed or logged. Console/log output
is counts, fixed reason/outcome codes, and hash-prefix ids only — never raw
docket text or defendant data.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from pipeline.envelope import _is_unparseable_duration
from pipeline.fact_review_vocab import (
    ADDITIVE_SENTENCING_CATEGORY,
    DISPOSITION_DATE_MISSING,
    ELIGIBILITY_REASON_CODES,
    JUDGE_NOT_NORMALIZED,
    MISSING_DISPOSITION_DATE,
    REVIEW_NEEDED,
    RUN_COMPLETED,
    RUN_FAILED,
    RUN_IN_PROGRESS,
    SENTINEL_COLLISION,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
)
from pipeline.facts.docket_links import collect_docket_links, insert_docket_links
from pipeline.facts.judge_attribution import build_docket_context, resolve_charge
from pipeline.facts.outcome_facts import (
    MVP_WINDOW_START,
    build_outcome_fact_row,
    evaluate_outcome_eligibility,
    insert_outcome_facts,
)
from pipeline.facts.sentence_facts import (
    build_sentence_fact_row,
    derive_component_match_method,
    evaluate_sentence_eligibility,
    insert_sentence_facts,
    parent_attributed,
)
from pipeline.normalization.charge_matcher import (
    ChargeMatcher,
    build_charge_review_item,
)
from pipeline.normalization.charge_roster_loader import load_charge_roster
from pipeline.normalization.judge_matcher import (
    ENTITY_JUDGE,
    ROLE_ASSIGNED,
    ROLE_DISPOSITION,
    JudgeMatcher,
    build_judge_review_item,
)
from pipeline.normalization.judge_roster_loader import load_judge_roster
from pipeline.normalization.outcome_mapper import (
    OutcomeMapper,
    build_outcome_review_item,
    load_taxonomy_snapshot,
)
from pipeline.normalization.review_items import build_review_item
from pipeline.normalization.sentencing_mapper import (
    ENTITY_SENTENCING,
    SentencingMapper,
    build_duration_review_item,
    build_sentencing_review_items,
    load_sentencing_taxonomy,
)
from pipeline.warning_codes import (
    MISSING_DISPOSITION_DATE as WARN_MISSING_DISPOSITION_DATE,
)
from pipeline.warning_codes import (
    SENTINEL_COLLISION as WARN_SENTINEL_COLLISION,
)
from pipeline.warning_codes import (
    UNPARSEABLE_DURATION,
)

logger = logging.getLogger("pipeline.facts.build_facts")

# A short, hygiene-safe note stamped on the run recording the roster/taxonomy
# provenance (schema identifiers + version only; no data).
_ROSTER_SNAPSHOT_NOTE = (
    "active ref.normalized_charges/ref.normalized_judges snapshot; "
    "taxonomy.json outcome categories"
)


class MixedCorpusVersionError(RuntimeError):
    """The parsed corpus carries more than one parser-version pair (STOP)."""


class EmptyCorpusError(RuntimeError):
    """No parsed dockets to build facts from (STOP)."""


class TaxonomyVersionMismatchError(RuntimeError):
    """The outcome and sentencing taxonomy snapshots disagree on version (STOP)."""


class SentenceIntegrityError(RuntimeError):
    """A sentence-layer integrity invariant failed (STOP; PD8 / duration).

    Raised for: a sentence component on a held (null-disposition) charge; a
    duration-unparseable count that disagrees with the envelope's own
    UNPARSEABLE_DURATION emission (predicate drift); a disposed-charge sentence
    with no parent outcome fact in the run; or a 1:1 count mismatch. Every case is
    stop-and-report, never self-adjudicated. (SD 15 divergence is a SOFT REPORT,
    not a stop — see :func:`_prepare_sentences`.)
    """


def _resolve_corpus_version(conn: psycopg.Connection) -> tuple[int, int]:
    """The single ``(record_parser_version, envelope_parser_version)`` in the corpus.

    A mixed-version corpus is a STOP (never silently stamp one version over a
    heterogeneous set); an empty corpus is a STOP (nothing to build).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT record_parser_version, envelope_parser_version "
            "FROM parsed.dockets"
        )
        pairs = cur.fetchall()
    if not pairs:
        raise EmptyCorpusError("no parsed.dockets rows; nothing to build")
    if len(pairs) > 1:
        raise MixedCorpusVersionError(
            f"parsed corpus carries {len(pairs)} distinct parser-version pairs; "
            "refusing to stamp one on the run"
        )
    record_version, envelope_version = pairs[0]
    return int(record_version), int(envelope_version)


def _load_charge_warning_codes(
    conn: psycopg.Connection,
) -> dict[tuple[str, int], list[str]]:
    """Charge-grain parser warning codes keyed by ``(docket_id, charge_sequence)``."""
    codes: dict[tuple[str, int], list[str]] = {}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT docket_id, charge_sequence, code FROM parsed.warnings "
            "WHERE charge_sequence IS NOT NULL"
        )
        for docket_id, charge_sequence, code in cur.fetchall():
            codes.setdefault((str(docket_id), int(charge_sequence)), []).append(code)
    return codes


def _load_dockets(conn: psycopg.Connection) -> list[dict[str, object]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, source_document_id, assigned_judge_raw FROM parsed.dockets"
        )
        return list(cur.fetchall())


def _load_charges_by_docket(
    conn: psycopg.Connection,
) -> dict[str, list[dict[str, object]]]:
    by_docket: dict[str, list[dict[str, object]]] = {}
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, docket_id, sequence, statute, offense, disposition_raw, "
            "disposition_date, disposition_judge_raw FROM parsed.charges"
        )
        for charge in cur.fetchall():
            by_docket.setdefault(str(charge["docket_id"]), []).append(charge)
    return by_docket


def _empty_reason_counts() -> dict[str, int]:
    """A stable, zero-initialized reason tally over the full committed vocabulary."""
    return {code: 0 for code in sorted(ELIGIBILITY_REASON_CODES)}


def _collect_outcome_rows(
    conn: psycopg.Connection,
    run_id: str,
    *,
    charge_matcher: ChargeMatcher,
    judge_matcher: JudgeMatcher,
    mapper: OutcomeMapper,
    taxonomy_version: str,
) -> tuple[list[dict[str, object]], dict[str, object], list[dict[str, object]]]:
    """Read the corpus and build every outcome-fact row (no writes here).

    Returns ``(rows, counts, review_items)``. One row per disposed charge; held
    charges are counted, never rowed. ``counts`` carries the run-report tallies used
    for the completion reconciliation (facts_written + held_skipped ==
    charges_processed; the outcome-code split equals the 22.4 mapper split over the
    same corpus). ``review_items`` are ``review.queue_items`` payloads built via the
    22.1 helpers (Task 23.4) for the charge / judge / outcome / attribution review
    paths this loop already computes — the 22.x/23.1 modules are consumed unchanged.
    """
    charge_warnings = _load_charge_warning_codes(conn)
    dockets = _load_dockets(conn)
    charges_by_docket = _load_charges_by_docket(conn)

    rows: list[dict[str, object]] = []
    review_items: list[dict[str, object]] = []
    charges_processed = 0
    held_skipped = 0
    mvp_eligible = public_eligible = judge_specific_eligible = 0
    review_needed_count = 0
    outcome_split: Counter[str] = Counter()
    reason_counts = _empty_reason_counts()

    for docket in dockets:
        docket_id = str(docket["id"])
        source_document_id = str(docket["source_document_id"])
        charges = charges_by_docket.get(docket_id, [])

        # The 23.1 docket context is derived ONCE per docket over ALL its charges.
        context_charges = [
            {
                "sequence": charge["sequence"],
                "disposition_judge_raw": charge["disposition_judge_raw"],
                "warning_codes": charge_warnings.get(
                    (docket_id, int(charge["sequence"])), []
                ),
            }
            for charge in charges
        ]
        context = build_docket_context(
            {
                "assigned_judge_raw": docket["assigned_judge_raw"],
                "charges": context_charges,
            },
            judge_matcher,
        )

        # Docket-grain review path: the assigned judge (22.3 normalization). Built
        # once per docket; None when absent or a clean match.
        assigned_judge_raw = docket["assigned_judge_raw"]
        assigned_item = build_judge_review_item(
            judge_matcher.match(
                assigned_judge_raw
                if assigned_judge_raw is None
                else str(assigned_judge_raw)
            ),
            source_document_id=source_document_id,
            role=ROLE_ASSIGNED,
            parsed_docket_id=docket_id,
        )
        if assigned_item is not None:
            review_items.append(assigned_item)

        for charge in charges:
            charges_processed += 1
            # Fact-creation domain: exactly one outcome fact per DISPOSED charge.
            # A null disposition_raw is a held charge -> no fact, no row (the 22.4
            # mapper returns None for it).
            outcome_result = mapper.map(charge["disposition_raw"])
            if outcome_result is None:
                held_skipped += 1
                continue

            sequence = int(charge["sequence"])
            charge_codes = charge_warnings.get((docket_id, sequence), [])

            charge_result = charge_matcher.match(
                statute=charge["statute"], offense=charge["offense"]
            )
            attribution = resolve_charge(
                {
                    "sequence": charge["sequence"],
                    "disposition_judge_raw": charge["disposition_judge_raw"],
                    "warning_codes": charge_codes,
                },
                context,
                judge_matcher,
                source_document_id=source_document_id,
                parsed_docket_id=docket_id,
                parsed_charge_id=str(charge["id"]),
            )

            # Charge-grain review paths (Task 23.4): charge normalization (22.2),
            # disposition-judge normalization (22.3), outcome mapping (22.4), and the
            # 23.1 ambiguous-attribution descriptor. Each helper returns None / no
            # descriptor for a clean result; only real signals reach the queue.
            charge_id = str(charge["id"])
            disposition_judge_raw = charge["disposition_judge_raw"]
            candidate_items = [
                build_charge_review_item(
                    charge_result,
                    source_document_id=source_document_id,
                    charge_sequence=sequence,
                    parsed_docket_id=docket_id,
                    parsed_charge_id=charge_id,
                ),
                build_judge_review_item(
                    judge_matcher.match(
                        disposition_judge_raw
                        if disposition_judge_raw is None
                        else str(disposition_judge_raw)
                    ),
                    source_document_id=source_document_id,
                    role=ROLE_DISPOSITION,
                    charge_sequence=sequence,
                    parsed_docket_id=docket_id,
                    parsed_charge_id=charge_id,
                ),
                build_outcome_review_item(
                    outcome_result,
                    source_document_id=source_document_id,
                    charge_sequence=sequence,
                    parsed_docket_id=docket_id,
                    parsed_charge_id=charge_id,
                ),
                attribution.review_descriptor,
            ]
            review_items.extend(
                dict(item) for item in candidate_items if item is not None
            )

            disposition_date = charge["disposition_date"]
            if disposition_date is not None and not isinstance(disposition_date, date):
                disposition_date = date.fromisoformat(str(disposition_date))

            eligibility = evaluate_outcome_eligibility(
                disposition_date=disposition_date,
                charge_result=charge_result,
                outcome_result=outcome_result,
                attribution=attribution,
                charge_warning_codes=charge_codes,
            )

            rows.append(
                build_outcome_fact_row(
                    build_run_id=run_id,
                    parsed_charge_id=str(charge["id"]),
                    parsed_docket_id=docket_id,
                    disposition_date=disposition_date,
                    charge_result=charge_result,
                    outcome_result=outcome_result,
                    attribution=attribution,
                    eligibility=eligibility,
                    taxonomy_version=taxonomy_version,
                )
            )

            outcome_split[outcome_result.outcome_code] += 1
            mvp_eligible += int(eligibility.mvp_eligible)
            public_eligible += int(eligibility.public_eligible)
            judge_specific_eligible += int(eligibility.judge_specific_eligible)
            review_needed_count += int(eligibility.review_needed)
            for code in eligibility.ineligibility_reason_codes:
                reason_counts[code] += 1

    counts: dict[str, object] = {
        "charges_processed": charges_processed,
        "facts_written": len(rows),
        "held_skipped": held_skipped,
        "mvp_eligible": mvp_eligible,
        "public_eligible": public_eligible,
        "judge_specific_eligible": judge_specific_eligible,
        "review_needed": review_needed_count,
        "outcome_code_split": dict(sorted(outcome_split.items())),
        "ineligible_by_reason": reason_counts,
    }
    return rows, counts, review_items


def _to_date(value: object) -> date | None:
    """Coerce a DB date value to ``date`` (psycopg returns ``date``; be defensive)."""
    if value is None or isinstance(value, date):
        return value  # type: ignore[return-value]
    return date.fromisoformat(str(value))


def _dur_view(sentence: dict[str, object]) -> dict[str, object]:
    """The four fields the 18.1 ``_is_unparseable_duration`` predicate reads.

    Durations are read strictly AS PARSED (``min_days`` / ``max_days`` / raw_text /
    sentence_type) — nothing is re-parsed (SD 10). The predicate is imported from
    the envelope module and consumed UNCHANGED so the duration signal is a single
    source of truth with the envelope's own UNPARSEABLE_DURATION emission.
    """
    return {
        "sentence_type": sentence["sentence_type"],
        "min_days": sentence["min_days"],
        "max_days": sentence["max_days"],
        "raw_text": sentence["raw_text"],
    }


def _load_all_sentences(conn: psycopg.Connection) -> list[dict[str, object]]:
    """Every parsed sentence joined to its charge's disposition state (one scan).

    Also carries the charge's ``docket_id`` / ``sequence`` and the docket's
    ``source_document_id`` so the sentence-grain review items (Task 23.4) can be
    anchored and dedup-keyed without a second scan; the STOP checks and SD-15 report
    ignore the extra columns.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT s.id, s.charge_id, s.component_order, s.sentence_type, "
            "s.raw_text, s.min_days, s.max_days, s.min_assumed, s.sentence_date, "
            "c.disposition_raw, c.disposition_date, c.docket_id, "
            "c.sequence AS charge_sequence, d.source_document_id "
            "FROM parsed.sentences s JOIN parsed.charges c ON s.charge_id = c.id "
            "JOIN parsed.dockets d ON c.docket_id = d.id"
        )
        return list(cur.fetchall())


def _duration_warning_count(conn: psycopg.Connection) -> int:
    """The corpus-wide count of ``UNPARSEABLE_DURATION`` parser warnings."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM parsed.warnings WHERE code = %s",
            (UNPARSEABLE_DURATION,),
        )
        row = cur.fetchone()
        assert row is not None
    return int(row[0])


def _prepare_sentences(conn: psycopg.Connection) -> dict[str, object]:
    """Read the sentence corpus and run the read-only STOP checks BEFORE any write.

    Returns the disposed-charge sentence rows plus the reconciliation counts.
    HARD STOP (``SentenceIntegrityError``) on: any sentence on a held
    (null-disposition) charge (orphan risk); or a duration-unparseable predicate
    count that disagrees with the envelope's UNPARSEABLE_DURATION emission
    (single-source-of-truth drift).

    SD 15 (``sentence_date`` == parent ``disposition_date``) is a SOFT REPORT, not
    a stop: the parser has two provenance paths for ``sentence_date`` — a
    component-level captured value (docket_parser.py:738) and a copy of the
    charge's disposition_date (docket_parser.py:925) — and the 21.3 loader carries
    the captured value verbatim. A divergence is therefore parser-origin and
    sound, not a defect; PD5 keys ``mvp_eligible`` off ``sentence_date`` regardless,
    so a sub-window captured date falls out via the existing
    ``sentence_date_before_mvp_window`` reason code. The divergence count, the
    MVP-boundary-straddle count, and the delta-day range are recorded for the run
    report.
    """
    all_sentences = _load_all_sentences(conn)

    held = [s for s in all_sentences if s["disposition_raw"] is None]
    if held:
        raise SentenceIntegrityError(
            f"{len(held)} sentence component(s) hang off held (null-disposition) "
            "charges; refusing to build (orphan risk)"
        )

    # The duration signal is component-grain but parsed.warnings is charge-grain,
    # so we re-apply the ENVELOPE's own predicate per component. It must reproduce
    # the envelope's emission exactly, else the predicate has drifted from it.
    dur_predicate_all = sum(
        1 for s in all_sentences if _is_unparseable_duration(_dur_view(s))
    )
    dur_warn_count = _duration_warning_count(conn)
    if dur_predicate_all != dur_warn_count:
        raise SentenceIntegrityError(
            f"duration-unparseable predicate ({dur_predicate_all}) disagrees with "
            f"the envelope UNPARSEABLE_DURATION emission ({dur_warn_count})"
        )

    disposed = [s for s in all_sentences if s["disposition_raw"] is not None]

    # SD 15 soft report: characterize (never gate) the sentence_date vs
    # disposition_date divergence.
    sd15_divergence = 0
    sd15_straddle_mvp = 0
    deltas: list[int] = []
    for s in disposed:
        sentence_date = _to_date(s["sentence_date"])
        disposition_date = _to_date(s["disposition_date"])
        if sentence_date == disposition_date:
            continue
        sd15_divergence += 1
        if sentence_date is not None and disposition_date is not None:
            deltas.append(abs((sentence_date - disposition_date).days))
            if (sentence_date >= MVP_WINDOW_START) != (
                disposition_date >= MVP_WINDOW_START
            ):
                sd15_straddle_mvp += 1

    return {
        "disposed_sentences": disposed,
        "components_on_disposed": len(disposed),
        "duration_warning_count": dur_warn_count,
        "duration_predicate_all": dur_predicate_all,
        "sd15_divergence": sd15_divergence,
        "sd15_straddle_mvp": sd15_straddle_mvp,
        "sd15_delta_days_min": min(deltas) if deltas else 0,
        "sd15_delta_days_max": max(deltas) if deltas else 0,
    }


def _load_outcome_fact_ids(conn: psycopg.Connection, run_id: str) -> dict[str, str]:
    """Map ``parsed_charge_id -> fact.charge_outcomes.id`` for the just-inserted run.

    Read back inside the build transaction (the rows are visible to their own
    connection pre-commit); the ``UNIQUE (build_run_id, parsed_charge_id)`` makes
    this a 1:1 map. This is how a sentence fact learns its parent's id without
    editing the 23.2 outcome-fact insert path.
    """
    ids: dict[str, str] = {}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, parsed_charge_id FROM fact.charge_outcomes "
            "WHERE build_run_id = %s",
            (run_id,),
        )
        for fact_id, parsed_charge_id in cur.fetchall():
            ids[str(parsed_charge_id)] = str(fact_id)
    return ids


def _collect_sentence_rows(
    prep: dict[str, object],
    outcome_id_by_charge: dict[str, str],
    parent_by_charge: dict[str, dict[str, object]],
    *,
    sentencing_mapper: SentencingMapper,
    taxonomy_version: str,
) -> tuple[list[dict[str, object]], dict[str, object], list[dict[str, object]]]:
    """Build every sentence-fact row (pure; no DB) + the separate sentence tallies.

    One row per parsed sentence component on a disposed charge; creation is NEVER
    gated by eligibility. Judge + normalized-charge fields are inherited from the
    parent outcome fact; the 22.5 mapper is applied per component at build time.
    STOP on a disposed-charge sentence whose charge has no parent outcome fact, or
    a 1:1 count mismatch.

    Also returns the sentence-grain ``review.queue_items`` payloads (Task 23.4):
    the 22.5 component items (unmapped / ambiguous / money-unparseable), the
    duration-unparseable item sourced from the per-component 18.1 predicate (the
    single source of truth, NOT ``parsed.warnings``), and the additive-category
    silent-loss item. The 22.5 module is consumed unchanged.
    """
    disposed: list[dict[str, object]] = prep["disposed_sentences"]  # type: ignore[assignment]

    rows: list[dict[str, object]] = []
    review_items: list[dict[str, object]] = []
    mvp_eligible = public_eligible = judge_specific_eligible = 0
    review_needed_count = 0
    reason_counts = _empty_reason_counts()
    category_split: Counter[str] = Counter()
    monetary = amount_set = money_unparseable = money_absent = 0
    multi_category = 0
    duration_facts = 0
    duration_charges: set[str] = set()

    for sentence in disposed:
        charge_id = str(sentence["charge_id"])
        parent_fact_id = outcome_id_by_charge.get(charge_id)
        if parent_fact_id is None:
            raise SentenceIntegrityError(
                "a disposed-charge sentence has no parent outcome fact in the run"
            )
        parent = parent_by_charge[charge_id]

        result = sentencing_mapper.map(
            str(sentence["sentence_type"]), str(sentence["raw_text"] or "")
        )
        component_match_method = derive_component_match_method(result)
        duration_unparseable = _is_unparseable_duration(_dur_view(sentence))
        sentence_date = _to_date(sentence["sentence_date"])

        # Sentence-grain review paths (Task 23.4). Anchors come off the extended
        # sentence scan; the dedup key uses only source_document_id + item_type +
        # (charge_sequence, component_order).
        source_document_id = str(sentence["source_document_id"])
        docket_id = str(sentence["docket_id"])
        charge_sequence = int(sentence["charge_sequence"])
        component_order = int(sentence["component_order"])
        sentence_id = str(sentence["id"])

        component_items = build_sentencing_review_items(
            result,
            source_document_id=source_document_id,
            charge_sequence=charge_sequence,
            component_order=component_order,
            parsed_docket_id=docket_id,
            parsed_charge_id=charge_id,
            parsed_sentence_id=sentence_id,
        )
        review_items.extend(component_items)
        if duration_unparseable:
            review_items.append(
                build_duration_review_item(
                    source_document_id=source_document_id,
                    charge_sequence=charge_sequence,
                    component_order=component_order,
                    parsed_docket_id=docket_id,
                    parsed_charge_id=charge_id,
                    parsed_sentence_id=sentence_id,
                    raw_value=str(sentence["sentence_type"]),
                )
            )
        # Additive silent-loss guard: emit ONLY when an additive category exists AND
        # the 22.5 helper produced no item for this component (so a money-unparseable
        # or ambiguous additive is never double-flagged). This routes the additive to
        # the queue; it does NOT touch the fact's review_needed (23.3 owns that).
        if len(result.categories) > 1 and not component_items:
            review_items.append(
                build_review_item(
                    source_document_id=source_document_id,
                    item_type=ADDITIVE_SENTENCING_CATEGORY,
                    severity=SEVERITY_LOW,
                    reason_code=REVIEW_NEEDED,
                    locator=(str(charge_sequence), str(component_order)),
                    parsed_docket_id=docket_id,
                    parsed_charge_id=charge_id,
                    parsed_sentence_id=sentence_id,
                    entity_type=ENTITY_SENTENCING,
                    raw_value=str(sentence["sentence_type"]),
                )
            )

        eligibility = evaluate_sentence_eligibility(
            sentence_date=sentence_date,
            result=result,
            component_match_method=component_match_method,
            duration_unparseable=duration_unparseable,
            parent_public_eligible=bool(parent["public_eligible"]),
            parent_attributed=parent_attributed(parent["judge_attribution_method"]),  # type: ignore[arg-type]
        )

        rows.append(
            build_sentence_fact_row(
                build_run_id=str(parent["build_run_id"]),
                charge_outcome_id=parent_fact_id,
                parsed_sentence_id=str(sentence["id"]),
                normalized_charge_id=parent["normalized_charge_id"],  # type: ignore[arg-type]
                sentence_date=sentence_date,
                result=result,
                component_match_method=component_match_method,
                min_days=sentence["min_days"],  # type: ignore[arg-type]
                max_days=sentence["max_days"],  # type: ignore[arg-type]
                min_assumed=bool(sentence["min_assumed"]),
                normalized_judge_id=parent["normalized_judge_id"],  # type: ignore[arg-type]
                judge_attribution_method=parent["judge_attribution_method"],  # type: ignore[arg-type]
                eligibility=eligibility,
                taxonomy_version=taxonomy_version,
            )
        )

        category_split[result.base.category_code] += 1
        mvp_eligible += int(eligibility.mvp_eligible)
        public_eligible += int(eligibility.public_eligible)
        judge_specific_eligible += int(eligibility.judge_specific_eligible)
        review_needed_count += int(eligibility.review_needed)
        for code in eligibility.ineligibility_reason_codes:
            reason_counts[code] += 1
        if len(result.categories) > 1:
            multi_category += 1
        if result.money is not None:
            monetary += 1
            if result.amount_cents is not None:
                amount_set += 1
            elif result.money_unparseable:
                money_unparseable += 1
            else:
                money_absent += 1
        if duration_unparseable:
            duration_facts += 1
            duration_charges.add(charge_id)

    components_on_disposed = int(prep["components_on_disposed"])  # type: ignore[call-overload]
    if len(rows) != components_on_disposed:
        raise SentenceIntegrityError(
            f"sentence-fact count ({len(rows)}) != parsed components on disposed "
            f"charges ({components_on_disposed})"
        )

    counts: dict[str, object] = {
        "sentence_facts_written": len(rows),
        "components_on_disposed": components_on_disposed,
        "mvp_eligible": mvp_eligible,
        "public_eligible": public_eligible,
        "judge_specific_eligible": judge_specific_eligible,
        "review_needed": review_needed_count,
        "sentencing_category_split": dict(sorted(category_split.items())),
        "ineligible_by_reason": reason_counts,
        "monetary_components": monetary,
        "amount_set": amount_set,
        "money_unparseable": money_unparseable,
        "money_absent": money_absent,
        "multi_category_components": multi_category,
        "duration_unparseable_facts": duration_facts,
        "duration_unparseable_charges": len(duration_charges),
        "duration_warning_count": prep["duration_warning_count"],
        "duration_predicate_all": prep["duration_predicate_all"],
        "sd15_divergence": prep["sd15_divergence"],
        "sd15_straddle_mvp": prep["sd15_straddle_mvp"],
        "sd15_delta_days_min": prep["sd15_delta_days_min"],
        "sd15_delta_days_max": prep["sd15_delta_days_max"],
    }
    return rows, counts, review_items


def _collect_warning_review_items(
    conn: psycopg.Connection,
) -> list[dict[str, object]]:
    """Build the envelope-warning-sourced review items (Task 23.4 R4).

    Scans ``parsed.warnings`` for the two codes 23.4 routes to the queue and joins
    each to its docket's stable ``source_document_id`` (the dedup anchor) and, when
    charge-grain, its ``parsed.charges`` id:

    - ``MISSING_DISPOSITION_DATE`` -> ``missing_disposition_date`` /
      ``disposition_date_missing`` / medium. The envelope emits this ONLY for a
      disposed charge with a null date (``disposition_raw`` present), so held /
      event-key charges structurally never flood the queue — no exclusion needed.
    - ``SENTINEL_COLLISION`` -> ``sentinel_collision`` / ``judge_not_normalized`` /
      medium. Emitted at TWO grains (docket-grain CASE INFORMATION, no
      ``charge_sequence``; charge-grain DISPOSITION). Both route here; the
      docket-grain case uses an empty locator, so the item count tracks the loaded
      warning tally (≤ it, dedup collapsing same charge/type).

    Uses a LEFT JOIN so a docket-grain (null ``charge_sequence``) warning still
    yields a row with a null charge id and an empty locator.
    """
    review_items: list[dict[str, object]] = []
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT w.code, w.charge_sequence, d.source_document_id, c.id AS charge_id "
            "FROM parsed.warnings w "
            "JOIN parsed.dockets d ON w.docket_id = d.id "
            "LEFT JOIN parsed.charges c "
            "  ON c.docket_id = w.docket_id AND c.sequence = w.charge_sequence "
            "WHERE w.code IN (%s, %s)",
            (WARN_MISSING_DISPOSITION_DATE, WARN_SENTINEL_COLLISION),
        )
        for row in cur.fetchall():
            source_document_id = str(row["source_document_id"])
            charge_sequence = row["charge_sequence"]
            charge_id = None if row["charge_id"] is None else str(row["charge_id"])
            # Charge-grain warnings carry a sequence -> a single-part locator; a
            # docket-grain warning (null sequence) uses the empty locator.
            locator = () if charge_sequence is None else (str(charge_sequence),)
            if row["code"] == WARN_MISSING_DISPOSITION_DATE:
                item_type, reason_code, entity_type = (
                    MISSING_DISPOSITION_DATE,
                    DISPOSITION_DATE_MISSING,
                    "disposition",
                )
            else:  # WARN_SENTINEL_COLLISION
                item_type, reason_code, entity_type = (
                    SENTINEL_COLLISION,
                    JUDGE_NOT_NORMALIZED,
                    ENTITY_JUDGE,
                )
            review_items.append(
                build_review_item(
                    source_document_id=source_document_id,
                    item_type=item_type,
                    severity=SEVERITY_MEDIUM,
                    reason_code=reason_code,
                    locator=locator,
                    parsed_charge_id=charge_id,
                    entity_type=entity_type,
                )
            )
    return review_items


def insert_review_items(
    conn: psycopg.Connection, review_items: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    """Insert review items with DB-enforced dedup; return per-type tallies.

    Idempotent and status-preserving (Task 23.4 AC2): payloads are first collapsed
    in memory by ``dedup_key`` (a same-record-same-type signal is one item), then
    each is inserted with ``ON CONFLICT (dedup_key) DO NOTHING`` against the 21.2
    unique constraint. An item that already exists from a prior run is left entirely
    untouched — including its ``status`` (the no-op insert fires no UPDATE, so the
    ``set_updated_at`` trigger never runs). Review items are NOT run-scoped: no
    build-run id is stored on them (SD 6).

    Returns ``generated`` (deduped, by type) and ``newly_inserted`` (actually added
    this run, by type) — the second equals zero on a re-run of an unchanged corpus.
    Runs inside the caller's transaction; does not commit.
    """
    deduped: dict[str, Mapping[str, object]] = {}
    for item in review_items:
        deduped.setdefault(str(item["dedup_key"]), item)

    generated_by_type: Counter[str] = Counter()
    inserted_by_type: Counter[str] = Counter()
    columns = (
        "item_type",
        "severity",
        "source_document_id",
        "parsed_docket_id",
        "parsed_charge_id",
        "parsed_sentence_id",
        "entity_type",
        "raw_value",
        "candidate_context",
        "reason_code",
        "status",
        "dedup_key",
    )
    placeholders = ", ".join(f"%({col})s" for col in columns)
    column_list = ", ".join(columns)
    with conn.cursor() as cur:
        for item in deduped.values():
            item_type = str(item["item_type"])
            generated_by_type[item_type] += 1
            candidate_context = item.get("candidate_context")
            params = {
                **item,
                "candidate_context": None
                if candidate_context is None
                else Json(candidate_context),
            }
            cur.execute(
                f"INSERT INTO review.queue_items ({column_list}) "  # noqa: S608 - columns are module constants, never input
                f"VALUES ({placeholders}) ON CONFLICT (dedup_key) DO NOTHING",
                params,
            )
            if cur.rowcount:
                inserted_by_type[item_type] += 1

    return {
        "generated_total": sum(generated_by_type.values()),
        "generated_by_type": dict(sorted(generated_by_type.items())),
        "newly_inserted_total": sum(inserted_by_type.values()),
        "newly_inserted_by_type": dict(sorted(inserted_by_type.items())),
    }


def _create_run(
    conn: psycopg.Connection,
    *,
    parser_version: int,
    envelope_parser_version: int,
    taxonomy_version: str,
    started_at: datetime,
) -> str:
    """Insert the ``in_progress`` run row and commit it (append-only history)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO fact.fact_build_runs
              (status, parser_version, envelope_parser_version, taxonomy_version,
               roster_snapshot_note, started_at)
            VALUES (%(status)s, %(parser_version)s, %(envelope_parser_version)s,
                    %(taxonomy_version)s, %(note)s, %(started_at)s)
            RETURNING id
            """,
            {
                "status": RUN_IN_PROGRESS,
                "parser_version": parser_version,
                "envelope_parser_version": envelope_parser_version,
                "taxonomy_version": taxonomy_version,
                "note": _ROSTER_SNAPSHOT_NOTE,
                "started_at": started_at,
            },
        )
        row = cur.fetchone()
        assert row is not None
    conn.commit()
    return str(row[0])


def _finish_run(
    conn: psycopg.Connection,
    run_id: str,
    *,
    status: str,
    completed_at: datetime,
    counts: dict[str, object] | None,
) -> None:
    """Flip a run to ``completed`` / ``failed`` with its completion timestamp."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE fact.fact_build_runs
               SET status = %(status)s, completed_at = %(completed_at)s,
                   counts = %(counts)s
             WHERE id = %(id)s
            """,
            {
                "status": status,
                "completed_at": completed_at,
                "counts": None if counts is None else Json(counts),
                "id": run_id,
            },
        )


def _print_summary(run_id: str, counts: dict[str, object]) -> None:
    """Print a counts-only run report (fixed codes only; no raw docket data)."""
    print(f"build-facts run={run_id[:16]} status={RUN_COMPLETED}")
    print(
        f"charges_processed={counts['charges_processed']} "
        f"facts_written={counts['facts_written']} "
        f"held_skipped={counts['held_skipped']}"
    )
    reconciles = int(counts["facts_written"]) + int(counts["held_skipped"]) == int(
        counts["charges_processed"]
    )
    print(f"reconcile facts_written+held_skipped==charges_processed: {reconciles}")
    print(
        f"mvp_eligible={counts['mvp_eligible']} "
        f"public_eligible={counts['public_eligible']} "
        f"judge_specific_eligible={counts['judge_specific_eligible']} "
        f"review_needed={counts['review_needed']}"
    )
    print("outcome_code_split:")
    for code, n in counts["outcome_code_split"].items():  # type: ignore[attr-defined]
        print(f"  {code:16} {n}")
    print("ineligible_by_reason:")
    for code, n in counts["ineligible_by_reason"].items():  # type: ignore[attr-defined]
        if n:
            print(f"  {code:34} {n}")
    if "sentences" in counts:
        _print_sentence_summary(counts["sentences"])  # type: ignore[arg-type]
    if "linkage" in counts:
        _print_linkage_summary(counts["linkage"])  # type: ignore[arg-type]
    if "review_items" in counts:
        _print_review_summary(counts["review_items"])  # type: ignore[arg-type]


def _print_linkage_summary(lc: dict[str, object]) -> None:
    """Print the CP<->MC held-case linkage block (Task 23.5) — counts only.

    Informational stage (AC4): these link rows do NOT affect the fact eligibility
    printed above. Resolved = in-corpus CP target (FK set); unresolved = out-of-corpus
    target (FK null) = a future-collection coverage signal (AC3). ``review_*`` are the
    unresolvable-reference items routed to the queue (malformed / ambiguous target)."""
    print(
        "--- cp<->mc held-case linkage (informational; AC4: no eligibility impact) ---"
    )
    print(
        f"mc_source_dockets={lc['source_mc_dockets_with_ref']} "
        f"links_total={lc['links_total']} resolved={lc['resolved']} "
        f"unresolved={lc['unresolved']}"
    )
    print(
        f"linkage_review_items malformed={lc['review_malformed']} "
        f"ambiguous={lc['review_ambiguous']}"
    )


def _print_review_summary(rc: dict[str, object]) -> None:
    """Print the review-queue block — item TYPES + counts only (hygiene: no raw
    values, no docket numbers). ``newly_inserted`` is zero on an unchanged re-run,
    demonstrating the dedup / status-preserving property (AC 3/4)."""
    print("--- review items ---")
    print(
        f"review_items generated={rc['generated_total']} "
        f"newly_inserted={rc['newly_inserted_total']}"
    )
    generated: dict[str, int] = rc["generated_by_type"]  # type: ignore[assignment]
    inserted: dict[str, int] = rc["newly_inserted_by_type"]  # type: ignore[assignment]
    print("review_items_by_type (generated / newly_inserted):")
    for item_type in sorted(generated):
        print(f"  {item_type:32} {generated[item_type]} / {inserted.get(item_type, 0)}")


def _print_sentence_summary(sc: dict[str, object]) -> None:
    """Print the sentence-fact block — counted SEPARATELY from outcomes (PD7)."""
    print("--- sentence facts ---")
    print(
        f"sentence_facts_written={sc['sentence_facts_written']} "
        f"components_on_disposed={sc['components_on_disposed']}"
    )
    reconciles = int(sc["sentence_facts_written"]) == int(sc["components_on_disposed"])
    print(f"reconcile sentence_facts==components_on_disposed: {reconciles}")
    print(
        f"mvp_eligible={sc['mvp_eligible']} "
        f"public_eligible={sc['public_eligible']} "
        f"judge_specific_eligible={sc['judge_specific_eligible']} "
        f"review_needed={sc['review_needed']}"
    )
    print(
        f"amount coverage: monetary={sc['monetary_components']} "
        f"amount_set={sc['amount_set']} money_unparseable={sc['money_unparseable']} "
        f"money_absent={sc['money_absent']}"
    )
    print(
        f"multi_category_components={sc['multi_category_components']} "
        f"(base stored; additive -> review)"
    )
    print(
        f"duration: facts={sc['duration_unparseable_facts']} "
        f"charges={sc['duration_unparseable_charges']} "
        f"envelope_warnings={sc['duration_warning_count']} "
        f"predicate_all={sc['duration_predicate_all']}"
    )
    # SD 15 soft report (documented finding, not a gate): the parser has two
    # sentence_date provenance paths — captured (docket_parser.py:738) and copied
    # from disposition_date (docket_parser.py:925); a divergence is parser-origin.
    print(
        f"sd15 divergence (sentence_date!=disposition_date): {sc['sd15_divergence']} "
        f"straddle_mvp={sc['sd15_straddle_mvp']} "
        f"delta_days={sc['sd15_delta_days_min']}..{sc['sd15_delta_days_max']} "
        "(parser paths: 738 captured / 925 copied)"
    )
    print("sentencing_category_split:")
    for code, n in sc["sentencing_category_split"].items():  # type: ignore[attr-defined]
        print(f"  {code:20} {n}")
    print("sentence_ineligible_by_reason:")
    for code, n in sc["ineligible_by_reason"].items():  # type: ignore[attr-defined]
        if n:
            print(f"  {code:34} {n}")


def build_facts(conn: psycopg.Connection, database_url: str) -> int:
    """Build outcome facts over the loaded corpus under one new run.

    ``conn`` is the open build connection; ``database_url`` is passed to the roster
    loaders (they open their own read-only connections at the boundary). Returns
    0 on a clean completed run, nonzero on a STOP or a failed build.
    """
    taxonomy = load_taxonomy_snapshot()
    mapper = OutcomeMapper(taxonomy)
    sentencing_taxonomy = load_sentencing_taxonomy()
    sentencing_mapper = SentencingMapper(sentencing_taxonomy)
    charge_matcher = ChargeMatcher(load_charge_roster(database_url))
    judge_matcher = JudgeMatcher(load_judge_roster(database_url))

    # Both mappers read the same taxonomy.json; a version disagreement would mean
    # a mixed stamp across the run's outcome and sentence facts -> STOP.
    if sentencing_taxonomy.taxonomy_version != taxonomy.taxonomy_version:
        logger.error(
            "refusing to build facts",
            extra={"reason": TaxonomyVersionMismatchError.__name__},
        )
        return 2

    try:
        parser_version, envelope_parser_version = _resolve_corpus_version(conn)
    except (EmptyCorpusError, MixedCorpusVersionError) as exc:
        logger.error("refusing to build facts", extra={"reason": type(exc).__name__})
        return 2

    # Read-only sentence integrity (held-charge / duration-emission / SD 15) runs
    # BEFORE any write, so a STOP leaves no run row (the empty/mixed-corpus rule).
    try:
        sentence_prep = _prepare_sentences(conn)
    except SentenceIntegrityError as exc:
        logger.error("refusing to build facts", extra={"reason": type(exc).__name__})
        return 2

    started_at = datetime.now(UTC)
    run_id = _create_run(
        conn,
        parser_version=parser_version,
        envelope_parser_version=envelope_parser_version,
        taxonomy_version=taxonomy.taxonomy_version,
        started_at=started_at,
    )

    try:
        rows, counts, outcome_review_items = _collect_outcome_rows(
            conn,
            run_id,
            charge_matcher=charge_matcher,
            judge_matcher=judge_matcher,
            mapper=mapper,
            taxonomy_version=taxonomy.taxonomy_version,
        )
        parent_by_charge = {str(row["parsed_charge_id"]): row for row in rows}
        with conn.transaction():
            insert_outcome_facts(conn, rows)
            # Parent ids exist only after insert; read them back inside the same
            # tx and hang the sentence facts off them (PD3 ordering).
            outcome_id_by_charge = _load_outcome_fact_ids(conn, run_id)
            sentence_rows, sentence_counts, sentence_review_items = (
                _collect_sentence_rows(
                    sentence_prep,
                    outcome_id_by_charge,
                    parent_by_charge,
                    sentencing_mapper=sentencing_mapper,
                    taxonomy_version=taxonomy.taxonomy_version,
                )
            )
            insert_sentence_facts(conn, sentence_rows)
            counts["sentences"] = sentence_counts
            # --- AC4 boundary (Task 23.5): CP<->MC held-case linkage is INFORMATIONAL
            # This stage runs STRICTLY AFTER every outcome/sentence fact and its
            # eligibility have been computed and inserted above. It only READS
            # parsed.dockets and WRITES parsed.docket_links rows + review items; it
            # feeds NOTHING back into fact eligibility. The outcome/sentence fact rows
            # are provably identical whether or not this stage runs — linkage never
            # re-opens the eligibility trio (Sprint 7 defers any attribution
            # consequence). Link rows are delete-and-reinserted (SD 6, current-state
            # projection); the review items join the persistent 23.4 dedup path below.
            link_rows, link_review_items, link_counts = collect_docket_links(conn)
            insert_docket_links(conn, link_rows)
            counts["linkage"] = link_counts
            # Route every 22.x/23.x review path into review.queue_items (Task 23.4).
            # NOT run-scoped: dedup-keyed, status-preserving across rebuilds. The
            # envelope-warning items are read here; the rest were built in the
            # collect passes above; the linkage items come from the stage above.
            warning_review_items = _collect_warning_review_items(conn)
            counts["review_items"] = insert_review_items(
                conn,
                [
                    *outcome_review_items,
                    *sentence_review_items,
                    *warning_review_items,
                    *link_review_items,
                ],
            )
            _finish_run(
                conn,
                run_id,
                status=RUN_COMPLETED,
                completed_at=datetime.now(UTC),
                counts=counts,
            )
    except Exception:
        conn.rollback()
        with conn.transaction():
            _finish_run(
                conn,
                run_id,
                status=RUN_FAILED,
                completed_at=datetime.now(UTC),
                counts=None,
            )
        logger.error(
            "fact build failed; run marked failed, no partial facts persisted",
            extra={"run": run_id[:16]},
        )
        return 1

    _print_summary(run_id, counts)
    logger.info("fact build complete", extra={"run": run_id[:16]})
    return 0


def run_build_facts(database_url: str) -> int:
    """CLI entry: open the build connection and run the outcome-fact build."""
    from pipeline import db

    with db.connect(database_url) as conn:
        return build_facts(conn, database_url)
