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
from pipeline.aggregates.generate import (
    DATA_START_DATE_DEFAULT as AGG_DATA_START_DATE_DEFAULT,
)
from pipeline.aggregates.generate import (
    DEFAULT_RUN_LABEL as AGG_DEFAULT_RUN_LABEL,
)
from pipeline.aggregates.generate import (
    THIN_DATA_MIN_SAMPLE_SIZE_DEFAULT as AGG_THIN_MIN_SAMPLE_DEFAULT,
)
from pipeline.aggregates.generate import (
    run_generate_aggregates,
)
from pipeline.aggregates.publish import run_publish_aggregates
from pipeline.aggregates.validate import run_validate_aggregates
from pipeline.close_held_review_items import run_close_held_review_items
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
from pipeline.facts.outcome_facts import FILED_DATE_FLOOR_DEFAULT
from pipeline.load import run_load
from pipeline.logging_utils import configure_logging
from pipeline.manual_import import run_manual_import
from pipeline.prune_fact_runs import run_prune_fact_runs
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
    (
        "prune-fact-runs",
        "Delete fact build runs WHOLE (run row + facts via CASCADE) so parsed "
        "reloads/supersessions can proceed past the fail-loud fact FKs.",
    ),
    (
        "close-held-review-items",
        "Close (as superseded) the open held-for-court-sourced review items "
        "whose generation the Task 29.3 mapper carve-out stopped; key-scoped, "
        "idempotent, dry-run without --confirm.",
    ),
    (
        "generate-aggregates",
        "Generate charge-only outcome and sentencing aggregates from eligible facts "
        "under a run.",
    ),
    (
        "validate-aggregates",
        "Validate a generated (unpublished) aggregate run: integrity, baseline, "
        "and privacy checks gating publish.",
    ),
    (
        "publish-aggregates",
        "Publish a validated aggregate run: set published_at and invalidate the "
        "prior published run in one transaction.",
    ),
    ("collect", "Collect docket-sheet PDFs from the portal into an intake dir."),
    (
        "migrate-window-ledger",
        "One-time COL-3 migration: split the shared search-mode window ledger "
        "into court-scoped ledgers and archive the shared file.",
    ),
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
        "prune-fact-runs",
        "close-held-review-items",
        "generate-aggregates",
        "validate-aggregates",
        "publish-aggregates",
        "collect",
        "migrate-window-ledger",
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
        if name == "build-facts":
            subparser.add_argument(
                "--filed-date-floor",
                type=date.fromisoformat,
                default=FILED_DATE_FLOOR_DEFAULT,
                help=(
                    "Filed-date floor (ISO YYYY-MM-DD): a fact is publicly "
                    "eligible only if its parent docket's filed_date is on or "
                    "after it (null filed_date is fail-closed ineligible). "
                    "Facts are still built for floored dockets — only the "
                    "eligibility dimension changes. Default: 2025-01-01."
                ),
            )
        if name == "prune-fact-runs":
            subparser.add_argument(
                "run_ids",
                nargs="*",
                metavar="RUN_ID",
                help=(
                    "fact.fact_build_runs ids (UUIDs) to prune whole. Mutually "
                    "exclusive with --all-completed; exactly one selection form "
                    "is required. Already-absent ids are idempotent success "
                    "(counted not_found); a non-completed id refuses the whole "
                    "invocation."
                ),
            )
            subparser.add_argument(
                "--all-completed",
                action="store_true",
                help=(
                    "Select every completed fact build run instead of naming "
                    "ids (the full prune-before-refresh form)."
                ),
            )
            subparser.add_argument(
                "--confirm",
                action="store_true",
                help=(
                    "Actually delete. Without it the command is a DRY RUN that "
                    "reports the selection and writes nothing."
                ),
            )
        if name == "close-held-review-items":
            subparser.add_argument(
                "--confirm",
                action="store_true",
                help=(
                    "Actually close (open -> superseded). Without it the command "
                    "is a DRY RUN that reports the selection counts and writes "
                    "nothing."
                ),
            )
        if name == "generate-aggregates":
            subparser.add_argument(
                "--build-run",
                default=None,
                dest="build_run_id",
                help=(
                    "Fact build-run id to aggregate from. Default: the latest "
                    "completed fact build run. Facts are run-scoped; the generator "
                    "never aggregates across runs."
                ),
            )
            subparser.add_argument(
                "--data-start-date",
                type=date.fromisoformat,
                default=AGG_DATA_START_DATE_DEFAULT,
                help=(
                    "MVP window floor (ISO YYYY-MM-DD); no aggregate date range "
                    "starts before it. Default: 2025-01-01."
                ),
            )
            subparser.add_argument(
                "--thin-min-sample",
                type=int,
                default=AGG_THIN_MIN_SAMPLE_DEFAULT,
                help=(
                    "Sample size below which a charge is flagged thin-data, applied "
                    "independently to the outcome and sentencing denominators (shown "
                    "with a warning, never hidden). Default: 10."
                ),
            )
            subparser.add_argument(
                "--label",
                default=AGG_DEFAULT_RUN_LABEL,
                help=(
                    "Human label for the aggregate run (report/log only; not "
                    f"persisted). Default: {AGG_DEFAULT_RUN_LABEL!r}."
                ),
            )
        if name == "validate-aggregates":
            subparser.add_argument(
                "--run",
                default=None,
                dest="aggregate_run_id",
                help=(
                    "Aggregate run id to validate; must be unpublished and "
                    "generated (in_progress) or validated (completed — "
                    "re-validation). Failed and published runs are refused. "
                    "Default: the latest generated (in_progress, unpublished) run."
                ),
            )
            subparser.add_argument(
                "--data-start-date",
                type=date.fromisoformat,
                default=AGG_DATA_START_DATE_DEFAULT,
                help=(
                    "MVP window floor (ISO YYYY-MM-DD); validation fails any "
                    "aggregate date range starting before it. Default: 2025-01-01."
                ),
            )
        if name == "publish-aggregates":
            subparser.add_argument(
                "--run",
                default=None,
                dest="aggregate_run_id",
                help=(
                    "Aggregate run id to publish; must be validated (completed) "
                    "and uninvalidated. An already-published, still-active run "
                    "is an idempotent no-op. Failed and invalidated runs are "
                    "refused. Default: the latest validated (completed, "
                    "unpublished) run — refused as stale if it was validated "
                    "before the active published run (pass --run to force an "
                    "older run)."
                ),
            )
        if name == "collect":
            subparser.add_argument(
                "--mode",
                choices=["enumerate", "search", "refresh"],
                default="enumerate",
                help=(
                    "Collection mode. 'enumerate' (default): the existing "
                    "docket-sequence probing (audit mode). 'search': one "
                    "Date-Filed advanced search per calendar day, harvesting "
                    "CP/MC criminal dockets from the results grid. Search mode "
                    "requires --start-date and --end-date. 'refresh': re-fetch "
                    "the loaded corpus's non-terminal dockets (COL-4b) so later "
                    "dispositions enter the corpus; requires --refresh-dir, an "
                    "EXPLICIT --court, and DATABASE_URL in the environment."
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
                    "in the window ledger). Refresh mode accepts MC, CP, or "
                    "both, filters the target list by docket-number prefix, and "
                    "REQUIRES the flag explicitly — no default is applied, so a "
                    "full refresh cannot silently shrink to one court. "
                    "Default (enumerate/search): MC."
                ),
            )
            subparser.add_argument(
                "--refresh-dir",
                type=Path,
                default=None,
                help=(
                    "Refresh mode only (required with --mode refresh): the "
                    "cycle-scoped directory where re-fetched docket sheets land "
                    "(<docket>.pdf); created if needed and must be outside any "
                    "git working tree. Keep ONE directory per refresh cycle, "
                    "stable across that cycle's sessions (a PDF already present "
                    "is skipped as already-fetched, making interrupted cycles "
                    "resumable); start every new cycle with a FRESH dated "
                    "directory (e.g. ~/court-data/refresh-intake-<UTC-date>/)."
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
                    "Search/refresh modes only (smoke tooling): cap on live PDF "
                    "fetches for the whole run; reaching it stops the run. "
                    "Omitted: no cap. Not used in production runs."
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
        if name == "migrate-window-ledger":
            # Deliberately flag-minimal: two directories, no pacing or
            # collection parameters — the counsel-locked values are not
            # reachable from here (COL-3 AC-8).
            subparser.add_argument(
                "--ledger-dir",
                type=Path,
                # Resolved here, at the CLI/run boundary — never at import.
                default=Path.home() / "court-data" / "coverage",
                help=(
                    "Directory holding the shared window ledger to migrate; "
                    "the court-scoped ledgers are written alongside it and the "
                    "shared file is archived in place (never deleted). Must be "
                    "outside any git working tree. Default: "
                    "~/court-data/coverage/."
                ),
            )
            subparser.add_argument(
                "--runs-dir",
                type=Path,
                default=Path.home() / "court-data" / "collection-runs",
                help=(
                    "Parent of per-run report dirs used to attribute each "
                    "shared-ledger entry to its court "
                    "(<runs-dir>/<run-id>/run-report.json). Default: "
                    "~/court-data/collection-runs/."
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


def _court_given_explicitly(argv: list[str]) -> bool:
    """True if ``--court`` appears in argv (either ``--court X`` or ``--court=X``).

    Refresh mode refuses to fall back to the flag's parse-level default: an
    accidental default-MC run would silently half-refresh the corpus and leave
    CP frozen — the exact bias COL-4b closes. argparse cannot distinguish an
    explicit ``--court MC`` from the default, so the raw argv is consulted.
    """
    return any(a == "--court" or a.startswith("--court=") for a in argv)


def _validate_collect_args(
    parser: argparse.ArgumentParser, args: argparse.Namespace, argv: list[str]
) -> None:
    """Mode-aware validation for ``collect`` (raises SystemExit(2) on error).

    ``--court`` is widened to {MC, CP, both} so search mode can select CP/both,
    but enumerate mode still supports only MC — enforced here at parse time so
    ``collect --court CP`` (enumerate) fails with the same argparse-style
    'invalid choice' error and exit code as before search mode existed. Search
    mode additionally requires the inclusive date range. Refresh mode requires
    --refresh-dir and an EXPLICIT --court (COL-4b; no default court).
    """
    if args.mode == "enumerate":
        if args.court != "MC":
            parser.error(
                f"argument --court: invalid choice: {args.court!r} for enumerate "
                "mode (only 'MC' is supported); use --mode search for CP/both"
            )
    elif args.mode == "search":
        if args.start_date is None or args.end_date is None:
            parser.error("--mode search requires --start-date and --end-date")
    else:  # refresh
        if args.refresh_dir is None:
            parser.error("--mode refresh requires --refresh-dir")
        if not _court_given_explicitly(argv):
            parser.error(
                "--mode refresh requires an explicit --court (MC, CP, or both); "
                "no default is applied in refresh mode"
            )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_usage(sys.stderr)
        return 2
    if args.command == "collect":
        # The effective argv mirrors what parse_args consumed (needed for the
        # refresh-mode explicit---court check).
        _validate_collect_args(parser, args, argv if argv is not None else sys.argv[1:])
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
        if args.mode == "refresh":
            # DATABASE_URL read at the run boundary (never at import, never
            # logged) — refresh derives its target list from the loaded
            # corpus. The other collect modes never read it.
            database_url = os.environ.get("DATABASE_URL", "")
            if not database_url.strip():
                logger.error(
                    "DATABASE_URL is required for refresh mode (target-list "
                    "derivation); set it in the environment (its value is "
                    "never printed or written)",
                    extra={"command": args.command},
                )
                return 2
            from pipeline.collector.run import run_collect_refresh

            return run_collect_refresh(
                database_url=database_url,
                court=args.court,
                refresh_dir=args.refresh_dir,
                max_minutes=args.max_minutes,
                report_dir=args.report_dir,
                headless=args.headless,
                batch_size=args.batch_size,
                batch_cooldown_seconds=args.batch_cooldown_seconds,
                max_fetches=args.max_fetches,
            )
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
    if args.command == "migrate-window-ledger":
        if running_in_ci():
            logger.error(
                "migrate-window-ledger operates on local court data and must "
                "never run in a CI environment; refusing",
                extra={"command": args.command},
            )
            return 2
        # Imported here (not at module top) so the CLI stays importable — and
        # the whole test suite runs — without the optional collector group.
        from pipeline.collector.run import run_migrate_window_ledger

        return run_migrate_window_ledger(
            ledger_dir=args.ledger_dir,
            runs_dir=args.runs_dir,
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
        return run_build_facts(database_url, filed_date_floor=args.filed_date_floor)
    if args.command == "prune-fact-runs":
        if running_in_ci():
            logger.error(
                "prune-fact-runs deletes fact build runs from the database and "
                "must never run in a CI environment; refusing (CI runs only the "
                "synthetic prune tests against its own Postgres service)",
                extra={"command": args.command},
            )
            return 2
        if bool(args.run_ids) == args.all_completed:
            logger.error(
                "exactly one selection form is required: explicit RUN_ID "
                "arguments or --all-completed (not both, not neither)",
                extra={"command": args.command},
            )
            return 2
        # DATABASE_URL read at the run boundary (never at import, never logged).
        database_url = os.environ.get("DATABASE_URL", "")
        if not database_url.strip():
            logger.error(
                "DATABASE_URL is required to prune fact runs; set it in the "
                "environment (its value is never printed or written)",
                extra={"command": args.command},
            )
            return 2
        with db.connect(database_url) as conn:
            return run_prune_fact_runs(
                conn,
                run_ids=args.run_ids,
                all_completed=args.all_completed,
                confirm=args.confirm,
            )
    if args.command == "close-held-review-items":
        if running_in_ci():
            logger.error(
                "close-held-review-items mutates review-queue triage state in the "
                "database and must never run in a CI environment; refusing (CI "
                "runs only the synthetic closure tests against its own Postgres "
                "service)",
                extra={"command": args.command},
            )
            return 2
        # DATABASE_URL read at the run boundary (never at import, never logged).
        # No salt: the closure reads structural anchors and statuses only.
        database_url = os.environ.get("DATABASE_URL", "")
        if not database_url.strip():
            logger.error(
                "DATABASE_URL is required to close held review items; set it in "
                "the environment (its value is never printed or written)",
                extra={"command": args.command},
            )
            return 2
        with db.connect(database_url) as conn:
            return run_close_held_review_items(conn, confirm=args.confirm)
    if args.command == "generate-aggregates":
        if running_in_ci():
            logger.error(
                "generate-aggregates reads local court facts and writes aggregates "
                "into the database; it must never run in a CI environment; refusing "
                "(CI runs only the synthetic aggregate tests against its own Postgres "
                "service)",
                extra={"command": args.command},
            )
            return 2
        # DATABASE_URL read at the run boundary (never at import, never logged).
        # No salt: analytics.* is aggregate-only and carries no defendant identity.
        database_url = os.environ.get("DATABASE_URL", "")
        if not database_url.strip():
            logger.error(
                "DATABASE_URL is required to generate aggregates; set it in the "
                "environment (its value is never printed or written)",
                extra={"command": args.command},
            )
            return 2
        return run_generate_aggregates(
            database_url,
            build_run_id=args.build_run_id,
            data_start_date=args.data_start_date,
            thin_min_sample=args.thin_min_sample,
            label=args.label,
        )
    if args.command == "validate-aggregates":
        if running_in_ci():
            logger.error(
                "validate-aggregates reads local aggregate data and writes run "
                "verdicts into the database; it must never run in a CI "
                "environment; refusing (CI runs only the synthetic validation "
                "tests against its own Postgres service)",
                extra={"command": args.command},
            )
            return 2
        # DATABASE_URL read at the run boundary (never at import, never logged).
        # No salt: analytics.* is aggregate-only and carries no defendant identity.
        database_url = os.environ.get("DATABASE_URL", "")
        if not database_url.strip():
            logger.error(
                "DATABASE_URL is required to validate aggregates; set it in the "
                "environment (its value is never printed or written)",
                extra={"command": args.command},
            )
            return 2
        return run_validate_aggregates(
            database_url,
            run_id=args.aggregate_run_id,
            data_start_date=args.data_start_date,
        )
    if args.command == "publish-aggregates":
        if running_in_ci():
            logger.error(
                "publish-aggregates swaps the active published aggregate run in "
                "the database; it must never run in a CI environment; refusing "
                "(CI runs only the synthetic publish tests against its own "
                "Postgres service)",
                extra={"command": args.command},
            )
            return 2
        # DATABASE_URL read at the run boundary (never at import, never logged).
        # No salt: analytics.* is aggregate-only and carries no defendant identity.
        database_url = os.environ.get("DATABASE_URL", "")
        if not database_url.strip():
            logger.error(
                "DATABASE_URL is required to publish aggregates; set it in the "
                "environment (its value is never printed or written)",
                extra={"command": args.command},
            )
            return 2
        return run_publish_aggregates(
            database_url,
            run_id=args.aggregate_run_id,
        )
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
