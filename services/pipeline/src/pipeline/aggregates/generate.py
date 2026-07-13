"""Charge-only OUTCOME aggregate generation + ``generate-aggregates`` (Task 26.1).

Reads eligible outcome facts from ONE ``fact.fact_build_runs`` run and writes
``analytics.charge_outcome_aggregates`` rows under a single ``analytics.aggregate_runs``
run. Charge-only outcomes only — no sentencing (26.2), no judge-specific (27.x), no
validation (28.1), no publish (28.2).

Eligibility is READ, never recomputed (Sprint 6 SD 1): the generator selects
``WHERE public_eligible`` and groups. The 2025-01-01 MVP window, the taxonomy
public-visibility flag, and every other gate already live on the facts from Sprint 5
— the aggregator re-applies none of them. There is no confidence threshold anywhere.

Run-status lifecycle mapping (Task 26.1, adjudicated in the planning chat). The
``analytics.aggregate_runs`` CHECK permits only ``in_progress|completed|failed``; the
Sprint 6 plan's lifecycle labels are NOT DB enum values. They map onto existing
columns, so this task needs no ``analytics.*`` migration:

    "generated" (26.1) -> status='in_progress', published_at/invalidated_at NULL
                          (a broken/unvalidated set is invisible to the public API,
                          whose predicate requires published_at IS NOT NULL)
    "validated" (28.1) -> status='completed'
    "failed"           -> status='failed'
    "published" (28.2) -> published_at set (the CHECK already requires 'completed')

Each invocation opens a NEW aggregate run and writes its rows via delete-and-reinsert
inside one transaction (SD 4; aggregate rows are immutable, so ON CONFLICT DO UPDATE is
never used). Published / invalidated runs are never read for reuse and never mutated.

Console/log output is counts, fixed reason/outcome/thin codes, and hash-prefix run ids
only — never docket numbers, raw text, or defendant data (facts carry no defendant
identity; ``analytics.*`` is aggregate-only). ``DATABASE_URL`` is read at the CLI
boundary only (21.3 pattern) and never printed or logged.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger("pipeline.aggregates.generate")

# --- Config defaults (Task 26.1 AC 2; no confidence thresholds anywhere) ---
DATA_START_DATE_DEFAULT = date(2025, 1, 1)
THIN_DATA_MIN_SAMPLE_SIZE_DEFAULT = 10
DEFAULT_RUN_LABEL = "charge-outcome-aggregates"

# --- Lifecycle status strings (see module docstring for the adjudicated mapping) ---
RUN_STATUS_GENERATED = "in_progress"
RUN_STATUS_FAILED = "failed"

# Thin-data reason surfaced in the run report (NOT stored: the aggregate tables carry
# only the is_thin_data boolean, and below_minimum_sample is its single implied cause).
BELOW_MINIMUM_SAMPLE = "below_minimum_sample"

_INSERT_COLUMNS = (
    "aggregate_run_id",
    "charge_id",
    "category_code",
    "count",
    "percentage",
    "sample_size",
    "date_range_start",
    "date_range_end",
    "is_thin_data",
    "taxonomy_version",
)


class NoCompletedBuildRunError(RuntimeError):
    """No completed ``fact.fact_build_runs`` run to aggregate from (STOP)."""


class BuildRunNotFoundError(RuntimeError):
    """A ``--build-run`` id that does not exist or is not completed (STOP)."""


class FactIntegrityError(RuntimeError):
    """A ``public_eligible`` fact violates an aggregation invariant (STOP).

    ``public_eligible`` structurally implies a matched charge (non-null
    ``normalized_charge_id``) and an in-window disposition date (non-null,
    >= the MVP start) — Sprint 5 eligibility guarantees both. A violation means the
    eligibility select and the fact rows disagree; that is stop-and-report, never a
    silently-skipped row.
    """


def _percentage(count: int, sample_size: int) -> str:
    """``count / sample_size`` as a percent string for the ``numeric(5,2)`` column.

    Half-up rounding to two decimals, mirroring the Sprint 2 aggregate seed's
    ``percentageOf``; returned as a string so no binary-float value ever reaches the
    driver.
    """
    value = (Decimal(count) * 100 / Decimal(sample_size)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return str(value)


def _resolve_build_run(
    conn: psycopg.Connection, build_run_id: str | None
) -> tuple[str, str, int, bool]:
    """Resolve the source fact build run: ``(id, taxonomy, parser, is_default)``.

    Default (``build_run_id`` None) = the latest COMPLETED run
    (``ORDER BY completed_at DESC LIMIT 1``); ``--build-run`` forces a specific id,
    which must exist and be completed. Facts are run-scoped (Sprint 5 SD 6); the
    generator never aggregates across runs.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        if build_run_id is not None:
            cur.execute(
                "SELECT id, status, taxonomy_version, parser_version "
                "FROM fact.fact_build_runs WHERE id = %s",
                (build_run_id,),
            )
            row = cur.fetchone()
            if row is None or row["status"] != "completed":
                raise BuildRunNotFoundError(
                    "requested --build-run is not a completed fact build run"
                )
            return (
                str(row["id"]),
                str(row["taxonomy_version"]),
                int(row["parser_version"]),
                False,
            )
        cur.execute(
            "SELECT id, taxonomy_version, parser_version FROM fact.fact_build_runs "
            "WHERE status = 'completed' ORDER BY completed_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        if row is None:
            raise NoCompletedBuildRunError(
                "no completed fact build run exists; run `pipeline build-facts` first"
            )
        return (
            str(row["id"]),
            str(row["taxonomy_version"]),
            int(row["parser_version"]),
            True,
        )


def _load_outcome_facts(
    conn: psycopg.Connection, build_run_id: str
) -> list[dict[str, object]]:
    """Every outcome fact for the build run (eligibility read, never recomputed)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT normalized_charge_id, outcome_category_code, disposition_date, "
            "public_eligible, ineligibility_reason_codes "
            "FROM fact.charge_outcomes WHERE build_run_id = %s",
            (build_run_id,),
        )
        return list(cur.fetchall())


def build_charge_outcome_aggregates(
    facts: Sequence[Mapping[str, object]],
    *,
    data_start_date: date,
    thin_min_sample: int,
    taxonomy_version: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Build every charge-outcome aggregate row from the run's facts (pure; no DB).

    Groups ``public_eligible`` facts by normalized charge, then by outcome category.
    Each row carries the charge's outcome sample size (its eligible-fact denominator),
    the category count, the count/sample_size percentage, the charge's eligible
    disposition-date range (never before ``data_start_date``), the thin-data flag
    (``sample_size < thin_min_sample``), the run's taxonomy version, and the run id
    (stamped by the caller). Groups with zero eligible facts produce no rows (SD 6).

    Returns ``(rows, report)``. ``report`` carries the run-report tallies: facts
    loaded / included / excluded, the fact layer's own ineligibility reason-code
    tally over the excluded facts, distinct charges, aggregate rows, thin-data
    charges, and the eligible date-range span.
    """
    included: list[Mapping[str, object]] = []
    excluded_reason_counts: Counter[str] = Counter()
    for fact in facts:
        if fact["public_eligible"]:
            included.append(fact)
        else:
            for code in fact["ineligibility_reason_codes"] or ():  # type: ignore[union-attr]
                excluded_reason_counts[str(code)] += 1

    # Group included facts by normalized charge (order-stable for a stable report).
    by_charge: dict[str, list[Mapping[str, object]]] = {}
    for fact in included:
        charge_id = fact["normalized_charge_id"]
        disposition_date = fact["disposition_date"]
        # public_eligible structurally guarantees both; a violation is stop-and-report.
        if charge_id is None:
            raise FactIntegrityError(
                "public_eligible fact has a null normalized_charge_id"
            )
        if disposition_date is None:
            raise FactIntegrityError("public_eligible fact has a null disposition_date")
        if disposition_date < data_start_date:
            raise FactIntegrityError(
                "public_eligible fact predates the configured data start date"
            )
        by_charge.setdefault(str(charge_id), []).append(fact)

    rows: list[dict[str, object]] = []
    thin_charges = 0
    run_date_max: date | None = None
    for charge_id, charge_facts in by_charge.items():
        sample_size = len(charge_facts)
        is_thin = sample_size < thin_min_sample
        if is_thin:
            thin_charges += 1
        dates = [f["disposition_date"] for f in charge_facts]
        charge_start = min(dates)  # type: ignore[type-var]
        charge_end = max(dates)  # type: ignore[type-var]
        run_date_max = (
            charge_end if run_date_max is None else max(run_date_max, charge_end)
        )  # type: ignore[type-var]

        category_counts = Counter(str(f["outcome_category_code"]) for f in charge_facts)
        for category_code, count in sorted(category_counts.items()):
            rows.append(
                {
                    "charge_id": charge_id,
                    "category_code": category_code,
                    "count": count,
                    "percentage": _percentage(count, sample_size),
                    "sample_size": sample_size,
                    "date_range_start": charge_start,
                    "date_range_end": charge_end,
                    "is_thin_data": is_thin,
                    "taxonomy_version": taxonomy_version,
                }
            )

    report: dict[str, object] = {
        "facts_loaded": len(facts),
        "facts_included": len(included),
        "facts_excluded": len(facts) - len(included),
        "excluded_by_reason": dict(sorted(excluded_reason_counts.items())),
        "charges_with_aggregates": len(by_charge),
        "outcome_aggregates_generated": len(rows),
        "thin_data_charges": thin_charges,
        "data_range_end": run_date_max,
    }
    return rows, report


def _create_run(
    conn: psycopg.Connection,
    *,
    taxonomy_version: str,
    parser_version: int,
    data_range_start: date,
    data_range_end: date,
    started_at: datetime,
) -> str:
    """Insert the ``in_progress`` ("generated") run row and commit it (history)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO analytics.aggregate_runs
              (status, started_at, parser_version, taxonomy_version,
               data_range_start, data_range_end)
            VALUES (%(status)s, %(started_at)s, %(parser_version)s,
                    %(taxonomy_version)s, %(data_range_start)s, %(data_range_end)s)
            RETURNING id
            """,
            {
                "status": RUN_STATUS_GENERATED,
                "started_at": started_at,
                "parser_version": str(parser_version),
                "taxonomy_version": taxonomy_version,
                "data_range_start": data_range_start,
                "data_range_end": data_range_end,
            },
        )
        row = cur.fetchone()
        assert row is not None
    conn.commit()
    return str(row[0])


def _write_aggregates(
    conn: psycopg.Connection, run_id: str, rows: Sequence[Mapping[str, object]]
) -> int:
    """Delete-and-reinsert this run's charge-outcome aggregate rows (caller's tx).

    Delete-first is the immutable-safe write path (SD 4): a re-generation of the same
    run replaces its rows rather than UPDATE-ing them. Insert-only otherwise. Does not
    commit; the caller owns the transaction boundary.
    """
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM analytics.charge_outcome_aggregates "
            "WHERE aggregate_run_id = %s",
            (run_id,),
        )
        if not rows:
            return 0
        columns = ", ".join(_INSERT_COLUMNS)
        placeholders = ", ".join(f"%({col})s" for col in _INSERT_COLUMNS)
        cur.executemany(
            f"INSERT INTO analytics.charge_outcome_aggregates ({columns}) "  # noqa: S608 - columns are module constants, never input
            f"VALUES ({placeholders})",
            [{**row, "aggregate_run_id": run_id} for row in rows],
        )
    return len(rows)


def _fail_run(conn: psycopg.Connection, run_id: str) -> None:
    """Mark a run ``failed`` in its own transaction (no partial rows persist)."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE analytics.aggregate_runs SET status = %s WHERE id = %s",
            (RUN_STATUS_FAILED, run_id),
        )


def _print_summary(
    run_id: str,
    build_run_id: str,
    *,
    is_default_build_run: bool,
    label: str,
    thin_min_sample: int,
    data_range_start: date,
    data_range_end: date,
    report: Mapping[str, object],
) -> None:
    """Counts-only run report (fixed codes + hash-prefix run ids; no docket data)."""
    source = "default" if is_default_build_run else "forced"
    print(
        f"generate-aggregates run={run_id[:16]} status=generated label={label} "
        f"build_run={build_run_id[:16]} ({source})"
    )
    print(
        f"facts_loaded={report['facts_loaded']} "
        f"facts_included={report['facts_included']} "
        f"facts_excluded={report['facts_excluded']}"
    )
    print("excluded_by_reason:")
    for code, n in report["excluded_by_reason"].items():  # type: ignore[attr-defined]
        if n:
            print(f"  {code:34} {n}")
    print(
        f"charges_with_aggregates={report['charges_with_aggregates']} "
        f"outcome_aggregates_generated={report['outcome_aggregates_generated']}"
    )
    print(
        f"thin_data_charges={report['thin_data_charges']} "
        f"({BELOW_MINIMUM_SAMPLE}; min_sample={thin_min_sample})"
    )
    print(f"data_range: {data_range_start.isoformat()}..{data_range_end.isoformat()}")


def generate_aggregates(
    conn: psycopg.Connection,
    *,
    build_run_id: str | None,
    data_start_date: date,
    thin_min_sample: int,
    label: str,
) -> int:
    """Generate charge-only outcome aggregates over one build run under a new run.

    Returns 0 on a clean generated run, nonzero on a STOP (no completed build run /
    bad ``--build-run`` / fact-integrity violation) or a failed write.
    """
    try:
        build_run_id, taxonomy_version, parser_version, is_default = _resolve_build_run(
            conn, build_run_id
        )
    except (NoCompletedBuildRunError, BuildRunNotFoundError) as exc:
        logger.error(
            "refusing to generate aggregates", extra={"reason": type(exc).__name__}
        )
        return 2

    facts = _load_outcome_facts(conn, build_run_id)

    # All reads + the pure build (including the fact-integrity STOP checks) happen
    # BEFORE any write, so a STOP leaves no run row.
    try:
        rows, report = build_charge_outcome_aggregates(
            facts,
            data_start_date=data_start_date,
            thin_min_sample=thin_min_sample,
            taxonomy_version=taxonomy_version,
        )
    except FactIntegrityError as exc:
        logger.error(
            "refusing to generate aggregates", extra={"reason": type(exc).__name__}
        )
        return 2

    # Run-level data range: the configured floor as start; the latest eligible
    # disposition date as end (the floor itself when the run has no eligible facts,
    # keeping the start <= end CHECK satisfied).
    data_range_end = report["data_range_end"] or data_start_date  # type: ignore[assignment]

    started_at = datetime.now(UTC)
    run_id = _create_run(
        conn,
        taxonomy_version=taxonomy_version,
        parser_version=parser_version,
        data_range_start=data_start_date,
        data_range_end=data_range_end,  # type: ignore[arg-type]
        started_at=started_at,
    )

    try:
        with conn.transaction():
            _write_aggregates(conn, run_id, rows)
    except Exception:
        conn.rollback()
        with conn.transaction():
            _fail_run(conn, run_id)
        logger.error(
            "aggregate generation failed; run marked failed, no partial rows persisted",
            extra={"run": run_id[:16]},
        )
        return 1

    _print_summary(
        run_id,
        build_run_id,
        is_default_build_run=is_default,
        label=label,
        thin_min_sample=thin_min_sample,
        data_range_start=data_start_date,
        data_range_end=data_range_end,  # type: ignore[arg-type]
        report=report,
    )
    logger.info("aggregate generation complete", extra={"run": run_id[:16]})
    return 0


def run_generate_aggregates(
    database_url: str,
    *,
    build_run_id: str | None,
    data_start_date: date,
    thin_min_sample: int,
    label: str,
) -> int:
    """CLI entry: open the connection and run charge-only outcome generation."""
    from pipeline import db

    with db.connect(database_url) as conn:
        return generate_aggregates(
            conn,
            build_run_id=build_run_id,
            data_start_date=data_start_date,
            thin_min_sample=thin_min_sample,
            label=label,
        )
