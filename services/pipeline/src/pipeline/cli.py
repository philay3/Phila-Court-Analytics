"""Command-line entrypoint for the pipeline.

``evaluate-extractors`` is implemented (Task 5.1); the other subcommands are
placeholders arriving in later tasks.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from pipeline.envelope import run_parse
from pipeline.equivalence_check import SALT_ENV_VAR, run_equivalence_check
from pipeline.evaluation.extractors import EXTRACTORS
from pipeline.evaluation.harness import run_evaluation
from pipeline.extraction import DEFAULT_LOW_TEXT_THRESHOLD, run_extraction
from pipeline.logging_utils import configure_logging
from pipeline.manual_import import run_manual_import
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
    ("evaluate-extractors", "Compare candidate PDF text extractors."),
    ("run-fixtures", "Run the pipeline against local fixture PDFs."),
)

IMPLEMENTED_COMMANDS = frozenset(
    {
        "evaluate-extractors",
        "extract-text",
        "import-manual",
        "seam-check",
        "equivalence-check",
        "parse",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_usage(sys.stderr)
        return 2
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
    logger.info("command not implemented", extra={"command": args.command})
    return 0
