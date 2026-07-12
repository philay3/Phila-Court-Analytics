"""Outcome-mapping coverage report (Task 22.4, AC 8 — the acceptance authority).

Runs the pure :class:`OutcomeMapper` over the corpus's distinct
``parsed.charges.disposition_raw`` values (with frequencies) against the taxonomy
loaded from taxonomy.json, and writes a coverage report to
``~/court-data/reports/``. It reports the mapped / unmapped / held split that the
task's acceptance authority checks:

- **mapped** — a terminal disposition present in the exact-match table, broken
  down per outcome code (distinct values and frequency-weighted rows);
- **unmapped -> unknown** — a terminal disposition absent from the table (its
  values live in the report FILE only, never console);
- **held (null disposition_raw)** — the AC-4 carve-out: no fact, no review. At
  the disposition grain a held charge is one whose ``disposition_raw`` IS NULL
  (:meth:`OutcomeMapper.map` returns ``None``).

Console hygiene: counts, taxonomy codes, and the taxonomy version only — never a
raw disposition value. The unmapped-tail values (standardized CPCMS disposition
phrases, but kept file-only for consistency with the 22.2/22.3 coverage tools)
go solely to the report file. Refuses to run in CI (``running_in_ci`` guard) and
reads ``DATABASE_URL`` only at the CLI boundary (never printed or written). Runs
end-to-end: it needs the loaded corpus and the generated taxonomy.json
(`pnpm generate`).

Usage::

    python -m pipeline.reports.outcome_coverage
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import Counter
from pathlib import Path

from pipeline.normalization.outcome_mapper import (
    OUTCOME_UNKNOWN,
    OutcomeMapper,
    load_taxonomy_snapshot,
)
from pipeline.paths import inside_git_worktree
from pipeline.seam_check import running_in_ci

logger = logging.getLogger("pipeline.reports.outcome_coverage")

DEFAULT_REPORT_DIR = Path.home() / "court-data" / "reports"

# The single disposition field mapped this task — schema identifiers only.
DISPOSITION_TABLE = "parsed.charges"
DISPOSITION_COLUMN = "disposition_raw"


def _fetch_value_frequencies(
    database_url: str,
) -> list[tuple[str | None, int]]:
    from pipeline.db import connect  # local import keeps psycopg off the import path

    with connect(database_url) as conn, conn.cursor() as cur:
        # noqa: S608 - table/column are module constants, never user/corpus input.
        cur.execute(
            f"SELECT {DISPOSITION_COLUMN}, COUNT(*) "  # noqa: S608
            f"FROM {DISPOSITION_TABLE} GROUP BY {DISPOSITION_COLUMN}"
        )
        return list(cur.fetchall())


def classify(
    mapper: OutcomeMapper, value_freqs: list[tuple[str | None, int]]
) -> dict[str, object]:
    """Classify each distinct disposition value into the mapped/unmapped/held split.

    Returns counts + the unmapped tail (values, report-file only). ``held`` is the
    null-disposition class (``map`` returns ``None``).
    """
    code_distinct: Counter[str] = Counter()
    code_rows: Counter[str] = Counter()
    mapped_distinct = mapped_rows = 0
    unmapped_distinct = unmapped_rows = 0
    held_distinct = held_rows = 0
    unmapped_tail: list[tuple[int, str]] = []

    for value, freq in value_freqs:
        result = mapper.map(value)
        if result is None:  # held carve-out (null disposition_raw)
            held_distinct += 1
            held_rows += freq
            continue
        if result.mapped:
            mapped_distinct += 1
            mapped_rows += freq
            code_distinct[result.outcome_code] += 1
            code_rows[result.outcome_code] += freq
        else:  # unmapped -> unknown
            unmapped_distinct += 1
            unmapped_rows += freq
            unmapped_tail.append((freq, result.raw_value))

    return {
        "total_distinct": len(value_freqs),
        "total_rows": sum(freq for _v, freq in value_freqs),
        "mapped_distinct": mapped_distinct,
        "mapped_rows": mapped_rows,
        "code_distinct": code_distinct,
        "code_rows": code_rows,
        "unmapped_distinct": unmapped_distinct,
        "unmapped_rows": unmapped_rows,
        "held_distinct": held_distinct,
        "held_rows": held_rows,
        "unmapped_tail": unmapped_tail,
    }


def build_outcome_coverage_report(
    taxonomy_version: str, stats: dict[str, object]
) -> str:
    """Full report text (file only) — INCLUDES the unmapped-tail values."""
    code_distinct: Counter[str] = stats["code_distinct"]  # type: ignore[assignment]
    code_rows: Counter[str] = stats["code_rows"]  # type: ignore[assignment]
    lines = [
        "Outcome-mapping coverage report",
        f"taxonomy_version: {taxonomy_version}",
        f"total rows: {stats['total_rows']}  (distinct values incl. null: "
        f"{stats['total_distinct']})",
        "",
        f"held (null disposition_raw): rows={stats['held_rows']} "
        f"distinct={stats['held_distinct']}  -> no fact, no review",
        f"mapped: rows={stats['mapped_rows']} distinct={stats['mapped_distinct']}",
    ]
    for code in sorted(code_rows):
        lines.append(
            f"  {code:<16} rows={code_rows[code]:<6} distinct={code_distinct[code]}"
        )
    lines.append(
        f"unmapped -> {OUTCOME_UNKNOWN}: rows={stats['unmapped_rows']} "
        f"distinct={stats['unmapped_distinct']}"
    )
    lines.append("")
    lines.append("--- unmapped disposition values (report file only) ---")
    tail: list[tuple[int, str]] = stats["unmapped_tail"]  # type: ignore[assignment]
    for freq, value in sorted(tail, key=lambda t: (-t[0], t[1])):
        lines.append(f"  {freq:>4}  {value!r}")
    lines.append("")
    return "\n".join(lines)


def print_headline(taxonomy_version: str, stats: dict[str, object]) -> None:
    """Print counts + codes ONLY — never a raw disposition value."""
    code_distinct: Counter[str] = stats["code_distinct"]  # type: ignore[assignment]
    code_rows: Counter[str] = stats["code_rows"]  # type: ignore[assignment]
    print(f"taxonomy_version={taxonomy_version}")
    print(f"total_rows={stats['total_rows']}")
    print(
        f"held (disposition_raw null): rows={stats['held_rows']} "
        f"distinct={stats['held_distinct']}"
    )
    print(f"mapped: rows={stats['mapped_rows']} distinct={stats['mapped_distinct']}")
    for code in sorted(code_rows):
        print(f"  {code:<16} rows={code_rows[code]:<6} distinct={code_distinct[code]}")
    print(
        f"unmapped->{OUTCOME_UNKNOWN}: rows={stats['unmapped_rows']} "
        f"distinct={stats['unmapped_distinct']}"
    )


def run(database_url: str, *, report_path: Path) -> int:
    if inside_git_worktree(report_path.parent):
        logger.error("refusing to write a report inside a git working tree")
        return 2
    taxonomy = load_taxonomy_snapshot()
    mapper = OutcomeMapper(taxonomy)
    value_freqs = _fetch_value_frequencies(database_url)
    stats = classify(mapper, value_freqs)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        build_outcome_coverage_report(taxonomy.taxonomy_version, stats)
    )
    print_headline(taxonomy.taxonomy_version, stats)
    print(f"report written: {report_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Outcome-mapping coverage report.")
    parser.add_argument("--report-name", default="22.4-outcome-coverage")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args(argv)

    if running_in_ci():
        logger.error(
            "outcome-coverage report reads local court data and must never run in "
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
