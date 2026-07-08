"""Command-line entrypoint for the pipeline.

All subcommands are placeholders; real implementations arrive in later tasks
(extraction evaluation starts in Task 5.1).
"""

import argparse
import logging
import sys

from pipeline.logging_utils import configure_logging

logger = logging.getLogger("pipeline.cli")

SUBCOMMANDS = (
    ("import-manual", "Import manually collected docket PDFs."),
    ("extract-text", "Extract text from imported docket PDFs."),
    ("evaluate-extractors", "Compare candidate PDF text extractors."),
    ("run-fixtures", "Run the pipeline against local fixture PDFs."),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline",
        description=(
            "Philadelphia Court Outcomes Analytics data pipeline (shell only; "
            "no command is implemented yet)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")
    for name, help_text in SUBCOMMANDS:
        subparsers.add_parser(name, help=help_text, description=help_text)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_usage(sys.stderr)
        return 2
    configure_logging()
    logger.info("command not implemented", extra={"command": args.command})
    return 0
