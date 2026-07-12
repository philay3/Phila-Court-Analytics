"""Command-line entrypoint for the pipeline.

``evaluate-extractors`` is implemented (Task 5.1); the other subcommands are
placeholders arriving in later tasks.
"""

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

from pipeline import db
from pipeline.collector.engine import (
    BATCH_COOLDOWN_DEFAULT_SECONDS,
    BATCH_SIZE_DEFAULT,
)
from pipeline.envelope import run_parse
from pipeline.equivalence_check import SALT_ENV_VAR, run_equivalence_check
from pipeline.evaluation.extractors import EXTRACTORS
from pipeline.evaluation.harness import run_evaluation
from pipeline.extraction import DEFAULT_LOW_TEXT_THRESHOLD, run_extraction
from pipeline.facts.build_facts import run_build_facts
from pipeline.load import run_load
from pipeline.logging_utils import configure_logging
from pipeline.manual_import import run_manual_import
from pipeline.run_fixtures import run_fixtures
from pipeline.seam_check import run_seam_check, running_in_ci

logger = logging.getLogger("pipeline.cli")

SUBCOMMANDS = (
    ("import-manual", "Import manually collected docket PDFs."),
    ("extract-text", "Extract text from imported docket PDFs."),
    ("seam-check", "Compare production extraction against Capstone reference text."),
    (
        "equivalence-check",
        "Diff ported extraction+parse output against the Capstone baseline.",
    ),
    ("parse", "Parse extraction artifacts into per-docket envelope artifacts."),
    ("load", "Load per-docket envelope artifacts into the raw/parsed DB tables."),
    (
        "build-facts",
        "Build fact.charge_outcomes from the loaded parsed corpus under a new run.",
    ),
    ("collect", "Collect docket-sheet PDFs from the portal into an intake dir."),
    ("evaluate-extractors", "Compare candidate PDF text extractors."),
    (
        "run-fixtures",
        "Regression-check the tier-1 fixture corpus (always) and, with "
        "--corpus-dir, drift-check real PDFs against local goldens (tier 2).",
    ),
)

IMPLEMENTED_COMMANDS = frozenset(
    {
        "evaluate-extractors",
        "extract-text",
        "import-manual",
        "seam-check",
        "equivalence-check",
        "parse",
        "load",
        "build-facts",
        "collect",
        "run-fixtures",
    }
)

PLACEHOLDER_COMMANDS = frozenset(
    name for name, _ in SUBCOMMANDS if name not in IMPLEMENTED_COMMANDS
)


def _parse_extractor_list(value: str) -> list[str]:
    names = list(dict.fromkeys(n.strip() for n in value.split(",") if n.strip()))
    unknown = [n for n in names if n not in EXTRACTORS]
    if unknown or not names:
        raise argparse.ArgumentTypeError(
            f"unknown extractor(s): {', '.join(unknown) or '(none given)'}; "
            f"valid: {', '.join(EXTRACTORS)}"
        )
    return names


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline",
        description="Philadelphia Court Outcomes Analytics data pipeline.",
    )
    subparsers = parser.add_subparsers(dest="command")
    for name, help_text in SUBCOMMANDS:
        subparser = subparsers.add_parser(name, help=help_text, description=help_text)
        if name == "import-manual":
            subparser.add_argument(
                "input_dir",
                type=Path,
                help="A directory of docket PDFs (scanned non-recursively).",
            )
            subparser.add_argument(
                "--metadata-root",
                type=Path,
                # Resolved here, at the CLI/run boundary — never at import.
                default=Path.home() / "court-data" / "imports",
                help=(
                    "Where hash-keyed import metadata records are written "
                    "(created if needed); must be outside any git working "
                    "tree. Default: ~/court-data/imports/."
                ),
            )
        if name == "extract-text":
            subparser.add_argument(
                "path",
                type=Path,
                help=("A PDF file, or a directory of PDFs (searched non-recursively)."),
            )
            subparser.add_argument(
                "--output-dir",
                type=Path,
                # Resolved here, at the CLI/run boundary — never at import.
                default=Path.home() / "court-data" / "extracted",
                help=(
                    "Where extraction artifacts are written (created if "
                    "needed); must be outside any git working tree. "
                    "Default: ~/court-data/extracted/."
                ),
            )
            subparser.add_argument(
                "--threshold",
                type=int,
                default=DEFAULT_LOW_TEXT_THRESHOLD,
                help=(
                    "Per-page character threshold (compared against stripped "
                    f"text) below which a page is flagged. Default: "
                    f"{DEFAULT_LOW_TEXT_THRESHOLD}."
                ),
            )
        if name == "seam-check":
            subparser.add_argument(
                "--corpus-dir",
                type=Path,
                # Resolved here, at the CLI/run boundary — never at import.
                default=Path.home() / "court-data" / "fixtures",
                help=(
                    "Directory of fixture PDFs to check (searched "
                    "non-recursively). Default: ~/court-data/fixtures/."
                ),
            )
            subparser.add_argument(
                "--reference-dir",
                type=Path,
                default=Path.home() / "court-data" / "capstone-reference-text",
                help=(
                    "Directory of Capstone reference JSON files, one "
                    "{stem}.json per PDF. Default: "
                    "~/court-data/capstone-reference-text/."
                ),
            )
            subparser.add_argument(
                "--report-dir",
                type=Path,
                default=Path.home() / "court-data" / "seam-report",
                help=(
                    "Where the seam-check report artifacts are written "
                    "(created if needed); must be outside any git working "
                    "tree. Default: ~/court-data/seam-report/."
                ),
            )
        if name == "equivalence-check":
            subparser.add_argument(
                "--corpus-dir",
                type=Path,
                # Resolved here, at the CLI/run boundary — never at import.
                default=Path.home() / "court-data" / "fixtures",
                help=(
                    "Directory of fixture PDFs to compare (searched "
                    "non-recursively). Default: ~/court-data/fixtures/."
                ),
            )
            subparser.add_argument(
                "--baseline-dir",
                type=Path,
                default=Path.home() / "court-data" / "capstone-baseline",
                help=(
                    "Directory of Capstone baseline interim JSON, indexed by "
                    "each record's docket_number. Default: "
                    "~/court-data/capstone-baseline/."
                ),
            )
            subparser.add_argument(
                "--output-dir",
                type=Path,
                default=Path.home() / "court-data" / "equivalence",
                help=(
                    "Where the equivalence report artifacts are written "
                    "(created if needed); must be outside any git working "
                    "tree. Default: ~/court-data/equivalence/."
                ),
            )
            subparser.add_argument(
                "--exclude-field",
                action="append",
                default=[],
                dest="exclude_fields",
                metavar="FIELD_PATH",
                help=(
                    "Additional field path to exclude from the diff (e.g. "
                    "'case.otn'); repeatable. parsed_at and parser_version are "
                    "always excluded."
                ),
            )
            subparser.add_argument(
                "--salt-parity-confirmed",
                action="store_true",
                help=(
                    "Compare case.defendant_hash. Pass ONLY when the baseline "
                    "was regenerated with the SAME salt as this run "
                    "(human-verified). Omitted (default): the hash field is "
                    "excluded and every artifact says so."
                ),
            )
        if name == "parse":
            subparser.add_argument(
                "--artifacts-dir",
                type=Path,
                # Resolved here, at the CLI/run boundary — never at import.
                default=Path.home() / "court-data" / "extracted",
                help=(
                    "Directory of 16.2 extraction artifacts (*.json, searched "
                    "non-recursively). Default: ~/court-data/extracted/."
                ),
            )
            subparser.add_argument(
                "--output-dir",
                type=Path,
                default=Path.home() / "court-data" / "envelopes",
                help=(
                    "Where per-docket envelope artifacts are written (created if "
                    "needed); must be outside any git working tree. Default: "
                    "~/court-data/envelopes/."
                ),
            )
        if name == "load":
            subparser.add_argument(
                "--envelopes-dir",
                type=Path,
                required=True,
                help=(
                    "Directory of per-docket envelope artifacts (*.json, searched "
                    "non-recursively) to load into the DB."
                ),
            )
            subparser.add_argument(
                "--import-metadata-dir",
                type=Path,
                # Resolved here, at the CLI/run boundary — never at import.
                default=Path.home() / "court-data" / "imports",
                help=(
                    "Directory of 16.3 hash-keyed import metadata records "
                    "(<sha256>.json). An envelope whose source hash has no record "
                    "here is a per-docket failure (no rows written). Default: "
                    "~/court-data/imports/."
                ),
            )
        if name == "collect":
            subparser.add_argument(
                "--mode",
                choices=["enumerate", "search"],
                default="enumerate",
                help=(
                    "Collection mode. 'enumerate' (default): the existing "
                    "docket-sequence probing (audit mode). 'search': one "
                    "Date-Filed advanced search per calendar day, harvesting "
                    "CP/MC criminal dockets from the results grid. Search mode "
                    "requires --start-date and --end-date."
                ),
            )
            subparser.add_argument(
                "--court",
                choices=["MC", "CP", "both"],
                default="MC",
                help=(
                    "Court to collect. Enumerate mode supports only MC "
                    "(MC-51-CR). Search mode accepts MC, CP, or both and gates "
                    "which harvested rows are FETCHED (both are always recorded "
                    "in the window ledger). Default: MC."
                ),
            )
            subparser.add_argument(
                "--start-date",
                type=date.fromisoformat,
                default=None,
                help=(
                    "Search mode only: first calendar day to search (ISO "
                    "YYYY-MM-DD, inclusive). Required with --mode search."
                ),
            )
            subparser.add_argument(
                "--end-date",
                type=date.fromisoformat,
                default=None,
                help=(
                    "Search mode only: last calendar day to search (ISO "
                    "YYYY-MM-DD, inclusive). Required with --mode search."
                ),
            )
            subparser.add_argument(
                "--max-fetches",
                type=int,
                default=None,
                help=(
                    "Search mode only (smoke tooling): cap on live PDF fetches "
                    "for the whole run; reaching it stops the run. Omitted: no "
                    "cap. Not used in production runs."
                ),
            )
            subparser.add_argument(
                "--recheck-windows",
                action="store_true",
                help=(
                    "Search mode only: ignore the window ledger and re-search "
                    "every window in range (mirrors --recheck-misses). Truncated "
                    "and blocked windows are always retried regardless."
                ),
            )
            subparser.add_argument(
                "--year", type=int, default=2025, help="Filing year. Default: 2025."
            )
            subparser.add_argument(
                "--start-seq",
                type=int,
                default=1,
                help="First docket sequence to enumerate (1-based). Default: 1.",
            )
            subparser.add_argument(
                "--count",
                type=int,
                default=600,
                help=(
                    "How many consecutive sequences to enumerate. The time cap "
                    "usually ends the run first. Default: 600."
                ),
            )
            subparser.add_argument(
                "--max-minutes",
                type=int,
                default=60,
                help=(
                    "Wall-clock stop in minutes. Hard-capped at the "
                    "counsel-locked 240-minute ceiling regardless of value. "
                    "Default: 60."
                ),
            )
            subparser.add_argument(
                "--intake-dir",
                type=Path,
                # Resolved here, at the CLI/run boundary — never at import.
                default=Path.home() / "court-data" / "intake",
                help=(
                    "Where collected PDFs land (<docket>.pdf); created if "
                    "needed and must be outside any git working tree. Default: "
                    "~/court-data/intake/."
                ),
            )
            subparser.add_argument(
                "--report-dir",
                type=Path,
                default=Path.home() / "court-data" / "collection-runs",
                help=(
                    "Parent for per-run report dirs (<report-dir>/<run-id>/ "
                    "with attempts.jsonl + run-report.json); created if needed "
                    "and must be outside any git working tree. Default: "
                    "~/court-data/collection-runs/."
                ),
            )
            subparser.add_argument(
                "--headless",
                action="store_true",
                help=(
                    "Run the browser headless. Default is headful (off): the "
                    "proven configuration and the honest posture."
                ),
            )
            subparser.add_argument(
                "--batch-size",
                type=int,
                default=BATCH_SIZE_DEFAULT,
                help=(
                    "Dockets per batch before the inter-batch cooldown. "
                    "Operational parameter. Default: 100."
                ),
            )
            subparser.add_argument(
                "--batch-cooldown-seconds",
                type=int,
                default=BATCH_COOLDOWN_DEFAULT_SECONDS,
                help=(
                    "Cooldown between batches, in seconds. Operational "
                    "parameter with an enforced 60s floor (may be raised, never "
                    "lowered below it). Default: 120. The counsel-locked "
                    "240-minute ceiling and 300s post-block cooldown are NOT "
                    "flags and cannot be changed."
                ),
            )
            subparser.add_argument(
                "--ledger-dir",
                type=Path,
                # Resolved here, at the CLI/run boundary — never at import.
                default=Path.home() / "court-data" / "coverage",
                help=(
                    "Where the persistent miss ledger lives "
                    "(miss-ledger-<court>-<year>.jsonl); created if needed and "
                    "must be outside any git working tree. Default: "
                    "~/court-data/coverage/."
                ),
            )
            subparser.add_argument(
                "--recheck-misses",
                action="store_true",
                help=(
                    "Ignore the miss ledger for this run and re-attempt every "
                    "docket number (confirmed misses are re-appended). Use to "
                    "revalidate a year still in progress, where a prior miss "
                    "may since have become a hit."
                ),
            )
        if name == "evaluate-extractors":
            subparser.add_argument(
                "--fixtures-dir",
                type=Path,
                required=True,
                help="Flat directory of fixture PDFs (searched non-recursively).",
            )
            subparser.add_argument(
                "--output-dir",
                type=Path,
                required=True,
                help=(
                    "Where report artifacts are written; must be outside any "
                    "git working tree."
                ),
            )
            subparser.add_argument(
                "--extractors",
                type=_parse_extractor_list,
                default=list(EXTRACTORS),
                help=(
                    f"Comma-separated subset of: {', '.join(EXTRACTORS)}. Default: all."
                ),
            )
            subparser.add_argument(
                "--dump-text",
                action="store_true",
                help=(
                    "Also write per-file extracted text to <output-dir>/text/ for "
                    "side-by-side human review (required for the Task 5.3 evaluation)."
                ),
            )
        if name == "run-fixtures":
            subparser.add_argument(
                "--corpus-dir",
                type=Path,
                default=None,
                help=(
                    "Local directory of real docket PDFs (searched "
                    "non-recursively). When given, tier 2 additionally runs: it "
                    "requires DEFENDANT_HASH_SALT and never runs in CI. Omitted: "
                    "tier 1 only."
                ),
            )
            subparser.add_argument(
                "--update-goldens",
                action="store_true",
                help=(
                    "Refresh EXISTING goldens that diverge, instead of reporting "
                    "drift. Tier 1: gates every tier-1 golden write (its goldens "
                    "are committed to git). Tier 2: refreshes only goldens that "
                    "already exist and diverge — it NEVER creates an absent "
                    "golden (use --init-goldens to establish first-time tier-2 "
                    "goldens). Passing --init-goldens AND --update-goldens "
                    "together is an explicit full-write mode: absent goldens are "
                    "created and divergent existing goldens are refreshed in the "
                    "same run. EVERY golden-writing invocation REQUIRES a "
                    "tasks/worklog.md note recording the write — the CLI cannot "
                    "enforce that, so it is on you."
                ),
            )
            subparser.add_argument(
                "--init-goldens",
                action="store_true",
                help=(
                    "Tier-2 only: establish goldens for dockets that have NONE "
                    "yet (writes ONLY absent goldens). Existing goldens are never "
                    "touched — a divergent existing golden is still reported, not "
                    "overwritten. Without this flag a tier-2 run NEVER writes an "
                    "absent golden: the docket is reported golden_missing and the "
                    "run exits nonzero. Combined with --update-goldens it becomes "
                    "full-write mode (absent created, divergent refreshed). Like "
                    "--update-goldens, EVERY golden-writing invocation REQUIRES a "
                    "tasks/worklog.md note recording the write."
                ),
            )
            subparser.add_argument(
                "--output-dir",
                type=Path,
                # Resolved here, at the CLI/run boundary — never at import.
                default=Path.home() / "court-data" / "goldens",
                help=(
                    "Tier-2 only: where hash-named goldens ({source_sha256}.json) "
                    "are written and, under reports/, a run-unique tier-2 report "
                    "(tier2-report-<UTC timestamp>.json) per run — a prior run's "
                    "report is never overwritten. Created if needed; must be "
                    "outside any git working tree. Default: ~/court-data/goldens/."
                ),
            )
    return parser


def _validate_collect_args(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    """Mode-aware validation for ``collect`` (raises SystemExit(2) on error).

    ``--court`` is widened to {MC, CP, both} so search mode can select CP/both,
    but enumerate mode still supports only MC — enforced here at parse time so
    ``collect --court CP`` (enumerate) fails with the same argparse-style
    'invalid choice' error and exit code as before search mode existed. Search
    mode additionally requires the inclusive date range.
    """
    if args.mode == "enumerate":
        if args.court != "MC":
            parser.error(
                f"argument --court: invalid choice: {args.court!r} for enumerate "
                "mode (only 'MC' is supported); use --mode search for CP/both"
            )
    else:  # search
        if args.start_date is None or args.end_date is None:
            parser.error("--mode search requires --start-date and --end-date")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_usage(sys.stderr)
        return 2
    if args.command == "collect":
        _validate_collect_args(parser, args)
    configure_logging()
    if args.command == "evaluate-extractors":
        return run_evaluation(
            fixtures_dir=args.fixtures_dir,
            output_dir=args.output_dir,
            extractor_names=args.extractors,
            dump_text=args.dump_text,
        )
    if args.command == "import-manual":
        return run_manual_import(args.input_dir, args.metadata_root)
    if args.command == "seam-check":
        if running_in_ci():
            logger.error(
                "seam-check runs over local court data and must never run in "
                "a CI environment; refusing",
                extra={"command": args.command},
            )
            return 2
        return run_seam_check(args.corpus_dir, args.reference_dir, args.report_dir)
    if args.command == "equivalence-check":
        if running_in_ci():
            logger.error(
                "equivalence-check runs over local court data and must never "
                "run in a CI environment; refusing",
                extra={"command": args.command},
            )
            return 2
        # Salt read at the run boundary (never at import); value never logged.
        salt = os.environ.get(SALT_ENV_VAR, "")
        if not salt.strip():
            logger.error(
                "DEFENDANT_HASH_SALT is required to run the parser; set it in "
                "the environment (its value is never printed or written)",
                extra={"command": args.command},
            )
            return 2
        return run_equivalence_check(
            args.corpus_dir,
            args.baseline_dir,
            args.output_dir,
            salt=salt,
            salt_parity_confirmed=args.salt_parity_confirmed,
            extra_exclusions=args.exclude_fields,
        )
    if args.command == "collect":
        if running_in_ci():
            logger.error(
                "collect performs live portal network access and must never "
                "run in a CI environment; refusing",
                extra={"command": args.command},
            )
            return 2
        # Imported here (not at module top) so the CLI stays importable — and
        # the whole test suite runs — without the optional collector group.
        if args.mode == "search":
            from pipeline.collector.run import run_collect_search

            return run_collect_search(
                court=args.court,
                start_date=args.start_date,
                end_date=args.end_date,
                max_minutes=args.max_minutes,
                intake_dir=args.intake_dir,
                report_dir=args.report_dir,
                ledger_dir=args.ledger_dir,
                headless=args.headless,
                batch_size=args.batch_size,
                batch_cooldown_seconds=args.batch_cooldown_seconds,
                max_fetches=args.max_fetches,
                recheck_windows=args.recheck_windows,
            )

        from pipeline.collector.run import run_collect

        return run_collect(
            court=args.court,
            year=args.year,
            start_seq=args.start_seq,
            count=args.count,
            max_minutes=args.max_minutes,
            intake_dir=args.intake_dir,
            report_dir=args.report_dir,
            ledger_dir=args.ledger_dir,
            headless=args.headless,
            batch_size=args.batch_size,
            batch_cooldown_seconds=args.batch_cooldown_seconds,
            recheck_misses=args.recheck_misses,
        )
    if args.command == "extract-text":
        return run_extraction(
            args.path,
            args.output_dir,
            low_text_threshold=args.threshold,
        )
    if args.command == "parse":
        if running_in_ci():
            logger.error(
                "parse runs over local court data and must never run in a CI "
                "environment; refusing",
                extra={"command": args.command},
            )
            return 2
        # Salt read at the run boundary (never at import); value never logged.
        salt = os.environ.get(SALT_ENV_VAR, "")
        if not salt.strip():
            logger.error(
                "DEFENDANT_HASH_SALT is required to run the parser; set it in "
                "the environment (its value is never printed or written)",
                extra={"command": args.command},
            )
            return 2
        return run_parse(args.artifacts_dir, args.output_dir, salt=salt)
    if args.command == "load":
        if running_in_ci():
            logger.error(
                "load writes local court data into the database and must never "
                "run in a CI environment; refusing (CI runs only the synthetic "
                "loader tests against its own Postgres service)",
                extra={"command": args.command},
            )
            return 2
        # DATABASE_URL read at the run boundary (never at import, never logged).
        database_url = os.environ.get("DATABASE_URL", "")
        if not database_url.strip():
            logger.error(
                "DATABASE_URL is required to run the loader; set it in the "
                "environment (its value is never printed or written)",
                extra={"command": args.command},
            )
            return 2
        with db.connect(database_url) as conn:
            return run_load(args.envelopes_dir, args.import_metadata_dir, conn)
    if args.command == "build-facts":
        if running_in_ci():
            logger.error(
                "build-facts reads local court data and writes facts into the "
                "database; it must never run in a CI environment; refusing (CI "
                "runs only the synthetic fact tests against its own Postgres "
                "service)",
                extra={"command": args.command},
            )
            return 2
        # DATABASE_URL read at the run boundary (never at import, never logged).
        # No salt: fact.charge_outcomes carries no defendant identity.
        database_url = os.environ.get("DATABASE_URL", "")
        if not database_url.strip():
            logger.error(
                "DATABASE_URL is required to build facts; set it in the "
                "environment (its value is never printed or written)",
                extra={"command": args.command},
            )
            return 2
        return run_build_facts(database_url)
    if args.command == "run-fixtures":
        # Tier 1 always runs (offline, repo-local, TIER1_TEST_SALT). Tier 2 runs
        # only with --corpus-dir and carries the local-court-data guards.
        tier2_salt: str | None = None
        if args.corpus_dir is not None:
            if running_in_ci():
                logger.error(
                    "run-fixtures --corpus-dir runs over local court data and "
                    "must never run in a CI environment; refusing",
                    extra={"command": args.command},
                )
                return 2
            # Salt read at the run boundary (never at import); value never logged.
            salt = os.environ.get(SALT_ENV_VAR, "")
            if not salt.strip():
                logger.error(
                    "DEFENDANT_HASH_SALT is required for tier 2 (--corpus-dir); "
                    "set it in the environment (its value is never printed or "
                    "written)",
                    extra={"command": args.command},
                )
                return 2
            tier2_salt = salt
        return run_fixtures(
            corpus_dir=args.corpus_dir,
            output_dir=args.output_dir,
            init_goldens=args.init_goldens,
            update_goldens=args.update_goldens,
            tier2_salt=tier2_salt,
        )
    logger.info("command not implemented", extra={"command": args.command})
    return 0
