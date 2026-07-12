"""Judge-roster coverage report (Task 22.3, AC 8).

Runs the pure :class:`JudgeMatcher` over the corpus's distinct judge-name values
in the two raw judge fields — ``parsed.dockets.assigned_judge_raw`` (docket
grain) and ``parsed.charges.disposition_judge_raw`` (charge grain) — against the
seeded roster snapshot, and writes a coverage report to ``~/court-data/reports/``:

- per-field match-method distribution (distinct values and frequency-weighted);
- the ABSENT class (null / blank) counted SEPARATELY from ``unmatched`` so the
  "matched of present" denominator is honest (REQUIRED FIX);
- the unmatched tail values (report FILE only — never console).

Console hygiene is TIGHTER than 22.2 (pinned decision 5): the raw judge values
are exactly the fields the sentinel finding flagged as sometimes carrying
defendant-name collisions, so NO raw value touches the console — console carries
counts, per-method frequencies, the unmatched-tail SIZE, and the ambiguous count
only. The values live solely in the report file. Runs end-to-end: seed the roster
(``pnpm db:seed``) first, then invoke this.

Usage::

    python -m pipeline.reports.judge_coverage
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import Counter
from pathlib import Path

from pipeline.normalization.judge_matcher import JudgeMatcher, RosterSnapshot
from pipeline.normalization.judge_roster_loader import load_judge_roster
from pipeline.normalization.vocab import (
    MATCH_METHOD_AMBIGUOUS,
    MATCH_METHOD_UNMATCHED,
    MATCH_METHODS,
)
from pipeline.paths import inside_git_worktree
from pipeline.seam_check import running_in_ci

logger = logging.getLogger("pipeline.reports.judge_coverage")

DEFAULT_REPORT_DIR = Path.home() / "court-data" / "reports"

# (field label, table, column) — schema identifiers only, no corpus data.
JUDGE_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("assigned", "parsed.dockets", "assigned_judge_raw"),
    ("disposition", "parsed.charges", "disposition_judge_raw"),
)


def _fetch_value_frequencies(
    database_url: str, table: str, column: str
) -> list[tuple[str | None, int]]:
    from pipeline.db import connect

    with connect(database_url) as conn, conn.cursor() as cur:
        # noqa: S608 - table/column are module constants, never user/corpus input.
        cur.execute(f"SELECT {column}, COUNT(*) FROM {table} GROUP BY {column}")  # noqa: S608
        return list(cur.fetchall())


def _field_stats(
    matcher: JudgeMatcher, value_freqs: list[tuple[str | None, int]]
) -> dict[str, object]:
    """Classify one field's distinct values; return counts + the unmatched tail.

    The ABSENT class (``match`` returns ``None`` for null / blank) is tracked
    separately from ``unmatched`` so coverage denominators are honest.
    """
    method_distinct: Counter[str] = Counter()
    method_rows: Counter[str] = Counter()
    absent_distinct = 0
    absent_rows = 0
    unmatched_tail: list[tuple[int, str | None]] = []

    for value, freq in value_freqs:
        result = matcher.match(value)
        if result is None:
            absent_distinct += 1
            absent_rows += freq
            continue
        method_distinct[result.match_method] += 1
        method_rows[result.match_method] += freq
        if result.match_method == MATCH_METHOD_UNMATCHED:
            unmatched_tail.append((freq, value))

    present_distinct = sum(method_distinct.values())
    present_rows = sum(method_rows.values())
    matched_rows = present_rows - method_rows.get(MATCH_METHOD_UNMATCHED, 0)
    return {
        "distinct_total": len(value_freqs),
        "absent_distinct": absent_distinct,
        "absent_rows": absent_rows,
        "present_distinct": present_distinct,
        "present_rows": present_rows,
        "matched_rows": matched_rows,
        "method_distinct": method_distinct,
        "method_rows": method_rows,
        "unmatched_tail_size": len(unmatched_tail),
        "ambiguous_distinct": method_distinct.get(MATCH_METHOD_AMBIGUOUS, 0),
        "unmatched_tail": unmatched_tail,
    }


def build_judge_coverage_report(
    snapshot: RosterSnapshot,
    field_value_freqs: dict[str, list[tuple[str | None, int]]],
) -> tuple[str, dict[str, dict[str, object]]]:
    """Return ``(report_text, per_field_headline)`` for the coverage run.

    ``report_text`` (file only) includes the unmatched tail VALUES;
    ``per_field_headline`` carries counts only (console + completion report).
    """
    matcher = JudgeMatcher(snapshot)
    headline: dict[str, dict[str, object]] = {}
    lines: list[str] = [
        "Judge-roster coverage report",
        f"roster entries: {len(snapshot.entries)}",
        "",
    ]

    for label, value_freqs in field_value_freqs.items():
        stats = _field_stats(matcher, value_freqs)
        headline[label] = stats
        pd = stats["present_distinct"]
        pr = stats["present_rows"]
        mr = stats["matched_rows"]
        lines.append(f"=== field: {label} ===")
        lines.append(f"distinct values (incl. absent): {stats['distinct_total']}")
        lines.append(
            f"absent (null/blank): distinct={stats['absent_distinct']} "
            f"rows={stats['absent_rows']}"
        )
        lines.append(f"present: distinct={pd} rows={pr} matched_rows={mr}")
        lines.append("method        distinct  rows_weighted")
        method_distinct: Counter[str] = stats["method_distinct"]  # type: ignore[assignment]
        method_rows: Counter[str] = stats["method_rows"]  # type: ignore[assignment]
        for method in sorted(MATCH_METHODS):
            d = method_distinct.get(method, 0)
            c = method_rows.get(method, 0)
            lines.append(f"{method:<14}{d:<10}{c}")
        lines.append(f"unmatched tail size (distinct): {stats['unmatched_tail_size']}")
        lines.append(f"ambiguous (distinct): {stats['ambiguous_distinct']}")
        lines.append("")
        lines.append("--- unmatched tail values (report file only) ---")
        tail: list[tuple[int, str | None]] = stats["unmatched_tail"]  # type: ignore[assignment]
        for freq, value in sorted(tail, key=lambda t: -t[0]):
            lines.append(f"  {freq:>4}  {value!r}")
        lines.append("")

    return "\n".join(lines), headline


def _print_headline(headline: dict[str, dict[str, object]]) -> None:
    """Print counts ONLY — never a raw judge value (pinned decision 5)."""
    for label, stats in headline.items():
        print(f"[{label}] distinct_total={stats['distinct_total']}")
        print(
            f"  absent(null/blank): distinct={stats['absent_distinct']} "
            f"rows={stats['absent_rows']}"
        )
        pd = stats["present_distinct"]
        pr = stats["present_rows"]
        mr = stats["matched_rows"]
        print(f"  present: distinct={pd} rows={pr} matched_rows={mr}")
        method_distinct: Counter[str] = stats["method_distinct"]  # type: ignore[assignment]
        method_rows: Counter[str] = stats["method_rows"]  # type: ignore[assignment]
        print("  match-method (distinct / rows_weighted):")
        for method in sorted(MATCH_METHODS):
            print(
                f"    {method:<10} {method_distinct.get(method, 0):<4} / "
                f"{method_rows.get(method, 0)}"
            )
        print(f"  unmatched_tail_size={stats['unmatched_tail_size']}")
        print(f"  ambiguous_distinct={stats['ambiguous_distinct']}")


def run(database_url: str, *, report_path: Path) -> int:
    if inside_git_worktree(report_path.parent):
        logger.error("refusing to write a report inside a git working tree")
        return 2
    snapshot = load_judge_roster(database_url)
    field_value_freqs = {
        label: _fetch_value_frequencies(database_url, table, column)
        for label, table, column in JUDGE_FIELDS
    }
    report_text, headline = build_judge_coverage_report(snapshot, field_value_freqs)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text)
    _print_headline(headline)
    print(f"report written: {report_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Judge-roster coverage report.")
    parser.add_argument("--report-name", default="22.3-judge-coverage")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args(argv)

    if running_in_ci():
        logger.error(
            "judge-coverage report reads local court data and must never run in "
            "a CI environment; refusing"
        )
        return 2
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url.strip():
        logger.error(
            "DATABASE_URL is required; set it in the environment "
            "(its value is never printed or written)"
        )
        return 2
    report_path = args.report_dir / f"{args.report_name}.txt"
    return run(database_url, report_path=report_path)


if __name__ == "__main__":
    sys.exit(main())
