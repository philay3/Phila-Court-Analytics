"""Baseline equivalence run — port-correctness gate (Task 17.3).

Runs the ported 16.2 extraction stage plus the 17.2 parser over the real
fixture corpus and diffs each parsed record field-by-field against the
regenerated Capstone baseline JSON. This is the acceptance test for the parser
port: it reports every divergence for human triage and fixes nothing. Any
divergence is a port defect or an environment difference — triage is a
planning-chat decision, not a "fix forward" here (hardening is Phase 18).

Per-docket pipeline (decision 1, plan-approved): ``extraction.extract`` for the
page text, then ``docket_parser.parse_docket_checked`` (the parser plus the
16.1 privacy assertions — its docstring names this comparator as the intended
caller). 17.1 proved the extraction seam byte-equivalent, so feeding
``extract``'s page text into the parser reproduces the baseline while keeping
``extraction_failed`` and ``parse_failed`` cleanly separable.

Status model (decisions 4/5): every corpus PDF ends in exactly one of
``equivalent`` / ``divergent`` / ``parse_failed`` / ``extraction_failed`` /
``baseline_missing``; every baseline record with no corpus PDF is reported
``corpus_missing`` so totals reconcile to the corpus in both directions. One
bad docket NEVER aborts the run: extraction returns a failed result rather than
raising, the parse is wrapped, and an outer guard catches anything else. A
raised privacy assertion (RuntimeError) is recorded as ``parse_failed`` with a
distinct ``privacy_assertion`` reason so a sentinel block is distinguishable
from an ordinary parse defect at triage time.

Salt parity (decision 3): the parser always needs a non-empty salt (supplied by
the CLI from the environment) or ``hash_defendant`` raises. Whether
``case.defendant_hash`` is *compared* is separate: only when the caller confirms
the baseline was regenerated with the SAME salt. Unconfirmed (the default), that
one field path is added to the exclusion set and every artifact says so. The
salt value itself is never printed or written anywhere.

Privacy rules (hard): the full report (which carries field values) is written
only under ``output_dir`` (default ``~/court-data/equivalence/``); a location
inside a git working tree is refused. Console/stdout carries counts, statuses,
and the salt-parity mode ONLY. Logs carry hash-prefix ids, court codes,
statuses, reasons, and divergence counts — never docket numbers, docket text,
or field values (CLAUDE.md hard rule + the 17.1 hash-prefix precedent; docket
numbers are defendant-identifying, so they stay in the out-of-repo report).
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from pipeline.docket_parser import parse_docket_checked
from pipeline.extraction import STATUS_FAILED as EXTRACTION_STATUS_FAILED
from pipeline.extraction import extract
from pipeline.helpers import ParseError
from pipeline.manual_import import DOCKET_NUMBER_RE
from pipeline.paths import inside_git_worktree

logger = logging.getLogger("pipeline.equivalence_check")

HASH_PREFIX_LEN = 16

# The environment variable the CLI reads the salt from (read at the run
# boundary, never at import; the value is never logged or written).
SALT_ENV_VAR = "DEFENDANT_HASH_SALT"

# Per-docket status vocabulary (decisions 4/5): exactly one per docket.
STATUS_EQUIVALENT = "equivalent"
STATUS_DIVERGENT = "divergent"
STATUS_PARSE_FAILED = "parse_failed"
STATUS_EXTRACTION_FAILED = "extraction_failed"
STATUS_BASELINE_MISSING = "baseline_missing"
STATUS_CORPUS_MISSING = "corpus_missing"

# Statuses a *corpus PDF* can end in — these sum to the corpus PDF count.
_CORPUS_STATUSES = (
    STATUS_EQUIVALENT,
    STATUS_DIVERGENT,
    STATUS_PARSE_FAILED,
    STATUS_EXTRACTION_FAILED,
    STATUS_BASELINE_MISSING,
)
# Stable display order for summaries; corpus_missing is a baseline-side status.
_SUMMARY_ORDER = (*_CORPUS_STATUSES, STATUS_CORPUS_MISSING)

# Structural reasons attached to a failure (never carry docket text).
REASON_EXTRACTION_FAILED = "extraction_failed"
REASON_PARSE_ERROR = "parse_error"
REASON_PRIVACY_ASSERTION = "privacy_assertion"
REASON_UNEXPECTED_EXCEPTION = "unexpected_exception"

# Divergence kinds recorded per field path.
KIND_VALUE = "value"
KIND_KEY_MISSING_IN_CORPUS = "key_missing_in_corpus"
KIND_KEY_MISSING_IN_BASELINE = "key_missing_in_baseline"
KIND_LIST_LENGTH = "list_length"

# Excluded field paths (decision 2): a single documented constant. parsed_at is
# a per-run timestamp and parser_version is a constant — neither is parse output.
EXCLUDED_FIELDS = frozenset({"parsed_at", "parser_version"})

# The defendant-hash field path, verified against the 17.2 record contract:
# docket_parser.parse_docket_text builds record["case"]["defendant_hash"], the
# only occurrence of the hash in the record. Excluded under parity-unconfirmed
# mode (decision 3).
DEFENDANT_HASH_PATH = "case.defendant_hash"

SALT_MODE_COMPARED = "hash_compared"
SALT_MODE_EXCLUDED = "hash_excluded_parity_unconfirmed"


class BaselineError(Exception):
    """Raised when the baseline directory cannot be loaded into records.

    Carries structural context only (shape, error type) — never a filename
    (baseline filenames may be docket numbers) and never file content.
    """


@dataclass
class BaselineLoad:
    """Result of loading the baseline directory."""

    index: dict[str, dict]
    records_loaded: int
    skipped: int
    duplicate_dockets: list[str]


@dataclass
class DocketResult:
    """Outcome for one docket. ``divergences`` carries field values and lands
    ONLY in the out-of-repo JSON report."""

    docket_number: str
    court: str
    status: str
    source_hash: str | None = None
    reason: str | None = None
    exception_type: str | None = None
    divergences: list[dict[str, object]] = field(default_factory=list)
    # 18.4 value gate: the parsed event_date/event_name for each HELD charge on
    # this docket (a charge carrying event keys — see ``_held_events``). Held
    # in-process only to compute the aggregate value-population gate; never
    # written per-docket to any artifact.
    held_events: list[dict[str, object]] = field(default_factory=list)
    # 18.5 UN-DISPOSAL check: sequences disposed in the baseline but left
    # undisposed by the corpus parse (the 18.4 ARD-routing regression signature).
    # Counts only; the sequence numbers are structural, never docket text.
    undisposals: list[int] = field(default_factory=list)


def _court_of(docket_number: str) -> str:
    """CP / MC from the canonical UJS docket-number pattern; else 'unknown'."""
    match = DOCKET_NUMBER_RE.match(docket_number)
    return match.group(1) if match else "unknown"


def _is_iso_date(value: object) -> bool:
    """True iff ``value`` is a string parseable as an ISO (YYYY-MM-DD) date."""
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _held_events(record: dict) -> list[dict[str, object]]:
    """The (event_date, event_name) pair for each HELD charge in a parsed record.

    Selection predicate (18.4, mirrors the parser's placement sweep exactly): a
    held charge is one that ENDS the parse undisposed — the placement sweep strips
    event keys from any charge later disposed, so a charge still carrying
    ``event_date``/``event_name`` is precisely a placement-sweep survivor. Keying
    off key PRESENCE (not truthiness) keeps this gate auditing the same charge set
    the ledger's Class A counts, so the value gate cannot silently diverge from the
    key-presence accounting it backstops.
    """
    return [
        {"event_date": charge.get("event_date"), "event_name": charge.get("event_name")}
        for charge in record.get("charges", [])
        if "event_date" in charge or "event_name" in charge
    ]


def _charge_is_disposed(charge: dict) -> bool:
    """A charge is disposed if it carries any disposition field — the same
    predicate the parser's placement sweep uses."""
    return (
        charge.get("disposition_raw") is not None
        or charge.get("disposition_date") is not None
        or charge.get("disposition_judge_raw") is not None
    )


def _undisposed_regressions(baseline: dict, corpus: dict) -> list[int]:
    """Sequences disposed in the baseline but undisposed in the corpus parse.

    The 18.4 ARD-routing regression signature (Task 18.5): a charge Capstone's
    baseline recorded as disposed that the corpus parse leaves with null
    disposition_raw/date/judge. Only sequences present in BOTH records are
    considered (a missing sequence is a separate charge-count divergence). This
    is a distinct, always-fail category — never folded into generic field
    divergence counts.
    """
    corpus_by_seq = {c.get("sequence"): c for c in corpus.get("charges", [])}
    out: list[int] = []
    for baseline_charge in baseline.get("charges", []):
        seq = baseline_charge.get("sequence")
        corpus_charge = corpus_by_seq.get(seq)
        if (
            _charge_is_disposed(baseline_charge)
            and corpus_charge is not None
            and not _charge_is_disposed(corpus_charge)
        ):
            out.append(seq)
    return out


def _hash_prefix(source_hash: str | None) -> str:
    return (source_hash or "unknown")[:HASH_PREFIX_LEN]


def load_baseline(baseline_dir: Path) -> BaselineLoad:
    """Load every ``*.json`` under ``baseline_dir`` into a docket-keyed index.

    Layout-robust (decision, plan fix 2): a file whose root is a single record
    object is indexed directly; a file whose root is a list has each element
    indexed. In both cases the key is each record's ``docket_number`` field,
    never the filename. A file root that is neither an object nor a list, or a
    file that is not readable JSON, raises ``BaselineError`` (loud, before the
    corpus pass). Records without a ``docket_number`` are counted as skipped.
    """
    index: dict[str, dict] = {}
    records_loaded = 0
    skipped = 0
    duplicates: set[str] = set()
    for json_path in sorted(baseline_dir.glob("*.json")):
        try:
            raw = json.loads(json_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise BaselineError(
                f"baseline file is not readable JSON: {type(exc).__name__}"
            ) from exc
        if isinstance(raw, list):
            records = raw
        elif isinstance(raw, dict):
            records = [raw]
        else:
            raise BaselineError(
                "baseline file root is neither a record object nor a list of records"
            )
        for record in records:
            if not isinstance(record, dict) or "docket_number" not in record:
                skipped += 1
                continue
            docket_number = str(record["docket_number"])
            records_loaded += 1
            if docket_number in index:
                duplicates.add(docket_number)
            index[docket_number] = record
    return BaselineLoad(
        index=index,
        records_loaded=records_loaded,
        skipped=skipped,
        duplicate_dockets=sorted(duplicates),
    )


def diff_records(
    baseline: object, corpus: object, *, exclusions: frozenset[str] | set[str]
) -> list[dict[str, object]]:
    """Deep field-by-field diff producing dotted/bracketed field paths.

    Paths look like ``case.filed_date`` and ``charges[0].sentences[1].min_days``.
    A path in ``exclusions`` is skipped and not recursed into. List-length
    mismatches record the surplus/missing elements *with their values* so the
    JSON report (out-of-repo) is triage-recoverable; scalar and key differences
    record both sides. Charges are ``sequence``-sorted by the parser, so
    positional list comparison is valid.
    """
    out: list[dict[str, object]] = []
    _diff("", baseline, corpus, exclusions, out)
    return out


def _diff(
    path: str,
    baseline: object,
    corpus: object,
    exclusions: frozenset[str] | set[str],
    out: list[dict[str, object]],
) -> None:
    if path and path in exclusions:
        return
    if isinstance(baseline, dict) and isinstance(corpus, dict):
        for key in sorted(set(baseline) | set(corpus)):
            child = f"{path}.{key}" if path else key
            if child in exclusions:
                continue
            in_baseline = key in baseline
            in_corpus = key in corpus
            if in_baseline and in_corpus:
                _diff(child, baseline[key], corpus[key], exclusions, out)
            elif in_baseline:
                out.append(
                    {
                        "path": child,
                        "kind": KIND_KEY_MISSING_IN_CORPUS,
                        "baseline": baseline[key],
                    }
                )
            else:
                out.append(
                    {
                        "path": child,
                        "kind": KIND_KEY_MISSING_IN_BASELINE,
                        "corpus": corpus[key],
                    }
                )
        return
    if isinstance(baseline, list) and isinstance(corpus, list):
        if len(baseline) != len(corpus):
            entry: dict[str, object] = {
                "path": path,
                "kind": KIND_LIST_LENGTH,
                "baseline_len": len(baseline),
                "corpus_len": len(corpus),
            }
            if len(corpus) > len(baseline):
                entry["surplus_in_corpus"] = corpus[len(baseline) :]
            else:
                entry["missing_from_corpus"] = baseline[len(corpus) :]
            out.append(entry)
        for index in range(min(len(baseline), len(corpus))):
            _diff(f"{path}[{index}]", baseline[index], corpus[index], exclusions, out)
        return
    if baseline != corpus:
        out.append(
            {"path": path, "kind": KIND_VALUE, "baseline": baseline, "corpus": corpus}
        )


def compare_one(
    pdf_path: Path,
    baseline_index: dict[str, dict],
    *,
    salt: str,
    exclusions: frozenset[str] | set[str],
) -> DocketResult:
    """Compare one corpus PDF against its baseline record.

    Order: baseline presence (no baseline -> ``baseline_missing``, nothing to
    compare); extraction (16.2); parse + privacy assertions (17.2); field diff.
    This never raises for the common failure modes; the run loop adds an outer
    guard for anything unexpected so a single docket cannot abort the corpus.
    """
    docket_number = pdf_path.stem
    court = _court_of(docket_number)
    try:
        source_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    except OSError:
        source_hash = None

    baseline = baseline_index.get(docket_number)
    if baseline is None:
        return DocketResult(
            docket_number, court, STATUS_BASELINE_MISSING, source_hash=source_hash
        )

    result = extract(pdf_path)
    if result.status == EXTRACTION_STATUS_FAILED:
        return DocketResult(
            docket_number,
            court,
            STATUS_EXTRACTION_FAILED,
            source_hash=source_hash,
            reason=REASON_EXTRACTION_FAILED,
        )

    try:
        record, _sentinels, _warnings = parse_docket_checked(
            docket_number, result.page_texts, salt=salt
        )
    except ParseError as exc:
        return DocketResult(
            docket_number,
            court,
            STATUS_PARSE_FAILED,
            source_hash=source_hash,
            reason=REASON_PARSE_ERROR,
            exception_type=type(exc).__name__,
        )
    except RuntimeError as exc:
        # A privacy assertion fired: a sentinel block. Distinct reason so triage
        # can tell it apart from an ordinary parse defect.
        return DocketResult(
            docket_number,
            court,
            STATUS_PARSE_FAILED,
            source_hash=source_hash,
            reason=REASON_PRIVACY_ASSERTION,
            exception_type=type(exc).__name__,
        )
    except Exception as exc:  # noqa: BLE001 - one bad docket must not abort the run
        return DocketResult(
            docket_number,
            court,
            STATUS_PARSE_FAILED,
            source_hash=source_hash,
            reason=REASON_UNEXPECTED_EXCEPTION,
            exception_type=type(exc).__name__,
        )

    divergences = diff_records(baseline, record, exclusions=exclusions)
    status = STATUS_DIVERGENT if divergences else STATUS_EQUIVALENT
    return DocketResult(
        docket_number,
        court,
        status,
        source_hash=source_hash,
        divergences=divergences,
        held_events=_held_events(record),
        undisposals=_undisposed_regressions(baseline, record),
    )


def _docket_entry(result: DocketResult) -> dict[str, object]:
    """Full per-docket report entry (out-of-repo only — carries docket number
    and, for divergences, field values)."""
    entry: dict[str, object] = {
        "docket_number": result.docket_number,
        "hash_prefix": _hash_prefix(result.source_hash),
        "court": result.court,
        "status": result.status,
    }
    if result.reason is not None:
        entry["reason"] = result.reason
    if result.exception_type is not None:
        entry["exception_type"] = result.exception_type
    if result.divergences:
        entry["divergences"] = result.divergences
    return entry


def _divergent_paths(result: DocketResult) -> list[str]:
    """Field paths only (no values) — safe for the human-readable summary."""
    return [str(divergence["path"]) for divergence in result.divergences]


def _render_summary(report: dict[str, object]) -> str:
    """Human-readable summary: paths and counts only, never field values."""
    header = report["header"]
    totals = report["totals"]
    by_court = report["by_court"]
    lines: list[str] = ["Baseline Equivalence Run (Task 17.3)", ""]
    lines.append(f"generated_at: {header['generated_at']}")
    lines.append(f"corpus_dir: {header['corpus_dir']}")
    lines.append(f"baseline_dir: {header['baseline_dir']}")
    lines.append(
        f"baseline_records_loaded: {header['baseline_records_loaded']} "
        f"(unique dockets: {header['baseline_unique_dockets']}, "
        f"skipped: {header['baseline_records_skipped']}, "
        f"duplicate dockets: {header['baseline_duplicate_docket_count']})"
    )
    lines.append(f"corpus_pdf_count: {header['corpus_pdf_count']}")
    lines.append(
        f"salt_parity: {header['salt_parity_mode']} "
        f"(confirmed={header['salt_parity_confirmed']})"
    )
    lines.append(f"excluded_fields: {', '.join(header['excluded_fields'])}")
    lines.append(f"reconciled: {header['reconciled']}")
    lines.append("")
    lines.append(f"VERDICT: {report['verdict']}")
    lines.append("")
    gate = report["held_value_gate"]
    lines.append(f"HELD-CHARGE VALUE GATE (18.4): {'PASS' if gate['pass'] else 'FAIL'}")
    lines.append(
        f"  held charges: {gate['held_charges_total']} "
        f"(populated: {gate['held_charges_populated']}, "
        f"violations: {gate['held_charges_violations']})"
    )
    lines.append(
        f"  distinct event_name vocabulary size: {gate['event_name_vocab_size']} "
        "(informational; event-name strings never written)"
    )
    lines.append("")
    undisposal = report["un_disposal"]
    lines.append(
        f"UN-DISPOSAL CHECK (18.5): {'PASS' if undisposal['pass'] else 'FAIL'}"
    )
    lines.append(
        f"  charges disposed in baseline but undisposed in corpus: "
        f"{undisposal['charges']} (across {undisposal['dockets']} dockets)"
    )
    lines.append("")
    lines.append("Totals:")
    for status in _SUMMARY_ORDER:
        lines.append(f"  {status}: {totals[status]}")
    lines.append("")
    lines.append("By court (CP / MC reported separately):")
    for court in sorted(by_court):
        counts = by_court[court]
        rendered = " ".join(f"{status}={counts[status]}" for status in _SUMMARY_ORDER)
        lines.append(f"  {court}: {rendered}")
    lines.append("")
    lines.append("Top divergent field paths (path: docket count):")
    top_paths = report["top_divergent_paths"]
    if top_paths:
        for path, count in top_paths:
            lines.append(f"  {path}: {count}")
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append("Dockets needing triage (paths only; values in the JSON report):")
    for docket in report["dockets"]:
        reason = f" reason={docket['reason']}" if docket.get("reason") else ""
        exc = f" exc={docket['exception_type']}" if docket.get("exception_type") else ""
        lines.append(
            f"  [{docket['hash_prefix']}] {docket['docket_number']} "
            f"({docket['court']}) {docket['status']}{reason}{exc}"
        )
        for divergence in docket.get("divergences", []):
            lines.append(f"      {divergence['path']} ({divergence['kind']})")
    return "\n".join(lines) + "\n"


def run_equivalence_check(
    corpus_dir: Path,
    baseline_dir: Path,
    output_dir: Path,
    *,
    salt: str,
    salt_parity_confirmed: bool,
    extra_exclusions: list[str],
) -> int:
    """Run the corpus comparator end-to-end and write the report artifacts.

    Returns a process exit code: 0 on a completed, reconciled run (divergences
    are recorded for triage, not fatal); 1 if reconciliation fails (the report
    is written for debugging but is not a valid gate artifact); 2 on invalid
    arguments or an unloadable/empty baseline.
    """
    if not corpus_dir.is_dir():
        logger.error(
            "corpus dir does not exist or is not a directory",
            extra={"corpus_dir": str(corpus_dir)},
        )
        return 2
    if not baseline_dir.is_dir():
        logger.error(
            "baseline dir does not exist or is not a directory",
            extra={"baseline_dir": str(baseline_dir)},
        )
        return 2
    if inside_git_worktree(output_dir):
        logger.error(
            "output dir resolves to a path inside a git working tree; "
            "choose a location outside any repository",
            extra={"output_dir": str(output_dir)},
        )
        return 2

    exclusions: set[str] = set(EXCLUDED_FIELDS) | set(extra_exclusions)
    if salt_parity_confirmed:
        salt_mode = SALT_MODE_COMPARED
    else:
        exclusions.add(DEFENDANT_HASH_PATH)
        salt_mode = SALT_MODE_EXCLUDED

    try:
        baseline = load_baseline(baseline_dir)
    except BaselineError as exc:
        logger.error("baseline load failed", extra={"error": str(exc)})
        return 2
    if baseline.records_loaded == 0:
        logger.error(
            "baseline dir contains no records (no *.json record with a "
            "docket_number field); refusing to run",
            extra={"baseline_dir": str(baseline_dir)},
        )
        return 2
    if baseline.duplicate_dockets:
        logger.warning(
            "baseline has duplicate docket numbers; the last record loaded wins",
            extra={"duplicate_docket_count": len(baseline.duplicate_dockets)},
        )

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
    logger.info(
        "starting equivalence check",
        extra={
            "file_count": len(pdf_paths),
            "baseline_records": baseline.records_loaded,
            "salt_mode": salt_mode,
        },
    )

    results: list[DocketResult] = []
    for pdf_path in pdf_paths:
        try:
            result = compare_one(
                pdf_path, baseline.index, salt=salt, exclusions=exclusions
            )
        except Exception as exc:  # noqa: BLE001 - one bad docket must not abort the run
            docket_number = pdf_path.stem
            result = DocketResult(
                docket_number,
                _court_of(docket_number),
                STATUS_PARSE_FAILED,
                reason=REASON_UNEXPECTED_EXCEPTION,
                exception_type=type(exc).__name__,
            )
        results.append(result)
        logger.info(
            "compared",
            extra={
                "file": _hash_prefix(result.source_hash),
                "court": result.court,
                "status": result.status,
                "reason": result.reason or "",
                "divergences": len(result.divergences),
            },
        )

    # Baseline records with no corresponding corpus PDF (decision 5). A corpus
    # docket "matched" the baseline iff its status is not baseline_missing.
    matched_dockets = {
        result.docket_number
        for result in results
        if result.status != STATUS_BASELINE_MISSING
    }
    corpus_missing_dockets = sorted(set(baseline.index) - matched_dockets)
    corpus_missing_results = [
        DocketResult(docket_number, _court_of(docket_number), STATUS_CORPUS_MISSING)
        for docket_number in corpus_missing_dockets
    ]

    all_results = results + corpus_missing_results
    counts = {status: 0 for status in _SUMMARY_ORDER}
    by_court: dict[str, dict[str, int]] = {}
    for result in all_results:
        counts[result.status] += 1
        bucket = by_court.setdefault(
            result.court, {status: 0 for status in _SUMMARY_ORDER}
        )
        bucket[result.status] += 1

    # Reconciliation is asserted, not merely reported (plan fix 7). (a) every
    # corpus PDF ended in exactly one corpus status; (b) every baseline record
    # is accounted for as matched-or-corpus_missing.
    corpus_status_sum = sum(counts[status] for status in _CORPUS_STATUSES)
    baseline_universe = len(baseline.index)
    reconciled = (corpus_status_sum == len(pdf_paths)) and (
        len(matched_dockets) + counts[STATUS_CORPUS_MISSING] == baseline_universe
    )
    if not reconciled:
        logger.error(
            "reconciliation failed: totals do not add up; the report is NOT a "
            "valid gate artifact",
            extra={
                "corpus_status_sum": corpus_status_sum,
                "corpus_pdf_count": len(pdf_paths),
                "matched_dockets": len(matched_dockets),
                "corpus_missing": counts[STATUS_CORPUS_MISSING],
                "baseline_universe": baseline_universe,
            },
        )

    path_counter: Counter[str] = Counter()
    for result in all_results:
        for path in _divergent_paths(result):
            path_counter[path] += 1
    top_divergent_paths = sorted(path_counter.items(), key=lambda kv: (-kv[1], kv[0]))

    # 18.4 value-verification gate. Every HELD charge (placement-sweep survivor —
    # see _held_events) must carry a non-null, date-parseable event_date and a
    # non-null event_name. This closes the 18.3 verification gap: key-presence
    # diffs are value-blind, so a corpus with 100% of held charges bearing event
    # keys can still have null/mis-sourced values. This is FAIL-LOUD and separate
    # from baseline equivalence — a violation is never folded into ledger Class A.
    # The distinct event_name vocabulary SIZE (a count) is reported as an
    # informational signal; the event_name strings themselves are never written.
    held_total = 0
    held_populated = 0
    held_violations = 0
    event_name_vocab: set[str] = set()
    for result in all_results:
        for event in result.held_events:
            held_total += 1
            date_ok = _is_iso_date(event.get("event_date"))
            name = event.get("event_name")
            name_ok = isinstance(name, str) and name.strip() != ""
            if date_ok and name_ok:
                held_populated += 1
            else:
                held_violations += 1
            if name_ok:
                event_name_vocab.add(name.strip().lower())
    held_value_gate_pass = held_violations == 0
    if not held_value_gate_pass:
        logger.error(
            "held-charge value gate FAILED: held charges with null/unparseable "
            "event_date or null event_name (structural counts only)",
            extra={
                "held_total": held_total,
                "held_violations": held_violations,
            },
        )

    # 18.5 UN-DISPOSAL check: charges disposed in the baseline but undisposed in
    # the corpus parse. A distinct, always-fail category — never folded into the
    # generic divergence counts. Zero is required for a green run.
    undisposal_charges = sum(len(result.undisposals) for result in all_results)
    undisposal_dockets = sum(1 for result in all_results if result.undisposals)
    undisposal_pass = undisposal_charges == 0
    if not undisposal_pass:
        logger.error(
            "UN-DISPOSAL check FAILED: charges disposed in baseline but undisposed "
            "in the corpus parse (structural counts only)",
            extra={
                "undisposal_charges": undisposal_charges,
                "undisposal_dockets": undisposal_dockets,
            },
        )

    gate_pass = reconciled and all(
        counts[status] == 0
        for status in (
            STATUS_DIVERGENT,
            STATUS_PARSE_FAILED,
            STATUS_EXTRACTION_FAILED,
            STATUS_BASELINE_MISSING,
            STATUS_CORPUS_MISSING,
        )
    )
    if gate_pass:
        verdict = (
            f"PASS — 100% field equivalence across {counts[STATUS_EQUIVALENT]} "
            "dockets (excluded fields noted above)."
        )
    elif not reconciled:
        verdict = "INVALID — reconciliation failed; totals do not add up (see log)."
    else:
        verdict = (
            "REVIEW REQUIRED — not 100% equivalent. Every divergence is listed "
            "individually below and in the JSON report for triage; none is "
            "auto-accepted."
        )

    report: dict[str, object] = {
        "header": {
            "generated_at": datetime.now(UTC).isoformat(),
            "corpus_dir": str(corpus_dir),
            "baseline_dir": str(baseline_dir),
            "baseline_records_loaded": baseline.records_loaded,
            "baseline_unique_dockets": baseline_universe,
            "baseline_records_skipped": baseline.skipped,
            "baseline_duplicate_docket_count": len(baseline.duplicate_dockets),
            "corpus_pdf_count": len(pdf_paths),
            "salt_parity_confirmed": salt_parity_confirmed,
            "salt_parity_mode": salt_mode,
            "excluded_fields": sorted(exclusions),
            "reconciled": reconciled,
        },
        "verdict": verdict,
        "held_value_gate": {
            "pass": held_value_gate_pass,
            "held_charges_total": held_total,
            "held_charges_populated": held_populated,
            "held_charges_violations": held_violations,
            "event_name_vocab_size": len(event_name_vocab),
        },
        "un_disposal": {
            "pass": undisposal_pass,
            "charges": undisposal_charges,
            "dockets": undisposal_dockets,
        },
        "totals": {status: counts[status] for status in _SUMMARY_ORDER},
        "by_court": by_court,
        "top_divergent_paths": top_divergent_paths,
        "dockets": [
            _docket_entry(result)
            for result in all_results
            if result.status != STATUS_EQUIVALENT
        ],
    }

    (output_dir / "equivalence-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    (output_dir / "equivalence-report.txt").write_text(_render_summary(report))

    # Console: counts, statuses, salt-parity mode, reconciliation ONLY. No
    # docket numbers, no field values.
    summary = " ".join(f"{status}={counts[status]}" for status in _SUMMARY_ORDER)
    print(summary)
    print(f"salt_parity: {salt_mode}")
    print(f"reconciled: {reconciled}")
    print(
        f"held_value_gate: {'PASS' if held_value_gate_pass else 'FAIL'} "
        f"(held={held_total} populated={held_populated} "
        f"violations={held_violations} event_name_vocab={len(event_name_vocab)})"
    )
    print(
        f"un_disposal: {'PASS' if undisposal_pass else 'FAIL'} "
        f"(charges={undisposal_charges} dockets={undisposal_dockets})"
    )
    logger.info(
        "equivalence check complete",
        extra={
            "file_count": len(pdf_paths),
            "reconciled": reconciled,
            "held_value_gate_pass": held_value_gate_pass,
            "undisposal_pass": undisposal_pass,
        },
    )
    return 0 if (reconciled and held_value_gate_pass and undisposal_pass) else 1
