"""``run-fixtures`` — golden regression + regeneration tooling (Task 19.2).

Two tiers, one projection:

* **Tier 1** (always runs) compares the committed synthetic corpus under
  ``tests/tier1/`` against its committed goldens. Fully offline and repo-local;
  fixtures are synthetic, so tier-1 console diffs may show field values. Writes
  are ALWAYS gated behind ``--update-goldens`` (these goldens are committed to
  git — there is no unflagged write path, new fixture or not).
* **Tier 2** (only when ``--corpus-dir`` is passed) runs the real 16.2
  extract-text + 18.1 parse/envelope stages over local PDFs, projects each
  envelope the SAME way, and tracks drift against goldens kept OUTSIDE the repo
  (default ``~/court-data/goldens/``, named ``{source_sha256}.json`` to mirror
  the ``~/court-data/envelopes/`` convention — never a raw docket number).
  Tier-2 console output carries counts, statuses, hash-prefix ids, and field
  PATHS only — never field values or docket text; the value-bearing diff lands
  only in the out-of-repo report file.

The golden PROJECTION is shared by both tiers (pinned decision 3): every fixture
and every real PDF is turned into a full envelope via
``pipeline.envelope.parse_document`` and then reduced by ``project_envelope`` to
the deterministic subset ``{status, record, warnings, review_needed, error}``.
Generation and comparison therefore never drift onto two serialization paths.

This module deliberately owns the tier-1 corpus paths (resolved relative to the
repo source tree). ``run-fixtures`` is a repo-local dev command — like the
retired ``generate_goldens.py`` it replaces — never invoked from an installed
wheel; the tier-1 regression itself is exercised in CI by ``tests/tier1/
test_regression.py`` under the ordinary pytest job.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# Reused wholesale (no modification): the 17.3 deep field-diff-with-exclusions
# utility for tier-2, and the shared git-worktree write guard.
from pipeline.envelope import PARSE_STATUS_FAILED, parse_document
from pipeline.equivalence_check import diff_records
from pipeline.extraction import STATUS_FAILED as EXTRACTION_STATUS_FAILED
from pipeline.extraction import STATUS_SUCCESS, extract
from pipeline.paths import inside_git_worktree

logger = logging.getLogger("pipeline.run_fixtures")

# ---------------------------------------------------------------------------
# Tier-1 constants (moved verbatim from the retired tests/tier1/support.py)
# ---------------------------------------------------------------------------

# The FIXED public test salt. NEVER the real DEFENDANT_HASH_SALT: committed
# tier-1 hashes derive from fictional names + this public constant, so they leak
# nothing and regeneration is reproducible. Tier 1 uses this regardless of what
# is present in the environment.
TIER1_TEST_SALT = "tier1-fixture-salt"

# Placeholder dockets (all-zeros sequence). The parser is handed the docket
# number explicitly (it never reads it from page text), so generation supplies
# one per court. Both are placeholder-hygiene-clean by construction.
DOCKET_CP = "CP-51-CR-0000000-2025"
DOCKET_MC = "MC-51-CR-0000000-2025"

# Multi-page fixtures separate ordered page texts with this exact delimiter line.
PAGE_DELIM = "=== PAGE BREAK ==="

# Tier-1 corpus lives under services/pipeline/tests/tier1/. Resolve it relative
# to this module: parents[2] == services/pipeline (src/pipeline/run_fixtures.py).
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
TIER1_DIR = _PACKAGE_ROOT / "tests" / "tier1"
FIXTURES_DIR = TIER1_DIR / "fixtures"
GOLDENS_DIR = TIER1_DIR / "goldens"
INDEX_PATH = TIER1_DIR / "fixture-index.yaml"

# ---------------------------------------------------------------------------
# The shared projection (pinned decision 3)
# ---------------------------------------------------------------------------

# Top-level envelope keys dropped to obtain the deterministic golden projection:
#   source_sha256        the PDF's content hash — identifies the source file,
#                        not parse output (empty/placeholder for tier-1 text
#                        fixtures, which have no source PDF).
#   parser_version       the ENVELOPE wrapper's own format version (currently 4).
#                        DISTINCT from record["parser_version"] (currently 2, the
#                        record-schema axis), which is NOT dropped and stays
#                        visible in the golden as a regression signal.
#   extraction_artifact  provenance pointer (artifact id / text hash / path) to
#                        the upstream 16.2 artifact — provenance, not parse output.
#   created_at           per-run wall-clock timestamp — non-deterministic.
_DROPPED_ENVELOPE_KEYS = frozenset(
    {"source_sha256", "parser_version", "extraction_artifact", "created_at"}
)


def project_envelope(envelope: dict) -> dict:
    """Reduce a full ``parse_document`` envelope to its deterministic golden
    projection: ``{status, record, warnings, review_needed, error}``.

    Drops the source/provenance/format/timestamp fields (see
    ``_DROPPED_ENVELOPE_KEYS``) and pops the record's non-deterministic
    ``parsed_at``. The record's own ``parser_version`` is deliberately retained.
    """
    projection = {k: v for k, v in envelope.items() if k not in _DROPPED_ENVELOPE_KEYS}
    record = projection.get("record")
    if record is not None:
        record = dict(record)
        record.pop("parsed_at", None)
        projection["record"] = record
    return projection


def golden_bytes(golden: dict) -> str:
    """Serialize a golden deterministically (sorted keys, trailing newline)."""
    return json.dumps(golden, indent=2, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# Tier-1 helpers (moved from support.py; build_golden now routes through the
# real envelope so both tiers share one projection path)
# ---------------------------------------------------------------------------


def docket_for_court(court_type: str) -> str:
    """Placeholder docket number for a fixture's ``court_type``."""
    if court_type == "Municipal Court":
        return DOCKET_MC
    if court_type == "Common Pleas":
        return DOCKET_CP
    raise ValueError(f"unknown court_type: {court_type!r}")


def golden_filename(fixture_filename: str) -> str:
    """Golden JSON filename paired 1:1 with a fixture ``*.txt`` filename."""
    return f"{Path(fixture_filename).stem}.json"


def load_fixture_pages(fixture_filename: str) -> list[str]:
    """Read a fixture ``*.txt`` into its ordered list of page texts.

    Pages split on the ``PAGE_DELIM`` line; a single-page fixture yields a
    one-element list. The parser consumes this list exactly as it consumes real
    extracted page text.
    """
    text = (FIXTURES_DIR / fixture_filename).read_text()
    if PAGE_DELIM in text:
        parts = text.split(PAGE_DELIM + "\n")
        return [part.rstrip("\n") for part in parts]
    return [text.rstrip("\n")]


def build_golden(docket_number: str, pages: list[str]) -> dict:
    """Build the deterministic tier-1 golden projection for one fixture.

    Routes through the real ``parse_document`` (extraction_status fixed at
    ``STATUS_SUCCESS`` so ``LOW_TEXT_EXTRACTION`` never fires from a text
    fixture, and the fixed public ``TIER1_TEST_SALT``), then projects. A fixture
    that raises during parse yields ``parse_document``'s ``failed`` envelope,
    which projects to the ``failed`` golden arm.
    """
    envelope = parse_document(
        docket_number,
        pages,
        source_sha256="",
        text_hash=None,
        provenance_path=None,
        extraction_status=STATUS_SUCCESS,
        salt=TIER1_TEST_SALT,
    )
    return project_envelope(envelope)


def load_golden(fixture_filename: str) -> dict:
    """Load a committed tier-1 golden by its paired fixture filename."""
    path = GOLDENS_DIR / golden_filename(fixture_filename)
    return json.loads(path.read_text())


def diff_fields(want, got, path: str = "") -> list[str]:
    """Recursive, readable field-level diff (tier-1; values are synthetic/safe).

    Returns ``path: want=<...> got=<...>`` lines; empty when equal. Makes a
    tier-1 regression failure legible instead of dumping blobs.
    """
    diffs: list[str] = []
    if isinstance(want, dict) and isinstance(got, dict):
        for key in sorted(set(want) | set(got)):
            child = f"{path}.{key}" if path else key
            if key not in want:
                diffs.append(f"{child}: want=<absent> got={got[key]!r}")
            elif key not in got:
                diffs.append(f"{child}: want={want[key]!r} got=<absent>")
            else:
                diffs.extend(diff_fields(want[key], got[key], child))
    elif isinstance(want, list) and isinstance(got, list):
        if len(want) != len(got):
            diffs.append(f"{path}: want len={len(want)} got len={len(got)}")
        for i, (w, g) in enumerate(zip(want, got, strict=False)):
            diffs.extend(diff_fields(w, g, f"{path}[{i}]"))
    elif want != got:
        diffs.append(f"{path}: want={want!r} got={got!r}")
    return diffs


def _load_index() -> dict:
    """Load ``fixture-index.yaml`` (pyyaml is a dev dep; imported lazily so the
    CLI stays importable in a production install without the dev group)."""
    import yaml

    return yaml.safe_load(INDEX_PATH.read_text())


# ---------------------------------------------------------------------------
# Tier-1 status vocabulary + runner
# ---------------------------------------------------------------------------

T1_MATCH = "match"
T1_DIVERGED = "diverged"
T1_UPDATED = "updated"
T1_NEW = "new"
T1_MISSING = "missing"

_T1_ORDER = (T1_MATCH, T1_DIVERGED, T1_UPDATED, T1_NEW, T1_MISSING)


@dataclass
class Tier1Entry:
    filename: str
    status: str
    diffs: list[str] = field(default_factory=list)


@dataclass
class Tier1Result:
    entries: list[Tier1Entry]

    def counts(self) -> dict[str, int]:
        counts = {status: 0 for status in _T1_ORDER}
        for entry in self.entries:
            counts[entry.status] += 1
        return counts

    @property
    def failed_run(self) -> bool:
        # diverged (unflagged) and missing (unflagged) are failures; match /
        # updated / new (both flagged) are clean.
        return any(e.status in (T1_DIVERGED, T1_MISSING) for e in self.entries)


def run_tier1(update_goldens: bool) -> Tier1Result:
    """Compare every indexed tier-1 fixture against its committed golden.

    With ``update_goldens`` a divergent golden is overwritten (``updated``) and a
    missing one is created (``new``). WITHOUT the flag, divergence is reported
    (``diverged``) and a missing golden is refused (``missing``) — never written.
    """
    index = _load_index()
    entries: list[Tier1Entry] = []
    for item in index["fixtures"]:
        filename = item["filename"]
        docket = docket_for_court(item["court_type"])
        pages = load_fixture_pages(filename)
        got = build_golden(docket, pages)
        golden_path = GOLDENS_DIR / golden_filename(filename)

        if golden_path.exists():
            want = json.loads(golden_path.read_text())
            diffs = diff_fields(want, got)
            if not diffs:
                entries.append(Tier1Entry(filename, T1_MATCH))
            elif update_goldens:
                golden_path.write_text(golden_bytes(got))
                entries.append(Tier1Entry(filename, T1_UPDATED, diffs))
            else:
                entries.append(Tier1Entry(filename, T1_DIVERGED, diffs))
        elif update_goldens:
            golden_path.write_text(golden_bytes(got))
            entries.append(Tier1Entry(filename, T1_NEW))
        else:
            # Committed-to-git file: never an unflagged write. Refuse and fail.
            entries.append(Tier1Entry(filename, T1_MISSING))

    return Tier1Result(entries)


def _print_tier1(result: Tier1Result) -> None:
    counts = result.counts()
    summary = " ".join(f"{status}={counts[status]}" for status in _T1_ORDER)
    print(f"tier1: {summary}")
    for entry in result.entries:
        if entry.status in (T1_MATCH, T1_UPDATED, T1_NEW):
            continue
        if entry.status == T1_MISSING:
            print(
                f"  {entry.filename}: MISSING golden — rerun with "
                f"--update-goldens to create it (and record a worklog note)"
            )
            continue
        print(f"  {entry.filename}: {entry.status}")
        for line in entry.diffs:
            print(f"      {line}")


# ---------------------------------------------------------------------------
# Tier-2 status vocabulary + runner
# ---------------------------------------------------------------------------

T2_MATCH = "match"
T2_DIVERGED = "diverged"
T2_UPDATED = "updated"
T2_NEW = "new"
T2_FAILED = "failed"

_T2_ORDER = (T2_MATCH, T2_DIVERGED, T2_UPDATED, T2_NEW, T2_FAILED)

# Structural failure reasons (never carry docket text).
REASON_EXTRACTION_FAILED = "extraction_failed"
REASON_PARSE_FAILED = "parse_failed"
REASON_UNEXPECTED_EXCEPTION = "unexpected_exception"

_HASH_PREFIX_LEN = 16


@dataclass
class Tier2Entry:
    hash_prefix: str
    status: str
    reason: str | None = None
    exception_class: str | None = None
    # Full value-bearing divergences — out-of-repo report file ONLY.
    divergences: list[dict[str, object]] = field(default_factory=list)

    def paths(self) -> list[str]:
        """Field paths only (no values) — safe for console/summary."""
        return [str(d["path"]) for d in self.divergences]


def _source_hash(pdf_path: Path) -> str:
    return hashlib.sha256(pdf_path.read_bytes()).hexdigest()


def _compare_one_tier2(
    pdf_path: Path, output_dir: Path, *, salt: str, update_goldens: bool
) -> Tier2Entry:
    """Extract → parse_document → project one PDF, then compare/write its golden.

    Per-docket exception capture (mandatory): extraction failure, a ``failed``
    envelope, or any unexpected exception all yield a ``failed`` entry — one bad
    docket never aborts the run, and no golden is written for it. A refresh
    (``--update-goldens``) never absolves a ``failed`` docket.
    """
    source_sha256: str | None = None
    try:
        source_sha256 = _source_hash(pdf_path)
        result = extract(pdf_path)
        if result.status == EXTRACTION_STATUS_FAILED:
            return Tier2Entry(
                _hash_prefix(source_sha256),
                T2_FAILED,
                reason=REASON_EXTRACTION_FAILED,
            )
        envelope = parse_document(
            pdf_path.stem,
            result.page_texts,
            source_sha256=source_sha256,
            text_hash=result.text_hash,
            provenance_path=None,
            extraction_status=result.status,
            salt=salt,
        )
        if envelope["status"] == PARSE_STATUS_FAILED:
            error = envelope.get("error") or {}
            return Tier2Entry(
                _hash_prefix(source_sha256),
                T2_FAILED,
                reason=REASON_PARSE_FAILED,
                exception_class=str(error.get("exception_class"))
                if error.get("exception_class") is not None
                else None,
            )
        got = project_envelope(envelope)
    except Exception as exc:  # noqa: BLE001 - one bad docket must not abort the run
        return Tier2Entry(
            _hash_prefix(source_sha256),
            T2_FAILED,
            reason=REASON_UNEXPECTED_EXCEPTION,
            exception_class=type(exc).__name__,
        )

    golden_path = output_dir / f"{source_sha256}.json"
    if golden_path.exists():
        want = json.loads(golden_path.read_text())
        divergences = diff_records(want, got, exclusions=frozenset())
        if not divergences:
            return Tier2Entry(_hash_prefix(source_sha256), T2_MATCH)
        if update_goldens:
            golden_path.write_text(golden_bytes(got))
            return Tier2Entry(
                _hash_prefix(source_sha256), T2_UPDATED, divergences=divergences
            )
        return Tier2Entry(
            _hash_prefix(source_sha256), T2_DIVERGED, divergences=divergences
        )

    # New golden: first time we have seen this source. Created without the flag
    # (the flag guards OVERWRITES of existing goldens, not first creation).
    golden_path.write_text(golden_bytes(got))
    return Tier2Entry(_hash_prefix(source_sha256), T2_NEW)


def _hash_prefix(source_hash: str | None) -> str:
    return (source_hash or "unknown")[:_HASH_PREFIX_LEN]


def _tier2_report(entries: list[Tier2Entry], corpus_dir: Path) -> dict[str, object]:
    """Full report (carries field values in divergences) — out-of-repo file
    ONLY. ``baseline`` in each divergence is the stored golden; ``corpus`` is the
    fresh parse (diff_records naming, reused unchanged)."""
    counts = {status: 0 for status in _T2_ORDER}
    for entry in entries:
        counts[entry.status] += 1
    dockets: list[dict[str, object]] = []
    for entry in entries:
        if entry.status == T2_MATCH:
            continue
        item: dict[str, object] = {
            "hash_prefix": entry.hash_prefix,
            "status": entry.status,
        }
        if entry.reason is not None:
            item["reason"] = entry.reason
        if entry.exception_class is not None:
            item["exception_class"] = entry.exception_class
        if entry.divergences:
            item["divergences"] = entry.divergences
        dockets.append(item)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "corpus_dir": str(corpus_dir),
        "totals": counts,
        "dockets": dockets,
    }


def _print_tier2(entries: list[Tier2Entry]) -> None:
    """Console output: counts, statuses, hash-prefix ids, field PATHS only.
    Never field values or docket text."""
    counts = {status: 0 for status in _T2_ORDER}
    for entry in entries:
        counts[entry.status] += 1
    summary = " ".join(f"{status}={counts[status]}" for status in _T2_ORDER)
    print(f"tier2: {summary}")
    for entry in entries:
        if entry.status == T2_MATCH:
            continue
        reason = f" reason={entry.reason}" if entry.reason else ""
        exc = f" exc={entry.exception_class}" if entry.exception_class else ""
        print(f"  [{entry.hash_prefix}] {entry.status}{reason}{exc}")
        for path in entry.paths():
            print(f"      {path}")


def run_tier2(
    corpus_dir: Path, output_dir: Path, *, salt: str, update_goldens: bool
) -> int:
    """Run tier 2 over ``corpus_dir`` and write goldens + report under
    ``output_dir``. Returns 2 on a guard failure, 1 on any drift/failure, 0 on a
    clean run.
    """
    if not corpus_dir.is_dir():
        logger.error(
            "corpus dir does not exist or is not a directory",
            extra={"corpus_dir": str(corpus_dir)},
        )
        return 2
    if inside_git_worktree(output_dir):
        logger.error(
            "output dir resolves to a path inside a git working tree; "
            "choose a location outside any repository",
            extra={"output_dir": str(output_dir)},
        )
        return 2

    pdf_paths = sorted(
        p for p in corpus_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"
    )
    if not pdf_paths:
        logger.error(
            "corpus dir contains no PDF files (search is non-recursive)",
            extra={"corpus_dir": str(corpus_dir)},
        )
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("starting tier-2 run", extra={"file_count": len(pdf_paths)})

    entries: list[Tier2Entry] = []
    for pdf_path in pdf_paths:
        entry = _compare_one_tier2(
            pdf_path, output_dir, salt=salt, update_goldens=update_goldens
        )
        entries.append(entry)
        logger.info(
            "compared",
            extra={
                "file": entry.hash_prefix,
                "status": entry.status,
                "reason": entry.reason or "",
                "divergences": len(entry.divergences),
            },
        )

    report = _tier2_report(entries, corpus_dir)
    (output_dir / "run-fixtures-tier2-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    _print_tier2(entries)

    # Non-zero on any diverged (unflagged) or failed (always, even under the
    # flag — a refresh cannot absolve a per-docket failure).
    dirty = any(e.status in (T2_DIVERGED, T2_FAILED) for e in entries)
    logger.info("tier-2 run complete", extra={"file_count": len(pdf_paths)})
    return 1 if dirty else 0


# ---------------------------------------------------------------------------
# Entry point (called from cli.py; CI/salt guards live at the CLI boundary)
# ---------------------------------------------------------------------------


def run_fixtures(
    *,
    corpus_dir: Path | None,
    output_dir: Path,
    update_goldens: bool,
    tier2_salt: str | None,
) -> int:
    """Run tier 1 always, then tier 2 when ``corpus_dir`` is given.

    ``tier2_salt`` is the real ``DEFENDANT_HASH_SALT`` (already validated
    non-empty by the CLI) and is required whenever ``corpus_dir`` is set. Tier 1
    always uses ``TIER1_TEST_SALT`` and ignores the environment entirely.
    Returns a process exit code (2 = guard failure, 1 = drift/failure, 0 = clean).
    """
    tier1 = run_tier1(update_goldens)
    _print_tier1(tier1)
    exit_code = 1 if tier1.failed_run else 0

    if corpus_dir is not None:
        assert tier2_salt is not None  # CLI guarantees this pairing
        rc = run_tier2(
            corpus_dir, output_dir, salt=tier2_salt, update_goldens=update_goldens
        )
        if rc == 2:
            return 2
        if rc == 1:
            exit_code = 1

    return exit_code
