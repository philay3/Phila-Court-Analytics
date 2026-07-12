"""Distinct-value + frequency report over corpus text fields (Task 22.2, AC 1).

Field-parameterized so Task 22.3 can reuse it verbatim for the judge fields:
call :func:`run` (or the CLI) with a different ``table``/``columns``. The report
gives, per column, the distinct-value count and a coverage-by-threshold table
(how many distinct values appear >= N times and what share of rows they cover),
plus the full distinct-value list ordered by frequency.

Console output is counts + coverage buckets ONLY — never the field values
themselves (hygiene is field-agnostic, so it holds for offense text and judge
names alike). The full detail, including values, goes only to the report file
under ``~/court-data/reports/``.

Usage::

    python -m pipeline.reports.distinct_values                 # charge default
    python -m pipeline.reports.distinct_values \
        --table parsed.charges --column statute --column offense \
        --report-name 22.2-distinct-values
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from pipeline.paths import inside_git_worktree
from pipeline.seam_check import running_in_ci

logger = logging.getLogger("pipeline.reports.distinct_values")

# Coverage thresholds surfaced in the bucket table (N = "appears >= N times").
THRESHOLDS: tuple[int, ...] = (1, 2, 3, 5, 10, 20, 50)

# Default field set: the charge statute/offense columns (Task 22.2). 22.3 passes
# its own table/columns; nothing corpus-derived is embedded here.
DEFAULT_TABLE = "parsed.charges"
DEFAULT_COLUMNS: tuple[str, ...] = ("statute", "offense")

DEFAULT_REPORT_DIR = Path.home() / "court-data" / "reports"

# Only simple identifiers are ever interpolated into the SELECT (never user data);
# this guard keeps that contract explicit and injection-proof.
_IDENT = re.compile(r"^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)?$")


def coverage_for_n(counter: Counter[str], n: int) -> tuple[int, int]:
    """``(distinct values with freq >= n, sum of their frequencies)``."""
    kept = [(v, c) for v, c in counter.items() if c >= n]
    return len(kept), sum(c for _, c in kept)


def _bucket_lines(counter: Counter[str], total: int) -> list[str]:
    lines = ["N   distinct>=N  rows_covered  row_coverage_pct"]
    for n in THRESHOLDS:
        d, c = coverage_for_n(counter, n)
        pct = (100.0 * c / total) if total else 0.0
        lines.append(f"{n:<4}{d:<13}{c:<14}{pct:.1f}%")
    return lines


def build_report(
    counters: dict[str, Counter[str]], total_rows: int, *, table: str
) -> str:
    """The full report text (INCLUDING field values) written to the report file."""
    lines = [
        f"Distinct-value report over {table}",
        f"total rows: {total_rows}",
        "",
    ]
    for column, counter in counters.items():
        n_null = sum(c for v, c in counter.items() if v is None)
        n_blank = sum(
            c for v, c in counter.items() if v is not None and str(v).strip() == ""
        )
        lines.append(
            f"=== {column}: {len(counter)} distinct (null={n_null} blank={n_blank}) ==="
        )
        lines.extend(_bucket_lines(counter, total_rows))
        lines.append("")
    for column, counter in counters.items():
        lines.append(f"=== {column}: ALL distinct values by frequency (desc) ===")
        for value, count in sorted(
            counter.items(), key=lambda kv: (-kv[1], str(kv[0]))
        ):
            lines.append(f"{count:>5}  {value!r}")
        lines.append("")
    return "\n".join(lines)


def _console_summary(counters: dict[str, Counter[str]], total_rows: int) -> None:
    """Print counts + coverage buckets ONLY (never field values)."""
    print(f"total_rows={total_rows}")
    for column, counter in counters.items():
        print(f"[{column}] distinct={len(counter)}")
        for n in THRESHOLDS:
            d, c = coverage_for_n(counter, n)
            pct = (100.0 * c / total_rows) if total_rows else 0.0
            print(f"  N={n:<3} distinct>={n}: {d:<4} rows_covered: {c:<6} ({pct:.1f}%)")


def _fetch_counters(
    database_url: str, table: str, columns: Sequence[str]
) -> tuple[dict[str, Counter[str]], int]:
    from pipeline.db import connect  # local import keeps psycopg off the import path

    for ident in (table, *columns):
        if not _IDENT.match(ident):
            raise ValueError(f"unsafe identifier: {ident!r}")
    col_sql = ", ".join(columns)
    counters: dict[str, Counter[str]] = {c: Counter() for c in columns}
    with connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {col_sql} FROM {table}")  # noqa: S608 - idents guarded
        rows = cur.fetchall()
    for row in rows:
        for column, value in zip(columns, row, strict=True):
            counters[column][value] += 1
    return counters, len(rows)


def run(
    database_url: str,
    *,
    table: str = DEFAULT_TABLE,
    columns: Sequence[str] = DEFAULT_COLUMNS,
    report_path: Path,
) -> int:
    """Generate the report to ``report_path`` and print the console summary."""
    if inside_git_worktree(report_path.parent):
        logger.error("refusing to write a report inside a git working tree")
        return 2
    counters, total_rows = _fetch_counters(database_url, table, list(columns))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_report(counters, total_rows, table=table))
    _console_summary(counters, total_rows)
    print(f"report written: {report_path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Distinct-value corpus report.")
    parser.add_argument("--table", default=DEFAULT_TABLE)
    parser.add_argument("--column", dest="columns", action="append")
    parser.add_argument("--report-name", default="22.2-distinct-values")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args(argv)

    if running_in_ci():
        logger.error(
            "distinct-value report reads local court data and must never run in "
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

    columns = args.columns or list(DEFAULT_COLUMNS)
    report_path = args.report_dir / f"{args.report_name}.txt"
    return run(database_url, table=args.table, columns=columns, report_path=report_path)


if __name__ == "__main__":
    sys.exit(main())
