"""Tableau extract builder — de-identified analytic CSVs from the live run.

Builds a small star schema (dimension + fact + diagnostic tables) sized for
Tableau Desktop/Public from the currently PUBLISHED aggregate run and its
stamped fact build run. Four viz families are covered:

1. judge x charge heatmap        -> fact_judge_charge_matrix / _outcomes_long
2. charge funnel over time       -> fact_charge_journeys / agg_charge_funnel_monthly
3. data-quality diagnostics      -> dq_*
4. case-duration distributions   -> fact_case_durations / agg_duration_percentiles

Nothing this script writes goes inside the repo tree. The default output root
is ``~/court-data/tableau/`` (rule 1); the script REFUSES to write into a git
working tree. Output is split into two directories with different disclosure
postures:

- ``publish-safe/`` — aggregate grain only, small cells flagged, no row-level
  court records. Safe to attach to a workbook that might reach Tableau Public.
- ``internal-only/`` — charge-journey and case grain. No docket numbers, no
  defendant hashes, no raw docket text: identifiers are truncated random UUIDs
  from the DB, which carry nothing derived from a docket. Still row-level court
  data, so it stays off any public workbook.

Authorities are REUSED, never re-implemented: the charge identity comes from
``ChargeMatcher``, the disposition mapping from ``OutcomeMapper``, and public
eligibility from ``evaluate_outcome_eligibility`` — the same three the
Phase 36 volume generator uses. The journey pass therefore reproduces
``analytics.charge_volume_aggregates`` exactly, and the script asserts that
reconciliation before it writes anything (``--skip-reconcile`` to override).

Console output is counts, fixed codes, and hash-prefix run ids only.
``DATABASE_URL`` is read at the process boundary and never logged.

Usage (from the repo root):

    cd services/pipeline && uv run python ../../scripts/export_tableau.py

    # options
    --out-root PATH     default ~/court-data/tableau
    --min-cell N        publish-safe suppression floor (default 10)
    --skip-reconcile    write even if the funnel disagrees with the run
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import os
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from pipeline.aggregates.volume import load_charge_warning_codes
from pipeline.conviction_family import CONVICTION_OUTCOME_CATEGORIES
from pipeline.facts.judge_attribution import METHOD_NONE, AttributionResult
from pipeline.facts.outcome_facts import (
    FILED_DATE_FLOOR_DEFAULT,
    PUBLIC_CHARGE_MATCH_METHODS,
    evaluate_outcome_eligibility,
)
from pipeline.normalization.charge_matcher import ChargeMatcher
from pipeline.normalization.charge_roster_loader import (
    load_charge_roster_from_connection,
)
from pipeline.normalization.outcome_mapper import OutcomeMapper, load_taxonomy_snapshot
from pipeline.warning_codes import SEVERITY as WARNING_SEVERITY

logger = logging.getLogger("export_tableau")

# The judge-attribution stub: attribution gates judge_specific_eligible only,
# which the journey pass reads off the fact row instead of recomputing.
_ATTRIBUTION_STUB = AttributionResult(normalized_judge_id=None, method=METHOD_NONE)

# Wilson score interval z for a 95% two-sided interval.
Z_95 = 1.959963984540054

# Publish-safe percentile cells below this n are dropped; heatmap cells below it
# keep their row but carry is_thin_data (the pipeline's own threshold, 10).
DEFAULT_MIN_CELL = 10

UNMATCHED_SLUG = "(unmatched)"
UNMATCHED_NAME = "Charge not on the roster"

# --- Charge grouping ---------------------------------------------------------
# A viz-friendly rollup of the 110-entry roster, derived MECHANICALLY from the
# public statute code: (title, chapter) -> label, where chapter is the section
# number's leading two digits (18 § 2702 -> ch. 27). Two documented section-level
# overrides move 18 § 907/908 (instruments of crime, offensive weapons) out of
# the statutory "inchoate crimes" chapter and in with weapons, where anyone
# reading a chart would look for them. Both roster entries with a null statute
# are mapped by slug. Nothing here is derived from docket content.
_TITLE18_CHAPTERS: dict[int, str] = {
    9: "Inchoate & Corrupt Organizations",
    25: "Homicide",
    27: "Assault & Threats",
    29: "Kidnapping & Restraint",
    31: "Sexual Offenses",
    33: "Property Damage & Arson",
    35: "Burglary & Trespass",
    37: "Robbery",
    39: "Theft",
    41: "Forgery & Fraud",
    43: "Offenses Against the Family",
    49: "Falsification & Witness Intimidation",
    51: "Obstructing Government Operations",
    55: "Disorderly Conduct & Public Order",
    61: "Firearms & Weapons",
    63: "Offenses Involving Minors",
    75: "Other Offenses (Title 18)",
    76: "Computer Offenses",
}

_TITLE_GROUPS: dict[int, str] = {
    23: "Protection From Abuse",
    35: "Controlled Substances",
    42: "Judicial Procedure",
    62: "Public Welfare Fraud",
    75: "Vehicle Code & DUI",
}

_SECTION_OVERRIDES: dict[tuple[int, str], str] = {
    (18, "907"): "Firearms & Weapons",
    (18, "908"): "Firearms & Weapons",
}

_SLUG_GROUP_FALLBACK: dict[str, str] = {
    "criminal-mischief": "Property Damage & Arson",
    "purchase-receipt-controlled-substance": "Controlled Substances",
}

_STATUTE_RE = re.compile(r"^\s*(\d+)\s*§+\s*([0-9][0-9.\-]*)")

# Grade severity order, most severe first. H1/H2 are the CPCMS homicide grades.
_GRADE_ORDER = ["H1", "H2", "F1", "F2", "F3", "F", "M1", "M2", "M3", "M", "S"]
_GRADE_RANK = {g: i for i, g in enumerate(_GRADE_ORDER)}

# Granular funnel stage -> (stage group, forum). The forum answers "how did this
# charge resolve" without any ranking or prediction language.
_STAGE_META: dict[str, tuple[str, str]] = {
    "still_pending": ("Awaiting disposition", "none"),
    "held_for_court": ("Held for court (no traced continuation)", "none"),
    "disposed_excluded": ("Disposed, excluded from public stats", "none"),
    "dismissed": ("Dismissed", "pretrial"),
    "withdrawn": ("Withdrawn", "pretrial"),
    "ard": ("Diverted (ARD)", "pretrial"),
    "diversion": ("Diverted (other program)", "pretrial"),
    "guilty_plea": ("Convicted — plea", "plea"),
    "guilty_verdict": ("Convicted — trial verdict", "trial"),
    "acquittal": ("Acquitted at trial", "trial"),
    "other": ("Other recorded outcome", "other"),
}

_STAGE_SORT = {
    "still_pending": 1,
    "held_for_court": 2,
    "dismissed": 3,
    "withdrawn": 4,
    "ard": 5,
    "diversion": 6,
    "guilty_plea": 7,
    "guilty_verdict": 8,
    "acquittal": 9,
    "other": 10,
    "disposed_excluded": 11,
}


def charge_group_for(slug: str, statute_code: str | None) -> str:
    """Public-statute rollup label for one roster identity."""
    if statute_code:
        m = _STATUTE_RE.match(statute_code)
        if m:
            title = int(m.group(1))
            section = m.group(2)
            override = _SECTION_OVERRIDES.get((title, section))
            if override:
                return override
            if title == 18:
                digits = re.sub(r"\D", "", section.split(".")[0])
                if digits:
                    # Pa.C.S. section numbering: a four-digit section's chapter
                    # is its two leading digits (2702 -> ch. 27); a three-digit
                    # section's is its one leading digit (901 -> ch. 9).
                    chapter = int(digits[:2]) if len(digits) >= 4 else int(digits[:1])
                    label = _TITLE18_CHAPTERS.get(chapter)
                    if label:
                        return label
            label = _TITLE_GROUPS.get(title)
            if label:
                return label
            return f"Title {title} — other"
    fallback = _SLUG_GROUP_FALLBACK.get(slug)
    if fallback:
        return fallback
    return "Unclassified"


def statute_title(statute_code: str | None) -> int | None:
    if not statute_code:
        return None
    m = _STATUTE_RE.match(statute_code)
    return int(m.group(1)) if m else None


# --- small helpers -----------------------------------------------------------


def wilson_bounds(
    successes: int, n: int, z: float = Z_95
) -> tuple[float | None, float | None]:
    """Wilson score interval for a binomial proportion (None when n == 0)."""
    if n <= 0:
        return (None, None)
    p = successes / n
    denom = 1.0 + (z * z) / n
    centre = p + (z * z) / (2.0 * n)
    spread = z * math.sqrt((p * (1.0 - p) + (z * z) / (4.0 * n)) / n)
    return ((centre - spread) / denom, (centre + spread) / denom)


def pct(numerator: int, denominator: int, places: int = 2) -> float | None:
    if denominator <= 0:
        return None
    return round(100.0 * numerator / denominator, places)


def r4(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def month_of(value: date | None) -> str | None:
    return None if value is None else value.strftime("%Y-%m-01")


def days_between(later: date | None, earlier: date | None) -> int | None:
    if later is None or earlier is None:
        return None
    return (later - earlier).days


def percentiles(values: list[float]) -> dict[str, float | None]:
    """p10/p25/p50/p75/p90 + mean, using linear interpolation."""
    if not values:
        return {k: None for k in ("p10", "p25", "p50", "p75", "p90", "mean")}
    ordered = sorted(values)
    out: dict[str, float | None] = {}
    for label, q in (
        ("p10", 0.10),
        ("p25", 0.25),
        ("p50", 0.50),
        ("p75", 0.75),
        ("p90", 0.90),
    ):
        if len(ordered) == 1:
            out[label] = round(ordered[0], 1)
            continue
        pos = q * (len(ordered) - 1)
        low = math.floor(pos)
        high = math.ceil(pos)
        if low == high:
            out[label] = round(ordered[low], 1)
        else:
            out[label] = round(
                ordered[low] + (ordered[high] - ordered[low]) * (pos - low), 1
            )
    out["mean"] = round(statistics.fmean(ordered), 1)
    return out


def prefix(value: Any, size: int = 8) -> str | None:
    """Hash-prefix form for run ids and surrogate keys."""
    return None if value is None else str(value).replace("-", "")[:size]


class CsvSink:
    """Writes one CSV and remembers what it wrote, for the manifest."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.written: list[dict[str, Any]] = []

    def write(
        self,
        folder: str,
        name: str,
        rows: list[dict[str, Any]],
        columns: list[str],
        description: str,
    ) -> None:
        target = self.root / folder
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"{name}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="raise")
            writer.writeheader()
            for row in rows:
                writer.writerow({c: row.get(c) for c in columns})
        self.written.append(
            {
                "file": f"{folder}/{name}.csv",
                "rows": len(rows),
                "columns": columns,
                "description": description,
            }
        )
        logger.info("wrote %s/%s.csv (%d rows)", folder, name, len(rows))


# --- run resolution ----------------------------------------------------------


def resolve_live_run(conn: psycopg.Connection) -> dict[str, Any]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, build_run_id, published_at, data_range_start, data_range_end,
                   taxonomy_version, parser_version
            FROM analytics.aggregate_runs
            WHERE published_at IS NOT NULL AND invalidated_at IS NULL
            """
        )
        row = cur.fetchone()
    if row is None:
        raise SystemExit("no active published aggregate run — nothing to export")
    if row["build_run_id"] is None:
        raise SystemExit(
            "published run carries no build_run_id — cannot reach the fact layer"
        )
    return dict(row)


# --- dimensions --------------------------------------------------------------


def build_dim_charge(conn: psycopg.Connection) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, slug, display_name, statute_code, is_active "
            "FROM ref.normalized_charges ORDER BY slug"
        )
        rows = [dict(r) for r in cur.fetchall()]
    out = []
    for row in rows:
        out.append(
            {
                "charge_id": str(row["id"]),
                "charge_slug": row["slug"],
                "charge_display_name": row["display_name"],
                "statute_code": row["statute_code"],
                "statute_title": statute_title(row["statute_code"]),
                "charge_group": charge_group_for(row["slug"], row["statute_code"]),
                "is_active": row["is_active"],
            }
        )
    out.append(
        {
            "charge_id": None,
            "charge_slug": UNMATCHED_SLUG,
            "charge_display_name": UNMATCHED_NAME,
            "statute_code": None,
            "statute_title": None,
            "charge_group": "Unclassified",
            "is_active": False,
        }
    )
    return out


def build_dim_judge(
    conn: psycopg.Connection, run_id: str, build_run_id: str
) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT j.id, j.slug, j.display_name, j.is_active,
                   COUNT(DISTINCT a.charge_id) AS charges_covered,
                   COALESCE(MAX(a.sample_size), 0) AS largest_charge_sample
            FROM ref.normalized_judges j
            LEFT JOIN analytics.judge_outcome_aggregates a
              ON a.judge_id = j.id AND a.aggregate_run_id = %(run)s
            GROUP BY j.id, j.slug, j.display_name, j.is_active
            ORDER BY j.slug
            """,
            {"run": run_id},
        )
        judges = [dict(r) for r in cur.fetchall()]

        cur.execute(
            """
            SELECT normalized_judge_id AS jid,
                   COUNT(*) FILTER (WHERE judge_specific_eligible)
                       AS judge_eligible_outcomes,
                   MIN(disposition_date) FILTER (WHERE judge_specific_eligible)
                       AS first_disposition,
                   MAX(disposition_date) FILTER (WHERE judge_specific_eligible)
                       AS last_disposition
            FROM fact.charge_outcomes
            WHERE build_run_id = %(build)s AND normalized_judge_id IS NOT NULL
            GROUP BY 1
            """,
            {"build": build_run_id},
        )
        coverage = {str(r["jid"]): dict(r) for r in cur.fetchall()}

        cur.execute(
            """
            SELECT o.normalized_judge_id AS jid, d.court_type_derived AS court,
                   COUNT(*) AS n
            FROM fact.charge_outcomes o
            JOIN parsed.dockets d ON d.id = o.parsed_docket_id
            WHERE o.build_run_id = %(build)s AND o.judge_specific_eligible
            GROUP BY 1, 2
            """,
            {"build": build_run_id},
        )
        courts: dict[str, Counter[str]] = defaultdict(Counter)
        for r in cur.fetchall():
            courts[str(r["jid"])][r["court"]] = r["n"]

    out = []
    for judge in judges:
        jid = str(judge["id"])
        cov = coverage.get(jid, {})
        court_mix = courts.get(jid, Counter())
        out.append(
            {
                "judge_id": jid,
                "judge_slug": judge["slug"],
                "judge_display_name": judge["display_name"],
                "is_active": judge["is_active"],
                "charges_covered": judge["charges_covered"],
                "judge_eligible_outcomes": cov.get("judge_eligible_outcomes", 0) or 0,
                "largest_charge_sample": judge["largest_charge_sample"],
                "first_disposition_date": cov.get("first_disposition"),
                "last_disposition_date": cov.get("last_disposition"),
                "primary_court": court_mix.most_common(1)[0][0] if court_mix else None,
                "mc_outcomes": court_mix.get("MC", 0),
                "cp_outcomes": court_mix.get("CP", 0),
            }
        )
    return out


def build_dim_taxonomy() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read the generated taxonomy artifact directly: the pipeline's
    TaxonomySnapshot carries only code -> public, not the display copy the
    dimension tables need."""
    here = Path(__file__).resolve()
    path = None
    for candidate in here.parents:
        probe = candidate / "packages" / "taxonomy" / "generated" / "taxonomy.json"
        if probe.is_file():
            path = probe
            break
    if path is None:
        raise SystemExit("taxonomy.json not found; run `pnpm generate`")
    data = json.loads(path.read_text())

    outcomes = []
    for entry in data["outcomeCategories"]:
        stage_group, forum = _STAGE_META.get(
            entry["code"], ("Other recorded outcome", "other")
        )
        outcomes.append(
            {
                "category_code": entry["code"],
                "display_name": entry["displayName"],
                "definition": entry["definition"],
                "sort_order": entry["sortOrder"],
                "is_public": entry["public"],
                "is_conviction": entry["code"] in CONVICTION_OUTCOME_CATEGORIES,
                "stage_group": stage_group,
                "forum": forum,
            }
        )
    sentencing = [
        {
            "category_code": entry["code"],
            "display_name": entry["displayName"],
            "definition": entry["definition"],
            "sort_order": entry["sortOrder"],
            "is_public": entry["public"],
            "carries_duration": entry["code"] in {"probation", "incarceration"},
        }
        for entry in data["sentencingCategories"]
    ]
    return outcomes, sentencing


# --- viz 1: judge x charge -----------------------------------------------------


def build_judge_charge(
    conn: psycopg.Connection,
    run_id: str,
    charge_dim: dict[str, dict[str, Any]],
    judge_dim: dict[str, dict[str, Any]],
) -> tuple[list[dict], list[dict]]:
    """The heatmap pair: one long row per (judge, charge, outcome) and one wide
    row per (judge, charge) cell carrying every rate plus the charge-only
    baseline the cell should be read against."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT j.slug AS judge_slug, c.slug AS charge_slug, a.category_code,
                   a.count, a.percentage, a.sample_size, a.is_thin_data,
                   a.date_range_start, a.date_range_end
            FROM analytics.judge_outcome_aggregates a
            JOIN ref.normalized_judges j ON j.id = a.judge_id
            JOIN ref.normalized_charges c ON c.id = a.charge_id
            WHERE a.aggregate_run_id = %(run)s
            ORDER BY j.slug, c.slug, a.category_code
            """,
            {"run": run_id},
        )
        judge_rows = [dict(r) for r in cur.fetchall()]

        cur.execute(
            """
            SELECT c.slug AS charge_slug, a.category_code, a.count, a.percentage,
                   a.sample_size, a.is_thin_data
            FROM analytics.charge_outcome_aggregates a
            JOIN ref.normalized_charges c ON c.id = a.charge_id
            WHERE a.aggregate_run_id = %(run)s
            """,
            {"run": run_id},
        )
        charge_rows = [dict(r) for r in cur.fetchall()]

        cur.execute(
            """
            SELECT j.slug AS judge_slug, c.slug AS charge_slug,
                   s.convictions, s.sentenced_convictions, s.wedge_count,
                   s.wedge_percentage, s.is_thin_data AS sentencing_is_thin
            FROM analytics.judge_sentencing_index_summaries s
            JOIN ref.normalized_judges j ON j.id = s.judge_id
            JOIN ref.normalized_charges c ON c.id = s.charge_id
            WHERE s.aggregate_run_id = %(run)s
            """,
            {"run": run_id},
        )
        sent_summary = {
            (r["judge_slug"], r["charge_slug"]): dict(r) for r in cur.fetchall()
        }

        cur.execute(
            """
            SELECT j.slug AS judge_slug, c.slug AS charge_slug, a.category_code,
                   a.conviction_count, a.percentage_of_sentenced,
                   a.median_min_days, a.median_max_days, a.min_assumed_percentage
            FROM analytics.judge_sentencing_index_aggregates a
            JOIN ref.normalized_judges j ON j.id = a.judge_id
            JOIN ref.normalized_charges c ON c.id = a.charge_id
            WHERE a.aggregate_run_id = %(run)s
            """,
            {"run": run_id},
        )
        sent_cats: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
        for r in cur.fetchall():
            sent_cats[(r["judge_slug"], r["charge_slug"])][r["category_code"]] = dict(r)

    # Charge-only baseline rates, keyed by charge slug.
    baseline: dict[str, dict[str, Any]] = defaultdict(dict)
    baseline_sample: dict[str, int] = {}
    for row in charge_rows:
        baseline[row["charge_slug"]][row["category_code"]] = row
        baseline_sample[row["charge_slug"]] = row["sample_size"]

    # --- long grain
    cells: dict[tuple[str, str], dict[str, Any]] = {}
    long_rows: list[dict[str, Any]] = []
    for row in judge_rows:
        key = (row["judge_slug"], row["charge_slug"])
        cell = cells.setdefault(
            key,
            {
                "counts": Counter(),
                "sample_size": row["sample_size"],
                "is_thin_data": row["is_thin_data"],
                "date_range_start": row["date_range_start"],
                "date_range_end": row["date_range_end"],
            },
        )
        cell["counts"][row["category_code"]] = row["count"]
        cell["date_range_start"] = min(
            cell["date_range_start"], row["date_range_start"]
        )
        cell["date_range_end"] = max(cell["date_range_end"], row["date_range_end"])

        low, high = wilson_bounds(row["count"], row["sample_size"])
        base = baseline[row["charge_slug"]].get(row["category_code"])
        base_pct = float(base["percentage"]) if base else 0.0
        charge_meta = charge_dim.get(row["charge_slug"], {})
        long_rows.append(
            {
                "judge_slug": row["judge_slug"],
                "judge_display_name": judge_dim.get(row["judge_slug"], {}).get(
                    "judge_display_name"
                ),
                "charge_slug": row["charge_slug"],
                "charge_display_name": charge_meta.get("charge_display_name"),
                "charge_group": charge_meta.get("charge_group"),
                "outcome_category": row["category_code"],
                "count": row["count"],
                "percentage": float(row["percentage"]),
                "sample_size": row["sample_size"],
                "is_thin_data": row["is_thin_data"],
                "wilson_low_pct": r4(None if low is None else low * 100),
                "wilson_high_pct": r4(None if high is None else high * 100),
                "wilson_width_pp": r4(None if low is None else (high - low) * 100),
                "charge_baseline_pct": base_pct,
                "charge_baseline_sample": baseline_sample.get(row["charge_slug"]),
                "diff_vs_charge_baseline_pp": round(
                    float(row["percentage"]) - base_pct, 2
                ),
                "date_range_start": row["date_range_start"],
                "date_range_end": row["date_range_end"],
            }
        )

    # --- wide grain
    matrix_rows: list[dict[str, Any]] = []
    for (judge_slug, charge_slug), cell in sorted(cells.items()):
        counts: Counter[str] = cell["counts"]
        n = cell["sample_size"]
        charge_meta = charge_dim.get(charge_slug, {})
        base = baseline[charge_slug]

        def base_pct_for(codes: list[str], base: dict = base) -> float:
            return round(
                sum(float(base[c]["percentage"]) for c in codes if c in base), 2
            )

        dismissed = counts.get("dismissed", 0)
        withdrawn = counts.get("withdrawn", 0)
        plea = counts.get("guilty_plea", 0)
        verdict = counts.get("guilty_verdict", 0)
        acquittal = counts.get("acquittal", 0)
        ard = counts.get("ard", 0)
        diversion = counts.get("diversion", 0)
        convictions_from_outcomes = plea + verdict
        trials = verdict + acquittal

        d_low, d_high = wilson_bounds(dismissed, n)
        dw_low, dw_high = wilson_bounds(dismissed + withdrawn, n)
        c_low, c_high = wilson_bounds(convictions_from_outcomes, n)

        summary = sent_summary.get((judge_slug, charge_slug), {})
        cats = sent_cats.get((judge_slug, charge_slug), {})
        incarceration = cats.get("incarceration", {})
        probation = cats.get("probation", {})

        row: dict[str, Any] = {
            "judge_slug": judge_slug,
            "judge_display_name": judge_dim.get(judge_slug, {}).get(
                "judge_display_name"
            ),
            "charge_slug": charge_slug,
            "charge_display_name": charge_meta.get("charge_display_name"),
            "charge_group": charge_meta.get("charge_group"),
            "statute_code": charge_meta.get("statute_code"),
            "sample_size": n,
            "is_thin_data": cell["is_thin_data"],
            "date_range_start": cell["date_range_start"],
            "date_range_end": cell["date_range_end"],
            "n_dismissed": dismissed,
            "n_withdrawn": withdrawn,
            "n_guilty_plea": plea,
            "n_guilty_verdict": verdict,
            "n_acquittal": acquittal,
            "n_ard": ard,
            "n_diversion": diversion,
            "n_other": counts.get("other", 0),
            "n_convictions": convictions_from_outcomes,
            "n_trial_outcomes": trials,
            "pct_dismissed": pct(dismissed, n),
            "pct_withdrawn": pct(withdrawn, n),
            "pct_dismissed_or_withdrawn": pct(dismissed + withdrawn, n),
            "pct_guilty_plea": pct(plea, n),
            "pct_guilty_verdict": pct(verdict, n),
            "pct_acquittal": pct(acquittal, n),
            "pct_ard": pct(ard, n),
            "pct_diversion": pct(diversion, n),
            "pct_convicted": pct(convictions_from_outcomes, n),
            "pct_trial_outcomes": pct(trials, n),
            "dismissed_wilson_low_pct": r4(None if d_low is None else d_low * 100),
            "dismissed_wilson_high_pct": r4(None if d_high is None else d_high * 100),
            "dismissed_wilson_width_pp": r4(
                None if d_low is None else (d_high - d_low) * 100
            ),
            "dismissed_or_withdrawn_wilson_low_pct": r4(
                None if dw_low is None else dw_low * 100
            ),
            "dismissed_or_withdrawn_wilson_high_pct": r4(
                None if dw_high is None else dw_high * 100
            ),
            "convicted_wilson_low_pct": r4(None if c_low is None else c_low * 100),
            "convicted_wilson_high_pct": r4(None if c_high is None else c_high * 100),
            "charge_baseline_sample": baseline_sample.get(charge_slug),
            "charge_baseline_pct_dismissed": base_pct_for(["dismissed"]),
            "charge_baseline_pct_dismissed_or_withdrawn": base_pct_for(
                ["dismissed", "withdrawn"]
            ),
            "charge_baseline_pct_convicted": base_pct_for(
                ["guilty_plea", "guilty_verdict"]
            ),
            "convictions": summary.get("convictions"),
            "sentenced_convictions": summary.get("sentenced_convictions"),
            "sentencing_wedge_count": summary.get("wedge_count"),
            "sentencing_wedge_pct": (
                float(summary["wedge_percentage"])
                if summary.get("wedge_percentage") is not None
                else None
            ),
            "incarceration_convictions": incarceration.get("conviction_count"),
            "incarceration_pct_of_sentenced": (
                float(incarceration["percentage_of_sentenced"])
                if incarceration.get("percentage_of_sentenced") is not None
                else None
            ),
            "incarceration_median_min_days": (
                float(incarceration["median_min_days"])
                if incarceration.get("median_min_days") is not None
                else None
            ),
            "incarceration_median_max_days": (
                float(incarceration["median_max_days"])
                if incarceration.get("median_max_days") is not None
                else None
            ),
            "probation_convictions": probation.get("conviction_count"),
            "probation_pct_of_sentenced": (
                float(probation["percentage_of_sentenced"])
                if probation.get("percentage_of_sentenced") is not None
                else None
            ),
            "probation_median_min_days": (
                float(probation["median_min_days"])
                if probation.get("median_min_days") is not None
                else None
            ),
            "probation_median_max_days": (
                float(probation["median_max_days"])
                if probation.get("median_max_days") is not None
                else None
            ),
        }
        row["diff_dismissed_vs_baseline_pp"] = round(
            (row["pct_dismissed"] or 0.0) - row["charge_baseline_pct_dismissed"], 2
        )
        row["diff_convicted_vs_baseline_pp"] = round(
            (row["pct_convicted"] or 0.0) - row["charge_baseline_pct_convicted"], 2
        )
        # "Distinguishable" only when the cell's own 95% interval excludes the
        # charge-wide rate — the honest guard against reading noise as a pattern.
        base_dismissed = row["charge_baseline_pct_dismissed"]
        row["dismissed_interval_excludes_baseline"] = d_low is not None and (
            base_dismissed < d_low * 100 or base_dismissed > d_high * 100
        )
        matrix_rows.append(row)

    return long_rows, matrix_rows


# --- viz 2 + 4: charge journeys ------------------------------------------------


def load_journey_corpus(
    conn: psycopg.Connection, build_run_id: str
) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT c.id, c.docket_id, c.sequence, c.statute, c.offense, c.grade,
                   c.disposition_raw, c.disposition_date, c.superseded_by_charge_id,
                   (c.superseded_by_charge_id IS NOT NULL) AS superseded,
                   d.filed_date, d.court_type_derived AS court, d.case_status,
                   o.outcome_category_code, o.public_eligible,
                   o.judge_specific_eligible,
                   o.judge_attribution_method, o.ineligibility_reason_codes,
                   o.review_needed AS fact_review_needed,
                   j.slug AS judge_slug, j.display_name AS judge_display_name
            FROM parsed.charges c
            JOIN parsed.dockets d ON d.id = c.docket_id
            LEFT JOIN fact.charge_outcomes o
                   ON o.parsed_charge_id = c.id AND o.build_run_id = %(build)s
            LEFT JOIN ref.normalized_judges j ON j.id = o.normalized_judge_id
            ORDER BY c.docket_id, c.sequence, c.id
            """,
            {"build": build_run_id},
        )
        return [dict(r) for r in cur.fetchall()]


def build_journeys(
    corpus: list[dict[str, Any]],
    warnings: dict[tuple[str, int], list[str]],
    *,
    matcher: ChargeMatcher,
    mapper: OutcomeMapper,
    charge_dim_by_id: dict[str, dict[str, Any]],
    filed_floor: date,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """One row per charge JOURNEY, superseded MC legs folded into their CP twin.

    Mirrors ``pipeline.aggregates.volume.build_charge_volume_rows`` bucket for
    bucket, then adds the lineage dates and durations the funnel/duration vizzes
    need. Returns (rows, report)."""
    # supersession points MC charge -> CP charge; index the reverse.
    mc_leg_for_cp: dict[str, dict[str, Any]] = {}
    for row in corpus:
        if row["superseded_by_charge_id"] is not None:
            mc_leg_for_cp[str(row["superseded_by_charge_id"])] = row

    report = Counter()
    journeys: list[dict[str, Any]] = []

    for row in corpus:
        report["rows_total"] += 1
        filed = row["filed_date"]
        if filed is None or filed < filed_floor:
            report["rows_pre_floor"] += 1
            continue
        report["rows_in_universe"] += 1

        disposition_raw = row["disposition_raw"]
        outcome_result = mapper.map(disposition_raw)
        is_held_form = disposition_raw is not None and outcome_result is None

        match = matcher.match(statute=row["statute"], offense=row["offense"])
        clean_identity = (
            str(match.normalized_id)
            if match.match_method in PUBLIC_CHARGE_MATCH_METHODS
            and match.normalized_id is not None
            else None
        )

        if row["superseded"]:
            if is_held_form:
                report["superseded_folded"] += 1
                continue
            report["superseded_not_held_anomaly"] += 1

        # --- bucket (identical arms to the volume generator)
        excluded_reasons: list[str] = []
        if outcome_result is None:
            stage = "still_pending" if disposition_raw is None else "held_for_court"
            outcome_category = None
            public_eligible = False
        else:
            eligibility = evaluate_outcome_eligibility(
                disposition_date=row["disposition_date"],
                filed_date=filed,
                filed_date_floor=filed_floor,
                charge_result=match,
                outcome_result=outcome_result,
                attribution=_ATTRIBUTION_STUB,
                charge_warning_codes=warnings.get(
                    (str(row["docket_id"]), int(row["sequence"])), []
                ),
            )
            public_eligible = eligibility.public_eligible
            if public_eligible:
                stage = outcome_result.outcome_code
                outcome_category = outcome_result.outcome_code
            else:
                stage = "disposed_excluded"
                outcome_category = None
                excluded_reasons = sorted(eligibility.ineligibility_reason_codes)
        report[f"stage_{stage}"] += 1

        # --- lineage
        mc_leg = mc_leg_for_cp.get(str(row["id"]))
        traced = mc_leg is not None
        entry_court = mc_leg["court"] if traced else row["court"]
        entry_filed_date = mc_leg["filed_date"] if traced else filed
        mc_held_date = mc_leg["disposition_date"] if traced else None
        cp_filed_date = filed if row["court"] == "CP" else None

        charge_meta = charge_dim_by_id.get(clean_identity or "", {})
        charge_slug = charge_meta.get("charge_slug", UNMATCHED_SLUG)
        stage_group, forum = _STAGE_META.get(stage, ("Other recorded outcome", "other"))

        # Judge is read off the fact row and kept only at the published judge
        # grain (judge_specific_eligible), so the extract can never show a
        # judge-attributed outcome the site itself would not attribute.
        judge_slug = row["judge_slug"] if row["judge_specific_eligible"] else None

        journeys.append(
            {
                "journey_key": prefix(row["id"], 12),
                "case_key": prefix(row["docket_id"], 12),
                "charge_slug": charge_slug,
                "charge_display_name": charge_meta.get(
                    "charge_display_name", UNMATCHED_NAME
                ),
                "charge_group": charge_meta.get("charge_group", "Unclassified"),
                "statute_code": charge_meta.get("statute_code"),
                "charge_match_method": match.match_method,
                "grade": row["grade"],
                "grade_class": _grade_class(row["grade"]),
                "entry_court": entry_court,
                "terminal_court": row["court"],
                "traced_mc_to_cp": traced,
                "crossed_courts": traced or (entry_court != row["court"]),
                "entry_filed_date": entry_filed_date,
                "entry_filed_month": month_of(entry_filed_date),
                "filed_date": filed,
                "filed_month": month_of(filed),
                "mc_held_date": mc_held_date,
                "cp_filed_date": cp_filed_date,
                "disposition_date": row["disposition_date"],
                "disposition_month": month_of(row["disposition_date"]),
                "funnel_stage": stage,
                "funnel_stage_group": stage_group,
                "funnel_stage_sort": _STAGE_SORT.get(stage, 99),
                "resolution_forum": forum,
                "outcome_category": outcome_category,
                "is_conviction": (
                    outcome_category in CONVICTION_OUTCOME_CATEGORIES
                    if outcome_category
                    else False
                ),
                "is_public_eligible": public_eligible,
                "excluded_reasons": ";".join(excluded_reasons) or None,
                "judge_slug": judge_slug,
                "judge_attribution_method": row["judge_attribution_method"],
                "case_status": row["case_status"],
                "days_entry_to_disposition": days_between(
                    row["disposition_date"], entry_filed_date
                ),
                "days_filed_to_disposition": days_between(
                    row["disposition_date"], filed
                ),
                # The bind-over instant itself is usually DATELESS: most
                # "Held for Court" forms carry no disposition date, so
                # days_mc_held_to_cp_filed is null except for the two dated
                # held variants. days_mc_filed_to_cp_filed is the measure that
                # always exists — MC docket filing to CP docket filing.
                "days_mc_filed_to_cp_filed": (
                    days_between(cp_filed_date, entry_filed_date) if traced else None
                ),
                "days_mc_held_to_cp_filed": (
                    days_between(cp_filed_date, mc_held_date) if traced else None
                ),
            }
        )

    return journeys, dict(report)


def _grade_class(grade: str | None) -> str:
    if not grade:
        return "Ungraded"
    if grade.startswith("H"):
        return "Homicide grade"
    if grade.startswith("F"):
        return "Felony"
    if grade.startswith("M"):
        return "Misdemeanor"
    if grade.startswith("S"):
        return "Summary"
    return "Other"


def reconcile_against_volume(
    conn: psycopg.Connection, run_id: str, journeys: list[dict[str, Any]]
) -> list[str]:
    """Prove the journey pass reproduces analytics.charge_volume_aggregates."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT c.slug AS charge_slug, v.charges_seen, v.outcomes_recorded,
                   v.held_for_court, v.still_pending, v.disposed_excluded
            FROM analytics.charge_volume_aggregates v
            JOIN ref.normalized_charges c ON c.id = v.charge_id
            WHERE v.aggregate_run_id = %(run)s
            """,
            {"run": run_id},
        )
        stored = {r["charge_slug"]: dict(r) for r in cur.fetchall()}

    derived: dict[str, Counter[str]] = defaultdict(Counter)
    for j in journeys:
        if j["charge_slug"] == UNMATCHED_SLUG:
            continue
        bucket = j["funnel_stage"]
        if bucket not in {"still_pending", "held_for_court", "disposed_excluded"}:
            bucket = "outcomes_recorded"
        derived[j["charge_slug"]][bucket] += 1
        derived[j["charge_slug"]]["charges_seen"] += 1

    problems: list[str] = []
    for slug, want in stored.items():
        got = derived.get(slug, Counter())
        for column in (
            "charges_seen",
            "outcomes_recorded",
            "held_for_court",
            "still_pending",
            "disposed_excluded",
        ):
            if got.get(column, 0) != want[column]:
                problems.append(
                    f"{slug}.{column}: journeys={got.get(column, 0)} "
                    f"stored={want[column]}"
                )
    for slug in derived:
        if slug not in stored:
            problems.append(f"{slug}: journeys present, no stored volume row")
    return problems


def build_funnel_monthly(
    journeys: list[dict[str, Any]], data_range_end: date
) -> list[dict[str, Any]]:
    grouped: Counter[tuple] = Counter()
    for j in journeys:
        grouped[
            (
                j["entry_filed_month"],
                j["entry_court"],
                j["charge_group"],
                j["charge_slug"],
                j["charge_display_name"],
                j["funnel_stage"],
                j["funnel_stage_group"],
                j["resolution_forum"],
                j["funnel_stage_sort"],
            )
        ] += 1

    # Denominator per (month, court, charge) so Tableau can draw a share
    # without a table calc, plus how much of that cohort has resolved at all.
    # A filing-month cohort is RIGHT-CENSORED: recent months are mostly still
    # pending, so an unguarded "dismissal rate by filing month" chart shows a
    # cliff that is observation time, not court behaviour. cohort_pct_resolved
    # is the guard.
    unresolved_stages = {"still_pending", "held_for_court"}
    cohort: Counter[tuple] = Counter()
    resolved: Counter[tuple] = Counter()
    for key, n in grouped.items():
        cohort[(key[0], key[1], key[3])] += n
        if key[5] not in unresolved_stages:
            resolved[(key[0], key[1], key[3])] += n

    rows = []
    for key, n in sorted(
        grouped.items(), key=lambda kv: (kv[0][0] or "", kv[0][1], kv[0][3], kv[0][8])
    ):
        month, court, group, slug, name, stage, stage_group, forum, sort = key
        total = cohort[(month, court, slug)]
        cohort_resolved = resolved[(month, court, slug)]
        month_start = date.fromisoformat(month) if month else None
        rows.append(
            {
                "entry_filed_month": month,
                "entry_court": court,
                "charge_group": group,
                "charge_slug": slug,
                "charge_display_name": name,
                "funnel_stage": stage,
                "funnel_stage_group": stage_group,
                "funnel_stage_sort": sort,
                "resolution_forum": forum,
                "journeys": n,
                "cohort_journeys": total,
                "pct_of_cohort": pct(n, total),
                "cohort_resolved_journeys": cohort_resolved,
                "cohort_pct_resolved": pct(cohort_resolved, total),
                "cohort_observation_days": days_between(data_range_end, month_start),
            }
        )
    return rows


def build_outcome_by_disposition_month(
    journeys: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """The un-censored companion to the filing-month funnel: recorded outcomes
    keyed on the month the disposition happened, so the outcome MIX reads as a
    time series without the cohort-maturation artefact."""
    grouped: Counter[tuple] = Counter()
    for j in journeys:
        if not j["outcome_category"] or not j["disposition_month"]:
            continue
        grouped[
            (
                j["disposition_month"],
                j["entry_court"],
                j["charge_group"],
                j["outcome_category"],
                j["resolution_forum"],
            )
        ] += 1

    month_totals: Counter[tuple] = Counter()
    for key, n in grouped.items():
        month_totals[(key[0], key[1], key[2])] += n

    rows = []
    for key, n in sorted(grouped.items()):
        month, court, group, outcome, forum = key
        total = month_totals[(month, court, group)]
        rows.append(
            {
                "disposition_month": month,
                "entry_court": court,
                "charge_group": group,
                "outcome_category": outcome,
                "resolution_forum": forum,
                "outcomes": n,
                "outcomes_in_month_group": total,
                "pct_of_month_group": pct(n, total),
            }
        )
    return rows


def build_case_durations(
    conn: psycopg.Connection, build_run_id: str, filed_floor: date
) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT d.id AS docket_id, d.court_type_derived AS court, d.filed_date,
                   d.case_status,
                   d.originating_docket_no IS NOT NULL AS has_originating,
                   COUNT(c.id) AS n_charges,
                   COUNT(c.id) FILTER (WHERE c.disposition_date IS NOT NULL)
                       AS n_dated_dispositions,
                   COUNT(c.id) FILTER (WHERE c.disposition_raw IS NULL) AS n_undisposed,
                   COUNT(c.id) FILTER (WHERE c.superseded_by_charge_id IS NOT NULL)
                       AS n_superseded,
                   MIN(c.disposition_date) AS first_disposition_date,
                   MAX(c.disposition_date) AS last_disposition_date,
                   COUNT(o.id) FILTER (WHERE o.public_eligible) AS n_public_eligible,
                   COUNT(o.id) FILTER (
                       WHERE o.public_eligible
                         AND o.outcome_category_code
                             IN ('guilty_plea', 'guilty_verdict')
                   ) AS n_convictions
            FROM parsed.dockets d
            JOIN parsed.charges c ON c.docket_id = d.id
            LEFT JOIN fact.charge_outcomes o
                   ON o.parsed_charge_id = c.id AND o.build_run_id = %(build)s
            WHERE d.filed_date >= %(floor)s
            GROUP BY d.id, d.court_type_derived, d.filed_date, d.case_status,
                     has_originating
            """,
            {"build": build_run_id, "floor": filed_floor},
        )
        base = [dict(r) for r in cur.fetchall()]

        cur.execute(
            """
            SELECT c.docket_id, c.grade, j.slug AS judge_slug, o.public_eligible
            FROM parsed.charges c
            JOIN parsed.dockets d ON d.id = c.docket_id
            LEFT JOIN fact.charge_outcomes o
                   ON o.parsed_charge_id = c.id AND o.build_run_id = %(build)s
            LEFT JOIN ref.normalized_judges j
                   ON j.id = o.normalized_judge_id AND o.judge_specific_eligible
            WHERE d.filed_date >= %(floor)s
            """,
            {"build": build_run_id, "floor": filed_floor},
        )
        grades: dict[str, list[str]] = defaultdict(list)
        judges: dict[str, Counter[str]] = defaultdict(Counter)
        for r in cur.fetchall():
            did = str(r["docket_id"])
            if r["grade"]:
                grades[did].append(r["grade"])
            if r["judge_slug"]:
                judges[did][r["judge_slug"]] += 1

    rows = []
    for row in base:
        did = str(row["docket_id"])
        docket_grades = grades.get(did, [])
        lead_grade = (
            min(docket_grades, key=lambda g: _GRADE_RANK.get(g, 99))
            if docket_grades
            else None
        )
        judge_mix = judges.get(did, Counter())
        n_charges = row["n_charges"]
        rows.append(
            {
                "case_key": prefix(row["docket_id"], 12),
                "court": row["court"],
                "case_status": row["case_status"],
                "continues_prior_mc_case": row["has_originating"],
                "filed_date": row["filed_date"],
                "filed_month": month_of(row["filed_date"]),
                "n_charges": n_charges,
                "n_undisposed_charges": row["n_undisposed"],
                "n_superseded_charges": row["n_superseded"],
                "n_public_eligible_outcomes": row["n_public_eligible"],
                "n_convictions": row["n_convictions"],
                "is_fully_disposed": row["n_undisposed"] == 0,
                "has_conviction": row["n_convictions"] > 0,
                "lead_grade": lead_grade,
                "lead_grade_class": _grade_class(lead_grade),
                "first_disposition_date": row["first_disposition_date"],
                "last_disposition_date": row["last_disposition_date"],
                "disposition_month": month_of(row["last_disposition_date"]),
                "days_filed_to_first_disposition": days_between(
                    row["first_disposition_date"], row["filed_date"]
                ),
                "days_filed_to_last_disposition": days_between(
                    row["last_disposition_date"], row["filed_date"]
                ),
                "judge_slug": judge_mix.most_common(1)[0][0] if judge_mix else None,
                "judges_on_case": len(judge_mix),
            }
        )
    return rows


def build_duration_percentiles(
    journeys: list[dict[str, Any]], cases: list[dict[str, Any]], min_cell: int
) -> list[dict[str, Any]]:
    """Publish-safe percentile table. Cells below min_cell are dropped entirely
    (row-level durations live in internal-only/)."""
    buckets: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)

    for j in journeys:
        d = j["days_entry_to_disposition"]
        if d is None or d < 0:
            continue
        if j["funnel_stage"] in {
            "still_pending",
            "held_for_court",
            "disposed_excluded",
        }:
            continue
        buckets[("charge_grain", "entry_court", j["entry_court"], "")].append(d)
        buckets[
            (
                "charge_grain",
                "entry_court_x_grade_class",
                j["entry_court"],
                j["grade_class"],
            )
        ].append(d)
        buckets[
            (
                "charge_grain",
                "entry_court_x_outcome",
                j["entry_court"],
                j["outcome_category"] or "",
            )
        ].append(d)
        buckets[("charge_grain", "charge_group", j["charge_group"], "")].append(d)
        buckets[("charge_grain", "outcome", j["outcome_category"] or "", "")].append(d)
        buckets[
            ("charge_grain", "crossed_courts", str(j["crossed_courts"]), "")
        ].append(d)
        if j["judge_slug"]:
            buckets[("charge_grain", "judge", j["judge_slug"], "")].append(d)
            buckets[
                (
                    "charge_grain",
                    "judge_x_entry_court",
                    j["judge_slug"],
                    j["entry_court"],
                )
            ].append(d)
        lag = j["days_mc_filed_to_cp_filed"]
        if lag is not None and lag >= 0:
            buckets[("mc_to_cp_lag", "all", "MC->CP", "")].append(lag)
            buckets[("mc_to_cp_lag", "charge_group", j["charge_group"], "")].append(lag)
            buckets[("mc_to_cp_lag", "grade_class", j["grade_class"], "")].append(lag)

    for c in cases:
        d = c["days_filed_to_last_disposition"]
        if d is None or d < 0 or not c["is_fully_disposed"]:
            continue
        buckets[("case_grain", "court", c["court"], "")].append(d)
        buckets[
            ("case_grain", "court_x_grade_class", c["court"], c["lead_grade_class"])
        ].append(d)
        if c["judge_slug"]:
            buckets[("case_grain", "judge", c["judge_slug"], "")].append(d)

    rows = []
    for (grain, dimension, value_a, value_b), values in sorted(buckets.items()):
        if len(values) < min_cell:
            continue
        p = percentiles(values)
        rows.append(
            {
                "grain": grain,
                "dimension": dimension,
                "dimension_value": value_a,
                "dimension_value_2": value_b or None,
                "n": len(values),
                "mean_days": p["mean"],
                "p10_days": p["p10"],
                "p25_days": p["p25"],
                "median_days": p["p50"],
                "p75_days": p["p75"],
                "p90_days": p["p90"],
                "iqr_days": (
                    None
                    if p["p75"] is None or p["p25"] is None
                    else round(p["p75"] - p["p25"], 1)
                ),
            }
        )
    return rows


# --- viz 3: data quality -------------------------------------------------------


def build_dq_ingest_status(conn: psycopg.Connection) -> list[dict[str, Any]]:
    """Document-level intake state by court. Deliberately NOT keyed on import
    month: the corpus is bulk-collected, so every document shares one import
    month and a monthly series there measures the operator's calendar, not the
    court's. Collection coverage over time lives in dq_coverage_monthly, which
    keys on the docket's FILING month."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT court_type AS court, status, error_code,
                   COUNT(*) AS documents,
                   MIN(imported_at)::date AS first_imported,
                   MAX(imported_at)::date AS last_imported
            FROM raw.source_documents
            GROUP BY 1, 2, 3 ORDER BY 1, 2, 3
            """
        )
        docs = [dict(r) for r in cur.fetchall()]
        cur.execute(
            """
            SELECT court_type AS court, COUNT(*) AS documents
            FROM raw.source_documents GROUP BY 1
            """
        )
        totals = {r["court"]: r["documents"] for r in cur.fetchall()}

    return [
        {
            "court": d["court"],
            "source_status": d["status"],
            "error_code": d["error_code"],
            "documents": d["documents"],
            "documents_for_court": totals.get(d["court"], 0),
            "pct_of_court": pct(d["documents"], totals.get(d["court"], 0)),
            "first_imported": d["first_imported"],
            "last_imported": d["last_imported"],
        }
        for d in docs
    ]


def build_dq_coverage_monthly(conn: psycopg.Connection) -> list[dict[str, Any]]:
    """Collection + parse coverage by the month the docket was FILED — the axis
    a coverage gap actually shows up on."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT date_trunc('month', d.filed_date)::date AS filed_month,
                   d.court_type_derived AS court,
                   COUNT(DISTINCT d.id) AS dockets,
                   COUNT(DISTINCT d.filed_date) AS distinct_filing_days,
                   COUNT(DISTINCT d.id) FILTER (WHERE d.review_needed)
                       AS dockets_review_needed,
                   COUNT(DISTINCT d.id) FILTER (WHERE d.assigned_judge_raw IS NULL)
                       AS dockets_without_assigned_judge,
                   COUNT(c.id) AS charges,
                   COUNT(c.id) FILTER (WHERE c.disposition_raw IS NOT NULL)
                       AS charges_disposed,
                   COUNT(c.id) FILTER (WHERE c.grade IS NULL) AS charges_ungraded,
                   COUNT(c.id) FILTER (WHERE c.superseded_by_charge_id IS NOT NULL)
                       AS charges_superseded
            FROM parsed.dockets d
            JOIN parsed.charges c ON c.docket_id = d.id
            WHERE d.filed_date IS NOT NULL
            GROUP BY 1, 2 ORDER BY 1, 2
            """
        )
        rows = [dict(r) for r in cur.fetchall()]

    return [
        {
            "filed_month": r["filed_month"],
            "court": r["court"],
            "dockets": r["dockets"],
            "distinct_filing_days": r["distinct_filing_days"],
            "charges": r["charges"],
            "charges_per_docket": round(r["charges"] / r["dockets"], 2)
            if r["dockets"]
            else None,
            "charges_disposed": r["charges_disposed"],
            "pct_charges_disposed": pct(r["charges_disposed"], r["charges"]),
            "charges_ungraded": r["charges_ungraded"],
            "pct_charges_ungraded": pct(r["charges_ungraded"], r["charges"]),
            "charges_superseded": r["charges_superseded"],
            "pct_charges_superseded": pct(r["charges_superseded"], r["charges"]),
            "dockets_review_needed": r["dockets_review_needed"],
            "pct_dockets_review_needed": pct(r["dockets_review_needed"], r["dockets"]),
            "dockets_without_assigned_judge": r["dockets_without_assigned_judge"],
        }
        for r in rows
    ]


def build_dq_warnings(conn: psycopg.Connection) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT w.code,
                   d.court_type_derived AS court,
                   EXTRACT(YEAR FROM d.filed_date)::int AS filed_year,
                   COUNT(*) AS occurrences,
                   COUNT(DISTINCT d.id) AS dockets_affected,
                   COUNT(*) FILTER (WHERE w.charge_sequence IS NOT NULL)
                       AS charge_grain_occurrences
            FROM parsed.warnings w
            JOIN parsed.dockets d ON d.id = w.docket_id
            GROUP BY 1, 2, 3 ORDER BY 1, 2, 3
            """
        )
        warn = [dict(r) for r in cur.fetchall()]
        cur.execute(
            """
            SELECT court_type_derived AS court,
                   EXTRACT(YEAR FROM filed_date)::int AS filed_year,
                   COUNT(*) AS dockets
            FROM parsed.dockets GROUP BY 1, 2
            """
        )
        totals = {(r["court"], r["filed_year"]): r["dockets"] for r in cur.fetchall()}

    rows = []
    for w in warn:
        denom = totals.get((w["court"], w["filed_year"]), 0)
        rows.append(
            {
                "warning_code": w["code"],
                "severity": WARNING_SEVERITY.get(w["code"], "unknown"),
                "blocks_public_use": WARNING_SEVERITY.get(w["code"]) == "review",
                "court": w["court"],
                "filed_year": w["filed_year"],
                "occurrences": w["occurrences"],
                "charge_grain_occurrences": w["charge_grain_occurrences"],
                "dockets_affected": w["dockets_affected"],
                "dockets_in_scope": denom,
                "pct_dockets_affected": pct(w["dockets_affected"], denom),
            }
        )
    return rows


def build_dq_supersession(
    conn: psycopg.Connection, journeys: list[dict[str, Any]]
) -> tuple[list[dict], list[dict]]:
    """Two views of the MC->CP tracing: the raw pointer census by docket year,
    and the traced-vs-untraced held population by month (the funnel's leak)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT EXTRACT(YEAR FROM d.filed_date)::int AS filed_year,
                   d.court_type_derived AS court,
                   COUNT(*) AS charges,
                   COUNT(*) FILTER (WHERE c.superseded_by_charge_id IS NOT NULL)
                       AS superseded_charges,
                   COUNT(*) FILTER (WHERE c.orig_seq IS NOT NULL)
                       AS charges_with_orig_seq,
                   COUNT(DISTINCT d.id) AS dockets,
                   COUNT(DISTINCT d.id)
                       FILTER (WHERE d.originating_docket_no IS NOT NULL)
                       AS dockets_with_originating_pointer
            FROM parsed.charges c
            JOIN parsed.dockets d ON d.id = c.docket_id
            GROUP BY 1, 2 ORDER BY 1, 2
            """
        )
        census = []
        for r in cur.fetchall():
            census.append(
                {
                    "filed_year": r["filed_year"],
                    "court": r["court"],
                    "dockets": r["dockets"],
                    "dockets_with_originating_pointer": r[
                        "dockets_with_originating_pointer"
                    ],
                    "pct_dockets_with_originating_pointer": pct(
                        r["dockets_with_originating_pointer"], r["dockets"]
                    ),
                    "charges": r["charges"],
                    "charges_with_orig_seq": r["charges_with_orig_seq"],
                    "pct_charges_with_orig_seq": pct(
                        r["charges_with_orig_seq"], r["charges"]
                    ),
                    "superseded_charges": r["superseded_charges"],
                    "pct_charges_superseded": pct(
                        r["superseded_charges"], r["charges"]
                    ),
                }
            )

    # Traced vs untraced, from the journey pass (folded legs are invisible there,
    # so count them from the pointer census side).
    tracing: dict[tuple, Counter] = defaultdict(Counter)
    for j in journeys:
        key = (j["entry_filed_month"], j["charge_group"])
        tracing[key]["journeys"] += 1
        if j["traced_mc_to_cp"]:
            tracing[key]["traced_mc_to_cp"] += 1
        if j["funnel_stage"] == "held_for_court":
            tracing[key]["held_untraced"] += 1

    trace_rows = []
    for (month, group), counts in sorted(
        tracing.items(), key=lambda kv: (kv[0][0] or "", kv[0][1])
    ):
        traced = counts["traced_mc_to_cp"]
        untraced = counts["held_untraced"]
        held_population = traced + untraced
        trace_rows.append(
            {
                "entry_filed_month": month,
                "charge_group": group,
                "journeys": counts["journeys"],
                "held_population": held_population,
                "traced_mc_to_cp": traced,
                "held_untraced": untraced,
                "pct_held_traced": pct(traced, held_population),
            }
        )
    return census, trace_rows


def build_dq_ineligibility(
    conn: psycopg.Connection, build_run_id: str
) -> list[dict[str, Any]]:
    rows = []
    with conn.cursor(row_factory=dict_row) as cur:
        for grain, table in (
            ("outcome", "fact.charge_outcomes"),
            ("sentence", "fact.charge_sentences"),
        ):
            cur.execute(
                f"""
                SELECT unnest(ineligibility_reason_codes) AS reason_code,
                       COUNT(*) AS facts
                FROM {table} WHERE build_run_id = %(build)s
                GROUP BY 1 ORDER BY 2 DESC
                """,
                {"build": build_run_id},
            )
            reasons = [dict(r) for r in cur.fetchall()]
            cur.execute(
                f"""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE public_eligible) AS public_eligible,
                       COUNT(*) FILTER (WHERE judge_specific_eligible) AS judge_eligible
                FROM {table} WHERE build_run_id = %(build)s
                """,
                {"build": build_run_id},
            )
            totals = dict(cur.fetchone())
            for r in reasons:
                rows.append(
                    {
                        "grain": grain,
                        "reason_code": r["reason_code"],
                        "facts": r["facts"],
                        "facts_in_grain": totals["total"],
                        "pct_of_grain": pct(r["facts"], totals["total"]),
                        "public_eligible_in_grain": totals["public_eligible"],
                        "judge_eligible_in_grain": totals["judge_eligible"],
                    }
                )
    return rows


def build_dq_judge_precision(
    matrix_rows: list[dict[str, Any]], min_cell: int
) -> list[dict[str, Any]]:
    rows = []
    for row in matrix_rows:
        width = row["dismissed_wilson_width_pp"]
        if width is None:
            band = "no interval"
        elif width <= 10:
            band = "±5pp or tighter"
        elif width <= 20:
            band = "±10pp"
        elif width <= 40:
            band = "±20pp"
        else:
            band = "wider than ±20pp"
        rows.append(
            {
                "judge_slug": row["judge_slug"],
                "charge_slug": row["charge_slug"],
                "charge_group": row["charge_group"],
                "sample_size": row["sample_size"],
                "meets_min_cell": row["sample_size"] >= min_cell,
                "is_thin_data": row["is_thin_data"],
                "pct_dismissed": row["pct_dismissed"],
                "dismissed_wilson_low_pct": row["dismissed_wilson_low_pct"],
                "dismissed_wilson_high_pct": row["dismissed_wilson_high_pct"],
                "dismissed_wilson_width_pp": width,
                "precision_band": band,
                "charge_baseline_pct_dismissed": row["charge_baseline_pct_dismissed"],
                "interval_excludes_charge_baseline": row[
                    "dismissed_interval_excludes_baseline"
                ],
            }
        )
    rows.sort(key=lambda r: (-(r["dismissed_wilson_width_pp"] or 0), r["judge_slug"]))
    return rows


def build_dq_summary(
    conn: psycopg.Connection,
    run: dict[str, Any],
    journey_report: dict[str, Any],
    journeys: list[dict[str, Any]],
    reconcile_problems: list[str],
) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM raw.source_documents)
                  AS source_documents,
              (SELECT COUNT(*) FROM raw.source_documents WHERE status = 'imported')
                  AS documents_imported,
              (SELECT COUNT(*) FROM parsed.dockets) AS dockets,
              (SELECT COUNT(*) FROM parsed.charges) AS charges,
              (SELECT COUNT(*) FROM parsed.charges
                WHERE superseded_by_charge_id IS NOT NULL) AS charges_superseded,
              (SELECT COUNT(*) FROM parsed.sentences) AS sentence_components,
              (SELECT COUNT(*) FROM parsed.warnings) AS parser_warnings,
              (SELECT COUNT(*) FROM ref.normalized_charges WHERE is_active)
                  AS roster_charges,
              (SELECT COUNT(*) FROM ref.normalized_judges WHERE is_active)
                  AS roster_judges,
              (SELECT COUNT(*) FROM fact.charge_outcomes
                WHERE build_run_id = %(build)s) AS outcome_facts,
              (SELECT COUNT(*) FROM fact.charge_outcomes
                WHERE build_run_id = %(build)s AND public_eligible)
                  AS outcome_facts_public,
              (SELECT COUNT(*) FROM fact.charge_outcomes
                WHERE build_run_id = %(build)s AND judge_specific_eligible)
                  AS outcome_facts_judge,
              (SELECT COUNT(*) FROM fact.charge_sentences
                WHERE build_run_id = %(build)s) AS sentence_facts
            """,
            {"build": str(run["build_run_id"])},
        )
        counts = dict(cur.fetchone())

    stage_counts = Counter(j["funnel_stage"] for j in journeys)
    metrics: list[tuple[str, Any, str]] = [
        ("aggregate_run", prefix(run["id"]), "run"),
        ("fact_build_run", prefix(run["build_run_id"]), "run"),
        ("published_at", run["published_at"].date().isoformat(), "run"),
        ("data_range_start", run["data_range_start"].isoformat(), "run"),
        ("data_range_end", run["data_range_end"].isoformat(), "run"),
        ("taxonomy_version", run["taxonomy_version"], "run"),
    ]
    for key, value in counts.items():
        metrics.append((key, value, "corpus"))
    for key, value in sorted(journey_report.items()):
        metrics.append((f"journey_{key}", value, "journey_pass"))
    for stage, n in sorted(
        stage_counts.items(), key=lambda kv: _STAGE_SORT.get(kv[0], 99)
    ):
        metrics.append((f"journeys_{stage}", n, "funnel"))
    metrics.append(("journeys_total", len(journeys), "funnel"))
    metrics.append(
        (
            "journeys_unmatched_charge",
            sum(1 for j in journeys if j["charge_slug"] == UNMATCHED_SLUG),
            "funnel",
        )
    )
    metrics.append(
        ("volume_reconciliation_mismatches", len(reconcile_problems), "integrity")
    )
    metrics.append(
        (
            "volume_reconciliation",
            "exact" if not reconcile_problems else "MISMATCH",
            "integrity",
        )
    )

    return [
        {"metric": name, "value": value, "section": section}
        for name, value, section in metrics
    ]


README_TEMPLATE = """# Tableau extracts — Philadelphia court outcomes

Generated {generated_at} from published aggregate run `{run}` (fact build
`{build}`), taxonomy {taxonomy}. Data range **{range_start} to {range_end}**;
charges are in scope when their docket was filed on or after **{floor}**.

Every number here was produced by `scripts/export_tableau.py` in the PCA repo.
Re-run that script after a publish cycle to refresh; each run writes a new
timestamped directory, so old workbooks keep pointing at the snapshot they were
built on.

The funnel tables reconcile **exactly** against the published
`analytics.charge_volume_aggregates` for this run ({reconciliation}) — the
export re-derives them through the same charge matcher, disposition mapper and
eligibility rules the pipeline uses, and refuses to write if they disagree.

## Two folders, two disclosure postures

**`publish-safe/`** — aggregate grain only. Percentile cells under n={min_cell}
are dropped; small heatmap cells are flagged rather than hidden. Fine in a
workbook that might reach Tableau Public.

**`internal-only/`** — one row per charge journey and per case. Row-level court
data: **keep it off any public workbook.**

Neither folder contains docket numbers, defendant hashes, or raw docket text.
`journey_key` and `case_key` are truncated random database UUIDs — they carry
nothing derived from a docket, and they **change on every corpus reload**, so
never join them across two extract runs.

## Files

### Dimensions (join these to everything)

- **`dim_charge.csv`** — one row per roster charge, plus one `(unmatched)` row.
  Key: `charge_slug`. `charge_group` is a rollup derived from the public
  statute code by Pa.C.S. title and chapter (18 § 2702 -> ch. 27 -> "Assault &
  Threats"), with two hand-set exceptions: 18 § 907 and § 908 (instruments of
  crime, offensive weapons) sit in "Firearms & Weapons" rather than the
  statutory inchoate-crimes chapter, because that is where a chart reader looks
  for them.
- **`dim_judge.csv`** — key `judge_slug`, with each judge's coverage in this run.
- **`dim_outcome_category.csv`** / **`dim_sentencing_category.csv`** — taxonomy
  codes with their published definitions. Use the definition text in tooltips.

### 1. Judge x charge heatmap

- **`fact_judge_charge_matrix.csv`** — the primary. One row per (judge, charge)
  cell: counts and percentages for every outcome, Wilson 95% bounds on the
  dismissal and conviction rates, the charge-wide baseline rate for the same
  charge, the difference in percentage points, and the cell's sentencing index
  (conviction counts, median incarceration and probation min/max days).
- **`fact_judge_charge_outcomes_long.csv`** — the same cells unpivoted to one
  row per outcome category, for small multiples of the full outcome mix.

Build: judges on rows, `charge_display_name` (or `charge_group`) on columns,
colour by `pct_dismissed`, size or label by `sample_size`. Filter
`is_thin_data = False` before drawing conclusions.

### 2. Charge funnel over time

- **`agg_charge_funnel_monthly.csv`** — journeys by entry month, entry court,
  charge and stage. `funnel_stage` is granular (pending / held / dismissed /
  withdrawn / ard / guilty_plea / guilty_verdict / acquittal / other /
  excluded); `funnel_stage_group` and `resolution_forum` (pretrial / plea /
  trial) are the coarser cuts.
- **`agg_outcome_by_disposition_month.csv`** — recorded outcomes keyed on the
  month the disposition happened. Use this, not the filing-month table, for any
  "is the mix changing" question (see the censoring caveat below).
- **`internal-only/fact_charge_journeys.csv`** — the row grain, one row per
  deduplicated charge journey, carrying the MC->CP lineage.

### 3. Data-quality diagnostics

- **`dq_corpus_summary.csv`** — one row per metric; the scorecard.
- **`dq_coverage_monthly.csv`** — collection and parse coverage by docket
  **filing** month.
- **`dq_ingest_status.csv`** — document intake state by court. Not a time
  series on purpose: the corpus is bulk-collected, so import date measures the
  operator's calendar, not the court's.
- **`dq_parse_warnings.csv`** — warning rates by code, court and filing year,
  with each code's severity and whether it blocks public use.
- **`dq_supersession_census.csv`** / **`dq_supersession_tracing_monthly.csv`** —
  MC->CP capture rates, and how much of each month's held-for-court population
  has a traced continuation.
- **`dq_ineligibility_reasons.csv`** — why facts drop out of the public and
  judge-specific grains.
- **`dq_judge_sample_precision.csv`** — every judge x charge cell ranked by
  Wilson interval width, with a `precision_band` label.

### 4. Case duration distributions

- **`agg_duration_percentiles.csv`** — p10/p25/median/p75/p90 plus mean and IQR.
  `grain` is `charge_grain` (filing to that charge's disposition),
  `case_grain` (filing to the docket's last disposition), or `mc_to_cp_lag`
  (MC filing to CP filing on traced journeys). Cells under n={min_cell} are
  dropped.
- **`internal-only/fact_charge_journeys.csv`** and
  **`internal-only/fact_case_durations.csv`** — the row grain box plots need.

## Modelling in Tableau

Use a **relationship** (noodle), not a join, between each fact table and the
dimensions:

```
fact_judge_charge_matrix  --  dim_judge   (judge_slug = judge_slug)
                          --  dim_charge  (charge_slug = charge_slug)
fact_charge_journeys      --  dim_charge  (charge_slug = charge_slug)
                          --  dim_judge   (judge_slug = judge_slug)
                          --  dim_outcome_category (outcome_category = category_code)
```

Set `entry_filed_month` / `disposition_month` / `filed_month` to Date, not
String, on first use — they are written as the first of the month.

## Caveats that change what a chart means

1. **Filing-month cohorts are right-censored.** A case filed last month has had
   no time to resolve, so "dismissal rate by filing month" falls off a cliff at
   the right edge — that is observation time, not court behaviour. Guard with
   `cohort_pct_resolved` (filter to mature cohorts) or use
   `agg_outcome_by_disposition_month` instead.
2. **Most judge x charge cells are small.** {thin_cells} of {total_cells} cells
   have fewer than 10 outcomes. Colour by a rate without filtering on
   `sample_size` and the heatmap will be mostly noise. `dismissed_wilson_*` and
   `dismissed_interval_excludes_baseline` are there so a cell is only called
   different from the charge-wide rate when its own interval says so.
3. **Charge grade is recorded at disposition.** Grade is present on ~96% of
   disposed charges and ~0% of undisposed ones, so any grade breakdown is
   implicitly conditioned on the charge having been disposed.
4. **`entry_court` is not the docket's court.** A charge that started in
   Municipal Court and continued into Common Pleas has `entry_court = MC` and
   `terminal_court = CP`, and is counted **once**. That is the deduplication
   the supersession pointer buys. `case_grain` rows in the percentile table use
   the docket's own court instead.
5. **The bind-over instant is dateless.** Most "Held for Court" dispositions
   carry no date, so `days_mc_held_to_cp_filed` is almost always empty.
   `days_mc_filed_to_cp_filed` is the measure that always exists.
6. **{unmatched} journeys carry `charge_slug = (unmatched)`** — real charges
   whose statute and text did not resolve to a single roster identity. They are
   in the funnel and duration tables and excluded from anything charge-keyed.
   Filter them out or show them as their own band; do not silently drop them.
7. **These are recorded outcomes, not predictions or rankings.** Judges hear
   different caseloads, and nothing here adjusts for case mix. A cell that
   differs from the charge-wide rate is a question to investigate, not a
   finding.
"""


def write_readme(
    out_dir: Path,
    run: dict[str, Any],
    matrix_rows: list[dict[str, Any]],
    journeys: list[dict[str, Any]],
    min_cell: int,
    reconciliation: str,
) -> None:
    text = README_TEMPLATE.format(
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        run=prefix(run["id"]),
        build=prefix(run["build_run_id"]),
        taxonomy=run["taxonomy_version"],
        range_start=run["data_range_start"],
        range_end=run["data_range_end"],
        floor=FILED_DATE_FLOOR_DEFAULT,
        reconciliation=reconciliation,
        min_cell=min_cell,
        thin_cells=sum(1 for r in matrix_rows if r["is_thin_data"]),
        total_cells=len(matrix_rows),
        unmatched=f"{sum(1 for j in journeys if j['charge_slug'] == UNMATCHED_SLUG):,}",
    )
    (out_dir / "README.md").write_text(text)


# --- driver --------------------------------------------------------------------


def assert_outside_repo(path: Path) -> None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path if path.exists() else path.parent,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return
    if result.returncode == 0 and result.stdout.strip() == "true":
        raise SystemExit(
            f"refusing to write extracts into a git working tree: {path} (rule 1)"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-root", type=Path, default=Path.home() / "court-data" / "tableau"
    )
    parser.add_argument("--min-cell", type=int, default=DEFAULT_MIN_CELL)
    parser.add_argument("--skip-reconcile", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is not set")

    with psycopg.connect(database_url) as conn:
        run = resolve_live_run(conn)
        run_id = str(run["id"])
        build_run_id = str(run["build_run_id"])
        logger.info(
            "live run %s (build %s), data range %s..%s",
            prefix(run_id),
            prefix(build_run_id),
            run["data_range_start"],
            run["data_range_end"],
        )

        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        out_dir = args.out_root / f"{stamp}-{prefix(run_id)}"
        assert_outside_repo(args.out_root)
        out_dir.mkdir(parents=True, exist_ok=True)
        sink = CsvSink(out_dir)

        # --- dimensions
        charge_dim_rows = build_dim_charge(conn)
        charge_dim = {r["charge_slug"]: r for r in charge_dim_rows}
        charge_dim_by_id = {
            r["charge_id"]: r for r in charge_dim_rows if r["charge_id"]
        }
        judge_dim_rows = build_dim_judge(conn, run_id, build_run_id)
        judge_dim = {r["judge_slug"]: r for r in judge_dim_rows}
        outcome_dim_rows, sentencing_dim_rows = build_dim_taxonomy()

        # --- viz 1
        long_rows, matrix_rows = build_judge_charge(conn, run_id, charge_dim, judge_dim)

        # --- viz 2 + 4 (journey pass over the real matcher/mapper)
        matcher = ChargeMatcher(load_charge_roster_from_connection(conn))
        mapper = OutcomeMapper(load_taxonomy_snapshot())
        corpus = load_journey_corpus(conn, build_run_id)
        warnings = load_charge_warning_codes(conn)
        journeys, journey_report = build_journeys(
            corpus,
            warnings,
            matcher=matcher,
            mapper=mapper,
            charge_dim_by_id=charge_dim_by_id,
            filed_floor=FILED_DATE_FLOOR_DEFAULT,
        )
        logger.info(
            "journeys built: %d (from %d in-universe charge rows)",
            len(journeys),
            journey_report.get("rows_in_universe", 0),
        )

        problems = reconcile_against_volume(conn, run_id, journeys)
        if problems:
            for p in problems[:10]:
                logger.error("volume reconciliation: %s", p)
            logger.error("volume reconciliation: %d mismatched measures", len(problems))
            if not args.skip_reconcile:
                raise SystemExit(
                    "journey funnel does not reproduce the published volume "
                    "aggregates; "
                    "re-run with --skip-reconcile only if that divergence is understood"
                )
        else:
            logger.info("volume reconciliation: exact against the published run")

        funnel_rows = build_funnel_monthly(journeys, run["data_range_end"])
        disposition_month_rows = build_outcome_by_disposition_month(journeys)
        case_rows = build_case_durations(conn, build_run_id, FILED_DATE_FLOOR_DEFAULT)
        duration_rows = build_duration_percentiles(journeys, case_rows, args.min_cell)

        # --- viz 3
        ingest_rows = build_dq_ingest_status(conn)
        coverage_rows = build_dq_coverage_monthly(conn)
        warning_rows = build_dq_warnings(conn)
        census_rows, trace_rows = build_dq_supersession(conn, journeys)
        inelig_rows = build_dq_ineligibility(conn, build_run_id)
        precision_rows = build_dq_judge_precision(matrix_rows, args.min_cell)
        summary_rows = build_dq_summary(conn, run, journey_report, journeys, problems)

    # --- write
    sink.write(
        "publish-safe",
        "dim_charge",
        charge_dim_rows,
        [
            "charge_id",
            "charge_slug",
            "charge_display_name",
            "statute_code",
            "statute_title",
            "charge_group",
            "is_active",
        ],
        "Charge roster with a statute-derived grouping for axis rollups.",
    )
    sink.write(
        "publish-safe",
        "dim_judge",
        judge_dim_rows,
        [
            "judge_id",
            "judge_slug",
            "judge_display_name",
            "is_active",
            "charges_covered",
            "judge_eligible_outcomes",
            "largest_charge_sample",
            "first_disposition_date",
            "last_disposition_date",
            "primary_court",
            "mc_outcomes",
            "cp_outcomes",
        ],
        "Judge roster with per-judge coverage in the live run.",
    )
    sink.write(
        "publish-safe",
        "dim_outcome_category",
        outcome_dim_rows,
        [
            "category_code",
            "display_name",
            "definition",
            "sort_order",
            "is_public",
            "is_conviction",
            "stage_group",
            "forum",
        ],
        "Outcome taxonomy with definitions and funnel stage grouping.",
    )
    sink.write(
        "publish-safe",
        "dim_sentencing_category",
        sentencing_dim_rows,
        [
            "category_code",
            "display_name",
            "definition",
            "sort_order",
            "is_public",
            "carries_duration",
        ],
        "Sentencing taxonomy with definitions.",
    )

    sink.write(
        "publish-safe",
        "fact_judge_charge_matrix",
        matrix_rows,
        list(matrix_rows[0].keys()) if matrix_rows else [],
        "VIZ 1 primary: one row per judge x charge cell, every rate plus "
        "Wilson bounds and the charge-wide baseline.",
    )
    sink.write(
        "publish-safe",
        "fact_judge_charge_outcomes_long",
        long_rows,
        list(long_rows[0].keys()) if long_rows else [],
        "VIZ 1 long form: one row per judge x charge x outcome category.",
    )

    sink.write(
        "publish-safe",
        "agg_charge_funnel_monthly",
        funnel_rows,
        list(funnel_rows[0].keys()) if funnel_rows else [],
        "VIZ 2 aggregate: journeys by entry month, entry court, charge and "
        "stage, with the cohort-maturity guard.",
    )
    sink.write(
        "publish-safe",
        "agg_outcome_by_disposition_month",
        disposition_month_rows,
        list(disposition_month_rows[0].keys()) if disposition_month_rows else [],
        "VIZ 2 companion: recorded outcomes by DISPOSITION month — the "
        "un-censored view of how the outcome mix moves.",
    )

    sink.write(
        "publish-safe",
        "agg_duration_percentiles",
        duration_rows,
        [
            "grain",
            "dimension",
            "dimension_value",
            "dimension_value_2",
            "n",
            "mean_days",
            "p10_days",
            "p25_days",
            "median_days",
            "p75_days",
            "p90_days",
            "iqr_days",
        ],
        "VIZ 4 aggregate: duration percentiles by court, grade, outcome and judge.",
    )

    sink.write(
        "publish-safe",
        "dq_corpus_summary",
        summary_rows,
        ["metric", "value", "section"],
        "VIZ 3: one-row-per-metric scorecard of the corpus and this export.",
    )
    sink.write(
        "publish-safe",
        "dq_ingest_status",
        ingest_rows,
        [
            "court",
            "source_status",
            "error_code",
            "documents",
            "documents_for_court",
            "pct_of_court",
            "first_imported",
            "last_imported",
        ],
        "VIZ 3: document intake state by court (not a time series — see "
        "dq_coverage_monthly).",
    )
    sink.write(
        "publish-safe",
        "dq_coverage_monthly",
        coverage_rows,
        list(coverage_rows[0].keys()) if coverage_rows else [],
        "VIZ 3: collection and parse coverage by docket FILING month and court.",
    )
    sink.write(
        "publish-safe",
        "dq_parse_warnings",
        warning_rows,
        [
            "warning_code",
            "severity",
            "blocks_public_use",
            "court",
            "filed_year",
            "occurrences",
            "charge_grain_occurrences",
            "dockets_affected",
            "dockets_in_scope",
            "pct_dockets_affected",
        ],
        "VIZ 3: parser warning rates by code, court and docket filing year.",
    )
    sink.write(
        "publish-safe",
        "dq_supersession_census",
        census_rows,
        [
            "filed_year",
            "court",
            "dockets",
            "dockets_with_originating_pointer",
            "pct_dockets_with_originating_pointer",
            "charges",
            "charges_with_orig_seq",
            "pct_charges_with_orig_seq",
            "superseded_charges",
            "pct_charges_superseded",
        ],
        "VIZ 3: MC->CP capture and supersession rates by docket filing year.",
    )
    sink.write(
        "publish-safe",
        "dq_supersession_tracing_monthly",
        trace_rows,
        [
            "entry_filed_month",
            "charge_group",
            "journeys",
            "held_population",
            "traced_mc_to_cp",
            "held_untraced",
            "pct_held_traced",
        ],
        "VIZ 3: how much of each month's held-for-court population is traced to CP.",
    )
    sink.write(
        "publish-safe",
        "dq_ineligibility_reasons",
        inelig_rows,
        [
            "grain",
            "reason_code",
            "facts",
            "facts_in_grain",
            "pct_of_grain",
            "public_eligible_in_grain",
            "judge_eligible_in_grain",
        ],
        "VIZ 3: why facts fall out of the public and judge grains.",
    )
    sink.write(
        "publish-safe",
        "dq_judge_sample_precision",
        precision_rows,
        [
            "judge_slug",
            "charge_slug",
            "charge_group",
            "sample_size",
            "meets_min_cell",
            "is_thin_data",
            "pct_dismissed",
            "dismissed_wilson_low_pct",
            "dismissed_wilson_high_pct",
            "dismissed_wilson_width_pp",
            "precision_band",
            "charge_baseline_pct_dismissed",
            "interval_excludes_charge_baseline",
        ],
        "VIZ 3: small-sample judge cells ranked by Wilson interval width.",
    )

    sink.write(
        "internal-only",
        "fact_charge_journeys",
        journeys,
        list(journeys[0].keys()) if journeys else [],
        "VIZ 2/4 row grain: one row per deduplicated charge journey with "
        "MC->CP lineage dates and durations.",
    )
    sink.write(
        "internal-only",
        "fact_case_durations",
        case_rows,
        list(case_rows[0].keys()) if case_rows else [],
        "VIZ 4 row grain: one row per docket filed in window, with durations.",
    )

    reconciliation = "exact" if not problems else f"{len(problems)} mismatches"
    write_readme(out_dir, run, matrix_rows, journeys, args.min_cell, reconciliation)

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "aggregate_run": prefix(run_id),
        "fact_build_run": prefix(build_run_id),
        "data_range": [
            run["data_range_start"].isoformat(),
            run["data_range_end"].isoformat(),
        ],
        "taxonomy_version": run["taxonomy_version"],
        "filed_date_floor": FILED_DATE_FLOOR_DEFAULT.isoformat(),
        "min_cell": args.min_cell,
        "volume_reconciliation": reconciliation,
        "journey_report": journey_report,
        "files": sink.written,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    logger.info("manifest written; extract root: %s", out_dir)
    print(out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
