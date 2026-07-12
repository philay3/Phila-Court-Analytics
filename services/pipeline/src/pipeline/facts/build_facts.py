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
from datetime import UTC, date, datetime

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from pipeline.envelope import _is_unparseable_duration
from pipeline.fact_review_vocab import (
    ELIGIBILITY_REASON_CODES,
    RUN_COMPLETED,
    RUN_FAILED,
    RUN_IN_PROGRESS,
)
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
from pipeline.normalization.charge_matcher import ChargeMatcher
from pipeline.normalization.charge_roster_loader import load_charge_roster
from pipeline.normalization.judge_matcher import JudgeMatcher
from pipeline.normalization.judge_roster_loader import load_judge_roster
from pipeline.normalization.outcome_mapper import OutcomeMapper, load_taxonomy_snapshot
from pipeline.normalization.sentencing_mapper import (
    SentencingMapper,
    load_sentencing_taxonomy,
)
from pipeline.warning_codes import UNPARSEABLE_DURATION

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
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Read the corpus and build every outcome-fact row (no writes here).

    Returns ``(rows, counts)``. One row per disposed charge; held charges are
    counted, never rowed. ``counts`` carries the run-report tallies used for the
    completion reconciliation (facts_written + held_skipped == charges_processed;
    the outcome-code split equals the 22.4 mapper split over the same corpus).
    """
    charge_warnings = _load_charge_warning_codes(conn)
    dockets = _load_dockets(conn)
    charges_by_docket = _load_charges_by_docket(conn)

    rows: list[dict[str, object]] = []
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
    return rows, counts


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
    """Every parsed sentence joined to its charge's disposition state (one scan)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT s.id, s.charge_id, s.component_order, s.sentence_type, "
            "s.raw_text, s.min_days, s.max_days, s.min_assumed, s.sentence_date, "
            "c.disposition_raw, c.disposition_date "
            "FROM parsed.sentences s JOIN parsed.charges c ON s.charge_id = c.id"
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
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Build every sentence-fact row (pure; no DB) + the separate sentence tallies.

    One row per parsed sentence component on a disposed charge; creation is NEVER
    gated by eligibility. Judge + normalized-charge fields are inherited from the
    parent outcome fact; the 22.5 mapper is applied per component at build time.
    STOP on a disposed-charge sentence whose charge has no parent outcome fact, or
    a 1:1 count mismatch.
    """
    disposed: list[dict[str, object]] = prep["disposed_sentences"]  # type: ignore[assignment]

    rows: list[dict[str, object]] = []
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
    return rows, counts


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
        rows, counts = _collect_outcome_rows(
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
            sentence_rows, sentence_counts = _collect_sentence_rows(
                sentence_prep,
                outcome_id_by_charge,
                parent_by_charge,
                sentencing_mapper=sentencing_mapper,
                taxonomy_version=taxonomy.taxonomy_version,
            )
            insert_sentence_facts(conn, sentence_rows)
            counts["sentences"] = sentence_counts
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
