"""Per-document parser output envelope + observation layer (Task 18.1).

Wraps the unchanged 17.2 parsed record with the 18.1 observability surface:
warnings (structural-only), a derived ``review_needed`` boolean, a parse status,
the extraction-artifact reference, and per-docket failure capture. This layer
OBSERVES; it never changes what the parser extracts. The record embedded in the
envelope is the exact object ``parse_docket_text`` returns — nothing inside it is
added, removed, renamed, or reformatted (criterion 5).

Two version numbers, deliberately distinct (decision 4 + decision 7): the
ENVELOPE carries ``parser_version = 2`` (this Phase-18 parse-pipeline format),
while the wrapped record keeps its own internal ``parser_version = 1``, untouched.
The record is the v1 Capstone-equivalent record; the envelope is the v2 wrapper.

Emission scope is observation-only (decision 6): warnings are wired ONLY for
conditions the current parser/extraction output already exposes. Three defined
codes are NOT emitted here — MISSING_CHARGE_SECTION, SUSPECT_JUDGE_LINE, and
SUSPECTED_AMENDED_CHARGE — because their detectors are future hardening work
(18.2). Their absence from emission is asserted by the closure test.

Failure capture (decision 5): a docket that raises during parse — ParseError,
KeyError (the quarantined unsupported-disposition specimen), anything — yields a
``failed``-status envelope with ``error.code = UNSUPPORTED_FORMAT`` and structural
context (the exception class name, no free-text message, no raw docket text). The
run never crashes on one bad docket.

Privacy: warnings and the error object carry structural context only; envelope
artifacts are written OUTSIDE the repo (default ``~/court-data/envelopes/``); no
raw docket text reaches logs or console.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from pipeline.docket_parser import parse_docket_text
from pipeline.extraction import STATUS_NEEDS_OCR_OR_REVIEW, STATUS_PARTIAL
from pipeline.paths import inside_git_worktree
from pipeline.warning_codes import (
    LOW_TEXT_EXTRACTION,
    MISSING_CHARGE_SECTION,
    MISSING_DISPOSITION_DATE,
    MISSING_SENTENCE_DATE,
    NON_TERMINAL_CASE,
    SUSPECT_JUDGE_LINE,
    SUSPECTED_AMENDED_CHARGE,
    UNPARSEABLE_DURATION,
    UNSUPPORTED_FORMAT,
    WARNING_CODES,
    derive_review_needed,
    make_warning,
)

logger = logging.getLogger("pipeline.envelope")

# The envelope format / parse-pipeline version (decision 4). Distinct from the
# wrapped record's internal parser_version, which stays 1 (decision 7).
ENVELOPE_PARSER_VERSION = 2

# Parse status vocabulary (decision 4/5): exactly one per envelope.
PARSE_STATUS_PARSED = "parsed"
PARSE_STATUS_FAILED = "failed"

# Extraction statuses that map to LOW_TEXT_EXTRACTION (decision 6). Sourced from
# the 16.2 vocabulary, not redefined here.
_LOW_TEXT_STATUSES = frozenset({STATUS_PARTIAL, STATUS_NEEDS_OCR_OR_REVIEW})

# Sentence types whose absence of a numeric duration is expected, so they never
# raise UNPARSEABLE_DURATION (accepted at plan review).
_NO_DURATION_TYPES = frozenset({"no further penalty", "fines and costs"})

# Defined codes 18.1 deliberately does NOT emit (their detectors are 18.2 work).
UNEMITTED_CODES: frozenset[str] = frozenset(
    {MISSING_CHARGE_SECTION, SUSPECT_JUDGE_LINE, SUSPECTED_AMENDED_CHARGE}
)
# Codes 18.1 can produce (as a warning or, for UNSUPPORTED_FORMAT, as an error).
EMITTED_CODES: frozenset[str] = WARNING_CODES - UNEMITTED_CODES


def _charge_has_disposition(charge: dict) -> bool:
    """True if the parser recorded any terminal outcome on this charge.

    A charge gets a disposition_raw, disposition_date, or sentence ONLY inside an
    event the ported MC path accepts as terminal (Final Disposition / ARD). So
    this reflects the parser's own terminality gating, read straight from the
    record — no page text, no reparsing.
    """
    return (
        charge["disposition_raw"] is not None
        or charge["disposition_date"] is not None
        or bool(charge["sentences"])
    )


def _is_unparseable_duration(sentence: dict) -> bool:
    """True if a duration-bearing sentence yielded no parsed days.

    ``to_days`` returned None for both bounds on a sentence whose type is not one
    of the no-duration types, yet a raw sentence string is present (e.g. "Life").
    """
    if sentence["sentence_type"].lower() in _NO_DURATION_TYPES:
        return False
    return (
        sentence["min_days"] is None
        and sentence["max_days"] is None
        and bool(sentence["raw_text"])
    )


def observe(record: dict, *, extraction_status: str) -> list[dict[str, object]]:
    """Derive the observation-only warnings for a successfully parsed record.

    Reads only the extraction status and the parsed record — never page text.
    Emits, in a stable order: LOW_TEXT_EXTRACTION (from the 16.2 status),
    NON_TERMINAL_CASE (no terminal event present), then per-charge
    MISSING_DISPOSITION_DATE and, per sentence, MISSING_SENTENCE_DATE /
    UNPARSEABLE_DURATION.
    """
    warnings: list[dict[str, object]] = []

    if extraction_status in _LOW_TEXT_STATUSES:
        warnings.append(make_warning(LOW_TEXT_EXTRACTION))

    charges = record["charges"]
    # NON_TERMINAL_CASE: the case has charges but NO terminal event was accepted
    # (nothing the parser gated as Final Disposition / ARD). A docket with a
    # genuine final disposition has at least one disposed charge, so it never
    # flags — interim non-final events alone do not qualify.
    if charges and not any(_charge_has_disposition(charge) for charge in charges):
        warnings.append(make_warning(NON_TERMINAL_CASE))

    for charge in charges:
        seq = charge["sequence"]
        if charge["disposition_raw"] is not None and charge["disposition_date"] is None:
            warnings.append(make_warning(MISSING_DISPOSITION_DATE, charge_sequence=seq))
        for sentence in charge["sentences"]:
            if sentence["sentence_date"] is None:
                warnings.append(
                    make_warning(MISSING_SENTENCE_DATE, charge_sequence=seq)
                )
            if _is_unparseable_duration(sentence):
                warnings.append(make_warning(UNPARSEABLE_DURATION, charge_sequence=seq))

    return warnings


def _assemble(
    *,
    source_sha256: str,
    extraction_artifact: dict[str, object],
    record: dict | None,
    warnings: list[dict[str, object]],
    status: str,
    error: dict[str, object] | None,
) -> dict[str, object]:
    """Assemble the envelope dict with exactly the pinned fields.

    ``review_needed`` is derived from every code in play — the warning codes plus,
    on a failed envelope, the error code (both from the same vocabulary).
    """
    codes: list[str] = [str(warning["code"]) for warning in warnings]
    if error is not None:
        codes.append(str(error["code"]))
    return {
        "source_sha256": source_sha256,
        "parser_version": ENVELOPE_PARSER_VERSION,
        "extraction_artifact": extraction_artifact,
        "record": record,
        "warnings": warnings,
        "review_needed": derive_review_needed(codes),
        "status": status,
        "created_at": datetime.now(UTC).isoformat(),
        "error": error,
    }


def parse_document(
    docket_number: str,
    pages_text: list[str],
    *,
    source_sha256: str,
    text_hash: str | None,
    provenance_path: str | None,
    extraction_status: str,
    salt: str,
) -> dict[str, object]:
    """Parse one document's page text and wrap it in an envelope.

    On success, embeds the parser's exact record object (unchanged) and the
    observation-only warnings. On ANY parse-time exception, returns a
    ``failed``-status envelope with ``error.code = UNSUPPORTED_FORMAT`` and the
    exception class name (structural context only) — the run continues.
    """
    extraction_artifact: dict[str, object] = {
        "artifact_id": source_sha256,
        "text_hash": text_hash,
        "provenance_path": provenance_path,
    }
    try:
        record, _sentinels = parse_docket_text(docket_number, pages_text, salt=salt)
    except Exception as exc:  # noqa: BLE001 - any parse failure becomes a failed envelope (decision 5)
        warnings: list[dict[str, object]] = []
        if extraction_status in _LOW_TEXT_STATUSES:
            warnings.append(make_warning(LOW_TEXT_EXTRACTION))
        error = {
            "code": UNSUPPORTED_FORMAT,
            "exception_class": type(exc).__name__,
        }
        return _assemble(
            source_sha256=source_sha256,
            extraction_artifact=extraction_artifact,
            record=None,
            warnings=warnings,
            status=PARSE_STATUS_FAILED,
            error=error,
        )

    warnings = observe(record, extraction_status=extraction_status)
    return _assemble(
        source_sha256=source_sha256,
        extraction_artifact=extraction_artifact,
        record=record,
        warnings=warnings,
        status=PARSE_STATUS_PARSED,
        error=None,
    )


def _artifact_docket_number(artifact: dict) -> str:
    """Docket number from the extraction artifact's original filename stem.

    Matches the import-stage convention (17.3): the filename stem is the docket
    number; the parser never derives it itself.
    """
    original_filename = str(artifact.get("original_filename", ""))
    return Path(original_filename).stem


# Envelope statuses in a stable summary order.
_SUMMARY_ORDER = (PARSE_STATUS_PARSED, PARSE_STATUS_FAILED)


def run_parse(artifacts_dir: Path, output_dir: Path, *, salt: str) -> int:
    """Turn 16.2 extraction artifacts into per-docket envelope artifacts.

    Reads every ``*.json`` under ``artifacts_dir``, parses each artifact's page
    text, and writes one ``{source_sha256}.json`` envelope per document under
    ``output_dir`` (created at the run boundary, refused inside a git working
    tree). One unreadable/bad artifact never aborts the run. Console and logs
    carry ids, counts, and statuses only — never docket text. Returns an exit code.
    """
    if not artifacts_dir.is_dir():
        logger.error(
            "artifacts dir does not exist or is not a directory",
            extra={"artifacts_dir": str(artifacts_dir)},
        )
        return 2
    artifact_paths = sorted(artifacts_dir.glob("*.json"))
    if not artifact_paths:
        logger.error(
            "artifacts dir contains no *.json extraction artifacts",
            extra={"artifacts_dir": str(artifacts_dir)},
        )
        return 2
    if inside_git_worktree(output_dir):
        logger.error(
            "output dir resolves to a path inside a git working tree; "
            "choose a location outside any repository",
            extra={"output_dir": str(output_dir)},
        )
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "starting parse",
        extra={"file_count": len(artifact_paths), "output_dir": str(output_dir)},
    )

    counts = {status: 0 for status in _SUMMARY_ORDER}
    skipped = 0
    for artifact_path in artifact_paths:
        try:
            artifact = json.loads(artifact_path.read_text())
            source_sha256 = str(artifact["source_sha256"])
            envelope = parse_document(
                _artifact_docket_number(artifact),
                list(artifact.get("pages", [])),
                source_sha256=source_sha256,
                text_hash=artifact.get("text_hash"),
                provenance_path=str(artifact_path),
                extraction_status=str(artifact.get("status", "")),
                salt=salt,
            )
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            # A malformed/unreadable artifact is skipped, not fatal; the error
            # type is structural, and no artifact content is logged.
            skipped += 1
            logger.warning(
                "skipped unreadable extraction artifact",
                extra={"error_type": type(exc).__name__},
            )
            continue

        out_path = output_dir / f"{source_sha256}.json"
        out_path.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n")
        counts[str(envelope["status"])] += 1
        logger.info(
            "parsed",
            extra={
                "file": source_sha256[:16],
                "status": envelope["status"],
                "review_needed": envelope["review_needed"],
                "warning_count": len(envelope["warnings"]),  # type: ignore[arg-type]
            },
        )

    summary = " ".join(f"{status}={counts[status]}" for status in _SUMMARY_ORDER)
    print(f"{summary} skipped={skipped}")
    logger.info("parse complete", extra={"file_count": len(artifact_paths)})
    return 0


def collect_codes(envelopes: Iterable[dict]) -> set[str]:
    """All warning and error codes appearing across the given envelopes.

    Used by the closure test to assert emitted codes are a subset of the defined
    vocabulary and never include an unemitted code.
    """
    codes: set[str] = set()
    for envelope in envelopes:
        for warning in envelope.get("warnings", []):
            codes.add(str(warning["code"]))
        error = envelope.get("error")
        if error is not None:
            codes.add(str(error["code"]))
    return codes
