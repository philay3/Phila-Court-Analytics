"""Aggregate + privacy validation over a generated, unpublished run (Task 28.1).

The validation step of the Sprint 6 lifecycle (SD 3 — generation, validation,
and publication are separate steps). ``pipeline validate-aggregates`` points
at a GENERATED run (``status='in_progress'``, ``published_at``/
``invalidated_at`` NULL — the 26.1 vocabulary mapping; no new status values,
no migration) and runs its check families over ALL NINE aggregate tables (the
four Sprint 6 tables plus the five Task 35.1 sentencing-index tables — the
index family adds the Scope C identities, the cross-population conviction
reconciliation, and the component-grain median checks enabled by the
persisted build-run id):

- Integrity per aggregate group/row: category counts sum to the stored
  sample size (one sample size per charge or charge+judge group);
  percentage/count alignment within ±0.005 (inclusive, ``Decimal`` — the
  exact envelope of correct 2-decimal rounding, pinning no rounding mode);
  sample size present; date range present, ``start >= DATA_START_DATE``
  (default 2025-01-01) and not inverted; taxonomy version and run id present.
- Baseline per SD 7: every judge-specific outcome aggregate's charge has a
  same-run charge-only outcome aggregate; every judge-specific sentencing
  aggregate's charge has a same-run charge-only sentencing counterpart.
- Privacy: every generated row (all columns, JSON-shaped) passes the
  ``@pca/shared`` forbidden-field scan via the Python port
  (``pipeline.forbidden_scan``), which loads the shared term artifact —
  never a hand-copied list.

Verdict (26.1 lifecycle mapping): any violation -> ``status='failed'`` —
terminal; the ``aggregate_runs_published_at_check`` DB constraint
(``published_at IS NULL OR status='completed'``) structurally blocks publish.
A clean pass -> ``status='completed'`` ("validated") with ``completed_at``
set. A fresh ``generate-aggregates`` always opens a NEW run row, so a failed
run is left as history, never reused or replaced in place.

Numbers discipline: nothing here pins a figure from any prior run —
validation operates on whatever run it is pointed at.

Console/log output is counts, fixed check codes, statuses, and hash-prefix
run ids only. A privacy violation's offending value is by definition suspect
and is NEVER printed or logged — only its check code and count.
``DATABASE_URL`` is read at the CLI boundary (21.3 pattern), never here.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row

from pipeline.conviction_family import CONVICTION_OUTCOME_CATEGORIES
from pipeline.forbidden_scan import ForbiddenTerms, scan_for_forbidden

logger = logging.getLogger("pipeline.aggregates.validate")

# --- Lifecycle status strings (26.1 adjudicated mapping; see generate.py) ---
RUN_STATUS_VALIDATED = "completed"
RUN_STATUS_FAILED = "failed"

# Statuses --run may target: a generated run, or an already-validated
# unpublished run (re-validation is idempotent). Failed runs are terminal and
# published/invalidated runs are immutable history — both refused.
VALIDATABLE_STATUSES = ("in_progress", "completed")

# Inclusive percentage/count alignment tolerance: numeric(5,2) storage means a
# correctly rounded percentage sits within 0.005 of the exact ratio.
PERCENTAGE_TOLERANCE = Decimal("0.005")

# The Task 35.1 index tables store numeric(4,1) percentages: the 1-decimal
# analogue of the same envelope.
PERCENTAGE_TOLERANCE_1DP = Decimal("0.05")

# --- Fixed check-code vocabulary (the only violation detail ever printed) ---
CHECK_COUNT_SUM_MISMATCH = "count_sum_mismatch"
CHECK_SAMPLE_SIZE_INCONSISTENT = "sample_size_inconsistent"
CHECK_PERCENTAGE_MISALIGNED = "percentage_misaligned"
CHECK_SAMPLE_SIZE_MISSING = "sample_size_missing"
CHECK_DATE_RANGE_MISSING = "date_range_missing"
CHECK_DATE_RANGE_BEFORE_WINDOW = "date_range_start_before_window"
CHECK_DATE_RANGE_INVERTED = "date_range_inverted"
CHECK_TAXONOMY_VERSION_MISSING = "taxonomy_version_missing"
CHECK_RUN_ID_MISMATCH = "run_id_mismatch"
CHECK_BASELINE_MISSING = "baseline_missing"
CHECK_PRIVACY_VIOLATION = "privacy_violation"

# --- Task 35.1 sentencing-index check codes ---
CHECK_WEDGE_IDENTITY_MISMATCH = "wedge_identity_mismatch"
CHECK_CATEGORY_COUNT_EXCEEDS_SENTENCED = "category_count_exceeds_sentenced"
CHECK_GRADE_MIX_SUM_MISMATCH = "grade_mix_sum_mismatch"
CHECK_SUMMARY_ROW_MISSING = "summary_row_missing"
CHECK_CONVICTION_RECONCILIATION_MISMATCH = "conviction_reconciliation_mismatch"
CHECK_MEDIAN_PRESENCE_MISMATCH = "median_presence_mismatch"
CHECK_MEDIAN_DAYS_INVALID = "median_days_invalid"
CHECK_COMPONENT_DURATION_INVALID = "component_duration_invalid"
CHECK_BUILD_RUN_ID_MISSING = "build_run_id_missing"

# (table, sample-size column, has judge_id) — the four generated populations.
AGGREGATE_TABLE_SPECS: tuple[tuple[str, str, bool], ...] = (
    ("charge_outcome_aggregates", "sample_size", False),
    ("charge_sentencing_aggregates", "sentencing_sample_size", False),
    ("judge_outcome_aggregates", "sample_size", True),
    ("judge_sentencing_aggregates", "sentencing_sample_size", True),
)

# The Task 35.1 conviction-grain index tables (validated by the index check
# family below, not by validate_table_rows — their shapes differ).
INDEX_TABLE_NAMES: tuple[str, ...] = (
    "charge_sentencing_index_summaries",
    "charge_sentencing_index_aggregates",
    "charge_conviction_grade_aggregates",
    "judge_sentencing_index_summaries",
    "judge_sentencing_index_aggregates",
)

# Print/report order over every validated table.
ALL_VALIDATED_TABLES: tuple[str, ...] = (
    tuple(spec[0] for spec in AGGREGATE_TABLE_SPECS) + INDEX_TABLE_NAMES
)


class NoGeneratedRunError(RuntimeError):
    """No generated (in_progress, unpublished) aggregate run exists (STOP)."""


class RunNotValidatableError(RuntimeError):
    """A ``--run`` id that is absent, failed, published, or invalidated (STOP)."""


def _as_decimal(value: object) -> Decimal:
    """Percentage column value as ``Decimal`` (psycopg numeric round-trip safe)."""
    return value if isinstance(value, Decimal) else Decimal(str(value))


def validate_table_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    sample_field: str,
    has_judge: bool,
    expected_run_id: str,
    data_start_date: object,
) -> Counter[str]:
    """Integrity checks over one table's rows for one run (pure; no DB).

    Row-level: run id matches the validated run; taxonomy version non-empty;
    sample size present (positive); date range present, not inverted, start
    >= ``data_start_date``; percentage within ``PERCENTAGE_TOLERANCE`` of
    ``count / sample``. Group-level (per charge, or charge+judge pair): one
    consistent sample size shared by every category row, and category counts
    summing exactly to it. Returns a check-code tally (counts only — safe to
    print).
    """
    violations: Counter[str] = Counter()
    groups: dict[tuple[str, ...], list[Mapping[str, object]]] = {}

    for row in rows:
        run_id = row.get("aggregate_run_id")
        if run_id is None or str(run_id) != expected_run_id:
            violations[CHECK_RUN_ID_MISMATCH] += 1

        taxonomy_version = row.get("taxonomy_version")
        if taxonomy_version is None or not str(taxonomy_version).strip():
            violations[CHECK_TAXONOMY_VERSION_MISSING] += 1

        sample = row.get(sample_field)
        sample_ok = isinstance(sample, int) and sample > 0
        if not sample_ok:
            violations[CHECK_SAMPLE_SIZE_MISSING] += 1

        start = row.get("date_range_start")
        end = row.get("date_range_end")
        if start is None or end is None:
            violations[CHECK_DATE_RANGE_MISSING] += 1
        else:
            if start < data_start_date:  # type: ignore[operator]
                violations[CHECK_DATE_RANGE_BEFORE_WINDOW] += 1
            if start > end:  # type: ignore[operator]
                violations[CHECK_DATE_RANGE_INVERTED] += 1

        if sample_ok:
            exact = Decimal(int(row["count"])) * 100 / Decimal(int(sample))  # type: ignore[call-overload]
            stored = _as_decimal(row["percentage"])
            if abs(stored - exact) > PERCENTAGE_TOLERANCE:
                violations[CHECK_PERCENTAGE_MISALIGNED] += 1

        group_key = (
            (str(row.get("charge_id")), str(row.get("judge_id")))
            if has_judge
            else (str(row.get("charge_id")),)
        )
        groups.setdefault(group_key, []).append(row)

    for group_rows in groups.values():
        samples = {row.get(sample_field) for row in group_rows}
        if len(samples) > 1:
            violations[CHECK_SAMPLE_SIZE_INCONSISTENT] += 1
            continue
        (sample,) = samples
        if not (isinstance(sample, int) and sample > 0):
            continue  # already tallied as sample_size_missing per row
        if sum(int(r["count"]) for r in group_rows) != sample:  # type: ignore[call-overload]
            violations[CHECK_COUNT_SUM_MISMATCH] += 1

    return violations


def validate_baseline(
    judge_rows: Sequence[Mapping[str, object]],
    baseline_rows: Sequence[Mapping[str, object]],
) -> Counter[str]:
    """SD-7 baseline check (pure; no DB): judge charges ⊆ charge-only charges.

    Both row sets must come from the SAME run and the SAME population
    (outcome vs outcome, sentencing vs sentencing). One ``baseline_missing``
    per distinct judge-covered charge with no charge-only counterpart.
    """
    baseline_charges = {str(row["charge_id"]) for row in baseline_rows}
    judge_charges = {str(row["charge_id"]) for row in judge_rows}
    missing = judge_charges - baseline_charges
    violations: Counter[str] = Counter()
    if missing:
        violations[CHECK_BASELINE_MISSING] = len(missing)
    return violations


def _cell_key(row: Mapping[str, object], *, judge_grain: bool) -> tuple[str, ...]:
    """The (charge[, judge]) grouping key shared by the index check family."""
    return (
        (str(row.get("charge_id")), str(row.get("judge_id")))
        if judge_grain
        else (str(row.get("charge_id")),)
    )


def validate_index_row_basics(
    rows: Sequence[Mapping[str, object]],
    *,
    expected_run_id: str,
    has_date_range: bool,
    data_start_date: object,
) -> Counter[str]:
    """Run-id / taxonomy / date-range checks over one index table (pure; no DB).

    The Task 35.1 analogue of the row-level slice of
    :func:`validate_table_rows` for the index tables' shapes (their count and
    percentage semantics are checked by the dedicated functions below).
    """
    violations: Counter[str] = Counter()
    for row in rows:
        run_id = row.get("aggregate_run_id")
        if run_id is None or str(run_id) != expected_run_id:
            violations[CHECK_RUN_ID_MISMATCH] += 1
        taxonomy_version = row.get("taxonomy_version")
        if taxonomy_version is None or not str(taxonomy_version).strip():
            violations[CHECK_TAXONOMY_VERSION_MISSING] += 1
        if has_date_range:
            start = row.get("date_range_start")
            end = row.get("date_range_end")
            if start is None or end is None:
                violations[CHECK_DATE_RANGE_MISSING] += 1
            else:
                if start < data_start_date:  # type: ignore[operator]
                    violations[CHECK_DATE_RANGE_BEFORE_WINDOW] += 1
                if start > end:  # type: ignore[operator]
                    violations[CHECK_DATE_RANGE_INVERTED] += 1
    return violations


def _percentage_misaligned_1dp(stored: object, count: int, denominator: int) -> bool:
    """True when a numeric(4,1) percentage is outside the 1-decimal envelope."""
    exact = Decimal(count) * 100 / Decimal(denominator)
    return abs(_as_decimal(stored) - exact) > PERCENTAGE_TOLERANCE_1DP


def validate_index_summaries(
    summary_rows: Sequence[Mapping[str, object]],
) -> Counter[str]:
    """Summary-row identities (pure; no DB): Scope C count/percentage checks.

    ``sentenced + wedge = convictions`` and the wedge percentage consistent
    with its counts within 1-decimal rounding. Structural bounds (convictions
    > 0, non-negative counts) are DB CHECKs and not re-tallied here.
    """
    violations: Counter[str] = Counter()
    for row in summary_rows:
        convictions = int(row["convictions"])  # type: ignore[call-overload]
        sentenced = int(row["sentenced_convictions"])  # type: ignore[call-overload]
        wedge = int(row["wedge_count"])  # type: ignore[call-overload]
        if sentenced + wedge != convictions:
            violations[CHECK_WEDGE_IDENTITY_MISMATCH] += 1
        if convictions > 0 and _percentage_misaligned_1dp(
            row["wedge_percentage"], wedge, convictions
        ):
            violations[CHECK_PERCENTAGE_MISALIGNED] += 1
    return violations


def validate_index_categories(
    category_rows: Sequence[Mapping[str, object]],
    summary_rows: Sequence[Mapping[str, object]],
    *,
    judge_grain: bool,
) -> Counter[str]:
    """Category-row identities against their cell summaries (pure; no DB).

    Every category row needs a same-run summary row for its cell; conviction
    count <= the cell's sentenced convictions; percentage consistent with
    count / sentenced within 1-decimal rounding; the three duration columns
    all-present-or-all-null, day values non-negative and min <= max. (Whether
    duration columns SHOULD be present is the component-grain check in
    :func:`validate_index_against_facts` — this function checks internal
    consistency only.)
    """
    violations: Counter[str] = Counter()
    summaries = {_cell_key(row, judge_grain=judge_grain): row for row in summary_rows}
    for row in category_rows:
        summary = summaries.get(_cell_key(row, judge_grain=judge_grain))
        count = int(row["conviction_count"])  # type: ignore[call-overload]
        if summary is None:
            violations[CHECK_SUMMARY_ROW_MISSING] += 1
        else:
            sentenced = int(summary["sentenced_convictions"])  # type: ignore[call-overload]
            if count > sentenced:
                violations[CHECK_CATEGORY_COUNT_EXCEEDS_SENTENCED] += 1
            if sentenced > 0 and _percentage_misaligned_1dp(
                row["percentage_of_sentenced"], count, sentenced
            ):
                violations[CHECK_PERCENTAGE_MISALIGNED] += 1
        median_min = row.get("median_min_days")
        median_max = row.get("median_max_days")
        min_assumed_pct = row.get("min_assumed_percentage")
        nulls = {median_min is None, median_max is None, min_assumed_pct is None}
        if len(nulls) > 1:
            violations[CHECK_MEDIAN_DAYS_INVALID] += 1
        elif median_min is not None and (
            _as_decimal(median_min) < 0
            or _as_decimal(median_min) > _as_decimal(median_max)
        ):
            violations[CHECK_MEDIAN_DAYS_INVALID] += 1
    return violations


def validate_grade_mix(
    grade_rows: Sequence[Mapping[str, object]],
    summary_rows: Sequence[Mapping[str, object]],
) -> Counter[str]:
    """Grade-mix identities (pure; no DB; charge grain only per ruling 2).

    Every grade row needs its cell's summary row; per cell the grade counts
    sum exactly to the summary's convictions; each percentage consistent with
    count / convictions within 1-decimal rounding.
    """
    violations: Counter[str] = Counter()
    summaries = {_cell_key(row, judge_grain=False): row for row in summary_rows}
    by_cell: dict[tuple[str, ...], list[Mapping[str, object]]] = {}
    for row in grade_rows:
        cell = _cell_key(row, judge_grain=False)
        summary = summaries.get(cell)
        if summary is None:
            violations[CHECK_SUMMARY_ROW_MISSING] += 1
            continue
        by_cell.setdefault(cell, []).append(row)
        convictions = int(summary["convictions"])  # type: ignore[call-overload]
        if convictions > 0 and _percentage_misaligned_1dp(
            row["percentage_of_convictions"],
            int(row["conviction_count"]),  # type: ignore[call-overload]
            convictions,
        ):
            violations[CHECK_PERCENTAGE_MISALIGNED] += 1
    for cell, cell_rows in by_cell.items():
        total = sum(int(r["conviction_count"]) for r in cell_rows)  # type: ignore[call-overload]
        if total != int(summaries[cell]["convictions"]):  # type: ignore[call-overload]
            violations[CHECK_GRADE_MIX_SUM_MISMATCH] += 1
    return violations


def validate_conviction_reconciliation(
    summary_rows: Sequence[Mapping[str, object]],
    outcome_rows: Sequence[Mapping[str, object]],
    *,
    judge_grain: bool,
) -> Counter[str]:
    """Cross-population reconciliation (pure; no DB) — Scope C.

    Per cell, the index summary's ``convictions`` must equal the SAME run's
    outcome-aggregate conviction-family total (via the named constant). The
    check runs over the UNION of cells: a summary with no outcome counterpart,
    or conviction-family outcome counts with no summary, is the same
    contradiction — the two populations may never disagree on a page.
    """
    violations: Counter[str] = Counter()
    family_totals: dict[tuple[str, ...], int] = {}
    for row in outcome_rows:
        if str(row.get("category_code")) in CONVICTION_OUTCOME_CATEGORIES:
            cell = _cell_key(row, judge_grain=judge_grain)
            family_totals[cell] = family_totals.get(cell, 0) + int(row["count"])  # type: ignore[call-overload]
    summary_totals = {
        _cell_key(row, judge_grain=judge_grain): int(row["convictions"])  # type: ignore[call-overload]
        for row in summary_rows
    }
    for cell in set(family_totals) | set(summary_totals):
        if family_totals.get(cell, 0) != summary_totals.get(cell, 0):
            violations[CHECK_CONVICTION_RECONCILIATION_MISMATCH] += 1
    return violations


def validate_index_against_facts(
    category_rows: Sequence[Mapping[str, object]],
    anchor_facts: Sequence[Mapping[str, object]],
    component_facts: Sequence[Mapping[str, object]],
    *,
    judge_grain: bool,
) -> Counter[str]:
    """Component-grain checks against the run's fact build (pure; no DB).

    Enabled by the persisted ``build_run_id``: medians must be present iff the
    cell's category has >= 1 duration-bearing public-eligible component, and
    every component feeding a cell must satisfy ``min <= max``, non-negative,
    never half-present. ``anchor_facts`` are the build's conviction-family
    outcome facts (eligibility READ from the flags, family via the named
    constant); ``component_facts`` its public-eligible sentence components.
    """
    violations: Counter[str] = Counter()
    eligibility_key = "judge_specific_eligible" if judge_grain else "public_eligible"

    anchor_cells: dict[str, tuple[str, ...]] = {}
    for fact in anchor_facts:
        if not fact[eligibility_key]:
            continue
        if str(fact["outcome_category_code"]) not in CONVICTION_OUTCOME_CATEGORIES:
            continue
        charge_id = fact["normalized_charge_id"]
        judge_id = fact["normalized_judge_id"]
        if charge_id is None or (judge_grain and judge_id is None):
            continue  # generator-side STOP territory; nothing to anchor here
        anchor_cells[str(fact["id"])] = (
            (str(charge_id), str(judge_id)) if judge_grain else (str(charge_id),)
        )

    duration_bearing: set[tuple[tuple[str, ...], str]] = set()
    for component in component_facts:
        cell = anchor_cells.get(str(component["charge_outcome_id"]))
        if cell is None:
            continue  # not feeding this grain's population
        min_days = component["min_days"]
        max_days = component["max_days"]
        if (min_days is None) != (max_days is None):
            violations[CHECK_COMPONENT_DURATION_INVALID] += 1
            continue
        if min_days is not None:
            if int(min_days) < 0 or int(min_days) > int(max_days):  # type: ignore[call-overload]
                violations[CHECK_COMPONENT_DURATION_INVALID] += 1
                continue
            duration_bearing.add((cell, str(component["sentencing_category_code"])))

    for row in category_rows:
        cell = _cell_key(row, judge_grain=judge_grain)
        expected = (cell, str(row.get("category_code"))) in duration_bearing
        stored = row.get("median_min_days") is not None
        if expected != stored:
            violations[CHECK_MEDIAN_PRESENCE_MISMATCH] += 1
    return violations


def scannable_row(row: Mapping[str, object]) -> dict[str, object]:
    """An aggregate row as a JSON-shaped dict for the forbidden-field scan.

    UUIDs, dates, timestamps, and numerics are stringified so every column —
    not just the text ones — passes under the value patterns; keys pass under
    the stem check as-is.
    """
    scannable: dict[str, object] = {}
    for key, value in row.items():
        if value is None or isinstance(value, bool | int | str):
            scannable[key] = value
        elif isinstance(value, datetime | Decimal):
            scannable[key] = str(value)
        else:
            # date, UUID, and any other driver type: their canonical str form.
            scannable[key] = (
                value.isoformat() if hasattr(value, "isoformat") else str(value)
            )
    return scannable


def validate_privacy(
    rows: Sequence[Mapping[str, object]], terms: ForbiddenTerms
) -> Counter[str]:
    """Forbidden-field scan over every row (pure; no DB). Counts only.

    The violations' offending values are deliberately discarded here:
    callers get a tally they can print without ever surfacing the content
    that failed the gate.
    """
    violations: Counter[str] = Counter()
    for row in rows:
        hits = scan_for_forbidden(scannable_row(row), terms)
        if hits:
            violations[CHECK_PRIVACY_VIOLATION] += len(hits)
    return violations


def _resolve_run(
    conn: psycopg.Connection, run_id: str | None
) -> tuple[str, str | None]:
    """Resolve the run to validate: ``(run id, its persisted build_run_id)``.

    Default: the latest generated run (``in_progress``, unpublished).
    ``--run`` forces a specific id, which must be unpublished, uninvalidated,
    and ``in_progress`` or ``completed`` (re-validation); ``failed`` runs are
    terminal and refused.

    The build-run id (Task 35.1) feeds the component-grain index checks; a
    NULL is tallied as ``build_run_id_missing`` by the caller, never resolved
    to a default — validation checks what the run recorded, nothing else.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        if run_id is not None:
            cur.execute(
                "SELECT status, published_at, invalidated_at, build_run_id "
                "FROM analytics.aggregate_runs WHERE id = %s",
                (run_id,),
            )
            row = cur.fetchone()
            if (
                row is None
                or row["status"] not in VALIDATABLE_STATUSES
                or row["published_at"] is not None
                or row["invalidated_at"] is not None
            ):
                raise RunNotValidatableError(
                    "requested --run is not a validatable (generated or "
                    "validated, unpublished) aggregate run"
                )
            build_run_id = row["build_run_id"]
            return run_id, (str(build_run_id) if build_run_id is not None else None)
        cur.execute(
            "SELECT id, build_run_id FROM analytics.aggregate_runs "
            "WHERE status = 'in_progress' AND published_at IS NULL "
            "AND invalidated_at IS NULL "
            "ORDER BY started_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        if row is None:
            raise NoGeneratedRunError(
                "no generated (unpublished) aggregate run exists; run "
                "`pipeline generate-aggregates` first"
            )
        build_run_id = row["build_run_id"]
        return str(row["id"]), (str(build_run_id) if build_run_id is not None else None)


def _load_conviction_anchor_facts(
    conn: psycopg.Connection, build_run_id: str
) -> list[dict[str, object]]:
    """The build's outcome facts as index anchors (eligibility read, not recomputed)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, normalized_charge_id, normalized_judge_id, "
            "outcome_category_code, public_eligible, judge_specific_eligible "
            "FROM fact.charge_outcomes WHERE build_run_id = %s",
            (build_run_id,),
        )
        return list(cur.fetchall())


def _load_eligible_components(
    conn: psycopg.Connection, build_run_id: str
) -> list[dict[str, object]]:
    """The build's public-eligible sentence components (duration columns only)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT charge_outcome_id, sentencing_category_code, "
            "min_days, max_days "
            "FROM fact.charge_sentences "
            "WHERE build_run_id = %s AND public_eligible",
            (build_run_id,),
        )
        return list(cur.fetchall())


def _load_table_rows(
    conn: psycopg.Connection, table: str, run_id: str
) -> list[dict[str, object]]:
    """Every generated row in one aggregate table for the run being validated."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT * FROM analytics.{table} WHERE aggregate_run_id = %s",  # noqa: S608 - table names are module constants, never input
            (run_id,),
        )
        return list(cur.fetchall())


def _mark_validated(conn: psycopg.Connection, run_id: str) -> None:
    """Set ``completed`` ("validated") + ``completed_at`` (its CHECK requires it)."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE analytics.aggregate_runs "
            "SET status = %s, completed_at = %s WHERE id = %s",
            (RUN_STATUS_VALIDATED, datetime.now(UTC), run_id),
        )


def _mark_failed(conn: psycopg.Connection, run_id: str) -> None:
    """Set ``failed`` — terminal; the published_at CHECK then blocks publish."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE analytics.aggregate_runs SET status = %s WHERE id = %s",
            (RUN_STATUS_FAILED, run_id),
        )


def validate_aggregates(
    conn: psycopg.Connection,
    *,
    run_id: str | None,
    data_start_date: object,
    terms: ForbiddenTerms,
) -> int:
    """Validate one generated run across all four tables and set its verdict.

    Returns 0 on a clean pass (run marked ``completed``), 1 on validation
    failure (run marked ``failed``; publish structurally blocked), 2 on a
    STOP (no run to validate / non-validatable ``--run``).
    """
    try:
        resolved_run_id, build_run_id = _resolve_run(conn, run_id)
    except (NoGeneratedRunError, RunNotValidatableError) as exc:
        logger.error(
            "refusing to validate aggregates", extra={"reason": type(exc).__name__}
        )
        return 2

    rows_checked: dict[str, int] = {}
    violations_by_table: dict[str, Counter[str]] = {}
    loaded: dict[str, list[dict[str, object]]] = {}

    for table, sample_field, has_judge in AGGREGATE_TABLE_SPECS:
        rows = _load_table_rows(conn, table, resolved_run_id)
        loaded[table] = rows
        rows_checked[table] = len(rows)
        table_violations = validate_table_rows(
            rows,
            sample_field=sample_field,
            has_judge=has_judge,
            expected_run_id=resolved_run_id,
            data_start_date=data_start_date,
        )
        table_violations += validate_privacy(rows, terms)
        violations_by_table[table] = table_violations

    # Baseline (SD 7): judge-specific populations against their same-run
    # charge-only counterparts, attributed to the judge tables.
    violations_by_table["judge_outcome_aggregates"] += validate_baseline(
        loaded["judge_outcome_aggregates"], loaded["charge_outcome_aggregates"]
    )
    violations_by_table["judge_sentencing_aggregates"] += validate_baseline(
        loaded["judge_sentencing_aggregates"], loaded["charge_sentencing_aggregates"]
    )

    # --- Task 35.1: the conviction-grain sentencing-index population. ---
    for table in INDEX_TABLE_NAMES:
        rows = _load_table_rows(conn, table, resolved_run_id)
        loaded[table] = rows
        rows_checked[table] = len(rows)
        violations_by_table[table] = validate_index_row_basics(
            rows,
            expected_run_id=resolved_run_id,
            has_date_range=table.endswith("summaries"),
            data_start_date=data_start_date,
        ) + validate_privacy(rows, terms)

    violations_by_table["charge_sentencing_index_summaries"] += (
        validate_index_summaries(loaded["charge_sentencing_index_summaries"])
    )
    violations_by_table["judge_sentencing_index_summaries"] += validate_index_summaries(
        loaded["judge_sentencing_index_summaries"]
    )
    violations_by_table["charge_sentencing_index_aggregates"] += (
        validate_index_categories(
            loaded["charge_sentencing_index_aggregates"],
            loaded["charge_sentencing_index_summaries"],
            judge_grain=False,
        )
    )
    violations_by_table["judge_sentencing_index_aggregates"] += (
        validate_index_categories(
            loaded["judge_sentencing_index_aggregates"],
            loaded["judge_sentencing_index_summaries"],
            judge_grain=True,
        )
    )
    violations_by_table["charge_conviction_grade_aggregates"] += validate_grade_mix(
        loaded["charge_conviction_grade_aggregates"],
        loaded["charge_sentencing_index_summaries"],
    )
    # Cross-population reconciliation (Scope C): the index and outcome
    # populations may never contradict each other on the same page.
    violations_by_table["charge_sentencing_index_summaries"] += (
        validate_conviction_reconciliation(
            loaded["charge_sentencing_index_summaries"],
            loaded["charge_outcome_aggregates"],
            judge_grain=False,
        )
    )
    violations_by_table["judge_sentencing_index_summaries"] += (
        validate_conviction_reconciliation(
            loaded["judge_sentencing_index_summaries"],
            loaded["judge_outcome_aggregates"],
            judge_grain=True,
        )
    )
    # Component-grain checks, enabled by the persisted build-run id. A NULL
    # build_run_id on a run that generated index rows is itself a violation
    # (Scope C: build-run id present on the run row).
    if build_run_id is None:
        violations_by_table["charge_sentencing_index_summaries"][
            CHECK_BUILD_RUN_ID_MISSING
        ] += 1
    else:
        anchor_facts = _load_conviction_anchor_facts(conn, build_run_id)
        component_facts = _load_eligible_components(conn, build_run_id)
        violations_by_table["charge_sentencing_index_aggregates"] += (
            validate_index_against_facts(
                loaded["charge_sentencing_index_aggregates"],
                anchor_facts,
                component_facts,
                judge_grain=False,
            )
        )
        violations_by_table["judge_sentencing_index_aggregates"] += (
            validate_index_against_facts(
                loaded["judge_sentencing_index_aggregates"],
                anchor_facts,
                component_facts,
                judge_grain=True,
            )
        )

    total_violations = sum(
        sum(counter.values()) for counter in violations_by_table.values()
    )
    verdict = "failed" if total_violations else "validated"

    with conn.transaction():
        if total_violations:
            _mark_failed(conn, resolved_run_id)
        else:
            _mark_validated(conn, resolved_run_id)

    print(f"validate-aggregates run={resolved_run_id[:16]} verdict={verdict}")
    for table in ALL_VALIDATED_TABLES:
        table_total = sum(violations_by_table[table].values())
        print(f"{table}: rows_checked={rows_checked[table]} violations={table_total}")
    if total_violations:
        print("violations_by_check:")
        for table in ALL_VALIDATED_TABLES:
            for code, n in sorted(violations_by_table[table].items()):
                print(f"  {table}.{code} {n}")
        print(
            f"run marked {RUN_STATUS_FAILED} (publish blocked); "
            "re-run `pipeline generate-aggregates` to open a new run"
        )
        logger.error(
            "aggregate validation failed",
            extra={"run": resolved_run_id[:16], "violations": total_violations},
        )
        return 1

    print(f"run marked {RUN_STATUS_VALIDATED} (validated)")
    logger.info("aggregate validation passed", extra={"run": resolved_run_id[:16]})
    return 0


def run_validate_aggregates(
    database_url: str,
    *,
    run_id: str | None,
    data_start_date: object,
) -> int:
    """CLI entry: load the shared term artifact, connect, and validate.

    A missing or degenerate forbidden-field artifact is a STOP (exit 2) —
    validation without the privacy gate must never look like a pass.
    """
    from pipeline import db
    from pipeline.forbidden_scan import load_forbidden_terms

    try:
        terms = load_forbidden_terms()
    except (FileNotFoundError, ValueError) as exc:
        logger.error(
            "refusing to validate aggregates without the shared forbidden-field "
            "artifact; run `pnpm generate`",
            extra={"reason": type(exc).__name__},
        )
        return 2

    with db.connect(database_url) as conn:
        return validate_aggregates(
            conn,
            run_id=run_id,
            data_start_date=data_start_date,
            terms=terms,
        )
