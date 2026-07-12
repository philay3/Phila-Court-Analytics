"""Sentencing recon + coverage report (Task 22.5).

Sibling of :mod:`pipeline.reports.outcome_coverage`; same posture — refuses to run
in CI (``running_in_ci`` guard), reads ``DATABASE_URL`` only at the CLI boundary
(never printed or written), refuses to write a report inside a git working tree,
and keeps CONSOLE output to counts + controlled ``sentence_type`` vocabulary only
(never ``raw_text``, dollar-line text, or third-party names).

Two modes:

- ``recon`` (Task 22.5 Part A) — MAP-INDEPENDENT. Reports the distinct
  ``parsed.sentences.sentence_type`` distribution and, per type, the money-amount
  bucket split (0 / exactly-1-distinct / >=2-distinct parseable amounts under the
  CANDIDATE currency regex), the restitution / community-service signal counts,
  and the Fine/Fines whole-token counts (the ``Fines and Costs`` -> ``fine`` vs
  ``costs_fees`` gate input). No sentence-type -> category map is consulted, so it
  runs BEFORE the map-approval gate to produce the curation input for it.
- ``coverage`` (Task 22.5 Part B) — the acceptance-authority corpus rerun; runs
  the finalized mapper + money extractor over the corpus. **Lands in Part B**
  (after the map gate); this module currently implements ``recon`` only.

Usage::

    python -m pipeline.reports.sentencing_coverage            # recon (default)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from pipeline.normalization.money_extractor import distinct_amounts, token_to_cents
from pipeline.normalization.sentencing_mapper import (
    CATEGORY_COMMUNITY_SERVICE,
    CATEGORY_RESTITUTION,
    SENTENCING_UNKNOWN,
    SentencingMapper,
    load_sentencing_taxonomy,
)
from pipeline.paths import inside_git_worktree
from pipeline.seam_check import running_in_ci

logger = logging.getLogger("pipeline.reports.sentencing_coverage")

DEFAULT_REPORT_DIR = Path.home() / "court-data" / "reports"

# The sentence-component fields this recon reads — schema identifiers only.
SENTENCE_TABLE = "parsed.sentences"
SENTENCE_TYPE_COLUMN = "sentence_type"
RAW_TEXT_COLUMN = "raw_text"

# taxonomy.json (generated, gitignored; `pnpm generate` builds it) — read ONLY
# for the version stamp on the recon header. The map itself is not consulted.
_TAXONOMY_RELPATH = ("packages", "taxonomy", "generated", "taxonomy.json")

# --- Candidate patterns (Task 22.5 Part A; FINALIZED at the map gate) ---------
# Currency-shaped money token: comma-grouped, OR a `.NN` decimal amount, OR a
# `$`-prefixed bare integer. This deliberately EXCLUDES bare non-`$` integers
# (e.g. "18" in "18 months") so sentence-duration digits are not miscounted as
# money; the recon separately reports "0 amounts but has digits" so the gate can
# size what a looser regex would add.
_CURRENCY_TOKEN = re.compile(
    r"\$?\d{1,3}(?:,\d{3})+(?:\.\d{2})?"  # 1,234 / 1,234.56 / 12,345,678.00
    r"|\$?\d+\.\d{2}"  # 500.00 / 1234.56
    r"|\$\d+"  # $500
)
# The `$`-REQUIRED money analysis uses the CANONICAL regex from money_extractor
# (imported: token_to_cents + distinct_amounts) — the ONE money-regex definition
# project-wide. Part A recon proved the `$`-optional `.NN` candidate above matches
# sentence-DURATION figures ("11.00 months") en masse; the gate LOCKED `$`-required.
# Both are reported so the contamination stays visible in the committed recon.
_RESTITUTION = re.compile(r"\bRestitution\b", re.IGNORECASE)
_COMMUNITY_SERVICE = re.compile(r"\bCommunity Service\b", re.IGNORECASE)
_HOURS = re.compile(r"\b\d+\s*hours?\b", re.IGNORECASE)
_FINE = re.compile(r"\bFines?\b", re.IGNORECASE)
_HAS_DIGIT = re.compile(r"\d")
_HAS_DOLLAR = re.compile(r"\$")
_DECIMAL_AMT = re.compile(r"\$?\d+\.\d{2}")
_COMMA_AMT = re.compile(r"\d{1,3}(?:,\d{3})+")
# Leading "Fines and Costs" label, stripped before searching for a DISCRETE fine
# mention (so a Fines-and-Costs component's own label is not counted as a fine).
_FAC_LABEL = re.compile(r"^\s*Fines?\s+and\s+Costs\b", re.IGNORECASE)


def distinct_candidate_cents(text: str) -> set[int]:
    """DISTINCT integer-cent amounts under the DURATION-CONTAMINATED candidate.

    Diagnostic only — kept so the committed recon still shows why the gate rejected
    the `$`-optional candidate (it matches "11.00 months" as "$11.00"). The clean
    money signal is :func:`money_extractor.distinct_amounts` (``$``-required).
    """
    return {token_to_cents(m.group(0)) for m in _CURRENCY_TOKEN.finditer(text)}


def money_bucket(n_distinct: int) -> str:
    """Bucket a distinct-amount count into ``'0'`` / ``'1'`` / ``'2+'``."""
    if n_distinct == 0:
        return "0"
    if n_distinct == 1:
        return "1"
    return "2+"


def _fine_beyond_label(sentence_type: str, raw_text: str) -> bool:
    """True iff a Fine/Fines token appears OTHER than the leading FAC label.

    For a ``Fines and Costs`` component whose ``raw_text`` opens with that label,
    strip the label first, so only a DISCRETE fine mention (a second occurrence,
    or a fine in a non-FAC component) counts. This isolates "is a discrete `fine`
    category worth populating" from the ever-present type label.
    """
    stripped = _FAC_LABEL.sub("", raw_text, count=1)
    return bool(_FINE.search(stripped))


def recon_counts(rows: Sequence[tuple[str, str]]) -> dict[str, object]:
    """Compute the Part A recon counts from ``(sentence_type, raw_text)`` rows.

    Pure (no DB, no I/O). Returns per-``sentence_type`` count tables plus totals;
    every value is a COUNT or a controlled ``sentence_type`` string — never any
    ``raw_text`` content.
    """
    per_type: dict[str, Counter[str]] = {}
    type_freq: Counter[str] = Counter()

    for sentence_type, raw_text in rows:
        stype = sentence_type if sentence_type is not None else "<null>"
        text = raw_text or ""
        type_freq[stype] += 1
        c = per_type.setdefault(stype, Counter())

        n_distinct = len(distinct_candidate_cents(text))
        c[f"money_{money_bucket(n_distinct)}"] += 1
        if n_distinct == 0 and _HAS_DIGIT.search(text):
            c["zero_amt_has_digits"] += 1

        # `$`-required money — the clean money signal (durations carry no `$`).
        n_dollar = len(distinct_amounts(text))
        c[f"dmoney_{money_bucket(n_dollar)}"] += 1

        # signals: restitution matches sentence_type OR raw_text (whole token).
        has_restitution = bool(_RESTITUTION.search(text) or _RESTITUTION.search(stype))
        if has_restitution:
            c["restitution"] += 1
            # restitution mention carrying NO `$` amount -> money_unparseable-shaped
            # (category stands, amount absent); sizes the zero-amount arm.
            if n_dollar == 0:
                c["restitution_no_dollar"] += 1
        if _COMMUNITY_SERVICE.search(text):
            c["cs_literal"] += 1
        elif _HOURS.search(text):
            c["hours_only"] += 1

        if _HAS_DOLLAR.search(text):
            c["has_dollar"] += 1
        if _DECIMAL_AMT.search(text):
            c["has_decimal"] += 1
        if _COMMA_AMT.search(text):
            c["has_comma"] += 1

        if _FINE.search(text):
            c["fine_token"] += 1
        if _fine_beyond_label(stype, text):
            c["fine_nonlabel"] += 1

    return {
        "total": sum(type_freq.values()),
        "distinct_types": len(type_freq),
        "type_freq": type_freq,
        "per_type": per_type,
    }


_METRICS: tuple[str, ...] = (
    "dmoney_0",
    "dmoney_1",
    "dmoney_2+",
    "money_0",
    "money_1",
    "money_2+",
    "zero_amt_has_digits",
    "restitution",
    "restitution_no_dollar",
    "cs_literal",
    "hours_only",
    "has_dollar",
    "has_decimal",
    "has_comma",
    "fine_token",
    "fine_nonlabel",
)


def _lines(version: str, stats: dict[str, object]) -> list[str]:
    """Render the recon as text lines — counts + ``sentence_type`` vocab only."""
    type_freq: Counter[str] = stats["type_freq"]  # type: ignore[assignment]
    per_type: dict[str, Counter[str]] = stats["per_type"]  # type: ignore[assignment]
    totals: Counter[str] = Counter()
    for c in per_type.values():
        totals.update(c)

    out = [
        "Sentencing recon (Task 22.5 Part A)",
        f"taxonomy_version: {version}",
        f"total sentence components: {stats['total']}  "
        f"distinct sentence_type: {stats['distinct_types']}",
        "",
        "money buckets = distinct parseable amounts under the CANDIDATE currency "
        "regex ($-prefixed | .NN decimal | comma-grouped)",
        "",
    ]
    for stype, freq in sorted(type_freq.items(), key=lambda kv: (-kv[1], kv[0])):
        c = per_type[stype]
        out.append(f"=== {stype!r}  count={freq} ===")
        out.append(
            f"  $-money: 0={c['dmoney_0']}  1={c['dmoney_1']}  2+={c['dmoney_2+']}"
        )
        out.append(
            f"  candidate-money (DURATION-CONTAMINATED): 0={c['money_0']}  "
            f"1={c['money_1']}  2+={c['money_2+']}  "
            f"(0-but-has-digits={c['zero_amt_has_digits']})"
        )
        out.append(
            f"  signals: restitution={c['restitution']} "
            f"(no-$={c['restitution_no_dollar']})  "
            f"community_service={c['cs_literal']}  hours_only={c['hours_only']}"
        )
        out.append(
            f"  shapes: $={c['has_dollar']}  decimal={c['has_decimal']}  "
            f"comma={c['has_comma']}"
        )
        out.append(f"  fine: token={c['fine_token']}  non_label={c['fine_nonlabel']}")
    out.append("")
    out.append("=== TOTALS (all sentence_types) ===")
    for m in _METRICS:
        out.append(f"  {m:<20} {totals[m]}")
    out.append("")
    return out


def _fetch_sentence_rows(database_url: str) -> list[tuple[str, str]]:
    from pipeline.db import connect  # local import keeps psycopg off import path

    with connect(database_url) as conn, conn.cursor() as cur:
        # noqa: S608 - table/columns are module constants, never user/corpus input.
        cur.execute(
            f"SELECT {SENTENCE_TYPE_COLUMN}, {RAW_TEXT_COLUMN} "  # noqa: S608
            f"FROM {SENTENCE_TABLE}"
        )
        return list(cur.fetchall())


def _taxonomy_version() -> str:
    here = Path(__file__).resolve()
    for candidate in here.parents:
        probe = candidate.joinpath(*_TAXONOMY_RELPATH)
        if probe.is_file():
            return str(json.loads(probe.read_text())["taxonomyVersion"])
    return "unknown"


def run_recon(database_url: str, *, report_path: Path) -> int:
    if inside_git_worktree(report_path.parent):
        logger.error("refusing to write a report inside a git working tree")
        return 2
    rows = _fetch_sentence_rows(database_url)
    stats = recon_counts(rows)
    version = _taxonomy_version()
    text = "\n".join(_lines(version, stats))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text)
    print(text)
    print(f"report written: {report_path}")
    return 0


# --- coverage mode (Task 22.5 Part B; the AC-8 acceptance authority) ----------


def coverage_counts(
    mapper: SentencingMapper, rows: Sequence[tuple[str, str]]
) -> dict[str, object]:
    """Run the finalized mapper over ``(sentence_type, raw_text)`` rows.

    Pure (no DB, no I/O). Returns the base-category distribution, the additive
    (restitution / community-service) counts, the ambiguous-community-service
    count, and the money split (rule (b)); every value is a COUNT or a taxonomy
    code — never any ``raw_text`` content.
    """
    base_by_code: Counter[str] = Counter()
    additive: Counter[str] = Counter()
    ambiguous_cs = 0
    monetary = money_set = money_absent = money_unparseable = 0

    for sentence_type, raw_text in rows:
        result = mapper.map(sentence_type, raw_text or "")
        base_by_code[result.base.category_code] += 1
        for cat in result.categories[1:]:
            additive[cat.category_code] += 1
        if result.ambiguous_community_service:
            ambiguous_cs += 1
        if result.money is not None:
            monetary += 1
            if result.amount_cents is not None:
                money_set += 1  # branch 3: exactly one distinct amount
            elif result.money_unparseable:
                money_unparseable += 1  # branch 2 / 4: present-but-unresolvable
            else:
                money_absent += 1  # branch 1: no `$` at all -> no item

    return {
        "total": sum(base_by_code.values()),
        "base_by_code": base_by_code,
        "additive": additive,
        "ambiguous_cs": ambiguous_cs,
        "monetary": monetary,
        "money_set": money_set,
        "money_absent": money_absent,
        "money_unparseable": money_unparseable,
    }


def coverage_lines(version: str, stats: dict[str, object]) -> list[str]:
    """Render the coverage distribution — counts + taxonomy codes only."""
    base: Counter[str] = stats["base_by_code"]  # type: ignore[assignment]
    additive: Counter[str] = stats["additive"]  # type: ignore[assignment]
    unmapped = base.get(SENTENCING_UNKNOWN, 0)
    out = [
        "Sentencing coverage (Task 22.5 Part B — AC-8 corpus rerun)",
        f"taxonomy_version: {version}",
        f"total sentence components: {stats['total']}",
        "",
        "base categories (sentence_type exact-match):",
    ]
    for code in sorted(c for c in base if c != SENTENCING_UNKNOWN):
        out.append(f"  {code:<20} {base[code]}")
    out.append(f"  {'unmapped->unknown':<20} {unmapped}")
    out.append("")
    out.append("additive category mappings (never collapsed):")
    out.append(f"  {CATEGORY_RESTITUTION:<20} {additive.get(CATEGORY_RESTITUTION, 0)}")
    out.append(
        f"  {CATEGORY_COMMUNITY_SERVICE:<20} "
        f"{additive.get(CATEGORY_COMMUNITY_SERVICE, 0)}"
    )
    out.append(f"  {'ambiguous-CS->review':<20} {stats['ambiguous_cs']}")
    out.append("")
    out.append("money (monetary components only; $-required, rule b):")
    out.append(f"  monetary components:        {stats['monetary']}")
    out.append(f"  amount SET (exactly one):   {stats['money_set']}")
    out.append(f"  absent, no item (no $):     {stats['money_absent']}")
    out.append(f"  money_unparseable item:     {stats['money_unparseable']}")
    out.append("")
    out.append("review items emitted:")
    out.append(f"  unmapped_sentencing_component  {unmapped}")
    out.append(f"  ambiguous_sentencing_component {stats['ambiguous_cs']}")
    out.append(f"  money_unparseable              {stats['money_unparseable']}")
    out.append("")
    return out


def run_coverage(database_url: str, *, report_path: Path) -> int:
    if inside_git_worktree(report_path.parent):
        logger.error("refusing to write a report inside a git working tree")
        return 2
    taxonomy = load_sentencing_taxonomy()
    mapper = SentencingMapper(taxonomy)
    rows = _fetch_sentence_rows(database_url)
    stats = coverage_counts(mapper, rows)
    text = "\n".join(coverage_lines(taxonomy.taxonomy_version, stats))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text)
    print(text)
    print(f"report written: {report_path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Sentencing recon/coverage report.")
    parser.add_argument("--mode", choices=("recon", "coverage"), default="recon")
    parser.add_argument("--report-name", default=None)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args(argv)

    if running_in_ci():
        logger.error(
            "sentencing recon/coverage reads local court data and must never run in "
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

    default_name = f"22.5-sentencing-{args.mode}"
    report_path = args.report_dir / f"{args.report_name or default_name}.txt"
    if args.mode == "coverage":
        return run_coverage(database_url, report_path=report_path)
    return run_recon(database_url, report_path=report_path)


if __name__ == "__main__":
    sys.exit(main())
