"""Tier-1 fixture-corpus test support (Task 19.1).

Shared, deterministic helpers for the committed synthetic regression corpus:
the fixed public test salt, the fixture/page loader, the golden PROJECTION
builder, golden IO, and a readable field-level diff. Imported by the tier-1
tests and by ``generate_goldens.py``. Contains NO ``test_*`` functions, so
pytest never collects it as a test module.

Golden projection (pinned decision 3, as approved at plan review): a golden is
the DETERMINISTIC subset of what the parse pipeline produces for one fixture --
``status``, the ``record`` with its non-deterministic ``parsed_at`` dropped, the
full ``warnings`` list, the derived ``review_needed`` boolean, and (on a failed
parse) the structural ``error``. Warnings and ``review_needed`` are composed
EXACTLY as ``pipeline.envelope.parse_document`` composes them -- the observation
layer (``observe``) plus the parser's own structural warnings -- so the corpus
exercises the real envelope semantics without persisting an envelope or its
non-deterministic id/timestamp fields. ``extraction_status`` is fixed at
``STATUS_SUCCESS`` so ``LOW_TEXT_EXTRACTION`` (an extraction-stage signal) never
fires from a text fixture (it is never faked).

Everything here is offline and repo-local; nothing reaches the local-only real
corpus root.
"""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.docket_parser import parse_docket_text
from pipeline.envelope import observe
from pipeline.extraction import STATUS_SUCCESS
from pipeline.warning_codes import (
    UNSUPPORTED_FORMAT,
    derive_review_needed,
)

# The FIXED public test salt (pinned decision 2). NEVER the real
# DEFENDANT_HASH_SALT: committed hashes derive from fictional names + this
# public constant, so they leak nothing and regeneration is reproducible.
TIER1_TEST_SALT = "tier1-fixture-salt"

# Placeholder dockets (all-zeros sequence). The parser is passed the docket
# number explicitly (it never reads it from the page text), so generation
# supplies one per court. Both are placeholder-hygiene-clean by construction.
DOCKET_CP = "CP-51-CR-0000000-2025"
DOCKET_MC = "MC-51-CR-0000000-2025"

# Multi-page fixtures separate ordered page texts with this exact delimiter line
# (single-page fixtures contain none). Kept as a visible, greppable marker so the
# hygiene scan stays a plain-text search.
PAGE_DELIM = "=== PAGE BREAK ==="

THIS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = THIS_DIR / "fixtures"
GOLDENS_DIR = THIS_DIR / "goldens"
INDEX_PATH = THIS_DIR / "fixture-index.yaml"


def docket_for_court(court_type: str) -> str:
    """Placeholder docket number for a fixture's court_type."""
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

    Pages are split on the ``PAGE_DELIM`` line; a single-page fixture yields a
    one-element list. The parser consumes this list exactly as it consumes real
    extracted page text.
    """
    text = (FIXTURES_DIR / fixture_filename).read_text()
    if PAGE_DELIM in text:
        parts = text.split(PAGE_DELIM + "\n")
        return [part.rstrip("\n") for part in parts]
    return [text.rstrip("\n")]


def build_golden(docket_number: str, pages: list[str]) -> dict:
    """Build the deterministic golden projection for one fixture.

    Mirrors ``pipeline.envelope.parse_document``'s warning composition and
    ``review_needed`` derivation, but keeps only the deterministic, id-free
    fields and drops the record's ``parsed_at`` timestamp. On ANY parse-time
    exception, returns the ``failed`` projection with the structural error arm
    (code + exception class name only).
    """
    try:
        record, _sentinels, parser_warnings = parse_docket_text(
            docket_number, pages, salt=TIER1_TEST_SALT
        )
    except Exception as exc:  # noqa: BLE001 - any parse failure is a failed projection
        codes = [UNSUPPORTED_FORMAT]
        return {
            "status": "failed",
            "record": None,
            "warnings": [],
            "review_needed": derive_review_needed(codes),
            "error": {
                "code": UNSUPPORTED_FORMAT,
                "exception_class": type(exc).__name__,
            },
        }

    warnings = observe(record, extraction_status=STATUS_SUCCESS) + parser_warnings
    codes = [str(w["code"]) for w in warnings]
    record = dict(record)
    record.pop("parsed_at", None)
    return {
        "status": "parsed",
        "record": record,
        "warnings": warnings,
        "review_needed": derive_review_needed(codes),
        "error": None,
    }


def golden_bytes(golden: dict) -> str:
    """Serialize a golden deterministically (sorted keys, trailing newline)."""
    return json.dumps(golden, indent=2, sort_keys=True) + "\n"


def load_golden(fixture_filename: str) -> dict:
    """Load a committed golden by its paired fixture filename."""
    path = GOLDENS_DIR / golden_filename(fixture_filename)
    return json.loads(path.read_text())


def diff_fields(want, got, path: str = "") -> list[str]:
    """Recursive field-level diff between a golden (``want``) and a fresh parse
    (``got``). Returns readable ``path: want=<...> got=<...>`` lines; empty when
    equal. Used to make a regression failure legible instead of dumping blobs."""
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
