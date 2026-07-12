"""Envelope -> database loader (`pipeline load`, Task 21.3).

Reads the per-docket envelope artifacts produced by ``pipeline parse`` and writes
them into the frozen 21.1 ``raw.source_documents`` + ``parsed.*`` tables. The
schema is FROZEN for this task: every envelope/record key is either loaded, or
listed as an intentional non-load in the README loader-semantics note. Nothing is
fabricated to satisfy a NOT-NULL column (see the failure arms below).

Load unit (decision 2): one docket, one transaction. The raw upsert plus the full
parsed graph (docket -> charges -> sentences, plus warnings and related_cases)
commit or roll back together. Per-docket exception isolation: one bad envelope
never kills the run; it is counted and the run continues.

Idempotency (decision 3), identity = source file hash, version =
``(envelope_parser_version, record_parser_version)`` compared as a tuple:

  - already loaded at the SAME version -> skip after a content re-check
    (zero writes); a content DIFFERENCE at equal versions is a per-docket
    failure and stop-and-report (never an overwrite).
  - NEWER version -> transactional replace: delete the docket row (CASCADE
    clears the parsed children), re-upsert the raw row, reinsert the graph.
  - OLDER version -> refuse (per-docket warning); never downgrade.

Failed envelopes (Q1 ruling, supersedes the original decision 4): a ``failed``
parse produced no record, so NO ``parsed.*`` rows are written — fabricating
NOT-NULL record values (``defendant_hash`` especially) would be dishonest data.
The raw row is upserted with the parse-failure status and the envelope's error
code; Sprint 6 review visibility comes from ``raw.source_documents`` and
exclusion from fact generation is structural (no parsed rows exist).

Missing 16.3 import record (Q1 ruling / Required Fix 1): the loader NEVER
synthesizes a ``raw.source_documents`` row from envelope fields alone — a missing
import record means the provenance chain is broken for that document, so it is a
per-docket failure with NO rows written (recovery: re-run the idempotent 16.3
`import-manual` over the source PDF, then reload). There are no sentinel/"unknown"
column values anywhere in the loader.

Console/log hygiene (decision 6): counts, statuses, fixed structural reason codes,
and hash-PREFIX ids only. No docket numbers, no raw text, no ``DATABASE_URL``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from pipeline.envelope import PARSE_STATUS_FAILED

logger = logging.getLogger("pipeline.load")

# The envelope format versions this loader accepts (21.3 pinned set). Anything
# else -> per-docket failure, never a guess (AC2). Pinned literally to the
# canonical 21.3 corpus version rather than tracking ENVELOPE_PARSER_VERSION so a
# future format bump cannot silently widen what this task's loader accepts.
ACCEPTED_ENVELOPE_VERSIONS: frozenset[int] = frozenset({5})

# The raw.source_documents.status value the loader writes for a failed-parse
# envelope. The 16.3 import-stage vocabulary (imported/duplicate/invalid/failed,
# in manual_import.py) describes the IMPORT outcome; this value describes the
# PARSE outcome at load time and is owned here (documented in the README note).
STATUS_PARSE_FAILED = "parse_failed"

# The seven run-report categories (Required Fix 3). Every envelope lands in
# exactly one; the totals reconcile to the envelope count.
LOADED = "loaded"
SKIPPED_SAME_VERSION = "skipped_same_version"
REPLACED_NEWER_VERSION = "replaced_newer_version"
REFUSED_OLDER_VERSION = "refused_older_version"
FAILED_ENVELOPE_LOADED = "failed_envelope_loaded"
FAILED_EXCEPTION = "failed_exception"
MISSING_IMPORT_RECORD = "missing_import_record"

_CATEGORY_ORDER = (
    LOADED,
    SKIPPED_SAME_VERSION,
    REPLACED_NEWER_VERSION,
    REFUSED_OLDER_VERSION,
    FAILED_ENVELOPE_LOADED,
    FAILED_EXCEPTION,
    MISSING_IMPORT_RECORD,
)

# The two categories that mean "something is wrong" and drive a nonzero exit
# (fail-loud): a per-docket exception/rejection, or a broken provenance chain.
_UNHEALTHY_CATEGORIES = (FAILED_EXCEPTION, MISSING_IMPORT_RECORD)

# Fixed, hygiene-safe structural reason codes for per-docket rejections.
_REASON_UNRECOGNIZED_VERSION = "unrecognized_envelope_version"
_REASON_CONTENT_MISMATCH = "equal_version_content_mismatch"


class _LoaderReject(Exception):
    """A deliberate per-docket rejection (rolled back, counted failed_exception).

    Carries a fixed structural ``reason`` code only — never docket text.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _read_import_record(import_metadata_dir: Path, source_sha256: str) -> dict | None:
    """The 16.3 import metadata record for a source hash, or None if absent."""
    path = import_metadata_dir / f"{source_sha256}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _derive_court_type(docket_number: str) -> str | None:
    """court_type_derived from the docket-number prefix (decision 5).

    Closed CP-/MC- mapping; any other prefix -> None (the caller logs a warning).
    Pure: no logging here, so the equal-version content re-check can reuse it.
    """
    if docket_number.startswith("CP-"):
        return "CP"
    if docket_number.startswith("MC-"):
        return "MC"
    return None


def _upsert_source_document(
    conn: psycopg.Connection,
    *,
    source_sha256: str,
    import_record: dict,
    status: str,
    error_code: str | None,
) -> str:
    """Upsert the raw.source_documents row from the 16.3 record; return its id.

    Identity is ``file_hash`` (the source sha256). All non-status columns come
    straight from the import record; ``status``/``error_code`` are supplied by
    the caller (import values for a parsed envelope, parse-failure values for a
    failed one). The row is MUTABLE, so a reload updates it in place (the 6.1
    trigger maintains ``updated_at``).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw.source_documents
              (file_hash, original_filename, file_size_bytes, imported_at,
               import_mode, status, error_code, docket_number_provenance,
               court_type, county)
            VALUES
              (%(file_hash)s, %(original_filename)s, %(file_size_bytes)s,
               %(imported_at)s, %(import_mode)s, %(status)s, %(error_code)s,
               %(docket_number_provenance)s, %(court_type)s, %(county)s)
            ON CONFLICT (file_hash) DO UPDATE SET
               original_filename = EXCLUDED.original_filename,
               file_size_bytes = EXCLUDED.file_size_bytes,
               imported_at = EXCLUDED.imported_at,
               import_mode = EXCLUDED.import_mode,
               status = EXCLUDED.status,
               error_code = EXCLUDED.error_code,
               docket_number_provenance = EXCLUDED.docket_number_provenance,
               court_type = EXCLUDED.court_type,
               county = EXCLUDED.county
            RETURNING id
            """,
            {
                "file_hash": source_sha256,
                "original_filename": import_record["original_filename"],
                "file_size_bytes": import_record["file_size_bytes"],
                "imported_at": import_record["imported_at"],
                "import_mode": import_record["mode"],
                "status": status,
                "error_code": error_code,
                "docket_number_provenance": import_record["docket_number_provenance"],
                "court_type": import_record["court_type"],
                "county": import_record["county"],
            },
        )
        row = cur.fetchone()
        assert row is not None  # INSERT ... RETURNING always yields a row
        return row[0]


def _insert_parsed_graph(
    conn: psycopg.Connection, source_document_id: str, envelope: dict
) -> None:
    """Insert the full parsed graph for one parsed envelope (decision 5/6)."""
    record = envelope["record"]
    case = record["case"]
    docket_number = record["docket_number"]
    derived = _derive_court_type(docket_number)
    if derived is None:
        # Not a parsed.warnings row: the warning vocabulary is closed (11 codes).
        # A logged, hash-prefix-only warning per decision 6.
        logger.warning(
            "docket-number prefix not CP-/MC-; court_type_derived set NULL",
            extra={"file": envelope["source_sha256"][:16]},
        )

    cross_court = case["cross_court_dockets"]
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO parsed.dockets
              (source_document_id, docket_number, record_parser_version,
               envelope_parser_version, parsed_at, county, court_type_recorded,
               court_type_derived, case_status, filed_date, otn, dc_number,
               cross_court_dockets, defendant_hash, assigned_judge_raw,
               envelope_status, review_needed, loaded_at)
            VALUES
              (%(source_document_id)s, %(docket_number)s, %(record_parser_version)s,
               %(envelope_parser_version)s, %(parsed_at)s, %(county)s,
               %(court_type_recorded)s, %(court_type_derived)s, %(case_status)s,
               %(filed_date)s, %(otn)s, %(dc_number)s, %(cross_court_dockets)s,
               %(defendant_hash)s, %(assigned_judge_raw)s, %(envelope_status)s,
               %(review_needed)s, now())
            RETURNING id
            """,
            {
                "source_document_id": source_document_id,
                "docket_number": docket_number,
                "record_parser_version": record["parser_version"],
                "envelope_parser_version": envelope["parser_version"],
                "parsed_at": record["parsed_at"],
                "county": case["county"],
                "court_type_recorded": case["court_type"],
                "court_type_derived": derived,
                "case_status": case["case_status"],
                "filed_date": case["filed_date"],
                "otn": case["otn"],
                "dc_number": case["dc_number"],
                "cross_court_dockets": None
                if cross_court is None
                else Json(cross_court),
                "defendant_hash": case["defendant_hash"],
                "assigned_judge_raw": case["assigned_judge_raw"],
                "envelope_status": envelope["status"],
                "review_needed": envelope["review_needed"],
            },
        )
        docket_row = cur.fetchone()
        assert docket_row is not None
        docket_id = docket_row[0]

        for charge in record["charges"]:
            cur.execute(
                """
                INSERT INTO parsed.charges
                  (docket_id, sequence, statute, grade, offense, disposition_raw,
                   disposition_date, disposition_judge_raw, event_name, event_date)
                VALUES
                  (%(docket_id)s, %(sequence)s, %(statute)s, %(grade)s, %(offense)s,
                   %(disposition_raw)s, %(disposition_date)s,
                   %(disposition_judge_raw)s, %(event_name)s, %(event_date)s)
                RETURNING id
                """,
                {
                    "docket_id": docket_id,
                    "sequence": charge["sequence"],
                    "statute": charge["statute"],
                    "grade": charge["grade"],
                    "offense": charge["offense"],
                    "disposition_raw": charge["disposition_raw"],
                    "disposition_date": charge["disposition_date"],
                    "disposition_judge_raw": charge["disposition_judge_raw"],
                    "event_name": charge.get("event_name"),
                    "event_date": charge.get("event_date"),
                },
            )
            charge_row = cur.fetchone()
            assert charge_row is not None
            charge_id = charge_row[0]

            # component_order = the sentence's 0-based position within the charge.
            for order, sentence in enumerate(charge["sentences"]):
                cur.execute(
                    """
                    INSERT INTO parsed.sentences
                      (charge_id, component_order, sentence_type, min_days,
                       max_days, min_assumed, program, sentence_date, raw_text)
                    VALUES
                      (%(charge_id)s, %(component_order)s, %(sentence_type)s,
                       %(min_days)s, %(max_days)s, %(min_assumed)s, %(program)s,
                       %(sentence_date)s, %(raw_text)s)
                    """,
                    {
                        "charge_id": charge_id,
                        "component_order": order,
                        "sentence_type": sentence["sentence_type"],
                        "min_days": sentence["min_days"],
                        "max_days": sentence["max_days"],
                        "min_assumed": sentence.get("min_assumed", False),
                        "program": sentence["program"],
                        "sentence_date": sentence["sentence_date"],
                        "raw_text": sentence["raw_text"],
                    },
                )

        for warning in envelope["warnings"]:
            cur.execute(
                """
                INSERT INTO parsed.warnings
                  (docket_id, code, section, charge_sequence, page, field)
                VALUES
                  (%(docket_id)s, %(code)s, %(section)s, %(charge_sequence)s,
                   %(page)s, %(field)s)
                """,
                {
                    "docket_id": docket_id,
                    "code": warning["code"],
                    "section": warning.get("section"),
                    "charge_sequence": warning.get("charge_sequence"),
                    "page": warning.get("page"),
                    "field": warning.get("field"),
                },
            )

        for related in record["related_cases"]:
            cur.execute(
                """
                INSERT INTO parsed.related_cases
                  (docket_id, docket_number, court, association_reason)
                VALUES
                  (%(docket_id)s, %(docket_number)s, %(court)s,
                   %(association_reason)s)
                """,
                {
                    "docket_id": docket_id,
                    "docket_number": related["docket_number"],
                    "court": related.get("court"),
                    "association_reason": related.get("association_reason"),
                },
            )


def _lookup_existing_docket(
    conn: psycopg.Connection, source_sha256: str
) -> tuple[str, tuple[int, int]] | None:
    """The already-loaded docket for a source hash, or None.

    Returns ``(docket_id, (envelope_parser_version, record_parser_version))``.
    This is the idempotency detection query.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.envelope_parser_version, d.record_parser_version
            FROM raw.source_documents s
            JOIN parsed.dockets d ON d.source_document_id = s.id
            WHERE s.file_hash = %(file_hash)s
            """,
            {"file_hash": source_sha256},
        )
        row = cur.fetchone()
    if row is None:
        return None
    return row[0], (row[1], row[2])


def _norm_date(value: object) -> str | None:
    """Normalize a date column / ISO date string to ``YYYY-MM-DD`` (or None).

    DB DATE columns come back as ``datetime.date`` (``.isoformat()``); envelope
    dates are already ``YYYY-MM-DD`` strings. Both collapse to the same string
    so the equal-version content comparison is representation-independent.
    """
    if value is None:
        return None
    isoformat = getattr(value, "isoformat", None)
    return isoformat() if callable(isoformat) else str(value)


def _envelope_projection(envelope: dict) -> dict:
    """Canonical, comparable projection of a parsed envelope's loadable content.

    Excludes loader-set/processing fields (surrogate ids, ``loaded_at``,
    ``created_at``, and ``parsed_at`` — a parse wall-clock, not court content
    whose timestamptz round-trip would differ from the naive envelope string).
    Child lists are sorted by their canonical JSON so ordering never matters.
    """
    record = envelope["record"]
    case = record["case"]
    charges = []
    for charge in record["charges"]:
        sentences = [
            {
                "component_order": order,
                "sentence_type": sentence["sentence_type"],
                "min_days": sentence["min_days"],
                "max_days": sentence["max_days"],
                "min_assumed": bool(sentence.get("min_assumed", False)),
                "program": sentence["program"],
                "sentence_date": _norm_date(sentence["sentence_date"]),
                "raw_text": sentence["raw_text"],
            }
            for order, sentence in enumerate(charge["sentences"])
        ]
        charges.append(
            {
                "sequence": charge["sequence"],
                "statute": charge["statute"],
                "grade": charge["grade"],
                "offense": charge["offense"],
                "disposition_raw": charge["disposition_raw"],
                "disposition_date": _norm_date(charge["disposition_date"]),
                "disposition_judge_raw": charge["disposition_judge_raw"],
                "event_name": charge.get("event_name"),
                "event_date": _norm_date(charge.get("event_date")),
                "sentences": _sorted_json(sentences),
            }
        )
    warnings = [
        {
            "code": warning["code"],
            "section": warning.get("section"),
            "charge_sequence": warning.get("charge_sequence"),
            "page": warning.get("page"),
            "field": warning.get("field"),
        }
        for warning in envelope["warnings"]
    ]
    related = [
        {
            "docket_number": rc["docket_number"],
            "court": rc.get("court"),
            "association_reason": rc.get("association_reason"),
        }
        for rc in record["related_cases"]
    ]
    return _assemble_projection(
        docket_number=record["docket_number"],
        record_parser_version=record["parser_version"],
        envelope_parser_version=envelope["parser_version"],
        envelope_status=envelope["status"],
        review_needed=bool(envelope["review_needed"]),
        county=case["county"],
        court_type_recorded=case["court_type"],
        court_type_derived=_derive_court_type(record["docket_number"]),
        case_status=case["case_status"],
        filed_date=_norm_date(case["filed_date"]),
        otn=case["otn"],
        dc_number=case["dc_number"],
        cross_court_dockets=case["cross_court_dockets"],
        defendant_hash=case["defendant_hash"],
        assigned_judge_raw=case["assigned_judge_raw"],
        charges=charges,
        warnings=warnings,
        related=related,
    )


def _db_projection(conn: psycopg.Connection, docket_id: str) -> dict:
    """The same canonical projection, reconstructed from the stored rows."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT docket_number, record_parser_version, envelope_parser_version,
                   county, court_type_recorded, court_type_derived, case_status,
                   filed_date, otn, dc_number, cross_court_dockets, defendant_hash,
                   assigned_judge_raw, envelope_status, review_needed
            FROM parsed.dockets WHERE id = %(id)s
            """,
            {"id": docket_id},
        )
        docket = cur.fetchone()
        assert docket is not None
        cur.execute(
            """
            SELECT id, sequence, statute, grade, offense, disposition_raw,
                   disposition_date, disposition_judge_raw, event_name, event_date
            FROM parsed.charges WHERE docket_id = %(id)s
            """,
            {"id": docket_id},
        )
        charge_rows = cur.fetchall()
        charges = []
        for charge in charge_rows:
            cur.execute(
                """
                SELECT component_order, sentence_type, min_days, max_days,
                       min_assumed, program, sentence_date, raw_text
                FROM parsed.sentences WHERE charge_id = %(id)s
                """,
                {"id": charge["id"]},
            )
            sentences = [
                {
                    "component_order": s["component_order"],
                    "sentence_type": s["sentence_type"],
                    "min_days": s["min_days"],
                    "max_days": s["max_days"],
                    "min_assumed": bool(s["min_assumed"]),
                    "program": s["program"],
                    "sentence_date": _norm_date(s["sentence_date"]),
                    "raw_text": s["raw_text"],
                }
                for s in cur.fetchall()
            ]
            charges.append(
                {
                    "sequence": charge["sequence"],
                    "statute": charge["statute"],
                    "grade": charge["grade"],
                    "offense": charge["offense"],
                    "disposition_raw": charge["disposition_raw"],
                    "disposition_date": _norm_date(charge["disposition_date"]),
                    "disposition_judge_raw": charge["disposition_judge_raw"],
                    "event_name": charge["event_name"],
                    "event_date": _norm_date(charge["event_date"]),
                    "sentences": _sorted_json(sentences),
                }
            )
        cur.execute(
            """
            SELECT code, section, charge_sequence, page, field
            FROM parsed.warnings WHERE docket_id = %(id)s
            """,
            {"id": docket_id},
        )
        warnings = [dict(w) for w in cur.fetchall()]
        cur.execute(
            """
            SELECT docket_number, court, association_reason
            FROM parsed.related_cases WHERE docket_id = %(id)s
            """,
            {"id": docket_id},
        )
        related = [dict(r) for r in cur.fetchall()]

    return _assemble_projection(
        docket_number=docket["docket_number"],
        record_parser_version=docket["record_parser_version"],
        envelope_parser_version=docket["envelope_parser_version"],
        envelope_status=docket["envelope_status"],
        review_needed=bool(docket["review_needed"]),
        county=docket["county"],
        court_type_recorded=docket["court_type_recorded"],
        court_type_derived=docket["court_type_derived"],
        case_status=docket["case_status"],
        filed_date=_norm_date(docket["filed_date"]),
        otn=docket["otn"],
        dc_number=docket["dc_number"],
        cross_court_dockets=docket["cross_court_dockets"],
        defendant_hash=docket["defendant_hash"],
        assigned_judge_raw=docket["assigned_judge_raw"],
        charges=charges,
        warnings=warnings,
        related=related,
    )


def _assemble_projection(
    *, charges: list, warnings: list, related: list, **scalar
) -> dict:
    """Assemble a projection dict with child lists sorted by canonical JSON."""
    return {
        **scalar,
        "charges": _sorted_json(charges),
        "warnings": _sorted_json(warnings),
        "related_cases": _sorted_json(related),
    }


def _sorted_json(items: list[dict]) -> list[dict]:
    """Order a list of dicts deterministically by canonical JSON (None-safe)."""
    return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))


def _content_matches(conn: psycopg.Connection, docket_id: str, envelope: dict) -> bool:
    """True iff the stored docket's content equals the incoming envelope's.

    The equal-version arm of decision 3: identical content -> skip (zero writes);
    a difference -> the caller rejects and stop-reports. Compares the two
    canonical projections, so it needs no content-hash column (schema frozen).
    """
    return _db_projection(conn, docket_id) == _envelope_projection(envelope)


def _load_one(
    conn: psycopg.Connection, envelope: dict, import_metadata_dir: Path
) -> str:
    """Load one envelope inside the caller's per-docket transaction.

    Returns the run-report category. Raises ``_LoaderReject`` for a deliberate
    per-docket rejection (rolled back, counted ``failed_exception``).
    """
    version = envelope.get("parser_version")
    if version not in ACCEPTED_ENVELOPE_VERSIONS:
        raise _LoaderReject(_REASON_UNRECOGNIZED_VERSION)

    source_sha256 = envelope["source_sha256"]
    import_record = _read_import_record(import_metadata_dir, source_sha256)
    if import_record is None:
        return MISSING_IMPORT_RECORD

    if envelope["status"] == PARSE_STATUS_FAILED:
        error = envelope.get("error") or {}
        _upsert_source_document(
            conn,
            source_sha256=source_sha256,
            import_record=import_record,
            status=STATUS_PARSE_FAILED,
            error_code=error.get("code"),
        )
        return FAILED_ENVELOPE_LOADED

    record = envelope["record"]
    incoming = (version, record["parser_version"])
    existing = _lookup_existing_docket(conn, source_sha256)

    if existing is None:
        source_document_id = _upsert_source_document(
            conn,
            source_sha256=source_sha256,
            import_record=import_record,
            status=import_record["status"],
            error_code=import_record["error_code"],
        )
        _insert_parsed_graph(conn, source_document_id, envelope)
        return LOADED

    docket_id, stored = existing
    if incoming == stored:
        if _content_matches(conn, docket_id, envelope):
            return SKIPPED_SAME_VERSION
        raise _LoaderReject(_REASON_CONTENT_MISMATCH)

    if incoming > stored:
        with conn.cursor() as cur:
            # CASCADE clears the parsed children; RESTRICT to raw is untouched.
            cur.execute(
                "DELETE FROM parsed.dockets WHERE id = %(id)s", {"id": docket_id}
            )
        source_document_id = _upsert_source_document(
            conn,
            source_sha256=source_sha256,
            import_record=import_record,
            status=import_record["status"],
            error_code=import_record["error_code"],
        )
        _insert_parsed_graph(conn, source_document_id, envelope)
        return REPLACED_NEWER_VERSION

    # incoming < stored: never downgrade (decision 3).
    logger.warning(
        "refusing envelope-version downgrade; no rows written",
        extra={"file": source_sha256[:16]},
    )
    return REFUSED_OLDER_VERSION


def run_load(
    envelopes_dir: Path, import_metadata_dir: Path, conn: psycopg.Connection
) -> int:
    """Load every ``*.json`` envelope under ``envelopes_dir`` into the DB.

    One transaction per docket, per-docket exception isolation, idempotent by
    source hash + version. Prints a counts-only run report whose seven categories
    reconcile to the envelope count. Returns 0 when the run is clean, nonzero when
    any envelope hit an unhealthy category (per-docket failure or missing import
    record) — fail-loud. Console/logs carry counts, statuses, fixed reason codes,
    and hash-prefix ids only.
    """
    if not envelopes_dir.is_dir():
        logger.error(
            "envelopes dir does not exist or is not a directory",
            extra={"envelopes_dir": str(envelopes_dir)},
        )
        return 2
    if not import_metadata_dir.is_dir():
        logger.error(
            "import-metadata dir does not exist or is not a directory",
            extra={"import_metadata_dir": str(import_metadata_dir)},
        )
        return 2
    envelope_paths = sorted(envelopes_dir.glob("*.json"))
    if not envelope_paths:
        logger.error(
            "envelopes dir contains no *.json envelope artifacts",
            extra={"envelopes_dir": str(envelopes_dir)},
        )
        return 2

    logger.info("starting load", extra={"file_count": len(envelope_paths)})
    counts = {category: 0 for category in _CATEGORY_ORDER}

    for envelope_path in envelope_paths:
        try:
            envelope = json.loads(envelope_path.read_text())
            prefix = str(envelope["source_sha256"])[:16]
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            counts[FAILED_EXCEPTION] += 1
            logger.warning(
                "skipped unreadable/invalid envelope artifact",
                extra={"error_type": type(exc).__name__},
            )
            continue

        try:
            with conn.transaction():
                category = _load_one(conn, envelope, import_metadata_dir)
        except _LoaderReject as exc:
            counts[FAILED_EXCEPTION] += 1
            logger.warning(
                "docket rejected", extra={"file": prefix, "reason": exc.reason}
            )
            continue
        except Exception as exc:  # noqa: BLE001 - per-docket isolation (decision 2)
            counts[FAILED_EXCEPTION] += 1
            logger.warning(
                "docket failed during load",
                extra={"file": prefix, "error_type": type(exc).__name__},
            )
            continue

        counts[category] += 1
        logger.info("processed", extra={"file": prefix, "outcome": category})

    total = sum(counts.values())
    summary = " ".join(f"{category}={counts[category]}" for category in _CATEGORY_ORDER)
    print(f"{summary} total={total}")
    logger.info("load complete", extra={"file_count": len(envelope_paths)})

    unhealthy = sum(counts[category] for category in _UNHEALTHY_CATEGORIES)
    return 0 if unhealthy == 0 else 1
