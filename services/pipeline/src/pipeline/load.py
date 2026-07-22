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

Supersession (Task COL-4a): a NEW source hash whose ``(docket_number,
court_type_derived)`` matches an already-loaded docket replaces that docket's
parsed graph — delete old graph + insert new graph in the same per-docket
transaction, unconditionally on the new hash (parser versions gate only the
same-hash arms above). The old ``raw.source_documents`` row is KEPT as
provenance with ``status = 'parse_superseded'``; its non-terminal review items
close out as ``superseded`` (triage state never transfers to the new parse). A
regression guard flags (never blocks) a superseding parse that shrank charges
or lost a disposition: warning + one ``supersession_regression`` review item
anchored to the NEW source document. Supersession is blocked fail-loud when
``fact.*`` rows still reference the old graph (RESTRICT FKs): the per-docket
rejection names ``pipeline prune-fact-runs`` as the remedy.

Stale-skip (COL-4a, plan-approved): envelope artifacts accumulate one file per
source hash, so after a supersession a full-dir re-load still sees the LOSING
envelope. An incoming envelope whose OWN raw row is already marked
``parse_superseded`` is a stale artifact of a fetch that lost — skipped with
zero writes (``skipped_stale_superseded``, healthy). Without this arm the old
and new envelopes would supersede each other back and forth on every full-dir
re-load; with it, a full canonical re-load after any supersession is a no-op.

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
from pipeline.fact_review_vocab import (
    REVIEW_NEEDED,
    SEVERITY_HIGH,
    STATUS_IN_REVIEW,
    STATUS_OPEN,
    STATUS_SUPERSEDED,
    SUPERSESSION_REGRESSION,
)
from pipeline.normalization.review_items import build_review_item

logger = logging.getLogger("pipeline.load")

# The envelope format versions this loader accepts (21.3 pinned set). Anything
# else -> per-docket failure, never a guess (AC2). Pinned literally to the
# current corpus version rather than tracking ENVELOPE_PARSER_VERSION so a
# future format bump cannot silently widen what this task's loader accepts.
# 32.2: moved {5} -> {6} with the event-line date fix, so the version tuple's
# newer-version arm transactionally replaces each docket's parsed graph at the
# 32.4 reload cycle. 34.4: moved {6} -> {7} with the Phase 34 hardening batch;
# the 34.5 rerun's reloads take the newer-version arm the same way. Stage-D
# unblock: moved {7} -> {8} with the 34.3-guard orphaned-sentence suppression;
# the v8 full-corpus reload takes the newer-version arm the same way.
ACCEPTED_ENVELOPE_VERSIONS: frozenset[int] = frozenset({8})

# The raw.source_documents.status value the loader writes for a failed-parse
# envelope. The 16.3 import-stage vocabulary (imported/duplicate/invalid/failed,
# in manual_import.py) describes the IMPORT outcome; this value describes the
# PARSE outcome at load time and is owned here (documented in the README note).
STATUS_PARSE_FAILED = "parse_failed"

# The raw.source_documents.status value for a document whose parsed graph was
# replaced by a docket supersession (COL-4a, pinned decision 2). The row itself
# is KEPT as provenance; only its status records the superseded parse. Same
# ownership pattern as STATUS_PARSE_FAILED above.
STATUS_PARSE_SUPERSEDED = "parse_superseded"

# The nine run-report categories (Required Fix 3; COL-4a adds `superseded` and
# `skipped_stale_superseded`). Every envelope lands in exactly one; the totals
# reconcile to the envelope count.
LOADED = "loaded"
SKIPPED_SAME_VERSION = "skipped_same_version"
REPLACED_NEWER_VERSION = "replaced_newer_version"
REFUSED_OLDER_VERSION = "refused_older_version"
SUPERSEDED = "superseded"
SKIPPED_STALE_SUPERSEDED = "skipped_stale_superseded"
FAILED_ENVELOPE_LOADED = "failed_envelope_loaded"
FAILED_EXCEPTION = "failed_exception"
MISSING_IMPORT_RECORD = "missing_import_record"

_CATEGORY_ORDER = (
    LOADED,
    SKIPPED_SAME_VERSION,
    REPLACED_NEWER_VERSION,
    REFUSED_OLDER_VERSION,
    SUPERSEDED,
    SKIPPED_STALE_SUPERSEDED,
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
_REASON_SUPERSESSION_BLOCKED = "supersession_blocked_by_fact_rows"


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
) -> str:
    """Insert the full parsed graph for one parsed envelope (decision 5/6).

    Returns the new ``parsed.dockets`` id (the supersession guard's review item
    stores it as ``parsed_docket_id``).
    """
    record = envelope["record"]
    case = record["case"]
    docket_number = record["docket_number"]
    derived = _derive_court_type(docket_number)
    if derived is None:
        # Not a parsed.warnings row: the warning vocabulary is closed (the
        # warning_codes module is the single source of truth for its members).
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

    return docket_id


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


def _lookup_docket_by_identity(
    conn: psycopg.Connection, docket_number: str, court_type_derived: str | None
) -> tuple[str, str] | None:
    """The already-loaded docket for ``(docket_number, court)``, or None.

    The supersession identity key (COL-4a pinned decision 4). Returns
    ``(docket_id, source_document_id)`` of the OLD graph. NULL-safe on
    ``court_type_derived`` (a non-CP/MC prefix derives None on both sides).
    R2-verified: the loaded corpus has at most one parsed row per docket number.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.source_document_id
            FROM parsed.dockets d
            WHERE d.docket_number = %(docket_number)s
              AND d.court_type_derived IS NOT DISTINCT FROM %(court_type_derived)s
            """,
            {
                "docket_number": docket_number,
                "court_type_derived": court_type_derived,
            },
        )
        row = cur.fetchone()
    if row is None:
        return None
    return row[0], row[1]


def _incoming_parse_superseded(conn: psycopg.Connection, source_sha256: str) -> bool:
    """True iff the incoming hash's own raw row is marked ``parse_superseded``.

    The stale-skip predicate (plan-approved): supersession marks the losing
    document's status, and the loser's envelope can never win again. Reached
    only when the hash has no parsed row (the same-hash arms catch it first).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT status FROM raw.source_documents WHERE file_hash = %(hash)s",
            {"hash": source_sha256},
        )
        row = cur.fetchone()
    return row is not None and row[0] == STATUS_PARSE_SUPERSEDED


def _fact_rows_reference_docket(conn: psycopg.Connection, docket_id: str) -> bool:
    """True iff any fact row still references the docket's parsed graph.

    The AC-14 pre-check: fact.* -> parsed.* FKs are RESTRICT by pinned design
    (fail-loud; run history is append-only), so a supersession delete would
    raise. Checking ``fact.charge_outcomes`` alone is sufficient — every
    ``fact.charge_sentences`` row has a NOT NULL parent outcome on the same
    docket's charge. Any residual FK race still fails loudly via per-docket
    isolation.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
              SELECT 1 FROM fact.charge_outcomes
              WHERE parsed_docket_id = %(docket_id)s
            )
            """,
            {"docket_id": docket_id},
        )
        row = cur.fetchone()
        assert row is not None
        return bool(row[0])


def _detect_regression(
    conn: psycopg.Connection, old_docket_id: str, envelope: dict
) -> dict | None:
    """Structural regression context for the guard, or None when clean.

    Pinned decision 3: the new parse regressed when it has FEWER charges than
    the old, or a previously disposed charge (non-null ``disposition_raw``) is
    now absent or undisposed at the same sequence. Read BEFORE the old graph is
    deleted. Everything returned is structural (counts, sequences, sub-case
    slugs) — never docket text.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT sequence, disposition_raw IS NOT NULL AS disposed
            FROM parsed.charges WHERE docket_id = %(id)s
            """,
            {"id": old_docket_id},
        )
        old_rows = cur.fetchall()
    old_disposed = {row[0] for row in old_rows if row[1]}

    new_charges = envelope["record"]["charges"]
    new_disposed = {
        charge["sequence"]
        for charge in new_charges
        if charge["disposition_raw"] is not None
    }

    subcases = []
    if len(new_charges) < len(old_rows):
        subcases.append("charge_shrink")
    lost = sorted(old_disposed - new_disposed)
    if lost:
        subcases.append("disposition_loss")
    if not subcases:
        return None
    return {
        "old_charge_count": len(old_rows),
        "new_charge_count": len(new_charges),
        "lost_disposition_sequences": lost,
        "subcases": subcases,
    }


def _close_out_review_items(conn: psycopg.Connection, source_document_id: str) -> int:
    """Close every non-terminal review item anchored to a superseded document.

    R1 mechanism (plan-approved): ``open`` and ``in_review`` items transition to
    the terminal ``superseded`` status; ``resolved``/``dismissed`` are already
    terminal and stay untouched. Triage state never transfers to the superseding
    document's items — the next fact build regenerates those fresh under new
    dedup keys (which incorporate the NEW source_document_id). Returns the count
    of items closed out.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE review.queue_items
            SET status = %(superseded)s
            WHERE source_document_id = %(source_document_id)s
              AND status IN (%(open)s, %(in_review)s)
            """,
            {
                "superseded": STATUS_SUPERSEDED,
                "source_document_id": source_document_id,
                "open": STATUS_OPEN,
                "in_review": STATUS_IN_REVIEW,
            },
        )
        return cur.rowcount


def _insert_regression_review_item(
    conn: psycopg.Connection,
    *,
    new_source_document_id: str,
    new_docket_id: str,
    regression: dict,
) -> None:
    """Insert the guard's ``supersession_regression`` review item (AC-2).

    One docket-scoped item per superseding document (both sub-cases share it,
    distinguished by ``candidate_context`` — the 23.5 precedent), anchored to
    the NEW source document so its dedup key is stable for THIS supersession
    and a later third fetch re-flags independently. ``ON CONFLICT DO NOTHING``
    keeps the write idempotent (the 23.4 insert semantics).
    """
    # psycopg returns uuid.UUID ids; the dedup-key builder requires strings.
    item = build_review_item(
        source_document_id=str(new_source_document_id),
        item_type=SUPERSESSION_REGRESSION,
        severity=SEVERITY_HIGH,
        reason_code=REVIEW_NEEDED,
        parsed_docket_id=str(new_docket_id),
        candidate_context=regression,
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO review.queue_items
              (item_type, severity, source_document_id, parsed_docket_id,
               parsed_charge_id, parsed_sentence_id, entity_type, raw_value,
               candidate_context, reason_code, status, dedup_key)
            VALUES
              (%(item_type)s, %(severity)s, %(source_document_id)s,
               %(parsed_docket_id)s, %(parsed_charge_id)s, %(parsed_sentence_id)s,
               %(entity_type)s, %(raw_value)s, %(candidate_context)s,
               %(reason_code)s, %(status)s, %(dedup_key)s)
            ON CONFLICT (dedup_key) DO NOTHING
            """,
            {**item, "candidate_context": Json(item["candidate_context"])},
        )


def _supersede(
    conn: psycopg.Connection,
    envelope: dict,
    import_record: dict,
    old_docket_id: str,
    old_source_document_id: str,
) -> str:
    """Replace the old parsed graph with the new envelope's (COL-4a).

    Runs inside the caller's per-docket transaction: guard read, review-item
    close-out, old-graph delete (CASCADE clears children and docket_links; the
    linker re-resolves at the next build — R4), old raw row marked
    ``parse_superseded`` (KEPT — pinned decision 2), new raw row upserted, new
    graph inserted. Replacement is unconditional on the new hash (pinned
    decision 3); the guard flags, never blocks.
    """
    source_sha256 = envelope["source_sha256"]
    if _fact_rows_reference_docket(conn, old_docket_id):
        # Fail-loud by design (R3 adjudication): the RESTRICT FKs stay, and the
        # remedy is the conscious whole-run prune, never a silent auto-prune.
        logger.warning(
            "supersession blocked: fact rows still reference the existing "
            "parsed graph; prune fact build runs first "
            "(`pipeline prune-fact-runs`), then re-run the load",
            extra={"file": source_sha256[:16]},
        )
        raise _LoaderReject(_REASON_SUPERSESSION_BLOCKED)

    regression = _detect_regression(conn, old_docket_id, envelope)
    closed_out = _close_out_review_items(conn, old_source_document_id)

    with conn.cursor() as cur:
        # CASCADE clears the parsed children (and docket_links, rebuilt at the
        # next build-facts); the raw row is deliberately kept as provenance.
        cur.execute(
            "DELETE FROM parsed.dockets WHERE id = %(id)s", {"id": old_docket_id}
        )
        cur.execute(
            "UPDATE raw.source_documents SET status = %(status)s WHERE id = %(id)s",
            {"status": STATUS_PARSE_SUPERSEDED, "id": old_source_document_id},
        )

    new_source_document_id = _upsert_source_document(
        conn,
        source_sha256=source_sha256,
        import_record=import_record,
        status=import_record["status"],
        error_code=import_record["error_code"],
    )
    new_docket_id = _insert_parsed_graph(conn, new_source_document_id, envelope)

    if regression is not None:
        logger.warning(
            "supersession regression: replacement proceeded; review item filed",
            extra={
                "file": source_sha256[:16],
                "subcases": ",".join(regression["subcases"]),
                "old_charge_count": regression["old_charge_count"],
                "new_charge_count": regression["new_charge_count"],
            },
        )
        _insert_regression_review_item(
            conn,
            new_source_document_id=new_source_document_id,
            new_docket_id=new_docket_id,
            regression=regression,
        )

    logger.info(
        "superseded parsed graph",
        extra={"file": source_sha256[:16], "review_items_closed": closed_out},
    )
    return SUPERSEDED


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
        # Stale-skip (COL-4a): a hash whose OWN raw row is already marked
        # parse_superseded lost a supersession; its envelope artifact is stale
        # and must never supersede the winner back (full-dir re-load safety).
        if _incoming_parse_superseded(conn, source_sha256):
            logger.info(
                "skipping stale envelope of a superseded parse; no rows written",
                extra={"file": source_sha256[:16]},
            )
            return SKIPPED_STALE_SUPERSEDED

        # New source hash. Same (docket_number, court) already loaded from a
        # DIFFERENT document -> supersession (COL-4a); otherwise a fresh load.
        docket_number = record["docket_number"]
        superseded = _lookup_docket_by_identity(
            conn, docket_number, _derive_court_type(docket_number)
        )
        if superseded is not None:
            old_docket_id, old_source_document_id = superseded
            return _supersede(
                conn, envelope, import_record, old_docket_id, old_source_document_id
            )
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
            # KNOWN-LATENT (COL-4a adjudication): if fact.* rows still reference
            # this graph, the RESTRICT FKs make this DELETE fail loudly — by
            # design, not separately guarded here. The remedy is the same
            # prune-first ordering as supersession (`pipeline prune-fact-runs`).
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
    source hash + version. Prints a counts-only run report whose nine categories
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
