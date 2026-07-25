"""Charge-volume funnel generation (Phase 36) — deduplicated at the source.

One generator pass over ``parsed.charges`` producing the
``analytics.charge_volume_aggregates`` population: one row per (run, charge)
with the charge's JOURNEY counts. The double-count fix is upstream in the data
(operator ruling 2026-07-25): an MC held charge traced to its CP continuation
carries ``superseded_by_charge_id`` and is NOT counted — its journey is
counted once, on the CP side, wherever that side currently stands. This module
simply filters ``superseded`` rows and tallies the rest.

Universe: charges on dockets filed on/after the filed-date floor (2025-01-01,
NULL filed_date fail-closed) — the population the public coverage language
already claims. A superseded MC row's CP twin is structurally in-universe
whenever the MC row is (a CP case is filed at/after the bind-over, never
before the MC filing), so folding never drops a journey from the universe.

Bucket split per charge row (the 36.0 R2 arms, unchanged):

- ``outcomes_recorded``  — terminally disposed AND ``public_eligible`` per
  :func:`pipeline.facts.outcome_facts.evaluate_outcome_eligibility` (judge
  attribution stubbed to none — it gates the judge grain only).
- ``held_for_court``     — a held-form disposition (the 22.4 mapper is the
  single authority) with NO supersession pointer: the untraced remainder,
  including CP cases not yet filed or not yet collected (time lag — expected
  to shrink on refreshes, never a defect).
- ``still_pending``      — null disposition.
- ``disposed_excluded``  — disposed, not fact-eligible (window/floor policy,
  review, unmapped disposition).

Attribution is the REAL matcher over (statute, offense) — rows that match no
roster identity (unmatched/ambiguous) are invisible to any per-charge page and
are reported as the corpus-level tail, never guessed onto a page.

The per-row closure identity holds by construction and is asserted here, is a
stored CHECK on the table, and is re-asserted by validation (which also owns
the cross-table identities: outcomes_recorded == the charge's outcome
aggregate sample size, and the fact-side sum over the stamped build run).
Nothing blocks at generate time beyond structural integrity — a
funnel-vs-percentages disagreement is validation's job, where it blocks
publish (the R4/R5 drift posture).

Console/log output: counts and fixed labels only — never docket numbers, raw
charge text, or defendant data.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date

import psycopg
from psycopg.rows import dict_row

from pipeline.facts.judge_attribution import METHOD_NONE, AttributionResult
from pipeline.facts.outcome_facts import (
    FILED_DATE_FLOOR_DEFAULT,
    PUBLIC_CHARGE_MATCH_METHODS,
    evaluate_outcome_eligibility,
)
from pipeline.normalization.charge_matcher import ChargeMatcher
from pipeline.normalization.outcome_mapper import OutcomeMapper

_VOLUME_INSERT_COLUMNS = (
    "aggregate_run_id",
    "charge_id",
    "charges_seen",
    "outcomes_recorded",
    "held_for_court",
    "still_pending",
    "disposed_excluded",
    "held_superseded",
    "taxonomy_version",
)

# The judge-attribution stub for eligibility evaluation: attribution gates
# judge_specific_eligible only, which the volume pass never reads.
_ATTRIBUTION_STUB = AttributionResult(normalized_judge_id=None, method=METHOD_NONE)


class VolumeIntegrityError(RuntimeError):
    """A computed volume row violates its own closure identity (STOP)."""


def load_volume_corpus(conn: psycopg.Connection) -> list[dict[str, object]]:
    """Every parsed charge with its docket's filed date and supersession flag."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT c.id, c.docket_id, c.sequence, c.statute, c.offense,
                   c.disposition_raw, c.disposition_date,
                   (c.superseded_by_charge_id IS NOT NULL) AS superseded,
                   d.filed_date
            FROM parsed.charges c
            JOIN parsed.dockets d ON d.id = c.docket_id
            ORDER BY c.docket_id, c.sequence, c.id
            """
        )
        return [dict(row) for row in cur.fetchall()]


def load_charge_warning_codes(
    conn: psycopg.Connection,
) -> dict[tuple[str, int], list[str]]:
    """Charge-grain warning codes keyed by (docket_id, sequence)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT docket_id, charge_sequence, code FROM parsed.warnings "
            "WHERE charge_sequence IS NOT NULL"
        )
        warnings: dict[tuple[str, int], list[str]] = {}
        for docket_id, charge_sequence, code in cur.fetchall():
            warnings.setdefault((str(docket_id), int(charge_sequence)), []).append(
                str(code)
            )
        return warnings


def build_charge_volume_rows(
    corpus: Sequence[Mapping[str, object]],
    warnings: Mapping[tuple[str, int], list[str]],
    *,
    matcher: ChargeMatcher,
    mapper: OutcomeMapper,
    taxonomy_version: str,
    filed_date_floor: date = FILED_DATE_FLOOR_DEFAULT,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Build every charge-volume row from the parsed corpus (pure; no DB).

    Returns ``(rows, report)``. Rows exist only for roster identities with at
    least one counted journey (``charges_seen > 0`` — the stored CHECK); an
    identity whose every in-universe row folded into CP twins produces no row
    and is tallied in the report instead.
    """
    seen: Counter[str] = Counter()
    outcomes: Counter[str] = Counter()
    held: Counter[str] = Counter()
    pending: Counter[str] = Counter()
    excluded: Counter[str] = Counter()
    superseded_by_identity: Counter[str] = Counter()

    report_counts = {
        "rows_total": 0,
        "rows_pre_floor": 0,
        "rows_in_universe": 0,
        "superseded_folded": 0,
        "superseded_not_held_anomaly": 0,
        "unmatched_rows": 0,
        "ambiguous_rows": 0,
        "outcomes_total": 0,
        "held_total": 0,
        "pending_total": 0,
        "excluded_total": 0,
    }

    for row in corpus:
        report_counts["rows_total"] += 1
        filed = row["filed_date"]
        if filed is None or filed < filed_date_floor:  # type: ignore[operator]
            report_counts["rows_pre_floor"] += 1
            continue
        report_counts["rows_in_universe"] += 1

        disposition_raw = row["disposition_raw"]
        outcome_result = mapper.map(disposition_raw)  # type: ignore[arg-type]
        is_held_form = disposition_raw is not None and outcome_result is None

        match = matcher.match(
            statute=row["statute"],  # type: ignore[arg-type]
            offense=row["offense"],  # type: ignore[arg-type]
        )
        clean_identity = (
            str(match.normalized_id)
            if match.match_method in PUBLIC_CHARGE_MATCH_METHODS
            and match.normalized_id is not None
            else None
        )

        # A superseded row's journey is counted on its CP side — fold it out.
        # The derivation only points held-form rows; a non-held superseded row
        # means the corpus moved under a stale derivation, so it is counted
        # normally (fail-open to visible counting) and tallied as an anomaly.
        if row["superseded"]:
            if is_held_form:
                report_counts["superseded_folded"] += 1
                if clean_identity is not None:
                    superseded_by_identity[clean_identity] += 1
                continue
            report_counts["superseded_not_held_anomaly"] += 1

        if match.match_method == "unmatched":
            report_counts["unmatched_rows"] += 1
        elif match.match_method == "ambiguous":
            report_counts["ambiguous_rows"] += 1

        if outcome_result is None:
            if disposition_raw is None:
                report_counts["pending_total"] += 1
                if clean_identity is not None:
                    seen[clean_identity] += 1
                    pending[clean_identity] += 1
            else:
                report_counts["held_total"] += 1
                if clean_identity is not None:
                    seen[clean_identity] += 1
                    held[clean_identity] += 1
            continue

        eligibility = evaluate_outcome_eligibility(
            disposition_date=row["disposition_date"],  # type: ignore[arg-type]
            filed_date=filed,  # type: ignore[arg-type]
            filed_date_floor=filed_date_floor,
            charge_result=match,
            outcome_result=outcome_result,
            attribution=_ATTRIBUTION_STUB,
            charge_warning_codes=warnings.get(
                (str(row["docket_id"]), int(row["sequence"])),
                [],  # type: ignore[arg-type]
            ),
        )
        if eligibility.public_eligible:
            report_counts["outcomes_total"] += 1
            if clean_identity is not None:
                seen[clean_identity] += 1
                outcomes[clean_identity] += 1
        else:
            report_counts["excluded_total"] += 1
            if clean_identity is not None:
                seen[clean_identity] += 1
                excluded[clean_identity] += 1

    rows: list[dict[str, object]] = []
    for charge_id in sorted(seen):
        charges_seen = seen[charge_id]
        row_out = {
            "charge_id": charge_id,
            "charges_seen": charges_seen,
            "outcomes_recorded": outcomes.get(charge_id, 0),
            "held_for_court": held.get(charge_id, 0),
            "still_pending": pending.get(charge_id, 0),
            "disposed_excluded": excluded.get(charge_id, 0),
            "held_superseded": superseded_by_identity.get(charge_id, 0),
            "taxonomy_version": taxonomy_version,
        }
        closure = (
            row_out["outcomes_recorded"]
            + row_out["held_for_court"]
            + row_out["still_pending"]
            + row_out["disposed_excluded"]
        )
        if closure != charges_seen:
            raise VolumeIntegrityError(
                "charge-volume closure identity failed pre-write"
            )
        rows.append(row_out)

    identities_fully_superseded = sum(
        1 for charge_id in superseded_by_identity if charge_id not in seen
    )

    report: dict[str, object] = {
        **report_counts,
        "volume_rows": len(rows),
        "identities_with_journeys": len(seen),
        "identities_fully_superseded": identities_fully_superseded,
    }
    return rows, report


def write_volume_rows(
    conn: psycopg.Connection, run_id: str, rows: Sequence[Mapping[str, object]]
) -> int:
    """Delete-and-reinsert this run's charge-volume rows (caller's tx; SD 4)."""
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM analytics.charge_volume_aggregates "
            "WHERE aggregate_run_id = %s",
            (run_id,),
        )
        if not rows:
            return 0
        columns = ", ".join(_VOLUME_INSERT_COLUMNS)
        placeholders = ", ".join(f"%({col})s" for col in _VOLUME_INSERT_COLUMNS)
        cur.executemany(
            f"INSERT INTO analytics.charge_volume_aggregates ({columns}) "  # noqa: S608 - columns are module constants, never input
            f"VALUES ({placeholders})",
            [{**row, "aggregate_run_id": run_id} for row in rows],
        )
    return len(rows)


def preview_by_slug(
    rows: Sequence[Mapping[str, object]],
    slug_by_id: Mapping[str, str],
    *,
    top: int = 20,
) -> list[str]:
    """Counts-only per-slug preview lines (backfill verification aid).

    Slugs are public roster identifiers; every figure is an aggregate count.
    Sorted by folded volume so the dedupe's biggest movers lead.
    """

    def slug_for(row: Mapping[str, object]) -> str:
        return slug_by_id.get(str(row["charge_id"]), str(row["charge_id"])[:8])

    ranked = sorted(
        rows,
        key=lambda r: (-int(r["held_superseded"]), slug_for(r)),  # type: ignore[arg-type]
    )
    lines = []
    for row in ranked[:top]:
        lines.append(
            f"  {slug_for(row)}: seen={row['charges_seen']} "
            f"outcomes={row['outcomes_recorded']} held={row['held_for_court']} "
            f"pending={row['still_pending']} excluded={row['disposed_excluded']} "
            f"folded_into_cp={row['held_superseded']}"
        )
    return lines
