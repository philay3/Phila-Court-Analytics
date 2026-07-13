"""Charge-only + judge-specific OUTCOME and SENTENCING aggregate
generation + ``generate-aggregates`` (Tasks 26.1, 26.2, 27.1, 27.2).

Reads eligible outcome facts and eligible sentence facts from ONE
``fact.fact_build_runs`` run and writes ``analytics.charge_outcome_aggregates``,
``analytics.charge_sentencing_aggregates``, ``analytics.judge_outcome_aggregates``,
and ``analytics.judge_sentencing_aggregates`` rows under a single
``analytics.aggregate_runs`` run, in the SAME generation invocation and the SAME
write transaction (Tasks 26.2, 27.1, 27.2). No validation (28.1), no publish (28.2).

The judge-specific passes (Tasks 27.1, 27.2) group ``judge_specific_eligible``
outcome facts (27.1) and sentence facts (27.2) by charge+judge pair, then by
category. The denominator is PER PAIR: each row's ``sample_size`` /
``sentencing_sample_size`` is that pair's eligible fact count, never the
charge-wide count — and the pair's sentencing sample is counted over sentence
facts independently, never copied from the pair's outcome sample (SD 5). The
baseline guarantee (Sprint 6 SD 7 — every judge-specific aggregate has a
same-run charge-only counterpart) is structural (``judge_specific_eligible`` implies
``public_eligible`` at fact build, for outcome AND sentence facts) and is asserted
in tests and re-validated in 28.1; the generator never generates baseline data
separately and adds no runtime enforcement. A pair with judge-specific outcomes
but no eligible judge-specific sentence facts simply gets no judge-sentencing
rows — the API's sentencing-unavailable arm covers it (SD 6), never a placeholder.

Sentencing sample size is computed INDEPENDENTLY (Sprint 6 SD 5): it counts the
charge's eligible *sentence* facts (one row per sentence component, never collapsed),
never copied from the outcome count. A charge with eligible outcomes but no eligible
sentence facts produces outcome rows and NO sentencing rows — the normal
sentencing-unavailable case (SD 6), never a placeholder.

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

# The sentencing aggregate table (task 6.2) shares AggregateRowBase but carries
# ``sentencing_sample_size`` in place of the outcome table's ``sample_size``.
_SENTENCING_INSERT_COLUMNS = (
    "aggregate_run_id",
    "charge_id",
    "category_code",
    "count",
    "percentage",
    "sentencing_sample_size",
    "date_range_start",
    "date_range_end",
    "is_thin_data",
    "taxonomy_version",
)

# The judge-specific outcome table (task 6.2) is the charge-only outcome shape
# plus ``judge_id`` (Task 27.1).
_JUDGE_INSERT_COLUMNS = (
    "aggregate_run_id",
    "charge_id",
    "judge_id",
    "category_code",
    "count",
    "percentage",
    "sample_size",
    "date_range_start",
    "date_range_end",
    "is_thin_data",
    "taxonomy_version",
)

# The judge-specific sentencing table (task 6.2) is the charge-only sentencing
# shape plus ``judge_id`` (Task 27.2): ``sentencing_sample_size``, never
# ``sample_size``.
_JUDGE_SENTENCING_INSERT_COLUMNS = (
    "aggregate_run_id",
    "charge_id",
    "judge_id",
    "category_code",
    "count",
    "percentage",
    "sentencing_sample_size",
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
    ``normalized_charge_id``) and an in-window date (non-null, >= the MVP start) —
    Sprint 5 eligibility guarantees both. For outcome facts the date is
    ``disposition_date``; for sentence facts it is the independently-captured
    ``sentence_date`` (SD 15), which can predate the disposition date but never the
    2025-01-01 floor. A violation means the eligibility select and the fact rows
    disagree; that is stop-and-report, never a silently-skipped row (SD 1: read
    eligibility, never recompute it — an eligible fact outside the window is a
    fact-layer defect to surface, not a row to silently filter).
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
    """Every outcome fact for the build run (eligibility read, never recomputed).

    ``normalized_judge_id`` / ``judge_specific_eligible`` feed the judge-specific
    pass (Task 27.1). ``judge_attribution_method`` is deliberately NOT selected:
    no aggregate column consumes it, and the fact layer already folded attribution
    validity into ``judge_specific_eligible`` (SD 1 — read eligibility, never
    re-apply attribution rules).
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT normalized_charge_id, outcome_category_code, disposition_date, "
            "public_eligible, ineligibility_reason_codes, "
            "normalized_judge_id, judge_specific_eligible "
            "FROM fact.charge_outcomes WHERE build_run_id = %s",
            (build_run_id,),
        )
        return list(cur.fetchall())


def _load_sentence_facts(
    conn: psycopg.Connection, build_run_id: str
) -> list[dict[str, object]]:
    """Every sentence fact for the build run (one row per component; never collapsed).

    Eligibility is read, never recomputed (SD 1). Multi-component sentences are
    ``fact.charge_sentences`` rows 1:1 with the parsed components, so grouping these
    rows by charge and category counts every component independently (SD 5).

    ``normalized_judge_id`` / ``judge_specific_eligible`` feed the judge-specific
    sentencing pass (Task 27.2), the same two-column extension 27.1 made to the
    outcome loader. ``judge_attribution_method`` is deliberately NOT selected:
    the fact layer already folded attribution validity into
    ``judge_specific_eligible`` (SD 1).
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT normalized_charge_id, sentencing_category_code, sentence_date, "
            "public_eligible, ineligibility_reason_codes, "
            "normalized_judge_id, judge_specific_eligible "
            "FROM fact.charge_sentences WHERE build_run_id = %s",
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


def build_judge_outcome_aggregates(
    facts: Sequence[Mapping[str, object]],
    *,
    data_start_date: date,
    thin_min_sample: int,
    taxonomy_version: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Build every judge-outcome aggregate row from the run's facts (pure; no DB).

    Parallel to :func:`build_charge_outcome_aggregates` over the SAME loaded outcome
    facts, selecting ``judge_specific_eligible`` (read, never recomputed — SD 1) and
    grouping by charge+judge pair, then by outcome category. Each row carries the
    PAIR's sample size (its eligible-fact denominator, never the charge-wide count),
    the category count, the count/sample_size percentage, the pair's eligible
    disposition-date range (never before ``data_start_date``), the per-pair thin-data
    flag (``sample_size < thin_min_sample``), the run's taxonomy version, and the run
    id (stamped by the caller). Pairs with zero eligible facts produce no rows (SD 6).

    An eligible fact with a null judge FK, null charge FK, null disposition date, or
    pre-window date is a fact-layer defect surfaced pre-write via
    :class:`FactIntegrityError` — never silently filtered.

    Returns ``(rows, report)``. ``report`` carries the run-report tallies: judge facts
    included, distinct charge+judge pairs covered, judge aggregate rows, thin-data
    pairs, and the pair-population date-range end.
    """
    included = [f for f in facts if f["judge_specific_eligible"]]

    # Group included facts by (charge, judge) pair (order-stable for a stable report).
    by_pair: dict[tuple[str, str], list[Mapping[str, object]]] = {}
    for fact in included:
        charge_id = fact["normalized_charge_id"]
        judge_id = fact["normalized_judge_id"]
        disposition_date = fact["disposition_date"]
        # judge_specific_eligible structurally guarantees all three; a violation is
        # stop-and-report.
        if charge_id is None:
            raise FactIntegrityError(
                "judge_specific_eligible fact has a null normalized_charge_id"
            )
        if judge_id is None:
            raise FactIntegrityError(
                "judge_specific_eligible fact has a null normalized_judge_id"
            )
        if disposition_date is None:
            raise FactIntegrityError(
                "judge_specific_eligible fact has a null disposition_date"
            )
        if disposition_date < data_start_date:
            raise FactIntegrityError(
                "judge_specific_eligible fact predates the configured data start date"
            )
        by_pair.setdefault((str(charge_id), str(judge_id)), []).append(fact)

    rows: list[dict[str, object]] = []
    thin_pairs = 0
    run_date_max: date | None = None
    for (charge_id, judge_id), pair_facts in by_pair.items():
        sample_size = len(pair_facts)
        is_thin = sample_size < thin_min_sample
        if is_thin:
            thin_pairs += 1
        dates = [f["disposition_date"] for f in pair_facts]
        pair_start = min(dates)  # type: ignore[type-var]
        pair_end = max(dates)  # type: ignore[type-var]
        run_date_max = pair_end if run_date_max is None else max(run_date_max, pair_end)  # type: ignore[type-var]

        category_counts = Counter(str(f["outcome_category_code"]) for f in pair_facts)
        for category_code, count in sorted(category_counts.items()):
            rows.append(
                {
                    "charge_id": charge_id,
                    "judge_id": judge_id,
                    "category_code": category_code,
                    "count": count,
                    "percentage": _percentage(count, sample_size),
                    "sample_size": sample_size,
                    "date_range_start": pair_start,
                    "date_range_end": pair_end,
                    "is_thin_data": is_thin,
                    "taxonomy_version": taxonomy_version,
                }
            )

    report: dict[str, object] = {
        "judge_facts_included": len(included),
        "charge_judge_pairs_covered": len(by_pair),
        "judge_outcome_aggregates_generated": len(rows),
        "thin_data_pairs": thin_pairs,
        "data_range_end": run_date_max,
    }
    return rows, report


def build_charge_sentencing_aggregates(
    facts: Sequence[Mapping[str, object]],
    *,
    data_start_date: date,
    thin_min_sample: int,
    taxonomy_version: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Build every charge-sentencing aggregate row from the run's sentence facts.

    Parallel to :func:`build_charge_outcome_aggregates` but over
    ``fact.charge_sentences`` (pure; no DB). Groups ``public_eligible`` sentence facts
    by normalized charge, then by sentencing category. Each row carries the charge's
    INDEPENDENT sentencing sample size (its eligible-sentence-fact denominator, SD 5 —
    never the outcome count), the category count, the count/sample_size percentage, the
    charge's eligible ``sentence_date`` range (never before ``data_start_date``, SD 15),
    the thin-data flag (``sample_size < thin_min_sample``), the run's taxonomy version,
    and the run id (stamped by the caller). Charges with zero eligible sentence facts
    produce no rows (SD 6) — the normal sentencing-unavailable case.

    Returns ``(rows, report)``. ``report`` carries the sentencing tallies: sentence
    facts loaded / included / excluded, the fact layer's own ineligibility reason-code
    tally over the excluded sentence facts, distinct charges with sentencing, sentencing
    aggregate rows, thin-data sentencing charges, and the eligible sentence-date span.
    """
    included: list[Mapping[str, object]] = []
    excluded_reason_counts: Counter[str] = Counter()
    for fact in facts:
        if fact["public_eligible"]:
            included.append(fact)
        else:
            for code in fact["ineligibility_reason_codes"] or ():  # type: ignore[union-attr]
                excluded_reason_counts[str(code)] += 1

    # Group included sentence facts by normalized charge (order-stable report).
    by_charge: dict[str, list[Mapping[str, object]]] = {}
    for fact in included:
        charge_id = fact["normalized_charge_id"]
        sentence_date = fact["sentence_date"]
        # public_eligible structurally guarantees both; a violation is stop-and-report.
        if charge_id is None:
            raise FactIntegrityError(
                "public_eligible sentence fact has a null normalized_charge_id"
            )
        if sentence_date is None:
            raise FactIntegrityError(
                "public_eligible sentence fact has a null sentence_date"
            )
        if sentence_date < data_start_date:
            raise FactIntegrityError(
                "public_eligible sentence fact predates the configured data start date"
            )
        by_charge.setdefault(str(charge_id), []).append(fact)

    rows: list[dict[str, object]] = []
    thin_charges = 0
    run_date_max: date | None = None
    for charge_id, charge_facts in by_charge.items():
        sentencing_sample_size = len(charge_facts)
        is_thin = sentencing_sample_size < thin_min_sample
        if is_thin:
            thin_charges += 1
        dates = [f["sentence_date"] for f in charge_facts]
        charge_start = min(dates)  # type: ignore[type-var]
        charge_end = max(dates)  # type: ignore[type-var]
        run_date_max = (
            charge_end if run_date_max is None else max(run_date_max, charge_end)
        )  # type: ignore[type-var]

        category_counts = Counter(
            str(f["sentencing_category_code"]) for f in charge_facts
        )
        for category_code, count in sorted(category_counts.items()):
            rows.append(
                {
                    "charge_id": charge_id,
                    "category_code": category_code,
                    "count": count,
                    "percentage": _percentage(count, sentencing_sample_size),
                    "sentencing_sample_size": sentencing_sample_size,
                    "date_range_start": charge_start,
                    "date_range_end": charge_end,
                    "is_thin_data": is_thin,
                    "taxonomy_version": taxonomy_version,
                }
            )

    report: dict[str, object] = {
        "sentence_facts_loaded": len(facts),
        "sentence_facts_included": len(included),
        "sentence_facts_excluded": len(facts) - len(included),
        "sentencing_excluded_by_reason": dict(sorted(excluded_reason_counts.items())),
        "charges_with_sentencing": len(by_charge),
        "sentencing_aggregates_generated": len(rows),
        "thin_data_sentencing_charges": thin_charges,
        "data_range_end": run_date_max,
    }
    return rows, report


def build_judge_sentencing_aggregates(
    facts: Sequence[Mapping[str, object]],
    *,
    data_start_date: date,
    thin_min_sample: int,
    taxonomy_version: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Build every judge-sentencing aggregate row from the run's sentence facts.

    Parallel to :func:`build_judge_outcome_aggregates` over the SAME loaded sentence
    facts (pure; no DB), selecting ``judge_specific_eligible`` (read, never
    recomputed — SD 1) and grouping by charge+judge pair, then by sentencing
    category. Each row carries the PAIR's INDEPENDENT ``sentencing_sample_size``
    (its eligible-sentence-fact denominator, SD 5 — never the pair's outcome count,
    never the charge-wide count), the category count, the count/sample percentage,
    the pair's eligible ``sentence_date`` range (never before ``data_start_date``;
    SD 15 — the independently-captured sentence date, never the parent disposition
    date), the per-pair thin-data flag (``sentencing_sample_size <
    thin_min_sample``), the run's taxonomy version, and the run id (stamped by the
    caller). Pairs with zero eligible sentence facts produce no rows (SD 6) — the
    normal sentencing-unavailable case, including pairs that DO have judge-specific
    outcome aggregates.

    An eligible fact with a null judge FK, null charge FK, null sentence date, or
    pre-window sentence date is a fact-layer defect surfaced pre-write via
    :class:`FactIntegrityError` — never silently filtered.

    Returns ``(rows, report)``. ``report`` carries the run-report tallies: judge
    sentence facts included, distinct charge+judge sentencing pairs covered, judge
    sentencing aggregate rows, thin-data sentencing pairs, and the pair-population
    sentence-date range end.
    """
    included = [f for f in facts if f["judge_specific_eligible"]]

    # Group included facts by (charge, judge) pair (order-stable for a stable report).
    by_pair: dict[tuple[str, str], list[Mapping[str, object]]] = {}
    for fact in included:
        charge_id = fact["normalized_charge_id"]
        judge_id = fact["normalized_judge_id"]
        sentence_date = fact["sentence_date"]
        # judge_specific_eligible structurally guarantees all three; a violation is
        # stop-and-report.
        if charge_id is None:
            raise FactIntegrityError(
                "judge_specific_eligible sentence fact has a null normalized_charge_id"
            )
        if judge_id is None:
            raise FactIntegrityError(
                "judge_specific_eligible sentence fact has a null normalized_judge_id"
            )
        if sentence_date is None:
            raise FactIntegrityError(
                "judge_specific_eligible sentence fact has a null sentence_date"
            )
        if sentence_date < data_start_date:
            raise FactIntegrityError(
                "judge_specific_eligible sentence fact predates the configured "
                "data start date"
            )
        by_pair.setdefault((str(charge_id), str(judge_id)), []).append(fact)

    rows: list[dict[str, object]] = []
    thin_pairs = 0
    run_date_max: date | None = None
    for (charge_id, judge_id), pair_facts in by_pair.items():
        sentencing_sample_size = len(pair_facts)
        is_thin = sentencing_sample_size < thin_min_sample
        if is_thin:
            thin_pairs += 1
        dates = [f["sentence_date"] for f in pair_facts]
        pair_start = min(dates)  # type: ignore[type-var]
        pair_end = max(dates)  # type: ignore[type-var]
        run_date_max = pair_end if run_date_max is None else max(run_date_max, pair_end)  # type: ignore[type-var]

        category_counts = Counter(
            str(f["sentencing_category_code"]) for f in pair_facts
        )
        for category_code, count in sorted(category_counts.items()):
            rows.append(
                {
                    "charge_id": charge_id,
                    "judge_id": judge_id,
                    "category_code": category_code,
                    "count": count,
                    "percentage": _percentage(count, sentencing_sample_size),
                    "sentencing_sample_size": sentencing_sample_size,
                    "date_range_start": pair_start,
                    "date_range_end": pair_end,
                    "is_thin_data": is_thin,
                    "taxonomy_version": taxonomy_version,
                }
            )

    report: dict[str, object] = {
        "judge_sentence_facts_included": len(included),
        "charge_judge_sentencing_pairs_covered": len(by_pair),
        "judge_sentencing_aggregates_generated": len(rows),
        "thin_data_sentencing_pairs": thin_pairs,
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


def _write_sentencing_aggregates(
    conn: psycopg.Connection, run_id: str, rows: Sequence[Mapping[str, object]]
) -> int:
    """Delete-and-reinsert this run's charge-sentencing aggregate rows (caller's tx).

    Same immutable-safe write path as :func:`_write_aggregates` (SD 4), targeting
    ``analytics.charge_sentencing_aggregates``. Does not commit; the caller owns the
    transaction boundary, so this write lands in the SAME transaction as the outcome
    write for one atomic run.
    """
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM analytics.charge_sentencing_aggregates "
            "WHERE aggregate_run_id = %s",
            (run_id,),
        )
        if not rows:
            return 0
        columns = ", ".join(_SENTENCING_INSERT_COLUMNS)
        placeholders = ", ".join(f"%({col})s" for col in _SENTENCING_INSERT_COLUMNS)
        cur.executemany(
            f"INSERT INTO analytics.charge_sentencing_aggregates ({columns}) "  # noqa: S608 - columns are module constants, never input
            f"VALUES ({placeholders})",
            [{**row, "aggregate_run_id": run_id} for row in rows],
        )
    return len(rows)


def _write_judge_outcome_aggregates(
    conn: psycopg.Connection, run_id: str, rows: Sequence[Mapping[str, object]]
) -> int:
    """Delete-and-reinsert this run's judge-outcome aggregate rows (caller's tx).

    Same immutable-safe write path as :func:`_write_aggregates` (SD 4), targeting
    ``analytics.judge_outcome_aggregates``. Does not commit; the caller owns the
    transaction boundary, so this write lands in the SAME transaction as the
    charge-only writes for one atomic run.
    """
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM analytics.judge_outcome_aggregates "
            "WHERE aggregate_run_id = %s",
            (run_id,),
        )
        if not rows:
            return 0
        columns = ", ".join(_JUDGE_INSERT_COLUMNS)
        placeholders = ", ".join(f"%({col})s" for col in _JUDGE_INSERT_COLUMNS)
        cur.executemany(
            f"INSERT INTO analytics.judge_outcome_aggregates ({columns}) "  # noqa: S608 - columns are module constants, never input
            f"VALUES ({placeholders})",
            [{**row, "aggregate_run_id": run_id} for row in rows],
        )
    return len(rows)


def _write_judge_sentencing_aggregates(
    conn: psycopg.Connection, run_id: str, rows: Sequence[Mapping[str, object]]
) -> int:
    """Delete-and-reinsert this run's judge-sentencing aggregate rows (caller's tx).

    Same immutable-safe write path as :func:`_write_aggregates` (SD 4), targeting
    ``analytics.judge_sentencing_aggregates``. Does not commit; the caller owns the
    transaction boundary, so this write lands in the SAME transaction as the other
    three passes for one atomic run.
    """
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM analytics.judge_sentencing_aggregates "
            "WHERE aggregate_run_id = %s",
            (run_id,),
        )
        if not rows:
            return 0
        columns = ", ".join(_JUDGE_SENTENCING_INSERT_COLUMNS)
        placeholders = ", ".join(
            f"%({col})s" for col in _JUDGE_SENTENCING_INSERT_COLUMNS
        )
        cur.executemany(
            f"INSERT INTO analytics.judge_sentencing_aggregates ({columns}) "  # noqa: S608 - columns are module constants, never input
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
    sentencing_report: Mapping[str, object],
    judge_report: Mapping[str, object],
    judge_sentencing_report: Mapping[str, object],
    charges_outcomes_no_sentencing: int,
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
    # Sentencing pass (Task 26.2): independent denominator, same run and transaction.
    print(
        f"sentence_facts_loaded={sentencing_report['sentence_facts_loaded']} "
        f"sentence_facts_included={sentencing_report['sentence_facts_included']} "
        f"sentence_facts_excluded={sentencing_report['sentence_facts_excluded']}"
    )
    print("sentencing_excluded_by_reason:")
    for code, n in sentencing_report["sentencing_excluded_by_reason"].items():  # type: ignore[attr-defined]
        if n:
            print(f"  {code:34} {n}")
    print(
        f"charges_with_sentencing={sentencing_report['charges_with_sentencing']} "
        "sentencing_aggregates_generated="
        f"{sentencing_report['sentencing_aggregates_generated']}"
    )
    thin_sentencing = sentencing_report["thin_data_sentencing_charges"]
    print(
        f"thin_data_sentencing_charges={thin_sentencing} "
        f"({BELOW_MINIMUM_SAMPLE}; min_sample={thin_min_sample})"
    )
    print(f"charges_with_outcomes_no_sentencing={charges_outcomes_no_sentencing}")
    # Judge-specific outcome pass (Task 27.1): per-pair denominators, same run and
    # transaction. Counts and ids only — judge names never reach console output.
    print(
        "judge_outcome_aggregates_generated="
        f"{judge_report['judge_outcome_aggregates_generated']} "
        f"charge_judge_pairs_covered={judge_report['charge_judge_pairs_covered']}"
    )
    print(
        f"thin_data_pairs={judge_report['thin_data_pairs']} "
        f"({BELOW_MINIMUM_SAMPLE}; min_sample={thin_min_sample})"
    )
    # Judge-specific sentencing pass (Task 27.2): independent per-pair sentencing
    # denominators, same run and transaction. Counts and ids only — judge names
    # never reach console output.
    print(
        "judge_sentencing_aggregates_generated="
        f"{judge_sentencing_report['judge_sentencing_aggregates_generated']} "
        "charge_judge_sentencing_pairs_covered="
        f"{judge_sentencing_report['charge_judge_sentencing_pairs_covered']}"
    )
    thin_sentencing_pairs = judge_sentencing_report["thin_data_sentencing_pairs"]
    print(
        f"thin_data_sentencing_pairs={thin_sentencing_pairs} "
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
    """Generate charge-only AND judge-specific outcome and sentencing aggregates.

    All four aggregate populations are read from one build run and written under the
    SAME new run and the SAME write transaction (Tasks 26.2, 27.1, 27.2). Returns 0
    on a clean generated run, nonzero on a STOP (no completed build run / bad
    ``--build-run`` / fact-integrity violation) or a failed write.
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
    sentence_facts = _load_sentence_facts(conn, build_run_id)

    # All reads + both pure builds (including the fact-integrity STOP checks for BOTH
    # populations) happen BEFORE any write, so a STOP leaves no run row.
    try:
        rows, report = build_charge_outcome_aggregates(
            facts,
            data_start_date=data_start_date,
            thin_min_sample=thin_min_sample,
            taxonomy_version=taxonomy_version,
        )
        sentencing_rows, sentencing_report = build_charge_sentencing_aggregates(
            sentence_facts,
            data_start_date=data_start_date,
            thin_min_sample=thin_min_sample,
            taxonomy_version=taxonomy_version,
        )
        judge_rows, judge_report = build_judge_outcome_aggregates(
            facts,
            data_start_date=data_start_date,
            thin_min_sample=thin_min_sample,
            taxonomy_version=taxonomy_version,
        )
        judge_sentencing_rows, judge_sentencing_report = (
            build_judge_sentencing_aggregates(
                sentence_facts,
                data_start_date=data_start_date,
                thin_min_sample=thin_min_sample,
                taxonomy_version=taxonomy_version,
            )
        )
    except FactIntegrityError as exc:
        logger.error(
            "refusing to generate aggregates", extra={"reason": type(exc).__name__}
        )
        return 2

    # Charges with eligible outcomes but no eligible sentence facts (SD 6 — the normal
    # sentencing-unavailable case). Derived from the emitted rows, so neither pure
    # builder is touched to expose its internal grouping.
    outcome_charges = {row["charge_id"] for row in rows}
    sentencing_charges = {row["charge_id"] for row in sentencing_rows}
    charges_outcomes_no_sentencing = len(outcome_charges - sentencing_charges)

    # Run-level data range: the configured floor as start; the latest eligible date as
    # end, taken as the UNION envelope of all populations (outcome disposition dates,
    # sentence dates, and the judge-pair disposition/sentence dates — the judge maxes
    # are structurally subsets of their charge-only counterparts, included so the run
    # row covers everything it wrote even if that fact-layer invariant were ever
    # violated). The floor itself when the run has no eligible facts at all, keeping
    # the start <= end CHECK happy.
    date_maxes = [
        d
        for d in (
            report["data_range_end"],
            sentencing_report["data_range_end"],
            judge_report["data_range_end"],
            judge_sentencing_report["data_range_end"],
        )
        if d is not None
    ]
    data_range_end = max(date_maxes) if date_maxes else data_start_date  # type: ignore[type-var]

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
            _write_sentencing_aggregates(conn, run_id, sentencing_rows)
            _write_judge_outcome_aggregates(conn, run_id, judge_rows)
            _write_judge_sentencing_aggregates(conn, run_id, judge_sentencing_rows)
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
        sentencing_report=sentencing_report,
        judge_report=judge_report,
        judge_sentencing_report=judge_sentencing_report,
        charges_outcomes_no_sentencing=charges_outcomes_no_sentencing,
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
    """CLI entry: open the connection and run aggregate generation (all passes)."""
    from pipeline import db

    with db.connect(database_url) as conn:
        return generate_aggregates(
            conn,
            build_run_id=build_run_id,
            data_start_date=data_start_date,
            thin_min_sample=thin_min_sample,
            label=label,
        )
