"""Command-line entrypoint for the pipeline.

``evaluate-extractors`` is implemented (Task 5.1); the other subcommands are
placeholders arriving in later tasks.
"""

import argparse
import logging
import sys
from pathlib import Path

from pipeline.evaluation.extractors import EXTRACTORS
from pipeline.evaluation.harness import run_evaluation
from pipeline.logging_utils import configure_logging

logger = logging.getLogger("pipeline.cli")

SUBCOMMANDS = (
    ("import-manual", "Import manually collected docket PDFs."),
    ("extract-text", "Extract text from imported docket PDFs."),
    ("evaluate-extractors", "Compare candidate PDF text extractors."),
    ("run-fixtures", "Run the pipeline against local fixture PDFs."),
)

PLACEHOLDER_COMMANDS = frozenset(
    name for name, _ in SUBCOMMANDS if name != "evaluate-extractors"
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
    logger.info("command not implemented", extra={"command": args.command})
    return 0
