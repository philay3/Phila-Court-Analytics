"""
Pseudonymous identity: the only code that ever touches a defendant name or
DOB. The parser (phase 3) and the loader (phase 4) both import from here so
the hash is identical everywhere. Names exist in memory only; nothing in
this module logs, prints, or stores them.

The salt is supplied explicitly by the caller (a required keyword-only
parameter). This module reads no environment and has no import-time side
effects; env reading happens only at the CLI boundary.
"""

from __future__ import annotations

import hashlib
import re


def normalize_name(name: str) -> str:
    lowered = name.lower()
    letters_only = re.sub(r"[^a-z\s]", " ", lowered)
    return re.sub(r"\s+", " ", letters_only).strip()


def hash_defendant(name: str, birth_year: int, *, salt: str) -> str:
    if not salt or not salt.strip():
        raise ValueError(
            "DEFENDANT_HASH_SALT is required: the salt parameter must be a "
            "non-empty string. There is no default salt."
        )
    basis = f"{salt}|{normalize_name(name)}|{birth_year}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _iter_values(obj):
    """Yield every leaf VALUE in a record, recursively, coerced to str. Key
    names are never yielded: they are structural constants defined in the
    parser, never derived from document text (proven by the key-allowlist
    unit test), so scanning them only produces false positives when a
    defendant name fragment coincides with a key substring."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_values(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _iter_values(v)
    elif obj is None:
        return
    else:
        yield str(obj)


def assert_no_leak(sentinels: list[str], record) -> None:
    """Hard stop if any identifying string appears in a record's VALUES.

    Scans values only, recursively across nested dicts and lists; key names
    are never scanned (they are structural constants, never document text).
    This keeps the check from tripping on a defendant name fragment that
    coincides with a structural key substring (for example a 4-letter fragment
    inside "cross_court_dockets") while still catching any real name or DOB
    that reaches a value. A bare str may be passed and is treated as one value.

    Sentinels are the defendant's printed name, its parts, and the DOB
    string. A collision (for example, a defendant who shares a surname with
    the judge) raises too; that is intentional. Investigate, record the
    collision in notes, and require owner confirmation before writing.
    """
    hay = " ".join(_iter_values(record)).lower()
    for s in sentinels:
        s = s.strip()
        if len(s) >= 3 and s.lower() in hay:
            raise RuntimeError(
                "privacy assertion failed: identifying string found in output"
            )


RELATED_CASE_KEYS = {"docket_number", "court", "association_reason"}


def assert_related_cases_clean(record: dict) -> None:
    """Structural half of the privacy assertion for Phase 7 MC sheets.

    A related-cases row carries a caption column with third-party names. The
    parser captures only docket number, court, and association reason. This
    guard fails the write if any entry carries a field beyond those three, so a
    caption (or any other stray value) can never reach interim JSON.
    """
    for entry in record.get("related_cases", []):
        extra = set(entry.keys()) - RELATED_CASE_KEYS
        if extra:
            raise RuntimeError(
                "privacy assertion failed: related case entry carries unexpected fields"
            )
