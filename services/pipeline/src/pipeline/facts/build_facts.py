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

from pipeline.fact_review_vocab import (
    ELIGIBILITY_REASON_CODES,
    RUN_COMPLETED,
    RUN_FAILED,
    RUN_IN_PROGRESS,
)
from pipeline.facts.judge_attribution import build_docket_context, resolve_charge
from pipeline.facts.outcome_facts import (
    build_outcome_fact_row,
    evaluate_outcome_eligibility,
    insert_outcome_facts,
)
from pipeline.normalization.charge_matcher import ChargeMatcher
from pipeline.normalization.charge_roster_loader import load_charge_roster
from pipeline.normalization.judge_matcher import JudgeMatcher
from pipeline.normalization.judge_roster_loader import load_judge_roster
from pipeline.normalization.outcome_mapper import OutcomeMapper, load_taxonomy_snapshot

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


def build_facts(conn: psycopg.Connection, database_url: str) -> int:
    """Build outcome facts over the loaded corpus under one new run.

    ``conn`` is the open build connection; ``database_url`` is passed to the roster
    loaders (they open their own read-only connections at the boundary). Returns
    0 on a clean completed run, nonzero on a STOP or a failed build.
    """
    taxonomy = load_taxonomy_snapshot()
    mapper = OutcomeMapper(taxonomy)
    charge_matcher = ChargeMatcher(load_charge_roster(database_url))
    judge_matcher = JudgeMatcher(load_judge_roster(database_url))

    try:
        parser_version, envelope_parser_version = _resolve_corpus_version(conn)
    except (EmptyCorpusError, MixedCorpusVersionError) as exc:
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
        with conn.transaction():
            insert_outcome_facts(conn, rows)
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
