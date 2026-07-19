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


def hash_defendant_name_only(name: str, *, salt: str) -> str:
    """Name-only basis for the MC blank-DOB caption variant (Task 34.4).

    Used ONLY when the parser positively identifies the blank-DOB caption
    signature: same normalization and salt flow as ``hash_defendant``, with the
    DOB component omitted — no sentinel year, no placeholder, no trailing
    separator. Collision note for the record: a name-only basis collides across
    same-name defendants more than name+year; inert, because ``defendant_hash``
    participates in no dedup, supersession, or fact keying. DOB-present
    documents never take this path and hash via ``hash_defendant`` unchanged.
    """
    if not salt or not salt.strip():
        raise ValueError(
            "DEFENDANT_HASH_SALT is required: the salt parameter must be a "
            "non-empty string. There is no default salt."
        )
    basis = f"{salt}|{normalize_name(name)}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def matches_as_token(sentinel: str, text_lower: str) -> bool:
    """True if ``sentinel`` occurs in ``text_lower`` bounded by a non-alphanumeric
    character (or string edge) on BOTH sides — a whole-token, case-insensitive
    containment test (Task 18.3 Q1, replacing the prior >=3-char substring test).

    ``text_lower`` MUST already be lowercased by the caller. Sentinels shorter
    than three characters never match (too collision-prone). A whole-token match
    is a strict subset of a substring match, so this rule can only *unblock*,
    never newly block, relative to the substring test it replaces.

    This is the SINGLE matching rule shared by the post-parse leak backstop
    (``assert_no_leak``) and the parse-time third-party name guard
    (``collides_with_sentinels``), so the guard nulls exactly what the backstop
    would otherwise hard-block.
    """
    s = sentinel.strip().lower()
    if len(s) < 3:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(s) + r"(?![a-z0-9])"
    return re.search(pattern, text_lower) is not None


def collides_with_sentinels(value: str, sentinels: list[str]) -> bool:
    """True if any sentinel occurs as a whole token inside ``value``.

    The parse-time third-party name guard (Task 18.3 Q2) calls this on a
    name-shaped judge-slot capture: a collision means the capture would carry an
    identifying string, so the field is nulled and flagged rather than passed
    through. Same boundary-anchored rule as ``assert_no_leak``, so a caught
    collision is precisely what the post-parse backstop would otherwise block.
    """
    value_lower = value.lower()
    return any(matches_as_token(s, value_lower) for s in sentinels)


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
    Matching is whole-token (boundary-anchored), so a defendant name fragment
    that coincides only with a sub-span of a larger legitimate token no longer
    trips the check, while any real name or DOB reaching a value as its own
    token is still caught (Task 18.3 Q1). A bare str may be passed and is
    treated as one value.

    Sentinels are the defendant's printed name, its parts, and the DOB string.
    This remains the fail-closed BACKSTOP: the parse-time third-party name guard
    (``collides_with_sentinels``) already nulls a colliding value in the known
    judge label contexts, so on a well-formed record this assertion should not
    fire; if it does, an identifying string reached an unguarded value and the
    write must stop.
    """
    hay = " ".join(_iter_values(record)).lower()
    for s in sentinels:
        if matches_as_token(s, hay):
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
