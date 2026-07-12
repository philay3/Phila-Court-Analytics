"""Charge-roster coverage report (Task 22.2, AC 8/pinned decision 9).

Runs the pure :class:`ChargeMatcher` over the corpus's distinct
``(statute, offense)`` charge pairs (loaded from ``parsed.charges``) against the
seeded roster snapshot and writes a coverage report to ``~/court-data/reports/``:

- match-method distribution (distinct pairs and frequency-weighted charges);
- coverage of the "appears >= N times" statute set (the roster floor, N given);
- the top unmatched pairs by frequency (report file only).

Console output: counts, match methods, and statute-code cites only — never
offense-text values (those go only to the report file). Runs end-to-end: seed
the roster (``pnpm db:seed``) first, then invoke this.

Usage::

    python -m pipeline.reports.charge_coverage --n 5
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import Counter
from pathlib import Path

from pipeline.normalization.charge_matcher import ChargeMatcher, RosterSnapshot
from pipeline.normalization.charge_roster_loader import load_charge_roster
from pipeline.normalization.vocab import MATCH_METHOD_UNMATCHED, MATCH_METHODS
from pipeline.paths import inside_git_worktree
from pipeline.seam_check import running_in_ci

logger = logging.getLogger("pipeline.reports.charge_coverage")

DEFAULT_REPORT_DIR = Path.home() / "court-data" / "reports"


def _fetch_charges(database_url: str) -> list[tuple[str | None, str | None]]:
    from pipeline.db import connect

    with connect(database_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT statute, offense FROM parsed.charges")
        return list(cur.fetchall())


def build_coverage_report(
    snapshot: RosterSnapshot,
    charges: list[tuple[str | None, str | None]],
    *,
    n_floor: int,
) -> tuple[str, dict[str, int]]:
    """Return ``(report_text, headline_counts)`` for the coverage run.

    ``headline_counts`` carries the numbers echoed to console and the completion
    report (distinct pairs, total charges, per-method distinct counts, and the
    >= N statute coverage) — no field values.
    """
    matcher = ChargeMatcher(snapshot)

    pair_freq: Counter[tuple[str | None, str | None]] = Counter(charges)
    total_charges = len(charges)

    # Match-method distribution over distinct pairs (and frequency-weighted).
    method_distinct: Counter[str] = Counter()
    method_charges: Counter[str] = Counter()
    unmatched_pairs: list[tuple[int, str | None, str | None]] = []
    # Per-statute coverage: a statute value is "covered" when its DOMINANT
    # (most-frequent) charge pairing normalizes to a matched method — statute
    # OR text tier. This reflects the floor as "the roster normalizes the
    # high-frequency charges", since the roster covers some alternate-granularity
    # codes through the offense text rather than a literal statute_code.
    dominant_pairing: dict[str | None, tuple[int, str | None]] = {}
    statute_freq: Counter[str | None] = Counter()
    for (statute, offense), freq in pair_freq.items():
        result = matcher.match(statute=statute, offense=offense)
        method_distinct[result.match_method] += 1
        method_charges[result.match_method] += freq
        statute_freq[statute] += freq
        if result.match_method == MATCH_METHOD_UNMATCHED:
            unmatched_pairs.append((freq, statute, offense))
        best = dominant_pairing.get(statute)
        if best is None or freq > best[0]:
            dominant_pairing[statute] = (freq, offense)

    over_floor = [(s, f) for s, f in statute_freq.items() if f >= n_floor]
    covered: list[tuple[str | None, int]] = []
    uncovered: list[tuple[str | None, int, str]] = []
    for statute, freq in over_floor:
        _, dom_offense = dominant_pairing[statute]
        method = matcher.match(statute=statute, offense=dom_offense).match_method
        if method == MATCH_METHOD_UNMATCHED:
            uncovered.append((statute, freq, method))
        else:
            covered.append((statute, freq))

    lines: list[str] = []
    lines.append("Charge-roster coverage report")
    lines.append(f"roster entries: {len(snapshot.entries)}")
    lines.append(f"total charges: {total_charges}")
    lines.append(f"distinct (statute, offense) pairs: {len(pair_freq)}")
    lines.append("")
    lines.append("=== match-method distribution ===")
    lines.append("method       distinct_pairs  charges_weighted")
    for method in sorted(MATCH_METHODS):
        dcount = method_distinct.get(method, 0)
        ccount = method_charges.get(method, 0)
        lines.append(f"{method:<13}{dcount:<16}{ccount}")
    lines.append("")
    lines.append(
        f"=== >= {n_floor}x statute-coverage floor (dominant-pairing match) ==="
    )
    lines.append(f"distinct statutes appearing >= {n_floor}x: {len(over_floor)}")
    lines.append(f"covered (dominant pairing matches): {len(covered)}")
    lines.append(f"NOT covered (dominant pairing unmatched): {len(uncovered)}")
    lines.append("uncovered statute codes (freq, dominant method):")
    for statute, freq, method in sorted(uncovered, key=lambda kv: -kv[1]):
        lines.append(f"  {freq:>4}  {statute!r}  [{method}]")
    lines.append("")
    lines.append("=== top unmatched (statute, offense) pairs by frequency ===")
    for freq, statute, offense in sorted(unmatched_pairs, key=lambda t: -t[0])[:100]:
        lines.append(f"  {freq:>4}  statute={statute!r}  offense={offense!r}")
    lines.append("")

    headline = {
        "roster_entries": len(snapshot.entries),
        "total_charges": total_charges,
        "distinct_pairs": len(pair_freq),
        "over_floor": len(over_floor),
        "covered": len(covered),
        "uncovered": len(uncovered),
        **{
            f"method_distinct::{m}": method_distinct.get(m, 0)
            for m in sorted(MATCH_METHODS)
        },
        **{
            f"method_charges::{m}": method_charges.get(m, 0)
            for m in sorted(MATCH_METHODS)
        },
    }
    return "\n".join(lines), headline


def _print_headline(headline: dict[str, int], n_floor: int) -> None:
    print(f"roster_entries={headline['roster_entries']}")
    print(f"total_charges={headline['total_charges']}")
    print(f"distinct_pairs={headline['distinct_pairs']}")
    print("match-method distribution (distinct_pairs / charges_weighted):")
    for method in sorted(MATCH_METHODS):
        d = headline[f"method_distinct::{method}"]
        c = headline[f"method_charges::{method}"]
        print(f"  {method:<10} {d:<5} / {c}")
    print(
        f">= {n_floor}x statutes: {headline['over_floor']} "
        f"covered={headline['covered']} uncovered={headline['uncovered']}"
    )


def run(database_url: str, *, n_floor: int, report_path: Path) -> int:
    if inside_git_worktree(report_path.parent):
        logger.error("refusing to write a report inside a git working tree")
        return 2
    snapshot = load_charge_roster(database_url)
    charges = _fetch_charges(database_url)
    report_text, headline = build_coverage_report(snapshot, charges, n_floor=n_floor)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text)
    _print_headline(headline, n_floor)
    print(f"report written: {report_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Charge-roster coverage report.")
    parser.add_argument("--n", type=int, default=5, help="coverage floor N")
    parser.add_argument("--report-name", default="22.2-charge-coverage")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args(argv)

    if running_in_ci():
        logger.error(
            "charge-coverage report reads local court data and must never run in "
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
    return run(database_url, n_floor=args.n, report_path=report_path)


if __name__ == "__main__":
    sys.exit(main())
